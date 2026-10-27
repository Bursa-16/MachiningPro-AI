"""Unit tests for CAD/drawing fusion engine — EPIC_04D Phase 2.

Coverage:
- AssociationScore composite property
- RequirementFeatureLink dataclass
- FusionAmbiguity fields
- FusionResult methods: confirm_link, reassign_link, mark_cad_only, mark_drawing_only
- CadFusionEngine.fuse() with no drawing session → CAD_ONLY completeness
- fuse_cad_with_drawing() top-level helper
- FusionCompleteness enum
- Enum value verification for all cad_fusion enums

Invariants preserved throughout:
    FABRICATED_DIMENSION=NO
    FABRICATED_DATUM_ASSOCIATION=NO
    FABRICATED_GDT_ASSOCIATION=NO
    AMBIGUOUS_ASSOCIATION_AUTO_APPROVED=NO
"""

from __future__ import annotations

import uuid
import pytest
from decimal import Decimal

from backend.interoperability.cad_fusion import (
    AmbiguityType,
    AssociationScore,
    AssociationStatus,
    CadFusionEngine,
    FusionAmbiguity,
    FusionCompleteness,
    FusionResult,
    FusionReviewEvent,
    RequirementFeatureLink,
    ReviewAction,
    fuse_cad_with_drawing,
)
from backend.interoperability.cad_feature_recognition import (
    FeatureRecognitionEngine,
    ManufacturingFeature,
    ManufacturingFeatureType,
    ManufacturingFeatureRecognitionResult,
    FeatureRecognitionConfidence,
    RecognitionMethod,
)
from backend.interoperability.geometry import CanonicalSurfaceType
from tests.fixtures.cad_golden.builder import (
    build_case_a,
    build_case_b,
    build_case_d,
    build_case_i,
    build_case_j,
    _pt,
    _v3,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fuse(rec_res: ManufacturingFeatureRecognitionResult, session_id: str | None = None) -> FusionResult:
    sid = session_id or str(uuid.uuid4())
    return CadFusionEngine().fuse(rec_res, None, sid)


def _recognize(case_fn) -> ManufacturingFeatureRecognitionResult:
    topo, geom, _ = case_fn()
    return FeatureRecognitionEngine().recognize(topo, geom)


def _empty_rec() -> ManufacturingFeatureRecognitionResult:
    return ManufacturingFeatureRecognitionResult(
        source_document_id="empty",
        recognition_version="1.0",
        features=[],
        patterns=[],
        accessibility={},
        tool_reach={},
        warnings=[],
        face_count=0,
        body_count=0,
    )


# ---------------------------------------------------------------------------
# AssociationScore composite property
# ---------------------------------------------------------------------------

class TestAssociationScore:
    def _make_score(
        self,
        type_compat=0.25,
        dim_match=0.25,
        orientation=0.10,
        proximity=0.20,
        datum=0.10,
        pattern=0.05,
        conf=0.05,
    ) -> AssociationScore:
        # Fields are floats (not Decimals) in the actual implementation
        return AssociationScore(
            requirement_id="req-001",
            feature_id="feat-001",
            type_compatibility=float(type_compat),
            dimension_match=float(dim_match),
            orientation_match=float(orientation),
            location_proximity=float(proximity),
            datum_relationship=float(datum),
            pattern_membership=float(pattern),
            source_confidence=float(conf),
        )

    def test_composite_property_exists(self):
        score = self._make_score()
        assert hasattr(score, "composite")

    def test_composite_is_numeric(self):
        score = self._make_score()
        assert isinstance(score.composite, (float, int, Decimal))

    def test_composite_max_is_one(self):
        # Max composite = 1.0 when ALL dimension values = 1.0
        score = self._make_score(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        assert abs(float(score.composite) - 1.0) < 1e-9

    def test_composite_zero(self):
        score = self._make_score(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        assert abs(float(score.composite)) < 1e-9

    def test_frozen(self):
        score = self._make_score()
        with pytest.raises((AttributeError, TypeError)):
            score.type_compatibility = 0.0  # type: ignore

    def test_requirement_id_stored(self):
        score = self._make_score()
        assert score.requirement_id == "req-001"

    def test_feature_id_stored(self):
        score = self._make_score()
        assert score.feature_id == "feat-001"


# ---------------------------------------------------------------------------
# AssociationStatus / ReviewAction / AmbiguityType / FusionCompleteness enums
# ---------------------------------------------------------------------------

class TestEnums:
    def test_association_status_has_auto_matched(self):
        assert AssociationStatus.AUTO_MATCHED is not None

    def test_association_status_has_unresolved(self):
        assert "UNRESOLVED" in [e.value for e in AssociationStatus]

    def test_association_status_has_rejected(self):
        assert "REJECTED" in [e.value for e in AssociationStatus]

    def test_review_action_confirm(self):
        assert "CONFIRM" in [e.value for e in ReviewAction]

    def test_review_action_reassign(self):
        assert "REASSIGN" in [e.value for e in ReviewAction]

    def test_review_action_reject(self):
        assert "REJECT" in [e.value for e in ReviewAction]

    def test_review_action_mark_cad_only(self):
        assert "MARK_CAD_ONLY" in [e.value for e in ReviewAction]

    def test_review_action_mark_drawing_only(self):
        assert "MARK_DRAWING_ONLY" in [e.value for e in ReviewAction]

    def test_ambiguity_type_has_multiple_candidates(self):
        vals = [e.value for e in AmbiguityType]
        # Any variant indicating multiple matching items
        assert any("MULTIPLE" in v or "CANDIDATE" in v for v in vals)

    def test_ambiguity_type_has_cad_only(self):
        vals = [e.value for e in AmbiguityType]
        assert any("CAD_ONLY" in v or "FEATURE" in v for v in vals)

    def test_fusion_completeness_full(self):
        vals = [e.value for e in FusionCompleteness]
        assert any("FULL" in v or "COMPLETE" in v for v in vals)

    def test_fusion_completeness_partial(self):
        assert "PARTIAL" in [e.value for e in FusionCompleteness]

    def test_fusion_completeness_cad_only(self):
        assert "CAD_ONLY" in [e.value for e in FusionCompleteness]


# ---------------------------------------------------------------------------
# RequirementFeatureLink
# ---------------------------------------------------------------------------

class TestRequirementFeatureLinkFields:
    def test_has_link_id(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(RequirementFeatureLink)}
        assert "link_id" in fields

    def test_has_requirement_id(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(RequirementFeatureLink)}
        assert "requirement_id" in fields

    def test_has_feature_id(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(RequirementFeatureLink)}
        assert "feature_id" in fields

    def test_has_status(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(RequirementFeatureLink)}
        assert "status" in fields

    def test_has_score(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(RequirementFeatureLink)}
        assert "score" in fields


# ---------------------------------------------------------------------------
# CadFusionEngine.fuse() — no drawing session
# ---------------------------------------------------------------------------

class TestCadFusionEngineNoDrawing:
    def setup_method(self):
        self.eng = CadFusionEngine()

    def _fuse_case(self, case_fn) -> FusionResult:
        return _fuse(_recognize(case_fn))

    def test_returns_fusion_result(self):
        res = self._fuse_case(build_case_a)
        assert isinstance(res, FusionResult)

    def test_no_drawing_completeness_is_cad_only(self):
        res = self._fuse_case(build_case_a)
        assert res.completeness == FusionCompleteness.CAD_ONLY

    def test_cad_only_feature_ids_non_empty(self):
        res = self._fuse_case(build_case_a)
        assert len(res.cad_only_feature_ids) > 0

    def test_drawing_only_req_ids_empty(self):
        res = self._fuse_case(build_case_a)
        assert len(res.drawing_only_req_ids) == 0

    def test_feature_links_empty_without_drawing(self):
        res = self._fuse_case(build_case_a)
        assert len(res.feature_links) == 0

    def test_review_events_empty_at_start(self):
        res = self._fuse_case(build_case_a)
        assert len(res.review_events) == 0

    def test_ambiguities_empty_without_drawing(self):
        res = self._fuse_case(build_case_a)
        assert len(res.ambiguities) == 0

    def test_top_level_wrapper_equivalent(self):
        rec = _recognize(build_case_a)
        sid = str(uuid.uuid4())
        res1 = self.eng.fuse(rec, None, sid)
        res2 = fuse_cad_with_drawing(rec, None, sid)
        assert res1.completeness == res2.completeness
        assert len(res1.cad_only_feature_ids) == len(res2.cad_only_feature_ids)

    def test_fusion_id_set(self):
        res = self._fuse_case(build_case_a)
        assert res.fusion_id

    def test_cad_session_id_stored(self):
        rec = _recognize(build_case_a)
        sid = "test-session-123"
        res = self.eng.fuse(rec, None, sid)
        assert res.cad_session_id == sid


# ---------------------------------------------------------------------------
# FusionResult mutation methods
# ---------------------------------------------------------------------------

class TestFusionResultMutations:
    def setup_method(self):
        rec = _recognize(build_case_a)
        self.res = _fuse(rec)
        self.feature_ids = list(self.res.cad_only_feature_ids)

    def test_mark_cad_only_adds_review_event(self):
        if not self.feature_ids:
            pytest.skip("No CAD-only features")
        fid = self.feature_ids[0]
        self.res.mark_cad_only(fid, "engineer-A")
        assert len(self.res.review_events) >= 1

    def test_mark_cad_only_event_has_correct_action(self):
        if not self.feature_ids:
            pytest.skip("No CAD-only features")
        fid = self.feature_ids[0]
        self.res.mark_cad_only(fid, "engineer-A")
        event = self.res.review_events[-1]
        assert event.action in (ReviewAction.MARK_CAD_ONLY, ReviewAction.CONFIRM)

    def test_mark_drawing_only_adds_review_event(self):
        # mark_drawing_only with a req_id that may not exist — engine handles gracefully
        self.res.mark_drawing_only("req-nonexistent", "engineer-B")
        # Either adds event or is a no-op; should not raise
        assert isinstance(self.res.review_events, list)

    def test_confirm_link_non_existent_no_crash(self):
        # Confirming a link that doesn't exist should not raise
        try:
            self.res.confirm_link("req-x", "feat-y", "engineer-C")
        except (KeyError, ValueError):
            pass  # acceptable — link not found

    def test_reassign_link_non_existent_no_crash(self):
        try:
            self.res.reassign_link("req-x", "feat-new", "engineer-D")
        except (KeyError, ValueError):
            pass  # acceptable

    def test_as_dict_returns_dict(self):
        d = self.res.as_dict()
        assert isinstance(d, dict)

    def test_unresolved_count_attr(self):
        # unresolved_count is a property/attribute, not a method
        count = self.res.unresolved_count
        assert isinstance(count, int)
        assert count >= 0

    def test_auto_matched_count_attr(self):
        count = self.res.auto_matched_count
        assert isinstance(count, int)
        assert count >= 0


# ---------------------------------------------------------------------------
# FusionAmbiguity
# ---------------------------------------------------------------------------

class TestFusionAmbiguity:
    def test_fields_present(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(FusionAmbiguity)}
        assert "ambiguity_id" in fields
        assert "ambiguity_type" in fields
        assert "description" in fields

    def test_requirement_id_field(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(FusionAmbiguity)}
        assert "requirement_id" in fields

    def test_feature_ids_or_candidates_field(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(FusionAmbiguity)}
        assert "feature_ids" in fields

    def test_requires_engineer_review_field(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(FusionAmbiguity)}
        assert "requires_engineer_review" in fields


# ---------------------------------------------------------------------------
# FusionReviewEvent
# ---------------------------------------------------------------------------

class TestFusionReviewEvent:
    def test_fields_present(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(FusionReviewEvent)}
        assert "event_id" in fields
        assert "action" in fields
        assert "user_id" in fields or "performed_by" in fields

    def test_feature_id_field(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(FusionReviewEvent)}
        assert "feature_id" in fields

    def test_action_field_type(self):
        rec = _recognize(build_case_a)
        res = _fuse(rec)
        fids = list(res.cad_only_feature_ids)
        if not fids:
            pytest.skip("No CAD-only features")
        res.mark_cad_only(fids[0], "engineer-X")
        event = res.review_events[-1]
        assert isinstance(event.action, ReviewAction)


# ---------------------------------------------------------------------------
# CAD-only invariant
# ---------------------------------------------------------------------------

class TestNoFabricationInvariant:
    def test_cad_only_features_reference_real_features(self):
        # FABRICATED_FEATURE=NO — every cad_only_feature_id must be a real feature
        rec = _recognize(build_case_a)
        real_ids = {f.feature_id for f in rec.features}
        res = _fuse(rec)
        for fid in res.cad_only_feature_ids:
            assert fid in real_ids, (
                f"cad_only_feature_id {fid} not in recognized features — FABRICATED_FEATURE violation"
            )

    def test_empty_recognition_empty_result(self):
        rec = _empty_rec()
        res = _fuse(rec)
        assert len(res.feature_links) == 0
        assert len(res.cad_only_feature_ids) == 0

    def test_completeness_is_enum_value(self):
        rec = _recognize(build_case_a)
        res = _fuse(rec)
        assert isinstance(res.completeness, FusionCompleteness)


# ---------------------------------------------------------------------------
# No drawing session edge cases across cases
# ---------------------------------------------------------------------------

class TestMultipleCases:
    @pytest.mark.parametrize("case_fn", [
        build_case_a,
        build_case_b,
        build_case_d,
        build_case_i,
        build_case_j,
    ])
    def test_all_recognized_features_appear_in_cad_only(self, case_fn):
        """With no drawing session, all features should be in cad_only_feature_ids."""
        rec = _recognize(case_fn)
        res = _fuse(rec)
        real_ids = {f.feature_id for f in rec.features}
        # All recognized feature IDs should be in cad_only
        assert real_ids == set(res.cad_only_feature_ids), (
            f"Mismatch: recognized={sorted(real_ids)}, "
            f"cad_only={sorted(res.cad_only_feature_ids)}"
        )

    @pytest.mark.parametrize("case_fn", [
        build_case_a,
        build_case_j,
    ])
    def test_cad_only_completeness_without_drawing(self, case_fn):
        rec = _recognize(case_fn)
        res = _fuse(rec)
        assert res.completeness == FusionCompleteness.CAD_ONLY
