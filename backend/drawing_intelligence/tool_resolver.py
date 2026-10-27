"""Tool Candidate Resolver — EPIC_04E Phase 2.

Queries CuttingToolCatalogRecord to find tools eligible for a given
OperationType / FeatureType.  REFERENCE_ONLY — never designates a winner.

ROUTE_TOOL_CANDIDATES_IMPLEMENTED=YES
FABRICATED_TOOL_COMPATIBILITY=NO
"""

from __future__ import annotations

from backend.domain.enums import OperationType
from backend.drawing_intelligence.route_domain import ToolCandidateSummary

__all__ = ["ToolCandidateResolver"]

_OP_TO_TOOL_TYPE_CODE: dict[OperationType, list[str]] = {
    OperationType.DRILLING:  ["DRILL"],
    OperationType.MILLING:   ["END_MILL", "FACE_MILL", "FACE_MILL_INSERT"],
    OperationType.FACING:    ["FACE_MILL", "FACE_MILL_INSERT"],
    OperationType.BORING:    ["BORING_BAR", "BORING_INSERT"],
    OperationType.REAMING:   ["REAMER"],
    OperationType.TAPPING:   ["TAP"],
    OperationType.THREADING: ["THREAD_MILL"],
    OperationType.TURNING:   ["TURNING_INSERT"],
    OperationType.HONING:    [],      # external — no catalog entries expected
    OperationType.LAPPING:   [],
    OperationType.GRINDING:  ["GRINDING_WHEEL"],
    OperationType.DEBURRING: ["DEBURRING_TOOL"],
    OperationType.INSPECTION: [],
}


def _score_tool(
    rec, op_type: OperationType, diameter_mm: float | None, iso_group: str | None
) -> int:
    score = 50
    op_codes = set(_OP_TO_TOOL_TYPE_CODE.get(op_type, []))
    rec_code = (rec.get("tool_type_code") or "").upper()
    if rec_code in op_codes:
        score += 30
    # Check supported_operations field
    supp = [s.lower() for s in (rec.get("supported_operations") or [])]
    if op_type.value in supp:
        score += 10
    # Material group match
    if iso_group:
        groups = [g.upper() for g in (rec.get("iso_material_groups") or [])]
        if iso_group.upper() in groups:
            score += 10
    # Diameter proximity
    if diameter_mm and rec.get("cutting_diameter_mm"):
        diff = abs(rec["cutting_diameter_mm"] - diameter_mm)
        if diff <= 1.0:
            score += 10
        elif diff <= 5.0:
            score += 5
    return max(0, min(100, score))


class ToolCandidateResolver:
    """Resolves OperationType → list[ToolCandidateSummary] from the catalog.

    ROUTE_TOOL_CANDIDATES_IMPLEMENTED=YES
    FABRICATED_TOOL_COMPATIBILITY=NO
    """

    def __init__(self) -> None:
        self._catalog: list | None = None

    def _get_catalog(self):
        if self._catalog is None:
            from backend.cutting_tools.seed_catalog import get_catalog
            self._catalog = get_catalog()
        return self._catalog

    def resolve(
        self,
        op_type: OperationType,
        feature_type: str | None = None,
        diameter_mm: float | None = None,
        iso_group: str | None = None,
        max_candidates: int = 3,
    ) -> list[ToolCandidateSummary]:
        """Return up to *max_candidates* tools eligible for *op_type*.

        Returns [] for operations with no catalog tool (honing, lapping).
        REFERENCE_ONLY=YES on every record.
        """
        op_codes = set(_OP_TO_TOOL_TYPE_CODE.get(op_type, []))
        if not op_codes:
            return []

        results: list[tuple[int, ToolCandidateSummary]] = []

        for rec in self._get_catalog():
            rec_d = rec.model_dump() if hasattr(rec, "model_dump") else dict(rec)
            rec_code = (rec_d.get("tool_type_code") or "").upper()
            supp = [s.lower() for s in (rec_d.get("supported_operations") or [])]
            if rec_code not in op_codes and op_type.value not in supp:
                continue

            score = _score_tool(rec_d, op_type, diameter_mm, iso_group)
            summary = ToolCandidateSummary(
                tool_id=rec_d.get("stable_id", ""),
                manufacturer=rec_d.get("manufacturer", ""),
                product_name=rec_d.get("product_name", ""),
                tool_type_code=rec_d.get("tool_type_code", "") or "",
                supported_operations=tuple(rec_d.get("supported_operations", [])),
                iso_material_groups=tuple(rec_d.get("iso_material_groups", [])),
                cutting_diameter_mm=rec_d.get("cutting_diameter_mm"),
                overall_length_mm=rec_d.get("overall_length_mm"),
                suitability_score=score,
                notes=(
                    f"Eligible for {op_type.value}. "
                    "REFERENCE_ONLY — verify with manufacturer."
                ),
            )
            results.append((score, summary))

        results.sort(key=lambda x: (-x[0], x[1].tool_id))
        return [s for _, s in results[:max_candidates]]
