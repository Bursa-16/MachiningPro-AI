"""
FastAPI router for the Cutting Parameters engineering workflow.

GET /api/cutting-parameters/query
    Returns all matching reference records for an operation + ISO material group,
    grouped by parameter type.  No fabricated recommendations.

GET /api/cutting-parameters/schema
    Returns supported operations, ISO material groups, and tool materials
    as enum lists for use by the frontend selectors.

POST /api/cutting-parameters/calculate
    Deterministic RPM and feed-rate calculations from Vc + diameter +
    feed inputs.  Uses backend.machining.formulas — no formula duplication.
"""

from __future__ import annotations

import logging
import os
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.cutting_parameters.models import (
    ApplicabilityScope,
    EvidenceStatus,
)
from backend.cutting_parameters.registry import CuttingParameterRegistry
from backend.cutting_parameters.seed_reference import seed_reference_registry
from backend.domain.enums import IsoMaterialGroup, OperationType, ToolMaterial
from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError
from backend.machining.formulas import (
    feed_rate_from_rpm_feed_per_rev,
    feed_rate_from_rpm_tooth_feed,
    spindle_speed_from_cutting_speed,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cutting-parameters", tags=["cutting-parameters"])

# ---------------------------------------------------------------------------
# Registry singleton — lazy init, re-initialised when env var changes
# ---------------------------------------------------------------------------

_registry: CuttingParameterRegistry | None = None
_seeded_path: str | None = None


def _get_registry() -> CuttingParameterRegistry:
    global _registry, _seeded_path
    current_path = os.environ.get("MACHININGPRO_CUTTING_PARAM_REF_PATH")
    if _registry is None or (current_path is not None and current_path != _seeded_path):
        reg = CuttingParameterRegistry()
        if current_path and Path(current_path).is_file():
            try:
                n = seed_reference_registry(reg, current_path)
                logger.info("Cutting parameter registry seeded: %d records", n)
            except Exception as exc:
                logger.warning("Could not seed cutting parameter registry: %s", exc)
        _registry = reg
        _seeded_path = current_path
    return _registry


def _reset_registry() -> None:
    """Force re-initialisation on next request.  For tests only."""
    global _registry, _seeded_path
    _registry = None
    _seeded_path = None


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ParameterRangeOut(BaseModel):
    parameter_type: str
    unit: str
    min_value: float
    max_value: float
    notes: str | None


class ProvenanceOut(BaseModel):
    source_reference: str | None
    page_section: str | None
    source_type: str


class MatchedScopeOut(BaseModel):
    operation: str | None
    iso_material_group: str | None
    tool_material: str | None


class QueryResponse(BaseModel):
    matched: bool
    match_level: str          # "ISO_GROUP_MATCH" | "NO_MATCH"
    match_reason: str
    evidence_status: str
    authority_label: str
    limitation_note: str
    parameters: list[ParameterRangeOut]
    provenance: ProvenanceOut | None
    scope: MatchedScopeOut


class SchemaResponse(BaseModel):
    operations: list[str]
    iso_material_groups: list[str]
    iso_material_labels: dict[str, str]
    tool_materials: list[str]


class CalculateRequest(BaseModel):
    vc_m_min: float
    diameter_mm: float
    operation: str
    feed_per_tooth_mm: float | None = None
    tooth_count: int | None = None
    feed_per_rev_mm: float | None = None


class CalculateResponse(BaseModel):
    rpm: float
    rpm_formula: str
    feed_rate_mm_min: float | None
    feed_rate_formula: str | None
    machine_limit_note: str


# ---------------------------------------------------------------------------
# ISO material group human labels (no private paths)
# ---------------------------------------------------------------------------

_ISO_LABELS: dict[str, str] = {
    "P": "ISO P — Steel",
    "M": "ISO M — Stainless Steel",
    "K": "ISO K — Cast Iron",
    "N": "ISO N — Non-Ferrous",
    "S": "ISO S — Ti / HRSA",
    "H": "ISO H — Hardened Steel",
}

_SUPPORTED_OPERATIONS: list[str] = ["turning", "milling", "drilling", "reaming"]
_SUPPORTED_TOOL_MATERIALS: list[str] = [v for v in ToolMaterial]
_SUPPORTED_ISO_GROUPS: list[str] = [v for v in IsoMaterialGroup]


# ---------------------------------------------------------------------------
# Query endpoint
# ---------------------------------------------------------------------------

@router.get("/query", response_model=QueryResponse)
def query_cutting_parameters(
    operation: str = Query(..., description="Operation type, e.g. 'turning'"),
    iso_material_group: str = Query(..., description="ISO 513 material group, e.g. 'P'"),
    tool_material: str | None = Query(None, description="Tool material, e.g. 'carbide'"),
) -> QueryResponse:
    """
    Return all matching reference cutting-parameter records.

    Records are REFERENCE_ONLY — not authoritative manufacturing specifications.
    Missing values are absent from the response (not set to zero).
    Source provenance is included; private file-system paths are NOT exposed.
    """
    # Validate operation
    try:
        op = OperationType(operation.lower())
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown operation {operation!r}. "
                   f"Supported: {_SUPPORTED_OPERATIONS}",
        ) from exc

    if op not in (
        OperationType.TURNING,
        OperationType.MILLING,
        OperationType.DRILLING,
        OperationType.REAMING,
    ):
        raise HTTPException(
            status_code=422,
            detail=f"Operation {operation!r} has no reference data. "
                   f"Supported: {_SUPPORTED_OPERATIONS}",
        )

    # Validate ISO material group
    try:
        iso = IsoMaterialGroup(iso_material_group.upper())
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown ISO material group {iso_material_group!r}. "
                   f"Supported: {_SUPPORTED_ISO_GROUPS}",
        ) from exc

    # Validate optional tool material
    tm: ToolMaterial | None = None
    if tool_material:
        try:
            tm = ToolMaterial(tool_material)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown tool material {tool_material!r}. "
                       f"Supported: {_SUPPORTED_TOOL_MATERIALS}",
            ) from exc

    registry = _get_registry()

    scope = ApplicabilityScope(
        operation_type=op,
        iso_material_group=iso,
        tool_material=tm,
    )

    records = registry.find(scope=scope)

    if not records:
        return QueryResponse(
            matched=False,
            match_level="NO_MATCH",
            match_reason=(
                f"No reference data found for {op.value} / ISO {iso.value}"
                + (f" / {tm.value}" if tm else "")
                + ". Try broader scope or different operation."
            ),
            evidence_status=EvidenceStatus.REFERENCE_ONLY,
            authority_label="Reference Guidance",
            limitation_note=(
                "No matching reference data is available for this combination. "
                "The reference library covers ISO groups P, M, K, N, S, H "
                "for Turning, Milling, Drilling, and Reaming operations."
            ),
            parameters=[],
            provenance=None,
            scope=MatchedScopeOut(
                operation=op.value,
                iso_material_group=iso.value,
                tool_material=tm.value if tm else None,
            ),
        )

    # Aggregate parameter ranges per parameter type (first record's provenance)
    param_map: dict[str, list[ParameterRangeOut]] = {}
    first_record = records[0]

    for rec in records:
        pt = rec.parameter_type.value
        if pt not in param_map:
            param_map[pt] = []
        param_map[pt].append(
            ParameterRangeOut(
                parameter_type=pt,
                unit=rec.value_range.unit.value,
                min_value=float(rec.value_range.min_value.value),
                max_value=float(rec.value_range.max_value.value),
                notes=rec.notes,
            )
        )

    # Flatten — for each parameter type, return the first record
    parameters = [entries[0] for entries in param_map.values()]

    # Build match reason
    matched_dims: list[str] = [f"operation={op.value}", f"ISO {iso.value}"]
    if tm:
        matched_dims.append(f"tool_material={tm.value}")
    match_reason = "Matched on: " + ", ".join(matched_dims)

    # Provenance: use first record; strip file-system paths (Hard Rule 11)
    prov = first_record.provenance
    prov_out = ProvenanceOut(
        source_reference=prov.source_reference,
        page_section=prov.page_section,
        # source_document is intentionally omitted — may contain private file paths
        source_type=prov.source_type.value,
    )

    return QueryResponse(
        matched=True,
        match_level="ISO_GROUP_MATCH",
        match_reason=match_reason,
        evidence_status=EvidenceStatus.REFERENCE_ONLY,
        authority_label="Reference Guidance",
        limitation_note=(
            "Values represent general industry starting envelopes from a secondary "
            "literature source. Not manufacturer-specific. Validate with production "
            "trials before use as authoritative inputs."
        ),
        parameters=parameters,
        provenance=prov_out,
        scope=MatchedScopeOut(
            operation=op.value,
            iso_material_group=iso.value,
            tool_material=tm.value if tm else None,
        ),
    )


