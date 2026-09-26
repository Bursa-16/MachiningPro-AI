"""MachiningPro AI — public / pre-login page router (PUBLIC-01A / PUBLIC-01B).

Registers the public home page and the page skeletons from
``frontend.public_site``. The home page (PUBLIC-01B) is the one page in the
registry with ``content_status="live"``; it renders ``public/home.html``
with the richer home-page context. Every other registered page is still a
``content_status="skeleton"`` placeholder rendered from ``public/skeleton.html``.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from frontend.public_site import (
    PUBLIC_PAGES,
    PublicPage,
    home_context,
    load_config,
    page_context,
)

router = APIRouter(tags=["public"])


def render_public_page(request: Request, page: PublicPage, template: str) -> HTMLResponse:
    """Render ``template`` with the shared public-layout context."""
    templates = request.app.state.templates
    ctx = page_context(page, load_config())
    response = templates.TemplateResponse(request, template, ctx)
    if not page.indexable:
        # Belt and braces with the <meta name="robots"> tag in the layout.
        response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


def _register(page: PublicPage) -> None:
    async def endpoint(request: Request) -> HTMLResponse:
        return render_public_page(request, page, "public/skeleton.html")

    endpoint.__name__ = f"public_{page.key.replace('-', '_')}"
    router.add_api_route(
        page.path,
        endpoint,
        methods=["GET"],
        response_class=HTMLResponse,
        name=endpoint.__name__,
    )


for _page in PUBLIC_PAGES:
    if _page.content_status == "skeleton":
        _register(_page)


# -- Home page (PUBLIC-01B) --------------------------------------------------
# Migrated off the legacy ``landing.html`` / ``public_base.html`` shell and
# onto the PUBLIC-01A public layout. Registered directly (not through
# ``_register``) because it needs the richer ``home_context`` and its own
# template, and it is intentionally excluded from the skeleton loop above.

@router.get("/", response_class=HTMLResponse, name="public_home")
async def home(request: Request) -> HTMLResponse:
    """Public MachiningPro AI home / landing page."""
    templates = request.app.state.templates
    ctx = home_context(load_config())
    return templates.TemplateResponse(request, "public/home.html", ctx)
