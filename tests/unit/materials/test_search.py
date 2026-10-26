"""Tests for MaterialCatalog search and filtering (EPIC_01)."""

from __future__ import annotations

import pytest

from backend.materials.catalog import MaterialCatalog


def _build_catalog() -> MaterialCatalog:
    from backend.materials.seed_catalog import seed_material_catalog
    cat = MaterialCatalog()
    cat.load(seed_material_catalog())
    return cat


class TestMaterialCatalogSearch:
    def test_list_items_returns_all(self):
        cat = _build_catalog()
        items = cat.list_items()
        assert len(items) >= 1

    def test_search_by_designation(self):
        cat = _build_catalog()
        results = cat.search(query="C45")
        ids = [r.material_id for r in results]
        assert "P-C45" in ids

    def test_search_by_aisi(self):
        cat = _build_catalog()
        results = cat.search(query="4140")
        ids = [r.material_id for r in results]
        assert "P-42CrMo4" in ids

    def test_filter_by_iso_group_p(self):
        cat = _build_catalog()
        results = cat.search(iso_group="P")
        for r in results:
            assert r.iso_group == "P"

    def test_filter_by_iso_group_s(self):
        cat = _build_catalog()
        results = cat.search(iso_group="S")
        for r in results:
            assert r.iso_group == "S"
        assert len(results) >= 2

    def test_filter_case_insensitive_iso(self):
        cat = _build_catalog()
        lower = cat.search(iso_group="p")
        upper = cat.search(iso_group="P")
        assert len(lower) == len(upper)

    def test_get_known_material(self):
        cat = _build_catalog()
        rec = cat.get("P-C45")
        assert rec is not None
        assert rec.designation == "C45"

    def test_get_unknown_returns_none(self):
        cat = _build_catalog()
        assert cat.get("NOT_EXIST") is None

    def test_limit_respected(self):
        cat = _build_catalog()
        results = cat.search(limit=2)
        assert len(results) <= 2

    def test_offset_paginates(self):
        cat = _build_catalog()
        page1 = cat.search(limit=3, offset=0)
        page2 = cat.search(limit=3, offset=3)
        ids1 = [r.material_id for r in page1]
        ids2 = [r.material_id for r in page2]
        assert len(set(ids1) & set(ids2)) == 0 or len(page2) == 0


class TestMaterialCatalogSummary:
    def test_summary_material_count(self):
        cat = _build_catalog()
        s = cat.summary()
        assert s.material_count == len(cat.list_items())

    def test_summary_has_iso_counts(self):
        cat = _build_catalog()
        s = cat.summary()
        assert "P" in s.iso_group_counts
        assert s.iso_group_counts["P"] >= 1

    def test_iso_groups_returns_six(self):
        cat = _build_catalog()
        groups = cat.iso_groups()
        codes = [g["code"] for g in groups]
        for code in ("P", "M", "K", "N", "S", "H"):
            assert code in codes


class TestMaterialCatalogDuplicateHandling:
    def test_duplicate_id_skipped(self):
        from backend.materials.seed_catalog import seed_material_catalog
        cat = MaterialCatalog()
        records = seed_material_catalog()[:3]
        dup = dict(records[0])  # duplicate the first record
        cat.load(records + [dup])
        # Catalog should have records length not records+1
        assert len(cat.list_items()) == len(records)
