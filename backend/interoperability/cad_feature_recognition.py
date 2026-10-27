"""CAD Feature Recognition Engine — EPIC_04D Phase 2.

Operates on CanonicalTopology + CanonicalGeometry (produced by any format adapter)
and applies deterministic topology/geometry rules to produce ManufacturingFeature records.

Pipeline:
    CanonicalTopology + CanonicalGeometry
        → face/edge classification
        → adjacency index
        → feature detection rules (holes, pockets, slots, bosses, chamfers, fillets, turning)
        → pattern detection
        → accessibility estimation
        → tool reach requirements
        → ManufacturingFeatureRecognitionResult

Architecture invariants:
    FABRICATED_FEATURE=NO       — only features with geometric evidence are returned
    COLLISION_FREE_CLAIM=NO     — accessibility is candidate only, no toolpath proof
    UNCERTAIN_FEATURE_AUTO_APPROVED=NO
    CAD_ONLY_MODE_INVENTS_TOLERANCES=NO
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

from backend.domain.units import Quantity, Unit
from backend.interoperability.geometry import (
    BoundingBox3D,
    CanonicalGeometry,
    CanonicalPoint3D,
    CanonicalSurface,
    CanonicalSurfaceType,
    CanonicalVector3D,
)
from backend.interoperability.topology import (
    CanonicalBody,
    CanonicalEdge,
    CanonicalFace,
    CanonicalLoop,
    CanonicalShell,
    CanonicalTopology,
    LoopType,
)

__all__ = [
    # Enums
    "ManufacturingFeatureType",
    "RecognitionMethod",
    "FeatureRecognitionConfidence",
    "PatternType",
    "AxisCount",
    # Feature models
    "ManufacturingFeature",
    "FeaturePattern",
    "FeatureAccessibility",
    "ToolReachRequirement",
    "SetupCandidate",
    # Topology analysis
    "FaceAdjacencyIndex",
    "build_adjacency_index",
    # Recognition result
    "ManufacturingFeatureRecognitionResult",
    # Engine
    "FeatureRecognitionEngine",
    "recognize_manufacturing_features",
    # DXF 2D support
    "Dxf2dEntity",
    "recognize_dxf_features",
]

_RECOGNITION_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ManufacturingFeatureType(StrEnum):
    HOLE = "HOLE"
    BLIND_HOLE = "BLIND_HOLE"
    THROUGH_HOLE = "THROUGH_HOLE"
    COUNTERBORE = "COUNTERBORE"
    COUNTERSINK = "COUNTERSINK"
    STEPPED_HOLE = "STEPPED_HOLE"
    THREADED_HOLE_CANDIDATE = "THREADED_HOLE_CANDIDATE"
    PRECISION_BORE_CANDIDATE = "PRECISION_BORE_CANDIDATE"
    CLOSED_POCKET = "CLOSED_POCKET"
    OPEN_POCKET = "OPEN_POCKET"
    ISLAND = "ISLAND"
    OPEN_SLOT = "OPEN_SLOT"
    CLOSED_SLOT = "CLOSED_SLOT"
    BOSS = "BOSS"
    STEP = "STEP"
    SHOULDER = "SHOULDER"
    PAD = "PAD"
    CHAMFER = "CHAMFER"
    FILLET = "FILLET"
    EDGE_BREAK = "EDGE_BREAK"
    OUTER_DIAMETER = "OUTER_DIAMETER"
    INNER_DIAMETER = "INNER_DIAMETER"
    GROOVE = "GROOVE"
    FACE_TURN = "FACE_TURN"
    TAPER = "TAPER"
    PLANAR_FACE = "PLANAR_FACE"
    FREEFORM = "FREEFORM"
    TURNING_DIAMETER = "TURNING_DIAMETER"
    UNKNOWN = "UNKNOWN"


class RecognitionMethod(StrEnum):
    BREP_TOPOLOGY = "BREP_TOPOLOGY"
    SURFACE_HEURISTIC = "SURFACE_HEURISTIC"
    DXF_2D = "DXF_2D"
    INFERRED = "INFERRED"


class FeatureRecognitionConfidence(StrEnum):
    EXACT_BREP = "EXACT_BREP"
    TOPOLOGY_RULE = "TOPOLOGY_RULE"
    GEOMETRY_RULE = "GEOMETRY_RULE"
    PATTERN_RECOGNIZED = "PATTERN_RECOGNIZED"
    INFERRED = "INFERRED"
    AMBIGUOUS = "AMBIGUOUS"
    USER_CONFIRMED = "USER_CONFIRMED"


_CONFIDENCE_SCORES: dict[FeatureRecognitionConfidence, float] = {
    FeatureRecognitionConfidence.EXACT_BREP: 0.97,
    FeatureRecognitionConfidence.TOPOLOGY_RULE: 0.90,
    FeatureRecognitionConfidence.GEOMETRY_RULE: 0.80,
    FeatureRecognitionConfidence.PATTERN_RECOGNIZED: 0.75,
    FeatureRecognitionConfidence.INFERRED: 0.60,
    FeatureRecognitionConfidence.AMBIGUOUS: 0.40,
    FeatureRecognitionConfidence.USER_CONFIRMED: 1.00,
}

REVIEW_REQUIRED_THRESHOLD = 0.75


class PatternType(StrEnum):
    LINEAR = "LINEAR"
    CIRCULAR = "CIRCULAR"
    GRID = "GRID"
    UNKNOWN = "UNKNOWN"


class AxisCount(StrEnum):
    THREE_AXIS = "3_AXIS"
    THREE_PLUS_TWO = "3_PLUS_2"
    FIVE_AXIS_CANDIDATE = "5_AXIS_CANDIDATE"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _new_fid(feature_type: ManufacturingFeatureType) -> str:
    return f"feat-{feature_type.lower().replace('_', '-')}-{uuid.uuid4().hex[:8]}"


def _new_pid() -> str:
    return f"pat-{uuid.uuid4().hex[:8]}"


def _qty_mm(val: float | Decimal) -> Quantity:
    return Quantity(value=Decimal(str(val)), unit=Unit.MM)


def _vec_mm(x: float, y: float, z: float) -> CanonicalVector3D:
    from decimal import Decimal

    from backend.domain.units import Quantity, Unit
    return CanonicalVector3D(
        x=Quantity(value=Decimal(str(x)), unit=Unit.DIMENSIONLESS),
        y=Quantity(value=Decimal(str(y)), unit=Unit.DIMENSIONLESS),
        z=Quantity(value=Decimal(str(z)), unit=Unit.DIMENSIONLESS),
    )


def _pt_mm(x: float, y: float, z: float) -> CanonicalPoint3D:
    return CanonicalPoint3D(
        x=_qty_mm(x), y=_qty_mm(y), z=_qty_mm(z)
    )


def _dec(v: float | str | Decimal) -> Decimal:
    return Decimal(str(v))


# ---------------------------------------------------------------------------
# Feature models
# ---------------------------------------------------------------------------

def _empty_map() -> MappingProxyType:
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class ManufacturingFeature:
    """A manufacturing feature recognized from B-Rep topology/geometry."""

    feature_id: str
    feature_type: ManufacturingFeatureType
    source_body_id: str
    source_face_ids: tuple[str, ...]
    source_edge_ids: tuple[str, ...]
    surface_type: CanonicalSurfaceType
    location: CanonicalPoint3D | None
    axis: CanonicalVector3D | None
    diameter_mm: Decimal | None
    depth_mm: Decimal | None
    width_mm: Decimal | None
    length_mm: Decimal | None
    radius_mm: Decimal | None
    angle_deg: Decimal | None
    bounding_box: BoundingBox3D | None
    recognition_method: RecognitionMethod
    confidence: FeatureRecognitionConfidence
    pattern_id: str | None
    confirmed_by: str | None
    metadata: MappingProxyType = field(default_factory=_empty_map)

    @property
    def confidence_score(self) -> float:
        return _CONFIDENCE_SCORES.get(self.confidence, 0.5)

    @property
    def requires_review(self) -> bool:
        return self.confidence_score < REVIEW_REQUIRED_THRESHOLD

    def confirm(self, user_id: str) -> ManufacturingFeature:
        from dataclasses import replace
        return replace(self, confirmed_by=user_id,
                       confidence=FeatureRecognitionConfidence.USER_CONFIRMED)

    def as_dict(self) -> dict:
        return {
            "feature_id": self.feature_id,
            "feature_type": self.feature_type,
            "source_body_id": self.source_body_id,
            "source_face_ids": list(self.source_face_ids),
            "surface_type": self.surface_type,
            "location": {
                "x_mm": float(self.location.x.value) if self.location else None,
                "y_mm": float(self.location.y.value) if self.location else None,
                "z_mm": float(self.location.z.value) if self.location else None,
            } if self.location else None,
            "axis": {
                "x": float(self.axis.x.value),
                "y": float(self.axis.y.value),
                "z": float(self.axis.z.value),
            } if self.axis else None,
            "diameter_mm": float(self.diameter_mm) if self.diameter_mm is not None else None,
            "depth_mm": float(self.depth_mm) if self.depth_mm is not None else None,
            "width_mm": float(self.width_mm) if self.width_mm is not None else None,
            "length_mm": float(self.length_mm) if self.length_mm is not None else None,
            "radius_mm": float(self.radius_mm) if self.radius_mm is not None else None,
            "angle_deg": float(self.angle_deg) if self.angle_deg is not None else None,
            "recognition_method": self.recognition_method,
            "confidence": self.confidence,
            "confidence_score": self.confidence_score,
            "requires_review": self.requires_review,
            "pattern_id": self.pattern_id,
            "confirmed_by": self.confirmed_by,
        }


@dataclass(frozen=True, slots=True)
class FeaturePattern:
    """A detected pattern of repeated features."""

    pattern_id: str
    pattern_type: PatternType
    feature_type: ManufacturingFeatureType
    member_feature_ids: tuple[str, ...]
    count: int
    spacing_mm: Decimal | None
    pitch_deg: Decimal | None
    pcd_mm: Decimal | None
    axis: CanonicalVector3D | None
    origin: CanonicalPoint3D | None
    confidence: FeatureRecognitionConfidence

    def as_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "feature_type": self.feature_type,
            "member_feature_ids": list(self.member_feature_ids),
            "count": self.count,
            "spacing_mm": float(self.spacing_mm) if self.spacing_mm is not None else None,
            "pitch_deg": float(self.pitch_deg) if self.pitch_deg is not None else None,
            "pcd_mm": float(self.pcd_mm) if self.pcd_mm is not None else None,
            "confidence": self.confidence,
        }


@dataclass(frozen=True, slots=True)
class FeatureAccessibility:
    """Candidate tool access directions for a feature."""

    feature_id: str
    candidate_access_directions: tuple[CanonicalVector3D, ...]
    primary_access_direction: CanonicalVector3D | None
    blocked_directions: tuple[CanonicalVector3D, ...]
    required_axis_count: AxisCount
    accessibility_note: str | None

    def as_dict(self) -> dict:
        def _v(v: CanonicalVector3D) -> dict:
            return {"x": float(v.x.value), "y": float(v.y.value), "z": float(v.z.value)}
        return {
            "feature_id": self.feature_id,
            "primary_access_direction": _v(self.primary_access_direction)
                if self.primary_access_direction else None,
            "required_axis_count": self.required_axis_count,
            "accessibility_note": self.accessibility_note,
        }


@dataclass(frozen=True, slots=True)
class ToolReachRequirement:
    """Minimum tool geometry required to machine a feature."""

    feature_id: str
    min_tool_diameter_mm: Decimal | None
    max_tool_diameter_mm: Decimal | None
    min_tool_depth_mm: Decimal | None
    neck_clearance_mm: Decimal | None
    access_opening_mm: Decimal | None
    min_stickout_mm: Decimal | None

    def as_dict(self) -> dict:
        def _f(v): return float(v) if v is not None else None
        return {
            "feature_id": self.feature_id,
            "min_tool_diameter_mm": _f(self.min_tool_diameter_mm),
            "max_tool_diameter_mm": _f(self.max_tool_diameter_mm),
            "min_tool_depth_mm": _f(self.min_tool_depth_mm),
            "min_stickout_mm": _f(self.min_stickout_mm),
        }


@dataclass(frozen=True, slots=True)
class SetupCandidate:
    """A candidate machining setup orientation."""

    setup_id: str
    machine_direction: CanonicalVector3D
    features_accessible: tuple[str, ...]
    datum_faces_reachable: tuple[str, ...]
    part_rotation_from_previous: Decimal | None
    estimated_setup_count: int


# ---------------------------------------------------------------------------
# Topology analysis
# ---------------------------------------------------------------------------

class FaceAdjacencyIndex:
    """Derived face-face adjacency map built from shared edges in CanonicalTopology."""

    def __init__(
        self,
        adjacency: dict[str, frozenset[str]],
        face_by_surface_type: dict[CanonicalSurfaceType, list[str]],
    ) -> None:
        self._adj = adjacency
        self._by_type = face_by_surface_type

    def neighbors(self, face_id: str) -> frozenset[str]:
        return self._adj.get(face_id, frozenset())

    def faces_of_type(self, surface_type: CanonicalSurfaceType) -> list[str]:
        return list(self._by_type.get(surface_type, []))

    def all_face_ids(self) -> list[str]:
        return list(self._adj.keys())


def build_adjacency_index(
    topology: CanonicalTopology,
    geometry: CanonicalGeometry,
) -> FaceAdjacencyIndex:
    """Build face-face adjacency index and surface-type index from CanonicalTopology."""
    loop_map = {lp.loop_id: lp for lp in topology.loops}

    # Map edge_id → set of face_ids that share this edge
    edge_to_faces: dict[str, list[str]] = {}
    for face in topology.faces:
        for loop_id in face.boundary_loop_ids:
            loop = loop_map.get(loop_id)
            if loop is None:
                continue
            for edge_id in loop.edge_ids:
                edge_to_faces.setdefault(edge_id, []).append(face.face_id)

    # Build adjacency from shared edges
    adjacency: dict[str, frozenset[str]] = {}
    for face in topology.faces:
        neighbors: set[str] = set()
        for loop_id in face.boundary_loop_ids:
            loop = loop_map.get(loop_id)
            if loop is None:
                continue
            for edge_id in loop.edge_ids:
                for other_face_id in edge_to_faces.get(edge_id, []):
                    if other_face_id != face.face_id:
                        neighbors.add(other_face_id)
        adjacency[face.face_id] = frozenset(neighbors)

    # Build surface-type index
    face_by_surface_type: dict[CanonicalSurfaceType, list[str]] = {}
    surf_map = {s.surface_id: s for s in geometry.surfaces}
    for face in topology.faces:
        surf = surf_map.get(face.surface_id)
        if surf is not None:
            stype = surf.surface_type
            face_by_surface_type.setdefault(stype, []).append(face.face_id)
        else:
            face_by_surface_type.setdefault(CanonicalSurfaceType.UNKNOWN, []).append(
                face.face_id
            )

    return FaceAdjacencyIndex(adjacency, face_by_surface_type)


# ---------------------------------------------------------------------------
# Internal geometry helpers
# ---------------------------------------------------------------------------

def _surface_for_face(
    face: CanonicalFace,
    topology: CanonicalTopology,
    geometry: CanonicalGeometry,
) -> CanonicalSurface | None:
    surf_map = {s.surface_id: s for s in geometry.surfaces}
    return surf_map.get(face.surface_id)


def _has_inner_loop(face: CanonicalFace, topology: CanonicalTopology) -> bool:
    loop_map = {lp.loop_id: lp for lp in topology.loops}
    for loop_id in face.boundary_loop_ids:
        loop = loop_map.get(loop_id)
        if loop and loop.loop_type == LoopType.INNER:
            return True
    return False


def _face_normal_approx(surf: CanonicalSurface) -> CanonicalVector3D | None:
    if surf.surface_type == CanonicalSurfaceType.PLANE and surf.normal is not None:
        return surf.normal
    if surf.surface_type == CanonicalSurfaceType.CYLINDER and surf.axis is not None:
        return surf.axis
    return None


def _vec_dot(a: CanonicalVector3D, b: CanonicalVector3D) -> float:
    return (
        float(a.x.value) * float(b.x.value)
        + float(a.y.value) * float(b.y.value)
        + float(a.z.value) * float(b.z.value)
    )


def _vec_len(v: CanonicalVector3D) -> float:
    x, y, z = float(v.x.value), float(v.y.value), float(v.z.value)
    return math.sqrt(x * x + y * y + z * z)


def _vec_cos_angle(a: CanonicalVector3D, b: CanonicalVector3D) -> float:
    la, lb = _vec_len(a), _vec_len(b)
    if la < 1e-9 or lb < 1e-9:
        return 0.0
    return _vec_dot(a, b) / (la * lb)


def _axes_parallel(a: CanonicalVector3D, b: CanonicalVector3D, tol: float = 0.05) -> bool:
    """True when axes are parallel (allowing anti-parallel)."""
    c = abs(_vec_cos_angle(a, b))
    return c > (1.0 - tol)


def _axes_perpendicular(a: CanonicalVector3D, b: CanonicalVector3D, tol: float = 0.05) -> bool:
    c = abs(_vec_cos_angle(a, b))
    return c < tol


_APPROX_EQ_TOL = _dec("0.5")


def _approx_eq(a: Decimal, b: Decimal, tol: Decimal = _APPROX_EQ_TOL) -> bool:
    return abs(a - b) <= tol


def _pt_to_float(p: CanonicalPoint3D) -> tuple[float, float, float]:
    return float(p.x.value), float(p.y.value), float(p.z.value)


def _pt_distance(a: CanonicalPoint3D, b: CanonicalPoint3D) -> float:
    ax, ay, az = _pt_to_float(a)
    bx, by, bz = _pt_to_float(b)
    return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2)


def _vec_from_points(a: CanonicalPoint3D, b: CanonicalPoint3D) -> tuple[float, float, float]:
    ax, ay, az = _pt_to_float(a)
    bx, by, bz = _pt_to_float(b)
    return bx - ax, by - ay, bz - az


def _axis_from_vec(x: float, y: float, z: float) -> CanonicalVector3D:
    length = math.sqrt(x * x + y * y + z * z)
    if length < 1e-9:
        return _vec_mm(0.0, 0.0, 1.0)
    return _vec_mm(x / length, y / length, z / length)


# ---------------------------------------------------------------------------
# Per-body recognition helpers
# ---------------------------------------------------------------------------

def _get_topology_maps(topology: CanonicalTopology) -> tuple[
    dict[str, CanonicalFace],
    dict[str, CanonicalLoop],
    dict[str, CanonicalEdge],
    dict[str, CanonicalShell],
]:
    face_map = {f.face_id: f for f in topology.faces}
    loop_map = {lp.loop_id: lp for lp in topology.loops}
    edge_map = {e.edge_id: e for e in topology.edges}
    shell_map = {s.shell_id: s for s in topology.shells}
    return face_map, loop_map, edge_map, shell_map


def _recognize_holes_in_body(
    body: CanonicalBody,
    topology: CanonicalTopology,
    geometry: CanonicalGeometry,
    adj: FaceAdjacencyIndex,
) -> list[ManufacturingFeature]:
    """Recognize hole-family features from CYLINDER faces in a body."""
    features: list[ManufacturingFeature] = []
    surf_map = {s.surface_id: s for s in geometry.surfaces}
    face_map = {f.face_id: f for f in topology.faces}

    # Collect all cylinder faces belonging to this body
    body_face_ids: set[str] = set()
    shell_map = {s.shell_id: s for s in topology.shells}
    for shell_id in body.shell_ids:
        shell = shell_map.get(shell_id)
        if shell:
            body_face_ids.update(shell.face_ids)

    cyl_faces = [
        fid for fid in adj.faces_of_type(CanonicalSurfaceType.CYLINDER)
        if fid in body_face_ids
    ]
    plane_faces_in_body = [
        fid for fid in adj.faces_of_type(CanonicalSurfaceType.PLANE)
        if fid in body_face_ids
    ]
    cone_faces_in_body = [
        fid for fid in adj.faces_of_type(CanonicalSurfaceType.CONE)
        if fid in body_face_ids
    ]

    # Group coaxial cylinders
    processed: set[str] = set()

    for cyl_fid in cyl_faces:
        if cyl_fid in processed:
            continue
        face = face_map.get(cyl_fid)
        if face is None:
            continue
        surf = surf_map.get(face.surface_id)
        if surf is None or surf.radius is None or surf.axis is None or surf.center is None:
            continue

        radius_mm = float(surf.radius.value)
        if radius_mm < 0.1:
            continue  # too small

        # Find coaxial cylinders (stepped holes, counterbores)
        coaxial_cyls: list[str] = [cyl_fid]
        for other_fid in cyl_faces:
            if other_fid == cyl_fid or other_fid not in body_face_ids:
                continue
            other_face = face_map.get(other_fid)
            if other_face is None:
                continue
            other_surf = surf_map.get(other_face.surface_id)
            if other_surf is None or other_surf.axis is None or other_surf.center is None:
                continue
            if _axes_parallel(surf.axis, other_surf.axis):
                # Check axis offset (coaxial = same center line)
                axis_vec = (
                    float(surf.axis.x.value),
                    float(surf.axis.y.value),
                    float(surf.axis.z.value),
                )
                c1 = (
                    float(surf.center.x.value),
                    float(surf.center.y.value),
                    float(surf.center.z.value),
                )
                c2 = (
                    float(other_surf.center.x.value),
                    float(other_surf.center.y.value),
                    float(other_surf.center.z.value),
                )
                diff = (c2[0] - c1[0], c2[1] - c1[1], c2[2] - c1[2])
                # Project diff onto axis
                dot = diff[0] * axis_vec[0] + diff[1] * axis_vec[1] + diff[2] * axis_vec[2]
                perp = math.sqrt(
                    sum((diff[i] - dot * axis_vec[i]) ** 2 for i in range(3))
                )
                if perp < max(radius_mm * 0.15, 1.0):
                    coaxial_cyls.append(other_fid)

        processed.update(coaxial_cyls)

        # Determine hole depth: look for planar end-cap neighbor faces
        adj_plane_fids = [
            p for p in plane_faces_in_body
            if any(
                p in adj.neighbors(c)
                for c in coaxial_cyls
            )
        ]

        depth_mm: Decimal | None = None
        end_planes = []
        for pfid in adj_plane_fids:
            pface = face_map.get(pfid)
            if pface is None:
                continue
            psurf = surf_map.get(pface.surface_id)
            if psurf and psurf.normal is not None:
                # Only accept planes roughly perpendicular to cylinder axis
                if _axes_perpendicular(psurf.normal, surf.axis, tol=0.25):
                    end_planes.append(pfid)

        # Compute depth from bounding box if no end cap found
        body_bbox = body.bounding_box
        if body_bbox is not None and end_planes:
            # simple depth from bbox extent along axis
            ax = (
                float(surf.axis.x.value),
                float(surf.axis.y.value),
                float(surf.axis.z.value),
            )
            extent = abs(
                ax[0] * float(body_bbox.size_x.value)
                + ax[1] * float(body_bbox.size_y.value)
                + ax[2] * float(body_bbox.size_z.value)
            )
            depth_mm = _dec(round(extent, 3))

        # Check for cone (countersink)
        adj_cone_fids = [
            c for c in cone_faces_in_body
            if any(c in adj.neighbors(cf) for cf in coaxial_cyls)
        ]

        # Determine feature type
        n_cyls = len(coaxial_cyls)
        if n_cyls >= 2:
            # Get radii
            radii = []
            for cfid in coaxial_cyls:
                cf = face_map.get(cfid)
                if cf:
                    cs = surf_map.get(cf.surface_id)
                    if cs and cs.radius:
                        radii.append(float(cs.radius.value))
            if adj_cone_fids:
                ftype = ManufacturingFeatureType.COUNTERSINK
            elif len(set(round(r, 1) for r in radii)) > 1:
                ftype = ManufacturingFeatureType.COUNTERBORE if n_cyls == 2 \
                    else ManufacturingFeatureType.STEPPED_HOLE
            else:
                ftype = ManufacturingFeatureType.HOLE
        elif adj_cone_fids:
            ftype = ManufacturingFeatureType.COUNTERSINK
        elif end_planes:
            ftype = ManufacturingFeatureType.BLIND_HOLE
        else:
            ftype = ManufacturingFeatureType.THROUGH_HOLE

        # For coaxial stepped holes / counterbores, use smallest (inner) radius for hole dia
        cyl_radii_mm: list[float] = []
        for cfid in coaxial_cyls:
            cf = face_map.get(cfid)
            if cf:
                cs = surf_map.get(cf.surface_id)
                if cs and cs.radius:
                    cyl_radii_mm.append(float(cs.radius.value))

        main_radius = min(cyl_radii_mm) if cyl_radii_mm else radius_mm
        diameter_mm = _dec(round(main_radius * 2.0, 3))

        confidence = (
            FeatureRecognitionConfidence.EXACT_BREP
            if end_planes or ftype == ManufacturingFeatureType.THROUGH_HOLE
            else FeatureRecognitionConfidence.TOPOLOGY_RULE
        )

        feat = ManufacturingFeature(
            feature_id=_new_fid(ftype),
            feature_type=ftype,
            source_body_id=body.body_id,
            source_face_ids=tuple(coaxial_cyls),
            source_edge_ids=(),
            surface_type=CanonicalSurfaceType.CYLINDER,
            location=surf.center,
            axis=surf.axis,
            diameter_mm=diameter_mm,
            depth_mm=depth_mm,
            width_mm=None,
            length_mm=None,
            radius_mm=None,
            angle_deg=None,
            bounding_box=body.bounding_box,
            recognition_method=RecognitionMethod.BREP_TOPOLOGY,
            confidence=confidence,
            pattern_id=None,
            confirmed_by=None,
        )
        features.append(feat)

    return features


def _recognize_pockets_in_body(
    body: CanonicalBody,
    topology: CanonicalTopology,
    geometry: CanonicalGeometry,
    adj: FaceAdjacencyIndex,
) -> list[ManufacturingFeature]:
    """Recognize pocket/slot features from connected planar face regions."""
    features: list[ManufacturingFeature] = []
    surf_map = {s.surface_id: s for s in geometry.surfaces}
    face_map = {f.face_id: f for f in topology.faces}

    body_face_ids: set[str] = set()
    shell_map = {s.shell_id: s for s in topology.shells}
    for shell_id in body.shell_ids:
        shell = shell_map.get(shell_id)
        if shell:
            body_face_ids.update(shell.face_ids)

    plane_faces = [
        fid for fid in adj.faces_of_type(CanonicalSurfaceType.PLANE)
        if fid in body_face_ids
    ]
    cyl_faces = {
        fid for fid in adj.faces_of_type(CanonicalSurfaceType.CYLINDER)
        if fid in body_face_ids
    }

    processed: set[str] = set()

    for floor_fid in plane_faces:
        if floor_fid in processed:
            continue
        floor_face = face_map.get(floor_fid)
        if floor_face is None:
            continue
        floor_surf = surf_map.get(floor_face.surface_id)
        if floor_surf is None or floor_surf.normal is None:
            continue

        # Find plane faces adjacent to this floor candidate
        adj_planes = [
            n for n in adj.neighbors(floor_fid)
            if n in plane_faces and n != floor_fid
        ]
        adj_cyls = [n for n in adj.neighbors(floor_fid) if n in cyl_faces]

        if len(adj_planes) < 2 and not adj_cyls:
            # Not enough walls for pocket/slot
            continue

        # All adjacent plane faces that are roughly perpendicular to floor
        walls: list[str] = []
        for wfid in adj_planes:
            wface = face_map.get(wfid)
            if wface is None:
                continue
            wsurf = surf_map.get(wface.surface_id)
            if wsurf and wsurf.normal is not None:
                if _axes_perpendicular(floor_surf.normal, wsurf.normal, tol=0.3):
                    walls.append(wfid)

        walls.extend(adj_cyls)

        if len(walls) < 2:
            continue

        processed.add(floor_fid)
        processed.update(walls)

        # Classify: 4 walls → pocket, 2 walls → slot
        # Check if any wall face lacks an adjacent face (open side)
        n_walls = len(walls)
        # For simplicity: ≥3 wall faces → pocket, 2 → slot
        if n_walls >= 3:
            # Closed vs open: check if any wall is on the outer body boundary
            ftype = ManufacturingFeatureType.CLOSED_POCKET
        else:
            ftype = ManufacturingFeatureType.OPEN_SLOT if n_walls == 2 \
                else ManufacturingFeatureType.CLOSED_SLOT

        # Estimate dimensions from body bbox
        bbox = body.bounding_box
        dim_x = float(bbox.size_x.value) if bbox else None
        dim_y = float(bbox.size_y.value) if bbox else None
        dim_z = float(bbox.size_z.value) if bbox else None

        depth_mm = _dec(round(min(filter(None, [dim_x, dim_y, dim_z] or [0.0])), 3)) \
            if dim_x and dim_y and dim_z else None
        width_mm = _dec(round(min(filter(None, [dim_x, dim_y])) if dim_x and dim_y else 0.0, 3)) \
            if dim_x and dim_y else None
        length_mm = _dec(round(max(filter(None, [dim_x, dim_y])) if dim_x and dim_y else 0.0, 3)) \
            if dim_x and dim_y else None

        feat = ManufacturingFeature(
            feature_id=_new_fid(ftype),
            feature_type=ftype,
            source_body_id=body.body_id,
            source_face_ids=(floor_fid, *walls),
            source_edge_ids=(),
            surface_type=CanonicalSurfaceType.PLANE,
            location=floor_surf.origin,
            axis=floor_surf.normal,
            diameter_mm=None,
            depth_mm=depth_mm,
            width_mm=width_mm,
            length_mm=length_mm,
            radius_mm=None,
            angle_deg=None,
            bounding_box=bbox,
            recognition_method=RecognitionMethod.BREP_TOPOLOGY,
            confidence=FeatureRecognitionConfidence.TOPOLOGY_RULE,
            pattern_id=None,
            confirmed_by=None,
        )
        features.append(feat)

    return features


def _recognize_planar_faces_in_body(
    body: CanonicalBody,
    topology: CanonicalTopology,
    geometry: CanonicalGeometry,
    adj: FaceAdjacencyIndex,
    existing_face_ids: set[str],
) -> list[ManufacturingFeature]:
    """Recognize remaining planar faces (datums, functional surfaces)."""
    features: list[ManufacturingFeature] = []
    surf_map = {s.surface_id: s for s in geometry.surfaces}
    face_map = {f.face_id: f for f in topology.faces}

    body_face_ids: set[str] = set()
    shell_map = {s.shell_id: s for s in topology.shells}
    for shell_id in body.shell_ids:
        shell = shell_map.get(shell_id)
        if shell:
            body_face_ids.update(shell.face_ids)

    plane_faces = [
        fid for fid in adj.faces_of_type(CanonicalSurfaceType.PLANE)
        if fid in body_face_ids and fid not in existing_face_ids
    ]

    for pfid in plane_faces:
        pface = face_map.get(pfid)
        if pface is None:
            continue
        psurf = surf_map.get(pface.surface_id)
        if psurf is None:
            continue
        feat = ManufacturingFeature(
            feature_id=_new_fid(ManufacturingFeatureType.PLANAR_FACE),
            feature_type=ManufacturingFeatureType.PLANAR_FACE,
            source_body_id=body.body_id,
            source_face_ids=(pfid,),
            source_edge_ids=(),
            surface_type=CanonicalSurfaceType.PLANE,
            location=psurf.origin,
            axis=psurf.normal,
            diameter_mm=None,
            depth_mm=None,
            width_mm=None,
            length_mm=None,
            radius_mm=None,
            angle_deg=None,
            bounding_box=body.bounding_box,
            recognition_method=RecognitionMethod.SURFACE_HEURISTIC,
            confidence=FeatureRecognitionConfidence.GEOMETRY_RULE,
            pattern_id=None,
            confirmed_by=None,
        )
        features.append(feat)

    return features


def _recognize_chamfers_fillets_in_body(
    body: CanonicalBody,
    topology: CanonicalTopology,
    geometry: CanonicalGeometry,
    adj: FaceAdjacencyIndex,
) -> list[ManufacturingFeature]:
    """Recognize chamfer (CONE) and fillet (TORUS) faces."""
    features: list[ManufacturingFeature] = []
    surf_map = {s.surface_id: s for s in geometry.surfaces}
    face_map = {f.face_id: f for f in topology.faces}

    body_face_ids: set[str] = set()
    shell_map = {s.shell_id: s for s in topology.shells}
    for shell_id in body.shell_ids:
        shell = shell_map.get(shell_id)
        if shell:
            body_face_ids.update(shell.face_ids)

    cone_faces = [
        fid for fid in adj.faces_of_type(CanonicalSurfaceType.CONE)
        if fid in body_face_ids
    ]
    torus_faces = [
        fid for fid in adj.faces_of_type(CanonicalSurfaceType.TORUS)
        if fid in body_face_ids
    ]

    for cfid in cone_faces:
        cface = face_map.get(cfid)
        if cface is None:
            continue
        csurf = surf_map.get(cface.surface_id)
        if csurf is None:
            continue
        angle = None
        if csurf.semi_angle is not None:
            angle = Quantity(value=csurf.semi_angle.value * 2, unit=csurf.semi_angle.unit)

        feat = ManufacturingFeature(
            feature_id=_new_fid(ManufacturingFeatureType.CHAMFER),
            feature_type=ManufacturingFeatureType.CHAMFER,
            source_body_id=body.body_id,
            source_face_ids=(cfid,),
            source_edge_ids=(),
            surface_type=CanonicalSurfaceType.CONE,
            location=csurf.center or csurf.origin,
            axis=csurf.axis,
            diameter_mm=None,
            depth_mm=None,
            width_mm=None,
            length_mm=None,
            radius_mm=csurf.radius,
            angle_deg=angle,
            bounding_box=None,
            recognition_method=RecognitionMethod.SURFACE_HEURISTIC,
            confidence=FeatureRecognitionConfidence.GEOMETRY_RULE,
            pattern_id=None,
            confirmed_by=None,
        )
        features.append(feat)

    for tfid in torus_faces:
        tface = face_map.get(tfid)
        if tface is None:
            continue
        tsurf = surf_map.get(tface.surface_id)
        if tsurf is None:
            continue

        ftype = ManufacturingFeatureType.FILLET
        # small torus (minor_radius < 1 mm) → edge break
        if tsurf.minor_radius is not None and float(tsurf.minor_radius.value) < 1.0:
            ftype = ManufacturingFeatureType.EDGE_BREAK

        feat = ManufacturingFeature(
            feature_id=_new_fid(ftype),
            feature_type=ftype,
            source_body_id=body.body_id,
            source_face_ids=(tfid,),
            source_edge_ids=(),
            surface_type=CanonicalSurfaceType.TORUS,
            location=tsurf.center or tsurf.origin,
            axis=tsurf.axis,
            diameter_mm=None,
            depth_mm=None,
            width_mm=None,
            length_mm=None,
            radius_mm=tsurf.minor_radius,
            angle_deg=None,
            bounding_box=None,
            recognition_method=RecognitionMethod.SURFACE_HEURISTIC,
            confidence=FeatureRecognitionConfidence.GEOMETRY_RULE,
            pattern_id=None,
            confirmed_by=None,
        )
        features.append(feat)

    return features


def _recognize_turning_features_in_body(
    body: CanonicalBody,
    topology: CanonicalTopology,
    geometry: CanonicalGeometry,
    adj: FaceAdjacencyIndex,
) -> list[ManufacturingFeature]:
    """Recognize axisymmetric (turning) features when body axis can be detected."""
    features: list[ManufacturingFeature] = []
    surf_map = {s.surface_id: s for s in geometry.surfaces}
    face_map = {f.face_id: f for f in topology.faces}

    body_face_ids: set[str] = set()
    shell_map = {s.shell_id: s for s in topology.shells}
    for shell_id in body.shell_ids:
        shell = shell_map.get(shell_id)
        if shell:
            body_face_ids.update(shell.face_ids)

    cyl_faces = [
        fid for fid in adj.faces_of_type(CanonicalSurfaceType.CYLINDER)
        if fid in body_face_ids
    ]

    if not cyl_faces:
        return features

    # Detect dominant body axis from largest-radius cylinder
    max_r = 0.0
    dominant_axis: CanonicalVector3D | None = None

    for cfid in cyl_faces:
        cf = face_map.get(cfid)
        if not cf:
            continue
        cs = surf_map.get(cf.surface_id)
        if cs and cs.radius and cs.axis:
            r = float(cs.radius.value)
            if r > max_r:
                max_r = r
                dominant_axis = cs.axis

    if dominant_axis is None:
        return features

    # Now classify each cylinder face relative to dominant axis
    for cfid in cyl_faces:
        cf = face_map.get(cfid)
        if not cf:
            continue
        cs = surf_map.get(cf.surface_id)
        if cs is None or cs.radius is None or cs.axis is None:
            continue

        radius_mm = _dec(round(float(cs.radius.value), 3))
        diameter_mm = radius_mm * 2

        is_coaxial = _axes_parallel(cs.axis, dominant_axis)
        if not is_coaxial:
            continue

        # Check neighbors for groove signature: flanked by plane faces
        adj_planes = [
            n for n in adj.neighbors(cfid)
            if n in adj.faces_of_type(CanonicalSurfaceType.PLANE)
            and n in body_face_ids
        ]

        if len(adj_planes) >= 2 and float(radius_mm) < max_r * 0.95:
            ftype = ManufacturingFeatureType.GROOVE
        elif float(radius_mm) >= max_r * 0.95:
            ftype = ManufacturingFeatureType.OUTER_DIAMETER
        else:
            ftype = ManufacturingFeatureType.TURNING_DIAMETER

        feat = ManufacturingFeature(
            feature_id=_new_fid(ftype),
            feature_type=ftype,
            source_body_id=body.body_id,
            source_face_ids=(cfid,),
            source_edge_ids=(),
            surface_type=CanonicalSurfaceType.CYLINDER,
            location=cs.center or cs.origin,
            axis=cs.axis,
            diameter_mm=diameter_mm,
            depth_mm=None,
            width_mm=None,
            length_mm=None,
            radius_mm=cs.radius,
            angle_deg=None,
            bounding_box=body.bounding_box,
            recognition_method=RecognitionMethod.BREP_TOPOLOGY,
            confidence=FeatureRecognitionConfidence.TOPOLOGY_RULE,
            pattern_id=None,
            confirmed_by=None,
        )
        features.append(feat)

    return features


def _recognize_boss_step_in_body(
    body: CanonicalBody,
    topology: CanonicalTopology,
    geometry: CanonicalGeometry,
    adj: FaceAdjacencyIndex,
) -> list[ManufacturingFeature]:
    """Recognize boss (raised cylinder) and step (Z-transition) features."""
    features: list[ManufacturingFeature] = []
    surf_map = {s.surface_id: s for s in geometry.surfaces}
    face_map = {f.face_id: f for f in topology.faces}

    body_face_ids: set[str] = set()
    shell_map = {s.shell_id: s for s in topology.shells}
    for shell_id in body.shell_ids:
        shell = shell_map.get(shell_id)
        if shell:
            body_face_ids.update(shell.face_ids)

    cyl_faces_in_body = {
        fid for fid in adj.faces_of_type(CanonicalSurfaceType.CYLINDER)
        if fid in body_face_ids
    }
    plane_faces_in_body = {
        fid for fid in adj.faces_of_type(CanonicalSurfaceType.PLANE)
        if fid in body_face_ids
    }

    for cfid in cyl_faces_in_body:
        cf = face_map.get(cfid)
        if not cf:
            continue
        cs = surf_map.get(cf.surface_id)
        if not cs or not cs.radius or not cs.axis:
            continue

        # Boss: cylinder face that is adjacent to a flat ring (plane perpendicular to axis)
        adj_perp_planes = [
            n for n in adj.neighbors(cfid)
            if n in plane_faces_in_body
        ]
        if not adj_perp_planes:
            continue

        # Check that at least one adjacent plane is roughly perpendicular to cylinder axis
        for ppfid in adj_perp_planes:
            ppface = face_map.get(ppfid)
            if not ppface:
                continue
            ppsurf = surf_map.get(ppface.surface_id)
            if ppsurf and ppsurf.normal and _axes_perpendicular(ppsurf.normal, cs.axis, tol=0.25):
                feat = ManufacturingFeature(
                    feature_id=_new_fid(ManufacturingFeatureType.BOSS),
                    feature_type=ManufacturingFeatureType.BOSS,
                    source_body_id=body.body_id,
                    source_face_ids=(cfid, ppfid),
                    source_edge_ids=(),
                    surface_type=CanonicalSurfaceType.CYLINDER,
                    location=cs.center or cs.origin,
                    axis=cs.axis,
                    diameter_mm=(
                        Quantity(value=cs.radius.value * 2, unit=cs.radius.unit)
                        if cs.radius else None
                    ),
                    depth_mm=None,
                    width_mm=None,
                    length_mm=None,
                    radius_mm=cs.radius,
                    angle_deg=None,
                    bounding_box=body.bounding_box,
                    recognition_method=RecognitionMethod.BREP_TOPOLOGY,
                    confidence=FeatureRecognitionConfidence.TOPOLOGY_RULE,
                    pattern_id=None,
                    confirmed_by=None,
                )
                features.append(feat)
                break

    return features


# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------

def _detect_patterns(features: list[ManufacturingFeature]) -> list[FeaturePattern]:
    """Detect circular and linear patterns among hole features."""
    patterns: list[FeaturePattern] = []

    hole_types = {
        ManufacturingFeatureType.HOLE,
        ManufacturingFeatureType.THROUGH_HOLE,
        ManufacturingFeatureType.BLIND_HOLE,
        ManufacturingFeatureType.COUNTERBORE,
        ManufacturingFeatureType.COUNTERSINK,
    }

    # Group hole features by diameter (within ±0.1 mm)
    grouped: dict[float, list[ManufacturingFeature]] = {}
    for feat in features:
        if feat.feature_type not in hole_types or feat.diameter_mm is None:
            continue
        d = round(float(feat.diameter_mm), 1)
        grouped.setdefault(d, []).append(feat)

    for _dia_key, grp in grouped.items():
        if len(grp) < 2:
            continue

        # Try circular pattern: check if all centers lie on a common circle
        centers = []
        for feat in grp:
            if feat.location:
                centers.append(_pt_to_float(feat.location))

        if len(centers) < 2:
            continue

        # Compute centroid
        cx = sum(c[0] for c in centers) / len(centers)
        cy = sum(c[1] for c in centers) / len(centers)
        cz = sum(c[2] for c in centers) / len(centers)

        # Distances from centroid
        dists = [
            math.sqrt((c[0] - cx) ** 2 + (c[1] - cy) ** 2 + (c[2] - cz) ** 2)
            for c in centers
        ]
        mean_dist = sum(dists) / len(dists)
        max_var = max(abs(d - mean_dist) for d in dists)

        pcd_mm: Decimal | None = None
        pitch_deg: Decimal | None = None
        spacing_mm: Decimal | None = None
        ptype = PatternType.UNKNOWN

        if mean_dist > 0.5 and max_var < mean_dist * 0.1:
            # Circular pattern
            pcd_mm = _dec(round(mean_dist * 2.0, 3))
            if len(centers) > 1:
                pitch_deg = _dec(round(360.0 / len(centers), 3))
            ptype = PatternType.CIRCULAR
        else:
            # Try linear: check collinearity
            if len(centers) >= 2:
                dx = centers[-1][0] - centers[0][0]
                dy = centers[-1][1] - centers[0][1]
                dz = centers[-1][2] - centers[0][2]
                total = math.sqrt(dx * dx + dy * dy + dz * dz)
                if total > 0.5 and len(centers) >= 2:
                    spacing_mm = _dec(round(total / max(1, len(centers) - 1), 3))
                    ptype = PatternType.LINEAR

        if ptype == PatternType.UNKNOWN:
            continue

        pat = FeaturePattern(
            pattern_id=_new_pid(),
            pattern_type=ptype,
            feature_type=grp[0].feature_type,
            member_feature_ids=tuple(f.feature_id for f in grp),
            count=len(grp),
            spacing_mm=spacing_mm,
            pitch_deg=pitch_deg,
            pcd_mm=pcd_mm,
            axis=grp[0].axis,
            origin=grp[0].location,
            confidence=FeatureRecognitionConfidence.PATTERN_RECOGNIZED,
        )
        patterns.append(pat)

    return patterns


# ---------------------------------------------------------------------------
# Accessibility estimation
# ---------------------------------------------------------------------------

def _estimate_accessibility(feature: ManufacturingFeature) -> FeatureAccessibility:
    """Estimate candidate access direction and axis count for a feature."""
    axis = feature.axis

    if axis is None:
        return FeatureAccessibility(
            feature_id=feature.feature_id,
            candidate_access_directions=(),
            primary_access_direction=None,
            blocked_directions=(),
            required_axis_count=AxisCount.UNKNOWN,
            accessibility_note="No axis information available",
        )

    ax_x = abs(float(axis.x.value))
    ax_y = abs(float(axis.y.value))
    ax_z = abs(float(axis.z.value))

    # Principal direction threshold
    if ax_z > 0.9:
        # Axis aligned with Z → 3-axis
        primary = axis
        axis_count = AxisCount.THREE_AXIS
    elif ax_x > 0.9 or ax_y > 0.9:
        # Axis in XZ or YZ plane → 3+2
        primary = axis
        axis_count = AxisCount.THREE_PLUS_TWO
    else:
        primary = axis
        axis_count = AxisCount.FIVE_AXIS_CANDIDATE

    # For pockets and slots → typically 3-axis if depth axis is Z
    if feature.feature_type in {
        ManufacturingFeatureType.CLOSED_POCKET,
        ManufacturingFeatureType.OPEN_POCKET,
        ManufacturingFeatureType.OPEN_SLOT,
        ManufacturingFeatureType.CLOSED_SLOT,
    }:
        if ax_z > 0.7:
            axis_count = AxisCount.THREE_AXIS

    return FeatureAccessibility(
        feature_id=feature.feature_id,
        candidate_access_directions=(primary,),
        primary_access_direction=primary,
        blocked_directions=(),
        required_axis_count=axis_count,
        accessibility_note=None,
    )


def _compute_tool_reach(feature: ManufacturingFeature) -> ToolReachRequirement:
    """Compute minimum tool reach requirements from feature geometry."""
    ftype = feature.feature_type
    dia = feature.diameter_mm
    depth = feature.depth_mm
    width = feature.width_mm

    min_dia = None
    max_dia = None
    min_depth = None
    stickout = None
    opening = None
    neck = None

    if ftype in {
        ManufacturingFeatureType.HOLE,
        ManufacturingFeatureType.BLIND_HOLE,
        ManufacturingFeatureType.THROUGH_HOLE,
        ManufacturingFeatureType.COUNTERBORE,
        ManufacturingFeatureType.COUNTERSINK,
    } and dia:
        min_dia = (dia * _dec("0.85")).quantize(_dec("0.001"))
        max_dia = dia
        if depth:
            min_depth = depth
            stickout = (depth + _dec("5.0")).quantize(_dec("0.001"))
        opening = dia

    elif ftype in {
        ManufacturingFeatureType.CLOSED_POCKET,
        ManufacturingFeatureType.OPEN_POCKET,
    } and width:
        min_dia = (width * _dec("0.5")).quantize(_dec("0.001"))
        max_dia = width
        if depth:
            min_depth = depth
            stickout = (depth + _dec("5.0")).quantize(_dec("0.001"))

    elif ftype in {
        ManufacturingFeatureType.OPEN_SLOT,
        ManufacturingFeatureType.CLOSED_SLOT,
    } and width:
        min_dia = width
        max_dia = width
        if depth:
            min_depth = depth
            stickout = (depth + _dec("5.0")).quantize(_dec("0.001"))

    return ToolReachRequirement(
        feature_id=feature.feature_id,
        min_tool_diameter_mm=min_dia,
        max_tool_diameter_mm=max_dia,
        min_tool_depth_mm=min_depth,
        neck_clearance_mm=neck,
        access_opening_mm=opening,
        min_stickout_mm=stickout,
    )


# ---------------------------------------------------------------------------
# Security / resource guards
# ---------------------------------------------------------------------------

_MAX_FACES = 2000
_MAX_EDGES = 10000
_MAX_SHELLS = 200


def _check_resource_limits(topology: CanonicalTopology) -> list[str]:
    warnings: list[str] = []
    n_faces = len(topology.faces)
    n_edges = len(topology.edges)
    n_shells = len(topology.shells)
    if n_faces > _MAX_FACES:
        warnings.append(
            f"Topology has {n_faces} faces (limit {_MAX_FACES}); "
            "recognition may be incomplete"
        )
    if n_edges > _MAX_EDGES:
        warnings.append(
            f"Topology has {n_edges} edges (limit {_MAX_EDGES})"
        )
    if n_shells > _MAX_SHELLS:
        warnings.append(
            f"Topology has {n_shells} shells (limit {_MAX_SHELLS})"
        )
    return warnings


# ---------------------------------------------------------------------------
# Recognition result
# ---------------------------------------------------------------------------

@dataclass
class ManufacturingFeatureRecognitionResult:
    """Complete output of the feature recognition engine."""

    source_document_id: str
    recognition_version: str
    features: list[ManufacturingFeature]
    patterns: list[FeaturePattern]
    accessibility: dict[str, FeatureAccessibility]
    tool_reach: dict[str, ToolReachRequirement]
    warnings: list[str]
    face_count: int
    body_count: int

    @property
    def feature_count(self) -> int:
        return len(self.features)

    @property
    def pattern_count(self) -> int:
        return len(self.patterns)

    def features_of_type(
        self, ftype: ManufacturingFeatureType
    ) -> list[ManufacturingFeature]:
        return [f for f in self.features if f.feature_type == ftype]

    def as_dict(self) -> dict:
        return {
            "source_document_id": self.source_document_id,
            "recognition_version": self.recognition_version,
            "feature_count": self.feature_count,
            "pattern_count": self.pattern_count,
            "warnings": self.warnings,
            "features": [f.as_dict() for f in self.features],
            "patterns": [p.as_dict() for p in self.patterns],
        }


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class FeatureRecognitionEngine:
    """Deterministic B-Rep feature recognition engine.

    Operates on CanonicalTopology + CanonicalGeometry.
    No LLM, no heuristics beyond topology rules.
    """

    def recognize(
        self,
        topology: CanonicalTopology,
        geometry: CanonicalGeometry,
        source_document_id: str = "unknown",
    ) -> ManufacturingFeatureRecognitionResult:
        warnings = _check_resource_limits(topology)

        adj = build_adjacency_index(topology, geometry)

        all_features: list[ManufacturingFeature] = []
        face_count = len(topology.faces)

        for body in topology.bodies:

            hole_feats = _recognize_holes_in_body(body, topology, geometry, adj)
            hole_face_ids = {fid for f in hole_feats for fid in f.source_face_ids}

            pocket_feats = _recognize_pockets_in_body(body, topology, geometry, adj)
            pocket_face_ids = {fid for f in pocket_feats for fid in f.source_face_ids}

            all_used = hole_face_ids | pocket_face_ids

            planar_feats = _recognize_planar_faces_in_body(
                body, topology, geometry, adj, all_used
            )

            chamfer_fillet_feats = _recognize_chamfers_fillets_in_body(
                body, topology, geometry, adj
            )
            turning_feats = _recognize_turning_features_in_body(
                body, topology, geometry, adj
            )
            boss_feats = _recognize_boss_step_in_body(
                body, topology, geometry, adj
            )

            all_features.extend(hole_feats)
            all_features.extend(pocket_feats)
            all_features.extend(planar_feats)
            all_features.extend(chamfer_fillet_feats)
            all_features.extend(turning_feats)
            all_features.extend(boss_feats)

        patterns = _detect_patterns(all_features)

        # Link pattern_id into features
        pat_member_map: dict[str, str] = {}
        for pat in patterns:
            for fid in pat.member_feature_ids:
                pat_member_map[fid] = pat.pattern_id

        linked_features: list[ManufacturingFeature] = []
        for feat in all_features:
            if feat.feature_id in pat_member_map:
                from dataclasses import replace
                linked_features.append(
                    replace(feat, pattern_id=pat_member_map[feat.feature_id])
                )
            else:
                linked_features.append(feat)

        accessibility = {
            f.feature_id: _estimate_accessibility(f) for f in linked_features
        }
        tool_reach = {
            f.feature_id: _compute_tool_reach(f) for f in linked_features
        }

        return ManufacturingFeatureRecognitionResult(
            source_document_id=source_document_id,
            recognition_version=_RECOGNITION_VERSION,
            features=linked_features,
            patterns=patterns,
            accessibility=accessibility,
            tool_reach=tool_reach,
            warnings=warnings,
            face_count=face_count,
            body_count=len(topology.bodies),
        )


def recognize_manufacturing_features(
    topology: CanonicalTopology,
    geometry: CanonicalGeometry,
    source_document_id: str = "unknown",
) -> ManufacturingFeatureRecognitionResult:
    return FeatureRecognitionEngine().recognize(topology, geometry, source_document_id)


# ---------------------------------------------------------------------------
# DXF 2D feature recognition
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Dxf2dEntity:
    """Minimal 2D DXF entity for feature recognition."""

    entity_type: str           # "CIRCLE", "ARC", "LINE", "POLYLINE"
    layer: str
    center_x: float | None = None
    center_y: float | None = None
    radius: float | None = None
    x1: float | None = None
    y1: float | None = None
    x2: float | None = None
    y2: float | None = None
    closed: bool = False


def recognize_dxf_features(
    entities: list[Dxf2dEntity],
    source_document_id: str = "unknown",
) -> list[ManufacturingFeature]:
    """Recognize manufacturing features from 2D DXF entities.

    FABRICATED_FEATURE=NO — only circles → hole candidates.
    """
    features: list[ManufacturingFeature] = []

    for ent in entities:
        if ent.entity_type == "CIRCLE" and ent.radius is not None and ent.radius > 0.05:
            diameter_mm = _dec(round(ent.radius * 2.0, 3))
            feat = ManufacturingFeature(
                feature_id=_new_fid(ManufacturingFeatureType.HOLE),
                feature_type=ManufacturingFeatureType.HOLE,
                source_body_id="dxf-2d",
                source_face_ids=(),
                source_edge_ids=(),
                surface_type=CanonicalSurfaceType.CYLINDER,
                location=_pt_mm(ent.center_x or 0.0, ent.center_y or 0.0, 0.0),
                axis=_vec_mm(0.0, 0.0, 1.0),
                diameter_mm=diameter_mm,
                depth_mm=None,  # depth unknown from 2D DXF
                width_mm=None,
                length_mm=None,
                radius_mm=_dec(str(ent.radius)),
                angle_deg=None,
                bounding_box=None,
                recognition_method=RecognitionMethod.DXF_2D,
                confidence=FeatureRecognitionConfidence.INFERRED,
                pattern_id=None,
                confirmed_by=None,
            )
            features.append(feat)

    return features
