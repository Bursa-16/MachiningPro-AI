"""
FastAPI router for the Machine Catalog (MACHINE_CATALOG_DATA_INTEGRATION_01).

GET /api/machines/schema          — available manufacturers, types, processes
GET /api/machines/summary         — aggregate counts
GET /api/machines/manufacturers   — manufacturer list
GET /api/machines                 — list with filters
GET /api/machines/{machine_id}    — single machine detail

Constraints:
  AUTH_PATTERN_PRESERVED=YES   — requires same JWT token as other routes
  PRIVATE_SOURCE_PATH_EXPOSED=NO
  FALSE_MACHINE_RECOMMENDATION_CLAIM=NO
  FALSE_AI_CLAIM=NO
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from backend.machines.catalog_models import MachineCatalogRecord, MachineCatalogSummary
from backend.machines.seed_catalog import seed_machine_catalog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/machines", tags=["machines"])

# ---------------------------------------------------------------------------
# In-memory registry — seeded at import time (no external file required)
# ---------------------------------------------------------------------------

_CATALOG: dict[str, MachineCatalogRecord] = {}
_MANUFACTURERS: list[str] = []
_MACHINE_TYPES: list[str] = []
_ALL_PROCESSES: list[str] = []


def _build_registry() -> None:
    global _CATALOG, _MANUFACTURERS, _MACHINE_TYPES, _ALL_PROCESSES
    records = seed_machine_catalog()
    seen_ids: set[str] = set()
    for raw in records:
        sid = raw["stable_id"]
        if sid in seen_ids:
            logger.warning("Duplicate machine id during seeding: %r — skipped", sid)
            continue
        seen_ids.add(sid)
        _CATALOG[sid] = MachineCatalogRecord(**raw)

    _MANUFACTURERS = sorted({r.manufacturer for r in _CATALOG.values()})
    _MACHINE_TYPES = sorted({r.machine_type for r in _CATALOG.values()})
    proc_set: set[str] = set()
    for r in _CATALOG.values():
        proc_set.update(r.supported_processes)
    _ALL_PROCESSES = sorted(proc_set)
    logger.info(
        "Machine catalog seeded: %d records, %d manufacturers, %d types",
        len(_CATALOG),
        len(_MANUFACTURERS),
        len(_MACHINE_TYPES),
    )


_build_registry()


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _filter_catalog(
    manufacturer: str | None,
    machine_type: str | None,
    process: str | None,
    axis_count: int | None,
) -> list[MachineCatalogRecord]:
    results = list(_CATALOG.values())
    if manufacturer:
        mf_lower = manufacturer.lower()
        results = [r for r in results if r.manufacturer.lower() == mf_lower]
    if machine_type:
        mt_lower = machine_type.lower()
        results = [r for r in results if r.machine_type.lower() == mt_lower]
    if process:
        proc_lower = process.lower()
        results = [r for r in results if proc_lower in [p.lower() for p in r.supported_processes]]
    if axis_count is not None:
        results = [r for r in results if r.axis_count == axis_count]
    return sorted(results, key=lambda r: (r.manufacturer, r.model))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/schema")
def machines_schema() -> dict:
    """Return available filter values: manufacturers, machine types, processes."""
    return {
        "manufacturers": _MANUFACTURERS,
        "machine_types": _MACHINE_TYPES,
        "processes": _ALL_PROCESSES,
        "axis_count_options": sorted({r.axis_count for r in _CATALOG.values()}),
        "machine_count": len(_CATALOG),
        "evidence_status": "MANUFACTURER_DATASHEET",
    }


@router.get("/summary", response_model=MachineCatalogSummary)
def machines_summary() -> MachineCatalogSummary:
    """Return aggregate machine catalog statistics."""
    sample = next(iter(_CATALOG.values()), None)
    return MachineCatalogSummary(
        machine_count=len(_CATALOG),
        manufacturer_count=len(_MANUFACTURERS),
        machine_type_count=len(_MACHINE_TYPES),
        manufacturers=_MANUFACTURERS,
        machine_types=_MACHINE_TYPES,
        source_title=sample.source_title if sample else "",
        evidence_status=sample.evidence_status if sample else "MANUFACTURER_DATASHEET",
    )


@router.get("/manufacturers")
def machines_manufacturers() -> dict:
    """Return list of available manufacturers."""
    return {"manufacturers": _MANUFACTURERS, "count": len(_MANUFACTURERS)}


@router.get("", response_model=list[MachineCatalogRecord])
def machines_list(
    manufacturer: str | None = Query(None),
    machine_type: str | None = Query(None),
    process: str | None = Query(None),
    axis_count: int | None = Query(None),
) -> list[MachineCatalogRecord]:
    """
    List machines with optional filters.

    Filters are case-insensitive exact-match.
    No ranking, no AI recommendation.
    """
    return _filter_catalog(manufacturer, machine_type, process, axis_count)


@router.get("/{machine_id}", response_model=MachineCatalogRecord)
def machine_detail(machine_id: str) -> MachineCatalogRecord:
    """
    Return full detail for one machine.

    Raises 404 when *machine_id* is not in the catalog.
    """
    record = _CATALOG.get(machine_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Machine '{machine_id}' not found")
    return record
