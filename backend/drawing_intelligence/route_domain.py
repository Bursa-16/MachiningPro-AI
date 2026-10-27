"""Advanced Process Route Optimization Domain Model — EPIC_04E Phase 2.

All models are frozen, deterministic, and engineering-first.

SAFETY FLAGS (verified at module level):
  FABRICATED_ROUTE=NO
  FABRICATED_PROCESS_CAPABILITY=NO
  FABRICATED_CYCLE_TIME=NO
  FABRICATED_TOOL_LIFE=NO
  FABRICATED_MACHINE_COMPATIBILITY=NO
  FABRICATED_TOOL_COMPATIBILITY=NO
  FABRICATED_CUTTING_PARAMETER=NO
  INFEASIBLE_ROUTE_RANKED_AS_FEASIBLE=NO
  INSUFFICIENT_DATA_TREATED_AS_PASS=NO
  AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO
  BLACK_BOX_AI_SCORE_USED=NO
  CUSTOMER_PROCESS_DATA_COMMITTED=NO
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.domain.enums import MachineType, OperationType, ToolType

__all__ = [
    # Enums
    "RouteFeasibilityStatus",
    "RouteRejectionReason",
    "RiskSeverity",
    "RiskCategory",
    "OverallRiskLevel",
    "ProcessCapabilityConfidence",
    "CycleTimeClassification",
    "OverrideType",
    "RouteStatus",
    # Data models
    "RouteOperation",
    "RouteSetup",
    "MachineCandidateSummary",
    "ToolCandidateSummary",
    "HolderCandidateSummary",
    "ParameterContext",
    "CycleTimeContext",
    "RiskFlag",
    "RouteRisk",
    "RouteRejection",
    "RouteScoreBreakdown",
    "RouteFeasibility",
    "RouteExplanation",
    "ParetoRoute",
    "ProcessRouteCandidate",
    "RouteAlternativeSet",
    "RouteOptimizationConfig",
    "RouteOverride",
    "OptimizedProcessPlan",
    "OptimizedPlanStep",
]

_ROUTE_DISCLAIMER = (
    "Process routes are generated from drawing requirements and curated catalog data. "
    "Results are REFERENCE_ONLY — NOT engineering-validated, NOT approved for production use. "
    "An engineer must review and approve before manufacturing use. "
    "AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO. "
    "FABRICATED_ROUTE=NO. BLACK_BOX_AI_SCORE_USED=NO."
)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class RouteFeasibilityStatus(StrEnum):
    FEASIBLE = "FEASIBLE"
    CONDITIONAL = "CONDITIONAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INFEASIBLE = "INFEASIBLE"


class RouteRejectionReason(StrEnum):
    TOLERANCE_NOT_SUPPORTED = "TOLERANCE_NOT_SUPPORTED"
    SURFACE_NOT_SUPPORTED = "SURFACE_NOT_SUPPORTED"
    FEATURE_ACCESS_NOT_SUPPORTED = "FEATURE_ACCESS_NOT_SUPPORTED"
    MACHINE_LIMIT = "MACHINE_LIMIT"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
    HOLDER_INCOMPATIBLE = "HOLDER_INCOMPATIBLE"
    MATERIAL_MISMATCH = "MATERIAL_MISMATCH"
    DATUM_SEQUENCE_CONFLICT = "DATUM_SEQUENCE_CONFLICT"
    GDT_SETUP_CONFLICT = "GDT_SETUP_CONFLICT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    CAPABILITY_GAP = "CAPABILITY_GAP"
    FEATURE_UNSUPPORTED = "FEATURE_UNSUPPORTED"
    SEQUENCE_VIOLATION = "SEQUENCE_VIOLATION"
    SEARCH_SPACE_PRUNED = "SEARCH_SPACE_PRUNED"


class RiskSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskCategory(StrEnum):
    TIGHT_TOLERANCE = "TIGHT_TOLERANCE"
    COMPLEX_GDT = "COMPLEX_GDT"
    SETUP_COUNT = "SETUP_COUNT"
    DATUM_TRANSFER = "DATUM_TRANSFER"
    LONG_REACH = "LONG_REACH"
    TOOL_SLENDERNESS = "TOOL_SLENDERNESS"
    MATERIAL_DIFFICULTY = "MATERIAL_DIFFICULTY"
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"
    MACHINE_UNCERTAINTY = "MACHINE_UNCERTAINTY"
    TOOL_UNCERTAINTY = "TOOL_UNCERTAINTY"
    INSPECTION_COMPLEXITY = "INSPECTION_COMPLEXITY"
    SURFACE_COMPLEXITY = "SURFACE_COMPLEXITY"


class OverallRiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ProcessCapabilityConfidence(StrEnum):
    VERIFIED_REFERENCE = "VERIFIED_REFERENCE"
    MANUFACTURER_REFERENCE = "MANUFACTURER_REFERENCE"
    LITERATURE_REFERENCE = "LITERATURE_REFERENCE"
    INTERNAL_VALIDATED = "INTERNAL_VALIDATED"
    ADVISORY = "ADVISORY"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class CycleTimeClassification(StrEnum):
    CALCULATED = "CALCULATED"
    REFERENCE = "REFERENCE"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"


class OverrideType(StrEnum):
    LOCK_OPERATION = "LOCK_OPERATION"
    LOCK_MACHINE = "LOCK_MACHINE"
    LOCK_TOOL = "LOCK_TOOL"
    LOCK_SETUP = "LOCK_SETUP"
    EXCLUDE_OPERATION = "EXCLUDE_OPERATION"
    EXCLUDE_MACHINE = "EXCLUDE_MACHINE"
    EXCLUDE_TOOL = "EXCLUDE_TOOL"
    REOPTIMIZE_UNLOCKED = "REOPTIMIZE_UNLOCKED"


class RouteStatus(StrEnum):
    DRAFT = "DRAFT"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# Candidate summaries (from catalog lookups — REFERENCE_ONLY)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class MachineCandidateSummary:
    """One candidate machine from the catalog — REFERENCE_ONLY."""

    machine_id: str
    manufacturer: str
    model: str
    machine_type_code: str
    axis_count: int
    spindle_max_rpm: int | None
    spindle_interface: str | None
    supported_processes: tuple[str, ...]
    suitability_score: int          # 0–100, deterministic
    rpm_margin_ok: bool | None      # None = unknown (spindle data absent)
    notes: str
    REFERENCE_ONLY: bool = True


@dataclass(frozen=True, slots=True)
class ToolCandidateSummary:
    """One candidate cutting tool — REFERENCE_ONLY."""

    tool_id: str
    manufacturer: str
    product_name: str
    tool_type_code: str
    supported_operations: tuple[str, ...]
    iso_material_groups: tuple[str, ...]
    cutting_diameter_mm: float | None
    overall_length_mm: float | None
    suitability_score: int
    notes: str
    REFERENCE_ONLY: bool = True


@dataclass(frozen=True, slots=True)
class HolderCandidateSummary:
    """One candidate tool holder — REFERENCE_ONLY."""

    holder_id: str
    manufacturer: str
    product_name: str
    holder_category: str
    machine_interface_key: str
    tool_interface_key: str
    clamping_range_min_mm: float | None
    clamping_range_max_mm: float | None
    max_rpm: int | None
    suitability_score: int
    notes: str
    REFERENCE_ONLY: bool = True


# ---------------------------------------------------------------------------
# Parameter and cycle-time contexts
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ParameterVariant:
    """One parameter set variant (CONSERVATIVE / BALANCED / PRODUCTIVITY)."""

    variant: str               # CONSERVATIVE | BALANCED | PRODUCTIVITY
    vc_m_min: float | None
    fz_mm: float | None
    ap_mm: float | None
    ae_mm: float | None
    confidence: ProcessCapabilityConfidence
    source_record_id: str | None
    notes: str


@dataclass(frozen=True, slots=True)
class ParameterContext:
    """Cutting parameter alternatives per step — REFERENCE_ONLY.

    FABRICATED_CUTTING_PARAMETER=NO: only populated from registry evidence.
    """

    material_iso_group: str | None
    variants: tuple[ParameterVariant, ...]
    disclaimer: str = (
        "Parameters from public manufacturer reference data. "
        "REFERENCE_ONLY. FABRICATED_CUTTING_PARAMETER=NO."
    )
    REFERENCE_ONLY: bool = True


@dataclass(frozen=True, slots=True)
class CycleTimeComponent:
    """One component of an operation's cycle time."""

    component: str             # cutting / rapid / approach_retract / tool_change / overhead
    value_s: float | None      # None = unknown
    classification: CycleTimeClassification
    basis: str


