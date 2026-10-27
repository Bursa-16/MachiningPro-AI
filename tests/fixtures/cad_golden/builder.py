"""Synthetic CAD topology/geometry builders for golden dataset cases A-J.

All cases build CanonicalTopology + CanonicalGeometry directly in Python.
No proprietary CAD files are used or committed.

CUSTOMER_CAD_COMMITTED=NO
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from backend.domain.units import Quantity, Unit
from backend.interoperability.geometry import (
    BoundingBox3D,
    CanonicalCurve,
    CanonicalCurveType,
    CanonicalGeometry,
    CanonicalPoint3D,
    CanonicalSurface,
    CanonicalSurfaceType,
    CanonicalVector3D,
)
from backend.interoperability.topology import (
    BodyType,
    CanonicalBody,
    CanonicalEdge,
    CanonicalFace,
    CanonicalLoop,
    CanonicalShell,
    CanonicalTopology,
    CanonicalVertex,
    LoopType,
    Orientation,
    ShellClosure,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _q(v: float) -> Quantity:
    return Quantity(value=Decimal(str(v)), unit=Unit.MM)


def _qd(v: float) -> Quantity:
    return Quantity(value=Decimal(str(v)), unit=Unit.DIMENSIONLESS)


def _pt(x: float, y: float, z: float) -> CanonicalPoint3D:
    return CanonicalPoint3D(x=_q(x), y=_q(y), z=_q(z))


def _v3(x: float, y: float, z: float) -> CanonicalVector3D:
    return CanonicalVector3D(x=_qd(x), y=_qd(y), z=_qd(z))


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _bbox(
    x_min: float, y_min: float, z_min: float,
    x_max: float, y_max: float, z_max: float,
) -> BoundingBox3D:
    return BoundingBox3D(
        min_point=_pt(x_min, y_min, z_min),
        max_point=_pt(x_max, y_max, z_max),
    )


def _make_plane_surface(sid: str, origin_z: float = 0.0, normal_z: float = 1.0) -> CanonicalSurface:
    return CanonicalSurface(
        surface_id=sid,
        surface_type=CanonicalSurfaceType.PLANE,
        origin=_pt(0.0, 0.0, origin_z),
        normal=_v3(0.0, 0.0, normal_z),
    )


def _make_cylinder_surface(
    sid: str,
    center_x: float, center_y: float, center_z: float,
    radius: float,
    axis_z: float = 1.0,
) -> CanonicalSurface:
    return CanonicalSurface(
        surface_id=sid,
        surface_type=CanonicalSurfaceType.CYLINDER,
        center=_pt(center_x, center_y, center_z),
        axis=_v3(0.0, 0.0, axis_z),
        radius=_q(radius),
        origin=_pt(center_x, center_y, center_z),
    )


def _make_cone_surface(
    sid: str,
    center_x: float, center_y: float, center_z: float,
    radius: float,
    semi_angle_deg: float = 45.0,
) -> CanonicalSurface:
    return CanonicalSurface(
        surface_id=sid,
        surface_type=CanonicalSurfaceType.CONE,
        center=_pt(center_x, center_y, center_z),
        axis=_v3(0.0, 0.0, 1.0),
        radius=_q(radius),
        semi_angle=Decimal(str(semi_angle_deg)),
        origin=_pt(center_x, center_y, center_z),
    )


def _make_torus_surface(
    sid: str,
    center_x: float, center_y: float, center_z: float,
    major_radius: float,
    minor_radius: float,
) -> CanonicalSurface:
    return CanonicalSurface(
        surface_id=sid,
        surface_type=CanonicalSurfaceType.TORUS,
        center=_pt(center_x, center_y, center_z),
        axis=_v3(0.0, 0.0, 1.0),
        major_radius=_q(major_radius),
        minor_radius=_q(minor_radius),
        origin=_pt(center_x, center_y, center_z),
    )


# Build a minimal but valid topology from surfaces
def _minimal_topo(
    topo_id: str,
    surfaces: list[CanonicalSurface],
    # list of (surface_id, loop_type) pairs for faces
    face_specs: list[tuple[str, LoopType]],
    adjacency: list[tuple[int, int]] | None = None,  # kept for API compat; ignored
    bbox: BoundingBox3D | None = None,
) -> tuple[CanonicalTopology, CanonicalGeometry]:
    """Build minimal valid topology for golden cases.

    All faces share three backbone edges so they are mutually adjacent in
    the FaceAdjacencyIndex — sufficient for feature-recognition heuristics.
    Each loop references exactly those 3 backbone edges (CanonicalLoop
    requires >= 3 edges with no duplicates per loop).

    adjacency parameter is accepted for API compatibility but is unused;
    full adjacency arises from the shared backbone edges.
    """
    surf_map = {s.surface_id: s for s in surfaces}

    # --- 3 backbone vertices forming a triangle ---------------------------
    v0 = CanonicalVertex(vertex_id="v0", point=_pt(0.0, 0.0, 0.0))
    v1 = CanonicalVertex(vertex_id="v1", point=_pt(1.0, 0.0, 0.0))
    v2 = CanonicalVertex(vertex_id="v2", point=_pt(0.5, 1.0, 0.0))

    # --- 3 backbone LINE curves -------------------------------------------
    bb_curves = [
        CanonicalCurve(
            curve_id="curve-bb0",
            curve_type=CanonicalCurveType.LINE,
            origin=_pt(0.0, 0.0, 0.0),
            direction=_v3(1.0, 0.0, 0.0),
        ),
        CanonicalCurve(
            curve_id="curve-bb1",
            curve_type=CanonicalCurveType.LINE,
            origin=_pt(1.0, 0.0, 0.0),
            direction=_v3(-0.5, 1.0, 0.0),
        ),
        CanonicalCurve(
            curve_id="curve-bb2",
            curve_type=CanonicalCurveType.LINE,
            origin=_pt(0.5, 1.0, 0.0),
            direction=_v3(-0.5, -1.0, 0.0),
        ),
    ]

    # --- 3 backbone edges (shared by all loops) ---------------------------
    bb_edges = [
        CanonicalEdge(
            edge_id="edge-bb0",
            start_vertex_id="v0",
            end_vertex_id="v1",
            curve_id="curve-bb0",
            orientation=Orientation.FORWARD,
        ),
        CanonicalEdge(
            edge_id="edge-bb1",
            start_vertex_id="v1",
            end_vertex_id="v2",
            curve_id="curve-bb1",
            orientation=Orientation.FORWARD,
        ),
        CanonicalEdge(
            edge_id="edge-bb2",
            start_vertex_id="v2",
            end_vertex_id="v0",
            curve_id="curve-bb2",
            orientation=Orientation.FORWARD,
        ),
    ]
    _BB_EDGE_IDS = ("edge-bb0", "edge-bb1", "edge-bb2")

    # --- per-face loops and face objects ----------------------------------
    # Also collect per-surface CIRCLE curves for geometry completeness
    extra_curves: list[CanonicalCurve] = []
    loops: list[CanonicalLoop] = []
    faces: list[CanonicalFace] = []

    for i, (sid, ltype) in enumerate(face_specs):
        surf = surf_map[sid]
        cid = f"curve-{i:03d}"
        lid = f"loop-{i:03d}"
        fid = f"face-{i:03d}"

        # Surface-representative curve (CIRCLE for cylinders/cones/tori,
        # LINE for planes)
        is_curved = surf.surface_type in (
            CanonicalSurfaceType.CYLINDER,
            CanonicalSurfaceType.CONE,
            CanonicalSurfaceType.SPHERE,
            CanonicalSurfaceType.TORUS,
        )
        if is_curved and surf.radius is not None:
            extra_curves.append(CanonicalCurve(
                curve_id=cid,
                curve_type=CanonicalCurveType.CIRCLE,
                center=surf.center or surf.origin,
                radius=surf.radius,
            ))
        else:
            extra_curves.append(CanonicalCurve(
                curve_id=cid,
                curve_type=CanonicalCurveType.LINE,
                origin=surf.origin or _pt(0.0, 0.0, 0.0),
                direction=surf.normal or _v3(0.0, 0.0, 1.0),
            ))

        loops.append(CanonicalLoop(
            loop_id=lid,
            edge_ids=_BB_EDGE_IDS,   # 3 shared backbone edges — valid
            loop_type=ltype,
            orientation=Orientation.FORWARD,
        ))
        faces.append(CanonicalFace(
            face_id=fid,
            surface_id=sid,
            boundary_loop_ids=(lid,),
            orientation=Orientation.FORWARD,
        ))

    all_curves = bb_curves + extra_curves
    geometry = CanonicalGeometry(
        geometry_id=f"geom-{topo_id}",
        curves=tuple(sorted(all_curves, key=lambda c: c.curve_id)),
        surfaces=tuple(sorted(surfaces, key=lambda s: s.surface_id)),
    )

    shell = CanonicalShell(
        shell_id="shell-0",
        face_ids=tuple(f.face_id for f in faces),
        closure=ShellClosure.CLOSED,
        is_oriented=True,
    )
    body = CanonicalBody(
        body_id="body-0",
        body_type=BodyType.SOLID,
        shell_ids=("shell-0",),
        bounding_box=bbox,
    )
    topo = CanonicalTopology(
        topology_id=topo_id,
        vertices=(v0, v1, v2),
        edges=tuple(bb_edges),
        loops=tuple(sorted(loops, key=lambda lp: lp.loop_id)),
        faces=tuple(sorted(faces, key=lambda f: f.face_id)),
        shells=(shell,),
        bodies=(body,),
        geometry=geometry,
    )
    return topo, geometry


# ---------------------------------------------------------------------------
# Case A — Block with blind hole (Ø8 × 8 mm)
# ---------------------------------------------------------------------------

def build_case_a() -> tuple[CanonicalTopology, CanonicalGeometry, dict]:
    """Case A: 20×20×10 mm block with blind hole Ø8×8 mm, axis=+Z."""
    surfaces = [
        _make_plane_surface("surf-top", origin_z=10.0, normal_z=1.0),     # face-000 TOP
        _make_plane_surface("surf-bot", origin_z=0.0, normal_z=-1.0),      # face-001 BOTTOM
        _make_plane_surface("surf-floor", origin_z=2.0, normal_z=1.0),     # face-002 HOLE FLOOR
        _make_cylinder_surface("surf-hole", 10.0, 10.0, 5.0, 4.0),         # face-003 HOLE WALL
    ]
    face_specs = [
        ("surf-top", LoopType.OUTER),    # face-000
        ("surf-bot", LoopType.OUTER),    # face-001
        ("surf-floor", LoopType.OUTER),  # face-002
        ("surf-hole", LoopType.INNER),   # face-003
    ]
    adjacency = [(0, 3), (2, 3)]  # top→hole, floor→hole
    bbox = _bbox(0.0, 0.0, 0.0, 20.0, 20.0, 10.0)
    topo, geom = _minimal_topo("case-a", surfaces, face_specs, adjacency, bbox)
    expected = {
        "feature_type": "BLIND_HOLE",
        "diameter_mm": 8.0,
        "surface_type": "CYLINDER",
    }
    return topo, geom, expected


# ---------------------------------------------------------------------------
# Case B — Block with counterbore (Ø6 × 15 through, Ø12 × 5)
# ---------------------------------------------------------------------------

def build_case_b() -> tuple[CanonicalTopology, CanonicalGeometry, dict]:
    """Case B: Block with counterbore — Ø6 × 15 through + Ø12 × 5 counterbore."""
    surfaces = [
        _make_plane_surface("surf-top", origin_z=20.0, normal_z=1.0),
        _make_plane_surface("surf-bot", origin_z=0.0, normal_z=-1.0),
        _make_plane_surface("surf-cb-floor", origin_z=15.0, normal_z=1.0),  # counterbore floor
        _make_cylinder_surface("surf-small-cyl", 15.0, 15.0, 10.0, 3.0),    # Ø6 bore
        _make_cylinder_surface("surf-large-cyl", 15.0, 15.0, 17.5, 6.0),    # Ø12 counterbore
    ]
    face_specs = [
        ("surf-top", LoopType.OUTER),
        ("surf-bot", LoopType.OUTER),
        ("surf-cb-floor", LoopType.OUTER),
        ("surf-small-cyl", LoopType.INNER),
        ("surf-large-cyl", LoopType.INNER),
    ]
    adjacency = [(2, 4), (2, 3), (0, 4)]
    bbox = _bbox(0.0, 0.0, 0.0, 30.0, 30.0, 20.0)
    topo, geom = _minimal_topo("case-b", surfaces, face_specs, adjacency, bbox)
    expected = {
        "feature_type": "COUNTERBORE",
        "surface_type": "CYLINDER",
    }
    return topo, geom, expected


# ---------------------------------------------------------------------------
# Case C — Block with countersink (Ø5 pilot + 90° cone)
# ---------------------------------------------------------------------------

def build_case_c() -> tuple[CanonicalTopology, CanonicalGeometry, dict]:
    """Case C: Block with countersink — Ø5 pilot + CONE surface at entry."""
    surfaces = [
        _make_plane_surface("surf-top", origin_z=15.0, normal_z=1.0),
        _make_plane_surface("surf-bot", origin_z=0.0, normal_z=-1.0),
        _make_cylinder_surface("surf-pilot", 10.0, 10.0, 7.5, 2.5),    # Ø5 pilot
        _make_cone_surface("surf-cs", 10.0, 10.0, 13.0, 4.0, 45.0),   # 90° countersink
    ]
    face_specs = [
        ("surf-top", LoopType.OUTER),
        ("surf-bot", LoopType.OUTER),
        ("surf-pilot", LoopType.INNER),
        ("surf-cs", LoopType.INNER),
    ]
    adjacency = [(2, 3), (0, 3)]
    bbox = _bbox(0.0, 0.0, 0.0, 20.0, 20.0, 15.0)
    topo, geom = _minimal_topo("case-c", surfaces, face_specs, adjacency, bbox)
    expected = {
        "feature_type": "COUNTERSINK",
        "surface_type": "CYLINDER",
    }
    return topo, geom, expected


# ---------------------------------------------------------------------------
# Case D — Block with closed pocket (15×10×8 mm)
# ---------------------------------------------------------------------------

def build_case_d() -> tuple[CanonicalTopology, CanonicalGeometry, dict]:
    """Case D: Block with closed pocket 15×10×8 mm."""
    surfaces = [
        _make_plane_surface("surf-top", origin_z=20.0, normal_z=1.0),
        _make_plane_surface("surf-bot", origin_z=0.0, normal_z=-1.0),
        _make_plane_surface("surf-floor", origin_z=12.0, normal_z=1.0),   # pocket floor
        # 4 walls perpendicular to floor normal — use horizontal planes with rotated normals
        CanonicalSurface(
            surface_id="surf-wall-n",
            surface_type=CanonicalSurfaceType.PLANE,
            origin=_pt(7.5, 15.0, 16.0),
            normal=_v3(0.0, 1.0, 0.0),
        ),
        CanonicalSurface(
            surface_id="surf-wall-s",
            surface_type=CanonicalSurfaceType.PLANE,
            origin=_pt(7.5, 5.0, 16.0),
            normal=_v3(0.0, -1.0, 0.0),
        ),
        CanonicalSurface(
            surface_id="surf-wall-e",
            surface_type=CanonicalSurfaceType.PLANE,
            origin=_pt(22.5, 10.0, 16.0),
            normal=_v3(1.0, 0.0, 0.0),
        ),
        CanonicalSurface(
            surface_id="surf-wall-w",
            surface_type=CanonicalSurfaceType.PLANE,
            origin=_pt(7.5, 10.0, 16.0),
            normal=_v3(-1.0, 0.0, 0.0),
        ),
    ]
    face_specs = [
        ("surf-top", LoopType.OUTER),
        ("surf-bot", LoopType.OUTER),
        ("surf-floor", LoopType.OUTER),
        ("surf-wall-n", LoopType.OUTER),
        ("surf-wall-s", LoopType.OUTER),
        ("surf-wall-e", LoopType.OUTER),
        ("surf-wall-w", LoopType.OUTER),
    ]
    adjacency = [(2, 3), (2, 4), (2, 5), (2, 6)]  # floor adj to each wall
    bbox = _bbox(0.0, 0.0, 0.0, 30.0, 20.0, 20.0)
    topo, geom = _minimal_topo("case-d", surfaces, face_specs, adjacency, bbox)
    expected = {
        "feature_type": "CLOSED_POCKET",
        "surface_type": "PLANE",
    }
    return topo, geom, expected


# ---------------------------------------------------------------------------
# Case E — Block with open slot (8×6 mm)
# ---------------------------------------------------------------------------

def build_case_e() -> tuple[CanonicalTopology, CanonicalGeometry, dict]:
    """Case E: Block with open slot W8 × D6 mm, open at two ends."""
    surfaces = [
        _make_plane_surface("surf-top", origin_z=20.0, normal_z=1.0),
        _make_plane_surface("surf-bot", origin_z=0.0, normal_z=-1.0),
        _make_plane_surface("surf-floor", origin_z=14.0, normal_z=1.0),  # slot floor
        CanonicalSurface(
            surface_id="surf-wall-a",
            surface_type=CanonicalSurfaceType.PLANE,
            origin=_pt(4.0, 15.0, 17.0),
            normal=_v3(1.0, 0.0, 0.0),
        ),
        CanonicalSurface(
            surface_id="surf-wall-b",
            surface_type=CanonicalSurfaceType.PLANE,
            origin=_pt(12.0, 15.0, 17.0),
            normal=_v3(-1.0, 0.0, 0.0),
        ),
    ]
    face_specs = [
        ("surf-top", LoopType.OUTER),
        ("surf-bot", LoopType.OUTER),
        ("surf-floor", LoopType.OUTER),
        ("surf-wall-a", LoopType.OUTER),
        ("surf-wall-b", LoopType.OUTER),
    ]
    adjacency = [(2, 3), (2, 4)]
    bbox = _bbox(0.0, 0.0, 0.0, 20.0, 30.0, 20.0)
    topo, geom = _minimal_topo("case-e", surfaces, face_specs, adjacency, bbox)
    expected = {
        "feature_type": "OPEN_SLOT",
        "surface_type": "PLANE",
    }
    return topo, geom, expected


# ---------------------------------------------------------------------------
# Case F — Boss (Ø15×8 mm raised cylinder on 30×30×5 base)
# ---------------------------------------------------------------------------

def build_case_f() -> tuple[CanonicalTopology, CanonicalGeometry, dict]:
    """Case F: Base plate 30×30×5 mm + central boss Ø15×8 mm."""
    surfaces = [
        _make_plane_surface("surf-base", origin_z=5.0, normal_z=1.0),      # base top face
        _make_plane_surface("surf-bot", origin_z=0.0, normal_z=-1.0),
        _make_plane_surface("surf-boss-top", origin_z=13.0, normal_z=1.0),  # boss top
        _make_cylinder_surface("surf-boss-cyl", 15.0, 15.0, 9.0, 7.5),     # Ø15 boss wall
    ]
    face_specs = [
        ("surf-base", LoopType.OUTER),
        ("surf-bot", LoopType.OUTER),
        ("surf-boss-top", LoopType.OUTER),
        ("surf-boss-cyl", LoopType.OUTER),
    ]
    adjacency = [(0, 3), (2, 3)]  # base adj boss-cyl, boss-top adj boss-cyl
    bbox = _bbox(0.0, 0.0, 0.0, 30.0, 30.0, 13.0)
    topo, geom = _minimal_topo("case-f", surfaces, face_specs, adjacency, bbox)
    expected = {
        "feature_type": "BOSS",
        "surface_type": "CYLINDER",
        "diameter_mm": 15.0,
    }
    return topo, geom, expected


# ---------------------------------------------------------------------------
# Case G — Stepped shaft (3 diameters: Ø30×25, Ø20×30, Ø14×20)
# ---------------------------------------------------------------------------

def build_case_g() -> tuple[CanonicalTopology, CanonicalGeometry, dict]:
    """Case G: Stepped shaft — 3 coaxial cylinders + shoulder faces."""
    surfaces = [
        _make_plane_surface("surf-end-l", origin_z=0.0, normal_z=-1.0),
        _make_plane_surface("surf-end-r", origin_z=75.0, normal_z=1.0),
        _make_plane_surface("surf-sh1", origin_z=25.0, normal_z=1.0),   # shoulder 1
        _make_plane_surface("surf-sh2", origin_z=55.0, normal_z=1.0),   # shoulder 2
        _make_cylinder_surface("surf-od1", 0.0, 0.0, 12.5, 15.0),       # Ø30
        _make_cylinder_surface("surf-od2", 0.0, 0.0, 40.0, 10.0),       # Ø20
        _make_cylinder_surface("surf-od3", 0.0, 0.0, 65.0, 7.0),        # Ø14
    ]
    face_specs = [
        ("surf-end-l", LoopType.OUTER),
        ("surf-end-r", LoopType.OUTER),
        ("surf-sh1", LoopType.OUTER),
        ("surf-sh2", LoopType.OUTER),
        ("surf-od1", LoopType.OUTER),
        ("surf-od2", LoopType.OUTER),
        ("surf-od3", LoopType.OUTER),
    ]
    adjacency = [(2, 4), (2, 5), (3, 5), (3, 6)]
    bbox = _bbox(-15.0, -15.0, 0.0, 15.0, 15.0, 75.0)
    topo, geom = _minimal_topo("case-g", surfaces, face_specs, adjacency, bbox)
    expected = {
        "has_outer_diameter": True,
        "has_groove": False,
        "diameter_count": 3,
    }
    return topo, geom, expected


# ---------------------------------------------------------------------------
# Case H — Shaft with groove (Ø30 with Ø16×4 groove)
# ---------------------------------------------------------------------------

def build_case_h() -> tuple[CanonicalTopology, CanonicalGeometry, dict]:
    """Case H: Shaft Ø30 with turning groove Ø16×4 flanked by shoulder faces."""
    surfaces = [
        _make_plane_surface("surf-end-l", origin_z=0.0, normal_z=-1.0),
        _make_plane_surface("surf-end-r", origin_z=50.0, normal_z=1.0),
        _make_plane_surface("surf-gr-sh-l", origin_z=20.0, normal_z=-1.0),  # groove left wall
        _make_plane_surface("surf-gr-sh-r", origin_z=24.0, normal_z=1.0),   # groove right wall
        _make_cylinder_surface("surf-od", 0.0, 0.0, 25.0, 15.0),            # Ø30 OD
        _make_cylinder_surface("surf-groove", 0.0, 0.0, 22.0, 8.0),         # Ø16 groove
    ]
    face_specs = [
        ("surf-end-l", LoopType.OUTER),
        ("surf-end-r", LoopType.OUTER),
        ("surf-gr-sh-l", LoopType.OUTER),
        ("surf-gr-sh-r", LoopType.OUTER),
        ("surf-od", LoopType.OUTER),
        ("surf-groove", LoopType.OUTER),
    ]
    adjacency = [(2, 5), (3, 5), (2, 4), (3, 4)]
    bbox = _bbox(-15.0, -15.0, 0.0, 15.0, 15.0, 50.0)
    topo, geom = _minimal_topo("case-h", surfaces, face_specs, adjacency, bbox)
    expected = {
        "feature_type": "GROOVE",
        "diameter_mm": 16.0,
    }
    return topo, geom, expected


# ---------------------------------------------------------------------------
# Case I — Hole pattern (4× Ø6 on 50 mm bolt circle)
# ---------------------------------------------------------------------------

def build_case_i() -> tuple[CanonicalTopology, CanonicalGeometry, dict]:
    """Case I: Block + 4× Ø6 through-holes on 50 mm PCD (circular pattern)."""
    import math
    pcd = 25.0  # radius = 25 mm → PCD = 50 mm
    hole_r = 3.0
    surfaces: list[CanonicalSurface] = [
        _make_plane_surface("surf-top", origin_z=20.0, normal_z=1.0),
        _make_plane_surface("surf-bot", origin_z=0.0, normal_z=-1.0),
    ]
    face_specs: list[tuple[str, LoopType]] = [
        ("surf-top", LoopType.OUTER),
        ("surf-bot", LoopType.OUTER),
    ]
    for k in range(4):
        angle = k * math.pi / 2  # 0°, 90°, 180°, 270°
        cx = pcd * math.cos(angle)
        cy = pcd * math.sin(angle)
        sid = f"surf-hole-{k}"
        surfaces.append(
            _make_cylinder_surface(sid, cx, cy, 10.0, hole_r)
        )
        face_specs.append((sid, LoopType.INNER))

    bbox = _bbox(-50.0, -50.0, 0.0, 50.0, 50.0, 20.0)
    topo, geom = _minimal_topo("case-i", surfaces, face_specs, None, bbox)
    expected = {
        "hole_count": 4,
        "pattern_type": "CIRCULAR",
        "pcd_mm": 50.0,
        "diameter_mm": 6.0,
    }
    return topo, geom, expected


# ---------------------------------------------------------------------------
# Case J — Mixed prismatic (pocket + holes + counterbore + chamfer + fillet)
# ---------------------------------------------------------------------------

def build_case_j() -> tuple[CanonicalTopology, CanonicalGeometry, dict]:
    """Case J: Complex part — pocket + 2 blind holes + counterbore + chamfer + fillet."""
    surfaces = [
        _make_plane_surface("surf-top", origin_z=30.0, normal_z=1.0),
        _make_plane_surface("surf-bot", origin_z=0.0, normal_z=-1.0),
        _make_plane_surface("surf-pock-floor", origin_z=20.0, normal_z=1.0),
        CanonicalSurface(
            surface_id="surf-pock-wall1",
            surface_type=CanonicalSurfaceType.PLANE,
            origin=_pt(10.0, 20.0, 25.0),
            normal=_v3(0.0, 1.0, 0.0),
        ),
        CanonicalSurface(
            surface_id="surf-pock-wall2",
            surface_type=CanonicalSurfaceType.PLANE,
            origin=_pt(10.0, 40.0, 25.0),
            normal=_v3(0.0, -1.0, 0.0),
        ),
        CanonicalSurface(
            surface_id="surf-pock-wall3",
            surface_type=CanonicalSurfaceType.PLANE,
            origin=_pt(40.0, 30.0, 25.0),
            normal=_v3(1.0, 0.0, 0.0),
        ),
        _make_cylinder_surface("surf-hole1", 15.0, 15.0, 15.0, 4.0),    # Ø8 hole1
        _make_cylinder_surface("surf-hole2", 35.0, 15.0, 15.0, 4.0),    # Ø8 hole2
        _make_cylinder_surface("surf-cb-small", 15.0, 45.0, 15.0, 3.0), # Ø6 CB pilot
        _make_cylinder_surface("surf-cb-large", 15.0, 45.0, 25.0, 6.0), # Ø12 CB top
        _make_plane_surface("surf-cb-floor", origin_z=22.0, normal_z=1.0),
        _make_cone_surface("surf-chmf", 35.0, 45.0, 28.0, 3.0, 45.0),  # chamfer
        _make_torus_surface("surf-fillet", 15.0, 30.0, 20.0, 10.0, 2.0),  # fillet
    ]
    face_specs = [
        ("surf-top", LoopType.OUTER),       # 0
        ("surf-bot", LoopType.OUTER),       # 1
        ("surf-pock-floor", LoopType.OUTER), # 2
        ("surf-pock-wall1", LoopType.OUTER), # 3
        ("surf-pock-wall2", LoopType.OUTER), # 4
        ("surf-pock-wall3", LoopType.OUTER), # 5
        ("surf-hole1", LoopType.INNER),     # 6
        ("surf-hole2", LoopType.INNER),     # 7
        ("surf-cb-small", LoopType.INNER),  # 8
        ("surf-cb-large", LoopType.INNER),  # 9
        ("surf-cb-floor", LoopType.OUTER),  # 10
        ("surf-chmf", LoopType.INNER),      # 11
        ("surf-fillet", LoopType.OUTER),    # 12
    ]
    adjacency = [
        (2, 3), (2, 4), (2, 5),  # pocket floor → walls
        (9, 10), (8, 9),          # counterbore
    ]
    bbox = _bbox(0.0, 0.0, 0.0, 50.0, 60.0, 30.0)
    topo, geom = _minimal_topo("case-j", surfaces, face_specs, adjacency, bbox)
    expected = {
        "min_features": 6,  # pocket + 2 holes + counterbore + chamfer + fillet
        "has_pocket": True,
        "has_counterbore": True,
        "has_chamfer": True,
        "has_fillet": True,
    }
    return topo, geom, expected


ALL_CASES = {
    "A": build_case_a,
    "B": build_case_b,
    "C": build_case_c,
    "D": build_case_d,
    "E": build_case_e,
    "F": build_case_f,
    "G": build_case_g,
    "H": build_case_h,
    "I": build_case_i,
    "J": build_case_j,
}
