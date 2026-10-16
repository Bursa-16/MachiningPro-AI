"""Tests for CuttingParameterRegistry (Stage 3G)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.cutting_parameters.models import (
    ApplicabilityScope,
    CuttingParameterRecord,
    EvidenceStatus,
    ParameterType,
    QuantityRange,
)
from backend.cutting_parameters.registry import CuttingParameterRegistry
from backend.domain.base import Provenance
from backend.domain.enums import (
    IsoMaterialGroup,
    OperationType,
    ProvenanceType,
)
from backend.domain.units import Quantity, Unit
from backend.empirical.exceptions import EmpiricalDataError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prov(ref: str = "src") -> Provenance:
    return Provenance(
        source_type=ProvenanceType.LITERATURE,
        source_reference=ref,
    )


def _vc_record(
    record_id: str,
    iso_group: IsoMaterialGroup = IsoMaterialGroup.P,
    operation: OperationType = OperationType.TURNING,
    lo: float = 100.0,
    hi: float = 200.0,
    evidence: EvidenceStatus = EvidenceStatus.REFERENCE_ONLY,
) -> CuttingParameterRecord:
    return CuttingParameterRecord(
        record_id=record_id,
        parameter_type=ParameterType.CUTTING_SPEED,
        value_range=QuantityRange(
            min_value=Quantity(Decimal(str(lo)), Unit.M_MIN),
            max_value=Quantity(Decimal(str(hi)), Unit.M_MIN),
        ),
        applicability=ApplicabilityScope(
            operation_type=operation,
            iso_material_group=iso_group,
        ),
        provenance=_prov(),
        evidence_status=evidence,
    )


def _fz_record(
    record_id: str, iso_group: IsoMaterialGroup = IsoMaterialGroup.P
) -> CuttingParameterRecord:
    return CuttingParameterRecord(
        record_id=record_id,
        parameter_type=ParameterType.FEED_PER_TOOTH,
        value_range=QuantityRange(
            min_value=Quantity(Decimal("0.03"), Unit.MM_TOOTH),
            max_value=Quantity(Decimal("0.18"), Unit.MM_TOOTH),
        ),
        applicability=ApplicabilityScope(
            operation_type=OperationType.MILLING,
            iso_material_group=iso_group,
        ),
        provenance=_prov(),
        evidence_status=EvidenceStatus.REFERENCE_ONLY,
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_and_get(self):
        reg = CuttingParameterRegistry()
        r = _vc_record("R1")
        reg.register(r)
        assert reg.get("R1") is r

    def test_duplicate_id_raises(self):
        reg = CuttingParameterRegistry()
        reg.register(_vc_record("R1"))
        with pytest.raises(EmpiricalDataError, match="already registered"):
            reg.register(_vc_record("R1"))

    def test_get_missing_raises(self):
        reg = CuttingParameterRegistry()
        with pytest.raises(EmpiricalDataError, match="no cutting parameter record"):
            reg.get("NONEXISTENT")

    def test_has_returns_true_after_register(self):
        reg = CuttingParameterRegistry()
        reg.register(_vc_record("R1"))
        assert reg.has("R1") is True

    def test_has_returns_false_before_register(self):
        reg = CuttingParameterRegistry()
        assert reg.has("R1") is False

    def test_contains_operator(self):
        reg = CuttingParameterRegistry()
        reg.register(_vc_record("R1"))
        assert "R1" in reg
        assert "R2" not in reg

    def test_len(self):
        reg = CuttingParameterRegistry()
        assert len(reg) == 0
        reg.register(_vc_record("R1"))
        assert len(reg) == 1
        reg.register(_vc_record("R2"))
        assert len(reg) == 2

    def test_register_non_record_raises(self):
        reg = CuttingParameterRegistry()
        with pytest.raises(TypeError):
            reg.register("not a record")  # type: ignore


# ---------------------------------------------------------------------------
# find() — scope + parameter_type + evidence_status filters
# ---------------------------------------------------------------------------

class TestFind:
    def setup_method(self):
        self.reg = CuttingParameterRegistry()
        self.reg.register(_vc_record("TURN_P_VC", IsoMaterialGroup.P, OperationType.TURNING))
        self.reg.register(_vc_record("TURN_M_VC", IsoMaterialGroup.M, OperationType.TURNING))
        self.reg.register(_vc_record("MILL_P_VC", IsoMaterialGroup.P, OperationType.MILLING))
        self.reg.register(_fz_record("MILL_P_FZ", IsoMaterialGroup.P))

    def test_find_all_no_filter(self):
        results = self.reg.find()
        assert len(results) == 4

    def test_find_by_operation_type(self):
        scope = ApplicabilityScope(operation_type=OperationType.TURNING)
        results = self.reg.find(scope=scope)
        assert len(results) == 2
        assert all(r.applicability.operation_type is OperationType.TURNING for r in results)

    def test_find_by_iso_material_group(self):
        scope = ApplicabilityScope(iso_material_group=IsoMaterialGroup.P)
        results = self.reg.find(scope=scope)
        ids = {r.record_id for r in results}
        assert "TURN_P_VC" in ids
        assert "MILL_P_VC" in ids
        assert "MILL_P_FZ" in ids
        assert "TURN_M_VC" not in ids

    def test_find_by_parameter_type(self):
        results = self.reg.find(parameter_type=ParameterType.FEED_PER_TOOTH)
        assert len(results) == 1
        assert results[0].record_id == "MILL_P_FZ"

    def test_find_combined_scope_and_parameter_type(self):
        scope = ApplicabilityScope(
            operation_type=OperationType.MILLING,
            iso_material_group=IsoMaterialGroup.P,
        )
        results = self.reg.find(scope=scope, parameter_type=ParameterType.CUTTING_SPEED)
        assert len(results) == 1
        assert results[0].record_id == "MILL_P_VC"

    def test_find_empty_result_is_empty_tuple(self):
        scope = ApplicabilityScope(operation_type=OperationType.DRILLING)
        results = self.reg.find(scope=scope)
        assert results == ()

    def test_find_results_sorted_by_record_id(self):
        results = self.reg.find()
        ids = [r.record_id for r in results]
        assert ids == sorted(ids)

    def test_find_by_evidence_status(self):
        results = self.reg.find(evidence_status=EvidenceStatus.REFERENCE_ONLY)
        assert len(results) == 4

    def test_find_authoritative_returns_empty_when_all_reference_only(self):
        results = self.reg.find_authoritative()
        assert results == ()


# ---------------------------------------------------------------------------
# Conflicting records: both preserved (Hard Rule 18)
# ---------------------------------------------------------------------------

class TestConflictingRecords:
    def test_conflicting_records_both_preserved(self):
        reg = CuttingParameterRegistry()
        r1 = _vc_record("SRC_A_VC", IsoMaterialGroup.P, OperationType.TURNING, 100, 200)
        r2 = CuttingParameterRecord(
            record_id="SRC_B_VC",  # different ID, same scope, different range
            parameter_type=ParameterType.CUTTING_SPEED,
            value_range=QuantityRange(
                min_value=Quantity(Decimal("120"), Unit.M_MIN),
                max_value=Quantity(Decimal("280"), Unit.M_MIN),
            ),
            applicability=ApplicabilityScope(
                operation_type=OperationType.TURNING,
                iso_material_group=IsoMaterialGroup.P,
            ),
            provenance=Provenance(
                source_type=ProvenanceType.MANUFACTURER_DATA,
                source_reference="Sandvik catalogue",
            ),
            evidence_status=EvidenceStatus.REFERENCE_ONLY,
        )
        reg.register(r1)
        reg.register(r2)

        scope = ApplicabilityScope(
            operation_type=OperationType.TURNING,
            iso_material_group=IsoMaterialGroup.P,
        )
        results = reg.find(scope=scope, parameter_type=ParameterType.CUTTING_SPEED)
        assert len(results) == 2
        # Values are NOT averaged — both raw records preserved
        min_vals = {r.value_range.min_value.value for r in results}
        assert Decimal("100") in min_vals
        assert Decimal("120") in min_vals


# ---------------------------------------------------------------------------
# ids() and all()
# ---------------------------------------------------------------------------

class TestIntrospection:
    def test_ids_deterministic(self):
        reg = CuttingParameterRegistry()
        reg.register(_vc_record("B"))
        reg.register(_vc_record("A"))
        # ids() returns in insertion order
        assert reg.ids() == ("B", "A")

    def test_all_sorted(self):
        reg = CuttingParameterRegistry()
        reg.register(_vc_record("B"))
        reg.register(_vc_record("A"))
        records = reg.all()
        assert records[0].record_id == "A"
        assert records[1].record_id == "B"
