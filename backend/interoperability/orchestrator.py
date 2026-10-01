"""CAD Import Orchestration Layer (Stage 4D).

Provides a deterministic orchestration pipeline that composes the Stage 4A
adapter contracts, Stage 4C format adapters, and Stage 4A canonical envelope
into a single, traceable import workflow.

Pipeline
--------
::

    CAD source (EngineeringSource)
        │
        ▼
    format detection (ContentSniffer + extension hints)
        │
        ▼
    adapter registry lookup (find_by_format → candidates)
        │
        ▼
    adapter selection (explicit caller choice or first-ordered)
        │
        ▼
    adapter execution (adapter.ingest)
        │
        ▼
    ImportResult
        ├─ CanonicalDocument
        ├─ ImportDiagnostics
        ├─ CapabilityRecord
        └─ ImportProvenance

Design principles
-----------------
* Deterministic — no random IDs (IDs are derived from source_id + adapter_id).
  No current timestamps embedded in IDs.
* Fail-closed — an unsupported format or adapter error always produces a
  documented ImportResult with status FAILED, not a raised exception
  at orchestration level.
* No fabrication — the orchestrator never invents geometry, topology,
  or capability claims. It propagates exactly what the adapter reports.
* Vendor-neutral — no format-specific logic outside the adapters.
* Optional dependencies remain optional — if no adapter can handle a source,
  the orchestrator returns UNSUPPORTED, not an error.

Non-goals
---------
* No feature recognition (Stage 4D+).
* No manufacturing-domain objects (Feature, Tool, etc.).
* No automatic best-adapter ranking — if the caller does not specify an
  adapter_id, the orchestrator selects the first alphabetically-ordered
  capable adapter and records the selection decision in diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from backend.domain.base import (
    Provenance,
    entity_as_dict,
    optional_non_empty_str,
    require_non_empty_str,
)
from backend.domain.enums import ProvenanceType
from backend.domain.exceptions import ValidationError
from backend.interoperability.adapter import FormatAdapter
from backend.interoperability.adapters._base import ContentSniffer
from backend.interoperability.adapters.registry_helpers import (
    build_default_adapter_registry,
)
from backend.interoperability.enums import (
    CapabilityLevel,
    NormalizationStatus,
)
from backend.interoperability.models import (
    CanonicalDocument,
    EngineeringSource,
    FidelityClass,
    FormatDescriptor,
)
from backend.interoperability.registry import AdapterRegistry

__all__ = [
    "CadImportOrchestrator",
    "CapabilityRecord",
    "FormatDetectionResult",
    "ImportDiagnostics",
    "ImportProvenance",
    "ImportResult",
    "ImportStatus",
    "detect_format",
]

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

class ImportStatus(StrEnum):
    """Overall outcome of an orchestrated import."""

    SUCCESS = "SUCCESS"
    """Adapter reached at least Level 1 (parsed) without errors."""

    PARTIAL = "PARTIAL"
    """Import completed but with fidelity loss or partial normalization."""

    UNSUPPORTED = "UNSUPPORTED"
    """No registered adapter could handle this source."""

    FAILED = "FAILED"
    """Adapter reported a fatal error (malformed input, missing content, etc.)."""

    DEGRADED = "DEGRADED"
    """Import succeeded at a lower capability level than requested due to
    missing optional dependencies or unsupported content."""


# ---------------------------------------------------------------------------
# Format detection result
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class FormatDetectionResult:
    """Result of format identification for an engineering source.

    Detection is heuristic and non-authoritative.  The adapter is the
    authoritative source of format identity (via ``can_handle``).

    Fields
    ------
    detected_format_id : str | None
        Best-guess format ID, or None when unrecognised.
    detection_confidence : str
        ``"HIGH"`` — content magic bytes matched;
        ``"MEDIUM"`` — file extension matched only;
        ``"LOW"`` — heuristic guess with uncertainty;
        ``"NONE"`` — format could not be determined.
    detection_method : str
        Human-readable description of how detection was performed.
    format_family_hint : str | None
        Broad family hint when format_id is uncertain (e.g. ``"STEP-GENERIC"``).
    """

    detected_format_id: str | None
    detection_confidence: str
    detection_method: str
    format_family_hint: str | None = None

    def __post_init__(self) -> None:
        _s = object.__setattr__
        if self.detected_format_id is not None:
            _s(self, "detected_format_id",
               require_non_empty_str(self.detected_format_id, "detected_format_id"))
        _s(self, "detection_confidence",
           require_non_empty_str(self.detection_confidence, "detection_confidence"))
        _s(self, "detection_method",
           require_non_empty_str(self.detection_method, "detection_method"))
        _s(self, "format_family_hint",
           optional_non_empty_str(self.format_family_hint, "format_family_hint"))


# ---------------------------------------------------------------------------
# Capability record
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CapabilityRecord:
    """Records the capability level achieved during an import.

    Fields
    ------
    achieved_level : CapabilityLevel
        The capability level the adapter actually reached.
    requested_level : CapabilityLevel | None
        The level requested by the caller (None = no explicit request).
    was_degraded : bool
        True when achieved_level < requested_level.
    degradation_reason : str | None
        Human-readable explanation of why degradation occurred.
    optional_dependency_absent : bool
        True when degradation was caused by an absent optional dependency.
    optional_dependency_name : str | None
        Name of the absent dependency when applicable.
    """

    achieved_level: CapabilityLevel
    requested_level: CapabilityLevel | None = None
    was_degraded: bool = False
    degradation_reason: str | None = None
    optional_dependency_absent: bool = False
    optional_dependency_name: str | None = None

    def __post_init__(self) -> None:
        _s = object.__setattr__
        if not isinstance(self.achieved_level, CapabilityLevel):
            raise ValidationError("achieved_level must be a CapabilityLevel")
        if self.requested_level is not None and not isinstance(
            self.requested_level, CapabilityLevel
        ):
            raise ValidationError("requested_level must be a CapabilityLevel or None")
        _s(self, "degradation_reason",
           optional_non_empty_str(self.degradation_reason, "degradation_reason"))
        _s(self, "optional_dependency_name",
           optional_non_empty_str(
               self.optional_dependency_name, "optional_dependency_name"))

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Import diagnostics
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ImportDiagnostics:
    """Structured diagnostics for an import pipeline run.

    Fields
    ------
    format_detection : FormatDetectionResult
        Result of the format-detection step.
    adapter_candidates : tuple[str, ...]
        adapter_id values of all adapters found for this format (sorted).
    selected_adapter_id : str | None
        The adapter that was actually used.
    selection_reason : str
        Why this adapter was selected (explicit, first-ordered, etc.).
    fidelity_adverse_count : int
        Number of adverse fidelity events in the import result.
    has_unsupported_content : bool
        True when any UNSUPPORTED fidelity event was recorded.
    has_loss : bool
        True when any LOST fidelity event was recorded.
    notes : tuple[str, ...]
        Additional diagnostic notes from the orchestrator.
    """

    format_detection: FormatDetectionResult
    adapter_candidates: tuple[str, ...]
    selected_adapter_id: str | None
    selection_reason: str
    fidelity_adverse_count: int
    has_unsupported_content: bool
    has_loss: bool
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _s = object.__setattr__
        if not isinstance(self.format_detection, FormatDetectionResult):
            raise ValidationError("format_detection must be a FormatDetectionResult")
        _s(self, "selection_reason",
           require_non_empty_str(self.selection_reason, "selection_reason"))
        _s(self, "selected_adapter_id",
           optional_non_empty_str(self.selected_adapter_id, "selected_adapter_id"))

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Import provenance
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ImportProvenance:
    """Traceability record for an orchestrated import.

    Links the import result back to the source identity and the adapter
    that produced it, in a form compatible with MachineryPro domain
    Provenance.

    Fields
    ------
    source_id : str
        The source that was imported.
    adapter_id : str
        The adapter that performed the import.
    adapter_version : str
        Adapter version at import time.
    format_id : str
        Format of the source (as determined by the adapter).
    capability_level : CapabilityLevel
        Capability level reached.
    normalization_status : NormalizationStatus
        Outcome of normalization.
    domain_provenance : Provenance
        MachineryPro Provenance for integration with domain models.
    notes : str | None
    """

    source_id: str
    adapter_id: str
    adapter_version: str
    format_id: str
    capability_level: CapabilityLevel
    normalization_status: NormalizationStatus
    domain_provenance: Provenance
    notes: str | None = None

    def __post_init__(self) -> None:
        _s = object.__setattr__
        _s(self, "source_id", require_non_empty_str(self.source_id, "source_id"))
        _s(self, "adapter_id", require_non_empty_str(self.adapter_id, "adapter_id"))
        _s(self, "adapter_version",
           require_non_empty_str(self.adapter_version, "adapter_version"))
        _s(self, "format_id", require_non_empty_str(self.format_id, "format_id"))
        if not isinstance(self.capability_level, CapabilityLevel):
            raise ValidationError("capability_level must be a CapabilityLevel")
        if not isinstance(self.normalization_status, NormalizationStatus):
            raise ValidationError("normalization_status must be a NormalizationStatus")
        if not isinstance(self.domain_provenance, Provenance):
            raise ValidationError("domain_provenance must be a Provenance")
        _s(self, "notes", optional_non_empty_str(self.notes, "notes"))

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Import result
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ImportResult:
    """Complete result of an orchestrated CAD import.

    The orchestrator always returns an ImportResult — even on failure.
    Callers must check ``status`` before consuming ``document``.

    Fields
    ------
    import_id : str
        Stable identifier for this import run.
        Derived deterministically as ``{source_id}::{adapter_id}``.
    status : ImportStatus
        Overall import outcome.
    document : CanonicalDocument | None
        Canonical document, or None when the import failed before producing one.
    diagnostics : ImportDiagnostics
        Structured diagnostics from the orchestration pipeline.
    capability : CapabilityRecord
        Capability level achieved and any degradation details.
    provenance : ImportProvenance | None
        Traceability record (None when no adapter was selected).
    error_message : str | None
        Human-readable error description when status is FAILED.
    """

    import_id: str
    status: ImportStatus
    document: CanonicalDocument | None
    diagnostics: ImportDiagnostics
    capability: CapabilityRecord
    provenance: ImportProvenance | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        _s = object.__setattr__
        _s(self, "import_id", require_non_empty_str(self.import_id, "import_id"))
        if not isinstance(self.status, ImportStatus):
            raise ValidationError("status must be an ImportStatus")
        if self.document is not None and not isinstance(self.document, CanonicalDocument):
            raise ValidationError("document must be a CanonicalDocument or None")
        if not isinstance(self.diagnostics, ImportDiagnostics):
            raise ValidationError("diagnostics must be ImportDiagnostics")
        if not isinstance(self.capability, CapabilityRecord):
            raise ValidationError("capability must be a CapabilityRecord")
        if self.provenance is not None and not isinstance(self.provenance, ImportProvenance):
            raise ValidationError("provenance must be an ImportProvenance or None")
        _s(self, "error_message",
           optional_non_empty_str(self.error_message, "error_message"))

    @property
    def succeeded(self) -> bool:
        """True when status is SUCCESS or DEGRADED (partial success)."""
        return self.status in (ImportStatus.SUCCESS, ImportStatus.DEGRADED,
                               ImportStatus.PARTIAL)

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Format detection helper
# ---------------------------------------------------------------------------

def detect_format(
    source: EngineeringSource,
    header_bytes: bytes | None = None,
) -> FormatDetectionResult:
    """Attempt to identify the format of an engineering source.

    Uses content sniffing (via source.notes) and file-extension hints.
    Returns a FormatDetectionResult — never raises.

    Args:
        source: The engineering source to identify.

    Returns:
        FormatDetectionResult with detected_format_id and confidence.
    """
    # Content-based detection (high confidence).  The explicit sample keeps
    # upload bytes out of EngineeringSource; notes remains a compatibility path.
    content_bytes = header_bytes
    if content_bytes is None and source.notes:
        content_bytes = source.notes.encode("utf-8", errors="replace")
    if content_bytes:
        sniffed = ContentSniffer.sniff(content_bytes)
        if sniffed:
            return FormatDetectionResult(
                detected_format_id=sniffed,
                detection_confidence="HIGH",
                detection_method="content_magic_bytes",
            )

    # Format ID already provided (caller-supplied, treat as HIGH)
    if source.source_format_id:
        return FormatDetectionResult(
            detected_format_id=source.source_format_id,
            detection_confidence="HIGH",
            detection_method="caller_supplied_format_id",
        )

    # Extension-based detection (medium confidence)
    if source.file_name:
        lower = source.file_name.lower()
        if lower.endswith((".stp", ".step", ".p21")):
            hint = "STEP-AP242" if "242" in lower else "STEP-GENERIC"
            return FormatDetectionResult(
                detected_format_id=hint,
                detection_confidence="MEDIUM",
                detection_method="file_extension",
                format_family_hint="STEP-GENERIC",
            )
        if lower.endswith((".igs", ".iges")):
            return FormatDetectionResult(
                detected_format_id="IGES",
                detection_confidence="MEDIUM",
                detection_method="file_extension",
            )
        if lower.endswith(".dxf"):
            return FormatDetectionResult(
                detected_format_id="DXF",
                detection_confidence="MEDIUM",
                detection_method="file_extension",
            )

    return FormatDetectionResult(
        detected_format_id=None,
        detection_confidence="NONE",
        detection_method="unrecognised",
    )


# ---------------------------------------------------------------------------
# Deterministic ID helper
# ---------------------------------------------------------------------------

def _make_import_id(source_id: str, adapter_id: str) -> str:
    """Derive a deterministic import ID from source and adapter identifiers."""
    return f"import::{source_id}::{adapter_id}"


def _make_failed_import_id(source_id: str) -> str:
    """Deterministic ID for a failed import (no adapter selected)."""
    return f"import::{source_id}::no-adapter"


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class CadImportOrchestrator:
    """Deterministic orchestration pipeline for CAD source ingestion.

    Composes:
    * Format detection (Stage 4C ContentSniffer + extension hints)
    * Adapter registry lookup (Stage 4A AdapterRegistry)
    * Adapter selection (explicit or first-ordered)
    * Adapter execution (Stage 4C adapters)
    * Result normalization (ImportResult)
    * Provenance construction

    No parsing, geometry, or CAD-kernel logic lives here.  The orchestrator
    delegates all format-specific work to the registered adapters.

    Usage::

        orchestrator = CadImportOrchestrator()
        result = orchestrator.import_source(source, format_descriptor)
        if result.succeeded:
            document = result.document
    """

    def __init__(
        self,
        registry: AdapterRegistry | None = None,
    ) -> None:
        """Construct an orchestrator.

        Args:
            registry: Adapter registry to use.  If None, the default
                registry (Stage 4C built-in adapters) is used.
        """
        self._registry: AdapterRegistry = (
            registry if registry is not None else build_default_adapter_registry()
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def import_source(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor | None = None,
        *,
        adapter_id: str | None = None,
        requested_level: CapabilityLevel | None = None,
        content_path: Path | None = None,
        header_bytes: bytes | None = None,
    ) -> ImportResult:
        """Orchestrate a full CAD import pipeline for *source*.

        Steps:
        1. Detect format (ContentSniffer + extension + caller hint).
        2. Resolve FormatDescriptor (caller-supplied or constructed from detection).
        3. Find adapter candidates from the registry.
        4. Select an adapter (explicit *adapter_id* or first-ordered candidate).
        5. Execute adapter.ingest().
        6. Build ImportResult with diagnostics, capability record, provenance.

        The orchestrator never raises on format/adapter issues — it always
        returns an ImportResult with an appropriate status.

        Args:
            source:            Engineering source to import.
            format_descriptor: Optional caller-supplied format descriptor.
                               When supplied and consistent with detection,
                               it is used directly.
            adapter_id:        Explicitly select a specific adapter by ID.
                               When None, the first alphabetically-ordered
                               capable adapter is used.
            requested_level:   Optional capability level the caller desires.
                               Used only to compute CapabilityRecord.was_degraded.

        Returns:
            ImportResult — always.
        """
        # --- Step 1: format detection ---
        detection = detect_format(source, header_bytes=header_bytes)

        # --- Step 2: resolve format descriptor ---
        resolved_descriptor = format_descriptor or self._resolve_descriptor(
            detection, source
        )

        # --- Step 3: find adapter candidates ---
        format_id_to_query = (
            resolved_descriptor.format_id
            if resolved_descriptor
            else (detection.detected_format_id or "")
        )
        candidates = self._registry.find_by_format(format_id_to_query)

        # Also check by source format_id in case descriptor differs
        if not candidates and source.source_format_id:
            candidates = self._registry.find_by_format(source.source_format_id)

        # --- Step 4: select adapter ---
        selected_adapter, selection_reason = self._select_adapter(
            candidates, adapter_id
        )

        # Build diagnostics stub (completed later)
        candidate_ids = tuple(a.metadata().adapter_id for a in candidates)

        if selected_adapter is None:
            return self._build_unsupported_result(
                source, detection, candidate_ids, format_id_to_query, requested_level,
                selection_reason=selection_reason,
            )

        # --- Step 5: execute adapter ---
        actual_descriptor = resolved_descriptor or self._minimal_descriptor(
            format_id_to_query or selected_adapter.metadata().format_ids[0]
        )

        # Confirm the selected adapter can handle this specific source.
        # can_handle() must be called after format resolution so the adapter
        # receives the confirmed descriptor.  An exception from can_handle is
        # deterministically recorded — it never propagates to the caller.
        try:
            if not selected_adapter.can_handle(source, actual_descriptor):
                return self._build_unsupported_result(
                    source, detection, candidate_ids, format_id_to_query,
                    requested_level,
                    selection_reason=(
                        f"can_handle_rejected:{selected_adapter.metadata().adapter_id}"
                    ),
                )
        except Exception as can_exc:  # noqa: BLE001
            return self._build_unsupported_result(
                source, detection, candidate_ids, format_id_to_query,
                requested_level,
                selection_reason=(
                    f"can_handle_raised:{selected_adapter.metadata().adapter_id}"
                    f":{can_exc}"
                ),
            )

        try:
            if content_path is None:
                document = selected_adapter.ingest(source, actual_descriptor)
            else:
                document = selected_adapter.ingest_file(
                    source, actual_descriptor, content_path
                )
        except Exception:  # noqa: BLE001
            return self._build_error_result(
                source, detection, candidate_ids,
                selected_adapter, actual_descriptor, requested_level,
                error="Adapter execution failed",
            )

        # --- Step 6: build result ---
        return self._build_success_result(
            source, detection, candidate_ids, selection_reason,
            selected_adapter, document, requested_level,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_descriptor(
        self,
        detection: FormatDetectionResult,
        source: EngineeringSource,
    ) -> FormatDescriptor | None:
        """Try to find a known descriptor for the detected format_id."""
        from backend.interoperability.adapters.dxf import DXF_DESCRIPTOR
        from backend.interoperability.adapters.iges import IGES_DESCRIPTOR
        from backend.interoperability.adapters.step import STEP_DESCRIPTORS

        fid = detection.detected_format_id or source.source_format_id
        if fid is None:
            return None
        if fid in STEP_DESCRIPTORS:
            return STEP_DESCRIPTORS[fid]
        if fid == "IGES":
            return IGES_DESCRIPTOR
        if fid == "DXF":
            return DXF_DESCRIPTOR
        return None

    @staticmethod
    def _minimal_descriptor(format_id: str) -> FormatDescriptor:
        """Construct a minimal descriptor when none is known."""
        from backend.interoperability.enums import AdapterLicense, FormatFamily

        return FormatDescriptor(
            format_id=format_id,
            canonical_name=format_id,
            family=FormatFamily.UNKNOWN,
            adapter_license=AdapterLicense.INTERNAL_PARSER,
        )

    @staticmethod
    def _select_adapter(
        candidates: tuple[FormatAdapter, ...],
        adapter_id: str | None,
    ) -> tuple[FormatAdapter | None, str]:
        """Select an adapter from candidates.

        Returns (adapter, selection_reason).
        """
        if not candidates:
            return None, "no_candidates"

        if adapter_id is not None:
            for a in candidates:
                if a.metadata().adapter_id == adapter_id:
                    return a, f"explicit_selection:{adapter_id}"
            # Requested adapter not in candidates
            return None, f"requested_adapter_not_found:{adapter_id}"

        # First alphabetically (candidates are already sorted by registry)
        return candidates[0], "first_ordered_candidate"

    def _build_unsupported_result(
        self,
        source: EngineeringSource,
        detection: FormatDetectionResult,
        candidate_ids: tuple[str, ...],
        format_id: str,
        requested_level: CapabilityLevel | None,
        *,
        selection_reason: str = "no_matching_adapter",
    ) -> ImportResult:
        diag = ImportDiagnostics(
            format_detection=detection,
            adapter_candidates=candidate_ids,
            selected_adapter_id=None,
            selection_reason=selection_reason,
            fidelity_adverse_count=0,
            has_unsupported_content=True,
            has_loss=False,
            notes=(f"No adapter found for format {format_id!r}",),
        )
        cap = CapabilityRecord(
            achieved_level=CapabilityLevel.LEVEL_0_RECOGNIZED,
            requested_level=requested_level,
            was_degraded=requested_level is not None,
            degradation_reason="no adapter available for this format",
        )
        return ImportResult(
            import_id=_make_failed_import_id(source.source_id),
            status=ImportStatus.UNSUPPORTED,
            document=None,
            diagnostics=diag,
            capability=cap,
            provenance=None,
            error_message=f"No adapter registered for format {format_id!r}",
        )

    def _build_error_result(
        self,
        source: EngineeringSource,
        detection: FormatDetectionResult,
        candidate_ids: tuple[str, ...],
        adapter: FormatAdapter,
        descriptor: FormatDescriptor,
        requested_level: CapabilityLevel | None,
        error: str,
    ) -> ImportResult:
        meta = adapter.metadata()
        diag = ImportDiagnostics(
            format_detection=detection,
            adapter_candidates=candidate_ids,
            selected_adapter_id=meta.adapter_id,
            selection_reason="adapter_raised_exception",
            fidelity_adverse_count=1,
            has_unsupported_content=False,
            has_loss=True,
            notes=(f"Adapter {meta.adapter_id!r} raised: {error}",),
        )
        cap = CapabilityRecord(
            achieved_level=CapabilityLevel.LEVEL_0_RECOGNIZED,
            requested_level=requested_level,
            was_degraded=requested_level is not None,
            degradation_reason=f"adapter exception: {error}",
        )
        prov = self._build_provenance(
            source, meta.adapter_id, meta.adapter_version,
            descriptor.format_id,
            CapabilityLevel.LEVEL_0_RECOGNIZED,
            NormalizationStatus.FAILED,
        )
        return ImportResult(
            import_id=_make_import_id(source.source_id, meta.adapter_id),
            status=ImportStatus.FAILED,
            document=None,
            diagnostics=diag,
            capability=cap,
            provenance=prov,
            error_message=error,
        )

    def _build_success_result(
        self,
        source: EngineeringSource,
        detection: FormatDetectionResult,
        candidate_ids: tuple[str, ...],
        selection_reason: str,
        adapter: FormatAdapter,
        document: CanonicalDocument,
        requested_level: CapabilityLevel | None,
    ) -> ImportResult:
        meta = adapter.metadata()
        report = document.fidelity_report
        adverse_count = len(report.adverse_events) if report else 0
        has_unsup = report.has_unsupported_content if report else False
        has_loss = report.has_loss if report else False

        notes_list: list[str] = []
        if document.normalization_status is NormalizationStatus.FAILED:
            notes_list.append("Adapter reported FAILED normalization status")

        diag = ImportDiagnostics(
            format_detection=detection,
            adapter_candidates=candidate_ids,
            selected_adapter_id=meta.adapter_id,
            selection_reason=selection_reason,
            fidelity_adverse_count=adverse_count,
            has_unsupported_content=has_unsup,
            has_loss=has_loss,
            notes=tuple(notes_list),
        )

        # Capability record
        achieved = document.capability_level
        was_degraded = False
        degradation_reason: str | None = None
        optional_absent = False
        optional_name: str | None = None

        if requested_level is not None:
            # Compare by ordinal position in CapabilityLevel ordering
            levels = list(CapabilityLevel)
            req_idx = levels.index(requested_level)
            ach_idx = levels.index(achieved)
            if ach_idx < req_idx:
                was_degraded = True
                degradation_reason = (
                    f"reached {achieved.value} but {requested_level.value} was requested"
                )
                if meta.requires_external_dependency and has_unsup:
                    optional_absent = True
                    optional_name = meta.external_dependency_name

        cap = CapabilityRecord(
            achieved_level=achieved,
            requested_level=requested_level,
            was_degraded=was_degraded,
            degradation_reason=degradation_reason,
            optional_dependency_absent=optional_absent,
            optional_dependency_name=optional_name,
        )

        prov = self._build_provenance(
            source, meta.adapter_id, meta.adapter_version,
            document.format_descriptor.format_id,
            achieved,
            document.normalization_status,
        )

        # Determine import status.
        # Priority: FAILED > INSUFFICIENT_DATA > UNSUPPORTED > PARTIAL > DEGRADED > SUCCESS
        norm_status = document.normalization_status
        if norm_status is NormalizationStatus.FAILED:
            status = ImportStatus.FAILED
        elif norm_status is NormalizationStatus.INSUFFICIENT_DATA:
            # Adapter could not extract required metadata — treat as FAILED
            status = ImportStatus.FAILED
        elif norm_status is NormalizationStatus.UNSUPPORTED:
            # Format recognized but not supported at this capability level
            status = ImportStatus.UNSUPPORTED
        elif has_loss:
            status = ImportStatus.PARTIAL
        elif was_degraded or has_unsup:
            status = ImportStatus.DEGRADED
        elif norm_status is NormalizationStatus.PARTIAL:
            status = ImportStatus.PARTIAL
        else:
            status = ImportStatus.SUCCESS

        # Extract error message from FAILED document fidelity events
        err_msg: str | None = None
        if status is ImportStatus.FAILED and report:
            lost = [e.description for e in report.events
                    if e.fidelity_class is FidelityClass.LOST]
            if lost:
                err_msg = lost[0]

        return ImportResult(
            import_id=_make_import_id(source.source_id, meta.adapter_id),
            status=status,
            document=document,
            diagnostics=diag,
            capability=cap,
            provenance=prov,
            error_message=err_msg,
        )

    @staticmethod
    def _build_provenance(
        source: EngineeringSource,
        adapter_id: str,
        adapter_version: str,
        format_id: str,
        capability_level: CapabilityLevel,
        normalization_status: NormalizationStatus,
    ) -> ImportProvenance:
        domain_prov = Provenance(
            source_type=ProvenanceType.USER_INPUT,
            source_reference=f"{adapter_id}@{adapter_version}",
            source_document=source.file_name or source.source_id,
            notes=f"format={format_id} level={capability_level.value}",
        )
        return ImportProvenance(
            source_id=source.source_id,
            adapter_id=adapter_id,
            adapter_version=adapter_version,
            format_id=format_id,
            capability_level=capability_level,
            normalization_status=normalization_status,
            domain_provenance=domain_prov,
        )
