"""STL / OBJ / 3MF mesh format adapters.

Capability roadmap (all three formats)
---------------------------------------
Pure Python (no external dependencies):
    Level 0 — RECOGNIZED  (magic bytes / header pattern / extension)
    Level 1 — PARSED      (vertex/face count, metadata harvest)

With ``numpy-stl`` (STL) or ``trimesh`` installed:
    Level 2 — NORMALIZED  (CanonicalGeometry mesh populated)

References
----------
STL  — ASCII and binary stereolithography format (public-domain spec)
OBJ  — Wavefront Technologies OBJ/MTL (public-domain spec)
3MF  — 3D Manufacturing Format, Open Specification v1.3 (3MF Consortium)
"""

from __future__ import annotations

import struct
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
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

__all__ = [
    "STL_DESCRIPTOR",
    "OBJ_DESCRIPTOR",
    "THREEMF_DESCRIPTOR",
    "StlAdapter",
    "ObjAdapter",
    "ThreeMfAdapter",
]

# ---------------------------------------------------------------------------
# Format descriptors
# ---------------------------------------------------------------------------

STL_DESCRIPTOR = FormatDescriptor(
    format_id="STL",
    canonical_name="Stereolithography (STL)",
    family=FormatFamily.MESH,
    extensions=("stl",),
    media_types=("model/stl", "application/sla"),
    vendor=None,
    is_open=True,
    is_proprietary=False,
    adapter_license=AdapterLicense.INTERNAL_PARSER,
    notes="ASCII and binary STL; vertex/face count parsed in pure Python.",
)

OBJ_DESCRIPTOR = FormatDescriptor(
    format_id="OBJ",
    canonical_name="Wavefront OBJ",
    family=FormatFamily.MESH,
    extensions=("obj",),
    media_types=("model/obj",),
    vendor="Wavefront Technologies",
    is_open=True,
    is_proprietary=False,
    adapter_license=AdapterLicense.INTERNAL_PARSER,
    notes="ASCII OBJ; vertex/face/normal count and material library parsed.",
)

THREEMF_DESCRIPTOR = FormatDescriptor(
    format_id="3MF",
    canonical_name="3D Manufacturing Format",
    family=FormatFamily.MESH,
    extensions=("3mf",),
    media_types=("model/3mf", "application/vnd.ms-package.3dmanufacturing-3dmodel+xml"),
    vendor="3MF Consortium",
    is_open=True,
    is_proprietary=False,
    adapter_license=AdapterLicense.INTERNAL_PARSER,
    notes="ZIP-based XML mesh format (3MF Consortium Open Specification v1.x).",
)

# ---------------------------------------------------------------------------
# STL adapter
# ---------------------------------------------------------------------------

_STL_BINARY_HEADER = 80
_STL_BINARY_MIN_SIZE = _STL_BINARY_HEADER + 4  # header + triangle count u32


def _parse_stl_bytes(data: bytes) -> dict[str, Any]:
    """Return {'is_binary', 'triangle_count', 'vertex_count'}."""
    result: dict[str, Any] = {"is_binary": False, "triangle_count": 0, "vertex_count": 0}

    # ASCII STL starts with "solid" (possibly preceded by whitespace)
    text_sample = data[:256].lstrip()
    if text_sample[:5].lower() == b"solid":
        # Try ASCII parse
        try:
            text = data.decode("ascii", errors="replace")
            facet_count = text.lower().count("facet normal")
            result["triangle_count"] = facet_count
            result["vertex_count"] = facet_count * 3
            return result
        except Exception:  # noqa: BLE001
            pass

    # Binary STL
    if len(data) < _STL_BINARY_MIN_SIZE:
        return result
    tri_count = struct.unpack_from("<I", data, _STL_BINARY_HEADER)[0]
    expected_size = _STL_BINARY_HEADER + 4 + tri_count * 50
    result["is_binary"] = True
    result["triangle_count"] = tri_count
    result["vertex_count"] = tri_count * 3
    result["expected_size_match"] = len(data) == expected_size
    return result


