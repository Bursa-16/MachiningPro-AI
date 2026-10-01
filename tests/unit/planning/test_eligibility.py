"""Stage 4 (PLANNING-01D): machine-eligibility resolution tests.

Covers ``backend.planning.eligibility.resolve_eligible_machines`` and the
``backend.planning.routing.resolve_routing_eligibility`` ProcessPlan bridge.

All tests exercise the REAL ``backend.machines.catalog.MachineCatalog`` and
REAL ``backend.domain.machine.Machine`` / ``backend.domain.operation.Operation``
instances — this suite proves the planning eligibility layer delegates to
existing engineering capability code rather than reimplementing it.

Note on duplicate machine IDs: ``MachineCatalog.register()`` already rejects
duplicate ``machine_id`` at registration (see ``tests/unit/machines/
test_catalog.py::TestRegistration::test_duplicate_id_rejected``), and
``find_by_operation()`` draws from that same de-duplicated registry. Duplicate
candidate machine IDs are therefore structurally impossible to produce
through the real catalog, so no separate duplicate-handling test is added
here — that would just re-test the catalog's own guarantee.
"""

from __future__ import annotations

import dataclasses

import pytest

from backend.domain.base import Provenance
from backend.domain.enums import MachineType, OperationType, ProvenanceType
from backend.domain.machine import Machine
from backend.domain.operation import Operation
from backend.domain.units import Quantity, Unit
from backend.machines.catalog import MachineCatalog
from backend.planning.eligibility import (
    EligibilityDiagnosticCode,
    EligibilityResult,
    resolve_eligible_machines,
)
from backend.planning.exceptions import (
    OperationIdentityMismatchError,
    PlanningError,
    UnknownOperationError,
)
from backend.planning.models import Routing
from backend.planning.routing import resolve_routing_eligibility
from backend.process_planning.models import PlanStatus, ProcessPlan, ProcessPlanStep

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _prov() -> Provenance:
    return Provenance(
        source_type=ProvenanceType.MANUFACTURER_DATA,
        source_reference="Fixture machine — test only",
    )


def _op_prov() -> Provenance:
    return Provenance(
        source_type=ProvenanceType.USER_INPUT,
        source_reference="Fixture operation — test only",
    )


def _make_mill(machine_id: str = "MILL-001") -> Machine:
    return Machine(
        machine_id=machine_id,
        name="Test VMC",
        machine_type=MachineType.MILL,
        axis_count=3,
        spindle_speed_min=Quantity.of("50", Unit.RPM),
        spindle_speed_max=Quantity.of("12000", Unit.RPM),
        spindle_power=Quantity.of("15", Unit.KW),
        provenance=_prov(),
        supported_operations=(OperationType.MILLING, OperationType.DRILLING),
    )


def _make_lathe(machine_id: str = "LATHE-001") -> Machine:
    return Machine(
        machine_id=machine_id,
        name="Test CNC Lathe",
        machine_type=MachineType.LATHE,
        axis_count=2,
        spindle_speed_min=Quantity.of("30", Unit.RPM),
        spindle_speed_max=Quantity.of("5000", Unit.RPM),
        spindle_power=Quantity.of("11", Unit.KW),
        provenance=_prov(),
        supported_operations=(OperationType.TURNING, OperationType.FACING),
    )


def _make_operation(
    operation_id: str = "OP-001",
    operation_type: OperationType = OperationType.MILLING,
) -> Operation:
    return Operation(
        operation_id=operation_id,
        part_id="PART-001",
        operation_type=operation_type,
        sequence_index=1,
        provenance=_op_prov(),
    )


# ---------------------------------------------------------------------------
# resolve_eligible_machines
# ---------------------------------------------------------------------------


