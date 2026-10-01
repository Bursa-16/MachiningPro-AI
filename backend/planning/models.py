"""Planning domain models (Stage 4 — PLANNING-01C).

This module defines the immutable, engineering-consistent data contracts for
future finite-capacity production scheduling (APS). It is the foundation
laid out by the governing audit, PLANNING-01A (OptiFactory Scheduling Engine
Audit + MachiningPro Integration Design): OptiFactory's own data model solves
a different, aggregate Sales & Operations Planning problem (period-level
make/sell/store quantities) and is explicitly NOT reused here — see
``docs/planning/PLANNING_DOMAIN_MODEL.md`` for the full rationale.

Design principles
------------------
* Frozen, slotted dataclasses — immutable once constructed, matching the
  convention already used by :mod:`backend.domain` and
  :mod:`backend.process_planning`.
* Reuse existing MachiningPro engineering entities **by reference (ID)**,
  never by duplication:
    - :class:`~backend.domain.operation.Operation`
    - :class:`~backend.domain.machine.Machine`
    - :class:`~backend.process_planning.models.ProcessPlan`
    - :class:`~backend.process_planning.models.ProcessPlanStep`
  This module never redefines what an "operation" or a "machine" *is* — it
  only adds the scheduling-specific state (start/end time, machine
  assignment, calendars, setup, locking) those entities do not carry.
* Fail-closed: invalid input raises :class:`~backend.domain.exceptions.ValidationError`
  (field-level) or a :mod:`backend.planning.exceptions` error (planning-level
  invariant), never a silently-substituted default.
* Solver-neutral: this module MUST NOT import ``ortools``, ``gurobipy``, or
  ``pulp``. It describes *data*, not how it is solved.
* Language-neutral: no user-facing (Turkish or English) strings live here.
  Free-text fields (``notes``, ``reason``, ``reference``) hold operational
  identifiers/notes, not localized presentation copy — that belongs in the
  frontend i18n layer.

Timezone policy
---------------
Every stored timestamp (``Job.release_date``/``due_date``,
``AvailabilityWindow.start``/``end``, ``MaintenanceWindow.start``/``end``,
``ScheduleOperation`` timestamps, ``Schedule.horizon_start``/``horizon_end``/
``created_at``) MUST be a timezone-aware :class:`datetime.datetime`
(``tzinfo is not None``). A naive datetime is rejected with
:class:`~backend.domain.exceptions.ValidationError`. Storing and comparing in
UTC is recommended; :class:`ResourceCalendar.timezone` carries the IANA zone
name (validated against :mod:`zoneinfo`) used to *interpret* shift/calendar
semantics for display and future recurrence rules — it does not change how
the stored instants themselves are compared.

Unit / duration policy
-----------------------
Durations use :class:`datetime.timedelta` exclusively (never a bare float or
"hours" field), per the same "no ambiguous bare numbers" discipline already
enforced for engineering values by :class:`backend.domain.units.Quantity`.
Non-duration engineering quantities that already have a canonical
:class:`~backend.domain.units.Unit` reuse ``Quantity``; free-form material
quantities (which have no canonical unit registered yet, see
:class:`MaterialRequirement`) carry an explicit ``quantity_unit`` string
field rather than being silently treated as dimensionless.

Setup-matrix missing-transition policy
----------------------------------------
See :class:`SetupMatrix` — a matrix entry is looked up by an *exact*
``(from_setup_key, to_setup_key)`` match. A missing entry is never inferred
(not even a same-key "no changeover" default); it either raises
:class:`~backend.planning.exceptions.UnknownSetupTransitionError`
(``MissingTransitionPolicy.NOT_ALLOWED``, the default) or returns an
explicitly configured ``default_duration``
(``MissingTransitionPolicy.DEFAULT_FALLBACK``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.domain.base import (
    entity_as_dict,
    optional_non_empty_str,
    require_non_empty_str,
    require_positive_decimal,
    require_positive_int,
)
from backend.domain.exceptions import ValidationError
from backend.planning.exceptions import UnknownSetupTransitionError

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids a hard runtime coupling
    from backend.process_planning.models import ProcessPlan

__all__ = [
    "JobPriority",
    "MissingTransitionPolicy",
    "ScheduleOperationStatus",
    "OptimizationStatus",
    "Job",
    "WorkOrder",
    "SchedulingOperation",
    "Routing",
    "AvailabilityWindow",
    "MaintenanceWindow",
    "ResourceCalendar",
    "SetupMatrix",
    "ToolRequirement",
    "FixtureRequirement",
    "MaterialRequirement",
    "ScheduleOperation",
    "Schedule",
    "Scenario",
    "OptimizationResult",
]

_SCHEMA_VERSION = "1"


# ---------------------------------------------------------------------------
# Shared validation helpers (planning-local; mirror backend.domain.base style)
# ---------------------------------------------------------------------------

def _require_tz_aware(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValidationError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValidationError(
            f"{field_name} must be timezone-aware (naive datetimes are rejected)"
        )
    return value


def _require_tz_aware_or_none(
    value: datetime | None, field_name: str
) -> datetime | None:
    if value is None:
        return None
    return _require_tz_aware(value, field_name)


def _require_non_negative_timedelta(
    value: timedelta, field_name: str
) -> timedelta:
    if not isinstance(value, timedelta):
        raise ValidationError(f"{field_name} must be a timedelta")
    if value < timedelta(0):
        raise ValidationError(
            f"{field_name} must not be negative, got {value}"
        )
    return value


def _require_positive_timedelta(value: timedelta, field_name: str) -> timedelta:
    _require_non_negative_timedelta(value, field_name)
    if value == timedelta(0):
        raise ValidationError(f"{field_name} must be strictly positive")
    return value


def _clean_id_tuple(
    values: tuple[str, ...], field_name: str, *, reject_duplicates: bool = False
) -> tuple[str, ...]:
    cleaned: list[str] = []
    for value in values:
        cleaned.append(require_non_empty_str(value, f"{field_name} entry"))
    if reject_duplicates and len(cleaned) != len(set(cleaned)):
        raise ValidationError(f"{field_name} must not contain duplicate IDs")
    return tuple(cleaned)


def _sorted_unique_id_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    """Clean, deduplicate, and sort an ID tuple for deterministic ordering."""
    cleaned = _clean_id_tuple(values, field_name)
    return tuple(sorted(set(cleaned)))


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class JobPriority(StrEnum):
    """Deterministic, bounded job priority."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MissingTransitionPolicy(StrEnum):
    """How :meth:`SetupMatrix.lookup` behaves when no entry matches.

    NOT_ALLOWED
        (default) Raise :class:`~backend.planning.exceptions.UnknownSetupTransitionError`.
        Nothing is inferred.
    DEFAULT_FALLBACK
        Return the matrix's explicitly configured ``default_duration``. A
        matrix using this policy MUST set ``default_duration``.
    """

    NOT_ALLOWED = "not_allowed"
    DEFAULT_FALLBACK = "default_fallback"


