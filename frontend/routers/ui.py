"""UI page router (UI-0A / UI-1A).

Serves the Jinja2-rendered HTML pages for the engineering interface.
All pages extend ``base.html`` which provides the sidebar navigation
and Tailwind/HTMX integration.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import HTMLResponse

from backend.interoperability.models import EngineeringSource
from backend.interoperability.orchestrator import (
    CadImportOrchestrator,
    ImportResult,
)

logger = logging.getLogger(__name__)

# File extensions accepted by the upload form (validated against actual adapters).
ACCEPTED_EXTENSIONS: frozenset[str] = frozenset({
    ".step", ".stp", ".p21",
    ".iges", ".igs",
    ".dxf",
})

router = APIRouter(tags=["ui"])

# -- Navigation definition (single source of truth) -----------------------

NAV_ITEMS: list[dict[str, str]] = [
    {"label": "Dashboard", "href": "/ui/", "icon": "home", "badge": ""},
    {"label": "CAD Import", "href": "/ui/cad-import", "icon": "upload", "badge": ""},
    {"label": "Geometry / Topology", "href": "/ui/geometry", "icon": "box", "badge": "PLANNED"},
    {"label": "Machining", "href": "/ui/machining", "icon": "settings", "badge": "PLANNED"},
    {"label": "Tools & Parameters", "href": "/ui/tools", "icon": "wrench", "badge": "PLANNED"},
    {"label": "Materials", "href": "/ui/materials", "icon": "layers", "badge": "PLANNED"},
    {"label": "Validation", "href": "/ui/validation", "icon": "shield-check", "badge": "PLANNED"},
    {"label": "AI Assistant", "href": "/ui/ai-assistant", "icon": "sparkles", "badge": "PLANNED"},
]

def _context(*, active_href: str, **extra: object) -> dict[str, object]:
    """Build the standard template context (without request)."""
    return {
        "nav_items": NAV_ITEMS,
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
        "error_message": result.error_message,
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
        "degradation_reason": result.capability.degradation_reason,
        # Fidelity
        "fidelity_adverse_count": diag.fidelity_adverse_count,
        "has_loss": diag.has_loss,
        "has_unsupported": diag.has_unsupported_content,
        "notes": diag.notes,
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
    if file is None or file.filename is None or file.filename.strip() == "":
        return _render(request, "cad_import.html", _context(
            **ctx_base, result=None, error="No file was uploaded.",
        ))

    filename = file.filename.strip()
    ext = _extension_of(filename)

    # --- Validate extension ---
    if ext not in ACCEPTED_EXTENSIONS:
        return _render(request, "cad_import.html", _context(
            **ctx_base, result=None,
            error=f"Unsupported file extension: '{ext}'. Accepted: {', '.join(sorted(ACCEPTED_EXTENSIONS))}",  # noqa: E501
        ))

    # --- Read file content (in memory — no permanent storage) ---
    try:
        content_bytes = await file.read()
    except Exception:
        logger.exception("Failed to read uploaded file")
        return _render(request, "cad_import.html", _context(
            **ctx_base, result=None, error="Failed to read the uploaded file.",
        ))

    if len(content_bytes) == 0:
        return _render(request, "cad_import.html", _context(
            **ctx_base, result=None, error="The uploaded file is empty.",
        ))

    file_size = len(content_bytes)

    # --- Build EngineeringSource ---
    # Pass first 512 bytes as notes for content sniffing by detect_format().
    header_text = content_bytes[:512].decode("utf-8", errors="replace")
    source = EngineeringSource(
        source_id=f"upload::{filename}",
        file_name=filename,
        notes=header_text,
    )

    # --- Run orchestrator ---
    try:
        orchestrator = CadImportOrchestrator()
        result: ImportResult = orchestrator.import_source(source)
    except Exception:
        logger.exception("CAD import orchestrator raised an unexpected exception")
        return _render(request, "cad_import.html", _context(
            **ctx_base, result=None,
            error="An internal error occurred during CAD import. No traceback is exposed.",
        ))

    display = _result_to_display(result)
    display["filename"] = filename
    display["file_size"] = file_size

    return _render(request, "cad_import.html", _context(
        **ctx_base, result=display, error=None,
    ))


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
