"""Phase 1D R3A: explicit orchestration, disabled/mock providers, authority boundary."""

from __future__ import annotations

import ast
import inspect
import re
import socket
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

import backend.interoperability.ocr_drawing as ocr_drawing
import backend.interoperability.pdf_drawing as pdf_drawing
import backend.interoperability.raster_drawing as raster_drawing
import backend.interoperability.vlm_assist as vlm_assist
import backend.interoperability.vlm_providers as vlm_providers
from backend.interoperability.drawing import (
    CanonicalDrawing,
    DrawingExtractionAuthority,
    DrawingIngestionDiagnostics,
    DrawingIngestionResult,
    DrawingIngestionStatus,
)
from backend.interoperability.vlm_assist import AiAssistedDrawingExtractor
from backend.interoperability.vlm_drawing import (
    DrawingAssistedIngestionResult,
    DrawingVlmAssistConfig,
)
from backend.interoperability.vlm_provider import (
    VlmCapabilities,
    VlmErrorCode,
    VlmLocality,
    VlmProvider,
    VlmRetryPolicy,
    VlmTaskKind,
)
from backend.interoperability.vlm_providers import DisabledVlmProvider, MockVlmProvider
from tests.unit.interoperability.vlm_fixtures import (
    FailingVlmProvider,
    SpyVlmProvider,
    make_identity,
    make_request,
)

_SOURCE_ID = "synthetic::r3a.pdf"
_ENABLED = DrawingVlmAssistConfig(enabled=True)


def _base_result() -> DrawingIngestionResult:
    return DrawingIngestionResult(
        source_id=_SOURCE_ID,
        diagnostics=DrawingIngestionDiagnostics(
            status=DrawingIngestionStatus.VALID,
            format_detected="PDF",
            parser_id="machiningpro.vector-pdf",
            parser_version="1.0.0",
        ),
        document=CanonicalDrawing(drawing_id="pdf-drawing-r3a", source_id=_SOURCE_ID),
    )


def _mock_identity():
    return MockVlmProvider().identity()


def _request(request_id: str = "vlm-req-000000000000000000000001", **kwargs):
    return make_request(request_id, model=_mock_identity(), **kwargs)


def _no_sleep(_seconds: float) -> None:
    return None


def _extractor(provider, **kwargs) -> AiAssistedDrawingExtractor:
    kwargs.setdefault("sleep", _no_sleep)
    return AiAssistedDrawingExtractor(provider, **kwargs)


# ---------------------------------------------------------------------------
# D01 / D02 / D03 — phase boundaries and explicit invocation
# ---------------------------------------------------------------------------


class TestPhaseBoundaries:
    @pytest.mark.parametrize(
        "module", [pdf_drawing, ocr_drawing, raster_drawing], ids=lambda m: m.__name__
    )
    def test_d01_d02_deterministic_modules_never_reference_phase_1d(self, module):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for name in ("vlm_assist", "vlm_providers", "vlm_provider", "vlm_drawing"):
            assert name not in source

    def test_d01_vector_parser_import_graph_excludes_vlm(self):
        from backend.interoperability.pdf_drawing import VectorPdfDrawingParser

        source = inspect.getsource(VectorPdfDrawingParser)
        assert "Vlm" not in source and "vlm" not in source

    def test_d03_parse_does_not_invoke_the_extractor(self, monkeypatch):
        calls: list[str] = []
        monkeypatch.setattr(
            AiAssistedDrawingExtractor,
            "extract_candidates",
            lambda *a, **k: calls.append("called"),
        )
        from backend.interoperability.pdf_drawing import (
            PdfDrawingParser,
            VectorPdfDrawingParser,
        )
        from tests.unit.interoperability.pdf_fixtures import PdfTextSpec, SyntheticPdfBuilder

        builder = SyntheticPdfBuilder()
        builder.add_vector_page(
            texts=(PdfTextSpec(text="25 mm", x=Decimal("40"), y=Decimal("150")),),
            include_image=True,
        )
        payload = builder.build()
        VectorPdfDrawingParser().parse(_SOURCE_ID, "d.pdf", payload)
        PdfDrawingParser().parse(_SOURCE_ID, "d.pdf", payload)
        assert calls == []

    def test_d03_disabled_config_never_calls_the_provider(self):
        spy = SpyVlmProvider(MockVlmProvider([b"{}"]))
        base = _base_result()
        outcome = _extractor(spy).extract_candidates(
            base, [_request()], config=DrawingVlmAssistConfig()
        )
        assert spy.recorded == []
        assert outcome.advisory is None
        assert outcome.result is base


