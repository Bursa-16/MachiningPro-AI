"""Raster image and SVG format adapters.

Handles: PNG, JPG/JPEG, TIFF, BMP, SVG

Capability roadmap
------------------
Pure Python (stdlib only):
    Level 0 — RECOGNIZED  (magic bytes / extension / XML namespace probe)
    Level 1 — PARSED      (image dimensions, bit depth, colour mode, metadata)

With ``Pillow`` installed (PNG/JPG/TIFF/BMP):
    Level 2 — NORMALIZED  (full ImageInfo populated with PIL metadata dict)

SVG is XML-only — parsed with stdlib xml.etree; no external dependency.

Use case in MachineryPro
------------------------
Standalone raster images (scanned drawings, inspection photos) ingested as
DRAWING-family sources for downstream VLM / OCR analysis pipelines.
SVG technical drawings ingested for vector content extraction.
"""

from __future__ import annotations

import struct
import xml.etree.ElementTree as ET
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
    "RASTER_DESCRIPTOR",
    "SVG_DESCRIPTOR",
    "RasterImageAdapter",
    "SvgAdapter",
]

# ---------------------------------------------------------------------------
# Format descriptors
# ---------------------------------------------------------------------------

RASTER_DESCRIPTOR = FormatDescriptor(
    format_id="RASTER-IMAGE",
    canonical_name="Raster Image (PNG/JPG/JPEG/TIFF/BMP)",
    family=FormatFamily.IMAGE,
    extensions=("png", "jpg", "jpeg", "tif", "tiff", "bmp"),
    media_types=(
        "image/png",
        "image/jpeg",
        "image/tiff",
        "image/bmp",
    ),
    vendor=None,
    is_open=True,
    is_proprietary=False,
    adapter_license=AdapterLicense.INTERNAL_PARSER,
    notes=(
        "PNG/JPG/TIFF/BMP raster images. Dimensions extracted via magic bytes "
        "in pure Python; full metadata via Pillow when available."
    ),
)

SVG_DESCRIPTOR = FormatDescriptor(
    format_id="SVG",
    canonical_name="Scalable Vector Graphics (SVG)",
    family=FormatFamily.IMAGE,
    extensions=("svg",),
    media_types=("image/svg+xml",),
    vendor="W3C",
    is_open=True,
    is_proprietary=False,
    adapter_license=AdapterLicense.INTERNAL_PARSER,
    notes="W3C SVG 1.1/2.0 vector image; parsed with stdlib xml.etree.",
)

# ---------------------------------------------------------------------------
# Magic-byte detection helpers
# ---------------------------------------------------------------------------

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_BMP_MAGIC = b"BM"
_TIFF_LE_MAGIC = b"II\x2a\x00"
_TIFF_BE_MAGIC = b"MM\x00\x2a"

_RASTER_EXTENSIONS = frozenset(("png", "jpg", "jpeg", "tif", "tiff", "bmp"))


def _detect_raster_format(data: bytes) -> str | None:
    """Return format tag from magic bytes or None."""
    if data[:8] == _PNG_MAGIC:
        return "PNG"
    if data[:3] == _JPEG_MAGIC:
        return "JPEG"
    if data[:2] == _BMP_MAGIC:
        return "BMP"
    if data[:4] in (_TIFF_LE_MAGIC, _TIFF_BE_MAGIC):
        return "TIFF"
    return None


def _parse_png_dimensions(data: bytes) -> tuple[int, int] | None:
    """Return (width, height) from PNG IHDR chunk."""
    if len(data) < 24:
        return None
    try:
        w = struct.unpack_from(">I", data, 16)[0]
        h = struct.unpack_from(">I", data, 20)[0]
        return w, h
    except struct.error:
        return None


def _parse_jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    """Scan JFIF/EXIF SOF markers for dimensions."""
    i = 2
    while i < len(data) - 8:
        if data[i] != 0xFF:
            break
        marker = data[i + 1]
        # SOF markers: 0xC0-0xC3, 0xC5-0xC7, 0xC9-0xCB, 0xCD-0xCF
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h = struct.unpack_from(">H", data, i + 5)[0]
            w = struct.unpack_from(">H", data, i + 7)[0]
            return w, h
        length = struct.unpack_from(">H", data, i + 2)[0]
        i += 2 + length
    return None


def _parse_bmp_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 26:
        return None
    try:
        w = struct.unpack_from("<I", data, 18)[0]
        h = struct.unpack_from("<I", data, 22)[0]
        return w, abs(h)  # height may be negative (top-down DIB)
    except struct.error:
        return None


