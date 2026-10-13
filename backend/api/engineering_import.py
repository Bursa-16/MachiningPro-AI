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

import os
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
# STEP tessellation (gmsh) — local only, no cloud, no paid API (HARD RULE 03)
# ---------------------------------------------------------------------------

def _tessellate_step(data: bytes) -> dict[str, Any] | None:
    """Tessellate STEP bytes with gmsh.

    Returns a browser-safe preview_mesh dict or None on failure.
    TEMP_FILE_UNIQUE=YES, TEMP_FILE_CLEANUP=YES, GMSH_FINALIZE_GUARANTEED=YES.
    Node tags are NOT assumed contiguous/zero-based (HARD RULE 17).
    Only triangle elements (type 2) are promoted to indices.
    """
    try:
        import gmsh  # noqa: PLC0415
    except ImportError:
        return None

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".step") as f:
            f.write(data)
            tmp_path = f.name

        gmsh.initialize(["-v", "0"], interruptible=False)
        try:
            gmsh.open(tmp_path)
            gmsh.model.mesh.generate(2)

            node_tags, coords, _ = gmsh.model.mesh.getNodes()
            if len(node_tags) == 0:
                return None

            tag_to_idx: dict[int, int] = {int(t): i for i, t in enumerate(node_tags)}

            elem_types, elem_tags_list, elem_node_tags = gmsh.model.mesh.getElements(dim=2)
            indices: list[int] = []
            for _etype, etags, enodes in zip(  # noqa: B905
                elem_types, elem_tags_list, elem_node_tags
            ):
                nodes_per = len(enodes) // max(len(etags), 1)
                if nodes_per == 3:
                    for i in range(len(etags)):
                        t = enodes[i * 3 : (i + 1) * 3]
                        indices.extend(
                            [tag_to_idx[int(t[0])], tag_to_idx[int(t[1])], tag_to_idx[int(t[2])]]
                        )

            if not indices:
                return None

            xs = coords[0::3]
            ys = coords[1::3]
            zs = coords[2::3]

            return {
                "positions": [float(c) for c in coords],
                "indices": indices,
                "bounding_box": {
                    "min": [float(min(xs)), float(min(ys)), float(min(zs))],
                    "max": [float(max(xs)), float(max(ys)), float(max(zs))],
                },
                "vertex_count": len(node_tags),
                "triangle_count": len(indices) // 3,
            }
        finally:
            gmsh.finalize()
    except Exception:  # noqa: BLE001
        return None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


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

    from backend.interoperability.geometry import CanonicalGeometry

    geom = document.geometry
    has_renderable_geometry = (
        isinstance(geom, CanonicalGeometry)
        and (len(geom.curves) > 0 or len(geom.surfaces) > 0)
    ) or (
        # Mesh formats (STL/OBJ/3MF): renderable when triangle count is positive
        document.format_descriptor.family == FormatFamily.MESH
        and int(entity_meta.get("triangle_count") or 0) > 0
    )

    # STEP preview: local gmsh tessellation (HARD RULE 03, 05, 09, 11, 17)
    preview_mesh: dict[str, Any] | None = None
    if (
        document.format_descriptor.family == FormatFamily.NEUTRAL_EXCHANGE
        and format_id.startswith("STEP")
        and import_status == "SUCCESS"
    ):
        preview_mesh = _tessellate_step(data)
        if preview_mesh is not None:
            # Tessellation proves renderable geometry (HARD RULE 14)
            has_renderable_geometry = True

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
        "has_renderable_geometry": has_renderable_geometry,
        "preview_mesh": preview_mesh,
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
