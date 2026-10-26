"""Tests for drawing_intelligence.feature_recognition (EPIC_04 Phase 2)."""

import pytest
from decimal import Decimal

from backend.domain.enums import FeatureType
from backend.drawing_intelligence.feature_recognition import (
    FeatureRecognitionEngine,
    recognize_features,
)
from backend.drawing_intelligence.requirements import (
    DatumReference,
    DatumReferenceFrame,
    DimensionalRequirement,
    DrawingRequirementSet,
    ExpandedFeatureControlFrame,
    GdtCharacteristic,
    GeometricRequirement,
    RequirementExtractionStatus,
    SurfaceFinishRequirement,
    ThreadRequirement,
)


def _make_req_set(**kwargs):
    defaults = {
        "source_id": "test-dwg",
        "drawing_number": None,
        "revision": None,
        "extraction_status": RequirementExtractionStatus.PARTIAL,
        "dimensional": (),
        "geometric": (),
        "surface_finish": (),
        "threads": (),
        "material": None,
        "heat_treatment": (),
    }
    defaults.update(kwargs)
    return DrawingRequirementSet(**defaults)


def _dim(req_id, dim_type, nominal=10.0, notes=None):
    return DimensionalRequirement(
        req_id=req_id,
        dimension_type=dim_type,
        nominal_value=Decimal(str(nominal)),
        unit="mm",
        notes=notes,
    )


def _geom(req_id, char, tol=0.05):
    fcf = ExpandedFeatureControlFrame(
        characteristic=char,
        tolerance_value=Decimal(str(tol)),
        tolerance_unit="mm",
    )
    return GeometricRequirement(req_id=req_id, fcf=fcf)


class TestThreadRecognition:
    def test_single_thread(self):
        t = ThreadRequirement(req_id="T-0001", designation="M12x1.75")
        rs = _make_req_set(threads=(t,))
        result = recognize_features(rs)
        assert result.feature_count == 1
        assert result.features[0].feature.feature_type == FeatureType.THREAD
        assert result.features[0].recognition_rule == "R-FR-001"

    def test_thread_with_diameter(self):
        t = ThreadRequirement(req_id="T-0001", designation="M12x1.75",
                               nominal_diameter_mm=Decimal("12"))
        rs = _make_req_set(threads=(t,))
        result = recognize_features(rs)
        feat = result.features[0].feature
        assert "nominal_diameter" in feat.dimensions

    def test_multiple_threads(self):
        threads = tuple(
            ThreadRequirement(req_id=f"T-{i:04d}", designation=f"M{6+i*2}x1")
            for i in range(3)
        )
        rs = _make_req_set(threads=threads)
        result = recognize_features(rs)
        assert result.feature_count == 3
        assert all(
            rf.feature.feature_type == FeatureType.THREAD
            for rf in result.features
        )


class TestHoleRecognition:
    def test_diameter_is_hole(self):
        dim = _dim("D-0001", "DIAMETER", nominal=20.0)
        rs = _make_req_set(dimensional=(dim,))
        result = recognize_features(rs)
        assert result.feature_count == 1
        assert result.features[0].feature.feature_type == FeatureType.HOLE
        assert result.features[0].recognition_rule == "R-FR-002"

    def test_diameter_with_depth_is_hole_with_depth(self):
        dim = _dim("D-0001", "DIAMETER", 15.0)
        depth = _dim("D-0002", "DEPTH", 30.0)
        rs = _make_req_set(dimensional=(dim, depth))
        result = recognize_features(rs)
        hole = result.features[0].feature
        assert hole.feature_type == FeatureType.HOLE
        assert "depth" in hole.dimensions

    def test_thread_before_hole_consumes_thread(self):
        t = ThreadRequirement(req_id="T-0001", designation="M10x1.5")
        dim = _dim("D-0001", "DIAMETER", 10.0)
        rs = _make_req_set(threads=(t,), dimensional=(dim,))
        result = recognize_features(rs)
        types = [rf.feature.feature_type for rf in result.features]
        assert FeatureType.THREAD in types


