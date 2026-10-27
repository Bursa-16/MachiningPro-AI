"""Tests for VirtualConditionCalculator (EPIC_04B Phase 2).

FABRICATED_VIRTUAL_CONDITION=NO
"""

import pytest
from decimal import Decimal

from backend.drawing_intelligence.bonus_tolerance import compute_virtual_condition
from backend.drawing_intelligence.requirements import (
    ExpandedFeatureControlFrame,
    FeatureOfSize,
    FeatureOfSizeKind,
    GdtCharacteristic,
    GdtModifier,
)


def _hole(upper="25.033", lower="25.000"):
    return FeatureOfSize(
        fos_id="FOS-H", kind=FeatureOfSizeKind.INTERNAL_CYLINDRICAL,
        nominal_mm=Decimal("25.0"),
        upper_limit_mm=Decimal(upper), lower_limit_mm=Decimal(lower),
        actual_size_mm=None, source_req_id=None, feature_id=None,
    )


def _shaft(upper="25.000", lower="24.979"):
    return FeatureOfSize(
        fos_id="FOS-S", kind=FeatureOfSizeKind.EXTERNAL_CYLINDRICAL,
        nominal_mm=Decimal("25.0"),
        upper_limit_mm=Decimal(upper), lower_limit_mm=Decimal(lower),
        actual_size_mm=None, source_req_id=None, feature_id=None,
    )


def _fcf(modifier, tol="0.05"):
    return ExpandedFeatureControlFrame(
        characteristic=GdtCharacteristic.POSITION,
        tolerance_value=Decimal(tol),
        tolerance_unit="mm", diameter_zone=True,
        modifier=modifier, datum_frame=None,
    )


class TestVirtualConditionRfsNotApplicable:
    def test_rfs_not_computed(self):
        r = compute_virtual_condition(_fcf(GdtModifier.NONE), _hole())
        assert r.computed is False
        assert "not applicable" in r.description


class TestVirtualConditionInternalMmc:
    """Hole MMC: VC = MMC_size − tolerance."""

    def test_basic(self):
        # MMC hole = 25.000, tol = 0.050 → VC = 24.950
        r = compute_virtual_condition(_fcf(GdtModifier.MMC, "0.050"), _hole())
        assert r.computed is True
        assert r.virtual_condition_mm == Decimal("24.950")

    def test_description_mentions_internal_mmc(self):
        r = compute_virtual_condition(_fcf(GdtModifier.MMC, "0.050"), _hole())
        assert "Internal MMC" in r.description


class TestVirtualConditionInternalLmc:
    """Hole LMC: VC = LMC_size + tolerance."""

    def test_basic(self):
        # LMC hole = 25.033, tol = 0.050 → VC = 25.083
        r = compute_virtual_condition(_fcf(GdtModifier.LMC, "0.050"), _hole())
        assert r.computed is True
        assert r.virtual_condition_mm == Decimal("25.083")


class TestVirtualConditionExternalMmc:
    """Shaft MMC: VC = MMC_size + tolerance."""

    def test_basic(self):
        # MMC shaft = 25.000, tol = 0.050 → VC = 25.050
        r = compute_virtual_condition(_fcf(GdtModifier.MMC, "0.050"), _shaft())
        assert r.computed is True
        assert r.virtual_condition_mm == Decimal("25.050")

    def test_description_mentions_external(self):
        r = compute_virtual_condition(_fcf(GdtModifier.MMC, "0.050"), _shaft())
        assert "External" in r.description


class TestVirtualConditionExternalLmc:
    """Shaft LMC: VC = LMC_size − tolerance."""

    def test_basic(self):
        # LMC shaft = 24.979, tol = 0.050 → VC = 24.929
        r = compute_virtual_condition(_fcf(GdtModifier.LMC, "0.050"), _shaft())
        assert r.computed is True
        assert r.virtual_condition_mm == Decimal("24.929")


class TestVirtualConditionMissingLimits:
    def test_no_limits_not_computed(self):
        fos = FeatureOfSize(
            fos_id="FOS-X", kind=FeatureOfSizeKind.INTERNAL_CYLINDRICAL,
            nominal_mm=None, upper_limit_mm=None, lower_limit_mm=None,
            actual_size_mm=None, source_req_id=None, feature_id=None,
        )
        r = compute_virtual_condition(_fcf(GdtModifier.MMC), fos)
        assert r.computed is False
        assert "INSUFFICIENT_DATA" in r.description


class TestVirtualConditionNonCylindrical:
    def test_non_cylindrical_not_computed(self):
        fos = FeatureOfSize(
            fos_id="FOS-W", kind=FeatureOfSizeKind.WIDTH,
            nominal_mm=Decimal("10"), upper_limit_mm=Decimal("10.05"),
            lower_limit_mm=Decimal("10.00"),
            actual_size_mm=None, source_req_id=None, feature_id=None,
        )
        r = compute_virtual_condition(_fcf(GdtModifier.MMC), fos)
        assert r.computed is False
        assert "cylindrical" in r.description.lower()
