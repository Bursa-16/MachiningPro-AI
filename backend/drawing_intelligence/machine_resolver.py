"""Machine Candidate Resolver — EPIC_04E Phase 2.

Queries MachineCatalogRecord to find machines eligible for a given
OperationType.  REFERENCE_ONLY — never designates a winner.

ROUTE_MACHINE_CANDIDATES_IMPLEMENTED=YES
FABRICATED_MACHINE_COMPATIBILITY=NO
"""

from __future__ import annotations

from backend.domain.enums import MachineType, OperationType
from backend.drawing_intelligence.route_alternatives import OPERATION_TO_MACHINE_TYPES
from backend.drawing_intelligence.route_domain import MachineCandidateSummary

__all__ = ["MachineCandidateResolver"]

_MACHINE_TYPE_CODE_MAP: dict[str, MachineType] = {
    "VMC": MachineType.VMC_3AXIS,
    "VMC_3AXIS": MachineType.VMC_3AXIS,
    "VMC_4AXIS": MachineType.VMC_4AXIS,
    "VMC_5AXIS": MachineType.VMC_5AXIS,
    "5AXIS": MachineType.VMC_5AXIS,
    "HMC": MachineType.HMC,
    "LATHE": MachineType.LATHE,
    "MILL_TURN": MachineType.MILL_TURN,
    "LATHE_Y": MachineType.LATHE_Y,
    "SWISS": MachineType.SWISS,
    "VTL": MachineType.VTL,
    "GANTRY": MachineType.GANTRY,
    "BORING_MILL": MachineType.BORING_MILL,
    "GRINDER": MachineType.GRINDER,
    "EDM": MachineType.EDM,
    "DRILL_TAP": MachineType.DRILL_TAP,
}


def _record_to_machine_type(code: str) -> MachineType | None:
    return _MACHINE_TYPE_CODE_MAP.get(code.upper())


def _suitability(record, op_type: OperationType, required_ra_um: float | None) -> int:
    """Compute a deterministic suitability score 0–100.

    Higher = better fit.  No fabricated values — only catalog fields used.
    """
    score = 50  # baseline

    eligible_types = OPERATION_TO_MACHINE_TYPES.get(op_type, ())
    m_type = _record_to_machine_type(record.machine_type_code or "")
    if m_type and m_type in eligible_types:
        score += 30
    elif record.milling_capable and op_type in (OperationType.MILLING, OperationType.DRILLING):
        score += 10
    elif record.turning_capable and op_type in (OperationType.TURNING, OperationType.BORING):
        score += 10

    # Prefer higher axis count for complex ops
    if record.axis_count and record.axis_count >= 5 and op_type in (
        OperationType.MILLING, OperationType.BORING
    ):
        score += 10
    elif record.axis_count and record.axis_count >= 4:
        score += 5

    # Penalise if required_ra demands specialty (honing / lapping / grinding)
    # and machine is not a GRINDER
    if required_ra_um and required_ra_um <= 0.1:
        if m_type not in (MachineType.GRINDER, MachineType.OTHER):
            score -= 10

    return max(0, min(100, score))


class MachineCandidateResolver:
    """Resolves OperationType → list[MachineCandidateSummary] from the catalog.

    ROUTE_MACHINE_CANDIDATES_IMPLEMENTED=YES
    FABRICATED_MACHINE_COMPATIBILITY=NO
    Returns [] (not error) when no catalog match exists.
    """

    def __init__(self) -> None:
        self._catalog: list | None = None

    def _get_catalog(self):
        if self._catalog is None:
            from backend.machines.seed_catalog import seed_machine_catalog
            self._catalog = seed_machine_catalog()
        return self._catalog

    def resolve(
        self,
        op_type: OperationType,
        required_ra_um: float | None = None,
        spindle_interface: str | None = None,
        max_candidates: int = 3,
    ) -> list[MachineCandidateSummary]:
        """Return up to *max_candidates* machines eligible for *op_type*.

        REFERENCE_ONLY=YES on every returned record.
        """
        eligible_types = set(OPERATION_TO_MACHINE_TYPES.get(op_type, ()))
        results: list[tuple[int, MachineCandidateSummary]] = []

        for rec in self._get_catalog():
            m_type = _record_to_machine_type(rec.get("machine_type_code", "") or "")
            if m_type not in eligible_types:
                continue

            # Filter by spindle interface if specified
            if spindle_interface:
                ifaces = rec.get("spindle_interfaces_supported", []) or []
                main_iface = rec.get("spindle_interface") or ""
                if spindle_interface not in ifaces and spindle_interface != main_iface:
                    continue

            score = _suitability(_RecordProxy(rec), op_type, required_ra_um)
            rpm = rec.get("spindle_max_rpm")
            summary = MachineCandidateSummary(
                machine_id=rec.get("stable_id", ""),
                manufacturer=rec.get("manufacturer", ""),
                model=rec.get("model", ""),
                machine_type_code=rec.get("machine_type_code", ""),
                axis_count=rec.get("axis_count", 0) or 0,
                spindle_max_rpm=rpm,
                spindle_interface=rec.get("spindle_interface"),
                supported_processes=tuple(rec.get("supported_processes", [])),
                suitability_score=score,
                rpm_margin_ok=None,  # requires required_rpm to evaluate
                notes=(
                    f"Eligible for {op_type.value}. "
                    "REFERENCE_ONLY — verify against actual shop floor."
                ),
            )
            results.append((score, summary))

        results.sort(key=lambda x: (-x[0], x[1].machine_id))
        return [s for _, s in results[:max_candidates]]

    def resolve_for_route(
        self,
        op_types: list[OperationType],
        required_ra_um: float | None = None,
        spindle_interface: str | None = None,
        max_candidates: int = 3,
    ) -> list[MachineCandidateSummary]:
        """Machines that support ALL op_types in the route."""
        if not op_types:
            return []
        candidates_per_op: list[set[str]] = []
        for op in op_types:
            cands = self.resolve(op, required_ra_um, spindle_interface, max_candidates=20)
            candidates_per_op.append({c.machine_id for c in cands})
        eligible_ids = candidates_per_op[0]
        for s in candidates_per_op[1:]:
            eligible_ids = eligible_ids & s

        all_cands = self.resolve(op_types[0], required_ra_um, spindle_interface, max_candidates=20)
        filtered = [c for c in all_cands if c.machine_id in eligible_ids]
        return filtered[:max_candidates]


class _RecordProxy:
    """Thin proxy to access dict records as attribute access."""

    def __init__(self, d: dict) -> None:
        self._d = d

    def __getattr__(self, name: str):
        return self._d.get(name)
