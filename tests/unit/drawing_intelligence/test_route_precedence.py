"""Tests for route_precedence — EPIC_04E Phase 2."""

import pytest

from backend.drawing_intelligence.route_precedence import (
    DRAWING_SEQUENCE_RULES_EXT,
    OperationPrecedenceGraph,
    PrecedenceEdge,
    PrecedenceEdgeType,
    PrecedenceNode,
    build_precedence_graph,
)
from backend.domain.enums import OperationType


def _node(node_id, op_type, feature_id="F1"):
    return PrecedenceNode(
        node_id=node_id,
        operation_type=op_type,
        sub_operation=None,
        feature_id=feature_id,
        setup_id="S-0001",
    )


def _edge(pred, succ, edge_type=PrecedenceEdgeType.BLOCKING):
    return PrecedenceEdge(
        predecessor_node_id=pred,
        successor_node_id=succ,
        edge_type=edge_type,
        rule_id="TEST-001",
        rationale="test",
    )


class TestOperationPrecedenceGraph:
    def test_empty_graph(self):
        g = OperationPrecedenceGraph()
        assert g.topological_order() == []
        assert not g.has_cycle()

    def test_add_node_and_edge(self):
        g = OperationPrecedenceGraph()
        g.add_node(_node("A", OperationType.DRILLING))
        g.add_node(_node("B", OperationType.REAMING))
        g.add_edge(_edge("A", "B"))
        order = g.topological_order()
        assert order.index("A") < order.index("B")

    def test_topological_order_respects_dependencies(self):
        g = OperationPrecedenceGraph()
        for node_id, op in [("A", OperationType.DRILLING), ("B", OperationType.REAMING), ("C", OperationType.INSPECTION)]:
            g.add_node(_node(node_id, op))
        g.add_edge(_edge("A", "B"))
        g.add_edge(_edge("B", "C"))
        order = g.topological_order()
        assert order.index("A") < order.index("B")
        assert order.index("B") < order.index("C")

    def test_has_cycle_detects_cycle(self):
        g = OperationPrecedenceGraph()
        g.add_node(_node("A", OperationType.DRILLING))
        g.add_node(_node("B", OperationType.BORING))
        g.add_edge(_edge("A", "B"))
        g.add_edge(_edge("B", "A"))  # cycle
        assert g.has_cycle()

    def test_has_no_cycle_in_dag(self):
        g = OperationPrecedenceGraph()
        g.add_node(_node("A", OperationType.DRILLING))
        g.add_node(_node("B", OperationType.REAMING))
        g.add_edge(_edge("A", "B"))
        assert not g.has_cycle()

    def test_predecessors_of(self):
        g = OperationPrecedenceGraph()
        g.add_node(_node("A", OperationType.DRILLING))
        g.add_node(_node("B", OperationType.REAMING))
        g.add_edge(_edge("A", "B"))
        preds = g.predecessors_of("B")
        pred_ids = [p.node_id for p in preds]
        assert "A" in pred_ids
        preds_a = g.predecessors_of("A")
        assert "B" not in [p.node_id for p in preds_a]

    def test_blocking_violations_empty_when_correct_order(self):
        g = OperationPrecedenceGraph()
        g.add_node(_node("A", OperationType.DRILLING))
        g.add_node(_node("B", OperationType.REAMING))
        g.add_edge(_edge("A", "B"))
        violations = g.blocking_violations(["A", "B"])
        assert violations == []

    def test_blocking_violations_found(self):
        g = OperationPrecedenceGraph()
        g.add_node(_node("A", OperationType.DRILLING))
        g.add_node(_node("B", OperationType.REAMING))
        g.add_edge(_edge("A", "B"))
        violations = g.blocking_violations(["B", "A"])  # reversed
        assert len(violations) >= 1

    def test_unknown_node_raises_value_error(self):
        g = OperationPrecedenceGraph()
        g.add_node(_node("A", OperationType.DRILLING))
        with pytest.raises(ValueError):
            g.add_edge(_edge("A", "NONEXISTENT"))


class TestDrawingSequenceRulesExt:
    def test_13_rules_defined(self):
        assert len(DRAWING_SEQUENCE_RULES_EXT) == 13

    def test_seq_ext_001_drill_before_ream(self):
        rule = next(r for r in DRAWING_SEQUENCE_RULES_EXT if r.rule_id == "SEQ-EXT-001")
        assert rule.predecessor_op == OperationType.DRILLING
        assert rule.successor_op == OperationType.REAMING

    def test_all_rules_have_ids(self):
        ids = [r.rule_id for r in DRAWING_SEQUENCE_RULES_EXT]
        assert len(ids) == len(set(ids))

    def test_rules_start_seq_ext(self):
        for rule in DRAWING_SEQUENCE_RULES_EXT:
            assert rule.rule_id.startswith("SEQ-EXT-")

    def test_all_rules_have_rationale(self):
        for rule in DRAWING_SEQUENCE_RULES_EXT:
            assert rule.rationale


class TestBuildPrecedenceGraph:
    def test_build_single_feature(self):
        ops = [
            ("OP1", OperationType.DRILLING, None, "F1"),
            ("OP2", OperationType.REAMING, None, "F1"),
        ]
        g = build_precedence_graph(ops)
        order = g.topological_order()
        assert order.index("OP1") < order.index("OP2")

    def test_build_no_applicable_rules(self):
        ops = [
            ("OP1", OperationType.MILLING, None, "F1"),
            ("OP2", OperationType.INSPECTION, None, "F1"),
        ]
        g = build_precedence_graph(ops)
        assert not g.has_cycle()

    def test_build_multi_feature_independent(self):
        ops = [
            ("A1", OperationType.DRILLING, None, "F1"),
            ("A2", OperationType.REAMING, None, "F1"),
            ("B1", OperationType.DRILLING, None, "F2"),
            ("B2", OperationType.REAMING, None, "F2"),
        ]
        g = build_precedence_graph(ops)
        order = g.topological_order()
        assert order.index("A1") < order.index("A2")
        assert order.index("B1") < order.index("B2")

    def test_build_empty_ops(self):
        g = build_precedence_graph([])
        assert g.topological_order() == []
