"""
Tool Holder Catalog API router.

Provides read endpoints for browsing the curated tool holder catalog.
Registry is built at module import — idempotent, no env var required.

PRIVATE_SOURCE_PATH_EXPOSED=NO
FALSE_HOLDER_RECOMMENDATION_CLAIM=NO
FALSE_COMPATIBILITY_CLAIM=NO
"""

from fastapi import APIRouter, HTTPException, Query

from backend.tool_holders.catalog_models import (
    ToolHolderCatalogRecord,
    ToolHolderCatalogSummary,
)
from backend.tool_holders.seed_catalog import (
    _SOURCE_TITLE,
    get_catalog,
    get_categories,
    get_collet_families,
    get_machine_interfaces,
    get_manufacturers,
    get_tool_interfaces,
)

router = APIRouter(prefix="/api/tool-holders", tags=["tool-holders"])

_CATALOG: dict[str, ToolHolderCatalogRecord] = {}


def _build_registry() -> None:
    for record in get_catalog():
        _CATALOG[record.stable_id] = record


_build_registry()


@router.get("/schema")
def tool_holders_schema() -> dict:
    """Return all filter options for the tool holder catalog UI."""
    return {
        "manufacturers": get_manufacturers(),
        "categories": get_categories(),
        "machine_interfaces": get_machine_interfaces(),
        "tool_interfaces": get_tool_interfaces(),
        "collet_families": get_collet_families(),
        "holder_count": len(_CATALOG),
        "evidence_status": "MANUFACTURER_CATALOG",
    }


@router.get("/summary", response_model=ToolHolderCatalogSummary)
def tool_holders_summary() -> ToolHolderCatalogSummary:
    """Return catalog summary statistics."""
    return ToolHolderCatalogSummary(
        holder_count=len(_CATALOG),
        manufacturer_count=len(get_manufacturers()),
        category_count=len(get_categories()),
        machine_interface_count=len(get_machine_interfaces()),
        tool_interface_count=len(get_tool_interfaces()),
        manufacturers=get_manufacturers(),
        categories=get_categories(),
        machine_interfaces=get_machine_interfaces(),
        tool_interfaces=get_tool_interfaces(),
        source_title=_SOURCE_TITLE,
        evidence_status="MANUFACTURER_CATALOG",
    )


@router.get("/manufacturers")
def tool_holders_manufacturers() -> dict:
    """Return list of manufacturers in catalog."""
    return {"manufacturers": get_manufacturers(), "count": len(get_manufacturers())}


@router.get("/categories")
def tool_holders_categories() -> dict:
    """Return list of holder categories in catalog."""
    return {"categories": get_categories(), "count": len(get_categories())}


@router.get("/interfaces")
def tool_holders_interfaces() -> dict:
    """Return machine and tool interface lists."""
    return {
        "machine_interfaces": get_machine_interfaces(),
        "tool_interfaces": get_tool_interfaces(),
        "collet_families": get_collet_families(),
    }


def _filter_catalog(
    manufacturer: str | None,
    category: str | None,
    machine_interface: str | None,
    tool_interface: str | None,
    collet_family: str | None,
) -> list[ToolHolderCatalogRecord]:
    results = list(_CATALOG.values())
    if manufacturer:
        ml = manufacturer.lower()
        results = [r for r in results if r.manufacturer.lower() == ml]
    if category:
        cl = category.lower()
        results = [r for r in results if r.holder_category.lower() == cl]
    if machine_interface:
        mi = machine_interface.upper().replace(" ", "")
        results = [r for r in results
                   if r.machine_interface_key.upper().replace(" ", "") == mi]
    if tool_interface:
        ti = tool_interface.upper()
        results = [r for r in results if r.tool_interface_key.upper() == ti]
    if collet_family:
        cf = collet_family.upper()
        results = [r for r in results
                   if r.collet_system and r.collet_system.upper() == cf]
    return results


@router.get("", response_model=list[ToolHolderCatalogRecord])
def tool_holders_list(
    manufacturer: str | None = Query(None),
    category: str | None = Query(None),
    machine_interface: str | None = Query(None),
    tool_interface: str | None = Query(None),
    collet_family: str | None = Query(None),
) -> list[ToolHolderCatalogRecord]:
    """
    Return filtered list of tool holders.
    All filters are optional and case-insensitive.
    """
    return _filter_catalog(manufacturer, category, machine_interface, tool_interface, collet_family)


@router.get("/{holder_id}", response_model=ToolHolderCatalogRecord)
def tool_holder_detail(holder_id: str) -> ToolHolderCatalogRecord:
    """Return a single tool holder record by stable ID."""
    record = _CATALOG.get(holder_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Holder not found: {holder_id!r}")
    return record
