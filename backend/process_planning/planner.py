"""Deterministic machining process planning engine (PROCESS_PLANNING_ENGINE_01).

Composes:
  - Selection engine (backend.selection.engine)  — compatible configs per step
  - Cutting parameter registry                   — reference evidence per step
  - Existing dependency graph validators         — structural plan integrity

What this engine DOES NOT DO:
  - Does NOT duplicate compatibility rules (COMPATIBILITY_LOGIC_DUPLICATED=NO)
  - Does NOT duplicate selection logic (SELECTION_LOGIC_DUPLICATED=NO)
  - Does NOT predict total cycle time
    (CYCLE_TIME_FOUNDATION_IMPLEMENTED=YES — explicit cutting_path_length_mm required)
  - Does NOT calculate cost (PROCESS_COST_MODEL_IMPLEMENTED=NO)
  - Does NOT predict tool life (TOOLLIFE_USED_FOR_PROCESS_PLAN_PREDICTION=NO)
  - Does NOT force a configuration winner when configurations are tied
    (FORCED_CONFIGURATION_WINNER=NO)
  - Does NOT claim AI planning (FALSE_AI_CLAIM=NO)
  - Does NOT claim optimal sequence (FALSE_OPTIMAL_SEQUENCE_CLAIM=NO)

Sequence rules implemented (advisory warnings only — do not change planning_status):
  SEQ-R001: reaming should be preceded by drilling (in the same plan)
  SEQ-R002: tapping should be preceded by drilling (in the same plan)
"""

from __future__ import annotations

import logging
from collections import deque

from backend.compatibility.engine import (
    get_machine_rapid_traverse_mpm,
    get_machine_spindle_max_rpm,
    get_tool_number_of_flutes,
)
from backend.compatibility.models import VALID_ISO_GROUPS, VALID_OPERATIONS
from backend.cutting_parameters.models import ApplicabilityScope
from backend.cutting_parameters.registry import CuttingParameterRegistry
from backend.domain.enums import IsoMaterialGroup, OperationType
from backend.process_planning.cycle_time import compute_step_cycle_time
from backend.process_planning.metrics import EngineeringMetric, compute_step_metrics
from backend.process_planning.plan_models import (
    PLAN_BLOCKED,
    PLAN_COMPLETE,
    PLAN_INSUFFICIENT_DATA,
    PLAN_PARTIAL,
    STEP_STATUS_BLOCKED,
    STEP_STATUS_INSUFFICIENT_DATA,
    STEP_STATUS_NOT_SUPPORTED,
    STEP_STATUS_PLANNED,
    CandidateConfigSummary,
    CuttingParameterRef,
    OperationStepRequest,
    PlanStep,
    ProcessPlanRequest,
    ProcessPlanResponse,
    ProcessPlanSummary,
    SequenceRuleWarning,
)
from backend.selection.engine import select
from backend.selection.models import SelectionRequest

logger = logging.getLogger(__name__)

_PROVENANCE = (
    "MachiningPro AI — PROCESS_PLANNING_ENGINE_01 — "
    "deterministic rules applied to publicly available manufacturer catalog data. "
    "REFERENCE_ONLY — no production validation implied."
)

