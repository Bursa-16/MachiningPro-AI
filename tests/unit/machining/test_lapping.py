"""
Unit tests — MachiningPro AI Stage 3L: Lapping Engineering Core

Tests cover:
  R-3001  lapping_contact_pressure
  R-3002  lapping_removed_volume
  R-3003  lapping_volumetric_mrr
  R-3004  lapping_removed_thickness
  R-3005  lapping_cycle_time

  estimate_lapping_removal_rate_preston (EMPIRICAL evaluator)
    - provenance guard (fail closed)
    - linearity (Preston is linear in P and v_r)

  Validation rules R-3051–R-3053

  Rule-ID uniqueness across Stage 3L
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.domain.base import Provenance
from backend.domain.enums import ProvenanceType
from backend.domain.result import ResultStatus
from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError
from backend.machining.lapping import (
    estimate_lapping_removal_rate_preston,
    lapping_contact_pressure,
    lapping_cycle_time,
    lapping_removed_thickness,
    lapping_removed_volume,
    lapping_volumetric_mrr,
)
from backend.machining.lapping_rules import (
    LAPPING_RULE_IDS,
    LAPPING_RULES,
    LappingContactPressureRule,
    LappingCycleTimeRule,
    LappingPressureRangeRule,
    LappingPrestonKProvenanceRule,
    LappingRemovedThicknessRule,
    LappingRemovedVolumeRule,
    LappingStockRemovalToleranceRule,
    LappingVolumetricMRRRule,
)

# ── helpers ──────────────────────────────────────────────────────────────────

def q(value, unit: Unit) -> Quantity:
    return Quantity.of(str(value), unit)


def verified_provenance() -> Provenance:
    return Provenance(
        source_type=ProvenanceType.MANUFACTURER_DATA,
        source_reference="Lapmaster-Wolters K_p test report LW-2024-007, Table 3",
        source_document="Lapmaster-Wolters K_p calibration data",
    )


# ── R-3001  lapping_contact_pressure ─────────────────────────────────────────

class TestLappingContactPressure:

    def test_known_value(self):
        # F=140 N, A=2800 mm² → P = 140/2800 = 0.05 MPa
        p = lapping_contact_pressure(q(140, Unit.N), Decimal("2800"))
        assert p.unit is Unit.MPA
        assert abs(p.value - Decimal("0.05")) < Decimal("0.0001")

    def test_unit_identity_1N_per_mm2_equals_1MPa(self):
        p = lapping_contact_pressure(q(1, Unit.N), Decimal("1"))
        assert abs(p.value - Decimal("1")) < Decimal("0.000001")

    def test_zero_force_raises(self):
        with pytest.raises(MachiningMathError, match="normal_force"):
            lapping_contact_pressure(q(0, Unit.N), Decimal("1000"))

    def test_negative_force_raises(self):
        with pytest.raises(MachiningMathError):
            lapping_contact_pressure(q(-10, Unit.N), Decimal("1000"))

    def test_zero_area_raises(self):
        with pytest.raises(MachiningMathError, match="contact_area"):
            lapping_contact_pressure(q(100, Unit.N), Decimal("0"))

    def test_negative_area_raises(self):
        with pytest.raises(MachiningMathError):
            lapping_contact_pressure(q(100, Unit.N), Decimal("-500"))

    def test_wrong_force_unit_raises(self):
        with pytest.raises(MachiningMathError, match="normal_force"):
            lapping_contact_pressure(q(100, Unit.MM), Decimal("1000"))

    def test_result_positive(self):
        p = lapping_contact_pressure(q(50, Unit.N), Decimal("500"))
        assert p.value > Decimal("0")


# ── R-3002  lapping_removed_volume ────────────────────────────────────────────

class TestLappingRemovedVolume:

    def test_known_value_in_mm(self):
        # A=2800 mm², Δh=0.003 mm (=3 µm) → V = 8.4 mm³
        v = lapping_removed_volume(Decimal("2800"), q("0.003", Unit.MM))
        assert v.unit is Unit.MM3
        assert abs(v.value - Decimal("8.4")) < Decimal("0.001")

    def test_zero_thickness_raises(self):
        with pytest.raises(MachiningMathError):
            lapping_removed_volume(Decimal("1000"), q(0, Unit.MM))

    def test_zero_area_raises(self):
        with pytest.raises(MachiningMathError):
            lapping_removed_volume(Decimal("0"), q("0.001", Unit.MM))

    def test_wrong_thickness_unit_raises(self):
        with pytest.raises(MachiningMathError):
            lapping_removed_volume(Decimal("1000"), q("0.003", Unit.M_MIN))

    def test_round_trip_with_r3004(self):
        area = Decimal("2000")
        dh_in = q("0.005", Unit.MM)
        v = lapping_removed_volume(area, dh_in)
        dh_back = lapping_removed_thickness(v, area)
        assert abs(dh_back.value - dh_in.value) < Decimal("0.000001")


# ── R-3003  lapping_volumetric_mrr ────────────────────────────────────────────

class TestLappingVolumetricMRR:

    def test_known_value(self):
        # V=8.4 mm³, t=0.625 min → MRR = 13.44 mm³/min
        mrr = lapping_volumetric_mrr(q("8.4", Unit.MM3), q("0.625", Unit.MIN))
        assert mrr.unit is Unit.MM3_MIN
        assert abs(mrr.value - Decimal("13.44")) < Decimal("0.001")

    def test_zero_volume_raises(self):
        with pytest.raises(MachiningMathError):
            lapping_volumetric_mrr(q(0, Unit.MM3), q(1, Unit.MIN))

    def test_zero_time_raises(self):
        with pytest.raises(MachiningMathError):
            lapping_volumetric_mrr(q("8.4", Unit.MM3), q(0, Unit.MIN))

    def test_wrong_unit_raises(self):
        with pytest.raises(MachiningMathError):
            lapping_volumetric_mrr(q("8.4", Unit.MM), q(1, Unit.MIN))

    def test_round_trip_with_r3005(self):
        v_target = q("10.0", Unit.MM3)
        mrr = q("5.0", Unit.MM3_MIN)
        t = lapping_cycle_time(v_target, mrr)
        # Just confirm cycle time is 2 min
        assert abs(t.value - Decimal("2")) < Decimal("0.001")


# ── R-3004  lapping_removed_thickness ────────────────────────────────────────

class TestLappingRemovedThickness:

    def test_known_value(self):
        # V=8.4 mm³, A=2800 mm² → Δh = 0.003 mm
        dh = lapping_removed_thickness(q("8.4", Unit.MM3), Decimal("2800"))
        assert dh.unit is Unit.MM
        assert abs(dh.value - Decimal("0.003")) < Decimal("0.000001")

    def test_zero_volume_raises(self):
        with pytest.raises(MachiningMathError):
            lapping_removed_thickness(q(0, Unit.MM3), Decimal("1000"))

    def test_zero_area_raises(self):
        with pytest.raises(MachiningMathError):
            lapping_removed_thickness(q("5.0", Unit.MM3), Decimal("0"))


# ── R-3005  lapping_cycle_time ────────────────────────────────────────────────

class TestLappingCycleTime:

    def test_known_value(self):
        # V_target=10 mm³, MRR=5 mm³/min → t=2 min
        t = lapping_cycle_time(q("10", Unit.MM3), q("5", Unit.MM3_MIN))
        assert t.unit is Unit.MIN
        assert abs(t.value - Decimal("2")) < Decimal("0.001")

    def test_zero_volume_raises(self):
        with pytest.raises(MachiningMathError):
            lapping_cycle_time(q(0, Unit.MM3), q("5", Unit.MM3_MIN))

    def test_zero_mrr_raises(self):
        with pytest.raises(MachiningMathError):
            lapping_cycle_time(q("10", Unit.MM3), q(0, Unit.MM3_MIN))

    def test_wrong_volume_unit_raises(self):
        with pytest.raises(MachiningMathError):
            lapping_cycle_time(q("10", Unit.MM), q("5", Unit.MM3_MIN))

    def test_wrong_mrr_unit_raises(self):
        with pytest.raises(MachiningMathError):
            lapping_cycle_time(q("10", Unit.MM3), q("5", Unit.MM3))


# ── Preston empirical evaluator ───────────────────────────────────────────────

class TestPrestonEmpirical:

    def test_known_value_with_provenance(self):
        # K_p=0.012, P=0.05 MPa, v_r=8 m/min → MRR=0.012×0.05×8=0.0048 mm³/min
        prov = verified_provenance()
        mrr = estimate_lapping_removal_rate_preston(
            q("0.012", Unit.DIMENSIONLESS),
            q("0.05", Unit.MPA),
            q("8", Unit.M_MIN),
            prov,
        )
        assert mrr.unit is Unit.MM3_MIN
        assert abs(mrr.value - Decimal("0.0048")) < Decimal("0.0001")

    def test_missing_provenance_fails_closed(self):
        with pytest.raises(MachiningMathError, match="provenance"):
            estimate_lapping_removal_rate_preston(
                q("0.012", Unit.DIMENSIONLESS),
                q("0.05", Unit.MPA),
                q("8", Unit.M_MIN),
                None,  # type: ignore
            )

    def test_none_source_reference_fails_closed(self):
        prov = Provenance(
            source_type=ProvenanceType.MANUFACTURER_DATA,
            source_reference=None,  # unverified
            source_document=None,
        )
        with pytest.raises(MachiningMathError, match="provenance"):
            estimate_lapping_removal_rate_preston(
                q("0.012", Unit.DIMENSIONLESS),
                q("0.05", Unit.MPA),
                q("8", Unit.M_MIN),
                prov,
            )

    def test_zero_kp_raises(self):
        with pytest.raises(MachiningMathError):
            estimate_lapping_removal_rate_preston(
                q(0, Unit.DIMENSIONLESS),
                q("0.05", Unit.MPA),
                q("8", Unit.M_MIN),
                verified_provenance(),
            )

    def test_linearity_doubling_pressure_doubles_mrr(self):
        prov = verified_provenance()
        mrr1 = estimate_lapping_removal_rate_preston(
            q("0.01", Unit.DIMENSIONLESS), q("0.05", Unit.MPA),
            q("5", Unit.M_MIN), prov,
        )
        mrr2 = estimate_lapping_removal_rate_preston(
            q("0.01", Unit.DIMENSIONLESS), q("0.10", Unit.MPA),
            q("5", Unit.M_MIN), prov,
        )
        assert abs(mrr2.value - mrr1.value * 2) < Decimal("0.0001")

    def test_linearity_doubling_speed_doubles_mrr(self):
        prov = verified_provenance()
        mrr1 = estimate_lapping_removal_rate_preston(
            q("0.01", Unit.DIMENSIONLESS), q("0.05", Unit.MPA),
            q("5", Unit.M_MIN), prov,
        )
        mrr2 = estimate_lapping_removal_rate_preston(
            q("0.01", Unit.DIMENSIONLESS), q("0.05", Unit.MPA),
            q("10", Unit.M_MIN), prov,
        )
        assert abs(mrr2.value - mrr1.value * 2) < Decimal("0.0001")

    def test_wrong_pressure_unit_raises(self):
        with pytest.raises(MachiningMathError):
            estimate_lapping_removal_rate_preston(
                q("0.012", Unit.DIMENSIONLESS),
                q("50", Unit.N),  # wrong — should be MPA
                q("8", Unit.M_MIN),
                verified_provenance(),
            )


# ── Validation rule tests ─────────────────────────────────────────────────────

class TestLappingValidationRules:

    def test_r3051_passes_within_range(self):
        rule = LappingPressureRangeRule()
        result = rule.evaluate({"pressure": q("0.05", Unit.MPA)})
        assert result.status is ResultStatus.PASS
        assert not result.warnings

    def test_r3051_warns_below_minimum(self):
        rule = LappingPressureRangeRule()
        result = rule.evaluate({"pressure": q("0.001", Unit.MPA)})
        assert result.status is ResultStatus.WARNING
        assert result.warnings

    def test_r3051_warns_above_maximum(self):
        rule = LappingPressureRangeRule()
        result = rule.evaluate({"pressure": q("0.5", Unit.MPA)})
        assert result.status is ResultStatus.WARNING
        assert result.warnings

    def test_r3052_passes_when_within_allowance(self):
        rule = LappingStockRemovalToleranceRule()
        result = rule.evaluate({
            "removed_thickness": q("0.002", Unit.MM),
            "max_allowance": q("0.005", Unit.MM),
        })
        assert result.status is ResultStatus.PASS

    def test_r3052_fails_when_exceeds_allowance(self):
        rule = LappingStockRemovalToleranceRule()
        result = rule.evaluate({
            "removed_thickness": q("0.010", Unit.MM),
            "max_allowance": q("0.005", Unit.MM),
        })
        assert result.status is ResultStatus.FAIL

    def test_r3053_passes_when_verified(self):
        rule = LappingPrestonKProvenanceRule()
        result = rule.evaluate({"kp_provenance_verified": True})
        assert result.status is ResultStatus.PASS

    def test_r3053_fails_when_unverified(self):
        rule = LappingPrestonKProvenanceRule()
        result = rule.evaluate({"kp_provenance_verified": False})
        assert result.status is ResultStatus.FAIL

    def test_r3053_fails_when_missing(self):
        rule = LappingPrestonKProvenanceRule()
        result = rule.evaluate({})
        # Missing required input is caught fail-closed by the base rule
        # wrapper before _evaluate runs.
        assert result.status is ResultStatus.INSUFFICIENT_DATA


# ── Rule wrapper smoke tests ──────────────────────────────────────────────────

class TestLappingRuleWrappers:

    def test_r3001_success(self):
        rule = LappingContactPressureRule()
        result = rule.evaluate({"normal_force": q(140, Unit.N),
                                "contact_area_mm2": Decimal("2800")})
        assert result.status is ResultStatus.PASS
        assert "pressure" in result.outputs

    def test_r3002_success(self):
        rule = LappingRemovedVolumeRule()
        result = rule.evaluate({"contact_area_mm2": Decimal("2800"),
                                "removed_thickness": q("0.003", Unit.MM)})
        assert result.status is ResultStatus.PASS

    def test_r3003_success(self):
        rule = LappingVolumetricMRRRule()
        result = rule.evaluate({"removed_volume": q("8.4", Unit.MM3),
                                "process_time": q("0.625", Unit.MIN)})
        assert result.status is ResultStatus.PASS

    def test_r3004_success(self):
        rule = LappingRemovedThicknessRule()
        result = rule.evaluate({"removed_volume": q("8.4", Unit.MM3),
                                "contact_area_mm2": Decimal("2800")})
        assert result.status is ResultStatus.PASS

    def test_r3005_success(self):
        rule = LappingCycleTimeRule()
        result = rule.evaluate({"target_removed_volume": q("10", Unit.MM3),
                                "volumetric_mrr": q("5", Unit.MM3_MIN)})
        assert result.status is ResultStatus.PASS


# ── Rule ID uniqueness ────────────────────────────────────────────────────────

class TestLappingRuleIDUniqueness:

    def test_no_duplicate_rule_ids(self):
        assert len(LAPPING_RULE_IDS) == len(set(LAPPING_RULE_IDS))

    def test_all_ids_in_r30xx_range(self):
        for rid in LAPPING_RULE_IDS:
            assert rid.startswith("R-30"), f"{rid} not in R-30xx range"

    def test_rule_count(self):
        # 5 calculation + 3 validation = 8
        assert len(LAPPING_RULES) == 8

    def test_no_overlap_with_honing_ids(self):
        from backend.machining.honing_rules import HONING_RULE_IDS
        overlap = set(HONING_RULE_IDS) & set(LAPPING_RULE_IDS)
        assert not overlap, f"Rule ID collision: {overlap}"


# ── OperationType enum test ───────────────────────────────────────────────────

class TestOperationTypeExtension:

    def test_honing_in_operation_type(self):
        from backend.domain.enums import OperationType
        assert hasattr(OperationType, "HONING")
        assert OperationType.HONING.value == "honing"

    def test_lapping_in_operation_type(self):
        from backend.domain.enums import OperationType
        assert hasattr(OperationType, "LAPPING")
        assert OperationType.LAPPING.value == "lapping"
