"""UI page router (UI-0A / UI-1A).

Serves the Jinja2-rendered HTML pages for the engineering interface.
All pages extend ``base.html`` which provides the sidebar navigation
and Tailwind/HTMX integration.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from backend.interoperability.enums import CapabilityLevel, FidelityClass
from backend.interoperability.models import EngineeringSource
from backend.interoperability.orchestrator import (
    CadImportOrchestrator,
    ImportResult,
    ImportStatus,
)
from frontend.cad_upload import StagedCadUpload, UploadRejected, stage_cad_upload
from frontend.navigation import build_sidebar, legacy_nav_items

logger = logging.getLogger(__name__)

# File extensions accepted by the upload form (validated against actual adapters).
ACCEPTED_EXTENSIONS: frozenset[str] = frozenset({
    ".step", ".stp", ".p21",
    ".iges", ".igs",
    ".dxf",
})

router = APIRouter(tags=["ui"])

# -- Navigation definition -------------------------------------------------
# The single source of truth now lives in ``frontend/navigation.py`` (UX-01A).
# ``NAV_ITEMS`` is kept as a derived, backward-compatible flat list.

NAV_ITEMS: list[dict[str, str]] = legacy_nav_items()


def _context(*, active_href: str, **extra: object) -> dict[str, object]:
    """Build the standard template context (without request)."""
    return {
        "nav_items": NAV_ITEMS,
        "nav_groups": build_sidebar(active_href),
        "active_href": active_href,
        **extra,
    }


def _render(
    request: Request,
    template_name: str,
    ctx: dict[str, object],
) -> HTMLResponse:
    """Render a Jinja2 template using the Starlette-compatible API."""
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        template_name,
        ctx,
    )


# -- Routes ----------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> HTMLResponse:
    """Public MachineryPro AI landing page."""
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "landing.html", {})


@router.get("/app")
async def app_entry() -> HTMLResponse:
    """Application entry — redirect to engineering workspace."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/ui/", status_code=302)


