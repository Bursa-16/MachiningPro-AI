"""Tests for CuttingParameterRecord, QuantityRange, ApplicabilityScope (Stage 3G)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.cutting_parameters.models import (
    AUTHORITATIVE_STATUSES,
    PARAMETER_CANONICAL_UNIT,
    ApplicabilityScope,
    CuttingParameterRecord,
    EvidenceStatus,
    ParameterType,
    QuantityRange,
)
from backend.domain.base import Provenance
from backend.domain.enums import (
    IsoMaterialGroup,
    OperationType,
    ProvenanceType,
    ToolMaterial,
)
from backend.domain.exceptions import ValidationError
from backend.domain.units import Quantity, Unit

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _prov(source_ref: str | None = "test-source") -> Provenance:
    return Provenance(
        source_type=ProvenanceType.LITERATURE,
        source_reference=source_ref,
    )


def _range(lo: float, hi: float, unit: Unit) -> QuantityRange:
    return QuantityRange(
        min_value=Quantity(Decimal(str(lo)), unit),
        max_value=Quantity(Decimal(str(hi)), unit),
    )


def _vc_range(lo: float, hi: float) -> QuantityRange:
    return _range(lo, hi, Unit.M_MIN)


def _record(
    record_id: str = "TEST_VC",
    parameter_type: ParameterType = ParameterType.CUTTING_SPEED,
    value_range: QuantityRange | None = None,
    evidence_status: EvidenceStatus = EvidenceStatus.REFERENCE_ONLY,
    source_ref: str | None = "src",
) -> CuttingParameterRecord:
    return CuttingParameterRecord(
        record_id=record_id,
        parameter_type=parameter_type,
        value_range=value_range or _vc_range(100, 200),
        applicability=ApplicabilityScope(
            operation_type=OperationType.TURNING,
            iso_material_group=IsoMaterialGroup.P,
        ),
        provenance=_prov(source_ref),
        evidence_status=evidence_status,
    )


# ---------------------------------------------------------------------------
# QuantityRange
# ---------------------------------------------------------------------------

class TestQuantityRange:
    def test_valid_range(self):
        r = _range(100, 200, Unit.M_MIN)
        assert r.min_value.value == Decimal("100")
        assert r.max_value.value == Decimal("200")
        assert r.unit is Unit.M_MIN

    def test_point_value(self):
        r = _range(150, 150, Unit.M_MIN)
        assert r.is_point is True

    def test_non_point(self):
        r = _range(100, 200, Unit.M_MIN)
        assert r.is_point is False

    def test_reversed_range_raises(self):
        with pytest.raises(ValidationError, match="min_value"):
            _range(200, 100, Unit.M_MIN)

    def test_mismatched_units_raises(self):
        with pytest.raises(ValidationError, match="same unit"):
            QuantityRange(
                min_value=Quantity(Decimal("100"), Unit.M_MIN),
                max_value=Quantity(Decimal("200"), Unit.MM_REV),
            )

    def test_contains_inside(self):
        r = _range(100, 200, Unit.M_MIN)
        assert r.contains(Quantity(Decimal("150"), Unit.M_MIN)) is True

    def test_contains_boundary_min(self):
        r = _range(100, 200, Unit.M_MIN)
        assert r.contains(Quantity(Decimal("100"), Unit.M_MIN)) is True

    def test_contains_boundary_max(self):
        r = _range(100, 200, Unit.M_MIN)
        assert r.contains(Quantity(Decimal("200"), Unit.M_MIN)) is True

    def test_contains_outside(self):
        r = _range(100, 200, Unit.M_MIN)
        assert r.contains(Quantity(Decimal("250"), Unit.M_MIN)) is False

    def test_non_quantity_raises(self):
        with pytest.raises(ValidationError):
            _range(100, 200, Unit.M_MIN).contains(150)  # type: ignore


# ---------------------------------------------------------------------------
# ApplicabilityScope
# ---------------------------------------------------------------------------

class TestApplicabilityScope:
    def test_all_none_scope(self):
        s = ApplicabilityScope()
        assert s.operation_type is None
        assert s.iso_material_group is None

    def test_matches_subset(self):
        record_scope = ApplicabilityScope(
            operation_type=OperationType.TURNING,
            iso_material_group=IsoMaterialGroup.P,
        )
        query = ApplicabilityScope(
            operation_type=OperationType.TURNING,
            iso_material_group=IsoMaterialGroup.P,
        )
        assert record_scope.matches(query) is True

    def test_matches_none_field_in_record_always_matches(self):
        record_scope = ApplicabilityScope(
            operation_type=OperationType.TURNING,
            iso_material_group=None,  # unspecified
        )
        query = ApplicabilityScope(
            operation_type=OperationType.TURNING,
            iso_material_group=IsoMaterialGroup.M,
        )
        assert record_scope.matches(query) is True

    def test_matches_none_field_in_query_always_matches(self):
        record_scope = ApplicabilityScope(
            operation_type=OperationType.TURNING,
            iso_material_group=IsoMaterialGroup.P,
        )
        query = ApplicabilityScope(
            operation_type=OperationType.TURNING,
            iso_material_group=None,  # no filter on material
        )
        assert record_scope.matches(query) is True

    def test_does_not_match_different_operation(self):
        record_scope = ApplicabilityScope(operation_type=OperationType.TURNING)
        query = ApplicabilityScope(operation_type=OperationType.MILLING)
        assert record_scope.matches(query) is False

    def test_does_not_match_different_material_group(self):
        record_scope = ApplicabilityScope(iso_material_group=IsoMaterialGroup.P)
        query = ApplicabilityScope(iso_material_group=IsoMaterialGroup.M)
        assert record_scope.matches(query) is False

    def test_does_not_match_different_tool_material(self):
        record_scope = ApplicabilityScope(tool_material=ToolMaterial.CARBIDE)
        query = ApplicabilityScope(tool_material=ToolMaterial.CBN)
        assert record_scope.matches(query) is False


# ---------------------------------------------------------------------------
# CuttingParameterRecord
# ---------------------------------------------------------------------------

class TestCuttingParameterRecord:
    def test_valid_reference_only(self):
        r = _record()
        assert r.record_id == "TEST_VC"
        assert r.evidence_status is EvidenceStatus.REFERENCE_ONLY

    def test_is_not_authoritative_when_reference_only(self):
        r = _record(evidence_status=EvidenceStatus.REFERENCE_ONLY)
        assert r.is_authoritative is False

    def test_is_authoritative_when_authoritative_with_source(self):
        r = _record(evidence_status=EvidenceStatus.AUTHORITATIVE, source_ref="ISO 513")
        assert r.is_authoritative is True

    def test_is_not_authoritative_when_authoritative_without_source(self):
        # CuttingParameterRecord raises ValidationError: AUTHORITATIVE needs source_ref
        with pytest.raises(ValidationError, match="source_reference"):
            _record(evidence_status=EvidenceStatus.AUTHORITATIVE, source_ref=None)

    def test_is_authoritative_when_experimental_with_source(self):
        r = _record(evidence_status=EvidenceStatus.EXPERIMENTAL, source_ref="exp-01")
        assert r.is_authoritative is True

    def test_empty_record_id_raises(self):
        with pytest.raises((ValidationError, ValueError)):
            CuttingParameterRecord(
                record_id="",
                parameter_type=ParameterType.CUTTING_SPEED,
                value_range=_vc_range(100, 200),
                applicability=ApplicabilityScope(),
                provenance=_prov(),
                evidence_status=EvidenceStatus.REFERENCE_ONLY,
            )

    def test_wrong_canonical_unit_raises(self):
        # FEED_PER_TOOTH must use Unit.MM_TOOTH, not Unit.M_MIN
        wrong_range = _range(0.05, 0.20, Unit.M_MIN)  # wrong unit for fz
        with pytest.raises(ValidationError, match="mm/tooth"):
            CuttingParameterRecord(
                record_id="BAD_UNIT",
                parameter_type=ParameterType.FEED_PER_TOOTH,
                value_range=wrong_range,
                applicability=ApplicabilityScope(),
                provenance=_prov(),
                evidence_status=EvidenceStatus.REFERENCE_ONLY,
            )

    def test_fz_and_fn_have_different_units(self):
        # Verifies Hard Rule 11: fz != fn semantics
        assert PARAMETER_CANONICAL_UNIT[ParameterType.FEED_PER_TOOTH] is Unit.MM_TOOTH
        assert PARAMETER_CANONICAL_UNIT[ParameterType.FEED_PER_REV] is Unit.MM_REV

    def test_ap_and_ae_both_use_mm(self):
        # Both are in MM but they are semantically different ParameterTypes
        assert PARAMETER_CANONICAL_UNIT[ParameterType.AXIAL_DEPTH_OF_CUT] is Unit.MM
        assert PARAMETER_CANONICAL_UNIT[ParameterType.RADIAL_ENGAGEMENT] is Unit.MM

    def test_matches_scope_delegates_to_applicability(self):
        r = _record()
        query = ApplicabilityScope(
            operation_type=OperationType.TURNING,
            iso_material_group=IsoMaterialGroup.P,
        )
        assert r.matches_scope(query) is True

    def test_authoritative_statuses_contains_authoritative_and_experimental(self):
        assert EvidenceStatus.AUTHORITATIVE in AUTHORITATIVE_STATUSES
        assert EvidenceStatus.EXPERIMENTAL in AUTHORITATIVE_STATUSES
        assert EvidenceStatus.REFERENCE_ONLY not in AUTHORITATIVE_STATUSES
        assert EvidenceStatus.UNVERIFIED not in AUTHORITATIVE_STATUSES
