"""ProcessPlan / routing → machine-eligibility bridge (Stage 4 — PLANNING-01D).

Bridges an already-derived :class:`backend.planning.models.Routing` (itself
derived from an existing :class:`backend.process_planning.models.ProcessPlan`
via :meth:`Routing.from_process_plan`) to per-operation machine eligibility,
using the capability layer in :mod:`backend.planning.eligibility`.

This module does not:

* Calculate solver start times.
* Perform any scheduling (assignment of a specific machine/time to an
  operation).
* Re-derive ordering or precedence — that is ``Routing``'s job, unchanged.
* Introduce a competing Operation registry — the caller supplies the
  ``operations`` lookup (whatever already loaded/queried those
  ``Operation`` instances); this module does not invent one.

It preserves operation identity (every result is keyed by the same
``operation_id`` the routing already carries) and preserves the routing's
own sequence, since results are returned in ``routing.ordered_operation_ids``
order.
"""

from __future__ import annotations

from collections.abc import Mapping

from backend.domain.operation import Operation
from backend.machines.catalog import MachineCatalog
from backend.planning.eligibility import EligibilityResult, resolve_eligible_machines
from backend.planning.exceptions import (
    OperationIdentityMismatchError,
    PlanningError,
    UnknownOperationError,
)
from backend.planning.models import Routing

__all__ = ["resolve_routing_eligibility"]


def resolve_routing_eligibility(
    routing: Routing,
    operations: Mapping[str, Operation],
    machine_catalog: MachineCatalog,
) -> tuple[EligibilityResult, ...]:
    """Resolve machine eligibility for every operation in *routing*, in order.

    Args:
        routing:         A :class:`~backend.planning.models.Routing`,
                         typically produced by
                         :meth:`Routing.from_process_plan`.
        operations:      A mapping from ``operation_id`` to the
                         corresponding, already-constructed
                         :class:`~backend.domain.operation.Operation`. This
                         bridge does not maintain or invent its own
                         Operation registry — the caller is responsible for
                         supplying real, previously-resolved instances.
        machine_catalog: The existing, already-populated
                         :class:`~backend.machines.catalog.MachineCatalog`.

    Returns:
        A tuple of :class:`~backend.planning.eligibility.EligibilityResult`,
        one per entry of ``routing.ordered_operation_ids``, in that same
        order — preserving the routing's own sequence.

    Raises:
        PlanningError: ``routing`` is not a ``Routing`` instance.
        UnknownOperationError: ``routing`` references an ``operation_id``
            that is not a key in ``operations`` — a reference-integrity
            failure, never silently skipped.
        OperationIdentityMismatchError: ``operations`` maps an
            ``operation_id`` key to an ``Operation`` whose own
            ``operation_id`` field does not match that key — never
            silently coerced, substituted, or continued past.

    Note:
        This function fails closed on the first defect encountered while
        walking ``routing.ordered_operation_ids`` in order: it never
        returns a partial tuple of results for a routing it could not
        fully resolve.
    """
    if not isinstance(routing, Routing):
        raise PlanningError(
            "routing must be a backend.planning.models.Routing instance"
        )

    results: list[EligibilityResult] = []
    for operation_id in routing.ordered_operation_ids:
        operation = operations.get(operation_id)
        if operation is None:
            raise UnknownOperationError(
                f"routing {routing.routing_id!r} references operation_id "
                f"{operation_id!r}, which is not present in the supplied "
                "operations mapping"
            )
        if operation.operation_id != operation_id:
            raise OperationIdentityMismatchError(
                f"routing {routing.routing_id!r}: operations mapping key "
                f"{operation_id!r} maps to an Operation whose own "
                f"operation_id is {operation.operation_id!r} — refusing to "
                "resolve eligibility under a mismatched identity"
            )
        results.append(resolve_eligible_machines(operation, machine_catalog))

    return tuple(results)
