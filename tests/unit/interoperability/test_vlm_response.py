"""Phase 1D R3B: strict, fail-closed response schema and provenance validation."""

from __future__ import annotations

import ast
import json
import re
import socket
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

import backend.interoperability.ocr_drawing as ocr_drawing
import backend.interoperability.pdf_drawing as pdf_drawing
import backend.interoperability.raster_drawing as raster_drawing
import backend.interoperability.vlm_response as vlm_response
from backend.interoperability.drawing import (
    CanonicalDrawing,
    DrawingBoundingBox,
    DrawingExtractionAuthority,
    DrawingIngestionDiagnostics,
    DrawingIngestionResult,
    DrawingIngestionStatus,
    DrawingParserIdentity,
    DrawingRasterSource,
)
from backend.interoperability.vlm_assist import AiAssistedDrawingExtractor
from backend.interoperability.vlm_drawing import (
    DrawingVlmAssistConfig,
    DrawingVlmEvidenceKind,
    DrawingVlmLegibility,
    DrawingVlmRegion,
    DrawingVlmRegionKind,
    DrawingVlmValidationStatus,
    VlmLimits,
)
from backend.interoperability.vlm_provider import VlmResponse
from backend.interoperability.vlm_providers import DisabledVlmProvider, MockVlmProvider
from backend.interoperability.vlm_response import (
    VLM_RESPONSE_SCHEMA_VERSION,
    VlmResponseError,
    VlmResponseErrorCode,
    parse_vlm_response,
)
from tests.unit.interoperability.vlm_fixtures import make_identity, make_request

