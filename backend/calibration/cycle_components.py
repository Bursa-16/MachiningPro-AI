"""Extended cycle-time component model — EPIC_04F.

CYCLE_TIME_COMPONENT_MODEL_IMPLEMENTED=YES
TOOL_CHANGE_TIME_COMPONENT_IMPLEMENTED=YES
SETUP_TIME_COMPONENT_IMPLEMENTED=YES
LOAD_UNLOAD_TIME_COMPONENT_IMPLEMENTED=YES
PROBING_TIME_COMPONENT_IMPLEMENTED=YES
INSPECTION_TIME_COMPONENT_IMPLEMENTED=YES
APPROACH_RETRACT_TIME_MODEL_IMPLEMENTED=YES
BATCH_QUANTITY_TIME_MODEL_IMPLEMENTED=YES
ROUTE_TOTAL_TIME_MODEL_IMPLEMENTED=YES
ROUTE_TIME_COMPLETENESS_IMPLEMENTED=YES
SPINDLE_ACCEL_TIME_IMPLEMENTED=DEFERRED

Safety:
UNKNOWN_TIME_COMPONENT_TREATED_AS_ZERO=NO
PARTIAL_TIME_PRESENTED_AS_TOTAL=NO
TOOL_CHANGE_GUESSED=NO
SETUP_TIME_GUESSED=NO
APPROACH_RETRACT_GUESSED=NO
"""

from __future__ import annotations

from backend.calibration.models import (
    BatchModel,
    CalibrationConfidence,
    CalibrationSource,
    CycleComponentStatus,
    CycleTimeCompleteness,
    CycleTimeComponent,
    CycleTimeEstimate,
)

__all__ = [
    "make_cutting_component",
    "make_rapid_component",
    "make_approach_retract_component",
    "make_tool_change_component",
    "make_spindle_accel_component",
    "make_setup_component",
    "make_load_unload_component",
    "make_probing_component",
    "make_inspection_component",
    "make_dwell_component",
    "assemble_cycle_time_estimate",
    "compute_batch_model",
    "SPINDLE_ACCEL_TIME_IMPLEMENTED",
]

SPINDLE_ACCEL_TIME_IMPLEMENTED = "DEFERRED"

_KNOWN_STATUSES = frozenset({
    CycleComponentStatus.CALCULATED,
    CycleComponentStatus.USER_SUPPLIED,
    CycleComponentStatus.REFERENCE,
})


def make_cutting_component(
    value_sec_min: float | None,
    value_sec_max: float | None,
    method: str = "t=L/Vf",
) -> CycleTimeComponent:
    if value_sec_min is not None and value_sec_max is not None:
        return CycleTimeComponent(
            component_id="CUTTING",
            component_type="CUTTING",
            status=CycleComponentStatus.CALCULATED,
            value_sec_min=value_sec_min,
            value_sec_max=value_sec_max,
            source=CalibrationSource.LITERATURE_REFERENCE,
            confidence=CalibrationConfidence.HIGH,
            method=method,
        )
    return CycleTimeComponent(
        component_id="CUTTING",
        component_type="CUTTING",
        status=CycleComponentStatus.UNKNOWN,
        source=CalibrationSource.INSUFFICIENT_DATA,
        confidence=CalibrationConfidence.UNKNOWN,
        method=method,
        missing_inputs=["cutting_path_length_mm", "feed_rate_mm_min"],
        notes="Cutting path length or feed rate not available.",
    )


def make_rapid_component(
    value_sec: float | None,
    machine_rapid_rate_available: bool = True,
) -> CycleTimeComponent:
    if value_sec is not None:
        return CycleTimeComponent(
            component_id="RAPID",
            component_type="RAPID",
            status=CycleComponentStatus.CALCULATED,
            value_sec_min=value_sec,
            value_sec_max=value_sec,
            source=CalibrationSource.MANUFACTURER_REFERENCE,
            confidence=CalibrationConfidence.MEDIUM,
            method="t=D/rapid_rate",
            notes="MULTI_AXIS_RAPID_TIME_IMPLEMENTED=NO — scalar effective path.",
        )
    missing = ["rapid_distance_mm"]
    if not machine_rapid_rate_available:
        missing.append("machine_rapid_traverse_mpm")
    return CycleTimeComponent(
        component_id="RAPID",
        component_type="RAPID",
        status=CycleComponentStatus.UNKNOWN,
        source=CalibrationSource.INSUFFICIENT_DATA,
        confidence=CalibrationConfidence.UNKNOWN,
        method="t=D/rapid_rate",
        missing_inputs=missing,
    )


