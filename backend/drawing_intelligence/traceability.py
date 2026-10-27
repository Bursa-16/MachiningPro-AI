"""Drawing-to-Process Traceability (EPIC_04 Phase 2 + 04B).

Maintains the chain: drawing dimension_id → feature_id → operation_step_id.

Phase 04B additions:
  - AdvancedTraceabilityEntry with datum_frame_fingerprint, modifier, confidence, ambiguity_ids
  - TraceabilityChain extended with gdt_entries

FABRICATED_DRAWING_REQUIREMENT=NO
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "TraceabilityEntry",
    "AdvancedTraceabilityEntry",
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
class AdvancedTraceabilityEntry:
    """GD&T-enriched traceability entry (Phase 04B)."""

    req_id: str
    feature_id: str
    step_id: str
    recognition_rule: str
    operation: str
    characteristic: str             # GdtCharacteristic.value
    modifier: str                   # GdtModifier.value
    datum_frame_fingerprint: str | None    # AdvancedDatumReferenceFrame.drf_fingerprint or None
    confidence: str                 # GdtConfidence.value
    ambiguity_ids: tuple[str, ...]  # GdtAmbiguity.ambiguity_id list


@dataclass(frozen=True, slots=True)
class TraceabilityChain:
    """Full traceability record for one source drawing."""

    source_id: str
    drawing_number: str | None
    revision: str | None
    entries: tuple[TraceabilityEntry, ...]
    gdt_entries: tuple[AdvancedTraceabilityEntry, ...] = ()

    def by_feature(self, feature_id: str) -> list[TraceabilityEntry]:
        return [e for e in self.entries if e.feature_id == feature_id]

    def by_step(self, step_id: str) -> list[TraceabilityEntry]:
        return [e for e in self.entries if e.step_id == step_id]

    def by_req(self, req_id: str) -> list[TraceabilityEntry]:
        return [e for e in self.entries if e.req_id == req_id]

    def gdt_by_feature(self, feature_id: str) -> list[AdvancedTraceabilityEntry]:
        return [e for e in self.gdt_entries if e.feature_id == feature_id]

    def gdt_by_req(self, req_id: str) -> list[AdvancedTraceabilityEntry]:
        return [e for e in self.gdt_entries if e.req_id == req_id]


class TraceabilityLedger:
    """Accumulates traceability entries during plan generation."""

    def __init__(self, source_id: str, drawing_number: str | None = None,
                 revision: str | None = None) -> None:
        self.source_id = source_id
        self.drawing_number = drawing_number
        self.revision = revision
        self._entries: list[TraceabilityEntry] = []
        self._gdt_entries: list[AdvancedTraceabilityEntry] = []

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

    def record_gdt(
        self,
        req_id: str,
        feature_id: str,
        step_id: str,
        recognition_rule: str,
        operation: str,
        characteristic: str,
        modifier: str,
        datum_frame_fingerprint: str | None,
        confidence: str,
        ambiguity_ids: tuple[str, ...] = (),
    ) -> None:
        self._gdt_entries.append(AdvancedTraceabilityEntry(
            req_id=req_id,
            feature_id=feature_id,
            step_id=step_id,
            recognition_rule=recognition_rule,
            operation=operation,
            characteristic=characteristic,
            modifier=modifier,
            datum_frame_fingerprint=datum_frame_fingerprint,
            confidence=confidence,
            ambiguity_ids=ambiguity_ids,
        ))

    def build(self) -> TraceabilityChain:
        return TraceabilityChain(
            source_id=self.source_id,
            drawing_number=self.drawing_number,
            revision=self.revision,
            entries=tuple(self._entries),
            gdt_entries=tuple(self._gdt_entries),
        )
