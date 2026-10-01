"""Phase 1D Task 2 — VLM drawing evidence, config and limits contract tests."""

from __future__ import annotations

import ast
import re
import socket
from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal
from pathlib import Path

import pytest

import backend.interoperability.vlm_drawing as vlm_drawing
from backend.interoperability.drawing import (
    CanonicalDrawing,
    DrawingBoundingBox,
    DrawingDatumReference,
    DrawingDimension,
    DrawingExtractionAuthority,
    DrawingGdtCharacteristic,
    DrawingIngestionDiagnostics,
    DrawingIngestionResult,
    DrawingIngestionStatus,
    DrawingParserIdentity,
    DrawingRasterSource,
    DrawingSourceLocation,
)
from backend.interoperability.gdt_drawing import (
    GdtTokenSource,
    recognize_feature_control_frames,
)
from backend.interoperability.vlm_drawing import (
    DrawingAdvisoryReport,
    DrawingAssistedIngestionResult,
    DrawingEvidenceOrigin,
    DrawingVlmAssistConfig,
    DrawingVlmEvidence,
    DrawingVlmEvidenceKind,
    DrawingVlmFinding,
    DrawingVlmLegibility,
    DrawingVlmMode,
    DrawingVlmRationale,
    DrawingVlmReconciliationStatus,
    DrawingVlmRegion,
    DrawingVlmRegionKind,
    DrawingVlmValidationStatus,
    VlmLimits,
)
from tests.unit.interoperability.vlm_fixtures import (
    FAKE_PROMPT_CONTRACT_VERSION,
    make_identity,
)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("network access is forbidden in VLM drawing tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


_SOURCE_ID = "synthetic::vlm-drawing.pdf"
_FINGERPRINT_A = "a" * 64
_FINGERPRINT_B = "0123456789abcdef" * 4


def _box(x0: str = "10", top: str = "20", x1: str = "60", bottom: str = "32") -> DrawingBoundingBox:
    return DrawingBoundingBox(Decimal(x0), Decimal(top), Decimal(x1), Decimal(bottom))


def _raster(page: int = 1) -> DrawingRasterSource:
    return DrawingRasterSource(
        source_id=_SOURCE_ID,
        page_number=page,
        image_object_id=f"page-{page}:image-1",
        bounding_box=_box("0", "0", "400", "300"),
        parser_identity=DrawingParserIdentity("raster-drawing", "1.0", "ocr-preprocess-v1"),
        image_format="FLATE",
    )


def _region(region_id: str = "vlm-region-1", **overrides) -> DrawingVlmRegion:
    values = {
        "region_id": region_id,
        "kind": DrawingVlmRegionKind.OCR_REVIEW,
        "page_number": 1,
        "raster_source": _raster(),
        "crop_px": (10, 20, 110, 60),
        "pdf_box": _box(),
        "trigger_evidence_ids": ("page-1:image-1:line-1-1-1",),
    }
    values.update(overrides)
    return DrawingVlmRegion(**values)


_VLM_PARSER = DrawingParserIdentity("machiningpro.vlm-assist", "1.0.0", "vlm-crop-v1")


def _location(
    *,
    evidence_id: str = "vlm-ev-1",
    region_id: str = "vlm-region-1",
    text: str = "25 mm",
    confidence: Decimal | None = Decimal("0.870000"),
    authority: DrawingExtractionAuthority = DrawingExtractionAuthority.ADVISORY,
    box: DrawingBoundingBox | None = None,
) -> DrawingSourceLocation:
    return DrawingSourceLocation(
        source_id=_SOURCE_ID,
        sheet_number=1,
        page_number=1,
        original_text=text,
        adapter_id="machiningpro.vlm-assist",
        adapter_version="fake-vlm@2026-09-24",
        confidence=confidence,
        authority=authority,
        bounding_box=box or _box(),
        source_object_ids=("page-1:image-1", region_id, evidence_id),
    )


def _evidence(evidence_id: str = "vlm-ev-1", **overrides) -> DrawingVlmEvidence:
    values = {
        "evidence_id": evidence_id,
        "evidence_kind": DrawingVlmEvidenceKind.DIMENSION,
        "raw_candidate": "25 mm",
        "legibility": DrawingVlmLegibility.CLEAR,
        "source_location": _location(evidence_id=evidence_id),
        "parser_identity": _VLM_PARSER,
        "model": make_identity(),
        "prompt_contract_version": FAKE_PROMPT_CONTRACT_VERSION,
        "region_id": "vlm-region-1",
        "request_id": "vlm-req-1",
        "sample_index": 0,
        "validation_status": DrawingVlmValidationStatus.VALID,
        "reported_confidence": Decimal("0.870000"),
    }
    values.update(overrides)
    return DrawingVlmEvidence(**values)


def _finding(finding_id: str = "vlm-finding-1", **overrides) -> DrawingVlmFinding:
    values = {
        "finding_id": finding_id,
        "status": DrawingVlmReconciliationStatus.CORROBORATED,
        "rationale": DrawingVlmRationale.EXACT_MATCH,
        "ai_evidence_ids": ("vlm-ev-1",),
        "deterministic_support_ids": ("pdf-dim-p0001-000001",),
        "deterministic_origins": (DrawingEvidenceOrigin.VECTOR,),
    }
    values.update(overrides)
    return DrawingVlmFinding(**values)


def _report(**overrides) -> DrawingAdvisoryReport:
    values = {
        "status": DrawingIngestionStatus.VALID,
        "prompt_contract_version": FAKE_PROMPT_CONTRACT_VERSION,
        "model": make_identity(),
        "config_fingerprint": _FINGERPRINT_A,
        "base_result_fingerprint": _FINGERPRINT_B,
        "regions": (_region(),),
        "evidence": (_evidence(),),
        "findings": (_finding(),),
        "diagnostics": (),
        "request_count": 1,
    }
    values.update(overrides)
    return DrawingAdvisoryReport(**values)


def _base_result() -> DrawingIngestionResult:
    return DrawingIngestionResult(
        source_id=_SOURCE_ID,
        diagnostics=DrawingIngestionDiagnostics(
            status=DrawingIngestionStatus.VALID,
            format_detected="PDF",
            parser_id="machiningpro.vector-pdf",
            parser_version="1.0.0",
        ),
        document=CanonicalDrawing(drawing_id="pdf-drawing-abc", source_id=_SOURCE_ID),
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("enum_type", "members"),
    [
        (DrawingEvidenceOrigin, ["VECTOR", "OCR", "AI_VLM"]),
        (DrawingVlmMode, ["BLIND", "GUIDED"]),
        (
            DrawingVlmRegionKind,
            ["OCR_REVIEW", "TITLE_BLOCK", "GDT_CANDIDATE", "IMAGE_OVERVIEW"],
        ),
        (
            DrawingVlmEvidenceKind,
            ["TEXT", "TITLE_FIELD", "DIMENSION", "DATUM_LABEL", "GDT_CHARACTERISTIC", "NOTE"],
        ),
        (DrawingVlmLegibility, ["CLEAR", "DEGRADED", "ILLEGIBLE"]),
        (DrawingVlmValidationStatus, ["VALID", "REJECTED"]),
        (
            DrawingVlmReconciliationStatus,
            [
                "CORROBORATED",
                "RECOVERY_CANDIDATE",
                "CONFLICT",
                "ADVISORY_ONLY",
                "REJECTED",
                "UNSTABLE",
            ],
        ),
        (
            DrawingVlmRationale,
            [
                "EXACT_MATCH",
                "OCR_BELOW_THRESHOLD",
                "DETERMINISTIC_OMITTED",
                "NO_DETERMINISTIC_EVIDENCE",
                "VALUE_MISMATCH",
                "DECIMAL_MISMATCH",
                "UNIT_MISMATCH",
                "TYPE_MISMATCH",
                "TOLERANCE_MISMATCH",
                "CHARACTER_MISMATCH",
                "GRAMMAR_REJECTED",
                "UNIT_NOT_EVIDENCED",
                "BARE_NUMBER",
                "INSIDE_TITLE_BLOCK",
                "IDENTIFIER_CONTEXT",
                "LABEL_NOT_EVIDENCED",
                "OUTSIDE_REGION",
                "UNSUPPORTED_KIND",
                "SAMPLE_DISAGREEMENT",
            ],
        ),
    ],
)
def test_enums_have_exactly_the_approved_members(enum_type, members):
    assert [item.value for item in enum_type] == members


def test_gdt_token_source_is_not_extended_with_ai():
    assert [item.value for item in GdtTokenSource] == ["VECTOR", "OCR"]


def test_vlm_evidence_cannot_enter_deterministic_gdt_recognition():
    with pytest.raises(TypeError):
        recognize_feature_control_frames([_evidence()])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------


class TestVlmLimits:
    def test_defaults_are_exactly_the_approved_values(self):
        limits = VlmLimits()
        assert limits.ocr_review_floor == Decimal("0.50")
        assert isinstance(limits.ocr_review_floor, Decimal)
        assert (
            limits.pages_considered,
            limits.regions_per_page,
            limits.regions_total,
            limits.crop_longest_edge_px,
            limits.crop_pixels,
            limits.crop_png_bytes,
            limits.requests_per_document,
            limits.samples_per_region,
            limits.maximum_samples_per_region,
            limits.attempts_per_request,
            limits.response_bytes,
            limits.output_tokens_hint,
            limits.items_per_response,
            limits.evidence_items_total,
            limits.raw_candidate_chars,
            limits.request_timeout_seconds,
            limits.assist_total_budget_seconds,
            limits.crop_worker_timeout_seconds,
            limits.region_padding_px,
            limits.diagnostics_max_count,
            limits.diagnostic_max_chars,
        ) == (
            10, 16, 64, 2_048, 4_194_304, 4_194_304, 64, 1, 3, 2, 262_144, 2_048,
            200, 5_000, 256, 30, 120, 30, 8, 50, 240,
        )

    @pytest.mark.parametrize(
        "name",
        [
            item.name
            for item in fields(VlmLimits)
            if item.name not in ("ocr_review_floor", "region_padding_px")
        ],
    )
    @pytest.mark.parametrize("value", [0, -1])
    def test_positive_int_limits_reject_zero_and_negative(self, name, value):
        with pytest.raises(ValueError):
            VlmLimits(**{name: value})

    @pytest.mark.parametrize("name", [item.name for item in fields(VlmLimits)][1:])
    @pytest.mark.parametrize("value", [True, 1.5, "8"])
    def test_int_limits_reject_bool_float_and_str(self, name, value):
        with pytest.raises(TypeError):
            VlmLimits(**{name: value})

    def test_region_padding_may_be_zero_but_not_negative(self):
        assert VlmLimits(region_padding_px=0).region_padding_px == 0
        with pytest.raises(ValueError):
            VlmLimits(region_padding_px=-1)

    @pytest.mark.parametrize("value", [Decimal("0"), Decimal("1"), Decimal("0.5")])
    def test_ocr_review_floor_boundaries_accepted(self, value):
        assert VlmLimits(ocr_review_floor=value).ocr_review_floor == value

    @pytest.mark.parametrize(
        "value", [Decimal("-0.01"), Decimal("1.01"), Decimal("NaN"), Decimal("Infinity")]
    )
    def test_ocr_review_floor_out_of_range_rejected(self, value):
        with pytest.raises(ValueError):
            VlmLimits(ocr_review_floor=value)

    @pytest.mark.parametrize("value", [0.5, "0.5", 1])
    def test_ocr_review_floor_must_be_decimal(self, value):
        with pytest.raises(TypeError):
            VlmLimits(ocr_review_floor=value)  # type: ignore[arg-type]

    def test_regions_per_page_must_not_exceed_total(self):
        assert VlmLimits(regions_per_page=64, regions_total=64).regions_per_page == 64
        with pytest.raises(ValueError, match="regions_total"):
            VlmLimits(regions_per_page=65, regions_total=64)

    def test_samples_default_and_maximum_relationship(self):
        assert VlmLimits(samples_per_region=3).samples_per_region == 3
        with pytest.raises(ValueError, match="maximum_samples_per_region"):
            VlmLimits(samples_per_region=4)
        assert VlmLimits(samples_per_region=5, maximum_samples_per_region=5)

    def test_timeouts_must_fit_the_total_budget(self):
        with pytest.raises(ValueError, match="request_timeout_seconds"):
            VlmLimits(request_timeout_seconds=121)
        with pytest.raises(ValueError, match="crop_worker_timeout_seconds"):
            VlmLimits(crop_worker_timeout_seconds=121)
        assert VlmLimits(request_timeout_seconds=120, crop_worker_timeout_seconds=120)

    def test_limits_are_frozen(self):
        with pytest.raises(FrozenInstanceError):
            VlmLimits().regions_total = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Assistance configuration
# ---------------------------------------------------------------------------


class TestAssistConfig:
    def test_conservative_defaults(self):
        config = DrawingVlmAssistConfig()
        assert config.enabled is False
        assert config.mode is DrawingVlmMode.BLIND
        assert config.allow_remote is False
        assert config.remote_allow_title_block is False
        assert config.assist_on_insufficient_data is False
        assert config.require_audit_for_remote is True
        assert config.allowed_provider_ids == ()
        assert config.limits == VlmLimits()

    def test_provider_ids_are_stored_in_deterministic_order(self):
        first = DrawingVlmAssistConfig(allowed_provider_ids=("local.b", "local.a"))
        second = DrawingVlmAssistConfig(allowed_provider_ids=("local.a", "local.b"))
        assert first.allowed_provider_ids == ("local.a", "local.b")
        assert first == second
        assert repr(first) == repr(second)

    def test_duplicate_provider_ids_rejected(self):
        with pytest.raises(ValueError, match="duplicates"):
            DrawingVlmAssistConfig(allowed_provider_ids=("local.a", "local.a"))

    @pytest.mark.parametrize("value", ["", "  ", "local\na", "x" * 129])
    def test_bad_provider_ids_rejected(self, value):
        with pytest.raises(ValueError):
            DrawingVlmAssistConfig(allowed_provider_ids=(value,))

    def test_provider_ids_must_be_tuple_of_str(self):
        with pytest.raises(TypeError):
            DrawingVlmAssistConfig(allowed_provider_ids=["local.a"])  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            DrawingVlmAssistConfig(allowed_provider_ids=(1,))  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "name",
        [
            "enabled",
            "allow_remote",
            "remote_allow_title_block",
            "assist_on_insufficient_data",
            "require_audit_for_remote",
        ],
    )
    def test_flags_must_be_bool(self, name):
        with pytest.raises(TypeError):
            DrawingVlmAssistConfig(**{name: 1})

    def test_mode_and_limits_are_typed(self):
        with pytest.raises(TypeError):
            DrawingVlmAssistConfig(mode="BLIND")  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            DrawingVlmAssistConfig(limits={})  # type: ignore[arg-type]

    def test_remote_fields_are_structural_only(self):
        config = DrawingVlmAssistConfig(enabled=True, allow_remote=True)
        assert config.allow_remote is True
        assert not any("url" in item.name or "key" in item.name for item in fields(config))

    def test_config_is_frozen(self):
        with pytest.raises(FrozenInstanceError):
            DrawingVlmAssistConfig().enabled = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Region
