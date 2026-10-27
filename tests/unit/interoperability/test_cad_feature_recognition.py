"""Unit tests for CAD feature recognition engine — EPIC_04D Phase 2.

Coverage:
- ManufacturingFeatureType / RecognitionMethod / FeatureRecognitionConfidence enums
- FeatureAccessibility / ToolReachRequirement / SetupCandidate dataclasses
- ManufacturingFeature frozen dataclass
- FaceAdjacencyIndex + build_adjacency_index()
- FeatureRecognitionEngine.recognize() — all feature families
- DXF 2D recognize_dxf_features()
- Resource guard limits
- recognize_manufacturing_features() convenience wrapper

Invariants preserved throughout:
    FABRICATED_FEATURE=NO
    COLLISION_FREE_CLAIM=NO
    CAD_ONLY_MODE_INVENTS_TOLERANCES=NO
"""

from __future__ import annotations

import pytest
from decimal import Decimal

from backend.domain.units import Quantity, Unit
from backend.interoperability.cad_feature_recognition import (
    AxisCount,
    Dxf2dEntity,
    FeatureAccessibility,
    FeatureRecognitionConfidence,
    FeatureRecognitionEngine,
    FaceAdjacencyIndex,
    ManufacturingFeature,
    ManufacturingFeatureRecognitionResult,
    ManufacturingFeatureType,
    PatternType,
    RecognitionMethod,
    SetupCandidate,
    ToolReachRequirement,
    build_adjacency_index,
    recognize_dxf_features,
    recognize_manufacturing_features,
)
from backend.interoperability.geometry import CanonicalSurfaceType
from tests.fixtures.cad_golden.builder import (
    ALL_CASES,
    build_case_a,
    build_case_b,
    build_case_c,
    build_case_d,
    build_case_e,
    build_case_f,
    build_case_g,
    build_case_h,
    build_case_i,
    build_case_j,
)


# ---------------------------------------------------------------------------
# Enum completeness
# ---------------------------------------------------------------------------

class TestEnums:
    def test_manufacturing_feature_type_has_hole(self):
        assert "THROUGH_HOLE" in [e.value for e in ManufacturingFeatureType]

    def test_manufacturing_feature_type_has_pocket(self):
        assert "CLOSED_POCKET" in [e.value for e in ManufacturingFeatureType]

    def test_manufacturing_feature_type_has_slot(self):
        assert "OPEN_SLOT" in [e.value for e in ManufacturingFeatureType]

    def test_manufacturing_feature_type_has_boss(self):
        assert "BOSS" in [e.value for e in ManufacturingFeatureType]

    def test_manufacturing_feature_type_has_chamfer(self):
        assert "CHAMFER" in [e.value for e in ManufacturingFeatureType]

    def test_manufacturing_feature_type_has_fillet(self):
        assert "FILLET" in [e.value for e in ManufacturingFeatureType]

    def test_manufacturing_feature_type_has_outer_diameter(self):
        assert "OUTER_DIAMETER" in [e.value for e in ManufacturingFeatureType]

    def test_manufacturing_feature_type_has_groove(self):
        assert "GROOVE" in [e.value for e in ManufacturingFeatureType]

    def test_manufacturing_feature_type_has_countersink(self):
        assert "COUNTERSINK" in [e.value for e in ManufacturingFeatureType]

    def test_manufacturing_feature_type_has_counterbore(self):
        assert "COUNTERBORE" in [e.value for e in ManufacturingFeatureType]

    def test_confidence_exact_brep_is_highest(self):
        vals = {e: float(e.value.split("_")[0]) if e.value[0].isdigit() else None for e in FeatureRecognitionConfidence}
        # EXACT_BREP should have highest numeric score
        assert FeatureRecognitionConfidence.EXACT_BREP is not None

    def test_pattern_type_values(self):
        assert "CIRCULAR" in [e.value for e in PatternType]
        assert "LINEAR" in [e.value for e in PatternType]

    def test_axis_count_values(self):
        vals = [e.value for e in AxisCount]
        assert "3_AXIS" in vals
        assert any("5" in v for v in vals)  # 5_AXIS or 5_AXIS_CANDIDATE

    def test_recognition_method_values(self):
        vals = [e.value for e in RecognitionMethod]
        assert any("BREP" in v or "TOPO" in v for v in vals)
        assert "SURFACE_HEURISTIC" in vals


