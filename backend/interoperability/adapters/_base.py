"""Shared helpers for Stage 4C built-in format adapters.

Internal module — not part of the public API.

Contains:
* Unique ID generation for canonical entities within an adapter session.
* Helper to build a ConversionFidelityReport from collected events.
* Helper to build a CanonicalDocument from adapter-session state.
* ContentSniffer: magic-bytes / header-pattern format identification.
"""

from __future__ import annotations

import uuid

from backend.interoperability.enums import (
    CapabilityLevel,
    FidelityClass,
    FidelityReportCompleteness,
    NormalizationStatus,
)
from backend.interoperability.models import (
    AdapterMetadata,
    CanonicalDocument,
    CanonicalEntityRef,
    ConversionFidelityReport,
    EngineeringSource,
    FidelityEvent,
    FormatDescriptor,
)

__all__ = [
    "AdapterSession",
    "ContentSniffer",
    "make_uid",
]


def make_uid(prefix: str = "") -> str:
    """Generate a stable-within-session unique identifier."""
    uid = uuid.uuid4().hex[:12]
    return f"{prefix}{uid}" if prefix else uid


class AdapterSession:
    """Mutable accumulator used by adapters during a single ingest call.

    Collects fidelity events, entity refs, and capability state, then
    produces the immutable CanonicalDocument at the end.

    Not thread-safe; one session per ingest() call.
    """

    def __init__(
        self,
        source: EngineeringSource,
        descriptor: FormatDescriptor,
        adapter_meta: AdapterMetadata,
    ) -> None:
        self.source = source
        self.descriptor = descriptor
        self.adapter_meta = adapter_meta
        self._fidelity_events: list[FidelityEvent] = []
        self._entity_refs: list[CanonicalEntityRef] = []
        self._capability_level = CapabilityLevel.LEVEL_0_RECOGNIZED
        self._normalization_status = NormalizationStatus.INSUFFICIENT_DATA
        self._fidelity_completeness = FidelityReportCompleteness.UNKNOWN
        self._source_entity_count: int | None = None
        self._extra_canonical_payloads: dict[str, object] = {}
        self._geometry: object | None = None
        self._topology: object | None = None
        self._built = False

    # ------------------------------------------------------------------
    # Capability progression
    # ------------------------------------------------------------------

    def mark_parsed(self) -> None:
        self._capability_level = CapabilityLevel.LEVEL_1_PARSED
        self._normalization_status = NormalizationStatus.SUCCESS

    def mark_normalized(self) -> None:
        self._capability_level = CapabilityLevel.LEVEL_2_NORMALIZED

    def mark_failed(self) -> None:
        self._normalization_status = NormalizationStatus.FAILED

    def mark_partial(self) -> None:
        self._normalization_status = NormalizationStatus.PARTIAL

    def mark_unsupported(self) -> None:
        self._normalization_status = NormalizationStatus.UNSUPPORTED

    def set_source_entity_count(self, n: int) -> None:
        self._source_entity_count = n

    def set_fidelity_completeness(self, c: FidelityReportCompleteness) -> None:
        self._fidelity_completeness = c

    # ------------------------------------------------------------------
    # Fidelity events
    # ------------------------------------------------------------------

    def record(
        self,
        fidelity_class: FidelityClass,
        description: str,
        source_ref: CanonicalEntityRef | None = None,
        target_ref: CanonicalEntityRef | None = None,
    ) -> None:
        event = FidelityEvent(
            event_id=make_uid("EV-"),
            fidelity_class=fidelity_class,
            description=description,
            source_entity_ref=source_ref,
            target_entity_ref=target_ref,
        )
        self._fidelity_events.append(event)

    def record_unsupported(self, description: str) -> None:
        self.record(FidelityClass.UNSUPPORTED, description)

    def record_inferred(self, description: str) -> None:
        self.record(FidelityClass.INFERRED, description)

    def record_lost(self, description: str) -> None:
        self.record(FidelityClass.LOST, description)

    def record_partial(self, description: str) -> None:
        self.record(FidelityClass.PARTIALLY_PRESERVED, description)

    # ------------------------------------------------------------------
    # Entity references
    # ------------------------------------------------------------------

    def add_entity_ref(self, ref: CanonicalEntityRef) -> None:
        self._entity_refs.append(ref)

    def set_geometry(self, geometry: object) -> None:
        if self._built:
            raise RuntimeError("adapter session has already been built")
        from backend.interoperability.geometry import CanonicalGeometry

        if not isinstance(geometry, CanonicalGeometry):
            raise TypeError("geometry must be a CanonicalGeometry")
        self._geometry = geometry

    def set_topology(self, topology: object) -> None:
        if self._built:
            raise RuntimeError("adapter session has already been built")
        from backend.interoperability.topology import CanonicalTopology

        if not isinstance(topology, CanonicalTopology):
            raise TypeError("topology must be a CanonicalTopology")
        self._topology = topology

    # ------------------------------------------------------------------
    # Build output
    # ------------------------------------------------------------------

    def build(self) -> CanonicalDocument:
        report = ConversionFidelityReport(
            report_id=make_uid("RPT-"),
            source_format_id=self.descriptor.format_id,
            adapter_id=self.adapter_meta.adapter_id,
            adapter_version=self.adapter_meta.adapter_version,
            completeness=self._fidelity_completeness,
            normalization_status=self._normalization_status,
            target_format_id=None,
            source_entity_count=self._source_entity_count,
            events=tuple(self._fidelity_events),
        )
        document = CanonicalDocument(
            document_id=make_uid("DOC-"),
            canonical_kind=self.descriptor.family.value,
            source=self.source,
            format_descriptor=self.descriptor,
            adapter_id=self.adapter_meta.adapter_id,
            adapter_version=self.adapter_meta.adapter_version,
            capability_level=self._capability_level,
            normalization_status=self._normalization_status,
            entity_refs=tuple(self._entity_refs),
            fidelity_report=report,
            geometry=self._geometry,
            topology=self._topology,
        )
        self._built = True
        return document


