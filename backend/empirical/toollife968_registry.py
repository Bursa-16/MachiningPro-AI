"""
In-memory queryable registry for ToolLife968Observation records.

Provides process-level singleton access via get_toollife968_registry().
"""

from __future__ import annotations

from backend.empirical.exceptions import EmpiricalDataError
from backend.empirical.toollife968_models import ToolLife968Observation


class ToolLife968Registry:
    """
    In-memory store for ToolLife968Observation records.

    Not thread-safe. Must be seeded via register_all() before any query.
    Subsequent register_all() calls append records unless allow_reregister=True.
    """

    def __init__(self) -> None:
        self._records: dict[str, ToolLife968Observation] = {}
        self._seeded: bool = False

    def is_seeded(self) -> bool:
        return self._seeded

    def record_count(self) -> int:
        return len(self._records)

    def register_all(
        self,
        records: list[ToolLife968Observation],
        *,
        allow_reregister: bool = False,
    ) -> int:
        """Bulk-register records. Returns count of records registered."""
        for rec in records:
            if not isinstance(rec, ToolLife968Observation):
                raise EmpiricalDataError(
                    f"Expected ToolLife968Observation, got {type(rec).__name__}"
                )
            if not allow_reregister and rec.observation_id in self._records:
                raise EmpiricalDataError(
                    f"Duplicate observation_id: {rec.observation_id!r}"
                )
            self._records[rec.observation_id] = rec
        self._seeded = True
        return len(records)

    def _require_seeded(self) -> None:
        if not self._seeded:
            raise EmpiricalDataError(
                "ToolLife968Registry has not been seeded. "
                "Call register_all() or seed_toollife968_registry() first."
            )

    def get_all(self) -> tuple[ToolLife968Observation, ...]:
        self._require_seeded()
        return tuple(self._records.values())

    def get_by_id(self, observation_id: str) -> ToolLife968Observation:
        self._require_seeded()
        if observation_id not in self._records:
            raise EmpiricalDataError(
                f"ToolLife968Observation not found: {observation_id!r}"
            )
        return self._records[observation_id]

    def filter(
        self,
        *,
        tool_index: int | None = None,
        tool_type: str | None = None,
        adoc_mm: float | None = None,
        rdoc_mm: float | None = None,
        eol_only: bool = False,
    ) -> tuple[ToolLife968Observation, ...]:
        """
        Filter observations by criteria (AND-combined).

        eol_only=True returns only observations where cycle_to_failure == 0.
        """
        self._require_seeded()
        results = list(self._records.values())
        if tool_index is not None:
            results = [r for r in results if r.tool_index == tool_index]
        if tool_type is not None:
            results = [r for r in results if r.tool_type == tool_type]
        if adoc_mm is not None:
            results = [r for r in results if float(r.adoc.value) == adoc_mm]
        if rdoc_mm is not None:
            results = [r for r in results if float(r.rdoc.value) == rdoc_mm]
        if eol_only:
            results = [r for r in results if r.is_eol]
        return tuple(results)

    def get_by_tool(self, tool_index: int) -> tuple[ToolLife968Observation, ...]:
        """Return all observations for a tool, sorted by (cycle_number, sample_index)."""
        self._require_seeded()
        tool_obs = [r for r in self._records.values() if r.tool_index == tool_index]
        return tuple(sorted(tool_obs, key=lambda r: (r.cycle_number, r.sample_index)))

    def get_eol_observations(self) -> tuple[ToolLife968Observation, ...]:
        """Return EOL observations (cycle_to_failure == 0)."""
        self._require_seeded()
        return tuple(r for r in self._records.values() if r.is_eol)


_TOOLLIFE968_REGISTRY: ToolLife968Registry | None = None


def get_toollife968_registry() -> ToolLife968Registry:
    """Return the process-level singleton ToolLife968Registry."""
    global _TOOLLIFE968_REGISTRY
    if _TOOLLIFE968_REGISTRY is None:
        _TOOLLIFE968_REGISTRY = ToolLife968Registry()
    return _TOOLLIFE968_REGISTRY