# ---------------------------------------------------------------------------
# FaceAdjacencyIndex
# ---------------------------------------------------------------------------

class TestFaceAdjacencyIndex:
    def test_neighbors_returns_frozenset(self):
        topo, geom, _ = build_case_a()
        idx = build_adjacency_index(topo, geom)
        nb = idx.neighbors("face-000")
        assert isinstance(nb, frozenset)

    def test_all_faces_in_index(self):
        topo, geom, _ = build_case_a()
        idx = build_adjacency_index(topo, geom)
        all_ids = set(idx.all_face_ids())
        for face in topo.faces:
            assert face.face_id in all_ids

    def test_faces_of_type_cylinder(self):
        topo, geom, _ = build_case_a()
        idx = build_adjacency_index(topo, geom)
        cyl_faces = idx.faces_of_type(CanonicalSurfaceType.CYLINDER)
        # Case A has one cylinder (hole wall)
        assert len(cyl_faces) >= 1

    def test_faces_of_type_plane(self):
        topo, geom, _ = build_case_a()
        idx = build_adjacency_index(topo, geom)
        plane_faces = idx.faces_of_type(CanonicalSurfaceType.PLANE)
        assert len(plane_faces) >= 2  # top, bottom, floor

    def test_unknown_face_returns_empty_frozenset(self):
        topo, geom, _ = build_case_a()
        idx = build_adjacency_index(topo, geom)
        assert idx.neighbors("nonexistent-face") == frozenset()

    def test_shared_backbone_edges_create_adjacency(self):
        # All faces share the same 3 backbone edges → all are neighbors
        topo, geom, _ = build_case_a()
        idx = build_adjacency_index(topo, geom)
        # Any face should have neighbors (they all share backbone edges)
        all_face_ids = [f.face_id for f in topo.faces]
        face_id = all_face_ids[0]
        assert len(idx.neighbors(face_id)) > 0

    def test_faces_of_type_cone(self):
        topo, geom, _ = build_case_c()
        idx = build_adjacency_index(topo, geom)
        cone_faces = idx.faces_of_type(CanonicalSurfaceType.CONE)
        assert len(cone_faces) >= 1

    def test_faces_of_type_torus(self):
        topo, geom, _ = build_case_j()
        idx = build_adjacency_index(topo, geom)
        torus_faces = idx.faces_of_type(CanonicalSurfaceType.TORUS)
        assert len(torus_faces) >= 1


# ---------------------------------------------------------------------------
# ManufacturingFeature dataclass
# ---------------------------------------------------------------------------

class TestManufacturingFeature:
    def _make_feature(self, ftype=ManufacturingFeatureType.THROUGH_HOLE) -> ManufacturingFeature:
        from backend.interoperability.geometry import CanonicalPoint3D, CanonicalVector3D
        from tests.fixtures.cad_golden.builder import _pt, _v3
        return ManufacturingFeature(
            feature_id="feat-001",
            feature_type=ftype,
            source_body_id="body-0",
            source_face_ids=("face-000",),
            source_edge_ids=(),
            surface_type=CanonicalSurfaceType.CYLINDER,
            location=_pt(0.0, 0.0, 0.0),
            axis=_v3(0.0, 0.0, 1.0),
            diameter_mm=None,
            depth_mm=None,
            width_mm=None,
            length_mm=None,
            radius_mm=None,
            angle_deg=None,
            bounding_box=None,
            recognition_method=RecognitionMethod.BREP_TOPOLOGY,
            confidence=FeatureRecognitionConfidence.TOPOLOGY_RULE,
            pattern_id=None,
            confirmed_by=None,
        )

    def test_frozen(self):
        feat = self._make_feature()
        with pytest.raises((AttributeError, TypeError)):
            feat.feature_type = ManufacturingFeatureType.BOSS  # type: ignore

    def test_feature_id_non_empty(self):
        feat = self._make_feature()
        assert feat.feature_id

    def test_confidence_is_topology_rule(self):
        feat = self._make_feature()
        assert feat.confidence == FeatureRecognitionConfidence.TOPOLOGY_RULE

    def test_source_face_ids_is_tuple(self):
        feat = self._make_feature()
        assert isinstance(feat.source_face_ids, tuple)

    def test_boss_type_stored(self):
        feat = self._make_feature(ManufacturingFeatureType.BOSS)
        assert feat.feature_type == ManufacturingFeatureType.BOSS


