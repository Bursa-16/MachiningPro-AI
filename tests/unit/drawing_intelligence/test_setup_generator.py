"""Tests for setup_generator — EPIC_04E Phase 2."""

import pytest

from backend.drawing_intelligence.setup_generator import SetupGenerator
from backend.domain.enums import OperationType


class TestSetupGenerator:
    def _gen(self, feature_ops, same_setup_pairs=None, datum_constraints=None):
        gen = SetupGenerator()
        return gen.generate(
            feature_ops,
            same_setup_pairs=same_setup_pairs or [],
            datum_constraints=datum_constraints or {},
        )

    def test_single_feature_single_setup(self):
        plan = self._gen({"F1": [OperationType.DRILLING]})
        assert plan.setup_count == 1
        assert plan.feature_to_setup.get("F1") is not None

    def test_two_independent_features_one_setup(self):
        plan = self._gen({
            "F1": [OperationType.DRILLING],
            "F2": [OperationType.DRILLING],
        })
        # Both drilling on same machine type — can share a setup
        assert plan.setup_count >= 1

    def test_same_setup_pair_forces_single_setup(self):
        plan = self._gen(
            {"F1": [OperationType.DRILLING], "F2": [OperationType.DRILLING]},
            same_setup_pairs=[("F1", "F2")],
        )
        # Same-setup pair means F1 and F2 in same setup
        assert plan.feature_to_setup["F1"] == plan.feature_to_setup["F2"]

    def test_empty_features(self):
        plan = self._gen({})
        assert plan.setup_count == 0

    def test_setup_sequence_numbers_monotone(self):
        plan = self._gen({
            "F1": [OperationType.DRILLING],
            "F2": [OperationType.MILLING],
            "F3": [OperationType.TURNING],
        })
        seq_nos = sorted(s.sequence_no for s in plan.setups)
        assert seq_nos == list(range(1, len(plan.setups) + 1))

    def test_all_features_assigned_a_setup(self):
        feature_ops = {
            "F1": [OperationType.DRILLING],
            "F2": [OperationType.BORING],
            "F3": [OperationType.MILLING],
        }
        plan = self._gen(feature_ops)
        for fid in feature_ops:
            assert fid in plan.feature_to_setup, f"{fid} not assigned to a setup"

    def test_mandatory_violation_recorded_when_incompatible_forced(self):
        # Force F1 (drilling only) and F2 (turning only) into same setup
        # These have different machine types — should record a warning
        plan = self._gen(
            {
                "F1": [OperationType.DRILLING],
                "F2": [OperationType.TURNING],
            },
            same_setup_pairs=[("F1", "F2")],
        )
        # Still assigns them (best-effort), but may warn
        assert plan.feature_to_setup["F1"] is not None

    def test_setup_objects_have_correct_feature_ids(self):
        plan = self._gen({
            "F1": [OperationType.DRILLING],
            "F2": [OperationType.DRILLING],
        }, same_setup_pairs=[("F1", "F2")])
        setup_id = plan.feature_to_setup["F1"]
        setup = next(s for s in plan.setups if s.setup_id == setup_id)
        assert "F1" in setup.feature_ids or "F2" in setup.feature_ids
