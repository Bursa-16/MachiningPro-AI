"""Deterministic process-plan builder (Stage 3J).

The builder accumulates explicit plan steps and, on :meth:`build`, constructs
an immutable :class:`~backend.process_planning.models.ProcessPlan` with the
aggregate engineering status determined by structural validation.

What the builder DOES
---------------------
* Accepts explicitly constructed ProcessPlanStep instances.
* Validates structural constraints (step ID uniqueness, sequence index
  uniqueness, predecessor existence, acyclic graph).
* Determines aggregate engineering status from step statuses.
* Returns an immutable ProcessPlan.

What the builder DOES NOT DO
-----------------------------
* Does not generate, suggest, or select any step content.
* Does not select tools, machines, operations, or parameters.
* Does not modify step assignments.
* Does not infer predecessors.
* Does not optimise the sequence.
"""

from __future__ import annotations

from backend.domain.base import Provenance
from backend.domain.exceptions import ValidationError
from backend.process_planning.models import (
    PlanStatus,
    ProcessPlan,
    ProcessPlanStep,
)
from backend.process_planning.validation import (
    aggregate_plan_status,
    validate_acyclic,
    validate_predecessors,
    validate_sequence_indexes,
    validate_step_ids,
)

__all__ = ["ProcessPlanBuilder"]


class ProcessPlanBuilder:
    """Accumulate explicit plan steps and build an immutable ProcessPlan.

    Usage::

        builder = ProcessPlanBuilder(plan_id="PP-001", part_id="PART-001",
                                     provenance=provenance)
        builder.add_step(step_a)
        builder.add_step(step_b)
        plan = builder.build()

    The builder is NOT reusable after :meth:`build` is called.
    """

    def __init__(
        self,
        plan_id: str,
        part_id: str,
        provenance: Provenance,
        notes: str | None = None,
    ) -> None:
        from backend.domain.base import require_non_empty_str

        self._plan_id = require_non_empty_str(plan_id, "plan_id")
        self._part_id = require_non_empty_str(part_id, "part_id")
        if not isinstance(provenance, Provenance):
            raise ValidationError("provenance must be a Provenance")
        self._provenance = provenance
        self._notes = notes
        self._steps: list[ProcessPlanStep] = []
        self._built = False

    def add_step(self, step: ProcessPlanStep) -> ProcessPlanBuilder:
        """Add an explicit step.  Returns self for optional method chaining.

        Raises:
            ValidationError: if *step* is not a ProcessPlanStep.
            RuntimeError:    if :meth:`build` has already been called.
        """
        if self._built:
            raise RuntimeError("ProcessPlanBuilder cannot be reused after build()")
        if not isinstance(step, ProcessPlanStep):
            raise ValidationError("step must be a ProcessPlanStep")
        self._steps.append(step)
        return self

    def build(self) -> ProcessPlan:
        """Build and return an immutable :class:`ProcessPlan`.

        Structural validation (R-2801–R-2804) is performed here.  If any
        structural check fails, the plan is built with INVALID status and
        the violations are preserved in the step statuses.

        Step-level engineering status is taken from each step's
        ``engineering_status`` field (set by the caller after running
        step-level validation via :mod:`backend.process_planning.validation`).

        Aggregate plan status is derived from step statuses (R-2810).

        After calling :meth:`build`, the builder is consumed and may not
        be reused.
        """
        if self._built:
            raise RuntimeError("ProcessPlanBuilder cannot be reused after build()")
        self._built = True

        steps = tuple(self._steps)

        # Structural checks — failures override step-level statuses
        structural_results = [
            validate_step_ids(steps),
            validate_sequence_indexes(steps),
            validate_predecessors(steps),
            validate_acyclic(steps),
        ]

        from backend.domain.enums import ResultStatus

        structural_failures = [
            r for r in structural_results if r.status is ResultStatus.FAIL
        ]

        if structural_failures:
            # Structural failures make the whole plan INVALID immediately
            return ProcessPlan(
                plan_id=self._plan_id,
                part_id=self._part_id,
                steps=tuple(sorted(steps, key=lambda s: s.sequence_index)),
                engineering_status=PlanStatus.INVALID,
                provenance=self._provenance,
                notes=self._notes,
            )

        # Sort by sequence_index (deterministic order)
        sorted_steps = tuple(sorted(steps, key=lambda s: s.sequence_index))

        # Aggregate from step engineering statuses (R-2810)
        plan_status, _ = aggregate_plan_status(sorted_steps)

        return ProcessPlan(
            plan_id=self._plan_id,
            part_id=self._part_id,
            steps=sorted_steps,
            engineering_status=plan_status,
            provenance=self._provenance,
            notes=self._notes,
        )

    def step_count(self) -> int:
        """Number of steps accumulated so far."""
        return len(self._steps)
