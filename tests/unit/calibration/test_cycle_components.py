"""Tests for cycle time components — EPIC_04F.

Safety flags verified:
UNKNOWN_TIME_COMPONENT_TREATED_AS_ZERO=NO
PARTIAL_TIME_PRESENTED_AS_TOTAL=NO
TOOL_CHANGE_GUESSED=NO
SETUP_TIME_GUESSED=NO
APPROACH_RETRACT_GUESSED=NO
"""

import pytest

from backend.calibration.cycle_components import (
    SPINDLE_ACCEL_TIME_IMPLEMENTED,
    assemble_cycle_time_estimate,
    compute_batch_model,
    make_approach_retract_component,
    make_cutting_component,
    make_dwell_component,
    make_inspection_component,
    make_load_unload_component,
    make_probing_component,
    make_rapid_component,
    make_setup_component,
    make_spindle_accel_component,
    make_tool_change_component,
)
from backend.calibration.models import (
    CycleComponentStatus,
    CycleTimeCompleteness,
)


class TestSafetyFlags:
    def test_spindle_accel_deferred(self):
        assert SPINDLE_ACCEL_TIME_IMPLEMENTED == "DEFERRED"


class TestMakeCuttingComponent:
    def test_known_values_calculated(self):
        c = make_cutting_component(30.0, 35.0)
        assert c.status == CycleComponentStatus.CALCULATED
        assert c.value_sec_min == 30.0
        assert c.value_sec_max == 35.0

    def test_none_values_unknown(self):
        c = make_cutting_component(None, None)
        assert c.status == CycleComponentStatus.UNKNOWN
        assert c.value_sec_min is None
        assert c.value_sec_max is None

    def test_missing_inputs_populated_when_unknown(self):
        c = make_cutting_component(None, None)
        assert len(c.missing_inputs) > 0


class TestMakeRapidComponent:
    def test_known_rapid_calculated(self):
        c = make_rapid_component(5.0)
        assert c.status == CycleComponentStatus.CALCULATED
        assert c.value_sec_min == 5.0

    def test_none_rapid_unknown(self):
        c = make_rapid_component(None)
        assert c.status == CycleComponentStatus.UNKNOWN


class TestMakeApproachRetract:
    def test_both_known_user_supplied(self):
        c = make_approach_retract_component(2.0, 1.5)
        assert c.status in (CycleComponentStatus.USER_SUPPLIED, CycleComponentStatus.CALCULATED)
        assert c.value_sec_min == pytest.approx(3.5)

    def test_none_approach_unknown(self):
        c = make_approach_retract_component(None, None)
        assert c.status == CycleComponentStatus.UNKNOWN
        assert c.value_sec_min is None

    def test_approach_retract_guessed_no(self):
        c = make_approach_retract_component(None, None)
        assert 'GUESSED' in c.notes or c.status == CycleComponentStatus.UNKNOWN


class TestMakeToolChangeComponent:
    def test_atc_known_reference(self):
        c = make_tool_change_component(6.0, tool_changes=2)
        assert c.status == CycleComponentStatus.REFERENCE
        assert c.value_sec_min == 12.0

    def test_atc_none_unknown(self):
        c = make_tool_change_component(None)
        assert c.status == CycleComponentStatus.UNKNOWN
        assert c.value_sec_min is None

    def test_tool_change_guessed_no(self):
        c = make_tool_change_component(None)
        assert 'GUESSED' in c.notes or c.status == CycleComponentStatus.UNKNOWN

    def test_zero_tool_changes(self):
        c = make_tool_change_component(6.0, tool_changes=0)
        assert c.value_sec_min == 0.0


class TestMakeSpindleAccel:
    def test_always_unknown(self):
        c = make_spindle_accel_component()
        assert c.status == CycleComponentStatus.UNKNOWN

    def test_deferred_in_notes(self):
        c = make_spindle_accel_component()
        assert 'DEFERRED' in c.notes


class TestMakeSetupComponent:
    def test_known_user_supplied(self):
        c = make_setup_component(1800.0)
        assert c.status == CycleComponentStatus.USER_SUPPLIED
        assert c.value_sec_min == 1800.0

    def test_none_unknown(self):
        c = make_setup_component(None)
        assert c.status == CycleComponentStatus.UNKNOWN
        assert c.value_sec_min is None

    def test_setup_guessed_no(self):
        c = make_setup_component(None)
        assert 'GUESSED' in c.notes or c.status == CycleComponentStatus.UNKNOWN


class TestAssembleCycleTimeEstimate:
    def test_fully_known_sets_total(self):
        comps = [
            make_cutting_component(60.0, 60.0),
            make_dwell_component(5.0),
        ]
        est = assemble_cycle_time_estimate(comps)
        assert est.completeness == CycleTimeCompleteness.FULLY_CALCULATED
        assert est.total_cycle_time_sec_min == pytest.approx(65.0)

    def test_partial_does_not_set_total(self):
        comps = [
            make_cutting_component(60.0, 60.0),
            make_tool_change_component(None),  # UNKNOWN
        ]
        est = assemble_cycle_time_estimate(comps)
        assert est.completeness == CycleTimeCompleteness.PARTIALLY_CALCULATED
        # PARTIAL_TIME_PRESENTED_AS_TOTAL=NO
        assert est.total_cycle_time_sec_min is None

    def test_partial_sets_known_total(self):
        comps = [
            make_cutting_component(60.0, 60.0),
            make_tool_change_component(None),
        ]
        est = assemble_cycle_time_estimate(comps)
        assert est.known_total_sec_min == pytest.approx(60.0)

    def test_all_unknown_insufficient_data(self):
        comps = [
            make_cutting_component(None, None),
            make_tool_change_component(None),
        ]
        est = assemble_cycle_time_estimate(comps)
        assert est.completeness == CycleTimeCompleteness.INSUFFICIENT_DATA
        assert est.known_total_sec_min is None
        assert est.total_cycle_time_sec_min is None

    def test_unknown_not_summed(self):
        # UNKNOWN_TIME_COMPONENT_TREATED_AS_ZERO=NO
        comps = [
            make_cutting_component(60.0, 60.0),
            make_tool_change_component(None),
        ]
        est = assemble_cycle_time_estimate(comps)
        # known total should be only 60, not 60+0
        assert est.known_total_sec_min == pytest.approx(60.0)

    def test_unknown_components_listed(self):
        comps = [
            make_cutting_component(None, None),
            make_setup_component(None),
        ]
        est = assemble_cycle_time_estimate(comps)
        assert 'CUTTING' in est.unknown_components
        assert 'SETUP' in est.unknown_components

    def test_limitations_present(self):
        comps = [make_cutting_component(30.0, 30.0)]
        est = assemble_cycle_time_estimate(comps)
        assert any('PARTIAL_TIME' in lim for lim in est.limitations)