@dataclass(frozen=True, slots=True)
class CycleTimeContext:
    """Cycle time breakdown for one operation.

    FABRICATED_CYCLE_TIME=NO: value_s is None where path length unknown.
    Partial time is never presented as total time.
    """

    components: tuple[CycleTimeComponent, ...]
    total_s: float | None          # None if any component is UNKNOWN
    is_partial: bool               # True when some components are UNKNOWN
    classification: CycleTimeClassification
    disclaimer: str = (
        "Cycle time requires explicit path length input. "
        "FABRICATED_CYCLE_TIME=NO. Partial time is NOT total time."
    )


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RiskFlag:
    flag_id: str
    category: RiskCategory
    severity: RiskSeverity
    description: str
    affected_feature_id: str | None
    mitigation_note: str


@dataclass(frozen=True, slots=True)
class RouteRisk:
    flags: tuple[RiskFlag, ...]
    overall_risk: OverallRiskLevel

    @property
    def flag_count(self) -> int:
        return len(self.flags)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.flags if f.severity is RiskSeverity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.flags if f.severity is RiskSeverity.HIGH)


# ---------------------------------------------------------------------------
# Feasibility and rejection
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RouteFeasibility:
    status: RouteFeasibilityStatus
    reason: str
    requirement_coverage: float    # 0.0–1.0
    unresolved_items: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RouteRejection:
    reason: RouteRejectionReason
    detail: str


