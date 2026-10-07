"""Phase 1D R3C: report-only reconciliation of advisory evidence and deterministic dimensions."""

from __future__ import annotations

import ast
import itertools
import re
import socket
from decimal import Decimal
from pathlib import Path

import pytest

import backend.interoperability.ocr_drawing as ocr_drawing
import backend.interoperability.pdf_drawing as pdf_drawing
import backend.interoperability.raster_drawing as raster_drawing
import backend.interoperability.vlm_assist as vlm_assist
import backend.interoperability.vlm_reconciliation as vlm_reconciliation
from backend.interoperability.drawing import (
    CanonicalDrawing,
    DrawingBoundingBox,
    DrawingDimension,
    DrawingDimensionType,
    DrawingExtractionAuthority,
    DrawingIngestionDiagnostics,
    DrawingIngestionResult,
    DrawingIngestionStatus,
    DrawingParserIdentity,
    DrawingSourceLocation,
    DrawingTolerance,
    DrawingToleranceType,
)
from backend.interoperability.vlm_assist import AiAssistedDrawingExtractor
from backend.interoperability.vlm_drawing import (
    DrawingAdvisoryReport,
    DrawingEvidenceOrigin,
    DrawingVlmAssistConfig,
    DrawingVlmEvidence,
    DrawingVlmEvidenceKind,
    DrawingVlmLegibility,
    DrawingVlmRationale,
    DrawingVlmReconciliationStatus,
    DrawingVlmValidationStatus,
)
from backend.interoperability.vlm_provider import VlmErrorCode
from backend.interoperability.vlm_providers import DisabledVlmProvider, MockVlmProvider
from backend.interoperability.vlm_reconciliation import (
    DrawingVlmComparison,
    DrawingVlmComparisonReason,
    DrawingVlmReconciliation,
    reconcile_advisory_evidence,
)
from backend.interoperability.vlm_response import VlmResponseError, parse_vlm_response
from tests.unit.interoperability.test_vlm_response import (
    _REQUEST_ID,
    _body,
    _bytes,
    _item,
    _region,
    _request,
    _response,
)
from tests.unit.interoperability.vlm_fixtures import make_identity

