"""
FastAPI router for the Machine Catalog (MACHINE_CATALOG_DATA_INTEGRATION_01 / EPIC_02).

GET /api/machines/schema          — available manufacturers, types, processes
GET /api/machines/summary         — aggregate counts
GET /api/machines/manufacturers   — manufacturer list
GET /api/machines                 — list with filters
GET /api/machines/search          — keyword + capability search
GET /api/machines/{machine_id}    — single machine detail
GET /api/machines/{machine_id}/capabilities  — process capability summary
GET /api/machines/{machine_id}/spindle       — spindle specification detail
GET /api/machines/{machine_id}/compatibility — spindle interface compatibility

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
    spindle_interface: str | None = None,
    min_spindle_rpm: int | None = None,
    min_power_kw: float | None = None,
    has_5axis: bool | None = None,
    controller_family: str | None = None,
) -> list[MachineCatalogRecord]:
    results = list(_CATALOG.values())
    if manufacturer:
        mf_lower = manufacturer.lower()
        results = [r for r in results if r.manufacturer.lower() == mf_lower]
    if machine_type:
        mt_lower = machine_type.lower()
        results = [
            r for r in results
            if r.machine_type.lower() == mt_lower or r.machine_type_code.lower() == mt_lower
        ]
    if process:
        proc_lower = process.lower()
        results = [r for r in results if proc_lower in [p.lower() for p in r.supported_processes]]
    if axis_count is not None:
        results = [r for r in results if r.axis_count == axis_count]
    if spindle_interface:
        si_lower = spindle_interface.lower()
        results = [
            r for r in results
            if (r.spindle_interface or "").lower() == si_lower
            or any(s.lower() == si_lower for s in r.spindle_interfaces_supported)
        ]
    if min_spindle_rpm is not None:
        # Fail-closed: None spindle_max_rpm is NOT treated as unlimited — excluded
        results = [
            r for r in results
            if r.spindle_max_rpm is not None and r.spindle_max_rpm >= min_spindle_rpm
        ]
    if min_power_kw is not None:
        # Fail-closed: None spindle_power_kw is NOT treated as unlimited — excluded
        results = [
            r for r in results
            if r.spindle_power_kw is not None and r.spindle_power_kw >= min_power_kw
        ]
    if has_5axis is True:
        results = [
            r for r in results
            if r.capable_5axis_simultaneous is True
            or r.simultaneous_axis_count == 5
        ]
    if controller_family:
        cf_lower = controller_family.lower()
        results = [
            r for r in results
            if r.controller_family and cf_lower in r.controller_family.lower()
        ]
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
    spindle_interface: str | None = Query(None),
    min_spindle_rpm: int | None = Query(None),
    min_power_kw: float | None = Query(None),
    has_5axis: bool | None = Query(None),
    controller_family: str | None = Query(None),
) -> list[MachineCatalogRecord]:
    """
    List machines with optional filters.

    Filters are case-insensitive. spindle_interface and controller_family use
    substring/exact matching. min_spindle_rpm and min_power_kw use fail-closed
    filtering: machines with unknown (None) limits are excluded.
    No ranking, no AI recommendation.
    """
    return _filter_catalog(
        manufacturer, machine_type, process, axis_count,
        spindle_interface=spindle_interface,
        min_spindle_rpm=min_spindle_rpm,
        min_power_kw=min_power_kw,
        has_5axis=has_5axis,
        controller_family=controller_family,
    )


@router.get("/search", response_model=list[MachineCatalogRecord])
def machines_search(
    q: str = Query(
        ..., description="Keyword to search in model, manufacturer, machine_type, controller_family"
    ),
    manufacturer: str | None = Query(None),
    machine_type: str | None = Query(None),
    spindle_interface: str | None = Query(None),
    min_spindle_rpm: int | None = Query(None),
    min_power_kw: float | None = Query(None),
    has_5axis: bool | None = Query(None),
) -> list[MachineCatalogRecord]:
    """
    Keyword + capability search across the machine catalog.

    Matches *q* (case-insensitive) against model name, manufacturer,
    machine_type, machine_type_code, family, and controller_family.
    Additional filters narrow further. No ranking by relevance — results
    are sorted alphabetically by manufacturer then model.
    """
    q_lower = q.strip().lower()
    candidates = _filter_catalog(
        manufacturer=manufacturer,
        machine_type=machine_type,
        process=None,
        axis_count=None,
        spindle_interface=spindle_interface,
        min_spindle_rpm=min_spindle_rpm,
        min_power_kw=min_power_kw,
        has_5axis=has_5axis,
    )
    return [
        r for r in candidates
        if q_lower in r.model.lower()
        or q_lower in r.manufacturer.lower()
        or q_lower in r.machine_type.lower()
        or q_lower in r.machine_type_code.lower()
        or (r.family and q_lower in r.family.lower())
        or (r.controller_family and q_lower in r.controller_family.lower())
    ]


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


@router.get("/{machine_id}/capabilities")
def machine_capabilities(machine_id: str) -> dict:
    """
    Return process capability summary for one machine.

    Reports which capabilities are confirmed True, which are False/None.
    No fabricated values — unknown capabilities are reported as null.
    """
    record = _CATALOG.get(machine_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Machine '{machine_id}' not found")
    return {
        "stable_id": record.stable_id,
        "manufacturer": record.manufacturer,
        "model": record.model,
        "machine_type_code": record.machine_type_code,
        "supported_processes": record.supported_processes,
        "axis_count": record.axis_count,
        "simultaneous_axis_count": record.simultaneous_axis_count,
        "turning_capable": record.turning_capable,
        "milling_capable": record.milling_capable,
        "drilling_capable": record.drilling_capable,
        "capable_tapping": record.capable_tapping,
        "capable_boring": record.capable_boring,
        "capable_threading": record.capable_threading,
        "capable_reaming": record.capable_reaming,
        "capable_5axis_simultaneous": record.capable_5axis_simultaneous,
        "capable_3plus2": record.capable_3plus2,
        "has_subspindle": record.has_subspindle,
        "has_y_axis": record.has_y_axis,
        "has_live_tooling": record.has_live_tooling,
        "has_b_axis": record.has_b_axis,
        "has_pallet_changer": record.has_pallet_changer,
        "through_spindle_coolant": record.through_spindle_coolant,
        "flood_coolant": record.flood_coolant,
        "mql_support": record.mql_support,
    }


@router.get("/{machine_id}/spindle")
def machine_spindle(machine_id: str) -> dict:
    """
    Return spindle specification for one machine.

    All fields are present with None for unknown values.
    No fabricated values.
    """
    record = _CATALOG.get(machine_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Machine '{machine_id}' not found")
    return {
        "stable_id": record.stable_id,
        "manufacturer": record.manufacturer,
        "model": record.model,
        "spindle_max_rpm": record.spindle_max_rpm,
        "spindle_min_rpm": record.spindle_min_rpm,
        "spindle_power_kw": record.spindle_power_kw,
        "spindle_power_continuous_kw": record.spindle_power_continuous_kw,
        "spindle_power_peak_kw": record.spindle_power_peak_kw,
        "spindle_torque_nm": record.spindle_torque_nm,
        "spindle_torque_continuous_nm": record.spindle_torque_continuous_nm,
        "spindle_torque_peak_nm": record.spindle_torque_peak_nm,
        "spindle_torque_at_rpm": record.spindle_torque_at_rpm,
        "spindle_interface": record.spindle_interface,
        "spindle_interfaces_supported": record.spindle_interfaces_supported,
        "max_cutting_feed_mm_min": record.max_cutting_feed_mm_min,
        "coolant_pressure_bar": record.coolant_pressure_bar,
        "through_spindle_coolant": record.through_spindle_coolant,
        "evidence_status": record.evidence_status,
    }


@router.get("/{machine_id}/compatibility")
def machine_compatibility(
    machine_id: str,
    spindle_interface: str | None = Query(None),
) -> dict:
    """
    Return spindle interface compatibility information for one machine.

    When *spindle_interface* is provided, reports whether it is compatible
    with this machine.  No fabricated values.
    Compatible = exact match on primary spindle_interface or
    found in spindle_interfaces_supported list.
    """
    record = _CATALOG.get(machine_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Machine '{machine_id}' not found")

    result: dict = {
        "stable_id": record.stable_id,
        "manufacturer": record.manufacturer,
        "model": record.model,
        "spindle_interface": record.spindle_interface,
        "spindle_interfaces_supported": record.spindle_interfaces_supported,
    }

    if spindle_interface:
        si_lower = spindle_interface.lower()
        primary_match = (record.spindle_interface or "").lower() == si_lower
        supported_match = any(
            s.lower() == si_lower for s in record.spindle_interfaces_supported
        )
        if primary_match or supported_match:
            result["compatibility"] = "COMPATIBLE"
            result["match_source"] = "primary" if primary_match else "supported_list"
        elif record.spindle_interface is None and not record.spindle_interfaces_supported:
            result["compatibility"] = "INSUFFICIENT_DATA"
            result["match_source"] = None
        else:
            result["compatibility"] = "INCOMPATIBLE"
            result["match_source"] = None
        result["queried_interface"] = spindle_interface

    return result