# ---------------------------------------------------------------------------


class TestRegion:
    def test_valid_region(self):
        region = _region()
        assert region.kind is DrawingVlmRegionKind.OCR_REVIEW
        assert region.crop_px == (10, 20, 110, 60)

    @pytest.mark.parametrize("crop", [(1, 2, 3), (1, 2, 3, 4, 5), [0, 0, 10, 10]])
    def test_malformed_crop_tuple_rejected(self, crop):
        with pytest.raises(TypeError):
            _region(crop_px=crop)

    @pytest.mark.parametrize("crop", [(True, 0, 10, 10), (0, 0, 10.0, 10), (0, "0", 10, 10)])
    def test_non_int_or_bool_coordinates_rejected(self, crop):
        with pytest.raises(TypeError):
            _region(crop_px=crop)

    @pytest.mark.parametrize(
        "crop", [(10, 0, 10, 10), (20, 0, 10, 10), (0, 10, 10, 10), (0, 20, 10, 10)]
    )
    def test_empty_or_reversed_coordinates_rejected(self, crop):
        with pytest.raises(ValueError):
            _region(crop_px=crop)

    def test_negative_coordinates_rejected(self):
        with pytest.raises(ValueError):
            _region(crop_px=(-1, 0, 10, 10))

    def test_duplicate_or_blank_trigger_ids_rejected(self):
        with pytest.raises(ValueError, match="duplicates"):
            _region(trigger_evidence_ids=("a", "a"))
        with pytest.raises(ValueError):
            _region(trigger_evidence_ids=("",))

    @pytest.mark.parametrize("page", [0, -1])
    def test_invalid_page_rejected(self, page):
        with pytest.raises(ValueError):
            _region(page_number=page)

    def test_page_must_match_raster_source(self):
        with pytest.raises(ValueError, match="raster_source"):
            _region(page_number=2)

    def test_typed_fields(self):
        with pytest.raises(TypeError):
            _region(kind="OCR_REVIEW")
        with pytest.raises(TypeError):
            _region(pdf_box=(0, 0, 1, 1))
        with pytest.raises(TypeError):
            _region(raster_source="page-1:image-1")

    def test_region_is_frozen(self):
        with pytest.raises(FrozenInstanceError):
            _region().region_id = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