_SOURCE_ID = "synthetic::r3b.pdf"
_REQUEST_ID = "vlm-req-000000000000000000000001"
_MODEL = MockVlmProvider().identity()
_LIMITS = VlmLimits()
_ENABLED = DrawingVlmAssistConfig(enabled=True)
_CODE = VlmResponseErrorCode


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("network access is forbidden in R3B tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


def _box(x0: str, top: str, x1: str, bottom: str) -> DrawingBoundingBox:
    return DrawingBoundingBox(Decimal(x0), Decimal(top), Decimal(x1), Decimal(bottom))


def _region(region_id: str = "vlm-region-1") -> DrawingVlmRegion:
    raster = DrawingRasterSource(
        source_id=_SOURCE_ID,
        page_number=1,
        image_object_id="page-1:image-1",
        bounding_box=_box("0", "0", "400", "300"),
        parser_identity=DrawingParserIdentity("raster-drawing", "1.0", "ocr-preprocess-v1"),
        image_format="FLATE",
    )
    return DrawingVlmRegion(
        region_id=region_id,
        kind=DrawingVlmRegionKind.OCR_REVIEW,
        page_number=1,
        raster_source=raster,
        crop_px=(10, 20, 110, 70),
        pdf_box=_box("100", "200", "200", "250"),
        trigger_evidence_ids=("page-1:image-1:line-1-1-1",),
    )


def _request(request_id: str = _REQUEST_ID):
    # A 100 x 50 declared crop keeps pixel -> point scaling exactly 1:1.
    return replace(
        make_request(request_id, model=_MODEL), image_width_px=100, image_height_px=50
    )


def _item(**overrides) -> dict:
    item = {
        "candidate_type": "DIMENSION",
        "value": "25 mm",
        "legibility": "CLEAR",
        "confidence": 0.87,
        "box": [10, 5, 60, 17],
    }
    item.update(overrides)
    return {key: value for key, value in item.items() if value is not ...}


def _body(items=None, **overrides) -> dict:
    body = {
        "schema_version": VLM_RESPONSE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "prompt_contract_version": _request().prompt_contract_version,
        "provider_id": _MODEL.provider_id,
        "model_id": _MODEL.model_id,
        "model_version": _MODEL.model_version,
        "items": [_item()] if items is None else items,
    }
    body.update(overrides)
    return {key: value for key, value in body.items() if value is not ...}


def _bytes(body) -> bytes:
    return json.dumps(body).encode("utf-8")


def _response(payload: bytes, request_id: str = _REQUEST_ID, model=_MODEL) -> VlmResponse:
    return VlmResponse(request_id=request_id, reported_model=model, payload=payload)


def _parse(payload, *, request=None, region=None, limits=_LIMITS):
    data = payload if isinstance(payload, bytes) else _bytes(payload)
    return parse_vlm_response(
        _response(data), request or _request(), region or _region(), limits=limits
    )


def _rejected(payload, code, **kwargs) -> None:
    with pytest.raises(VlmResponseError) as raised:
        _parse(payload, **kwargs)
    assert raised.value.code is code


def _base_result() -> DrawingIngestionResult:
    return DrawingIngestionResult(
        source_id=_SOURCE_ID,
        diagnostics=DrawingIngestionDiagnostics(
            status=DrawingIngestionStatus.VALID,
            format_detected="PDF",
            parser_id="machiningpro.vector-pdf",
            parser_version="1.0.0",
        ),
        document=CanonicalDrawing(drawing_id="pdf-drawing-r3b", source_id=_SOURCE_ID),
    )


def _assist(outcomes, requests=None, regions=None, config=_ENABLED):
    requests = requests if requests is not None else [_request()]
    regions = regions if regions is not None else {r.request_id: _region() for r in requests}
    provider = MockVlmProvider(outcomes)
    base = _base_result()
    result = AiAssistedDrawingExtractor(provider, sleep=lambda _s: None).extract_candidates(
        base, requests, config=config, regions=regions
    )
    return base, result


# ---------------------------------------------------------------------------
# T01 / T14 / T18 — valid response, advisory authority, determinism
# ---------------------------------------------------------------------------


class TestValidResponse:
    def test_t01_valid_typed_response_is_accepted_with_full_provenance(self):
        (evidence,) = _parse(_body())
        assert evidence.evidence_kind is DrawingVlmEvidenceKind.DIMENSION
        assert evidence.raw_candidate == "25 mm"
        assert evidence.legibility is DrawingVlmLegibility.CLEAR
        assert evidence.validation_status is DrawingVlmValidationStatus.VALID
        assert evidence.reported_confidence == Decimal("0.87")
        assert evidence.source_location.confidence == Decimal("0.87")
        assert evidence.model == _MODEL
        assert evidence.prompt_contract_version == _request().prompt_contract_version
        assert evidence.request_id == _REQUEST_ID
        assert evidence.region_id == "vlm-region-1"
        assert evidence.sample_index == 0
        location = evidence.source_location
        assert location.source_id == _SOURCE_ID
        assert location.page_number == 1
        assert location.original_text == "25 mm"
        assert location.adapter_version == f"{_MODEL.model_id}@{_MODEL.model_version}"
        assert location.source_object_ids == (
            "page-1:image-1",
            "vlm-region-1",
            evidence.evidence_id,
        )
        # 1:1 scale, so the crop-pixel box offsets the region's PDF box exactly.
        assert location.bounding_box == _box("110", "205", "160", "217")

    def test_optional_fields_confidence_and_reference(self):
        item = _item(confidence=..., evidence_reference="page-1:image-1:line-1-1-1")
        (evidence,) = _parse(_body([item]))
        assert evidence.reported_confidence is None
        assert evidence.source_location.confidence is None
        assert "page-1:image-1:line-1-1-1" in evidence.source_location.source_object_ids

    def test_integer_confidence_boundaries_are_accepted(self):
        for value in (0, 1, 0.0, 1.0):
            (evidence,) = _parse(_body([_item(confidence=value)]))
            assert evidence.reported_confidence in (Decimal("0"), Decimal("1"))

    def test_empty_items_is_valid_and_yields_no_evidence(self):
        assert _parse(_body([])) == ()

    def test_every_supported_candidate_type_is_accepted(self):
        for kind in DrawingVlmEvidenceKind:
            (evidence,) = _parse(_body([_item(candidate_type=kind.value)]))
            assert evidence.evidence_kind is kind

    def test_t14_validated_evidence_is_advisory_and_never_normalized(self):
        (evidence,) = _parse(_body())
        assert evidence.source_location.authority is DrawingExtractionAuthority.ADVISORY
        assert evidence.normalized_dimension is None
        assert evidence.normalized_characteristic is None
        assert evidence.normalized_datum is None
        assert evidence.normalized_candidate is None

    def test_t18_repeated_parsing_is_deterministic(self):
        payload = _body([_item(), _item(value="DIA 10 mm", box=[0, 0, 20, 10])])
        first, second = _parse(payload), _parse(payload)
        assert first == second
        assert len({item.evidence_id for item in first}) == 2

    def test_evidence_ids_differ_by_request_region_and_sample(self):
        one = _parse(_body())[0].evidence_id
        other_region = _parse(_body(), region=_region("vlm-region-2"))[0].evidence_id
        sample = parse_vlm_response(
            _response(_bytes(_body())), _request(), _region(), limits=_LIMITS, sample_index=1
        )[0].evidence_id
        assert len({one, other_region, sample}) == 3


# ---------------------------------------------------------------------------
# T02 / T03 — structure
# ---------------------------------------------------------------------------


class TestStructure:
    @pytest.mark.parametrize(
        "key",
        [
            "schema_version",
            "request_id",
            "prompt_contract_version",
            "provider_id",
            "model_id",
            "model_version",
            "items",
        ],
    )
    def test_t02_missing_top_level_field_rejected(self, key):
        _rejected(_body(**{key: ...}), _CODE.MISSING_FIELD)

    @pytest.mark.parametrize("key", ["candidate_type", "value", "legibility", "box"])
    def test_t02_missing_item_field_rejected(self, key):
        _rejected(_body([_item(**{key: ...})]), _CODE.MISSING_FIELD)

    @pytest.mark.parametrize("document", [[], "text", 3, None, True])
    def test_t03_wrong_top_level_type_rejected(self, document):
        _rejected(_bytes(document), _CODE.TOP_LEVEL_TYPE)

    @pytest.mark.parametrize("items", [{}, "x", 3, None])
    def test_items_must_be_a_list(self, items):
        _rejected(_body(items=...) | {"items": items}, _CODE.ITEMS_INVALID)

    @pytest.mark.parametrize("item", ["x", 3, None, []])
    def test_each_item_must_be_an_object(self, item):
        _rejected(_body([item]), _CODE.ITEMS_INVALID)

    def test_unknown_top_level_and_item_fields_rejected(self):
        _rejected(_body(extra="x"), _CODE.UNKNOWN_FIELD)
        _rejected(_body([_item(page=7)]), _CODE.UNKNOWN_FIELD)

    @pytest.mark.parametrize("key", ["normalized_value", "rationale", "authority", "warnings"])
    def test_model_cannot_supply_normalized_values_or_authority(self, key):
        _rejected(_body([_item(**{key: "x"})]), _CODE.UNKNOWN_FIELD)

    def test_duplicate_json_keys_rejected(self):
        raw = _bytes(_body()).decode()
        raw = raw.replace('"items"', '"request_id": "other", "items"', 1)
        _rejected(raw.encode(), _CODE.DUPLICATE_KEY)

    def test_invalid_utf8_and_invalid_json_rejected(self):
        _rejected(b"\xff\xfe\x00", _CODE.NOT_UTF8)
        _rejected(b"{not json", _CODE.NOT_JSON)
        _rejected(b"", _CODE.NOT_JSON)
        _rejected(b"[" * 100_000, _CODE.NOT_JSON)

    def test_too_many_items_and_oversized_payload_rejected(self):
        limits = VlmLimits(items_per_response=1)
        _rejected(_body([_item(), _item()]), _CODE.TOO_MANY_ITEMS, limits=limits)
        _rejected(b" " * 300_000, _CODE.TOO_LARGE)

    def test_schema_version_must_match(self):
        older = "machiningpro.drawing-vlm.response.v0"
        _rejected(_body(schema_version=older), _CODE.SCHEMA_VERSION)
        _rejected(_body(schema_version=1), _CODE.SCHEMA_VERSION)


# ---------------------------------------------------------------------------
# T04 — candidate type, value, legibility
# ---------------------------------------------------------------------------


class TestCandidateFields:
    @pytest.mark.parametrize("value", ["WELD", "dimension", "", None, 5, ["DIMENSION"]])
    def test_t04_unsupported_candidate_type_rejected(self, value):
        _rejected(_body([_item(candidate_type=value)]), _CODE.CANDIDATE_TYPE)

    @pytest.mark.parametrize("value", ["", "   ", None, 5, "a\x00b", "line\nbreak", "x" * 257])
    def test_invalid_value_rejected(self, value):
        _rejected(_body([_item(value=value)]), _CODE.VALUE_INVALID)

    @pytest.mark.parametrize("value", ["clear", "UNKNOWN", None, 1])
    def test_invalid_legibility_rejected(self, value):
        _rejected(_body([_item(legibility=value)]), _CODE.LEGIBILITY)


# ---------------------------------------------------------------------------
# T05 / T06 / T07 — confidence
# ---------------------------------------------------------------------------


class TestConfidence:
    @pytest.mark.parametrize("value", ["0.9", True, False, [0.5], {"v": 1}, 85, 100, -0.1, 1.01])
    def test_t05_malformed_or_out_of_range_confidence_rejected(self, value):
        _rejected(_body([_item(confidence=value)]), _CODE.CONFIDENCE)

    def test_t05_percentages_are_never_reinterpreted(self):
        _rejected(_body([_item(confidence=87)]), _CODE.CONFIDENCE)

    @pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
    def test_t06_t07_non_finite_confidence_rejected(self, token):
        raw = _bytes(_body()).decode().replace("0.87", token)
        _rejected(raw.encode(), _CODE.NON_FINITE_NUMBER)

    def test_huge_exponent_confidence_is_out_of_range(self):
        raw = _bytes(_body()).decode().replace("0.87", "1e999")
        _rejected(raw.encode(), _CODE.CONFIDENCE)


# ---------------------------------------------------------------------------
# T08 / T09 / T10 — page, bounding box, provenance
# ---------------------------------------------------------------------------


class TestGeometryAndProvenance:
    def test_t08_page_is_derived_from_the_region_and_cannot_be_supplied(self):
        _rejected(_body([_item(page=2)]), _CODE.UNKNOWN_FIELD)
        _rejected(_body(page_number=0), _CODE.UNKNOWN_FIELD)

    def test_t08_invalid_page_region_cannot_exist(self):
        with pytest.raises(ValueError):
            replace(_region(), page_number=0)
        with pytest.raises(ValueError):
            replace(_region(), page_number=2)  # does not match the raster source page

    @pytest.mark.parametrize(
        "box",
        [
            [10, 5, 5, 17],  # inverted x
            [10, 17, 60, 5],  # inverted y
            [10, 5, 10, 17],  # zero width
            [10, 5, 60, 5],  # zero height
            [-1, 0, 20, 20],  # negative
            [0, 0, 101, 20],  # beyond image width
            [0, 0, 20, 51],  # beyond image height
            [1, 2, 3],  # wrong length
            [1, 2, 3, 4, 5],
            [1.5, 2, 30, 40],  # fractional coordinate
            [True, 0, 20, 20],  # bool is not an int
            ["1", 2, 3, 4],
            "10,5,60,17",
            None,
            {"x0": 1},
        ],
    )
    def test_t09_malformed_bounding_box_rejected(self, box):
        _rejected(_body([_item(box=box)]), _CODE.BOX)

    def test_full_image_box_is_accepted(self):
        (evidence,) = _parse(_body([_item(box=[0, 0, 100, 50])]))
        assert evidence.source_location.bounding_box == _box("100", "200", "200", "250")

    def test_t10_unknown_evidence_reference_rejected(self):
        _rejected(_body([_item(evidence_reference="not-a-trigger")]), _CODE.EVIDENCE_REFERENCE)
        _rejected(_body([_item(evidence_reference=5)]), _CODE.EVIDENCE_REFERENCE)

    def test_t10_region_without_raster_provenance_cannot_exist(self):
        with pytest.raises(TypeError):
            replace(_region(), raster_source=None)  # type: ignore[arg-type]

    def test_scaling_follows_the_declared_crop_size(self):
        request = replace(_request(), image_width_px=200, image_height_px=100)
        (evidence,) = _parse(_body([_item(box=[0, 0, 200, 100])]), request=request)
        assert evidence.source_location.bounding_box == _box("100", "200", "200", "250")


# ---------------------------------------------------------------------------
# T11 / T12 / T13 — identity
# ---------------------------------------------------------------------------


class TestIdentity:
    @pytest.mark.parametrize(
        "field", ["provider_id", "model_id", "model_version", "prompt_contract_version"]
    )
    def test_t11_t13_body_identity_mismatch_rejected(self, field):
        _rejected(_body(**{field: "someone-else"}), _CODE.IDENTITY_MISMATCH)

    @pytest.mark.parametrize("field", ["provider_id", "model_id", "model_version"])
    @pytest.mark.parametrize("value", [None, 5, "", ["x"]])
    def test_t13_malformed_model_identity_rejected(self, field, value):
        _rejected(_body(**{field: value}), _CODE.IDENTITY_MISMATCH)

    def test_t12_body_request_id_mismatch_rejected(self):
        _rejected(_body(request_id="vlm-req-other"), _CODE.IDENTITY_MISMATCH)

    def test_t12_envelope_request_id_mismatch_rejected(self):
        with pytest.raises(VlmResponseError) as raised:
            parse_vlm_response(
                _response(_bytes(_body()), request_id="vlm-req-other"),
                _request(),
                _region(),
                limits=_LIMITS,
            )
        assert raised.value.code is _CODE.IDENTITY_MISMATCH

    def test_t11_envelope_model_mismatch_rejected(self):
        other = make_identity(provider_id="someone.else")
        with pytest.raises(VlmResponseError) as raised:
            parse_vlm_response(
                _response(_bytes(_body()), model=other), _request(), _region(), limits=_LIMITS
            )
        assert raised.value.code is _CODE.IDENTITY_MISMATCH

    def test_error_carries_only_a_stable_code(self):
        error = VlmResponseError(_CODE.NOT_JSON)
        assert str(error) == "NOT_JSON" and repr(error) == "VlmResponseError(NOT_JSON)"
        with pytest.raises(TypeError):
            VlmResponseError("free text")  # type: ignore[arg-type]

    def test_argument_types_are_validated(self):
        with pytest.raises(TypeError):
            parse_vlm_response(b"{}", _request(), _region(), limits=_LIMITS)  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            parse_vlm_response(_response(b"{}"), _request(), _region(), limits=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# T15 / T16 / T17 — orchestrated: deterministic evidence is never touched
# ---------------------------------------------------------------------------


class TestOrchestratedAuthorityBoundary:
    def test_t15_valid_response_leaves_deterministic_result_unchanged(self):
        before = repr(_base_result())
        base, outcome = _assist([_bytes(_body())])
        assert outcome.result is base
        assert repr(outcome.result) == before
        assert outcome.advisory.status is DrawingIngestionStatus.VALID
        assert len(outcome.advisory.evidence) == 1
        assert outcome.advisory.findings == ()
        assert all(
            item.source_location.authority is DrawingExtractionAuthority.ADVISORY
            for item in outcome.advisory.evidence
        )
        assert outcome.result.document.all_dimensions == ()
        assert outcome.advisory.regions == (_region(),)

    def test_t16_rejected_response_leaves_deterministic_result_unchanged(self):
        before = repr(_base_result())
        base, outcome = _assist([_bytes(_body(items=[_item(confidence=87)]))])
        assert outcome.result is base
        assert repr(outcome.result) == before

    def test_t17_malformed_response_produces_no_evidence_or_findings(self):
        for payload in (b"{bad", _bytes([1, 2]), _bytes(_body(request_id="x"))):
            _, outcome = _assist([payload])
            assert outcome.advisory.status is DrawingIngestionStatus.FAILED
            assert outcome.advisory.evidence == () and outcome.advisory.findings == ()
            assert outcome.advisory.diagnostics[0].startswith("VLM_RESPONSE_")

    def test_diagnostics_are_constant_codes_without_provider_text(self):
        _, outcome = _assist([_bytes(_body([_item(value="SECRET-VENDOR-TEXT\x00")]))])
        assert outcome.advisory.diagnostics == ("VLM_RESPONSE_VALUE_INVALID",)
        assert "SECRET" not in repr(outcome)

    def test_one_bad_response_rejects_everything_with_no_partial_evidence(self):
        second = "vlm-req-000000000000000000000002"
        requests = [_request(), _request(second)]
        good = _bytes(_body())
        bad = _bytes(_body(request_id=second, items=[_item(box=[5, 5, 1, 1])]))
        _, outcome = _assist([good, bad], requests=requests)
        assert outcome.advisory.status is DrawingIngestionStatus.FAILED
        assert outcome.advisory.evidence == ()
        assert outcome.advisory.diagnostics == ("VLM_RESPONSE_BOX",)

    def test_multiple_valid_requests_share_regions_and_keep_order(self):
        second = "vlm-req-000000000000000000000002"
        requests = [_request(), _request(second)]
        payloads = [
            _bytes(_body()),
            _bytes(_body(request_id=second, items=[_item(value="DIA 10 mm")])),
        ]
        _, outcome = _assist(payloads, requests=requests)
        assert [e.raw_candidate for e in outcome.advisory.evidence] == ["25 mm", "DIA 10 mm"]
        assert [e.request_id for e in outcome.advisory.evidence] == [_REQUEST_ID, second]
        assert len(outcome.advisory.regions) == 1  # same region reused
        assert outcome.advisory.request_count == 2

    def test_empty_items_yield_no_candidates_not_valid(self):
        _, outcome = _assist([_bytes(_body([]))])
        assert outcome.advisory.status is DrawingIngestionStatus.INSUFFICIENT_DATA
        assert outcome.advisory.diagnostics == ("VLM_NO_CANDIDATES",)
        assert outcome.advisory.evidence == ()

    def test_evidence_total_limit_fails_closed(self):
        config = DrawingVlmAssistConfig(
            enabled=True, limits=VlmLimits(evidence_items_total=1)
        )
        payload = _bytes(_body([_item(), _item(value="DIA 10 mm", box=[0, 0, 20, 10])]))
        _, outcome = _assist([payload], config=config)
        assert outcome.advisory.status is DrawingIngestionStatus.FAILED
        assert outcome.advisory.diagnostics == ("VLM_EVIDENCE_LIMIT",)
        assert outcome.advisory.evidence == ()

    def test_orchestrated_parse_is_deterministic(self):
        first = _assist([_bytes(_body())])[1]
        second = _assist([_bytes(_body())])[1]
        assert first == second

    def test_every_request_needs_a_region(self):
        with pytest.raises(ValueError):
            _assist([_bytes(_body())], regions={})

    def test_conflicting_regions_sharing_an_id_are_rejected(self):
        second = "vlm-req-000000000000000000000002"
        other = replace(_region(), crop_px=(0, 0, 5, 5))
        with pytest.raises(ValueError):
            _assist(
                [_bytes(_body()), _bytes(_body(request_id=second))],
                requests=[_request(), _request(second)],
                regions={_REQUEST_ID: _region(), second: other},
            )

    def test_without_regions_r3a_behavior_is_unchanged(self):
        provider = MockVlmProvider([_bytes(_body())])
        outcome = AiAssistedDrawingExtractor(provider).extract_candidates(
            _base_result(), [_request()], config=_ENABLED
        )
        assert outcome.advisory.evidence == ()
        assert outcome.advisory.diagnostics == ("VLM_RESPONSES_NOT_PARSED",)

    def test_disabled_config_never_parses_or_calls(self):
        provider = MockVlmProvider([_bytes(_body())])
        outcome = AiAssistedDrawingExtractor(provider).extract_candidates(
            _base_result(),
            [_request()],
            config=DrawingVlmAssistConfig(),
            regions={_REQUEST_ID: _region()},
        )
        assert outcome.advisory is None and provider.call_count == 0

    def test_t19_disabled_provider_behavior_unchanged(self):
        provider = DisabledVlmProvider()
        request = replace(
            make_request(model=provider.identity()), image_width_px=100, image_height_px=50
        )
        base = _base_result()
        outcome = AiAssistedDrawingExtractor(provider).extract_candidates(
            base, [request], config=_ENABLED, regions={request.request_id: _region()}
        )
        assert outcome.result is base
        assert outcome.advisory.status is DrawingIngestionStatus.UNSUPPORTED
        assert outcome.advisory.diagnostics == ("VLM_DISABLED",)
        assert outcome.advisory.evidence == ()

    def test_t20_mock_provider_stays_deterministic(self):
        assert _assist([_bytes(_body())])[1] == _assist([_bytes(_body())])[1]


# ---------------------------------------------------------------------------
# T21 / T22 / T23 — reachability and no network
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module", [pdf_drawing, ocr_drawing, raster_drawing], ids=lambda m: m.__name__
)
def test_t21_t22_deterministic_modules_never_reference_the_response_parser(module):
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "vlm_response" not in source and "parse_vlm_response" not in source


def test_t23_response_module_has_no_network_sdk_env_clock_or_random_imports():
    path = Path(vlm_response.__file__)
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
        r"datetime|time)(\.|$)"
    )
    assert not [name for name in imported if forbidden.match(name)]
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not names & {"environ", "getenv", "open", "socket", "urlopen"}
