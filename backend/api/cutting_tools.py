"""
Cutting Tool Catalog API router.

Provides read endpoints for browsing the curated cutting tool catalog.
Registry is built at module import — idempotent, no env var required.

PRIVATE_SOURCE_PATH_EXPOSED=NO
FALSE_TOOL_RECOMMENDATION_CLAIM=NO
"""

from fastapi import APIRouter, HTTPException, Query

from backend.cutting_tools.catalog_models import (
    CuttingToolCatalogRecord,
    CuttingToolCatalogSummary,
)
from backend.cutting_tools.seed_catalog import (
    get_catalog,
    get_categories,
    get_coating_types,
    get_iso_groups,
    get_manufacturers,
    get_operations,
    get_substrate_codes,
    get_tool_materials,
)

router = APIRouter(prefix="/api/cutting-tools", tags=["cutting-tools"])

# In-memory registry built once at import time
_CATALOG: dict[str, CuttingToolCatalogRecord] = {}


def _build_registry() -> None:
    for record in get_catalog():
        _CATALOG[record.stable_id] = record


_build_registry()


@router.get("/schema")
def cutting_tools_schema() -> dict:
    """
    Return all filter options for the cutting tool catalog UI.
    No authentication required (public catalog metadata).
    """
    records = list(_CATALOG.values())
    return {
        "manufacturers": get_manufacturers(),
        "categories": get_categories(),
        "category_codes": get_categories(),
        "operations": get_operations(),
        "tool_materials": get_tool_materials(),
        "iso_material_groups": get_iso_groups(),
        "substrate_codes": get_substrate_codes(),
        "coating_types": get_coating_types(),
        "tool_count": len(records),
        "evidence_status": "MANUFACTURER_CATALOG",
    }


@router.get("/summary", response_model=CuttingToolCatalogSummary)
def cutting_tools_summary() -> CuttingToolCatalogSummary:
    """Return catalog summary statistics."""
    records = list(_CATALOG.values())
    from backend.cutting_tools.seed_catalog import _SOURCE_TITLE
    return CuttingToolCatalogSummary(
        tool_count=len(records),
        manufacturer_count=len(get_manufacturers()),
        category_count=len(get_categories()),
        tool_material_count=len(get_tool_materials()),
        manufacturers=get_manufacturers(),
        categories=get_categories(),
        tool_materials=get_tool_materials(),
        iso_material_groups=get_iso_groups(),
        source_title=_SOURCE_TITLE,
        evidence_status="MANUFACTURER_CATALOG",
    )


@router.get("/manufacturers")
def cutting_tools_manufacturers() -> dict:
    """Return list of manufacturers in catalog."""
    return {"manufacturers": get_manufacturers(), "count": len(get_manufacturers())}


@router.get("/categories")
def cutting_tools_categories() -> dict:
    """Return list of tool categories in catalog."""
    return {"categories": get_categories(), "count": len(get_categories())}


def _filter_catalog(
    manufacturer: str | None,
    category: str | None,
    operation: str | None,
    tool_material: str | None,
    iso_group: str | None,
    substrate_material_code: str | None = None,
    coating_type: str | None = None,
) -> list[CuttingToolCatalogRecord]:
    results = list(_CATALOG.values())
    if manufacturer:
        ml = manufacturer.lower()
        results = [r for r in results if r.manufacturer.lower() == ml]
    if category:
        cl = category.lower()
        results = [r for r in results if r.tool_category.lower() == cl
                   or r.tool_category_code.lower() == cl]
    if operation:
        ol = operation.lower()
        results = [r for r in results if ol in [op.lower() for op in r.supported_operations]]
    if tool_material:
        tl = tool_material.lower()
        results = [r for r in results if r.tool_material and r.tool_material.lower() == tl]
    if iso_group:
        ig = iso_group.upper()
        results = [r for r in results if ig in r.iso_material_groups]
    if substrate_material_code:
        sl = substrate_material_code.upper()
        results = [r for r in results if r.substrate_material_code and
                   r.substrate_material_code.upper() == sl]
    if coating_type:
        ctl = coating_type.upper()
        results = [r for r in results if r.coating_type and r.coating_type.upper() == ctl]
    return results


@router.get("/search", response_model=list[CuttingToolCatalogRecord])
def cutting_tools_search(
    q: str = Query(..., min_length=1, description="Keyword search in name, manufacturer, category"),
) -> list[CuttingToolCatalogRecord]:
    """
    Full-text keyword search across product name, manufacturer,
    catalog code, category, and subcategory.
    """
    ql = q.lower()
    return [
        r for r in _CATALOG.values()
        if ql in r.product_name.lower()
        or ql in r.manufacturer.lower()
        or ql in r.tool_category.lower()
        or (r.catalog_code and ql in r.catalog_code.lower())
        or (r.tool_subcategory and ql in r.tool_subcategory.lower())
    ]


@router.get("", response_model=list[CuttingToolCatalogRecord])
def cutting_tools_list(
    manufacturer: str | None = Query(None),
    category: str | None = Query(None),
    operation: str | None = Query(None),
    tool_material: str | None = Query(None),
    iso_group: str | None = Query(None),
    substrate_material_code: str | None = Query(None),
    coating_type: str | None = Query(None),
) -> list[CuttingToolCatalogRecord]:
    """
    Return filtered list of cutting tools.
    All filters are optional and case-insensitive.
    """
    return _filter_catalog(
        manufacturer, category, operation, tool_material, iso_group,
        substrate_material_code, coating_type,
    )


@router.get("/{tool_id}", response_model=CuttingToolCatalogRecord)
def cutting_tool_detail(tool_id: str) -> CuttingToolCatalogRecord:
    """Return a single cutting tool record by stable ID."""
    record = _CATALOG.get(tool_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id!r}")
    return record