class ScheduleOperationStatus(StrEnum):
    """Lifecycle status of one solved schedule entry.

    Distinct from :class:`backend.domain.enums.OperationStatus` (which
    describes the underlying engineering ``Operation``'s own lifecycle,
    PLANNED/COMPLETED/CANCELLED): this enum describes the *scheduling*
    lifecycle of one placement of that operation on the timeline.
    """

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OptimizationStatus(StrEnum):
    """Solver-outcome status.

    An ``OPTIMAL`` claim is never made by this data model — it is only ever
    carried through from whatever solver stage produced the
    :class:`OptimizationResult`. See that class's docstring for the
    consistency invariant this model DOES enforce.
    """

    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    TIME_LIMIT = "time_limit"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Job:
    """A production job: the demand-side unit scheduling plans against.

    No customer/commercial fields are modeled — MachiningPro's existing
    domain has no order/customer entity today (see PLANNING-01A, Phase 6),
    so none is invented here.
    """

    job_id: str
    part_id: str
    quantity: int
    priority: JobPriority = JobPriority.NORMAL
    release_date: datetime | None = None
    due_date: datetime | None = None
    notes: str | None = None
    schema_version: str = _SCHEMA_VERSION

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "job_id", require_non_empty_str(self.job_id, "job_id"))
        _set(self, "part_id", require_non_empty_str(self.part_id, "part_id"))
        _set(self, "quantity", require_positive_int(self.quantity, "quantity"))
        if not isinstance(self.priority, JobPriority):
            raise ValidationError("priority must be a JobPriority")
        _set(
            self,
            "release_date",
            _require_tz_aware_or_none(self.release_date, "release_date"),
        )
        _set(self, "due_date", _require_tz_aware_or_none(self.due_date, "due_date"))
        if (
            self.release_date is not None
            and self.due_date is not None
            and self.due_date < self.release_date
        ):
            raise ValidationError("due_date must be >= release_date")
        _set(self, "notes", optional_non_empty_str(self.notes, "notes"))

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# WorkOrder
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class WorkOrder:
    """A manufacturable execution unit for a :class:`Job`.

    References ``process_plan_id`` only — it never copies
    :class:`~backend.process_planning.models.ProcessPlan` content.
    """

    work_order_id: str
    job_id: str
    process_plan_id: str
    quantity: int
    notes: str | None = None
    schema_version: str = _SCHEMA_VERSION

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(
            self,
            "work_order_id",
            require_non_empty_str(self.work_order_id, "work_order_id"),
        )
        _set(self, "job_id", require_non_empty_str(self.job_id, "job_id"))
        _set(
            self,
            "process_plan_id",
            require_non_empty_str(self.process_plan_id, "process_plan_id"),
        )
        _set(self, "quantity", require_positive_int(self.quantity, "quantity"))
        _set(self, "notes", optional_non_empty_str(self.notes, "notes"))

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# SchedulingOperation
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SchedulingOperation:
    """Scheduling-specific state for one existing engineering operation.

    Wraps :class:`backend.domain.operation.Operation` by ``operation_id``
    reference. Does not duplicate any field ``Operation`` already carries
    (``operation_type``, ``feature_ids``, ``tool_ids``, ...) — it only adds
    what scheduling needs and CAM does not: an earliest-start bound, a
    duration estimate, scheduling-facing predecessors, and the eligible
    machine set a future scheduler may assign from.

    ``duration_estimate`` is **not calculated here** — per PLANNING-01C
    scope, deriving it from machining formulas/cutting parameters is
    deliberately deferred to a later stage. Callers must supply an explicit,
    already-derived :class:`datetime.timedelta`.
    """

    operation_id: str
    work_order_id: str
    duration_estimate: timedelta
    earliest_start: datetime | None = None
    predecessor_operation_ids: tuple[str, ...] = ()
    eligible_machine_ids: tuple[str, ...] = ()
    schema_version: str = _SCHEMA_VERSION

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(
            self,
            "operation_id",
            require_non_empty_str(self.operation_id, "operation_id"),
        )
        _set(
            self,
            "work_order_id",
            require_non_empty_str(self.work_order_id, "work_order_id"),
        )
        _set(
            self,
            "duration_estimate",
            _require_positive_timedelta(self.duration_estimate, "duration_estimate"),
        )
        _set(
            self,
            "earliest_start",
            _require_tz_aware_or_none(self.earliest_start, "earliest_start"),
        )
        preds = _clean_id_tuple(
            self.predecessor_operation_ids, "predecessor_operation_ids"
        )
        if self.operation_id in preds:
            raise ValidationError(
                f"operation {self.operation_id!r} declares itself as a predecessor"
            )
        _set(self, "predecessor_operation_ids", preds)
        _set(
            self,
            "eligible_machine_ids",
            _sorted_unique_id_tuple(self.eligible_machine_ids, "eligible_machine_ids"),
        )

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Routing:
    """A thin scheduling-facing view over an existing process plan's
    ordering and precedence.

    This is deliberately a *projection*, not a second source of truth: use
    :meth:`from_process_plan` to derive one from an existing
    :class:`~backend.process_planning.models.ProcessPlan` rather than hand-
    authoring ``ordered_operation_ids``/``precedence`` independently.
    Structural correctness (step-ID uniqueness, acyclic dependency graph) is
    validated by :mod:`backend.process_planning.validation` and is not
    re-validated here.
    """

    routing_id: str
    process_plan_id: str
    ordered_operation_ids: tuple[str, ...]
    precedence: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    schema_version: str = _SCHEMA_VERSION

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "routing_id", require_non_empty_str(self.routing_id, "routing_id"))
        _set(
            self,
            "process_plan_id",
            require_non_empty_str(self.process_plan_id, "process_plan_id"),
        )
        ordered = _clean_id_tuple(
            self.ordered_operation_ids,
            "ordered_operation_ids",
            reject_duplicates=True,
        )
        _set(self, "ordered_operation_ids", ordered)

        known_ids = set(ordered)
        cleaned_precedence: dict[str, tuple[str, ...]] = {}
        for op_id, preds in dict(self.precedence or {}).items():
            op_id = require_non_empty_str(op_id, "precedence key")
            if op_id not in known_ids:
                raise ValidationError(
                    f"precedence references unknown operation_id {op_id!r} "
                    "(not in ordered_operation_ids)"
                )
            cleaned_preds = _clean_id_tuple(tuple(preds), f"precedence[{op_id!r}]")
            for pred_id in cleaned_preds:
                if pred_id == op_id:
                    raise ValidationError(
                        f"operation {op_id!r} declares itself as a predecessor"
                    )
                if pred_id not in known_ids:
                    raise ValidationError(
                        f"operation {op_id!r} references unknown predecessor "
                        f"{pred_id!r}"
                    )
            cleaned_precedence[op_id] = cleaned_preds
        _set(self, "precedence", MappingProxyType(cleaned_precedence))

    @classmethod
    def from_process_plan(cls, plan: ProcessPlan, routing_id: str) -> Routing:
        """Derive a :class:`Routing` from an existing ``ProcessPlan``.

        Reuses ``plan.ordered_steps`` / ``step.predecessor_step_ids``
        directly — it does not re-implement or re-validate the plan's own
        acyclicity/uniqueness checks (those are
        :mod:`backend.process_planning.validation`'s responsibility).
        """
        ordered = tuple(step.step_id for step in plan.ordered_steps)
        precedence = {
            step.step_id: step.predecessor_step_ids for step in plan.steps
        }
        return cls(
            routing_id=routing_id,
            process_plan_id=plan.plan_id,
            ordered_operation_ids=ordered,
            precedence=precedence,
        )

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# AvailabilityWindow / MaintenanceWindow
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class AvailabilityWindow:
    """One contiguous interval during which a resource is available.

    Both ``start`` and ``end`` must be timezone-aware; ``end`` must be
    strictly after ``start`` (a zero-duration window is rejected).
    """

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "start", _require_tz_aware(self.start, "start"))
        _set(self, "end", _require_tz_aware(self.end, "end"))
        if self.end <= self.start:
            raise ValidationError("end must be strictly after start")

    def overlaps(self, other: AvailabilityWindow) -> bool:
        """True when this window and *other* share any instant."""
        return self.start < other.end and other.start < self.end

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


