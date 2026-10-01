"""Stage 4B: canonical geometry model tests for the interoperability layer."""

from __future__ import annotations

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
    GeometryContainerError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mm(value: int | float | str) -> Quantity:
    return Quantity.of(value, unit=Unit.MM)

def _point(x=0, y=0, z=0, *, point_id=None, source_entity_ref=None) -> CanonicalPoint3D:
    return CanonicalPoint3D(
        _mm(x),
        _mm(y),
        _mm(z),
        point_id=point_id,
        source_entity_ref=source_entity_ref,
    )

def _vec(x=0, y=0, z=0) -> CanonicalVector3D:
    return CanonicalVector3D(x, y, z)  # dimensionless

# ---------------------------------------------------------------------------
# A. CanonicalPoint3D
# ---------------------------------------------------------------------------

class TestCanonicalPoint3D:
    def test_minimal_valid(self) -> None:
        p = _point(1, 2, 3)
        assert p.x.value == 1
        assert p.y.value == 2
        assert p.z.value == 3
        assert p.unit is Unit.MM

    def test_meter_unit(self) -> None:
        p = CanonicalPoint3D(
            Quantity.of("1.0", Unit.M),
            Quantity.of("2.0", Unit.M),
            Quantity.of("3.0", Unit.M),
        )
        assert p.unit is Unit.M
        assert p.x.value == 1

    def test_mixed_length_units_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalPoint3D(_mm(1), Quantity.of("2", Unit.M), _mm(3))

    def test_non_length_unit_rejected(self) -> None:
        bad = Quantity.of(1, Unit.RPM)
        with pytest.raises(ValidationError):
            CanonicalPoint3D(bad, _mm(0), _mm(0))

    def test_bool_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalPoint3D(True, _mm(0), _mm(0))

    def test_nan_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalPoint3D(_mm("NaN"), _mm(0), _mm(0))

    def test_infinity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalPoint3D(_mm("Infinity"), _mm(0), _mm(0))

    def test_string_decimal_accepted(self) -> None:
        p = _point("1.5", "2.25", "3.125")
        assert p.x.value == 1.5
        assert p.z.value == 3.125

    def test_immutable(self) -> None:
        p = _point(1, 2, 3)
        with pytest.raises((AttributeError, TypeError)):
            p.x = _mm(99)  # type: ignore[misc]

    def test_metadata_immutable(self) -> None:
        p = _point(1, 2, 3, source_entity_ref="X")
        # MappingProxyType
        with pytest.raises(TypeError):
            p.metadata["x"] = 1  # type: ignore[index]

    def test_empty_source_entity_ref_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _point(1, 2, 3, source_entity_ref="")

    def test_as_dict_keys(self) -> None:
        d = _point(1, 2, 3, point_id="P1").as_dict()
        assert d["point_id"] == "P1"
        # Quantity components are serialized to their exact Decimal string.
        assert d["x"] == "1"
        assert d["y"] == "2"
        assert d["z"] == "3"
        assert "x" in d and "y" in d and "z" in d

# ---------------------------------------------------------------------------
# B. CanonicalVector3D
# ---------------------------------------------------------------------------

class TestCanonicalVector3D:
    def test_dimensionless_components(self) -> None:
        v = _vec(1, 2, 3)
        assert v.x.unit is Unit.DIMENSIONLESS
        assert v.is_zero is False

    def test_zero_detection(self) -> None:
        v = _vec(0, 0, 0)
        assert v.is_zero is True

    def test_length_unit_rejected(self) -> None:
        bad = _mm(1)
        with pytest.raises(ValidationError):
            CanonicalVector3D(bad, _mm(0), _mm(0))

    def test_immutable(self) -> None:
        v = _vec(1, 0, 0)
        with pytest.raises((AttributeError, TypeError)):
            v.x = _vec(2, 0, 0).x  # type: ignore[misc]

# ---------------------------------------------------------------------------
# C. BoundingBox3D
# ---------------------------------------------------------------------------

class TestBoundingBox3D:
    def test_normal(self) -> None:
        bb = BoundingBox3D(_point(0, 0, 0), _point(10, 20, 30))
        assert bb.size_x.value == 10
        assert bb.size_y.value == 20
        assert bb.size_z.value == 30
        assert bb.unit is Unit.MM

    def test_zero_extent_allowed(self) -> None:
        p = _point(1, 1, 1)
        bb = BoundingBox3D(p, p)
        assert bb.size_x.value == 0
        assert bb.size_y.value == 0
        assert bb.size_z.value == 0

    def test_min_gt_max_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox3D(_point(1, 0, 0), _point(0, 1, 1))

    def test_mixed_unit_corners_rejected(self) -> None:
        m_pt = CanonicalPoint3D(
            Quantity.of(0, Unit.M), Quantity.of(0, Unit.M), Quantity.of(0, Unit.M)
        )
        with pytest.raises(ValidationError):
            BoundingBox3D(m_pt, _point(0, 0, 0))

    def test_immutable(self) -> None:
        bb = BoundingBox3D(_point(0, 0, 0), _point(1, 1, 1))
        with pytest.raises((AttributeError, TypeError)):
            bb.bbox_id = "MUTATED"  # type: ignore[misc]

    def test_repeatability(self) -> None:
        bb1 = BoundingBox3D(_point(0, 0, 0), _point(1, 2, 3))
        bb2 = BoundingBox3D(_point(0, 0, 0), _point(1, 2, 3))
        assert bb1 == bb2
        assert bb1.as_dict() == bb2.as_dict()