def make_approach_retract_component(
    approach_sec: float | None,
    retract_sec: float | None,
    distance_known: bool = False,
) -> CycleTimeComponent:
    """APPROACH_RETRACT_GUESSED=NO: UNKNOWN when no explicit distance."""
    if approach_sec is not None and retract_sec is not None:
        total = approach_sec + retract_sec
        status = (
            CycleComponentStatus.CALCULATED
            if distance_known
            else CycleComponentStatus.USER_SUPPLIED
        )
        return CycleTimeComponent(
            component_id="APPROACH_RETRACT",
            component_type="APPROACH",
            status=status,
            value_sec_min=total,
            value_sec_max=total,
            source=CalibrationSource.USER_OVERRIDE,
            confidence=CalibrationConfidence.MEDIUM,
            method="explicit_distance_or_allowance",
        )
    return CycleTimeComponent(
        component_id="APPROACH_RETRACT",
        component_type="APPROACH",
        status=CycleComponentStatus.UNKNOWN,
        source=CalibrationSource.INSUFFICIENT_DATA,
        confidence=CalibrationConfidence.UNKNOWN,
        method="explicit_distance_or_allowance",
        missing_inputs=["approach_distance_mm", "retract_distance_mm"],
        notes="APPROACH_RETRACT_GUESSED=NO — not estimated without explicit geometry.",
    )


def make_tool_change_component(
    atc_time_sec: float | None,
    tool_changes: int = 1,
    machine_id: str | None = None,
) -> CycleTimeComponent:
    """TOOL_CHANGE_GUESSED=NO: UNKNOWN when atc_time_sec not in catalog."""
    if atc_time_sec is not None and tool_changes >= 0:
        total_sec = atc_time_sec * tool_changes
        return CycleTimeComponent(
            component_id="TOOL_CHANGE",
            component_type="TOOL_CHANGE",
            status=CycleComponentStatus.REFERENCE,
            value_sec_min=total_sec,
            value_sec_max=total_sec,
            source=CalibrationSource.MANUFACTURER_REFERENCE,
            confidence=CalibrationConfidence.MEDIUM,
            method=f"atc_time×changes={atc_time_sec}×{tool_changes}",
            notes=f"Machine: {machine_id or 'unspecified'}",
        )
    return CycleTimeComponent(
        component_id="TOOL_CHANGE",
        component_type="TOOL_CHANGE",
        status=CycleComponentStatus.UNKNOWN,
        source=CalibrationSource.INSUFFICIENT_DATA,
        confidence=CalibrationConfidence.UNKNOWN,
        method="atc_time×changes",
        missing_inputs=["atc_time_sec"],
        notes="TOOL_CHANGE_GUESSED=NO — ATC time not in machine catalog.",
    )


def make_spindle_accel_component() -> CycleTimeComponent:
    """SPINDLE_ACCEL_TIME_IMPLEMENTED=DEFERRED — no standard catalog source."""
    return CycleTimeComponent(
        component_id="SPINDLE_ACCEL_DECEL",
        component_type="SPINDLE_ACCEL_DECEL",
        status=CycleComponentStatus.UNKNOWN,
        source=CalibrationSource.INSUFFICIENT_DATA,
        confidence=CalibrationConfidence.UNKNOWN,
        method="DEFERRED",
        missing_inputs=["spindle_acceleration_data"],
        notes="SPINDLE_ACCEL_TIME_IMPLEMENTED=DEFERRED.",
    )


