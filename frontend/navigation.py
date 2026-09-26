"""MachiningPro AI — post-login navigation model (UX-01A).

Single source of truth for the engineering workspace sidebar.

The sidebar is organised into a small number of groups so that the full
module list is not visible at once. Only the group that contains the
active page is expanded by default; every other group can be opened on
demand and the browser remembers the viewer's choice (see
``static/js/app-shell.js``).

Rules:
* Every entry maps to a route that already exists in ``routers/ui.py``.
  No route is invented here to match a target diagram.
* ``status`` is factual: ``"available"`` for implemented modules,
  ``"planned"`` for deliberate placeholders.
* This module contains no authorization logic. Role-based visibility is
  prepared for (``roles`` field) but not enforced, because the backend has
  no role contract yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

NavStatus = Literal["available", "planned"]


@dataclass(frozen=True)
class NavItem:
    """A single sidebar destination."""

    id: str
    label: str
    href: str
    icon: str
    status: NavStatus = "available"
    # Reserved for future role-aware disclosure (UX-01C/D). Empty means
    # "visible to everyone". Not an access-control mechanism.
    roles: tuple[str, ...] = ()

    @property
    def badge(self) -> str:
        return "PLANNED" if self.status == "planned" else ""


@dataclass(frozen=True)
class NavGroup:
    """A labelled cluster of sidebar destinations."""

    id: str
    label: str
    items: tuple[NavItem, ...]
    # Non-collapsible groups render as a static section (e.g. the
    # always-visible Dashboard entry).
    collapsible: bool = True


@dataclass(frozen=True)
class NavGroupView:
    """Render-ready group state for one request."""

    id: str
    label: str
    collapsible: bool
    is_active: bool
    is_open: bool
    items: tuple[NavItemView, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class NavItemView:
    """Render-ready item state for one request."""

    id: str
    label: str
    href: str
    icon: str
    badge: str
    is_active: bool


# -- Sidebar definition -----------------------------------------------------
# Group labels are part of the existing UI contract (tests/unit/frontend).

NAV_GROUPS: tuple[NavGroup, ...] = (
    NavGroup(
        id="workspace",
        label="Workspace",
        collapsible=False,
        items=(NavItem("dashboard", "Dashboard", "/ui/", "home"),),
    ),
    NavGroup(
        id="engineering-data",
        label="Engineering Data",
        items=(
            NavItem("cad-import", "CAD Import", "/ui/cad-import", "upload"),
            NavItem("geometry", "Geometry / Topology", "/ui/geometry", "box", "planned"),
        ),
    ),
    NavGroup(
        id="manufacturing",
        label="Manufacturing",
        items=(
            NavItem("machining", "Machining", "/ui/machining", "settings", "planned"),
            NavItem("tools", "Tools & Parameters", "/ui/tools", "wrench", "planned"),
            NavItem("materials", "Materials", "/ui/materials", "layers", "planned"),
        ),
    ),
    NavGroup(
        id="assurance",
        label="Assurance",
        items=(
            NavItem("validation", "Validation", "/ui/validation", "shield-check", "planned"),
        ),
    ),
    NavGroup(
        id="intelligence",
        label="Intelligence",
        items=(
            NavItem("ai-assistant", "AI Assistant", "/ui/ai-assistant", "sparkles", "planned"),
        ),
    ),
)


def iter_nav_items() -> tuple[NavItem, ...]:
    """All sidebar items in display order."""
    return tuple(item for group in NAV_GROUPS for item in group.items)


def legacy_nav_items() -> list[dict[str, str]]:
    """Flat list in the pre-UX-01A ``NAV_ITEMS`` shape (backward compatible)."""
    return [
        {"label": i.label, "href": i.href, "icon": i.icon, "badge": i.badge}
        for i in iter_nav_items()
    ]


def build_sidebar(active_href: str) -> tuple[NavGroupView, ...]:
    """Resolve open/active state for every group for the current page."""
    views: list[NavGroupView] = []
    for group in NAV_GROUPS:
        items = tuple(
            NavItemView(
                id=i.id,
                label=i.label,
                href=i.href,
                icon=i.icon,
                badge=i.badge,
                is_active=i.href == active_href,
            )
            for i in group.items
        )
        is_active = any(i.is_active for i in items)
        views.append(
            NavGroupView(
                id=group.id,
                label=group.label,
                collapsible=group.collapsible,
                is_active=is_active,
                # Only the group holding the current page opens by default.
                is_open=is_active or not group.collapsible,
                items=items,
            )
        )
    return tuple(views)
