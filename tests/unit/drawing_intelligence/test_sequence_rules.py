"""Tests for drawing_intelligence.sequence_rules (EPIC_04 Phase 2)."""

import pytest

from backend.domain.enums import FeatureType, OperationType
from backend.drawing_intelligence.sequence_rules import (
    DRAWING_SEQUENCE_RULES,
    SequenceRuleSeverity,
    check_sequence,
    insert_mandatory_predecessors,
)


class TestSequenceRuleDefinitions:
    def test_drill_before_ream_defined(self):
        rule = next(
            (r for r in DRAWING_SEQUENCE_RULES if r.rule_id == "SEQ-DR-001"),
            None,
        )
        assert rule is not None
        assert rule.predecessor_op == OperationType.DRILLING
        assert rule.successor_op == OperationType.REAMING
        assert rule.severity == SequenceRuleSeverity.BLOCKING

    def test_drill_before_tap_defined(self):
        rule = next(
            (r for r in DRAWING_SEQUENCE_RULES if r.rule_id == "SEQ-DR-002"),
            None,
        )
        assert rule is not None
        assert rule.predecessor_op == OperationType.DRILLING
        assert rule.successor_op == OperationType.TAPPING

    def test_all_rules_have_rationale(self):
        for rule in DRAWING_SEQUENCE_RULES:
            assert rule.rationale.strip(), f"{rule.rule_id} has empty rationale"

    def test_rule_count_at_least_8(self):
        assert len(DRAWING_SEQUENCE_RULES) >= 8


class TestCheckSequence:
    def test_correct_drill_ream_order(self):
        ops = [OperationType.DRILLING, OperationType.REAMING]
        results = check_sequence(ops, FeatureType.HOLE)
        seqdr001 = next((r for r in results if r.rule_id == "SEQ-DR-001"), None)
        assert seqdr001 is not None
        assert seqdr001.satisfied

    def test_wrong_ream_drill_order(self):
        ops = [OperationType.REAMING, OperationType.DRILLING]
        results = check_sequence(ops, FeatureType.HOLE)
        seqdr001 = next((r for r in results if r.rule_id == "SEQ-DR-001"), None)
        assert seqdr001 is not None
        assert not seqdr001.satisfied
        assert seqdr001.severity == SequenceRuleSeverity.BLOCKING

    def test_correct_drill_tap_order(self):
        ops = [OperationType.DRILLING, OperationType.TAPPING]
        results = check_sequence(ops, FeatureType.THREAD)
        seqdr002 = next((r for r in results if r.rule_id == "SEQ-DR-002"), None)
        assert seqdr002 is not None
        assert seqdr002.satisfied

    def test_ops_not_in_sequence_not_checked(self):
        ops = [OperationType.MILLING]  # no drilling/reaming
        results = check_sequence(ops, FeatureType.HOLE)
        # No rules triggered — result is empty
        assert results == []

    def test_no_feature_type_filter(self):
        ops = [OperationType.DRILLING, OperationType.TAPPING]
        results = check_sequence(ops)  # no feature_type
        assert any(r.rule_id == "SEQ-DR-002" for r in results)


class TestInsertMandatoryPredecessors:
    def test_insert_drill_before_ream(self):
        ops = [OperationType.REAMING]  # missing drill
        result = insert_mandatory_predecessors(ops, FeatureType.HOLE)
        assert OperationType.DRILLING in result
        assert result.index(OperationType.DRILLING) < result.index(OperationType.REAMING)

    def test_insert_drill_before_tap(self):
        ops = [OperationType.TAPPING]
        result = insert_mandatory_predecessors(ops, FeatureType.THREAD)
        assert OperationType.DRILLING in result
        assert result.index(OperationType.DRILLING) < result.index(OperationType.TAPPING)

    def test_no_insert_when_predecessor_present(self):
        ops = [OperationType.DRILLING, OperationType.REAMING]
        result = insert_mandatory_predecessors(ops, FeatureType.HOLE)
        assert result == ops

    def test_does_not_mutate_input(self):
        original = [OperationType.REAMING]
        _ = insert_mandatory_predecessors(original, FeatureType.HOLE)
        assert original == [OperationType.REAMING]  # not mutated

    def test_empty_sequence_unchanged(self):
        result = insert_mandatory_predecessors([], FeatureType.HOLE)
        assert result == []

    def test_advisory_rules_not_inserted(self):
        # SEQ-DR-004 (boring before honing) is ADVISORY — should NOT be auto-inserted
        ops = [OperationType.HONING]
        result = insert_mandatory_predecessors(ops, FeatureType.HOLE)
        # Boring should not be inserted since it's advisory
        assert OperationType.BORING not in result
