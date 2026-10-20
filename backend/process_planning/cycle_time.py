"""Deterministic cycle-time foundation for process plan steps.

PROCESS_PLAN_CYCLE_TIME_FOUNDATION_01

Rules enforced here:
    CUTTING_TIME_FORMULA_DUPLICATED=NO  (calls canonical machining_time_from_distance_feed_rate)
    PATH_LENGTH_GUESSED=NO
    APPROACH_DISTANCE_GUESSED=NO
    RETRACT_DISTANCE_GUESSED=NO
    DWELL_TIME_GUESSED=NO
    TOOL_CHANGE_TIME_GUESSED=NO
    DRILL_TRAVEL_ALLOWANCE_GUESSED=NO
    REAM_TRAVEL_ALLOWANCE_GUESSED=NO
    TURNING_PASS_COUNT_INFERRED=NO
    MILLING_PATH_GENERATION_IMPLEMENTED=NO
    MULTI_AXIS_RAPID_TIME_IMPLEMENTED=NO
    SPINDLE_ACCEL_TIME_IMPLEMENTED=NO
    SETUP_TIME_MODEL_IMPLEMENTED=NO
    LOAD_UNLOAD_TIME_MODEL_IMPLEMENTED=NO
    TOOL_CHANGE_TIME_MODEL_IMPLEMENTED=NO
    KNOWN_SUBTOTAL_MISLABELED_AS_TOTAL=NO
    CYCLE_TIME_AVAILABILITY_CHANGES_PLAN_STATUS=NO
    FALSE_PRODUCTION_CYCLE_TIME_CLAIM=NO
    FALSE_TAKT_CLAIM=NO
    FALSE_OEE_CLAIM=NO
    FALSE_CAPACITY_CLAIM=NO
    CYCLE_TIME_COST_LINK_IMPLEMENTED=NO
    PRIVATE_LOCAL_PATH_VISIBLE=NO
    FEED_RANGE_MIDPOINT_ASSUMED=NO
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from backend.domain.units import Quantity, Unit
from backend.machining.formulas import machining_time_from_distance_feed_rate
from backend.process_planning.metrics import EngineeringMetric, MetricStatus

__all__ = [
    "CycleTimeStatus",
    "CycleTimeScope",
    "TimeComponentStatus",
    "TimeComponent",
    "StepCycleTime",
    "compute_step_cycle_time",
]

_FORMULA_REF = "t = L / Vf  [machining_time_from_distance_feed_rate @ backend.machining.formulas]"


class CycleTimeStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CycleTimeScope(StrEnum):
    CUTTING_ONLY = "CUTTING_ONLY"
    CUTTING_PLUS_EXPLICIT_NONCUTTING = "CUTTING_PLUS_EXPLICIT_NONCUTTING"
    COMPLETE_EXPLICIT_CYCLE = "COMPLETE_EXPLICIT_CYCLE"


class TimeComponentStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class TimeComponent(BaseModel):
    component_id: str
    component_type: str
    status: TimeComponentStatus
    time_sec_min: float | None = None
    time_sec_max: float | None = None
    distance_mm: float | None = None
    rate_mm_min: float | None = None
    formula_reference: str | None = None
    input_provenance: str | None = None
    missing_inputs: list[str] = []
    limitations: list[str] = []


class StepCycleTime(BaseModel):
    status: CycleTimeStatus
    scope: CycleTimeScope
    cutting_time: TimeComponent | None = None
    rapid_time: TimeComponent | None = None
    dwell_time: TimeComponent | None = None
    tool_change_time: None = None        # TOOL_CHANGE_TIME_MODEL_IMPLEMENTED=NO
    known_subtotal_sec_min: float | None = None
    known_subtotal_sec_max: float | None = None
    total_cycle_time: None = None        # COMPLETE_EXPLICIT_CYCLE not achievable yet
    components: list[TimeComponent] = []
    missing_inputs: list[str] = []
    limitations: list[str] = []


def _min_to_sec(t_min: float) -> float:
    return t_min * 60.0


def _cutting_component(
    path_mm: float,
    path_source: str | None,
    feed_metric: EngineeringMetric | None,
) -> TimeComponent:
    """Compute cutting time.

    Reuses canonical machining_time_from_distance_feed_rate.
    FEED_FORMULA_DUPLICATED=NO — never re-implements t = L / fr.
    FEED_RANGE_MIDPOINT_ASSUMED=NO — fastest=L/max_feed, slowest=L/min_feed.
    """
    if feed_metric is None:
        return TimeComponent(
            component_id="CUTTING",
            component_type="CUTTING",
            status=TimeComponentStatus.INSUFFICIENT_DATA,
            distance_mm=path_mm,
            input_provenance=path_source,
            missing_inputs=["feed_rate_mm_min"],
            limitations=["Feed rate metric not available for this step."],
        )

    if feed_metric.status != MetricStatus.AVAILABLE:
        missing = list(feed_metric.missing_inputs or []) or ["feed_rate_mm_min"]
        return TimeComponent(
            component_id="CUTTING",
            component_type="CUTTING",
            status=TimeComponentStatus.INSUFFICIENT_DATA,
            distance_mm=path_mm,
            input_provenance=path_source,
            missing_inputs=missing,
            limitations=[f"Feed rate metric status: {feed_metric.status}"],
        )

    max_feed = feed_metric.max_value
    min_feed = feed_metric.min_value

    if max_feed is None or min_feed is None or max_feed <= 0 or min_feed <= 0:
        return TimeComponent(
            component_id="CUTTING",
            component_type="CUTTING",
            status=TimeComponentStatus.INSUFFICIENT_DATA,
            distance_mm=path_mm,
            input_provenance=path_source,
            missing_inputs=["feed_rate_mm_min"],
        )

    # Fastest cut: highest feed rate → shortest time
    t_fastest = machining_time_from_distance_feed_rate(
        Quantity(path_mm, Unit.MM),
        Quantity(max_feed, Unit.MM_MIN),
    )
    # Slowest cut: lowest feed rate → longest time
    t_slowest = machining_time_from_distance_feed_rate(
        Quantity(path_mm, Unit.MM),
        Quantity(min_feed, Unit.MM_MIN),
    )

    return TimeComponent(
        component_id="CUTTING",
        component_type="CUTTING",
        status=TimeComponentStatus.AVAILABLE,
        time_sec_min=round(_min_to_sec(float(t_fastest.value)), 4),
        time_sec_max=round(_min_to_sec(float(t_slowest.value)), 4),
        distance_mm=path_mm,
        formula_reference=_FORMULA_REF,
        input_provenance=path_source or "USER_INPUT",
    )


def _rapid_component(
    rapid_distance_mm: float,
    machine_rapid_traverse_mpm: float | None,
) -> TimeComponent:
    """Compute rapid traverse time.

    RAPID_RATE_GUESSED=NO — only uses source-backed catalog values.
    MULTI_AXIS_RAPID_TIME_IMPLEMENTED=NO — rapid_distance_mm is effective path,
    not a vector decomposition.
    """
    if machine_rapid_traverse_mpm is None:
        return TimeComponent(
            component_id="RAPID",
            component_type="RAPID",
            status=TimeComponentStatus.INSUFFICIENT_DATA,
            distance_mm=rapid_distance_mm,
            input_provenance="USER_INPUT",
            missing_inputs=["machine_rapid_traverse_mpm"],
            limitations=["Rapid traverse rate not in machine catalog for this machine."],
        )

    rapid_rate_mm_min = machine_rapid_traverse_mpm * 1000.0

    t_rapid = machining_time_from_distance_feed_rate(
        Quantity(rapid_distance_mm, Unit.MM),
        Quantity(rapid_rate_mm_min, Unit.MM_MIN),
    )
    t_rapid_sec = round(_min_to_sec(float(t_rapid.value)), 4)

    return TimeComponent(
        component_id="RAPID",
        component_type="RAPID",
        status=TimeComponentStatus.AVAILABLE,
        time_sec_min=t_rapid_sec,
        time_sec_max=t_rapid_sec,
        distance_mm=rapid_distance_mm,
        rate_mm_min=round(rapid_rate_mm_min, 2),
        formula_reference=_FORMULA_REF,
        input_provenance="USER_INPUT",
    )


def _dwell_component(dwell_sec: float) -> TimeComponent:
    return TimeComponent(
        component_id="DWELL",
        component_type="DWELL",
        status=TimeComponentStatus.AVAILABLE,
        time_sec_min=round(dwell_sec, 4),
        time_sec_max=round(dwell_sec, 4),
        input_provenance="USER_INPUT",
    )


def _overall_status(components: list[TimeComponent]) -> CycleTimeStatus:
    if not components:
        return CycleTimeStatus.INSUFFICIENT_DATA
    available = sum(1 for c in components if c.status == TimeComponentStatus.AVAILABLE)
    if available == len(components):
        return CycleTimeStatus.COMPLETE
    if available > 0:
        return CycleTimeStatus.PARTIAL
    return CycleTimeStatus.INSUFFICIENT_DATA


def compute_step_cycle_time(
    *,
    cutting_path_length_mm: float | None,
    cutting_path_source: str | None,
    feed_rate_metric: EngineeringMetric | None,
    rapid_distance_mm: float | None,
    machine_rapid_traverse_mpm: float | None,
    dwell_sec: float | None,
) -> StepCycleTime:
    """Compute deterministic cycle-time foundation for a single process plan step.

    Never alters the step's planning_status.
    Known subtotal is NOT total cycle time.
    Tool-change, setup, and load/unload times are not modelled.
    """
    has_rapid = rapid_distance_mm is not None and rapid_distance_mm > 0
    has_dwell = dwell_sec is not None and dwell_sec > 0

    scope = (
        CycleTimeScope.CUTTING_PLUS_EXPLICIT_NONCUTTING
        if (has_rapid or has_dwell)
        else CycleTimeScope.CUTTING_ONLY
    )

    limitations = [
        "TOOL_CHANGE_TIME_MODEL_IMPLEMENTED=NO — no source-backed ATC time in catalog.",
        "SETUP_TIME_MODEL_IMPLEMENTED=NO — no setup time data.",
        "KNOWN_SUBTOTAL_IS_NOT_TOTAL_CYCLE_TIME — non-cutting components may be absent.",
    ]

    top_missing: list[str] = []
    components: list[TimeComponent] = []

    # Cutting time
    if cutting_path_length_mm is not None:
        ct = _cutting_component(cutting_path_length_mm, cutting_path_source, feed_rate_metric)
    else:
        top_missing.append("cutting_path_length_mm")
        ct = TimeComponent(
            component_id="CUTTING",
            component_type="CUTTING",
            status=TimeComponentStatus.INSUFFICIENT_DATA,
            missing_inputs=["cutting_path_length_mm"],
            limitations=["Cutting path length not provided."],
        )
    components.append(ct)
    if ct.status != TimeComponentStatus.AVAILABLE:
        for mi in ct.missing_inputs:
            if mi not in top_missing:
                top_missing.append(mi)

    # Rapid time
    rapid_comp: TimeComponent | None = None
    if has_rapid:
        rapid_comp = _rapid_component(rapid_distance_mm, machine_rapid_traverse_mpm)  # type: ignore[arg-type]
        components.append(rapid_comp)
        if rapid_comp.status != TimeComponentStatus.AVAILABLE:
            for mi in rapid_comp.missing_inputs:
                if mi not in top_missing:
                    top_missing.append(mi)

    # Dwell time
    dwell_comp: TimeComponent | None = None
    if has_dwell:
        dwell_comp = _dwell_component(dwell_sec)  # type: ignore[arg-type]
        components.append(dwell_comp)

    # Known subtotal (sum of available components only)
    subtotal_min: float | None = None
    subtotal_max: float | None = None
    for comp in components:
        if comp.status == TimeComponentStatus.AVAILABLE:
            subtotal_min = (subtotal_min or 0.0) + (comp.time_sec_min or 0.0)
            subtotal_max = (subtotal_max or 0.0) + (comp.time_sec_max or 0.0)

    if subtotal_min is not None:
        subtotal_min = round(subtotal_min, 4)
    if subtotal_max is not None:
        subtotal_max = round(subtotal_max, 4)

    return StepCycleTime(
        status=_overall_status(components),
        scope=scope,
        cutting_time=ct,
        rapid_time=rapid_comp,
        dwell_time=dwell_comp,
        tool_change_time=None,
        known_subtotal_sec_min=subtotal_min,
        known_subtotal_sec_max=subtotal_max,
        total_cycle_time=None,
        components=components,
        missing_inputs=top_missing,
        limitations=limitations,
    )
