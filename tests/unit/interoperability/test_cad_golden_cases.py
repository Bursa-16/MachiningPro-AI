"""Integration tests for CAD feature recognition using golden dataset cases A-J.

Each case exercises the full pipeline:
    golden topology/geometry → FeatureRecognitionEngine → ManufacturingFeatureRecognitionResult
    → (optionally) CadFusionEngine → FusionResult

Golden cases use synthetic topologies built in Python (no proprietary CAD files).
CUSTOMER_CAD_COMMITTED=NO
"""

from __future__ import annotations

import pytest

from backend.interoperability.cad_feature_recognition import (
    FeatureRecognitionEngine,
    FeatureRecognitionConfidence,
    ManufacturingFeatureType,
    RecognitionMethod,
)
from backend.interoperability.cad_fusion import (
    AssociationStatus,
    CadFusionEngine,
    FusionCompleteness,
)
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


_ENGINE = FeatureRecognitionEngine()
_FUSION = CadFusionEngine()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _feature_types(res) -> list[str]:
    return [f.feature_type.value for f in res.features]


def _fuse(rec_res):
    import uuid
    return _FUSION.fuse(rec_res, None, str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# All cases build without error
# ---------------------------------------------------------------------------

class TestAllCasesConstruct:
    @pytest.mark.parametrize("case_name,fn", list(ALL_CASES.items()))
    def test_builds_without_error(self, case_name, fn):
        topo, geom, _ = fn()
        assert topo is not None
        assert geom is not None
        assert len(topo.faces) > 0
        assert len(topo.edges) == 3  # 3 backbone edges

    @pytest.mark.parametrize("case_name,fn", list(ALL_CASES.items()))
    def test_recognizes_without_error(self, case_name, fn):
        topo, geom, _ = fn()
        res = _ENGINE.recognize(topo, geom)
        assert res is not None

    @pytest.mark.parametrize("case_name,fn", list(ALL_CASES.items()))
    def test_fuses_without_error(self, case_name, fn):
        topo, geom, _ = fn()
        res = _ENGINE.recognize(topo, geom)
        fres = _fuse(res)
        assert fres is not None


# ---------------------------------------------------------------------------
# Case A — Block + blind hole
# ---------------------------------------------------------------------------

class TestCaseA:
    def setup_method(self):
        topo, geom, _ = build_case_a()
        self.res = _ENGINE.recognize(topo, geom)

    def test_hole_detected(self):
        types = _feature_types(self.res)
        assert any("HOLE" in t for t in types), f"No hole in {types}"

    def test_body_count_is_one(self):
        assert self.res.body_count == 1

    def test_face_count_is_four(self):
        assert self.res.face_count == 4

    def test_every_feature_has_source_face(self):
        for f in self.res.features:
            assert len(f.source_face_ids) > 0

    def test_recognition_version_set(self):
        assert self.res.recognition_version

    def test_accessibility_candidates_present(self):
        # Engine should produce accessibility data as a dict
        assert isinstance(self.res.accessibility, dict)


# ---------------------------------------------------------------------------
# Case B — Counterbore
# ---------------------------------------------------------------------------

class TestCaseB:
    def setup_method(self):
        topo, geom, _ = build_case_b()
        self.res = _ENGINE.recognize(topo, geom)

    def test_counterbore_detected(self):
        types = _feature_types(self.res)
        assert "COUNTERBORE" in types, f"No COUNTERBORE in {types}"

    def test_outer_diameter_detected(self):
        types = _feature_types(self.res)
        assert "OUTER_DIAMETER" in types, f"No OUTER_DIAMETER in {types}"

    def test_multiple_features(self):
        assert len(self.res.features) >= 2


# ---------------------------------------------------------------------------
# Case C — Countersink
# ---------------------------------------------------------------------------

class TestCaseC:
    def setup_method(self):
        topo, geom, _ = build_case_c()
        self.res = _ENGINE.recognize(topo, geom)

    def test_countersink_detected(self):
        types = _feature_types(self.res)
        assert "COUNTERSINK" in types, f"No COUNTERSINK in {types}"

    def test_chamfer_detected(self):
        types = _feature_types(self.res)
        assert "CHAMFER" in types, f"No CHAMFER in {types}"

    def test_cone_surfaces_recognized(self):
        # At least one feature from a CONE surface
        from backend.interoperability.geometry import CanonicalSurfaceType
        cone_feats = [f for f in self.res.features if f.surface_type == CanonicalSurfaceType.CONE]
        assert len(cone_feats) >= 1


# ---------------------------------------------------------------------------
# Case D — Closed pocket
# ---------------------------------------------------------------------------

class TestCaseD:
    def setup_method(self):
        topo, geom, _ = build_case_d()
        self.res = _ENGINE.recognize(topo, geom)

    def test_closed_pocket_detected(self):
        types = _feature_types(self.res)
        assert "CLOSED_POCKET" in types, f"No CLOSED_POCKET in {types}"

    def test_face_count_is_seven(self):
        assert self.res.face_count == 7


# ---------------------------------------------------------------------------
# Case E — Open slot
# ---------------------------------------------------------------------------

class TestCaseE:
    def setup_method(self):
        topo, geom, _ = build_case_e()
        self.res = _ENGINE.recognize(topo, geom)

    def test_open_slot_detected(self):
        types = _feature_types(self.res)
        assert "OPEN_SLOT" in types, f"No OPEN_SLOT in {types}"

    def test_slot_count_gte_one(self):
        slot_feats = [f for f in self.res.features if f.feature_type == ManufacturingFeatureType.OPEN_SLOT]
        assert len(slot_feats) >= 1


# ---------------------------------------------------------------------------
# Case F — Boss
# ---------------------------------------------------------------------------

class TestCaseF:
    def setup_method(self):
        topo, geom, _ = build_case_f()
        self.res = _ENGINE.recognize(topo, geom)

    def test_cylindrical_feature_detected(self):
        types = _feature_types(self.res)
        assert any(t in types for t in ("BOSS", "OUTER_DIAMETER", "THROUGH_HOLE")), (
            f"No cylindrical feature in {types}"
        )

    def test_features_non_empty(self):
        assert len(self.res.features) > 0


# ---------------------------------------------------------------------------
# Case G — Stepped shaft (3 diameters)
# ---------------------------------------------------------------------------

class TestCaseG:
    def setup_method(self):
        topo, geom, _ = build_case_g()
        self.res = _ENGINE.recognize(topo, geom)

    def test_turning_feature_detected(self):
        types = _feature_types(self.res)
        assert any(t in types for t in ("OUTER_DIAMETER", "STEPPED_HOLE", "GROOVE")), (
            f"No turning feature in {types}"
        )

    def test_multiple_features(self):
        assert len(self.res.features) >= 2

    def test_face_count_is_seven(self):
        assert self.res.face_count == 7


# ---------------------------------------------------------------------------
# Case H — Groove
# ---------------------------------------------------------------------------

class TestCaseH:
    def setup_method(self):
        topo, geom, _ = build_case_h()
        self.res = _ENGINE.recognize(topo, geom)

    def test_groove_detected(self):
        types = _feature_types(self.res)
        assert "GROOVE" in types, f"No GROOVE in {types}"

    def test_outer_diameter_detected(self):
        types = _feature_types(self.res)
        assert "OUTER_DIAMETER" in types, f"No OUTER_DIAMETER in {types}"

    def test_face_count_is_six(self):
        assert self.res.face_count == 6


# ---------------------------------------------------------------------------
# Case I — 4× hole pattern (bolt circle)
# ---------------------------------------------------------------------------

class TestCaseI:
    def setup_method(self):
        topo, geom, _ = build_case_i()
        self.res = _ENGINE.recognize(topo, geom)

    def test_four_holes_detected(self):
        hole_feats = [f for f in self.res.features if "HOLE" in f.feature_type.value]
        assert len(hole_feats) == 4, f"Expected 4 holes, got {len(hole_feats)}"

    def test_face_count_is_six(self):
        # 2 base faces + 4 cylinder faces
        assert self.res.face_count == 6

    def test_patterns_field_present(self):
        assert hasattr(self.res, "patterns")


# ---------------------------------------------------------------------------
# Case J — Mixed prismatic
# ---------------------------------------------------------------------------

class TestCaseJ:
    def setup_method(self):
        topo, geom, _ = build_case_j()
        self.res = _ENGINE.recognize(topo, geom)

    def test_at_least_six_features(self):
        assert len(self.res.features) >= 6, f"Expected >= 6, got {len(self.res.features)}"

    def test_countersink_detected(self):
        types = _feature_types(self.res)
        assert "COUNTERSINK" in types

    def test_closed_pocket_detected(self):
        types = _feature_types(self.res)
        assert "CLOSED_POCKET" in types

    def test_chamfer_detected(self):
        types = _feature_types(self.res)
        assert "CHAMFER" in types

    def test_fillet_detected(self):
        types = _feature_types(self.res)
        assert "FILLET" in types

    def test_boss_or_od_detected(self):
        types = _feature_types(self.res)
        assert any(t in types for t in ("BOSS", "OUTER_DIAMETER"))

    def test_groove_detected(self):
        types = _feature_types(self.res)
        assert "GROOVE" in types

    def test_face_count_is_thirteen(self):
        assert self.res.face_count == 13

    def test_fused_without_error(self):
        fres = _fuse(self.res)
        assert fres is not None
        assert isinstance(fres.cad_only_feature_ids, (list, tuple, set))


# ---------------------------------------------------------------------------
# Cross-case invariants
# ---------------------------------------------------------------------------

class TestCrossCaseInvariants:
    @pytest.mark.parametrize("case_name,fn", list(ALL_CASES.items()))
    def test_no_fabricated_features(self, case_name, fn):
        """FABRICATED_FEATURE=NO — every feature must reference at least one source face."""
        topo, geom, _ = fn()
        res = _ENGINE.recognize(topo, geom)
        for feat in res.features:
            assert len(feat.source_face_ids) > 0, (
                f"Case {case_name}: feature {feat.feature_id} ({feat.feature_type}) "
                f"has no source faces — FABRICATED_FEATURE violation"
            )

    @pytest.mark.parametrize("case_name,fn", list(ALL_CASES.items()))
    def test_deterministic(self, case_name, fn):
        """Recognition must be deterministic."""
        topo, geom, _ = fn()
        eng = FeatureRecognitionEngine()
        res1 = eng.recognize(topo, geom)
        res2 = eng.recognize(topo, geom)
        types1 = sorted(f.feature_type.value for f in res1.features)
        types2 = sorted(f.feature_type.value for f in res2.features)
        assert types1 == types2, f"Case {case_name}: non-deterministic results"

    @pytest.mark.parametrize("case_name,fn", list(ALL_CASES.items()))
    def test_fusion_cad_only_links_traceable(self, case_name, fn):
        """Every cad_only_feature_id must reference a real feature — FABRICATED_FEATURE=NO."""
        topo, geom, _ = fn()
        res = _ENGINE.recognize(topo, geom)
        real_ids = {f.feature_id for f in res.features}
        fres = _fuse(res)
        for fid in fres.cad_only_feature_ids:
            assert fid in real_ids, (
                f"Case {case_name}: cad_only_feature_id {fid} references phantom feature"
            )
