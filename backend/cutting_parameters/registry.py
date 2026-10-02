"""In-memory empirical cutting-parameter registry (Stage 3G).

Provides deterministic registration and lookup of
:class:`~backend.cutting_parameters.models.CuttingParameterRecord` instances.

Design invariants
-----------------
* Duplicate ``record_id`` is rejected at registration (fail closed).
* Exact-ID lookup raises :class:`~backend.empirical.exceptions.EmpiricalDataError`
  when the ID is not found.
* Collection queries return **all** matching records in deterministic order
  (sorted by ``record_id``).  They never return a single "best" result,
  never rank, never average, and never silently resolve conflicts.
* An empty result set is returned as an empty tuple — not an error — so
  callers can distinguish "no data" from "bad query".
* Conflicting records (same scope, different source, different values) are
  preserved as separate entries.  The caller decides how to handle
  multiple matches.

No AI logic, no fuzzy matching, no heuristic ranking.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.cutting_parameters.models import (
    ApplicabilityScope,
    CuttingParameterRecord,
    EvidenceStatus,
    ParameterType,
)
from backend.empirical.exceptions import EmpiricalDataError

__all__ = ["CuttingParameterRegistry"]


@dataclass
class CuttingParameterRegistry:
    """In-memory registry of empirical cutting-parameter records.

    ``_records`` is intentionally private.  All mutation goes through
    :meth:`register` so duplicate-ID rejection cannot be bypassed.

    Thread-safety
    -------------
    Not thread-safe.  MachineryPro AI is single-threaded at Stage 3G.
    """

    _records: dict[str, CuttingParameterRecord] = field(
        default_factory=dict, init=False
    )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self, record: CuttingParameterRecord
    ) -> CuttingParameterRecord:
        """Register *record*; raise :class:`EmpiricalDataError` on duplicate ID.

        Args:
            record: A fully validated :class:`CuttingParameterRecord`.

        Returns:
            The registered record (same object — no copy).

        Raises:
            TypeError: when *record* is not a ``CuttingParameterRecord``.
            EmpiricalDataError: when the record's ID is already registered.
        """
        if not isinstance(record, CuttingParameterRecord):
            raise TypeError(
                "only CuttingParameterRecord instances can be registered"
            )
        if record.record_id in self._records:
            raise EmpiricalDataError(
                f"record id {record.record_id!r} is already registered"
            )
        self._records[record.record_id] = record
        return record

    # ------------------------------------------------------------------
    # Exact-ID lookup
    # ------------------------------------------------------------------

    def get(self, record_id: str) -> CuttingParameterRecord:
        """Return the record with *record_id*.

        Raises:
            EmpiricalDataError: when the ID is not registered.
        """
        record = self._records.get(record_id)
        if record is None:
            raise EmpiricalDataError(
                f"no cutting parameter record with id {record_id!r}"
            )
        return record

    def has(self, record_id: str) -> bool:
        """True when *record_id* is registered."""
        return record_id in self._records

    # ------------------------------------------------------------------
    # Collection queries — always return tuples, never single "best"
    # ------------------------------------------------------------------

    def find(
        self,
        *,
        scope: ApplicabilityScope | None = None,
        parameter_type: ParameterType | None = None,
        evidence_status: EvidenceStatus | None = None,
    ) -> tuple[CuttingParameterRecord, ...]:
        """Return all records that satisfy ALL supplied filters.

        Filters that are ``None`` are not applied (match everything).

        Multiple matching records are returned in deterministic order
        (sorted by ``record_id``).  No ranking, no automatic selection.

        Args:
            scope: Applicability scope filter; uses
                :meth:`~CuttingParameterRecord.matches_scope` logic.
            parameter_type: If set, only records with this
                :class:`ParameterType` are returned.
            evidence_status: If set, only records with this
                :class:`EvidenceStatus` are returned.

        Returns:
            Tuple of matching records sorted by ``record_id``.
            Empty tuple when nothing matches.
        """
        results: list[CuttingParameterRecord] = []
        for record in self._records.values():
            if parameter_type is not None and record.parameter_type != parameter_type:
                continue
            if evidence_status is not None and record.evidence_status != evidence_status:
                continue
            if scope is not None and not record.matches_scope(scope):
                continue
            results.append(record)
        return tuple(sorted(results, key=lambda r: r.record_id))

    def find_authoritative(
        self,
        *,
        scope: ApplicabilityScope | None = None,
        parameter_type: ParameterType | None = None,
    ) -> tuple[CuttingParameterRecord, ...]:
        """Return only records whose :attr:`~CuttingParameterRecord.is_authoritative`
        is ``True``, applying the same scope and parameter-type filters.

        Multiple authoritative records from different sources are preserved
        as separate entries.  The caller must decide how to resolve them.
        """
        all_matches = self.find(scope=scope, parameter_type=parameter_type)
        return tuple(r for r in all_matches if r.is_authoritative)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def ids(self) -> tuple[str, ...]:
        """All registered record IDs in stable registration order."""
        return tuple(self._records)

    def all(self) -> tuple[CuttingParameterRecord, ...]:
        """All registered records sorted by record_id (deterministic)."""
        return tuple(sorted(self._records.values(), key=lambda r: r.record_id))

    def __len__(self) -> int:
        return len(self._records)

    def __contains__(self, record_id: str) -> bool:
        return self.has(record_id)
