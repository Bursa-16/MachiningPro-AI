# MachiningPro AI — PUBLIC-01A + UX-01A Implementation Plan

**Date:** 2026-09-26
**Slices:** PUBLIC-01A, UX-01A
**Status:** Implemented

---

## File-by-File Implementation Plan

### New Files

| File | Slice | Purpose |
|------|-------|---------|
| `frontend/navigation.py` | UX-01A | Navigation model — `NavItem`, `NavGroup`, `NavGroupView`, `NavItemView` dataclasses. `build_sidebar(active_href)` resolves open/active state. `legacy_nav_items()` for backward compatibility. |
| `frontend/public_site.py` | PUBLIC-01A | Page registry (11 `PublicPage` entries), env-driven `PublicSiteConfig` (base URL, social links, response time), `page_context()` builder. No-fabrication by design. |
| `frontend/routers/public.py` | PUBLIC-01A | Auto-registers GET routes for all skeleton-status pages via `router.add_api_route()` loop. Sets `X-Robots-Tag` for non-indexable pages. |
| `frontend/templates/partials/app_sidebar_nav.html` | UX-01A | Jinja2 partial: `<details>` groups with chevron, `<div>` for non-collapsible. `data-nav-group`, `data-nav-group-active` attributes for JS. |
| `frontend/templates/public/layout.html` | PUBLIC-01A | Standalone public shell. Skip link, OG/Twitter meta, canonical URL, noindex for skeletons. Includes `_header.html`, `_footer.html`. Floating FAB (hidden on contact page). |
| `frontend/templates/public/_header.html` | PUBLIC-01A | Sticky header: brand, desktop nav (hidden ≤ 1100 px), `<details>` compact menu (shown ≤ 1100 px), Sign In + Request Demo CTAs. |
| `frontend/templates/public/_footer.html` | PUBLIC-01A | 4-column grid: about, product links, company links, legal. Social links only when configured. |
| `frontend/templates/public/_macros.html` | PUBLIC-01A | `cta()` button macro, `nav_links()` list macro. |
| `frontend/templates/public/skeleton.html` | PUBLIC-01A | Honest placeholder: eyebrow, h1, description, "This page is being prepared" notice, CTAs. |
| `frontend/static/js/app-shell.js` | UX-01A | Progressive enhancement (~100 lines). `initGroups()` persists sidebar group state in localStorage. `initDrawer()` manages off-canvas drawer (toggle, backdrop, Escape, media query cleanup). All storage wrapped in try/catch. |
| `tests/unit/frontend/test_ux01a_navigation.py` | UX-01A | 20+ tests: route mapping, unique IDs, legacy shape, group open/close logic, ARIA, mobile controls, brand name, skip link, drawer CSS. |
| `tests/unit/frontend/test_public01a_shell.py` | PUBLIC-01A | 25+ tests: registry, SEO meta, skeleton rendering, no-fabrication assertions (no fake prices, testimonials, tracking, WhatsApp), config env vars. |
| `docs/superpowers/specs/2026-09-26-public-prelogin-ux-design.md` | Both | Design spec: audit, target IA, SEO/mobile/a11y/no-fabrication strategies, phase breakdown. |
| `docs/superpowers/plans/2026-09-26-public-prelogin-ux-plan.md` | Both | This file. |

### Modified Files

| File | Slice | Change |
|------|-------|--------|
| `frontend/routers/ui.py` | UX-01A | Replaced hard-coded `NAV_ITEMS` with `legacy_nav_items()`. Added `build_sidebar(active_href)` to `_context()`. |
| `frontend/app.py` | PUBLIC-01A | Added `from frontend.routers import public` and `application.include_router(public.router)`. |
| `frontend/templates/base.html` | UX-01A | Skip link, sidebar partial include, mobile bar with toggle button, backdrop, `app-shell.js` script. Fixed brand to "MachiningPro AI". |
| `frontend/static/design-system.css` | Both | Appended Section 22 (UX-01A: skip link, grouped sidebar, focus-visible, drawer, reduced motion) and Section 23 (PUBLIC-01A: public shell, header, nav, footer, FAB, responsive breakpoints). CRLF preserved. |
| `frontend/templates/cad_import.html` | UX-01A | Brand fix: "MachineryPro AI" → "MachiningPro AI" (2 occurrences). |
| `frontend/templates/planned.html` | UX-01A | Brand fix: "MachineryPro AI" → "MachiningPro AI" (1 occurrence). |
| `tests/unit/frontend/test_app.py` | UX-01A | Updated assertion: `"MachiningPro AI" in resp.text`. |

