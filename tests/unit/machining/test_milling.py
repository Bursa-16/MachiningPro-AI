"""Tests for deterministic milling calculations (Stage 3C).

Covers:
  - feed_per_rev_from_tooth_feed
  - radial_engagement_ratio
  - axial_engagement_ratio
  - milling_machining_time
  - milling_mrr
  - input validation (negative, zero, NaN, Inf, bool, wrong unit)
  - round-trip consistency
  - deterministic repeatability
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.domain.exceptions import UnitError
from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError
from backend.machining.milling import (
    axial_engagement_ratio,
    feed_per_rev_from_tooth_feed,
    milling_machining_time,
    milling_mrr,
    radial_engagement_ratio,
)

Q = Quantity.of


# ===================================================================
# feed_per_rev_from_tooth_feed
# ===================================================================

class TestFeedPerRevFromToothFeed:
    def test_nominal(self):
        # 4 teeth, 0.1 mm/tooth → 0.4 mm/rev
        result = feed_per_rev_from_tooth_feed(4, Q("0.1", Unit.MM_TOOTH))
        assert result.unit is Unit.MM_REV
        assert result.value == Decimal("0.4")

    def test_single_tooth(self):
        result = feed_per_rev_from_tooth_feed(1, Q("0.2", Unit.MM_TOOTH))
        assert result.value == Decimal("0.2")

    def test_zero_feed_per_tooth(self):
        result = feed_per_rev_from_tooth_feed(4, Q("0", Unit.MM_TOOTH))
        assert result.value == Decimal("0")

    def test_large_tooth_count(self):
        result = feed_per_rev_from_tooth_feed(12, Q("0.05", Unit.MM_TOOTH))
        assert result.value == Decimal("0.60")

    def test_wrong_unit_rejected(self):
        with pytest.raises(MachiningMathError, match="mm/tooth"):
            feed_per_rev_from_tooth_feed(4, Q("0.1", Unit.MM_REV))

    def test_negative_feed_rejected(self):
        with pytest.raises(MachiningMathError, match="non-negative"):
            feed_per_rev_from_tooth_feed(4, Q("-0.1", Unit.MM_TOOTH))

    def test_zero_tooth_count_rejected(self):
        with pytest.raises(MachiningMathError, match="positive"):
            feed_per_rev_from_tooth_feed(0, Q("0.1", Unit.MM_TOOTH))

    def test_negative_tooth_count_rejected(self):
        with pytest.raises(MachiningMathError, match="positive"):
            feed_per_rev_from_tooth_feed(-2, Q("0.1", Unit.MM_TOOTH))

    def test_bool_tooth_count_rejected(self):
        with pytest.raises(MachiningMathError, match="integer"):
            feed_per_rev_from_tooth_feed(True, Q("0.1", Unit.MM_TOOTH))

    def test_float_tooth_count_rejected(self):
        with pytest.raises(MachiningMathError, match="integer"):
            feed_per_rev_from_tooth_feed(2.5, Q("0.1", Unit.MM_TOOTH))  # type: ignore[arg-type]

    def test_deterministic_repeatability(self):
        a = feed_per_rev_from_tooth_feed(4, Q("0.1", Unit.MM_TOOTH))
        b = feed_per_rev_from_tooth_feed(4, Q("0.1", Unit.MM_TOOTH))
        assert a.value == b.value


# ===================================================================
# radial_engagement_ratio
# ===================================================================

class TestRadialEngagementRatio:
    def test_full_slotting(self):
        # ae = D → ratio = 1.0
        result = radial_engagement_ratio(Q("20", Unit.MM), Q("20", Unit.MM))
        assert result.unit is Unit.DIMENSIONLESS
        assert result.value == Decimal("1")

    def test_half_engagement(self):
        result = radial_engagement_ratio(Q("10", Unit.MM), Q("20", Unit.MM))
        assert result.value == Decimal("0.5")

    def test_zero_radial_width(self):
        result = radial_engagement_ratio(Q("0", Unit.MM), Q("20", Unit.MM))
        assert result.value == Decimal("0")

    def test_ae_exceeds_d(self):
        # Not rejected by the ratio function itself — geometrically allowed
        # as a ratio (R-2210 validates the physical constraint)
        result = radial_engagement_ratio(Q("25", Unit.MM), Q("20", Unit.MM))
        assert result.value == Decimal("1.25")

    def test_zero_diameter_rejected(self):
        with pytest.raises(MachiningMathError, match="positive"):
            radial_engagement_ratio(Q("10", Unit.MM), Q("0", Unit.MM))

    def test_negative_ae_rejected(self):
        with pytest.raises(MachiningMathError, match="non-negative"):
            radial_engagement_ratio(Q("-5", Unit.MM), Q("20", Unit.MM))

    def test_wrong_unit_rejected(self):
        with pytest.raises(MachiningMathError, match="mm"):
            radial_engagement_ratio(Q("10", Unit.M_MIN), Q("20", Unit.MM))


# ===================================================================
# axial_engagement_ratio
# ===================================================================

class TestAxialEngagementRatio:
    def test_nominal(self):
        result = axial_engagement_ratio(Q("5", Unit.MM), Q("20", Unit.MM))
        assert result.unit is Unit.DIMENSIONLESS
        assert result.value == Decimal("0.25")

    def test_deep_cut(self):
        result = axial_engagement_ratio(Q("40", Unit.MM), Q("20", Unit.MM))
        assert result.value == Decimal("2")

    def test_zero_depth(self):
        result = axial_engagement_ratio(Q("0", Unit.MM), Q("20", Unit.MM))
        assert result.value == Decimal("0")

    def test_zero_diameter_rejected(self):
        with pytest.raises(MachiningMathError, match="positive"):
            axial_engagement_ratio(Q("5", Unit.MM), Q("0", Unit.MM))

    def test_negative_depth_rejected(self):
        with pytest.raises(MachiningMathError, match="non-negative"):
            axial_engagement_ratio(Q("-5", Unit.MM), Q("20", Unit.MM))


# ===================================================================
# milling_machining_time
# ===================================================================

class TestMillingMachiningTime:
    def test_nominal(self):
        # n=1000, z=4, fz=0.1 → Vf=400 mm/min; L=200 → t=0.5 min
        result = milling_machining_time(
            Q("1000", Unit.RPM), 4, Q("0.1", Unit.MM_TOOTH), Q("200", Unit.MM)
        )
        assert result.unit is Unit.MIN
        assert result.value == Decimal("0.5")

    def test_zero_distance(self):
        result = milling_machining_time(
            Q("1000", Unit.RPM), 4, Q("0.1", Unit.MM_TOOTH), Q("0", Unit.MM)
        )
        assert result.value == Decimal("0")

    def test_very_small_feed(self):
        result = milling_machining_time(
            Q("100", Unit.RPM), 1, Q("0.001", Unit.MM_TOOTH), Q("10", Unit.MM)
        )
        assert result.unit is Unit.MIN
        assert result.value == Decimal("100")

    def test_zero_rpm_with_positive_distance_rejected(self):
        # Vf=0 with L>0 → division by zero in machining_time
        with pytest.raises(MachiningMathError, match="positive"):
            milling_machining_time(
                Q("0", Unit.RPM), 4, Q("0.1", Unit.MM_TOOTH), Q("100", Unit.MM)
            )


# ===================================================================
# milling_mrr
# ===================================================================

class TestMillingMRR:
    def test_nominal(self):
        # ap=2, ae=10, n=1000, z=4, fz=0.1 → Vf=400; MRR=2*10*400=8000 mm³/min
        result = milling_mrr(
            Q("2", Unit.MM), Q("10", Unit.MM),
            Q("1000", Unit.RPM), 4, Q("0.1", Unit.MM_TOOTH),
        )
        assert result.unit is Unit.MM3_MIN
        assert result.value == Decimal("8000")

    def test_zero_depth_gives_zero(self):
        result = milling_mrr(
            Q("0", Unit.MM), Q("10", Unit.MM),
            Q("1000", Unit.RPM), 4, Q("0.1", Unit.MM_TOOTH),
        )
        assert result.value == Decimal("0")

    def test_zero_width_gives_zero(self):
        result = milling_mrr(
            Q("2", Unit.MM), Q("0", Unit.MM),
            Q("1000", Unit.RPM), 4, Q("0.1", Unit.MM_TOOTH),
        )
        assert result.value == Decimal("0")


# ===================================================================
# Round-trip consistency
# ===================================================================

class TestRoundTrip:
    def test_feed_per_rev_round_trip(self):
        """z × fz → f_rev, then fz_recovered ≈ fz."""
        z = 4
        fz = Q("0.15", Unit.MM_TOOTH)
        f_rev = feed_per_rev_from_tooth_feed(z, fz)
        # Recover: fz = f_rev / z
        fz_recovered = f_rev.value / Decimal(z)
        assert fz_recovered == fz.value

    def test_mrr_via_direct_vs_composed(self):
        """milling_mrr should equal Stage 3A milling_material_removal_rate
        when given the same feed rate."""
        from backend.machining.formulas import (
            feed_rate_from_rpm_tooth_feed,
            milling_material_removal_rate,
        )

        ap = Q("3", Unit.MM)
        ae = Q("12", Unit.MM)
        n = Q("800", Unit.RPM)
        z = 4
        fz = Q("0.08", Unit.MM_TOOTH)

        vf = feed_rate_from_rpm_tooth_feed(n, z, fz)
        mrr_direct = milling_material_removal_rate(ap, ae, vf)
        mrr_composed = milling_mrr(ap, ae, n, z, fz)
        assert mrr_direct.value == mrr_composed.value

    def test_machining_time_via_direct_vs_composed(self):
        """milling_machining_time should equal Stage 3A machining_time
        when given the same feed rate."""
        from backend.machining.formulas import (
            feed_rate_from_rpm_tooth_feed,
            machining_time_from_distance_feed_rate,
        )

        n = Q("1000", Unit.RPM)
        z = 4
        fz = Q("0.1", Unit.MM_TOOTH)
        dist = Q("200", Unit.MM)

        vf = feed_rate_from_rpm_tooth_feed(n, z, fz)
        t_direct = machining_time_from_distance_feed_rate(dist, vf)
        t_composed = milling_machining_time(n, z, fz, dist)
        assert t_direct.value == t_composed.value


# ===================================================================
# NaN / Infinity edge cases
# ===================================================================

class TestSpecialValues:
    def test_nan_feed_rejected(self):
        with pytest.raises((MachiningMathError, ValueError, UnitError)):
            feed_per_rev_from_tooth_feed(4, Q(float("nan"), Unit.MM_TOOTH))

    def test_inf_feed_rejected(self):
        with pytest.raises((MachiningMathError, ValueError, UnitError)):
            feed_per_rev_from_tooth_feed(4, Q(float("inf"), Unit.MM_TOOTH))

    def test_nan_diameter_rejected(self):
        with pytest.raises((MachiningMathError, ValueError, UnitError)):
            radial_engagement_ratio(Q("10", Unit.MM), Q(float("nan"), Unit.MM))

    def test_inf_diameter_rejected(self):
        with pytest.raises((MachiningMathError, ValueError, UnitError)):
            radial_engagement_ratio(Q("10", Unit.MM), Q(float("inf"), Unit.MM))
