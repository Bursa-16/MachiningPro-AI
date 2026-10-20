"""Deterministic configuration-selection engine (COMPATIBILITY_SELECTION_ENGINE_01).

Builds strictly on top of the existing compatibility engine without duplicating
any compatibility logic (COMPATIBILITY_LOGIC_DUPLICATED=NO).

Selection criteria (source-backed, deterministic only — in precedence order):
  1. RPM margin %  — (machine_max_rpm - calculated_rpm) / machine_max_rpm
     Only applicable when Vc+D provided AND machine.spindle_max_rpm is not None.
     Higher margin = better spindle headroom. MISSING_LIMIT_AS_ZERO=NO:
     absent max_rpm is NOT treated as zero — the criterion is skipped (inapplicable).
  2. Cutting-parameter reference guidance available — from compatibility response.
  3. Lexicographic by (machine_id, holder_id, cutting_tool_id) — stable output
     ordering ONLY; NOT an engineering criterion.

Engineering tie: two candidates are in an engineering tie when all source-backed
engineering criteria (1 and 2) produce identical values. The lexicographic
ordering within a tie group never breaks an engineering tie.

Forbidden:
  TOOLLIFE_USED_FOR_SELECTION=NO
  ARBITRARY_SELECTION_SCORE=NO
  FORCED_WINNER_WHEN_TIED=NO
  AI_RANKING=NO
  FALSE_OPTIMIZATION_CLAIM=NO
"""

from __future__ import annotations

import logging
from itertools import product

from backend.compatibility.engine import (
    _HOLDERS,
    _MACHINES,
    _TOOLS,
)
from backend.compatibility.engine import evaluate as _compat_evaluate
from backend.compatibility.models import CompatibilityRequest
from backend.selection.models import (
    CandidateEntry,
    SelectionCriterionResult,
    SelectionRequest,
    SelectionResponse,
)

logger = logging.getLogger(__name__)

_SAMPLE_LIMIT = 5
_MAX_CANDIDATES_HARD_CAP = 200  # absolute cap on ranked candidates returned


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rpm_margin(machine_max_rpm: int | None, calculated_rpm: float | None) -> float | None:
    """Return (max - calc) / max as a float, or None if not computable."""
    if machine_max_rpm is None or calculated_rpm is None:
        return None
    if machine_max_rpm <= 0:
        return None
    return (machine_max_rpm - calculated_rpm) / machine_max_rpm


def _engineering_key(
    rpm_margin: float | None,
    reference_guidance: bool,
    rpm_applicable: bool,
) -> tuple:
    """Comparable key over source-backed engineering criteria only."""
    if rpm_applicable and rpm_margin is not None:
        return (round(rpm_margin, 6), int(reference_guidance))
    return (None, int(reference_guidance))


def _sort_key(
    rpm_margin: float | None,
    reference_guidance: bool,
    rpm_applicable: bool,
    machine_id: str,
    holder_id: str,
    tool_id: str,
) -> tuple:
    """
    Full sort key: engineering criteria (descending) then stable lexicographic.

    The tuple is built so that Python's default ascending sort naturally puts
    better candidates first:
      - RPM margin: negated so higher margin sorts first.
      - Reference guidance: negated (True=1 → -1 sorts before False=0 → 0).
      - IDs: ascending lexicographic for stable determinism.
    """
    if rpm_applicable and rpm_margin is not None:
        rpm_key: float | None = -round(rpm_margin, 6)
    else:
        rpm_key = None

    # When rpm_key is None, place those candidates after rpm-known ones, by using
    # a large sentinel. Candidates without RPM criterion are compared on the same
    # engineering level (reference guidance + lexicographic).
    rpm_sort: float = rpm_key if rpm_key is not None else float('inf')
    return (rpm_sort, -int(reference_guidance), machine_id, holder_id, tool_id)


