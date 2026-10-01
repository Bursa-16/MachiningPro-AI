"""Stage 4B: canonical topology model tests for the interoperability layer."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.domain.exceptions import ValidationError
from backend.domain.units import Quantity, Unit
from backend.interoperability.enums import (
    AdapterLicense,
    CapabilityLevel,
    FormatFamily,
    NormalizationStatus,
)
from backend.interoperability.geometry import (
    CanonicalCurve,
    CanonicalCurveType,
    CanonicalGeometry,
    CanonicalPoint3D,
    CanonicalSurface,
    CanonicalSurfaceType,
)
from backend.interoperability.models import (
    CanonicalDocument,
    CanonicalEntityRef,
    EngineeringSource,
    FormatDescriptor,
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
    TopologyContainerError,
    Transform3D,
)

# ---------------------------------------------------------------------------
# Builders for the rectangular-block synthetic example
# ---------------------------------------------------------------------------

def _mm(v):
    return Quantity.of(v, Unit.MM)

def _cube_vertices():
    coords = [
        (0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0),
        (0, 0, 10), (10, 0, 10), (10, 10, 10), (0, 10, 10),
    ]
    return tuple(
        CanonicalVertex(f"V{i}", CanonicalPoint3D(_mm(x), _mm(y), _mm(z)))
        for i, (x, y, z) in enumerate(coords)
    )

_EDGE_SPECS = (
    ("E0", "V0", "V1"), ("E1", "V1", "V2"), ("E2", "V2", "V3"), ("E3", "V3", "V0"),
    ("E4", "V4", "V5"), ("E5", "V5", "V6"), ("E6", "V6", "V7"), ("E7", "V7", "V4"),
    ("E8", "V0", "V4"), ("E9", "V1", "V5"), ("E10", "V2", "V6"), ("E11", "V3", "V7"),
)

_FACE_EDGES = {
    "FBOTTOM": ("E0", "E1", "E2", "E3"),
    "FTOP":    ("E4", "E7", "E6", "E5"),
    "FFRONT":  ("E0", "E9", "E4", "E8"),
    "FRIGHT":  ("E1", "E10", "E5", "E9"),
    "FBACK":   ("E2", "E11", "E6", "E10"),
    "FLEFT":   ("E3", "E8", "E7", "E11"),
}

def _cube_curves():
    return tuple(
        CanonicalCurve(f"C{i}", CanonicalCurveType.LINE) for i in range(12)
    )

def _cube_edges():
    return tuple(
        CanonicalEdge(eid, sv, ev, f"C{idx}", Orientation.FORWARD)
        for idx, (eid, sv, ev) in enumerate(_EDGE_SPECS)
    )

def _cube_surfaces():
    return tuple(
        CanonicalSurface(fid, CanonicalSurfaceType.PLANE)
        for fid in _FACE_EDGES
    )

def _cube_loops():
    return tuple(
        CanonicalLoop(
            f"L_{fid}",
            edge_ids=eids,
            loop_type=LoopType.OUTER,
        )
        for fid, eids in _FACE_EDGES.items()
    )

def _cube_faces():
    return tuple(
        CanonicalFace(
            fid,
            fid,
            (f"L_{fid}",),
            Orientation.FORWARD,
        )
        for fid in _FACE_EDGES
    )

def _cube_shell():
    return CanonicalShell(
        "SH1",
        tuple(f.face_id for f in _cube_faces()),
        ShellClosure.CLOSED,
    )

def _cube_body():
    return CanonicalBody("B1", BodyType.SOLID, (_cube_shell().shell_id,))

def _cube_geometry():
    return CanonicalGeometry(
        "G1",
        curves=_cube_curves(),
        surfaces=_cube_surfaces(),
    )

def _cube_topology(with_geometry: bool = True):
    kwargs = {
        "topology_id": "T1",
        "vertices": _cube_vertices(),
        "edges": _cube_edges(),
        "loops": _cube_loops(),
        "faces": _cube_faces(),
        "shells": (_cube_shell(),),
        "bodies": (_cube_body(),),
    }
    if with_geometry:
        kwargs["geometry"] = _cube_geometry()
    return CanonicalTopology(**kwargs)

# ---------------------------------------------------------------------------
# A. CanonicalVertex / CanonicalLoop / CanonicalFace / CanonicalShell / CanonicalBody
# ---------------------------------------------------------------------------

class TestCanonicalVertex:
    def test_basic(self) -> None:
        p = CanonicalPoint3D(_mm(0), _mm(0), _mm(0))
        v = CanonicalVertex("V1", p)
        assert v.vertex_id == "V1"
        assert v.point is p

    def test_empty_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalVertex("", CanonicalPoint3D(_mm(0), _mm(0), _mm(0)))

    def test_immutable(self) -> None:
        v = CanonicalVertex("V1", CanonicalPoint3D(_mm(0), _mm(0), _mm(0)))
        with pytest.raises((AttributeError, TypeError)):
            v.vertex_id = "MUTATED"  # type: ignore[misc]

class TestCanonicalEdge:
    def test_basic(self) -> None:
        e = CanonicalEdge("E1", "V0", "V1", "C0")
        assert e.curve_id == "C0"

    def test_start_equals_end_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalEdge("E1", "V0", "V0", "C0")

    def test_empty_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalEdge("", "V0", "V1", "C0")
        with pytest.raises(ValidationError):
            CanonicalEdge("E1", "", "V1", "C0")
        with pytest.raises(ValidationError):
            CanonicalEdge("E1", "V0", "", "C0")
        with pytest.raises(ValidationError):
            CanonicalEdge("E1", "V0", "V1", "")

    def test_orientation_coercion_from_string(self) -> None:
        e = CanonicalEdge("E1", "V0", "V1", "C0", orientation="FORWARD")
        assert e.orientation is Orientation.FORWARD

    def test_bad_orientation_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalEdge("E1", "V0", "V1", "C0", orientation="NONSENSE")  # type: ignore[arg-type]

    def test_immutable(self) -> None:
        e = CanonicalEdge("E1", "V0", "V1", "C0")
        with pytest.raises((AttributeError, TypeError)):
            e.curve_id = "MUTATED"  # type: ignore[misc]

class TestCanonicalLoop:
    def test_minimum_three_edges(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalLoop("L1", edge_ids=("E0", "E1"))

    def test_duplicate_edge_ref_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalLoop(
                "L1", edge_ids=("E0", "E1", "E0")
            )

    def test_blank_edge_ref_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalLoop("L1", edge_ids=("E0", "E1", " "))

    def test_order_preserved(self) -> None:
        loop = CanonicalLoop("L1", edge_ids=("E0", "E1", "E2"))
        assert loop.edge_ids == ("E0", "E1", "E2")

    def test_orientation_string(self) -> None:
        loop = CanonicalLoop("L1", edge_ids=("E0", "E1", "E2"), orientation="FORWARD")
        assert loop.orientation is Orientation.FORWARD

    def test_immutable(self) -> None:
        loop = CanonicalLoop("L1", edge_ids=("E0", "E1", "E2"))
        with pytest.raises((AttributeError, TypeError)):
            loop.loop_id = "MUTATED"  # type: ignore[misc]

class TestCanonicalFace:
    def test_requires_at_least_one_loop(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalFace("F1", "S1", boundary_loop_ids=())

    def test_duplicate_loop_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalFace("F1", "S1", boundary_loop_ids=("L1", "L1", "L2"))

    def test_outer_then_inner_order_preserved(self) -> None:
        f = CanonicalFace(
            "F1", "S1",
            ("L_OUTER", "L_INNER1", "L_INNER2"),
            Orientation.FORWARD,
        )
        assert f.boundary_loop_ids == ("L_OUTER", "L_INNER1", "L_INNER2")

    def test_immutable(self) -> None:
        f = CanonicalFace("F1", "S1", ("L1",))
        with pytest.raises((AttributeError, TypeError)):
            f.surface_id = "MUTATED"  # type: ignore[misc]

class TestCanonicalShell:
    def test_requires_at_least_one_face(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalShell("SH1", face_ids=())

    def test_duplicate_face_ref_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalShell("SH1", face_ids=("F0", "F1", "F0"))

    def test_default_closure_unknown(self) -> None:
        sh = CanonicalShell("SH1", face_ids=("F0", "F1", "F2"))
        assert sh.closure is ShellClosure.UNKNOWN

    def test_immutable(self) -> None:
        sh = CanonicalShell("SH1", face_ids=("F0", "F1", "F2"))
        with pytest.raises((AttributeError, TypeError)):
            sh.closure = ShellClosure.CLOSED  # type: ignore[misc]

class TestCanonicalBody:
    def test_requires_shell(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalBody("B1", BodyType.SOLID, shell_ids=())

    def test_duplicate_shell_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalBody("B1", BodyType.SOLID, shell_ids=("SH1", "SH1"))

    def test_body_type_string_coerced(self) -> None:
        b = CanonicalBody("B1", "SOLID", ("SH1",))
        assert b.body_type is BodyType.SOLID

    def test_immutable(self) -> None:
        b = CanonicalBody("B1", BodyType.SOLID, ("SH1",))
        with pytest.raises((AttributeError, TypeError)):
            b.body_id = "MUTATED"  # type: ignore[misc]

class TestTransform3D:
    def test_default_identity(self) -> None:
        t = Transform3D()
        assert t.translation == (Decimal(0), Decimal(0), Decimal(0))
        assert t.rotation == ()

    def test_translation_length_must_be_three(self) -> None:
        with pytest.raises(ValidationError):
            Transform3D(translation=(Decimal(0), Decimal(0)))

    def test_rotation_must_be_nine(self) -> None:
        with pytest.raises(ValidationError):
            Transform3D(rotation=(Decimal(1),) * 5)

    def test_non_finite_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Transform3D(translation=(Decimal("NaN"), Decimal(0), Decimal(0)))

    def test_immutable(self) -> None:
        t = Transform3D()
        with pytest.raises((AttributeError, TypeError)):
            t.translation = (Decimal(1), Decimal(0), Decimal(0))  # type: ignore[misc]

# ---------------------------------------------------------------------------
# B. Reference integrity inside CanonicalTopology
# ---------------------------------------------------------------------------

class TestReferenceIntegrity:
    def test_valid_cube_builds(self) -> None:
        t = _cube_topology()
        assert len(t.vertices) == 8
        assert len(t.edges) == 12
        assert len(t.loops) == 6
        assert len(t.faces) == 6
        assert len(t.shells) == 1
        assert len(t.bodies) == 1

    def test_missing_start_vertex_rejected(self) -> None:
        edges = tuple(
            CanonicalEdge(eid, sv, ev, f"C{idx}", Orientation.FORWARD)
            for idx, (eid, sv, ev) in enumerate(_EDGE_SPECS)
        )
        # Patch: make E0 reference a non-existent start vertex.
        edges = (CanonicalEdge("E_BAD", "V_MISSING", "V0", "C0"),) + edges[1:]
        with pytest.raises(TopologyContainerError):
            CanonicalTopology(
                "T1",
                vertices=_cube_vertices(),
                edges=edges,
                loops=_cube_loops(),
                faces=_cube_faces(),
                shells=(_cube_shell(),),
                bodies=(_cube_body(),),
                geometry=_cube_geometry(),
            )

    def test_missing_end_vertex_rejected(self) -> None:
        edges = list(_cube_edges())
        edges[0] = CanonicalEdge("E0", "V0", "V_MISSING", "C0")
        with pytest.raises(TopologyContainerError):
            CanonicalTopology(
                "T1",
                vertices=_cube_vertices(),
                edges=tuple(edges),
                loops=_cube_loops(),
                faces=_cube_faces(),
                shells=(_cube_shell(),),
                bodies=(_cube_body(),),
                geometry=_cube_geometry(),
            )

    def test_missing_curve_rejected(self) -> None:
        edges = list(_cube_edges())
        edges[0] = CanonicalEdge("E0", "V0", "V1", "C_MISSING")
        with pytest.raises(TopologyContainerError):
            CanonicalTopology(
                "T1",
                vertices=_cube_vertices(),
                edges=tuple(edges),
                loops=_cube_loops(),
                faces=_cube_faces(),
                shells=(_cube_shell(),),
                bodies=(_cube_body(),),
                geometry=_cube_geometry(),
            )

    def test_missing_loop_edge_rejected(self) -> None:
        loops = list(_cube_loops())
        # Replace edge E0 reference with E_MISSING in the first loop.
        first = loops[0]
        loops[0] = CanonicalLoop(
            first.loop_id,
            ("E_MISSING", first.edge_ids[1], first.edge_ids[2]),
            loop_type=first.loop_type,
        )
        with pytest.raises(TopologyContainerError):
            CanonicalTopology(
                "T1",
                vertices=_cube_vertices(),
                edges=_cube_edges(),
                loops=tuple(loops),
                faces=_cube_faces(),
                shells=(_cube_shell(),),
                bodies=(_cube_body(),),
                geometry=_cube_geometry(),
            )

    def test_missing_face_surface_rejected(self) -> None:
        faces = list(_cube_faces())
        first = faces[0]
        faces[0] = CanonicalFace(
            first.face_id, "S_MISSING", first.boundary_loop_ids
        )
        with pytest.raises(TopologyContainerError):
            CanonicalTopology(
                "T1",
                vertices=_cube_vertices(),
                edges=_cube_edges(),
                loops=_cube_loops(),
                faces=tuple(faces),
                shells=(_cube_shell(),),
                bodies=(_cube_body(),),
                geometry=_cube_geometry(),
            )

    def test_missing_face_loop_rejected(self) -> None:
        faces = list(_cube_faces())
        first = faces[0]
        faces[0] = CanonicalFace(
            first.face_id, first.surface_id, ("L_MISSING",)
        )
        with pytest.raises(TopologyContainerError):
            CanonicalTopology(
                "T1",
                vertices=_cube_vertices(),
                edges=_cube_edges(),
                loops=_cube_loops(),
                faces=tuple(faces),
                shells=(_cube_shell(),),
                bodies=(_cube_body(),),
                geometry=_cube_geometry(),
            )

    def test_missing_shell_face_rejected(self) -> None:
        sh = CanonicalShell("SH1", ("F_MISSING",) + tuple(
            f.face_id for f in _cube_faces()
        )[1:], ShellClosure.CLOSED)
        with pytest.raises(TopologyContainerError):
            CanonicalTopology(
                "T1",
                vertices=_cube_vertices(),
                edges=_cube_edges(),
                loops=_cube_loops(),
                faces=_cube_faces(),
                shells=(sh,),
                bodies=(_cube_body(),),
                geometry=_cube_geometry(),
            )

    def test_missing_body_shell_rejected(self) -> None:
        body = CanonicalBody("B1", BodyType.SOLID, ("SH_MISSING",))
        with pytest.raises(TopologyContainerError):
            CanonicalTopology(
                "T1",
                vertices=_cube_vertices(),
                edges=_cube_edges(),
                loops=_cube_loops(),
                faces=_cube_faces(),
                shells=(_cube_shell(),),
                bodies=(body,),
                geometry=_cube_geometry(),
            )

# ---------------------------------------------------------------------------
# C. Duplicate-ID rejection across all topology classes
# ---------------------------------------------------------------------------

class TestDuplicateIDRejection:
    def test_duplicate_vertex_id(self) -> None:
        vs = _cube_vertices()
        vs = (vs[0],) + vs  # duplicate V0
        with pytest.raises(ValidationError):
            CanonicalTopology(
                "T1", vertices=vs, edges=_cube_edges(), loops=_cube_loops(),
                faces=_cube_faces(), shells=(_cube_shell(),),
                bodies=(_cube_body(),), geometry=_cube_geometry(),
            )

    def test_duplicate_edge_id(self) -> None:
        es = _cube_edges()
        es = (es[0],) + es
        with pytest.raises(ValidationError):
            CanonicalTopology(
                "T1", vertices=_cube_vertices(), edges=es,
                loops=_cube_loops(), faces=_cube_faces(),
                shells=(_cube_shell(),), bodies=(_cube_body(),),
                geometry=_cube_geometry(),
            )

    def test_duplicate_loop_id(self) -> None:
        ls = _cube_loops()
        ls = (ls[0],) + ls
        with pytest.raises(ValidationError):
            CanonicalTopology(
                "T1", vertices=_cube_vertices(), edges=_cube_edges(),
                loops=ls, faces=_cube_faces(),
                shells=(_cube_shell(),), bodies=(_cube_body(),),
                geometry=_cube_geometry(),
            )

    def test_duplicate_face_id(self) -> None:
        fs = _cube_faces()
        fs = (fs[0],) + fs
        with pytest.raises(ValidationError):
            CanonicalTopology(
                "T1", vertices=_cube_vertices(), edges=_cube_edges(),
                loops=_cube_loops(), faces=fs,
                shells=(_cube_shell(),), bodies=(_cube_body(),),
                geometry=_cube_geometry(),
            )

    def test_duplicate_shell_id(self) -> None:
        sh = _cube_shell()
        with pytest.raises(ValidationError):
            CanonicalTopology(
                "T1", vertices=_cube_vertices(), edges=_cube_edges(),
                loops=_cube_loops(), faces=_cube_faces(),
                shells=(sh, sh), bodies=(_cube_body(),),
                geometry=_cube_geometry(),
            )

    def test_duplicate_body_id(self) -> None:
        b = _cube_body()
        with pytest.raises(ValidationError):
            CanonicalTopology(
                "T1", vertices=_cube_vertices(), edges=_cube_edges(),
                loops=_cube_loops(), faces=_cube_faces(),
                shells=(_cube_shell(),), bodies=(b, b),
                geometry=_cube_geometry(),
            )

# ---------------------------------------------------------------------------
# D. Determinism / accessors
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_ordered_iteration_sorted(self) -> None:
        t = _cube_topology()
        v_ids = [v.vertex_id for v in t.ordered_vertices]
        assert v_ids == sorted(v_ids)
        e_ids = [e.edge_id for e in t.ordered_edges]
        assert e_ids == sorted(e_ids)

    def test_get_helpers(self) -> None:
        t = _cube_topology()
        assert t.get_vertex("V0").vertex_id == "V0"
        assert t.get_edge("E0").edge_id == "E0"
        assert t.get_face("FTOP").face_id == "FTOP"

    def test_missing_get_raises(self) -> None:
        t = _cube_topology()
        with pytest.raises(TopologyContainerError):
            t.get_vertex("V_MISSING")
        with pytest.raises(TopologyContainerError):
            t.get_edge("E_MISSING")
        with pytest.raises(TopologyContainerError):
            t.get_face("F_MISSING")
        with pytest.raises(TopologyContainerError):
            t.get_shell("SH_MISSING")
        with pytest.raises(TopologyContainerError):
            t.get_body("B_MISSING")
        with pytest.raises(TopologyContainerError):
            t.get_loop("L_MISSING")

    def test_as_dict_deterministic(self) -> None:
        t1 = _cube_topology()
        t2 = _cube_topology()
        assert t1.as_dict() == t2.as_dict()

# ---------------------------------------------------------------------------
# E. Cross-stage composition: Stage 4A + Stage 4B
# ---------------------------------------------------------------------------

class TestStage4AComposition:
    def test_engineering_source_to_canonical_document_to_topology(self) -> None:
        """Stage 4A EngineeringSource + CanonicalDocument composed with
        Stage 4B CanonicalTopology.

        Demonstrates the cross-stage composition without parsing any file.
        """
        source = EngineeringSource(
            source_id="SRC-MP-001",
            source_format_id="STEP-AP242",
            file_name="block.step",
            vendor="ISO",
        )
        descriptor = FormatDescriptor(
            format_id="STEP-AP242",
            canonical_name="STEP AP242",
            family=FormatFamily.NEUTRAL_EXCHANGE,
            extensions=("stp", "step"),
            media_types=("model/step",),
            is_open=True,
            adapter_license=AdapterLicense.OPEN_SOURCE,
        )
        document = CanonicalDocument(
            document_id="DOC-MP-001",
            canonical_kind="CAD_GEOMETRY",
            source=source,
            format_descriptor=descriptor,
            adapter_id="occt-step",
            adapter_version="1.0.0",
            capability_level=CapabilityLevel.LEVEL_2_NORMALIZED,
            normalization_status=NormalizationStatus.SUCCESS,
            entity_refs=(
                CanonicalEntityRef(entity_id="B1", entity_kind="CanonicalBody"),
                CanonicalEntityRef(entity_id="FBOTTOM", entity_kind="CanonicalFace"),
            ),
        )

        topology = _cube_topology()
        body_ref = next(r for r in document.entity_refs if r.entity_kind == "CanonicalBody")
        assert body_ref.entity_id == topology.get_body("B1").body_id

        face_ref = next(r for r in document.entity_refs if r.entity_kind == "CanonicalFace")
        assert face_ref.entity_id == topology.get_face("FBOTTOM").face_id
