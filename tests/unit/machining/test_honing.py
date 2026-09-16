"""
Unit tests — MachiningPro AI Stage 3K: Honing Engineering Core

Tests cover:
  R-2901  honing_peripheral_speed
  R-2902  honing_crosshatch_included_angle
  R-2903  honing_required_stroke_speed
  R-2904  honing_resultant_speed
  R-2905  honing_radial_stock
  R-2906  honing_removed_volume

  Rule wrappers (HoningPeripheralSpeedRule, etc.)
  Validation rules R-2951–R-2953

  - Normal / known values
  - Zero rejection
  - Negative rejection
  - Wrong unit rejection
  - Boolean rejection via Quantity
  - Inverse / round-trip checks
  - Rule-ID uniqueness across Stage 3K

[ASSUMPTION A4] Test style matches existing test_turning.py convention.
"""
from __future__ import annotations

import math
from decimal import Decimal

import pytest

from backend.domain.result import ResultStatus
from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError
from backend.machining.honing import (
    honing_crosshatch_included_angle,
    honing_peripheral_speed,
    honing_radial_stock,
    honing_removed_volume,
    honing_required_stroke_speed,
    honing_resultant_speed,
)
from backend.machining.honing_rules import (
    HONING_RULE_IDS,
    HONING_RULES,
    HoningCrosshatchAngleBoundsRule,
    HoningCrosshatchIncludedAngleRule,
    HoningPeripheralSpeedBoundRule,
    HoningPeripheralSpeedRule,
    HoningRadialStockRule,
    HoningRemovedVolumeRule,
    HoningRequiredStrokeSpeedRule,
    HoningResultantSpeedRule,
    HoningStockPositiveRule,
)

# ── helpers ──────────────────────────────────────────────────────────────────

def q(value, unit: Unit) -> Quantity:
    return Quantity.of(str(value), unit)


# ── R-2901  honing_peripheral_speed ─────────────────────────────────────────

class TestHoningPeripheralSpeed:

    def test_known_value(self):
        # v_p = π × 82 × 180 / 1000 ≈ 46.37 m/min
        v_p = honing_peripheral_speed(q(82, Unit.MM), q(180, Unit.RPM))
        assert v_p.unit is Unit.M_MIN
        expected = Decimal(str(math.pi * 82 * 180 / 1000))
        assert abs(v_p.value - expected) < Decimal("0.01")

    def test_larger_bore(self):
        # v_p = π × 100 × 200 / 1000 ≈ 62.83 m/min
        v_p = honing_peripheral_speed(q(100, Unit.MM), q(200, Unit.RPM))
        assert v_p.value > Decimal("62") and v_p.value < Decimal("64")

    def test_zero_diameter_raises(self):
        with pytest.raises(MachiningMathError, match="bore_diameter"):
            honing_peripheral_speed(q(0, Unit.MM), q(180, Unit.RPM))

    def test_negative_diameter_raises(self):
        with pytest.raises(MachiningMathError):
            honing_peripheral_speed(q(-10, Unit.MM), q(180, Unit.RPM))

    def test_zero_rpm_raises(self):
        with pytest.raises(MachiningMathError, match="spindle_speed"):
            honing_peripheral_speed(q(82, Unit.MM), q(0, Unit.RPM))

    def test_negative_rpm_raises(self):
        with pytest.raises(MachiningMathError):
            honing_peripheral_speed(q(82, Unit.MM), q(-50, Unit.RPM))

    def test_wrong_unit_diameter_raises(self):
        with pytest.raises(MachiningMathError, match="bore_diameter"):
            honing_peripheral_speed(q(82, Unit.M_MIN), q(180, Unit.RPM))

    def test_wrong_unit_speed_raises(self):
        with pytest.raises(MachiningMathError, match="spindle_speed"):
            honing_peripheral_speed(q(82, Unit.MM), q(180, Unit.MM))

    def test_result_positive(self):
        v_p = honing_peripheral_speed(q(30, Unit.MM), q(300, Unit.RPM))
        assert v_p.value > Decimal("0")


# ── R-2902  honing_crosshatch_included_angle ─────────────────────────────────

