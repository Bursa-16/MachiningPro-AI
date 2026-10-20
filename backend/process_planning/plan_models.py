"""API-facing Pydantic models for the deterministic process planning engine.

PROCESS_PLANNING_ENGINE_01
PROCESS_PLAN_CYCLE_TIME_FOUNDATION_01

FALSE_AI_CLAIM=NO
FALSE_OPTIMIZATION_CLAIM=NO
FALSE_CYCLE_TIME_CLAIM=NO
FALSE_COST_CLAIM=NO
SELECTION_LOGIC_DUPLICATED=NO
COMPATIBILITY_LOGIC_DUPLICATED=NO
CYCLE_TIME_FOUNDATION_IMPLEMENTED=YES
PROCESS_COST_MODEL_IMPLEMENTED=NO
TOOLLIFE_USED_FOR_PROCESS_PLAN_PREDICTION=NO
FORCED_CONFIGURATION_WINNER=NO
PATH_LENGTH_GUESSED=NO
FEED_FORMULA_DUPLICATED=NO
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field, field_validator

from backend.process_planning.cycle_time import StepCycleTime
from backend.process_planning.metrics import StepEngineeringMetrics

# ---------------------------------------------------------------------------
# Step-level planning status
# ---------------------------------------------------------------------------

STEP_STATUS_PLANNED = "PLANNED"
STEP_STATUS_BLOCKED = "BLOCKED"
STEP_STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
STEP_STATUS_NOT_SUPPORTED = "NOT_SUPPORTED"

# ---------------------------------------------------------------------------
# Plan-level overall status
# ---------------------------------------------------------------------------

PLAN_COMPLETE = "PLAN_COMPLETE"
PLAN_PARTIAL = "PLAN_PARTIAL"
PLAN_BLOCKED = "PLAN_BLOCKED"
PLAN_INSUFFICIENT_DATA = "PLAN_INSUFFICIENT_DATA"

VALID_PLAN_STATUSES: frozenset[str] = frozenset(
    {PLAN_COMPLETE, PLAN_PARTIAL, PLAN_BLOCKED, PLAN_INSUFFICIENT_DATA}
)

_DISCLAIMER = (
    "Process plans are evaluated against publicly available manufacturer catalog data "
    "and deterministic engineering rules. Results are REFERENCE_ONLY — NOT engineering "
    "optimisation, cost analysis, cycle-time prediction, or production validation. "
    "Validate all configurations through production trials before manufacturing use."
)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class OperationStepRequest(BaseModel):
    """One requested operation in a process plan."""

    step_id: str
    sequence_number: int
    operation: str
    feature_id: str | None = None
    machine_id: str | None = None
    cutting_tool_id: str | None = None
    cutting_speed_m_min: float | None = None
    tool_diameter_mm: float | None = None
    predecessor_step_ids: list[str] = Field(default_factory=list)

    # Cycle-time foundation explicit job inputs (PROCESS_PLAN_CYCLE_TIME_FOUNDATION_01)
    # PATH_LENGTH_GUESSED=NO — never inferred from operation name or geometry.
    cutting_path_length_mm: float | None = None
    cutting_path_source: str | None = None   # USER_INPUT / CAM_DERIVED / NC_DERIVED / …
    rapid_distance_mm: float | None = None
    dwell_sec: float | None = None

    @field_validator("cutting_path_length_mm", mode="before")
    @classmethod
    def _validate_path_length(cls, v: object) -> object:
        if v is None:
            return v
        v = float(v)  # type: ignore[arg-type]
        if not math.isfinite(v):
            raise ValueError("cutting_path_length_mm must be finite")
        if v <= 0:
            raise ValueError("cutting_path_length_mm must be > 0")
        return v

    @field_validator("rapid_distance_mm", mode="before")
    @classmethod
    def _validate_rapid_distance(cls, v: object) -> object:
        if v is None:
            return v
        v = float(v)  # type: ignore[arg-type]
        if not math.isfinite(v):
            raise ValueError("rapid_distance_mm must be finite")
        if v <= 0:
            raise ValueError("rapid_distance_mm must be > 0")
        return v

    @field_validator("dwell_sec", mode="before")
    @classmethod
    def _validate_dwell(cls, v: object) -> object:
        if v is None:
            return v
        v = float(v)  # type: ignore[arg-type]
        if not math.isfinite(v):
            raise ValueError("dwell_sec must be finite")
        if v < 0:
            raise ValueError("dwell_sec must be >= 0")
        return v


class ProcessPlanRequest(BaseModel):
    """Input for a deterministic process plan generation."""

    part_name: str
    material_iso_group: str
    operations: list[OperationStepRequest]


# ---------------------------------------------------------------------------
# Response sub-models
# ---------------------------------------------------------------------------

class SequenceRuleWarning(BaseModel):
    rule_id: str
    reason_code: str
    explanation: str
    affected_step_ids: list[str]


class CuttingParameterRef(BaseModel):
    record_id: str
    parameter_type: str
    min_value: float
    max_value: float
    unit: str
    evidence_status: str
    source_reference: str | None


class CandidateConfigSummary(BaseModel):
    machine_id: str
    holder_id: str
    cutting_tool_id: str
    rank: int | None
    engineering_tie: bool
    compatibility_status: str


class PlanStep(BaseModel):
    step_id: str
    sequence_number: int
    operation: str
    feature_id: str | None
    planning_status: str  # PLANNED / BLOCKED / INSUFFICIENT_DATA / NOT_SUPPORTED
    setup_group: str = "UNSPECIFIED"  # SETUP_OPTIMIZATION_IMPLEMENTED=NO

    # Selection evidence
    selection_state: str | None
    candidates_evaluated: int
    compatible_count: int
    incompatible_count: int
    not_rankable_count: int

    # Top candidate configurations (tied or ranked)
    candidate_configurations: list[CandidateConfigSummary]
    engineering_tie: bool
    engineering_tie_count: int

    # Cutting parameter evidence
    cutting_parameter_references: list[CuttingParameterRef]
    cutting_parameter_reference_available: bool

    # Engineering traces from first compatible candidate
    compatibility_trace: list[dict]
    selection_criteria_trace: list[dict]

    # Dependencies
    predecessor_step_ids: list[str]

    # Sequence rule warnings applicable to this step
    sequence_warnings: list[SequenceRuleWarning]

    # Diagnostic samples (rejected / not-rankable)
    rejected_sample: list[dict]
    not_rankable_sample: list[dict]

    # Missing data items
    missing_data: list[str]
    planning_notes: str | None

    # Engineering metrics (PROCESS_PLAN_ENGINEERING_METRICS_01)
    engineering_metrics: StepEngineeringMetrics | None = None

    # Cycle-time foundation (PROCESS_PLAN_CYCLE_TIME_FOUNDATION_01)
    # CYCLE_TIME_AVAILABILITY_CHANGES_PLAN_STATUS=NO
    cycle_time: StepCycleTime | None = None


class ProcessPlanSummary(BaseModel):
    step_count: int
    planned_count: int
    blocked_count: int
    insufficient_data_count: int
    not_supported_count: int
    machine_ids_used: list[str]   # from top candidate of each PLANNED step
    holder_ids_used: list[str]
    tool_ids_used: list[str]
    engineering_tie_count: int    # PLANNED steps where all top candidates are tied
    missing_data_summary: list[str]
    sequence_rule_warning_count: int


class ProcessPlanResponse(BaseModel):
    """Complete deterministic process plan result."""

    part_name: str
    material_iso_group: str
    plan_status: str  # PLAN_COMPLETE / PLAN_PARTIAL / PLAN_BLOCKED / PLAN_INSUFFICIENT_DATA
    steps: list[PlanStep]

    dependency_graph_valid: bool
    dependency_violations: list[str]

    sequence_rules_applied: list[dict]
    alternative_valid_sequence_supported: bool
    sequence_not_uniquely_determined: bool

    summary: ProcessPlanSummary
    limitations: list[str]
    provenance: str
    disclaimer: str = _DISCLAIMER

    # Engineering metrics summary (PROCESS_PLAN_ENGINEERING_METRICS_01)
    # ENGINEERING_METRICS_SCORE_IMPLEMENTED=NO
    metrics_available_count: int = 0
    metrics_not_available_count: int = 0
    metrics_insufficient_data_count: int = 0

    # Cycle-time summary (PROCESS_PLAN_CYCLE_TIME_FOUNDATION_01)
    # PARTIAL_PLAN_TIME_PRESENTED_AS_TOTAL=NO
    cycle_time_complete_count: int = 0
    cycle_time_partial_count: int = 0
    cycle_time_insufficient_count: int = 0
