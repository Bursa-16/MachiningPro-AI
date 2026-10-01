"""Machine calendar / shift / maintenance availability translation layer
(Stage 4 — PLANNING-01F).

This module answers exactly one question, deliberately separate from
machine *eligibility* (PLANNING-01D, :mod:`backend.planning.eligibility`):

    Eligibility asks: "Can this machine technically perform this
    operation?" (capability — operation type, spindle range, etc.)

    This module asks: "When can this *already-eligible* machine actually
    perform work at all?" (calendar availability — shifts, maintenance,
    the planning horizon itself)

These concerns are kept strictly separate: this module never widens or
narrows an eligible-machine set, never inspects ``Operation``/``Machine``
capability fields, and never re-derives anything
:func:`~backend.planning.eligibility.resolve_eligible_machines` already
decided. It only turns existing
:class:`~backend.planning.models.ResourceCalendar` data into a
deterministic, per-machine, horizon-clipped set of usable time windows —
first as domain :class:`~backend.planning.models.AvailabilityWindow`
instances (:func:`normalize_machine_availability`,
:func:`resolve_machine_calendars`), then, separately, as solver-relative
offsets (:func:`to_solver_availability`) for
:class:`~backend.planning.solver_models.SolverAvailabilityWindow` /
:class:`~backend.planning.solver_models.SolverProblem`.

Why ``ResourceCalendar``/``AvailabilityWindow``/``MaintenanceWindow`` are
reused, not reinvented
--------------------------------------------------------------------------
PLANNING-01C already defines these three frozen, fail-closed, timezone-
aware domain types. This module does not introduce a competing calendar
representation — it only *derives* a normalized view from them. See the
"ResourceCalendar shape note" below for the one real structural quirk this
module has to work around explicitly.

ResourceCalendar shape note (confirmed by reading the real current source,
not assumed)
--------------------------------------------------------------------------
:class:`~backend.planning.models.ResourceCalendar` is not itself tied to a
single ``machine_id`` — it only carries a ``calendar_id``. Its
``availability_windows`` are generic (no ``machine_id`` field at all), but
its ``maintenance_windows`` each carry their own ``machine_id``
(:class:`~backend.planning.models.MaintenanceWindow`). This lets one
calendar object be shared as a shift template across several machines
(the caller maps several ``machine_id`` keys to the same
``ResourceCalendar``) while still carrying machine-specific maintenance
entries when convenient. This module's policy, made explicit here rather
than left implicit:

* When resolving availability for a specific ``machine_id`` against a
  given ``ResourceCalendar``, **all** of that calendar's
  ``availability_windows`` apply (they are not machine-scoped — the
  calendar itself is what was mapped to this machine).
* Only the ``maintenance_windows`` whose own ``machine_id`` matches the
  ``machine_id`` being resolved are subtracted. A maintenance window in a
  shared calendar whose ``machine_id`` names a *different* machine is
  simply not applied here — it is not an error (the calendar may be
  legitimately shared, and that entry is presumably applied when *that*
  other machine's availability is resolved against the same calendar
  object). This module never reassigns or guesses a mismatched
  ``machine_id``.

No-calendar policy
--------------------
An eligible machine with no entry in the caller-supplied
``machine_id -> ResourceCalendar`` mapping is treated as **continuously
available for the entire ``[horizon_start, horizon_end)`` window** — not
as "unavailable" and not as an error. This is a deliberate, documented
default (see ``docs/planning/CALENDAR_CONSTRAINTS.md``), verified directly
by ``test_no_calendar_entry_is_continuously_available``.

Non-preemption policy
------------------------
This module (and the solver integration built on top of it in
:mod:`backend.planning.optimizer_adapter`) never splits an operation
across two availability windows. An operation that does not fit entirely
inside one single window on a given machine simply cannot use that
machine — see ``docs/planning/CALENDAR_CONSTRAINTS.md`` for the full
rationale. This module itself does not enforce that (it only produces
windows); the non-preemption rule is enforced where operations and
windows are actually paired, in
:func:`~backend.planning.optimizer_adapter.solve`.

Fail-closed policy
-------------------
* A naive (non-timezone-aware) ``horizon_start``/``horizon_end``, or a
  ``horizon_end`` that is not strictly after ``horizon_start``, is
  rejected via :class:`~backend.planning.exceptions.InvalidSolverProblemError`
  — the same exception type
  :func:`backend.planning.scheduler.schedule_routing` already uses for
  every other horizon-shape problem, so a horizon defect is always the
  same exception regardless of which internal function first notices it.
* A ``machine_calendars`` mapping that is not an actual ``Mapping``, that
  references a machine_id not registered in the supplied
  :class:`~backend.machines.catalog.MachineCatalog`, or whose value is not
  an actual :class:`~backend.planning.models.ResourceCalendar` instance,
  is rejected via :class:`~backend.planning.exceptions.InvalidCalendarError`
  — a calendar *data* problem, kept distinct from a horizon *shape*
  problem.
* This module never needs to re-validate a malformed
  ``AvailabilityWindow``/``MaintenanceWindow`` itself: both are frozen
  dataclasses whose own ``__post_init__`` (PLANNING-01C) already makes it
  impossible to construct an invalid instance (naive datetime, or
  ``end <= start``) in the first place. There is no redundant re-check
  here — there is nothing left to re-check.
* A machine resolving to **zero** usable windows (fully consumed by
  maintenance, or fully clipped outside the horizon) is not an error at
  this layer — it is a legitimate, representable fact about that machine
  in this horizon. Whether that makes the overall problem infeasible is
  decided later, when operations and windows are actually paired.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime

from backend.domain.base import require_non_empty_str
from backend.machines.catalog import MachineCatalog
from backend.planning.exceptions import InvalidCalendarError, InvalidSolverProblemError
from backend.planning.models import AvailabilityWindow, MaintenanceWindow, ResourceCalendar
from backend.planning.solver_models import (
    SolverAvailabilityWindow,
    timedelta_offset_to_solver_seconds,
)

__all__ = [
    "normalize_machine_availability",
    "resolve_machine_calendars",
    "to_solver_availability",
]


def _require_tz_aware(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime):
        raise InvalidSolverProblemError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise InvalidSolverProblemError(
            f"{field_name} must be timezone-aware (naive datetimes are rejected)"
        )


def _require_valid_horizon(horizon_start: datetime, horizon_end: datetime) -> None:
    _require_tz_aware(horizon_start, "horizon_start")
    _require_tz_aware(horizon_end, "horizon_end")
    if horizon_end <= horizon_start:
        raise InvalidSolverProblemError("horizon_end must be strictly after horizon_start")


def _clip_window(
    window: AvailabilityWindow, horizon_start: datetime, horizon_end: datetime
) -> AvailabilityWindow | None:
    """Clip *window* to ``[horizon_start, horizon_end)``.

    Returns ``None`` (discarded) when the clipped result would be
    zero-length or the window falls entirely outside the horizon — this is
    the "unavailable periods outside horizon are ignored/clipped" rule.
    """
    start = max(window.start, horizon_start)
    end = min(window.end, horizon_end)
    if end <= start:
        return None
    return AvailabilityWindow(start=start, end=end)


def _merge_windows(windows: tuple[AvailabilityWindow, ...]) -> tuple[AvailabilityWindow, ...]:
    """Merge overlapping and touching windows into maximal contiguous spans.

    Two windows that merely *touch* (``a.end == b.start``) are merged too:
    there is no real gap between them, so treating them as one continuous
    span is semantics-preserving, not a lossy simplification — an
    operation could never legitimately need to observe a zero-width gap.

    Reachability note: this function's one real caller
    (:func:`normalize_machine_availability`) can never actually hand it two
    *genuinely overlapping* windows — :class:`ResourceCalendar` itself
    already rejects two overlapping ``availability_windows`` entries at
    construction (PLANNING-01C), and clipping to the horizon is monotonic
    (it can only shrink or discard a window, never grow one), so it cannot
    introduce a new overlap between two already-non-overlapping windows
    either. Only the *touching* case is reachable in practice today. The
    general algorithm still handles true overlap correctly (verified
    directly against this function, not through a real ``ResourceCalendar``
    — see ``test_overlapping_availability_windows_merge``), which matters
    if a future caller ever builds windows some other way.
    """
    ordered = sorted(windows, key=lambda w: (w.start, w.end))
    merged: list[AvailabilityWindow] = []
    for window in ordered:
        if merged and window.start <= merged[-1].end:
            previous = merged[-1]
            if window.end > previous.end:
                merged[-1] = AvailabilityWindow(start=previous.start, end=window.end)
        else:
            merged.append(window)
    return tuple(merged)


def _subtract_interval(
    window: AvailabilityWindow, cut_start: datetime, cut_end: datetime
) -> tuple[AvailabilityWindow, ...]:
    """Remove ``[cut_start, cut_end)`` from *window*, returning 0, 1, or 2 pieces."""
    if cut_end <= window.start or cut_start >= window.end:
        return (window,)
    pieces: list[AvailabilityWindow] = []
    if cut_start > window.start:
        pieces.append(AvailabilityWindow(start=window.start, end=min(cut_start, window.end)))
    if cut_end < window.end:
        pieces.append(AvailabilityWindow(start=max(cut_end, window.start), end=window.end))
    return tuple(p for p in pieces if p.end > p.start)


def normalize_machine_availability(
    calendar: ResourceCalendar | None,
    machine_id: str,
    horizon_start: datetime,
    horizon_end: datetime,
) -> tuple[AvailabilityWindow, ...]:
    """Resolve one machine's usable time windows within ``[horizon_start, horizon_end)``.

    Args:
        calendar: The :class:`ResourceCalendar` mapped to *machine_id*, or
            ``None`` to apply the no-calendar policy (continuous
            availability for the whole horizon).
        machine_id: The machine this resolution is for — used only to
            select which of *calendar*'s ``maintenance_windows`` apply
            (see the module docstring's "ResourceCalendar shape note").
        horizon_start: Timezone-aware. Inclusive lower bound.
        horizon_end: Timezone-aware, strictly after *horizon_start*.
            Exclusive upper bound.

    Returns:
        A tuple of non-overlapping :class:`AvailabilityWindow`, sorted by
        ``start``, clipped to the horizon, with maintenance subtracted and
        overlapping/touching windows merged. Empty when the machine has no
        usable time at all in this horizon.

    Raises:
        InvalidSolverProblemError: naive or inverted horizon.
        InvalidCalendarError: *calendar* is neither ``None`` nor a
            ``ResourceCalendar`` instance.
    """
    _require_valid_horizon(horizon_start, horizon_end)
    require_non_empty_str(machine_id, "machine_id")

    if calendar is None:
        return (AvailabilityWindow(start=horizon_start, end=horizon_end),)

    if not isinstance(calendar, ResourceCalendar):
        raise InvalidCalendarError(
            f"calendar for machine {machine_id!r} must be a ResourceCalendar instance, "
            f"got {type(calendar).__name__}"
        )

    clipped = tuple(
        clipped_window
        for window in calendar.availability_windows
        if (clipped_window := _clip_window(window, horizon_start, horizon_end)) is not None
    )
    merged = _merge_windows(clipped)

    relevant_maintenance: list[MaintenanceWindow] = [
        window for window in calendar.maintenance_windows if window.machine_id == machine_id
    ]

    current = merged
    for maintenance in relevant_maintenance:
        cut_start = max(maintenance.start, horizon_start)
        cut_end = min(maintenance.end, horizon_end)
        if cut_end <= cut_start:
            continue  # maintenance falls entirely outside the horizon -- ignored
        current = tuple(
            piece
            for window in current
            for piece in _subtract_interval(window, cut_start, cut_end)
        )

    return tuple(sorted(current, key=lambda w: (w.start, w.end)))


def resolve_machine_calendars(
    machine_ids: Iterable[str],
    machine_calendars: Mapping[str, ResourceCalendar] | None,
    machine_catalog: MachineCatalog,
    horizon_start: datetime,
    horizon_end: datetime,
) -> dict[str, tuple[AvailabilityWindow, ...]]:
    """Resolve normalized availability for every machine in *machine_ids*.

    Args:
        machine_ids: Every machine that needs a resolved availability
            answer (typically every machine that is eligible for at least
            one operation in the current scheduling run).
        machine_calendars: Caller-supplied ``machine_id -> ResourceCalendar``
            mapping, or ``None`` to apply the no-calendar policy to every
            machine.
        machine_catalog: The existing, already-populated
            :class:`~backend.machines.catalog.MachineCatalog` — used only
            to validate that every key of *machine_calendars* names a real,
            registered machine.
        horizon_start: Timezone-aware.
        horizon_end: Timezone-aware, strictly after *horizon_start*.

    Returns:
        ``{machine_id: normalized_windows}`` for every id in *machine_ids*
        (deduplicated, order-independent input; deterministic sorted
        output keys). A machine's tuple may be empty — that is data, not
        an error (see the module docstring's fail-closed policy note).

    Raises:
        InvalidSolverProblemError: naive or inverted horizon.
        InvalidCalendarError: *machine_calendars* is not a ``Mapping``, a
            key is not a non-empty string, a key names a machine that is
            not registered in *machine_catalog*, or a value is not a
            ``ResourceCalendar`` instance.
    """
    _require_valid_horizon(horizon_start, horizon_end)
    if not isinstance(machine_catalog, MachineCatalog):
        raise InvalidCalendarError(
            "machine_catalog must be an existing backend.machines.catalog.MachineCatalog instance"
        )

    if machine_calendars is not None:
        if not isinstance(machine_calendars, Mapping):
            raise InvalidCalendarError(
                "machine_calendars must be a Mapping[machine_id, ResourceCalendar] or None"
            )
        for key, value in machine_calendars.items():
            if not isinstance(key, str) or not key.strip():
                raise InvalidCalendarError(
                    "machine_calendars keys must be non-empty machine_id strings"
                )
            if not machine_catalog.has(key):
                raise InvalidCalendarError(
                    f"machine_calendars references unknown machine {key!r}, which is "
                    "not registered in machine_catalog"
                )
            if not isinstance(value, ResourceCalendar):
                raise InvalidCalendarError(
                    f"machine_calendars[{key!r}] must be a ResourceCalendar instance, "
                    f"got {type(value).__name__}"
                )

    result: dict[str, tuple[AvailabilityWindow, ...]] = {}
    for machine_id in sorted(set(machine_ids)):
        calendar = machine_calendars.get(machine_id) if machine_calendars is not None else None
        result[machine_id] = normalize_machine_availability(
            calendar, machine_id, horizon_start, horizon_end
        )
    return result


def to_solver_availability(
    normalized: Mapping[str, tuple[AvailabilityWindow, ...]],
    horizon_start: datetime,
) -> dict[str, tuple[SolverAvailabilityWindow, ...]]:
    """Convert normalized, absolute-time availability into solver-relative offsets.

    This is the one function in this module that touches
    :mod:`backend.planning.solver_models` — it is the boundary where
    absolute ``datetime`` availability data is translated into the
    integer-second, horizon-relative shape CP-SAT needs. No ``datetime``
    crosses into the solver layer; only :class:`SolverAvailabilityWindow`
    does.

    Args:
        normalized: The result of :func:`resolve_machine_calendars`.
        horizon_start: The same timezone-aware ``horizon_start`` the
            normalization was performed against — offsets are computed
            relative to this instant.

    Returns:
        ``{machine_id: (SolverAvailabilityWindow, ...)}``, one entry per
        key of *normalized*, preserving order-independence via a fresh
        dict (the individual tuples are already sorted by
        :func:`resolve_machine_calendars`/:func:`normalize_machine_availability`).

    Raises:
        InvalidSolverProblemError: *horizon_start* is naive, or a window's
            offset is negative or not an exact whole number of seconds
            (propagated from
            :func:`~backend.planning.solver_models.timedelta_offset_to_solver_seconds`).
    """
    _require_tz_aware(horizon_start, "horizon_start")
    result: dict[str, tuple[SolverAvailabilityWindow, ...]] = {}
    for machine_id, windows in normalized.items():
        result[machine_id] = tuple(
            SolverAvailabilityWindow(
                start_offset=timedelta_offset_to_solver_seconds(
                    window.start - horizon_start, f"{machine_id!r} availability window start"
                ),
                end_offset=timedelta_offset_to_solver_seconds(
                    window.end - horizon_start, f"{machine_id!r} availability window end"
                ),
            )
            for window in windows
        )
    return result
