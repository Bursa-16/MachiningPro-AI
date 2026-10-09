"""Universal Engineering Import API (UNIVERSAL_IMPORT_02).

Single authenticated POST endpoint that accepts any supported engineering file,
runs the built-in universal adapter registry (created in UNIVERSAL_IMPORT_01),
and returns structured format metadata as JSON.

No cloud conversion. No paid API. All processing local. Fail-closed.

Endpoint: POST /api/import
Returns:  200 with ImportResponse JSON on any recognized/parseable file.
          422 if the file is empty or exceeds MAX_IMPORT_BYTES.

The endpoint deliberately does NOT replicate the drawing-analysis pipeline
(/api/drawings). PDF files that need full drawing analysis should still be
submitted to /api/drawings. This endpoint provides format detection and
Level 0–1 metadata for ALL supported formats.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import Response

from backend.api.auth import verify_token
from backend.api.dxf_render import png_to_single_page_pdf, render_dxf_to_png
from backend.interoperability.adapters._base import ContentSniffer
from backend.interoperability.adapters.registry_helpers import build_default_adapter_registry
from backend.interoperability.enums import FormatFamily, NormalizationStatus
from backend.interoperability.models import EngineeringSource, FormatDescriptor

router = APIRouter(prefix="/api/import", tags=["engineering-import"])

MAX_IMPORT_BYTES = 64 * 1024 * 1024  # 64 MB

# ---------------------------------------------------------------------------
# Extension → (format_id, family) mapping – mirrors the backend registry
# ---------------------------------------------------------------------------

_EXT_TO_FORMAT: dict[str, tuple[str, str]] = {
    "pdf":    ("PDF", "DOCUMENT"),
    "png":    ("RASTER-IMAGE", "IMAGE"),
    "jpg":    ("RASTER-IMAGE", "IMAGE"),
    "jpeg":   ("RASTER-IMAGE", "IMAGE"),
    "tif":    ("RASTER-IMAGE", "IMAGE"),
    "tiff":   ("RASTER-IMAGE", "IMAGE"),
    "bmp":    ("RASTER-IMAGE", "IMAGE"),
    "svg":    ("SVG",          "IMAGE"),
    "dxf":    ("DXF",          "DRAWING"),
    "step":   ("STEP-GENERIC", "NEUTRAL_EXCHANGE"),
    "stp":    ("STEP-GENERIC", "NEUTRAL_EXCHANGE"),
    "iges":   ("IGES",         "NEUTRAL_EXCHANGE"),
    "igs":    ("IGES",         "NEUTRAL_EXCHANGE"),
    "stl":    ("STL",          "MESH"),
    "obj":    ("OBJ",          "MESH"),
    "3mf":    ("3MF",          "MESH"),
    "nc":     ("NC-GCODE",     "NC"),
    "gcode":  ("NC-GCODE",     "NC"),
    "tap":    ("NC-GCODE",     "NC"),
    "g":      ("NC-GCODE",     "NC"),
    "cnc":    ("NC-GCODE",     "NC"),
    "ngc":    ("NC-GCODE",     "NC"),
    "mpf":    ("NC-GCODE",     "NC"),
}

_FAMILY_LABELS: dict[str, str] = {
    "NEUTRAL_EXCHANGE": "CAD Neutral Exchange",
    "CAD":              "CAD Geometry",
    "NATIVE_CAD":       "Native CAD (proprietary)",
    "MESH":             "Mesh Geometry",
    "NC":               "NC / G-code Program",
    "DRAWING":          "2D Engineering Drawing",
    "IMAGE":            "Raster / Vector Image",
    "DOCUMENT":         "Engineering Document",
    "UNKNOWN":          "Unknown",
}

# ---------------------------------------------------------------------------
# Auth helper (same pattern as drawing_analysis.py)
# ---------------------------------------------------------------------------

def require_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """Bearer token from the existing login; fails closed with 401."""
    scheme, _, token = (authorization or "").partition(" ")
    payload = (
        verify_token(token.strip())
        if scheme.lower() == "bearer" and token.strip()
        else None
    )
    if payload is None:
        raise HTTPException(401, detail={"error_code": "UNAUTHENTICATED"})
    return payload


# ---------------------------------------------------------------------------
# Lazily built registry (one instance per process lifetime)
# ---------------------------------------------------------------------------

_registry = None


def _get_registry():
    global _registry  # noqa: PLW0603
    if _registry is None:
        _registry = build_default_adapter_registry()
    return _registry


# ---------------------------------------------------------------------------
# Format detection helpers
# ---------------------------------------------------------------------------

def _ext(filename: str | None) -> str:
    """Return lowercase extension without the leading dot, or empty string."""
    if not filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _detect_format_id(header: bytes, filename: str | None) -> tuple[str, str]:
    """Return (format_id, family_str) using ContentSniffer then extension."""
    sniffed = ContentSniffer.sniff(header)
    if sniffed:
        if sniffed.startswith("STEP-"):
            return sniffed, "NEUTRAL_EXCHANGE"
        if sniffed in ("DXF", "DXF-BINARY"):
            return sniffed, "DRAWING"
        if sniffed == "IGES":
            return "IGES", "NEUTRAL_EXCHANGE"
        return sniffed, "UNKNOWN"
    ext = _ext(filename)
    if ext in _EXT_TO_FORMAT:
        return _EXT_TO_FORMAT[ext]
    return "UNKNOWN", "UNKNOWN"


def _minimal_descriptor(format_id: str, family_str: str) -> FormatDescriptor:
    """Build a minimal FormatDescriptor sufficient for ingest."""
    try:
        family = FormatFamily(family_str)
    except ValueError:
        family = FormatFamily.UNKNOWN
    return FormatDescriptor(
        format_id=format_id,
        canonical_name=format_id,
        family=family,
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("")
def import_file(
    file: UploadFile = File(...),  # noqa: B008
    _user: dict[str, Any] = Depends(require_user),  # noqa: B008
) -> dict[str, Any]:
    """Detect format and parse an engineering file to Level 0–1.

    Returns structured JSON with format_id, format_family, import_status,
    capability_level, entity_count, and format-specific metadata extracted
    by the universal adapter registry.

    Never returns raw parser errors or file content to the caller.
    """
    data = file.file.read(MAX_IMPORT_BYTES + 1)
    if not data:
        raise HTTPException(422, detail={"error_code": "EMPTY_FILE"})
    if len(data) > MAX_IMPORT_BYTES:
        raise HTTPException(413, detail={"error_code": "FILE_TOO_LARGE"})

    filename = file.filename or "upload"
    format_id, family_str = _detect_format_id(data[:512], filename)

    # Look up an adapter from the registry
    registry = _get_registry()
    source = EngineeringSource(
        source_id=f"import::{filename}",
        source_format_id=format_id if format_id != "UNKNOWN" else None,
        file_name=filename,
    )
    descriptor = _minimal_descriptor(format_id, family_str)
    adapters = registry.find_by_format(format_id)

    if not adapters:
        # Format not in registry — return a recognized-but-unsupported response
        return {
            "file_name": filename,
            "format_id": format_id,
            "format_family": family_str,
            "format_family_label": _FAMILY_LABELS.get(family_str, family_str),
            "import_status": "UNRECOGNIZED",
            "capability_level": "LEVEL_0_RECOGNIZED",
            "entity_count": 0,
            "metadata": {},
        }

    adapter = adapters[0]

    # Write bytes to a temp file so ingest_file can read them
    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=f".{_ext(filename) or 'bin'}",
        ) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        document = adapter.ingest_file(source, descriptor, tmp_path)
    except Exception:  # noqa: BLE001
        return {
            "file_name": filename,
            "format_id": format_id,
            "format_family": family_str,
            "format_family_label": _FAMILY_LABELS.get(family_str, family_str),
            "import_status": "PARSE_ERROR",
            "capability_level": "LEVEL_0_RECOGNIZED",
            "entity_count": 0,
            "metadata": {},
        }
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass

    # Map NormalizationStatus → import_status string
    status_map = {
        NormalizationStatus.SUCCESS: "SUCCESS",
        NormalizationStatus.PARTIAL: "PARTIAL",
        NormalizationStatus.FAILED: "FAILED",
        NormalizationStatus.UNSUPPORTED: "UNSUPPORTED",
        NormalizationStatus.INSUFFICIENT_DATA: "INSUFFICIENT_DATA",
    }
    import_status = status_map.get(document.normalization_status, "UNKNOWN")

    # Collect entity metadata (first entity ref's metadata dict)
    entity_meta: dict[str, Any] = {}
    if document.entity_refs:
        raw = document.entity_refs[0].metadata
        # Sanitize: only JSON-safe scalar types pass through
        entity_meta = {
            k: v
            for k, v in (raw or {}).items()
            if isinstance(v, (str, int, float, bool)) or v is None
        }

    # If the format provides its own entity count in metadata (e.g. DXF header
    # reports 843 entities before ezdxf is available), promote that count to the
    # top-level field and remove it from the metadata block to avoid duplication.
    display_entity_count = len(document.entity_refs)
    if "entity_count" in entity_meta and isinstance(entity_meta["entity_count"], int):
        display_entity_count = int(entity_meta.pop("entity_count"))

    # Fidelity summary
    fidelity_events = [
        {
            "class": e.fidelity_class.value,
            "description": e.description[:200] if e.description else "",
        }
        for e in (document.fidelity_report.events if document.fidelity_report else [])
    ]

    return {
        "file_name": filename,
        "format_id": document.format_descriptor.format_id,
        "format_family": document.format_descriptor.family.value,
        "format_family_label": _FAMILY_LABELS.get(
            document.format_descriptor.family.value,
            document.format_descriptor.family.value,
        ),
        "import_status": import_status,
        "capability_level": document.capability_level.value,
        "entity_count": display_entity_count,
        "metadata": entity_meta,
        "fidelity_events": fidelity_events[:10],  # cap at 10 for API response
        "adapter_id": document.adapter_id,
    }


@router.post("/dxf-as-pdf")
def dxf_as_pdf(
    file: UploadFile = File(...),  # noqa: B008
    _user: dict[str, Any] = Depends(require_user),  # noqa: B008
) -> Response:
    """Render a DXF file to a raster image and return it wrapped in a single-page PDF.

    The returned PDF is accepted by POST /api/drawings (passes %PDF- magic-bytes
    check, parseable by pdfplumber) so the DXF geometry can flow through the
    existing drawing-analysis + Ollama AI pipeline.

    LOCAL_ONLY: uses Pillow only.  No ezdxf, no cloud, no paid API.
    AI_AUTHORITY=ADVISORY: the rendered image is advisory VLM input only.
    SOURCE_DXF_OVERWRITE_ALLOWED=NO: input bytes are never mutated.
    """
    data = file.file.read(MAX_IMPORT_BYTES + 1)
    if not data:
        raise HTTPException(422, detail={"error_code": "EMPTY_FILE"})
    if len(data) > MAX_IMPORT_BYTES:
        raise HTTPException(413, detail={"error_code": "FILE_TOO_LARGE"})

    try:
        text = data.decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(422, detail={"error_code": "DECODE_FAILED"}) from exc

    png_bytes = render_dxf_to_png(text)
    if png_bytes is None:
        raise HTTPException(
            422,
            detail={"error_code": "RENDER_FAILED",
                    "message": "DXF contains no renderable geometry (LINE/CIRCLE/ARC/LWPOLYLINE)"},
        )

    pdf_bytes = png_to_single_page_pdf(png_bytes)
    return Response(content=pdf_bytes, media_type="application/pdf")
