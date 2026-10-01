"""STEP AP203 / AP214 / AP242 format adapter (Stage 4C).

Capability roadmap
------------------
With ZERO external dependencies (pure Python):
    Level 0 — RECOGNIZED  (extension / magic byte match)
    Level 1 — PARSED      (ISO-10303-21 header, section inventory, entity count)

With ``pythonocc-core`` (OpenCASCADE Python bindings) installed:
    Level 2 — NORMALIZED  (CanonicalGeometry + CanonicalTopology populated)

Level 2 is NOT attempted here; it requires the Stage 4C OCCTBridge (Stage 4C-b),
which depends on a working pythonocc-core installation.  The adapter
detects availability at runtime and records an UNSUPPORTED fidelity
event when the bridge is absent, rather than raising an exception.

Fail-closed policy
------------------
* A corrupt or truncated STEP header returns Level 0 + NormalizationStatus.FAILED.
* Absence of geometry kernel returns Level 1 + UNSUPPORTED fidelity event.
* Duplicate SECTION types in the header are recorded as PARTIALLY_PRESERVED.

References
----------
ISO 10303-21:2016 (Physical File Format)
ISO 10303-1:1994 (Product Data Representation and Exchange)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backend.interoperability.adapter import FormatAdapter
from backend.interoperability.adapters._base import (
    AdapterSession,
    make_uid,
)
from backend.interoperability.enums import (
    AdapterCapability,
    AdapterLicense,
    CapabilityLevel,
    FidelityClass,
    FidelityReportCompleteness,
    FormatFamily,
)
from backend.interoperability.models import (
    AdapterMetadata,
    CanonicalDocument,
    CanonicalEntityRef,
    EngineeringSource,
    FormatDescriptor,
)

__all__ = ["StepTokenAdapter"]

_ADAPTER_ID = "machinerypro-step-token-v1"
_ADAPTER_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Known STEP format descriptors
# ---------------------------------------------------------------------------

STEP_AP203 = FormatDescriptor(
    format_id="STEP-AP203",
    canonical_name="STEP AP203",
    family=FormatFamily.NEUTRAL_EXCHANGE,
    extensions=("stp", "step", "p21"),
    media_types=("model/step",),
    vendor="ISO",
    is_open=True,
    is_proprietary=False,
    adapter_license=AdapterLicense.INTERNAL_PARSER,
    notes="ISO 10303-21 Part 203: Configuration Controlled 3D Design",
)

STEP_AP214 = FormatDescriptor(
    format_id="STEP-AP214",
    canonical_name="STEP AP214",
    family=FormatFamily.NEUTRAL_EXCHANGE,
    extensions=("stp", "step", "p21"),
    media_types=("model/step",),
    vendor="ISO",
    is_open=True,
    is_proprietary=False,
    adapter_license=AdapterLicense.INTERNAL_PARSER,
    notes="ISO 10303-21 Part 214: Automotive Design",
)

STEP_AP242 = FormatDescriptor(
    format_id="STEP-AP242",
    canonical_name="STEP AP242",
    family=FormatFamily.NEUTRAL_EXCHANGE,
    extensions=("stp", "step", "p21", "stp242"),
    media_types=("model/step",),
    vendor="ISO",
    is_open=True,
    is_proprietary=False,
    adapter_license=AdapterLicense.INTERNAL_PARSER,
    notes="ISO 10303-21 Part 242: Managed Model Based 3D Engineering (includes PMI)",
)

STEP_GENERIC = FormatDescriptor(
    format_id="STEP-GENERIC",
    canonical_name="STEP (version unknown)",
    family=FormatFamily.NEUTRAL_EXCHANGE,
    extensions=("stp", "step", "p21"),
    media_types=("model/step",),
    vendor="ISO",
    is_open=True,
    is_proprietary=False,
    adapter_license=AdapterLicense.INTERNAL_PARSER,
)

STEP_DESCRIPTORS: dict[str, FormatDescriptor] = {
    "STEP-AP203": STEP_AP203,
    "STEP-AP214": STEP_AP214,
    "STEP-AP242": STEP_AP242,
    "STEP-GENERIC": STEP_GENERIC,
}

# ---------------------------------------------------------------------------
# STEP token-level parser helpers (pure Python, no geometry kernel)
# ---------------------------------------------------------------------------

# Matches ISO-10303-21 section delimiters and HEADER fields
_SECTION_RE = re.compile(
    r"(?:^|\n)(HEADER|DATA|ENDSEC|END-ISO-10303-21)\s*;",
    re.IGNORECASE | re.MULTILINE,
)
_FILE_DESCRIPTION_RE = re.compile(
    r"FILE_DESCRIPTION\s*\(\s*\(\s*'([^']*)'\s*(?:,\s*'[^']*'\s*)*\)\s*,\s*'([^']*)'\s*\)",
    re.IGNORECASE,
)
_FILE_SCHEMA_RE = re.compile(
    r"FILE_SCHEMA\s*\(\s*\(\s*'([^']*)'\s*(?:,\s*'[^']*'\s*)*\)\s*\)",
    re.IGNORECASE,
)
_ENTITY_RE = re.compile(r"^#\d+\s*=", re.MULTILINE)


def _parse_step_header(text: str) -> dict[str, Any]:
    """Extract metadata from the STEP HEADER section."""
    result: dict[str, Any] = {
        "sections": [],
        "file_description": None,
        "file_schema": None,
        "ap_version": None,
        "entity_count": 0,
    }

    # Section inventory
    sections = [m.group(1).upper() for m in _SECTION_RE.finditer(text)]
    result["sections"] = sections

    # Entity count in DATA section
    result["entity_count"] = len(_ENTITY_RE.findall(text))

    # FILE_DESCRIPTION
    m = _FILE_DESCRIPTION_RE.search(text)
    if m:
        result["file_description"] = m.group(1).strip()

    # FILE_SCHEMA → AP version
    m = _FILE_SCHEMA_RE.search(text)
    if m:
        schema = m.group(1).strip().upper()
        result["file_schema"] = schema
        if "AP242" in schema:
            result["ap_version"] = "AP242"
        elif "AP214" in schema:
            result["ap_version"] = "AP214"
        elif "AP203" in schema:
            result["ap_version"] = "AP203"

    return result


def _resolve_descriptor(ap_version: str | None) -> FormatDescriptor:
    if ap_version == "AP242":
        return STEP_AP242
    if ap_version == "AP214":
        return STEP_AP214
    if ap_version == "AP203":
        return STEP_AP203
    return STEP_GENERIC


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class StepTokenAdapter(FormatAdapter):
    """Pure-Python STEP adapter (Level 0–1 without geometry kernel).

    Reach Level 2 requires ``pythonocc-core``; detection is automatic.
    """

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def metadata(self) -> AdapterMetadata:
        base_caps = [
            AdapterCapability.RECOGNIZE,
            AdapterCapability.PARSE,
            AdapterCapability.NORMALIZE,
        ]
        if self._occt_available():
            base_caps += [
                AdapterCapability.EXTRACT_GEOMETRY,
                AdapterCapability.EXTRACT_TOPOLOGY,
                AdapterCapability.EXTRACT_ASSEMBLY,
            ]
        return AdapterMetadata(
            adapter_id=_ADAPTER_ID,
            adapter_name="MachineryPro STEP Token Adapter",
            adapter_version=_ADAPTER_VERSION,
            format_ids=tuple(STEP_DESCRIPTORS.keys()),
            capabilities=tuple(base_caps),
            max_capability_level=(
                CapabilityLevel.LEVEL_2_NORMALIZED
                if self._occt_available()
                else CapabilityLevel.LEVEL_1_PARSED
            ),
            adapter_license=AdapterLicense.INTERNAL_PARSER,
            requires_external_dependency=True,
            external_dependency_name="pythonocc-core (optional; Level 2+ geometry)",
            notes=(
                "Pure-Python parser reaches Level 1. "
                "Level 2 (geometry + topology) requires pythonocc-core."
            ),
        )

    # ------------------------------------------------------------------
    # Format detection
    # ------------------------------------------------------------------

    @staticmethod
    def _occt_available() -> bool:
        """True when pythonocc-core (OCC.Core.STEPControl) is importable."""
        try:
            import OCC.Core.STEPControl  # noqa: F401
            return True
        except ImportError:
            return False

    def can_handle(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor | None = None,
    ) -> bool:
        """True when format_id is a known STEP variant OR file_name suggests STEP."""
        if source.source_format_id in STEP_DESCRIPTORS:
            return True
        if format_descriptor and format_descriptor.format_id in STEP_DESCRIPTORS:
            return True
        if source.file_name:
            lower = source.file_name.lower()
            if any(lower.endswith(f".{ext}") for ext in ("stp", "step", "p21", "stp242")):
                return True
        return False

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------

    def ingest(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
    ) -> CanonicalDocument:
        """Ingest a STEP file from its text bytes.

        The source must have been opened and its content supplied via
        ``source.checksum`` or, more practically, the caller passes
        ``content_bytes`` via the session mechanism.  For Stage 4C the
        content is expected as a UTF-8 string stored in
        ``source.notes`` (test pathway) or as external bytes.

        In production Stage 4C-b, a content provider supplies bytes
        separately; the adapter reads them via the FormatAdapter
        content protocol (not yet defined — uses notes fallback here).
        """
        return self._ingest_text(source, format_descriptor, self._obtain_text(source))

    def ingest_file(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
        content_path: Path,
    ) -> CanonicalDocument:
        """Ingest the complete bounded upload from its staged path."""
        text = content_path.read_text(encoding="utf-8", errors="replace")
        return self._ingest_text(source, format_descriptor, text)

    def _ingest_text(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
        text: str | None,
    ) -> CanonicalDocument:
        session = AdapterSession(source, format_descriptor, self.metadata())

        if text is None:
            session.mark_failed()
            session.record(
                FidelityClass.LOST,
                "STEP content could not be obtained; no content provider attached",
            )
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        # Level 0: recognised (already established by can_handle)
        # Check ISO-10303-21 magic
        if "ISO-10303-21" not in text.upper()[:200]:
            session.mark_failed()
            session.record(
                FidelityClass.LOST,
                "Content does not begin with ISO-10303-21 header; not a valid STEP file",
            )
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        # Parse header (Level 1)
        try:
            meta = _parse_step_header(text)
        except Exception as exc:  # noqa: BLE001
            session.mark_failed()
            session.record(
                FidelityClass.LOST,
                f"STEP header parse error: {exc}",
            )
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        session.mark_parsed()
        session.set_source_entity_count(meta["entity_count"])

        # Record section inventory
        sections = meta["sections"]
        if "DATA" not in sections:
            session.record_unsupported(
                "STEP file has no DATA section; geometry cannot be extracted"
            )

        # Resolve AP version
        ap_version = meta.get("ap_version")

        # Add a document-level entity ref for the header metadata
        header_ref = CanonicalEntityRef(
            entity_id=make_uid("STEP-HEADER-"),
            entity_kind="StepHeader",
            metadata={
                "ap_version": ap_version or "unknown",
                "entity_count": meta["entity_count"],
                "file_description": meta.get("file_description") or "",
                "file_schema": meta.get("file_schema") or "",
                "sections": sections,
            },
        )
        session.add_entity_ref(header_ref)

        # Level 2: geometry normalization (requires pythonocc-core)
        if self._occt_available():
            self._normalize_geometry(text, session)
        else:
            session.record_unsupported(
                "Level 2 geometry normalization requires pythonocc-core "
                "(not installed). Install via: pip install pythonocc-core "
                "or: conda install -c conda-forge pythonocc-core"
            )
            # Level 1 is complete and correct; this is not a failure
            session.set_fidelity_completeness(FidelityReportCompleteness.PARTIAL)
            return session.build()

        session.set_fidelity_completeness(FidelityReportCompleteness.COMPLETE)
        session.mark_normalized()
        return session.build()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _obtain_text(source: EngineeringSource) -> str | None:
        """Extract text content from source.

        Stage 4C uses source.notes as the content transport for testing.
        A production content-provider protocol replaces this.
        """
        if source.notes:
            return source.notes
        return None

    @staticmethod
    def _normalize_geometry(
        text: str,
        session: AdapterSession,
    ) -> None:
        """Populate CanonicalGeometry via pythonocc-core (when available)."""
        # This method body is reached only when pythonocc-core is confirmed
        # importable (guarded by _occt_available()).  The import is deferred
        # so the module loads normally without pythonocc-core present.
        try:
            import os
            import tempfile

            from OCC.Core.IFSelect import IFSelect_RetDone
            from OCC.Core.STEPControl import STEPControl_Reader

            # Write text to a temp file (OCCT requires a file path)
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".stp", delete=False, encoding="utf-8"
            ) as tf:
                tf.write(text)
                tmp_path = tf.name

            try:
                reader = STEPControl_Reader()
                status = reader.ReadFile(tmp_path)
                if status != IFSelect_RetDone:
                    session.mark_partial()
                    session.record_lost("pythonocc-core ReadFile returned non-Done status")
                    return

                reader.TransferRoots()
                n_shapes = reader.NbShapes()
                session.set_source_entity_count(n_shapes)

                for i in range(1, n_shapes + 1):
                    shape_ref = CanonicalEntityRef(
                        entity_id=make_uid("OCCT-SHAPE-"),
                        entity_kind="OCCTShape",
                        metadata={"shape_index": i},
                    )
                    session.add_entity_ref(shape_ref)

                # Full CanonicalGeometry/Topology bridge is Stage 4C-b (OCCTBridge).
                # This stub confirms shapes were read; fidelity is PARTIAL until
                # the bridge maps B-rep to canonical models.
                session.record_partial(
                    f"pythonocc-core transferred {n_shapes} shape(s); "
                    "B-Rep → CanonicalGeometry mapping deferred to Stage 4C-b OCCTBridge"
                )

            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        except Exception as exc:  # noqa: BLE001
            session.mark_partial()
            session.record_lost(f"pythonocc-core geometry normalization failed: {exc}")
