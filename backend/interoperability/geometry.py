"""Vendor-neutral canonical geometry model (Stage 4B).

Establishes the deterministic, immutable, vendor-neutral geometric
descriptors that future format adapters (STEP, IGES, Parasolid, ACIS,
native CAD, DXF, STL, etc.) will populate.

Stage 4B provides DATA MODELS + VALIDATION only.  No parsing, no kernel,
no tessellation, no Boolean operations, no feature recognition.

Architecture position
---------------------

    SOURCE FORMAT
        ↓
    FORMAT ADAPTER / PARSER (Stage 4C+)
        ↓
    CANONICAL ENGINEERING REPRESENTATION (CER)   ← Stage 4A
        ↓
    CANONICAL GEOMETRY / TOPOLOGY                ← this module (geometry)
        ↓
    CANONICAL TOPOLOGY                           (sibling module: topology)
        ↓
    SEMANTIC NORMALIZATION (Stage 4D+)
        ↓
    MANUFACTURING FEATURE RECOGNITION (Stage 4D+)
        ↓
    MachineryPro domain Feature
        ↓
    DFM / Process Planning / CAM / Validation

Separation of geometry and topology
-----------------------------------

* GEOMETRY  : mathematical shape description (this module).
* TOPOLOGY  : connectivity / adjacency / containment (sibling topology module).

Geometry does not know about adjacency.  Topology references geometry via
stable IDs but does not embed full geometric objects.  This separation
is enforced at construction time.

Units
-----

Every coordinate carries an explicit ``Quantity`` (Decimal value + Unit).
There is NO silent mm/inch assumption.  Two coordinates are equal only
when both value and unit are identical.

Direction vectors are dimensionless (``Unit.DIMENSIONLESS``) to keep
direction and position semantically distinct.

Determinism
-----------

* All models are ``@dataclass(frozen=True, slots=True)``.
* Iterables are normalized to tuples.
* Iteration order over a collection is by canonical ID.
* NaN / Infinity / bool as numeric values are rejected.

Non-goals
---------

* No curve / surface evaluation.
* No tessellation / mesh generation.
* No Boolean / intersection / healing.
* No manufacturing-feature classification (Stage 4D).
* No format-specific fields.
* No hidden geometric tolerance.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

from backend.domain.base import (
    entity_as_dict,
    optional_non_empty_str,
    require_non_empty_str,
)
from backend.domain.exceptions import ValidationError
from backend.domain.units import Numeric, Quantity, Unit, _to_decimal

__all__ = [
    "BoundingBox3D",
    "CanonicalCurve",
    "CanonicalCurveType",
    "CanonicalGeometry",
    "CanonicalPoint3D",
    "CanonicalSurface",
    "CanonicalSurfaceType",
    "CanonicalVector3D",
    "GeometryContainerError",
]


class GeometryContainerError(ValidationError):
    """Raised for structural failures inside canonical geometry containers."""


def _require_finite_decimal(value: Numeric, field_name: str) -> Decimal:
    converted = _to_decimal(value, field_name)
    if not converted.is_finite():
        raise ValidationError(
            f"{field_name} must be finite, got {converted}"
        )
    return converted


def _normalize_length_quantity(
    value: Numeric | Quantity, field_name: str
) -> Quantity:
    if isinstance(value, Quantity):
        if value.unit not in (Unit.MM, Unit.M):
            raise ValidationError(
                f"{field_name} must be a length quantity (MM or M), got unit {value.unit!r}"
            )
        return value
    return Quantity(value=_require_finite_decimal(value, field_name), unit=Unit.MM)


def _normalize_dimensionless_quantity(
    value: Numeric | Quantity, field_name: str
) -> Quantity:
    if isinstance(value, Quantity):
        if value.unit is not Unit.DIMENSIONLESS:
            raise ValidationError(
                f"{field_name} must be a dimensionless Quantity "
                f"({Unit.DIMENSIONLESS!r}), got unit {value.unit!r}"
            )
        return value
    return Quantity(
        value=_require_finite_decimal(value, field_name),
        unit=Unit.DIMENSIONLESS,
    )


def _normalize_decimal_tuple(
    values: Iterable[Numeric], field_name: str
) -> tuple[Decimal, ...]:
    out: list[Decimal] = []
    for i, v in enumerate(values):
        out.append(_require_finite_decimal(v, f"{field_name}[{i}]"))
    return tuple(out)


def _empty_mappingproxy() -> MappingProxyType:
    return MappingProxyType({})


def _normalize_immutable_mapping(
    mapping: Mapping[str, object] | None,
) -> MappingProxyType:
    if mapping is None:
        return MappingProxyType({})
    if not isinstance(mapping, Mapping):
        raise ValidationError("metadata must be a mapping or None")
    return MappingProxyType(dict(mapping))


def _require_unique_ids(
    items: Iterable[object],
    id_attr: str,
    field_name: str,
) -> None:
    seen: set[object] = set()
    for item in items:
        if not hasattr(item, id_attr):
            raise ValidationError(
                f"{field_name}: item lacks identifier attribute {id_attr!r}"
            )
        key = getattr(item, id_attr)
        if key in seen:
            raise ValidationError(
                f"{field_name}: duplicate identifier {key!r}"
            )
        seen.add(key)


def _normalize_optional_point(
    value, field_name: str
):
    if value is None:
        return None
    if not isinstance(value, CanonicalPoint3D):
        raise ValidationError(f"{field_name} must be a CanonicalPoint3D or None")
    return value


def _normalize_optional_vector(
    value, field_name: str
):
    if value is None:
        return None
    if not isinstance(value, CanonicalVector3D):
        raise ValidationError(
            f"{field_name} must be a CanonicalVector3D or None"
        )
    return value


@dataclass(frozen=True, slots=True)
class CanonicalPoint3D:
    """An immutable 3D point with explicit length-units on every coordinate.

    A point is a *position*, never a direction or displacement.  All three
    coordinates carry the same canonical length Unit (MM or M); mixing
    length units across coordinates is rejected at construction.
    """

    x: Quantity
    y: Quantity
    z: Quantity
    point_id: str | None = None
    source_entity_ref: str | None = None
    metadata: MappingProxyType = field(default_factory=_empty_mappingproxy)

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "x", _normalize_length_quantity(self.x, "x"))
        _set(self, "y", _normalize_length_quantity(self.y, "y"))
        _set(self, "z", _normalize_length_quantity(self.z, "z"))
        if self.x.unit is not self.y.unit or self.y.unit is not self.z.unit:
            raise ValidationError(
                "point coordinates must share a single length unit "
                f"(got x={self.x.unit}, y={self.y.unit}, z={self.z.unit})"
            )
        if self.point_id is not None:
            _set(self, "point_id", require_non_empty_str(self.point_id, "point_id"))
        _set(
            self,
            "source_entity_ref",
            optional_non_empty_str(self.source_entity_ref, "source_entity_ref"),
        )
        _set(self, "metadata", _normalize_immutable_mapping(self.metadata))

    @property
    def unit(self) -> Unit:
        return self.x.unit

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


@dataclass(frozen=True, slots=True)
class CanonicalVector3D:
    """An immutable 3D *directional* vector with dimensionless components.

    Vectors represent orientation or normalized direction.  They are NOT
    positions.  If a displacement is needed, use CanonicalPoint3D
    subtraction and attach a length Unit explicitly.

    All components are dimensionless (Unit.DIMENSIONLESS).
    """

    x: Quantity
    y: Quantity
    z: Quantity
    vector_id: str | None = None
    source_entity_ref: str | None = None
    metadata: MappingProxyType = field(default_factory=_empty_mappingproxy)

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "x", _normalize_dimensionless_quantity(self.x, "x"))
        _set(self, "y", _normalize_dimensionless_quantity(self.y, "y"))
        _set(self, "z", _normalize_dimensionless_quantity(self.z, "z"))
        if self.vector_id is not None:
            _set(self, "vector_id", require_non_empty_str(self.vector_id, "vector_id"))
        _set(
            self,
            "source_entity_ref",
            optional_non_empty_str(self.source_entity_ref, "source_entity_ref"),
        )
        _set(self, "metadata", _normalize_immutable_mapping(self.metadata))

    @property
    def is_zero(self) -> bool:
        return (
            self.x.value == 0
            and self.y.value == 0
            and self.z.value == 0
        )

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


@dataclass(frozen=True, slots=True)
class BoundingBox3D:
    """Deterministic axis-aligned bounding box.

    Validation
    ----------
    * Coordinates must share a single length unit.
    * min_x <= max_x, min_y <= max_y, min_z <= max_z.

    No oriented bounding box in Stage 4B.
    """

    min_point: CanonicalPoint3D
    max_point: CanonicalPoint3D
    bbox_id: str | None = None
    source_entity_ref: str | None = None
    metadata: MappingProxyType = field(default_factory=_empty_mappingproxy)

    def __post_init__(self) -> None:
        if not isinstance(self.min_point, CanonicalPoint3D):
            raise ValidationError("min_point must be a CanonicalPoint3D")
        if not isinstance(self.max_point, CanonicalPoint3D):
            raise ValidationError("max_point must be a CanonicalPoint3D")
        if self.min_point.unit is not self.max_point.unit:
            raise ValidationError(
                "bounding box corners must share a single length unit "
                f"(got min={self.min_point.unit}, max={self.max_point.unit})"
            )
        if self.min_point.x.value > self.max_point.x.value:
            raise ValidationError(
                "bounding box min_x must be <= max_x "
                f"(got {self.min_point.x.value} > {self.max_point.x.value})"
            )
        if self.min_point.y.value > self.max_point.y.value:
            raise ValidationError(
                "bounding box min_y must be <= max_y "
                f"(got {self.min_point.y.value} > {self.max_point.y.value})"
            )
        if self.min_point.z.value > self.max_point.z.value:
            raise ValidationError(
                "bounding box min_z must be <= max_z "
                f"(got {self.min_point.z.value} > {self.max_point.z.value})"
            )
        _set = object.__setattr__
        if self.bbox_id is not None:
            _set(self, "bbox_id", require_non_empty_str(self.bbox_id, "bbox_id"))
        _set(
            self,
            "source_entity_ref",
            optional_non_empty_str(self.source_entity_ref, "source_entity_ref"),
        )
        _set(self, "metadata", _normalize_immutable_mapping(self.metadata))

    @property
    def unit(self) -> Unit:
        return self.min_point.unit

    @property
    def size_x(self) -> Quantity:
        return Quantity(
            value=self.max_point.x.value - self.min_point.x.value,
            unit=self.unit,
        )

    @property
    def size_y(self) -> Quantity:
        return Quantity(
            value=self.max_point.y.value - self.min_point.y.value,
            unit=self.unit,
        )

    @property
    def size_z(self) -> Quantity:
        return Quantity(
            value=self.max_point.z.value - self.min_point.z.value,
            unit=self.unit,
        )

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


class CanonicalCurveType(StrEnum):
    """Vendor-neutral canonical curve classification.

    Members are stable strings; do not rename without a schema migration.
    """

    LINE = "LINE"
    CIRCLE = "CIRCLE"
    ELLIPSE = "ELLIPSE"
    ARC = "ARC"
    BSPLINE = "BSPLINE"
    NURBS = "NURBS"
    POLYLINE = "POLYLINE"
    UNKNOWN = "UNKNOWN"


class CanonicalSurfaceType(StrEnum):
    """Vendor-neutral canonical surface classification.

    Members are stable strings; do not rename without a schema migration.
    """

    PLANE = "PLANE"
    CYLINDER = "CYLINDER"
    CONE = "CONE"
    SPHERE = "SPHERE"
    TORUS = "TORUS"
    NURBS = "NURBS"
    BSPLINE = "BSPLINE"
    REVOLUTION = "REVOLUTION"
    EXTRUSION = "EXTRUSION"
    OFFSET = "OFFSET"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class CanonicalCurve:
    """An immutable canonical curve descriptor.

    Stage 4B does not evaluate curves.  Geometry descriptions are stored
    as canonical data; future adapters populate this descriptor and
    future evaluators (Stage 4C+) may consume it.

    Primitive-specific optional data:

    * ``origin`` / ``direction`` for LINE.
    * ``center`` / ``axis`` / ``radius`` for CIRCLE / ARC.
    * ``center`` / ``major_radius`` / ``minor_radius`` / ``axis`` for ELLIPSE.
    * ``degree`` / ``control_points`` / ``knots`` / ``weights`` for
      BSPLINE / NURBS.
    """

    curve_id: str
    curve_type: CanonicalCurveType
    source_entity_ref: str | None = None
    origin: CanonicalPoint3D | None = None
    direction: CanonicalVector3D | None = None
    center: CanonicalPoint3D | None = None
    axis: CanonicalVector3D | None = None
    radius: Quantity | None = None
    major_radius: Quantity | None = None
    minor_radius: Quantity | None = None
    degree: int | None = None
    control_points: tuple[CanonicalPoint3D, ...] = ()
    knots: tuple[Decimal, ...] = ()
    weights: tuple[Decimal, ...] = ()
    metadata: MappingProxyType = field(default_factory=_empty_mappingproxy)

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "curve_id", require_non_empty_str(self.curve_id, "curve_id"))
        if not isinstance(self.curve_type, CanonicalCurveType):
            raise ValidationError(
                f"curve_type must be a CanonicalCurveType, got {self.curve_type!r}"
            )
        _set(
            self,
            "source_entity_ref",
            optional_non_empty_str(self.source_entity_ref, "source_entity_ref"),
        )
        _set(self, "origin", _normalize_optional_point(self.origin, "origin"))
        _set(self, "direction", _normalize_optional_vector(self.direction, "direction"))
        _set(self, "center", _normalize_optional_point(self.center, "center"))
        _set(self, "axis", _normalize_optional_vector(self.axis, "axis"))
        if self.radius is not None:
            _set(self, "radius", _normalize_length_quantity(self.radius, "radius"))
            if self.radius.value <= 0:
                raise ValidationError("radius must be strictly positive when known")
        if self.major_radius is not None:
            _set(
                self,
                "major_radius",
                _normalize_length_quantity(self.major_radius, "major_radius"),
            )
            if self.major_radius.value <= 0:
                raise ValidationError(
                    "major_radius must be strictly positive when known"
                )
        if self.minor_radius is not None:
            _set(
                self,
                "minor_radius",
                _normalize_length_quantity(self.minor_radius, "minor_radius"),
            )
            if self.minor_radius.value <= 0:
                raise ValidationError(
                    "minor_radius must be strictly positive when known"
                )
        if self.degree is not None:
            if isinstance(self.degree, bool) or not isinstance(self.degree, int):
                raise ValidationError("degree must be an integer or None")
            if self.degree < 0:
                raise ValidationError("degree must be non-negative")
        cps = list(self.control_points)
        for i, cp in enumerate(cps):
            if not isinstance(cp, CanonicalPoint3D):
                raise ValidationError(
                    f"control_points[{i}] must be a CanonicalPoint3D"
                )
        _set(self, "control_points", tuple(cps))
        _set(self, "knots", _normalize_decimal_tuple(self.knots, "knots"))
        _set(self, "weights", _normalize_decimal_tuple(self.weights, "weights"))
        _set(self, "metadata", _normalize_immutable_mapping(self.metadata))

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


@dataclass(frozen=True, slots=True)
class CanonicalSurface:
    """An immutable canonical surface descriptor.

    Stage 4B does not evaluate surfaces.  A CYLINDER here is *not*
    automatically classified as a manufacturing hole, boss, or bore;
    manufacturing semantics belong to Stage 4D.

    Primitive-specific optional data:

    * ``origin`` + ``normal`` for PLANE.
    * ``origin`` + ``axis`` + ``radius`` for CYLINDER.
    * ``origin`` + ``axis`` + ``semi_angle`` for CONE.
    * ``center`` + ``radius`` for SPHERE.
    * ``center`` + ``axis`` + ``major_radius`` + ``minor_radius`` for TORUS.
    * ``degree`` / ``control_points`` / ``knots`` / ``weights`` for
      NURBS / BSPLINE.
    """

    surface_id: str
    surface_type: CanonicalSurfaceType
    source_entity_ref: str | None = None
    origin: CanonicalPoint3D | None = None
    center: CanonicalPoint3D | None = None
    axis: CanonicalVector3D | None = None
    normal: CanonicalVector3D | None = None
    radius: Quantity | None = None
    major_radius: Quantity | None = None
    minor_radius: Quantity | None = None
    semi_angle: Quantity | None = None
    degree: int | None = None
    control_points: tuple[CanonicalPoint3D, ...] = ()
    knots: tuple[Decimal, ...] = ()
    weights: tuple[Decimal, ...] = ()
    metadata: MappingProxyType = field(default_factory=_empty_mappingproxy)

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "surface_id", require_non_empty_str(self.surface_id, "surface_id"))
        if not isinstance(self.surface_type, CanonicalSurfaceType):
            raise ValidationError(
                f"surface_type must be a CanonicalSurfaceType, "
                f"got {self.surface_type!r}"
            )
        _set(
            self,
            "source_entity_ref",
            optional_non_empty_str(self.source_entity_ref, "source_entity_ref"),
        )
        _set(self, "origin", _normalize_optional_point(self.origin, "origin"))
        _set(self, "center", _normalize_optional_point(self.center, "center"))
        _set(self, "axis", _normalize_optional_vector(self.axis, "axis"))
        _set(self, "normal", _normalize_optional_vector(self.normal, "normal"))
        if self.radius is not None:
            _set(self, "radius", _normalize_length_quantity(self.radius, "radius"))
            if self.radius.value <= 0:
                raise ValidationError("radius must be strictly positive when known")
        if self.major_radius is not None:
            _set(
                self,
                "major_radius",
                _normalize_length_quantity(self.major_radius, "major_radius"),
            )
            if self.major_radius.value <= 0:
                raise ValidationError(
                    "major_radius must be strictly positive when known"
                )
        if self.minor_radius is not None:
            _set(
                self,
                "minor_radius",
                _normalize_length_quantity(self.minor_radius, "minor_radius"),
            )
            if self.minor_radius.value <= 0:
                raise ValidationError(
                    "minor_radius must be strictly positive when known"
                )
        if self.semi_angle is not None:
            _set(
                self,
                "semi_angle",
                _normalize_dimensionless_quantity(self.semi_angle, "semi_angle"),
            )
            if self.semi_angle.value < 0:
                raise ValidationError("semi_angle must be non-negative when known")
        if self.degree is not None:
            if isinstance(self.degree, bool) or not isinstance(self.degree, int):
                raise ValidationError("degree must be an integer or None")
            if self.degree < 0:
                raise ValidationError("degree must be non-negative")
        cps = list(self.control_points)
        for i, cp in enumerate(cps):
            if not isinstance(cp, CanonicalPoint3D):
                raise ValidationError(
                    f"control_points[{i}] must be a CanonicalPoint3D"
                )
        _set(self, "control_points", tuple(cps))
        _set(self, "knots", _normalize_decimal_tuple(self.knots, "knots"))
        _set(self, "weights", _normalize_decimal_tuple(self.weights, "weights"))
        _set(self, "metadata", _normalize_immutable_mapping(self.metadata))

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


@dataclass(frozen=True, slots=True)
class CanonicalGeometry:
    """Container for canonical curves and surfaces of a document.

    Determinism
    -----------
    * Iteration over curves / surfaces returns them sorted by ID.
    * Duplicate curve_id / surface_id are rejected at construction.
    * This container is immutable; it never auto-repairs or auto-classifies.

    Geometry and topology are kept separate.  Curves/surfaces here have
    no adjacency information.
    """

    geometry_id: str
    curves: tuple[CanonicalCurve, ...] = ()
    surfaces: tuple[CanonicalSurface, ...] = ()
    bounding_box: BoundingBox3D | None = None
    source_entity_ref: str | None = None
    metadata: MappingProxyType = field(default_factory=_empty_mappingproxy)

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "geometry_id", require_non_empty_str(self.geometry_id, "geometry_id"))
        curves = list(self.curves)
        for i, c in enumerate(curves):
            if not isinstance(c, CanonicalCurve):
                raise ValidationError(f"curves[{i}] must be a CanonicalCurve")
        _set(self, "curves", tuple(curves))
        surfaces = list(self.surfaces)
        for i, s in enumerate(surfaces):
            if not isinstance(s, CanonicalSurface):
                raise ValidationError(f"surfaces[{i}] must be a CanonicalSurface")
        _set(self, "surfaces", tuple(surfaces))
        _require_unique_ids(self.curves, "curve_id", "curves")
        _require_unique_ids(self.surfaces, "surface_id", "surfaces")
        if self.bounding_box is not None and not isinstance(
            self.bounding_box, BoundingBox3D
        ):
            raise ValidationError("bounding_box must be a BoundingBox3D or None")
        _set(
            self,
            "source_entity_ref",
            optional_non_empty_str(self.source_entity_ref, "source_entity_ref"),
        )
        _set(self, "metadata", _normalize_immutable_mapping(self.metadata))

    @property
    def ordered_curves(self) -> tuple[CanonicalCurve, ...]:
        return tuple(sorted(self.curves, key=lambda c: c.curve_id))

    @property
    def ordered_surfaces(self) -> tuple[CanonicalSurface, ...]:
        return tuple(sorted(self.surfaces, key=lambda s: s.surface_id))

    def get_curve(self, curve_id: str) -> CanonicalCurve:
        for c in self.ordered_curves:
            if c.curve_id == curve_id:
                return c
        raise GeometryContainerError(f"curve_id {curve_id!r} not found")

    def get_surface(self, surface_id: str) -> CanonicalSurface:
        for s in self.ordered_surfaces:
            if s.surface_id == surface_id:
                return s
        raise GeometryContainerError(f"surface_id {surface_id!r} not found")

    def has_curve(self, curve_id: str) -> bool:
        return any(c.curve_id == curve_id for c in self.curves)

    def has_surface(self, surface_id: str) -> bool:
        return any(s.surface_id == surface_id for s in self.surfaces)

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)
