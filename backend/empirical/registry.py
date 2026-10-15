"""In-memory registry for VP100 empirical machining records (Stage EMPIRICAL-01A).

Provides deterministic, queryable access to VP100EmpiricalRecord instances
loaded from the source XLSX.  The registry is populated once at application
startup via :func:`~backend.empirical.seed_vp100.seed_vp100_registry`.

Design
------
* Thread-safe for concurrent reads after the initial seed (no concurrent
  writes are expected; the registry is populated once at startup).
* All query methods return immutable tuples.
* Fail-closed: querying before seeding raises EmpiricalDataError.
"""

from __future__ import annotations

from backend.empirical.exceptions import EmpiricalDataError
from backend.empirical.models import VP100EmpiricalRecord

__all__ = [
    "VP100EmpiricalRegistry",
    "get_vp100_registry",
]


class VP100EmpiricalRegistry:
    """Queryable in-memory store for VP100 empirical observations.

    Lifecycle
    ---------
    1. Construct an instance.
    2. Call :meth:`register_all` exactly once with the loaded records.
    3. Query via :meth:`get_all`, :meth:`get_by_id`, or :meth:`filter`.
    """

    def __init__(self) -> None:
        self._records: dict[str, VP100EmpiricalRecord] = {}
        self._seeded = False

    # ------------------------------------------------------------------
    # Write side (called once at startup)
    # ------------------------------------------------------------------

    def register_all(
        self,
        records: list[VP100EmpiricalRecord],
        *,
        allow_reregister: bool = False,
    ) -> int:
        """Register a batch of records.

        Parameters
        ----------
        records:
            Records to store.  Must all be VP100EmpiricalRecord instances.
        allow_reregister:
            When *True*, re-registering the same ``record_id`` replaces the
            existing entry (idempotent re-seed).  When *False* (default), a
            duplicate ``record_id`` raises :class:`EmpiricalDataError`.

        Returns
        -------
        int
            Number of records now in the registry after registration.
        """
        for rec in records:
            if not isinstance(rec, VP100EmpiricalRecord):
                raise EmpiricalDataError(
                    f"Expected VP100EmpiricalRecord; got {type(rec).__name__}"
                )
            if rec.record_id in self._records and not allow_reregister:
                raise EmpiricalDataError(
                    f"Duplicate record_id {rec.record_id!r}; "
                    "use allow_reregister=True for idempotent re-seed"
                )
            self._records[rec.record_id] = rec
        self._seeded = True
        return len(self._records)

    # ------------------------------------------------------------------
    # Read side
    # ------------------------------------------------------------------

    def _require_seeded(self) -> None:
        if not self._seeded:
            raise EmpiricalDataError(
                "VP100EmpiricalRegistry has not been seeded.  "
                "Call seed_vp100_registry() before querying."
            )

    def record_count(self) -> int:
        """Number of records currently in the registry."""
        return len(self._records)

    def is_seeded(self) -> bool:
        """True after at least one successful :meth:`register_all` call."""
        return self._seeded

    def get_all(self) -> tuple[VP100EmpiricalRecord, ...]:
        """Return all records in insertion (source row) order."""
        self._require_seeded()
        return tuple(self._records.values())

    def get_by_id(self, record_id: str) -> VP100EmpiricalRecord:
        """Return the record with the given ID.

        Raises
        ------
        EmpiricalDataError
            When no record with *record_id* exists.
        """
        self._require_seeded()
        rec = self._records.get(record_id)
        if rec is None:
            raise EmpiricalDataError(
                f"No VP100 record found with record_id={record_id!r}"
            )
        return rec

    def filter(
        self,
        *,
        tool_condition: str | None = None,
        coating: str | None = None,
        combination: str | None = None,
        replicate: int | None = None,
    ) -> tuple[VP100EmpiricalRecord, ...]:
        """Return records matching all supplied criteria.

        A ``None`` criterion matches any value (no filtering on that
        dimension).  Returns an empty tuple when no records match.

        Parameters
        ----------
        tool_condition: "C0" / "C1" / "C2" / "C3"
        coating: "Uncoated" / "TiN" / "AlTiN" / "AlTiN/TiSiXN"
        combination: "A" – "H"
        replicate: 1 – 3
        """
        self._require_seeded()
        result = []
        for rec in self._records.values():
            if tool_condition is not None and rec.tool_condition != tool_condition:
                continue
            if coating is not None and rec.coating != coating:
                continue
            if combination is not None and rec.combination != combination:
                continue
            if replicate is not None and rec.replicate != replicate:
                continue
            result.append(rec)
        return tuple(result)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_REGISTRY: VP100EmpiricalRegistry | None = None


def get_vp100_registry() -> VP100EmpiricalRegistry:
    """Return the module-level VP100 registry, creating it if needed.

    The returned instance is unseeded until
    :func:`~backend.empirical.seed_vp100.seed_vp100_registry` is called.
    """
    global _REGISTRY  # noqa: PLW0603
    if _REGISTRY is None:
        _REGISTRY = VP100EmpiricalRegistry()
    return _REGISTRY