_SEQUENCE_RULES = [
    {
        "rule_id": "SEQ-R001",
        "reason_code": "DRILLING_BEFORE_REAMING",
        "explanation": (
            "Reaming requires a pre-drilled hole. "
            "A drilling step should precede or be declared as a predecessor of any reaming step."
        ),
    },
    {
        "rule_id": "SEQ-R002",
        "reason_code": "DRILLING_BEFORE_TAPPING",
        "explanation": (
            "Tapping requires a pre-drilled hole. "
            "A drilling step should precede or be declared as a predecessor of any tapping step."
        ),
    },
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_dependency_graph(
    steps: list[OperationStepRequest],
) -> tuple[bool, list[str]]:
    """Validate step IDs, predecessors, and acyclicity. Returns (valid, violations)."""
    violations: list[str] = []
    known_ids = {s.step_id for s in steps}

    # Duplicate step IDs
    seen: set[str] = set()
    for s in steps:
        if s.step_id in seen:
            violations.append(f"Duplicate step_id: {s.step_id!r}")
        seen.add(s.step_id)

    # Duplicate sequence numbers
    seq_seen: set[int] = set()
    for s in steps:
        if s.sequence_number in seq_seen:
            violations.append(f"Duplicate sequence_number: {s.sequence_number}")
        seq_seen.add(s.sequence_number)

    # Predecessor references
    for s in steps:
        for pred_id in s.predecessor_step_ids:
            if pred_id == s.step_id:
                violations.append(f"Step {s.step_id!r} declares itself as predecessor")
            elif pred_id not in known_ids:
                violations.append(
                    f"Step {s.step_id!r} references unknown predecessor {pred_id!r}"
                )

    # Cycle detection (Kahn's algorithm)
    in_degree = {s.step_id: 0 for s in steps}
    adjacency: dict[str, list[str]] = {s.step_id: [] for s in steps}
    for s in steps:
        for pred_id in s.predecessor_step_ids:
            if pred_id in adjacency:
                adjacency[pred_id].append(s.step_id)
                in_degree[s.step_id] += 1

    queue: deque[str] = deque(sid for sid, d in in_degree.items() if d == 0)
    processed = 0
    while queue:
        node = queue.popleft()
        processed += 1
        for successor in adjacency.get(node, []):
            in_degree[successor] -= 1
            if in_degree[successor] == 0:
                queue.append(successor)

    if processed != len(steps):
        cycle_members = sorted(sid for sid, d in in_degree.items() if d > 0)
        violations.append(f"Circular dependency detected among steps: {cycle_members}")

    return len(violations) == 0, violations


def _query_cutting_params(
    registry: CuttingParameterRegistry,
    operation: str,
    iso_group: str,
) -> list[CuttingParameterRef]:
    """Query the cutting parameter registry for reference evidence."""
    try:
        op = OperationType(operation)
        grp = IsoMaterialGroup(iso_group)
    except ValueError:
        return []

    scope = ApplicabilityScope(operation_type=op, iso_material_group=grp)
    try:
        records = registry.find(scope=scope)
    except Exception:
        return []

    refs: list[CuttingParameterRef] = []
    for r in records:
        try:
            min_v = float(r.value_range.min_value)
            max_v = float(r.value_range.max_value)
            refs.append(
                CuttingParameterRef(
                    record_id=r.record_id,
                    parameter_type=str(r.parameter_type),
                    min_value=min_v,
                    max_value=max_v,
                    unit=str(r.value_range.unit.value),
                    evidence_status=str(r.evidence_status),
                    source_reference=r.provenance.source_reference,
                )
            )
        except Exception as exc:
            logger.debug("Skipping cutting parameter record %s: %s", r.record_id, exc)
    return refs


def _map_selection_to_planning_status(
    overall_state: str,
    compatible_count: int,
    incompatible_count: int,
    not_rankable_count: int,
) -> str:
    if overall_state in ("SELECTION_AVAILABLE", "COMPATIBLE_BUT_NO_DIFFERENTIATING_EVIDENCE"):
        return STEP_STATUS_PLANNED
    if overall_state == "INSUFFICIENT_DATA_FOR_SELECTION":
        return STEP_STATUS_INSUFFICIENT_DATA
    # NO_COMPATIBLE_CONFIGURATION
    if incompatible_count > 0 and incompatible_count >= not_rankable_count:
        return STEP_STATUS_BLOCKED
    return STEP_STATUS_INSUFFICIENT_DATA


def _apply_sequence_rules(
    steps: list[OperationStepRequest],
) -> dict[str, list[SequenceRuleWarning]]:
    """Apply safe advisory sequencing rules. Returns per-step warning lists."""
    step_ops = {s.step_id: s.operation.lower() for s in steps}
    step_preds: dict[str, set[str]] = {
        s.step_id: set(s.predecessor_step_ids) for s in steps
    }

    # Build operation-to-steps mapping
    op_to_steps: dict[str, list[str]] = {}
    for s in steps:
        op = s.operation.lower()
        op_to_steps.setdefault(op, []).append(s.step_id)

    warnings: dict[str, list[SequenceRuleWarning]] = {s.step_id: [] for s in steps}

    # Helper: does any predecessor chain include a step with the given operation?
    def _has_preceding_op(step_id: str, required_op: str) -> bool:
        # BFS over predecessor chain
        visited: set[str] = set()
        queue: deque[str] = deque(step_preds.get(step_id, set()))
        while queue:
            pid = queue.popleft()
            if pid in visited:
                continue
            visited.add(pid)
            if step_ops.get(pid, "") == required_op:
                return True
            queue.extend(step_preds.get(pid, set()))

        # Also check if a prior sequence step has the required op
        # (steps with lower sequence_number are implicitly before)
        seq_map = {s.step_id: s.sequence_number for s in steps}
        this_seq = seq_map.get(step_id, 0)
        for sid, op in step_ops.items():
            if op == required_op and seq_map.get(sid, 0) < this_seq:
                return True
        return False

    # SEQ-R001: reaming should be preceded by drilling
    for sid in op_to_steps.get("reaming", []):
        if not _has_preceding_op(sid, "drilling"):
            w = SequenceRuleWarning(
                rule_id="SEQ-R001",
                reason_code="DRILLING_BEFORE_REAMING",
                explanation=(
                    "Reaming requires a pre-drilled hole. "
                    "No drilling step precedes or is declared as a predecessor of "
                    f"this reaming step ({sid!r})."
                ),
                affected_step_ids=[sid],
            )
            warnings[sid].append(w)

    # SEQ-R002: tapping should be preceded by drilling
    for sid in op_to_steps.get("tapping", []):
        if not _has_preceding_op(sid, "drilling"):
            w = SequenceRuleWarning(
                rule_id="SEQ-R002",
                reason_code="DRILLING_BEFORE_TAPPING",
                explanation=(
                    "Tapping requires a pre-drilled and tapped hole. "
                    "No drilling step precedes or is declared as a predecessor of "
                    f"this tapping step ({sid!r})."
                ),
                affected_step_ids=[sid],
            )
            warnings[sid].append(w)

    return warnings


def _feed_rate_metric_from_step_metrics(
    eng_metrics: object,
) -> EngineeringMetric | None:
    """Return the FEED_RATE_RANGE EngineeringMetric from StepEngineeringMetrics, or None."""
    if eng_metrics is None:
        return None
    for m in getattr(eng_metrics, "metrics", []):
        if getattr(m, "metric_id", None) == "FEED_RATE_RANGE":
            return m
    return None


def _alternative_sequence_supported(steps: list[OperationStepRequest]) -> bool:
    """True when 2+ steps have no declared dependency (alternative orderings exist)."""
    if len(steps) < 2:
        return False
    # Check if any pair of steps has no declared predecessor relationship
    all_preds: dict[str, set[str]] = {s.step_id: set(s.predecessor_step_ids) for s in steps}

    # Build transitive closure
    def _ancestors(sid: str) -> set[str]:
        visited: set[str] = set()
        q: deque[str] = deque(all_preds.get(sid, set()))
        while q:
            p = q.popleft()
            if p in visited:
                continue
            visited.add(p)
            q.extend(all_preds.get(p, set()))
        return visited

    independent_pairs = 0
    step_list = list(steps)
    for i in range(len(step_list)):
        for j in range(i + 1, len(step_list)):
            a = step_list[i].step_id
            b = step_list[j].step_id
            if a not in _ancestors(b) and b not in _ancestors(a):
                independent_pairs += 1
    return independent_pairs > 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_plan(
    req: ProcessPlanRequest,
    registry: CuttingParameterRegistry,
) -> ProcessPlanResponse:
    """
    Generate a deterministic process plan for the given part and operations.

    Composes the selection engine (for each operation step) and the cutting
    parameter registry (for reference evidence) without duplicating either.
    """
    iso_group = req.material_iso_group.upper()
    steps_in = req.operations

    # -------------------------------------------------------------------
    # 1. Validate dependency graph
    # -------------------------------------------------------------------
    dep_valid, dep_violations = _validate_dependency_graph(steps_in)

    # -------------------------------------------------------------------
    # 2. Apply sequencing rules (advisory warnings, computed before steps)
    # -------------------------------------------------------------------
    seq_warnings_by_step = _apply_sequence_rules(steps_in)

    # -------------------------------------------------------------------
    # 3. Process each operation step
    # -------------------------------------------------------------------
    plan_steps: list[PlanStep] = []

    for step_req in sorted(steps_in, key=lambda s: s.sequence_number):
        op = step_req.operation.lower()
        step_warnings = seq_warnings_by_step.get(step_req.step_id, [])

        # Unsupported operation
        if op not in VALID_OPERATIONS:
            plan_steps.append(
                PlanStep(
                    step_id=step_req.step_id,
                    sequence_number=step_req.sequence_number,
                    operation=step_req.operation,
                    feature_id=step_req.feature_id,
                    planning_status=STEP_STATUS_NOT_SUPPORTED,
                    setup_group="UNSPECIFIED",
                    selection_state=None,
                    candidates_evaluated=0,
                    compatible_count=0,
                    incompatible_count=0,
                    not_rankable_count=0,
                    candidate_configurations=[],
                    engineering_tie=False,
                    engineering_tie_count=0,
                    cutting_parameter_references=[],
                    cutting_parameter_reference_available=False,
                    compatibility_trace=[],
                    selection_criteria_trace=[],
                    predecessor_step_ids=step_req.predecessor_step_ids,
                    sequence_warnings=step_warnings,
                    rejected_sample=[],
                    not_rankable_sample=[],
                    missing_data=[
                        f"Operation {step_req.operation!r} is not supported "
                        "by the current catalog."
                    ],
                    planning_notes=(
                        f"Operation {step_req.operation!r} is not in the supported set: "
                        f"{sorted(VALID_OPERATIONS)}"
                    ),
                )
            )
            continue

        # Validate ISO group
        if iso_group not in VALID_ISO_GROUPS:
            plan_steps.append(
                PlanStep(
                    step_id=step_req.step_id,
                    sequence_number=step_req.sequence_number,
                    operation=step_req.operation,
                    feature_id=step_req.feature_id,
                    planning_status=STEP_STATUS_INSUFFICIENT_DATA,
                    setup_group="UNSPECIFIED",
                    selection_state=None,
                    candidates_evaluated=0,
                    compatible_count=0,
                    incompatible_count=0,
                    not_rankable_count=0,
                    candidate_configurations=[],
                    engineering_tie=False,
                    engineering_tie_count=0,
                    cutting_parameter_references=[],
                    cutting_parameter_reference_available=False,
                    compatibility_trace=[],
                    selection_criteria_trace=[],
                    predecessor_step_ids=step_req.predecessor_step_ids,
                    sequence_warnings=step_warnings,
                    rejected_sample=[],
                    not_rankable_sample=[],
                    missing_data=[f"ISO material group {iso_group!r} is not supported."],
                    planning_notes=None,
                )
            )
            continue

        # Run selection engine
        sel_req = SelectionRequest(
            operation=op,
            iso_material_group=iso_group,
            machine_id=step_req.machine_id,
            cutting_tool_id=step_req.cutting_tool_id,
            cutting_speed_m_min=step_req.cutting_speed_m_min,
            tool_diameter_mm=step_req.tool_diameter_mm,
            max_eligible_returned=50,
        )
        sel_resp = select(sel_req)

        # Determine planning status
        planning_status = _map_selection_to_planning_status(
            sel_resp.overall_state,
            sel_resp.compatible_count,
            sel_resp.incompatible_count,
            sel_resp.not_rankable_count,
        )

        # Build candidate configuration summaries (top 5 max)
        candidate_configs: list[CandidateConfigSummary] = [
            CandidateConfigSummary(
                machine_id=c.machine_id,
                holder_id=c.holder_id,
                cutting_tool_id=c.cutting_tool_id,
                rank=c.rank,
                engineering_tie=c.engineering_tie,
                compatibility_status=c.compatibility_status,
            )
            for c in sel_resp.ranked_candidates[:5]
        ]

        engineering_tie = (
            len(sel_resp.ranked_candidates) > 0
            and all(c.engineering_tie for c in sel_resp.ranked_candidates)
        )
        engineering_tie_count = sum(
            1 for c in sel_resp.ranked_candidates if c.engineering_tie
        )

        # Get compatibility/selection trace from first ranked candidate
        compat_trace: list[dict] = []
        sel_criteria_trace: list[dict] = []
        if sel_resp.ranked_candidates:
            top = sel_resp.ranked_candidates[0]
            compat_trace = [r.model_dump() for r in top.compatibility_trace]
            sel_criteria_trace = [r.model_dump() for r in top.selection_criteria_trace]

        # Query cutting parameter evidence
        cp_refs = _query_cutting_params(registry, op, iso_group)
        cp_available = len(cp_refs) > 0

        # ---------------------------------------------------------------
        # Engineering metrics
        # PROCESS_PLAN_ENGINEERING_METRICS_01
        # Gather inputs from canonical sources — no formula duplication.
        # ---------------------------------------------------------------
        # calculated_rpm / rpm_margin_frac: from top ranked candidate
        # (for BLOCKED/INSUFFICIENT_DATA steps: try any available candidate)
        _metric_rpm: float | None = None
        _metric_margin: float | None = None
        _metric_machine_max_rpm: int | None = None
        _metric_tool_id: str | None = step_req.cutting_tool_id
        _metric_flutes: int | None = None

        _any_candidate = (
            sel_resp.ranked_candidates[:1]
            or sel_resp.rejected_sample[:1]
            or sel_resp.not_rankable_sample[:1]
        )
        if _any_candidate:
            _metric_rpm = _any_candidate[0].calculated_rpm

        if sel_resp.ranked_candidates:
            _top = sel_resp.ranked_candidates[0]
            _metric_margin = _top.rpm_margin_pct  # fraction (e.g. 0.417 = 41.7%)
            # Machine spindle max RPM from catalog via compatibility engine
            _metric_machine_max_rpm = get_machine_spindle_max_rpm(_top.machine_id)
            # Tool flute count from catalog (FLUTE_COUNT_INFERRED=NO)
            _effective_tool_id = step_req.cutting_tool_id or _top.cutting_tool_id
            _metric_tool_id = _effective_tool_id
            _metric_flutes = get_tool_number_of_flutes(_effective_tool_id)

        step_eng_metrics = compute_step_metrics(
            operation=op,
            calculated_rpm=_metric_rpm,
            rpm_margin_frac=_metric_margin,
            machine_spindle_max_rpm=_metric_machine_max_rpm,
            cutting_param_refs=cp_refs,
            tool_diameter_mm=step_req.tool_diameter_mm,
            number_of_flutes=_metric_flutes,
            cutting_tool_id=_metric_tool_id,
        )

        # ---------------------------------------------------------------
        # Cycle-time foundation
        # PROCESS_PLAN_CYCLE_TIME_FOUNDATION_01
        # CYCLE_TIME_AVAILABILITY_CHANGES_PLAN_STATUS=NO
        # FEED_FORMULA_DUPLICATED=NO
        # PATH_LENGTH_GUESSED=NO
        # ---------------------------------------------------------------
        _ct_machine_id: str | None = (
            sel_resp.ranked_candidates[0].machine_id
            if sel_resp.ranked_candidates
            else step_req.machine_id
        )
        step_cycle_time = compute_step_cycle_time(
            cutting_path_length_mm=step_req.cutting_path_length_mm,
            cutting_path_source=step_req.cutting_path_source,
            feed_rate_metric=_feed_rate_metric_from_step_metrics(step_eng_metrics),
            rapid_distance_mm=step_req.rapid_distance_mm,
            machine_rapid_traverse_mpm=(
                get_machine_rapid_traverse_mpm(_ct_machine_id)
                if _ct_machine_id
                else None
            ),
            dwell_sec=step_req.dwell_sec,
        )

        # Build missing_data list
        missing_data: list[str] = []
        if planning_status == STEP_STATUS_BLOCKED:
            missing_data.append(
                f"No compatible machine/holder/tool combination found for operation "
                f"{op!r} on ISO {iso_group}. Hard compatibility failures prevent planning."
            )
        elif planning_status == STEP_STATUS_INSUFFICIENT_DATA:
            missing_data.append(
                f"Insufficient catalog data to determine compatible configurations "
                f"for operation {op!r} on ISO {iso_group}."
            )

        if not cp_available:
            missing_data.append(
                f"No cutting parameter reference guidance available for "
                f"operation {op!r} on ISO {iso_group}."
            )

        if planning_status == STEP_STATUS_PLANNED and engineering_tie:
            missing_data.append(
                "All eligible configurations are in an engineering tie — "
                "no source-backed criterion differentiates them. "
                "Enriching holder max_rpm or reference guidance data would enable differentiation."
            )

        plan_steps.append(
            PlanStep(
                step_id=step_req.step_id,
                sequence_number=step_req.sequence_number,
                operation=step_req.operation,
                feature_id=step_req.feature_id,
                planning_status=planning_status,
                setup_group="UNSPECIFIED",
                selection_state=sel_resp.overall_state,
                candidates_evaluated=sel_resp.candidates_evaluated,
                compatible_count=sel_resp.compatible_count,
                incompatible_count=sel_resp.incompatible_count,
                not_rankable_count=sel_resp.not_rankable_count,
                candidate_configurations=candidate_configs,
                engineering_tie=engineering_tie,
                engineering_tie_count=engineering_tie_count,
                cutting_parameter_references=cp_refs,
                cutting_parameter_reference_available=cp_available,
                compatibility_trace=compat_trace,
                selection_criteria_trace=sel_criteria_trace,
                predecessor_step_ids=step_req.predecessor_step_ids,
                sequence_warnings=step_warnings,
                rejected_sample=[c.model_dump() for c in sel_resp.rejected_sample],
                not_rankable_sample=[c.model_dump() for c in sel_resp.not_rankable_sample],
                missing_data=missing_data,
                planning_notes=None,
                engineering_metrics=step_eng_metrics,
                cycle_time=step_cycle_time,
            )
        )

    # -------------------------------------------------------------------
    # 4. Determine overall plan status
    # -------------------------------------------------------------------
    planned = [s for s in plan_steps if s.planning_status == STEP_STATUS_PLANNED]
    blocked = [s for s in plan_steps if s.planning_status == STEP_STATUS_BLOCKED]
    insuff = [s for s in plan_steps if s.planning_status == STEP_STATUS_INSUFFICIENT_DATA]
    not_sup = [s for s in plan_steps if s.planning_status == STEP_STATUS_NOT_SUPPORTED]

    non_planned = blocked + insuff + not_sup

    if not plan_steps:
        plan_status = PLAN_INSUFFICIENT_DATA
    elif len(planned) == len(plan_steps):
        plan_status = PLAN_COMPLETE
    elif planned and non_planned:
        plan_status = PLAN_PARTIAL
    elif not planned and blocked:
        plan_status = PLAN_BLOCKED
    else:
        plan_status = PLAN_INSUFFICIENT_DATA

    # -------------------------------------------------------------------
    # 5. Build summary
    # -------------------------------------------------------------------
    machine_ids: list[str] = []
    holder_ids: list[str] = []
    tool_ids: list[str] = []
    for s in planned:
        if s.candidate_configurations:
            top = s.candidate_configurations[0]
            if top.machine_id not in machine_ids:
                machine_ids.append(top.machine_id)
            if top.holder_id not in holder_ids:
                holder_ids.append(top.holder_id)
            if top.cutting_tool_id not in tool_ids:
                tool_ids.append(top.cutting_tool_id)

    all_missing: list[str] = []
    for s in plan_steps:
        for m in s.missing_data:
            if m not in all_missing:
                all_missing.append(m)

    seq_warning_count = sum(len(s.sequence_warnings) for s in plan_steps)
    tie_count = sum(1 for s in planned if s.engineering_tie)

    summary = ProcessPlanSummary(
        step_count=len(plan_steps),
        planned_count=len(planned),
        blocked_count=len(blocked),
        insufficient_data_count=len(insuff),
        not_supported_count=len(not_sup),
        machine_ids_used=machine_ids,
        holder_ids_used=holder_ids,
        tool_ids_used=tool_ids,
        engineering_tie_count=tie_count,
        missing_data_summary=all_missing,
        sequence_rule_warning_count=seq_warning_count,
    )

    # -------------------------------------------------------------------
    # 6. Build limitations list
    # -------------------------------------------------------------------
    limitations: list[str] = [
        (
            "CYCLE_TIME_FOUNDATION_IMPLEMENTED=YES (CUTTING_PLUS_EXPLICIT_NONCUTTING scope) — "
            "explicit cutting_path_length_mm required; path is never inferred from geometry."
        ),
        (
            "PROCESS_COST_MODEL_IMPLEMENTED=NO — cost models require validated cost "
            "inputs not available in this engine."
        ),
        (
            "TOOLLIFE_USED_FOR_PROCESS_PLAN_PREDICTION=NO — tool-life prediction "
            "is not used in process planning."
        ),
        (
            "SETUP_OPTIMIZATION_IMPLEMENTED=NO — setup grouping requires workholding "
            "and orientation data not available."
        ),
    ]
    if tie_count > 0:
        limitations.append(
            f"{tie_count} PLANNED step(s) have engineering ties — "
            "no source-backed criterion differentiates configurations. "
            "Holder max_rpm data or cutting-parameter reference guidance "
            "would enable differentiation."
        )
    if dep_violations:
        limitations.append(f"Dependency graph violations: {len(dep_violations)} issue(s).")

    # Material library enrichment (additive — backward compatible)
    if req.material_id:
        try:
            from backend.materials.catalog import get_catalog as _get_mat_catalog
            mat_record = _get_mat_catalog().get(req.material_id)
            if mat_record is not None and mat_record.machinability is not None:
                mac = mat_record.machinability
                advisory_parts = [f"Material library: {mat_record.designation} (ISO {mat_record.iso_group})"]
                if mac.work_hardening and mac.work_hardening not in ("LOW", "UNKNOWN"):
                    advisory_parts.append(f"work_hardening={mac.work_hardening}")
                if mac.thermal_load and mac.thermal_load not in ("LOW", "UNKNOWN"):
                    advisory_parts.append(f"thermal_load={mac.thermal_load}")
                if mac.coolant_guidance:
                    advisory_parts.append(f"coolant: {mac.coolant_guidance}")
                limitations.append(" — ".join(advisory_parts) + " (REFERENCE_ONLY)")
        except Exception:
            pass  # Material enrichment is additive; never fail the plan on lookup error

    # -------------------------------------------------------------------
    # 7. Alternative sequence support
    # -------------------------------------------------------------------
    alt_seq = _alternative_sequence_supported(steps_in)

    # -------------------------------------------------------------------
    # 8. Aggregate engineering metrics counts across all steps
    # -------------------------------------------------------------------
    total_metrics_available = sum(
        s.engineering_metrics.metrics_available_count
        for s in plan_steps
        if s.engineering_metrics is not None
    )
    total_metrics_not_available = sum(
        s.engineering_metrics.metrics_not_available_count
        for s in plan_steps
        if s.engineering_metrics is not None
    )
    total_metrics_insufficient = sum(
        s.engineering_metrics.metrics_insufficient_data_count
        for s in plan_steps
        if s.engineering_metrics is not None
    )

    # -------------------------------------------------------------------
    # 9. Aggregate cycle-time counts across all steps
    # PARTIAL_PLAN_TIME_PRESENTED_AS_TOTAL=NO
    # -------------------------------------------------------------------
    ct_complete = sum(
        1 for s in plan_steps
        if s.cycle_time is not None and s.cycle_time.status == "COMPLETE"
    )
    ct_partial = sum(
        1 for s in plan_steps
        if s.cycle_time is not None and s.cycle_time.status == "PARTIAL"
    )
    ct_insufficient = sum(
        1 for s in plan_steps
        if s.cycle_time is not None and s.cycle_time.status == "INSUFFICIENT_DATA"
    )

    return ProcessPlanResponse(
        part_name=req.part_name,
        material_iso_group=iso_group,
        plan_status=plan_status,
        steps=plan_steps,
        dependency_graph_valid=dep_valid,
        dependency_violations=dep_violations,
        sequence_rules_applied=_SEQUENCE_RULES,
        alternative_valid_sequence_supported=alt_seq,
        sequence_not_uniquely_determined=alt_seq,
        summary=summary,
        limitations=limitations,
        provenance=_PROVENANCE,
        metrics_available_count=total_metrics_available,
        metrics_not_available_count=total_metrics_not_available,
        metrics_insufficient_data_count=total_metrics_insufficient,
        cycle_time_complete_count=ct_complete,
        cycle_time_partial_count=ct_partial,
        cycle_time_insufficient_count=ct_insufficient,
    )
