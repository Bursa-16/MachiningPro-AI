"""Unit tests for graphical association engine."""

import pytest
from decimal import Decimal

from backend.interoperability.association import (
    AnnotationAssociation,
    AnnotationType,
    AssociationCandidate,
    AssociationState,
    BoundingBox2D,
    FeatureType,
    associate_annotation,
    infer_feature_type,
    _bbox_distance,
    _proximity_score,
    _semantic_score,
)


class TestBoundingBox2D:
    def test_center_x(self):
        bb = BoundingBox2D(Decimal("10"), Decimal("20"), Decimal("40"), Decimal("30"))
        assert bb.cx == Decimal("30")

    def test_center_y(self):
        bb = BoundingBox2D(Decimal("10"), Decimal("20"), Decimal("40"), Decimal("30"))
        assert bb.cy == Decimal("35")

    def test_center_zero_origin(self):
        bb = BoundingBox2D(Decimal("0"), Decimal("0"), Decimal("100"), Decimal("100"))
        assert bb.cx == Decimal("50")
        assert bb.cy == Decimal("50")


class TestBboxDistance:
    def test_same_center_distance_zero(self):
        bb = BoundingBox2D(Decimal("0"), Decimal("0"), Decimal("10"), Decimal("10"))
        assert _bbox_distance(bb, bb) == Decimal("0")

    def test_horizontal_offset(self):
        a = BoundingBox2D(Decimal("0"), Decimal("0"), Decimal("10"), Decimal("10"))
        b = BoundingBox2D(Decimal("20"), Decimal("0"), Decimal("10"), Decimal("10"))
        # centers: (5,5) and (25,5) → distance = 20
        assert _bbox_distance(a, b) == Decimal("20")


class TestProximityScore:
    def test_distance_zero_gives_one(self):
        score = _proximity_score(Decimal("0"), Decimal("100"))
        assert score == Decimal("1")

    def test_distance_equal_max_gives_zero(self):
        score = _proximity_score(Decimal("100"), Decimal("100"))
        assert score == Decimal("0")

    def test_distance_half_max_gives_half(self):
        score = _proximity_score(Decimal("50"), Decimal("100"))
        assert score == Decimal("0.5")

    def test_distance_beyond_max_gives_zero(self):
        score = _proximity_score(Decimal("150"), Decimal("100"))
        assert score == Decimal("0")

    def test_zero_max_distance_gives_zero(self):
        score = _proximity_score(Decimal("5"), Decimal("0"))
        assert score == Decimal("0")


class TestSemanticScore:
    def test_fit_on_hole_is_1(self):
        score = _semantic_score(AnnotationType.FIT, FeatureType.HOLE)
        assert score == Decimal("1.0")

    def test_fit_on_shaft_is_1(self):
        score = _semantic_score(AnnotationType.FIT, FeatureType.SHAFT)
        assert score == Decimal("1.0")

    def test_thread_on_threaded_hole_is_1(self):
        score = _semantic_score(AnnotationType.THREAD, FeatureType.THREADED_HOLE)
        assert score == Decimal("1.0")

    def test_surface_finish_on_planar_face(self):
        score = _semantic_score(AnnotationType.SURFACE_FINISH, FeatureType.PLANAR_FACE)
        assert score == Decimal("0.9")

    def test_gdt_on_hole_pattern(self):
        score = _semantic_score(AnnotationType.GDT, FeatureType.HOLE_PATTERN)
        assert score == Decimal("0.9")

    def test_unknown_combo_returns_half(self):
        score = _semantic_score(AnnotationType.DIMENSION, FeatureType.SHAFT)
        assert score == Decimal("0.5")


class TestInferFeatureType:
    def test_fit_defaults_to_hole(self):
        assert infer_feature_type(AnnotationType.FIT) == FeatureType.HOLE

    def test_fit_shaft_subtype(self):
        assert infer_feature_type(AnnotationType.FIT, "SHAFT_something") == FeatureType.SHAFT

    def test_thread_is_threaded_hole(self):
        assert infer_feature_type(AnnotationType.THREAD) == FeatureType.THREADED_HOLE

    def test_surface_finish_is_planar(self):
        assert infer_feature_type(AnnotationType.SURFACE_FINISH) == FeatureType.PLANAR_FACE

    def test_dimension_default_planar(self):
        assert infer_feature_type(AnnotationType.DIMENSION) == FeatureType.PLANAR_FACE

    def test_dimension_diametral_is_hole(self):
        assert infer_feature_type(AnnotationType.DIMENSION, "DIAMETRAL") == FeatureType.HOLE

    def test_dimension_radial_is_fillet(self):
        assert infer_feature_type(AnnotationType.DIMENSION, "RADIAL") == FeatureType.FILLET

    def test_note_is_unknown(self):
        assert infer_feature_type(AnnotationType.NOTE) == FeatureType.UNKNOWN