def _parse_tiff_dimensions(data: bytes) -> tuple[int, int] | None:
    """Read the first IFD for ImageWidth (256) and ImageLength (257)."""
    if len(data) < 8:
        return None
    try:
        endian = "<" if data[:2] == b"II" else ">"
        offset = struct.unpack_from(endian + "I", data, 4)[0]
        if offset + 2 > len(data):
            return None
        n_entries = struct.unpack_from(endian + "H", data, offset)[0]
        w = h = None
        for i in range(n_entries):
            entry_offset = offset + 2 + i * 12
            if entry_offset + 12 > len(data):
                break
            tag = struct.unpack_from(endian + "H", data, entry_offset)[0]
            dtype = struct.unpack_from(endian + "H", data, entry_offset + 2)[0]
            val_offset = entry_offset + 8
            if dtype == 3:  # SHORT
                val = struct.unpack_from(endian + "H", data, val_offset)[0]
            elif dtype == 4:  # LONG
                val = struct.unpack_from(endian + "I", data, val_offset)[0]
            else:
                continue
            if tag == 256:
                w = val
            elif tag == 257:
                h = val
        if w and h:
            return w, h
    except Exception:  # noqa: BLE001
        pass
    return None


def _extract_raster_info_pure(data: bytes, fmt: str) -> dict[str, Any]:
    info: dict[str, Any] = {"format": fmt, "width": None, "height": None}
    dims: tuple[int, int] | None = None
    if fmt == "PNG":
        dims = _parse_png_dimensions(data)
    elif fmt == "JPEG":
        dims = _parse_jpeg_dimensions(data)
    elif fmt == "BMP":
        dims = _parse_bmp_dimensions(data)
    elif fmt == "TIFF":
        dims = _parse_tiff_dimensions(data)
    if dims:
        info["width"], info["height"] = dims
    return info


def _extract_raster_info_pillow(data: bytes) -> dict[str, Any]:
    """Use Pillow for richer metadata extraction when available."""
    try:
        from io import BytesIO

        from PIL import Image  # type: ignore[import-untyped]

        img = Image.open(BytesIO(data))
        img.load()
        return {
            "format": img.format or "UNKNOWN",
            "width": img.width,
            "height": img.height,
            "mode": img.mode,
            "info_keys": list(img.info.keys()),
        }
    except Exception:  # noqa: BLE001
        return {}


# ---------------------------------------------------------------------------
# Raster image adapter
# ---------------------------------------------------------------------------


class RasterImageAdapter(FormatAdapter):
    """Level 0–1 adapter for PNG, JPG/JPEG, TIFF, BMP images."""

    _ADAPTER_ID = "machinerypro-raster-image-v1"
    _ADAPTER_VERSION = "1.0.0"

    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            adapter_id=self._ADAPTER_ID,
            adapter_name="MachineryPro Raster Image Adapter",
            adapter_version=self._ADAPTER_VERSION,
            format_ids=("RASTER-IMAGE",),
            capabilities=(
                AdapterCapability.RECOGNIZE,
                AdapterCapability.PARSE,
                AdapterCapability.NORMALIZE,
                AdapterCapability.EXTRACT_DRAWING,
            ),
            max_capability_level=CapabilityLevel.LEVEL_1_PARSED,
            adapter_license=AdapterLicense.INTERNAL_PARSER,
            requires_external_dependency=False,
            notes=(
                "Raster image dimensions from magic bytes (pure Python). "
                "Pillow used for full metadata when available."
            ),
        )

    def can_handle(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor | None = None,
    ) -> bool:
        if source.source_format_id == "RASTER-IMAGE":
            return True
        if format_descriptor and format_descriptor.format_id == "RASTER-IMAGE":
            return True
        if source.file_name:
            ext = source.file_name.rsplit(".", 1)[-1].lower() if "." in source.file_name else ""
            if ext in _RASTER_EXTENSIONS:
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
            session.record(FidelityClass.LOST, "Raster image content not available")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        fmt = _detect_raster_format(data)
        if fmt is None:
            session.record_inferred(
                "Magic bytes not recognized as PNG/JPEG/BMP/TIFF; "
                "falling back to extension-based identification."
            )
            # Extension fallback
            if source.file_name:
                ext = source.file_name.rsplit(".", 1)[-1].lower()
                ext_map = {"png": "PNG", "jpg": "JPEG", "jpeg": "JPEG",
                           "tif": "TIFF", "tiff": "TIFF", "bmp": "BMP"}
                fmt = ext_map.get(ext)
            if fmt is None:
                session.mark_failed()
                session.record(
                    FidelityClass.LOST,
                    "Cannot identify raster format from magic bytes or extension",
                )
                session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
                return session.build()

        # Try Pillow first; fall back to pure-Python header read
        pillow_info = _extract_raster_info_pillow(data)
        if pillow_info.get("width"):
            info = pillow_info
            info.setdefault("format", fmt)
        else:
            info = _extract_raster_info_pure(data, fmt)

        session.mark_parsed()
        session.set_source_entity_count(1)

        ref = CanonicalEntityRef(
            entity_id=make_uid("RASTER-IMG-"),
            entity_kind="RasterImage",
            metadata={
                "raster_format": info.get("format", fmt),
                "width": info.get("width"),
                "height": info.get("height"),
                "mode": info.get("mode"),
                "has_pillow_metadata": bool(pillow_info.get("info_keys")),
            },
        )
        session.add_entity_ref(ref)
        session.set_fidelity_completeness(FidelityReportCompleteness.COMPLETE)
        return session.build()