@router.get("/ui/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Dashboard / project home."""
    return _render(
        request,
        "index.html",
        _context(active_href="/ui/"),
    )


# -- CAD Import (UI-1A) ---------------------------------------------------

def _extension_of(filename: str) -> str:
    """Return lowercased file extension including the dot."""
    dot = filename.rfind(".")
    if dot < 0:
        return ""
    return filename[dot:].lower()


def _result_to_display(result: ImportResult) -> dict[str, object]:
    """Extract display-safe fields from an ImportResult."""
    diag = result.diagnostics
    det = diag.format_detection
    doc = result.document

    display: dict[str, object] = {
        "import_id": result.import_id,
        "status": result.status.value,
        "succeeded": result.succeeded,
        "error_message": (
            "CAD input was rejected during import validation."
            if result.error_message
            else None
        ),
        # Format detection
        "detected_format": det.detected_format_id or "Unknown",
        "detection_confidence": det.detection_confidence,
        "detection_method": det.detection_method,
        # Adapter
        "adapter_id": diag.selected_adapter_id or "None",
        "adapter_candidates": ", ".join(diag.adapter_candidates) if diag.adapter_candidates else "None",  # noqa: E501
        "selection_reason": diag.selection_reason,
        # Capability
        "achieved_level": result.capability.achieved_level.value,
        "was_degraded": result.capability.was_degraded,
        "degradation_reason": (
            "Import capability was degraded."
            if result.capability.degradation_reason
            else None
        ),
        # Fidelity
        "fidelity_adverse_count": diag.fidelity_adverse_count,
        "has_loss": diag.has_loss,
        "has_unsupported": diag.has_unsupported_content,
        "notes": (
            ("Additional import diagnostics were recorded.",)
            if diag.notes
            else ()
        ),
    }

    if doc is not None:
        display["normalization_status"] = doc.normalization_status.value
        display["capability_level"] = doc.capability_level.value
        display["entity_ref_count"] = len(doc.entity_refs)
        display["canonical_kind"] = doc.canonical_kind
        display["schema_version"] = doc.schema_version
        display["has_fidelity_report"] = doc.fidelity_report is not None
    else:
        display["normalization_status"] = "N/A"
        display["capability_level"] = result.capability.achieved_level.value
        display["entity_ref_count"] = 0
        display["canonical_kind"] = "N/A"
        display["schema_version"] = "N/A"
        display["has_fidelity_report"] = False

    if result.provenance is not None:
        display["provenance_adapter"] = result.provenance.adapter_id
        display["provenance_version"] = result.provenance.adapter_version
        display["provenance_format"] = result.provenance.format_id
    else:
        display["provenance_adapter"] = "N/A"
        display["provenance_version"] = "N/A"
        display["provenance_format"] = "N/A"

    return display


def _adapter_status(result: ImportResult) -> str:
    """Report adapter availability independently from parse outcome."""
    if result.diagnostics.selected_adapter_id is None:
        return "UNAVAILABLE"
    if result.status is ImportStatus.FAILED:
        return "LIVE"
    levels = list(CapabilityLevel)
    below_geometry = levels.index(result.capability.achieved_level) < levels.index(
        CapabilityLevel.LEVEL_2_NORMALIZED
    )
    if (
        below_geometry
        or result.capability.was_degraded
        or result.diagnostics.has_unsupported_content
    ):
        return "CONDITIONAL"
    return "LIVE"


def _entity_summaries(
    result: ImportResult,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    if result.document is None:
        return None, None
    geometry = result.document.geometry
    geometry_summary = None
    if geometry is not None:
        tolerance = geometry.metadata.get("iges_minimum_resolution_mm")
        geometry_summary = {
            "curve_count": len(geometry.curves),
            "surface_count": len(geometry.surfaces),
            "has_bounding_box": geometry.bounding_box is not None,
            "source_unit": geometry.metadata.get("iges_source_unit"),
            "tolerance_mm": str(tolerance) if tolerance is not None else None,
        }

    topology = result.document.topology
    topology_summary = None
    if topology is not None:
        topology_summary = {
            "vertex_count": len(topology.vertices),
            "edge_count": len(topology.edges),
            "loop_count": len(topology.loops),
            "face_count": len(topology.faces),
            "shell_count": len(topology.shells),
            "body_count": len(topology.bodies),
        }
    return geometry_summary, topology_summary


def _unsupported_entity_summaries(result: ImportResult) -> list[str]:
    if result.document is None or result.document.fidelity_report is None:
        return []
    summaries = []
    for event in result.document.fidelity_report.events:
        if event.fidelity_class is not FidelityClass.UNSUPPORTED:
            continue
        safe = " ".join(event.description.split())[:240]
        summaries.append(safe)
        if len(summaries) == 20:
            break
    return summaries


def _result_to_safe_summary(
    result: ImportResult,
    staged: StagedCadUpload,
) -> dict[str, object]:
    """Build an allowlisted summary without recursively serializing domain data."""
    display = _result_to_display(result)
    geometry_summary, topology_summary = _entity_summaries(result)
    diagnostics = {
        "detection_confidence": result.diagnostics.format_detection.detection_confidence,
        "detection_method": result.diagnostics.format_detection.detection_method,
        "adapter_candidates": list(result.diagnostics.adapter_candidates),
        "selected_adapter_id": result.diagnostics.selected_adapter_id,
        "selection_reason": result.diagnostics.selection_reason,
        "fidelity_adverse_count": result.diagnostics.fidelity_adverse_count,
        "has_unsupported_content": result.diagnostics.has_unsupported_content,
        "has_loss": result.diagnostics.has_loss,
        "unsupported_entities": _unsupported_entity_summaries(result),
    }
    display.update({
        "filename": staged.filename,
        "detected_format": staged.detected_format,
        "file_size": staged.file_size,
        "sha256": staged.sha256,
        "adapter_status": _adapter_status(result),
        "parse_status": result.status.value,
        "diagnostics": diagnostics,
        "geometry_summary": geometry_summary,
        "topology_summary": topology_summary,
    })
    return display


async def _execute_cad_import(file: UploadFile) -> dict[str, object]:
    async with stage_cad_upload(file) as staged:
        source = EngineeringSource(
            source_id=f"upload::{staged.filename}",
            file_name=staged.filename,
            media_type=staged.content_type,
            checksum=f"sha256:{staged.sha256}",
        )
        result = CadImportOrchestrator().import_source(
            source,
            content_path=staged.path,
            header_bytes=staged.header_bytes,
        )
        return _result_to_safe_summary(result, staged)


_API_RESULT_FIELDS = (
    "filename",
    "detected_format",
    "file_size",
    "sha256",
    "adapter_status",
    "parse_status",
    "diagnostics",
    "geometry_summary",
    "topology_summary",
)


@router.get("/ui/cad-import", response_class=HTMLResponse)
async def cad_import_get(request: Request) -> HTMLResponse:
    """CAD Import upload form."""
    return _render(
        request,
        "cad_import.html",
        _context(
            active_href="/ui/cad-import",
            accepted_extensions=", ".join(sorted(ACCEPTED_EXTENSIONS)),
            result=None,
            error=None,
        ),
    )


@router.post("/ui/cad-import", response_class=HTMLResponse)
async def cad_import_post(request: Request, file: UploadFile | None = None) -> HTMLResponse:
    """Handle CAD file upload and run the import orchestrator."""
    ctx_base = {"active_href": "/ui/cad-import",
                "accepted_extensions": ", ".join(sorted(ACCEPTED_EXTENSIONS))}

    # --- Validate upload presence ---
    if file is None:
        return _render(request, "cad_import.html", _context(
            **ctx_base, result=None, error="No file was uploaded.",
        ))

    try:
        display = await _execute_cad_import(file)
    except UploadRejected as exc:
        response = _render(request, "cad_import.html", _context(
            **ctx_base, result=None, error=exc.safe_message,
        ))
        if exc.status_code == 413:
            response.status_code = 413
        return response
    except Exception:
        logger.error("CAD import failed with an unexpected internal error")
        return _render(request, "cad_import.html", _context(
            **ctx_base, result=None,
            error="An internal error occurred during CAD import. No traceback is exposed.",
        ))

    return _render(request, "cad_import.html", _context(
        **ctx_base, result=display, error=None,
    ))

    # --- Read file content (in memory — no permanent storage) ---
@router.post("/api/cad-import", response_class=JSONResponse)
async def cad_import_api(file: UploadFile | None = None) -> JSONResponse:
    """Import CAD data and return an explicitly allowlisted JSON summary."""
    if file is None:
        return JSONResponse(
            {
                "detail": "No file was uploaded.",
                "adapter_status": "UNAVAILABLE",
                "parse_status": "REJECTED",
            },
            status_code=400,
        )
    try:
        summary = await _execute_cad_import(file)
    except UploadRejected as exc:
        return JSONResponse(
            {
                "detail": exc.safe_message,
                "adapter_status": "UNAVAILABLE",
                "parse_status": "REJECTED",
            },
            status_code=exc.status_code,
        )
    except Exception:
        logger.error("CAD import API failed with an unexpected internal error")
        return JSONResponse(
            {
                "detail": "An internal error occurred during CAD import.",
                "adapter_status": "UNAVAILABLE",
                "parse_status": "FAILED",
            },
            status_code=500,
        )
    return JSONResponse({field: summary[field] for field in _API_RESULT_FIELDS})


def _planned(request: Request, href: str, page_label: str) -> HTMLResponse:
    """Render a deliberate placeholder for an upcoming engineering module."""
    return _render(
        request,
        "planned.html",
        _context(active_href=href, page_label=page_label),
    )


@router.get("/ui/geometry", response_class=HTMLResponse)
async def geometry(request: Request) -> HTMLResponse:
    return _planned(request, "/ui/geometry", "Geometry / Topology")


@router.get("/ui/machining", response_class=HTMLResponse)
async def machining(request: Request) -> HTMLResponse:
    return _planned(request, "/ui/machining", "Machining")


@router.get("/ui/tools", response_class=HTMLResponse)
async def tools(request: Request) -> HTMLResponse:
    return _planned(request, "/ui/tools", "Tools & Parameters")


@router.get("/ui/materials", response_class=HTMLResponse)
async def materials(request: Request) -> HTMLResponse:
    return _planned(request, "/ui/materials", "Materials")


@router.get("/ui/validation", response_class=HTMLResponse)
async def validation(request: Request) -> HTMLResponse:
    return _planned(request, "/ui/validation", "Validation")


@router.get("/ui/ai-assistant", response_class=HTMLResponse)
async def ai_assistant(request: Request) -> HTMLResponse:
    return _planned(request, "/ui/ai-assistant", "AI Assistant")