def _ahead_reason(
    current_eng: tuple,
    next_eng: tuple,
    rpm_applicable: bool,
) -> str | None:
    """Return a human-readable reason why current_eng ranks ahead of next_eng."""
    if current_eng == next_eng:
        return None

    if rpm_applicable:
        curr_rpm, curr_ref = current_eng
        next_rpm, next_ref = next_eng
        if curr_rpm is not None and next_rpm is not None and curr_rpm > next_rpm:
            curr_pct = round(curr_rpm * 100, 1)
            next_pct = round(next_rpm * 100, 1)
            return f"Higher RPM margin: {curr_pct}% vs {next_pct}%"
        if curr_rpm is not None and next_rpm is None:
            curr_pct = round(curr_rpm * 100, 1)
            return (
                f"RPM margin known ({curr_pct}%); "
                "lower-ranked candidates have no machine RPM limit published"
            )
        if curr_ref > next_ref:
            return "Cutting-parameter reference guidance available"
    else:
        _, curr_ref = current_eng
        _, next_ref = next_eng
        if curr_ref > next_ref:
            return "Cutting-parameter reference guidance available"

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def select(req: SelectionRequest) -> SelectionResponse:
    """
    Evaluate all eligible machine/holder/tool combinations for the given
    operation and ISO material group, rank COMPATIBLE candidates deterministically,
    and return the full selection response.
    """
    operation = req.operation.lower()
    iso_group = req.iso_material_group.upper()

    # -----------------------------------------------------------------------
    # 1. Build candidate pool (pre-filter for efficiency)
    # -----------------------------------------------------------------------
    if req.machine_id is not None:
        machine_pool = {req.machine_id: _MACHINES[req.machine_id]}
    else:
        machine_pool = _MACHINES

    if req.cutting_tool_id is not None:
        tool_pool = {req.cutting_tool_id: _TOOLS[req.cutting_tool_id]}
    else:
        tool_pool = _TOOLS

    # Pre-filter: machines that support the operation
    filtered_machines = {
        mid: m for mid, m in machine_pool.items()
        if operation in [p.lower() for p in m.supported_processes]
    }

    # Pre-filter: tools that support operation AND iso group
    filtered_tools = {
        tid: t for tid, t in tool_pool.items()
        if (
            operation in [op.lower() for op in t.supported_operations]
            and iso_group in (t.iso_material_groups or [])
        )
    }

    all_holder_ids = list(_HOLDERS.keys())

    # -----------------------------------------------------------------------
    # 2. Evaluate compatibility for each triple
    # -----------------------------------------------------------------------
    compatible: list[CandidateEntry] = []
    rejected: list[CandidateEntry] = []
    not_rankable: list[CandidateEntry] = []

    vc = req.cutting_speed_m_min
    d = req.tool_diameter_mm
    rpm_applicable = (vc is not None and d is not None)

    for (mid, machine), (tid, _tool), hid in product(
        filtered_machines.items(),
        filtered_tools.items(),
        all_holder_ids,
    ):
        compat_req = CompatibilityRequest(
            machine_id=mid,
            holder_id=hid,
            cutting_tool_id=tid,
            operation=operation,
            iso_material_group=iso_group,
            cutting_speed_m_min=vc,
            tool_diameter_mm=d,
        )
        compat_resp = _compat_evaluate(compat_req)

        margin = _rpm_margin(machine.spindle_max_rpm, compat_resp.calculated_rpm)

        criteria_trace = _build_criteria_trace(
            rpm_applicable=rpm_applicable,
            rpm_margin=margin,
            machine_max_rpm=machine.spindle_max_rpm,
            calculated_rpm=compat_resp.calculated_rpm,
            reference_guidance=compat_resp.reference_guidance_available,
        )

        base = dict(
            machine_id=mid,
            holder_id=hid,
            cutting_tool_id=tid,
            compatibility_status=compat_resp.overall_status,
            compatibility_trace=compat_resp.rule_results,
            selection_criteria_trace=criteria_trace,
            rpm_margin_pct=margin,
            reference_guidance_available=compat_resp.reference_guidance_available,
            calculated_rpm=compat_resp.calculated_rpm,
        )

        if compat_resp.overall_status == "COMPATIBLE":
            compatible.append(CandidateEntry(
                candidate_status="RANKED",
                **base,
            ))
        elif compat_resp.overall_status == "INCOMPATIBLE":
            failure_rules = ", ".join(compat_resp.hard_failures) or "unspecified"
            rejected.append(CandidateEntry(
                candidate_status="REJECTED",
                rejection_reason=f"Incompatible: hard failures in [{failure_rules}]",
                **base,
            ))
        else:  # INSUFFICIENT_DATA
            unknown_rules = ", ".join(compat_resp.unknown_rules) or "unspecified"
            not_rankable.append(CandidateEntry(
                candidate_status="NOT_RANKABLE",
                not_rankable_reason=f"Insufficient data: unknown rules [{unknown_rules}]",
                **base,
            ))

    # -----------------------------------------------------------------------
    # 3. Rank COMPATIBLE candidates deterministically
    # -----------------------------------------------------------------------
    if compatible:
        compatible.sort(key=lambda c: _sort_key(
            rpm_margin=c.rpm_margin_pct,
            reference_guidance=c.reference_guidance_available,
            rpm_applicable=rpm_applicable,
            machine_id=c.machine_id,
            holder_id=c.holder_id,
            tool_id=c.cutting_tool_id,
        ))

        # Assign ranks and detect engineering ties
        eng_keys = [
            _engineering_key(c.rpm_margin_pct, c.reference_guidance_available, rpm_applicable)
            for c in compatible
        ]

        # Map each unique engineering key to a rank number
        seen_keys: list[tuple] = []
        key_to_rank: dict[tuple, int] = {}
        rank_counter = 1
        for ek in eng_keys:
            if ek not in key_to_rank:
                key_to_rank[ek] = rank_counter
                seen_keys.append(ek)
                rank_counter += 1

        # Count how many candidates share each engineering key
        key_count: dict[tuple, int] = {}
        for ek in eng_keys:
            key_count[ek] = key_count.get(ek, 0) + 1

        # Build unique sorted engineering keys list for ahead_reason computation
        unique_sorted_keys = seen_keys  # already insertion-ordered

        for i, cand in enumerate(compatible):
            ek = eng_keys[i]
            rank = key_to_rank[ek]
            is_tied = key_count[ek] > 1

            # Find the next lower engineering key (if any) for ahead_reason
            ek_idx = unique_sorted_keys.index(ek)
            ahead = None
            if ek_idx + 1 < len(unique_sorted_keys):
                next_ek = unique_sorted_keys[ek_idx + 1]
                ahead = _ahead_reason(ek, next_ek, rpm_applicable)

            tie_reason = None
            if is_tied:
                tie_reason = (
                    "No source-backed engineering criterion differentiates "
                    "these configurations. Lexicographic ordering is for "
                    "stable output only."
                )

            compatible[i] = cand.model_copy(update=dict(
                rank=rank,
                engineering_tie=is_tied,
                engineering_tie_reason=tie_reason,
                ahead_reason=ahead,
            ))

    # -----------------------------------------------------------------------
    # 4. Determine overall state
    # -----------------------------------------------------------------------
    n_compatible = len(compatible)
    n_incompatible = len(rejected)
    n_not_rankable = len(not_rankable)

    if n_compatible == 0:
        if n_incompatible == 0 and n_not_rankable == 0:
            # No candidates generated at all (pre-filter removed everything)
            overall_state = "NO_COMPATIBLE_CONFIGURATION"
        elif n_not_rankable > n_incompatible:
            # Dominant signal is missing catalog data, not hard incompatibility
            overall_state = "INSUFFICIENT_DATA_FOR_SELECTION"
        else:
            # Dominant signal is hard incompatibility
            overall_state = "NO_COMPATIBLE_CONFIGURATION"
    else:
        # Check if all compatible are in a single rank group (all tied)
        unique_ranks = {c.rank for c in compatible if c.rank is not None}
        if len(unique_ranks) <= 1:
            overall_state = "COMPATIBLE_BUT_NO_DIFFERENTIATING_EVIDENCE"
        else:
            overall_state = "SELECTION_AVAILABLE"

    # -----------------------------------------------------------------------
    # 5. Apply max_eligible_returned cap
    # -----------------------------------------------------------------------
    cap = min(req.max_eligible_returned, _MAX_CANDIDATES_HARD_CAP)
    ranked_to_return = compatible[:cap]

    return SelectionResponse(
        overall_state=overall_state,
        operation=operation,
        iso_material_group=iso_group,
        candidates_evaluated=n_compatible + n_incompatible + n_not_rankable,
        compatible_count=n_compatible,
        incompatible_count=n_incompatible,
        not_rankable_count=n_not_rankable,
        ranked_candidates=ranked_to_return,
        rejected_sample=rejected[:_SAMPLE_LIMIT],
        not_rankable_sample=not_rankable[:_SAMPLE_LIMIT],
    )


