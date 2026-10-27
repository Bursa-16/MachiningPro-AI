"""Graphical association engine for drawing semantic extraction.

Associates parsed annotations (dimensions, GDT, fits, threads, surface finish)
to manufacturing features using spatial proximity and type compatibility.

FABRICATED_FEATURE_ASSOCIATION=NO
All associations are candidate-ranked; no automatic confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum, unique


@unique
class AssociationState(StrEnum):
    AUTO_MATCHED = "AUTO_MATCHED"           # Single unambiguous spatial match
    MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"  # >1 candidate; needs review
    UNRESOLVED = "UNRESOLVED"               # No candidate found
    USER_MATCHED = "USER_MATCHED"           # Engineer confirmed


@unique
class AnnotationType(StrEnum):
    DIMENSION = "DIMENSION"
    GDT = "GDT"
    FIT = "FIT"
    THREAD = "THREAD"
    SURFACE_FINISH = "SURFACE_FINISH"
    NOTE = "NOTE"
    TITLE_FIELD = "TITLE_FIELD"
    DATUM = "DATUM"


@unique
class FeatureType(StrEnum):
    HOLE = "HOLE"
    THREADED_HOLE = "THREADED_HOLE"
    PLANAR_FACE = "PLANAR_FACE"
    CYLINDRICAL_FACE = "CYLINDRICAL_FACE"
    FILLET = "FILLET"
    CHAMFER = "CHAMFER"
    HOLE_PATTERN = "HOLE_PATTERN"
    SHAFT = "SHAFT"
    PART = "PART"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class BoundingBox2D:
    x: Decimal
    y: Decimal
    width: Decimal
    height: Decimal

    @property
    def cx(self) -> Decimal:
        return self.x + self.width / 2

    @property
    def cy(self) -> Decimal:
        return self.y + self.height / 2


@dataclass(frozen=True)
class AssociationCandidate:
    """A ranked candidate feature association for an annotation."""
    feature_id: str
    feature_type: FeatureType
    spatial_score: Decimal      # 0–1; proximity score
    semantic_score: Decimal     # 0–1; type compatibility score
    combined_score: Decimal     # weighted combination


@dataclass(frozen=True)
class AnnotationAssociation:
    """Result of associating a parsed annotation to features."""
    annotation_id: str
    annotation_type: AnnotationType
    state: AssociationState
    candidates: tuple[AssociationCandidate, ...]
    confirmed_feature_id: str | None    # Set only when USER_MATCHED or AUTO_MATCHED
    inferred_feature_type: FeatureType  # Best-guess type from annotation semantics


def _bbox_distance(a: BoundingBox2D, b: BoundingBox2D) -> Decimal:
    """Euclidean distance between centers of two bounding boxes."""
    dx = a.cx - b.cx
    dy = a.cy - b.cy
    return (dx * dx + dy * dy).sqrt()


def _proximity_score(distance: Decimal, max_distance: Decimal) -> Decimal:
    """Returns 1.0 at distance=0, 0.0 at distance>=max_distance."""
    if max_distance <= Decimal("0"):
        return Decimal("0")
    if distance >= max_distance:
        return Decimal("0")
    return (Decimal("1") - distance / max_distance).max(Decimal("0"))


def _semantic_score(annotation_type: AnnotationType, feature_type: FeatureType) -> Decimal:
    """Type compatibility score between annotation and feature types."""
    _COMPAT: dict[tuple[AnnotationType, FeatureType], Decimal] = {
        (AnnotationType.DIMENSION, FeatureType.HOLE): Decimal("0.8"),
        (AnnotationType.DIMENSION, FeatureType.PLANAR_FACE): Decimal("0.7"),
        (AnnotationType.DIMENSION, FeatureType.CYLINDRICAL_FACE): Decimal("0.7"),
        (AnnotationType.FIT, FeatureType.HOLE): Decimal("1.0"),
        (AnnotationType.FIT, FeatureType.SHAFT): Decimal("1.0"),
        (AnnotationType.THREAD, FeatureType.THREADED_HOLE): Decimal("1.0"),
        (AnnotationType.SURFACE_FINISH, FeatureType.PLANAR_FACE): Decimal("0.9"),
        (AnnotationType.SURFACE_FINISH, FeatureType.CYLINDRICAL_FACE): Decimal("0.8"),
        (AnnotationType.GDT, FeatureType.HOLE): Decimal("0.85"),
        (AnnotationType.GDT, FeatureType.HOLE_PATTERN): Decimal("0.9"),
        (AnnotationType.GDT, FeatureType.PLANAR_FACE): Decimal("0.8"),
        (AnnotationType.GDT, FeatureType.CYLINDRICAL_FACE): Decimal("0.8"),
    }
    return _COMPAT.get((annotation_type, feature_type), Decimal("0.5"))


def infer_feature_type(
    annotation_type: AnnotationType,
    annotation_subtype: str | None = None,
) -> FeatureType:
    """Infer the likely feature type from annotation type and subtype."""
    if annotation_type == AnnotationType.FIT:
        if annotation_subtype and annotation_subtype.startswith("HOLE"):
            return FeatureType.HOLE
        if annotation_subtype and annotation_subtype.startswith("SHAFT"):
            return FeatureType.SHAFT
        return FeatureType.HOLE  # fits more commonly on holes
    if annotation_type == AnnotationType.THREAD:
        return FeatureType.THREADED_HOLE
    if annotation_type == AnnotationType.SURFACE_FINISH:
        return FeatureType.PLANAR_FACE
    if annotation_type == AnnotationType.GDT:
        return FeatureType.HOLE
    if annotation_type == AnnotationType.DIMENSION:
        if annotation_subtype == "DIAMETRAL":
            return FeatureType.HOLE
        if annotation_subtype == "RADIAL":
            return FeatureType.FILLET
        return FeatureType.PLANAR_FACE
    return FeatureType.UNKNOWN


def associate_annotation(
    annotation_id: str,
    annotation_type: AnnotationType,
    annotation_bbox: BoundingBox2D | None,
    annotation_subtype: str | None,
    feature_bboxes: dict[str, tuple[BoundingBox2D, FeatureType]],
    *,
    max_proximity_pts: Decimal = Decimal("72"),
    proximity_weight: Decimal = Decimal("0.6"),
    semantic_weight: Decimal = Decimal("0.4"),
) -> AnnotationAssociation:
    """Associate an annotation to candidate features using spatial + type rules."""

    inferred_type = infer_feature_type(annotation_type, annotation_subtype)

    if not feature_bboxes or annotation_bbox is None:
        return AnnotationAssociation(
            annotation_id=annotation_id,
            annotation_type=annotation_type,
            state=AssociationState.UNRESOLVED,
            candidates=(),
            confirmed_feature_id=None,
            inferred_feature_type=inferred_type,
        )

    candidates: list[AssociationCandidate] = []
    for feat_id, (feat_bbox, feat_type) in feature_bboxes.items():
        dist = _bbox_distance(annotation_bbox, feat_bbox)
        prox = _proximity_score(dist, max_proximity_pts)
        sem = _semantic_score(annotation_type, feat_type)
        combined = proximity_weight * prox + semantic_weight * sem
        if combined > Decimal("0"):
            candidates.append(AssociationCandidate(
                feature_id=feat_id,
                feature_type=feat_type,
                spatial_score=prox,
                semantic_score=sem,
                combined_score=combined,
            ))

    candidates.sort(key=lambda c: c.combined_score, reverse=True)
    candidates_tuple = tuple(candidates[:5])  # keep top 5

    if not candidates_tuple:
        return AnnotationAssociation(
            annotation_id=annotation_id,
            annotation_type=annotation_type,
            state=AssociationState.UNRESOLVED,
            candidates=(),
            confirmed_feature_id=None,
            inferred_feature_type=inferred_type,
        )

    # Single confident match: top score ≥ 0.70 and well separated from second
    top = candidates_tuple[0]
    if top.combined_score >= Decimal("0.70"):
        if len(candidates_tuple) == 1 or (
            candidates_tuple[1].combined_score < top.combined_score - Decimal("0.15")
        ):
            return AnnotationAssociation(
                annotation_id=annotation_id,
                annotation_type=annotation_type,
                state=AssociationState.AUTO_MATCHED,
                candidates=candidates_tuple,
                confirmed_feature_id=top.feature_id,
                inferred_feature_type=inferred_type,
            )

    return AnnotationAssociation(
        annotation_id=annotation_id,
        annotation_type=annotation_type,
        state=AssociationState.MULTIPLE_CANDIDATES,
        candidates=candidates_tuple,
        confirmed_feature_id=None,
        inferred_feature_type=inferred_type,
    )