class StlAdapter(FormatAdapter):
    """Level 0–1 STL mesh adapter (pure Python)."""

    _ADAPTER_ID = "machinerypro-stl-v1"
    _ADAPTER_VERSION = "1.0.0"

    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            adapter_id=self._ADAPTER_ID,
            adapter_name="MachineryPro STL Mesh Adapter",
            adapter_version=self._ADAPTER_VERSION,
            format_ids=("STL",),
            capabilities=(
                AdapterCapability.RECOGNIZE,
                AdapterCapability.PARSE,
                AdapterCapability.NORMALIZE,
            ),
            max_capability_level=CapabilityLevel.LEVEL_1_PARSED,
            adapter_license=AdapterLicense.INTERNAL_PARSER,
            requires_external_dependency=False,
            notes="Pure-Python STL parser; ASCII and binary STL supported.",
        )

    def can_handle(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor | None = None,
    ) -> bool:
        if source.source_format_id == "STL":
            return True
        if format_descriptor and format_descriptor.format_id == "STL":
            return True
        if source.file_name and source.file_name.lower().endswith(".stl"):
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
            session.record(FidelityClass.LOST, "STL content not available")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        try:
            info = _parse_stl_bytes(data)
        except Exception as exc:  # noqa: BLE001
            session.mark_failed()
            session.record(FidelityClass.LOST, f"STL parse error: {exc}")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        session.mark_parsed()
        session.set_source_entity_count(info["triangle_count"])

        ref = CanonicalEntityRef(
            entity_id=make_uid("STL-MESH-"),
            entity_kind="StlMesh",
            metadata={
                "is_binary": info["is_binary"],
                "triangle_count": info["triangle_count"],
                "vertex_count": info["vertex_count"],
            },
        )
        session.add_entity_ref(ref)
        session.set_fidelity_completeness(FidelityReportCompleteness.COMPLETE)
        return session.build()


# ---------------------------------------------------------------------------
# OBJ adapter
# ---------------------------------------------------------------------------

def _parse_obj_text(text: str) -> dict[str, Any]:
    v = vn = vt = f = 0
    mtl_libs: list[str] = []
    object_names: list[str] = []
    for line in text.splitlines():
        tok = line.split()
        if not tok:
            continue
        t = tok[0].lower()
        if t == "v":
            v += 1
        elif t == "vn":
            vn += 1
        elif t == "vt":
            vt += 1
        elif t == "f":
            f += 1
        elif t == "mtllib" and len(tok) > 1:
            mtl_libs.append(tok[1])
        elif t == "o" and len(tok) > 1:
            object_names.append(tok[1])
    return {
        "vertex_count": v,
        "normal_count": vn,
        "texcoord_count": vt,
        "face_count": f,
        "mtl_libs": mtl_libs,
        "object_names": object_names,
    }


class ObjAdapter(FormatAdapter):
    """Level 0–1 Wavefront OBJ mesh adapter (pure Python)."""

    _ADAPTER_ID = "machinerypro-obj-v1"
    _ADAPTER_VERSION = "1.0.0"

    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            adapter_id=self._ADAPTER_ID,
            adapter_name="MachineryPro OBJ Mesh Adapter",
            adapter_version=self._ADAPTER_VERSION,
            format_ids=("OBJ",),
            capabilities=(
                AdapterCapability.RECOGNIZE,
                AdapterCapability.PARSE,
                AdapterCapability.NORMALIZE,
            ),
            max_capability_level=CapabilityLevel.LEVEL_1_PARSED,
            adapter_license=AdapterLicense.INTERNAL_PARSER,
            requires_external_dependency=False,
            notes="Pure-Python OBJ parser; vertex/face/normal counts harvested.",
        )

    def can_handle(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor | None = None,
    ) -> bool:
        if source.source_format_id == "OBJ":
            return True
        if format_descriptor and format_descriptor.format_id == "OBJ":
            return True
        if source.file_name and source.file_name.lower().endswith(".obj"):
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
            session.record(FidelityClass.LOST, "OBJ content not available")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        try:
            text = data.decode("utf-8", errors="replace")
            info = _parse_obj_text(text)
        except Exception as exc:  # noqa: BLE001
            session.mark_failed()
            session.record(FidelityClass.LOST, f"OBJ parse error: {exc}")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        session.mark_parsed()
        session.set_source_entity_count(info["face_count"])

        ref = CanonicalEntityRef(
            entity_id=make_uid("OBJ-MESH-"),
            entity_kind="ObjMesh",
            metadata={
                "vertex_count": info["vertex_count"],
                "normal_count": info["normal_count"],
                "texcoord_count": info["texcoord_count"],
                "face_count": info["face_count"],
                "mtl_libs": info["mtl_libs"],
                "object_names": info["object_names"],
            },
        )
        session.add_entity_ref(ref)
        session.set_fidelity_completeness(FidelityReportCompleteness.COMPLETE)
        return session.build()


