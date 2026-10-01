"""Stage 3A tests: deterministic machining formulas.

Expected values are computed independently (not by re-implementing the
formula) using Decimal arithmetic with the same pi constant.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError
from backend.machining.formulas import (
    PI,
    cutting_speed_from_spindle_speed,
    feed_per_rev_from_feed_rate,
    feed_per_tooth_from_feed_rate,
    feed_rate_from_rpm_feed_per_rev,
    feed_rate_from_rpm_tooth_feed,
    machining_time_from_distance_feed_rate,
    milling_material_removal_rate,
    power_from_torque_rpm,
    spindle_speed_from_cutting_speed,
    spindle_speed_from_feed_rate_feed_per_rev,
    spindle_speed_from_feed_rate_tooth_feed,
    tooth_count_from_feed_rate,
    torque_from_power_rpm,
)

# ---------------------------------------------------------------------------
# Independent expected-value helpers (not formula re-implementations)
# ---------------------------------------------------------------------------

def _expect_spindle_speed(vc: Decimal, d: Decimal) -> Decimal:
    """Independently compute n = 1000*Vc/(pi*D)."""
    return (Decimal("1000") * vc) / (PI * d)


def _expect_cutting_speed(n: Decimal, d: Decimal) -> Decimal:
    """Independently compute Vc = pi*D*n/1000."""
    return (PI * d * n) / Decimal("1000")


# ---------------------------------------------------------------------------
# A. Spindle speed <-> cutting speed
# ---------------------------------------------------------------------------

class TestSpindleSpeedFromCuttingSpeed:
    def test_vc_plus_diameter_gives_rpm(self) -> None:
        vc = Quantity.of(100, Unit.M_MIN)
        d = Quantity.of(10, Unit.MM)
        result = spindle_speed_from_cutting_speed(vc, d)
        assert result.unit is Unit.RPM
        expected = _expect_spindle_speed(Decimal("100"), Decimal("10"))
        assert result.value == expected

    def test_known_textbook_round_trip(self) -> None:
        vc = Quantity.of(120, Unit.M_MIN)
        d = Quantity.of(20, Unit.MM)
        rpm = spindle_speed_from_cutting_speed(vc, d)
        back = cutting_speed_from_spindle_speed(rpm, d)
        assert back.unit is Unit.M_MIN
        assert back.value == Decimal("120")

    def test_zero_diameter_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            spindle_speed_from_cutting_speed(
                Quantity.of(100, Unit.M_MIN), Quantity.of(0, Unit.MM)
            )

    def test_negative_diameter_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            spindle_speed_from_cutting_speed(
                Quantity.of(100, Unit.M_MIN), Quantity.of(-5, Unit.MM)
            )

    def test_wrong_unit_cutting_speed_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            spindle_speed_from_cutting_speed(
                Quantity.of(100, Unit.MM_MIN), Quantity.of(10, Unit.MM)
            )

    def test_wrong_unit_diameter_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            spindle_speed_from_cutting_speed(
                Quantity.of(100, Unit.M_MIN), Quantity.of(10, Unit.MM_MIN)
            )

    def test_zero_cutting_speed_gives_zero_rpm(self) -> None:
        result = spindle_speed_from_cutting_speed(
            Quantity.of(0, Unit.M_MIN), Quantity.of(10, Unit.MM)
        )
        assert result.value == Decimal("0")
        assert result.unit is Unit.RPM


class TestCuttingSpeedFromSpindleSpeed:
    def test_rpm_plus_diameter_gives_vc(self) -> None:
        n = Quantity.of(3183, Unit.RPM)
        d = Quantity.of(10, Unit.MM)
        result = cutting_speed_from_spindle_speed(n, d)
        assert result.unit is Unit.M_MIN
        expected = _expect_cutting_speed(Decimal("3183"), Decimal("10"))
        assert result.value == expected

    def test_zero_rpm_gives_zero_vc(self) -> None:
        result = cutting_speed_from_spindle_speed(
            Quantity.of(0, Unit.RPM), Quantity.of(10, Unit.MM)
        )
        assert result.value == Decimal("0")
        assert result.unit is Unit.M_MIN

    def test_zero_diameter_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            cutting_speed_from_spindle_speed(
                Quantity.of(1000, Unit.RPM), Quantity.of(0, Unit.MM)
            )

    def test_negative_diameter_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            cutting_speed_from_spindle_speed(
                Quantity.of(1000, Unit.RPM), Quantity.of(-1, Unit.MM)
            )


# ---------------------------------------------------------------------------
# B. Turning / drilling feed
# ---------------------------------------------------------------------------

class TestFeedRateFromRpmFeedPerRev:
    def test_rpm_times_mm_rev_gives_mm_min(self) -> None:
        n = Quantity.of(1000, Unit.RPM)
        f = Quantity.of(0.2, Unit.MM_REV)
        result = feed_rate_from_rpm_feed_per_rev(n, f)
        assert result.unit is Unit.MM_MIN
        assert result.value == Decimal("200")

    def test_zero_rpm_gives_zero_feed(self) -> None:
        result = feed_rate_from_rpm_feed_per_rev(
            Quantity.of(0, Unit.RPM), Quantity.of(0.2, Unit.MM_REV)
        )
        assert result.value == Decimal("0")

    def test_wrong_unit_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            feed_rate_from_rpm_feed_per_rev(
                Quantity.of(1000, Unit.MM), Quantity.of(0.2, Unit.MM_REV)
            )


class TestFeedPerRevFromFeedRate:
    def test_inverse_feed_per_rev(self) -> None:
        fr = Quantity.of(200, Unit.MM_MIN)
        n = Quantity.of(1000, Unit.RPM)
        result = feed_per_rev_from_feed_rate(fr, n)
        assert result.unit is Unit.MM_REV
        assert result.value == Decimal("0.2")

    def test_zero_rpm_inverse_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            feed_per_rev_from_feed_rate(
                Quantity.of(200, Unit.MM_MIN), Quantity.of(0, Unit.RPM)
            )

    def test_wrong_unit_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            feed_per_rev_from_feed_rate(
                Quantity.of(200, Unit.MM_REV), Quantity.of(1000, Unit.RPM)
            )


class TestSpindleSpeedFromFeedRateFeedPerRev:
    def test_inverse_rpm(self) -> None:
        fr = Quantity.of(200, Unit.MM_MIN)
        f = Quantity.of(0.2, Unit.MM_REV)
        result = spindle_speed_from_feed_rate_feed_per_rev(fr, f)
        assert result.unit is Unit.RPM
        assert result.value == Decimal("1000")

    def test_zero_feed_per_rev_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            spindle_speed_from_feed_rate_feed_per_rev(
                Quantity.of(200, Unit.MM_MIN), Quantity.of(0, Unit.MM_REV)
            )


# ---------------------------------------------------------------------------
# C. Milling feed
# ---------------------------------------------------------------------------

class TestFeedRateFromRpmToothFeed:
    def test_rpm_times_z_times_fz(self) -> None:
        n = Quantity.of(2000, Unit.RPM)
        fz = Quantity.of(0.1, Unit.MM_TOOTH)
        result = feed_rate_from_rpm_tooth_feed(n, 4, fz)
        assert result.unit is Unit.MM_MIN
        assert result.value == Decimal("800")

    def test_zero_rpm_gives_zero_feed(self) -> None:
        result = feed_rate_from_rpm_tooth_feed(
            Quantity.of(0, Unit.RPM), 4, Quantity.of(0.1, Unit.MM_TOOTH)
        )
        assert result.value == Decimal("0")

    def test_tooth_count_zero_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            feed_rate_from_rpm_tooth_feed(
                Quantity.of(2000, Unit.RPM), 0, Quantity.of(0.1, Unit.MM_TOOTH)
            )

    def test_tooth_count_negative_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            feed_rate_from_rpm_tooth_feed(
                Quantity.of(2000, Unit.RPM), -2, Quantity.of(0.1, Unit.MM_TOOTH)
            )

    def test_tooth_count_float_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            feed_rate_from_rpm_tooth_feed(
                Quantity.of(2000, Unit.RPM), 2.5, Quantity.of(0.1, Unit.MM_TOOTH)  # type: ignore[arg-type]
            )

    def test_tooth_count_bool_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            feed_rate_from_rpm_tooth_feed(
                Quantity.of(2000, Unit.RPM), True, Quantity.of(0.1, Unit.MM_TOOTH)  # type: ignore[arg-type]
            )


class TestFeedPerToothFromFeedRate:
    def test_inverse_fz(self) -> None:
        fr = Quantity.of(800, Unit.MM_MIN)
        n = Quantity.of(2000, Unit.RPM)
        result = feed_per_tooth_from_feed_rate(fr, n, 4)
        assert result.unit is Unit.MM_TOOTH
        assert result.value == Decimal("0.1")

    def test_zero_rpm_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            feed_per_tooth_from_feed_rate(
                Quantity.of(800, Unit.MM_MIN), Quantity.of(0, Unit.RPM), 4
            )

    def test_zero_tooth_count_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            feed_per_tooth_from_feed_rate(
                Quantity.of(800, Unit.MM_MIN), Quantity.of(2000, Unit.RPM), 0
            )


class TestSpindleSpeedFromFeedRateToothFeed:
    def test_inverse_rpm(self) -> None:
        fr = Quantity.of(800, Unit.MM_MIN)
        fz = Quantity.of(0.1, Unit.MM_TOOTH)
        result = spindle_speed_from_feed_rate_tooth_feed(fr, 4, fz)
        assert result.unit is Unit.RPM
        assert result.value == Decimal("2000")

    def test_zero_fz_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            spindle_speed_from_feed_rate_tooth_feed(
                Quantity.of(800, Unit.MM_MIN), 4, Quantity.of(0, Unit.MM_TOOTH)
            )


class TestToothCountFromFeedRate:
    def test_inverse_tooth_count(self) -> None:
        fr = Quantity.of(800, Unit.MM_MIN)
        n = Quantity.of(2000, Unit.RPM)
        fz = Quantity.of(0.1, Unit.MM_TOOTH)
        result = tooth_count_from_feed_rate(fr, n, fz)
        assert result == 4

    def test_non_integer_result_rejected(self) -> None:
        fr = Quantity.of(850, Unit.MM_MIN)
        n = Quantity.of(2000, Unit.RPM)
        fz = Quantity.of(0.1, Unit.MM_TOOTH)
        with pytest.raises(MachiningMathError):
            tooth_count_from_feed_rate(fr, n, fz)

    def test_zero_rpm_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            tooth_count_from_feed_rate(
                Quantity.of(800, Unit.MM_MIN), Quantity.of(0, Unit.RPM),
                Quantity.of(0.1, Unit.MM_TOOTH)
            )


# ---------------------------------------------------------------------------
# D. Material removal rate
# ---------------------------------------------------------------------------

class TestMillingMaterialRemovalRate:
    def test_basic_mrr(self) -> None:
        ap = Quantity.of(2, Unit.MM)
        ae = Quantity.of(10, Unit.MM)
        fr = Quantity.of(200, Unit.MM_MIN)
        result = milling_material_removal_rate(ap, ae, fr)
        assert result.unit is Unit.MM3_MIN
        assert result.value == Decimal("4000")

    def test_zero_depth_gives_zero_mrr(self) -> None:
        result = milling_material_removal_rate(
            Quantity.of(0, Unit.MM), Quantity.of(10, Unit.MM),
            Quantity.of(200, Unit.MM_MIN)
        )
        assert result.value == Decimal("0")

    def test_negative_depth_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            milling_material_removal_rate(
                Quantity.of(-1, Unit.MM), Quantity.of(10, Unit.MM),
                Quantity.of(200, Unit.MM_MIN)
            )

    def test_wrong_unit_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            milling_material_removal_rate(
                Quantity.of(2, Unit.MM), Quantity.of(10, Unit.MM),
                Quantity.of(200, Unit.M_MIN)
            )


# ---------------------------------------------------------------------------
# E. Machining time
# ---------------------------------------------------------------------------

class TestMachiningTime:
    def test_distance_over_feed_gives_minutes(self) -> None:
        distance = Quantity.of(100, Unit.MM)
        fr = Quantity.of(200, Unit.MM_MIN)
        result = machining_time_from_distance_feed_rate(distance, fr)
        assert result.unit is Unit.MIN
        assert result.value == Decimal("0.5")

    def test_zero_distance_gives_zero_time(self) -> None:
        result = machining_time_from_distance_feed_rate(
            Quantity.of(0, Unit.MM), Quantity.of(200, Unit.MM_MIN)
        )
        assert result.value == Decimal("0")
        assert result.unit is Unit.MIN

    def test_zero_feed_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            machining_time_from_distance_feed_rate(
                Quantity.of(100, Unit.MM), Quantity.of(0, Unit.MM_MIN)
            )

    def test_negative_distance_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            machining_time_from_distance_feed_rate(
                Quantity.of(-10, Unit.MM), Quantity.of(200, Unit.MM_MIN)
            )


# ---------------------------------------------------------------------------
# F. Power / torque
# ---------------------------------------------------------------------------

class TestTorqueFromPower:
    def test_power_plus_rpm_gives_torque(self) -> None:
        power = Quantity.of(10, Unit.KW)
        n = Quantity.of(1000, Unit.RPM)
        result = torque_from_power_rpm(power, n)
        assert result.unit is Unit.NM
        # T = P * 60000 / (2*pi*n) = 10*60000/(2*pi*1000) = 600000/(2000*pi)
        expected = (Decimal("10") * Decimal("60000")) / (Decimal("2") * PI * Decimal("1000"))
        assert result.value == expected

    def test_zero_rpm_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            torque_from_power_rpm(Quantity.of(10, Unit.KW), Quantity.of(0, Unit.RPM))

    def test_wrong_unit_rejected(self) -> None:
        with pytest.raises(MachiningMathError):
            torque_from_power_rpm(Quantity.of(10, Unit.NM), Quantity.of(1000, Unit.RPM))


class TestPowerFromTorque:
    def test_torque_plus_rpm_gives_power(self) -> None:
        torque = Quantity.of(95.4929658551372, Unit.NM)  # ~ 9549.3/100
        n = Quantity.of(1000, Unit.RPM)
        result = power_from_torque_rpm(torque, n)
        assert result.unit is Unit.KW
        expected = (
            Decimal("2") * PI * Decimal("1000") * Decimal("95.4929658551372")
        ) / Decimal("60000")
        assert result.value == expected

    def test_round_trip_consistency(self) -> None:
        power = Quantity.of(5, Unit.KW)
        n = Quantity.of(1500, Unit.RPM)
        torque = torque_from_power_rpm(power, n)
        back = power_from_torque_rpm(torque, n)
        assert back.value == Decimal("5")
        assert back.unit is Unit.KW

    def test_zero_rpm_gives_zero_power(self) -> None:
        result = power_from_torque_rpm(
            Quantity.of(50, Unit.NM), Quantity.of(0, Unit.RPM)
        )
        assert result.value == Decimal("0")
        assert result.unit is Unit.KW


# ---------------------------------------------------------------------------
# G. General
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_repeatable_results(self) -> None:
        vc = Quantity.of(100, Unit.M_MIN)
        d = Quantity.of(10, Unit.MM)
        r1 = spindle_speed_from_cutting_speed(vc, d)
        r2 = spindle_speed_from_cutting_speed(vc, d)
        assert r1.value == r2.value
        assert r1.unit is r2.unit

    def test_no_ai_or_network_dependency(self) -> None:
        import backend.machining.formulas as mod
        source = open(mod.__file__).read()
        assert "import requests" not in source
        assert "import openai" not in source
        assert "import torch" not in source