# ---------------------------------------------------------------------------
# D04 / D05 — disabled and mock providers
# ---------------------------------------------------------------------------


class TestDisabledProvider:
    def test_d04_disabled_provider_fails_closed_without_findings(self):
        base = _base_result()
        provider = DisabledVlmProvider()
        request = make_request(model=provider.identity())
        outcome = _extractor(provider).extract_candidates(base, [request], config=_ENABLED)
        assert outcome.result is base
        assert outcome.advisory is not None
        assert outcome.advisory.status is DrawingIngestionStatus.UNSUPPORTED
        assert outcome.advisory.diagnostics == ("VLM_DISABLED",)
        assert outcome.advisory.evidence == () and outcome.advisory.findings == ()

    def test_d04_disabled_provider_is_a_vlm_provider_and_always_raises(self):
        provider = DisabledVlmProvider()
        assert isinstance(provider, VlmProvider)
        from backend.interoperability.vlm_provider import VlmCancellation, VlmProviderError

        with pytest.raises(VlmProviderError) as raised:
            provider.infer(
                make_request(model=provider.identity()),
                deadline_seconds=1.0,
                cancellation=VlmCancellation(),
            )
        assert raised.value.code is VlmErrorCode.DISABLED


class TestMockProvider:
    def test_d05_mock_is_deterministic_and_script_ordered(self):
        def run():
            provider = MockVlmProvider([b"one", b"two"])
            return _extractor(provider).extract_candidates(
                _base_result(),
                [_request("vlm-req-1"), _request("vlm-req-2")],
                config=_ENABLED,
            )

        first, second = run(), run()
        assert first == second
        assert first.advisory.request_count == 2

    def test_d05_mock_is_local_only(self):
        with pytest.raises(ValueError):
            MockVlmProvider(identity=make_identity(locality=VlmLocality.REMOTE))

    def test_d05_mock_exhausted_script_is_unavailable(self):
        outcome = _extractor(MockVlmProvider([])).extract_candidates(
            _base_result(), [_request()], config=_ENABLED
        )
        assert outcome.advisory.status is DrawingIngestionStatus.FAILED
        assert outcome.advisory.diagnostics[0] == "VLM_UNAVAILABLE"

    def test_d05_mock_rejects_invalid_outcomes(self):
        with pytest.raises(TypeError):
            MockVlmProvider(["not-bytes"])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# D07 / D15 — failures, bounded retry, timeout budget
# ---------------------------------------------------------------------------