# ---------------------------------------------------------------------------
# 3MF adapter
# ---------------------------------------------------------------------------

_3MF_CONTENT_TYPES_PATH = "[Content_Types].xml"
_3MF_MODEL_NAMESPACE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"


def _parse_3mf_bytes(data: bytes) -> dict[str, Any]:
    result: dict[str, Any] = {
        "vertex_count": 0,
        "triangle_count": 0,
        "object_count": 0,
        "metadata": {},
        "is_valid_3mf": False,
    }
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            names = zf.namelist()
            result["is_valid_3mf"] = _3MF_CONTENT_TYPES_PATH in names

            # Find model file (typically 3D/3dmodel.model)
            model_paths = [n for n in names if n.lower().endswith(".model")]
            if not model_paths:
                return result

            model_xml = zf.read(model_paths[0])
            root = ET.fromstring(model_xml)
            ns = {"m": _3MF_MODEL_NAMESPACE}

            # Metadata
            for meta in root.findall("m:metadata", ns):
                name_attr = meta.get("name", "")
                if name_attr:
                    result["metadata"][name_attr] = meta.text or ""

            # Count objects, vertices, triangles
            for obj in root.findall(".//m:object", ns):
                result["object_count"] += 1
                mesh = obj.find("m:mesh", ns)
                if mesh is not None:
                    vertices = mesh.find("m:vertices", ns)
                    triangles = mesh.find("m:triangles", ns)
                    if vertices is not None:
                        result["vertex_count"] += len(list(vertices))
                    if triangles is not None:
                        result["triangle_count"] += len(list(triangles))
    except Exception:  # noqa: BLE001
        pass
    return result


class ThreeMfAdapter(FormatAdapter):
    """Level 0–1 3MF mesh adapter (pure Python; ZIP + XML parsing)."""

    _ADAPTER_ID = "machinerypro-3mf-v1"
    _ADAPTER_VERSION = "1.0.0"

    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            adapter_id=self._ADAPTER_ID,
            adapter_name="MachineryPro 3MF Mesh Adapter",
            adapter_version=self._ADAPTER_VERSION,
            format_ids=("3MF",),
            capabilities=(
                AdapterCapability.RECOGNIZE,
                AdapterCapability.PARSE,
                AdapterCapability.NORMALIZE,
            ),
            max_capability_level=CapabilityLevel.LEVEL_1_PARSED,
            adapter_license=AdapterLicense.INTERNAL_PARSER,
            requires_external_dependency=False,
            notes="Pure-Python 3MF (ZIP+XML); vertex/triangle count harvested.",
        )

    def can_handle(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor | None = None,
    ) -> bool:
        if source.source_format_id == "3MF":
            return True
        if format_descriptor and format_descriptor.format_id == "3MF":
            return True
        if source.file_name and source.file_name.lower().endswith(".3mf"):
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
            session.record(FidelityClass.LOST, "3MF content not available")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        try:
            info = _parse_3mf_bytes(data)
        except Exception as exc:  # noqa: BLE001
            session.mark_failed()
            session.record(FidelityClass.LOST, f"3MF parse error: {exc}")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        if not info["is_valid_3mf"]:
            session.mark_failed()
            session.record(
                FidelityClass.LOST,
                "Not a valid 3MF package (missing [Content_Types].xml)",
            )
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        session.mark_parsed()
        session.set_source_entity_count(info["triangle_count"])

        ref = CanonicalEntityRef(
            entity_id=make_uid("3MF-MESH-"),
            entity_kind="ThreeMfMesh",
            metadata={
                "vertex_count": info["vertex_count"],
                "triangle_count": info["triangle_count"],
                "object_count": info["object_count"],
                "embedded_metadata": info["metadata"],
            },
        )
        session.add_entity_ref(ref)
        session.set_fidelity_completeness(FidelityReportCompleteness.COMPLETE)
        return session.build()


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _bytes_from_source(source: EngineeringSource) -> bytes | None:
    """Extract raw bytes from source.notes (test pathway).

    Uses latin-1 encoding (1:1 byte↔char mapping) so binary content
    round-trips without loss through the str notes field.
    """
    if source.notes:
        return source.notes.encode("latin-1", errors="replace")
    return None
