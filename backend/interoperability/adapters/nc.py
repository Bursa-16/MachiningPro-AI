"""NC / G-code / TAP format adapter.

Capability roadmap
------------------
Pure Python (no external dependencies):
    Level 0 — RECOGNIZED  (extension match + heuristic content probe)
    Level 1 — PARSED      (block count, modal groups harvested, program numbers)

With optional dialect plugins:
    Level 2 — NORMALIZED  (motion blocks mapped to toolpath segments)
    Level 5 — PROCESS_CONTENT  (feed/speed/tool extracted per block)

Supported extension families:
    .nc, .gcode, .g, .tap, .cnc, .ngc, .mpf, .min, .nc1

References
----------
ISO 6983-1:2009 (G-code / M-code base standard)
EIA-274-D (historical RS-274-D / G-code)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backend.interoperability.adapter import FormatAdapter
from backend.interoperability.adapters._base import AdapterSession, make_uid
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

__all__ = ["NC_DESCRIPTOR", "NcAdapter"]

# ---------------------------------------------------------------------------
# Format descriptors
# ---------------------------------------------------------------------------

NC_DESCRIPTOR = FormatDescriptor(
    format_id="NC-GCODE",
    canonical_name="NC / G-code program",
    family=FormatFamily.NC,
    extensions=("nc", "gcode", "g", "tap", "cnc", "ngc", "mpf", "min", "nc1"),
    media_types=("text/x-gcode",),
    vendor=None,
    is_open=True,
    is_proprietary=False,
    adapter_license=AdapterLicense.INTERNAL_PARSER,
    notes=(
        "ISO 6983-1 G/M-code programs. Block count, modal codes, "
        "program number extracted in pure Python."
    ),
)

# ---------------------------------------------------------------------------
# NC parse helpers
# ---------------------------------------------------------------------------

_NC_EXTENSIONS = frozenset(
    ("nc", "gcode", "g", "tap", "cnc", "ngc", "mpf", "min", "nc1")
)

# Block (line) patterns
_BLOCK_RE = re.compile(r"^\s*(?:N\d+\s+)?([A-Z][^;%\n]*)", re.IGNORECASE | re.MULTILINE)
_GCODE_RE = re.compile(r"G(\d+(?:\.\d+)?)", re.IGNORECASE)
_MCODE_RE = re.compile(r"M(\d+)", re.IGNORECASE)
_PROGRAM_NO_RE = re.compile(r"(?:^|\n)\s*(?:O|%)\s*(\d+)", re.IGNORECASE)
_TOOL_RE = re.compile(r"T(\d+)", re.IGNORECASE)
_FEED_RE = re.compile(r"F([\d.]+)", re.IGNORECASE)
_SPEED_RE = re.compile(r"S([\d.]+)", re.IGNORECASE)


def _probe_nc_content(data: bytes) -> bool:
    """Heuristic: returns True when data looks like G-code."""
    try:
        text = data[:1024].decode("ascii", errors="replace").upper()
    except Exception:  # noqa: BLE001
        return False
    # Any G/M-code block strongly indicates NC
    if re.search(r"\bG\d+\b|\bM\d+\b", text):
        return True
    # Program number (O-word or %)
    if re.search(r"(?:^|\n)\s*[O%]\d+", text):
        return True
    return False


def _parse_nc_text(text: str) -> dict[str, Any]:
    g_codes: set[str] = set()
    m_codes: set[str] = set()
    tools: set[str] = set()
    feeds: list[float] = []
    speeds: list[float] = []

    for m in _GCODE_RE.finditer(text):
        g_codes.add(m.group(1))
    for m in _MCODE_RE.finditer(text):
        m_codes.add(m.group(1))
    for m in _TOOL_RE.finditer(text):
        tools.add(m.group(1))
    for m in _FEED_RE.finditer(text):
        try:
            feeds.append(float(m.group(1)))
        except ValueError:
            pass
    for m in _SPEED_RE.finditer(text):
        try:
            speeds.append(float(m.group(1)))
        except ValueError:
            pass

    # Program numbers
    program_numbers = [m.group(1) for m in _PROGRAM_NO_RE.finditer(text)]

    # Block count (non-empty, non-comment lines)
    block_count = sum(
        1 for line in text.splitlines()
        if line.strip() and not line.strip().startswith(";")
        and not line.strip().startswith("(")
    )

    return {
        "block_count": block_count,
        "g_codes": sorted(g_codes),
        "m_codes": sorted(m_codes),
        "tool_numbers": sorted(tools),
        "program_numbers": program_numbers,
        "feed_values": feeds,
        "speed_values": speeds,
    }


class NcAdapter(FormatAdapter):
    """Level 0–1 NC/G-code adapter (pure Python, dialect-agnostic)."""

    _ADAPTER_ID = "machinerypro-nc-gcode-v1"
    _ADAPTER_VERSION = "1.0.0"

    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            adapter_id=self._ADAPTER_ID,
            adapter_name="MachineryPro NC/G-code Adapter",
            adapter_version=self._ADAPTER_VERSION,
            format_ids=("NC-GCODE",),
            capabilities=(
                AdapterCapability.RECOGNIZE,
                AdapterCapability.PARSE,
                AdapterCapability.NORMALIZE,
                AdapterCapability.EXTRACT_NC,
            ),
            max_capability_level=CapabilityLevel.LEVEL_1_PARSED,
            adapter_license=AdapterLicense.INTERNAL_PARSER,
            requires_external_dependency=False,
            notes=(
                "Dialect-agnostic ISO 6983-1 parser. Block count, modal groups, "
                "program numbers, tool/feed/speed harvested. "
                "Controller-specific dialect plugins extend to Level 2+."
            ),
        )

    def can_handle(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor | None = None,
    ) -> bool:
        if source.source_format_id == "NC-GCODE":
            return True
        if format_descriptor and format_descriptor.format_id == "NC-GCODE":
            return True
        if source.file_name:
            ext = source.file_name.rsplit(".", 1)[-1].lower() if "." in source.file_name else ""
            if ext in _NC_EXTENSIONS:
                return True
        return False

    def ingest(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
    ) -> CanonicalDocument:
        data = _bytes_from_source(source)
        return self._ingest_bytes(source, format_descriptor, data)

    def ingest_file(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
        content_path: Path,
    ) -> CanonicalDocument:
        return self._ingest_bytes(source, format_descriptor, content_path.read_bytes())

    def _ingest_bytes(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
        data: bytes | None,
    ) -> CanonicalDocument:
        session = AdapterSession(source, format_descriptor, self.metadata())

        if not data:
            session.mark_failed()
            session.record(FidelityClass.LOST, "NC content not available")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        # Content probe
        if not _probe_nc_content(data):
            session.record_inferred(
                "Content does not contain recognizable G/M-code blocks; "
                "proceeding with best-effort parse."
            )

        try:
            text = data.decode("utf-8", errors="replace")
            info = _parse_nc_text(text)
        except Exception as exc:  # noqa: BLE001
            session.mark_failed()
            session.record(FidelityClass.LOST, f"NC parse error: {exc}")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        session.mark_parsed()
        session.set_source_entity_count(info["block_count"])

        ref = CanonicalEntityRef(
            entity_id=make_uid("NC-PROG-"),
            entity_kind="NcProgram",
            metadata={
                "block_count": info["block_count"],
                "g_codes": info["g_codes"],
                "m_codes": info["m_codes"],
                "tool_numbers": info["tool_numbers"],
                "program_numbers": info["program_numbers"],
                "feed_count": len(info["feed_values"]),
                "speed_count": len(info["speed_values"]),
            },
        )
        session.add_entity_ref(ref)
        session.set_fidelity_completeness(FidelityReportCompleteness.COMPLETE)
        return session.build()


def _bytes_from_source(source: EngineeringSource) -> bytes | None:
    if source.notes:
        return source.notes.encode("utf-8", errors="replace")
    return None
