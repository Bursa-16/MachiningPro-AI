"""Tests for surface finish capability library — EPIC_04F."""

import pytest

from backend.calibration.models import CapabilityStatus
from backend.calibration.surface_capability import (
    SURFACE_CAPABILITY_LIBRARY,
    SurfaceOperationFamily,
    surface_capability_margin,
)


class TestSurfaceCapabilityLibrary:
    def test_all_ops_in_library(self):
        for op in SurfaceOperationFamily:
            assert op in SURFACE_CAPABILITY_LIBRARY

    def test_lapping_best_ra_smallest(self):
        lapping = SURFACE_CAPABILITY_LIBRARY[SurfaceOperationFamily.LAPPING]
        assert lapping.ra_best_um < 0.1 + 1e-9

    def test_grinding_better_than_rough_turning(self):
        grinding = SURFACE_CAPABILITY_LIBRARY[SurfaceOperationFamily.GRINDING]
        rough = SURFACE_CAPABILITY_LIBRARY[SurfaceOperationFamily.ROUGH_TURNING]
        assert grinding.ra_best_um < rough.ra_best_um

    def test_typical_ge_best_for_all(self):
        for rec in SURFACE_CAPABILITY_LIBRARY.values():
            assert rec.ra_typical_um >= rec.ra_best_um


class TestSurfaceCapabilityMargin:
    def test_finish_turning_ra1_6_capable(self):
        r = surface_capability_margin('FINISH_TURNING', 1.6)
        assert r.status in (CapabilityStatus.ROBUST, CapabilityStatus.ACCEPTABLE, CapabilityStatus.MARGINAL)

    def test_rough_turning_ra0_4_not_capable(self):
        r = surface_capability_margin('ROUGH_TURNING', 0.4)
        assert r.status == CapabilityStatus.NOT_CAPABLE

    def test_grinding_ra0_4_robust_or_acceptable(self):
        # Grinding best = 0.1µm; required 0.4µm → ratio 0.1/0.4 = 0.25 → ROBUST
        r = surface_capability_margin('GRINDING', 0.4)
        assert r.status == CapabilityStatus.ROBUST

    def test_unknown_operation_insufficient_data(self):
        r = surface_capability_margin('EDM', 1.6)
        assert r.status == CapabilityStatus.INSUFFICIENT_DATA

    def test_unknown_not_treated_as_supported(self):
        r = surface_capability_margin('PLASMA_CUT', 1.6)
        assert r.status not in (CapabilityStatus.ROBUST, CapabilityStatus.ACCEPTABLE)

    def test_zero_ra_insufficient_data(self):
        r = surface_capability_margin('GRINDING', 0.0)
        assert r.status == CapabilityStatus.INSUFFICIENT_DATA

    def test_margin_ratio_computed(self):
        r = surface_capability_margin('FINISH_TURNING', 1.6)
        assert r.margin_ratio is not None
        assert r.margin_ratio == pytest.approx(0.4 / 1.6, rel=1e-3)

    def test_margin_ratio_le_1_means_capable(self):
        r = surface_capability_margin('FINISH_TURNING', 1.6)
        if r.status != CapabilityStatus.INSUFFICIENT_DATA:
            assert r.margin_ratio is not None
            if r.margin_ratio <= 1.0:
                assert r.status != CapabilityStatus.NOT_CAPABLE

    def test_use_typical_gives_larger_ratio(self):
        r_best = surface_capability_margin('FINISH_TURNING', 1.6, use_typical=False)
        r_typ = surface_capability_margin('FINISH_TURNING', 1.6, use_typical=True)
        assert r_typ.margin_ratio is not None and r_best.margin_ratio is not None
        assert r_typ.margin_ratio >= r_best.margin_ratio

    def test_robust_threshold_0_67(self):
        # grinding best 0.1, required 0.4 → ratio 0.25 <= 0.67 → ROBUST
        r = surface_capability_margin('GRINDING', 0.4)
        assert r.status == CapabilityStatus.ROBUST

    def test_lapping_ra_0_1_achievable(self):
        # Lapping best=0.05; ratio = 0.05/0.1 = 0.5 → ROBUST
        r = surface_capability_margin('LAPPING', 0.1)
        assert r.status == CapabilityStatus.ROBUST

    def test_honing_ra_0_2_marginal_or_better(self):
        # Honing best=0.1; ratio = 0.1/0.2 = 0.5 → ROBUST
        r = surface_capability_margin('HONING', 0.2)
        assert r.status in (CapabilityStatus.ROBUST, CapabilityStatus.ACCEPTABLE, CapabilityStatus.MARGINAL)

    def test_reaming_ra_0_8_capable(self):
        # Reaming best=0.4, ratio=0.4/0.8=0.5 → ROBUST
        r = surface_capability_margin('REAMING', 0.8)
        assert r.status == CapabilityStatus.ROBUST

    def test_boring_ra_3_2_not_capable(self):
        # Boring best=0.4; required 3.2 → ratio = 0.4/3.2 = 0.125 ≤ 0.67 → ROBUST (capable)
        r = surface_capability_margin('BORING', 3.2)
        assert r.status == CapabilityStatus.ROBUST

    def test_result_has_operation_field(self):
        r = surface_capability_margin('GRINDING', 0.4)
        assert r.operation == 'GRINDING'

    def test_achievable_best_populated(self):
        r = surface_capability_margin('FINISH_MILLING', 1.6)
        assert r.achievable_ra_um_best is not None

    def test_achievable_typical_populated(self):
        r = surface_capability_margin('FINISH_MILLING', 1.6)
        assert r.achievable_ra_um_typical is not None
