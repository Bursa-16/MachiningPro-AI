"""
FastAPI router for the Tool Life empirical explorer (TOOL_LIFE_UI_INTEGRATION_01).

Serves the Piecuch-Zabiński ToolLife 968 empirical dataset:
  GET /api/tool-life/summary          — dataset-level summary + limitations
  GET /api/tool-life/tools            — tool list with basic lifecycle stats
  GET /api/tool-life/tools/{tool_id}  — lifecycle + sensor series for one tool

Evidence level: EXPERIMENTAL.
Production deployment readiness: NOT VALIDATED.
Taylor fit: NOT POSSIBLE (no Vc column in source dataset).
VB (flank wear): NOT IN SOURCE DATASET.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.empirical.exceptions import EmpiricalDataError
from backend.empirical.seed_toollife968 import seed_toollife968_registry
from backend.empirical.toollife968_models import (
    TOOLLIFE968_SENSOR_FEATURE_COUNT,
    TOOLLIFE968_TOTAL_COL_COUNT,
)
from backend.empirical.toollife968_registry import (
    ToolLife968Registry,
    get_toollife968_registry,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tool-life", tags=["tool-life"])

_ENV_VAR = "MACHININGPRO_TOOLLIFE968_SOURCE_PATH"

# ---------------------------------------------------------------------------
# Lazy seeding — called once on first request
# ---------------------------------------------------------------------------

_seeded: bool = False
_seed_attempted: bool = False


def _get_registry() -> ToolLife968Registry | None:
    """Return the registry singleton, seeding if needed. Returns None if unavailable."""
    global _seeded, _seed_attempted
    if not _seed_attempted:
        _seed_attempted = True
        reg = get_toollife968_registry()
        if not reg.is_seeded():
            path_str = os.environ.get(_ENV_VAR)
            if path_str and Path(path_str).is_file():
                try:
                    n, _ = seed_toollife968_registry(Path(path_str), reg)
                    logger.info("ToolLife968 registry seeded: %d records", n)
                    _seeded = True
                except (EmpiricalDataError, FileNotFoundError) as exc:
                    logger.warning("ToolLife968 seed failed: %s", exc)
            else:
                logger.info("ToolLife968 source path not configured (%s not set)", _ENV_VAR)
        else:
            _seeded = True
    return get_toollife968_registry()


def _reset_registry_state() -> None:
    """Reset seeding state. For tests only."""
    global _seeded, _seed_attempted
    _seeded = False
    _seed_attempted = False


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ToolLifeSummaryOut(BaseModel):
    seeded: bool
    observation_count: int
    tool_count: int
    feature_count: int
    sensor_feature_count: int
    eol_observation_count: int
    evidence_status: str
    source_dataset: str
    source_doi: str | None
    source_sheet: str | None
    cycle_to_failure_semantics: str
    sensor_feature_headers: list[str]
    limitations: list[str]


class ToolSummaryOut(BaseModel):
    tool_id: int
    tool_type: str
    observation_count: int
    total_cycles: int
    adoc_mm: float
    rdoc_mm: float
    eol_present: bool
    min_cycle_to_failure: int
    max_cycle_to_failure: int


class LifecyclePointOut(BaseModel):
    obs_idx: int
    cycle_number: int
    sample_index: int
    cycle_to_failure: int
    cycle_to_failure_normalized: float
    is_eol: bool


class SensorSeriesOut(BaseModel):
    feature_index: int
    feature_name: str
    values: list[float]


class ToolDetailOut(BaseModel):
    tool_id: int
    tool_type: str
    observation_count: int
    total_cycles: int
    adoc_mm: float
    rdoc_mm: float
    tool_holder_length_mm: float
    hardness_mean: float
    eol_present: bool
    lifecycle: list[LifecyclePointOut]
    sensor_series: SensorSeriesOut
    source_doi: str | None
    evidence_status: str


# ---------------------------------------------------------------------------
# Static limitations text
# ---------------------------------------------------------------------------

_LIMITATIONS: list[str] = [
    "VB (flank wear, mm) is NOT present in this dataset — flank wear thresholds cannot be derived.",
    "No cutting speed Vc column — Taylor C/n coefficients CANNOT be fitted from this data.",
    "CycleToFailure is a per-tool countdown (0 = EOL). It is NOT cumulative age.",
    "Leakage risk: cycle_number is strongly inversely correlated with CycleToFailure "
    "within each tool. Using cycle_number as a standalone sensor-based predictor "
    "replicates the target variable; not valid for independent production deployment.",
    "Sensor-only leave-one-tool-out prediction performance was weak in prior audit — "
    "independent deployment prediction requires additional validation and data.",
    "HardnessMean units are unstated in the source (values ~35–41, consistent with HRC). "
    "Do NOT assume HB.",
    "Production deployment readiness: NOT VALIDATED. This dataset supports research and "
    "empirical exploration only.",
]


# ---------------------------------------------------------------------------
# Summary endpoint
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=ToolLifeSummaryOut)
def tool_life_summary() -> ToolLifeSummaryOut:
    """
    Return dataset-level summary.

    Returns seeded=false with zero counts if the ToolLife 968 data is not
    configured in this deployment (MACHININGPRO_TOOLLIFE968_SOURCE_PATH not set).
    """
    reg = _get_registry()

    if reg is None or not reg.is_seeded():
        return ToolLifeSummaryOut(
            seeded=False,
            observation_count=0,
            tool_count=0,
            feature_count=0,
            sensor_feature_count=0,
            eol_observation_count=0,
            evidence_status="EXPERIMENTAL",
            source_dataset="TOOLLIFE-968",
            source_doi="10.6084/m9.figshare.28589216",
            source_sheet="Golden ToolLife 968",
            cycle_to_failure_semantics="countdown_to_eol",
            sensor_feature_headers=[],
            limitations=_LIMITATIONS,
        )

    all_obs = reg.get_all()
    tool_indices = {o.tool_index for o in all_obs}
    eol_count = len(reg.get_eol_observations())

    # Sensor feature headers from first record's source meta
    headers: list[str] = []
    if all_obs:
        headers = list(all_obs[0].source.sensor_feature_headers)
    source_doi = all_obs[0].source.doi if all_obs else None
    source_sheet = all_obs[0].source.source_sheet if all_obs else None
    source_dataset = all_obs[0].source.source_dataset if all_obs else "TOOLLIFE-968"

    return ToolLifeSummaryOut(
        seeded=True,
        observation_count=len(all_obs),
        tool_count=len(tool_indices),
        feature_count=TOOLLIFE968_TOTAL_COL_COUNT,
        sensor_feature_count=TOOLLIFE968_SENSOR_FEATURE_COUNT,
        eol_observation_count=eol_count,
        evidence_status="EXPERIMENTAL",
        source_dataset=source_dataset,
        source_doi=source_doi,
        source_sheet=source_sheet,
        cycle_to_failure_semantics="countdown_to_eol",
        sensor_feature_headers=headers,
        limitations=_LIMITATIONS,
    )


# ---------------------------------------------------------------------------
# Tools list endpoint
# ---------------------------------------------------------------------------

@router.get("/tools", response_model=list[ToolSummaryOut])
def tool_life_tools() -> list[ToolSummaryOut]:
    """List all tools with basic lifecycle statistics."""
    reg = _get_registry()
    if reg is None or not reg.is_seeded():
        raise HTTPException(
            status_code=503,
            detail=(
                "ToolLife 968 data not configured. "
                f"Set {_ENV_VAR} to the source workbook path."
            ),
        )

    all_obs = reg.get_all()
    tool_indices = sorted({o.tool_index for o in all_obs})
    result: list[ToolSummaryOut] = []

    for tid in tool_indices:
        obs_list = sorted(
            [o for o in all_obs if o.tool_index == tid],
            key=lambda o: (o.cycle_number, o.sample_index),
        )
        if not obs_list:
            continue
        first = obs_list[0]
        ctf_values = [o.cycle_to_failure for o in obs_list]
        eol_present = any(o.is_eol for o in obs_list)
        total_cycles = first.total_tool_life_cycles

        result.append(ToolSummaryOut(
            tool_id=tid,
            tool_type=first.tool_type,
            observation_count=len(obs_list),
            total_cycles=total_cycles,
            adoc_mm=float(first.adoc.value),
            rdoc_mm=float(first.rdoc.value),
            eol_present=eol_present,
            min_cycle_to_failure=min(ctf_values),
            max_cycle_to_failure=max(ctf_values),
        ))

    return result


# ---------------------------------------------------------------------------
# Tool detail endpoint
# ---------------------------------------------------------------------------

@router.get("/tools/{tool_id}", response_model=ToolDetailOut)
def tool_life_detail(
    tool_id: int,
    feature_index: int = Query(
        default=0,
        ge=0,
        lt=TOOLLIFE968_SENSOR_FEATURE_COUNT,
        description="Sensor feature index (0–119)",
    ),
) -> ToolDetailOut:
    """
    Return lifecycle series and one sensor feature series for a tool.

    feature_index selects which of the 120 sensor statistical features to
    include in the sensor_series. Default is 0 (first feature in source order).
    """
    reg = _get_registry()
    if reg is None or not reg.is_seeded():
        raise HTTPException(
            status_code=503,
            detail=(
                "ToolLife 968 data not configured. "
                f"Set {_ENV_VAR} to the source workbook path."
            ),
        )

    try:
        obs_list = reg.get_by_tool(tool_id)
    except EmpiricalDataError:
        obs_list = ()

    if not obs_list:
        # Check if tool_id simply has no records
        all_ids = {o.tool_index for o in reg.get_all()}
        if tool_id not in all_ids:
            raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")
        # No observations for this tool (shouldn't happen, but guard)
        raise HTTPException(
            status_code=404, detail=f"No observations found for tool {tool_id}"
        )

    first = obs_list[0]
    eol_present = any(o.is_eol for o in obs_list)
    total_cycles = first.total_tool_life_cycles

    # Sensor feature name
    headers = list(first.source.sensor_feature_headers)
    feature_name = headers[feature_index] if feature_index < len(headers) else f"feature_{feature_index}"

    lifecycle: list[LifecyclePointOut] = []
    sensor_values: list[float] = []

    for idx, obs in enumerate(obs_list):
        lifecycle.append(LifecyclePointOut(
            obs_idx=idx,
            cycle_number=obs.cycle_number,
            sample_index=obs.sample_index,
            cycle_to_failure=obs.cycle_to_failure,
            cycle_to_failure_normalized=float(obs.cycle_to_failure_normalized),
            is_eol=obs.is_eol,
        ))
        sensor_values.append(obs.sensor_features[feature_index])

    source_doi = first.source.doi

    return ToolDetailOut(
        tool_id=tool_id,
        tool_type=first.tool_type,
        observation_count=len(obs_list),
        total_cycles=total_cycles,
        adoc_mm=float(first.adoc.value),
        rdoc_mm=float(first.rdoc.value),
        tool_holder_length_mm=float(first.tool_holder_length.value),
        hardness_mean=float(first.hardness_mean),
        eol_present=eol_present,
        lifecycle=lifecycle,
        sensor_series=SensorSeriesOut(
            feature_index=feature_index,
            feature_name=feature_name,
            values=sensor_values,
        ),
        source_doi=source_doi,
        evidence_status="EXPERIMENTAL",
    )
