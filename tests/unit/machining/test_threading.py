"""Tests for deterministic threading calculations (Stage 3E)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.domain.exceptions import UnitError
from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError
from backend.machining.threading import (
    effective_threading_travel,
    lead_from_pitch,
    pitch_from_lead,
    spindle_speed_from_thread_feed,
    thread_feed_rate,
    threading_machining_time,
    threading_revolutions,
    threads_per_mm,
)

Q = Quantity.of


# ===================================================================
# lead_from_pitch / pitch_from_lead
# ===================================================================

class TestLeadFromPitch:
    def test_single_start(self):
        result = lead_from_pitch(Q("1.5", Unit.MM_REV))
        assert result.unit is Unit.MM_REV
        assert result.value == Decimal("1.5")

    def test_single_start_explicit(self):
        result = lead_from_pitch(Q("1.5", Unit.MM_REV), 1)
        assert result.value == Decimal("1.5")

    def test_multi_start(self):
        result = lead_from_pitch(Q("1.5", Unit.MM_REV), 3)
        assert result.value == Decimal("4.5")

    def test_zero_pitch_rejected(self):
        with pytest.raises(MachiningMathError, match="positive"):
            lead_from_pitch(Q("0", Unit.MM_REV))

    def test_negative_pitch_rejected(self):
        with pytest.raises(MachiningMathError, match="positive"):
            lead_from_pitch(Q("-1", Unit.MM_REV))

    def test_zero_starts_rejected(self):
        with pytest.raises(MachiningMathError, match="positive"):
            lead_from_pitch(Q("1.5", Unit.MM_REV), 0)

    def test_bool_starts_rejected(self):
        with pytest.raises(MachiningMathError, match="integer"):
            lead_from_pitch(Q("1.5", Unit.MM_REV), True)

    def test_wrong_unit_rejected(self):
        with pytest.raises(MachiningMathError, match="mm/rev"):
            lead_from_pitch(Q("1.5", Unit.MM))


class TestPitchFromLead:
    def test_single_start(self):
        result = pitch_from_lead(Q("1.5", Unit.MM_REV))
        assert result.value == Decimal("1.5")

    def test_multi_start(self):
        result = pitch_from_lead(Q("4.5", Unit.MM_REV), 3)
        assert result.value == Decimal("1.5")

    def test_zero_lead_rejected(self):
        with pytest.raises(MachiningMathError, match="positive"):
            pitch_from_lead(Q("0", Unit.MM_REV))


class TestThreadsPerMm:
    def test_nominal(self):
        # pitch=1.5 → 1/1.5 = 0.666...
        result = threads_per_mm(Q("1.5", Unit.MM_REV))
        assert result.unit is Unit.DIMENSIONLESS
        expected = Decimal("1") / Decimal("1.5")
        assert result.value == expected

    def test_fine_pitch(self):
        result = threads_per_mm(Q("0.5", Unit.MM_REV))
        assert result.value == Decimal("2")

    def test_zero_rejected(self):
        with pytest.raises(MachiningMathError, match="positive"):
            threads_per_mm(Q("0", Unit.MM_REV))


# ===================================================================
# Round-trip: lead ↔ pitch
# ===================================================================

class TestLeadPitchRoundTrip:
    def test_single_start_round_trip(self):
        pitch = Q("1.5", Unit.MM_REV)
        lead = lead_from_pitch(pitch, 1)
        recovered = pitch_from_lead(lead, 1)
        assert recovered.value == pitch.value

    def test_multi_start_round_trip(self):
        pitch = Q("2.0", Unit.MM_REV)
        starts = 3
        lead = lead_from_pitch(pitch, starts)
        recovered = pitch_from_lead(lead, starts)
        assert recovered.value == pitch.value


# ===================================================================
# thread_feed_rate / spindle_speed_from_thread_feed
# ===================================================================

class TestThreadFeedRate:
    def test_nominal(self):
        # n=500, lead=1.5 → Vf=750
        result = thread_feed_rate(Q("500", Unit.RPM), Q("1.5", Unit.MM_REV))
        assert result.unit is Unit.MM_MIN
        assert result.value == Decimal("750")

    def test_zero_rpm(self):
        result = thread_feed_rate(Q("0", Unit.RPM), Q("1.5", Unit.MM_REV))
        assert result.value == Decimal("0")


class TestSpindleSpeedFromThreadFeed:
    def test_nominal(self):
        result = spindle_speed_from_thread_feed(Q("750", Unit.MM_MIN), Q("1.5", Unit.MM_REV))
        assert result.unit is Unit.RPM
        assert result.value == Decimal("500")

    def test_zero_lead_rejected(self):
        with pytest.raises(MachiningMathError, match="positive"):
            spindle_speed_from_thread_feed(Q("750", Unit.MM_MIN), Q("0", Unit.MM_REV))


class TestFeedRoundTrip:
    def test_vf_to_n_round_trip(self):
        n = Q("500", Unit.RPM)
        lead = Q("1.5", Unit.MM_REV)
        vf = thread_feed_rate(n, lead)
        n_recovered = spindle_speed_from_thread_feed(vf, lead)
        assert n_recovered.value == n.value


# ===================================================================
# effective_threading_travel
# ===================================================================

class TestEffectiveThreadingTravel:
    def test_length_only(self):
        result = effective_threading_travel(Q("20", Unit.MM))
        assert result.value == Decimal("20")

    def test_with_allowances(self):
        result = effective_threading_travel(
            Q("20", Unit.MM),
            approach_allowance=Q("2", Unit.MM),
            overtravel_allowance=Q("1", Unit.MM),
        )
        assert result.value == Decimal("23")

    def test_zero_length(self):
        result = effective_threading_travel(Q("0", Unit.MM))
        assert result.value == Decimal("0")

    def test_negative_rejected(self):
        with pytest.raises(MachiningMathError, match="non-negative"):
            effective_threading_travel(Q("-5", Unit.MM))

    def test_wrong_unit_rejected(self):
        with pytest.raises(MachiningMathError, match="mm"):
            effective_threading_travel(Q("20", Unit.RPM))


# ===================================================================
# threading_machining_time
# ===================================================================

class TestThreadingMachiningTime:
    def test_nominal(self):
        # n=500, lead=1.5 → Vf=750; L=20 → t=20/750
        result = threading_machining_time(
            Q("500", Unit.RPM), Q("1.5", Unit.MM_REV), Q("20", Unit.MM)
        )
        assert result.unit is Unit.MIN
        expected = Decimal("20") / Decimal("750")
        assert result.value == expected

    def test_with_allowances(self):
        # L_eff=23, Vf=750 → t=23/750
        result = threading_machining_time(
            Q("500", Unit.RPM), Q("1.5", Unit.MM_REV), Q("20", Unit.MM),
            approach_allowance=Q("2", Unit.MM),
            overtravel_allowance=Q("1", Unit.MM),
        )
        expected = Decimal("23") / Decimal("750")
        assert result.value == expected

    def test_zero_length(self):
        result = threading_machining_time(
            Q("500", Unit.RPM), Q("1.5", Unit.MM_REV), Q("0", Unit.MM)
        )
        assert result.value == Decimal("0")


# ===================================================================
# threading_revolutions
# ===================================================================

class TestThreadingRevolutions:
    def test_nominal(self):
        # travel=30, lead=1.5 → 20 revolutions
        result = threading_revolutions(Q("30", Unit.MM), Q("1.5", Unit.MM_REV))
        assert result.unit is Unit.DIMENSIONLESS
        assert result.value == Decimal("20")

    def test_fractional(self):
        # travel=10, lead=3 → 3.333...
        result = threading_revolutions(Q("10", Unit.MM), Q("3", Unit.MM_REV))
        expected = Decimal("10") / Decimal("3")
        assert result.value == expected

    def test_zero_travel(self):
        result = threading_revolutions(Q("0", Unit.MM), Q("1.5", Unit.MM_REV))
        assert result.value == Decimal("0")

    def test_zero_lead_rejected(self):
        with pytest.raises(MachiningMathError, match="positive"):
            threading_revolutions(Q("30", Unit.MM), Q("0", Unit.MM_REV))


# ===================================================================
# Determinism
# ===================================================================

class TestDeterminism:
    def test_repeat_lead(self):
        a = lead_from_pitch(Q("1.5", Unit.MM_REV), 3)
        b = lead_from_pitch(Q("1.5", Unit.MM_REV), 3)
        assert a.value == b.value

    def test_repeat_time(self):
        a = threading_machining_time(
            Q("500", Unit.RPM), Q("1.5", Unit.MM_REV), Q("20", Unit.MM)
        )
        b = threading_machining_time(
            Q("500", Unit.RPM), Q("1.5", Unit.MM_REV), Q("20", Unit.MM)
        )
        assert a.value == b.value


# ===================================================================
# NaN / Infinity
# ===================================================================

class TestSpecialValues:
    def test_nan_pitch_rejected(self):
        with pytest.raises((MachiningMathError, ValueError, UnitError)):
            lead_from_pitch(Q(float("nan"), Unit.MM_REV))

    def test_inf_pitch_rejected(self):
        with pytest.raises((MachiningMathError, ValueError, UnitError)):
            lead_from_pitch(Q(float("inf"), Unit.MM_REV))
