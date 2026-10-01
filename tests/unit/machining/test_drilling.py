"""Tests for deterministic drilling calculations (Stage 3D).

Covers:
  - effective_drilling_travel
  - drilling_machining_time
  - hole_cross_sectional_area
  - cylindrical_hole_volume
  - drilling_mrr
  - Stage 3A formula reuse (spindle speed, feed rate)
  - round-trip consistency
  - input validation
  - deterministic repeatability
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.domain.exceptions import UnitError
from backend.domain.units import Quantity, Unit
from backend.machining.drilling import (
    cylindrical_hole_volume,
    drilling_machining_time,
    drilling_mrr,
    effective_drilling_travel,
    hole_cross_sectional_area,
)
from backend.machining.exceptions import MachiningMathError

Q = Quantity.of

PI = Decimal("3.14159265358979323846264338327950288419716939937510")


# ===================================================================
# effective_drilling_travel
# ===================================================================

class TestEffectiveDrillingTravel:
    def test_depth_only(self):
        result = effective_drilling_travel(Q("30", Unit.MM))
        assert result.unit is Unit.MM
        assert result.value == Decimal("30")

    def test_with_approach(self):
        result = effective_drilling_travel(Q("30", Unit.MM), approach_allowance=Q("2", Unit.MM))
        assert result.value == Decimal("32")

    def test_with_breakthrough(self):
        result = effective_drilling_travel(
            Q("30", Unit.MM), breakthrough_allowance=Q("3", Unit.MM)
        )
        assert result.value == Decimal("33")

    def test_with_both_allowances(self):
        result = effective_drilling_travel(
            Q("30", Unit.MM),
            approach_allowance=Q("2", Unit.MM),
            breakthrough_allowance=Q("3", Unit.MM),
        )
        assert result.value == Decimal("35")

    def test_zero_depth(self):
        result = effective_drilling_travel(Q("0", Unit.MM))
        assert result.value == Decimal("0")

    def test_zero_allowances(self):
        result = effective_drilling_travel(
            Q("30", Unit.MM),
            approach_allowance=Q("0", Unit.MM),
            breakthrough_allowance=Q("0", Unit.MM),
        )
        assert result.value == Decimal("30")

    def test_negative_depth_rejected(self):
        with pytest.raises(MachiningMathError, match="non-negative"):
            effective_drilling_travel(Q("-5", Unit.MM))

    def test_negative_approach_rejected(self):
        with pytest.raises(MachiningMathError, match="non-negative"):
            effective_drilling_travel(Q("30", Unit.MM), approach_allowance=Q("-1", Unit.MM))

    def test_wrong_unit_rejected(self):
        with pytest.raises(MachiningMathError, match="mm"):
            effective_drilling_travel(Q("30", Unit.M_MIN))


# ===================================================================
# drilling_machining_time
# ===================================================================

class TestDrillingMachiningTime:
    def test_nominal(self):
        # n=1000, f=0.2 → Vf=200; depth=30 → t=30/200=0.15
        result = drilling_machining_time(
            Q("1000", Unit.RPM), Q("0.2", Unit.MM_REV), Q("30", Unit.MM)
        )
        assert result.unit is Unit.MIN
        assert result.value == Decimal("0.15")

    def test_with_allowances(self):
        # n=1000, f=0.2 → Vf=200; depth=30+2+3=35 → t=35/200=0.175
        result = drilling_machining_time(
            Q("1000", Unit.RPM), Q("0.2", Unit.MM_REV), Q("30", Unit.MM),
            approach_allowance=Q("2", Unit.MM),
            breakthrough_allowance=Q("3", Unit.MM),
        )
        assert result.value == Decimal("0.175")

    def test_zero_depth(self):
        result = drilling_machining_time(
            Q("1000", Unit.RPM), Q("0.2", Unit.MM_REV), Q("0", Unit.MM)
        )
        assert result.value == Decimal("0")

    def test_zero_rpm_positive_depth_rejected(self):
        with pytest.raises(MachiningMathError):
            drilling_machining_time(
                Q("0", Unit.RPM), Q("0.2", Unit.MM_REV), Q("30", Unit.MM)
            )


# ===================================================================
# hole_cross_sectional_area
# ===================================================================

class TestHoleCrossSectionalArea:
    def test_nominal(self):
        # D=10 → A = π×100/4 = 25π
        result = hole_cross_sectional_area(Q("10", Unit.MM))
        assert result.unit is Unit.DIMENSIONLESS
        expected = PI * Decimal("100") / Decimal("4")
        assert result.value == expected

    def test_small_diameter(self):
        result = hole_cross_sectional_area(Q("1", Unit.MM))
        expected = PI / Decimal("4")
        assert result.value == expected

    def test_zero_rejected(self):
        with pytest.raises(MachiningMathError, match="positive"):
            hole_cross_sectional_area(Q("0", Unit.MM))

    def test_negative_rejected(self):
        with pytest.raises(MachiningMathError, match="positive"):
            hole_cross_sectional_area(Q("-5", Unit.MM))

    def test_wrong_unit_rejected(self):
        with pytest.raises(MachiningMathError, match="mm"):
            hole_cross_sectional_area(Q("10", Unit.RPM))


# ===================================================================
# cylindrical_hole_volume
# ===================================================================

class TestCylindricalHoleVolume:
    def test_nominal(self):
        # D=10, depth=30 → V = (π×100/4)×30 = 750π
        result = cylindrical_hole_volume(Q("10", Unit.MM), Q("30", Unit.MM))
        assert result.unit is Unit.MM3
        expected = PI * Decimal("100") / Decimal("4") * Decimal("30")
        assert result.value == expected

    def test_zero_depth(self):
        result = cylindrical_hole_volume(Q("10", Unit.MM), Q("0", Unit.MM))
        assert result.value == Decimal("0")

    def test_zero_diameter_rejected(self):
        with pytest.raises(MachiningMathError, match="positive"):
            cylindrical_hole_volume(Q("0", Unit.MM), Q("30", Unit.MM))

    def test_negative_depth_rejected(self):
        with pytest.raises(MachiningMathError, match="non-negative"):
            cylindrical_hole_volume(Q("10", Unit.MM), Q("-5", Unit.MM))


# ===================================================================
# drilling_mrr
# ===================================================================

class TestDrillingMRR:
    def test_nominal(self):
        # D=10, Vf=200 → Q = (π×100/4)×200
        result = drilling_mrr(Q("10", Unit.MM), Q("200", Unit.MM_MIN))
        assert result.unit is Unit.MM3_MIN
        expected = PI * Decimal("100") / Decimal("4") * Decimal("200")
        assert result.value == expected

    def test_zero_feed_rate(self):
        result = drilling_mrr(Q("10", Unit.MM), Q("0", Unit.MM_MIN))
        assert result.value == Decimal("0")

    def test_zero_diameter_rejected(self):
        with pytest.raises(MachiningMathError, match="positive"):
            drilling_mrr(Q("0", Unit.MM), Q("200", Unit.MM_MIN))

    def test_negative_feed_rejected(self):
        with pytest.raises(MachiningMathError, match="non-negative"):
            drilling_mrr(Q("10", Unit.MM), Q("-50", Unit.MM_MIN))


# ===================================================================
# Stage 3A reuse verification
# ===================================================================

class TestStage3AReuse:
    def test_drilling_time_uses_stage3a(self):
        """drilling_machining_time should match manual Stage 3A composition."""
        from backend.machining.formulas import (
            feed_rate_from_rpm_feed_per_rev,
            machining_time_from_distance_feed_rate,
        )

        n = Q("1000", Unit.RPM)
        f = Q("0.2", Unit.MM_REV)
        depth = Q("30", Unit.MM)
        approach = Q("2", Unit.MM)

        vf = feed_rate_from_rpm_feed_per_rev(n, f)
        travel = Q("32", Unit.MM)  # 30 + 2
        t_manual = machining_time_from_distance_feed_rate(travel, vf)
        t_drilling = drilling_machining_time(n, f, depth, approach_allowance=approach)
        assert t_manual.value == t_drilling.value


# ===================================================================
# Round-trip consistency
# ===================================================================

class TestRoundTrip:
    def test_volume_equals_area_times_depth(self):
        """V should equal A × depth."""
        d = Q("12", Unit.MM)
        depth = Q("25", Unit.MM)
        area = hole_cross_sectional_area(d)
        volume = cylindrical_hole_volume(d, depth)
        assert volume.value == area.value * depth.value

    def test_mrr_equals_area_times_feed_rate(self):
        """Q should equal A × Vf."""
        d = Q("12", Unit.MM)
        vf = Q("300", Unit.MM_MIN)
        area = hole_cross_sectional_area(d)
        mrr = drilling_mrr(d, vf)
        assert mrr.value == area.value * vf.value


# ===================================================================
# Deterministic repeatability
# ===================================================================

class TestDeterminism:
    def test_repeat_mrr(self):
        a = drilling_mrr(Q("10", Unit.MM), Q("200", Unit.MM_MIN))
        b = drilling_mrr(Q("10", Unit.MM), Q("200", Unit.MM_MIN))
        assert a.value == b.value

    def test_repeat_volume(self):
        a = cylindrical_hole_volume(Q("10", Unit.MM), Q("30", Unit.MM))
        b = cylindrical_hole_volume(Q("10", Unit.MM), Q("30", Unit.MM))
        assert a.value == b.value


# ===================================================================
# NaN / Infinity
# ===================================================================

class TestSpecialValues:
    def test_nan_diameter_rejected(self):
        with pytest.raises((MachiningMathError, ValueError, UnitError)):
            drilling_mrr(Q(float("nan"), Unit.MM), Q("200", Unit.MM_MIN))

    def test_inf_diameter_rejected(self):
        with pytest.raises((MachiningMathError, ValueError, UnitError)):
            drilling_mrr(Q(float("inf"), Unit.MM), Q("200", Unit.MM_MIN))

    def test_nan_depth_rejected(self):
        with pytest.raises((MachiningMathError, ValueError, UnitError)):
            cylindrical_hole_volume(Q("10", Unit.MM), Q(float("nan"), Unit.MM))