class TestEvidence:
    def test_valid_advisory_evidence(self):
        evidence = _evidence(
            normalized_dimension=DrawingDimension(
                dimension_id="vlm-ev-1", nominal_value=Decimal("25"), unit="mm"
            ),
            normalized_candidate="25 mm",
        )
        assert evidence.source_location.authority is DrawingExtractionAuthority.ADVISORY
        assert evidence.normalized_dimension.nominal_value == Decimal("25")

    @pytest.mark.parametrize(
        "authority",
        [
            DrawingExtractionAuthority.EXTRACTED,
            DrawingExtractionAuthority.DECLARED,
            DrawingExtractionAuthority.INFERRED,
        ],
    )
    def test_non_advisory_source_location_rejected(self, authority):
        with pytest.raises(ValueError, match="ADVISORY"):
            _evidence(source_location=_location(authority=authority))

    @pytest.mark.parametrize(
        "value", [Decimal("-0.1"), Decimal("1.1"), Decimal("NaN"), Decimal("Infinity")]
    )
    def test_invalid_confidence_rejected(self, value):
        with pytest.raises(ValueError):
            _evidence(reported_confidence=value)

    def test_confidence_must_be_decimal_or_none_and_mirrored(self):
        with pytest.raises(TypeError):
            _evidence(reported_confidence=0.8)
        with pytest.raises(ValueError, match="mirror"):
            _evidence(reported_confidence=Decimal("0.5"))
        evidence = _evidence(
            reported_confidence=None, source_location=_location(confidence=None)
        )
        assert evidence.reported_confidence is None

    @pytest.mark.parametrize("value", [-1, True, 1.0, "0"])
    def test_invalid_sample_index_rejected(self, value):
        with pytest.raises((TypeError, ValueError)):
            _evidence(sample_index=value)

    def test_valid_with_rejection_rationale_rejected(self):
        with pytest.raises(ValueError, match="rejection_rationale"):
            _evidence(rejection_rationale=DrawingVlmRationale.BARE_NUMBER)

    def test_rejected_requires_rationale(self):
        with pytest.raises(ValueError, match="rejection_rationale"):
            _evidence(validation_status=DrawingVlmValidationStatus.REJECTED)
        rejected = _evidence(
            validation_status=DrawingVlmValidationStatus.REJECTED,
            rejection_rationale=DrawingVlmRationale.UNIT_NOT_EVIDENCED,
        )
        assert rejected.rejection_rationale is DrawingVlmRationale.UNIT_NOT_EVIDENCED

    def test_valid_evidence_requires_mapped_box_but_rejected_may_omit_it(self):
        location = replace(_location(), bounding_box=None)
        with pytest.raises(ValueError, match="bounding box"):
            _evidence(source_location=location)
        rejected = _evidence(
            source_location=location,
            validation_status=DrawingVlmValidationStatus.REJECTED,
            rejection_rationale=DrawingVlmRationale.OUTSIDE_REGION,
        )
        assert rejected.source_location.bounding_box is None

    def test_provenance_must_reference_region_and_evidence(self):
        location = replace(_location(), source_object_ids=("page-1:image-1", "vlm-ev-1"))
        with pytest.raises(ValueError, match="region_id"):
            _evidence(source_location=location)

    def test_provenance_original_text_must_equal_raw_candidate(self):
        with pytest.raises(ValueError, match="raw_candidate"):
            _evidence(source_location=_location(text="26 mm"))

    def test_page_is_required(self):
        with pytest.raises(ValueError, match="page_number"):
            _evidence(source_location=replace(_location(), page_number=None))

    def test_raw_candidate_is_not_parsed_or_length_bounded_here(self):
        long_text = "x" * 1_000
        evidence = _evidence(
            evidence_kind=DrawingVlmEvidenceKind.NOTE,
            raw_candidate=long_text,
            source_location=_location(text=long_text),
        )
        assert evidence.raw_candidate == long_text
        assert evidence.normalized_candidate is None
        for bad in ("", "  ", "a\x00b"):
            with pytest.raises(ValueError):
                _evidence(raw_candidate=bad)

    def test_normalized_fields_match_evidence_kind(self):
        with pytest.raises(ValueError, match="field_key"):
            _evidence(field_key="drawing_number")
        with pytest.raises(ValueError, match="normalized_characteristic"):
            _evidence(normalized_characteristic=DrawingGdtCharacteristic.FLATNESS)
        with pytest.raises(ValueError, match="normalized_datum"):
            _evidence(normalized_datum=DrawingDatumReference("A"))
        with pytest.raises(ValueError, match="normalized_dimension"):
            _evidence(
                evidence_kind=DrawingVlmEvidenceKind.TEXT,
                normalized_dimension=DrawingDimension("d", Decimal("1"), "mm"),
            )
        title = _evidence(
            evidence_kind=DrawingVlmEvidenceKind.TITLE_FIELD, field_key="drawing_number"
        )
        assert title.field_key == "drawing_number"

    def test_datum_label_must_be_single_uppercase_letter(self):
        datum = _evidence(
            evidence_kind=DrawingVlmEvidenceKind.DATUM_LABEL,
            normalized_datum=DrawingDatumReference("B"),
        )
        assert datum.normalized_datum.datum_label == "B"
        with pytest.raises(ValueError, match="uppercase"):
            _evidence(
                evidence_kind=DrawingVlmEvidenceKind.DATUM_LABEL,
                normalized_datum=DrawingDatumReference("AB"),
            )

    def test_typed_fields(self):
        with pytest.raises(TypeError):
            _evidence(model="fake-vlm")
        with pytest.raises(TypeError):
            _evidence(parser_identity=("vlm", "1"))
        with pytest.raises(TypeError):
            _evidence(evidence_kind="DIMENSION")
        with pytest.raises(TypeError):
            _evidence(legibility="CLEAR")
        with pytest.raises(TypeError):
            _evidence(validation_status="VALID")

    @pytest.mark.parametrize(
        "name", ["evidence_id", "prompt_contract_version", "region_id", "request_id"]
    )
    def test_blank_identifiers_rejected(self, name):
        with pytest.raises(ValueError):
            _evidence(**{name: " "})

    def test_evidence_is_frozen(self):
        with pytest.raises(FrozenInstanceError):
            _evidence().raw_candidate = "26 mm"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------


