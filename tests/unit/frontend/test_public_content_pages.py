"""PUBLIC-01C — Product / How It Works / Solutions content pages.

Product, How It Works and Solutions were migrated off the generic
skeleton loop onto their own templates and centralized data structures in
``frontend.public_site`` (``CAPABILITIES`` with ``key_capabilities``,
``HOW_IT_WORKS_STEPS``, ``SOLUTION_GROUPS``) — see
docs/superpowers/specs/2026-09-26-public-prelogin-ux-design.md.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from frontend.app import app
from frontend.public_site import (
    CAPABILITIES,
    HOW_IT_WORKS_STEPS,
    PAGES_BY_KEY,
    SOLUTION_GROUPS,
)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, follow_redirects=False)


@pytest.fixture()
def product(client: TestClient) -> str:
    return client.get("/product").text


@pytest.fixture()
def how_it_works(client: TestClient) -> str:
    return client.get("/how-it-works").text


@pytest.fixture()
def solutions(client: TestClient) -> str:
    return client.get("/solutions").text


def _no_dead_links(client: TestClient, html: str) -> None:
    links = re.findall(r'class="mp-pub-nav__link"[^>]*href="([^"]+)"', html)
    assert links, "expected primary nav links in the rendered header"
    for href in set(links):
        assert client.get(href).status_code == 200, href


# -- Product -------------------------------------------------------------

class TestProductPage:
    def test_returns_200(self, client: TestClient) -> None:
        assert client.get("/product").status_code == 200

    def test_one_h1(self, product: str) -> None:
        assert product.count("<h1") == 1

    def test_title_tag(self, product: str) -> None:
        page = PAGES_BY_KEY["product"]
        assert f"<title>{page.title}</title>" in product

    def test_not_noindex(self, client: TestClient) -> None:
        resp = client.get("/product")
        assert resp.headers.get("x-robots-tag") is None
        assert 'name="robots" content="noindex' not in resp.text

    def test_capability_status_labels_match_registry(self, product: str) -> None:
        # Every CAPABILITIES entry's rendered badge must match its actual
        # registry status — not merely "at least one available exists".
        for cap in CAPABILITIES:
            escaped_name = cap.name.replace("&", "&amp;")
            pattern = (
                r'<span class="mp-badge mp-badge--status-(\w+)">([^<]+)</span>\s*'
                r'</div>\s*<h3 class="mp-card__title">' + re.escape(escaped_name) + r"</h3>"
            )
            match = re.search(pattern, product)
            assert match, f"no capability card found for {cap.name!r}"
            rendered_status, rendered_label = match.groups()
            assert rendered_status == cap.status
            assert rendered_label == cap.capability_label

    def test_engineering_authority_statement_present(self, product: str) -> None:
        assert "Engineering Authority Model" in product
        assert "authoritative" in product.lower()

    def test_maturity_matrix_present(self, product: str) -> None:
        assert "Product Maturity Matrix" in product
        assert "Roadmap" in product

    def test_no_fabricated_claims(self, product: str) -> None:
        low = product.lower()
        for phrase in (
            "testimonial", "customer-logo", "trusted by", "partnered with",
            "industry leading", "world's best", "guaranteed accuracy",
            "roi of", "% faster", "% more accurate",
        ):
            assert phrase not in low
        assert not re.search(r"[$€£₺]\s?\d", product)

    def test_cross_links_to_how_it_works_and_solutions(
        self, client: TestClient, product: str,
    ) -> None:
        assert 'href="/how-it-works"' in product
        assert 'href="/solutions"' in product
        assert client.get("/how-it-works").status_code == 200
        assert client.get("/solutions").status_code == 200

    def test_no_dead_header_links(self, client: TestClient, product: str) -> None:
        _no_dead_links(client, product)


# -- How It Works ----------------------------------------------------------

class TestHowItWorksPage:
    def test_returns_200(self, client: TestClient) -> None:
        assert client.get("/how-it-works").status_code == 200

    def test_one_h1(self, how_it_works: str) -> None:
        assert how_it_works.count("<h1") == 1

    def test_title_tag(self, how_it_works: str) -> None:
        page = PAGES_BY_KEY["how-it-works"]
        assert f"<title>{page.title}</title>" in how_it_works

    def test_not_noindex(self, client: TestClient) -> None:
        resp = client.get("/how-it-works")
        assert resp.headers.get("x-robots-tag") is None

    def test_workflow_steps_actually_rendered(self, how_it_works: str) -> None:
        # Must not be vacuous: assert every step's own data (index, title,
        # status label where non-available) actually appears attached to
        # its own <li data-hiw-step="N">, not just present anywhere on the
        # page.
        for i, step in enumerate(HOW_IT_WORKS_STEPS, start=1):
            pattern = (
                rf'data-hiw-step="{i}">.*?<span class="mp-home-steps__index"[^>]*>{i}</span>'
                rf".*?{re.escape(step.title)}"
            )
            assert re.search(pattern, how_it_works, re.DOTALL), (
                f"step {i} ({step.title!r}) not found at its own position"
            )
            if step.status != "available":
                assert step.status_label in how_it_works

    def test_no_autonomous_ai_claim(self, how_it_works: str) -> None:
        # The page legitimately states the *negative* ("does not make
        # autonomous manufacturing decisions"), so check for an affirmative
        # claim rather than banning the bare word "autonomous".
        low = how_it_works.lower()
        for phrase in (
            "fully automated decision", "replaces the engineer",
            "no human review needed", "makes autonomous",
            "acts autonomously", "autonomous decision-making",
        ):
            assert phrase not in low
        assert "does not make autonomous manufacturing decisions" in low

    def test_user_control_section_present(self, how_it_works: str) -> None:
        assert "You Stay in Control" in how_it_works
        assert "advisory" in how_it_works.lower()

    def test_cta_links_valid(self, client: TestClient, how_it_works: str) -> None:
        primary = r'href="/contact" class="mp-btn mp-btn--primary[^"]*">Request Demo<'
        secondary = r'href="/product" class="mp-btn mp-btn--secondary[^"]*">Explore Product<'
        assert re.search(primary, how_it_works)
        assert re.search(secondary, how_it_works)
        assert client.get("/contact").status_code == 200
        assert client.get("/product").status_code == 200

    def test_no_dead_header_links(self, client: TestClient, how_it_works: str) -> None:
        _no_dead_links(client, how_it_works)


# -- Solutions ---------------------------------------------------------------

class TestSolutionsPage:
    def test_returns_200(self, client: TestClient) -> None:
        assert client.get("/solutions").status_code == 200

    def test_one_h1(self, solutions: str) -> None:
        assert solutions.count("<h1") == 1

    def test_title_tag(self, solutions: str) -> None:
        page = PAGES_BY_KEY["solutions"]
        assert f"<title>{page.title}</title>" in solutions

    def test_not_noindex(self, client: TestClient) -> None:
        resp = client.get("/solutions")
        assert resp.headers.get("x-robots-tag") is None

    def test_every_solution_group_rendered(self, solutions: str) -> None:
        for group in SOLUTION_GROUPS:
            assert f'data-solution="{group.key}"' in solutions
            assert group.role in solutions

    def test_maturity_status_mapped_correctly(self, solutions: str) -> None:
        for group in SOLUTION_GROUPS:
            pattern = (
                rf'data-solution="{re.escape(group.key)}">\s*'
                rf'<div class="mp-card__meta">\s*'
                r'<span class="mp-badge mp-badge--status-(\w+)">([^<]+)</span>'
            )
            match = re.search(pattern, solutions)
            assert match, f"no card found for solution {group.key!r}"
            rendered_status, rendered_label = match.groups()
            assert rendered_status == group.status
            assert rendered_label == group.maturity_label

    def test_no_customer_names(self, solutions: str) -> None:
        low = solutions.lower()
        for word in ["partnered with", "trusted by", "case study:", "customer said"]:
            assert word not in low

    def test_no_quantified_roi_claims(self, solutions: str) -> None:
        low = solutions.lower()
        for phrase in ("reduce cost by", "increase productivity by", "% faster", "roi of"):
            assert phrase not in low
        assert not re.search(r"\d+%", solutions)

    def test_cross_links_to_product_and_request_demo(
        self, client: TestClient, solutions: str,
    ) -> None:
        assert 'href="/product"' in solutions
        assert 'href="/contact"' in solutions
        assert client.get("/product").status_code == 200

    def test_no_dead_header_links(self, client: TestClient, solutions: str) -> None:
        _no_dead_links(client, solutions)


# -- SEO ----------------------------------------------------------------------

class TestSEO:
    def test_unique_titles(self, product: str, how_it_works: str, solutions: str) -> None:
        titles = [
            re.search(r"<title>([^<]+)</title>", html).group(1)
            for html in (product, how_it_works, solutions)
        ]
        assert len(set(titles)) == 3

    def test_unique_descriptions(self, product: str, how_it_works: str, solutions: str) -> None:
        descs = [
            re.search(r'name="description" content="([^"]+)"', html).group(1)
            for html in (product, how_it_works, solutions)
        ]
        assert len(set(descs)) == 3

    def test_canonical_only_with_configured_base_url(self, client: TestClient) -> None:
        for path in ("/product", "/how-it-works", "/solutions"):
            assert 'rel="canonical"' not in client.get(path).text

    def test_canonical_renders_when_configured(self, client: TestClient, monkeypatch) -> None:
        monkeypatch.setenv("MACHININGPRO_PUBLIC_BASE_URL", "https://example.test")
        for path in ("/product", "/how-it-works", "/solutions"):
            html = client.get(path).text
            assert f'<link rel="canonical" href="https://example.test{path}" />' in html

    def test_no_accidental_noindex(self, client: TestClient) -> None:
        for path in ("/product", "/how-it-works", "/solutions"):
            resp = client.get(path)
            assert resp.headers.get("x-robots-tag") is None
            assert 'name="robots" content="noindex' not in resp.text


# -- Accessibility -------------------------------------------------------------

class TestAccessibility:
    @pytest.mark.parametrize("path", ["/product", "/how-it-works", "/solutions"])
    def test_semantic_landmarks(self, client: TestClient, path: str) -> None:
        html = client.get(path).text
        assert "<header" in html and "<main" in html and "<footer" in html
        assert 'href="#mp-pub-main"' in html

    @pytest.mark.parametrize("path", ["/product", "/how-it-works", "/solutions"])
    def test_no_duplicate_ids(self, client: TestClient, path: str) -> None:
        html = client.get(path).text
        ids = re.findall(r'id="([^"]+)"', html)
        duplicates = {i for i in ids if ids.count(i) > 1}
        assert not duplicates, f"{path}: duplicate ids {duplicates}"

    @pytest.mark.parametrize("path", ["/product", "/how-it-works", "/solutions"])
    def test_status_communicated_as_text(self, client: TestClient, path: str) -> None:
        # Badges must carry visible text, not rely on color alone.
        html = client.get(path).text
        has_text_badge = re.search(r"mp-badge[^>]*>[A-Za-z]", html)
        assert has_text_badge or "Available" in html or "In Development" in html

    @pytest.mark.parametrize("path", ["/product", "/how-it-works", "/solutions"])
    def test_heading_hierarchy_no_skip(self, client: TestClient, path: str) -> None:
        html = client.get(path).text
        levels = [int(t) for t in re.findall(r"<h([1-4])[ >]", html)]
        assert levels[0] == 1
        for prev, curr in zip(levels, levels[1:], strict=False):
            assert curr <= prev + 1, f"{path}: heading jumped from h{prev} to h{curr}"
