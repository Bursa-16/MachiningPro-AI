# MachiningPro AI — PUBLIC-01A + UX-01A Design Specification

**Date:** 2026-09-26
**Slices:** PUBLIC-01A (public/pre-login shell foundation), UX-01A (post-login navigation foundation)
**Status:** Implemented — pending review and commit

---

## 1. Current-State Audit (Phase 0)

### Frontend Architecture

Two parallel frontend systems exist:

| System | Stack | Status |
|--------|-------|--------|
| **Server-rendered (tracked)** | FastAPI + Jinja2, design-system.css (~71 KB), HTMX | Live — serves `/`, `/ui/*` |
| **React SPA (untracked)** | Vite + React + TypeScript + Tailwind 4, TorqPro-branded | Under `frontend/app/`, not served by FastAPI, not modified |

All work targets the tracked server-rendered system only.

### Pre-Login State (before PUBLIC-01A)

- `/` — standalone `landing.html` (no shared shell)
- No public pages for Product, Pricing, FAQ, etc.
- No SEO metadata, Open Graph tags, or canonical URL support
- No `robots` directives
- No environment-driven configuration for social links or response-time statements

### Post-Login State (before UX-01A)

- Flat sidebar: hard-coded `NAV_ITEMS` list in `routers/ui.py` — 8 items, all visible at once
- No grouping, no collapsibility, no progressive disclosure
- Sidebar brand text read "MachineryPro AI" (incorrect product name)
- No skip link, no ARIA landmarks on navigation, no `aria-current`
- No mobile off-canvas drawer — sidebar pushed content on narrow viewports
- No keyboard shortcut to close mobile nav

### Dirty/Untracked State Preserved

- `frontend/templates/public_base.html` — already modified in working tree; not touched
- `frontend/app/` — entire React SPA untracked; not touched
- VLM backend files (`vlm_provider.py`, `vlm_drawing.py`) — not touched

---

## 2. Target Information Architecture

### Public Layer (PUBLIC-01A)

```
/                  → Home (live — existing landing, migrated to public shell in PUBLIC-01B)
/product           → Product (skeleton)
/how-it-works      → How It Works (skeleton)
/solutions         → Solutions (skeleton)
/case-studies      → Case Studies (skeleton)
/pricing           → Packages & Pricing (skeleton)
/faq               → FAQ (skeleton)
/about             → About MachiningPro AI (skeleton)
/contact           → Request a Demo (skeleton)
/privacy           → Privacy Policy (skeleton)
/terms             → Terms of Use (skeleton)
```

**Primary navigation (header):** Product · How It Works · Solutions · Case Studies · Pricing · FAQ · About

**Company nav (footer):** Contact · Sign In · (configured social links)

**Legal nav (footer):** Privacy · Terms

### Post-Login Sidebar (UX-01A)

```
Workspace (static, non-collapsible)
  └─ Dashboard          /ui/

Engineering Data (collapsible)
  ├─ CAD Import         /ui/cad-import
  └─ Geometry/Topology  /ui/geometry        [PLANNED]

Manufacturing (collapsible)
  ├─ Machining          /ui/machining       [PLANNED]
  ├─ Tools & Parameters /ui/tools           [PLANNED]
  └─ Materials          /ui/materials       [PLANNED]

Assurance (collapsible)
  └─ Validation         /ui/validation      [PLANNED]

Intelligence (collapsible)
  └─ AI Assistant       /ui/ai-assistant    [PLANNED]
```

Only the group containing the current page opens by default. Other groups retain the viewer's last open/close state via `localStorage`.

---

## 3. SEO Strategy

- **Skeleton pages** carry `<meta name="robots" content="noindex, follow" />` and `X-Robots-Tag: noindex, follow` HTTP header — they are not indexed until content is reviewed and `content_status` changes to `"live"`.
- **Canonical URL** rendered only when `MACHININGPRO_PUBLIC_BASE_URL` is set to an HTTPS origin.
- **Open Graph / Twitter card** tags on every public page: `og:site_name`, `og:title`, `og:description`, `og:type`, `og:url` (if canonical configured), `twitter:card`.
- **Title format:** `Page Label | MachiningPro AI` (home page: `MachiningPro AI | Intelligent Manufacturing Engineering Platform`).
- **Meta descriptions:** 50–200 characters, unique per page, factual.
- No tracking scripts, analytics pixels, or Google Tag Manager until explicitly configured.

