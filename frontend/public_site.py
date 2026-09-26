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

ContentStatus = Literal["live", "skeleton"]
NavPlacement = Literal["primary", "company", "legal", "none"]


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
        nav="primary",
    ),
    PublicPage(
        key="how-it-works", path="/how-it-works", nav_label="How It Works",
        heading="How It Works", title=_title("How It Works"),
        description=(
            "The MachiningPro AI engineering workflow: from CAD or drawing input "
            "to analysis, engineering evidence, process configuration and validation."
        ),
        nav="primary",
    ),
    PublicPage(
        key="solutions", path="/solutions", nav_label="Solutions", heading="Solutions",
        title=_title("Solutions"),
        description=(
            "How manufacturing, process and quality engineering teams can use "
            "MachiningPro AI in their day-to-day engineering work."
        ),
        nav="primary",
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


def pages_for(nav: NavPlacement) -> tuple[PublicPage, ...]:
    return tuple(p for p in PUBLIC_PAGES if p.nav == nav)


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
    return PublicSiteConfig(
        base_url=base,
        response_time_statement=statement,
        social_links=tuple(socials),
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
        },
        "page": page,
        "canonical_url": config.canonical_url(page.path),
        "config": config,
        "primary_nav": pages_for("primary"),
        "company_nav": pages_for("company"),
        "legal_nav": pages_for("legal"),
    }
