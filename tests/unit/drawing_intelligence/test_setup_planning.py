"""Tests for SetupPlanner (EPIC_04B Phase 2)."""

import pytest
from decimal import Decimal

from backend.drawing_intelligence.setup_planning import build_setup_hints
from backend.drawing_intelligence.requirements import (
    DatumReference,
    DatumReferenceFrame,
    DrawingRequirementSet,
    ExpandedFeatureControlFrame,
    GeometricRequirement,
    GdtCharacteristic,
    GdtModifier,
    RequirementExtractionStatus,
)


def _drf(primary="A", secondary=None, tertiary=None):
    sec = DatumReference(label=secondary, precedence=2, modifier=GdtModifier.NONE) if secondary else None
    ter = DatumReference(label=tertiary, precedence=3, modifier=GdtModifier.NONE) if tertiary else None
    return DatumReferenceFrame(
        primary=DatumReference(label=primary, precedence=1, modifier=GdtModifier.NONE),
        secondary=sec, tertiary=ter,
    )


def _geom_req(req_id, char, tol="0.1", feature_ref=None, datum=None):
    return GeometricRequirement(
        req_id=req_id,
        feature_ref=feature_ref,
        fcf=ExpandedFeatureControlFrame(
            characteristic=char,
            tolerance_value=Decimal(tol), tolerance_unit="mm",
            diameter_zone=True, modifier=GdtModifier.NONE,
            datum_frame=datum,
        ),
    )


def _empty_req_set():
    return DrawingRequirementSet(
        source_id="SRC-001", drawing_number="DWG-001", revision="A",
        extraction_status=RequirementExtractionStatus.COMPLETE,
        dimensional=(), geometric=(), surface_finish=(), threads=(),
        material=None, heat_treatment=(),
    )


def _req_set_with(*geom_reqs):
    return DrawingRequirementSet(
        source_id="SRC-001", drawing_number="DWG-001", revision="A",
        extraction_status=RequirementExtractionStatus.COMPLETE,
        dimensional=(), geometric=tuple(geom_reqs), surface_finish=(), threads=(),
        material=None, heat_treatment=(),
    )


class TestSetupPlannerFromDrf:
    def test_primary_datum_label(self):
        drf = _drf("A")
        hint = build_setup_hints(_empty_req_set(), drf=drf)
        assert hint.primary_datum_label == "A"

    def test_secondary_tertiary_from_drf(self):
        drf = _drf("A", secondary="B", tertiary="C")
        hint = build_setup_hints(_empty_req_set(), drf=drf)
        assert hint.secondary_datum_label == "B"
        assert hint.tertiary_datum_label == "C"

    def test_no_secondary_when_single_datum(self):
        drf = _drf("A")
        hint = build_setup_hints(_empty_req_set(), drf=drf)
        assert hint.secondary_datum_label is None
        assert hint.tertiary_datum_label is None

    def test_setup_notes_contain_label(self):
        drf = _drf("Z")
        hint = build_setup_hints(_empty_req_set(), drf=drf)
        assert "Z" in hint.primary_setup_note


class TestSetupPlannerRunoutSameSetup:
    def test_circular_runout_added_to_same_setup(self):
        geom = _geom_req("REQ-001", GdtCharacteristic.CIRCULAR_RUNOUT,
                         tol="0.010", datum=_drf("A"))
        hint = build_setup_hints(_req_set_with(geom))
        assert "REQ-001" in hint.same_setup_requirements

    def test_total_runout_adds_warning(self):
        geom = _geom_req("REQ-002", GdtCharacteristic.TOTAL_RUNOUT,
                         tol="0.005", datum=_drf("A"))
        hint = build_setup_hints(_req_set_with(geom))
        assert any("one chucking" in w for w in hint.access_warnings)
        assert "REQ-002" in hint.same_setup_requirements

    def test_multiple_runout_features_all_in_same_setup(self):
        g1 = _geom_req("REQ-001", GdtCharacteristic.CIRCULAR_RUNOUT, tol="0.010", datum=_drf("A"))
        g2 = _geom_req("REQ-002", GdtCharacteristic.CIRCULAR_RUNOUT, tol="0.010", datum=_drf("A"))
        hint = build_setup_hints(_req_set_with(g1, g2))
        assert "REQ-001" in hint.same_setup_requirements
        assert "REQ-002" in hint.same_setup_requirements


class TestSetupPlannerTightPosition:
    def test_tight_position_added_to_same_setup(self):
        geom = _geom_req("REQ-003", GdtCharacteristic.POSITION,
                         tol="0.025", datum=_drf("A"))
        hint = build_setup_hints(_req_set_with(geom))
        assert "REQ-003" in hint.same_setup_requirements

    def test_loose_position_not_in_same_setup(self):
        geom = _geom_req("REQ-004", GdtCharacteristic.POSITION,
                         tol="0.500", datum=_drf("A"))
        hint = build_setup_hints(_req_set_with(geom))
        assert "REQ-004" not in hint.same_setup_requirements


class TestSetupPlannerFallbackFromGeom:
    def test_datum_inferred_from_geometric_when_no_drf(self):
        geom = _geom_req("REQ-001", GdtCharacteristic.POSITION,
                         tol="0.100", datum=_drf("X"))
        hint = build_setup_hints(_req_set_with(geom))
        assert hint.primary_datum_label == "X"


class TestSetupPlannerEmptyDrawing:
    def test_empty_drawing_no_setup_requirements(self):
        hint = build_setup_hints(_empty_req_set())
        assert hint.same_setup_requirements == ()
        assert hint.access_warnings == ()
        assert hint.primary_datum_label == "UNKNOWN"
