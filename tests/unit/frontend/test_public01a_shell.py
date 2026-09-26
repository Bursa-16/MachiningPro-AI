"""PUBLIC-01A — MachiningPro AI public shell, page registry and metadata."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from frontend.app import app
from frontend.public_site import (
    PAGES_BY_KEY,
    PUBLIC_PAGES,
    PublicSiteConfig,
    load_config,
    pages_for,
)

SKELETON_PAGES = [p for p in PUBLIC_PAGES if p.content_status == "skeleton"]


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, follow_redirects=False)


# -- Registry --------------------------------------------------------------

class TestRegistry:
    def test_required_public_pages_registered(self) -> None:
        for key in ("home", "product", "how-it-works", "solutions", "case-studies",
                    "pricing", "faq", "about", "contact", "privacy", "terms"):
            assert key in PAGES_BY_KEY

    def test_titles_and_descriptions_unique(self) -> None:
        titles = [p.title for p in PUBLIC_PAGES]
        descs = [p.description for p in PUBLIC_PAGES]
        assert len(set(titles)) == len(titles)
        assert len(set(descs)) == len(descs)

    def test_every_title_names_the_product(self) -> None:
        for page in PUBLIC_PAGES:
            assert "MachiningPro AI" in page.title
            assert "MachineryPro" not in page.title + page.description

    def test_description_lengths_are_reasonable(self) -> None:
        for page in PUBLIC_PAGES:
            assert 50 <= len(page.description) <= 200, page.key

    def test_primary_nav_matches_brief_and_is_small(self) -> None:
        labels = [p.nav_label for p in pages_for("primary")]
        assert labels == ["Product", "How It Works", "Solutions", "Case Studies",
                          "Pricing", "FAQ", "About"]

    def test_skeletons_are_not_indexable(self) -> None:
        assert SKELETON_PAGES
        assert all(not p.indexable for p in SKELETON_PAGES)


# -- Routes ----------------------------------------------------------------

class TestRoutes:
    @pytest.mark.parametrize("page", SKELETON_PAGES, ids=lambda p: p.key)
    def test_skeleton_route_renders(self, client: TestClient, page) -> None:
        resp = client.get(page.path)
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert resp.headers["x-robots-tag"] == "noindex, follow"
        html = resp.text
        assert f"<title>{page.title}</title>" in html
        assert f'<meta name="description" content="{page.description}" />' in html
        assert '<meta name="robots" content="noindex, follow" />' in html
        assert "This page is being prepared." in html

    def test_existing_routes_unchanged(self, client: TestClient) -> None:
        assert client.get("/").status_code == 200
        assert client.get("/ui/").status_code == 200
        resp = client.get("/app")
        assert resp.status_code == 302 and resp.headers["location"] == "/ui/"

    def test_public_pages_do_not_load_dev_tailwind_cdn(self, client: TestClient) -> None:
        assert "cdn.tailwindcss.com" not in client.get("/product").text


# -- Shell structure -------------------------------------------------------

class TestShell:
    @pytest.fixture()
    def html(self, client: TestClient) -> str:
        return client.get("/how-it-works").text

    def test_semantic_landmarks(self, html: str) -> None:
        assert "<header" in html and "<main" in html and "<footer" in html
        assert html.count("<h1") == 1
        assert 'href="#mp-pub-main"' in html and 'id="mp-pub-main"' in html

    def test_header_ctas(self, html: str) -> None:
        assert re.search(r'href="/contact" class="mp-btn mp-btn--primary">Request Demo<', html)
        assert re.search(r'href="/app" class="mp-btn mp-btn--ghost">Sign In<', html)

    def test_current_page_marked(self, html: str) -> None:
        assert 'href="/how-it-works" aria-current="page"' in html

    def test_compact_menu_is_native_disclosure(self, html: str) -> None:
        assert '<details class="mp-pub-menu">' in html
        assert 'aria-label="Open site menu"' in html

    def test_footer_links_legal_pages(self, html: str) -> None:
        assert 'href="/privacy"' in html and 'href="/terms"' in html

    def test_mobile_contact_button_is_internal(self, html: str) -> None:
        assert '<a class="mp-pub-fab" href="/contact">Request Demo</a>' in html
        assert "wa.me" not in html and "whatsapp" not in html.lower()

    def test_no_fab_on_contact_page(self, client: TestClient) -> None:
        assert "mp-pub-fab" not in client.get("/contact").text.split("</footer>")[1]

    def test_open_graph_present(self, html: str) -> None:
        for prop in ("og:site_name", "og:title", "og:description", "og:type"):
            assert f'property="{prop}"' in html
        assert 'name="twitter:card"' in html


# -- No fabrication --------------------------------------------------------

class TestNoFabrication:
    @pytest.mark.parametrize("page", SKELETON_PAGES, ids=lambda p: p.key)
    def test_no_invented_facts(self, client: TestClient, page) -> None:
        html = client.get(page.path).text.lower()
        for banned in ("testimonial", "customer-logo", "★", "mailto:", "tel:",
                       "googletagmanager", "gtag(", "google-analytics",
                       "maps.google", "linkedin.com", "twitter.com", "x.com/"):
            assert banned not in html, f"{banned!r} on {page.path}"

    def test_pricing_has_no_price_figures(self, client: TestClient) -> None:
        html = client.get("/pricing").text
        assert not re.search(r"[$€£₺]\s?\d", html)
        assert "available on request" in html

    def test_legal_pages_flagged_as_unreviewed(self, client: TestClient) -> None:
        for path in ("/privacy", "/terms"):
            assert "not been legally reviewed" in client.get(path).text

    def test_no_canonical_without_configured_base_url(self, client: TestClient) -> None:
        assert 'rel="canonical"' not in client.get("/faq").text


# -- Configuration ---------------------------------------------------------

class TestConfig:
    def test_defaults_are_empty(self) -> None:
        cfg = load_config({})
        assert cfg == PublicSiteConfig()
        assert cfg.canonical_url("/faq") is None

    def test_base_url_requires_https(self) -> None:
        assert load_config({"MACHININGPRO_PUBLIC_BASE_URL": "http://x.test"}).base_url is None
        cfg = load_config({"MACHININGPRO_PUBLIC_BASE_URL": "https://x.test/"})
        assert cfg.canonical_url("/faq") == "https://x.test/faq"

    def test_only_configured_https_social_links(self) -> None:
        cfg = load_config({
            "MACHININGPRO_SOCIAL_LINKEDIN": "https://www.linkedin.com/company/example",
            "MACHININGPRO_SOCIAL_GITHUB": "javascript:alert(1)",
        })
        assert [s.platform for s in cfg.social_links] == ["linkedin"]

    def test_configured_values_render(self, client: TestClient, monkeypatch) -> None:
        monkeypatch.setenv("MACHININGPRO_PUBLIC_BASE_URL", "https://example.test")
        monkeypatch.setenv("MACHININGPRO_RESPONSE_TIME", "We aim to respond within 1 business day.")
        monkeypatch.setenv("MACHININGPRO_SOCIAL_GITHUB", "https://github.com/example")
        html = client.get("/faq").text
        assert '<link rel="canonical" href="https://example.test/faq" />' in html
        assert '<meta property="og:url" content="https://example.test/faq" />' in html
        assert "We aim to respond within 1 business day." in html
        assert 'href="https://github.com/example" rel="noopener noreferrer"' in html
