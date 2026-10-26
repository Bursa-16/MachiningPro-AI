"""In-memory MaterialCatalog — seeded from seed_catalog at import time.

MISSING_VALUE_AS_ZERO=NO
FABRICATED_MATERIAL_PROPERTY=NO
"""

from __future__ import annotations

import logging

from backend.materials.models import (
    MaterialListItem,
    MaterialRecord,
    MaterialSummary,
)

logger = logging.getLogger(__name__)

_ISO_GROUP_LABELS = {
    "P": "P — Steels",
    "M": "M — Stainless Steels",
    "K": "K — Cast Irons",
    "N": "N — Non-Ferrous",
    "S": "S — Superalloys & Titanium",
    "H": "H — Hardened Materials",
}

_ISO_SUBGROUP_LABELS = {
    "P_STEEL": "Steel",
    "M_STAINLESS": "Stainless Steel",
    "K_CAST_IRON": "Cast Iron",
    "N_ALUMINUM": "Aluminum Alloy",
    "N_COPPER": "Copper Alloy",
    "S_TITANIUM": "Titanium Alloy",
    "S_NICKEL_HRSA": "Nickel HRSA (e.g. Inconel)",
    "H_HARDENED": "Hardened Steel",
    "UNSPECIFIED": "Unspecified",
}

_FAMILY_LABELS = {
    "steel": "Steel",
    "stainless_steel": "Stainless Steel",
    "cast_iron": "Cast Iron",
    "aluminum": "Aluminum",
    "copper_alloy": "Copper Alloy",
    "titanium": "Titanium",
    "nickel_alloy": "Nickel Alloy",
    "graphite": "Graphite",
    "ceramic_material": "Engineering Ceramic",
    "plastic": "Plastic",
    "composite": "Composite",
    "other": "Other",
}


class MaterialCatalog:
    """Thread-safe in-memory catalog (read-only after build)."""

    def __init__(self) -> None:
        self._records: dict[str, MaterialRecord] = {}

    def load(self, records: list[dict]) -> None:
        seen: set[str] = set()
        for raw in records:
            mid = raw.get("material_id", "")
            if not mid:
                logger.warning("Material record missing material_id — skipped")
                continue
            if mid in seen:
                logger.warning("Duplicate material_id during seeding: %r — skipped", mid)
                continue
            seen.add(mid)
            self._records[mid] = MaterialRecord(**raw)
        logger.info("Material catalog loaded: %d records", len(self._records))

    def get(self, material_id: str) -> MaterialRecord | None:
        return self._records.get(material_id)

    def list_items(self) -> list[MaterialListItem]:
        return [self._to_list_item(r) for r in self._records.values()]

    def search(
        self,
        query: str | None = None,
        iso_group: str | None = None,
        family: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MaterialListItem]:
        results = list(self._records.values())

        if iso_group:
            results = [r for r in results if r.iso_group == iso_group.upper()]

        if family:
            fl = family.lower()
            results = [r for r in results if r.material_family.lower() == fl]

        if query:
            ql = query.lower()
            filtered = []
            for r in results:
                text = " ".join([
                    r.designation,
                    r.werkstoff_nr or "",
                    r.standard_en or "",
                    r.standard_din or "",
                    r.standard_aisi or "",
                    r.standard_uns or "",
                ] + r.aliases).lower()
                if ql in text:
                    filtered.append(r)
            results = filtered

        results.sort(key=lambda r: (r.iso_group, r.designation))
        return [self._to_list_item(r) for r in results[offset: offset + limit]]

    def summary(self) -> MaterialSummary:
        iso_counts: dict[str, int] = {}
        family_counts: dict[str, int] = {}
        for r in self._records.values():
            iso_counts[r.iso_group] = iso_counts.get(r.iso_group, 0) + 1
            family_counts[r.material_family] = family_counts.get(r.material_family, 0) + 1
        return MaterialSummary(
            material_count=len(self._records),
            iso_group_counts=iso_counts,
            family_counts=family_counts,
            source_title="MachiningPro Material Intelligence Foundation (EPIC_01 MVP)",
            evidence_note=(
                "Mechanical properties from EN/DIN/ASTM standards. "
                "Cutting envelopes are REFERENCE_ONLY general industry data. "
                "Tool compatibility from Programlar Sandvik synthesis (REFERENCE_ONLY). "
                "Validate all values with manufacturer data before production use."
            ),
        )

    def iso_groups(self) -> list[dict]:
        from backend.materials.models import IsoGroupInfo
        iso_group_info = [
            IsoGroupInfo(code="P", label="Steels", description="Unalloyed and low-alloy steels, long-chipping", color_hint="blue"),
            IsoGroupInfo(code="M", label="Stainless Steels", description="Austenitic, ferritic, duplex stainless steels", color_hint="purple"),
            IsoGroupInfo(code="K", label="Cast Irons", description="Grey cast iron, nodular cast iron, malleable cast iron", color_hint="green"),
            IsoGroupInfo(code="N", label="Non-Ferrous", description="Aluminum, copper, magnesium and other non-ferrous alloys", color_hint="orange"),
            IsoGroupInfo(code="S", label="Superalloys & Titanium", description="Heat-resistant superalloys and titanium alloys — split S_TITANIUM / S_NICKEL_HRSA", color_hint="red"),
            IsoGroupInfo(code="H", label="Hardened Materials", description="Hardened steels, hard cast irons, chilled cast iron", color_hint="gray"),
        ]
        return [i.model_dump() for i in iso_group_info]

    @staticmethod
    def _to_list_item(r: MaterialRecord) -> MaterialListItem:
        return MaterialListItem(
            material_id=r.material_id,
            designation=r.designation,
            werkstoff_nr=r.werkstoff_nr,
            standard_aisi=r.standard_aisi,
            iso_group=r.iso_group,
            iso_subgroup=r.iso_subgroup,
            material_family=r.material_family,
            data_confidence=r.data_confidence,
            has_conditions=len(r.conditions) > 0,
            has_machinability=r.machinability is not None,
            has_tool_compat=len(r.tool_compatibility) > 0,
            has_cutting_refs=len(r.cutting_references) > 0,
            aliases=r.aliases,
        )


# Singleton catalog — built at import time (same pattern as MachineCatalog)
_catalog: MaterialCatalog | None = None


def get_catalog() -> MaterialCatalog:
    global _catalog
    if _catalog is None:
        from backend.materials.seed_catalog import seed_material_catalog
        _catalog = MaterialCatalog()
        _catalog.load(seed_material_catalog())
    return _catalog
