"""Tests for control plan."""
import pytest
from backend.manufacturing_plan.characteristic import (
    ManufacturingCharacteristic, CharacteristicType, CharacteristicCriticality,
)
from backend.manufacturing_plan.control_plan import (
    ReactionPlan,
    ControlPlan,
    ControlPlanStatus,
    build_control_plan,
    _assign_reaction,
    _assign_responsibility,
)


def _char(cid="c1", criticality=CharacteristicCriticality.STANDARD,
          char_type=CharacteristicType.DIMENSION):
    return ManufacturingCharacteristic(
        characteristic_id=cid,
        source_requirement_id=None,
        feature_id="f1",
        char_type=char_type,
        label=f"char_{cid}",
        nominal_value=25.0,
        upper_limit=25.05,
        lower_limit=24.95,
        criticality=criticality,
    )


class TestReactionPlan:
    def test_all_values(self):
        vals = {e.value for e in ReactionPlan}
        assert "STOP_AND_REVIEW" in vals
        assert "SEGREGATE" in vals
        assert "REMEASURE" in vals

    def test_assign_key_char(self):
        c = _char(criticality=CharacteristicCriticality.KEY_CHARACTERISTIC)
        assert _assign_reaction(c.criticality) == ReactionPlan.STOP_AND_REVIEW

    def test_assign_critical(self):
        c = _char(criticality=CharacteristicCriticality.CRITICAL)
        assert _assign_reaction(c.criticality) == ReactionPlan.SEGREGATE

    def test_assign_standard(self):
        c = _char(criticality=CharacteristicCriticality.STANDARD)
        assert _assign_reaction(c.criticality) == ReactionPlan.REMEASURE

    def test_assign_important(self):
        c = _char(criticality=CharacteristicCriticality.IMPORTANT)
        assert _assign_reaction(c.criticality) == ReactionPlan.REMEASURE


class TestAssignResponsibility:
    def test_key_char_qc(self):
        assert _assign_responsibility(CharacteristicCriticality.KEY_CHARACTERISTIC) == "QC"

    def test_critical_qc(self):
        assert _assign_responsibility(CharacteristicCriticality.CRITICAL) == "QC"

    def test_important_operator(self):
        assert _assign_responsibility(CharacteristicCriticality.IMPORTANT) == "OPERATOR"

    def test_standard_operator(self):
        assert _assign_responsibility(CharacteristicCriticality.STANDARD) == "OPERATOR"


class TestBuildControlPlan:
    def test_empty_chars(self):
        cp = build_control_plan("mp1", [], [], "DWG-001", "A")
        assert isinstance(cp, ControlPlan)
        assert cp.rows == []

    def test_autonomous_nonconformance_false(self):
        cp = build_control_plan("mp1", [], [])
        assert cp.AUTONOMOUS_NONCONFORMANCE_DISPOSITION is False

    def test_draft_status(self):
        cp = build_control_plan("mp1", [], [])
        assert cp.status == ControlPlanStatus.DRAFT

    def test_one_char_one_row(self):
        chars = [_char("c1")]
        cp = build_control_plan("mp1", chars, [])
        assert len(cp.rows) == 1

    def test_key_char_row_stop_and_review(self):
        chars = [_char("c1", criticality=CharacteristicCriticality.KEY_CHARACTERISTIC)]
        cp = build_control_plan("mp1", chars, [])
        assert cp.rows[0].reaction_plan == ReactionPlan.STOP_AND_REVIEW

    def test_critical_char_row_segregate(self):
        chars = [_char("c1", criticality=CharacteristicCriticality.CRITICAL)]
        cp = build_control_plan("mp1", chars, [])
        assert cp.rows[0].reaction_plan == ReactionPlan.SEGREGATE

    def test_key_char_qc_responsibility(self):
        chars = [_char("c1", criticality=CharacteristicCriticality.KEY_CHARACTERISTIC)]
        cp = build_control_plan("mp1", chars, [])
        assert cp.rows[0].responsibility == "QC"

    def test_disclaimer_set(self):
        cp = build_control_plan("mp1", [], [])
        assert cp.disclaimer != ""

    def test_drawing_number_set(self):
        cp = build_control_plan("mp1", [], [], drawing_number="DWG-999")
        assert cp.drawing_number == "DWG-999"
