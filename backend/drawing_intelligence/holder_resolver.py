"""Holder Candidate Resolver — EPIC_04E Phase 2.

Queries ToolHolderCatalogRecord to find holders compatible with a given
machine interface and tool interface.  REFERENCE_ONLY.

ROUTE_HOLDER_CANDIDATES_IMPLEMENTED=YES
"""

from __future__ import annotations

from backend.domain.enums import OperationType
from backend.drawing_intelligence.route_domain import HolderCandidateSummary

__all__ = ["HolderCandidateResolver"]


def _score_holder(rec_d: dict, op_type: OperationType, max_rpm_required: int | None) -> int:
    score = 50
    supp = [s.lower() for s in (rec_d.get("supported_processes") or [])]
    if op_type.value in supp:
        score += 20
    # RPM check
    if max_rpm_required and rec_d.get("max_rpm"):
        if rec_d["max_rpm"] >= max_rpm_required:
            score += 15
        else:
            score -= 15
    # Through-coolant bonus for drilling/boring
    if op_type in (OperationType.DRILLING, OperationType.BORING, OperationType.REAMING):
        if rec_d.get("through_coolant"):
            score += 10
    return max(0, min(100, score))


class HolderCandidateResolver:
    """Resolves (machine_interface, tool_interface) → list[HolderCandidateSummary].

    ROUTE_HOLDER_CANDIDATES_IMPLEMENTED=YES
    """

    def __init__(self) -> None:
        self._catalog: list | None = None

    def _get_catalog(self):
        if self._catalog is None:
            from backend.tool_holders.seed_catalog import get_catalog
            self._catalog = get_catalog()
        return self._catalog

    def resolve(
        self,
        machine_interface: str | None,
        op_type: OperationType | None = None,
        max_rpm_required: int | None = None,
        max_candidates: int = 2,
    ) -> list[HolderCandidateSummary]:
        """Return holders compatible with *machine_interface*.

        When machine_interface is None, returns an empty list (REFERENCE_ONLY,
        not fabricated matches).
        """
        if machine_interface is None:
            return []

        results: list[tuple[int, HolderCandidateSummary]] = []
        for rec in self._get_catalog():
            rec_d = rec.model_dump() if hasattr(rec, "model_dump") else dict(rec)
            iface_key = (rec_d.get("machine_interface_key") or "").upper()
            iface = (rec_d.get("machine_interface") or "").upper()
            target = machine_interface.upper()
            if target not in (iface_key, iface):
                continue

            score = _score_holder(rec_d, op_type or OperationType.OTHER, max_rpm_required)
            summary = HolderCandidateSummary(
                holder_id=rec_d.get("stable_id", ""),
                manufacturer=rec_d.get("manufacturer", ""),
                product_name=rec_d.get("product_name", ""),
                holder_category=rec_d.get("holder_category", ""),
                machine_interface_key=rec_d.get("machine_interface_key", ""),
                tool_interface_key=rec_d.get("tool_interface_key", ""),
                clamping_range_min_mm=rec_d.get("clamping_range_min_mm"),
                clamping_range_max_mm=rec_d.get("clamping_range_max_mm"),
                max_rpm=rec_d.get("max_rpm"),
                suitability_score=score,
                notes=(
                    f"Compatible with {machine_interface} interface. "
                    "REFERENCE_ONLY — verify with holder manufacturer."
                ),
            )
            results.append((score, summary))

        results.sort(key=lambda x: (-x[0], x[1].holder_id))
        return [s for _, s in results[:max_candidates]]