@dataclass(frozen=True, slots=True)
class MaintenanceWindow:
    """A planned-downtime interval for one specific machine.

    No scheduling logic lives here (per PLANNING-01C scope) — this is a pure
    data record; a future scheduler consumes it as a hard constraint.
    """

    machine_id: str
    start: datetime
    end: datetime
    reason: str | None = None
    reference: str | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "machine_id", require_non_empty_str(self.machine_id, "machine_id"))
        _set(self, "start", _require_tz_aware(self.start, "start"))
        _set(self, "end", _require_tz_aware(self.end, "end"))
        if self.end <= self.start:
            raise ValidationError("end must be strictly after start")
        _set(self, "reason", optional_non_empty_str(self.reason, "reason"))
        _set(self, "reference", optional_non_empty_str(self.reference, "reference"))

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# ResourceCalendar
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ResourceCalendar:
    """A resource's (typically a machine's) availability calendar.

    Deliberately minimal for PLANNING-01C: explicit
    :class:`AvailabilityWindow`/:class:`MaintenanceWindow` instances only.
    No recurrence engine (weekly shift patterns, holiday rule expansion,
    etc.) is implemented yet — those windows must already be expanded into
    explicit instants by the caller.

    Overlap policy (explicit, deterministic):

    * Two distinct ``availability_windows`` entries must not overlap or
      duplicate each other within one calendar — an "available" window
      overlapping another "available" window is ambiguous and is rejected.
    * ``maintenance_windows`` MAY overlap ``availability_windows`` (that is
      their entire purpose: carving planned downtime out of otherwise
      available time) but two ``maintenance_windows`` entries must not be
      exact duplicates of each other.

    Both window collections are stored sorted by ``start`` (then ``end``)
    for deterministic ordering, regardless of construction order.
    """

    calendar_id: str
    timezone: str
    availability_windows: tuple[AvailabilityWindow, ...] = ()
    maintenance_windows: tuple[MaintenanceWindow, ...] = ()

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "calendar_id", require_non_empty_str(self.calendar_id, "calendar_id"))

        tz_name = require_non_empty_str(self.timezone, "timezone")
        try:
            ZoneInfo(tz_name)
        except ZoneInfoNotFoundError as exc:
            raise ValidationError(f"timezone is not a known IANA zone: {tz_name!r}") from exc
        _set(self, "timezone", tz_name)

        avail = self.availability_windows
        for window in avail:
            if not isinstance(window, AvailabilityWindow):
                raise ValidationError(
                    "availability_windows entries must be AvailabilityWindow"
                )
        sorted_avail = tuple(sorted(avail, key=lambda w: (w.start, w.end)))
        for earlier, later in zip(sorted_avail, sorted_avail[1:], strict=False):
            if earlier.overlaps(later) or (
                earlier.start == later.start and earlier.end == later.end
            ):
                raise ValidationError(
                    "availability_windows must not overlap or duplicate: "
                    f"{earlier} overlaps {later}"
                )
        _set(self, "availability_windows", sorted_avail)

        maint = self.maintenance_windows
        for window in maint:
            if not isinstance(window, MaintenanceWindow):
                raise ValidationError(
                    "maintenance_windows entries must be MaintenanceWindow"
                )
        sorted_maint = tuple(sorted(maint, key=lambda w: (w.machine_id, w.start, w.end)))
        seen: set[tuple[str, datetime, datetime]] = set()
        for window in sorted_maint:
            key = (window.machine_id, window.start, window.end)
            if key in seen:
                raise ValidationError(
                    f"duplicate maintenance_windows entry for machine "
                    f"{window.machine_id!r}: {window.start} - {window.end}"
                )
            seen.add(key)
        _set(self, "maintenance_windows", sorted_maint)

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# SetupMatrix
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SetupMatrix:
    """Sequence-dependent setup/changeover duration lookup for one machine.

    See the module-level "Setup-matrix missing-transition policy" section
    for the full semantics of :meth:`lookup`.
    """

    matrix_id: str
    machine_id: str
    entries: Mapping[tuple[str, str], timedelta] = field(default_factory=dict)
    policy: MissingTransitionPolicy = MissingTransitionPolicy.NOT_ALLOWED
    default_duration: timedelta | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "matrix_id", require_non_empty_str(self.matrix_id, "matrix_id"))
        _set(self, "machine_id", require_non_empty_str(self.machine_id, "machine_id"))

        cleaned_entries: dict[tuple[str, str], timedelta] = {}
        for key, duration in dict(self.entries or {}).items():
            if (
                not isinstance(key, tuple)
                or len(key) != 2
                or not all(isinstance(part, str) for part in key)
            ):
                raise ValidationError(
                    "entries keys must be (from_setup_key, to_setup_key) string tuples"
                )
            from_key = require_non_empty_str(key[0], "entries key (from_setup_key)")
            to_key = require_non_empty_str(key[1], "entries key (to_setup_key)")
            cleaned_entries[(from_key, to_key)] = _require_non_negative_timedelta(
                duration, f"entries[{from_key!r}, {to_key!r}]"
            )
        _set(self, "entries", MappingProxyType(cleaned_entries))

        if not isinstance(self.policy, MissingTransitionPolicy):
            raise ValidationError("policy must be a MissingTransitionPolicy")

        if self.policy is MissingTransitionPolicy.DEFAULT_FALLBACK:
            if self.default_duration is None:
                raise ValidationError(
                    "default_duration is required when policy is DEFAULT_FALLBACK"
                )
            _set(
                self,
                "default_duration",
                _require_non_negative_timedelta(
                    self.default_duration, "default_duration"
                ),
            )
        elif self.default_duration is not None:
            raise ValidationError(
                "default_duration must be None when policy is NOT_ALLOWED "
                "(a configured fallback that can never be reached is a "
                "silent inconsistency)"
            )

    def lookup(self, from_setup_key: str, to_setup_key: str) -> timedelta:
        """Return the setup duration for an exact ``(from, to)`` transition.

        Deterministic exact-match lookup only — nothing is inferred for an
        unlisted transition, not even a same-key "no changeover" default.

        Raises:
            UnknownSetupTransitionError: no entry matches and ``policy`` is
                ``NOT_ALLOWED``.
        """
        from_key = require_non_empty_str(from_setup_key, "from_setup_key")
        to_key = require_non_empty_str(to_setup_key, "to_setup_key")
        key = (from_key, to_key)
        if key in self.entries:
            return self.entries[key]
        if self.policy is MissingTransitionPolicy.DEFAULT_FALLBACK:
            assert self.default_duration is not None  # enforced in __post_init__
            return self.default_duration
        raise UnknownSetupTransitionError(
            f"no setup transition configured for machine {self.machine_id!r}: "
            f"{from_key!r} -> {to_key!r}"
        )

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# ToolRequirement / FixtureRequirement
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ToolRequirement:
    """A scheduling-time tool requirement for one operation.

    References an existing tool identity by ``tool_id`` — no inventory
    logic (available quantity on hand, reservation, consumption) is
    implemented here.
    """

    operation_id: str
    tool_id: str
    quantity: int = 1
    required_from: datetime | None = None
    required_until: datetime | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(
            self,
            "operation_id",
            require_non_empty_str(self.operation_id, "operation_id"),
        )
        _set(self, "tool_id", require_non_empty_str(self.tool_id, "tool_id"))
        _set(self, "quantity", require_positive_int(self.quantity, "quantity"))
        _set(
            self,
            "required_from",
            _require_tz_aware_or_none(self.required_from, "required_from"),
        )
        _set(
            self,
            "required_until",
            _require_tz_aware_or_none(self.required_until, "required_until"),
        )
        if (
            self.required_from is not None
            and self.required_until is not None
            and self.required_until < self.required_from
        ):
            raise ValidationError("required_until must be >= required_from")

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


