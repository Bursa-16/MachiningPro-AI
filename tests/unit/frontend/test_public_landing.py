"""PUBLIC-01B — Public home page tests.

Supersedes the PUBLIC-0A landing tests: the home page was migrated off the
legacy ``landing.html`` / ``public_base.html`` shell onto the PUBLIC-01A
public layout (``public/home.html``), with real product-grounded content —
see docs/superpowers/specs/2026-09-26-public-prelogin-ux-design.md.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from frontend.app import app
from frontend.public_site import CAPABILITIES, PAGES_BY_KEY, WORKFLOW_STEPS


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, follow_redirects=False)


@pytest.fixture()
def home(client: TestClient) -> str:
    return client.get("/").text


# -- Route behavior ----------------------------------------------------------

class TestRoutes:
    def test_root_returns_200(self, client: TestClient) -> None:
        assert client.get("/").status_code == 200

    def test_root_is_html(self, client: TestClient) -> None:
        resp = client.get("/")
        assert "text/html" in resp.headers["content-type"]

    def test_workspace_still_works(self, client: TestClient) -> None:
        resp = client.get("/ui/")
        assert resp.status_code == 200
        assert "Dashboard" in resp.text

    def test_app_redirects_to_workspace(self, client: TestClient) -> None:
        resp = client.get("/app")
        assert resp.status_code == 302
        assert resp.headers["location"] == "/ui/"

    def test_cad_import_still_works(self, client: TestClient) -> None:
        assert client.get("/ui/cad-import").status_code == 200


# -- Structure / branding -----------------------------------------------------

class TestHomeContent:
    def test_uses_public_shell(self, home: str) -> None:
        assert "mp-pub-header" in home
        assert "mp-pub-footer" in home

    def test_product_name(self, home: str) -> None:
        assert "MachiningPro AI" in home

    def test_exactly_one_h1(self, home: str) -> None:
        assert home.count("<h1") == 1

    def test_hero_lead_present(self, home: str) -> None:
        assert "mp-home-hero__lead" in home

    def test_workflow_section(self, home: str) -> None:
        # PUBLIC-01C test hardening: the previous version of this test
        # (`"how-it-works" in home.lower() or ...`) was vacuous — every page
        # contains an href="/how-it-works" nav/CTA link, so it could not
        # fail even if the whole "How MachiningPro AI Works" section were
        # deleted. Assert the section's own heading id and at least one
        # data-driven step actually render instead.
        assert 'id="mp-home-howitworks-h"' in home
        assert "How MachiningPro AI Works</h2>" in home
        for step in WORKFLOW_STEPS:
            assert step.title in home, f"missing workflow step: {step.title}"

    def test_step_format(self, home: str) -> None:
        assert "STEP" in home or "STP" in home

    def test_no_hardcoded_contact_details(self, home: str) -> None:
        # The legacy landing page hard-coded a mailto: address; the public
        # layer must route contact through the /contact page instead.
        assert "mailto:" not in home
        assert "machineryproai.com" not in home.lower()


# -- CTA hierarchy ------------------------------------------------------------

class TestCTAs:
    def test_request_demo_cta(self, home: str) -> None:
        assert re.search(r'href="/contact" class="mp-btn mp-btn--primary[^"]*">Request Demo<', home)

    def test_how_it_works_cta(self, home: str) -> None:
        pattern = r'href="/how-it-works" class="mp-btn mp-btn--secondary[^"]*">How It Works<'
        assert re.search(pattern, home)

    def test_sign_in_cta(self, home: str) -> None:
        assert re.search(r'href="/app" class="mp-btn mp-btn--ghost[^"]*">Sign In<', home)

    def test_final_cta_present(self, home: str) -> None:
        assert "Explore How It Works" in home

    def test_no_dead_header_links(self, client: TestClient, home: str) -> None:
        # Every primary-nav link in the header must resolve to a real,
        # registered route (200), not a dead link.
        links = re.findall(r'class="mp-pub-nav__link"[^>]*href="([^"]+)"', home)
        assert links, "expected primary nav links in the rendered header"
        for href in set(links):
            assert client.get(href).status_code == 200, href

    def test_no_fake_urgency(self, home: str) -> None:
        for phrase in ("limited spots", "act now", "hurry", "countdown"):
            assert phrase not in home.lower()


# -- Core capabilities / product maturity ------------------------------------

class TestCapabilitiesAndMaturity:
    def test_all_capabilities_rendered(self, home: str) -> None:
        # Jinja autoescapes "&" to "&amp;" in rendered HTML.
        for cap in CAPABILITIES:
            assert cap.name.replace("&", "&amp;") in home

    def test_status_labels_present(self, home: str) -> None:
        assert "Available" in home
        assert "In Development" in home

    def test_no_capability_overclaimed_as_available(self, home: str) -> None:
        # PUBLIC-01C test hardening: the previous version of this test only
        # asserted that at least one CAPABILITIES entry has status
        # "available" — a fact about the static data, unconnected to what
        # actually renders, so it could not catch a template bug that
        # mislabels a card's maturity. For every capability, locate its
        # rendered card and verify the badge status/label match the
        # registry exactly (Jinja escapes "&" to "&amp;").
        for cap in CAPABILITIES:
            escaped_name = cap.name.replace("&", "&amp;")
            pattern = (
                r'<span class="mp-badge mp-badge--status-(\w+)">([^<]+)</span>\s*'
                r'</div>\s*<h3 class="mp-card__title">' + re.escape(escaped_name) + r"</h3>"
            )
            match = re.search(pattern, home)
            assert match, f"no capability card found for {cap.name!r}"
            rendered_status, rendered_label = match.groups()
            assert rendered_status == cap.status, (
                f"{cap.name}: rendered badge status {rendered_status!r} != "
                f"registry status {cap.status!r}"
            )
            assert rendered_label == cap.capability_label

    def test_maturity_section_present(self, home: str) -> None:
        assert "Product Maturity" in home
        assert "Roadmap" in home


# -- No fabricated content -----------------------------------------------------

class TestNoFabrication:
    def test_no_fake_testimonials(self, home: str) -> None:
        for word in ["testimonial", "customer said", "client quote"]:
            assert word.lower() not in home.lower()

    def test_no_fake_logos(self, home: str) -> None:
        assert "customer-logo" not in home.lower()

    def test_no_prices(self, home: str) -> None:
        assert not re.search(r"[$€£₺]\s?\d", home)

    def test_no_pricing_tiers_invented(self, home: str) -> None:
        # Package/tier names are not yet approved for publication (see
        # /pricing, still a skeleton); the home page must not invent them.
        for tier in ("Starter", "Professional tier", "Enterprise tier"):
            assert tier not in home

    def test_no_roi_or_superlative_claims(self, home: str) -> None:
        for phrase in ("industry leading", "world's best", "guaranteed accuracy",
                        "roi of", "% faster", "% more accurate"):
            assert phrase not in home.lower()

    def test_no_customer_names(self, home: str) -> None:
        for word in ["partnered with", "trusted by", "case study:"]:
            assert word.lower() not in home.lower()


# -- Metadata / SEO -----------------------------------------------------------

class TestMetadata:
    def test_title_tag(self, home: str) -> None:
        home_page = PAGES_BY_KEY["home"]
        assert f"<title>{home_page.title}</title>" in home

    def test_meta_description(self, home: str) -> None:
        assert 'name="description"' in home

    def test_og_title_and_description(self, home: str) -> None:
        assert 'property="og:title"' in home
        assert 'property="og:description"' in home

    def test_noindex_not_present_on_home(self, home: str) -> None:
        assert 'name="robots" content="noindex' not in home

    def test_home_not_noindex_header(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.headers.get("x-robots-tag") is None


# -- Accessibility structure ---------------------------------------------------

class TestAccessibilityStructure:
    def test_landmarks(self, home: str) -> None:
        assert "<header" in home and "<main" in home and "<footer" in home

    def test_skip_link(self, home: str) -> None:
        assert 'href="#mp-pub-main"' in home

    def test_all_imgs_have_alt(self, home: str) -> None:
        for img in re.findall(r"<img[^>]+>", home):
            assert 'alt="' in img, f"Missing alt: {img[:60]}"

    def test_no_content_only_communicated_by_color(self, home: str) -> None:
        # Status badges must carry text, not just a color class.
        assert "Available" in home
        assert "In Development" in home
