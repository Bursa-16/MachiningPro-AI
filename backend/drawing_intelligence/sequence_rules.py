"""Process Sequence Rules for Drawing-to-Process Intelligence (EPIC_04 Phase 2).

Extends the existing SEQ-R001/R002 rules (planner.py) with drawing-aware
rules that enforce physically required operation precedence.

Rule IDs SEQ-R001/R002 are reserved for planner.py (process_planning module).
Drawing-intelligence rules start at SEQ-DR-001.

All rules are deterministic. LLM_REQUIRED_FOR_ROUTE_GENERATION=NO.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.domain.enums import FeatureType, OperationType

__all__ = [
    "SequenceRuleResult",
    "SequenceRuleSeverity",
    "SequenceRule",
    "DRAWING_SEQUENCE_RULES",
    "check_sequence",
    "insert_mandatory_predecessors",
]


class SequenceRuleSeverity(StrEnum):
    BLOCKING = "BLOCKING"     # Violating this makes the plan physically invalid
    ADVISORY = "ADVISORY"     # Best practice — violation noted but not rejected


@dataclass(frozen=True, slots=True)
class SequenceRule:
    """A precedence rule: predecessor must appear before successor."""

    rule_id: str
    predecessor_op: OperationType
    successor_op: OperationType
    feature_context: FeatureType | None  # None = applies to all contexts
    severity: SequenceRuleSeverity
    rationale: str

    def applies_to(self, feature_type: FeatureType) -> bool:
        return self.feature_context is None or self.feature_context == feature_type


@dataclass(frozen=True, slots=True)
class SequenceRuleResult:
    """Outcome of checking one sequence rule against a proposed operation list."""

    rule_id: str
    satisfied: bool
    severity: SequenceRuleSeverity
    message: str


# ---------------------------------------------------------------------------
# Drawing-intelligence sequence rules (SEQ-DR-xxx)
# ---------------------------------------------------------------------------

DRAWING_SEQUENCE_RULES: tuple[SequenceRule, ...] = (
    # Hole preparation chain
    SequenceRule(
        rule_id="SEQ-DR-001",
        predecessor_op=OperationType.DRILLING,
        successor_op=OperationType.REAMING,
        feature_context=FeatureType.HOLE,
        severity=SequenceRuleSeverity.BLOCKING,
        rationale="Reamer requires a pre-drilled hole; cannot ream from solid",
    ),
    SequenceRule(
        rule_id="SEQ-DR-002",
        predecessor_op=OperationType.DRILLING,
        successor_op=OperationType.TAPPING,
        feature_context=FeatureType.THREAD,
        severity=SequenceRuleSeverity.BLOCKING,
        rationale="Tap requires a pre-drilled clearance hole",
    ),
    SequenceRule(
        rule_id="SEQ-DR-003",
        predecessor_op=OperationType.DRILLING,
        successor_op=OperationType.BORING,
        feature_context=FeatureType.HOLE,
        severity=SequenceRuleSeverity.BLOCKING,
        rationale="Boring bar requires a pre-drilled hole to enter",
    ),
    SequenceRule(
        rule_id="SEQ-DR-004",
        predecessor_op=OperationType.BORING,
        successor_op=OperationType.HONING,
        feature_context=FeatureType.HOLE,
        severity=SequenceRuleSeverity.ADVISORY,
        rationale="Honing follows a finish-bored hole; direct honing from drill "
                  "leaves too much stock",
    ),
    SequenceRule(
        rule_id="SEQ-DR-005",
        predecessor_op=OperationType.TURNING,
        successor_op=OperationType.GRINDING,
        feature_context=FeatureType.CYLINDRICAL_SURFACE,
        severity=SequenceRuleSeverity.ADVISORY,
        rationale="Grinding requires turned pre-stock; also applies to hardened parts",
    ),
    SequenceRule(
        rule_id="SEQ-DR-006",
        predecessor_op=OperationType.MILLING,
        successor_op=OperationType.DEBURRING,
        feature_context=None,
        severity=SequenceRuleSeverity.ADVISORY,
        rationale="Deburring follows stock-removal operations",
    ),
    SequenceRule(
        rule_id="SEQ-DR-007",
        predecessor_op=OperationType.REAMING,
        successor_op=OperationType.HONING,
        feature_context=FeatureType.HOLE,
        severity=SequenceRuleSeverity.ADVISORY,
        rationale="Honing after reaming for ultra-fine bore finish (Ra < 0.4 µm)",
    ),
    SequenceRule(
        rule_id="SEQ-DR-008",
        predecessor_op=OperationType.FACING,
        successor_op=OperationType.TURNING,
        feature_context=None,
        severity=SequenceRuleSeverity.ADVISORY,
        rationale="Face the part before OD turning to establish datum face",
    ),
)


# ---------------------------------------------------------------------------
# Rule checking
# ---------------------------------------------------------------------------

def check_sequence(
    operations: list[OperationType],
    feature_type: FeatureType | None = None,
) -> list[SequenceRuleResult]:
    """Check a proposed operation sequence against all applicable rules.

    Returns results for every applicable rule, satisfied or not.
    """
    results: list[SequenceRuleResult] = []
    op_set = set(operations)

    for rule in DRAWING_SEQUENCE_RULES:
        # Only apply rules relevant to the feature context
        if feature_type is not None and not rule.applies_to(feature_type):
            continue
        # Only check when both operations appear in the proposed sequence
        if rule.predecessor_op not in op_set or rule.successor_op not in op_set:
            continue

        try:
            pred_idx = operations.index(rule.predecessor_op)
            succ_idx = operations.index(rule.successor_op)
        except ValueError:
            continue

        satisfied = pred_idx < succ_idx
        if satisfied:
            msg = (
                f"{rule.predecessor_op} correctly precedes {rule.successor_op}"
            )
        else:
            msg = (
                f"{rule.rule_id}: {rule.successor_op} must follow "
                f"{rule.predecessor_op} — {rule.rationale}"
            )

        results.append(SequenceRuleResult(
            rule_id=rule.rule_id,
            satisfied=satisfied,
            severity=rule.severity,
            message=msg,
        ))

    return results


def insert_mandatory_predecessors(
    operations: list[OperationType],
    feature_type: FeatureType | None = None,
) -> list[OperationType]:
    """Insert missing mandatory predecessors to satisfy BLOCKING rules.

    Only inserts when the predecessor is absent AND the successor is present.
    Does not reorder existing operations.
    Returns a new list; never mutates input.
    """
    result = list(operations)
    op_set = set(result)

    for rule in DRAWING_SEQUENCE_RULES:
        if rule.severity != SequenceRuleSeverity.BLOCKING:
            continue
        if feature_type is not None and not rule.applies_to(feature_type):
            continue

        pred = rule.predecessor_op
        succ = rule.successor_op

        if succ in op_set and pred not in op_set:
            # Insert predecessor before successor
            succ_idx = result.index(succ)
            result.insert(succ_idx, pred)
            op_set.add(pred)

    return result