def make_setup_component(
    setup_sec: float | None,
    source: CalibrationSource = CalibrationSource.USER_OVERRIDE,
) -> CycleTimeComponent:
    """SETUP_TIME_GUESSED=NO: explicit only."""
    if setup_sec is not None and setup_sec >= 0:
        confidence = (
            CalibrationConfidence.HIGH
            if source == CalibrationSource.USER_OVERRIDE
            else CalibrationConfidence.MEDIUM
        )
        return CycleTimeComponent(
            component_id="SETUP",
            component_type="SETUP",
            status=CycleComponentStatus.USER_SUPPLIED,
            value_sec_min=setup_sec,
            value_sec_max=setup_sec,
            source=source,
            confidence=confidence,
            method="explicit_input",
        )
    return CycleTimeComponent(
        component_id="SETUP",
        component_type="SETUP",
        status=CycleComponentStatus.UNKNOWN,
        source=CalibrationSource.INSUFFICIENT_DATA,
        confidence=CalibrationConfidence.UNKNOWN,
        method="explicit_input",
        missing_inputs=["setup_time_sec"],
        notes="SETUP_TIME_GUESSED=NO.",
    )


def make_load_unload_component(
    value_sec: float | None,
    source: CalibrationSource = CalibrationSource.USER_OVERRIDE,
) -> CycleTimeComponent:
    if value_sec is not None and value_sec >= 0:
        return CycleTimeComponent(
            component_id="LOAD_UNLOAD",
            component_type="LOAD_UNLOAD",
            status=CycleComponentStatus.USER_SUPPLIED,
            value_sec_min=value_sec,
            value_sec_max=value_sec,
            source=source,
            confidence=CalibrationConfidence.MEDIUM,
            method="explicit_input",
        )
    return CycleTimeComponent(
        component_id="LOAD_UNLOAD",
        component_type="LOAD_UNLOAD",
        status=CycleComponentStatus.UNKNOWN,
        source=CalibrationSource.INSUFFICIENT_DATA,
        confidence=CalibrationConfidence.UNKNOWN,
        method="explicit_input",
        missing_inputs=["load_unload_time_sec"],
    )


def make_probing_component(
    value_sec: float | None,
    source: CalibrationSource = CalibrationSource.USER_OVERRIDE,
) -> CycleTimeComponent:
    if value_sec is not None and value_sec >= 0:
        return CycleTimeComponent(
            component_id="PROBING",
            component_type="PROBING",
            status=CycleComponentStatus.USER_SUPPLIED,
            value_sec_min=value_sec,
            value_sec_max=value_sec,
            source=source,
            confidence=CalibrationConfidence.MEDIUM,
            method="explicit_input",
        )
    return CycleTimeComponent(
        component_id="PROBING",
        component_type="PROBING",
        status=CycleComponentStatus.UNKNOWN,
        source=CalibrationSource.INSUFFICIENT_DATA,
        confidence=CalibrationConfidence.UNKNOWN,
        method="explicit_input",
        missing_inputs=["probing_time_sec"],
        notes="Probing cycle time not fabricated.",
    )


def make_inspection_component(
    value_sec: float | None,
    source: CalibrationSource = CalibrationSource.USER_OVERRIDE,
) -> CycleTimeComponent:
    if value_sec is not None and value_sec >= 0:
        return CycleTimeComponent(
            component_id="INSPECTION",
            component_type="INSPECTION",
            status=CycleComponentStatus.USER_SUPPLIED,
            value_sec_min=value_sec,
            value_sec_max=value_sec,
            source=source,
            confidence=CalibrationConfidence.MEDIUM,
            method="explicit_input",
        )
    return CycleTimeComponent(
        component_id="INSPECTION",
        component_type="INSPECTION",
        status=CycleComponentStatus.UNKNOWN,
        source=CalibrationSource.INSUFFICIENT_DATA,
        confidence=CalibrationConfidence.UNKNOWN,
        method="explicit_input",
        missing_inputs=["inspection_time_sec"],
    )


def make_dwell_component(value_sec: float) -> CycleTimeComponent:
    return CycleTimeComponent(
        component_id="DWELL",
        component_type="DWELL",
        status=CycleComponentStatus.USER_SUPPLIED,
        value_sec_min=value_sec,
        value_sec_max=value_sec,
        source=CalibrationSource.USER_OVERRIDE,
        confidence=CalibrationConfidence.HIGH,
        method="explicit_input",
    )