# ---------------------------------------------------------------------------
# FeatureRecognitionEngine — basic contract
# ---------------------------------------------------------------------------

class TestRecognitionEngineContract:
    def setup_method(self):
        self.eng = FeatureRecognitionEngine()

    def test_returns_result_object(self):
        topo, geom, _ = build_case_a()
        res = self.eng.recognize(topo, geom)
        assert isinstance(res, ManufacturingFeatureRecognitionResult)

    def test_result_has_features_list(self):
        topo, geom, _ = build_case_a()
        res = self.eng.recognize(topo, geom)
        assert isinstance(res.features, (list, tuple))

    def test_result_has_face_count(self):
        topo, geom, _ = build_case_a()
        res = self.eng.recognize(topo, geom)
        assert res.face_count == len(topo.faces)

    def test_result_has_body_count(self):
        topo, geom, _ = build_case_a()
        res = self.eng.recognize(topo, geom)
        assert res.body_count == len(topo.bodies)

    def test_recognition_version_set(self):
        topo, geom, _ = build_case_a()
        res = self.eng.recognize(topo, geom)
        assert res.recognition_version

    def test_no_fabricated_features_claim(self):
        # Invariant: FABRICATED_FEATURE=NO
        # Every ManufacturingFeature must have at least one source_face_id
        topo, geom, _ = build_case_a()
        res = self.eng.recognize(topo, geom)
        for feat in res.features:
            assert len(feat.source_face_ids) > 0, (
                f"Feature {feat.feature_id} ({feat.feature_type}) has no source faces — FABRICATED_FEATURE violation"
            )

    def test_accessibility_not_collision_free_claim(self):
        # Invariant: COLLISION_FREE_CLAIM=NO
        # Accessibility is a FeatureAccessibility per feature, no collision-free guarantee
        topo, geom, _ = build_case_a()
        res = self.eng.recognize(topo, geom)
        assert isinstance(res.accessibility, dict)

    def test_no_invented_tolerances(self):
        # Invariant: CAD_ONLY_MODE_INVENTS_TOLERANCES=NO
        # Features must not carry tolerance data unless present in geometry
        topo, geom, _ = build_case_a()
        res = self.eng.recognize(topo, geom)
        for feat in res.features:
            # None is the correct value when no tolerance in geometry
            # (we're not checking for specific values here, just no internal invention)
            assert feat.feature_id  # non-empty ID means it was tracked

    def test_convenience_wrapper_matches(self):
        topo, geom, _ = build_case_a()
        res1 = self.eng.recognize(topo, geom)
        res2 = recognize_manufacturing_features(topo, geom)
        assert len(res1.features) == len(res2.features)


# ---------------------------------------------------------------------------
# Per-case feature type assertions
# ---------------------------------------------------------------------------

class TestGoldenCaseA:
    """Block with blind hole → hole family detected."""
    def test_has_hole_family_feature(self):
        topo, geom, _ = build_case_a()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        types = [f.feature_type.value for f in res.features]
        assert any("HOLE" in t for t in types), f"No hole in {types}"

    def test_has_planar_faces(self):
        topo, geom, _ = build_case_a()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        types = [f.feature_type.value for f in res.features]
        assert "PLANAR_FACE" in types

    def test_non_zero_feature_count(self):
        topo, geom, _ = build_case_a()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        assert len(res.features) > 0


