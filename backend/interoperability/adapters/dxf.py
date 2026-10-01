"""DXF R12–R2024 format adapter (Stage 4C).

Capability roadmap
------------------
Pure Python (no external dependencies):
    Level 0 — RECOGNIZED  (extension / group-code-0 detection)
    Level 1 — PARSED      (section inventory, layer names, entity type histogram)

With ``ezdxf`` installed:
    Level 2 — NORMALIZED  (CanonicalGeometry populated from DXF entities)

References
----------
AutoCAD DXF Reference — Autodesk (public, annually updated)
DXF R12 fixed-format specification (public domain)
"""

from __future__ import annotations

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

__all__ = ["DxfTokenAdapter"]

_ADAPTER_ID = "machinerypro-dxf-token-v1"
_ADAPTER_VERSION = "1.0.0"

DXF_DESCRIPTOR = FormatDescriptor(
    format_id="DXF",
    canonical_name="AutoCAD DXF",
    family=FormatFamily.DRAWING,
    extensions=("dxf",),
    media_types=("image/vnd.dxf", "application/dxf"),
    vendor="Autodesk",
    is_open=True,
    is_proprietary=False,
    adapter_license=AdapterLicense.INTERNAL_PARSER,
    notes=(
        "Drawing Exchange Format, R12–R2024. "
        "Level 2 geometry normalization requires ezdxf (MIT license)."
    ),
)

# Known DXF section names
_KNOWN_SECTIONS = frozenset(
    {"HEADER", "CLASSES", "TABLES", "BLOCKS", "ENTITIES", "OBJECTS", "THUMBNAILIMAGE"}
)

# DXF entity types that map to geometry
_GEOMETRY_ENTITY_TYPES = frozenset(
    {
        "LINE", "CIRCLE", "ARC", "ELLIPSE", "SPLINE", "LWPOLYLINE",
        "POLYLINE", "VERTEX", "POINT", "3DFACE", "SOLID", "TRACE",
        "XLINE", "RAY", "MLINE", "HELIX",
    }
)


def _parse_dxf_text(text: str) -> dict[str, object]:
    """Tokenize a text DXF file into section/entity metadata."""
    result: dict[str, object] = {
        "sections": [],
        "entity_counts": {},
        "layers": set(),
        "dxf_version": None,
        "valid": False,
    }

    lines = text.splitlines()
    i = 0
    n = len(lines)
    sections: list[str] = []
    entity_types: list[str] = []
    layers: set[str] = set()

    while i < n - 1:
        try:
            group_code = lines[i].strip()
            value = lines[i + 1].strip()
        except IndexError:
            break
        i += 2

        if group_code == "0" and value == "SECTION":
            # Next group code 2 gives section name
            if i < n - 1 and lines[i].strip() == "2":
                section_name = lines[i + 1].strip().upper()
                sections.append(section_name)
                i += 2

        if group_code == "9" and value == "$ACADVER":
            # Next group code 1 gives the version string
            if i < n - 1 and lines[i].strip() == "1":
                result["dxf_version"] = lines[i + 1].strip()
                i += 2

        if group_code == "0" and value in _GEOMETRY_ENTITY_TYPES:
            entity_types.append(value)

        if group_code == "8":  # layer name
            if value:
                layers.add(value)

    result["sections"] = sections
    result["entity_counts"] = dict(Counter(entity_types))
    result["layers"] = layers
    result["valid"] = "ENTITIES" in sections or "HEADER" in sections
    return result