class TestFinding:
    def test_valid_findings(self):
        assert _finding().status is DrawingVlmReconciliationStatus.CORROBORATED
        advisory = _finding(
            status=DrawingVlmReconciliationStatus.ADVISORY_ONLY,
            rationale=DrawingVlmRationale.NO_DETERMINISTIC_EVIDENCE,
            deterministic_support_ids=(),
            deterministic_origins=(),
        )
        assert advisory.deterministic_support_ids == ()
        conflict = _finding(
            status=DrawingVlmReconciliationStatus.CONFLICT,
            rationale=DrawingVlmRationale.DECIMAL_MISMATCH,
            deterministic_origins=(DrawingEvidenceOrigin.VECTOR, DrawingEvidenceOrigin.OCR),
            conflict_ids=("pdf-dim-p0001-000001",),
        )
        assert conflict.deterministic_origins == (
            DrawingEvidenceOrigin.VECTOR,
            DrawingEvidenceOrigin.OCR,
        )

    @pytest.mark.parametrize(
        "name", ["ai_evidence_ids", "deterministic_support_ids", "conflict_ids"]
    )
    def test_duplicate_ids_rejected(self, name):
        with pytest.raises(ValueError, match="duplicates"):
            _finding(**{name: ("x", "x")})

    def test_empty_ids_rejected(self):
        with pytest.raises(ValueError):
            _finding(finding_id="")
        with pytest.raises(ValueError):
            _finding(ai_evidence_ids=())
        with pytest.raises(ValueError):
            _finding(ai_evidence_ids=("",))

    def test_origins_are_typed_unique_and_deterministic_only(self):
        with pytest.raises(TypeError):
            _finding(deterministic_origins=("VECTOR",))
        with pytest.raises(ValueError, match="duplicates"):
            _finding(
                deterministic_origins=(DrawingEvidenceOrigin.OCR, DrawingEvidenceOrigin.OCR)
            )
        with pytest.raises(ValueError, match="AI_VLM"):
            _finding(deterministic_origins=(DrawingEvidenceOrigin.AI_VLM,))

    def test_support_ids_and_origins_travel_together(self):
        with pytest.raises(ValueError, match="both"):
            _finding(deterministic_origins=())
        with pytest.raises(ValueError, match="both"):
            _finding(
                status=DrawingVlmReconciliationStatus.ADVISORY_ONLY,
                deterministic_support_ids=(),
            )

    def test_ai_ids_cannot_pose_as_deterministic_support(self):
        with pytest.raises(ValueError, match="deterministic support"):
            _finding(deterministic_support_ids=("vlm-ev-1",))

    @pytest.mark.parametrize(
        "status",
        [
            DrawingVlmReconciliationStatus.CORROBORATED,
            DrawingVlmReconciliationStatus.RECOVERY_CANDIDATE,
            DrawingVlmReconciliationStatus.CONFLICT,
        ],
    )
    def test_statuses_defined_by_deterministic_support_require_it(self, status):
        with pytest.raises(ValueError, match="requires deterministic support"):
            _finding(status=status, deterministic_support_ids=(), deterministic_origins=())

    def test_conflict_requires_conflict_ids(self):
        with pytest.raises(ValueError, match="conflict_ids"):
            _finding(status=DrawingVlmReconciliationStatus.CONFLICT)

    def test_finding_is_frozen(self):
        with pytest.raises(FrozenInstanceError):
            _finding().status = DrawingVlmReconciliationStatus.REJECTED  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Advisory report