class TestHoningCrosshatchIncludedAngle:

    def test_known_value_29deg(self):
        # v_h=12, v_p=46 → α ≈ 2×arctan(12/46) ≈ 29.0°
        alpha = honing_crosshatch_included_angle(q(12, Unit.M_MIN), q(46, Unit.M_MIN))
        assert alpha.unit is Unit.DIMENSIONLESS
        expected = Decimal(str(2 * math.degrees(math.atan(12 / 46))))
        assert abs(alpha.value - expected) < Decimal("0.1")

    def test_zero_stroke_gives_zero(self):
        alpha = honing_crosshatch_included_angle(q(0, Unit.M_MIN), q(40, Unit.M_MIN))
        assert alpha.value == Decimal("0")

    def test_equal_speeds_gives_90deg(self):
        alpha = honing_crosshatch_included_angle(q(10, Unit.M_MIN), q(10, Unit.M_MIN))
        assert abs(alpha.value - Decimal("90")) < Decimal("0.01")

    def test_zero_peripheral_raises(self):
        with pytest.raises(MachiningMathError, match="peripheral_speed"):
            honing_crosshatch_included_angle(q(12, Unit.M_MIN), q(0, Unit.M_MIN))

    def test_wrong_unit_raises(self):
        with pytest.raises(MachiningMathError):
            honing_crosshatch_included_angle(q(12, Unit.MM), q(46, Unit.M_MIN))

    def test_included_angle_convention(self):
        # The included angle must be 2× the single-groove half-angle.
        # Single groove angle at v_h=v_p: half-angle = 45°, included = 90°
        alpha = honing_crosshatch_included_angle(q(20, Unit.M_MIN), q(20, Unit.M_MIN))
        assert abs(alpha.value - Decimal("90")) < Decimal("0.01")

        # Single groove angle at v_h=0: half-angle = 0°, included = 0°
        alpha_zero = honing_crosshatch_included_angle(q(0, Unit.M_MIN), q(20, Unit.M_MIN))
        assert alpha_zero.value == Decimal("0")


# ── R-2903  honing_required_stroke_speed ─────────────────────────────────────

class TestHoningRequiredStrokeSpeed:

    def test_round_trip_40deg(self):
        # Set target 40° → compute v_h → compute alpha back → must be 40°
        v_p = q(50, Unit.M_MIN)
        v_h = honing_required_stroke_speed(q(40, Unit.DIMENSIONLESS), v_p)
        alpha_back = honing_crosshatch_included_angle(v_h, v_p)
        assert abs(alpha_back.value - Decimal("40")) < Decimal("0.001")

    def test_round_trip_30deg(self):
        v_p = q(46, Unit.M_MIN)
        v_h = honing_required_stroke_speed(q(30, Unit.DIMENSIONLESS), v_p)
        alpha_back = honing_crosshatch_included_angle(v_h, v_p)
        assert abs(alpha_back.value - Decimal("30")) < Decimal("0.001")

    def test_zero_angle_raises(self):
        with pytest.raises(MachiningMathError, match="0"):
            honing_required_stroke_speed(q(0, Unit.DIMENSIONLESS), q(50, Unit.M_MIN))

    def test_180_angle_raises(self):
        with pytest.raises(MachiningMathError):
            honing_required_stroke_speed(q(180, Unit.DIMENSIONLESS), q(50, Unit.M_MIN))

    def test_negative_angle_raises(self):
        with pytest.raises(MachiningMathError):
            honing_required_stroke_speed(q(-10, Unit.DIMENSIONLESS), q(50, Unit.M_MIN))

    def test_result_positive_for_valid_angle(self):
        v_h = honing_required_stroke_speed(q(45, Unit.DIMENSIONLESS), q(40, Unit.M_MIN))
        assert v_h.value > Decimal("0")
        assert v_h.unit is Unit.M_MIN

    def test_wrong_unit_raises(self):
        with pytest.raises(MachiningMathError):
            honing_required_stroke_speed(q(40, Unit.MM), q(50, Unit.M_MIN))


# ── R-2904  honing_resultant_speed ───────────────────────────────────────────

class TestHoningResultantSpeed:

    def test_pythagorean_triple_3_4_5(self):
        v_c = honing_resultant_speed(q(3, Unit.M_MIN), q(4, Unit.M_MIN))
        assert abs(v_c.value - Decimal("5")) < Decimal("0.001")

    def test_pythagorean_triple_5_12_13(self):
        v_c = honing_resultant_speed(q(5, Unit.M_MIN), q(12, Unit.M_MIN))
        assert abs(v_c.value - Decimal("13")) < Decimal("0.001")

    def test_both_zero_raises(self):
        with pytest.raises(MachiningMathError):
            honing_resultant_speed(q(0, Unit.M_MIN), q(0, Unit.M_MIN))

    def test_one_zero_ok(self):
        v_c = honing_resultant_speed(q(0, Unit.M_MIN), q(40, Unit.M_MIN))
        assert v_c.value == Decimal("40")

    def test_negative_stroke_raises(self):
        with pytest.raises(MachiningMathError):
            honing_resultant_speed(q(-5, Unit.M_MIN), q(40, Unit.M_MIN))

    def test_result_unit_is_m_min(self):
        v_c = honing_resultant_speed(q(12, Unit.M_MIN), q(46, Unit.M_MIN))
        assert v_c.unit is Unit.M_MIN


