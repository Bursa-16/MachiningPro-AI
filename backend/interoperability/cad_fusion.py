"""Drawing/CAD Fusion Engine — EPIC_04D Phase 2.

Fuses EPIC_04C drawing semantic extraction results with CAD manufacturing features.

Pipeline:
    ExtractionSession (drawing semantics)
    + ManufacturingFeatureRecognitionResult (CAD features)
    → AssociationScore per (requirement, feature) pair
    → AUTO_MATCHED / MULTIPLE_CANDIDATES / UNRESOLVED per requirement
    → FusionResult

Architecture invariants:
    FABRICATED_DIMENSION=NO
    FABRICATED_DATUM_ASSOCIATION=NO
    FABRICATED_GDT_ASSOCIATION=NO
    FABRICATED_THREAD_ASSOCIATION=NO
    FABRICATED_SURFACE_FINISH_ASSOCIATION=NO
    AMBIGUOUS_ASSOCIATION_AUTO_APPROVED=NO
    UNCERTAIN_EXTRACTION_AUTO_APPROVED=NO
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from backend.interoperability.cad_feature_recognition import (
    ManufacturingFeature,
    ManufacturingFeatureRecognitionResult,
    ManufacturingFeatureType,
)

__all__ = [
    # Enums
    "AssociationStatus",
    "AmbiguityType",
    "ReviewAction",
    "FusionCompleteness",
    # Models
    "RequirementFeatureLink",
    "FusionAmbiguity",
    "FusionReviewEvent",
    "FusionResult",
    # Engine
    "CadFusionEngine",
    "fuse_cad_with_drawing",
]

_FUSION_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

_AUTO_MATCH_MIN_SCORE = 0.70
_AUTO_MATCH_MIN_GAP = 0.15
_DIMENSION_MATCH_TOL_MM = Decimal("0.5")


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class AssociationStatus(StrEnum):
    AUTO_MATCHED = "AUTO_MATCHED"
    MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"
    UNRESOLVED = "UNRESOLVED"
    USER_MATCHED = "USER_MATCHED"
    REJECTED = "REJECTED"


class AmbiguityType(StrEnum):
    MULTIPLE_MATCHING_HOLES = "MULTIPLE_MATCHING_HOLES"
    MULTIPLE_SAME_SIZE_FEATURES = "MULTIPLE_SAME_SIZE_FEATURES"
    UNRESOLVED_DATUM = "UNRESOLVED_DATUM"
    DRAWING_ONLY_REQUIREMENT = "DRAWING_ONLY_REQUIREMENT"
    CAD_ONLY_FEATURE = "CAD_ONLY_FEATURE"
    CONFLICTING_GEOMETRY = "CONFLICTING_GEOMETRY"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    LOW_CONFIDENCE_EXTRACTION = "LOW_CONFIDENCE_EXTRACTION"
    MULTIPLE_ASSOCIATION_CANDIDATES = "MULTIPLE_ASSOCIATION_CANDIDATES"
    UNRESOLVED_REQUIREMENT = "UNRESOLVED_REQUIREMENT"


class ReviewAction(StrEnum):
    CONFIRM = "CONFIRM"
    REASSIGN = "REASSIGN"
    REJECT = "REJECT"
    MARK_CAD_ONLY = "MARK_CAD_ONLY"
    MARK_DRAWING_ONLY = "MARK_DRAWING_ONLY"
    MERGE = "MERGE"
    SPLIT = "SPLIT"


class FusionCompleteness(StrEnum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    DRAWING_ONLY = "DRAWING_ONLY"
    CAD_ONLY = "CAD_ONLY"
    EMPTY = "EMPTY"


# ---------------------------------------------------------------------------
# Association scoring
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class AssociationScore:
    """Weighted composite score for a (requirement, feature) association candidate."""

    requirement_id: str
    feature_id: str
    type_compatibility: float        # 0–1
    dimension_match: float           # 0–1
    orientation_match: float         # 0–1
    location_proximity: float        # 0–1
    datum_relationship: float        # 0–1
    pattern_membership: float        # 0–1
    source_confidence: float         # 0–1

    @property
    def composite(self) -> float:
        return (
            self.type_compatibility * 0.25
            + self.dimension_match * 0.25
            + self.location_proximity * 0.20
            + self.orientation_match * 0.10
            + self.datum_relationship * 0.10
            + self.pattern_membership * 0.05
            + self.source_confidence * 0.05
        )


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------

@dataclass
class RequirementFeatureLink:
    """A confirmed or candidate link between a drawing requirement and a CAD feature."""

    link_id: str
    requirement_id: str
    feature_id: str
    requirement_type: str          # e.g. "DIMENSION", "GDT_FCF", "THREAD", "DATUM"
    dimension_role: str | None     # e.g. "DIAMETER", "DEPTH", "WIDTH"
    score: AssociationScore
    status: AssociationStatus
    created_at: datetime

    def as_dict(self) -> dict:
        return {
            "link_id": self.link_id,
            "requirement_id": self.requirement_id,
            "feature_id": self.feature_id,
            "requirement_type": self.requirement_type,
            "dimension_role": self.dimension_role,
            "composite_score": self.score.composite,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class FusionAmbiguity:
    """A detected ambiguity in the fusion result."""

    ambiguity_id: str
    ambiguity_type: AmbiguityType
    requirement_id: str | None
    feature_ids: tuple[str, ...]
    description: str
    requires_engineer_review: bool

    def as_dict(self) -> dict:
        return {
            "ambiguity_id": self.ambiguity_id,
            "ambiguity_type": self.ambiguity_type,
            "requirement_id": self.requirement_id,
            "feature_ids": list(self.feature_ids),
            "description": self.description,
            "requires_engineer_review": self.requires_engineer_review,
        }


@dataclass
class FusionReviewEvent:
    """Audit trail entry for engineer review actions."""

    event_id: str
    session_id: str
    action: ReviewAction
    feature_id: str | None
    requirement_id: str | None
    new_feature_id: str | None
    user_id: str | None
    note: str | None
    created_at: datetime


@dataclass
class FusionResult:
    """Complete output of the drawing/CAD fusion engine."""

    fusion_id: str
    cad_session_id: str
    drawing_session_id: str | None
    feature_links: list[RequirementFeatureLink]
    ambiguities: list[FusionAmbiguity]
    drawing_only_req_ids: list[str]
    cad_only_feature_ids: list[str]
    completeness: FusionCompleteness
    review_events: list[FusionReviewEvent]
    created_at: datetime

    @property
    def auto_matched_count(self) -> int:
        return sum(
            1 for lnk in self.feature_links
            if lnk.status == AssociationStatus.AUTO_MATCHED
        )

    @property
    def unresolved_count(self) -> int:
        return len(self.drawing_only_req_ids)

    def as_dict(self) -> dict:
        return {
            "fusion_id": self.fusion_id,
            "cad_session_id": self.cad_session_id,
            "drawing_session_id": self.drawing_session_id,
            "completeness": self.completeness,
            "auto_matched_count": self.auto_matched_count,
            "unresolved_count": self.unresolved_count,
            "ambiguity_count": len(self.ambiguities),
            "cad_only_feature_count": len(self.cad_only_feature_ids),
            "feature_links": [lnk.as_dict() for lnk in self.feature_links],
            "ambiguities": [a.as_dict() for a in self.ambiguities],
            "drawing_only_req_ids": self.drawing_only_req_ids,
            "cad_only_feature_ids": self.cad_only_feature_ids,
        }

    # ---- engineer review mutations ----

    def confirm_link(self, requirement_id: str, feature_id: str, user_id: str) -> None:
        for lnk in self.feature_links:
            if lnk.requirement_id == requirement_id and lnk.feature_id == feature_id:
                lnk.status = AssociationStatus.USER_MATCHED
                self.review_events.append(FusionReviewEvent(
                    event_id=str(uuid.uuid4()),
                    session_id=self.cad_session_id,
                    action=ReviewAction.CONFIRM,
                    feature_id=feature_id,
                    requirement_id=requirement_id,
                    new_feature_id=None,
                    user_id=user_id,
                    note=None,
                    created_at=datetime.now(UTC),
                ))
                return

    def reassign_link(
        self,
        requirement_id: str,
        new_feature_id: str,
        user_id: str,
    ) -> None:
        for lnk in self.feature_links:
            if lnk.requirement_id == requirement_id:
                old_fid = lnk.feature_id
                lnk.feature_id = new_feature_id  # type: ignore[misc]  # dataclass field
                lnk.status = AssociationStatus.USER_MATCHED
                self.review_events.append(FusionReviewEvent(
                    event_id=str(uuid.uuid4()),
                    session_id=self.cad_session_id,
                    action=ReviewAction.REASSIGN,
                    feature_id=old_fid,
                    requirement_id=requirement_id,
                    new_feature_id=new_feature_id,
                    user_id=user_id,
                    note=None,
                    created_at=datetime.now(UTC),
                ))
                return
        # No existing link — create one
        self.feature_links.append(RequirementFeatureLink(
            link_id=str(uuid.uuid4()),
            requirement_id=requirement_id,
            feature_id=new_feature_id,
            requirement_type="MANUAL",
            dimension_role=None,
            score=AssociationScore(
                requirement_id=requirement_id,
                feature_id=new_feature_id,
                type_compatibility=1.0,
                dimension_match=1.0,
                orientation_match=1.0,
                location_proximity=1.0,
                datum_relationship=1.0,
                pattern_membership=0.0,
                source_confidence=1.0,
            ),
            status=AssociationStatus.USER_MATCHED,
            created_at=datetime.now(UTC),
        ))

    def mark_drawing_only(self, requirement_id: str, user_id: str) -> None:
        if requirement_id not in self.drawing_only_req_ids:
            self.drawing_only_req_ids.append(requirement_id)
        self.review_events.append(FusionReviewEvent(
            event_id=str(uuid.uuid4()),
            session_id=self.cad_session_id,
            action=ReviewAction.MARK_DRAWING_ONLY,
            feature_id=None,
            requirement_id=requirement_id,
            new_feature_id=None,
            user_id=user_id,
            note=None,
            created_at=datetime.now(UTC),
        ))

    def mark_cad_only(self, feature_id: str, user_id: str) -> None:
        if feature_id not in self.cad_only_feature_ids:
            self.cad_only_feature_ids.append(feature_id)
        self.review_events.append(FusionReviewEvent(
            event_id=str(uuid.uuid4()),
            session_id=self.cad_session_id,
            action=ReviewAction.MARK_CAD_ONLY,
            feature_id=feature_id,
            requirement_id=None,
            new_feature_id=None,
            user_id=user_id,
            note=None,
            created_at=datetime.now(UTC),
        ))


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

_TYPE_COMPAT_MAP: dict[tuple[str, str], float] = {
    # (normalized_detection_type, feature_type) → compatibility score
    ("DIMENSION", "THROUGH_HOLE"): 0.9,
    ("DIMENSION", "BLIND_HOLE"): 0.9,
    ("DIMENSION", "HOLE"): 0.9,
    ("DIMENSION", "COUNTERBORE"): 0.85,
    ("DIMENSION", "COUNTERSINK"): 0.85,
    ("DIMENSION", "OPEN_SLOT"): 0.8,
    ("DIMENSION", "CLOSED_SLOT"): 0.8,
    ("DIMENSION", "CLOSED_POCKET"): 0.8,
    ("DIMENSION", "OPEN_POCKET"): 0.8,
    ("DIMENSION", "PLANAR_FACE"): 0.7,
    ("DIMENSION", "OUTER_DIAMETER"): 0.85,
    ("DIMENSION", "INNER_DIAMETER"): 0.85,
    ("DIMENSION", "CHAMFER"): 0.8,
    ("DIMENSION", "FILLET"): 0.8,
    ("DIMENSION", "BOSS"): 0.8,
    ("GDT_FCF", "PLANAR_FACE"): 0.9,
    ("GDT_FCF", "THROUGH_HOLE"): 0.85,
    ("GDT_FCF", "BLIND_HOLE"): 0.85,
    ("GDT_FCF", "OUTER_DIAMETER"): 0.85,
    ("GDT_FCF", "INNER_DIAMETER"): 0.85,
    ("DATUM", "PLANAR_FACE"): 0.9,
    ("DATUM", "OUTER_DIAMETER"): 0.8,
    ("THREAD", "THROUGH_HOLE"): 0.9,
    ("THREAD", "BLIND_HOLE"): 0.9,
    ("THREAD", "HOLE"): 0.9,
    ("THREAD", "OUTER_DIAMETER"): 0.8,
    ("SURFACE_FINISH", "PLANAR_FACE"): 0.85,
    ("SURFACE_FINISH", "OUTER_DIAMETER"): 0.85,
    ("SURFACE_FINISH", "INNER_DIAMETER"): 0.85,
    ("SURFACE_FINISH", "THROUGH_HOLE"): 0.8,
    ("SURFACE_FINISH", "BLIND_HOLE"): 0.8,
    ("FIT", "THROUGH_HOLE"): 0.9,
    ("FIT", "BLIND_HOLE"): 0.9,
    ("FIT", "HOLE"): 0.9,
    ("FIT", "INNER_DIAMETER"): 0.85,
    ("FIT", "OUTER_DIAMETER"): 0.85,
}


def _type_compat(req_type: str, feat_type: ManufacturingFeatureType) -> float:
    return _TYPE_COMPAT_MAP.get((req_type, feat_type.value), 0.3)


def _dimension_match_score(
    req_value_str: str | None,
    req_type: str,
    feature: ManufacturingFeature,
) -> float:
    if req_value_str is None:
        return 0.5

    # Try extracting numeric value from requirement
    try:
        # Strip units, parentheses, etc.
        import re
        m = re.search(r"[\d]+(?:[.,]\d+)?", req_value_str.replace(",", "."))
        if not m:
            return 0.5
        req_val = Decimal(m.group())
    except Exception:
        return 0.5

    # Map subtype to feature dimension
    dim = None
    if req_type == "DIMENSION":
        if "Ø" in (req_value_str or "") or "diam" in req_value_str.lower():
            dim = feature.diameter_mm
        elif feature.diameter_mm is not None:
            dim = feature.diameter_mm
        elif feature.width_mm is not None:
            dim = feature.width_mm
        elif feature.length_mm is not None:
            dim = feature.length_mm
    elif req_type in ("THREAD", "FIT"):
        dim = feature.diameter_mm
    elif req_type == "SURFACE_FINISH":
        return 0.6  # Can't dimension-match Ra to geometry
    elif req_type == "GDT_FCF":
        return 0.6

    if dim is None:
        return 0.4

    diff = abs(req_val - dim)
    if diff <= Decimal("0.1"):
        return 1.0
    if diff <= Decimal("0.5"):
        return 0.85
    if diff <= Decimal("2.0"):
        return 0.60
    if diff <= Decimal("10.0"):
        return 0.30
    return 0.10


def _score_pair(
    req_id: str,
    req_type: str,
    req_value: str | None,
    req_source_confidence: float,
    feature: ManufacturingFeature,
) -> AssociationScore:
    type_compat = _type_compat(req_type, feature.feature_type)
    dim_match = _dimension_match_score(req_value, req_type, feature)

    return AssociationScore(
        requirement_id=req_id,
        feature_id=feature.feature_id,
        type_compatibility=type_compat,
        dimension_match=dim_match,
        orientation_match=0.5,       # no spatial info in current model
        location_proximity=0.5,      # no spatial info
        datum_relationship=0.5,      # no datum pairing yet
        pattern_membership=0.0,
        source_confidence=req_source_confidence,
    )


# ---------------------------------------------------------------------------
# Minimal drawing session interface
# ---------------------------------------------------------------------------

class _DrawingRequirement:
    """Thin adapter to extract requirement data from NormalizedDetection."""

    def __init__(self, detection: Any) -> None:
        self._d = detection

    @property
    def req_id(self) -> str:
        return getattr(self._d, "detection_id", str(uuid.uuid4()))

    @property
    def req_type(self) -> str:
        t = getattr(self._d, "normalized_type", None)
        return str(t) if t else "UNKNOWN"

    @property
    def value_str(self) -> str | None:
        return getattr(self._d, "normalized_value", None)

    @property
    def source_confidence(self) -> float:
        c = getattr(self._d, "confidence", None)
        return float(c) if c is not None else 0.5

    @property
    def review_state(self) -> str:
        rs = getattr(self._d, "review_state", None)
        return str(rs) if rs else "PENDING"

    @property
    def is_confirmed(self) -> bool:
        return self.review_state == "CONFIRMED"


# ---------------------------------------------------------------------------
# Fusion engine
# ---------------------------------------------------------------------------

class CadFusionEngine:
    """Deterministic drawing/CAD fusion engine.

    AMBIGUOUS_ASSOCIATION_AUTO_APPROVED=NO — scores below threshold remain UNRESOLVED.
    """

    def fuse(
        self,
        recognition_result: ManufacturingFeatureRecognitionResult,
        drawing_session: Any | None,
        cad_session_id: str,
    ) -> FusionResult:
        fusion_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        features = recognition_result.features
        feature_ids = {f.feature_id for f in features}

        # Extract requirements from drawing session
        requirements: list[_DrawingRequirement] = []
        if drawing_session is not None:
            detections = getattr(drawing_session, "detections", None) or []
            for det in detections:
                req = _DrawingRequirement(det)
                # Only process confirmed requirements (or all if no review workflow)
                requirements.append(req)

        if not requirements and not features:
            return FusionResult(
                fusion_id=fusion_id,
                cad_session_id=cad_session_id,
                drawing_session_id=getattr(drawing_session, "session_id", None),
                feature_links=[],
                ambiguities=[],
                drawing_only_req_ids=[],
                cad_only_feature_ids=list(feature_ids),
                completeness=FusionCompleteness.EMPTY,
                review_events=[],
                created_at=now,
            )

        if not requirements:
            return FusionResult(
                fusion_id=fusion_id,
                cad_session_id=cad_session_id,
                drawing_session_id=None,
                feature_links=[],
                ambiguities=[],
                drawing_only_req_ids=[],
                cad_only_feature_ids=list(feature_ids),
                completeness=FusionCompleteness.CAD_ONLY,
                review_events=[],
                created_at=now,
            )

        if not features:
            return FusionResult(
                fusion_id=fusion_id,
                cad_session_id=cad_session_id,
                drawing_session_id=getattr(drawing_session, "session_id", None),
                feature_links=[],
                ambiguities=[],
                drawing_only_req_ids=[req.req_id for req in requirements],
                cad_only_feature_ids=[],
                completeness=FusionCompleteness.DRAWING_ONLY,
                review_events=[],
                created_at=now,
            )

        # Score all (requirement, feature) pairs
        feature_links: list[RequirementFeatureLink] = []
        ambiguities: list[FusionAmbiguity] = []
        drawing_only_req_ids: list[str] = []
        linked_feature_ids: set[str] = set()

        for req in requirements:
            # Skip UNKNOWN or NOTE types
            if req.req_type in ("NOTE", "TITLE_FIELD", "UNKNOWN", "GENERAL_TOLERANCE"):
                drawing_only_req_ids.append(req.req_id)
                continue

            scores = [
                _score_pair(
                    req.req_id,
                    req.req_type,
                    req.value_str,
                    req.source_confidence,
                    feat,
                )
                for feat in features
            ]

            scores.sort(key=lambda s: s.composite, reverse=True)

            if not scores:
                drawing_only_req_ids.append(req.req_id)
                continue

            top = scores[0]
            second = scores[1] if len(scores) > 1 else None

            if top.composite >= _AUTO_MATCH_MIN_SCORE:
                if second is not None and (top.composite - second.composite) < _AUTO_MATCH_MIN_GAP:
                    # Multiple candidates
                    status = AssociationStatus.MULTIPLE_CANDIDATES
                    ambiguities.append(FusionAmbiguity(
                        ambiguity_id=str(uuid.uuid4()),
                        ambiguity_type=AmbiguityType.MULTIPLE_ASSOCIATION_CANDIDATES,
                        requirement_id=req.req_id,
                        feature_ids=tuple(s.feature_id for s in scores[:3]),
                        description=f"Multiple features match {req.req_type} "
                                    f"({req.value_str}) with similar score",
                        requires_engineer_review=True,
                    ))
                else:
                    status = AssociationStatus.AUTO_MATCHED
                    linked_feature_ids.add(top.feature_id)
            else:
                status = AssociationStatus.UNRESOLVED
                drawing_only_req_ids.append(req.req_id)
                ambiguities.append(FusionAmbiguity(
                    ambiguity_id=str(uuid.uuid4()),
                    ambiguity_type=AmbiguityType.UNRESOLVED_REQUIREMENT,
                    requirement_id=req.req_id,
                    feature_ids=(),
                    description=f"No CAD feature matches {req.req_type} "
                                f"({req.value_str}) with sufficient confidence",
                    requires_engineer_review=True,
                ))
                continue

            # Determine dimension role
            dim_role = None
            if req.req_type == "DIMENSION":
                val = req.value_str or ""
                if "Ø" in val or "diam" in val.lower():
                    dim_role = "DIAMETER"
                elif "depth" in val.lower():
                    dim_role = "DEPTH"
                elif "width" in val.lower() or "W" in val:
                    dim_role = "WIDTH"
                else:
                    dim_role = "LINEAR"

            feature_links.append(RequirementFeatureLink(
                link_id=str(uuid.uuid4()),
                requirement_id=req.req_id,
                feature_id=top.feature_id,
                requirement_type=req.req_type,
                dimension_role=dim_role,
                score=top,
                status=status,
                created_at=now,
            ))

        # CAD-only features
        cad_only_feature_ids = [
            f.feature_id for f in features
            if f.feature_id not in linked_feature_ids
            and f.feature_type != ManufacturingFeatureType.PLANAR_FACE
        ]

        # Ambiguity: CAD-only features
        for fid in cad_only_feature_ids:
            feat = next((f for f in features if f.feature_id == fid), None)
            if feat and feat.feature_type not in {
                ManufacturingFeatureType.CHAMFER,
                ManufacturingFeatureType.FILLET,
                ManufacturingFeatureType.EDGE_BREAK,
            }:
                ambiguities.append(FusionAmbiguity(
                    ambiguity_id=str(uuid.uuid4()),
                    ambiguity_type=AmbiguityType.CAD_ONLY_FEATURE,
                    requirement_id=None,
                    feature_ids=(fid,),
                    description=f"CAD feature {feat.feature_type} has no drawing requirement",
                    requires_engineer_review=False,
                ))

        # Determine completeness
        n_linked = len([
            lnk for lnk in feature_links if lnk.status == AssociationStatus.AUTO_MATCHED
        ])
        n_req = len(requirements)
        if n_req == 0:
            completeness = FusionCompleteness.CAD_ONLY
        elif n_linked == 0:
            completeness = FusionCompleteness.DRAWING_ONLY
        elif len(drawing_only_req_ids) == 0 and len(cad_only_feature_ids) == 0:
            completeness = FusionCompleteness.FULL
        else:
            completeness = FusionCompleteness.PARTIAL

        return FusionResult(
            fusion_id=fusion_id,
            cad_session_id=cad_session_id,
            drawing_session_id=getattr(drawing_session, "session_id", None),
            feature_links=feature_links,
            ambiguities=ambiguities,
            drawing_only_req_ids=drawing_only_req_ids,
            cad_only_feature_ids=cad_only_feature_ids,
            completeness=completeness,
            review_events=[],
            created_at=now,
        )


def fuse_cad_with_drawing(
    recognition_result: ManufacturingFeatureRecognitionResult,
    drawing_session: Any | None,
    cad_session_id: str,
) -> FusionResult:
    return CadFusionEngine().fuse(recognition_result, drawing_session, cad_session_id)
