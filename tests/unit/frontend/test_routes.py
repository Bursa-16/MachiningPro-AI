"""Route integrity and workstation reconciliation tests."""

import pytest
from fastapi.testclient import TestClient

from frontend.app import app

PLANNED_ROUTES = (
    ("/ui/geometry", "Geometry / Topology"),
    ("/ui/machining", "Machining"),
    ("/ui/tools", "Tools & Parameters"),
    ("/ui/materials", "Materials"),
    ("/ui/validation", "Validation"),
    ("/ui/ai-assistant", "AI Assistant"),
)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize(("href", "label"), PLANNED_ROUTES)
def test_planned_route_returns_placeholder(
    client: TestClient,
    href: str,
    label: str,
) -> None:
    response = client.get(href)

    assert response.status_code == 200
    assert "PLANNED" in response.text
    assert label.replace("&", "&amp;") in response.text
    assert f'href="{href}"' in response.text
    assert 'aria-current="page"' in response.text


def test_workstation_keeps_modules_in_sidebar_only(client: TestClient) -> None:
    html = client.get("/ui/").text

    assert "mp-nav-group" in html
    assert "mp-action-cards" not in html
    assert "Engineering Modules" not in html
    assert "Architecture Principle" not in html


def test_honing_and_lapping_rows_are_not_marked_advisory(client: TestClient) -> None:
    html = client.get("/ui/").text
    authority_after_empty_value = (
        '<span class="mp-prop-val mp-prop-val--muted">—</span>'
        '<span class="mp-authority'
    )

    honing_row = html.split("Honing stone", maxsplit=1)[1].split("</div>", maxsplit=1)[0]
    lapping_row = html.split("Lapping plate", maxsplit=1)[1].split("</div>", maxsplit=1)[0]
    assert authority_after_empty_value not in honing_row
    assert authority_after_empty_value not in lapping_row
