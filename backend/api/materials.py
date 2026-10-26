"""FastAPI router for the Material Catalog (EPIC_01_MATERIAL_INTELLIGENCE_FOUNDATION).

GET /api/materials/iso-groups         — ISO group metadata list
GET /api/materials/summary            — aggregate counts
GET /api/materials/search?q=term      — cross-field search
GET /api/materials                    — list with optional filters
GET /api/materials/{material_id}      — full detail
GET /api/materials/{material_id}/machinability      — machinability + tool compat
GET /api/materials/{material_id}/cutting-context    — cutting parameter references

Constraints:
  FABRICATED_MATERIAL_PROPERTY=NO
  FABRICATED_CUTTING_PARAMETER=NO
  PRIVATE_SOURCE_PATH_EXPOSED=NO
  FALSE_AI_CLAIM=NO
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from backend.materials.catalog import get_catalog
from backend.materials.models import (
    MaterialDetail,
    MaterialListItem,
    MaterialMachinabilityRecord,
    MaterialRecord,
    MaterialSummary,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/materials", tags=["materials"])


def _catalog():
    return get_catalog()


# ---------------------------------------------------------------------------
# Metadata endpoints (no path params — must be before /{material_id})
# ---------------------------------------------------------------------------

@router.get("/iso-groups")
def materials_iso_groups() -> list[dict]:
    """Return ISO 513 group metadata with labels, descriptions, and color hints."""
    return _catalog().iso_groups()


@router.get("/summary", response_model=MaterialSummary)
def materials_summary() -> MaterialSummary:
    """Return aggregate material catalog statistics."""
    return _catalog().summary()


@router.get("/search", response_model=list[MaterialListItem])
def materials_search(
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(50, ge=1, le=200),
) -> list[MaterialListItem]:
    """Full-text search across designation, standards, aliases, and Werkstoff-Nr."""
    return _catalog().search(query=q, limit=limit)


# ---------------------------------------------------------------------------
# List endpoint
# ---------------------------------------------------------------------------

@router.get("", response_model=list[MaterialListItem])
def materials_list(
    iso_group: str | None = Query(None, description="Filter by ISO group (P/M/K/N/S/H)"),
    family: str | None = Query(None, description="Filter by material family"),
    search: str | None = Query(None, description="Search term"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[MaterialListItem]:
    """List materials with optional ISO group, family, and full-text search filters."""
    return _catalog().search(
        query=search,
        iso_group=iso_group,
        family=family,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Detail endpoints
# ---------------------------------------------------------------------------

@router.get("/{material_id}", response_model=MaterialDetail)
def material_detail(material_id: str) -> MaterialDetail:
    """Return full detail for one material including conditions, machinability, and tool compat."""
    record = _catalog().get(material_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Material '{material_id}' not found")

    _ISO_GROUP_LABELS = {
        "P": "P — Steels", "M": "M — Stainless Steels", "K": "K — Cast Irons",
        "N": "N — Non-Ferrous", "S": "S — Superalloys & Titanium", "H": "H — Hardened Materials",
    }
    _ISO_SUBGROUP_LABELS = {
        "P_STEEL": "Steel", "M_STAINLESS": "Stainless Steel", "K_CAST_IRON": "Cast Iron",
        "N_ALUMINUM": "Aluminum Alloy", "N_COPPER": "Copper Alloy",
        "S_TITANIUM": "Titanium Alloy", "S_NICKEL_HRSA": "Nickel HRSA",
        "H_HARDENED": "Hardened Steel", "UNSPECIFIED": "Unspecified",
    }
    _FAMILY_LABELS = {
        "steel": "Steel", "stainless_steel": "Stainless Steel", "cast_iron": "Cast Iron",
        "aluminum": "Aluminum", "copper_alloy": "Copper Alloy", "titanium": "Titanium",
        "nickel_alloy": "Nickel Alloy", "graphite": "Graphite",
        "ceramic_material": "Engineering Ceramic", "plastic": "Plastic",
        "composite": "Composite", "other": "Other",
    }

    return MaterialDetail(
        record=record,
        iso_group_label=_ISO_GROUP_LABELS.get(record.iso_group, record.iso_group),
        iso_subgroup_label=_ISO_SUBGROUP_LABELS.get(record.iso_subgroup, record.iso_subgroup),
        family_label=_FAMILY_LABELS.get(record.material_family, record.material_family),
    )


@router.get("/{material_id}/machinability")
def material_machinability(material_id: str) -> dict:
    """Return machinability metadata and tool-material compatibility for one material."""
    record = _catalog().get(material_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Material '{material_id}' not found")
    return {
        "material_id": material_id,
        "designation": record.designation,
        "iso_group": record.iso_group,
        "machinability": record.machinability.model_dump() if record.machinability else None,
        "tool_compatibility": [tc.model_dump() for tc in record.tool_compatibility],
        "evidence_note": (
            "Machinability data and tool compatibility ratings are REFERENCE_ONLY — "
            "from general industry synthesis. Validate with OEM cutting data before production use."
        ),
    }


@router.get("/{material_id}/cutting-context")
def material_cutting_context(
    material_id: str,
    operation: str | None = Query(None, description="Filter by operation (turning/milling/drilling)"),
    tool_material: str | None = Query(None, description="Filter by tool material"),
) -> dict:
    """Return cutting parameter reference envelopes for a material.

    These are REFERENCE_ONLY general industry envelopes.
    Never use without OEM validation.
    """
    record = _catalog().get(material_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Material '{material_id}' not found")

    refs = record.cutting_references
    if operation:
        refs = [r for r in refs if r.operation.lower() == operation.lower()]
    if tool_material:
        refs = [r for r in refs if r.tool_material.lower() == tool_material.lower()]

    return {
        "material_id": material_id,
        "designation": record.designation,
        "iso_group": record.iso_group,
        "iso_subgroup": record.iso_subgroup,
        "cutting_references": [r.model_dump() for r in refs],
        "evidence_note": (
            "REFERENCE_ONLY — general industry cutting parameter envelopes. "
            "NOT OEM catalog values. Validate with manufacturer data before production use."
        ),
    }
