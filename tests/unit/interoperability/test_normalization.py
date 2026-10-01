"""Stage 4F: Geometry normalization and transform service tests.

Reconstructed recovery test suite for the Stage 4F implementation.
Covers deterministic point/vector/geometry/topology transforms, unit
normalization, validation, and Stage 4A-4E regression guards.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.domain.exceptions import ValidationError
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
from backend.interoperability.normalization import (
    GeometryNormalizationResult,
    TransformApplicationMode,
    apply_transform_to_geometry,
    apply_transform_to_point,
    apply_transform_to_topology,
    apply_transform_to_vector,
    normalize_geometry_units,
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
    ShellClosure,
    Transform3D,
)


def _mm(v: str) -> Quantity:
    return Quantity.of(v, Unit.MM)


def _d(v: str) -> Quantity:
    return Quantity.of(v, Unit.DIMENSIONLESS)


def _pt(x: str, y: str, z: str) -> CanonicalPoint3D:
    return CanonicalPoint3D(_mm(x), _mm(y), _mm(z))


def _vec(x: str, y: str, z: str) -> CanonicalVector3D:
    return CanonicalVector3D(_d(x), _d(y), _d(z))


def _identity() -> Transform3D:
    return Transform3D()


def _translation(tx: str, ty: str, tz: str) -> Transform3D:
    return Transform3D(
        translation=(Decimal(tx), Decimal(ty), Decimal(tz)),
    )


def _rotation_z90() -> Transform3D:
    return Transform3D(
        translation=(Decimal(0), Decimal(0), Decimal(0)),
        rotation=(
            Decimal(0), Decimal(-1), Decimal(0),
            Decimal(1), Decimal(0), Decimal(0),
            Decimal(0), Decimal(0), Decimal(1),
        ),
    )


def _minimal_geo() -> CanonicalGeometry:
    return CanonicalGeometry(
        geometry_id="GEO-001",
        curves=(
            CanonicalCurve(
                curve_id="C-001",
                curve_type=CanonicalCurveType.LINE,
            ),
        ),
        surfaces=(
            CanonicalSurface(
                surface_id="S-001",
                surface_type=CanonicalSurfaceType.PLANE,
            ),
        ),
    )


def _minimal_topo(geo: CanonicalGeometry | None = None) -> CanonicalTopology:
    g = geo or _minimal_geo()
    v1 = CanonicalVertex("V-001", _pt("0", "0", "0"))
    v2 = CanonicalVertex("V-002", _pt("10", "0", "0"))
    v3 = CanonicalVertex("V-003", _pt("10", "10", "0"))
    e1 = CanonicalEdge("E-001", "V-001", "V-002", "C-001")
    e2 = CanonicalEdge("E-002", "V-002", "V-003", "C-001")
    e3 = CanonicalEdge("E-003", "V-003", "V-001", "C-001")
    lp = CanonicalLoop("L-001", ("E-001", "E-002", "E-003"), LoopType.OUTER)
    face = CanonicalFace("F-001", "S-001", ("L-001",))
    shell = CanonicalShell(
        "SH-001",
        ("F-001",),
        closure=ShellClosure.CLOSED,
    )
    body = CanonicalBody(
        body_id="B-001",
        body_type=BodyType.SOLID,
        shell_ids=("SH-001",),
    )
    return CanonicalTopology(
        topology_id="TOPO-001",
        geometry=g,
        vertices=(v1, v2, v3),
        edges=(e1, e2, e3),
        loops=(lp,),
        faces=(face,),
        shells=(shell,),
        bodies=(body,),
    )


class TestPointTransform:
    def test_identity_point(self) -> None:
        p = _pt("5", "3", "1")
        result = apply_transform_to_point(p, _identity())
        assert result.x.value == Decimal("5")
        assert result.y.value == Decimal("3")
        assert result.z.value == Decimal("1")
        assert result.x.unit is Unit.MM

    def test_translation_point(self) -> None:
        result = apply_transform_to_point(
            _pt("0", "0", "0"),
            _translation("10", "20", "30"),
        )
        assert result.x.value == Decimal("10")
        assert result.y.value == Decimal("20")
        assert result.z.value == Decimal("30")

    def test_rotation_z90(self) -> None:
        result = apply_transform_to_point(_pt("1", "0", "0"), _rotation_z90())
        assert result.x.value == Decimal("0")
        assert result.y.value == Decimal("1")
        assert result.z.value == Decimal("0")

    def test_combined_rotation_and_translation(self) -> None:
        t = Transform3D(
            translation=(Decimal("5"), Decimal("0"), Decimal("0")),
            rotation=_rotation_z90().rotation,
        )
        result = apply_transform_to_point(_pt("1", "0", "0"), t)
        assert result.x.value == Decimal("5")
        assert result.y.value == Decimal("1")
        assert result.z.value == Decimal("0")

    def test_new_object(self) -> None:
        p = _pt("1", "2", "3")
        assert apply_transform_to_point(p, _identity()) is not p

    def test_invalid_point(self) -> None:
        with pytest.raises(ValidationError):
            apply_transform_to_point("bad", _identity())  # type: ignore[arg-type]


class TestVectorTransform:
    def test_rotation(self) -> None:
        result = apply_transform_to_vector(_vec("1", "0", "0"), _rotation_z90())
        assert result.x.value == Decimal("0")
        assert result.y.value == Decimal("1")

    def test_translation_not_applied(self) -> None:
        result = apply_transform_to_vector(
            _vec("1", "0", "0"),
            _translation("100", "100", "100"),
        )
        assert result.x.value == Decimal("1")
        assert result.y.value == Decimal("0")
        assert result.z.value == Decimal("0")

    def test_dimensionless_preserved(self) -> None:
        result = apply_transform_to_vector(_vec("0", "1", "0"), _rotation_z90())
        assert result.x.unit is Unit.DIMENSIONLESS
        assert result.y.unit is Unit.DIMENSIONLESS
        assert result.z.unit is Unit.DIMENSIONLESS


class TestCurveSurfaceGeometryTransform:
    def test_line_origin_translated(self) -> None:
        geo = CanonicalGeometry(
            geometry_id="GEO-001",
            curves=(
                CanonicalCurve(
                    curve_id="C-001",
                    curve_type=CanonicalCurveType.LINE,
                    origin=_pt("0", "0", "0"),
                    direction=_vec("1", "0", "0"),
                ),
            ),
        )
        result = apply_transform_to_geometry(geo, _translation("5", "0", "0"))
        assert result.succeeded
        c = result.output_geometry.get_curve("C-001")
        assert c.origin.x.value == Decimal("5")

    def test_line_direction_rotated(self) -> None:
        geo = CanonicalGeometry(
            geometry_id="GEO-001",
            curves=(
                CanonicalCurve(
                    curve_id="C-001",
                    curve_type=CanonicalCurveType.LINE,
                    direction=_vec("1", "0", "0"),
                ),
            ),
        )
        result = apply_transform_to_geometry(geo, _rotation_z90())
        assert result.succeeded
        c = result.output_geometry.get_curve("C-001")
        assert c.direction.x.value == Decimal("0")
        assert c.direction.y.value == Decimal("1")

    def test_circle_radius_unchanged(self) -> None:
        geo = CanonicalGeometry(
            geometry_id="GEO-001",
            curves=(
                CanonicalCurve(
                    curve_id="C-001",
                    curve_type=CanonicalCurveType.CIRCLE,
                    radius=Quantity.of("25", Unit.MM),
                ),
            ),
        )
        result = apply_transform_to_geometry(geo, _rotation_z90())
        assert result.succeeded
        c = result.output_geometry.get_curve("C-001")
        assert c.radius.value == Decimal("25")
        assert c.radius.unit is Unit.MM

    def test_plane_origin_translated(self) -> None:
        geo = CanonicalGeometry(
            geometry_id="GEO-001",
            surfaces=(
                CanonicalSurface(
                    surface_id="S-001",
                    surface_type=CanonicalSurfaceType.PLANE,
                    origin=_pt("1", "2", "3"),
                    normal=_vec("0", "0", "1"),
                ),
            ),
        )
        result = apply_transform_to_geometry(geo, _translation("10", "0", "0"))
        assert result.succeeded
        s = result.output_geometry.get_surface("S-001")
        assert s.origin.x.value == Decimal("11")

    def test_cylinder_radius_unchanged(self) -> None:
        geo = CanonicalGeometry(
            geometry_id="GEO-001",
            surfaces=(
                CanonicalSurface(
                    surface_id="S-CYL",
                    surface_type=CanonicalSurfaceType.CYLINDER,
                    radius=Quantity.of("5", Unit.MM),
                ),
            ),
        )
        result = apply_transform_to_geometry(geo, _rotation_z90())
        assert result.succeeded
        assert result.output_geometry.get_surface("S-CYL").radius.value == Decimal("5")

    def test_geometry_result_and_id(self) -> None:
        result = apply_transform_to_geometry(_minimal_geo(), _identity())
        assert isinstance(result, GeometryNormalizationResult)
        assert result.succeeded
        assert result.is_lossless
        assert result.output_geometry.geometry_id == "GEO-001"
        assert result.source_geometry_id == "GEO-001"

    def test_deterministic(self) -> None:
        geo = _minimal_geo()
        t = _translation("1", "0", "0")
        r1 = apply_transform_to_geometry(geo, t)
        r2 = apply_transform_to_geometry(geo, t)
        assert r1.source_geometry_id == r2.source_geometry_id
        assert r1.is_lossless == r2.is_lossless


class TestBoundingBox:
    def _geo(self) -> CanonicalGeometry:
        return CanonicalGeometry(
            geometry_id="GEO-001",
            bounding_box=BoundingBox3D(
                min_point=_pt("0", "0", "0"),
                max_point=_pt("10", "10", "10"),
            ),
        )

    def test_translation(self) -> None:
        result = apply_transform_to_geometry(self._geo(), _translation("5", "0", "0"))
        bb = result.output_geometry.bounding_box
        assert bb.min_point.x.value == Decimal("5")
        assert bb.max_point.x.value == Decimal("15")

    def test_rotation_recomputes_aabb(self) -> None:
        result = apply_transform_to_geometry(self._geo(), _rotation_z90())
        bb = result.output_geometry.bounding_box
        assert bb.min_point.x.value <= Decimal("0")
        assert bb.max_point.y.value >= Decimal("0")

    def test_unit_preserved(self) -> None:
        result = apply_transform_to_geometry(self._geo(), _translation("1", "1", "1"))
        assert result.output_geometry.bounding_box.min_point.unit is Unit.MM


class TestTopologyTransform:
    def test_bake_transforms_vertices(self) -> None:
        topo = _minimal_topo()
        result = apply_transform_to_topology(
            topo,
            _translation("5", "0", "0"),
            mode=TransformApplicationMode.BAKE_TRANSFORM,
        )
        assert result.succeeded
        assert (
            result.output_topology.get_vertex("V-001").point.x.value
            == Decimal("5")
        )

    def test_bake_clears_body_transform(self) -> None:
        topo = _minimal_topo()
        result = apply_transform_to_topology(
            topo,
            _identity(),
            mode=TransformApplicationMode.BAKE_TRANSFORM,
        )
        assert result.succeeded
        assert result.output_topology.bodies[0].transform is None

    def test_connectivity_preserved(self) -> None:
        result = apply_transform_to_topology(
            _minimal_topo(),
            _translation("1", "0", "0"),
        )
        edge = result.output_topology.get_edge("E-001")
        assert edge.start_vertex_id == "V-001"
        assert edge.end_vertex_id == "V-002"

    def test_topology_id_preserved(self) -> None:
        result = apply_transform_to_topology(_minimal_topo(), _identity())
        assert result.output_topology.topology_id == "TOPO-001"

    def test_preserve_vertices_unchanged(self) -> None:
        topo = _minimal_topo()
        t = _translation("99", "0", "0")
        result = apply_transform_to_topology(
            topo,
            t,
            mode=TransformApplicationMode.PRESERVE_PLACEMENT,
        )
        assert result.succeeded
        assert result.output_topology.get_vertex("V-001").point.x.value == Decimal("0")

    def test_preserve_records_transform(self) -> None:
        t = _translation("5", "0", "0")
        result = apply_transform_to_topology(
            _minimal_topo(),
            t,
            mode=TransformApplicationMode.PRESERVE_PLACEMENT,
        )
        assert result.succeeded
        assert result.output_topology.bodies[0].transform is not None
        assert result.output_topology.bodies[0].transform.translation[0] == Decimal("5")


class TestUnitNormalization:
    def test_mm_to_m(self) -> None:
        geo = CanonicalGeometry(
            geometry_id="GEO-001",
            curves=(
                CanonicalCurve(
                    curve_id="C-001",
                    curve_type=CanonicalCurveType.LINE,
                    origin=_pt("1000", "0", "0"),
                ),
            ),
        )
        result = normalize_geometry_units(geo, Unit.M)
        assert result.succeeded
        c = result.output_geometry.get_curve("C-001")
        assert c.origin.x.value == Decimal("1")
        assert c.origin.x.unit is Unit.M

    def test_m_to_mm(self) -> None:
        p = CanonicalPoint3D(
            Quantity.of("1", Unit.M),
            Quantity.of("0", Unit.M),
            Quantity.of("0", Unit.M),
        )
        geo = CanonicalGeometry(
            geometry_id="GEO-001",
            curves=(
                CanonicalCurve(
                    curve_id="C-001",
                    curve_type=CanonicalCurveType.LINE,
                    origin=p,
                ),
            ),
        )
        result = normalize_geometry_units(geo, Unit.MM)
        c = result.output_geometry.get_curve("C-001")
        assert c.origin.x.value == Decimal("1000")
        assert c.origin.x.unit is Unit.MM

    def test_same_unit_lossless(self) -> None:
        result = normalize_geometry_units(_minimal_geo(), Unit.MM)
        assert result.succeeded
        assert result.is_lossless

    def test_invalid_target_unit(self) -> None:
        with pytest.raises(ValidationError):
            normalize_geometry_units(_minimal_geo(), Unit.DIMENSIONLESS)

    def test_radius_mm_to_m(self) -> None:
        geo = CanonicalGeometry(
            geometry_id="GEO-001",
            curves=(
                CanonicalCurve(
                    curve_id="C-CIRCLE",
                    curve_type=CanonicalCurveType.CIRCLE,
                    radius=Quantity.of("500", Unit.MM),
                ),
            ),
        )
        result = normalize_geometry_units(geo, Unit.M)
        c = result.output_geometry.get_curve("C-CIRCLE")
        assert c.radius.value == Decimal("500") / Decimal("1000")
        assert c.radius.unit is Unit.M


class TestFailureCases:
    def test_bad_transform_in_point(self) -> None:
        with pytest.raises(ValidationError):
            apply_transform_to_point(_pt("0", "0", "0"), None)  # type: ignore[arg-type]

    def test_bad_vector(self) -> None:
        with pytest.raises(ValidationError):
            apply_transform_to_vector(None, _identity())  # type: ignore[arg-type]

    def test_bad_geometry(self) -> None:
        with pytest.raises(ValidationError):
            apply_transform_to_geometry(None, _identity())  # type: ignore[arg-type]

    def test_bad_topology(self) -> None:
        with pytest.raises(ValidationError):
            apply_transform_to_topology(None, _identity())  # type: ignore[arg-type]

    def test_invalid_mode(self) -> None:
        with pytest.raises(ValidationError):
            apply_transform_to_topology(
                _minimal_topo(),
                _identity(),
                mode="INVALID",  # type: ignore[arg-type]
            )


class TestStage4Regression:
    def test_normalization_module_imports(self) -> None:
        import backend.interoperability.normalization  # noqa: F401

    def test_no_stale_exact_identifiers(self) -> None:
        import ast
        import inspect

        import backend.interoperability.normalization as mod

        src = inspect.getsource(mod)
        tree = ast.parse(src)
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        stale = {
            "CurveType",
            "SurfaceType",
            "TopologyOrientation",
            "ShellClosureStatus",
            "NEUTRAL_GEOMETRY",
            "GeometryLengthUnit",
        }
        assert not (names & stale), f"Stale exact identifiers found: {names & stale}"

    def test_format_family_neutral_exchange(self) -> None:
        from backend.interoperability.enums import FormatFamily

        assert hasattr(FormatFamily, "NEUTRAL_EXCHANGE")
        assert not hasattr(FormatFamily, "NEUTRAL_GEOMETRY")

    def test_population_module_intact(self) -> None:
        from backend.interoperability.population import (  # noqa: F401
            CanonicalPopulationBridge,
            check_eligibility,
        )

    def test_orchestrator_intact(self) -> None:
        from backend.interoperability.orchestrator import (  # noqa: F401
            CadImportOrchestrator,
        )