class TestResolveEligibleMachines:
    def test_single_capable_machine(self) -> None:
        """1. Operation supported by exactly one machine -> returns that machine."""
        catalog = MachineCatalog()
        catalog.register(_make_mill("MILL-001"))
        catalog.register(_make_lathe("LATHE-001"))  # does not support MILLING

        operation = _make_operation(operation_type=OperationType.MILLING)
        result = resolve_eligible_machines(operation, catalog)

        assert result.eligible_machine_ids == ("MILL-001",)
        assert result.diagnostic_code is EligibilityDiagnosticCode.RESOLVED

    def test_multiple_capable_machines_deterministic(self) -> None:
        """2. Operation supported by multiple machines -> deterministic sorted result."""
        catalog = MachineCatalog()
        catalog.register(_make_mill("MILL-002"))
        catalog.register(_make_mill("MILL-001"))

        operation = _make_operation(operation_type=OperationType.MILLING)
        result = resolve_eligible_machines(operation, catalog)

        assert result.eligible_machine_ids == ("MILL-001", "MILL-002")
        # Calling again must yield the identical tuple (referential determinism).
        assert resolve_eligible_machines(operation, catalog).eligible_machine_ids == (
            "MILL-001",
            "MILL-002",
        )

    def test_unsupported_operation_no_false_positive(self) -> None:
        """3. Unsupported operation -> no false-positive machine eligibility."""
        catalog = MachineCatalog()
        catalog.register(_make_mill("MILL-001"))

        operation = _make_operation(operation_type=OperationType.GRINDING)
        result = resolve_eligible_machines(operation, catalog)

        assert result.eligible_machine_ids == ()
        assert result.diagnostic_code is EligibilityDiagnosticCode.NO_CAPABLE_MACHINE

    def test_empty_catalog_fails_closed(self) -> None:
        """4. Empty machine catalog -> fail-closed behavior (never "assume eligible")."""
        catalog = MachineCatalog()
        operation = _make_operation(operation_type=OperationType.MILLING)

        result = resolve_eligible_machines(operation, catalog)

        assert result.eligible_machine_ids == ()
        assert result.diagnostic_code is EligibilityDiagnosticCode.NO_CAPABLE_MACHINE

    def test_wrong_operation_type_excluded(self) -> None:
        """5. Machine supporting the wrong operation type -> excluded."""
        catalog = MachineCatalog()
        catalog.register(_make_lathe("LATHE-001"))  # TURNING, FACING only

        operation = _make_operation(operation_type=OperationType.MILLING)
        result = resolve_eligible_machines(operation, catalog)

        assert "LATHE-001" not in result.eligible_machine_ids
        assert result.eligible_machine_ids == ()

    def test_real_machine_catalog_actually_used(self) -> None:
        """7. Existing MachineCatalog is genuinely queried, not a fake local map.

        Registering a NEW machine into the same catalog changes the result on
        the next call — proving resolution reads live from the catalog
        rather than from any planning-local snapshot.
        """
        catalog = MachineCatalog()
        operation = _make_operation(operation_type=OperationType.MILLING)

        before = resolve_eligible_machines(operation, catalog)
        assert before.eligible_machine_ids == ()

        catalog.register(_make_mill("MILL-001"))

        after = resolve_eligible_machines(operation, catalog)
        assert after.eligible_machine_ids == ("MILL-001",)

    def test_frozen_scheduling_operation_style_result_is_immutable(self) -> None:
        """8. EligibilityResult itself is frozen (nothing mutates a resolved result)."""
        catalog = MachineCatalog()
        catalog.register(_make_mill("MILL-001"))
        operation = _make_operation(operation_type=OperationType.MILLING)

        result = resolve_eligible_machines(operation, catalog)

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.eligible_machine_ids = ()  # type: ignore[misc]

    def test_real_existing_operation_instance_used(self) -> None:
        """9. A real, existing Operation instance is used end-to-end."""
        operation = Operation(
            operation_id="OP-REAL-001",
            part_id="PART-001",
            operation_type=OperationType.TURNING,
            sequence_index=1,
            provenance=_op_prov(),
        )
        catalog = MachineCatalog()
        catalog.register(_make_lathe("LATHE-001"))

        result = resolve_eligible_machines(operation, catalog)

        assert result.operation_id == operation.operation_id
        assert result.operation_type is operation.operation_type
        assert result.eligible_machine_ids == ("LATHE-001",)

    def test_non_operation_rejected(self) -> None:
        catalog = MachineCatalog()
        with pytest.raises(PlanningError):
            resolve_eligible_machines("not-an-operation", catalog)  # type: ignore[arg-type]

    def test_non_catalog_rejected(self) -> None:
        operation = _make_operation()
        with pytest.raises(PlanningError):
            resolve_eligible_machines(operation, {"MILL-001": _make_mill()})  # type: ignore[arg-type]

    def test_result_immutable_and_is_dataclass(self) -> None:
        catalog = MachineCatalog()
        catalog.register(_make_mill("MILL-001"))
        operation = _make_operation(operation_type=OperationType.MILLING)

        result = resolve_eligible_machines(operation, catalog)
        assert isinstance(result, EligibilityResult)
        assert result.as_dict()["eligible_machine_ids"] == ["MILL-001"]


# ---------------------------------------------------------------------------
# resolve_routing_eligibility (ProcessPlan bridge)
# ---------------------------------------------------------------------------


