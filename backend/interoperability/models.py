"""Core Canonical Engineering Representation (CER) models (Stage 4A).

Defines vendor-neutral, immutable data contracts for the engineering
interoperability layer.  These models sit between source file adapters and
the MachineryPro manufacturing-domain models (Feature, Operation, Tool, etc.)

Stage 4A establishes the top-level envelope and reference structures only.
Deeper canonical schemas (geometry, topology, PMI, CAM, NC, etc.) are
introduced in Stages 4B onward and attach to these contracts.

Architecture
------------

  SOURCE FILE
  → FormatAdapter (Stage 4B+)
  → CanonicalDocument          ← defined here
  → [semantic normalization]
  → MachineryPro Domain Models (Stages 3A–3J)
  → Deterministic engineering analysis

Conventions inherited from Stages 3A–3J
----------------------------------------
* frozen dataclasses — immutable once constructed.
* StrEnum — serializable, deterministic.
* Decimal where numeric engineering values are needed (rare in Stage 4A).
* require_non_empty_str / optional_non_empty_str from domain.base.
* Provenance from domain.base for source traceability.
* entity_as_dict for deterministic serialization.
* ValidationError from domain.exceptions for structural failures.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from backend.domain.base import (
    Provenance,
    entity_as_dict,
    optional_non_empty_str,
    require_non_empty_str,
)
from backend.domain.exceptions import ValidationError
from backend.interoperability.enums import (
    AdapterCapability,
    AdapterLicense,
    CapabilityLevel,
    FidelityClass,
    FidelityReportCompleteness,
    FormatFamily,
    NormalizationStatus,
)

__all__ = [
    "EngineeringSource",
    "FormatDescriptor",
    "AdapterMetadata",
    "CanonicalEntityRef",
    "FidelityEvent",
    "ConversionFidelityReport",
    "CanonicalDocument",
]


# ---------------------------------------------------------------------------
# Engineering source identity
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class EngineeringSource:
    """Immutable identity record for an engineering data source.

    Represents where a piece of engineering data came from — a file,
    a database record, an API response — without embedding the data
    itself or requiring a filesystem path.

    Fields
    ------
    source_id : str
        Stable unique identifier for this source within the current session
        or catalog.  Caller-supplied; MachineryPro does not generate IDs.
    source_format_id : str | None
        The format identifier (e.g. ``"STEP-AP242"``, ``"FANUC-NC"``).
        May be None when the format has not yet been identified.
    file_name : str | None
        Original filename if available (no path — paths are environment-
        specific and not stable).
    media_type : str | None
        MIME type when known (e.g. ``"model/step"``, ``"text/plain"``).
    vendor : str | None
        Originating software vendor when known (e.g. ``"Siemens"``).
    source_system : str | None
        Originating system name (e.g. ``"NX 2206"``, ``"Mastercam 2024"``).
    version : str | None
        Format or file version when extractable.
    checksum : str | None
        Content hash in the form ``"algorithm:hex"``
        (e.g. ``"sha256:abcdef..."``).  Caller supplies; not computed here.
    source_reference : str | None
        Human-readable locator (URL, URN, document number, archive path).
        NOT a filesystem path — paths are environment-specific.
    notes : str | None
        Optional free-text notes.
    """

    source_id: str
    source_format_id: str | None = None
    file_name: str | None = None
    media_type: str | None = None
    vendor: str | None = None
    source_system: str | None = None
    version: str | None = None
    checksum: str | None = None
    source_reference: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "source_id", require_non_empty_str(self.source_id, "source_id"))
        for name in (
            "source_format_id", "file_name", "media_type", "vendor",
            "source_system", "version", "checksum", "source_reference", "notes",
        ):
            _set(self, name, optional_non_empty_str(getattr(self, name), name))

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Format descriptor
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class FormatDescriptor:
    """Vendor-neutral descriptor for an engineering file format.

    Describes what a format IS, not what a specific file contains.
    A registry of FormatDescriptor instances is populated by format adapters;
    Stage 4A ships no production format database.

    Extension-based identification is explicitly marked as non-authoritative:
    ``".prt"`` could be NX, Creo, or another system.  Adapters must confirm
    format identity through content sniffing, not extension alone.

    Fields
    ------
    format_id : str
        Stable unique identifier (e.g. ``"STEP-AP242"``, ``"FANUC-0I"``).
    canonical_name : str
        Human-readable name (e.g. ``"STEP AP242"``).
    family : FormatFamily
        Primary format family.
    extensions : tuple[str, ...]
        Common file extensions, lowercase without leading dot.
        Non-authoritative for format identification.
    media_types : tuple[str, ...]
        MIME types (may be empty for formats with no registered MIME type).
    vendor : str | None
        Originating vendor/organization (e.g. ``"ISO"``, ``"Siemens"``).
    is_open : bool
        True when the format specification is publicly available.
    is_proprietary : bool
        True when the format requires reverse-engineering or vendor SDK.
    requires_commercial_sdk : bool
        True when full read/write requires a paid commercial SDK or license.
    adapter_license : AdapterLicense | None
        Licensing model for the preferred adapter implementation.
    notes : str | None
        Additional notes (version history, known limitations, etc.).
    """

    format_id: str
    canonical_name: str
    family: FormatFamily
    extensions: tuple[str, ...] = ()
    media_types: tuple[str, ...] = ()
    vendor: str | None = None
    is_open: bool = True
    is_proprietary: bool = False
    requires_commercial_sdk: bool = False
    adapter_license: AdapterLicense | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "format_id", require_non_empty_str(self.format_id, "format_id"))
        _set(
            self,
            "canonical_name",
            require_non_empty_str(self.canonical_name, "canonical_name"),
        )
        if not isinstance(self.family, FormatFamily):
            raise ValidationError("family must be a FormatFamily")
        # Validate extensions tuple
        cleaned_exts: list[str] = []
        for ext in self.extensions:
            cleaned_exts.append(
                require_non_empty_str(ext, "extensions entry").lower()
            )
        object.__setattr__(self, "extensions", tuple(cleaned_exts))
        # Validate media_types tuple
        cleaned_mt: list[str] = []
        for mt in self.media_types:
            cleaned_mt.append(require_non_empty_str(mt, "media_types entry").lower())
        object.__setattr__(self, "media_types", tuple(cleaned_mt))
        for name in ("vendor", "notes"):
            _set(self, name, optional_non_empty_str(getattr(self, name), name))
        if not isinstance(self.is_open, bool):
            raise ValidationError("is_open must be bool")
        if not isinstance(self.is_proprietary, bool):
            raise ValidationError("is_proprietary must be bool")
        if not isinstance(self.requires_commercial_sdk, bool):
            raise ValidationError("requires_commercial_sdk must be bool")
        if self.adapter_license is not None and not isinstance(
            self.adapter_license, AdapterLicense
        ):
            raise ValidationError("adapter_license must be an AdapterLicense or None")

    def extension_matches(self, filename: str) -> bool:
        """True when *filename*'s extension matches this descriptor.

        Non-authoritative: extension match is a hint, not confirmation.
        Adapters must independently verify format identity via content
        sniffing or magic bytes.
        """
        lower = filename.lower()
        return any(lower.endswith(f".{ext}") for ext in self.extensions)

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Adapter metadata
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class AdapterMetadata:
    """Declared metadata for a format adapter.

    Adapters self-declare their identity, capabilities, and the format(s)
    they support.  The registry stores these declarations; callers use them
    to discover and select adapters explicitly.

    Fields
    ------
    adapter_id : str
        Stable unique identifier (e.g. ``"occt-step-adapter"``).
    adapter_name : str
        Human-readable name.
    adapter_version : str
        Semantic version of the adapter implementation.
    format_ids : tuple[str, ...]
        Format IDs this adapter can handle.
    capabilities : tuple[AdapterCapability, ...]
        Declared capabilities (RECOGNIZE, PARSE, NORMALIZE, etc.).
    max_capability_level : CapabilityLevel
        Highest capability level this adapter can reach.
    adapter_license : AdapterLicense
        Licensing model.
    requires_external_dependency : bool
        True when the adapter requires an external library, SDK, or
        installed application to function.
    external_dependency_name : str | None
        Name of the external dependency when applicable.
    notes : str | None
        Optional notes.
    """

    adapter_id: str
    adapter_name: str
    adapter_version: str
    format_ids: tuple[str, ...]
    capabilities: tuple[AdapterCapability, ...]
    max_capability_level: CapabilityLevel
    adapter_license: AdapterLicense
    requires_external_dependency: bool = False
    external_dependency_name: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "adapter_id", require_non_empty_str(self.adapter_id, "adapter_id"))
        _set(
            self,
            "adapter_name",
            require_non_empty_str(self.adapter_name, "adapter_name"),
        )
        _set(
            self,
            "adapter_version",
            require_non_empty_str(self.adapter_version, "adapter_version"),
        )
        if not self.format_ids:
            raise ValidationError("format_ids must not be empty")
        cleaned_fmts: list[str] = []
        for fid in self.format_ids:
            cleaned_fmts.append(require_non_empty_str(fid, "format_ids entry"))
        object.__setattr__(self, "format_ids", tuple(cleaned_fmts))
        if not self.capabilities:
            raise ValidationError("capabilities must not be empty")
        for cap in self.capabilities:
            if not isinstance(cap, AdapterCapability):
                raise ValidationError("capabilities entries must be AdapterCapability")
        if not isinstance(self.max_capability_level, CapabilityLevel):
            raise ValidationError("max_capability_level must be a CapabilityLevel")
        if not isinstance(self.adapter_license, AdapterLicense):
            raise ValidationError("adapter_license must be an AdapterLicense")
        if not isinstance(self.requires_external_dependency, bool):
            raise ValidationError("requires_external_dependency must be bool")
        _set(
            self,
            "external_dependency_name",
            optional_non_empty_str(
                self.external_dependency_name, "external_dependency_name"
            ),
        )
        _set(self, "notes", optional_non_empty_str(self.notes, "notes"))

    def supports_capability(self, capability: AdapterCapability) -> bool:
        """True when this adapter declares the given capability."""
        return capability in self.capabilities

    def supports_format(self, format_id: str) -> bool:
        """True when this adapter declares support for the given format_id."""
        return format_id in self.format_ids

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Canonical entity reference
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CanonicalEntityRef:
    """A stable, typed reference to a canonical engineering entity.

    Used within CanonicalDocument to reference geometry bodies, faces,
    features, operations, PMI annotations, etc. without requiring those
    deep schemas to exist in Stage 4A.

    Future canonical model stages (4B, 4C, …) will populate the actual
    entity objects; this reference mechanism allows the envelope to work
    before those models are implemented.

    Fields
    ------
    entity_id : str
        Stable ID within the document scope.
    entity_kind : str
        Semantic type of the entity (e.g. ``"BRepSolid"``, ``"GDTCallout"``,
        ``"NCBlock"``, ``"CAMOperation"``).
    source_entity_id : str | None
        Corresponding ID in the source file (for traceability).
    parent_entity_id : str | None
        ID of the containing entity (e.g. assembly → component).
    metadata : Mapping[str, object]
        Additional key/value metadata.  Immutable proxy after construction.
    """

    entity_id: str
    entity_kind: str
    source_entity_id: str | None = None
    parent_entity_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "entity_id", require_non_empty_str(self.entity_id, "entity_id"))
        _set(self, "entity_kind", require_non_empty_str(self.entity_kind, "entity_kind"))
        _set(
            self,
            "source_entity_id",
            optional_non_empty_str(self.source_entity_id, "source_entity_id"),
        )
        _set(
            self,
            "parent_entity_id",
            optional_non_empty_str(self.parent_entity_id, "parent_entity_id"),
        )
        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Fidelity event
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class FidelityEvent:
    """One event in a conversion / normalization fidelity record.

    Every normalization step that does not produce a fully PRESERVED result
    MUST record a FidelityEvent.  Silent semantic downgrade is prohibited:

        "No adapter may silently downgrade engineering semantics.  Any loss,
        inference, reconstruction, unsupported semantic, or confidence
        reduction must be explicitly represented in fidelity metadata."

    Fields
    ------
    event_id : str
        Stable identifier within the report.
    fidelity_class : FidelityClass
        Classification of the event.
    source_entity_ref : CanonicalEntityRef | None
        The entity in the source that was affected.
    target_entity_ref : CanonicalEntityRef | None
        The entity in the normalized output (may be None if LOST).
    description : str
        Human-readable explanation of what happened.
    source_semantic : str | None
        What the source data represented semantically.
    target_semantic : str | None
        What the normalized output represents semantically.
    """

    event_id: str
    fidelity_class: FidelityClass
    description: str
    source_entity_ref: CanonicalEntityRef | None = None
    target_entity_ref: CanonicalEntityRef | None = None
    source_semantic: str | None = None
    target_semantic: str | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "event_id", require_non_empty_str(self.event_id, "event_id"))
        if not isinstance(self.fidelity_class, FidelityClass):
            raise ValidationError("fidelity_class must be a FidelityClass")
        _set(self, "description", require_non_empty_str(self.description, "description"))
        if self.source_entity_ref is not None and not isinstance(
            self.source_entity_ref, CanonicalEntityRef
        ):
            raise ValidationError(
                "source_entity_ref must be a CanonicalEntityRef or None"
            )
        if self.target_entity_ref is not None and not isinstance(
            self.target_entity_ref, CanonicalEntityRef
        ):
            raise ValidationError(
                "target_entity_ref must be a CanonicalEntityRef or None"
            )
        _set(
            self,
            "source_semantic",
            optional_non_empty_str(self.source_semantic, "source_semantic"),
        )
        _set(
            self,
            "target_semantic",
            optional_non_empty_str(self.target_semantic, "target_semantic"),
        )

    @property
    def is_adverse(self) -> bool:
        """True for any class other than PRESERVED."""
        return self.fidelity_class is not FidelityClass.PRESERVED

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Conversion fidelity report
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ConversionFidelityReport:
    """Immutable record of conversion / normalization fidelity.

    Every adapter that moves data from a source format to a Canonical
    Engineering Representation MUST produce a fidelity report.  The report
    is an engineering artifact, not a log message.

    Losslessness rule (fail-closed):

        is_lossless == True
        ONLY when:
        (a) completeness is COMPLETE, AND
        (b) all events have fidelity_class == PRESERVED (or no events), AND
        (c) no event of any adverse class exists.

        is_lossless MUST be False when:
        - completeness is PARTIAL or UNKNOWN
        - any LOST / DOWNGRADED / INFERRED / RECONSTRUCTED / UNSUPPORTED
          / PARTIALLY_PRESERVED event exists

    Fields
    ------
    report_id : str
        Stable unique identifier.
    source_format_id : str
        Format ID of the source.
    target_format_id : str | None
        Format ID of the output (None for normalization-only steps).
    adapter_id : str
        The adapter that produced this report.
    adapter_version : str
        Version of the adapter at report generation time.
    source_entity_count : int | None
        Total entities in the source (None if unknown).
    events : tuple[FidelityEvent, ...]
        All recorded fidelity events.  PRESERVED events need not be recorded
        individually when the adapter performs bulk-PRESERVED normalization;
        in that case, source_entity_count and the absence of adverse events
        implies full preservation — but only when completeness is COMPLETE.
    completeness : FidelityReportCompleteness
        Whether all source entities were evaluated.
    normalization_status : NormalizationStatus
        The outcome of the normalization step itself.
    notes : str | None
        Optional adapter-level notes.
    """

    report_id: str
    source_format_id: str
    adapter_id: str
    adapter_version: str
    completeness: FidelityReportCompleteness
    normalization_status: NormalizationStatus
    target_format_id: str | None = None
    source_entity_count: int | None = None
    events: tuple[FidelityEvent, ...] = ()
    notes: str | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "report_id", require_non_empty_str(self.report_id, "report_id"))
        _set(
            self,
            "source_format_id",
            require_non_empty_str(self.source_format_id, "source_format_id"),
        )
        _set(
            self,
            "adapter_id",
            require_non_empty_str(self.adapter_id, "adapter_id"),
        )
        _set(
            self,
            "adapter_version",
            require_non_empty_str(self.adapter_version, "adapter_version"),
        )
        _set(
            self,
            "target_format_id",
            optional_non_empty_str(self.target_format_id, "target_format_id"),
        )
        if not isinstance(self.completeness, FidelityReportCompleteness):
            raise ValidationError("completeness must be a FidelityReportCompleteness")
        if not isinstance(self.normalization_status, NormalizationStatus):
            raise ValidationError("normalization_status must be a NormalizationStatus")
        if self.source_entity_count is not None:
            if (
                isinstance(self.source_entity_count, bool)
                or not isinstance(self.source_entity_count, int)
                or self.source_entity_count < 0
            ):
                raise ValidationError(
                    "source_entity_count must be a non-negative integer or None"
                )
        for event in self.events:
            if not isinstance(event, FidelityEvent):
                raise ValidationError("events entries must be FidelityEvent instances")
        _set(self, "notes", optional_non_empty_str(self.notes, "notes"))

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def adverse_events(self) -> tuple[FidelityEvent, ...]:
        """All events with fidelity_class other than PRESERVED."""
        return tuple(e for e in self.events if e.is_adverse)

    @property
    def has_loss(self) -> bool:
        return any(e.fidelity_class is FidelityClass.LOST for e in self.events)

    @property
    def has_inference(self) -> bool:
        return any(e.fidelity_class is FidelityClass.INFERRED for e in self.events)

    @property
    def has_reconstruction(self) -> bool:
        return any(
            e.fidelity_class is FidelityClass.RECONSTRUCTED for e in self.events
        )

    @property
    def has_unsupported_content(self) -> bool:
        return any(
            e.fidelity_class is FidelityClass.UNSUPPORTED for e in self.events
        )

    @property
    def has_downgrade(self) -> bool:
        return any(
            e.fidelity_class is FidelityClass.DOWNGRADED for e in self.events
        )

    @property
    def has_partial_preservation(self) -> bool:
        return any(
            e.fidelity_class is FidelityClass.PARTIALLY_PRESERVED
            for e in self.events
        )

    @property
    def is_lossless(self) -> bool:
        """True ONLY when ALL of the following hold:

        1. completeness is COMPLETE.
        2. No adverse fidelity event exists (LOST, DOWNGRADED, INFERRED,
           RECONSTRUCTED, UNSUPPORTED, PARTIALLY_PRESERVED).

        This property is fail-closed: it returns False whenever losslessness
        cannot be confidently asserted, including when completeness is UNKNOWN
        or PARTIAL.
        """
        if self.completeness is not FidelityReportCompleteness.COMPLETE:
            return False
        return len(self.adverse_events) == 0

    def counts_by_class(self) -> dict[str, int]:
        """Return a deterministic count of events per FidelityClass."""
        counts: dict[str, int] = {cls.value: 0 for cls in FidelityClass}
        for event in self.events:
            counts[event.fidelity_class.value] += 1
        return counts

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Canonical document envelope
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CanonicalDocument:
    """Top-level envelope for a Canonical Engineering Representation document.

    A CanonicalDocument is the output of a successful normalization step.
    It identifies the source, the adapter used, the capability level reached,
    and holds references to the canonical entities contained within it.

    Deep entity content (geometry bodies, PMI callouts, CAM operations, NC
    blocks, etc.) is not embedded here at Stage 4A.  Entity references
    (CanonicalEntityRef) provide forward pointers; deep canonical schemas
    are introduced in Stages 4B onward.

    This envelope is designed to be stable across all future stage additions.

    Fields
    ------
    document_id : str
        Stable unique identifier for this CER document.
    canonical_kind : str
        Primary kind of canonical content (e.g. ``"CAD_GEOMETRY"``,
        ``"NC_PROGRAM"``, ``"CAM_PROJECT"``).  Free-form at Stage 4A;
        later stages will define controlled values.
    source : EngineeringSource
        Identity of the original data source.
    format_descriptor : FormatDescriptor
        Descriptor of the format that was ingested.
    adapter_id : str
        ID of the adapter that produced this document.
    adapter_version : str
        Version of the adapter.
    capability_level : CapabilityLevel
        Highest capability level reached during normalization.
    normalization_status : NormalizationStatus
        Outcome of the normalization step.
    entity_refs : tuple[CanonicalEntityRef, ...]
        References to the canonical entities contained in this document.
        Sorted by entity_id for deterministic ordering.
    fidelity_report : ConversionFidelityReport | None
        Fidelity report for this normalization step.  May be None when the
        adapter has not yet reached normalization (Level 0–1).
    provenance : Provenance | None
        MachineryPro Provenance for integration with domain models.
    schema_version : str
        CER schema version (for forward compatibility).
    notes : str | None
        Optional notes.
    """

    document_id: str
    canonical_kind: str
    source: EngineeringSource
    format_descriptor: FormatDescriptor
    adapter_id: str
    adapter_version: str
    capability_level: CapabilityLevel
    normalization_status: NormalizationStatus
    entity_refs: tuple[CanonicalEntityRef, ...] = ()
    fidelity_report: ConversionFidelityReport | None = None
    provenance: Provenance | None = None
    geometry: object | None = None
    topology: object | None = None
    schema_version: str = "4A.0"
    notes: str | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(
            self,
            "document_id",
            require_non_empty_str(self.document_id, "document_id"),
        )
        _set(
            self,
            "canonical_kind",
            require_non_empty_str(self.canonical_kind, "canonical_kind"),
        )
        if not isinstance(self.source, EngineeringSource):
            raise ValidationError("source must be an EngineeringSource")
        if not isinstance(self.format_descriptor, FormatDescriptor):
            raise ValidationError("format_descriptor must be a FormatDescriptor")
        _set(self, "adapter_id", require_non_empty_str(self.adapter_id, "adapter_id"))
        _set(
            self,
            "adapter_version",
            require_non_empty_str(self.adapter_version, "adapter_version"),
        )
        if not isinstance(self.capability_level, CapabilityLevel):
            raise ValidationError("capability_level must be a CapabilityLevel")
        if not isinstance(self.normalization_status, NormalizationStatus):
            raise ValidationError("normalization_status must be a NormalizationStatus")
        for ref in self.entity_refs:
            if not isinstance(ref, CanonicalEntityRef):
                raise ValidationError(
                    "entity_refs entries must be CanonicalEntityRef instances"
                )
        if self.fidelity_report is not None and not isinstance(
            self.fidelity_report, ConversionFidelityReport
        ):
            raise ValidationError(
                "fidelity_report must be a ConversionFidelityReport or None"
            )
        if self.provenance is not None and not isinstance(self.provenance, Provenance):
            raise ValidationError("provenance must be a Provenance or None")
        if self.geometry is not None:
            from backend.interoperability.geometry import CanonicalGeometry

            if not isinstance(self.geometry, CanonicalGeometry):
                raise ValidationError("geometry must be a CanonicalGeometry or None")
        if self.topology is not None:
            from backend.interoperability.topology import CanonicalTopology

            if not isinstance(self.topology, CanonicalTopology):
                raise ValidationError("topology must be a CanonicalTopology or None")
            if self.geometry is not None and self.topology.geometry is not self.geometry:
                raise ValidationError(
                    "topology geometry must reference the document geometry"
                )
        _set(
            self,
            "schema_version",
            require_non_empty_str(self.schema_version, "schema_version"),
        )
        _set(self, "notes", optional_non_empty_str(self.notes, "notes"))

    @property
    def ordered_entity_refs(self) -> tuple[CanonicalEntityRef, ...]:
        """Entity references sorted by entity_id (deterministic)."""
        return tuple(sorted(self.entity_refs, key=lambda r: r.entity_id))

    @property
    def is_lossless(self) -> bool:
        """True when the fidelity report confirms lossless normalization."""
        if self.fidelity_report is None:
            return False
        return self.fidelity_report.is_lossless

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)