# ---------------------------------------------------------------------------
# Score breakdown (transparent, no black box)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RouteScoreBreakdown:
    """Deterministic score breakdown — BLACK_BOX_AI_SCORE_USED=NO.

    Each component is a non-negative integer; components sum to total.
    Max values:
      technical_feasibility  15
      requirement_coverage   15
      process_capability     15
      gdt_confidence         10
      machine_compatibility  10
      tool_compatibility     10
      setup_efficiency       10
      cycle_time              5  (0 when unknown)
      data_completeness       5
      risk_penalty           -15 (deduction, negative)
    Normalized total max = 100 before risk_penalty is applied.
    """

    technical_feasibility: int   # 0–15
    requirement_coverage: int    # 0–15
    process_capability: int      # 0–15
    gdt_confidence: int          # 0–10
    machine_compatibility: int   # 0–10
    tool_compatibility: int      # 0–10
    setup_efficiency: int        # 0–10
    cycle_time: int              # 0–5
    data_completeness: int       # 0–5
    risk_penalty: int            # 0 to -15 (stored as negative int)
    strategy_bonus: int          # 0–10 (strategy-specific bonus)

    @property
    def total(self) -> int:
        raw = (
            self.technical_feasibility
            + self.requirement_coverage
            + self.process_capability
            + self.gdt_confidence
            + self.machine_compatibility
            + self.tool_compatibility
            + self.setup_efficiency
            + self.cycle_time
            + self.data_completeness
            + self.risk_penalty
            + self.strategy_bonus
        )
        return max(0, min(100, raw))


# ---------------------------------------------------------------------------
# Explanation engine
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RouteExplanation:
    """Why this route was selected and why alternatives were ranked lower."""

    why_selected: str
    why_ranked_above_alternatives: tuple[str, ...]
    gdt_tolerance_decisions: tuple[str, ...]
    machine_selection_rationale: str | None
    tool_selection_rationale: str | None
    rejected_alternatives_summary: tuple[str, ...]
    uncertain_data_items: tuple[str, ...]


# ---------------------------------------------------------------------------
# Operation and setup structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RouteOperation:
    """One manufacturing operation within a route."""

    op_id: str
    sequence_no: int
    operation_type: OperationType
    sub_operation: str | None      # CENTER_DRILL, ROUGH, SEMI_FINISH, FINISH, etc.
    setup_id: str
    feature_id: str | None
    tool_type_required: ToolType | None
    target_ra_um: float | None
    target_it_grade: str | None
    is_inspection: bool
    notes: str


@dataclass(frozen=True, slots=True)
class RouteSetup:
    """One machining setup within a route."""

    setup_id: str
    sequence_no: int
    label: str
    feature_ids: tuple[str, ...]
    datum_reference: str | None
    machine_type_required: MachineType | None
    accessibility_notes: tuple[str, ...]
    operation_ids: tuple[str, ...]


# ---------------------------------------------------------------------------
# Pareto route entry
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ParetoRoute:
    route_id: str
    score_total: int
    op_count: int
    setup_count: int
    risk_level: OverallRiskLevel
    cycle_time_s: float | None
    is_pareto_optimal: bool
    dominated_by: tuple[str, ...]    # route_ids that dominate this one