class TestFailureModel:
    @pytest.mark.parametrize(
        "code",
        [
            VlmErrorCode.UNAVAILABLE,
            VlmErrorCode.TIMEOUT,
            VlmErrorCode.CANCELLED,
            VlmErrorCode.REQUEST_REJECTED,
            VlmErrorCode.RESPONSE_TOO_LARGE,
        ],
    )
    def test_terminal_codes_fail_closed_without_retry(self, code):
        provider = FailingVlmProvider(code, identity=_mock_identity())
        base = _base_result()
        outcome = _extractor(provider).extract_candidates(base, [_request()], config=_ENABLED)
        assert provider.calls == 1
        assert outcome.result is base
        assert outcome.advisory.status is DrawingIngestionStatus.FAILED
        assert outcome.advisory.diagnostics == (f"VLM_{code.value}",)
        assert outcome.advisory.evidence == ()

    def test_unsupported_code_maps_to_unsupported_status(self):
        provider = FailingVlmProvider(VlmErrorCode.UNSUPPORTED, identity=_mock_identity())
        outcome = _extractor(provider).extract_candidates(
            _base_result(), [_request()], config=_ENABLED
        )
        assert outcome.advisory.status is DrawingIngestionStatus.UNSUPPORTED

    def test_d15_retry_is_bounded_and_reports_exhaustion(self):
        provider = FailingVlmProvider(VlmErrorCode.TRANSIENT, identity=_mock_identity())
        sleeps: list[float] = []
        outcome = _extractor(provider, sleep=sleeps.append).extract_candidates(
            _base_result(), [_request()], config=_ENABLED
        )
        assert provider.calls == 2
        assert sleeps == [1.0]
        assert outcome.advisory.diagnostics == ("VLM_TRANSIENT", "VLM_RETRY_EXHAUSTED")
        assert outcome.advisory.status is DrawingIngestionStatus.FAILED

    def test_d15_retry_then_success(self):
        provider = MockVlmProvider([VlmErrorCode.RATE_LIMITED, b"payload"])
        outcome = _extractor(provider).extract_candidates(
            _base_result(), [_request()], config=_ENABLED
        )
        assert provider.call_count == 2
        assert outcome.advisory.status is DrawingIngestionStatus.INSUFFICIENT_DATA
        assert outcome.advisory.diagnostics == ("VLM_RESPONSES_NOT_PARSED",)

    def test_d15_policy_cannot_exceed_config_attempt_limit(self):
        provider = FailingVlmProvider(VlmErrorCode.TRANSIENT, identity=_mock_identity())
        policy = VlmRetryPolicy(
            max_attempts=5, backoff_seconds=tuple(Decimal("0") for _ in range(4))
        )
        _extractor(provider, retry_policy=policy).extract_candidates(
            _base_result(), [_request()], config=_ENABLED
        )
        assert provider.calls == 2  # VlmLimits.attempts_per_request default

    def test_d07_budget_exhaustion_fails_closed(self):
        ticks = iter([0.0, 1000.0, 1000.0])
        provider = MockVlmProvider([b"payload"])
        outcome = _extractor(provider, monotonic=lambda: next(ticks)).extract_candidates(
            _base_result(), [_request()], config=_ENABLED
        )
        assert provider.call_count == 0
        assert outcome.advisory.diagnostics == ("VLM_BUDGET_EXHAUSTED",)

    def test_deadline_is_bounded_by_request_timeout(self):
        spy = SpyVlmProvider(MockVlmProvider([b"payload"]))
        _extractor(spy).extract_candidates(_base_result(), [_request()], config=_ENABLED)
        assert spy.recorded[0].deadline_seconds <= _ENABLED.limits.request_timeout_seconds

    def test_unexpected_provider_exception_is_contained_without_leaking_text(self):
        class _Exploding(MockVlmProvider):
            def infer(self, request, *, deadline_seconds, cancellation):
                raise RuntimeError("secret-token-123 vendor traceback")

        outcome = _extractor(_Exploding()).extract_candidates(
            _base_result(), [_request()], config=_ENABLED
        )
        assert outcome.advisory.diagnostics == ("VLM_PROVIDER_FAILURE",)
        assert "secret" not in repr(outcome)

    @pytest.mark.parametrize(
        ("payload", "code"),
        [(b"", "VLM_RESPONSE_EMPTY"), (b"x" * 300_000, "VLM_RESPONSE_TOO_LARGE")],
        ids=["empty", "oversized"],
    )
    def test_empty_and_oversized_responses_fail_closed(self, payload, code):
        outcome = _extractor(MockVlmProvider([payload])).extract_candidates(
            _base_result(), [_request()], config=_ENABLED
        )
        assert outcome.advisory.status is DrawingIngestionStatus.FAILED
        assert outcome.advisory.diagnostics == (code,)

    def test_request_count_limit_fails_before_any_call(self):
        provider = MockVlmProvider([b"x"] * 3)
        config = DrawingVlmAssistConfig(
            enabled=True,
            limits=type(_ENABLED.limits)(requests_per_document=1),
        )
        outcome = _extractor(provider).extract_candidates(
            _base_result(), [_request("vlm-req-1"), _request("vlm-req-2")], config=config
        )
        assert provider.call_count == 0
        assert outcome.advisory.diagnostics == ("VLM_REQUEST_LIMIT",)

    def test_d16_oversized_input_fails_before_any_call(self):
        capabilities = VlmCapabilities(
            task_kinds=(VlmTaskKind.TRANSCRIBE,),
            max_image_bytes=10,
            max_image_pixels=1,
            structured_output=True,
        )
        provider = MockVlmProvider([b"x"], capabilities=capabilities)
        outcome = _extractor(provider).extract_candidates(
            _base_result(), [_request()], config=_ENABLED
        )
        assert provider.call_count == 0
        assert outcome.advisory.diagnostics == ("VLM_OVERSIZED_INPUT",)

    def test_unsupported_task_is_refused_before_any_call(self):
        capabilities = VlmCapabilities(
            task_kinds=(VlmTaskKind.TRANSCRIBE,),
            max_image_bytes=1_000_000,
            max_image_pixels=1_000_000,
            structured_output=True,
        )
        provider = MockVlmProvider([b"x"], capabilities=capabilities)
        outcome = _extractor(provider).extract_candidates(
            _base_result(),
            [_request(task_kind=VlmTaskKind.GDT_CHARACTERISTIC)],
            config=_ENABLED,
        )
        assert provider.call_count == 0
        assert outcome.advisory.diagnostics == ("VLM_TASK_UNSUPPORTED",)

    def test_mixed_prompt_versions_are_a_programming_error(self):
        other = replace(_request("vlm-req-2"), prompt_contract_version="other")
        mixed = [_request("vlm-req-1"), other]
        with pytest.raises(ValueError):
            _extractor(MockVlmProvider([b"x", b"y"])).extract_candidates(
                _base_result(), mixed, config=_ENABLED
            )


