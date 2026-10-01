"""Phase 1D Task 1 — vendor-neutral VLM provider contract tests."""

from __future__ import annotations

import ast
import socket
import threading
from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal
from pathlib import Path

import pytest

import backend.interoperability.vlm_provider as vlm_provider
from backend.interoperability.vlm_provider import (
    VlmCancellation,
    VlmCapabilities,
    VlmErrorCode,
    VlmLocality,
    VlmModelIdentity,
    VlmProvider,
    VlmProviderError,
    VlmRequest,
    VlmResponse,
    VlmRetryPolicy,
    VlmSamplingHints,
    VlmTaskKind,
)
from tests.unit.interoperability.vlm_fixtures import (
    FailingVlmProvider,
    ReplayVlmProvider,
    ScriptedVlmProvider,
    SpyVlmProvider,
    make_capabilities,
    make_identity,
    make_request,
    tiny_png,
)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("network access is forbidden in VLM provider tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


_FORBIDDEN_FIELD_FRAGMENTS = (
    "path",
    "file",
    "source_id",
    "drawing_id",
    "timestamp",
    "time",
    "date",
    "env",
    "key",
    "secret",
    "token_value",
    "credential",
    "password",
    "url",
    "endpoint",
)


# ---------------------------------------------------------------------------
# Model identity
# ---------------------------------------------------------------------------


class TestModelIdentity:
    def test_local_identity(self):
        identity = make_identity()
        assert identity.locality is VlmLocality.LOCAL
        assert identity.model_version == "2026-09-24"

    def test_remote_is_descriptive_metadata_only(self):
        identity = make_identity(provider_id="example.remote", locality=VlmLocality.REMOTE)
        assert identity.locality is VlmLocality.REMOTE
        assert {item.value for item in VlmLocality} == {"LOCAL", "REMOTE"}

    @pytest.mark.parametrize("name", ["provider_id", "model_id", "model_version"])
    @pytest.mark.parametrize("value", ["", "   ", "a\nb", "a\x00b", "x" * 129])
    def test_invalid_text_fields_rejected(self, name, value):
        with pytest.raises(ValueError):
            make_identity(**{name: value})

    @pytest.mark.parametrize("name", ["provider_id", "model_id", "model_version"])
    def test_non_string_fields_rejected(self, name):
        with pytest.raises(TypeError):
            make_identity(**{name: 123})

    @pytest.mark.parametrize(
        "version",
        [
            "latest",
            "LATEST",
            "current",
            "stable",
            "default",
            "v2-latest",
            "model:stable",
            "model@latest",
            "gpt-latest",
            "v1.Current",
        ],
    )
    def test_ambiguous_alias_versions_rejected(self, version):
        with pytest.raises(ValueError, match="pinned"):
            make_identity(model_version=version)

    @pytest.mark.parametrize(
        "version",
        [
            "2026-09-24",
            "v1.2.3",
            "model-stable-20260924",
            "default-v2-20260924",
            "current-generation-2026-09-24",
            "stable-build-2026-09-24",
            "latestness-7",
        ],
    )
    def test_explicit_pinned_versions_accepted(self, version):
        assert make_identity(model_version=version).model_version == version

    def test_locality_must_be_enum(self):
        with pytest.raises(TypeError):
            VlmModelIdentity("p", "m", "1", "LOCAL")  # type: ignore[arg-type]

    def test_identity_is_immutable_and_hashable(self):
        identity = make_identity()
        with pytest.raises(FrozenInstanceError):
            identity.model_id = "other"  # type: ignore[misc]
        assert hash(identity) == hash(make_identity())


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class TestCapabilities:
    def test_valid_capabilities(self):
        capabilities = make_capabilities()
        assert capabilities.structured_output is True
        assert capabilities.max_image_pixels == 4_194_304

    def test_task_kinds_are_stored_in_deterministic_order(self):
        forward = VlmCapabilities(
            (VlmTaskKind.TRANSCRIBE, VlmTaskKind.GDT_CHARACTERISTIC), 1, 1, False
        )
        reverse = VlmCapabilities(
            (VlmTaskKind.GDT_CHARACTERISTIC, VlmTaskKind.TRANSCRIBE), 1, 1, False
        )
        assert forward == reverse
        assert repr(forward) == repr(reverse)
        assert forward.task_kinds == tuple(VlmTaskKind)

    @pytest.mark.parametrize("name", ["max_image_bytes", "max_image_pixels"])
    @pytest.mark.parametrize("value", [0, -1])
    def test_non_positive_limits_rejected(self, name, value):
        with pytest.raises(ValueError):
            replace(make_capabilities(), **{name: value})

    @pytest.mark.parametrize("name", ["max_image_bytes", "max_image_pixels"])
    @pytest.mark.parametrize("value", [True, 1.5, "10"])
    def test_non_int_or_bool_limits_rejected(self, name, value):
        with pytest.raises(TypeError):
            replace(make_capabilities(), **{name: value})

    def test_duplicate_task_kinds_rejected(self):
        with pytest.raises(ValueError, match="duplicates"):
            VlmCapabilities((VlmTaskKind.TRANSCRIBE, VlmTaskKind.TRANSCRIBE), 1, 1, True)

    @pytest.mark.parametrize("kinds", [(), ["TRANSCRIBE"], ("TRANSCRIBE",)])
    def test_invalid_task_kind_collections_rejected(self, kinds):
        with pytest.raises((TypeError, ValueError)):
            VlmCapabilities(kinds, 1, 1, True)  # type: ignore[arg-type]

    def test_structured_output_must_be_bool(self):
        with pytest.raises(TypeError):
            replace(make_capabilities(), structured_output=1)

    def test_only_approved_task_kinds_exist(self):
        assert [item.value for item in VlmTaskKind] == ["TRANSCRIBE", "GDT_CHARACTERISTIC"]


# ---------------------------------------------------------------------------
# Sampling hints
# ---------------------------------------------------------------------------


class TestSamplingHints:
    def test_defaults(self):
        hints = VlmSamplingHints()
        assert hints.temperature == Decimal("0")
        assert isinstance(hints.temperature, Decimal)
        assert hints.max_output_tokens == 2048
        assert hints.seed is None

    def test_decimal_temperature_accepted(self):
        assert VlmSamplingHints(temperature=Decimal("0.2")).temperature == Decimal("0.2")

    @pytest.mark.parametrize(
        "value", [Decimal("-0.1"), Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")]
    )
    def test_negative_or_non_finite_temperature_rejected(self, value):
        with pytest.raises(ValueError):
            VlmSamplingHints(temperature=value)

    @pytest.mark.parametrize("value", [0.0, 0, "0"])
    def test_non_decimal_temperature_rejected(self, value):
        with pytest.raises(TypeError):
            VlmSamplingHints(temperature=value)  # type: ignore[arg-type]

    @pytest.mark.parametrize("value", [0, -5])
    def test_non_positive_token_limit_rejected(self, value):
        with pytest.raises(ValueError):
            VlmSamplingHints(max_output_tokens=value)

    @pytest.mark.parametrize("value", [True, 10.0, "10"])
    def test_non_int_token_limit_rejected(self, value):
        with pytest.raises(TypeError):
            VlmSamplingHints(max_output_tokens=value)  # type: ignore[arg-type]

    @pytest.mark.parametrize("value", [True, False, 1.0, Decimal("7"), "7"])
    def test_invalid_seed_type_rejected(self, value):
        with pytest.raises(TypeError):
            VlmSamplingHints(seed=value)  # type: ignore[arg-type]

    @pytest.mark.parametrize("value", [0, 1, -1, 2**63, -(2**63)])
    def test_any_int_seed_accepted(self, value):
        assert VlmSamplingHints(seed=value).seed == value


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class TestRequest:
    def test_valid_request_defaults(self):
        request = make_request()
        assert request.task_kind is VlmTaskKind.TRANSCRIBE
        assert request.context_text == ()
        assert request.sampling == VlmSamplingHints()
        assert request.max_response_bytes == 262_144

    def test_image_bytes_hidden_from_repr(self):
        request = make_request()
        rendered = repr(request)
        assert "image_png" not in rendered
        assert "PNG" not in rendered
        assert repr(request.image_png) not in rendered

    @pytest.mark.parametrize("name", ["image_width_px", "image_height_px"])
    @pytest.mark.parametrize("value", [0, -2])
    def test_invalid_dimensions_rejected(self, name, value):
        with pytest.raises(ValueError):
            replace(make_request(), **{name: value})

    @pytest.mark.parametrize("name", ["image_width_px", "image_height_px"])
    def test_bool_dimensions_rejected(self, name):
        with pytest.raises(TypeError):
            replace(make_request(), **{name: True})

    @pytest.mark.parametrize("value", [0, -1])
    def test_invalid_max_response_bytes_rejected(self, value):
        with pytest.raises(ValueError):
            replace(make_request(), max_response_bytes=value)

    def test_bool_max_response_bytes_rejected(self):
        with pytest.raises(TypeError):
            replace(make_request(), max_response_bytes=True)

    @pytest.mark.parametrize("name", ["request_id", "prompt_contract_version"])
    @pytest.mark.parametrize("value", ["", "  ", "id\twith-tab", "x" * 129])
    def test_invalid_ids_rejected(self, name, value):
        with pytest.raises(ValueError):
            replace(make_request(), **{name: value})

    def test_image_must_be_png_bytes(self):
        with pytest.raises(TypeError):
            replace(make_request(), image_png=bytearray(tiny_png()))
        with pytest.raises(ValueError):
            replace(make_request(), image_png=b"GIF89a")
        with pytest.raises(ValueError):
            replace(make_request(), image_png=b"")

    def test_task_kind_and_model_are_typed(self):
        with pytest.raises(TypeError):
            replace(make_request(), task_kind="TRANSCRIBE")
        with pytest.raises(TypeError):
            replace(make_request(), model="fake-vlm")
        with pytest.raises(TypeError):
            replace(make_request(), sampling={"temperature": 0})

    def test_context_is_structurally_validated_tuple(self):
        assert make_request(context_text=("25 mm",)).context_text == ("25 mm",)
        with pytest.raises(TypeError):
            replace(make_request(), context_text=["25 mm"])
        with pytest.raises(TypeError):
            make_request(context_text=(25,))  # type: ignore[arg-type]
        for invalid in ("", "   ", "line\nbreak", "nul\x00"):
            with pytest.raises(ValueError):
                make_request(context_text=(invalid,))

    def test_context_has_no_numeric_limits_in_provider_contract(self):
        # Size limits belong to the later VlmLimits / orchestration layer.
        many = make_request(context_text=("x",) * 500)
        long = make_request(context_text=("x" * 20_000,))
        assert len(many.context_text) == 500
        assert len(long.context_text[0]) == 20_000

    def test_request_has_no_path_source_or_secret_fields(self):
        names = {item.name for item in fields(VlmRequest)}
        assert names == {
            "request_id",
            "prompt_contract_version",
            "task_kind",
            "model",
            "image_png",
            "image_width_px",
            "image_height_px",
            "context_text",
            "sampling",
            "max_response_bytes",
        }

    def test_request_is_immutable(self):
        request = make_request()
        with pytest.raises(FrozenInstanceError):
            request.request_id = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


def _response(**overrides) -> VlmResponse:
    values = {
        "request_id": "vlm-req-000000000000000000000001",
        "reported_model": make_identity(),
        "payload": b'{"secret-sentinel": true}',
    }
    values.update(overrides)
    return VlmResponse(**values)


class TestResponse:
    def test_valid_response(self):
        response = _response()
        assert response.provider_request_ref is None
        assert response.payload == b'{"secret-sentinel": true}'

    def test_payload_hidden_from_repr(self):
        rendered = repr(_response())
        assert "secret-sentinel" not in rendered
        assert "payload" not in rendered

    def test_optional_provider_ref(self):
        assert _response(provider_request_ref="req_abc123").provider_request_ref == "req_abc123"

    @pytest.mark.parametrize("value", ["", " ", "ref\nnext", "r" * 257])
    def test_invalid_provider_ref_rejected(self, value):
        with pytest.raises(ValueError):
            _response(provider_request_ref=value)

    @pytest.mark.parametrize("value", ["", "x" * 129, "id\x07"])
    def test_invalid_request_id_rejected(self, value):
        with pytest.raises(ValueError):
            _response(request_id=value)

    def test_payload_must_be_bytes_and_is_not_parsed(self):
        with pytest.raises(TypeError):
            _response(payload='{"a": 1}')
        assert _response(payload=b"not json at all").payload == b"not json at all"

    def test_reported_model_is_typed(self):
        with pytest.raises(TypeError):
            _response(reported_model="fake-vlm")


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


class TestCancellation:
    def test_initially_not_cancelled(self):
        assert VlmCancellation().is_cancelled() is False

    def test_cancel_sets_flag_and_is_idempotent(self):
        cancellation = VlmCancellation()
        cancellation.cancel()
        cancellation.cancel()
        assert cancellation.is_cancelled() is True
        assert repr(cancellation) == "VlmCancellation(cancelled=True)"

    def test_thread_safe_cancellation(self):
        cancellation = VlmCancellation()
        start = threading.Barrier(9)
        observed: list[bool] = []

        def canceller():
            start.wait()
            cancellation.cancel()

        def observer():
            start.wait()
            while not cancellation.is_cancelled():
                pass
            observed.append(True)

        threads = [threading.Thread(target=canceller) for _ in range(4)]
        threads += [threading.Thread(target=observer) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        assert all(not thread.is_alive() for thread in threads)
        assert observed == [True] * 5
        assert cancellation.is_cancelled() is True


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------


class TestErrorModel:
    def test_all_approved_codes_exist(self):
        assert {code.value for code in VlmErrorCode} == {
            "UNAVAILABLE",
            "DISABLED",
            "TIMEOUT",
            "CANCELLED",
            "RATE_LIMITED",
            "TRANSIENT",
            "REQUEST_REJECTED",
            "UNSUPPORTED",
            "RESPONSE_TOO_LARGE",
        }

    @pytest.mark.parametrize("code", list(VlmErrorCode))
    def test_error_carries_stable_code_only(self, code):
        error = VlmProviderError(code)
        assert error.code is code
        assert str(error) == code.value
        assert error.args == (code.value,)
        assert repr(error) == f"VlmProviderError({code.value})"

    def test_error_rejects_free_text_and_untyped_codes(self):
        with pytest.raises(TypeError):
            VlmProviderError("TIMEOUT")  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            VlmProviderError(VlmErrorCode.TIMEOUT, "vendor said: quota")  # type: ignore[call-arg]

    def test_error_pickles_with_code(self):
        import pickle

        restored = pickle.loads(pickle.dumps(VlmProviderError(VlmErrorCode.TRANSIENT)))
        assert restored.code is VlmErrorCode.TRANSIENT


# ---------------------------------------------------------------------------
# Provider protocol and fakes
# ---------------------------------------------------------------------------


class TestProviderFakes:
    def test_fakes_satisfy_protocol(self):
        for provider in (
            ScriptedVlmProvider([b"{}"]),
            ReplayVlmProvider({}),
            FailingVlmProvider(VlmErrorCode.UNAVAILABLE),
            SpyVlmProvider(ReplayVlmProvider({})),
        ):
            assert isinstance(provider, VlmProvider)
            assert provider.identity() == make_identity()
            assert provider.capabilities() == make_capabilities()

    def test_scripted_provider_returns_outcomes_in_order(self):
        provider = ScriptedVlmProvider([b"first", VlmErrorCode.TRANSIENT, b"third"])
        cancellation = VlmCancellation()
        request = make_request()

        first = provider.infer(request, deadline_seconds=30.0, cancellation=cancellation)
        with pytest.raises(VlmProviderError) as error:
            provider.infer(request, deadline_seconds=30.0, cancellation=cancellation)
        third = provider.infer(request, deadline_seconds=30.0, cancellation=cancellation)

        assert first.payload == b"first"
        assert first.request_id == request.request_id
        assert first.reported_model == provider.identity()
        assert error.value.code is VlmErrorCode.TRANSIENT
        assert third.payload == b"third"
        with pytest.raises(VlmProviderError) as exhausted:
            provider.infer(request, deadline_seconds=30.0, cancellation=cancellation)
        assert exhausted.value.code is VlmErrorCode.UNAVAILABLE

    def test_replay_provider_is_deterministic(self):
        request = make_request("vlm-req-a")
        provider = ReplayVlmProvider({"vlm-req-a": b'{"items": []}'})
        responses = [
            provider.infer(request, deadline_seconds=1.0, cancellation=VlmCancellation())
            for _ in range(3)
        ]
        assert responses[0] == responses[1] == responses[2]
        with pytest.raises(VlmProviderError) as unknown:
            provider.infer(
                make_request("vlm-req-b"), deadline_seconds=1.0, cancellation=VlmCancellation()
            )
        assert unknown.value.code is VlmErrorCode.REQUEST_REJECTED

    def test_spy_provider_captures_requests(self):
        spy = SpyVlmProvider(ReplayVlmProvider({"vlm-req-a": b"{}"}))
        cancellation = VlmCancellation()
        request = make_request("vlm-req-a")

        spy.infer(request, deadline_seconds=12.5, cancellation=cancellation)

        assert len(spy.recorded) == 1
        assert spy.recorded[0].request is request
        assert spy.recorded[0].deadline_seconds == 12.5
        assert spy.recorded[0].cancellation is cancellation

    @pytest.mark.parametrize("code", list(VlmErrorCode))
    def test_failing_provider_raises_its_code(self, code):
        provider = FailingVlmProvider(code)
        with pytest.raises(VlmProviderError) as error:
            provider.infer(make_request(), deadline_seconds=1.0, cancellation=VlmCancellation())
        assert error.value.code is code
        assert provider.calls == 1

    def test_fakes_honor_cancellation(self):
        cancellation = VlmCancellation()
        cancellation.cancel()
        for provider in (ScriptedVlmProvider([b"{}"]), ReplayVlmProvider({"x": b"{}"})):
            with pytest.raises(VlmProviderError) as error:
                provider.infer(
                    make_request("x"), deadline_seconds=1.0, cancellation=cancellation
                )
            assert error.value.code is VlmErrorCode.CANCELLED


# ---------------------------------------------------------------------------
# Retry policy
# ---------------------------------------------------------------------------


class TestRetryPolicy:
    def test_defaults(self):
        policy = VlmRetryPolicy()
        assert policy.max_attempts == 2
        assert policy.retry_on == (VlmErrorCode.TRANSIENT, VlmErrorCode.RATE_LIMITED)
        assert policy.backoff_seconds == (Decimal("1"),)

    def test_timeout_is_not_retried_by_default(self):
        assert VlmErrorCode.TIMEOUT not in VlmRetryPolicy().retry_on

    @pytest.mark.parametrize("value", [0, -1])
    def test_invalid_attempts_rejected(self, value):
        with pytest.raises(ValueError):
            VlmRetryPolicy(max_attempts=value, backoff_seconds=())

    @pytest.mark.parametrize("value", [True, 2.0, "2"])
    def test_non_int_attempts_rejected(self, value):
        with pytest.raises(TypeError):
            VlmRetryPolicy(max_attempts=value)  # type: ignore[arg-type]

    def test_single_attempt_policy_needs_no_backoff(self):
        policy = VlmRetryPolicy(max_attempts=1, backoff_seconds=())
        assert policy.backoff_seconds == ()

    def test_duplicate_codes_rejected(self):
        with pytest.raises(ValueError, match="duplicates"):
            VlmRetryPolicy(retry_on=(VlmErrorCode.TRANSIENT, VlmErrorCode.TRANSIENT))

    def test_invalid_code_values_rejected(self):
        with pytest.raises(TypeError):
            VlmRetryPolicy(retry_on=("TRANSIENT",))  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            VlmRetryPolicy(retry_on=[VlmErrorCode.TRANSIENT])  # type: ignore[arg-type]

    def test_caller_may_configure_any_valid_codes(self):
        every_code = tuple(VlmErrorCode)
        policy = VlmRetryPolicy(retry_on=every_code)
        assert policy.retry_on == every_code
        custom = VlmRetryPolicy(retry_on=(VlmErrorCode.CANCELLED, VlmErrorCode.TIMEOUT))
        assert custom.retry_on == (VlmErrorCode.CANCELLED, VlmErrorCode.TIMEOUT)
        assert VlmRetryPolicy(retry_on=()).retry_on == ()

    @pytest.mark.parametrize(
        "backoff",
        [(Decimal("-1"),), (Decimal("NaN"),), (Decimal("Infinity"),), (1,), (1.0,)],
    )
    def test_invalid_backoff_rejected(self, backoff):
        with pytest.raises((TypeError, ValueError)):
            VlmRetryPolicy(backoff_seconds=backoff)

    @pytest.mark.parametrize(
        ("attempts", "backoff"),
        [(2, ()), (2, (Decimal("1"), Decimal("1"))), (3, (Decimal("1"),))],
    )
    def test_backoff_count_must_match_attempts(self, attempts, backoff):
        with pytest.raises(ValueError, match="max_attempts - 1"):
            VlmRetryPolicy(max_attempts=attempts, backoff_seconds=backoff)

    def test_deterministic_structure(self):
        first = VlmRetryPolicy(
            max_attempts=3, backoff_seconds=(Decimal("0.5"), Decimal("2"))
        )
        second = VlmRetryPolicy(
            max_attempts=3, backoff_seconds=(Decimal("0.5"), Decimal("2"))
        )
        assert first == second
        assert repr(first) == repr(second)
        assert hash(first) == hash(second)
        with pytest.raises(FrozenInstanceError):
            first.max_attempts = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Safety / scope
# ---------------------------------------------------------------------------


class TestSafety:
    @pytest.mark.parametrize(
        "contract",
        [VlmModelIdentity, VlmCapabilities, VlmSamplingHints, VlmRequest, VlmResponse,
         VlmRetryPolicy],
    )
    def test_no_path_time_or_credential_fields(self, contract):
        for item in fields(contract):
            lowered = item.name.lower()
            assert not any(fragment in lowered for fragment in _FORBIDDEN_FIELD_FRAGMENTS), (
                f"{contract.__name__}.{item.name}"
            )

    def test_reprs_contain_no_image_or_payload_bytes(self):
        request = make_request()
        response = _response(payload=b"RAW-PAYLOAD-SENTINEL")
        rendered = repr(request) + repr(response)
        assert "RAW-PAYLOAD-SENTINEL" not in rendered
        assert "\\x89PNG" not in rendered
        assert "IHDR" not in rendered

    def test_module_has_no_network_vendor_or_clock_imports(self):
        tree = ast.parse(Path(vlm_provider.__file__).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert imported == {
            "__future__",
            "re",
            "threading",
            "unicodedata",
            "dataclasses",
            "decimal",
            "enum",
            "typing",
        }

    def test_module_source_has_no_double_encoded_text(self):
        source = Path(vlm_provider.__file__).read_text(encoding="utf-8")
        for marker in ("Ã", "â€"):
            assert marker not in source

    def test_public_api_is_exactly_the_task_contract(self):
        assert sorted(vlm_provider.__all__) == sorted(
            [
                "VlmCancellation",
                "VlmCapabilities",
                "VlmErrorCode",
                "VlmLocality",
                "VlmModelIdentity",
                "VlmProvider",
                "VlmProviderError",
                "VlmRequest",
                "VlmResponse",
                "VlmRetryPolicy",
                "VlmSamplingHints",
                "VlmTaskKind",
            ]
        )
