"""Pydantic models for the deterministic configuration-selection API.

FALSE_AI_CLAIM=NO
FALSE_OPTIMIZATION_CLAIM=NO
FALSE_RECOMMENDATION_CLAIM=NO
FALSE_PRODUCTION_VALIDATION_CLAIM=NO
TOOLLIFE_USED_FOR_SELECTION=NO
ARBITRARY_SELECTION_SCORE=NO
FORCED_WINNER_WHEN_TIED=NO
"""

from __future__ import annotations

from pydantic import BaseModel

from backend.compatibility.models import RuleResult

_DISCLAIMER = (
    "Configuration selection is evaluated against publicly available manufacturer catalog data. "
    "Rankings reflect available catalog evidence only — NOT engineering optimisation, "
    "cost analysis, or tool-life prediction. "
    "Results are REFERENCE_ONLY and carry no production validation. "
    "Validate all configurations through production trials before manufacturing use."
)

VALID_OVERALL_STATES: frozenset[str] = frozenset({
    "SELECTION_AVAILABLE",
    "NO_COMPATIBLE_CONFIGURATION",
    "COMPATIBLE_BUT_NO_DIFFERENTIATING_EVIDENCE",
    "INSUFFICIENT_DATA_FOR_SELECTION",
})

CANDIDATE_STATUSES: frozenset[str] = frozenset({
    "RANKED",
    "REJECTED",
    "NOT_RANKABLE",
})


class SelectionCriterionResult(BaseModel):
    """Trace entry for one selection criterion evaluation."""

    criterion_id: str
    applicable: bool
    value: str | None = None
    note: str


class CandidateEntry(BaseModel):
    """Full record for one evaluated machine/holder/tool combination."""

    candidate_status: str           # RANKED | REJECTED | NOT_RANKABLE
    rank: int | None = None         # 1-based; shared across engineering ties; None if not RANKED
    engineering_tie: bool = False
    engineering_tie_reason: str | None = None
    ahead_reason: str | None = None # why this rank is ahead of the next rank group (if any)

    machine_id: str
    holder_id: str
    cutting_tool_id: str

    compatibility_status: str       # COMPATIBLE | INCOMPATIBLE | INSUFFICIENT_DATA
    compatibility_trace: list[RuleResult]

    selection_criteria_trace: list[SelectionCriterionResult]

    rejection_reason: str | None = None
    not_rankable_reason: str | None = None

    rpm_margin_pct: float | None = None
    reference_guidance_available: bool = False
    calculated_rpm: float | None = None


class SelectionRequest(BaseModel):
    """Input for a deterministic configuration-selection evaluation."""

    operation: str
    iso_material_group: str
    machine_id: str | None = None           # optional — restrict to this machine
    cutting_tool_id: str | None = None      # optional — restrict to this cutting tool
    cutting_speed_m_min: float | None = None
    tool_diameter_mm: float | None = None
    max_eligible_returned: int = 50         # cap on ranked candidates in response


class SelectionResponse(BaseModel):
    """Complete deterministic configuration-selection result."""

    overall_state: str
    operation: str
    iso_material_group: str

    candidates_evaluated: int
    compatible_count: int
    incompatible_count: int
    not_rankable_count: int

    ranked_candidates: list[CandidateEntry]
    rejected_sample: list[CandidateEntry]       # up to 5 REJECTED entries
    not_rankable_sample: list[CandidateEntry]   # up to 5 NOT_RANKABLE entries

    disclaimer: str = _DISCLAIMER
