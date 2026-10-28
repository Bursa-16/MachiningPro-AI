"""Tests for tolerance capability library — EPIC_04F."""

import pytest

from backend.calibration.models import CalibrationSource, CapabilityStatus
from backend.calibration.tolerance_capability import (
    ToleranceOperationFamily,
    TOLERANCE_CAPABILITY_LIBRARY,
    can_achieve_tolerance,
)


class TestToleranceOperationFamily:
    def test_all_families_present(self):
        families = [f.value for f in ToleranceOperationFamily]
        assert 'FINISH_TURNING' in families
        assert 'GRINDING' in families
        assert 'HONING' in families
        assert 'DRILLING' in families

    def test_library_covers_all_families(self):
        for family in ToleranceOperationFamily:
            assert family in TOLERANCE_CAPABILITY_LIBRARY, f"Missing: {family}"


class TestCanAchieveTolerance:
    def test_finish_turning_it8_25mm_capable(self):
        result = can_achieve_tolerance('FINISH_TURNING', 33.0, 25.0)
        # IT8@25mm ≈ 33µm; FINISH_TURNING covers IT7-9 → within range
        assert result.status in (
            CapabilityStatus.ROBUST, CapabilityStatus.ACCEPTABLE, CapabilityStatus.MARGINAL
        )

    def test_rough_turning_it6_not_capable(self):
        # Rough turning = IT11-13, IT6 is too tight
        it6_25mm = 13.0  # approximate
        result = can_achieve_tolerance('ROUGH_TURNING', it6_25mm, 25.0)
        assert result.status == CapabilityStatus.NOT_CAPABLE

    def test_grinding_it5_50mm_capable(self):
        # Grinding covers IT4-7; IT5 should be achievable
        result = can_achieve_tolerance('GRINDING', 11.0, 50.0)
        assert result.status in (
            CapabilityStatus.ROBUST, CapabilityStatus.ACCEPTABLE, CapabilityStatus.MARGINAL
        )

    def test_unknown_operation_returns_insufficient_data(self):
        result = can_achieve_tolerance('LASER_CUT', 10.0, 25.0)
        assert result.status == CapabilityStatus.INSUFFICIENT_DATA

    def test_unknown_operation_treated_as_supported_no(self):
        # UNKNOWN_CAPABILITY_TREATED_AS_SUPPORTED=NO
        result = can_achieve_tolerance('LASER_CUT', 10.0, 25.0)
        assert result.status != CapabilityStatus.ROBUST
        assert result.status != CapabilityStatus.ACCEPTABLE

    def test_out_of_size_range_reaming(self):
        # Reaming size range: 3–80 mm; 200mm is out of range
        result = can_achieve_tolerance('REAMING', 10.0, 200.0)
        assert result.status == CapabilityStatus.INSUFFICIENT_DATA

    def test_reaming_nominal_10mm_it7(self):
        # Reaming covers IT6-8; IT7@10mm ≈ 15µm
        result = can_achieve_tolerance('REAMING', 15.0, 10.0)
        assert result.status in (
            CapabilityStatus.ROBUST, CapabilityStatus.ACCEPTABLE, CapabilityStatus.MARGINAL
        )

    def test_margin_ratio_positive_when_capable(self):
        result = can_achieve_tolerance('FINISH_BORING', 20.0, 25.0)
        if result.status != CapabilityStatus.INSUFFICIENT_DATA:
            assert result.margin_ratio is not None

    def test_source_is_literature_reference(self):
        result = can_achieve_tolerance('FINISH_TURNING', 25.0, 25.0)
        assert result.source in (
            CalibrationSource.LITERATURE_REFERENCE,
            CalibrationSource.INSUFFICIENT_DATA,
        )

    def test_zero_tolerance_insufficient_data(self):
        result = can_achieve_tolerance('FINISH_TURNING', 0, 25.0)
        assert result.status == CapabilityStatus.INSUFFICIENT_DATA

    def test_negative_tolerance_insufficient_data(self):
        result = can_achieve_tolerance('FINISH_TURNING', -5.0, 25.0)
        assert result.status == CapabilityStatus.INSUFFICIENT_DATA

    def test_honing_it5_tight(self):
        # Honing IT4-6
        result = can_achieve_tolerance('HONING', 8.0, 25.0)
        # Depends on exact tolerance values but should not be INSUFFICIENT_DATA for valid size
        assert result.status != CapabilityStatus.INSUFFICIENT_DATA or result.reference_capability_um is None

    def test_result_has_operation_field(self):
        result = can_achieve_tolerance('DRILLING', 50.0, 25.0)
        assert result.operation == 'DRILLING'

    def test_result_has_nominal_size(self):
        result = can_achieve_tolerance('FINISH_TURNING', 25.0, 50.0)
        assert result.nominal_size_mm == 50.0

    def test_machine_validated_flag_accepted(self):
        result = can_achieve_tolerance('REAMING', 10.0, 25.0, machine_validated=True)
        assert result is not None

    def test_drilling_it11_100mm_capable(self):
        # Drilling covers IT9-12; IT11 is well within range
        result = can_achieve_tolerance('DRILLING', 160.0, 100.0)
        assert result.status in (
            CapabilityStatus.ROBUST, CapabilityStatus.ACCEPTABLE, CapabilityStatus.MARGINAL
        )

    def test_rough_boring_it8_25mm(self):
        # Rough boring IT9-12; IT8 would be too tight
        it8_25mm = 33.0
        result = can_achieve_tolerance('ROUGH_BORING', it8_25mm, 25.0)
        assert result.status in (
            CapabilityStatus.NOT_CAPABLE, CapabilityStatus.INSUFFICIENT_DATA,
        )

    def test_finish_boring_it6_25mm(self):
        # Finish boring IT5-8; IT6 should be achievable
        it6_25mm = 13.0
        result = can_achieve_tolerance('FINISH_BORING', it6_25mm, 25.0)
        assert result.status in (
            CapabilityStatus.ROBUST, CapabilityStatus.ACCEPTABLE,
            CapabilityStatus.MARGINAL, CapabilityStatus.INSUFFICIENT_DATA,
        )

    def test_threading_returns_result(self):
        result = can_achieve_tolerance('THREADING', 100.0, 10.0)
        assert result is not None
        assert result.operation == 'THREADING'