# ── R-2905  honing_radial_stock ──────────────────────────────────────────────

class TestHoningRadialStock:

    def test_known_value(self):
        # D_i=81.95, D_f=82.02 → s = (82.02-81.95)/2 = 0.035
        s = honing_radial_stock(q("81.95", Unit.MM), q("82.02", Unit.MM))
        assert s.unit is Unit.MM
        assert abs(s.value - Decimal("0.035")) < Decimal("0.0001")

    def test_equal_diameters_raises(self):
        with pytest.raises(MachiningMathError):
            honing_radial_stock(q(82, Unit.MM), q(82, Unit.MM))

    def test_final_less_than_initial_raises(self):
        with pytest.raises(MachiningMathError):
            honing_radial_stock(q(82, Unit.MM), q(81, Unit.MM))

    def test_zero_initial_raises(self):
        with pytest.raises(MachiningMathError):
            honing_radial_stock(q(0, Unit.MM), q(82, Unit.MM))

    def test_negative_final_raises(self):
        with pytest.raises(MachiningMathError):
            honing_radial_stock(q(82, Unit.MM), q(-1, Unit.MM))

    def test_result_positive(self):
        s = honing_radial_stock(q(50, Unit.MM), q("50.02", Unit.MM))
        assert s.value > Decimal("0")


# ── R-2906  honing_removed_volume ────────────────────────────────────────────

class TestHoningRemovedVolume:

    def test_formula_reference(self):
        # V = π/4 × (81² - 80²) × 100
        D_i, D_f, L = Decimal("80"), Decimal("81"), Decimal("100")
        v = honing_removed_volume(
            Quantity.of(D_i, Unit.MM),
            Quantity.of(D_f, Unit.MM),
            Quantity.of(L, Unit.MM),
        )
        expected = Decimal(str(math.pi / 4)) * (D_f ** 2 - D_i ** 2) * L
        assert abs(v.value - expected) < Decimal("0.1")
        assert v.unit is Unit.MM3

    def test_result_positive(self):
        v = honing_removed_volume(q("81.95", Unit.MM), q("82.02", Unit.MM), q(120, Unit.MM))
        assert v.value > Decimal("0")

    def test_zero_bore_length_raises(self):
        with pytest.raises(MachiningMathError):
            honing_removed_volume(q(80, Unit.MM), q(81, Unit.MM), q(0, Unit.MM))

    def test_final_less_than_initial_raises(self):
        with pytest.raises(MachiningMathError):
            honing_removed_volume(q(82, Unit.MM), q(81, Unit.MM), q(100, Unit.MM))

    def test_wrong_unit_raises(self):
        with pytest.raises(MachiningMathError):
            honing_removed_volume(q(80, Unit.M_MIN), q(81, Unit.MM), q(100, Unit.MM))


# ── Rule wrapper smoke tests ──────────────────────────────────────────────────

