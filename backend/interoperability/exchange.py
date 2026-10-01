"""Canonical Exchange Document (CED) Layer (Stage 4D).

The CED wraps an ImportResult with higher-level exchange semantics:
a stable document reference, cross-session traceability, and a compact
summary suitable for display or downstream pipeline consumption.

The CED is the boundary object that passes between the interoperability
layer and MachineryPro domain stages (feature recognition, process
planning, etc.).  Domain stages should consume CanonicalExchangeDocument,
not raw CanonicalDocument or ImportResult.

Design
------
* Immutable frozen dataclass.
* Deterministic ID: derived from import_id, not random.
* No deep CER content embedded — the CED holds the CanonicalDocument
  reference and its entity_refs, not the geometry objects themselves.
* No manufacturing-feature classification here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from backend.domain.base import entity_as_dict, require_non_empty_str
from backend.domain.exceptions import ValidationError
from backend.interoperability.enums import CapabilityLevel, NormalizationStatus
from backend.interoperability.models import CanonicalDocument, CanonicalEntityRef
from backend.interoperability.orchestrator import (
    ImportResult,
    ImportStatus,
)

__all__ = [
    "ExchangeDocumentStatus",
    "CanonicalExchangeDocument",
    "build_exchange_document",
]


class ExchangeDocumentStatus(StrEnum):
    """Readiness of a CED for downstream consumption."""

    READY = "READY"
    """Document has content at Level 1+ and may be used downstream."""

    PARTIAL = "PARTIAL"
    """Document has partial content; downstream consumers must handle gaps."""

    UNAVAILABLE = "UNAVAILABLE"
    """Import failed; no usable content; document is a failure record only."""


@dataclass(frozen=True, slots=True)
class CanonicalExchangeDocument:
    """Boundary object passed from the interoperability layer to domain stages.

    Fields
    ------
    ced_id : str
        Stable deterministic ID derived from the import_id.
    exchange_status : ExchangeDocumentStatus
        Readiness for downstream consumption.
    source_id : str
        ID of the original engineering source.
    format_id : str
        Format of the imported document.
    adapter_id : str
        Adapter that produced this document.
    capability_level : CapabilityLevel
        Level reached during import.
    normalization_status : NormalizationStatus
        Normalization outcome.
    entity_count : int
        Number of canonical entity references in the document.
    entity_refs : tuple[CanonicalEntityRef, ...]
        Entity references, sorted by entity_id (deterministic).
    canonical_document : CanonicalDocument | None
        The underlying canonical document.
    is_lossless : bool
        True only when the fidelity report confirms lossless ingestion.
    summary : str
        One-line human-readable summary of the exchange document.
    metadata : Mapping[str, object]
        Additional structured metadata (adapter notes, etc.).
    """

    ced_id: str
    exchange_status: ExchangeDocumentStatus
    source_id: str
    format_id: str
    adapter_id: str
    capability_level: CapabilityLevel
    normalization_status: NormalizationStatus
    entity_count: int
    entity_refs: tuple[CanonicalEntityRef, ...]
    canonical_document: CanonicalDocument | None
    is_lossless: bool
    summary: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _s = object.__setattr__
        _s(self, "ced_id", require_non_empty_str(self.ced_id, "ced_id"))
        if not isinstance(self.exchange_status, ExchangeDocumentStatus):
            raise ValidationError("exchange_status must be an ExchangeDocumentStatus")
        _s(self, "source_id", require_non_empty_str(self.source_id, "source_id"))
        _s(self, "format_id", require_non_empty_str(self.format_id, "format_id"))
        _s(self, "adapter_id", require_non_empty_str(self.adapter_id, "adapter_id"))
        if not isinstance(self.capability_level, CapabilityLevel):
            raise ValidationError("capability_level must be a CapabilityLevel")
        if not isinstance(self.normalization_status, NormalizationStatus):
            raise ValidationError("normalization_status must be a NormalizationStatus")
        if (isinstance(self.entity_count, bool)
                or not isinstance(self.entity_count, int)
                or self.entity_count < 0):
            raise ValidationError("entity_count must be a non-negative integer")
        for ref in self.entity_refs:
            if not isinstance(ref, CanonicalEntityRef):
                raise ValidationError("entity_refs entries must be CanonicalEntityRef")
        if self.canonical_document is not None and not isinstance(
            self.canonical_document, CanonicalDocument
        ):
            raise ValidationError("canonical_document must be a CanonicalDocument or None")
        _s(self, "summary", require_non_empty_str(self.summary, "summary"))
        _s(self, "metadata", MappingProxyType(dict(self.metadata or {})))

    @property
    def is_ready(self) -> bool:
        return self.exchange_status is ExchangeDocumentStatus.READY

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


def build_exchange_document(result: ImportResult) -> CanonicalExchangeDocument:
    """Construct a CanonicalExchangeDocument from an ImportResult.

    This is the canonical transition from the interoperability layer to
    downstream domain consumers.

    Args:
        result: The ImportResult from CadImportOrchestrator.import_source().

    Returns:
        CanonicalExchangeDocument with deterministic ID and exchange status.
    """
    if not isinstance(result, ImportResult):
        raise ValidationError("result must be an ImportResult")

    ced_id = f"ced::{result.import_id}"

    doc = result.document
    prov = result.provenance

    # Exchange status
    if result.status in (ImportStatus.FAILED, ImportStatus.UNSUPPORTED):
        exchange_status = ExchangeDocumentStatus.UNAVAILABLE
    elif result.status is ImportStatus.PARTIAL or result.diagnostics.has_loss:
        exchange_status = ExchangeDocumentStatus.PARTIAL
    else:
        exchange_status = ExchangeDocumentStatus.READY

    # Core fields from document or provenance
    source_id = result.diagnostics.format_detection.detection_method  # fallback
    if prov:
        source_id = prov.source_id
    elif doc:
        source_id = doc.source.source_id

    format_id = "unknown"
    if prov:
        format_id = prov.format_id
    elif doc:
        format_id = doc.format_descriptor.format_id

    adapter_id = "unknown"
    if prov:
        adapter_id = prov.adapter_id
    elif result.diagnostics.selected_adapter_id:
        adapter_id = result.diagnostics.selected_adapter_id

    cap_level = result.capability.achieved_level
    norm_status = (
        doc.normalization_status if doc else NormalizationStatus.FAILED
    )

    # Entity refs sorted deterministically
    entity_refs: tuple[CanonicalEntityRef, ...] = ()
    if doc:
        entity_refs = doc.ordered_entity_refs

    is_lossless = doc.is_lossless if doc else False

    # Summary
    summary = (
        f"{exchange_status.value} | {format_id} | "
        f"{cap_level.value} | "
        f"{len(entity_refs)} entities | "
        f"{'lossless' if is_lossless else 'with-fidelity-events'}"
    )

    # Metadata
    meta: dict[str, object] = {
        "import_status": result.status.value,
        "adverse_fidelity_events": result.diagnostics.fidelity_adverse_count,
        "has_unsupported_content": result.diagnostics.has_unsupported_content,
        "has_loss": result.diagnostics.has_loss,
        "detection_confidence": result.diagnostics.format_detection.detection_confidence,
        "selection_reason": result.diagnostics.selection_reason,
    }

    return CanonicalExchangeDocument(
        ced_id=ced_id,
        exchange_status=exchange_status,
        source_id=source_id,
        format_id=format_id,
        adapter_id=adapter_id,
        capability_level=cap_level,
        normalization_status=norm_status,
        entity_count=len(entity_refs),
        entity_refs=entity_refs,
        canonical_document=doc,
        is_lossless=is_lossless,
        summary=summary,
        metadata=meta,
    )