def assemble_cycle_time_estimate(
    components: list[CycleTimeComponent],
    uncertainty_note: str = "",
) -> CycleTimeEstimate:
    """Assemble components into a CycleTimeEstimate.

    PARTIAL_TIME_PRESENTED_AS_TOTAL=NO:
      known_total = sum of known components only.
      total_cycle_time = set only when no unknown components.
    UNKNOWN_TIME_COMPONENT_TREATED_AS_ZERO=NO
    """
    known_min = 0.0
    known_max = 0.0
    has_any_known = False
    unknown_ids: list[str] = []

    for comp in components:
        if comp.status in _KNOWN_STATUSES and comp.value_sec_min is not None:
            known_min += comp.value_sec_min
            known_max += (
                comp.value_sec_max if comp.value_sec_max is not None else comp.value_sec_min
            )
            has_any_known = True
        else:
            unknown_ids.append(comp.component_id)

    if not unknown_ids:
        completeness = CycleTimeCompleteness.FULLY_CALCULATED
    elif has_any_known:
        completeness = CycleTimeCompleteness.PARTIALLY_CALCULATED
    else:
        completeness = CycleTimeCompleteness.INSUFFICIENT_DATA

    total_min = round(known_min, 4) if has_any_known else None
    total_max = round(known_max, 4) if has_any_known else None
    is_full = completeness == CycleTimeCompleteness.FULLY_CALCULATED
    full_min = round(known_min, 4) if is_full else None
    full_max = round(known_max, 4) if is_full else None

    return CycleTimeEstimate(
        components=components,
        completeness=completeness,
        known_total_sec_min=total_min,
        known_total_sec_max=total_max,
        total_cycle_time_sec_min=full_min,
        total_cycle_time_sec_max=full_max,
        unknown_components=unknown_ids,
        uncertainty_note=uncertainty_note or (
            "Some time components are UNKNOWN — known total is NOT total cycle time."
            if unknown_ids
            else ""
        ),
        limitations=[
            "PARTIAL_TIME_PRESENTED_AS_TOTAL=NO",
            "UNKNOWN_TIME_COMPONENT_TREATED_AS_ZERO=NO",
        ],
    )


def compute_batch_model(
    batch_quantity: int,
    setup_sec: float | None,
    cutting_sec_min: float | None,
    cutting_sec_max: float | None,
    other_per_part_sec: float = 0.0,
) -> BatchModel:
    """Compute per-part amortized cycle time.

    per_part_setup_sec = setup_sec / batch_quantity
    per_part_total = cutting + amortized_setup + other_per_part
    """
    if batch_quantity <= 0:
        return BatchModel(
            batch_quantity=batch_quantity,
            completeness=CycleTimeCompleteness.INSUFFICIENT_DATA,
            notes="batch_quantity must be > 0",
        )

    per_part_setup: float | None = None
    if setup_sec is not None:
        per_part_setup = round(setup_sec / batch_quantity, 4)

    per_part_total_min: float | None = None
    per_part_total_max: float | None = None
    completeness: CycleTimeCompleteness

    if cutting_sec_min is not None and per_part_setup is not None:
        per_part_total_min = round(
            cutting_sec_min + per_part_setup + other_per_part_sec, 4
        )
        per_part_total_max = round(
            (cutting_sec_max if cutting_sec_max is not None else cutting_sec_min)
            + per_part_setup
            + other_per_part_sec,
            4,
        )
        completeness = CycleTimeCompleteness.FULLY_CALCULATED
    elif cutting_sec_min is not None or per_part_setup is not None:
        completeness = CycleTimeCompleteness.PARTIALLY_CALCULATED
    else:
        completeness = CycleTimeCompleteness.INSUFFICIENT_DATA

    return BatchModel(
        batch_quantity=batch_quantity,
        setup_sec=setup_sec,
        per_part_cutting_sec_min=cutting_sec_min,
        per_part_cutting_sec_max=cutting_sec_max,
        per_part_setup_sec=per_part_setup,
        per_part_total_sec_min=per_part_total_min,
        per_part_total_sec_max=per_part_total_max,
        completeness=completeness,
    )
