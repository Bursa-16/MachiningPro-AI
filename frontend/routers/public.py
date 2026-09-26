"""MachiningPro AI — public / pre-login page router (PUBLIC-01A / -01B / -01C).

Registers the public "live" content pages and the page skeletons from
``frontend.public_site``. Home (PUBLIC-01B), Product, How It Works and
Solutions (PUBLIC-01C) are the pages in the registry with
``content_status="live"``; each renders its own template with a richer,
page-specific context. Every other registered page is still a
``content_status="skeleton"`` placeholder rendered from ``public/skeleton.html``.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from frontend.public_site import (
    PAGES_BY_KEY,
    PUBLIC_PAGES,
    PublicPage,
    home_context,
    how_it_works_context,
    load_config,
    page_context,
    product_context,
    solutions_context,
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


# -- Product / How It Works / Solutions (PUBLIC-01C) -------------------------
# Migrated off the generic skeleton loop above (``PublicPage.content_status``
# flipped to "live" in the registry) onto their own templates and context
# builders, the same pattern the home page established in PUBLIC-01B.

@router.get(PAGES_BY_KEY["product"].path, response_class=HTMLResponse, name="public_product")
async def product(request: Request) -> HTMLResponse:
    """Public MachiningPro AI product page."""
    templates = request.app.state.templates
    ctx = product_context(load_config())
    return templates.TemplateResponse(request, "public/product.html", ctx)


@router.get(
    PAGES_BY_KEY["how-it-works"].path, response_class=HTMLResponse, name="public_how_it_works",
)
async def how_it_works(request: Request) -> HTMLResponse:
    """Public MachiningPro AI how-it-works page."""
    templates = request.app.state.templates
    ctx = how_it_works_context(load_config())
    return templates.TemplateResponse(request, "public/how_it_works.html", ctx)


@router.get(PAGES_BY_KEY["solutions"].path, response_class=HTMLResponse, name="public_solutions")
async def solutions(request: Request) -> HTMLResponse:
    """Public MachiningPro AI solutions page."""
    templates = request.app.state.templates
    ctx = solutions_context(load_config())
    return templates.TemplateResponse(request, "public/solutions.html", ctx)