class TestSlotPocketRecognition:
    def test_slot_keyword_in_notes(self):
        dim = _dim("D-0001", "WIDTH", 8.0, notes="slot 8mm")
        rs = _make_req_set(dimensional=(dim,))
        result = recognize_features(rs)
        assert result.features[0].feature.feature_type == FeatureType.SLOT
        assert result.features[0].recognition_rule == "R-FR-003"

    def test_slot_keyword_in_dimension_type(self):
        dim = _dim("D-0001", "SLOT_WIDTH", 6.0)
        rs = _make_req_set(dimensional=(dim,))
        result = recognize_features(rs)
        assert result.features[0].feature.feature_type == FeatureType.SLOT

    def test_pocket_keyword(self):
        dim = _dim("D-0001", "POCKET_WIDTH", 20.0)
        rs = _make_req_set(dimensional=(dim,))
        result = recognize_features(rs)
        assert result.features[0].feature.feature_type == FeatureType.POCKET
        assert result.features[0].recognition_rule == "R-FR-004"


class TestChamferFilletGrooveRecognition:
    def test_chamfer_keyword_in_notes(self):
        dim = _dim("D-0001", "SIZE", 2.0, notes="chamfer 2mm")
        rs = _make_req_set(dimensional=(dim,))
        result = recognize_features(rs)
        assert result.features[0].feature.feature_type == FeatureType.CHAMFER

    def test_fillet_via_radius_type(self):
        dim = _dim("D-0001", "RADIUS", 3.0)
        rs = _make_req_set(dimensional=(dim,))
        result = recognize_features(rs)
        assert result.features[0].feature.feature_type == FeatureType.FILLET

    def test_groove_keyword(self):
        dim = _dim("D-0001", "GROOVE_WIDTH", 4.0)
        rs = _make_req_set(dimensional=(dim,))
        result = recognize_features(rs)
        assert result.features[0].feature.feature_type == FeatureType.GROOVE


class TestGdtRecognition:
    def test_circularity_is_cylindrical_surface(self):
        geom = _geom("G-0001", GdtCharacteristic.CIRCULARITY, 0.01)
        rs = _make_req_set(geometric=(geom,))
        result = recognize_features(rs)
        assert result.features[0].feature.feature_type == FeatureType.CYLINDRICAL_SURFACE
        assert result.features[0].recognition_rule == "R-FR-005"

    def test_cylindricity_is_cylindrical_surface(self):
        geom = _geom("G-0001", GdtCharacteristic.CYLINDRICITY, 0.02)
        rs = _make_req_set(geometric=(geom,))
        result = recognize_features(rs)
        assert result.features[0].feature.feature_type == FeatureType.CYLINDRICAL_SURFACE

    def test_flatness_is_planar_face(self):
        geom = _geom("G-0001", GdtCharacteristic.FLATNESS, 0.05)
        rs = _make_req_set(geometric=(geom,))
        result = recognize_features(rs)
        assert result.features[0].feature.feature_type == FeatureType.PLANAR_FACE
        assert result.features[0].recognition_rule == "R-FR-006"

    def test_perpendicularity_is_planar_face(self):
        geom = _geom("G-0001", GdtCharacteristic.PERPENDICULARITY, 0.03)
        rs = _make_req_set(geometric=(geom,))
        result = recognize_features(rs)
        assert result.features[0].feature.feature_type == FeatureType.PLANAR_FACE


class TestUnrecognized:
    def test_no_requirements_no_features(self):
        rs = _make_req_set()
        result = recognize_features(rs)
        assert result.feature_count == 0
        assert len(result.unrecognized_req_ids) == 0

    def test_surface_finish_only_is_unrecognized(self):
        sf = SurfaceFinishRequirement(req_id="SF-0001", ra_um=Decimal("1.6"))
        rs = _make_req_set(surface_finish=(sf,))
        result = recognize_features(rs)
        # SF alone doesn't generate a feature
        assert result.feature_count == 0
        assert "SF-0001" in result.unrecognized_req_ids


class TestProvenanceNotFabricated:
    def test_provenance_is_deterministic_calculation(self):
        from backend.domain.enums import ProvenanceType
        dim = _dim("D-0001", "DIAMETER", 10.0)
        rs = _make_req_set(dimensional=(dim,))
        result = recognize_features(rs)
        feat = result.features[0].feature
        assert feat.provenance.source_type == ProvenanceType.DETERMINISTIC_CALCULATION