_SOURCE_ID = "synthetic::r3c.pdf"
_MODEL = MockVlmProvider().identity()
_C = DrawingVlmComparison
_R = DrawingVlmComparisonReason
_FINGERPRINT = "a" * 64
_REF_1 = "page-1:image-1:line-1-1-1"
_REF_2 = "page-1:image-1:line-1-1-2"
_REF_3 = "page-1:image-1:line-1-1-3"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("network access is forbidden in R3C tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


def _box() -> DrawingBoundingBox:
    return DrawingBoundingBox(Decimal("110"), Decimal("205"), Decimal("160"), Decimal("217"))


def _dimension(
    dimension_id: str = "pdf-dim-p0001-000001",
    *,
    text: str | None = "25 mm",
    ids: tuple[str, ...] = ("page-1:image-1", _REF_1),
    adapter: str = "tesseract-ocr",
    value: str = "25",
    unit: str = "mm",
    dimension_type: DrawingDimensionType = DrawingDimensionType.LINEAR,
    tolerance: DrawingTolerance | None = None,
    page: int = 1,
    with_location: bool = True,
) -> DrawingDimension:
    location = None
    if with_location:
        location = DrawingSourceLocation(
            source_id=_SOURCE_ID,
            page_number=page,
            original_text=text,
            adapter_id=adapter,
            adapter_version="1",
            authority=DrawingExtractionAuthority.EXTRACTED,
            bounding_box=_box(),
            source_object_ids=ids,
        )
    return DrawingDimension(
        dimension_id=dimension_id,
        nominal_value=Decimal(value),
        unit=unit,
        dimension_type=dimension_type,
        tolerance=tolerance,
        source_location=location,
    )


def _base(*dimensions: DrawingDimension) -> DrawingIngestionResult:
    return DrawingIngestionResult(
        source_id=_SOURCE_ID,
        diagnostics=DrawingIngestionDiagnostics(
            status=DrawingIngestionStatus.VALID,
            format_detected="PDF",
            parser_id="machiningpro.vector-pdf",
            parser_version="1.0.0",
        ),
        document=CanonicalDrawing(
            drawing_id="pdf-drawing-r3c", source_id=_SOURCE_ID, all_dimensions=tuple(dimensions)
        ),
    )


def _evidence(
    evidence_id: str = "vlm-ev-1",
    *,
    raw: str = "25 mm",
    reference: str | None = _REF_1,
    kind: DrawingVlmEvidenceKind = DrawingVlmEvidenceKind.DIMENSION,
    normalized: DrawingDimension | None = None,
    region_id: str = "vlm-region-1",
) -> DrawingVlmEvidence:
    ids = ["page-1:image-1", region_id, evidence_id]
    if reference is not None:
        ids.append(reference)
    location = DrawingSourceLocation(
        source_id=_SOURCE_ID,
        page_number=1,
        original_text=raw,
        adapter_id="machiningpro.vlm-assist",
        adapter_version="mock-vlm@1",
        confidence=Decimal("0.9"),
        authority=DrawingExtractionAuthority.ADVISORY,
        bounding_box=_box(),
        source_object_ids=tuple(ids),
    )
    return DrawingVlmEvidence(
        evidence_id=evidence_id,
        evidence_kind=kind,
        raw_candidate=raw,
        legibility=DrawingVlmLegibility.CLEAR,
        source_location=location,
        parser_identity=DrawingParserIdentity("machiningpro.vlm-assist", "1.0.0"),
        model=_MODEL,
        prompt_contract_version=_request().prompt_contract_version,
        region_id=region_id,
        request_id=_REQUEST_ID,
        sample_index=0,
        validation_status=DrawingVlmValidationStatus.VALID,
        reported_confidence=Decimal("0.9"),
        normalized_dimension=normalized,
    )


def _region_with_triggers(*triggers: str):
    from dataclasses import replace

    return replace(_region(), trigger_evidence_ids=triggers or (_REF_1, _REF_2, _REF_3))


def _report(*evidence: DrawingVlmEvidence) -> DrawingAdvisoryReport:
    return DrawingAdvisoryReport(
        status=DrawingIngestionStatus.VALID,
        prompt_contract_version=_request().prompt_contract_version,
        model=_MODEL,
        config_fingerprint=_FINGERPRINT,
        base_result_fingerprint=_FINGERPRINT,
        regions=(_region_with_triggers(),),
        evidence=tuple(evidence),
        request_count=1,
    )


def _one(base, *evidence):
    results = reconcile_advisory_evidence(base, _report(*evidence))
    assert len(results) == 1
    return results[0]


# ---------------------------------------------------------------------------
# T01–T06: the six states
# ---------------------------------------------------------------------------


class TestStates:
    def test_t01_exact_structured_agreement(self):
        result = _one(_base(_dimension()), _evidence())
        assert result.status is _C.AGREES and result.reason is _R.TEXT_EQUAL
        assert result.ai_evidence_ids == ("vlm-ev-1",)
        assert result.deterministic_ids == ("pdf-dim-p0001-000001",)
        finding = result.finding
        assert finding.status is DrawingVlmReconciliationStatus.CORROBORATED
        assert finding.rationale is DrawingVlmRationale.EXACT_MATCH
        assert finding.deterministic_origins == (DrawingEvidenceOrigin.OCR,)

    def test_t01_unicode_and_surrounding_space_follow_the_ocr_normalization_only(self):
        decomposed = "25 mm"
        assert _one(_base(_dimension(text=" 25 mm ")), _evidence(raw="25 mm")).status is _C.AGREES
        result = _one(_base(_dimension(text="25 mm")), _evidence(raw=decomposed))
        assert result.status is _C.CONFLICTS  # no whitespace/alias folding is invented

    def test_t02_differing_value_conflicts(self):
        result = _one(_base(_dimension()), _evidence(raw="26 mm"))
        assert result.status is _C.CONFLICTS and result.reason is _R.TEXT_MISMATCH
        finding = result.finding
        assert finding.status is DrawingVlmReconciliationStatus.CONFLICT
        assert finding.rationale is DrawingVlmRationale.VALUE_MISMATCH
        assert finding.conflict_ids == ("pdf-dim-p0001-000001",)

    def test_t03_ai_only_without_deterministic_counterpart(self):
        result = _one(_base(), _evidence())
        assert result.status is _C.AI_ONLY
        assert result.reason is _R.NO_DETERMINISTIC_COUNTERPART
        assert result.finding.status is DrawingVlmReconciliationStatus.ADVISORY_ONLY
        assert result.finding.rationale is DrawingVlmRationale.NO_DETERMINISTIC_EVIDENCE

    def test_t04_deterministic_only_without_ai_match(self):
        result = _one(_base(_dimension()))
        assert result.status is _C.DETERMINISTIC_ONLY
        assert result.reason is _R.NO_AI_COUNTERPART
        assert result.ai_evidence_ids == () and result.finding is None

    @pytest.mark.parametrize(
        "kind",
        [k for k in DrawingVlmEvidenceKind if k is not DrawingVlmEvidenceKind.DIMENSION],
    )
    def test_t05_incompatible_kind_is_not_comparable(self, kind):
        results = reconcile_advisory_evidence(
            _base(_dimension()), _report(_evidence(kind=kind))
        )
        statuses = {item.status for item in results}
        assert statuses == {_C.NOT_COMPARABLE, _C.DETERMINISTIC_ONLY}
        item = next(r for r in results if r.status is _C.NOT_COMPARABLE)
        assert item.reason is _R.UNSUPPORTED_KIND
        assert item.finding.rationale is DrawingVlmRationale.UNSUPPORTED_KIND

    def test_t05_missing_structured_identity_is_not_comparable(self):
        results = reconcile_advisory_evidence(
            _base(_dimension()), _report(_evidence(reference=None))
        )
        item = next(r for r in results if r.ai_evidence_ids)
        assert item.status is _C.NOT_COMPARABLE and item.reason is _R.NO_STRUCTURED_IDENTITY

    def test_t05_unknown_deterministic_origin_or_text_is_not_comparable(self):
        origin = _one(_base(_dimension(adapter="someone-else")), _evidence())
        assert origin.status is _C.NOT_COMPARABLE
        assert origin.reason is _R.UNKNOWN_DETERMINISTIC_ORIGIN
        assert origin.deterministic_ids and origin.finding is None
        no_text = _one(_base(_dimension(text=None)), _evidence())
        assert no_text.status is _C.NOT_COMPARABLE and no_text.reason is _R.NO_DETERMINISTIC_TEXT

    def test_t06_two_ai_candidates_for_one_dimension_are_ambiguous(self):
        results = reconcile_advisory_evidence(
            _base(_dimension()),
            _report(_evidence("vlm-ev-1"), _evidence("vlm-ev-2", raw="25 mm")),
        )
        assert len(results) == 1
        item = results[0]
        assert item.status is _C.AMBIGUOUS and item.reason is _R.MULTIPLE_AI_CANDIDATES
        assert item.ai_evidence_ids == ("vlm-ev-1", "vlm-ev-2")
        assert item.finding is None

    def test_t06_one_ai_candidate_matching_two_dimensions_is_ambiguous(self):
        base = _base(_dimension("pdf-dim-1"), _dimension("pdf-dim-2", text="26 mm"))
        (item,) = reconcile_advisory_evidence(base, _report(_evidence()))
        assert item.status is _C.AMBIGUOUS
        assert item.reason is _R.MULTIPLE_DETERMINISTIC_MATCHES
        assert item.deterministic_ids == ("pdf-dim-1", "pdf-dim-2")

    def test_ambiguity_never_picks_a_first_match(self):
        base = _base(_dimension("pdf-dim-1"), _dimension("pdf-dim-2"))
        (item,) = reconcile_advisory_evidence(base, _report(_evidence()))
        assert item.status is not _C.AGREES and item.status is _C.AMBIGUOUS

    def test_duplicate_identifiers_are_validation_errors(self):
        with pytest.raises(ValueError):
            reconcile_advisory_evidence(
                _base(_dimension("dup"), _dimension("dup", ids=("x",))), _report()
            )
        report = _report(_evidence("vlm-ev-1"))
        object.__setattr__(report, "evidence", (report.evidence[0], report.evidence[0]))
        with pytest.raises(ValueError):
            reconcile_advisory_evidence(_base(_dimension()), report)

    def test_different_page_does_not_match(self):
        results = reconcile_advisory_evidence(_base(_dimension(page=2)), _report(_evidence()))
        assert {r.status for r in results} == {_C.AI_ONLY, _C.DETERMINISTIC_ONLY}

    def test_rejected_evidence_is_not_reconciled(self):
        evidence = _evidence()
        object.__setattr__(evidence, "validation_status", DrawingVlmValidationStatus.REJECTED)
        results = reconcile_advisory_evidence(_base(_dimension()), _report(evidence))
        assert [r.status for r in results] == [_C.DETERMINISTIC_ONLY]


# ---------------------------------------------------------------------------
# T07–T11: authority, mutation, provenance
# ---------------------------------------------------------------------------


class TestAuthorityAndProvenance:
    def test_t07_no_state_promotes_authority(self):
        assert vlm_reconciliation.AGREEMENT_AUTO_PROMOTION_ALLOWED is False
        assert vlm_reconciliation.CONFLICT_AUTO_RESOLUTION_ALLOWED is False
        assert vlm_reconciliation.AI_ONLY_AUTO_PROMOTION_ALLOWED is False
        assert vlm_assist.AI_DEFAULT_AUTHORITY is DrawingExtractionAuthority.ADVISORY
        for raw in ("25 mm", "26 mm"):
            evidence = _evidence(raw=raw)
            _one(_base(_dimension()), evidence)
            assert evidence.source_location.authority is DrawingExtractionAuthority.ADVISORY

    def test_t08_conflict_does_not_overwrite_deterministic_evidence(self):
        dimension = _dimension()
        base = _base(dimension)
        before = repr(base)
        evidence = _evidence(raw="26 mm")
        before_ai = repr(evidence)
        _one(base, evidence)
        assert repr(base) == before and repr(evidence) == before_ai
        assert base.document.all_dimensions == (dimension,)
        assert base.document.all_dimensions[0].nominal_value == Decimal("25")
        assert base.document.all_dimensions[0].source_location.original_text == "25 mm"

    def test_t09_ai_only_does_not_alter_the_canonical_drawing(self):
        base = _base(_dimension())
        before = repr(base.document)
        reconcile_advisory_evidence(base, _report(_evidence(reference=_REF_2)))
        assert repr(base.document) == before
        assert len(base.document.all_dimensions) == 1

    def test_t10_t11_both_provenance_chains_are_retained(self):
        dimension = _dimension(ids=("page-1:image-1", _REF_1, "extra-det-id"))
        result = _one(_base(dimension), _evidence())
        provenance = set(result.provenance_ids)
        assert {"page-1:image-1", _REF_1, "extra-det-id"} <= provenance  # deterministic
        assert {"vlm-region-1", "vlm-ev-1"} <= provenance  # AI
        assert list(result.provenance_ids) == sorted(result.provenance_ids)

    def test_results_hold_identifiers_not_engineering_values(self):
        result = _one(_base(_dimension()), _evidence(raw="26 mm"))
        text = repr(result)
        assert "26 mm" not in text and "25" not in text.replace("pdf-dim-p0001-000001", "")

    def test_reconciliation_type_validates_its_shape(self):
        with pytest.raises(ValueError):
            DrawingVlmReconciliation("r", _C.AGREES, _R.TEXT_EQUAL, ("a",), (), ())
        with pytest.raises(TypeError):
            DrawingVlmReconciliation("r", "AGREES", _R.TEXT_EQUAL, ("a",), ("d",), ())  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            DrawingVlmReconciliation(
                "r", _C.AMBIGUOUS, _R.MULTIPLE_AI_CANDIDATES, ("a",), ("d",), ()
            )

    def test_adapter_literals_match_the_deterministic_stages(self):
        assert vlm_reconciliation._VECTOR_ADAPTER_ID == pdf_drawing._PARSER_ID
        assert vlm_reconciliation._OCR_ADAPTER_ID == ocr_drawing._OCR_PARSER.parser_id


# ---------------------------------------------------------------------------
# T12–T15: determinism, ordering, no fuzzy matching, no invented tolerance
# ---------------------------------------------------------------------------


class TestDeterminismAndComparisonRules:
    def test_t12_repeated_reconciliation_is_deterministic(self):
        base, report = _base(_dimension()), _report(_evidence(raw="26 mm"))
        assert reconcile_advisory_evidence(base, report) == reconcile_advisory_evidence(
            base, report
        )

    def test_t13_result_is_independent_of_input_order(self):
        dims = [
            _dimension("pdf-dim-1", ids=("page-1:image-1", _REF_1), text="25 mm"),
            _dimension("pdf-dim-2", ids=("page-1:image-1", _REF_2), text="30 mm"),
            _dimension("pdf-dim-3", ids=("page-1:image-1", "unmatched"), text="9 mm"),
        ]
        ai = [
            _evidence("vlm-ev-1", raw="25 mm", reference=_REF_1),
            _evidence("vlm-ev-2", raw="31 mm", reference=_REF_2),
            _evidence("vlm-ev-3", raw="5 mm", reference=_REF_3),
        ]
        baseline = reconcile_advisory_evidence(_base(*dims), _report(*ai))
        assert {r.status for r in baseline} == {
            _C.AGREES,
            _C.CONFLICTS,
            _C.AI_ONLY,
            _C.DETERMINISTIC_ONLY,
        }
        for dim_order, ai_order in itertools.product(
            itertools.permutations(dims), itertools.permutations(ai)
        ):
            assert reconcile_advisory_evidence(_base(*dim_order), _report(*ai_order)) == baseline

    def test_t14_no_fuzzy_matching_by_proximity_or_text_similarity(self):
        # Same text, same box, same page, but no shared source object id.
        dimension = _dimension(ids=("page-1:image-1", "some-other-object"))
        results = reconcile_advisory_evidence(_base(dimension), _report(_evidence()))
        assert {r.status for r in results} == {_C.AI_ONLY, _C.DETERMINISTIC_ONLY}
        assert not any(r.status in (_C.AGREES, _C.CONFLICTS) for r in results)

    def test_the_shared_raster_object_id_alone_is_never_an_identity(self):
        # Every OCR item on an image shares its image object id; it must not match.
        dimension = _dimension(ids=("page-1:image-1",))
        results = reconcile_advisory_evidence(_base(dimension), _report(_evidence()))
        assert {r.status for r in results} == {_C.AI_ONLY, _C.DETERMINISTIC_ONLY}

    def test_t15_normalized_dimensions_compare_exactly_with_no_epsilon(self):
        def conflict_reason(**changes):
            normalized = _dimension("ai-dim", **{"ids": ("n",), "adapter": "x", **changes})
            return _one(_base(_dimension()), _evidence(normalized=normalized))

        assert conflict_reason().status is _C.AGREES
        assert conflict_reason(value="25.0").status is _C.AGREES  # canonical Decimal equality
        near = conflict_reason(value="25.0000001")
        assert near.status is _C.CONFLICTS and near.reason is _R.VALUE_MISMATCH
        assert conflict_reason(unit="in").reason is _R.UNIT_MISMATCH
        diameter = conflict_reason(dimension_type=DrawingDimensionType.DIAMETRAL)
        assert diameter.reason is _R.TYPE_MISMATCH
        tolerance = DrawingTolerance(
            tolerance_id="t",
            tolerance_type=DrawingToleranceType.SYMMETRIC,
            unit="mm",
            upper_value=Decimal("0.1"),
            lower_value=Decimal("-0.1"),
        )
        assert conflict_reason(tolerance=tolerance).reason is _R.TOLERANCE_MISMATCH
        assert near.finding.rationale is DrawingVlmRationale.VALUE_MISMATCH

    def test_unit_conversion_is_never_attempted(self):
        normalized = _dimension("ai-dim", ids=("n",), adapter="x", value="1", unit="in")
        result = _one(_base(_dimension(value="25.4")), _evidence(normalized=normalized))
        assert result.status is _C.CONFLICTS and result.reason is _R.UNIT_MISMATCH


# ---------------------------------------------------------------------------
# T16–T18 and the orchestrated opt-in
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_t16_malformed_candidates_are_still_rejected_by_r3b(self):
        with pytest.raises(VlmResponseError):
            parse_vlm_response(
                _response(_bytes(_body([_item(confidence=87)]))),
                _request(),
                _region(),
                limits=DrawingVlmAssistConfig().limits,
            )

    def _extract(self, response_items, dimension, *, reconcile=True):
        from dataclasses import replace

        region = replace(_region(), trigger_evidence_ids=(_REF_1, _REF_2))
        provider = MockVlmProvider([_bytes(_body(response_items))])
        base = _base(dimension) if dimension is not None else _base()
        outcome = AiAssistedDrawingExtractor(provider).extract_candidates(
            base,
            [_request()],
            config=DrawingVlmAssistConfig(enabled=True),
            regions={_REQUEST_ID: region},
            reconcile=reconcile,
        )
        return base, outcome

    def test_orchestrated_agreement_adds_an_advisory_finding_only(self):
        item = _item(evidence_reference=_REF_1)
        base, outcome = self._extract([item], _dimension())
        before = repr(base)
        (finding,) = outcome.advisory.findings
        assert finding.status is DrawingVlmReconciliationStatus.CORROBORATED
        assert outcome.result is base and repr(base) == before
        assert outcome.advisory.evidence[0].source_location.authority is (
            DrawingExtractionAuthority.ADVISORY
        )

    def test_orchestrated_conflict_keeps_both_sides_and_deterministic_values(self):
        item = _item(value="26 mm", evidence_reference=_REF_1)
        base, outcome = self._extract([item], _dimension())
        (finding,) = outcome.advisory.findings
        assert finding.status is DrawingVlmReconciliationStatus.CONFLICT
        assert outcome.advisory.evidence[0].raw_candidate == "26 mm"
        assert base.document.all_dimensions[0].source_location.original_text == "25 mm"

    def test_orchestrated_ai_only_and_default_off(self):
        item = _item(evidence_reference=_REF_2)
        _, outcome = self._extract([item], _dimension())
        assert outcome.advisory.findings[0].status is DrawingVlmReconciliationStatus.ADVISORY_ONLY
        _, plain = self._extract([item], _dimension(), reconcile=False)
        assert plain.advisory.findings == ()

    def test_orchestrated_ambiguity_yields_no_finding(self):
        item = _item(evidence_reference=_REF_1)
        dims = (_dimension("pdf-dim-1"), _dimension("pdf-dim-2"))
        from dataclasses import replace

        region = replace(_region(), trigger_evidence_ids=(_REF_1,))
        provider = MockVlmProvider([_bytes(_body([item]))])
        outcome = AiAssistedDrawingExtractor(provider).extract_candidates(
            _base(*dims),
            [_request()],
            config=DrawingVlmAssistConfig(enabled=True),
            regions={_REQUEST_ID: region},
            reconcile=True,
        )
        assert outcome.advisory.findings == ()
        assert outcome.advisory.status is DrawingIngestionStatus.VALID

    def test_orchestrated_rejected_response_never_reconciles(self):
        base, outcome = self._extract([_item(confidence=87)], _dimension())
        assert outcome.advisory.status is DrawingIngestionStatus.FAILED
        assert outcome.advisory.findings == () and outcome.advisory.evidence == ()

    def test_disabled_config_skips_everything(self):
        provider = MockVlmProvider([_bytes(_body())])
        outcome = AiAssistedDrawingExtractor(provider).extract_candidates(
            _base(_dimension()),
            [_request()],
            config=DrawingVlmAssistConfig(),
            regions={_REQUEST_ID: _region()},
            reconcile=True,
        )
        assert outcome.advisory is None and provider.call_count == 0

    def test_t17_disabled_provider_unchanged(self):
        provider = DisabledVlmProvider()
        from dataclasses import replace

        from tests.unit.interoperability.vlm_fixtures import make_request

        request = replace(
            make_request(model=provider.identity()), image_width_px=100, image_height_px=50
        )
        outcome = AiAssistedDrawingExtractor(provider).extract_candidates(
            _base(_dimension()),
            [request],
            config=DrawingVlmAssistConfig(enabled=True),
            regions={request.request_id: _region()},
            reconcile=True,
        )
        assert outcome.advisory.status is DrawingIngestionStatus.UNSUPPORTED
        assert outcome.advisory.diagnostics == ("VLM_DISABLED",)
        assert outcome.advisory.findings == ()

    def test_t18_mock_provider_unchanged_and_deterministic(self):
        first = self._extract([_item(evidence_reference=_REF_1)], _dimension())[1]
        second = self._extract([_item(evidence_reference=_REF_1)], _dimension())[1]
        assert first == second
        unavailable = MockVlmProvider([VlmErrorCode.UNAVAILABLE])
        assert unavailable.call_count == 0

    def test_argument_types_are_validated(self):
        with pytest.raises(TypeError):
            reconcile_advisory_evidence("x", _report())  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            reconcile_advisory_evidence(_base(), "x")  # type: ignore[arg-type]

    def test_result_without_a_document_yields_only_ai_results(self):
        base = DrawingIngestionResult(
            source_id=_SOURCE_ID,
            diagnostics=DrawingIngestionDiagnostics(
                status=DrawingIngestionStatus.INSUFFICIENT_DATA,
                format_detected="PDF",
                parser_id="machiningpro.vector-pdf",
                parser_version="1.0.0",
            ),
        )
        (item,) = reconcile_advisory_evidence(base, _report(_evidence()))
        assert item.status is _C.AI_ONLY


# ---------------------------------------------------------------------------
# T19–T23: isolation, no network
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module", [pdf_drawing, ocr_drawing, raster_drawing], ids=lambda m: m.__name__
)
def test_t19_t20_deterministic_modules_never_reference_reconciliation_or_ai(module):
    source = Path(module.__file__).read_text(encoding="utf-8")
    for name in ("vlm_reconciliation", "reconcile_advisory_evidence", "vlm_assist"):
        assert name not in source


def test_t19_vector_parser_cannot_reach_reconciliation():
    import inspect

    source = inspect.getsource(pdf_drawing.VectorPdfDrawingParser)
    assert "reconcil" not in source.lower() and "vlm" not in source.lower()


def test_t23_reconciliation_module_has_no_network_sdk_env_clock_or_random_imports():
    path = Path(vlm_reconciliation.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = re.compile(
        r"^(socket|ssl|http|urllib|requests|httpx|aiohttp|openai|anthropic|google|azure|boto3|"
        r"ollama|transformers|huggingface_hub|random|secrets|uuid|os|subprocess|pathlib|"
        r"datetime|time|backend\.interoperability\.(pdf_drawing|ocr_drawing|raster_drawing))"
        r"(\.|$)"
    )
    assert not [name for name in imported if forbidden.match(name)]
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not names & {"environ", "getenv", "open", "socket", "urlopen"}


def test_make_identity_is_not_used_to_fake_the_provider():
    # Guard: the mock provider identity (not a fixture identity) is what R3C evidence carries.
    assert make_identity().provider_id != _MODEL.provider_id
