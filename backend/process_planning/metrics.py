"""Deterministic engineering metrics for process plan steps.

PROCESS_PLAN_ENGINEERING_METRICS_01

Aggregation/presentation layer only — does NOT re-implement any formula
from backend.machining.formulas.  All numeric values come from pre-computed
canonical sources (compatibility / selection engine outputs) or from
source-backed cutting-parameter reference records.

Rules enforced here:
  CALCULATED_RPM_REUSED=YES
  RPM_FORMULA_DUPLICATED=NO
  SELECTION_RPM_LOGIC_DUPLICATED=NO
  MISSING_METRIC_AS_ZERO=NO
  METRIC_AVAILABILITY_CHANGES_PLAN_STATUS=NO
  ENGINEERING_METRICS_SCORE_IMPLEMENTED=NO
  FALSE_AI_CLAIM=NO
  FALSE_OPTIMIZATION_CLAIM=NO
  FALSE_PRODUCTION_VALIDATION_CLAIM=NO

Metrics implemented:
  CALCULATED_RPM     — reused from compatibility / selection engine output
  RPM_UTILIZATION    — 100 × n / n_max (machine spindle max)
  RPM_MARGIN         — reused from selection engine; (n_max − n) / n_max
  FEED_RATE_RANGE    — reference-based feed × RPM (range)
  AXIAL_ENGAGEMENT_RATIO — ap / D (range)

Metrics NOT implemented (input gaps documented in feasibility report):
  MRR, cutting force, machining power, spindle torque,
  predicted surface roughness, cycle time, process cost, tool life.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

__all__ = [
    "MetricStatus",
    "EngineeringMetric",
    "StepEngineeringMetrics",
    "compute_step_metrics",
]


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------

class MetricStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_APPLICABLE = "NOT_APPLICABLE"


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class EngineeringMetric(BaseModel):
    metric_id: str
    metric_name: str
    status: MetricStatus
    value: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    unit: str | None = None
    formula_reference: str | None = None
    inputs_used: list[str] = []
    missing_inputs: list[str] = []
    explanation: str | None = None


class StepEngineeringMetrics(BaseModel):
    metrics: list[EngineeringMetric]
    metrics_available_count: int
    metrics_not_available_count: int
    metrics_insufficient_data_count: int


# ---------------------------------------------------------------------------
# Internal helpers — one per metric
# ---------------------------------------------------------------------------

def _rpm_metric(calculated_rpm: float | None) -> EngineeringMetric:
    """Expose pre-computed canonical RPM. CALCULATED_RPM_REUSED=YES."""
    if calculated_rpm is not None and calculated_rpm > 0:
        return EngineeringMetric(
            metric_id="CALCULATED_RPM",
            metric_name="Spindle Speed",
            status=MetricStatus.AVAILABLE,
            value=round(calculated_rpm),
            unit="rpm",
            formula_reference="n = (1000 × Vc) / (π × D)",
            inputs_used=["cutting_speed_m_min (Vc)", "tool_diameter_mm (D)"],
            explanation=(
                "Spindle speed from compatibility engine. "
                "Calculated from cutting speed and tool diameter."
            ),
        )
    if calculated_rpm is None:
        return EngineeringMetric(
            metric_id="CALCULATED_RPM",
            metric_name="Spindle Speed",
            status=MetricStatus.INSUFFICIENT_DATA,
            missing_inputs=["cutting_speed_m_min (Vc)", "tool_diameter_mm (D)"],
            explanation="Vc and/or tool diameter not provided for this step.",
        )
    return EngineeringMetric(
        metric_id="CALCULATED_RPM",
        metric_name="Spindle Speed",
        status=MetricStatus.NOT_AVAILABLE,
        explanation="Calculated RPM is zero — check Vc and diameter inputs.",
    )


def _rpm_utilization_metric(
    calculated_rpm: float | None,
    machine_spindle_max_rpm: int | None,
) -> EngineeringMetric:
    """100 × n / n_max. Machine spindle only — MISSING_LIMIT_AS_ZERO=NO."""
    if calculated_rpm is None or calculated_rpm <= 0:
        return EngineeringMetric(
            metric_id="RPM_UTILIZATION",
            metric_name="RPM Utilization",
            status=MetricStatus.INSUFFICIENT_DATA,
            missing_inputs=["calculated_rpm (n)"],
            explanation="Calculated RPM not available.",
        )
    if machine_spindle_max_rpm is None:
        return EngineeringMetric(
            metric_id="RPM_UTILIZATION",
            metric_name="RPM Utilization",
            status=MetricStatus.INSUFFICIENT_DATA,
            missing_inputs=["machine_spindle_max_rpm (n_max)"],
            explanation=(
                "Machine spindle max RPM not published for the selected machine. "
                "MISSING_LIMIT_AS_ZERO=NO."
            ),
        )
    if machine_spindle_max_rpm <= 0:
        return EngineeringMetric(
            metric_id="RPM_UTILIZATION",
            metric_name="RPM Utilization",
            status=MetricStatus.NOT_AVAILABLE,
            explanation="Machine spindle max RPM is not positive.",
        )
    utilization = round(100.0 * calculated_rpm / machine_spindle_max_rpm, 1)
    return EngineeringMetric(
        metric_id="RPM_UTILIZATION",
        metric_name="RPM Utilization",
        status=MetricStatus.AVAILABLE,
        value=utilization,
        unit="%",
        formula_reference="utilization = 100 × n / n_max",
        inputs_used=[
            f"n = {round(calculated_rpm)} rpm",
            f"n_max = {machine_spindle_max_rpm} rpm",
        ],
        explanation=(
            f"Machine spindle utilization: {round(calculated_rpm)} / "
            f"{machine_spindle_max_rpm} rpm = {utilization}%."
        ),
    )


def _rpm_margin_metric(
    rpm_margin_frac: float | None,
    calculated_rpm: float | None,
    machine_spindle_max_rpm: int | None,
) -> EngineeringMetric:
    """Reuse canonical RPM margin from selection engine (fraction → display as %).

    rpm_margin_frac = (n_max − n) / n_max  (decimal, e.g. 0.417 = 41.7 %)
    RPM_MARGIN_SEMANTICS_AMBIGUOUS=NO — machine-spindle-only margin.
    """
    if rpm_margin_frac is None:
        if calculated_rpm is None:
            return EngineeringMetric(
                metric_id="RPM_MARGIN",
                metric_name="RPM Margin",
                status=MetricStatus.INSUFFICIENT_DATA,
                missing_inputs=["calculated_rpm (n)"],
                explanation="Vc or tool diameter not provided; RPM margin cannot be determined.",
            )
        if machine_spindle_max_rpm is None:
            return EngineeringMetric(
                metric_id="RPM_MARGIN",
                metric_name="RPM Margin",
                status=MetricStatus.INSUFFICIENT_DATA,
                missing_inputs=["machine_spindle_max_rpm (n_max)"],
                explanation=(
                    "Machine spindle max RPM not published. MISSING_LIMIT_AS_ZERO=NO."
                ),
            )
        return EngineeringMetric(
            metric_id="RPM_MARGIN",
            metric_name="RPM Margin",
            status=MetricStatus.NOT_AVAILABLE,
            explanation="RPM margin could not be determined.",
        )

    pct = round(rpm_margin_frac * 100, 1)
    rpm_headroom = (
        round(machine_spindle_max_rpm - calculated_rpm)
        if machine_spindle_max_rpm is not None and calculated_rpm is not None
        else None
    )
    headroom_note = (
        f" ({rpm_headroom:+} rpm headroom)" if rpm_headroom is not None else ""
    )
    return EngineeringMetric(
        metric_id="RPM_MARGIN",
        metric_name="RPM Margin",
        status=MetricStatus.AVAILABLE,
        value=pct,
        unit="%",
        formula_reference="margin = (n_max − n) / n_max",
        inputs_used=[
            f"n = {round(calculated_rpm)} rpm" if calculated_rpm else "n (calculated)",
            (
                f"n_max = {machine_spindle_max_rpm} rpm"
                if machine_spindle_max_rpm
                else "n_max (machine)"
            ),
        ],
        explanation=(
            f"Spindle headroom: {pct}%{headroom_note}. "
            "Reused from selection engine. Machine-spindle margin only."
        ),
    )


def _feed_rate_range_metric(
    *,
    operation: str,
    calculated_rpm: float | None,
    cutting_param_refs: list,
    number_of_flutes: int | None,
    cutting_tool_id: str | None,
) -> EngineeringMetric:
    """Reference-based feed rate range.

    Turning / drilling / reaming: fr = fn × n
    Milling:                       fr = fz × z × n
    FLUTE_COUNT_INFERRED=NO — z from tool catalog only.
    MISSING_METRIC_AS_ZERO=NO.
    """
    op = operation.lower()

    if calculated_rpm is None or calculated_rpm <= 0:
        return EngineeringMetric(
            metric_id="FEED_RATE_RANGE",
            metric_name="Feed Rate Range",
            status=MetricStatus.INSUFFICIENT_DATA,
            missing_inputs=["calculated_rpm (n)"],
            explanation="Calculated RPM not available; feed rate cannot be computed.",
        )

    is_milling = (op == "milling")
    param_type_needed = "FEED_PER_TOOTH" if is_milling else "FEED_PER_REV"
    feed_refs = [r for r in cutting_param_refs if r.parameter_type == param_type_needed]

    if not feed_refs:
        return EngineeringMetric(
            metric_id="FEED_RATE_RANGE",
            metric_name="Feed Rate Range",
            status=MetricStatus.NOT_AVAILABLE,
            missing_inputs=[f"{param_type_needed} reference records"],
            explanation=(
                f"No {param_type_needed} reference records for this "
                "operation / material combination."
            ),
        )

    min_feed = min(r.min_value for r in feed_refs)
    max_feed = max(r.max_value for r in feed_refs)

    if is_milling:
        if number_of_flutes is None:
            tool_note = f" ({cutting_tool_id})" if cutting_tool_id else ""
            return EngineeringMetric(
                metric_id="FEED_RATE_RANGE",
                metric_name="Feed Rate Range",
                status=MetricStatus.INSUFFICIENT_DATA,
                inputs_used=[f"FEED_PER_TOOTH: {min_feed}–{max_feed} mm/tooth"],
                missing_inputs=["number_of_flutes (z)"],
                explanation=(
                    f"FLUTE_COUNT_INFERRED=NO: number_of_flutes not available"
                    f"{tool_note}. Cannot compute milling feed rate."
                ),
            )
        min_fr = round(min_feed * number_of_flutes * calculated_rpm, 1)
        max_fr = round(max_feed * number_of_flutes * calculated_rpm, 1)
        formula = "fr = fz × z × n"
        inputs_used = [
            f"fz: {min_feed}–{max_feed} mm/tooth",
            f"z = {number_of_flutes} flutes",
            f"n = {round(calculated_rpm)} rpm",
        ]
        unit = "mm/min"
    else:
        min_fr = round(min_feed * calculated_rpm, 1)
        max_fr = round(max_feed * calculated_rpm, 1)
        formula = "fr = fn × n"
        inputs_used = [
            f"fn: {min_feed}–{max_feed} mm/rev",
            f"n = {round(calculated_rpm)} rpm",
        ]
        unit = "mm/min"

    return EngineeringMetric(
        metric_id="FEED_RATE_RANGE",
        metric_name="Feed Rate Range",
        status=MetricStatus.AVAILABLE,
        min_value=min_fr,
        max_value=max_fr,
        unit=unit,
        formula_reference=formula,
        inputs_used=inputs_used,
        explanation=(
            f"Reference-based range: {min_fr}–{max_fr} mm/min. "
            "REFERENCE_ONLY — validate before production use."
        ),
    )


def _axial_engagement_metric(
    *,
    tool_diameter_mm: float | None,
    cutting_param_refs: list,
) -> EngineeringMetric:
    """ap / D ratio from source-backed cutting parameter records.

    Geometric engagement only — not load %, utilisation %, or efficiency.
    """
    ap_refs = [r for r in cutting_param_refs if r.parameter_type == "AXIAL_DEPTH_OF_CUT"]

    if not ap_refs:
        return EngineeringMetric(
            metric_id="AXIAL_ENGAGEMENT_RATIO",
            metric_name="Axial Engagement Ratio",
            status=MetricStatus.NOT_AVAILABLE,
            missing_inputs=["AXIAL_DEPTH_OF_CUT reference records (ap)"],
            explanation=(
                "No AXIAL_DEPTH_OF_CUT reference records for this "
                "operation / material combination."
            ),
        )

    if tool_diameter_mm is None or tool_diameter_mm <= 0:
        return EngineeringMetric(
            metric_id="AXIAL_ENGAGEMENT_RATIO",
            metric_name="Axial Engagement Ratio",
            status=MetricStatus.INSUFFICIENT_DATA,
            inputs_used=["AXIAL_DEPTH_OF_CUT reference available"],
            missing_inputs=["tool_diameter_mm (D)"],
            explanation=(
                "Tool diameter not provided for this step; "
                "axial engagement ratio cannot be computed."
            ),
        )

    min_ap = min(r.min_value for r in ap_refs)
    max_ap = max(r.max_value for r in ap_refs)
    min_ratio = round(min_ap / tool_diameter_mm, 4)
    max_ratio = round(max_ap / tool_diameter_mm, 4)

    return EngineeringMetric(
        metric_id="AXIAL_ENGAGEMENT_RATIO",
        metric_name="Axial Engagement Ratio",
        status=MetricStatus.AVAILABLE,
        min_value=min_ratio,
        max_value=max_ratio,
        unit="ap/D",
        formula_reference="ratio = ap / D",
        inputs_used=[
            f"ap: {min_ap}–{max_ap} mm",
            f"D = {tool_diameter_mm} mm",
        ],
        explanation=(
            f"Geometric axial engagement: ap/D = {min_ratio}–{max_ratio}. "
            "Reference-based. Not a load or utilisation metric."
        ),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def compute_step_metrics(
    *,
    operation: str,
    calculated_rpm: float | None,
    rpm_margin_frac: float | None,
    machine_spindle_max_rpm: int | None,
    cutting_param_refs: list,
    tool_diameter_mm: float | None,
    number_of_flutes: int | None,
    cutting_tool_id: str | None,
) -> StepEngineeringMetrics:
    """Compute all engineering metrics for one plan step.

    Args:
        operation: e.g. "milling", "drilling"
        calculated_rpm: from selection/compatibility engine (REUSED, not recalculated)
        rpm_margin_frac: (n_max-n)/n_max as decimal fraction (from selection engine)
        machine_spindle_max_rpm: from machine catalog record
        cutting_param_refs: CuttingParameterRef list from plan step
        tool_diameter_mm: from step request
        number_of_flutes: from cutting tool catalog record (FLUTE_COUNT_INFERRED=NO)
        cutting_tool_id: stable_id of selected/constrained tool (for diagnostics)
    """
    metrics = [
        _rpm_metric(calculated_rpm),
        _rpm_utilization_metric(calculated_rpm, machine_spindle_max_rpm),
        _rpm_margin_metric(rpm_margin_frac, calculated_rpm, machine_spindle_max_rpm),
        _feed_rate_range_metric(
            operation=operation,
            calculated_rpm=calculated_rpm,
            cutting_param_refs=cutting_param_refs,
            number_of_flutes=number_of_flutes,
            cutting_tool_id=cutting_tool_id,
        ),
        _axial_engagement_metric(
            tool_diameter_mm=tool_diameter_mm,
            cutting_param_refs=cutting_param_refs,
        ),
    ]

    available = sum(1 for m in metrics if m.status == MetricStatus.AVAILABLE)
    not_available = sum(1 for m in metrics if m.status == MetricStatus.NOT_AVAILABLE)
    insufficient = sum(1 for m in metrics if m.status == MetricStatus.INSUFFICIENT_DATA)

    return StepEngineeringMetrics(
        metrics=metrics,
        metrics_available_count=available,
        metrics_not_available_count=not_available,
        metrics_insufficient_data_count=insufficient,
    )