@dataclass(frozen=True, slots=True)
class FixtureRequirement:
    """A scheduling-time fixture requirement for one operation.

    Mirrors :class:`ToolRequirement`. MachiningPro has no fixture catalog
    today (per PLANNING-01A, Phase 6) — this references ``fixture_id`` as an
    opaque identifier; no fixture catalog is invented here.
    """

    operation_id: str
    fixture_id: str
    quantity: int = 1
    required_from: datetime | None = None
    required_until: datetime | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(
            self,
            "operation_id",
            require_non_empty_str(self.operation_id, "operation_id"),
        )
        _set(self, "fixture_id", require_non_empty_str(self.fixture_id, "fixture_id"))
        _set(self, "quantity", require_positive_int(self.quantity, "quantity"))
        _set(
            self,
            "required_from",
            _require_tz_aware_or_none(self.required_from, "required_from"),
        )
        _set(
            self,
            "required_until",
            _require_tz_aware_or_none(self.required_until, "required_until"),
        )
        if (
            self.required_from is not None
            and self.required_until is not None
            and self.required_until < self.required_from
        ):
            raise ValidationError("required_until must be >= required_from")

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# MaterialRequirement
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class MaterialRequirement:
    """A future-MRP-compatible material requirement for a work order.

    No BOM explosion and no purchasing logic is implemented here — this is
    a plain requirement record a future MRP integration (PLANNING-01H, per
    PLANNING-01A's roadmap) can consume.

    ``quantity_unit`` is an explicit free-text unit label (e.g. ``"kg"``,
    ``"pcs"``, ``"m"``) rather than :class:`backend.domain.units.Unit`,
    because that canonical unit enum does not yet register generic
    material-quantity units — leaving it implicit would be exactly the kind
    of "bare ambiguous numeric field" this module's unit policy forbids.
    """

    work_order_id: str
    material_id: str
    quantity: Decimal
    quantity_unit: str
    required_by: datetime | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(
            self,
            "work_order_id",
            require_non_empty_str(self.work_order_id, "work_order_id"),
        )
        _set(self, "material_id", require_non_empty_str(self.material_id, "material_id"))
        quantity = require_positive_decimal(self.quantity, "quantity")
        assert quantity is not None  # a bare (non-None) input is required here
        _set(self, "quantity", quantity)
        _set(
            self,
            "quantity_unit",
            require_non_empty_str(self.quantity_unit, "quantity_unit"),
        )
        _set(
            self,
            "required_by",
            _require_tz_aware_or_none(self.required_by, "required_by"),
        )

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# ScheduleOperation
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ScheduleOperation:
    """One solved placement of a :class:`SchedulingOperation` in time.

    ``setup_start``/``setup_end`` are optional and, when present, must both
    be present (never just one), with ``setup_end`` no later than
    ``start_time`` — the changeover finishes at or before the operation
    itself begins.
    """

    operation_id: str
    machine_id: str
    start_time: datetime
    end_time: datetime
    setup_start: datetime | None = None
    setup_end: datetime | None = None
    status: ScheduleOperationStatus = ScheduleOperationStatus.SCHEDULED

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(
            self,
            "operation_id",
            require_non_empty_str(self.operation_id, "operation_id"),
        )
        _set(self, "machine_id", require_non_empty_str(self.machine_id, "machine_id"))
        _set(self, "start_time", _require_tz_aware(self.start_time, "start_time"))
        _set(self, "end_time", _require_tz_aware(self.end_time, "end_time"))
        if self.end_time <= self.start_time:
            raise ValidationError("end_time must be strictly after start_time")

        if (self.setup_start is None) != (self.setup_end is None):
            raise ValidationError(
                "setup_start and setup_end must both be set or both be None"
            )
        if self.setup_start is not None:
            _set(self, "setup_start", _require_tz_aware(self.setup_start, "setup_start"))
            _set(self, "setup_end", _require_tz_aware(self.setup_end, "setup_end"))
            if self.setup_end <= self.setup_start:
                raise ValidationError("setup_end must be strictly after setup_start")
            if self.setup_end > self.start_time:
                raise ValidationError(
                    "setup_end must be at or before start_time"
                )

        if not isinstance(self.status, ScheduleOperationStatus):
            raise ValidationError("status must be a ScheduleOperationStatus")

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Schedule:
    """An immutable, solved schedule: a horizon plus its operations.

    Operations are stored sorted by ``(start_time, machine_id,
    operation_id)`` for deterministic ordering regardless of construction
    order. Carries no UI formatting — presentation (Gantt rendering, etc.)
    is entirely a frontend concern.
    """

    schedule_id: str
    horizon_start: datetime
    horizon_end: datetime
    operations: tuple[ScheduleOperation, ...]
    created_at: datetime
    solver_reference: str | None = None
    schema_version: str = _SCHEMA_VERSION

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "schedule_id", require_non_empty_str(self.schedule_id, "schedule_id"))
        _set(
            self,
            "horizon_start",
            _require_tz_aware(self.horizon_start, "horizon_start"),
        )
        _set(self, "horizon_end", _require_tz_aware(self.horizon_end, "horizon_end"))
        if self.horizon_end <= self.horizon_start:
            raise ValidationError("horizon_end must be strictly after horizon_start")
        _set(self, "created_at", _require_tz_aware(self.created_at, "created_at"))

        ops = self.operations
        for op in ops:
            if not isinstance(op, ScheduleOperation):
                raise ValidationError("operations entries must be ScheduleOperation")

        op_ids = [op.operation_id for op in ops]
        if len(op_ids) != len(set(op_ids)):
            raise ValidationError("operations must not contain duplicate operation_id")

        for op in ops:
            if op.start_time < self.horizon_start or op.end_time > self.horizon_end:
                raise ValidationError(
                    f"operation {op.operation_id!r} "
                    f"({op.start_time} - {op.end_time}) falls outside the "
                    f"schedule horizon ({self.horizon_start} - {self.horizon_end})"
                )

        sorted_ops = tuple(
            sorted(ops, key=lambda o: (o.start_time, o.machine_id, o.operation_id))
        )
        _set(self, "operations", sorted_ops)
        _set(
            self,
            "solver_reference",
            optional_non_empty_str(self.solver_reference, "solver_reference"),
        )

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------

