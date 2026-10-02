"""Deterministic in-memory machine-tool catalog (Stage 3H).

Provides registration and exact lookup of
:class:`~backend.domain.machine.Machine` instances.

No production seed machines are included.  Every ``Machine`` admitted to
the catalog must carry explicit provenance before it can be used in
capability validation.

Lookup semantics
----------------
* Exact-ID lookup raises :class:`~backend.empirical.exceptions.EmpiricalDataError`
  when the ID is not found.
* Collection queries return all matching records in deterministic order
  (sorted by ``machine_id``).
* Duplicate ``machine_id`` is rejected at registration (fail closed).
* No ranking, no fuzzy search, no AI.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.domain.enums import MachineType, OperationType
from backend.domain.machine import Machine
from backend.empirical.exceptions import EmpiricalDataError

__all__ = ["MachineCatalog"]


@dataclass
class MachineCatalog:
    """In-memory catalog of :class:`~backend.domain.machine.Machine` records.

    ``_machines`` is private; all mutation goes through :meth:`register`.
    """

    _machines: dict[str, Machine] = field(default_factory=dict, init=False)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, machine: Machine) -> Machine:
        """Register *machine*; raise on duplicate ``machine_id``.

        Args:
            machine: A fully validated :class:`Machine` instance.

        Returns:
            The registered machine (same object — no copy).

        Raises:
            TypeError: when *machine* is not a :class:`Machine`.
            EmpiricalDataError: when the ID is already registered.
        """
        if not isinstance(machine, Machine):
            raise TypeError("only Machine instances can be registered")
        if machine.machine_id in self._machines:
            raise EmpiricalDataError(
                f"machine id {machine.machine_id!r} is already registered"
            )
        self._machines[machine.machine_id] = machine
        return machine

    # ------------------------------------------------------------------
    # Exact-ID lookup
    # ------------------------------------------------------------------

    def get(self, machine_id: str) -> Machine:
        """Return the machine with *machine_id*.

        Raises:
            EmpiricalDataError: when the ID is not registered.
        """
        machine = self._machines.get(machine_id)
        if machine is None:
            raise EmpiricalDataError(
                f"no machine with id {machine_id!r}"
            )
        return machine

    def has(self, machine_id: str) -> bool:
        """True when *machine_id* is registered."""
        return machine_id in self._machines

    # ------------------------------------------------------------------
    # Collection queries
    # ------------------------------------------------------------------

    def find_by_type(self, machine_type: MachineType) -> tuple[Machine, ...]:
        """All machines of the given :class:`MachineType`.

        Returns empty tuple when none match.  Sorted by ``machine_id``.
        """
        return tuple(
            sorted(
                (m for m in self._machines.values() if m.machine_type is machine_type),
                key=lambda m: m.machine_id,
            )
        )

    def find_by_operation(
        self, operation_type: OperationType
    ) -> tuple[Machine, ...]:
        """All machines that support the given :class:`OperationType`.

        Returns empty tuple when none match.  Sorted by ``machine_id``.
        """
        return tuple(
            sorted(
                (
                    m
                    for m in self._machines.values()
                    if operation_type in m.supported_operations
                ),
                key=lambda m: m.machine_id,
            )
        )

    def all(self) -> tuple[Machine, ...]:
        """All registered machines sorted by ``machine_id`` (deterministic)."""
        return tuple(sorted(self._machines.values(), key=lambda m: m.machine_id))

    def ids(self) -> tuple[str, ...]:
        """All registered machine IDs in stable registration order."""
        return tuple(self._machines)

    def __len__(self) -> int:
        return len(self._machines)

    def __contains__(self, machine_id: str) -> bool:
        return self.has(machine_id)