# ---------------------------------------------------------------------------


class TestAdvisoryReport:
    def test_valid_report(self):
        report = _report()
        assert report.status is DrawingIngestionStatus.VALID
        assert report.request_count == 1

    def test_valid_partial_report(self):
        report = _report(
            status=DrawingIngestionStatus.PARTIAL,
            diagnostics=("VLM_TIMEOUT",),
            request_count=2,
        )
        assert report.diagnostics == ("VLM_TIMEOUT",)

    def test_insufficient_report_without_model(self):
        report = _report(
            status=DrawingIngestionStatus.INSUFFICIENT_DATA,
            model=None,
            regions=(),
            evidence=(),
            findings=(),
            diagnostics=("VLM_NO_ELIGIBLE_REGIONS",),
            request_count=0,
        )
        assert report.model is None

    @pytest.mark.parametrize(
        "status", [DrawingIngestionStatus.FAILED, DrawingIngestionStatus.UNSUPPORTED]
    )
    def test_failed_or_unsupported_reject_evidence_and_findings(self, status):
        with pytest.raises(ValueError, match="must not carry"):
            _report(status=status, findings=())
        with pytest.raises(ValueError, match="must not carry"):
            _report(status=status, evidence=(), findings=(_finding(),))
        empty = _report(status=status, evidence=(), findings=(), request_count=0)
        assert empty.evidence == () and empty.findings == ()

    def test_duplicate_ids_rejected(self):
        with pytest.raises(ValueError, match="region IDs"):
            _report(regions=(_region(), _region()))
        with pytest.raises(ValueError, match="evidence IDs"):
            _report(evidence=(_evidence(), _evidence()))
        with pytest.raises(ValueError, match="finding IDs"):
            _report(findings=(_finding(), _finding()))

    def test_references_must_resolve_within_the_report(self):
        with pytest.raises(ValueError, match="report region"):
            _report(regions=(_region("vlm-region-2"),))
        with pytest.raises(ValueError, match="report evidence"):
            _report(findings=(_finding(ai_evidence_ids=("vlm-ev-missing",)),))

    def test_evidence_must_match_report_model_and_contract(self):
        with pytest.raises(ValueError, match="model"):
            _report(model=make_identity(model_version="2026-10-01"))
        with pytest.raises(ValueError, match="model"):
            _report(model=None)
        with pytest.raises(ValueError, match="prompt contract"):
            _report(prompt_contract_version="machiningpro.drawing-vlm.v2")

    @pytest.mark.parametrize("value", [-1, True, 1.0])
    def test_request_count_validation(self, value):
        with pytest.raises((TypeError, ValueError)):
            _report(request_count=value)

    def test_diagnostic_count_and_length_limits(self):
        assert len(_report(diagnostics=("VLM_X",) * 50).diagnostics) == 50
        with pytest.raises(ValueError):
            _report(diagnostics=("VLM_X",) * 51)
        assert _report(diagnostics=("X" * 240,))
        with pytest.raises(ValueError):
            _report(diagnostics=("X" * 241,))
        with pytest.raises(TypeError):
            _report(diagnostics=["VLM_X"])

    @pytest.mark.parametrize("value", ["A" * 64, "a" * 63, "g" * 64, "", "sha256:" + "a" * 57])
    def test_fingerprints_are_structurally_validated(self, value):
        with pytest.raises(ValueError):
            _report(config_fingerprint=value)
        with pytest.raises(ValueError):
            _report(base_result_fingerprint=value)

    def test_collections_are_typed_tuples(self):
        with pytest.raises(TypeError):
            _report(regions=[_region()])
        with pytest.raises(TypeError):
            _report(evidence=("vlm-ev-1",))

    def test_repr_contains_no_sensitive_payloads(self):
        rendered = repr(_report())
        for forbidden in ("PNG", "IHDR", "payload", "image_png", "api_key", "password"):
            assert forbidden not in rendered

    def test_report_is_frozen(self):
        with pytest.raises(FrozenInstanceError):
            _report().request_count = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Assisted result