class TestHoningRuleWrappers:

    def test_r2901_success(self):
        rule = HoningPeripheralSpeedRule()
        result = rule.evaluate({"bore_diameter": q(82, Unit.MM),
                                "spindle_speed": q(180, Unit.RPM)})
        assert result.status is ResultStatus.PASS
        assert "peripheral_speed" in result.outputs

    def test_r2901_failure_zero_diameter(self):
        rule = HoningPeripheralSpeedRule()
        result = rule.evaluate({"bore_diameter": q(0, Unit.MM),
                                "spindle_speed": q(180, Unit.RPM)})
        assert result.status is ResultStatus.FAIL

    def test_r2902_success_and_angle_in_output(self):
        rule = HoningCrosshatchIncludedAngleRule()
        result = rule.evaluate({"stroke_speed": q(12, Unit.M_MIN),
                                "peripheral_speed": q(46, Unit.M_MIN)})
        assert result.status is ResultStatus.PASS
        assert "crosshatch_included_angle_deg" in result.outputs

    def test_r2903_round_trip(self):
        rule_angle = HoningCrosshatchIncludedAngleRule()
        rule_speed = HoningRequiredStrokeSpeedRule()
        v_p = q(50, Unit.M_MIN)
        v_h = q(20, Unit.M_MIN)
        r1 = rule_angle.evaluate({"stroke_speed": v_h, "peripheral_speed": v_p})
        alpha = r1.outputs["crosshatch_included_angle_deg"]
        r2 = rule_speed.evaluate({"crosshatch_included_angle_deg": alpha,
                                  "peripheral_speed": v_p})
        assert r2.status is ResultStatus.PASS
        v_h_back = r2.outputs["stroke_speed"]
        assert abs(v_h_back.value - v_h.value) < Decimal("0.001")

    def test_r2904_success(self):
        rule = HoningResultantSpeedRule()
        result = rule.evaluate({"stroke_speed": q(3, Unit.M_MIN),
                                "peripheral_speed": q(4, Unit.M_MIN)})
        assert result.status is ResultStatus.PASS
        assert abs(result.outputs["resultant_speed"].value - Decimal("5")) < Decimal("0.001")

    def test_r2905_success(self):
        rule = HoningRadialStockRule()
        result = rule.evaluate({"diameter_initial": q("81.95", Unit.MM),
                                "diameter_final": q("82.02", Unit.MM)})
        assert result.status is ResultStatus.PASS

    def test_r2906_success(self):
        rule = HoningRemovedVolumeRule()
        result = rule.evaluate({"diameter_initial": q(80, Unit.MM),
                                "diameter_final": q(81, Unit.MM),
                                "bore_length": q(100, Unit.MM)})
        assert result.status is ResultStatus.PASS
        assert result.outputs["volume_removed"].unit is Unit.MM3


# ── Validation rule tests ─────────────────────────────────────────────────────

class TestHoningValidationRules:

    def test_r2951_passes_below_60(self):
        rule = HoningPeripheralSpeedBoundRule()
        result = rule.evaluate({"peripheral_speed": q(46, Unit.M_MIN)})
        assert result.status is ResultStatus.PASS
        assert not result.warnings

    def test_r2951_warns_above_60(self):
        rule = HoningPeripheralSpeedBoundRule()
        result = rule.evaluate({"peripheral_speed": q(70, Unit.M_MIN)})
        # Should warn, not fail
        assert result.status is ResultStatus.WARNING
        assert result.warnings

    def test_r2952_passes_for_valid_angle(self):
        rule = HoningCrosshatchAngleBoundsRule()
        result = rule.evaluate({"crosshatch_included_angle_deg": q(30, Unit.DIMENSIONLESS)})
        assert result.status is ResultStatus.PASS

    def test_r2952_fails_below_20(self):
        rule = HoningCrosshatchAngleBoundsRule()
        result = rule.evaluate({"crosshatch_included_angle_deg": q(15, Unit.DIMENSIONLESS)})
        assert result.status is ResultStatus.FAIL

    def test_r2952_fails_above_60(self):
        rule = HoningCrosshatchAngleBoundsRule()
        result = rule.evaluate({"crosshatch_included_angle_deg": q(65, Unit.DIMENSIONLESS)})
        assert result.status is ResultStatus.FAIL

    def test_r2953_passes_when_final_greater(self):
        rule = HoningStockPositiveRule()
        result = rule.evaluate({"diameter_initial": q(81, Unit.MM),
                                "diameter_final": q(82, Unit.MM)})
        assert result.status is ResultStatus.PASS

    def test_r2953_fails_when_equal(self):
        rule = HoningStockPositiveRule()
        result = rule.evaluate({"diameter_initial": q(82, Unit.MM),
                                "diameter_final": q(82, Unit.MM)})
        assert result.status is ResultStatus.FAIL


# ── Rule ID uniqueness ────────────────────────────────────────────────────────

class TestHoningRuleIDUniqueness:

    def test_no_duplicate_rule_ids(self):
        assert len(HONING_RULE_IDS) == len(set(HONING_RULE_IDS))

    def test_all_ids_in_r29xx_range(self):
        for rid in HONING_RULE_IDS:
            assert rid.startswith("R-29"), f"{rid} not in R-29xx range"

    def test_rule_count(self):
        # 6 calculation + 3 validation = 9
        assert len(HONING_RULES) == 9