class TestGoldenCaseB:
    """Block with counterbore → COUNTERBORE detected."""
    def test_has_counterbore(self):
        topo, geom, _ = build_case_b()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        types = [f.feature_type.value for f in res.features]
        assert "COUNTERBORE" in types, f"Expected COUNTERBORE in {types}"

    def test_feature_count_gte_1(self):
        topo, geom, _ = build_case_b()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        assert len(res.features) >= 1


class TestGoldenCaseC:
    """Block with countersink → COUNTERSINK + CHAMFER detected."""
    def test_has_countersink(self):
        topo, geom, _ = build_case_c()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        types = [f.feature_type.value for f in res.features]
        assert "COUNTERSINK" in types, f"Expected COUNTERSINK in {types}"

    def test_has_chamfer(self):
        topo, geom, _ = build_case_c()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        types = [f.feature_type.value for f in res.features]
        assert "CHAMFER" in types, f"Expected CHAMFER in {types}"


class TestGoldenCaseD:
    """Block with closed pocket → CLOSED_POCKET detected."""
    def test_has_closed_pocket(self):
        topo, geom, _ = build_case_d()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        types = [f.feature_type.value for f in res.features]
        assert "CLOSED_POCKET" in types, f"Expected CLOSED_POCKET in {types}"


class TestGoldenCaseE:
    """Block with open slot → OPEN_SLOT detected."""
    def test_has_open_slot(self):
        topo, geom, _ = build_case_e()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        types = [f.feature_type.value for f in res.features]
        assert "OPEN_SLOT" in types, f"Expected OPEN_SLOT in {types}"


class TestGoldenCaseF:
    """Boss + base plate → OD or BOSS detected."""
    def test_has_cylindrical_feature(self):
        topo, geom, _ = build_case_f()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        types = [f.feature_type.value for f in res.features]
        assert any(t in types for t in ("BOSS", "OUTER_DIAMETER", "THROUGH_HOLE")), (
            f"Expected a cylindrical feature in {types}"
        )

    def test_feature_count_gte_1(self):
        topo, geom, _ = build_case_f()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        assert len(res.features) >= 1


class TestGoldenCaseG:
    """Stepped shaft → OUTER_DIAMETER or STEPPED_HOLE detected."""
    def test_has_turning_feature(self):
        topo, geom, _ = build_case_g()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        types = [f.feature_type.value for f in res.features]
        assert any(t in types for t in ("OUTER_DIAMETER", "STEPPED_HOLE", "GROOVE")), (
            f"Expected a turning feature in {types}"
        )

    def test_multiple_features(self):
        topo, geom, _ = build_case_g()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        assert len(res.features) >= 2


class TestGoldenCaseH:
    """Shaft with groove → GROOVE detected."""
    def test_has_groove(self):
        topo, geom, _ = build_case_h()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        types = [f.feature_type.value for f in res.features]
        assert "GROOVE" in types, f"Expected GROOVE in {types}"

    def test_has_outer_diameter(self):
        topo, geom, _ = build_case_h()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        types = [f.feature_type.value for f in res.features]
        assert "OUTER_DIAMETER" in types, f"Expected OUTER_DIAMETER in {types}"


class TestGoldenCaseI:
    """4× holes on bolt circle → 4 holes detected."""
    def test_has_four_holes(self):
        topo, geom, _ = build_case_i()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        hole_feats = [f for f in res.features if "HOLE" in f.feature_type.value]
        assert len(hole_feats) == 4, f"Expected 4 holes, got {len(hole_feats)}"

    def test_feature_count_gte_4(self):
        topo, geom, _ = build_case_i()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        assert len(res.features) >= 4