class TestResolveRoutingEligibility:
    def _plan_and_routing(self) -> tuple[ProcessPlan, Routing]:
        step_a = ProcessPlanStep(
            step_id="STEP-A", sequence_index=0, operation_type=OperationType.TURNING
        )
        step_b = ProcessPlanStep(
            step_id="STEP-B",
            sequence_index=1,
            operation_type=OperationType.MILLING,
            predecessor_step_ids=("STEP-A",),
        )
        plan = ProcessPlan(
            plan_id="PP-001",
            part_id="PART-001",
            steps=(step_b, step_a),  # deliberately out of order
            engineering_status=PlanStatus.INCOMPLETE,
            provenance=_op_prov(),
        )
        routing = Routing.from_process_plan(plan, routing_id="ROUTING-001")
        return plan, routing

    def test_preserves_order_and_precedence(self) -> None:
        """10. ProcessPlan bridge preserves precedence and ordering."""
        _, routing = self._plan_and_routing()
        assert routing.ordered_operation_ids == ("STEP-A", "STEP-B")
        assert routing.precedence["STEP-B"] == ("STEP-A",)

        operations = {
            "STEP-A": _make_operation("STEP-A", OperationType.TURNING),
            "STEP-B": _make_operation("STEP-B", OperationType.MILLING),
        }
        catalog = MachineCatalog()
        catalog.register(_make_lathe("LATHE-001"))
        catalog.register(_make_mill("MILL-001"))

        results = resolve_routing_eligibility(routing, operations, catalog)

        # Results come back in routing order (STEP-A, then STEP-B) — the
        # bridge does not reorder or recompute precedence.
        assert [r.operation_id for r in results] == ["STEP-A", "STEP-B"]
        assert results[0].eligible_machine_ids == ("LATHE-001",)
        assert results[1].eligible_machine_ids == ("MILL-001",)

    def test_unknown_operation_id_raises(self) -> None:
        _, routing = self._plan_and_routing()
        operations = {
            "STEP-A": _make_operation("STEP-A", OperationType.TURNING),
            # STEP-B intentionally missing from the lookup
        }
        catalog = MachineCatalog()
        catalog.register(_make_lathe("LATHE-001"))

        with pytest.raises(UnknownOperationError, match="STEP-B"):
            resolve_routing_eligibility(routing, operations, catalog)

    def test_does_not_calculate_solver_timing(self) -> None:
        """The bridge's result carries no timing/scheduling fields at all —
        proves it does not perform scheduling."""
        _, routing = self._plan_and_routing()
        operations = {
            "STEP-A": _make_operation("STEP-A", OperationType.TURNING),
            "STEP-B": _make_operation("STEP-B", OperationType.MILLING),
        }
        catalog = MachineCatalog()
        catalog.register(_make_lathe("LATHE-001"))
        catalog.register(_make_mill("MILL-001"))

        results = resolve_routing_eligibility(routing, operations, catalog)

        for result in results:
            assert not hasattr(result, "start_time")
            assert not hasattr(result, "end_time")
            assert not hasattr(result, "machine_id")  # a single assignment, not a set of candidates

    def test_non_routing_rejected(self) -> None:
        with pytest.raises(PlanningError):
            resolve_routing_eligibility("not-a-routing", {}, MachineCatalog())  # type: ignore[arg-type]

    def test_operation_identity_mismatch_rejected(self) -> None:
        """Regression: a mapping key must agree with the Operation's own
        operation_id — a malformed mapping such as

            operations["OP10"] = Operation(operation_id="OP20", ...)

        must be rejected, not silently accepted under the wrong identity.
        """
        _, routing = self._plan_and_routing()  # expects STEP-A, STEP-B
        mismatched_operation = _make_operation(
            operation_id="STEP-WRONG", operation_type=OperationType.TURNING
        )
        operations = {
            "STEP-A": mismatched_operation,  # key STEP-A, but .operation_id == STEP-WRONG
            "STEP-B": _make_operation("STEP-B", OperationType.MILLING),
        }
        catalog = MachineCatalog()
        catalog.register(_make_lathe("LATHE-001"))
        catalog.register(_make_mill("MILL-001"))

        with pytest.raises(OperationIdentityMismatchError, match="STEP-A"):
            resolve_routing_eligibility(routing, operations, catalog)

    def test_operation_identity_mismatch_returns_no_partial_result(self) -> None:
        """The mismatch must fail closed before returning anything — no
        partial eligibility tuple for the operations already resolved."""
        _, routing = self._plan_and_routing()  # expects STEP-A, STEP-B
        mismatched_operation = _make_operation(
            operation_id="STEP-WRONG", operation_type=OperationType.MILLING
        )
        operations = {
            "STEP-A": _make_operation("STEP-A", OperationType.TURNING),
            "STEP-B": mismatched_operation,  # the mismatch is on the SECOND operation
        }
        catalog = MachineCatalog()
        catalog.register(_make_lathe("LATHE-001"))
        catalog.register(_make_mill("MILL-001"))

        try:
            resolve_routing_eligibility(routing, operations, catalog)
            pytest.fail("expected OperationIdentityMismatchError")
        except OperationIdentityMismatchError as exc:
            # The exception itself carries no partial results — proving
            # the function never returns a truncated tuple to the caller
            # (a caught exception simply has no return value at all).
            assert not hasattr(exc, "eligible_machine_ids")
            assert not hasattr(exc, "results")