def _build_criteria_trace(
    *,
    rpm_applicable: bool,
    rpm_margin: float | None,
    machine_max_rpm: int | None,
    calculated_rpm: float | None,
    reference_guidance: bool,
) -> list[SelectionCriterionResult]:
    trace = []

    if rpm_applicable:
        if machine_max_rpm is None:
            trace.append(SelectionCriterionResult(
                criterion_id="RPM_MARGIN",
                applicable=False,
                value=None,
                note="Machine max RPM not published; MISSING_LIMIT_AS_ZERO=NO: criterion skipped.",
            ))
        elif calculated_rpm is None:
            trace.append(SelectionCriterionResult(
                criterion_id="RPM_MARGIN",
                applicable=False,
                value=None,
                note="Calculated RPM unavailable; criterion skipped.",
            ))
        else:
            pct = round(rpm_margin * 100, 2) if rpm_margin is not None else None
            trace.append(SelectionCriterionResult(
                criterion_id="RPM_MARGIN",
                applicable=True,
                value=f"{pct}%" if pct is not None else None,
                note=(
                    f"Machine max {machine_max_rpm} RPM; "
                    f"calculated {round(calculated_rpm)} RPM; "
                    f"margin {pct}%."
                ),
            ))
    else:
        trace.append(SelectionCriterionResult(
            criterion_id="RPM_MARGIN",
            applicable=False,
            value=None,
            note="Vc and diameter not provided; RPM margin criterion not applicable.",
        ))

    trace.append(SelectionCriterionResult(
        criterion_id="REFERENCE_GUIDANCE",
        applicable=True,
        value=str(reference_guidance),
        note=(
            "Cutting-parameter reference guidance available."
            if reference_guidance
            else "No cutting-parameter reference guidance for this combination."
        ),
    ))

    return trace
