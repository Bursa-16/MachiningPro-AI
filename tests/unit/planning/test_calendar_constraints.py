"""Tests for the PLANNING-01F calendar/shift/maintenance translation layer
(:mod:`backend.planning.calendar_constraints`)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.domain.base import Provenance
from backend.domain.enums import MachineType, OperationType, ProvenanceType
from backend.domain.machine import Machine
from backend.domain.units import Quantity, Unit
from backend.machines.catalog import MachineCatalog
from backend.planning.calendar_constraints import (
    _merge_windows,
    normalize_machine_availability,
    resolve_machine_calendars,
    to_solver_availability,
)
from backend.planning.exceptions import InvalidCalendarError, InvalidSolverProblemError
from backend.planning.models import AvailabilityWindow, MaintenanceWindow, ResourceCalendar
from backend.planning.solver_models import SolverAvailabilityWindow

HORIZON_START = datetime(2026, 9, 28, 8, 0, 0, tzinfo=UTC)
HORIZON_END = datetime(2026, 9, 29, 8, 0, 0, tzinfo=UTC)

_PROV = Provenance(source_type=ProvenanceType.USER_INPUT)


def _rpm(value):
    return Quantity.of(value, Unit.RPM)


def _kw(value):
    return Quantity.of(value, Unit.KW)


def _machine(machine_id):
    return Machine(
        machine_id=machine_id,
        name=machine_id,
        machine_type=MachineType.MILL,
        axis_count=3,
        spindle_speed_min=_rpm(100),
        spindle_speed_max=_rpm(10000),
        spindle_power=_kw(10),
        provenance=_PROV,
        supported_operations=(OperationType.MILLING,),
    )


def _t(hour, minute=0, day=28):
    return datetime(2026, 9, day, hour, minute, 0, tzinfo=UTC)


def _window(start_hour, end_hour, start_min=0, end_min=0):
    return AvailabilityWindow(start=_t(start_hour, start_min), end=_t(end_hour, end_min))


# ---------------------------------------------------------------------------
# 13. no calendar -> explicit continuous-availability policy
# ---------------------------------------------------------------------------


def test_no_calendar_entry_is_continuously_available():
    result = normalize_machine_availability(None, "M1", HORIZON_START, HORIZON_END)
    assert result == (AvailabilityWindow(start=HORIZON_START, end=HORIZON_END),)


# ---------------------------------------------------------------------------
# 7. maintenance subtracts from availability
# ---------------------------------------------------------------------------


def test_maintenance_subtracts_from_availability():
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(_window(8, 17),),
        maintenance_windows=(MaintenanceWindow(machine_id="M1", start=_t(12), end=_t(13, 30)),),
    )
    result = normalize_machine_availability(calendar, "M1", HORIZON_START, HORIZON_END)
    assert result == (
        AvailabilityWindow(start=_t(8), end=_t(12)),
        AvailabilityWindow(start=_t(13, 30), end=_t(17)),
    )


def test_maintenance_for_a_different_machine_in_a_shared_calendar_is_not_applied():
    # A shared calendar's maintenance_windows are scoped by their own
    # machine_id (see the module docstring's "ResourceCalendar shape note")
    # -- a maintenance entry for M2 must not affect M1's resolution even
    # though both machines are mapped to the same calendar object.
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(_window(8, 17),),
        maintenance_windows=(MaintenanceWindow(machine_id="M2", start=_t(12), end=_t(13)),),
    )
    result = normalize_machine_availability(calendar, "M1", HORIZON_START, HORIZON_END)
    assert result == (AvailabilityWindow(start=_t(8), end=_t(17)),)


# ---------------------------------------------------------------------------
# 9. overlapping availability windows normalize correctly
# ---------------------------------------------------------------------------


def test_overlapping_availability_windows_merge():
    # Real-world reachability note (discovered while writing this test, not
    # assumed beforehand): ResourceCalendar.__post_init__ already rejects
    # two *availability* windows that overlap each other (PLANNING-01C) --
    # so it is impossible to construct a real ResourceCalendar that would
    # ever hand normalize_machine_availability() two genuinely overlapping
    # availability windows in the first place, and clipping to the horizon
    # is monotonic (it can only shrink or discard a window, never grow one),
    # so it cannot introduce a new overlap between two already-non-
    # overlapping windows either. The "overlap" branch of the general
    # merge algorithm is therefore unreachable through the one real caller
    # today -- exercised here directly against the private merge helper
    # instead (the same pattern PLANNING-01E's own test suite already uses
    # for _build_solver_problem, for the same reason: there is no other way
    # to observe this general-purpose internal behavior).
    windows = (_window(8, 14), _window(12, 17))
    assert _merge_windows(windows) == (AvailabilityWindow(start=_t(8), end=_t(17)),)


def test_overlapping_windows_cannot_reach_normalize_via_a_real_calendar():
    from backend.domain.exceptions import ValidationError

    with pytest.raises(ValidationError):
        ResourceCalendar(
            calendar_id="C1",
            timezone="UTC",
            availability_windows=(_window(8, 14), _window(12, 17)),
        )


# ---------------------------------------------------------------------------
# 10. adjacent (touching) availability windows deterministic policy
# ---------------------------------------------------------------------------


def test_adjacent_touching_windows_merge_into_one():
    # ResourceCalendar itself rejects two *available* windows that overlap
    # or duplicate, but touching (end == next start) is neither -- it is
    # legitimately two calendar entries describing one continuous span.
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(_window(8, 12), _window(12, 17)),
    )
    result = normalize_machine_availability(calendar, "M1", HORIZON_START, HORIZON_END)
    assert result == (AvailabilityWindow(start=_t(8), end=_t(17)),)


def test_non_touching_windows_stay_separate():
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(_window(8, 12), _window(13, 17)),
    )
    result = normalize_machine_availability(calendar, "M1", HORIZON_START, HORIZON_END)
    assert result == (
        AvailabilityWindow(start=_t(8), end=_t(12)),
        AvailabilityWindow(start=_t(13), end=_t(17)),
    )


# ---------------------------------------------------------------------------
# 11. maintenance outside horizon ignored/clipped correctly
# ---------------------------------------------------------------------------


def test_maintenance_outside_horizon_is_ignored():
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(_window(8, 17),),
        maintenance_windows=(
            MaintenanceWindow(
                machine_id="M1",
                start=datetime(2026, 9, 30, 8, 0, tzinfo=UTC),  # entirely after horizon_end
                end=datetime(2026, 9, 30, 9, 0, tzinfo=UTC),
            ),
        ),
    )
    result = normalize_machine_availability(calendar, "M1", HORIZON_START, HORIZON_END)
    assert result == (AvailabilityWindow(start=_t(8), end=_t(17)),)


def test_maintenance_straddling_horizon_boundary_is_clipped():
    # Maintenance starts before horizon_start and ends inside it -- only
    # the in-horizon portion should be subtracted.
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(_window(8, 17),),
        maintenance_windows=(
            MaintenanceWindow(
                machine_id="M1",
                start=datetime(2026, 9, 28, 6, 0, tzinfo=UTC),  # before horizon_start
                end=_t(9),
            ),
        ),
    )
    result = normalize_machine_availability(calendar, "M1", HORIZON_START, HORIZON_END)
    assert result == (AvailabilityWindow(start=_t(9), end=_t(17)),)


# ---------------------------------------------------------------------------
# 12. availability partially outside horizon clipped correctly
# ---------------------------------------------------------------------------


def test_availability_partially_outside_horizon_is_clipped():
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(
            AvailabilityWindow(start=datetime(2026, 9, 28, 6, 0, tzinfo=UTC), end=_t(10)),
        ),
    )
    result = normalize_machine_availability(calendar, "M1", HORIZON_START, HORIZON_END)
    assert result == (AvailabilityWindow(start=HORIZON_START, end=_t(10)),)


def test_availability_entirely_outside_horizon_is_discarded():
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(
            AvailabilityWindow(
                start=datetime(2026, 9, 30, 8, 0, tzinfo=UTC),
                end=datetime(2026, 9, 30, 17, 0, tzinfo=UTC),
            ),
        ),
    )
    result = normalize_machine_availability(calendar, "M1", HORIZON_START, HORIZON_END)
    assert result == ()


def test_zero_length_clipped_window_is_discarded():
    # Window ends exactly at horizon_start -- clips to zero length.
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(
            AvailabilityWindow(
                start=datetime(2026, 9, 28, 6, 0, tzinfo=UTC), end=HORIZON_START
            ),
        ),
    )
    result = normalize_machine_availability(calendar, "M1", HORIZON_START, HORIZON_END)
    assert result == ()


# ---------------------------------------------------------------------------
# PLANNING-01F REVIEW FIX R1 -- named regression test for the exact
# two-touching-maintenance-windows boundary case worked through by hand
# during the independent review (not previously a named test: only a
# single-maintenance-window case was covered by
# test_maintenance_subtracts_from_availability).
# ---------------------------------------------------------------------------


def test_two_touching_maintenance_windows_subtract_as_one_combined_gap():
    # availability: 08:00-12:00 + 12:00-16:00 (touching -> merges to 08:00-16:00)
    # maintenance:  10:00-11:00 + 11:00-12:00 (touching -> together remove 10:00-12:00)
    # expected normalized result: 08:00-10:00 + 12:00-16:00
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(_window(8, 12), _window(12, 16)),
        maintenance_windows=(
            MaintenanceWindow(machine_id="M1", start=_t(10), end=_t(11)),
            MaintenanceWindow(machine_id="M1", start=_t(11), end=_t(12)),
        ),
    )
    result = normalize_machine_availability(calendar, "M1", HORIZON_START, HORIZON_END)
    assert result == (
        AvailabilityWindow(start=_t(8), end=_t(10)),
        AvailabilityWindow(start=_t(12), end=_t(16)),
    )


def test_two_touching_maintenance_windows_order_independent():
    # Same as above but with the two maintenance windows supplied in the
    # reverse order -- sequential subtraction must be order-independent.
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(_window(8, 12), _window(12, 16)),
        maintenance_windows=(
            MaintenanceWindow(machine_id="M1", start=_t(11), end=_t(12)),
            MaintenanceWindow(machine_id="M1", start=_t(10), end=_t(11)),
        ),
    )
    result = normalize_machine_availability(calendar, "M1", HORIZON_START, HORIZON_END)
    assert result == (
        AvailabilityWindow(start=_t(8), end=_t(10)),
        AvailabilityWindow(start=_t(12), end=_t(16)),
    )


# ---------------------------------------------------------------------------
# 14. unknown machine calendar -> fail closed
# ---------------------------------------------------------------------------


def test_unknown_machine_in_calendar_mapping_fails_closed():
    catalog = MachineCatalog()
    catalog.register(_machine("M1"))
    calendar = ResourceCalendar(calendar_id="C1", timezone="UTC")
    with pytest.raises(InvalidCalendarError):
        resolve_machine_calendars(
            ["M1"], {"GHOST_MACHINE": calendar}, catalog, HORIZON_START, HORIZON_END
        )


def test_non_resource_calendar_value_fails_closed():
    catalog = MachineCatalog()
    catalog.register(_machine("M1"))
    with pytest.raises(InvalidCalendarError):
        resolve_machine_calendars(
            ["M1"], {"M1": "not-a-calendar"}, catalog, HORIZON_START, HORIZON_END
        )


def test_non_mapping_machine_calendars_fails_closed():
    catalog = MachineCatalog()
    catalog.register(_machine("M1"))
    with pytest.raises(InvalidCalendarError):
        resolve_machine_calendars(
            ["M1"], ["not", "a", "mapping"], catalog, HORIZON_START, HORIZON_END
        )


# ---------------------------------------------------------------------------
# 15. naive calendar-function datetime -> fail closed
# ---------------------------------------------------------------------------


def test_naive_horizon_start_fails_closed():
    # AvailabilityWindow/MaintenanceWindow/ResourceCalendar themselves
    # already reject a naive datetime at construction time (PLANNING-01C) --
    # a naive datetime can never actually reach this module packaged inside
    # one of those. The reachable naive-datetime path here is horizon_start/
    # horizon_end, supplied directly by the caller.
    naive = datetime(2026, 9, 28, 8, 0, 0)
    with pytest.raises(InvalidSolverProblemError):
        normalize_machine_availability(None, "M1", naive, HORIZON_END)


def test_naive_horizon_end_fails_closed():
    naive = datetime(2026, 9, 29, 8, 0, 0)
    with pytest.raises(InvalidSolverProblemError):
        normalize_machine_availability(None, "M1", HORIZON_START, naive)


def test_availability_window_itself_rejects_naive_datetime_at_construction():
    # Documents *why* test_naive_horizon_*_fails_closed above are the only
    # reachable naive-datetime paths in this module: a naive AvailabilityWindow
    # cannot even be constructed, let alone reach calendar_constraints.
    from backend.domain.exceptions import ValidationError

    with pytest.raises(ValidationError):
        AvailabilityWindow(start=datetime(2026, 9, 28, 8, 0, 0), end=_t(9))


# ---------------------------------------------------------------------------
# 16. horizon_end <= horizon_start -> fail closed
# ---------------------------------------------------------------------------


def test_horizon_end_equal_to_horizon_start_fails_closed():
    with pytest.raises(InvalidSolverProblemError):
        normalize_machine_availability(None, "M1", HORIZON_START, HORIZON_START)


def test_horizon_end_before_horizon_start_fails_closed():
    with pytest.raises(InvalidSolverProblemError):
        normalize_machine_availability(None, "M1", HORIZON_END, HORIZON_START)


# ---------------------------------------------------------------------------
# resolve_machine_calendars: multi-machine resolution, deterministic keys
# ---------------------------------------------------------------------------


def test_resolve_machine_calendars_covers_every_requested_machine():
    catalog = MachineCatalog()
    catalog.register(_machine("M1"))
    catalog.register(_machine("M2"))
    calendar = ResourceCalendar(
        calendar_id="C1", timezone="UTC", availability_windows=(_window(8, 12),)
    )

    resolved = resolve_machine_calendars(
        ["M2", "M1"], {"M1": calendar}, catalog, HORIZON_START, HORIZON_END
    )
    assert set(resolved) == {"M1", "M2"}
    assert resolved["M1"] == (AvailabilityWindow(start=_t(8), end=_t(12)),)
    # M2 has no mapping entry -> continuous-availability policy applies.
    assert resolved["M2"] == (AvailabilityWindow(start=HORIZON_START, end=HORIZON_END),)


def test_resolve_machine_calendars_with_none_mapping_applies_continuous_policy_to_all():
    catalog = MachineCatalog()
    catalog.register(_machine("M1"))
    resolved = resolve_machine_calendars(["M1"], None, catalog, HORIZON_START, HORIZON_END)
    assert resolved == {"M1": (AvailabilityWindow(start=HORIZON_START, end=HORIZON_END),)}


# ---------------------------------------------------------------------------
# to_solver_availability: absolute -> solver-relative conversion
# ---------------------------------------------------------------------------


def test_to_solver_availability_converts_offsets_correctly():
    normalized = {
        "M1": (
            AvailabilityWindow(start=_t(8), end=_t(10)),
            AvailabilityWindow(start=_t(11), end=_t(12)),
        )
    }
    solver_availability = to_solver_availability(normalized, HORIZON_START)
    assert solver_availability == {
        "M1": (
            SolverAvailabilityWindow(start_offset=0, end_offset=7200),
            SolverAvailabilityWindow(start_offset=10800, end_offset=14400),
        )
    }


def test_to_solver_availability_preserves_empty_tuple_for_unavailable_machine():
    solver_availability = to_solver_availability({"M1": ()}, HORIZON_START)
    assert solver_availability == {"M1": ()}


# ---------------------------------------------------------------------------
# Ticket example, reproduced exactly (docstring-level example verification)
# ---------------------------------------------------------------------------


def test_ticket_worked_example_reproduced_exactly():
    horizon_start = datetime(2026, 9, 28, 8, 0, tzinfo=UTC)
    horizon_end = datetime(2026, 9, 29, 8, 0, tzinfo=UTC)
    calendar = ResourceCalendar(
        calendar_id="C1",
        timezone="UTC",
        availability_windows=(
            AvailabilityWindow(start=_t(8), end=_t(12)),
            AvailabilityWindow(start=_t(13), end=_t(17)),
        ),
        maintenance_windows=(MaintenanceWindow(machine_id="M1", start=_t(10), end=_t(11)),),
    )
    normalized = normalize_machine_availability(calendar, "M1", horizon_start, horizon_end)
    solver_windows = to_solver_availability({"M1": normalized}, horizon_start)["M1"]
    assert solver_windows == (
        SolverAvailabilityWindow(start_offset=0, end_offset=7200),
        SolverAvailabilityWindow(start_offset=10800, end_offset=14400),
        SolverAvailabilityWindow(start_offset=18000, end_offset=32400),
    )