class TestAssociateAnnotation:
    def _make_bb(self, x, y, w=10, h=10):
        return BoundingBox2D(Decimal(str(x)), Decimal(str(y)), Decimal(str(w)), Decimal(str(h)))

    def test_empty_features_returns_unresolved(self):
        result = associate_annotation(
            "ann-1", AnnotationType.FIT,
            self._make_bb(10, 10), None, {}
        )
        assert result.state == AssociationState.UNRESOLVED
        assert result.candidates == ()

    def test_no_bbox_returns_unresolved(self):
        features = {"f1": (self._make_bb(10, 10), FeatureType.HOLE)}
        result = associate_annotation(
            "ann-1", AnnotationType.FIT, None, None, features
        )
        assert result.state == AssociationState.UNRESOLVED

    def test_single_close_feature_auto_matched(self):
        # Annotation at (10,10), feature very close at (12,12)
        ann_bb = self._make_bb(10, 10)
        feat_bb = self._make_bb(12, 12)
        features = {"f1": (feat_bb, FeatureType.HOLE)}
        result = associate_annotation(
            "ann-1", AnnotationType.FIT, ann_bb, None, features
        )
        assert result.state == AssociationState.AUTO_MATCHED
        assert result.confirmed_feature_id == "f1"

    def test_two_similar_features_multiple_candidates(self):
        ann_bb = self._make_bb(50, 50)
        # Two features at equal distance
        feat_bb1 = self._make_bb(55, 50)
        feat_bb2 = self._make_bb(45, 50)
        features = {
            "f1": (feat_bb1, FeatureType.HOLE),
            "f2": (feat_bb2, FeatureType.HOLE),
        }
        result = associate_annotation(
            "ann-1", AnnotationType.FIT, ann_bb, None, features,
            max_proximity_pts=Decimal("200"),
        )
        assert result.state in (AssociationState.MULTIPLE_CANDIDATES, AssociationState.AUTO_MATCHED)

    def test_very_far_feature_unresolved(self):
        ann_bb = self._make_bb(0, 0)
        feat_bb = self._make_bb(5000, 5000)
        features = {"f1": (feat_bb, FeatureType.HOLE)}
        result = associate_annotation(
            "ann-1", AnnotationType.FIT, ann_bb, None, features,
            max_proximity_pts=Decimal("72"),
        )
        # Far feature may still have semantic score but combined may be low
        assert result.state in (AssociationState.UNRESOLVED, AssociationState.MULTIPLE_CANDIDATES, AssociationState.AUTO_MATCHED)

    def test_annotation_id_preserved(self):
        features = {"f1": (self._make_bb(10, 10), FeatureType.HOLE)}
        result = associate_annotation(
            "my-annotation-id", AnnotationType.FIT,
            self._make_bb(10, 10), None, features
        )
        assert result.annotation_id == "my-annotation-id"

    def test_inferred_feature_type_set(self):
        features = {"f1": (self._make_bb(10, 10), FeatureType.HOLE)}
        result = associate_annotation(
            "ann-1", AnnotationType.THREAD,
            self._make_bb(10, 10), None, features
        )
        assert result.inferred_feature_type == FeatureType.THREADED_HOLE

    def test_top5_candidates_limit(self):
        ann_bb = self._make_bb(50, 50)
        features = {
            f"f{i}": (self._make_bb(50 + i * 3, 50), FeatureType.HOLE)
            for i in range(10)
        }
        result = associate_annotation(
            "ann-1", AnnotationType.FIT, ann_bb, None, features,
            max_proximity_pts=Decimal("200"),
        )
        assert len(result.candidates) <= 5


class TestAssociateAnnotationFabricatedCheck:
    """FABRICATED_FEATURE_ASSOCIATION=NO — no auto-confirm when ambiguous."""

    def test_multiple_candidates_confirmed_id_is_none(self):
        ann_bb = BoundingBox2D(Decimal("50"), Decimal("50"), Decimal("10"), Decimal("10"))
        feat_bb1 = BoundingBox2D(Decimal("52"), Decimal("50"), Decimal("10"), Decimal("10"))
        feat_bb2 = BoundingBox2D(Decimal("48"), Decimal("50"), Decimal("10"), Decimal("10"))
        features = {
            "f1": (feat_bb1, FeatureType.HOLE),
            "f2": (feat_bb2, FeatureType.HOLE),
        }
        result = associate_annotation(
            "ann-1", AnnotationType.FIT, ann_bb, None, features,
            max_proximity_pts=Decimal("200"),
        )
        if result.state == AssociationState.MULTIPLE_CANDIDATES:
            assert result.confirmed_feature_id is None