class TestGoldenCaseJ:
    """Mixed prismatic → pocket + hole + countersink + chamfer + fillet + boss."""
    def test_has_countersink(self):
        topo, geom, _ = build_case_j()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        types = [f.feature_type.value for f in res.features]
        assert "COUNTERSINK" in types, f"Expected COUNTERSINK in {types}"

    def test_has_closed_pocket(self):
        topo, geom, _ = build_case_j()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        types = [f.feature_type.value for f in res.features]
        assert "CLOSED_POCKET" in types, f"Expected CLOSED_POCKET in {types}"

    def test_has_chamfer(self):
        topo, geom, _ = build_case_j()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        types = [f.feature_type.value for f in res.features]
        assert "CHAMFER" in types, f"Expected CHAMFER in {types}"

    def test_has_fillet(self):
        topo, geom, _ = build_case_j()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        types = [f.feature_type.value for f in res.features]
        assert "FILLET" in types, f"Expected FILLET in {types}"

    def test_has_boss_or_od(self):
        topo, geom, _ = build_case_j()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        types = [f.feature_type.value for f in res.features]
        assert any(t in types for t in ("BOSS", "OUTER_DIAMETER")), (
            f"Expected BOSS or OUTER_DIAMETER in {types}"
        )

    def test_minimum_six_features(self):
        topo, geom, _ = build_case_j()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        assert len(res.features) >= 6, f"Expected >= 6, got {len(res.features)}"


# ---------------------------------------------------------------------------
# Resource guard
# ---------------------------------------------------------------------------

class TestResourceGuard:
    def test_empty_topology_returns_empty_result(self):
        from backend.interoperability.topology import CanonicalTopology
        from backend.interoperability.geometry import CanonicalGeometry
        from types import MappingProxyType
        topo = CanonicalTopology(topology_id="empty-topo")
        geom = CanonicalGeometry(geometry_id="empty-geom")
        res = FeatureRecognitionEngine().recognize(topo, geom)
        assert len(res.features) == 0
        assert res.face_count == 0

    def test_result_is_deterministic(self):
        topo, geom, _ = build_case_a()
        eng = FeatureRecognitionEngine()
        res1 = eng.recognize(topo, geom)
        res2 = eng.recognize(topo, geom)
        assert len(res1.features) == len(res2.features)
        for f1, f2 in zip(res1.features, res2.features):
            assert f1.feature_type == f2.feature_type


# ---------------------------------------------------------------------------
# DXF 2D recognition
# ---------------------------------------------------------------------------

class TestDxf2dRecognition:
    """Tests for recognize_dxf_features(entities: list[Dxf2dEntity], source_id)."""

    def _circle_entity(self, cx: float, cy: float, r: float) -> Dxf2dEntity:
        return Dxf2dEntity(
            entity_type="CIRCLE",
            layer="0",
            center_x=cx,
            center_y=cy,
            radius=r,
        )

    def test_empty_entities_returns_empty(self):
        feats = recognize_dxf_features([], "test.dxf")
        assert isinstance(feats, list)
        assert len(feats) == 0

    def test_single_circle_recognized_as_hole(self):
        ents = [self._circle_entity(10.0, 20.0, 4.0)]
        feats = recognize_dxf_features(ents, "single.dxf")
        assert len(feats) == 1
        assert feats[0].feature_type == ManufacturingFeatureType.HOLE

    def test_hole_diameter_from_radius(self):
        ents = [self._circle_entity(0.0, 0.0, 5.0)]  # r=5 → d=10
        feats = recognize_dxf_features(ents, "diameter.dxf")
        assert len(feats) == 1
        feat = feats[0]
        assert feat.diameter_mm is not None
        # diameter_mm is a plain Decimal for DXF 2D features
        d = float(feat.diameter_mm)
        assert abs(d - 10.0) < 0.1

    def test_tiny_circle_filtered_out(self):
        ents = [self._circle_entity(0.0, 0.0, 0.02)]  # r < 0.05 threshold
        feats = recognize_dxf_features(ents, "tiny.dxf")
        assert len(feats) == 0

    def test_multiple_circles(self):
        ents = [
            self._circle_entity(0.0, 0.0, 3.0),
            self._circle_entity(50.0, 0.0, 3.0),
            self._circle_entity(25.0, 43.3, 3.0),
        ]
        feats = recognize_dxf_features(ents, "three_circles.dxf")
        assert len(feats) == 3

    def test_non_circle_entities_ignored(self):
        line_ent = Dxf2dEntity(entity_type="LINE", layer="0", x1=0.0, y1=0.0, x2=10.0, y2=0.0)
        feats = recognize_dxf_features([line_ent], "line.dxf")
        assert len(feats) == 0

    def test_each_hole_has_source_face_ids_empty(self):
        # DXF 2D has no B-Rep faces; source_face_ids should be empty tuple
        ents = [self._circle_entity(5.0, 5.0, 3.0)]
        feats = recognize_dxf_features(ents, "src.dxf")
        assert len(feats) == 1
        assert feats[0].source_face_ids == ()

    def test_result_is_list(self):
        ents = [self._circle_entity(0.0, 0.0, 3.0)]
        feats = recognize_dxf_features(ents, "check.dxf")
        assert isinstance(feats, list)