# ---------------------------------------------------------------------------
# Remote / allow-list refusal (no network capability in R3A)
# ---------------------------------------------------------------------------


class TestEgressRefusal:
    def test_remote_provider_is_refused_without_a_call_even_if_allowed(self):
        class _Remote:
            calls = 0
            _identity = make_identity(provider_id="fake.remote", locality=VlmLocality.REMOTE)

            def identity(self):
                return self._identity

            def capabilities(self):
                return MockVlmProvider().capabilities()

            def infer(self, request, *, deadline_seconds, cancellation):
                type(self).calls += 1
                raise AssertionError("remote provider must never be called in R3A")

        config = DrawingVlmAssistConfig(
            enabled=True, allow_remote=True, allowed_provider_ids=("fake.remote",)
        )
        request = make_request(model=_Remote._identity)
        outcome = _extractor(_Remote()).extract_candidates(
            _base_result(), [request], config=config
        )
        assert _Remote.calls == 0
        assert outcome.advisory.status is DrawingIngestionStatus.UNSUPPORTED
        assert outcome.advisory.diagnostics == ("VLM_REMOTE_NOT_SUPPORTED",)

    def test_allow_list_restricts_providers_when_set(self):
        provider = MockVlmProvider([b"x"])
        config = DrawingVlmAssistConfig(enabled=True, allowed_provider_ids=("other.provider",))
        outcome = _extractor(provider).extract_candidates(
            _base_result(), [_request()], config=config
        )
        assert provider.call_count == 0
        assert outcome.advisory.diagnostics == ("VLM_PROVIDER_NOT_ALLOWED",)

    def test_request_model_must_match_provider_identity(self):
        provider = MockVlmProvider([b"x"])
        request = make_request(model=make_identity(provider_id="someone.else"))
        outcome = _extractor(provider).extract_candidates(
            _base_result(), [request], config=_ENABLED
        )
        assert provider.call_count == 0
        assert outcome.advisory.diagnostics == ("VLM_MODEL_MISMATCH",)

    def test_no_sockets_are_opened(self, monkeypatch):
        def _boom(*args, **kwargs):
            raise AssertionError("network access attempted")

        monkeypatch.setattr(socket, "socket", _boom)
        monkeypatch.setattr(socket, "create_connection", _boom)
        outcome = _extractor(MockVlmProvider([b"x"])).extract_candidates(
            _base_result(), [_request()], config=_ENABLED
        )
        assert outcome.advisory.status is DrawingIngestionStatus.INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# D10 / D18 — authority boundary
