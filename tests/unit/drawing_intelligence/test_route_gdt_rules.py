"""Tests for R-RT-GDT-001 through R-RT-GDT-007 route rules (EPIC_04B Phase 2)."""

import pytest
from decimal import Decimal

from backend.drawing_intelligence.route_generator import generate_routes
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
from backend.drawing_intelligence.feature_recognition import RecognizedFeature
from backend.domain.enums import FeatureType


def _drf(label="A"):
    return DatumReferenceFrame(
        primary=DatumReference(label=label, precedence=1, modifier=GdtModifier.NONE),
        secondary=None, tertiary=None,
    )


def _fcf(char, tol="0.1", modifier=GdtModifier.NONE, datum=None):
    return ExpandedFeatureControlFrame(
        characteristic=char, tolerance_value=Decimal(tol),
        tolerance_unit="mm", diameter_zone=True,
        modifier=modifier, datum_frame=datum,
    )


def _geom(req_id, char, tol="0.1", modifier=GdtModifier.NONE, feature_ref="F-001", datum=None):
    return GeometricRequirement(
        req_id=req_id, feature_ref=feature_ref,
        fcf=_fcf(char, tol, modifier, datum),
    )


def _req_set(*geom_reqs):
    return DrawingRequirementSet(
        source_id="SRC-001", drawing_number="DWG-001", revision="A",
        extraction_status=RequirementExtractionStatus.COMPLETE,
        dimensional=(), geometric=tuple(geom_reqs), surface_finish=(), threads=(),
        material=None, heat_treatment=(),
    )


def _recognized_hole(feature_id="F-001"):
    from unittest.mock import MagicMock
    from backend.domain.feature import Feature
    feat = MagicMock(spec=Feature)
    feat.feature_id = feature_id
    feat.feature_type = FeatureType.HOLE
    rf = MagicMock(spec=RecognizedFeature)
    rf.feature = feat
    rf.source_req_ids = (feature_id,)
    return rf


class TestRRTGDT001TightPosition:
    def test_tight_position_generates_r001_warning(self):
        geom = _geom("REQ-001", GdtCharacteristic.POSITION, tol="0.025",
                     datum=_drf("A"), feature_ref="F-001")
        result = generate_routes(_recognized_hole(), _req_set(geom))
        all_warnings = " ".join(result.warnings)
        assert "R-RT-GDT-001" in all_warnings

    def test_very_tight_position_jig_boring_note(self):
        geom = _geom("REQ-001", GdtCharacteristic.POSITION, tol="0.010",
                     datum=_drf("A"), feature_ref="F-001")
        result = generate_routes(_recognized_hole(), _req_set(geom))
        all_warnings = " ".join(result.warnings)
        assert "jig boring" in all_warnings or "boring" in all_warnings.lower()

    def test_loose_position_no_r001_warning(self):
        geom = _geom("REQ-001", GdtCharacteristic.POSITION, tol="0.500",
                     datum=_drf("A"), feature_ref="F-001")
        result = generate_routes(_recognized_hole(), _req_set(geom))
        all_warnings = " ".join(result.warnings)
        assert "R-RT-GDT-001" not in all_warnings


class TestRRTGDT002Perpendicularity:
    def test_tight_perp_generates_r002_warning(self):
        geom = _geom("REQ-002", GdtCharacteristic.PERPENDICULARITY, tol="0.020",
                     datum=_drf("A"), feature_ref="F-001")
        result = generate_routes(_recognized_hole(), _req_set(geom))
        assert "R-RT-GDT-002" in " ".join(result.warnings)

    def test_loose_perp_no_r002_warning(self):
        geom = _geom("REQ-002", GdtCharacteristic.PERPENDICULARITY, tol="0.200",
                     datum=_drf("A"), feature_ref="F-001")
        result = generate_routes(_recognized_hole(), _req_set(geom))
        assert "R-RT-GDT-002" not in " ".join(result.warnings)


class TestRRTGDT003Cylindricity:
    def test_cylindricity_generates_r003_warning(self):
        geom = _geom("REQ-003", GdtCharacteristic.CYLINDRICITY, tol="0.010",
                     feature_ref="F-001")
        result = generate_routes(_recognized_hole(), _req_set(geom))
        assert "R-RT-GDT-003" in " ".join(result.warnings)


class TestRRTGDT004Runout:
    def test_circular_runout_r004(self):
        geom = _geom("REQ-004", GdtCharacteristic.CIRCULAR_RUNOUT, tol="0.015",
                     datum=_drf("A"), feature_ref="F-001")
        result = generate_routes(_recognized_hole(), _req_set(geom))
        assert "R-RT-GDT-004" in " ".join(result.warnings)

    def test_total_runout_r004(self):
        geom = _geom("REQ-004", GdtCharacteristic.TOTAL_RUNOUT, tol="0.015",
                     datum=_drf("A"), feature_ref="F-001")
        result = generate_routes(_recognized_hole(), _req_set(geom))
        assert "R-RT-GDT-004" in " ".join(result.warnings)
        assert "one chucking" in " ".join(result.warnings)


class TestRRTGDT005Profile:
    def test_profile_of_surface_r005(self):
        geom = _geom("REQ-005", GdtCharacteristic.PROFILE_OF_A_SURFACE, tol="0.100",
                     datum=_drf("A"), feature_ref="F-001")
        result = generate_routes(_recognized_hole(), _req_set(geom))
        assert "R-RT-GDT-005" in " ".join(result.warnings)


class TestRRTGDT006ModifierInspection:
    def test_mmc_generates_r006_warning(self):
        geom = _geom("REQ-006", GdtCharacteristic.POSITION, tol="0.100",
                     modifier=GdtModifier.MMC, datum=_drf("A"), feature_ref="F-001")
        result = generate_routes(_recognized_hole(), _req_set(geom))
        assert "R-RT-GDT-006" in " ".join(result.warnings)

    def test_lmc_generates_r006_warning(self):
        geom = _geom("REQ-006", GdtCharacteristic.POSITION, tol="0.100",
                     modifier=GdtModifier.LMC, datum=_drf("A"), feature_ref="F-001")
        result = generate_routes(_recognized_hole(), _req_set(geom))
        assert "R-RT-GDT-006" in " ".join(result.warnings)

    def test_rfs_no_r006_warning(self):
        geom = _geom("REQ-006", GdtCharacteristic.POSITION, tol="0.100",
                     modifier=GdtModifier.NONE, datum=_drf("A"), feature_ref="F-001")
        result = generate_routes(_recognized_hole(), _req_set(geom))
        assert "R-RT-GDT-006" not in " ".join(result.warnings)
