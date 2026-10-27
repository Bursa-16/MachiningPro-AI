# ruff: noqa: E501
"""Feature Precedence Graph (DAG) — EPIC_04E Phase 2.

Deterministic directed acyclic graph of operation dependencies.
No cycles, no stochastic ordering.

FEATURE_PRECEDENCE_GRAPH_IMPLEMENTED=YES
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from backend.domain.enums import OperationType

__all__ = [
    "PrecedenceEdgeType",
    "PrecedenceEdge",
    "PrecedenceNode",
    "OperationPrecedenceGraph",
    "build_precedence_graph",
    "DRAWING_SEQUENCE_RULES_EXT",
]


class PrecedenceEdgeType(StrEnum):
    BLOCKING = "BLOCKING"
    ADVISORY = "ADVISORY"


@dataclass(frozen=True, slots=True)
class PrecedenceEdge:
    """A directed dependency: *predecessor* must complete before *successor*."""

    predecessor_node_id: str
    successor_node_id: str
    edge_type: PrecedenceEdgeType
    rule_id: str
    rationale: str


@dataclass(frozen=True, slots=True)
class PrecedenceNode:
    """One operation node in the precedence graph."""

    node_id: str
    operation_type: OperationType
    sub_operation: str | None
    feature_id: str | None
    setup_id: str


@dataclass
class OperationPrecedenceGraph:
    """DAG of manufacturing operation dependencies.

    Edges encode MUST_PRECEDE relationships.
    FEATURE_PRECEDENCE_GRAPH_IMPLEMENTED=YES
    """

    nodes: dict[str, PrecedenceNode] = field(default_factory=dict)
    edges: list[PrecedenceEdge] = field(default_factory=list)

    def add_node(self, node: PrecedenceNode) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, edge: PrecedenceEdge) -> None:
        if edge.predecessor_node_id not in self.nodes:
            raise ValueError(f"Predecessor {edge.predecessor_node_id!r} not in graph")
        if edge.successor_node_id not in self.nodes:
            raise ValueError(f"Successor {edge.successor_node_id!r} not in graph")
        self.edges.append(edge)

    def predecessors_of(self, node_id: str) -> list[PrecedenceNode]:
        ids = {e.predecessor_node_id for e in self.edges if e.successor_node_id == node_id}
        return [self.nodes[i] for i in ids if i in self.nodes]

    def successors_of(self, node_id: str) -> list[PrecedenceNode]:
        ids = {e.successor_node_id for e in self.edges if e.predecessor_node_id == node_id}
        return [self.nodes[i] for i in ids if i in self.nodes]

    def topological_order(self) -> list[str]:
        """Return node_ids in valid execution order (Kahn's algorithm)."""
        in_degree: dict[str, int] = {n: 0 for n in self.nodes}
        for e in self.edges:
            in_degree[e.successor_node_id] += 1
        queue = sorted(n for n, d in in_degree.items() if d == 0)
        result: list[str] = []
        while queue:
            n = queue.pop(0)
            result.append(n)
            for e in self.edges:
                if e.predecessor_node_id == n:
                    in_degree[e.successor_node_id] -= 1
                    if in_degree[e.successor_node_id] == 0:
                        queue.append(e.successor_node_id)
                        queue.sort()
        return result

    def has_cycle(self) -> bool:
        return len(self.topological_order()) != len(self.nodes)

    def blocking_violations(self, proposed_order: list[str]) -> list[PrecedenceEdge]:
        """Return BLOCKING edges violated by *proposed_order*."""
        idx = {n: i for i, n in enumerate(proposed_order)}
        return [
            e for e in self.edges
            if e.edge_type is PrecedenceEdgeType.BLOCKING
            and e.predecessor_node_id in idx
            and e.successor_node_id in idx
            and idx[e.predecessor_node_id] > idx[e.successor_node_id]
        ]


# ---------------------------------------------------------------------------
# Extended drawing sequence rules (superset of sequence_rules.py)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SequenceRule:
    rule_id: str
    predecessor_op: OperationType
    successor_op: OperationType
    edge_type: PrecedenceEdgeType
    rationale: str


DRAWING_SEQUENCE_RULES_EXT: tuple[SequenceRule, ...] = (
    SequenceRule("SEQ-EXT-001", OperationType.DRILLING, OperationType.REAMING,      PrecedenceEdgeType.BLOCKING,  "Hole must be drilled before reaming"),
    SequenceRule("SEQ-EXT-002", OperationType.DRILLING, OperationType.TAPPING,      PrecedenceEdgeType.BLOCKING,  "Tap drill must precede tapping"),
    SequenceRule("SEQ-EXT-003", OperationType.DRILLING, OperationType.BORING,       PrecedenceEdgeType.BLOCKING,  "Pilot hole required before boring"),
    SequenceRule("SEQ-EXT-004", OperationType.BORING,   OperationType.HONING,       PrecedenceEdgeType.BLOCKING,  "Bore must be finish-bored before honing"),
    SequenceRule("SEQ-EXT-005", OperationType.DRILLING, OperationType.THREADING,    PrecedenceEdgeType.BLOCKING,  "Drill before thread milling"),
    SequenceRule("SEQ-EXT-006", OperationType.TURNING,  OperationType.GRINDING,     PrecedenceEdgeType.BLOCKING,  "OD must be turned before cylindrical grinding"),
    SequenceRule("SEQ-EXT-007", OperationType.MILLING,  OperationType.GRINDING,     PrecedenceEdgeType.BLOCKING,  "Surface must be milled before surface grinding"),
    SequenceRule("SEQ-EXT-008", OperationType.FACING,   OperationType.DRILLING,     PrecedenceEdgeType.ADVISORY,  "Face datum before drilling position-controlled holes"),
    SequenceRule("SEQ-EXT-009", OperationType.TURNING,  OperationType.THREADING,    PrecedenceEdgeType.BLOCKING,  "OD must be turned before single-point threading"),
    SequenceRule("SEQ-EXT-010", OperationType.GRINDING, OperationType.LAPPING,      PrecedenceEdgeType.BLOCKING,  "Grind before lapping"),
    SequenceRule("SEQ-EXT-011", OperationType.BORING,   OperationType.LAPPING,      PrecedenceEdgeType.BLOCKING,  "Bore before lapping"),
    SequenceRule("SEQ-EXT-012", OperationType.MILLING,  OperationType.DEBURRING,    PrecedenceEdgeType.ADVISORY,  "Deburring after milling"),
    SequenceRule("SEQ-EXT-013", OperationType.DRILLING, OperationType.DEBURRING,    PrecedenceEdgeType.ADVISORY,  "Deburring after drilling"),
)


def build_precedence_graph(
    operations: list[tuple[str, OperationType, str | None, str | None]],
) -> OperationPrecedenceGraph:
    """Build a precedence graph from a list of (node_id, op_type, sub_op, feature_id) tuples.

    Applies DRAWING_SEQUENCE_RULES_EXT to insert edges where both predecessor
    and successor operation types are present.

    setup_id defaults to 'S-0001' (caller should assign proper setup IDs).
    """
    graph = OperationPrecedenceGraph()
    for node_id, op_type, sub_op, feat_id in operations:
        graph.add_node(PrecedenceNode(
            node_id=node_id,
            operation_type=op_type,
            sub_operation=sub_op,
            feature_id=feat_id,
            setup_id="S-0001",
        ))

    # Apply sequence rules — same feature only (by feature_id)
    by_feature: dict[str | None, list[tuple[str, OperationType]]] = {}
    for node_id, op_type, _, feat_id in operations:
        by_feature.setdefault(feat_id, []).append((node_id, op_type))

    for rule in DRAWING_SEQUENCE_RULES_EXT:
        for _feat_id, ops in by_feature.items():
            preds = [(nid, op) for nid, op in ops if op == rule.predecessor_op]
            succs = [(nid, op) for nid, op in ops if op == rule.successor_op]
            for p_id, _ in preds:
                for s_id, _ in succs:
                    if p_id != s_id:
                        try:
                            graph.add_edge(PrecedenceEdge(
                                predecessor_node_id=p_id,
                                successor_node_id=s_id,
                                edge_type=rule.edge_type,
                                rule_id=rule.rule_id,
                                rationale=rule.rationale,
                            ))
                        except ValueError:
                            pass  # node not in graph — skip

    return graph