# ---------------------------------------------------------------------------


class TestAuthorityBoundary:
    def test_authority_constants(self):
        assert vlm_assist.AI_DEFAULT_AUTHORITY is DrawingExtractionAuthority.ADVISORY
        assert vlm_assist.AUTO_PROMOTION_ALLOWED is False
        assert vlm_assist.DETERMINISTIC_EVIDENCE_OVERWRITE_ALLOWED is False

    def test_d10_deterministic_result_is_carried_unchanged_for_every_outcome(self):
        outcomes = [
            _extractor(DisabledVlmProvider()).extract_candidates(
                base := _base_result(),
                [make_request(model=DisabledVlmProvider().identity())],
                config=_ENABLED,
            ),
            _extractor(MockVlmProvider([b"x"])).extract_candidates(
                base2 := _base_result(), [_request()], config=_ENABLED
            ),
            _extractor(MockVlmProvider([])).extract_candidates(
                base3 := _base_result(), [_request()], config=_ENABLED
            ),
        ]
        for outcome, original in zip(outcomes, (base, base2, base3), strict=True):
            assert outcome.result is original
            assert outcome.result.document == original.document

    def test_d18_report_carries_no_evidence_findings_or_canonical_content(self):
        outcome = _extractor(MockVlmProvider([b"engineering says DIA 30 mm"])).extract_candidates(
            _base_result(), [_request()], config=_ENABLED
        )
        assert isinstance(outcome, DrawingAssistedIngestionResult)
        assert outcome.advisory.evidence == () and outcome.advisory.findings == ()
        assert outcome.result.document.all_dimensions == ()
        assert "DIA 30" not in repr(outcome)

    def test_fingerprints_are_deterministic_sha256(self):
        first = _extractor(MockVlmProvider([b"x"])).extract_candidates(
            _base_result(), [_request()], config=_ENABLED
        )
        second = _extractor(MockVlmProvider([b"x"])).extract_candidates(
            _base_result(), [_request()], config=_ENABLED
        )
        assert first.advisory.config_fingerprint == second.advisory.config_fingerprint
        assert re.fullmatch(r"[0-9a-f]{64}", first.advisory.base_result_fingerprint)

    def test_constructor_and_input_types_are_validated(self):
        with pytest.raises(TypeError):
            AiAssistedDrawingExtractor(object())  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            _extractor(MockVlmProvider()).extract_candidates(
                "not-a-result", [], config=_ENABLED  # type: ignore[arg-type]
            )
        with pytest.raises(TypeError):
            _extractor(MockVlmProvider()).extract_candidates(
                _base_result(), [], config=object()  # type: ignore[arg-type]
            )
        with pytest.raises(TypeError):
            _extractor(MockVlmProvider()).extract_candidates(
                _base_result(), ["x"], config=_ENABLED  # type: ignore[list-item]
            )

    def test_no_requests_is_insufficient_not_fabricated(self):
        outcome = _extractor(MockVlmProvider()).extract_candidates(
            _base_result(), [], config=_ENABLED
        )
        assert outcome.advisory.status is DrawingIngestionStatus.INSUFFICIENT_DATA
        assert outcome.advisory.diagnostics == ("VLM_NO_REQUESTS",)


# ---------------------------------------------------------------------------
# Source-level safety: no network / SDK / env / randomness in R3A modules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("module", [vlm_assist, vlm_providers], ids=lambda m: m.__name__)
def test_r3a_modules_have_no_network_sdk_env_or_random_imports(module):
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = re.compile(
        r"^(socket|ssl|http|urllib|requests|httpx|aiohttp|openai|anthropic|google|boto3|"
        r"ollama|transformers|huggingface_hub|random|secrets|uuid|os|subprocess|pathlib|"
        r"datetime)(\.|$)"
    )
    assert not [name for name in imported if forbidden.match(name)]
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "environ" not in source and "getenv" not in source
    assert "open(" not in source
