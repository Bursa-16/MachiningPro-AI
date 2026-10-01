"""Stage 3B tests: deterministic turning calculations."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError
from backend.machining.turning import (
    PI,
    equal_pass_depth,
    facing_removed_volume,
    facing_travel,
    final_diameter_boring,
    final_diameter_external,
    longitudinal_turning_time,
    pass_count,
    radial_stock_boring,
    radial_stock_external,
    removed_volume_boring,
    removed_volume_external,
    turning_mrr_direct,
    turning_mrr_from_volume_time,
)

FOUR = Decimal("4")


def _expected_cylinder_volume(d_outer: Decimal, d_inner: Decimal, length: Decimal) -> Decimal:
    """Independent reference: (pi/4)*(D_outer^2 - D_inner^2)*L."""
    return (PI / FOUR) * (d_outer * d_outer - d_inner * d_inner) * length


# ---------------------------------------------------------------------------
# A. External turning geometry
# ---------------------------------------------------------------------------

class TestExternalRadialStock:
    def test_radial_stock_from_diameters(self) -> None:
        result = radial_stock_external(
            Quantity.of(50, Unit.MM), Quantity.of(46, Unit.MM)
        )
        assert result.value == Decimal("2")
        assert result.unit is Unit.MM

    def test_equal_diameters_zero_stock(self) -> None:
        result = radial_stock_external(
            Quantity.of(50, Unit.MM), Quantity.of(50, Unit.MM)
        )
        assert result.value == Decimal("0")

    def test_final_exceeds_initial_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            radial_stock_external(
                Quantity.of(46, Unit.MM), Quantity.of(50, Unit.MM)
            )

    def test_zero_initial_diameter_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            radial_stock_external(
                Quantity.of(0, Unit.MM), Quantity.of(0, Unit.MM)
            )

    def test_negative_diameter_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            radial_stock_external(
                Quantity.of(-50, Unit.MM), Quantity.of(46, Unit.MM)
            )

    def test_wrong_unit_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            radial_stock_external(
                Quantity.of(50, Unit.MM_MIN), Quantity.of(46, Unit.MM)
            )


class TestExternalFinalDiameter:
    def test_final_diameter_from_radial_depth(self) -> None:
        result = final_diameter_external(
            Quantity.of(50, Unit.MM), Quantity.of(2, Unit.MM)
        )
        assert result.value == Decimal("46")
        assert result.unit is Unit.MM

    def test_inverse_consistency(self) -> None:
        d0 = Quantity.of(60, Unit.MM)
        stock = radial_stock_external(d0, Quantity.of(50, Unit.MM))
        d1 = final_diameter_external(d0, stock)
        assert d1.value == Decimal("50")

    def test_excessive_depth_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            final_diameter_external(
                Quantity.of(10, Unit.MM), Quantity.of(6, Unit.MM)
            )

    def test_zero_depth_gives_same_diameter(self) -> None:
        result = final_diameter_external(
            Quantity.of(50, Unit.MM), Quantity.of(0, Unit.MM)
        )
        assert result.value == Decimal("50")


# ---------------------------------------------------------------------------
# B. Boring geometry
# ---------------------------------------------------------------------------

class TestBoringRadialStock:
    def test_boring_radial_stock(self) -> None:
        result = radial_stock_boring(
            Quantity.of(20, Unit.MM), Quantity.of(24, Unit.MM)
        )
        assert result.value == Decimal("2")
        assert result.unit is Unit.MM

    def test_equal_diameters_zero_stock(self) -> None:
        result = radial_stock_boring(
            Quantity.of(20, Unit.MM), Quantity.of(20, Unit.MM)
        )
        assert result.value == Decimal("0")

    def test_final_smaller_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            radial_stock_boring(
                Quantity.of(24, Unit.MM), Quantity.of(20, Unit.MM)
            )


class TestBoringFinalDiameter:
    def test_final_bore_from_radial_depth(self) -> None:
        result = final_diameter_boring(
            Quantity.of(20, Unit.MM), Quantity.of(2, Unit.MM)
        )
        assert result.value == Decimal("24")

    def test_inverse_consistency(self) -> None:
        d0 = Quantity.of(30, Unit.MM)
        stock = radial_stock_boring(d0, Quantity.of(36, Unit.MM))
        d1 = final_diameter_boring(d0, stock)
        assert d1.value == Decimal("36")


# ---------------------------------------------------------------------------
# C. Pass count
# ---------------------------------------------------------------------------

class TestPassCount:
    def test_exact_division(self) -> None:
        result = pass_count(
            Quantity.of(6, Unit.MM), Quantity.of(2, Unit.MM)
        )
        assert result == 3

    def test_remainder_ceils(self) -> None:
        result = pass_count(
            Quantity.of(5, Unit.MM), Quantity.of(2, Unit.MM)
        )
        assert result == 3

    def test_zero_stock_zero_passes(self) -> None:
        result = pass_count(
            Quantity.of(0, Unit.MM), Quantity.of(2, Unit.MM)
        )
        assert result == 0

    def test_max_depth_zero_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            pass_count(
                Quantity.of(5, Unit.MM), Quantity.of(0, Unit.MM)
            )

    def test_max_depth_negative_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            pass_count(
                Quantity.of(5, Unit.MM), Quantity.of(-1, Unit.MM)
            )


class TestEqualPassDepth:
    def test_equal_depth(self) -> None:
        result = equal_pass_depth(Quantity.of(5, Unit.MM), 3)
        assert result.value == Decimal("5") / Decimal("3")
        assert result.unit is Unit.MM

    def test_depth_never_exceeds_max(self) -> None:
        max_depth = Decimal("2")
        pc = pass_count(Quantity.of(5, Unit.MM), Quantity.of(2, Unit.MM))
        depth = equal_pass_depth(Quantity.of(5, Unit.MM), pc)
        assert depth.value <= max_depth

    def test_zero_pass_count_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            equal_pass_depth(Quantity.of(5, Unit.MM), 0)

    def test_float_pass_count_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            equal_pass_depth(Quantity.of(5, Unit.MM), 2.5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# D. Longitudinal turning time
# ---------------------------------------------------------------------------

class TestLongitudinalTurningTime:
    def test_rpm_feed_length(self) -> None:
        result = longitudinal_turning_time(
            Quantity.of(1000, Unit.RPM),
            Quantity.of(0.2, Unit.MM_REV),
            Quantity.of(100, Unit.MM),
        )
        assert result.unit is Unit.MIN
        # feed_rate = 1000 * 0.2 = 200 mm/min; time = 100/200 = 0.5 min
        assert result.value == Decimal("0.5")

    def test_with_allowances(self) -> None:
        result = longitudinal_turning_time(
            Quantity.of(1000, Unit.RPM),
            Quantity.of(0.2, Unit.MM_REV),
            Quantity.of(100, Unit.MM),
            approach_allowance=Quantity.of(2, Unit.MM),
            overtravel_allowance=Quantity.of(3, Unit.MM),
        )
        # effective = 100 + 2 + 3 = 105; feed_rate = 200; time = 105/200 = 0.525
        assert result.value == Decimal("0.525")

    def test_zero_length(self) -> None:
        result = longitudinal_turning_time(
            Quantity.of(1000, Unit.RPM),
            Quantity.of(0.2, Unit.MM_REV),
            Quantity.of(0, Unit.MM),
        )
        assert result.value == Decimal("0")

    def test_zero_rpm_with_feed_rejected_via_zero_feed_rate(self) -> None:
        with pytest.raises(MachiningMathError):
            longitudinal_turning_time(
                Quantity.of(0, Unit.RPM),
                Quantity.of(0.2, Unit.MM_REV),
                Quantity.of(100, Unit.MM),
            )

    def test_negative_feed_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            longitudinal_turning_time(
                Quantity.of(1000, Unit.RPM),
                Quantity.of(-0.2, Unit.MM_REV),
                Quantity.of(100, Unit.MM),
            )


# ---------------------------------------------------------------------------
# E. Removed volume
# ---------------------------------------------------------------------------

class TestExternalRemovedVolume:
    def test_independent_reference_case(self) -> None:
        """D0=50, D1=46, L=100 -> V = (pi/2500)*100 = 2*pi*100."""
        result = removed_volume_external(
            Quantity.of(50, Unit.MM),
            Quantity.of(46, Unit.MM),
            Quantity.of(100, Unit.MM),
        )
        expected = _expected_cylinder_volume(
            Decimal("50"), Decimal("46"), Decimal("100")
        )
        assert result.value == expected
        assert result.unit is Unit.MM3

    def test_zero_stock_zero_volume(self) -> None:
        result = removed_volume_external(
            Quantity.of(50, Unit.MM),
            Quantity.of(50, Unit.MM),
            Quantity.of(100, Unit.MM),
        )
        assert result.value == Decimal("0")

    def test_wrong_unit_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            removed_volume_external(
                Quantity.of(50, Unit.MM),
                Quantity.of(46, Unit.MM),
                Quantity.of(100, Unit.MM_MIN),
            )


class TestBoringRemovedVolume:
    def test_independent_reference_case(self) -> None:
        result = removed_volume_boring(
            Quantity.of(20, Unit.MM),
            Quantity.of(24, Unit.MM),
            Quantity.of(50, Unit.MM),
        )
        expected = _expected_cylinder_volume(
            Decimal("24"), Decimal("20"), Decimal("50")
        )
        assert result.value == expected
        assert result.unit is Unit.MM3

    def test_zero_stock_zero_volume(self) -> None:
        result = removed_volume_boring(
            Quantity.of(20, Unit.MM),
            Quantity.of(20, Unit.MM),
            Quantity.of(50, Unit.MM),
        )
        assert result.value == Decimal("0")


# ---------------------------------------------------------------------------
# F. Turning MRR
# ---------------------------------------------------------------------------

class TestTurningMRR:
    def test_volume_over_time(self) -> None:
        result = turning_mrr_from_volume_time(
            Quantity.of(1000, Unit.MM3),
            Quantity.of(2, Unit.MIN),
        )
        assert result.value == Decimal("500")
        assert result.unit is Unit.MM3_MIN

    def test_zero_time_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            turning_mrr_from_volume_time(
                Quantity.of(1000, Unit.MM3),
                Quantity.of(0, Unit.MIN),
            )

    def test_direct_mrr(self) -> None:
        result = turning_mrr_direct(
            Quantity.of(50, Unit.MM),
            Quantity.of(46, Unit.MM),
            Quantity.of(200, Unit.MM_MIN),
        )
        # area = (pi/4)*(50^2 - 46^2) = (pi/4)*(2500-2116) = (pi/4)*384
        expected_area = (PI / FOUR) * (Decimal("2500") - Decimal("2116"))
        expected = expected_area * Decimal("200")
        assert result.value == expected
        assert result.unit is Unit.MM3_MIN

    def test_volume_time_vs_direct_consistency(self) -> None:
        d0 = Quantity.of(60, Unit.MM)
        d1 = Quantity.of(50, Unit.MM)
        fr = Quantity.of(300, Unit.MM_MIN)
        direct = turning_mrr_direct(d0, d1, fr)
        # volume per unit time should match direct calculation
        volume = removed_volume_external(d0, d1, Quantity.of(1, Unit.MM))
        # MRR_direct = area * fr = (pi/4)*(D0^2-D1^2) * fr
        # volume for L=1 = (pi/4)*(D0^2-D1^2) * 1
        # So MRR_direct = volume_L1 * fr
        assert direct.value == volume.value * fr.value


# ---------------------------------------------------------------------------
# G. Facing
# ---------------------------------------------------------------------------

class TestFacingTravel:
    def test_outer_to_center(self) -> None:
        result = facing_travel(
            Quantity.of(100, Unit.MM),
            Quantity.of(0, Unit.MM),
        )
        assert result.value == Decimal("50")
        assert result.unit is Unit.MM

    def test_outer_to_inner(self) -> None:
        result = facing_travel(
            Quantity.of(100, Unit.MM),
            Quantity.of(40, Unit.MM),
        )
        assert result.value == Decimal("30")

    def test_with_allowances(self) -> None:
        result = facing_travel(
            Quantity.of(100, Unit.MM),
            Quantity.of(40, Unit.MM),
            approach_allowance=Quantity.of(1, Unit.MM),
            overtravel_allowance=Quantity.of(1, Unit.MM),
        )
        assert result.value == Decimal("32")

    def test_inner_exceeds_outer_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            facing_travel(
                Quantity.of(40, Unit.MM),
                Quantity.of(100, Unit.MM),
            )

    def test_negative_allowance_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            facing_travel(
                Quantity.of(100, Unit.MM),
                Quantity.of(0, Unit.MM),
                approach_allowance=Quantity.of(-1, Unit.MM),
            )


class TestFacingRemovedVolume:
    def test_face_volume(self) -> None:
        result = facing_removed_volume(
            Quantity.of(100, Unit.MM),
            Quantity.of(40, Unit.MM),
            Quantity.of(2, Unit.MM),
        )
        expected = _expected_cylinder_volume(
            Decimal("100"), Decimal("40"), Decimal("2")
        )
        assert result.value == expected
        assert result.unit is Unit.MM3

    def test_zero_face_depth_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            facing_removed_volume(
                Quantity.of(100, Unit.MM),
                Quantity.of(40, Unit.MM),
                Quantity.of(0, Unit.MM),
            )


# ---------------------------------------------------------------------------
# H. General
# ---------------------------------------------------------------------------

class TestGeneral:
    def test_deterministic_repeatability(self) -> None:
        r1 = radial_stock_external(
            Quantity.of(50, Unit.MM), Quantity.of(46, Unit.MM)
        )
        r2 = radial_stock_external(
            Quantity.of(50, Unit.MM), Quantity.of(46, Unit.MM)
        )
        assert r1.value == r2.value
        assert r1.unit is r2.unit

    def test_no_ai_or_network_dependency(self) -> None:
        import backend.machining.turning as mod
        source = open(mod.__file__).read()
        assert "import requests" not in source
        assert "import openai" not in source
        assert "import torch" not in source