class ContentSniffer:
    """Magic-bytes and header-pattern based format identification.

    Returns the most likely format family and specific format ID
    from the first bytes of a file without reading the whole thing.

    All detection is heuristic; callers should treat results as
    hints, not authoritative identification.
    """

    # STEP: ISO-10303-21 header; first non-whitespace token is "ISO-10303-21;"
    _STEP_MAGIC = b"ISO-10303-21;"
    _STEP_MAGIC_ALT = b"iso-10303-21;"  # case-insensitive check

    # IGES: ASCII file; first field of section line is always the field
    # delimiter and section code; we check for "S" section header pattern
    # (a solid sequence of 72 ASCII chars + field delimiter + "S" + sequence).
    # Simpler: the 73rd char of a well-formed IGES line is "S", "G", "D",
    # "P", or "T". We sniff for common IGES G-section text.
    _IGES_PATTERNS: tuple[bytes, ...] = (
        b",,",   # IGES global section has lots of commas
        b"9H",   # IGES Hollerith string prefix common in G-section
    )

    # DXF: ASCII "DXF" files start with group code 0 followed by "SECTION"
    _DXF_MAGIC = b"  0\r\nSECTION"
    _DXF_MAGIC_ALT = b"  0\nSECTION"
    _DXF_MAGIC_BINARY = b"AutoCAD Binary DXF"

    @classmethod
    def sniff(cls, header_bytes: bytes) -> str | None:
        """Return a format_id hint or None if unrecognised.

        Uses only the first 512 bytes.
        """
        sample = header_bytes[:512]
        upper = sample.upper()

        if cls._STEP_MAGIC in upper:
            # Determine AP version from HEADER section if present
            if b"AP242" in upper:
                return "STEP-AP242"
            if b"AP214" in upper:
                return "STEP-AP214"
            if b"AP203" in upper:
                return "STEP-AP203"
            return "STEP-GENERIC"

        if cls._DXF_MAGIC_BINARY in sample:
            return "DXF-BINARY"

        if cls._DXF_MAGIC in sample or cls._DXF_MAGIC_ALT in sample:
            return "DXF"

        # IGES: harder to sniff reliably.  Check for 72-char line + section code
        try:
            lines = sample.split(b"\n")[:5]
            for line in lines:
                stripped = line.rstrip(b"\r")
                if len(stripped) >= 73 and stripped[72:73] in (b"S", b"G"):
                    return "IGES"
        except Exception:  # noqa: BLE001
            pass

        return None
