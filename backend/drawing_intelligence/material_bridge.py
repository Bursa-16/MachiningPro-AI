"""Material Bridge (EPIC_04 Phase 2).

Resolves DrawingMaterialNote / MaterialRequirement → MaterialRecord
from the MaterialCatalog.

FABRICATED_CUTTING_PARAMETER=NO
FABRICATED_MACHINE_COMPATIBILITY=NO
Unknown material designation → NONE match confidence, never fabricated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.drawing_intelligence.requirements import MaterialRequirement

__all__ = [
    "MaterialBridgeResult",
    "MaterialBridge",
    "resolve_material",
]


@dataclass(frozen=True, slots=True)
class MaterialBridgeResult:
    """Outcome of a material resolution attempt."""

    raw_designation: str
    matched_material_id: str | None
    matched_designation: str | None
    iso_group: str | None
    confidence: str            # "EXACT" | "PARTIAL" | "NONE"
    search_query_used: str
    catalog_size: int

    @property
    def resolved(self) -> bool:
        return self.matched_material_id is not None


class MaterialBridge:
    """Resolves a raw material designation string against the MaterialCatalog.

    Strategy:
    1. Exact match on designation / aliases.
    2. Partial match on whitespace-normalised tokens.
    3. NONE — returned with match_confidence=NONE, never fabricated.
    """

    def __init__(self) -> None:
        self._catalog = None  # lazy load

    def _get_catalog(self):
        if self._catalog is None:
            from backend.materials.catalog import get_catalog
            self._catalog = get_catalog()
        return self._catalog

    def resolve(self, raw_designation: str) -> MaterialBridgeResult:
        cat = self._get_catalog()
        items = cat.list_items()
        query = self._normalise(raw_designation)

        # 1. Exact designation match (case-insensitive)
        for item in items:
            if self._normalise(item.designation) == query:
                return MaterialBridgeResult(
                    raw_designation=raw_designation,
                    matched_material_id=item.material_id,
                    matched_designation=item.designation,
                    iso_group=item.iso_group if isinstance(item.iso_group, str) else (item.iso_group.value if item.iso_group else None),
                    confidence="EXACT",
                    search_query_used=query,
                    catalog_size=len(items),
                )

        # 2. Partial: search the catalog with the raw string
        results = cat.search(raw_designation)
        if results:
            best = results[0]
            return MaterialBridgeResult(
                raw_designation=raw_designation,
                matched_material_id=best.material_id,
                matched_designation=best.designation,
                iso_group=best.iso_group if isinstance(best.iso_group, str) else (best.iso_group.value if best.iso_group else None),
                confidence="PARTIAL",
                search_query_used=query,
                catalog_size=len(items),
            )

        # 3. No match
        return MaterialBridgeResult(
            raw_designation=raw_designation,
            matched_material_id=None,
            matched_designation=None,
            iso_group=None,
            confidence="NONE",
            search_query_used=query,
            catalog_size=len(items),
        )

    def resolve_requirement(self, req: MaterialRequirement) -> MaterialBridgeResult:
        """Convenience: resolve from a MaterialRequirement object."""
        return self.resolve(req.raw_designation)

    @staticmethod
    def _normalise(text: str) -> str:
        return re.sub(r"\s+", " ", text.strip()).upper()


def resolve_material(raw_designation: str) -> MaterialBridgeResult:
    """Convenience function: resolve material without managing a bridge instance."""
    return MaterialBridge().resolve(raw_designation)