_JSON_SAFE_PRIMITIVES = (str, int, float, bool, type(None))


@dataclass(frozen=True, slots=True)
class Scenario:
    """A named what-if configuration for future scheduling/comparison.

    ``objective_configuration`` is intentionally restricted to JSON-safe
    primitive values (``str``/``int``/``float``/``bool``/``None``) — this
    keeps the planning domain model solver-neutral by construction: a
    solver-specific object (an OR-Tools model, a Gurobi environment, ...)
    cannot be smuggled in through this field.

    Does not implement solving — this is a configuration record only.
    """

    scenario_id: str
    name: str
    job_ids: tuple[str, ...] = ()
    work_order_ids: tuple[str, ...] = ()
    calendar_ids: tuple[str, ...] = ()
    objective_configuration: Mapping[str, object] = field(default_factory=dict)
    locked_operation_ids: tuple[str, ...] = ()
    frozen_horizon_end: datetime | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "scenario_id", require_non_empty_str(self.scenario_id, "scenario_id"))
        _set(self, "name", require_non_empty_str(self.name, "name"))
        _set(
            self,
            "job_ids",
            _clean_id_tuple(self.job_ids, "job_ids", reject_duplicates=True),
        )
        _set(
            self,
            "work_order_ids",
            _clean_id_tuple(
                self.work_order_ids, "work_order_ids", reject_duplicates=True
            ),
        )
        _set(
            self,
            "calendar_ids",
            _clean_id_tuple(self.calendar_ids, "calendar_ids", reject_duplicates=True),
        )
        _set(
            self,
            "locked_operation_ids",
            _clean_id_tuple(
                self.locked_operation_ids,
                "locked_operation_ids",
                reject_duplicates=True,
            ),
        )

        cleaned_config: dict[str, object] = {}
        for key, value in dict(self.objective_configuration or {}).items():
            key = require_non_empty_str(key, "objective_configuration key")
            if not isinstance(value, _JSON_SAFE_PRIMITIVES):
                raise ValidationError(
                    f"objective_configuration[{key!r}] must be a JSON-safe "
                    "primitive (str/int/float/bool/None); the planning "
                    "domain model must remain solver-neutral"
                )
            cleaned_config[key] = value
        _set(self, "objective_configuration", MappingProxyType(cleaned_config))

        _set(
            self,
            "frozen_horizon_end",
            _require_tz_aware_or_none(self.frozen_horizon_end, "frozen_horizon_end"),
        )

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# OptimizationResult
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class OptimizationResult:
    """The outcome of a (future) solver run against a :class:`Scenario`.

    Consistency invariant (enforced here, unconditionally):

    * ``INFEASIBLE`` or ``ERROR`` results must NOT carry a ``schedule``.
    * ``OPTIMAL`` or ``FEASIBLE`` results MUST carry a ``schedule`` (a
      result cannot claim success while providing no evidence of one).
    * ``TIME_LIMIT`` may carry a best-found ``schedule`` or ``None``,
      since a time-limited solve may or may not have found a feasible
      incumbent.

    This class cannot verify that a solver's ``OPTIMAL`` claim is actually
    optimal — that responsibility belongs entirely to the (not-yet-built)
    solver stage. It only enforces the narrower, mechanically checkable
    invariant above: a result may never claim failure while silently
    carrying a schedule, nor claim success while carrying none.
    """

    result_id: str
    scenario_id: str
    status: OptimizationStatus
    solve_time: timedelta | None = None
    objective_values: Mapping[str, Decimal] = field(default_factory=dict)
    schedule: Schedule | None = None
    constraint_violations: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "result_id", require_non_empty_str(self.result_id, "result_id"))
        _set(self, "scenario_id", require_non_empty_str(self.scenario_id, "scenario_id"))
        if not isinstance(self.status, OptimizationStatus):
            raise ValidationError("status must be an OptimizationStatus")

        if self.solve_time is not None:
            _set(
                self,
                "solve_time",
                _require_non_negative_timedelta(self.solve_time, "solve_time"),
            )

        cleaned_objectives: dict[str, Decimal] = {}
        for key, value in dict(self.objective_values or {}).items():
            key = require_non_empty_str(key, "objective_values key")
            if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
                raise ValidationError(
                    f"objective_values[{key!r}] must be a number"
                )
            cleaned_objectives[key] = Decimal(str(value))
        _set(self, "objective_values", MappingProxyType(cleaned_objectives))

        if self.schedule is not None and not isinstance(self.schedule, Schedule):
            raise ValidationError("schedule must be a Schedule or None")

        if self.status in (OptimizationStatus.INFEASIBLE, OptimizationStatus.ERROR):
            if self.schedule is not None:
                raise ValidationError(
                    f"{self.status} results must not carry a schedule"
                )
        elif self.status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE):
            if self.schedule is None:
                raise ValidationError(
                    f"{self.status} results must carry a schedule"
                )

        _set(
            self,
            "constraint_violations",
            _clean_id_tuple(self.constraint_violations, "constraint_violations"),
        )
        _set(self, "diagnostics", _clean_id_tuple(self.diagnostics, "diagnostics"))

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)
