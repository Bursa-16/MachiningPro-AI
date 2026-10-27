"""Tests for FeatureOfSize model (EPIC_04B Phase 2)."""

import pytest
from decimal import Decimal

from backend.drawing_intelligence.requirements import (
    FeatureOfSize,
    FeatureOfSizeKind,
)


def _internal(actual=None, upper="25.033", lower="25.000"):
    return FeatureOfSize(
        fos_id="FOS-001",
        kind=FeatureOfSizeKind.INTERNAL_CYLINDRICAL,
        nominal_mm=Decimal("25.0"),
        upper_limit_mm=Decimal(upper),
        lower_limit_mm=Decimal(lower),
        actual_size_mm=Decimal(actual) if actual else None,
        source_req_id="REQ-001",
        feature_id="F-001",
    )


def _external(actual=None, upper="25.000", lower="24.979"):
    return FeatureOfSize(
        fos_id="FOS-002",
        kind=FeatureOfSizeKind.EXTERNAL_CYLINDRICAL,
        nominal_mm=Decimal("25.0"),
        upper_limit_mm=Decimal(upper),
        lower_limit_mm=Decimal(lower),
        actual_size_mm=Decimal(actual) if actual else None,
        source_req_id="REQ-002",
        feature_id="F-002",
    )


class TestFeatureOfSizeValidation:
    def test_empty_fos_id_rejected(self):
        with pytest.raises(ValueError, match="fos_id"):
            FeatureOfSize(
                fos_id="",
                kind=FeatureOfSizeKind.INTERNAL_CYLINDRICAL,
                nominal_mm=None, upper_limit_mm=None, lower_limit_mm=None,
                actual_size_mm=None, source_req_id=None, feature_id=None,
            )

    def test_inverted_limits_rejected(self):
        with pytest.raises(ValueError, match="upper_limit_mm"):
            FeatureOfSize(
                fos_id="FOS-X",
                kind=FeatureOfSizeKind.INTERNAL_CYLINDRICAL,
                nominal_mm=Decimal("10"),
                upper_limit_mm=Decimal("9"),   # inverted
                lower_limit_mm=Decimal("10"),
                actual_size_mm=None, source_req_id=None, feature_id=None,
            )

    def test_equal_limits_accepted(self):
        fos = FeatureOfSize(
            fos_id="FOS-X",
            kind=FeatureOfSizeKind.WIDTH,
            nominal_mm=Decimal("10"),
            upper_limit_mm=Decimal("10"),
            lower_limit_mm=Decimal("10"),
            actual_size_mm=None, source_req_id=None, feature_id=None,
        )
        assert fos.upper_limit_mm == fos.lower_limit_mm


class TestFeatureOfSizeMmcLmc:
    def test_internal_mmc_is_smallest(self):
        fos = _internal()
        assert fos.mmc_size_mm == Decimal("25.000")

    def test_internal_lmc_is_largest(self):
        fos = _internal()
        assert fos.lmc_size_mm == Decimal("25.033")

    def test_external_mmc_is_largest(self):
        fos = _external()
        assert fos.mmc_size_mm == Decimal("25.000")

    def test_external_lmc_is_smallest(self):
        fos = _external()
        assert fos.lmc_size_mm == Decimal("24.979")

    def test_no_limits_returns_none(self):
        fos = FeatureOfSize(
            fos_id="FOS-X",
            kind=FeatureOfSizeKind.INTERNAL_CYLINDRICAL,
            nominal_mm=None, upper_limit_mm=None, lower_limit_mm=None,
            actual_size_mm=None, source_req_id=None, feature_id=None,
        )
        assert fos.mmc_size_mm is None
        assert fos.lmc_size_mm is None


class TestFeatureOfSizeIsTrueFos:
    def test_internal_cylindrical_is_true(self):
        assert _internal().is_true_fos is True

    def test_external_cylindrical_is_true(self):
        assert _external().is_true_fos is True

    def test_non_fos_is_false(self):
        fos = FeatureOfSize(
            fos_id="FOS-X",
            kind=FeatureOfSizeKind.NON_FEATURE_OF_SIZE,
            nominal_mm=None, upper_limit_mm=None, lower_limit_mm=None,
            actual_size_mm=None, source_req_id=None, feature_id=None,
        )
        assert fos.is_true_fos is False

    def test_unknown_is_false(self):
        fos = FeatureOfSize(
            fos_id="FOS-X",
            kind=FeatureOfSizeKind.UNKNOWN,
            nominal_mm=None, upper_limit_mm=None, lower_limit_mm=None,
            actual_size_mm=None, source_req_id=None, feature_id=None,
        )
        assert fos.is_true_fos is False

    def test_width_is_true(self):
        fos = FeatureOfSize(
            fos_id="FOS-X",
            kind=FeatureOfSizeKind.WIDTH,
            nominal_mm=Decimal("10"), upper_limit_mm=Decimal("10.015"),
            lower_limit_mm=Decimal("10.000"),
            actual_size_mm=None, source_req_id=None, feature_id=None,
        )
        assert fos.is_true_fos is True


class TestActualSizeNeverFabricated:
    """FABRICATED_ACTUAL_SIZE=NO — actual_size_mm must remain None unless explicitly set."""

    def test_actual_size_defaults_none(self):
        fos = _internal()
        assert fos.actual_size_mm is None

    def test_actual_size_explicit_set(self):
        fos = _internal(actual="25.010")
        assert fos.actual_size_mm == Decimal("25.010")
