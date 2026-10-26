"""Drawing-to-Process Traceability (EPIC_04 Phase 2).

Maintains the chain: drawing dimension_id → feature_id → operation_step_id.

This module records the provenance trail so that any operation step in a
generated plan can be traced back to the source drawing requirement that
mandated it.

FABRICATED_DRAWING_REQUIREMENT=NO
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "TraceabilityEntry",
    "TraceabilityChain",
    "TraceabilityLedger",
]


@dataclass(frozen=True, slots=True)
class TraceabilityEntry:
    """One link in the chain: requirement → feature → step."""

    req_id: str             # DimensionalRequirement.req_id etc.
    feature_id: str         # Feature.feature_id
    step_id: str            # Generated step_id in the plan
    recognition_rule: str   # Which rule recognised the feature (R-FR-xxx)
    operation: str          # OperationType value


@dataclass(frozen=True, slots=True)
class TraceabilityChain:
    """Full traceability record for one source drawing."""

    source_id: str
    drawing_number: str | None
    revision: str | None
    entries: tuple[TraceabilityEntry, ...]

    def by_feature(self, feature_id: str) -> list[TraceabilityEntry]:
        return [e for e in self.entries if e.feature_id == feature_id]

    def by_step(self, step_id: str) -> list[TraceabilityEntry]:
        return [e for e in self.entries if e.step_id == step_id]

    def by_req(self, req_id: str) -> list[TraceabilityEntry]:
        return [e for e in self.entries if e.req_id == req_id]


class TraceabilityLedger:
    """Accumulates traceability entries during plan generation."""

    def __init__(self, source_id: str, drawing_number: str | None = None,
                 revision: str | None = None) -> None:
        self.source_id = source_id
        self.drawing_number = drawing_number
        self.revision = revision
        self._entries: list[TraceabilityEntry] = []

    def record(
        self,
        req_id: str,
        feature_id: str,
        step_id: str,
        recognition_rule: str,
        operation: str,
    ) -> None:
        self._entries.append(TraceabilityEntry(
            req_id=req_id,
            feature_id=feature_id,
            step_id=step_id,
            recognition_rule=recognition_rule,
            operation=operation,
        ))

    def build(self) -> TraceabilityChain:
        return TraceabilityChain(
            source_id=self.source_id,
            drawing_number=self.drawing_number,
            revision=self.revision,
            entries=tuple(self._entries),
        )