# ---------------------------------------------------------------------------
# D. CanonicalCurve
# ---------------------------------------------------------------------------

class TestCanonicalCurve:
    def test_line_minimal(self) -> None:
        c = CanonicalCurve("C1", CanonicalCurveType.LINE)
        assert c.curve_type is CanonicalCurveType.LINE
        assert c.curve_id == "C1"
        assert c.radius is None

    def test_circle_with_radius(self) -> None:
        c = CanonicalCurve(
            "C2",
            CanonicalCurveType.CIRCLE,
            center=_point(1, 2, 3),
            radius=_mm(10),
        )
        assert c.radius is not None
        assert c.radius.value == 10

    def test_radius_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalCurve("C3", CanonicalCurveType.CIRCLE, radius=_mm(0))

    def test_ellipse_major_minor(self) -> None:
        c = CanonicalCurve(
            "C4",
            CanonicalCurveType.ELLIPSE,
            center=_point(0, 0, 0),
            major_radius=_mm(20),
            minor_radius=_mm(10),
        )
        assert c.major_radius is not None
        assert c.minor_radius is not None

    def test_nurbs_knots_and_weights(self) -> None:
        c = CanonicalCurve(
            "C5",
            CanonicalCurveType.NURBS,
            degree=3,
            knots=(0, 0, 0, 0, 1, 1, 1, 1),
            weights=(1, 1, 1, 1),
        )
        assert len(c.knots) == 8
        assert len(c.weights) == 4

    def test_degree_must_be_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalCurve("C6", CanonicalCurveType.BSPLINE, degree=-1)

    def test_degree_bool_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalCurve("C7", CanonicalCurveType.BSPLINE, degree=True)  # type: ignore[arg-type]

    def test_control_points_must_be_points(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalCurve(
                "C8",
                CanonicalCurveType.BSPLINE,
                control_points=("not", "a", "point"),  # type: ignore[arg-type]
            )

    def test_empty_curve_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalCurve("", CanonicalCurveType.LINE)

    def test_invalid_curve_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalCurve("X", "NOT_A_TYPE")  # type: ignore[arg-type]

    def test_immutable(self) -> None:
        c = CanonicalCurve("C9", CanonicalCurveType.LINE)
        with pytest.raises((AttributeError, TypeError)):
            c.curve_type = CanonicalCurveType.CIRCLE  # type: ignore[misc]

    def test_deterministic_serialization(self) -> None:
        c1 = CanonicalCurve("C10", CanonicalCurveType.LINE, origin=_point(1, 2, 3))
        c2 = CanonicalCurve("C10", CanonicalCurveType.LINE, origin=_point(1, 2, 3))
        assert c1.as_dict() == c2.as_dict()

# ---------------------------------------------------------------------------
# E. CanonicalSurface
# ---------------------------------------------------------------------------

class TestCanonicalSurface:
    def test_plane_minimal(self) -> None:
        s = CanonicalSurface("S1", CanonicalSurfaceType.PLANE)
        assert s.surface_type is CanonicalSurfaceType.PLANE

    def test_cylinder_with_radius(self) -> None:
        s = CanonicalSurface(
            "S2",
            CanonicalSurfaceType.CYLINDER,
            origin=_point(0, 0, 0),
            radius=_mm(15),
        )
        assert s.radius is not None
        assert s.radius.value == 15

    def test_cone_with_semi_angle(self) -> None:
        s = CanonicalSurface(
            "S3",
            CanonicalSurfaceType.CONE,
            origin=_point(0, 0, 0),
            semi_angle=0.5,
        )
        assert s.semi_angle is not None
        assert s.semi_angle.unit is Unit.DIMENSIONLESS

    def test_torus_with_two_radii(self) -> None:
        s = CanonicalSurface(
            "S4",
            CanonicalSurfaceType.TORUS,
            center=_point(0, 0, 0),
            major_radius=_mm(100),
            minor_radius=_mm(20),
        )
        assert s.major_radius is not None
        assert s.minor_radius is not None

    def test_sphere_radius_positive(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalSurface(
                "S5", CanonicalSurfaceType.SPHERE, radius=_mm(-1)
            )

    def test_empty_surface_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalSurface("", CanonicalSurfaceType.PLANE)

    def test_immutable(self) -> None:
        s = CanonicalSurface("S6", CanonicalSurfaceType.PLANE)
        with pytest.raises((AttributeError, TypeError)):
            s.surface_type = CanonicalSurfaceType.CYLINDER  # type: ignore[misc]

    def test_cylinder_is_NOT_manufacturing_feature(self) -> None:
        """A CYLINDER surface is geometric only.

        No manufacturing classification is implied.
        """
        s = CanonicalSurface(
            "S7",
            CanonicalSurfaceType.CYLINDER,
            origin=_point(0, 0, 0),
            axis=CanonicalVector3D(0, 0, 1),
            radius=_mm(5),
        )
        # The surface is purely geometric.
        assert s.surface_type is CanonicalSurfaceType.CYLINDER
        # No manufacturing-related attribute exists on CanonicalSurface.
        assert not hasattr(s, "manufacturing_class")
        assert not hasattr(s, "is_hole")
        assert not hasattr(s, "is_bore")
        assert not hasattr(s, "is_boss")

# ---------------------------------------------------------------------------
# F. CanonicalGeometry container
# ---------------------------------------------------------------------------

class TestCanonicalGeometry:
    def test_empty_container(self) -> None:
        g = CanonicalGeometry("G1")
        assert g.ordered_curves == ()
        assert g.ordered_surfaces == ()

    def test_duplicate_curve_id_rejected(self) -> None:
        c1 = CanonicalCurve("C1", CanonicalCurveType.LINE)
        c2 = CanonicalCurve("C1", CanonicalCurveType.CIRCLE)
        with pytest.raises(ValidationError):
            CanonicalGeometry("G1", curves=(c1, c2))

    def test_duplicate_surface_id_rejected(self) -> None:
        s1 = CanonicalSurface("S1", CanonicalSurfaceType.PLANE)
        s2 = CanonicalSurface("S1", CanonicalSurfaceType.PLANE)
        with pytest.raises(ValidationError):
            CanonicalGeometry("G1", surfaces=(s1, s2))

    def test_lookup_helpers(self) -> None:
        c = CanonicalCurve("C1", CanonicalCurveType.LINE)
        s = CanonicalSurface("S1", CanonicalSurfaceType.PLANE)
        g = CanonicalGeometry("G1", curves=(c,), surfaces=(s,))
        assert g.get_curve("C1") is c
        assert g.get_surface("S1") is s
        assert g.has_curve("C1") is True
        assert g.has_surface("S1") is True

    def test_missing_lookup_raises(self) -> None:
        g = CanonicalGeometry("G1")
        with pytest.raises(GeometryContainerError):
            g.get_curve("nope")
        with pytest.raises(GeometryContainerError):
            g.get_surface("nope")

    def test_ordered_iteration_is_sorted(self) -> None:
        c_b = CanonicalCurve("C-B", CanonicalCurveType.LINE)
        c_a = CanonicalCurve("C-A", CanonicalCurveType.LINE)
        g = CanonicalGeometry("G1", curves=(c_b, c_a))
        ids = [c.curve_id for c in g.ordered_curves]
        assert ids == ["C-A", "C-B"]

    def test_bounding_box_attach(self) -> None:
        bb = BoundingBox3D(_point(0, 0, 0), _point(10, 10, 10))
        g = CanonicalGeometry("G1", bounding_box=bb)
        assert g.bounding_box is bb

    def test_invalid_bounding_box_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalGeometry("G1", bounding_box="not a bbox")  # type: ignore[arg-type]

    def test_invalid_curve_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalGeometry("G1", curves=("not a curve",))  # type: ignore[arg-type]

    def test_invalid_surface_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalGeometry("G1", surfaces=("not a surface",))  # type: ignore[arg-type]

    def test_empty_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalGeometry("")

    def test_immutable(self) -> None:
        g = CanonicalGeometry("G1")
        with pytest.raises((AttributeError, TypeError)):
            g.geometry_id = "MUTATED"  # type: ignore[misc]

    def test_as_dict_deterministic(self) -> None:
        c = CanonicalCurve("C1", CanonicalCurveType.LINE)
        g1 = CanonicalGeometry("G1", curves=(c,))
        g2 = CanonicalGeometry("G1", curves=(c,))
        assert g1.as_dict() == g2.as_dict()

# ---------------------------------------------------------------------------
# G. Cylindrical surface example (synthetic)
# ---------------------------------------------------------------------------

class TestCylinderExample:
    def test_cylinder_surface_with_axis_and_radius(self) -> None:
        s = CanonicalSurface(
            "cyl_001",
            CanonicalSurfaceType.CYLINDER,
            origin=_point(0, 0, 0),
            axis=CanonicalVector3D(0, 0, 1),
            radius=_mm(25),
        )
        assert s.surface_type is CanonicalSurfaceType.CYLINDER
        assert s.radius is not None
        assert s.radius.value == 25
        assert s.axis is not None
        # Geometry is purely geometric; no manufacturing semantics attached.
        assert not hasattr(s, "manufacturing_role")
