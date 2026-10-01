"""Tests for deterministic hole finishing calculations (Stage 3F)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.domain.exceptions import UnitError
from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError
from backend.machining.hole_finishing import (
    annular_cross_sectional_area,
    annular_volume,
    diametral_stock,
    effective_hole_finishing_travel,
    hole_finishing_machining_time,
    hole_finishing_mrr,
    radial_stock,
)

Q = Quantity.of
PI = Decimal("3.14159265358979323846264338327950288419716939937510")
FOUR = Decimal("4")
TWO = Decimal("2")


class TestDiametralStock:
    def test_nominal(self):
        result = diametral_stock(Q("9.8", Unit.MM), Q("10", Unit.MM))
        assert result.unit is Unit.MM
        assert result.value == Decimal("0.2")

    def test_equal_diameters(self):
        result = diametral_stock(Q("10", Unit.MM), Q("10", Unit.MM))
        assert result.value == Decimal("0")

    def test_reversed_rejected(self):
        with pytest.raises(MachiningMathError, match=">="):
            diametral_stock(Q("10", Unit.MM), Q("9", Unit.MM))

    def test_zero_diameter_rejected(self):
        with pytest.raises(MachiningMathError, match="positive"):
            diametral_stock(Q("0", Unit.MM), Q("10", Unit.MM))

    def test_wrong_unit_rejected(self):
        with pytest.raises(MachiningMathError, match="mm"):
            diametral_stock(Q("9.8", Unit.RPM), Q("10", Unit.MM))


class TestRadialStock:
    def test_nominal(self):
        result = radial_stock(Q("9.8", Unit.MM), Q("10", Unit.MM))
        assert result.value == Decimal("0.1")

    def test_diametral_equals_twice_radial(self):
        d_i, d_f = Q("9.5", Unit.MM), Q("10", Unit.MM)
        dia = diametral_stock(d_i, d_f)
        rad = radial_stock(d_i, d_f)
        assert dia.value == rad.value * TWO

    def test_equal_diameters(self):
        result = radial_stock(Q("10", Unit.MM), Q("10", Unit.MM))
        assert result.value == Decimal("0")


class TestAnnularCrossSectionalArea:
    def test_nominal(self):
        # D_i=9.8, D_f=10 → π/4 × (100 - 96.04) = π/4 × 3.96
        result = annular_cross_sectional_area(Q("9.8", Unit.MM), Q("10", Unit.MM))
        assert result.unit is Unit.DIMENSIONLESS
        expected = (PI / FOUR) * (Decimal("100") - Decimal("96.04"))
        assert result.value == expected

    def test_equal_diameters_zero(self):
        result = annular_cross_sectional_area(Q("10", Unit.MM), Q("10", Unit.MM))
        assert result.value == Decimal("0")


class TestAnnularVolume:
    def test_nominal(self):
        d_i, d_f, length = Q("9.8", Unit.MM), Q("10", Unit.MM), Q("30", Unit.MM)
        result = annular_volume(d_i, d_f, length)
        assert result.unit is Unit.MM3
        expected = (PI / FOUR) * (Decimal("100") - Decimal("96.04")) * Decimal("30")
        assert result.value == expected

    def test_zero_length(self):
        result = annular_volume(Q("9.8", Unit.MM), Q("10", Unit.MM), Q("0", Unit.MM))
        assert result.value == Decimal("0")

    def test_negative_length_rejected(self):
        with pytest.raises(MachiningMathError, match="non-negative"):
            annular_volume(Q("9.8", Unit.MM), Q("10", Unit.MM), Q("-5", Unit.MM))

    def test_volume_equals_area_times_length(self):
        d_i, d_f = Q("9.5", Unit.MM), Q("10", Unit.MM)
        length = Q("25", Unit.MM)
        area = annular_cross_sectional_area(d_i, d_f)
        vol = annular_volume(d_i, d_f, length)
        assert vol.value == area.value * length.value


class TestHoleFinishingMRR:
    def test_nominal(self):
        d_i, d_f = Q("9.8", Unit.MM), Q("10", Unit.MM)
        vf = Q("200", Unit.MM_MIN)
        result = hole_finishing_mrr(d_i, d_f, vf)
        assert result.unit is Unit.MM3_MIN
        expected = (PI / FOUR) * (Decimal("100") - Decimal("96.04")) * Decimal("200")
        assert result.value == expected

    def test_zero_feed(self):
        result = hole_finishing_mrr(Q("9.8", Unit.MM), Q("10", Unit.MM), Q("0", Unit.MM_MIN))
        assert result.value == Decimal("0")

    def test_equal_diameters_zero(self):
        result = hole_finishing_mrr(Q("10", Unit.MM), Q("10", Unit.MM), Q("200", Unit.MM_MIN))
        assert result.value == Decimal("0")

    def test_mrr_equals_area_times_vf(self):
        d_i, d_f = Q("9.5", Unit.MM), Q("10", Unit.MM)
        vf = Q("150", Unit.MM_MIN)
        area = annular_cross_sectional_area(d_i, d_f)
        mrr = hole_finishing_mrr(d_i, d_f, vf)
        assert mrr.value == area.value * vf.value


class TestEffectiveTravel:
    def test_length_only(self):
        result = effective_hole_finishing_travel(Q("30", Unit.MM))
        assert result.value == Decimal("30")

    def test_with_allowances(self):
        result = effective_hole_finishing_travel(
            Q("30", Unit.MM),
            approach_allowance=Q("2", Unit.MM),
            overtravel_allowance=Q("1", Unit.MM),
        )
        assert result.value == Decimal("33")

    def test_negative_rejected(self):
        with pytest.raises(MachiningMathError, match="non-negative"):
            effective_hole_finishing_travel(Q("-5", Unit.MM))


class TestMachiningTime:
    def test_nominal(self):
        # n=500, f=0.4 → Vf=200; L=30 → t=0.15
        result = hole_finishing_machining_time(
            Q("500", Unit.RPM), Q("0.4", Unit.MM_REV), Q("30", Unit.MM)
        )
        assert result.unit is Unit.MIN
        assert result.value == Decimal("0.15")

    def test_with_allowances(self):
        # L_eff=33, Vf=200 → t=0.165
        result = hole_finishing_machining_time(
            Q("500", Unit.RPM), Q("0.4", Unit.MM_REV), Q("30", Unit.MM),
            approach_allowance=Q("2", Unit.MM),
            overtravel_allowance=Q("1", Unit.MM),
        )
        assert result.value == Decimal("0.165")

    def test_zero_length(self):
        result = hole_finishing_machining_time(
            Q("500", Unit.RPM), Q("0.4", Unit.MM_REV), Q("0", Unit.MM)
        )
        assert result.value == Decimal("0")


class TestDeterminism:
    def test_repeat_mrr(self):
        a = hole_finishing_mrr(Q("9.8", Unit.MM), Q("10", Unit.MM), Q("200", Unit.MM_MIN))
        b = hole_finishing_mrr(Q("9.8", Unit.MM), Q("10", Unit.MM), Q("200", Unit.MM_MIN))
        assert a.value == b.value


class TestSpecialValues:
    def test_nan_rejected(self):
        with pytest.raises((MachiningMathError, ValueError, UnitError)):
            diametral_stock(Q(float("nan"), Unit.MM), Q("10", Unit.MM))

    def test_inf_rejected(self):
        with pytest.raises((MachiningMathError, ValueError, UnitError)):
            diametral_stock(Q(float("inf"), Unit.MM), Q("10", Unit.MM))