---

## 4. Analytics & Tracking Strategy

No analytics are injected in PUBLIC-01A. The template structure supports future injection via:
- `MACHININGPRO_ANALYTICS_*` environment variables (not implemented yet)
- A `{% block head_extra %}` hook in the public layout (available for PUBLIC-01B)

---

## 5. Form & Disclosure Strategy

- Contact page renders an honest "The online demo request form is not available yet" notice.
- No `mailto:`, `tel:`, WhatsApp, or third-party chat links are fabricated.
- The Request Demo CTA links to `/contact`; once the form is built (PUBLIC-01C), it will submit server-side.

---

## 6. Mobile Strategy

### Public Pages

| Breakpoint | Behaviour |
|------------|-----------|
| ≥ 1101 px | Desktop nav visible, compact menu hidden |
| ≤ 1100 px | Desktop nav + desktop CTAs hidden, `<details>` compact menu visible |
| ≤ 640 px  | Brand tagline hidden, floating "Request Demo" FAB shown (except on `/contact`), footer collapses to single column |

Compact menu uses native `<details>`/`<summary>` — works without JavaScript.

### Post-Login Workspace

| Breakpoint | Behaviour |
|------------|-----------|
| ≥ 901 px  | Sidebar visible as a column, mobile bar hidden |
| ≤ 900 px  | Sidebar hidden, mobile bar with Menu button visible, sidebar slides in as off-canvas drawer (transform + visibility transition) |

Drawer closes on: backdrop click, Escape key, resize to ≥ 901 px. Focus moves to first focusable element in sidebar when opened; returns to toggle button on Escape.

---

## 7. Accessibility Strategy

- Skip link: `<a href="#mp-pub-main" class="mp-skip-link">Skip to main content</a>` (public) and `<a href="#mp-main" class="mp-skip-link">Skip to main content</a>` (workspace)
- Semantic landmarks: `<header>`, `<nav aria-label="Primary">`, `<main>`, `<footer>`
- `aria-current="page"` on the active nav link
- `aria-expanded` on mobile menu toggle, updated by JS
- `aria-controls` linking toggle to sidebar
- `aria-label` on compact menu summary and footer nav sections
- Focus-visible ring: 2 px offset, uses CSS custom property `--mp-focus-ring`
- `prefers-reduced-motion` respected: transforms and transitions suppressed
- One `<h1>` per page
- SVG icons: `aria-hidden="true" focusable="false"`

---

## 8. No-Fabrication Policy

This policy applies to PUBLIC-01A and all future public-layer work:

1. **No fake customers, logos, or testimonials.** The case-studies skeleton states this explicitly.
2. **No price figures.** Pricing skeleton says "available on request." The test suite asserts no currency+digit patterns appear.
3. **No social links unless configured** via `MACHININGPRO_SOCIAL_*` env vars with valid HTTPS URLs.
4. **No analytics or tracking IDs** unless explicitly configured.
5. **No contact details** (email, phone, address) unless configured.
6. **Legal pages flagged** as "not been legally reviewed."
7. **Skeleton pages** say "This page is being prepared" — not marketing copy.

---

## 9. Phase Breakdown

| Phase | Scope | Status |
|-------|-------|--------|
| **PUBLIC-01A** | Shell, registry, skeleton pages, SEO meta, env-driven config | ✅ Implemented |
| PUBLIC-01B | Home page migration to public shell, hero content | Planned |
| PUBLIC-01C | Contact form (server-side), thank-you page | Planned |
| PUBLIC-01D | Content pages (Product, How It Works, Solutions, FAQ, About) | Planned |
| PUBLIC-01E | Case studies structure, legal page content | Planned |
| **UX-01A** | Grouped sidebar, drawer, skip link, ARIA, localStorage persistence | ✅ Implemented |
| UX-01B | Basic/Advanced progressive disclosure toggle | Planned |
| UX-01C | Role-based visibility (requires backend role contract) | Planned |
| UX-01D | Global search, breadcrumbs, keyboard navigation | Planned |
