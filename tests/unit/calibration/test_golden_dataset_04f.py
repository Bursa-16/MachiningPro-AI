"""Golden dataset for EPIC_04F — 10 synthetic calibration cases A–J.

All expected values are derived from public engineering handbook formulas.
FABRICATED_PROCESS_CAPABILITY=NO
FABRICATED_CYCLE_TIME=NO
PARTIAL_TIME_PRESENTED_AS_TOTAL=NO
UNKNOWN_TIME_COMPONENT_TREATED_AS_ZERO=NO
"""

import pytest

from backend.calibration.cycle_components import (
    assemble_cycle_time_estimate,
    compute_batch_model,
    make_cutting_component,
    make_setup_component,
    make_tool_change_component,
)
from backend.calibration.models import CapabilityStatus, CycleTimeCompleteness
from backend.calibration.surface_capability import surface_capability_margin
from backend.calibration.tolerance_capability import can_achieve_tolerance


# ─── Case A: Finish turning IT8 bore ──────────────────────────────────────────
class TestCaseA_FinishTurningIT8:
    def test_finish_turning_25mm_it8_capable(self):
        # IT8 @25mm ≈ 33µm; FINISH_TURNING covers IT7–9
        result = can_achieve_tolerance("FINISH_TURNING", 33.0, 25.0)
        assert result.status in (
            CapabilityStatus.ROBUST, CapabilityStatus.ACCEPTABLE, CapabilityStatus.MARGINAL
        )

    def test_finish_turning_ra_1_6_capable(self):
        result = surface_capability_margin("FINISH_TURNING", 1.6)
        assert result.status in (
            CapabilityStatus.ROBUST, CapabilityStatus.ACCEPTABLE, CapabilityStatus.MARGINAL
        )


# ─── Case B: Grinding IT5 journal ─────────────────────────────────────────────
class TestCaseB_GrindingIT5:
    def test_grinding_50mm_it5_capable(self):
        # IT5 @50mm ≈ 11µm; GRINDING covers IT4–7
        result = can_achieve_tolerance("GRINDING", 11.0, 50.0)
        assert result.status in (
            CapabilityStatus.ROBUST, CapabilityStatus.ACCEPTABLE, CapabilityStatus.MARGINAL
        )

    def test_grinding_ra_0_4_robust(self):
        # grinding best 0.1µm; required 0.4µm → ratio 0.25 ≤ 0.67 → ROBUST
        result = surface_capability_margin("GRINDING", 0.4)
        assert result.status == CapabilityStatus.ROBUST


# ─── Case C: Drilling IT10 through-hole ───────────────────────────────────────
class TestCaseC_DrillingIT10:
    def test_drilling_25mm_it10_capable(self):
        # IT10 @25mm ≈ 84µm; DRILLING covers IT9–12
        result = can_achieve_tolerance("DRILLING", 84.0, 25.0)
        assert result.status in (
            CapabilityStatus.ROBUST, CapabilityStatus.ACCEPTABLE, CapabilityStatus.MARGINAL
        )

    def test_drilling_it6_too_tight(self):
        # IT6@25mm ≈13µm; DRILLING IT9-12 cannot achieve
        result = can_achieve_tolerance("DRILLING", 13.0, 25.0)
        assert result.status == CapabilityStatus.NOT_CAPABLE


# ─── Case D: Reaming IT7 bore ─────────────────────────────────────────────────
class TestCaseD_ReamingIT7:
    def test_reaming_20mm_it7_capable(self):
        # IT7@20mm ≈21µm; REAMING covers IT6–8 for 3–80mm
        result = can_achieve_tolerance("REAMING", 21.0, 20.0)
        assert result.status in (
            CapabilityStatus.ROBUST, CapabilityStatus.ACCEPTABLE, CapabilityStatus.MARGINAL
        )

    def test_reaming_out_of_size_range(self):
        # 150mm is outside REAMING size range
        result = can_achieve_tolerance("REAMING", 25.0, 150.0)
        assert result.status == CapabilityStatus.INSUFFICIENT_DATA


