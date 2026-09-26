"""MachiningPro AI — public / pre-login site foundation (PUBLIC-01A).

Single source of truth for:

* the public page registry (paths, titles, meta descriptions, nav placement),
* site-level configuration that must come from the environment rather than
  being hard-coded (canonical base URL, social profiles, response-time
  statement).

No-fabrication policy
---------------------
Nothing here may invent customers, testimonials, prices, addresses, social
accounts, certifications or performance claims. Optional facts are ``None``
until they are configured, and templates render nothing for ``None``.

Pages whose content has not been written and reviewed are registered as
``content_status="skeleton"``; they render an honest "being prepared" state
and are marked ``noindex`` so search engines do not index placeholder pages.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlparse

SITE_NAME = "MachiningPro AI"
SITE_TAGLINE = "Intelligent Manufacturing Engineering Platform"
SITE_SUMMARY = (
    "Deterministic manufacturing engineering intelligence with AI-assisted "
    "decision support."
)

# Static fallback for the footer copyright line (PUBLIC-01B). Deliberately not
# derived from the wall clock so rendered output — and tests — stay
# deterministic; override with MACHININGPRO_COPYRIGHT_YEAR when it is stale.
DEFAULT_COPYRIGHT_YEAR = 2026

ContentStatus = Literal["live", "skeleton"]
NavPlacement = Literal["primary", "company", "legal", "none"]
CapabilityStatus = Literal["available", "in_development", "roadmap"]

# Section-specific display text for the same underlying status (PUBLIC-01B).
CAPABILITY_STATUS_LABELS: dict[CapabilityStatus, str] = {
    "available": "Available",
    "in_development": "In Development",
    "roadmap": "Planned",
}
MATURITY_STATUS_LABELS: dict[CapabilityStatus, str] = {
    "available": "Available Now",
    "in_development": "In Active Development",
    "roadmap": "Roadmap",
}


@dataclass(frozen=True)
class PublicPage:
    """Metadata for one public page."""

    key: str
    path: str
    nav_label: str
    heading: str
    title: str
    description: str
    nav: NavPlacement
    content_status: ContentStatus = "skeleton"
    # Extra, page-specific honesty note shown on skeleton pages.
    status_note: str | None = None

    @property
    def indexable(self) -> bool:
        return self.content_status == "live"


def _title(label: str) -> str:
    return f"{label} | {SITE_NAME}"


# -- Page registry -----------------------------------------------------------
# Order matters: it is the display order in navigation and the footer.

PUBLIC_PAGES: tuple[PublicPage, ...] = (
    PublicPage(
        key="home", path="/", nav_label="Home", heading=SITE_NAME,
        title=f"{SITE_NAME} | {SITE_TAGLINE}",
        description=(
            "MachiningPro AI is a deterministic-first manufacturing engineering "
            "platform: CAD import, machining calculations, DFM checks and process "
            "planning, with clearly labelled AI assistance."
        ),
        nav="none", content_status="live",
    ),
    PublicPage(
        key="product", path="/product", nav_label="Product", heading="Product",
        title=_title("Product"),
        description=(
            "What MachiningPro AI covers today and what is in development, "
            "with each capability labelled Available, In development or Planned."
        ),
        nav="primary", content_status="live",
    ),
    PublicPage(
        key="how-it-works", path="/how-it-works", nav_label="How It Works",
        heading="How It Works", title=_title("How It Works"),
        description=(
            "The MachiningPro AI engineering workflow: from CAD or drawing input "
            "to analysis, engineering evidence, process configuration and validation."
        ),
        nav="primary", content_status="live",
    ),
    PublicPage(
        key="solutions", path="/solutions", nav_label="Solutions", heading="Solutions",
        title=_title("Solutions"),
        description=(
            "How manufacturing, process and quality engineering teams can use "
            "MachiningPro AI in their day-to-day engineering work."
        ),
        nav="primary", content_status="live",
    ),
    PublicPage(
        key="case-studies", path="/case-studies", nav_label="Case Studies",
        heading="Case Studies", title=_title("Case Studies"),
        description=(
            "Engineering validation examples and sample workflows for MachiningPro AI, "
            "clearly labelled as examples until customer case studies are approved."
        ),
        nav="primary",
        status_note=(
            "No customer case studies have been published. Future entries will be "
            "labelled as internal demonstrations or engineering validation examples "
            "unless a customer has approved publication."
        ),
    ),
    PublicPage(
        key="pricing", path="/pricing", nav_label="Pricing", heading="Packages & Pricing",
        title=_title("Pricing"),
        description=(
            "MachiningPro AI package structure. Commercial pricing has not been "
            "published and is available on request."
        ),
        nav="primary",
        status_note="Commercial pricing has not been published. Pricing is available on request.",
    ),
    PublicPage(
        key="faq", path="/faq", nav_label="FAQ", heading="Frequently Asked Questions",
        title=_title("FAQ"),
        description=(
            "Answers about MachiningPro AI scope: supported file formats, machining "
            "processes, the role of AI, deployment and data handling."
        ),
        nav="primary",
    ),
    PublicPage(
        key="about", path="/about", nav_label="About", heading="About MachiningPro AI",
        title=_title("About"),
        description="About MachiningPro AI, its engineering principles and the team building it.",
        nav="primary",
    ),
    PublicPage(
        key="contact", path="/contact", nav_label="Contact", heading="Request a Demo",
        title=_title("Request a Demo"),
        description="Request a MachiningPro AI demonstration or get in touch with the team.",
        nav="company",
        status_note="The online demo request form is not available yet.",
    ),
    PublicPage(
        key="privacy", path="/privacy", nav_label="Privacy", heading="Privacy Policy",
        title=_title("Privacy Policy"),
        description="How MachiningPro AI handles contact, account and engineering document data.",
        nav="legal",
        status_note=(
            "The privacy policy is being drafted and has not been legally reviewed. "
            "It will be published here once approved."
        ),
    ),
    PublicPage(
        key="terms", path="/terms", nav_label="Terms", heading="Terms of Use",
        title=_title("Terms of Use"),
        description="Terms of use for the MachiningPro AI website and platform.",
        nav="legal",
        status_note=(
            "The terms of use are being drafted and have not been legally reviewed. "
            "They will be published here once approved."
        ),
    ),
)

PAGES_BY_KEY: dict[str, PublicPage] = {p.key: p for p in PUBLIC_PAGES}

# Header CTAs. "Sign In" enters the existing workspace route; MachiningPro AI
# has no authentication backend yet (see docs/superpowers/specs 2026-09-26).
SIGN_IN_HREF = "/app"
REQUEST_DEMO_HREF = "/contact"
HOW_IT_WORKS_HREF = "/how-it-works"
PRODUCT_HREF = "/product"
SOLUTIONS_HREF = "/solutions"


def pages_for(nav: NavPlacement) -> tuple[PublicPage, ...]:
    return tuple(p for p in PUBLIC_PAGES if p.nav == nav)


# -- Footer groups (PUBLIC-01B) ----------------------------------------------
# The footer groups pages differently from the flat header `nav` placement,
# so it is defined by page key rather than by the `nav` field.

FOOTER_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Product", ("product", "how-it-works", "solutions", "pricing")),
    ("Resources", ("case-studies", "faq")),
    ("Company", ("about", "contact")),
    ("Legal", ("privacy", "terms")),
)


def footer_groups() -> tuple[tuple[str, tuple[PublicPage, ...]], ...]:
    """Resolve :data:`FOOTER_GROUPS` into renderable ``(label, pages)`` pairs."""
    return tuple(
        (label, tuple(PAGES_BY_KEY[key] for key in keys))
        for label, keys in FOOTER_GROUPS
    )


# -- Capabilities (PUBLIC-01B) ------------------------------------------------
# Single source of truth for both the home page's "Core Capabilities" cards
# and its "Product Maturity" section (grouped by status). Maturity is graded
# from concrete repository evidence, never guessed:
#   - "available"     — a real, end-to-end, tested workspace workflow exists.
#   - "in_development" — substantive backend modules exist and/or a nav
#     placeholder is already wired in, but there is no finished workspace
#     workflow yet. This is the conservative default when maturity is
#     ambiguous (see docs/superpowers/specs 2026-09-26-public-prelogin-ux-design.md).
#   - "roadmap"        — only design-intent documentation exists; no
#     implementation and no nav placeholder anywhere in the product.

@dataclass(frozen=True)
class PublicCapability:
    key: str
    name: str
    description: str
    status: CapabilityStatus
    # PUBLIC-01C: short, scannable bullets for the Product page's capability
    # family cards. Restatements of `description`, never new claims.
    key_capabilities: tuple[str, ...] = field(default_factory=tuple)

    @property
    def capability_label(self) -> str:
        return CAPABILITY_STATUS_LABELS[self.status]

    @property
    def maturity_label(self) -> str:
        return MATURITY_STATUS_LABELS[self.status]


CAPABILITIES: tuple[PublicCapability, ...] = (
    PublicCapability(
        key="cad-geometry",
        name="CAD / Geometry Intelligence",
        description=(
            "Import STEP, IGES and DXF files, extract canonical geometry and "
            "topology, and review format-detection and fidelity diagnostics "
            "in the engineering workspace."
        ),
        status="available",
        key_capabilities=(
            "STEP, IGES and DXF import",
            "Canonical geometry and topology extraction",
            "Format-detection confidence and fidelity diagnostics",
        ),
    ),
    PublicCapability(
        key="drawing",
        name="Technical Drawing Intelligence",
        description=(
            "Interpreting 2D technical drawings — PDF, raster and vector — "
            "into structured engineering data, including dimensions and "
            "GD&T. Backend parsing exists; a dedicated workspace view is "
            "not yet available."
        ),
        status="in_development",
        key_capabilities=(
            "PDF, raster and vector drawing parsing",
            "Dimension and GD&T extraction",
            "Dedicated workspace review view planned",
        ),
    ),
    PublicCapability(
        key="machining",
        name="Machining Engineering",
        description=(
            "Deterministic formulas for turning, milling, drilling, "
            "threading, hole finishing, honing and lapping. A dedicated "
            "machining workspace view is planned."
        ),
        status="in_development",
        key_capabilities=(
            "Turning, milling and drilling formulas",
            "Threading, hole finishing, honing and lapping",
            "Dedicated machining workspace view planned",
        ),
    ),
    PublicCapability(
        key="machine-tool",
        name="Machine & Tool Libraries",
        description=(
            "Catalog structures for machines, cutting tools and materials, "
            "with capability and validation rules. Workspace views for "
            "browsing and editing these libraries are planned."
        ),
        status="in_development",
        key_capabilities=(
            "Machine, tool and material catalog structures",
            "Capability and validation rules",
            "Workspace browsing and editing planned",
        ),
    ),
    PublicCapability(
        key="quality",
        name="Quality & Validation",
        description=(
            "Design-for-manufacturability rule checks and process-plan "
            "validation. A dedicated validation workspace view is planned."
        ),
        status="in_development",
        key_capabilities=(
            "Design-for-manufacturability rule checks",
            "Process-plan validation",
            "Dedicated validation workspace view planned",
        ),
    ),
    PublicCapability(
        key="ai",
        name="AI-Assisted Engineering",
        description=(
            "Advisory-only AI assistance that never overrides a "
            "deterministic engineering result and is always visually "
            "distinguished from it. Not yet available in the workspace."
        ),
        status="in_development",
        key_capabilities=(
            "Advisory-only, never authoritative",
            "Always visually distinguished from deterministic results",
            "Not yet available in the workspace",
        ),
    ),
    PublicCapability(
        key="costing",
        name="Cost / RFQ",
        description=(
            "Cycle-time and should-cost estimation for quoting. Currently "
            "design intent only, with no implementation yet."
        ),
        status="roadmap",
        key_capabilities=(
            "Cycle-time and should-cost estimation (design intent)",
            "No implementation yet",
        ),
    ),
)

CAPABILITIES_BY_KEY: dict[str, PublicCapability] = {c.key: c for c in CAPABILITIES}

# Ordered from least to most conservative, so max() over statuses yields the
# most conservative one — used to grade anything (a workflow step, a solution
# group) that draws on more than one capability, without hand-picking a status
# that could drift from the CAPABILITIES source of truth (PUBLIC-01C).
_STATUS_SEVERITY: dict[CapabilityStatus, int] = {
    "available": 0,
    "in_development": 1,
    "roadmap": 2,
}


def conservative_status(capability_keys: tuple[str, ...]) -> CapabilityStatus:
    """Most conservative status among the given `CAPABILITIES` keys."""
    statuses = [CAPABILITIES_BY_KEY[key].status for key in capability_keys]
    return max(statuses, key=lambda s: _STATUS_SEVERITY[s])


def capabilities_by_status() -> tuple[tuple[str, tuple[PublicCapability, ...]], ...]:
    """Group :data:`CAPABILITIES` by status for the maturity section, in a
    fixed, honest order: shipped first, then active work, then roadmap."""
    order: tuple[CapabilityStatus, ...] = ("available", "in_development", "roadmap")
    return tuple(
        (MATURITY_STATUS_LABELS[status], tuple(c for c in CAPABILITIES if c.status == status))
        for status in order
    )


# -- How it works (PUBLIC-01B) -----------------------------------------------

@dataclass(frozen=True)
class WorkflowStep:
    title: str
    description: str
    status: CapabilityStatus

    @property
    def status_label(self) -> str:
        return CAPABILITY_STATUS_LABELS[self.status]


WORKFLOW_STEPS: tuple[WorkflowStep, ...] = (
    WorkflowStep(
        "Import or Select",
        "Bring in a STEP, IGES or DXF file through the engineering workspace.",
        "available",
    ),
    WorkflowStep(
        "Analyze",
        "Format detection, adapter selection and canonical geometry/topology "
        "extraction run automatically on import.",
        "available",
    ),
    WorkflowStep(
        "Review Engineering Evidence",
        "Inspect detection confidence, fidelity diagnostics and any "
        "unsupported entities before trusting the result.",
        "available",
    ),
    WorkflowStep(
        "Configure Manufacturing Process",
        "Select machining operations, tools and parameters for the part. "
        "A dedicated workspace view is planned.",
        "in_development",
    ),
    WorkflowStep(
        "Validate",
        "Run design-for-manufacturability and process-plan checks. A "
        "dedicated validation workspace view is planned.",
        "in_development",
    ),
    WorkflowStep(
        "Report",
        "Produce a traceable summary of the engineering decisions made. "
        "Planned.",
        "in_development",
    ),
)

# Condensed labels for the platform-flow visual (distinct from the numbered
# steps above, which read from the user's task; this reads from the data).
PROCESS_FLOW_STAGES: tuple[str, ...] = (
    "Drawing / CAD",
    "Engineering Evidence",
    "Machining Configuration",
    "Machine + Tool Context",
    "Validation",
    "Cost / Report",
)


# -- Target users (PUBLIC-01B) -----------------------------------------------

@dataclass(frozen=True)
class TargetUser:
    role: str
    description: str


TARGET_USERS: tuple[TargetUser, ...] = (
    TargetUser(
        "Manufacturing Engineers",
        "Process selection, parameter calculation and DFM validation in one "
        "structured workflow.",
    ),
    TargetUser(
        "Process Engineers",
        "Process planning, sequence validation and traceability across a "
        "part's manufacturing route.",
    ),
    TargetUser(
        "Quality Engineers",
        "Engineering rule validation, provenance and an audit trail for "
        "every calculated result.",
    ),
    TargetUser(
        "Supplier Development / Industrialization",
        "A consistent CAD-to-manufacturing pipeline for new product "
        "introduction across suppliers.",
    ),
    TargetUser(
        "Cost / RFQ Engineers",
        "A future home for cycle-time and should-cost estimation, "
        "currently on the roadmap.",
    ),
    TargetUser(
        "Technical Product / Project Teams",
        "A shared, traceable view of engineering status across CAD, "
        "machining and validation.",
    ),
)


# -- Trust / status strip (PUBLIC-01B) ---------------------------------------
# Restrained, factual points only — no customer logos, no claims this
# repository cannot substantiate.

TRUST_POINTS: tuple[str, ...] = (
    "Engineering-first architecture",
    "Deterministic calculations",
    "Traceable evidence",
    "AI-assisted, not AI-authoritative",
)


# -- Configuration -----------------------------------------------------------

SOCIAL_PLATFORMS: tuple[tuple[str, str], ...] = (
    ("linkedin", "LinkedIn"),
    ("github", "GitHub"),
    ("youtube", "YouTube"),
    ("x", "X"),
)


@dataclass(frozen=True)
class SocialLink:
    platform: str
    label: str
    url: str


@dataclass(frozen=True)
class PublicSiteConfig:
    """Environment-driven facts. ``None``/empty means "not approved yet"."""

    base_url: str | None = None
    response_time_statement: str | None = None
    social_links: tuple[SocialLink, ...] = field(default_factory=tuple)
    copyright_year: int = DEFAULT_COPYRIGHT_YEAR

    def canonical_url(self, path: str) -> str | None:
        if not self.base_url:
            return None
        return self.base_url + path


def _clean_https_url(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    return value


def load_config(env: Mapping[str, str] | None = None) -> PublicSiteConfig:
    """Read public-site facts from environment variables.

    ``MACHININGPRO_PUBLIC_BASE_URL``       https origin used for canonical/OG URLs
    ``MACHININGPRO_RESPONSE_TIME``         approved response-time sentence
    ``MACHININGPRO_SOCIAL_<PLATFORM>``     https profile URL (LINKEDIN, GITHUB, YOUTUBE, X)
    """
    env = os.environ if env is None else env
    base = _clean_https_url(env.get("MACHININGPRO_PUBLIC_BASE_URL"))
    if base:
        base = base.rstrip("/")
    statement = (env.get("MACHININGPRO_RESPONSE_TIME") or "").strip() or None
    socials = []
    for key, label in SOCIAL_PLATFORMS:
        url = _clean_https_url(env.get(f"MACHININGPRO_SOCIAL_{key.upper()}"))
        if url:
            socials.append(SocialLink(key, label, url))
    year = DEFAULT_COPYRIGHT_YEAR
    raw_year = (env.get("MACHININGPRO_COPYRIGHT_YEAR") or "").strip()
    if raw_year.isdigit():
        year = int(raw_year)
    return PublicSiteConfig(
        base_url=base,
        response_time_statement=statement,
        social_links=tuple(socials),
        copyright_year=year,
    )


def page_context(page: PublicPage, config: PublicSiteConfig) -> dict[str, object]:
    """Template context shared by every page rendered with the public layout."""
    return {
        "site": {
            "name": SITE_NAME,
            "tagline": SITE_TAGLINE,
            "summary": SITE_SUMMARY,
            "sign_in_href": SIGN_IN_HREF,
            "request_demo_href": REQUEST_DEMO_HREF,
            "how_it_works_href": HOW_IT_WORKS_HREF,
            "product_href": PRODUCT_HREF,
            "solutions_href": SOLUTIONS_HREF,
        },
        "page": page,
        "canonical_url": config.canonical_url(page.path),
        "config": config,
        "primary_nav": pages_for("primary"),
        "company_nav": pages_for("company"),
        "legal_nav": pages_for("legal"),
        "footer_groups": footer_groups(),
    }


def home_context(config: PublicSiteConfig) -> dict[str, object]:
    """Template context for the home page — :func:`page_context` plus the
    additional, home-only content structures (PUBLIC-01B)."""
    ctx = page_context(PAGES_BY_KEY["home"], config)
    ctx.update(
        {
            "trust_points": TRUST_POINTS,
            "capabilities": CAPABILITIES,
            "workflow_steps": WORKFLOW_STEPS,
            "process_flow_stages": PROCESS_FLOW_STAGES,
            "target_users": TARGET_USERS,
            "maturity_groups": capabilities_by_status(),
        }
    )
    return ctx


# -- Engineering authority (PUBLIC-01C) ---------------------------------------
# Shared between the Product page ("Engineering Authority Model") and the How
# It Works page ("User Control") so the same principle is stated once, not
# duplicated with two independently-editable copies.

ENGINEERING_AUTHORITY_PRINCIPLES: tuple[str, ...] = (
    "Deterministic engineering results are authoritative and are never "
    "silently overridden by AI output.",
    "AI assistance is advisory only — interpretation, evidence review, "
    "explanation, retrieval and summarization — and is always visually "
    "distinguished from a deterministic result.",
    "Engineering decisions remain reviewable: parameters stay editable and "
    "evidence stays inspectable rather than hidden behind an automated verdict.",
    "MachiningPro AI does not make autonomous manufacturing decisions on a "
    "user's behalf.",
)


# -- Data / library foundation (PUBLIC-01C) -----------------------------------
# High-level only; no claim of complete or worldwide catalog coverage, since
# that has not been implemented or measured.

DATA_LIBRARY_FOUNDATION: tuple[str, ...] = (
    "Machine and cutting-tool catalog structures, designed to support "
    "structured engineering libraries rather than a fixed, complete list.",
    "Material reference structures for the same purpose.",
    "Process knowledge encoded as deterministic machining formulas, not "
    "free-text rules of thumb.",
    "Technical drawing evidence: structured dimensions and GD&T extracted "
    "from parsed drawings, where drawing parsing is available.",
    "Engineering rules for design-for-manufacturability and process-plan "
    "checks.",
)


# -- Validation & traceability (PUBLIC-01C) -----------------------------------
# Every term here maps to a concrete field already surfaced in the CAD import
# workspace view (frontend/routers/ui.py::_result_to_display /
# _result_to_safe_summary) — no invented capability.

VALIDATION_TRACEABILITY_POINTS: tuple[str, ...] = (
    "Deterministic calculations are authoritative; results are not "
    "silently adjusted by AI.",
    "Provenance is recorded per import: which adapter, and which adapter "
    "version, produced a given result.",
    "Format-detection confidence and detection method are shown, not "
    "hidden.",
    "Fidelity diagnostics flag unsupported or degraded content instead of "
    "silently discarding it.",
    "Structured, traceable reporting of these findings is on the roadmap; "
    "today the evidence is reviewable in the CAD import result view.",
)


# -- How It Works — full workflow (PUBLIC-01C) --------------------------------
# A fuller, 9-step version of the home page's condensed WORKFLOW_STEPS
# (frontend/public_site.py::WORKFLOW_STEPS, left untouched to avoid
# regressing PUBLIC-01B). Each status is graded against the same
# CAPABILITIES entries the rest of the site uses — see the inline comments —
# so a step is never marked more mature than the capability it depends on.

HOW_IT_WORKS_STEPS: tuple[WorkflowStep, ...] = (
    WorkflowStep(
        "Open the Engineering Workspace",
        "Start in the engineering workspace, the shared environment for "
        "every step below.",
        "available",
    ),
    WorkflowStep(
        "Import CAD Data",
        "Bring in a STEP, IGES or DXF file. Format detection, adapter "
        "selection and canonical geometry/topology extraction run "
        "automatically.",
        CAPABILITIES_BY_KEY["cad-geometry"].status,
    ),
    WorkflowStep(
        "Review Engineering Evidence",
        "Inspect detection confidence, fidelity diagnostics and any "
        "unsupported entities before trusting the result.",
        CAPABILITIES_BY_KEY["cad-geometry"].status,
    ),
    WorkflowStep(
        "Interpret Technical Drawings",
        "Parse a 2D technical drawing — PDF, raster or vector — into "
        "structured dimensions and GD&T. A dedicated workspace review "
        "view is planned.",
        CAPABILITIES_BY_KEY["drawing"].status,
    ),
    WorkflowStep(
        "Select Machining Context",
        "Choose the manufacturing process, machine, tool and material for "
        "the part. Dedicated workspace views are planned.",
        conservative_status(("machining", "machine-tool")),
    ),
    WorkflowStep(
        "Configure Process Parameters",
        "Set the machining parameters for the selected operations, using "
        "deterministic formulas. A dedicated workspace view is planned.",
        CAPABILITIES_BY_KEY["machining"].status,
    ),
    WorkflowStep(
        "Validate Engineering Constraints",
        "Run design-for-manufacturability and process-plan checks against "
        "the configuration. A dedicated validation workspace view is "
        "planned.",
        CAPABILITIES_BY_KEY["quality"].status,
    ),
    WorkflowStep(
        "Review Cost / RFQ Implications",
        "See cycle-time and should-cost estimates for the configured "
        "process. Currently design intent only, with no implementation "
        "yet.",
        CAPABILITIES_BY_KEY["costing"].status,
    ),
    WorkflowStep(
        "Generate a Structured Report",
        "Produce a traceable summary of the engineering decisions made "
        "across the workflow. Planned.",
        "roadmap",
    ),
)


# -- Solutions (PUBLIC-01C) ---------------------------------------------------
# Organized by role/problem, not by internal software module, per the
# PUBLIC-01C brief. Maturity is never hand-picked: it is the most
# conservative status among the capabilities a solution actually draws on
# (see :func:`conservative_status`), so it cannot drift from CAPABILITIES.

@dataclass(frozen=True)
class SolutionGroup:
    key: str
    role: str
    challenge: str
    how_it_helps: str
    capability_keys: tuple[str, ...]

    @property
    def status(self) -> CapabilityStatus:
        return conservative_status(self.capability_keys)

    @property
    def maturity_label(self) -> str:
        return MATURITY_STATUS_LABELS[self.status]

    @property
    def capabilities(self) -> tuple[PublicCapability, ...]:
        return tuple(CAPABILITIES_BY_KEY[key] for key in self.capability_keys)


SOLUTION_GROUPS: tuple[SolutionGroup, ...] = (
    SolutionGroup(
        key="manufacturing-engineering",
        role="Manufacturing Engineering",
        challenge=(
            "Selecting a manufacturing process, calculating machining "
            "parameters and checking design-for-manufacturability in one "
            "place, instead of switching between spreadsheets and rules "
            "of thumb."
        ),
        how_it_helps=(
            "Import CAD geometry, run deterministic machining "
            "calculations and review DFM checks against evidence you can "
            "inspect line by line."
        ),
        capability_keys=("cad-geometry", "machining", "quality"),
    ),
    SolutionGroup(
        key="process-engineering",
        role="Process Engineering",
        challenge=(
            "Defining operations, sequencing them and keeping tooling and "
            "process context consistent across a part's manufacturing "
            "route."
        ),
        how_it_helps=(
            "Structure the process plan around deterministic machining "
            "formulas and machine/tool library data, with a process-plan "
            "validation layer in progress."
        ),
        capability_keys=("machining", "machine-tool", "quality"),
    ),
    SolutionGroup(
        key="quality-engineering",
        role="Quality Engineering",
        challenge=(
            "Turning a 2D technical drawing into structured tolerance and "
            "GD&T evidence, with a traceable validation record."
        ),
        how_it_helps=(
            "Technical drawing parsing already extracts dimensions and "
            "GD&T at the backend level; a dedicated workspace review view "
            "and validation reporting are in progress."
        ),
        capability_keys=("drawing", "quality"),
    ),
    SolutionGroup(
        key="supplier-development",
        role="Supplier Development / Industrialization",
        challenge=(
            "Giving a new supplier a consistent, traceable CAD-to-"
            "manufacturing pipeline during new product introduction."
        ),
        how_it_helps=(
            "CAD import and canonical geometry extraction give suppliers "
            "and internal teams a shared starting point today; broader "
            "process and validation views for a full pipeline are in "
            "progress. MachiningPro AI does not grant supplier approval "
            "on its own."
        ),
        capability_keys=("cad-geometry", "quality"),
    ),
    SolutionGroup(
        key="cost-rfq",
        role="Cost / RFQ",
        challenge=(
            "Getting a cycle-time and should-cost estimate for quoting "
            "without a dedicated engineering tool."
        ),
        how_it_helps=(
            "Cost and RFQ support is design intent today, meant to build "
            "on the same engineering evidence produced earlier in the "
            "workflow."
        ),
        capability_keys=("costing",),
    ),
    SolutionGroup(
        key="technical-project-teams",
        role="Technical Project Teams",
        challenge=(
            "Keeping a shared, traceable view of engineering status "
            "across CAD, drawings, machining and validation for a project "
            "team."
        ),
        how_it_helps=(
            "CAD import and engineering evidence review give a team a "
            "common reference point today; broader cross-discipline "
            "status reporting is in progress."
        ),
        capability_keys=("cad-geometry", "machining", "quality"),
    ),
)


def product_context(config: PublicSiteConfig) -> dict[str, object]:
    """Template context for the Product page (PUBLIC-01C)."""
    ctx = page_context(PAGES_BY_KEY["product"], config)
    ctx.update(
        {
            "capabilities": CAPABILITIES,
            "maturity_groups": capabilities_by_status(),
            "authority_principles": ENGINEERING_AUTHORITY_PRINCIPLES,
            "data_library_foundation": DATA_LIBRARY_FOUNDATION,
            "validation_points": VALIDATION_TRACEABILITY_POINTS,
        }
    )
    return ctx


def how_it_works_context(config: PublicSiteConfig) -> dict[str, object]:
    """Template context for the How It Works page (PUBLIC-01C)."""
    ctx = page_context(PAGES_BY_KEY["how-it-works"], config)
    ctx.update(
        {
            "steps": HOW_IT_WORKS_STEPS,
            "authority_principles": ENGINEERING_AUTHORITY_PRINCIPLES,
        }
    )
    return ctx


def solutions_context(config: PublicSiteConfig) -> dict[str, object]:
    """Template context for the Solutions page (PUBLIC-01C)."""
    ctx = page_context(PAGES_BY_KEY["solutions"], config)
    ctx.update({"solution_groups": SOLUTION_GROUPS})
    return ctx