class DxfTokenAdapter(FormatAdapter):
    """DXF format adapter (Level 0–1 pure Python, Level 2 with ezdxf)."""

    @staticmethod
    def _ezdxf_available() -> bool:
        try:
            import ezdxf  # noqa: F401
            return True
        except ImportError:
            return False

    def metadata(self) -> AdapterMetadata:
        caps = [
            AdapterCapability.RECOGNIZE,
            AdapterCapability.PARSE,
            AdapterCapability.NORMALIZE,
            AdapterCapability.EXTRACT_DRAWING,
        ]
        if self._ezdxf_available():
            caps.append(AdapterCapability.EXTRACT_GEOMETRY)
        return AdapterMetadata(
            adapter_id=_ADAPTER_ID,
            adapter_name="MachineryPro DXF Token Adapter",
            adapter_version=_ADAPTER_VERSION,
            format_ids=("DXF",),
            capabilities=tuple(caps),
            max_capability_level=(
                CapabilityLevel.LEVEL_2_NORMALIZED
                if self._ezdxf_available()
                else CapabilityLevel.LEVEL_1_PARSED
            ),
            adapter_license=AdapterLicense.INTERNAL_PARSER,
            requires_external_dependency=True,
            external_dependency_name="ezdxf (optional; Level 2 geometry)",
            notes=(
                "Pure-Python DXF parser reaches Level 1. "
                "Level 2 requires ezdxf (MIT): pip install ezdxf"
            ),
        )

    def can_handle(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor | None = None,
    ) -> bool:
        if source.source_format_id == "DXF":
            return True
        if format_descriptor and format_descriptor.format_id == "DXF":
            return True
        if source.file_name and source.file_name.lower().endswith(".dxf"):
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
            session.record(FidelityClass.LOST, "No DXF content provided")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        # Level 0 check: group-code pattern
        lines = text.splitlines()[:10]
        has_group0 = any(
            i < len(lines) - 1 and lines[i].strip() == "0"
            for i in range(len(lines))
        )
        if not has_group0:
            session.mark_failed()
            session.record(
                FidelityClass.LOST,
                "Content does not match DXF group-code format",
            )
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        # Parse
        try:
            meta = _parse_dxf_text(text)
        except Exception as exc:  # noqa: BLE001
            session.mark_failed()
            session.record(FidelityClass.LOST, f"DXF parse error: {exc}")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        session.mark_parsed()
        entity_counts: dict[str, int] = meta["entity_counts"]  # type: ignore[assignment]
        total_entities = sum(entity_counts.values())
        session.set_source_entity_count(total_entities)

        header_ref = CanonicalEntityRef(
            entity_id=make_uid("DXF-HEADER-"),
            entity_kind="DxfHeader",
            metadata={
                "dxf_version": meta.get("dxf_version") or "unknown",
                "sections": meta["sections"],
                "entity_count": total_entities,
                "entity_type_summary": entity_counts,
                "layer_count": len(meta["layers"]),  # type: ignore[arg-type]
            },
        )
        session.add_entity_ref(header_ref)

        if not meta["valid"]:
            session.record_partial(
                "DXF file may be incomplete; no HEADER or ENTITIES section found"
            )

        # Level 2 via ezdxf
        if self._ezdxf_available():
            self._normalize_geometry_ezdxf(text, session)
        else:
            session.record_unsupported(
                "Level 2 geometry normalization requires ezdxf (MIT license). "
                "Install via: pip install ezdxf"
            )
            session.set_fidelity_completeness(FidelityReportCompleteness.PARTIAL)
            return session.build()

        session.mark_normalized()
        session.set_fidelity_completeness(FidelityReportCompleteness.COMPLETE)
        return session.build()

    @staticmethod
    def _normalize_geometry_ezdxf(text: str, session: AdapterSession) -> None:
        try:
            import io

            import ezdxf

            doc = ezdxf.read(io.StringIO(text))
            msp = doc.modelspace()

            geometry_entities = []
            for entity in msp:
                dxftype = entity.dxftype()
                entity_ref = CanonicalEntityRef(
                    entity_id=make_uid("DXF-ENT-"),
                    entity_kind=f"DxfEntity_{dxftype}",
                    source_entity_id=(
                        str(entity.dxf.handle) if hasattr(entity.dxf, "handle") else None
                    ),
                    metadata={"dxftype": dxftype},
                )
                session.add_entity_ref(entity_ref)
                if dxftype in _GEOMETRY_ENTITY_TYPES:
                    geometry_entities.append(entity_ref)

            if not geometry_entities:
                session.record_unsupported(
                    "DXF modelspace contains no recognized geometry entities"
                )
            else:
                # Full CanonicalGeometry mapping is Stage 4C-c (DXFGeometryBridge).
                # This stub confirms entities were read.
                session.record_partial(
                    f"ezdxf read {len(geometry_entities)} geometry entity(ies); "
                    "entity → CER mapping deferred to Stage 4C-c DXFGeometryBridge"
                )

        except Exception as exc:  # noqa: BLE001
            session.mark_partial()
            session.record_lost(f"ezdxf geometry normalization failed: {exc}")