# ---------------------------------------------------------------------------


class TestAssistedResult:
    def test_with_and_without_advisory(self):
        base = _base_result()
        report = _report()
        with_report = DrawingAssistedIngestionResult(result=base, advisory=report)
        without = DrawingAssistedIngestionResult(result=base)
        assert with_report.advisory is report
        assert without.advisory is None

    def test_result_is_carried_unchanged(self):
        base = _base_result()
        snapshot = repr(base)
        wrapper = DrawingAssistedIngestionResult(result=base, advisory=_report())
        assert wrapper.result is base
        assert wrapper.result == base
        assert repr(base) == snapshot

    def test_typed_fields(self):
        with pytest.raises(TypeError):
            DrawingAssistedIngestionResult(result=None)  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            DrawingAssistedIngestionResult(result=_base_result(), advisory="report")  # type: ignore[arg-type]

    def test_assisted_result_is_frozen(self):
        wrapper = DrawingAssistedIngestionResult(result=_base_result())
        with pytest.raises(FrozenInstanceError):
            wrapper.advisory = _report()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Security / structure
# ---------------------------------------------------------------------------

_CONTRACTS = (
    VlmLimits,
    DrawingVlmAssistConfig,
    DrawingVlmRegion,
    DrawingVlmEvidence,
    DrawingVlmFinding,
    DrawingAdvisoryReport,
    DrawingAssistedIngestionResult,
)
_FORBIDDEN_FIELD_WORDS = {
    "timestamp", "time", "date", "datetime", "path", "filename", "file", "url",
    "endpoint", "key", "apikey", "secret", "password", "credential", "credentials",
    "token", "payload", "bytes", "png", "image",
}


@pytest.mark.parametrize("contract", _CONTRACTS)
def test_no_timestamp_path_credential_payload_or_image_fields(contract):
    for item in fields(contract):
        words = set(item.name.lower().split("_"))
        # VlmLimits byte-count limits; field_key is a title-block field name slot.
        allowed = {"crop_png_bytes", "response_bytes", "field_key"}
        if item.name in allowed:
            continue
        assert not words & _FORBIDDEN_FIELD_WORDS, f"{contract.__name__}.{item.name}"


def test_all_public_contracts_are_frozen():
    for contract in _CONTRACTS:
        assert contract.__dataclass_params__.frozen, contract.__name__


def test_module_has_no_network_vendor_or_clock_imports():
    tree = ast.parse(Path(vlm_drawing.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = re.compile(
        r"^(socket|ssl|http|urllib|requests|httpx|aiohttp|openai|anthropic|datetime|time|"
        r"uuid|random|os|subprocess)(\.|$)"
    )
    assert not [name for name in imported if forbidden.match(name)]


def test_module_does_not_import_the_parser():
    source = Path(vlm_drawing.__file__).read_text(encoding="utf-8")
    assert "pdf_drawing" not in source
    assert "Ã" not in source and "â€" not in source