# ---------------------------------------------------------------------------
# Schema endpoint — static enum lists for frontend selectors
# ---------------------------------------------------------------------------

@router.get("/schema", response_model=SchemaResponse)
def cutting_parameter_schema() -> SchemaResponse:
    """Return supported operations, ISO material groups and tool materials."""
    return SchemaResponse(
        operations=_SUPPORTED_OPERATIONS,
        iso_material_groups=_SUPPORTED_ISO_GROUPS,
        iso_material_labels=_ISO_LABELS,
        tool_materials=_SUPPORTED_TOOL_MATERIALS,
    )


# ---------------------------------------------------------------------------
# Calculate endpoint
# ---------------------------------------------------------------------------

@router.post("/calculate", response_model=CalculateResponse)
def calculate_parameters(req: CalculateRequest) -> CalculateResponse:
    """
    Deterministic machining calculations.

    RPM: n = 1000 × Vc / (π × D)
    Milling feed rate: Vf = n × z × fz
    Turning/drilling feed rate: fr = n × f
    """
    vc = Decimal(str(req.vc_m_min))
    d = Decimal(str(req.diameter_mm))

    if vc <= 0:
        raise HTTPException(status_code=422, detail="vc_m_min must be positive")
    if d <= 0:
        raise HTTPException(status_code=422, detail="diameter_mm must be positive")

    try:
        n_qty = spindle_speed_from_cutting_speed(
            cutting_speed=Quantity(value=vc, unit=Unit.M_MIN),
            diameter=Quantity(value=d, unit=Unit.MM),
        )
        rpm = float(n_qty.value)
    except MachiningMathError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    rpm_formula = "n = 1000 × Vc / (π × D)"

    # Feed rate — depends on operation
    op_lower = req.operation.lower()
    feed_rate: float | None = None
    feed_formula: str | None = None

    if op_lower == "milling" and req.feed_per_tooth_mm is not None and req.tooth_count is not None:
        fz = Decimal(str(req.feed_per_tooth_mm))
        z = req.tooth_count
        if fz <= 0:
            raise HTTPException(status_code=422, detail="feed_per_tooth_mm must be positive")
        if z <= 0:
            raise HTTPException(status_code=422, detail="tooth_count must be positive")
        try:
            fr_qty = feed_rate_from_rpm_tooth_feed(
                spindle_speed=n_qty,
                tooth_count=z,
                feed_per_tooth=Quantity(value=fz, unit=Unit.MM_TOOTH),
            )
            feed_rate = float(fr_qty.value)
            feed_formula = "Vf = n × z × fz"
        except MachiningMathError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    elif op_lower in ("turning", "drilling", "reaming") and req.feed_per_rev_mm is not None:
        fn = Decimal(str(req.feed_per_rev_mm))
        if fn <= 0:
            raise HTTPException(status_code=422, detail="feed_per_rev_mm must be positive")
        try:
            fr_qty = feed_rate_from_rpm_feed_per_rev(
                spindle_speed=n_qty,
                feed_per_rev=Quantity(value=fn, unit=Unit.MM_REV),
            )
            feed_rate = float(fr_qty.value)
            feed_formula = "fr = n × f"
        except MachiningMathError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return CalculateResponse(
        rpm=round(rpm, 1),
        rpm_formula=rpm_formula,
        feed_rate_mm_min=round(feed_rate, 2) if feed_rate is not None else None,
        feed_rate_formula=feed_formula,
        machine_limit_note=(
            "Verify RPM and feed rate against machine spindle and axis limits "
            "before use."
        ),
    )
