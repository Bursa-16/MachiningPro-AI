"""MachiningPro AI — public / pre-login page router (PUBLIC-01A).

Registers the public page skeletons from ``frontend.public_site``. The
existing landing page at ``/`` is still served by ``routers/ui.py`` and is
migrated onto the new public layout in PUBLIC-01B.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from frontend.public_site import PUBLIC_PAGES, PublicPage, load_config, page_context

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
