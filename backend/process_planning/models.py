"""Process plan data models (Stage 3J).

Defines the minimal, immutable, traceable data contracts for a deterministic
process plan.

Design principles
-----------------
* Frozen dataclasses — immutable once constructed.
* IDs only for referenced entities (Feature, Tool, Machine, CuttingParameterRecord):
  avoids duplicating domain objects inside the plan and keeps the model
  lightweight.
* Engineering status is separate from human review status.
* VALIDATED requires all mandatory validations to have passed — partial
  information can never produce VALIDATED.
* All validation is performed by :mod:`backend.process_planning.validation`,
  not inside ``__post_init__``.  Models carry data; validation produces results.

Engineering status semantics
-----------------------------
VALIDATED
    Every mandatory check for this step or plan has been explicitly evaluated
    and passed.

INCOMPLETE
    No mandatory failure, but at least one required assignment or validation
    is missing.  May become VALIDATED once missing data is supplied.

INVALID
    At least one mandatory check failed (DFM, machine capability, dependency
    cycle, missing operation type, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.domain.base import (
    Provenance,
    entity_as_dict,
    optional_non_empty_str,
    require_non_empty_str,
)
from backend.domain.enums import OperationType
from backend.domain.exceptions import ValidationError

__all__ = [
    "PlanStatus",
    "ReviewStatus",
    "ProcessPlanStep",
    "ProcessPlan",
]


# ---------------------------------------------------------------------------
# Status enums
# ---------------------------------------------------------------------------

class PlanStatus(StrEnum):
    """Engineering validity status for a plan step or the whole plan.

    Semantics are strictly hierarchical:
    INVALID > INCOMPLETE > VALIDATED.
    VALIDATED requires all mandatory explicit validations to have passed.
    Partial information can never produce VALIDATED.
    """

    VALIDATED = "VALIDATED"
    INCOMPLETE = "INCOMPLETE"
    INVALID = "INVALID"


class ReviewStatus(StrEnum):
    """Human review lifecycle state.

    This is SEPARATE from engineering validity.  A plan can be VALIDATED
    (all engineering checks pass) and still be NOT_REVIEWED (no human has
    approved it).  These are independent axes.
    """

    NOT_REVIEWED = "NOT_REVIEWED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# ---------------------------------------------------------------------------
# ProcessPlanStep
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ProcessPlanStep:
    """One explicit step in a deterministic process plan.

    All assignments are explicit.  Nothing is inferred or defaulted.
    Missing required assignments leave the step in INCOMPLETE status when
    validated.

    The step carries IDs for referenced domain entities (feature, tool,
    machine, empirical records) rather than embedding the full objects.
    This keeps the model lightweight and avoids circular-dependency risks.

    Fields
    ------
    step_id : str
        Stable unique identifier within the plan.
    sequence_index : int
        Explicit ordering position (≥ 0).  Steps are sorted by this when
        building a plan.  Duplicate sequence_index values are rejected by
        the plan validator.
    feature_id : str | None
        The feature this step operates on.  Required for DFM/geometry
        validation.
    operation_type : OperationType | None
        The process family for this step.  Required for process–feature
        compatibility check (Stage 3I).
    tool_id : str | None
        Explicitly assigned tool.  Required when geometry checks apply.
    machine_id : str | None
        Explicitly assigned machine.  Required for machine capability
        validation.
    parameter_record_ids : tuple[str, ...]
        IDs of CuttingParameterRecord instances from the Stage 3G registry
        that govern this step.  May be empty when no empirical records are
        required.
    predecessor_step_ids : tuple[str, ...]
        IDs of steps that must precede this step.  Circular dependencies
        are rejected by the plan validator.
    engineering_status : PlanStatus
        Set by the caller or builder after validation.  Default is INCOMPLETE.
    review_status : ReviewStatus
        Human review state, independent of engineering validity.
    notes : str | None
        Optional free-text notes.
    """

    step_id: str
    sequence_index: int
    feature_id: str | None = None
    operation_type: OperationType | None = None
    tool_id: str | None = None
    machine_id: str | None = None
    parameter_record_ids: tuple[str, ...] = ()
    predecessor_step_ids: tuple[str, ...] = ()
    engineering_status: PlanStatus = PlanStatus.INCOMPLETE
    review_status: ReviewStatus = ReviewStatus.NOT_REVIEWED
    notes: str | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "step_id", require_non_empty_str(self.step_id, "step_id"))

        if isinstance(self.sequence_index, bool) or not isinstance(
            self.sequence_index, int
        ):
            raise ValidationError("sequence_index must be an integer")
        if self.sequence_index < 0:
            raise ValidationError(
                f"sequence_index must be >= 0, got {self.sequence_index}"
            )

        if self.feature_id is not None:
            _set(
                self,
                "feature_id",
                require_non_empty_str(self.feature_id, "feature_id"),
            )

        if self.operation_type is not None and not isinstance(
            self.operation_type, OperationType
        ):
            raise ValidationError("operation_type must be an OperationType or None")

        if self.tool_id is not None:
            _set(
                self,
                "tool_id",
                require_non_empty_str(self.tool_id, "tool_id"),
            )

        if self.machine_id is not None:
            _set(
                self,
                "machine_id",
                require_non_empty_str(self.machine_id, "machine_id"),
            )

        # Validate parameter_record_ids
        cleaned_params: list[str] = []
        for rid in self.parameter_record_ids:
            cleaned_params.append(
                require_non_empty_str(rid, "parameter_record_ids entry")
            )
        object.__setattr__(self, "parameter_record_ids", tuple(cleaned_params))

        # Validate predecessor_step_ids
        cleaned_preds: list[str] = []
        for pid in self.predecessor_step_ids:
            cleaned_preds.append(
                require_non_empty_str(pid, "predecessor_step_ids entry")
            )
        object.__setattr__(self, "predecessor_step_ids", tuple(cleaned_preds))

        if not isinstance(self.engineering_status, PlanStatus):
            raise ValidationError("engineering_status must be a PlanStatus")
        if not isinstance(self.review_status, ReviewStatus):
            raise ValidationError("review_status must be a ReviewStatus")

        _set(self, "notes", optional_non_empty_str(self.notes, "notes"))

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# ProcessPlan
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ProcessPlan:
    """An immutable, ordered, traceable deterministic process plan.

    A ProcessPlan is a container of ProcessPlanStep instances ordered by
    sequence_index.  It does not embed domain objects — steps carry IDs.

    Validation (step uniqueness, dependency graph, aggregate status) is
    performed by :mod:`backend.process_planning.validation` and the
    :class:`~backend.process_planning.builder.ProcessPlanBuilder`.

    Fields
    ------
    plan_id : str
        Stable unique identifier.
    part_id : str
        The part this plan applies to.
    steps : tuple[ProcessPlanStep, ...]
        Ordered tuple of steps (sorted by sequence_index when built).
    engineering_status : PlanStatus
        Aggregate engineering validity; set after validation.
    review_status : ReviewStatus
        Human review state.
    provenance : Provenance
        Who created this plan and how.
    notes : str | None
        Optional notes.
    """

    plan_id: str
    part_id: str
    steps: tuple[ProcessPlanStep, ...]
    engineering_status: PlanStatus
    provenance: Provenance
    review_status: ReviewStatus = ReviewStatus.NOT_REVIEWED
    notes: str | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "plan_id", require_non_empty_str(self.plan_id, "plan_id"))
        _set(self, "part_id", require_non_empty_str(self.part_id, "part_id"))

        if not isinstance(self.steps, tuple):
            raise ValidationError("steps must be a tuple of ProcessPlanStep")
        for step in self.steps:
            if not isinstance(step, ProcessPlanStep):
                raise ValidationError(
                    "each element of steps must be a ProcessPlanStep"
                )

        if not isinstance(self.engineering_status, PlanStatus):
            raise ValidationError("engineering_status must be a PlanStatus")
        if not isinstance(self.review_status, ReviewStatus):
            raise ValidationError("review_status must be a ReviewStatus")
        if not isinstance(self.provenance, Provenance):
            raise ValidationError("provenance must be a Provenance")
        _set(self, "notes", optional_non_empty_str(self.notes, "notes"))

    @property
    def ordered_steps(self) -> tuple[ProcessPlanStep, ...]:
        """Steps sorted by sequence_index (deterministic)."""
        return tuple(sorted(self.steps, key=lambda s: s.sequence_index))

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)