# ---------------------------------------------------------------------------
# SVG adapter
# ---------------------------------------------------------------------------

_SVG_NAMESPACE = "http://www.w3.org/2000/svg"


def _parse_svg_bytes(data: bytes) -> dict[str, Any]:
    result: dict[str, Any] = {
        "width": None,
        "height": None,
        "viewBox": None,
        "element_count": 0,
        "has_svg_namespace": False,
    }
    try:
        text = data.decode("utf-8", errors="replace")
        # Quick probe for SVG namespace
        if "svg" in text[:512].lower():
            result["has_svg_namespace"] = True
        root = ET.fromstring(data)
        result["width"] = root.get("width")
        result["height"] = root.get("height")
        result["viewBox"] = root.get("viewBox")
        result["element_count"] = sum(1 for _ in root.iter())
        if root.tag in (
            "svg",
            f"{{{_SVG_NAMESPACE}}}svg",
            "{http://www.w3.org/2000/svg}svg",
        ):
            result["has_svg_namespace"] = True
    except Exception:  # noqa: BLE001
        pass
    return result


class SvgAdapter(FormatAdapter):
    """Level 0–1 SVG vector drawing adapter (stdlib xml.etree only)."""

    _ADAPTER_ID = "machinerypro-svg-v1"
    _ADAPTER_VERSION = "1.0.0"

    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            adapter_id=self._ADAPTER_ID,
            adapter_name="MachineryPro SVG Adapter",
            adapter_version=self._ADAPTER_VERSION,
            format_ids=("SVG",),
            capabilities=(
                AdapterCapability.RECOGNIZE,
                AdapterCapability.PARSE,
                AdapterCapability.NORMALIZE,
                AdapterCapability.EXTRACT_DRAWING,
            ),
            max_capability_level=CapabilityLevel.LEVEL_1_PARSED,
            adapter_license=AdapterLicense.INTERNAL_PARSER,
            requires_external_dependency=False,
            notes="SVG 1.1/2.0 via stdlib xml.etree; dimensions and element count harvested.",
        )

    def can_handle(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor | None = None,
    ) -> bool:
        if source.source_format_id == "SVG":
            return True
        if format_descriptor and format_descriptor.format_id == "SVG":
            return True
        if source.file_name and source.file_name.lower().endswith(".svg"):
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
            session.record(FidelityClass.LOST, "SVG content not available")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        try:
            info = _parse_svg_bytes(data)
        except Exception as exc:  # noqa: BLE001
            session.mark_failed()
            session.record(FidelityClass.LOST, f"SVG parse error: {exc}")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        if not info["has_svg_namespace"]:
            session.record_inferred(
                "SVG namespace not detected in root element; content may not be SVG."
            )

        session.mark_parsed()
        session.set_source_entity_count(info["element_count"])

        ref = CanonicalEntityRef(
            entity_id=make_uid("SVG-DOC-"),
            entity_kind="SvgDocument",
            metadata={
                "width": info["width"],
                "height": info["height"],
                "viewBox": info["viewBox"],
                "element_count": info["element_count"],
            },
        )
        session.add_entity_ref(ref)
        session.set_fidelity_completeness(FidelityReportCompleteness.COMPLETE)
        return session.build()


def _bytes_from_source(source: EngineeringSource) -> bytes | None:
    """Extract raw bytes from source.notes (test pathway).

    Uses latin-1 (1:1 byte↔char) so binary content round-trips losslessly.
    """
    if source.notes:
        return source.notes.encode("latin-1", errors="replace")
    return None
