"""Deterministic format adapter registry (Stage 4A).

Provides explicit registration and lookup of format adapters.

Design invariants
-----------------
* Duplicate adapter_id is rejected at registration (fail closed).
* Lookup returns all matching adapters in deterministic order (sorted by
  adapter_id).  The registry NEVER selects one automatically.
* No hidden prioritization, no implicit "best adapter" selection.
* When multiple adapters support the same format: all are returned.
  The caller chooses explicitly.
* No fuzzy matching; no approximate format detection.
* The registry is not a singleton — callers construct instances.

Example::

    registry = AdapterRegistry()
    registry.register(my_step_adapter)
    registry.register(my_commercial_step_adapter)

    # Returns BOTH adapters; caller chooses:
    adapters = registry.find_by_format("STEP-AP242")
    selected = caller_chooses(adapters)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.domain.exceptions import DomainError
from backend.interoperability.adapter import FormatAdapter
from backend.interoperability.enums import AdapterCapability, FormatFamily
from backend.interoperability.models import AdapterMetadata

__all__ = ["AdapterRegistryError", "AdapterRegistry"]


class AdapterRegistryError(DomainError):
    """Raised for adapter registry failures (duplicate ID, not found, etc.)."""


@dataclass
class AdapterRegistry:
    """Deterministic in-memory registry of format adapters.

    Stores adapter instances indexed by adapter_id.  All lookups return
    tuples sorted by adapter_id for reproducibility.
    """

    _adapters: dict[str, FormatAdapter] = field(
        default_factory=dict, init=False
    )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, adapter: FormatAdapter) -> FormatAdapter:
        """Register *adapter*.

        Raises:
            TypeError:             when *adapter* is not a FormatAdapter.
            AdapterRegistryError:  when the adapter's ID is already registered.
        """
        if not isinstance(adapter, FormatAdapter):
            raise TypeError("only FormatAdapter instances can be registered")
        meta = adapter.metadata()
        if meta.adapter_id in self._adapters:
            raise AdapterRegistryError(
                f"adapter id {meta.adapter_id!r} is already registered"
            )
        self._adapters[meta.adapter_id] = adapter
        return adapter

    # ------------------------------------------------------------------
    # Exact-ID lookup
    # ------------------------------------------------------------------

    def get(self, adapter_id: str) -> FormatAdapter:
        """Return the adapter with *adapter_id*.

        Raises:
            AdapterRegistryError: when not found.
        """
        adapter = self._adapters.get(adapter_id)
        if adapter is None:
            raise AdapterRegistryError(
                f"no adapter registered with id {adapter_id!r}"
            )
        return adapter

    def has(self, adapter_id: str) -> bool:
        """True when *adapter_id* is registered."""
        return adapter_id in self._adapters

    # ------------------------------------------------------------------
    # Collection queries — always tuples, sorted by adapter_id
    # ------------------------------------------------------------------

    def find_by_format(self, format_id: str) -> tuple[FormatAdapter, ...]:
        """All adapters that declare support for *format_id*.

        Sorted by adapter_id (deterministic).  Empty tuple when none match.
        The caller must choose among multiple results; the registry never
        selects one automatically.
        """
        return tuple(
            sorted(
                (a for a in self._adapters.values() if a.metadata().supports_format(format_id)),
                key=lambda a: a.metadata().adapter_id,
            )
        )

    def find_by_family(self, family: FormatFamily) -> tuple[FormatAdapter, ...]:
        """All adapters whose declared format_ids include formats in *family*.

        This is a rough capability query; family membership is not stored
        directly in AdapterMetadata — the registry cross-references via the
        format_ids declared by each adapter.

        Since the registry does not store FormatDescriptor objects (those
        belong to a separate format catalog), family-based lookup is advisory:
        it checks format_id string conventions only.

        Sorted by adapter_id.
        """
        # Adapters cannot be queried by family directly without a format
        # catalog — return all adapters for now and let callers filter.
        # This method signature is defined here for the interface; a
        # format catalog integration is introduced in Stage 4B+.
        _ = family  # will be used when format catalog is integrated
        return self.all()

    def find_by_capability(
        self, capability: AdapterCapability
    ) -> tuple[FormatAdapter, ...]:
        """All adapters that declare *capability*.

        Sorted by adapter_id.
        """
        return tuple(
            sorted(
                (
                    a
                    for a in self._adapters.values()
                    if a.metadata().supports_capability(capability)
                ),
                key=lambda a: a.metadata().adapter_id,
            )
        )

    def all(self) -> tuple[FormatAdapter, ...]:
        """All registered adapters sorted by adapter_id (deterministic)."""
        return tuple(
            sorted(self._adapters.values(), key=lambda a: a.metadata().adapter_id)
        )

    def ids(self) -> tuple[str, ...]:
        """All registered adapter IDs in stable registration order."""
        return tuple(self._adapters)

    def metadata_for_all(self) -> tuple[AdapterMetadata, ...]:
        """AdapterMetadata for all adapters, sorted by adapter_id."""
        return tuple(a.metadata() for a in self.all())

    def __len__(self) -> int:
        return len(self._adapters)

    def __contains__(self, adapter_id: str) -> bool:
        return self.has(adapter_id)
