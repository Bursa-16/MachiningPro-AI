"""Tests for drawing_intelligence.material_bridge (EPIC_04 Phase 2)."""

import pytest

from backend.drawing_intelligence.material_bridge import (
    MaterialBridge,
    MaterialBridgeResult,
    resolve_material,
)


class TestMaterialBridgeResult:
    def test_resolved_when_id_set(self):
        r = MaterialBridgeResult(
            raw_designation="42CrMo4",
            matched_material_id="mat-001",
            matched_designation="42CrMo4",
            iso_group="P",
            confidence="EXACT",
            search_query_used="42CRMO4",
            catalog_size=19,
        )
        assert r.resolved

    def test_not_resolved_when_id_none(self):
        r = MaterialBridgeResult(
            raw_designation="UNK",
            matched_material_id=None,
            matched_designation=None,
            iso_group=None,
            confidence="NONE",
            search_query_used="UNK",
            catalog_size=19,
        )
        assert not r.resolved


class TestMaterialBridgeLogic:
    def test_resolve_normalises_case(self):
        bridge = MaterialBridge()
        r = bridge.resolve("  42crMo4  ")
        # Normalised uppercase query used
        assert r.search_query_used.strip() == "42CRMO4"

    def test_unknown_material_returns_none_confidence(self):
        bridge = MaterialBridge()
        r = bridge.resolve("XYZXYZ_NO_SUCH_MATERIAL_9999")
        assert r.confidence == "NONE"
        assert r.matched_material_id is None
        # FABRICATED_MATERIAL=NO — nothing fabricated
        assert r.matched_designation is None

    def test_catalog_size_positive(self):
        bridge = MaterialBridge()
        r = bridge.resolve("Steel")
        assert r.catalog_size > 0

    def test_resolve_material_convenience(self):
        r = resolve_material("42CrMo4")
        # Must be a MaterialBridgeResult
        assert isinstance(r, MaterialBridgeResult)

    def test_partial_match_is_not_exact(self):
        bridge = MaterialBridge()
        # "steel" is likely a partial match but not an exact material designation
        r = bridge.resolve("steel")
        assert r.confidence in ("PARTIAL", "NONE")
        # Whatever the result, it must not fabricate
        if r.confidence == "NONE":
            assert r.matched_material_id is None

    def test_no_fabricated_iso_group(self):
        bridge = MaterialBridge()
        r = bridge.resolve("XYZXYZ_NO_SUCH_MATERIAL_9999")
        # No match → iso_group must be None, not fabricated
        assert r.iso_group is None