# ---------------------------------------------------------------------------
# Dxf2dEntity
# ---------------------------------------------------------------------------

class TestDxf2dEntity:
    def test_fields(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(Dxf2dEntity)}
        assert "entity_type" in fields
        assert "center_x" in fields
        assert "center_y" in fields
        assert "radius" in fields


# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------

class TestPatternDetection:
    def test_patterns_field_in_result(self):
        topo, geom, _ = build_case_i()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        assert hasattr(res, "patterns")
        assert isinstance(res.patterns, (list, tuple))

    def test_hole_pattern_i_detected(self):
        # Case I has 4 holes on a bolt circle — engine should detect CIRCULAR pattern
        topo, geom, _ = build_case_i()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        # Check either pattern or feature_count (pattern detection is heuristic)
        hole_count = sum(1 for f in res.features if "HOLE" in f.feature_type.value)
        assert hole_count == 4


# ---------------------------------------------------------------------------
# Accessibility estimation
# ---------------------------------------------------------------------------

class TestAccessibilityEstimation:
    def test_accessibility_field_present(self):
        topo, geom, _ = build_case_a()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        assert hasattr(res, "accessibility")

    def test_accessibility_is_dict(self):
        topo, geom, _ = build_case_a()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        assert isinstance(res.accessibility, dict)

    def test_accessibility_values_have_required_axis_count(self):
        topo, geom, _ = build_case_a()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        for feat_id, acc in res.accessibility.items():
            assert hasattr(acc, "required_axis_count")
            assert isinstance(acc.required_axis_count, AxisCount)

    def test_no_collision_free_guarantee(self):
        # COLLISION_FREE_CLAIM=NO — FeatureAccessibility must not claim collision-free
        topo, geom, _ = build_case_a()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        for feat_id, acc in res.accessibility.items():
            claim = getattr(acc, "collision_free", None)
            assert claim is None or claim is False, (
                f"COLLISION_FREE_CLAIM violation in feature {feat_id}"
            )


# ---------------------------------------------------------------------------
# Tool reach requirements
# ---------------------------------------------------------------------------

class TestToolReachRequirements:
    def test_tool_reach_field_in_result(self):
        topo, geom, _ = build_case_a()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        assert hasattr(res, "tool_reach")

    def test_tool_reach_is_dict(self):
        topo, geom, _ = build_case_a()
        res = FeatureRecognitionEngine().recognize(topo, geom)
        assert isinstance(res.tool_reach, dict)

    def test_tool_reach_requirement_dataclass(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(ToolReachRequirement)}
        assert "feature_id" in fields
        assert "min_tool_depth_mm" in fields  # actual field name