### Not Modified (scope protection)

- `frontend/templates/public_base.html` — pre-existing dirty state preserved
- `frontend/app/` — untracked React SPA, TorqPro-branded
- `backend/interoperability/vlm_provider.py`, `backend/interoperability/vlm_drawing.py` — VLM backend out of scope
- No database migrations

---

## Acceptance Criteria

### PUBLIC-01A

- [x] 11 public pages registered in `public_site.py` with unique titles and descriptions
- [x] Every title contains "MachiningPro AI"; none contains "MachineryPro"
- [x] Primary nav order: Product · How It Works · Solutions · Case Studies · Pricing · FAQ · About
- [x] Skeleton pages render HTTP 200 with `noindex` meta + header
- [x] Skeleton pages display "This page is being prepared"
- [x] No Tailwind CDN loaded on public pages
- [x] Semantic landmarks: `<header>`, `<main>`, `<footer>`, single `<h1>`
- [x] Skip link present and targets `#mp-pub-main`
- [x] Header CTAs: "Request Demo" (primary, → /contact), "Sign In" (ghost, → /app)
- [x] `aria-current="page"` on active nav link
- [x] Compact menu uses native `<details>` with `aria-label`
- [x] Footer links Privacy and Terms
- [x] Mobile FAB is internal (`/contact`), not WhatsApp; hidden on contact page
- [x] Open Graph + Twitter card meta present
- [x] No fabricated content: no testimonials, customer logos, price figures, analytics, `mailto:`, `tel:`
- [x] Pricing has no currency+digit patterns; says "available on request"
- [x] Legal pages flagged as "not been legally reviewed"
- [x] No canonical URL without configured base URL
- [x] Config defaults are empty; base URL requires HTTPS; only configured social links render
- [x] Existing routes (`/`, `/ui/`, `/app`) unchanged

### UX-01A

- [x] Every nav item maps to an existing route in `routers/ui.py`
- [x] No UI route dropped from the old flat list
- [x] Unique IDs and hrefs across all items
- [x] `legacy_nav_items()` returns backward-compatible shape
- [x] Only the active group opens by default; others closed
- [x] Exactly one item marked active per page
- [x] `"planned"` status is factual (matches deliberate placeholders)
- [x] Groups are small (≤ 5 items each)
- [x] Dashboard is static (non-collapsible)
- [x] `aria-current="page"` appears exactly once
- [x] Chevron SVG present in collapsible group summaries
- [x] Navigation wrapped in `<nav aria-label>`
- [x] Mobile toggle button with `aria-controls` and `aria-expanded`
- [x] Skip link present
- [x] `app-shell.js` served at `/static/js/app-shell.js`
- [x] Drawer CSS present (`.mp-shell--nav-open`, `mp-drawer-backdrop`)
- [x] Brand name "MachiningPro AI" (not "MachineryPro AI") throughout
- [x] localStorage persistence: group state remembered across page loads
- [x] Escape key closes drawer and returns focus to toggle
- [x] `prefers-reduced-motion` respected

### Cross-Cutting

- [x] All frontend tests pass (287+)
- [x] Ruff clean (no lint errors)
- [x] No horizontal overflow at 6 tested viewports (320–1440 px)
- [x] Mixed CRLF/LF line endings in CSS preserved
- [x] Pre-existing dirty files untouched
- [x] VLM backend files untouched
- [x] No commits, no pushes