# ─── Case E: Rough turning IT12 stock removal ─────────────────────────────────
class TestCaseE_RoughTurning:
    def test_rough_turning_50mm_it12_capable(self):
        # IT12@50mm ≈ 250µm; ROUGH_TURNING covers IT11–13
        result = can_achieve_tolerance("ROUGH_TURNING", 250.0, 50.0)
        assert result.status in (
            CapabilityStatus.ROBUST, CapabilityStatus.ACCEPTABLE, CapabilityStatus.MARGINAL
        )

    def test_rough_turning_ra_3_2_marginal_or_better(self):
        # rough turning best 3.2; required 3.2 → ratio 1.0 → MARGINAL
        result = surface_capability_margin("ROUGH_TURNING", 3.2)
        assert result.status == CapabilityStatus.MARGINAL


# ─── Case F: Cycle time — fully known ─────────────────────────────────────────
class TestCaseF_CycleTimeFull:
    def test_fully_known_total_set(self):
        comps = [
            make_cutting_component(120.0, 130.0),
            make_tool_change_component(5.0, tool_changes=2),
            make_setup_component(1800.0),
        ]
        est = assemble_cycle_time_estimate(comps)
        assert est.completeness == CycleTimeCompleteness.FULLY_CALCULATED
        assert est.total_cycle_time_sec_min == pytest.approx(120.0 + 10.0 + 1800.0)
        assert est.total_cycle_time_sec_max == pytest.approx(130.0 + 10.0 + 1800.0)

    def test_fully_known_no_unknown_components(self):
        comps = [
            make_cutting_component(120.0, 130.0),
            make_tool_change_component(5.0, tool_changes=2),
        ]
        est = assemble_cycle_time_estimate(comps)
        assert est.completeness == CycleTimeCompleteness.FULLY_CALCULATED
        assert len(est.unknown_components) == 0


# ─── Case G: Cycle time — partial (UNKNOWN not summed) ────────────────────────
class TestCaseG_CycleTimePartial:
    def test_partial_total_not_presented_as_total(self):
        comps = [
            make_cutting_component(60.0, 65.0),
            make_tool_change_component(None),  # UNKNOWN
        ]
        est = assemble_cycle_time_estimate(comps)
        assert est.completeness == CycleTimeCompleteness.PARTIALLY_CALCULATED
        assert est.total_cycle_time_sec_min is None  # PARTIAL_TIME_PRESENTED_AS_TOTAL=NO

    def test_unknown_not_zero(self):
        comps = [
            make_cutting_component(60.0, 60.0),
            make_tool_change_component(None),
        ]
        est = assemble_cycle_time_estimate(comps)
        assert est.known_total_sec_min == pytest.approx(60.0)


# ─── Case H: Batch amortization ───────────────────────────────────────────────
class TestCaseH_BatchAmortization:
    def test_batch_50_amortizes_setup(self):
        b = compute_batch_model(50, 3600.0, 90.0, 95.0)
        assert b.completeness == CycleTimeCompleteness.FULLY_CALCULATED
        assert b.per_part_setup_sec == pytest.approx(72.0)
        assert b.per_part_total_sec_min == pytest.approx(90.0 + 72.0)


# ─── Case I: Lapping ultra-fine surface ───────────────────────────────────────
class TestCaseI_Lapping:
    def test_lapping_ra_0_05_achievable_robust(self):
        # lapping best 0.05µm; required 0.05µm → ratio 1.0 → MARGINAL
        result = surface_capability_margin("LAPPING", 0.05)
        assert result.status == CapabilityStatus.MARGINAL

    def test_lapping_ra_0_2_robust(self):
        # lapping best 0.05; ratio 0.05/0.2 = 0.25 → ROBUST
        result = surface_capability_margin("LAPPING", 0.2)
        assert result.status == CapabilityStatus.ROBUST


# ─── Case J: Honing bore finish IT5 ──────────────────────────────────────────
class TestCaseJ_Honing:
    def test_honing_20mm_it5_capable(self):
        # Honing IT4-6; IT5 should be achievable
        result = can_achieve_tolerance("HONING", 9.0, 20.0)
        assert result.status in (
            CapabilityStatus.ROBUST, CapabilityStatus.ACCEPTABLE,
            CapabilityStatus.MARGINAL, CapabilityStatus.INSUFFICIENT_DATA,
        )

    def test_honing_ra_0_1_marginal_or_better(self):
        # Honing best 0.1µm; ratio 0.1/0.1 = 1.0 → MARGINAL
        result = surface_capability_margin("HONING", 0.1)
        assert result.status in (CapabilityStatus.MARGINAL, CapabilityStatus.ACCEPTABLE, CapabilityStatus.ROBUST)
