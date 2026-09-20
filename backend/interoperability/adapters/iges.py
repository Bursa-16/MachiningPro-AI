"""IGES 5.x format adapter (Stage 4C).

Capability roadmap
------------------
Pure Python (no external dependencies):
    Level 0 — RECOGNIZED  (extension / header pattern)
    Level 1 — PARSED      (section inventory, directory entries, entity type histogram)

Level 2 geometry normalization requires pythonocc-core (same bridge as STEP).

References
----------
IGES 5.3 (1996) — Initial Graphics Exchange Specification
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

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

__all__ = ["IgesTokenAdapter"]

_ADAPTER_ID = "machinerypro-iges-token-v1"
_ADAPTER_VERSION = "1.0.0"

IGES_DESCRIPTOR = FormatDescriptor(
    format_id="IGES",
    canonical_name="IGES 5.x",
    family=FormatFamily.NEUTRAL_EXCHANGE,
    extensions=("igs", "iges"),
    media_types=("model/iges",),
    vendor="ANSI",
    is_open=True,
    is_proprietary=False,
    adapter_license=AdapterLicense.INTERNAL_PARSER,
    notes="ANSI/ASME Y14.26M — Initial Graphics Exchange Specification",
)

# IGES section codes (column 73)
_SECTION_CODES = {"S", "G", "D", "P", "T"}

# Directory-entry entity type number is columns 1–8 of the D-section
_DE_TYPE_RE = re.compile(r"^(.{8})(.{8})", re.MULTILINE)

# Known IGES entity type numbers → descriptive name
_IGES_ENTITY_NAMES: dict[int, str] = {
    100: "Circular Arc",
    102: "Composite Curve",
    104: "Conic Arc",
    106: "Copious Data",
    108: "Plane",
    110: "Line",
    112: "Parametric Spline Curve",
    114: "Parametric Spline Surface",
    116: "Point",
    118: "Ruled Surface",
    120: "Surface of Revolution",
    122: "Tabulated Cylinder",
    124: "Transformation Matrix",
    126: "Rational B-Spline Curve",
    128: "Rational B-Spline Surface",
    130: "Offset Curve",
    140: "Offset Surface",
    142: "Curve on Parametric Surface",
    143: "Bounded Surface",
    144: "Trimmed Surface",
    186: "Manifold Solid B-Rep Object",
    190: "Plane Surface",
    192: "Right Circular Cylindrical Surface",
    194: "Right Circular Conical Surface",
    196: "Spherical Surface",
    198: "Toroidal Surface",
    308: "Subfigure Definition",
    314: "Color Definition",
    402: "Associativity Instance",
    408: "Singular Subfigure Instance",
    504: "Edge",
    508: "Loop",
    510: "Face",
    514: "Shell",
}


def _parse_iges_sections(text: str) -> dict[str, object]:
    """Parse an IGES file into section lines and entity histogram."""
    lines = text.splitlines()
    result: dict[str, object] = {
        "sections": set(),
        "entity_type_counts": {},
        "global_section_params": None,
        "line_count": len(lines),
        "valid": False,
    }

    d_lines: list[str] = []
    g_lines: list[str] = []
    entity_types: list[int] = []

    for line in lines:
        if len(line) < 73:
            continue
        code = line[72]
        if code not in _SECTION_CODES:
            continue
        result["sections"].add(code)  # type: ignore[union-attr]
        if code == "D":
            d_lines.append(line)
        elif code == "G":
            g_lines.append(line[:72])

    # Extract entity type numbers from D-section (every other line is an entry)
    for line in d_lines[::2]:  # type 1 lines are even-indexed
        raw = line[:8].strip()
        try:
            entity_types.append(int(raw))
        except ValueError:
            pass

    counts = Counter(entity_types)
    result["entity_type_counts"] = dict(counts)
    result["valid"] = "S" in result["sections"] and "G" in result["sections"]

    if g_lines:
        result["global_section_params"] = " ".join(g_lines)

    return result


class IgesTokenAdapter(FormatAdapter):
    """Pure-Python IGES adapter (Level 0–1)."""

    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            adapter_id=_ADAPTER_ID,
            adapter_name="MachineryPro IGES Token Adapter",
            adapter_version=_ADAPTER_VERSION,
            format_ids=("IGES",),
            capabilities=(
                AdapterCapability.RECOGNIZE,
                AdapterCapability.PARSE,
                AdapterCapability.NORMALIZE,
            ),
            max_capability_level=CapabilityLevel.LEVEL_1_PARSED,
            adapter_license=AdapterLicense.INTERNAL_PARSER,
            requires_external_dependency=False,
            notes=(
                "Pure-Python IGES parser reaches Level 1 (section inventory, "
                "entity type histogram). Level 2 geometry requires pythonocc-core."
            ),
        )

    def can_handle(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor | None = None,
    ) -> bool:
        if source.source_format_id == "IGES":
            return True
        if format_descriptor and format_descriptor.format_id == "IGES":
            return True
        if source.file_name:
            lower = source.file_name.lower()
            if lower.endswith(".igs") or lower.endswith(".iges"):
                return True
        return False

    def ingest(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
    ) -> CanonicalDocument:
        return self._ingest_text(source, format_descriptor, source.notes)

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

        if not text:
            session.mark_failed()
            session.record(FidelityClass.LOST, "No IGES content provided")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        # Basic validity
        if not any(
            len(line) >= 73 and line[72] in _SECTION_CODES
            for line in text.splitlines()[:10]
            if len(line) >= 73
        ):
            session.mark_failed()
            session.record(
                FidelityClass.LOST,
                "Content does not match IGES 80-column fixed-format structure",
            )
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        # Parse sections
        try:
            meta = _parse_iges_sections(text)
        except Exception as exc:  # noqa: BLE001
            session.mark_failed()
            session.record(FidelityClass.LOST, f"IGES section parse error: {exc}")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        session.mark_parsed()
        entity_counts: dict[int, int] = meta["entity_type_counts"]  # type: ignore[assignment]
        total_entities = sum(entity_counts.values())
        session.set_source_entity_count(total_entities)

        # Header ref
        header_ref = CanonicalEntityRef(
            entity_id=make_uid("IGES-HEADER-"),
            entity_kind="IgesHeader",
            metadata={
                "sections": sorted(meta["sections"]),  # type: ignore[arg-type]
                "entity_count": total_entities,
                "entity_type_summary": {
                    _IGES_ENTITY_NAMES.get(k, f"type_{k}"): v
                    for k, v in entity_counts.items()
                },
            },
        )
        session.add_entity_ref(header_ref)

        # Note unsupported section types
        if "D" not in meta["sections"]:
            session.record_unsupported("IGES file lacks a Directory section; no entities found")
        if "P" not in meta["sections"]:
            session.record_unsupported(
                "IGES file lacks a Parameter section; geometry cannot be extracted"
            )

        # Record unsupported entity types (complex surfaces, PMI, etc.)
        unsupported = {
            k: v for k, v in entity_counts.items()
            if k not in _IGES_ENTITY_NAMES
        }
        if unsupported:
            session.record_unsupported(
                f"IGES file contains {sum(unsupported.values())} entities "
                f"of unrecognised types: {list(unsupported.keys())}"
            )

        # Geometry requires pythonocc-core
        session.record_unsupported(
            "Level 2 geometry normalization requires pythonocc-core "
            "(not installed). Install via: conda install -c conda-forge pythonocc-core"
        )
        session.set_fidelity_completeness(FidelityReportCompleteness.PARTIAL)
        return session.build()