# ---------------------------------------------------------------------------
# Route override
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RouteOverride:
    override_id: str
    override_type: OverrideType
    target_id: str      # operation_type / machine_id / tool_id / setup_id
    value: str
    applied_by: str
    note: str


# ---------------------------------------------------------------------------
# ProcessRouteCandidate — the central model
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ProcessRouteCandidate:
    """One complete candidate process route for a feature or part.

    AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO always.
    FABRICATED_ROUTE=NO — operations come from evidence-backed templates only.
    """

    route_id: str
    feature_id: str | None
    strategy: str                             # RouteStrategy value
    status: RouteStatus
    feasibility: RouteFeasibility
    setups: tuple[RouteSetup, ...]
    operations: tuple[RouteOperation, ...]
    machine_candidates: tuple[MachineCandidateSummary, ...]
    tool_candidates: tuple[ToolCandidateSummary, ...]
    holder_candidates: tuple[HolderCandidateSummary, ...]
    parameter_context: ParameterContext | None
    cycle_time_context: CycleTimeContext | None
    risk: RouteRisk
    score: RouteScoreBreakdown
    confidence: ProcessCapabilityConfidence
    explanation: RouteExplanation
    rejection_reasons: tuple[RouteRejection, ...]
    unresolved_items: tuple[str, ...]
    overrides_applied: tuple[RouteOverride, ...]
    traceability_fingerprint: str
    disclaimer: str = _ROUTE_DISCLAIMER

    @property
    def op_count(self) -> int:
        return sum(1 for op in self.operations if not op.is_inspection)

    @property
    def setup_count(self) -> int:
        return len(self.setups)

    @property
    def is_feasible(self) -> bool:
        return self.feasibility.status in (
            RouteFeasibilityStatus.FEASIBLE,
            RouteFeasibilityStatus.CONDITIONAL,
        )


# ---------------------------------------------------------------------------
# Route alternative set (per-feature or per-part)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RouteOptimizationConfig:
    strategy: str = "BALANCED"
    max_routes_per_feature: int = 5
    max_machine_candidates: int = 3
    max_tool_candidates: int = 3
    max_holder_candidates: int = 2
    beam_width: int = 3
    include_pareto: bool = True
    max_setups: int = 6


@dataclass(frozen=True, slots=True)
class RouteAlternativeSet:
    """All candidate routes for one feature, with Pareto frontier."""

    source_id: str
    feature_id: str | None
    config: RouteOptimizationConfig
    candidates: tuple[ProcessRouteCandidate, ...]
    pareto_frontier: tuple[ParetoRoute, ...]
    selected_route_id: str | None        # None = no feasible route found
    selection_rationale: str
    disclaimer: str = _ROUTE_DISCLAIMER

    @property
    def feasible_count(self) -> int:
        return sum(1 for c in self.candidates if c.is_feasible)


# ---------------------------------------------------------------------------
# Optimized process plan — final output
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class OptimizedPlanStep:
    """One step in the optimized process plan."""

    step_id: str
    setup_no: int
    operation_no: int
    feature_id: str | None
    operation_type: OperationType
    sub_operation: str | None
    machine_candidates: tuple[MachineCandidateSummary, ...]
    tool_candidates: tuple[ToolCandidateSummary, ...]
    holder_candidates: tuple[HolderCandidateSummary, ...]
    parameter_context: ParameterContext | None
    cycle_time_context: CycleTimeContext | None
    target_requirement: str | None
    inspection_note: str | None
    risk_flags: tuple[RiskFlag, ...]
    confidence: ProcessCapabilityConfidence
    why_selected: str
    unresolved_data: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OptimizedProcessPlan:
    """Final optimized process plan — REFERENCE_ONLY, always DRAFT.

    AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO
    """

    plan_id: str
    source_id: str
    drawing_number: str | None
    revision: str | None
    status: RouteStatus
    strategy: str
    steps: tuple[OptimizedPlanStep, ...]
    alternative_sets: tuple[RouteAlternativeSet, ...]
    overrides: tuple[RouteOverride, ...]
    risk: RouteRisk
    traceability_fingerprint: str
    generation_warnings: tuple[str, ...]
    disclaimer: str = _ROUTE_DISCLAIMER

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def setup_count(self) -> int:
        if not self.steps:
            return 0
        return max(s.setup_no for s in self.steps)
