"""Canonical mapping tests for real IGES entity parameters."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.interoperability.geometry import (
    CanonicalCurveType,
    CanonicalSurfaceType,
)
from backend.interoperability.iges_mapping import map_iges_model
from backend.interoperability.iges_parser import parse_iges_bytes
from tests.unit.interoperability.iges_fixtures import EntitySpec, make_iges


def _mapped(*entities: EntitySpec, **global_kwargs):
    return map_iges_model(parse_iges_bytes(make_iges(tuple(entities), **global_kwargs)))


def test_maps_line_from_parameters_with_units_scale_and_transform() -> None:
    result = _mapped(
        EntitySpec(
            110,
            "110,1.25,2.5,3.75,4.25,6.5,8.75;",
            transform_pointer=3,
        ),
        EntitySpec(124, "124,1,0,0,10,0,1,0,-2,0,0,1,0.5;"),
        model_scale="2",
        unit_flag=1,
        unit_name="IN",
        minimum_resolution="0.0002",
    )

    assert result.issues == ()
    assert result.geometry is not None
    curve = result.geometry.curves[0]
    assert curve.curve_type is CanonicalCurveType.LINE
    assert curve.origin.x.value == Decimal("571.50")
    assert curve.origin.y.value == Decimal("25.40")
    assert curve.origin.z.value == Decimal("215.90")
    end_point = curve.metadata["end_point"]
    assert end_point.x.value == Decimal("723.90")
    assert end_point.y.value == Decimal("228.60")
    assert end_point.z.value == Decimal("469.90")
    assert result.geometry.metadata["iges_source_unit"] == "IN"
    assert result.geometry.metadata["iges_minimum_resolution_mm"] == Decimal(
        "0.01016"
    )


def test_maps_circular_arc_and_standalone_point_from_parameters() -> None:
    result = _mapped(
        EntitySpec(100, "100,3,1,2,4,2,1,5;"),
        EntitySpec(116, "116,7.25,-8.5,9.75,0;"),
    )

    assert result.geometry is not None
    arc = result.geometry.curves[0]
    assert arc.curve_type is CanonicalCurveType.ARC
    assert arc.center.x.value == Decimal("1")
    assert arc.center.y.value == Decimal("2")
    assert arc.center.z.value == Decimal("3")
    assert arc.radius.value == Decimal("3")
    assert arc.metadata["start_point"].x.value == Decimal("4")
    assert arc.metadata["end_point"].y.value == Decimal("5")
    point = result.geometry.metadata["standalone_points"][0]
    assert point.x.value == Decimal("7.25")
    assert point.y.value == Decimal("-8.5")
    assert point.z.value == Decimal("9.75")


def test_maps_rational_bspline_curve_without_discarding_parameters() -> None:
    parameters = (
        "126,2,2,1,0,0,0,"
        "0,0,0,1,1,1,"
        "1,0.75,1.25,"
        "0,0,0,2,3,0,5,3,0,"
        "0,1,0,0,1;"
    )
    result = _mapped(EntitySpec(126, parameters))

    assert result.geometry is not None
    curve = result.geometry.curves[0]
    assert curve.curve_type is CanonicalCurveType.NURBS
    assert curve.degree == 2
    assert curve.knots == tuple(map(Decimal, ("0", "0", "0", "1", "1", "1")))
    assert curve.weights == tuple(map(Decimal, ("1", "0.75", "1.25")))
    assert [point.x.value for point in curve.control_points] == [
        Decimal("0"),
        Decimal("2"),
        Decimal("5"),
    ]
    assert curve.metadata["parameter_range"] == (Decimal("0"), Decimal("1"))
    assert curve.metadata["plane_normal"] == (
        Decimal("0"),
        Decimal("0"),
        Decimal("1"),
    )


def test_maps_plane_and_rational_bspline_surface_parameters() -> None:
    bspline_surface = (
        "128,1,1,1,1,0,0,1,0,0,"
        "0,0,1,1,0,0,1,1,"
        "1,1,1,1,"
        "0,0,2,3,0,2,0,4,2,3,4,2,"
        "0,1,0,1;"
    )
    result = _mapped(
        EntitySpec(108, "108,0,0,2,8,0,0,0,4,1;"),
        EntitySpec(128, bspline_surface),
    )

    assert result.geometry is not None
    plane, nurbs = result.geometry.surfaces
    assert plane.surface_type is CanonicalSurfaceType.PLANE
    assert plane.origin.z.value == Decimal("4")
    assert plane.normal.z.value == Decimal("1")
    assert nurbs.surface_type is CanonicalSurfaceType.BSPLINE
    assert nurbs.metadata["u_degree"] == 1
    assert nurbs.metadata["v_degree"] == 1
    assert nurbs.metadata["u_knots"] == (
        Decimal("0"),
        Decimal("0"),
        Decimal("1"),
        Decimal("1"),
    )
    assert nurbs.metadata["v_knots"] == nurbs.metadata["u_knots"]
    assert nurbs.metadata["control_point_grid_shape"] == (2, 2)
    assert nurbs.metadata["u_parameter_range"] == (Decimal("0"), Decimal("1"))
    assert nurbs.metadata["v_parameter_range"] == (Decimal("0"), Decimal("1"))
    assert [point.z.value for point in nurbs.control_points] == [
        Decimal("2"),
        Decimal("2"),
        Decimal("2"),
        Decimal("2"),
    ]


def test_maps_pointer_based_elementary_surfaces() -> None:
    result = _mapped(
        EntitySpec(116, "116,1,2,3,0;"),
        EntitySpec(123, "123,0,0,1;"),
        EntitySpec(123, "123,1,0,0;"),
        EntitySpec(190, "190,1,3,5;", form_number=1),
        EntitySpec(192, "192,1,3,2.5,5;", form_number=1),
        EntitySpec(194, "194,1,3,4.5,30,5;", form_number=1),
        EntitySpec(196, "196,1,6.5,3,5;", form_number=1),
        EntitySpec(198, "198,1,3,7.5,1.5,5;", form_number=1),
    )

    assert result.issues == ()
    assert result.geometry is not None
    surfaces = {surface.surface_type: surface for surface in result.geometry.surfaces}
    assert surfaces[CanonicalSurfaceType.PLANE].origin.x.value == Decimal("1")
    assert surfaces[CanonicalSurfaceType.CYLINDER].radius.value == Decimal("2.5")
    assert surfaces[CanonicalSurfaceType.CONE].radius.value == Decimal("4.5")
    assert surfaces[CanonicalSurfaceType.CONE].semi_angle.value == Decimal("30")
    assert surfaces[CanonicalSurfaceType.SPHERE].radius.value == Decimal("6.5")
    assert surfaces[CanonicalSurfaceType.TORUS].major_radius.value == Decimal("7.5")
    assert surfaces[CanonicalSurfaceType.TORUS].minor_radius.value == Decimal("1.5")
    assert all(surface.axis is None or surface.axis.z.value == 1 for surface in surfaces.values())


def test_non_rigid_transform_cannot_silently_distort_analytic_surface() -> None:
    result = _mapped(
        EntitySpec(116, "116,1,2,3,0;"),
        EntitySpec(124, "124,2,0,0,0,0,2,0,0,0,0,2,0;"),
        EntitySpec(196, "196,1,5;", transform_pointer=3),
    )

    assert result.geometry is None
    assert result.topology is None
    assert any(
        issue.entity_type == 196 and "rigid" in issue.reason.lower()
        for issue in result.issues
    )


def test_singular_transform_fails_closed_before_mapping_geometry() -> None:
    result = _mapped(
        EntitySpec(116, "116,1,2,3,0;", transform_pointer=3),
        EntitySpec(124, "124,0,0,0,0,0,0,0,0,0,0,0,0;"),
    )

    assert result.geometry is None
    assert any(
        issue.entity_type == 124 and "singular" in issue.reason.lower()
        for issue in result.issues
    )

def test_unsupported_entity_form_fails_closed() -> None:
    result = _mapped(EntitySpec(110, "110,0,0,0,1,0,0;", form_number=999))

    assert result.geometry is None
    assert result.topology is None
    assert result.issues[0].entity_type == 110
    assert result.issues[0].form_number == 999
    assert "unsupported form" in result.issues[0].reason.lower()


def test_unsupported_geometry_fails_closed_with_entity_diagnostic() -> None:
    result = _mapped(EntitySpec(118, "118,1,3,0,0;"))

    assert result.geometry is None
    assert result.topology is None
    assert result.issues[0].entity_type == 118
    assert result.issues[0].fatal is True
    assert result.issues[0].affects_topology is True
    assert "unsupported" in result.issues[0].reason.lower()


def test_independent_annotation_degrades_without_discarding_geometry() -> None:
    result = _mapped(
        EntitySpec(110, "110,0,0,0,1,0,0;"),
        EntitySpec(212, "212,0;"),
    )

    assert result.geometry is not None
    assert len(result.geometry.curves) == 1
    assert result.issues[0].entity_type == 212
    assert result.issues[0].fatal is False
    assert result.issues[0].affects_topology is False


@pytest.mark.parametrize(
    "parameters",
    [
        "110,0,0,0,0,0,0;",
        "100,0,0,0,0,0,0,0;",
        "128,1,1,1,1,0,0,1,0,0,0,1;",
    ],
)
def test_invalid_geometry_parameters_fail_closed(parameters: str) -> None:
    entity_type = int(parameters.split(",", 1)[0])
    result = _mapped(EntitySpec(entity_type, parameters))

    assert result.geometry is None
    assert result.issues
    assert result.issues[0].fatal is True


def test_negative_sphere_radius_fails_closed() -> None:
    result = _mapped(
        EntitySpec(116, "116,0,0,0,0;"),
        EntitySpec(196, "196,1,-1;"),
    )

    assert result.geometry is None
    assert result.issues
    assert any(issue.entity_type == 196 and issue.fatal for issue in result.issues)


def _triangle_brep_entities(*, loop_parameters: str | None = None):
    return (
        EntitySpec(108, "108,0,0,1,0,0,0,0,0,1;"),
        EntitySpec(110, "110,0,0,0,2,0,0;"),
        EntitySpec(110, "110,2,0,0,0,2,0;"),
        EntitySpec(110, "110,0,2,0,0,0,0;"),
        EntitySpec(502, "502,3,0,0,0,2,0,0,0,2,0;", form_number=1),
        EntitySpec(
            504,
            "504,3,3,9,1,9,2,5,9,2,9,3,7,9,3,9,1;",
            form_number=1,
        ),
        EntitySpec(
            508,
            loop_parameters
            or "508,3,0,11,1,1,0,0,11,2,1,0,0,11,3,1,0;",
            form_number=1,
        ),
        EntitySpec(510, "510,1,1,1,13;", form_number=1),
        EntitySpec(514, "514,1,15,1;", form_number=1),
        EntitySpec(186, "186,17,1,0;"),
    )


def test_maps_parameter_authored_manifold_brep_topology() -> None:
    result = _mapped(*_triangle_brep_entities())

    assert result.issues == ()
    assert result.geometry is not None
    assert result.topology is not None
    topology = result.topology
    assert len(topology.vertices) == 3
    assert len(topology.edges) == 3
    assert len(topology.loops) == 1
    assert len(topology.faces) == 1
    assert len(topology.shells) == 1
    assert len(topology.bodies) == 1
    assert [vertex.point.x.value for vertex in topology.vertices] == [
        Decimal("0"),
        Decimal("2"),
        Decimal("0"),
    ]
    assert topology.edges[0].start_vertex_id.endswith("-0001")
    assert topology.edges[0].end_vertex_id.endswith("-0002")
    assert topology.loops[0].edge_ids == tuple(edge.edge_id for edge in topology.edges)
    assert topology.faces[0].surface_id == "surface-de-0000001"
    assert topology.shells[0].face_ids == (topology.faces[0].face_id,)
    assert topology.bodies[0].shell_ids == (topology.shells[0].shell_id,)
    assert topology.geometry is result.geometry


def test_preserves_bounded_and_trimmed_surface_relationships() -> None:
    result = _mapped(
        EntitySpec(108, "108,0,0,1,0,0,0,0,0,1;"),
        EntitySpec(110, "110,0,0,0,2,0,0;"),
        EntitySpec(141, "141,1,3,1,1,3,0,1,3;"),
        EntitySpec(142, "142,1,1,3,3,3;"),
        EntitySpec(143, "143,1,1,1,5;"),
        EntitySpec(144, "144,1,1,0,7;"),
    )

    assert result.issues == ()
    assert result.geometry is not None
    bounded = result.geometry.get_surface("surface-de-0000009")
    trimmed = result.geometry.get_surface("surface-de-0000011")
    assert bounded.metadata["base_surface_id"] == "surface-de-0000001"
    assert bounded.metadata["boundary_relationship_ids"] == ("iges-de-0000005",)
    assert trimmed.metadata["base_surface_id"] == "surface-de-0000001"
    assert trimmed.metadata["outer_boundary_relationship_id"] == "iges-de-0000007"


def test_invalid_boundary_entity_cannot_create_a_bounded_surface() -> None:
    result = _mapped(
        EntitySpec(108, "108,0,0,1,0,0,0,0,0,1;"),
        EntitySpec(110, "110,0,0,0,2,0,0;"),
        EntitySpec(141, "141,1,9,1,1,3,0,1,3;"),
        EntitySpec(143, "143,1,1,1,5;"),
    )

    assert result.geometry is not None
    assert [surface.surface_id for surface in result.geometry.surfaces] == [
        "surface-de-0000001"
    ]
    assert result.topology is None
    assert any(
        issue.entity_type == 141 and issue.affects_topology
        for issue in result.issues
    )


def test_trimmed_surface_keeps_natural_outer_slot_before_inner_boundaries() -> None:
    result = _mapped(
        EntitySpec(108, "108,0,0,1,0,0,0,0,0,1;"),
        EntitySpec(110, "110,0,0,0,2,0,0;"),
        EntitySpec(142, "142,1,1,3,3,3;"),
        EntitySpec(144, "144,1,0,1,0,5;"),
    )

    assert result.issues == ()
    assert result.geometry is not None
    trimmed = result.geometry.get_surface("surface-de-0000007")
    assert trimmed.metadata["outer_boundary_relationship_id"] is None
    assert trimmed.metadata["inner_boundary_relationship_ids"] == (
        "iges-de-0000005",
    )


@pytest.mark.parametrize(
    ("boundary", "surface"),
    [
        (EntitySpec(141, "141,1,3,3,1,5,0,1,5;"), EntitySpec(143, "143,1,1,1,7;")),
        (EntitySpec(142, "142,1,3,5,5,3;"), EntitySpec(144, "144,1,1,0,7;")),
    ],
)
def test_boundary_must_reference_the_surface_it_bounds(
    boundary: EntitySpec,
    surface: EntitySpec,
) -> None:
    result = _mapped(
        EntitySpec(108, "108,0,0,1,0,0,0,0,0,1;"),
        EntitySpec(108, "108,0,0,1,1,0,0,0,0,1;"),
        EntitySpec(110, "110,0,0,0,2,0,0;"),
        boundary,
        surface,
    )

    assert result.topology is None
    assert result.geometry is not None
    assert all(item.surface_id != "surface-de-0000009" for item in result.geometry.surfaces)
    assert any(
        "different surface" in issue.reason for issue in result.issues
    ), result.issues
    assert any(
        issue.entity_type == surface.entity_type and issue.affects_topology
        for issue in result.issues
    )


@pytest.mark.parametrize(
    "loop_parameters",
    [
        "508,3,0,11,1,1,0,0,11,1,1,0,0,11,3,1,0;",
        "508,3,1,9,1,1,0,0,11,2,1,0,0,11,3,1,0;",
    ],
)
def test_invalid_brep_dependency_emits_no_partial_topology(
    loop_parameters: str,
) -> None:
    result = _mapped(*_triangle_brep_entities(loop_parameters=loop_parameters))

    assert result.geometry is not None
    assert result.topology is None
    assert result.issues
    assert any(issue.affects_topology for issue in result.issues)
    assert all(issue.fatal is False for issue in result.issues)
