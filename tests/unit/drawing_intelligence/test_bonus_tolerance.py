"""Tests for BonusToleranceCalculator (EPIC_04B Phase 2).

FABRICATED_ACTUAL_SIZE=NO
FABRICATED_BONUS_TOLERANCE=NO
"""

import pytest
from decimal import Decimal

from backend.drawing_intelligence.bonus_tolerance import compute_bonus_tolerance
from backend.drawing_intelligence.requirements import (
    ExpandedFeatureControlFrame,
    FeatureOfSize,
    FeatureOfSizeKind,
    GdtCharacteristic,
    GdtModifier,
)


def _hole_fos(actual=None, upper="25.033", lower="25.000"):
    return FeatureOfSize(
        fos_id="FOS-H",
        kind=FeatureOfSizeKind.INTERNAL_CYLINDRICAL,
        nominal_mm=Decimal("25.0"),
        upper_limit_mm=Decimal(upper),
        lower_limit_mm=Decimal(lower),
        actual_size_mm=Decimal(actual) if actual else None,
        source_req_id="R-001", feature_id="F-001",
    )


def _shaft_fos(actual=None, upper="25.000", lower="24.979"):
    return FeatureOfSize(
        fos_id="FOS-S",
        kind=FeatureOfSizeKind.EXTERNAL_CYLINDRICAL,
        nominal_mm=Decimal("25.0"),
        upper_limit_mm=Decimal(upper),
        lower_limit_mm=Decimal(lower),
        actual_size_mm=Decimal(actual) if actual else None,
        source_req_id="R-002", feature_id="F-002",
    )


def _fcf(modifier, tol="0.1"):
    return ExpandedFeatureControlFrame(
        characteristic=GdtCharacteristic.POSITION,
        tolerance_value=Decimal(tol),
        tolerance_unit="mm",
        diameter_zone=True,
        modifier=modifier,
        datum_frame=None,
    )


class TestBonusToleranceNotComputedWhenActualNone:
    """FABRICATED_ACTUAL_SIZE=NO gate — no actual size → not computed."""

    def test_mmc_hole_no_actual(self):
        result = compute_bonus_tolerance(_fcf(GdtModifier.MMC), _hole_fos())
        assert result.computed is False
        assert "INSUFFICIENT_DATA" in result.reason_not_computed
        assert result.bonus_amount is None
        assert result.total_tolerance is None

    def test_lmc_shaft_no_actual(self):
        result = compute_bonus_tolerance(_fcf(GdtModifier.LMC), _shaft_fos())
        assert result.computed is False
        assert result.bonus_amount is None


class TestBonusToleranceRfsNotApplicable:
    def test_rfs_returns_not_computed(self):
        result = compute_bonus_tolerance(_fcf(GdtModifier.NONE), _hole_fos(actual="25.010"))
        assert result.computed is False
        assert "MMC or LMC" in result.reason_not_computed


class TestBonusToleranceHoleMmc:
    """Internal (hole) MMC: bonus = actual − MMC_size."""

    def test_hole_at_lmc_max_bonus(self):
        # actual=25.033 (LMC), MMC=25.000 → bonus=0.033
        result = compute_bonus_tolerance(_fcf(GdtModifier.MMC, "0.100"), _hole_fos(actual="25.033"))
        assert result.computed is True
        assert result.bonus_amount == Decimal("0.033")
        assert result.total_tolerance == Decimal("0.133")

    def test_hole_at_mmc_zero_bonus(self):
        # actual=25.000 (MMC) → bonus=0
        result = compute_bonus_tolerance(_fcf(GdtModifier.MMC, "0.100"), _hole_fos(actual="25.000"))
        assert result.computed is True
        assert result.bonus_amount == Decimal("0")
        assert result.total_tolerance == Decimal("0.100")

    def test_hole_midsize_bonus(self):
        # actual=25.016 → bonus=0.016
        result = compute_bonus_tolerance(_fcf(GdtModifier.MMC, "0.050"), _hole_fos(actual="25.016"))
        assert result.computed is True
        assert result.bonus_amount == Decimal("0.016")
        assert result.total_tolerance == Decimal("0.066")


class TestBonusToleranceHoleLmc:
    """Internal (hole) LMC: bonus = LMC_size − actual."""

    def test_hole_at_mmc_max_bonus_lmc(self):
        # actual=25.000 (MMC), LMC=25.033 → bonus=0.033
        result = compute_bonus_tolerance(_fcf(GdtModifier.LMC, "0.100"), _hole_fos(actual="25.000"))
        assert result.computed is True
        assert result.bonus_amount == Decimal("0.033")
        assert result.total_tolerance == Decimal("0.133")


class TestBonusToleranceShaftMmc:
    """External (shaft) MMC: bonus = MMC_size − actual."""

    def test_shaft_at_lmc_max_bonus(self):
        # actual=24.979 (LMC), MMC=25.000 → bonus=0.021
        result = compute_bonus_tolerance(_fcf(GdtModifier.MMC, "0.050"), _shaft_fos(actual="24.979"))
        assert result.computed is True
        assert result.bonus_amount == Decimal("0.021")
        assert result.total_tolerance == Decimal("0.071")

    def test_shaft_at_mmc_zero_bonus(self):
        result = compute_bonus_tolerance(_fcf(GdtModifier.MMC, "0.050"), _shaft_fos(actual="25.000"))
        assert result.computed is True
        assert result.bonus_amount == Decimal("0")

    def test_shaft_midsize_bonus(self):
        # actual=24.990, MMC=25.000 → bonus=0.010
        result = compute_bonus_tolerance(_fcf(GdtModifier.MMC, "0.030"), _shaft_fos(actual="24.990"))
        assert result.computed is True
        assert result.bonus_amount == Decimal("0.010")


class TestBonusToleranceNonFosRejected:
    def test_non_fos_feature_returns_not_computed(self):
        fos = FeatureOfSize(
            fos_id="FOS-X",
            kind=FeatureOfSizeKind.NON_FEATURE_OF_SIZE,
            nominal_mm=None, upper_limit_mm=None, lower_limit_mm=None,
            actual_size_mm=Decimal("10.0"),
            source_req_id=None, feature_id=None,
        )
        result = compute_bonus_tolerance(_fcf(GdtModifier.MMC), fos)
        assert result.computed is False

    def test_no_size_limits_returns_not_computed(self):
        fos = FeatureOfSize(
            fos_id="FOS-X",
            kind=FeatureOfSizeKind.INTERNAL_CYLINDRICAL,
            nominal_mm=None, upper_limit_mm=None, lower_limit_mm=None,
            actual_size_mm=Decimal("10.0"),
            source_req_id=None, feature_id=None,
        )
        result = compute_bonus_tolerance(_fcf(GdtModifier.MMC), fos)
        assert result.computed is False


class TestBonusToleranceSafeTotal:
    def test_safe_total_returns_stated_when_not_computed(self):
        result = compute_bonus_tolerance(_fcf(GdtModifier.MMC), _hole_fos())
        assert result.safe_total == Decimal("0.1")
