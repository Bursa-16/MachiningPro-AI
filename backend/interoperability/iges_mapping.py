"""Map parsed IGES entities to vendor-neutral canonical geometry/topology."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation, localcontext

from backend.domain.exceptions import ValidationError
from backend.domain.units import Quantity, Unit
from backend.interoperability.geometry import (
    CanonicalCurve,
    CanonicalCurveType,
    CanonicalGeometry,
    CanonicalPoint3D,
    CanonicalSurface,
    CanonicalSurfaceType,
    CanonicalVector3D,
)
from backend.interoperability.iges_parser import (
    IgesEntity,
    IgesGlobalSection,
    IgesModel,
)
from backend.interoperability.models import CanonicalEntityRef
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

__all__ = [
    "IgesMappingIssue",
    "IgesMappingResult",
    "map_iges_model",
]

_GEOMETRY_TYPES = {100, 108, 110, 116, 118, 126, 128, 190, 192, 194, 196, 198}
_AUXILIARY_TYPES = {123, 124}
_BOUNDARY_TYPES = {141, 142, 143, 144}
_TOPOLOGY_TYPES = {186, 502, 504, 508, 510, 514}
_PRESENTATION_TYPES = {
    202,
    206,
    208,
    210,
    212,
    214,
    216,
    218,
    220,
    222,
    228,
    314,
}
_SUPPORTED_FORMS: dict[int, frozenset[int]] = {
    100: frozenset({0}),
    108: frozenset({0}),
    110: frozenset({0}),
    116: frozenset({0}),
    123: frozenset({0}),
    124: frozenset({0}),
    126: frozenset(range(6)),
    128: frozenset(range(10)),
    141: frozenset({0}),
    142: frozenset({0}),
    143: frozenset({0}),
    144: frozenset({0}),
    186: frozenset({0}),
    190: frozenset({0, 1}),
    192: frozenset({0, 1}),
    194: frozenset({0, 1}),
    196: frozenset({0, 1}),
    198: frozenset({0, 1}),
    502: frozenset({1}),
    504: frozenset({1}),
    508: frozenset({0, 1}),
    510: frozenset({1}),
    514: frozenset({1, 2}),
}


class _MappingError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class IgesMappingIssue:
    de_pointer: int
    entity_type: int
    form_number: int
    reason: str
    fatal: bool
    affects_topology: bool


@dataclass(frozen=True, slots=True)
class IgesMappingResult:
    geometry: CanonicalGeometry | None
    topology: CanonicalTopology | None
    entity_refs: tuple[CanonicalEntityRef, ...]
    issues: tuple[IgesMappingIssue, ...]


_Matrix = tuple[
    tuple[Decimal, Decimal, Decimal, Decimal],
    tuple[Decimal, Decimal, Decimal, Decimal],
    tuple[Decimal, Decimal, Decimal, Decimal],
]
_IDENTITY: _Matrix = (
    (Decimal(1), Decimal(0), Decimal(0), Decimal(0)),
    (Decimal(0), Decimal(1), Decimal(0), Decimal(0)),
    (Decimal(0), Decimal(0), Decimal(1), Decimal(0)),
)


def _de_id(pointer: int) -> str:
    return f"iges-de-{pointer:07d}"


def _curve_id(pointer: int) -> str:
    return f"curve-de-{pointer:07d}"


def _surface_id(pointer: int) -> str:
    return f"surface-de-{pointer:07d}"


def _point_id(pointer: int) -> str:
    return f"point-de-{pointer:07d}"


def _numeric(entity: IgesEntity, index: int, name: str) -> Decimal:
    if index >= len(entity.parameters):
        raise _MappingError(f"missing {name} parameter at index {index}")
    value = entity.parameters[index]
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise _MappingError(f"{name} must be numeric")
    result = Decimal(value)
    if not result.is_finite():
        raise _MappingError(f"{name} must be finite")
    return result


def _integer(entity: IgesEntity, index: int, name: str) -> int:
    value = _numeric(entity, index, name)
    integral = value.to_integral_value()
    if value != integral:
        raise _MappingError(f"{name} must be an integer")
    return int(integral)


def _require_parameter_count(
    entity: IgesEntity, minimum: int, entity_name: str
) -> None:
    if len(entity.parameters) < minimum:
        raise _MappingError(
            f"{entity_name} requires at least {minimum - 1} parameters, "
            f"got {len(entity.parameters) - 1}"
        )


def _scale(global_section: IgesGlobalSection) -> Decimal:
    return global_section.model_scale * global_section.millimetres_per_model_unit


def _length_mm(value: Decimal, global_section: IgesGlobalSection) -> Quantity:
    return Quantity(value=value * _scale(global_section), unit=Unit.MM)


def _point(
    xyz: tuple[Decimal, Decimal, Decimal],
    global_section: IgesGlobalSection,
    *,
    point_id: str | None = None,
    source_entity_ref: str | None = None,
) -> CanonicalPoint3D:
    return CanonicalPoint3D(
        x=_length_mm(xyz[0], global_section),
        y=_length_mm(xyz[1], global_section),
        z=_length_mm(xyz[2], global_section),
        point_id=point_id,
        source_entity_ref=source_entity_ref,
    )


def _vector(xyz: tuple[Decimal, Decimal, Decimal]) -> CanonicalVector3D:
    length_squared = sum(component * component for component in xyz)
    if length_squared <= 0:
        raise _MappingError("direction vector must be non-zero")
    try:
        with localcontext() as context:
            context.prec = 50
            length = length_squared.sqrt()
            normalized = tuple(component / length for component in xyz)
    except InvalidOperation as exc:
        raise _MappingError("direction vector cannot be normalized") from exc
    return CanonicalVector3D(
        x=Quantity(normalized[0], Unit.DIMENSIONLESS),
        y=Quantity(normalized[1], Unit.DIMENSIONLESS),
        z=Quantity(normalized[2], Unit.DIMENSIONLESS),
    )


def _apply_matrix_to_raw_point(
    matrix: _Matrix, xyz: tuple[Decimal, Decimal, Decimal]
) -> tuple[Decimal, Decimal, Decimal]:
    x, y, z = xyz
    return tuple(
        row[0] * x + row[1] * y + row[2] * z + row[3] for row in matrix
    )  # type: ignore[return-value]


def _apply_matrix_to_raw_vector(
    matrix: _Matrix, xyz: tuple[Decimal, Decimal, Decimal]
) -> tuple[Decimal, Decimal, Decimal]:
    x, y, z = xyz
    return tuple(
        row[0] * x + row[1] * y + row[2] * z for row in matrix
    )  # type: ignore[return-value]


def _compose(first: _Matrix, second: _Matrix) -> _Matrix:
    """Return the affine composition ``first(second(point))``."""

    rows: list[tuple[Decimal, Decimal, Decimal, Decimal]] = []
    for row in range(3):
        linear = tuple(
            sum(first[row][k] * second[k][column] for k in range(3))
            for column in range(3)
        )
        translation = (
            sum(first[row][k] * second[k][3] for k in range(3))
            + first[row][3]
        )
        rows.append((linear[0], linear[1], linear[2], translation))
    return (rows[0], rows[1], rows[2])


def _is_rigid(matrix: _Matrix) -> bool:
    tolerance = Decimal("1e-24")
    for first in range(3):
        for second in range(3):
            dot = sum(matrix[row][first] * matrix[row][second] for row in range(3))
            expected = Decimal(1) if first == second else Decimal(0)
            if abs(dot - expected) > tolerance:
                return False
    return True


def _linear_determinant(matrix: _Matrix) -> Decimal:
    return (
        matrix[0][0]
        * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1]
        * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2]
        * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


class _MappingContext:
    def __init__(self, model: IgesModel) -> None:
        self.model = model
        self.transforms: dict[int, _Matrix] = {}
        self.points: dict[int, CanonicalPoint3D] = {}
        self.directions: dict[int, CanonicalVector3D] = {}
        self.curves: dict[int, CanonicalCurve] = {}
        self.surfaces: dict[int, CanonicalSurface] = {}
        self.entity_refs: list[CanonicalEntityRef] = []
        self.issues: list[IgesMappingIssue] = []
        self.geometry: CanonicalGeometry | None = None
        self.topology: CanonicalTopology | None = None
        self.vertex_lists: dict[int, tuple[CanonicalVertex, ...]] = {}
        self.edge_lists: dict[int, tuple[CanonicalEdge, ...]] = {}
        self.loops: dict[int, CanonicalLoop] = {}
        self.faces: dict[int, CanonicalFace] = {}
        self.shells: dict[int, CanonicalShell] = {}
        self.bodies: dict[int, CanonicalBody] = {}
        self.valid_boundary_relationships: set[int] = set()
        self.boundary_surfaces: dict[int, int] = {}
        self.invalid_entities: set[int] = set()

    def _entity(self, pointer: int, expected_types: set[int], name: str) -> IgesEntity:
        entity = self.model.entities_by_pointer.get(pointer)
        if entity is None:
            raise _MappingError(f"{name} references missing DE {pointer}")
        if entity.directory.entity_type not in expected_types:
            raise _MappingError(
                f"{name} DE {pointer} has entity type {entity.directory.entity_type}, "
                f"expected one of {sorted(expected_types)}"
            )
        return entity

    def _parse_transforms(self) -> None:
        for entity in self.model.entities:
            if entity.directory.entity_type != 124:
                continue
            pointer = entity.directory.de_pointer
            if pointer in self.invalid_entities:
                continue
            try:
                _require_parameter_count(entity, 13, "type 124 transformation matrix")
                values = tuple(
                    _numeric(entity, index, f"matrix value {index}")
                    for index in range(1, 13)
                )
                matrix: _Matrix = (
                    (values[0], values[1], values[2], values[3]),
                    (values[4], values[5], values[6], values[7]),
                    (values[8], values[9], values[10], values[11]),
                )
                if _linear_determinant(matrix) == 0:
                    raise _MappingError("type 124 transformation matrix is singular")
                self.transforms[pointer] = matrix
            except (_MappingError, ValidationError, InvalidOperation) as exc:
                self.invalid_entities.add(pointer)
                self._record_issue(
                    entity,
                    f"invalid IGES entity type 124: {exc}",
                    fatal=True,
                    affects_topology=True,
                )

    def _validate_supported_forms(self) -> None:
        for entity in self.model.entities:
            allowed = _SUPPORTED_FORMS.get(entity.directory.entity_type)
            if allowed is None or entity.directory.form_number in allowed:
                continue
            self.invalid_entities.add(entity.directory.de_pointer)
            self._record_issue(
                entity,
                f"unsupported form {entity.directory.form_number} for IGES entity "
                f"type {entity.directory.entity_type}",
                fatal=True,
                affects_topology=True,
            )

    def _require_rigid_entity_transform(self, entity: IgesEntity) -> None:
        if not _is_rigid(self._matrix_for_entity(entity)):
            raise _MappingError(
                f"type {entity.directory.entity_type} analytic surface requires a "
                "rigid transformation"
            )

    def _matrix_for_entity(self, entity: IgesEntity) -> _Matrix:
        pointer = entity.directory.transformation_matrix_pointer
        if not pointer:
            return _IDENTITY
        chain: list[_Matrix] = []
        visited: set[int] = set()
        while pointer:
            if pointer in visited:
                raise _MappingError(f"cyclic transformation reference at DE {pointer}")
            visited.add(pointer)
            transform_entity = self._entity(pointer, {124}, "transformation")
            matrix = self.transforms.get(pointer)
            if matrix is None:
                raise _MappingError(f"transformation DE {pointer} was not decoded")
            chain.append(matrix)
            pointer = transform_entity.directory.transformation_matrix_pointer
        result = _IDENTITY
        for matrix in chain:
            result = _compose(matrix, result)
        return result

    def _source_xyz(self, point: CanonicalPoint3D) -> tuple[Decimal, Decimal, Decimal]:
        scale = _scale(self.model.global_section)
        return (
            point.x.value / scale,
            point.y.value / scale,
            point.z.value / scale,
        )

    def _apply_point_transform(
        self, point: CanonicalPoint3D, entity: IgesEntity
    ) -> CanonicalPoint3D:
        matrix = self._matrix_for_entity(entity)
        if matrix == _IDENTITY:
            return point
        raw = _apply_matrix_to_raw_point(matrix, self._source_xyz(point))
        return _point(
            raw,
            self.model.global_section,
            source_entity_ref=_de_id(entity.directory.de_pointer),
        )

    def _apply_vector_transform(
        self, vector: CanonicalVector3D, entity: IgesEntity
    ) -> CanonicalVector3D:
        matrix = self._matrix_for_entity(entity)
        raw = (vector.x.value, vector.y.value, vector.z.value)
        return _vector(_apply_matrix_to_raw_vector(matrix, raw))

    def _map_point_116(self, entity: IgesEntity) -> CanonicalPoint3D:
        _require_parameter_count(entity, 4, "type 116 point")
        raw = tuple(_numeric(entity, index, f"coordinate {index}") for index in range(1, 4))
        transformed = _apply_matrix_to_raw_point(self._matrix_for_entity(entity), raw)
        pointer = entity.directory.de_pointer
        return _point(
            transformed,
            self.model.global_section,
            point_id=_point_id(pointer),
            source_entity_ref=_de_id(pointer),
        )

    def _map_direction_123(self, entity: IgesEntity) -> CanonicalVector3D:
        _require_parameter_count(entity, 4, "type 123 direction")
        raw = tuple(_numeric(entity, index, f"direction {index}") for index in range(1, 4))
        transformed = _apply_matrix_to_raw_vector(self._matrix_for_entity(entity), raw)
        return _vector(transformed)

    def _point_reference(self, pointer: int, owner: IgesEntity) -> CanonicalPoint3D:
        self._entity(pointer, {116}, "point")
        point = self.points.get(pointer)
        if point is None:
            raise _MappingError(f"point DE {pointer} was not decoded")
        return self._apply_point_transform(point, owner)

    def _direction_reference(
        self, pointer: int, owner: IgesEntity
    ) -> CanonicalVector3D:
        self._entity(pointer, {123}, "direction")
        direction = self.directions.get(pointer)
        if direction is None:
            raise _MappingError(f"direction DE {pointer} was not decoded")
        return self._apply_vector_transform(direction, owner)

    def _map_line_110(self, entity: IgesEntity) -> CanonicalCurve:
        _require_parameter_count(entity, 7, "type 110 line")
        start = tuple(_numeric(entity, index, f"start coordinate {index}") for index in range(1, 4))
        end = tuple(_numeric(entity, index, f"end coordinate {index}") for index in range(4, 7))
        matrix = self._matrix_for_entity(entity)
        start = _apply_matrix_to_raw_point(matrix, start)
        end = _apply_matrix_to_raw_point(matrix, end)
        delta = tuple(end[index] - start[index] for index in range(3))
        pointer = entity.directory.de_pointer
        end_point = _point(end, self.model.global_section, source_entity_ref=_de_id(pointer))
        return CanonicalCurve(
            curve_id=_curve_id(pointer),
            curve_type=CanonicalCurveType.LINE,
            source_entity_ref=_de_id(pointer),
            origin=_point(
                start, self.model.global_section, source_entity_ref=_de_id(pointer)
            ),
            direction=_vector(delta),
            metadata={"end_point": end_point},
        )

    def _map_arc_100(self, entity: IgesEntity) -> CanonicalCurve:
        _require_parameter_count(entity, 8, "type 100 circular arc")
        matrix = self._matrix_for_entity(entity)
        if not _is_rigid(matrix):
            raise _MappingError("type 100 arc requires a rigid transformation")
        z = _numeric(entity, 1, "plane Z")
        center_raw = (_numeric(entity, 2, "center X"), _numeric(entity, 3, "center Y"), z)
        start_raw = (_numeric(entity, 4, "start X"), _numeric(entity, 5, "start Y"), z)
        end_raw = (_numeric(entity, 6, "end X"), _numeric(entity, 7, "end Y"), z)
        center_raw = _apply_matrix_to_raw_point(matrix, center_raw)
        start_raw = _apply_matrix_to_raw_point(matrix, start_raw)
        end_raw = _apply_matrix_to_raw_point(matrix, end_raw)
        start_delta = tuple(start_raw[index] - center_raw[index] for index in range(3))
        end_delta = tuple(end_raw[index] - center_raw[index] for index in range(3))
        start_radius_squared = sum(value * value for value in start_delta)
        end_radius_squared = sum(value * value for value in end_delta)
        if start_radius_squared <= 0 or start_radius_squared != end_radius_squared:
            raise _MappingError("type 100 arc start/end radii must be equal and positive")
        with localcontext() as context:
            context.prec = 50
            radius = start_radius_squared.sqrt()
        pointer = entity.directory.de_pointer
        normal_raw = _apply_matrix_to_raw_vector(matrix, (Decimal(0), Decimal(0), Decimal(1)))
        return CanonicalCurve(
            curve_id=_curve_id(pointer),
            curve_type=CanonicalCurveType.ARC,
            source_entity_ref=_de_id(pointer),
            center=_point(center_raw, self.model.global_section),
            axis=_vector(normal_raw),
            radius=_length_mm(radius, self.model.global_section),
            metadata={
                "start_point": _point(start_raw, self.model.global_section),
                "end_point": _point(end_raw, self.model.global_section),
            },
        )

    def _map_bspline_curve_126(self, entity: IgesEntity) -> CanonicalCurve:
        _require_parameter_count(entity, 7, "type 126 rational B-spline curve")
        upper_index = _integer(entity, 1, "upper index")
        degree = _integer(entity, 2, "degree")
        if upper_index < 1 or degree < 1 or degree > upper_index:
            raise _MappingError("type 126 degree and upper index are inconsistent")
        flags = tuple(
            _integer(entity, index, f"property flag {index - 2}")
            for index in range(3, 7)
        )
        if any(flag not in {0, 1} for flag in flags):
            raise _MappingError("type 126 property flags must be 0 or 1")
        knot_count = upper_index + degree + 2
        control_point_count = upper_index + 1
        knot_start = 7
        weight_start = knot_start + knot_count
        control_start = weight_start + control_point_count
        parameter_start = control_start + control_point_count * 3
        _require_parameter_count(entity, parameter_start + 5, "type 126 rational B-spline curve")
        knots = tuple(
            _numeric(entity, knot_start + offset, "knot")
            for offset in range(knot_count)
        )
        if any(
            first > second
            for first, second in zip(knots, knots[1:], strict=False)
        ):
            raise _MappingError("type 126 knot vector must be nondecreasing")
        weights = tuple(
            _numeric(entity, weight_start + offset, "weight")
            for offset in range(control_point_count)
        )
        if any(weight <= 0 for weight in weights):
            raise _MappingError("type 126 weights must be positive")
        matrix = self._matrix_for_entity(entity)
        control_points = []
        for offset in range(control_point_count):
            index = control_start + offset * 3
            raw = tuple(_numeric(entity, index + axis, "control point") for axis in range(3))
            control_points.append(
                _point(
                    _apply_matrix_to_raw_point(matrix, raw),
                    self.model.global_section,
                )
            )
        parameter_range = (
            _numeric(entity, parameter_start, "start parameter"),
            _numeric(entity, parameter_start + 1, "end parameter"),
        )
        if parameter_range[0] >= parameter_range[1]:
            raise _MappingError("type 126 parameter range must increase")
        normal = tuple(
            _numeric(entity, parameter_start + 2 + axis, "plane normal")
            for axis in range(3)
        )
        pointer = entity.directory.de_pointer
        return CanonicalCurve(
            curve_id=_curve_id(pointer),
            curve_type=(
                CanonicalCurveType.BSPLINE if flags[2] == 1 else CanonicalCurveType.NURBS
            ),
            source_entity_ref=_de_id(pointer),
            degree=degree,
            control_points=tuple(control_points),
            knots=knots,
            weights=weights,
            metadata={
                "planar": bool(flags[0]),
                "closed": bool(flags[1]),
                "periodic": bool(flags[3]),
                "parameter_range": parameter_range,
                "plane_normal": normal,
            },
        )

    def _map_plane_108(self, entity: IgesEntity) -> CanonicalSurface:
        _require_parameter_count(entity, 5, "type 108 plane")
        matrix = self._matrix_for_entity(entity)
        if not _is_rigid(matrix):
            raise _MappingError("type 108 plane requires a rigid transformation")
        coefficients = tuple(_numeric(entity, index, "plane coefficient") for index in range(1, 4))
        displacement = _numeric(entity, 4, "plane displacement")
        norm_squared = sum(value * value for value in coefficients)
        if norm_squared <= 0:
            raise _MappingError("type 108 plane normal must be non-zero")
        origin_raw = tuple(value * displacement / norm_squared for value in coefficients)
        origin_raw = _apply_matrix_to_raw_point(matrix, origin_raw)
        normal_raw = _apply_matrix_to_raw_vector(matrix, coefficients)
        pointer = entity.directory.de_pointer
        return CanonicalSurface(
            surface_id=_surface_id(pointer),
            surface_type=CanonicalSurfaceType.PLANE,
            source_entity_ref=_de_id(pointer),
            origin=_point(origin_raw, self.model.global_section),
            normal=_vector(normal_raw),
            metadata={"equation_coefficients": (*coefficients, displacement)},
        )

    def _map_bspline_surface_128(self, entity: IgesEntity) -> CanonicalSurface:
        _require_parameter_count(entity, 10, "type 128 rational B-spline surface")
        upper_u = _integer(entity, 1, "U upper index")
        upper_v = _integer(entity, 2, "V upper index")
        degree_u = _integer(entity, 3, "U degree")
        degree_v = _integer(entity, 4, "V degree")
        if min(upper_u, upper_v, degree_u, degree_v) < 1:
            raise _MappingError("type 128 indices and degrees must be positive")
        if degree_u > upper_u or degree_v > upper_v:
            raise _MappingError("type 128 degree exceeds its upper index")
        flags = tuple(
            _integer(entity, index, f"property flag {index - 4}")
            for index in range(5, 10)
        )
        if any(flag not in {0, 1} for flag in flags):
            raise _MappingError("type 128 property flags must be 0 or 1")
        u_knot_count = upper_u + degree_u + 2
        v_knot_count = upper_v + degree_v + 2
        point_count = (upper_u + 1) * (upper_v + 1)
        u_start = 10
        v_start = u_start + u_knot_count
        weight_start = v_start + v_knot_count
        control_start = weight_start + point_count
        range_start = control_start + point_count * 3
        _require_parameter_count(entity, range_start + 4, "type 128 rational B-spline surface")
        u_knots = tuple(
            _numeric(entity, u_start + offset, "U knot")
            for offset in range(u_knot_count)
        )
        v_knots = tuple(
            _numeric(entity, v_start + offset, "V knot")
            for offset in range(v_knot_count)
        )
        if any(
            first > second
            for first, second in zip(u_knots, u_knots[1:], strict=False)
        ):
            raise _MappingError("type 128 U knot vector must be nondecreasing")
        if any(
            first > second
            for first, second in zip(v_knots, v_knots[1:], strict=False)
        ):
            raise _MappingError("type 128 V knot vector must be nondecreasing")
        weights = tuple(
            _numeric(entity, weight_start + offset, "weight")
            for offset in range(point_count)
        )
        if any(weight <= 0 for weight in weights):
            raise _MappingError("type 128 weights must be positive")
        matrix = self._matrix_for_entity(entity)
        control_points = []
        for offset in range(point_count):
            index = control_start + offset * 3
            raw = tuple(_numeric(entity, index + axis, "control point") for axis in range(3))
            control_points.append(
                _point(_apply_matrix_to_raw_point(matrix, raw), self.model.global_section)
            )
        u_range = (
            _numeric(entity, range_start, "U start"),
            _numeric(entity, range_start + 1, "U end"),
        )
        v_range = (
            _numeric(entity, range_start + 2, "V start"),
            _numeric(entity, range_start + 3, "V end"),
        )
        if u_range[0] >= u_range[1] or v_range[0] >= v_range[1]:
            raise _MappingError("type 128 parameter ranges must increase")
        pointer = entity.directory.de_pointer
        return CanonicalSurface(
            surface_id=_surface_id(pointer),
            surface_type=(
                CanonicalSurfaceType.BSPLINE
                if flags[2] == 1
                else CanonicalSurfaceType.NURBS
            ),
            source_entity_ref=_de_id(pointer),
            degree=degree_u if degree_u == degree_v else None,
            control_points=tuple(control_points),
            weights=weights,
            metadata={
                "u_degree": degree_u,
                "v_degree": degree_v,
                "u_knots": u_knots,
                "v_knots": v_knots,
                "control_point_grid_shape": (upper_u + 1, upper_v + 1),
                "u_parameter_range": u_range,
                "v_parameter_range": v_range,
                "closed_u": bool(flags[0]),
                "closed_v": bool(flags[1]),
                "periodic_u": bool(flags[3]),
                "periodic_v": bool(flags[4]),
            },
        )

    def _surface_reference_metadata(
        self, entity: IgesEntity, reference_pointer_index: int
    ) -> dict[str, object]:
        metadata: dict[str, object] = {}
        if entity.directory.form_number == 1:
            reference_pointer = _integer(
                entity, reference_pointer_index, "reference direction pointer"
            )
            reference = self._direction_reference(reference_pointer, entity)
            metadata["reference_direction"] = (
                reference.x.value,
                reference.y.value,
                reference.z.value,
            )
        elif entity.directory.form_number != 0:
            raise _MappingError(
                f"unsupported form {entity.directory.form_number} for type "
                f"{entity.directory.entity_type}"
            )
        return metadata

    def _map_plane_surface_190(self, entity: IgesEntity) -> CanonicalSurface:
        _require_parameter_count(entity, 3, "type 190 plane surface")
        self._require_rigid_entity_transform(entity)
        location = self._point_reference(_integer(entity, 1, "location pointer"), entity)
        normal = self._direction_reference(_integer(entity, 2, "normal pointer"), entity)
        metadata = self._surface_reference_metadata(entity, 3)
        pointer = entity.directory.de_pointer
        return CanonicalSurface(
            surface_id=_surface_id(pointer),
            surface_type=CanonicalSurfaceType.PLANE,
            source_entity_ref=_de_id(pointer),
            origin=location,
            normal=normal,
            metadata=metadata,
        )

    def _map_cylinder_192(self, entity: IgesEntity) -> CanonicalSurface:
        _require_parameter_count(entity, 4, "type 192 cylindrical surface")
        self._require_rigid_entity_transform(entity)
        location = self._point_reference(_integer(entity, 1, "location pointer"), entity)
        axis = self._direction_reference(_integer(entity, 2, "axis pointer"), entity)
        radius = _numeric(entity, 3, "radius")
        if radius <= 0:
            raise _MappingError("type 192 radius must be positive")
        metadata = self._surface_reference_metadata(entity, 4)
        pointer = entity.directory.de_pointer
        return CanonicalSurface(
            surface_id=_surface_id(pointer),
            surface_type=CanonicalSurfaceType.CYLINDER,
            source_entity_ref=_de_id(pointer),
            origin=location,
            axis=axis,
            radius=_length_mm(radius, self.model.global_section),
            metadata=metadata,
        )

    def _map_cone_194(self, entity: IgesEntity) -> CanonicalSurface:
        _require_parameter_count(entity, 5, "type 194 conical surface")
        self._require_rigid_entity_transform(entity)
        location = self._point_reference(_integer(entity, 1, "location pointer"), entity)
        axis = self._direction_reference(_integer(entity, 2, "axis pointer"), entity)
        radius = _numeric(entity, 3, "radius")
        angle = _numeric(entity, 4, "semi-angle")
        if radius <= 0 or not (Decimal(0) < angle < Decimal(90)):
            raise _MappingError("type 194 radius and semi-angle are outside valid bounds")
        metadata = self._surface_reference_metadata(entity, 5)
        metadata["semi_angle_unit"] = "degree"
        pointer = entity.directory.de_pointer
        return CanonicalSurface(
            surface_id=_surface_id(pointer),
            surface_type=CanonicalSurfaceType.CONE,
            source_entity_ref=_de_id(pointer),
            origin=location,
            axis=axis,
            radius=_length_mm(radius, self.model.global_section),
            semi_angle=Quantity(angle, Unit.DIMENSIONLESS),
            metadata=metadata,
        )

    def _map_sphere_196(self, entity: IgesEntity) -> CanonicalSurface:
        _require_parameter_count(entity, 3, "type 196 spherical surface")
        self._require_rigid_entity_transform(entity)
        center = self._point_reference(_integer(entity, 1, "center pointer"), entity)
        radius = _numeric(entity, 2, "radius")
        if radius <= 0:
            raise _MappingError("type 196 radius must be positive")
        axis = None
        metadata: dict[str, object] = {}
        if entity.directory.form_number == 1:
            _require_parameter_count(entity, 5, "parametrized type 196 spherical surface")
            axis = self._direction_reference(_integer(entity, 3, "axis pointer"), entity)
            metadata = self._surface_reference_metadata(entity, 4)
        elif entity.directory.form_number != 0:
            raise _MappingError(f"unsupported form {entity.directory.form_number} for type 196")
        pointer = entity.directory.de_pointer
        return CanonicalSurface(
            surface_id=_surface_id(pointer),
            surface_type=CanonicalSurfaceType.SPHERE,
            source_entity_ref=_de_id(pointer),
            center=center,
            axis=axis,
            radius=_length_mm(radius, self.model.global_section),
            metadata=metadata,
        )

    def _map_torus_198(self, entity: IgesEntity) -> CanonicalSurface:
        _require_parameter_count(entity, 5, "type 198 toroidal surface")
        self._require_rigid_entity_transform(entity)
        center = self._point_reference(_integer(entity, 1, "center pointer"), entity)
        axis = self._direction_reference(_integer(entity, 2, "axis pointer"), entity)
        major_radius = _numeric(entity, 3, "major radius")
        minor_radius = _numeric(entity, 4, "minor radius")
        if major_radius <= 0 or minor_radius <= 0:
            raise _MappingError("type 198 radii must be positive")
        metadata = self._surface_reference_metadata(entity, 5)
        pointer = entity.directory.de_pointer
        return CanonicalSurface(
            surface_id=_surface_id(pointer),
            surface_type=CanonicalSurfaceType.TORUS,
            source_entity_ref=_de_id(pointer),
            center=center,
            axis=axis,
            major_radius=_length_mm(major_radius, self.model.global_section),
            minor_radius=_length_mm(minor_radius, self.model.global_section),
            metadata=metadata,
        )

    def _record_issue(
        self,
        entity: IgesEntity,
        reason: str,
        *,
        fatal: bool,
        affects_topology: bool,
    ) -> None:
        self.issues.append(
            IgesMappingIssue(
                de_pointer=entity.directory.de_pointer,
                entity_type=entity.directory.entity_type,
                form_number=entity.directory.form_number,
                reason=reason,
                fatal=fatal,
                affects_topology=affects_topology,
            )
        )

    def _add_ref(
        self,
        entity: IgesEntity,
        kind: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        pointer = entity.directory.de_pointer
        ref_metadata: dict[str, object] = {
            "iges_entity_type": entity.directory.entity_type,
            "iges_form_number": entity.directory.form_number,
        }
        if metadata:
            ref_metadata.update(metadata)
        self.entity_refs.append(
            CanonicalEntityRef(
                entity_id=_de_id(pointer),
                entity_kind=kind,
                source_entity_id=str(pointer),
                metadata=ref_metadata,
            )
        )

    def map_geometry_entities(self) -> None:
        self._validate_supported_forms()
        self._parse_transforms()
        for entity in self.model.entities:
            entity_type = entity.directory.entity_type
            if entity.directory.de_pointer in self.invalid_entities:
                continue
            try:
                if entity_type == 116:
                    self.points[entity.directory.de_pointer] = self._map_point_116(entity)
                    self._add_ref(entity, "IgesPoint")
                elif entity_type == 123:
                    self.directions[entity.directory.de_pointer] = self._map_direction_123(entity)
                    self._add_ref(entity, "IgesDirection")
                elif entity_type == 124:
                    self._add_ref(entity, "IgesTransformationMatrix")
            except (_MappingError, ValidationError, InvalidOperation) as exc:
                self._record_issue(
                    entity,
                    f"invalid IGES entity type {entity_type}: {exc}",
                    fatal=True,
                    affects_topology=True,
                )

        mappers = {
            100: self._map_arc_100,
            108: self._map_plane_108,
            110: self._map_line_110,
            126: self._map_bspline_curve_126,
            128: self._map_bspline_surface_128,
            190: self._map_plane_surface_190,
            192: self._map_cylinder_192,
            194: self._map_cone_194,
            196: self._map_sphere_196,
            198: self._map_torus_198,
        }
        for entity in self.model.entities:
            entity_type = entity.directory.entity_type
            if entity.directory.de_pointer in self.invalid_entities:
                continue
            mapper = mappers.get(entity_type)
            if mapper is not None:
                try:
                    mapped = mapper(entity)
                    if isinstance(mapped, CanonicalCurve):
                        self.curves[entity.directory.de_pointer] = mapped
                        kind = "IgesCanonicalCurve"
                    else:
                        self.surfaces[entity.directory.de_pointer] = mapped
                        kind = "IgesCanonicalSurface"
                    self._add_ref(entity, kind)
                except (_MappingError, ValidationError, InvalidOperation) as exc:
                    self._record_issue(
                        entity,
                        f"invalid IGES entity type {entity_type}: {exc}",
                        fatal=True,
                        affects_topology=True,
                    )
                continue
            if entity_type in _AUXILIARY_TYPES or entity_type == 116:
                continue
            if entity_type in _BOUNDARY_TYPES or entity_type in _TOPOLOGY_TYPES:
                continue
            if entity_type in _PRESENTATION_TYPES:
                self._record_issue(
                    entity,
                    f"unsupported presentation/annotation IGES entity type {entity_type}",
                    fatal=False,
                    affects_topology=False,
                )
                self._add_ref(entity, "IgesUnsupportedPresentationEntity")
                continue
            self._record_issue(
                entity,
                f"unsupported geometry/topology IGES entity type {entity_type}",
                fatal=True,
                affects_topology=True,
            )
            self._add_ref(entity, "IgesUnsupportedEntity")

    def _surface_reference(self, pointer: int, owner_name: str) -> CanonicalSurface:
        surface = self.surfaces.get(pointer)
        if surface is None:
            entity = self.model.entities_by_pointer.get(pointer)
            entity_type = entity.directory.entity_type if entity is not None else "missing"
            raise _MappingError(
                f"{owner_name} references unavailable surface DE {pointer} "
                f"(type {entity_type})"
            )
        return surface

    def _curve_reference(self, pointer: int, owner_name: str) -> CanonicalCurve:
        curve = self.curves.get(pointer)
        if curve is None:
            entity = self.model.entities_by_pointer.get(pointer)
            entity_type = entity.directory.entity_type if entity is not None else "missing"
            raise _MappingError(
                f"{owner_name} references unavailable curve DE {pointer} "
                f"(type {entity_type})"
            )
        return curve

    def _map_boundary_141(self, entity: IgesEntity) -> None:
        _require_parameter_count(entity, 8, "type 141 boundary")
        boundary_type = _integer(entity, 1, "boundary type")
        preference = _integer(entity, 2, "preferred representation")
        surface_pointer = _integer(entity, 3, "surface pointer")
        curve_count = _integer(entity, 4, "curve count")
        if boundary_type not in {0, 1}:
            raise _MappingError("type 141 boundary type must be 0 or 1")
        if preference not in {0, 1, 2, 3}:
            raise _MappingError("type 141 preferred representation must be 0 through 3")
        if curve_count < 1:
            raise _MappingError("type 141 curve count must be positive")
        self._surface_reference(surface_pointer, "type 141")
        cursor = 5
        model_curve_ids: list[str] = []
        senses: list[bool] = []
        parameter_curve_ids: list[tuple[str, ...]] = []
        for _ in range(curve_count):
            model_curve_pointer = _integer(entity, cursor, "model-space curve pointer")
            sense = _integer(entity, cursor + 1, "orientation flag")
            parameter_curve_count = _integer(
                entity, cursor + 2, "parameter curve count"
            )
            if sense not in {0, 1} or parameter_curve_count < 0:
                raise _MappingError("type 141 orientation/count is invalid")
            model_curve_ids.append(
                self._curve_reference(model_curve_pointer, "type 141").curve_id
            )
            parameter_ids = []
            for offset in range(parameter_curve_count):
                parameter_pointer = _integer(
                    entity, cursor + 3 + offset, "parameter curve pointer"
                )
                parameter_ids.append(
                    self._curve_reference(parameter_pointer, "type 141").curve_id
                )
            if boundary_type == 0 and parameter_ids:
                raise _MappingError(
                    "type 141 model-space-only boundary has parameter curves"
                )
            senses.append(bool(sense))
            parameter_curve_ids.append(tuple(parameter_ids))
            cursor += 3 + parameter_curve_count
        _require_parameter_count(entity, cursor, "type 141 boundary")
        self._add_ref(
            entity,
            "IgesBoundary",
            {
                "boundary_type": boundary_type,
                "preferred_representation": preference,
                "surface_id": _surface_id(surface_pointer),
                "model_curve_ids": tuple(model_curve_ids),
                "orientation_reversals": tuple(senses),
                "parameter_curve_ids": tuple(parameter_curve_ids),
            },
        )
        self.boundary_surfaces[entity.directory.de_pointer] = surface_pointer

    def _map_curve_on_surface_142(self, entity: IgesEntity) -> None:
        _require_parameter_count(entity, 6, "type 142 curve on parametric surface")
        creation_flag = _integer(entity, 1, "creation flag")
        surface_pointer = _integer(entity, 2, "surface pointer")
        parameter_curve_pointer = _integer(entity, 3, "parameter-space curve pointer")
        model_curve_pointer = _integer(entity, 4, "model-space curve pointer")
        preference = _integer(entity, 5, "preferred representation")
        self._surface_reference(surface_pointer, "type 142")
        if parameter_curve_pointer:
            self._curve_reference(parameter_curve_pointer, "type 142")
        if model_curve_pointer:
            self._curve_reference(model_curve_pointer, "type 142")
        if not parameter_curve_pointer and not model_curve_pointer:
            raise _MappingError("type 142 requires a parameter-space or model-space curve")
        if preference not in {0, 1, 2, 3}:
            raise _MappingError("type 142 preferred representation must be 0 through 3")
        self._add_ref(
            entity,
            "IgesCurveOnParametricSurface",
            {
                "creation_flag": creation_flag,
                "surface_id": _surface_id(surface_pointer),
                "parameter_curve_id": (
                    _curve_id(parameter_curve_pointer)
                    if parameter_curve_pointer
                    else None
                ),
                "model_curve_id": (
                    _curve_id(model_curve_pointer) if model_curve_pointer else None
                ),
                "preferred_representation": preference,
            },
        )
        self.boundary_surfaces[entity.directory.de_pointer] = surface_pointer

    def _map_bounded_surface_143(self, entity: IgesEntity) -> CanonicalSurface:
        _require_parameter_count(entity, 5, "type 143 bounded surface")
        boundary_type = _integer(entity, 1, "boundary type")
        base_pointer = _integer(entity, 2, "base surface pointer")
        boundary_count = _integer(entity, 3, "boundary count")
        if boundary_type not in {0, 1} or boundary_count < 1:
            raise _MappingError("type 143 boundary flags/count are invalid")
        _require_parameter_count(entity, 4 + boundary_count, "type 143 bounded surface")
        base = self._surface_reference(base_pointer, "type 143")
        relationship_ids: list[str] = []
        for offset in range(boundary_count):
            pointer = _integer(entity, 4 + offset, "boundary pointer")
            self._entity(pointer, {141}, "type 143 boundary")
            if pointer not in self.valid_boundary_relationships:
                raise _MappingError(
                    f"type 143 boundary DE {pointer} failed validation"
                )
            if self.boundary_surfaces[pointer] != base_pointer:
                raise _MappingError(
                    f"type 143 boundary DE {pointer} references a different surface"
                )
            relationship_ids.append(_de_id(pointer))
        pointer = entity.directory.de_pointer
        metadata = dict(base.metadata)
        metadata.update(
            {
                "base_surface_id": base.surface_id,
                "boundary_type": boundary_type,
                "boundary_relationship_ids": tuple(relationship_ids),
            }
        )
        return replace(
            base,
            surface_id=_surface_id(pointer),
            source_entity_ref=_de_id(pointer),
            metadata=metadata,
        )

    def _map_trimmed_surface_144(self, entity: IgesEntity) -> CanonicalSurface:
        _require_parameter_count(entity, 4, "type 144 trimmed surface")
        base_pointer = _integer(entity, 1, "base surface pointer")
        outer_flag = _integer(entity, 2, "outer boundary flag")
        inner_count = _integer(entity, 3, "inner boundary count")
        if outer_flag not in {0, 1} or inner_count < 0:
            raise _MappingError("type 144 boundary flags/count are invalid")
        required = 5 + inner_count
        _require_parameter_count(entity, required, "type 144 trimmed surface")
        base = self._surface_reference(base_pointer, "type 144")
        outer_pointer = _integer(entity, 4, "outer boundary pointer")
        outer_id = None
        if outer_flag:
            self._entity(outer_pointer, {142}, "type 144 outer boundary")
            if outer_pointer not in self.valid_boundary_relationships:
                raise _MappingError(
                    f"type 144 outer boundary DE {outer_pointer} failed validation"
                )
            if self.boundary_surfaces[outer_pointer] != base_pointer:
                raise _MappingError(
                    f"type 144 outer boundary DE {outer_pointer} references a "
                    "different surface"
                )
            outer_id = _de_id(outer_pointer)
        elif outer_pointer != 0:
            raise _MappingError(
                "type 144 natural outer boundary pointer must be zero"
            )
        inner_ids = []
        for offset in range(inner_count):
            inner_pointer = _integer(entity, 5 + offset, "inner boundary pointer")
            self._entity(inner_pointer, {142}, "type 144 inner boundary")
            if inner_pointer not in self.valid_boundary_relationships:
                raise _MappingError(
                    f"type 144 inner boundary DE {inner_pointer} failed validation"
                )
            if self.boundary_surfaces[inner_pointer] != base_pointer:
                raise _MappingError(
                    f"type 144 inner boundary DE {inner_pointer} references a "
                    "different surface"
                )
            inner_ids.append(_de_id(inner_pointer))
        pointer = entity.directory.de_pointer
        metadata = dict(base.metadata)
        metadata.update(
            {
                "base_surface_id": base.surface_id,
                "outer_boundary_relationship_id": outer_id,
                "inner_boundary_relationship_ids": tuple(inner_ids),
            }
        )
        return replace(
            base,
            surface_id=_surface_id(pointer),
            source_entity_ref=_de_id(pointer),
            metadata=metadata,
        )

    def _map_boundaries(self) -> None:
        for entity_type, mapper in (
            (141, self._map_boundary_141),
            (142, self._map_curve_on_surface_142),
        ):
            for entity in self.model.entities:
                if entity.directory.entity_type != entity_type:
                    continue
                if entity.directory.de_pointer in self.invalid_entities:
                    continue
                try:
                    mapper(entity)
                    self.valid_boundary_relationships.add(
                        entity.directory.de_pointer
                    )
                except (_MappingError, ValidationError) as exc:
                    self._record_issue(
                        entity,
                        f"invalid IGES boundary entity type {entity_type}: {exc}",
                        fatal=False,
                        affects_topology=True,
                    )
        for entity_type, mapper in (
            (143, self._map_bounded_surface_143),
            (144, self._map_trimmed_surface_144),
        ):
            for entity in self.model.entities:
                if entity.directory.entity_type != entity_type:
                    continue
                if entity.directory.de_pointer in self.invalid_entities:
                    continue
                try:
                    surface = mapper(entity)
                    self.surfaces[entity.directory.de_pointer] = surface
                    self._add_ref(entity, "IgesCanonicalBoundedSurface")
                except (_MappingError, ValidationError) as exc:
                    self._record_issue(
                        entity,
                        f"invalid IGES boundary entity type {entity_type}: {exc}",
                        fatal=False,
                        affects_topology=True,
                    )

    def _map_vertex_list_502(self, entity: IgesEntity) -> tuple[CanonicalVertex, ...]:
        vertex_count = _integer(entity, 1, "vertex count")
        if vertex_count < 1:
            raise _MappingError("type 502 vertex count must be positive")
        _require_parameter_count(entity, 2 + vertex_count * 3, "type 502 vertex list")
        matrix = self._matrix_for_entity(entity)
        pointer = entity.directory.de_pointer
        vertices = []
        for offset in range(vertex_count):
            index = 2 + offset * 3
            raw = tuple(_numeric(entity, index + axis, "vertex coordinate") for axis in range(3))
            raw = _apply_matrix_to_raw_point(matrix, raw)
            vertex_id = f"vertex-de-{pointer:07d}-{offset + 1:04d}"
            vertices.append(
                CanonicalVertex(
                    vertex_id=vertex_id,
                    point=_point(
                        raw,
                        self.model.global_section,
                        point_id=f"{vertex_id}-point",
                        source_entity_ref=_de_id(pointer),
                    ),
                    source_entity_ref=_de_id(pointer),
                    metadata={"iges_vertex_index": offset + 1},
                )
            )
        return tuple(vertices)

    def _vertex_from_list(self, list_pointer: int, index: int) -> CanonicalVertex:
        vertices = self.vertex_lists.get(list_pointer)
        if vertices is None:
            raise _MappingError(f"vertex list DE {list_pointer} is unavailable")
        if index < 1 or index > len(vertices):
            raise _MappingError(
                f"vertex index {index} is outside DE {list_pointer} vertex list"
            )
        return vertices[index - 1]

    def _map_edge_list_504(self, entity: IgesEntity) -> tuple[CanonicalEdge, ...]:
        edge_count = _integer(entity, 1, "edge count")
        if edge_count < 1:
            raise _MappingError("type 504 edge count must be positive")
        _require_parameter_count(entity, 2 + edge_count * 5, "type 504 edge list")
        pointer = entity.directory.de_pointer
        edges = []
        for offset in range(edge_count):
            index = 2 + offset * 5
            curve_pointer = _integer(entity, index, "curve pointer")
            start_list = _integer(entity, index + 1, "start vertex list pointer")
            start_index = _integer(entity, index + 2, "start vertex index")
            end_list = _integer(entity, index + 3, "end vertex list pointer")
            end_index = _integer(entity, index + 4, "end vertex index")
            curve = self._curve_reference(curve_pointer, "type 504")
            start = self._vertex_from_list(start_list, start_index)
            end = self._vertex_from_list(end_list, end_index)
            edges.append(
                CanonicalEdge(
                    edge_id=f"edge-de-{pointer:07d}-{offset + 1:04d}",
                    start_vertex_id=start.vertex_id,
                    end_vertex_id=end.vertex_id,
                    curve_id=curve.curve_id,
                    source_entity_ref=_de_id(pointer),
                    metadata={"iges_edge_index": offset + 1},
                )
            )
        return tuple(edges)

    def _edge_from_list(self, list_pointer: int, index: int) -> CanonicalEdge:
        edges = self.edge_lists.get(list_pointer)
        if edges is None:
            raise _MappingError(f"edge list DE {list_pointer} is unavailable")
        if index < 1 or index > len(edges):
            raise _MappingError(f"edge index {index} is outside DE {list_pointer} edge list")
        return edges[index - 1]

    def _map_loop_508(self, entity: IgesEntity) -> CanonicalLoop:
        member_count = _integer(entity, 1, "loop member count")
        if member_count < 3:
            raise _MappingError("type 508 loop requires at least three members")
        pointer = entity.directory.de_pointer
        cursor = 2
        edge_ids: list[str] = []
        orientations: list[str] = []
        parameter_curve_ids: list[tuple[str, ...]] = []
        for _ in range(member_count):
            member_type = _integer(entity, cursor, "loop member type")
            if member_type != 0:
                raise _MappingError(
                    f"unsupported type 508 vertex-use member type {member_type}"
                )
            list_pointer = _integer(entity, cursor + 1, "edge list pointer")
            edge_index = _integer(entity, cursor + 2, "edge index")
            orientation_flag = _integer(entity, cursor + 3, "edge orientation")
            parameter_curve_count = _integer(
                entity, cursor + 4, "parameter curve count"
            )
            if orientation_flag not in {0, 1} or parameter_curve_count < 0:
                raise _MappingError("type 508 orientation/count is invalid")
            edge = self._edge_from_list(list_pointer, edge_index)
            edge_ids.append(edge.edge_id)
            orientations.append(
                Orientation.FORWARD.value
                if orientation_flag == 1
                else Orientation.REVERSED.value
            )
            curve_ids: list[str] = []
            for parameter_index in range(parameter_curve_count):
                iso_index = cursor + 5 + parameter_index * 2
                _integer(entity, iso_index, "isoparametric flag")
                curve_pointer = _integer(
                    entity, iso_index + 1, "parameter curve pointer"
                )
                curve_ids.append(
                    self._curve_reference(curve_pointer, "type 508").curve_id
                )
            parameter_curve_ids.append(tuple(curve_ids))
            cursor += 5 + parameter_curve_count * 2
        return CanonicalLoop(
            loop_id=f"loop-de-{pointer:07d}",
            edge_ids=tuple(edge_ids),
            loop_type=LoopType.UNKNOWN,
            source_entity_ref=_de_id(pointer),
            metadata={
                "edge_orientations": tuple(orientations),
                "parameter_curve_ids": tuple(parameter_curve_ids),
            },
        )

    def _map_face_510(self, entity: IgesEntity) -> CanonicalFace:
        surface_pointer = _integer(entity, 1, "surface pointer")
        loop_count = _integer(entity, 2, "loop count")
        outer_flag = _integer(entity, 3, "outer loop flag")
        if loop_count < 1 or outer_flag not in {0, 1}:
            raise _MappingError("type 510 loop count/outer flag is invalid")
        _require_parameter_count(entity, 4 + loop_count, "type 510 face")
        surface = self._surface_reference(surface_pointer, "type 510")
        loops = []
        for offset in range(loop_count):
            loop_pointer = _integer(entity, 4 + offset, "loop pointer")
            loop = self.loops.get(loop_pointer)
            if loop is None:
                raise _MappingError(f"face references unavailable loop DE {loop_pointer}")
            loops.append(loop)
        pointer = entity.directory.de_pointer
        return CanonicalFace(
            face_id=f"face-de-{pointer:07d}",
            surface_id=surface.surface_id,
            boundary_loop_ids=tuple(loop.loop_id for loop in loops),
            source_entity_ref=_de_id(pointer),
            metadata={"outer_loop_is_first": bool(outer_flag)},
        )

    def _map_shell_514(self, entity: IgesEntity) -> CanonicalShell:
        face_count = _integer(entity, 1, "face count")
        if face_count < 1:
            raise _MappingError("type 514 face count must be positive")
        _require_parameter_count(entity, 2 + face_count * 2, "type 514 shell")
        faces = []
        orientations = []
        for offset in range(face_count):
            face_pointer = _integer(entity, 2 + offset * 2, "face pointer")
            orientation = _integer(entity, 3 + offset * 2, "face orientation")
            if orientation not in {0, 1}:
                raise _MappingError("type 514 face orientation must be 0 or 1")
            face = self.faces.get(face_pointer)
            if face is None:
                raise _MappingError(f"shell references unavailable face DE {face_pointer}")
            faces.append(face)
            orientations.append(bool(orientation))
        pointer = entity.directory.de_pointer
        return CanonicalShell(
            shell_id=f"shell-de-{pointer:07d}",
            face_ids=tuple(face.face_id for face in faces),
            closure=ShellClosure.UNKNOWN,
            is_oriented=True,
            source_entity_ref=_de_id(pointer),
            metadata={"face_orientation_flags": tuple(orientations)},
        )

    def _map_solid_186(self, entity: IgesEntity) -> CanonicalBody:
        shell_pointer = _integer(entity, 1, "outer shell pointer")
        orientation = _integer(entity, 2, "outer shell orientation")
        void_count = _integer(entity, 3, "void shell count")
        if orientation not in {0, 1} or void_count < 0:
            raise _MappingError("type 186 orientation/count is invalid")
        _require_parameter_count(entity, 4 + void_count * 2, "type 186 solid")
        shell_pointers = [shell_pointer]
        shell_orientations = [bool(orientation)]
        for offset in range(void_count):
            void_pointer = _integer(entity, 4 + offset * 2, "void shell pointer")
            void_orientation = _integer(
                entity, 5 + offset * 2, "void shell orientation"
            )
            if void_orientation not in {0, 1}:
                raise _MappingError("type 186 void shell orientation must be 0 or 1")
            shell_pointers.append(void_pointer)
            shell_orientations.append(bool(void_orientation))
        shells = []
        for pointer in shell_pointers:
            shell = self.shells.get(pointer)
            if shell is None:
                raise _MappingError(f"solid references unavailable shell DE {pointer}")
            closed = replace(shell, closure=ShellClosure.CLOSED)
            self.shells[pointer] = closed
            shells.append(closed)
        pointer = entity.directory.de_pointer
        return CanonicalBody(
            body_id=f"body-de-{pointer:07d}",
            body_type=BodyType.SOLID,
            shell_ids=tuple(shell.shell_id for shell in shells),
            source_entity_ref=_de_id(pointer),
            metadata={"shell_orientation_flags": tuple(shell_orientations)},
        )

    def _map_topology_group(
        self,
        entity_type: int,
        mapper,
        target: dict,
        kind: str,
    ) -> None:
        for entity in self.model.entities:
            if entity.directory.entity_type != entity_type:
                continue
            try:
                target[entity.directory.de_pointer] = mapper(entity)
                self._add_ref(entity, kind)
            except (_MappingError, ValidationError) as exc:
                self._record_issue(
                    entity,
                    f"invalid IGES topology entity type {entity_type}: {exc}",
                    fatal=False,
                    affects_topology=True,
                )

    def _build_geometry(self) -> CanonicalGeometry | None:
        if self.geometry is not None:
            return self.geometry
        if not (self.curves or self.surfaces or self.points):
            return None
        tolerance = self.model.global_section.minimum_resolution
        self.geometry = CanonicalGeometry(
            geometry_id="geometry-iges",
            curves=tuple(self.curves[pointer] for pointer in sorted(self.curves)),
            surfaces=tuple(self.surfaces[pointer] for pointer in sorted(self.surfaces)),
            metadata={
                "iges_source_unit": self.model.global_section.unit_name,
                "iges_model_scale": self.model.global_section.model_scale,
                "iges_minimum_resolution_mm": (
                    tolerance * _scale(self.model.global_section)
                    if tolerance is not None
                    else None
                ),
                "standalone_points": tuple(
                    self.points[pointer] for pointer in sorted(self.points)
                ),
            },
        )
        return self.geometry

    def map_topology_entities(self) -> None:
        self._map_boundaries()
        if any(issue.fatal for issue in self.issues):
            return
        self._map_topology_group(
            502, self._map_vertex_list_502, self.vertex_lists, "IgesVertexList"
        )
        self._map_topology_group(
            504, self._map_edge_list_504, self.edge_lists, "IgesEdgeList"
        )
        self._map_topology_group(508, self._map_loop_508, self.loops, "IgesLoop")
        self._map_topology_group(510, self._map_face_510, self.faces, "IgesFace")
        self._map_topology_group(514, self._map_shell_514, self.shells, "IgesShell")
        self._map_topology_group(186, self._map_solid_186, self.bodies, "IgesManifoldSolid")
        topology_entities_present = any(
            entity.directory.entity_type in _TOPOLOGY_TYPES
            for entity in self.model.entities
        )
        if not topology_entities_present or any(
            issue.affects_topology for issue in self.issues
        ):
            return
        geometry = self._build_geometry()
        if geometry is None:
            return
        self.topology = CanonicalTopology(
            topology_id="topology-iges",
            vertices=tuple(
                vertex
                for pointer in sorted(self.vertex_lists)
                for vertex in self.vertex_lists[pointer]
            ),
            edges=tuple(
                edge
                for pointer in sorted(self.edge_lists)
                for edge in self.edge_lists[pointer]
            ),
            loops=tuple(self.loops[pointer] for pointer in sorted(self.loops)),
            faces=tuple(self.faces[pointer] for pointer in sorted(self.faces)),
            shells=tuple(self.shells[pointer] for pointer in sorted(self.shells)),
            bodies=tuple(self.bodies[pointer] for pointer in sorted(self.bodies)),
            geometry=geometry,
            source_entity_ref=(
                _de_id(min(self.bodies)) if self.bodies else None
            ),
        )

    def build_result(self) -> IgesMappingResult:
        fatal = any(issue.fatal for issue in self.issues)
        geometry = None if fatal else self._build_geometry()
        topology = None if fatal else self.topology
        return IgesMappingResult(
            geometry=geometry,
            topology=topology,
            entity_refs=tuple(self.entity_refs),
            issues=tuple(self.issues),
        )


def map_iges_model(model: IgesModel) -> IgesMappingResult:
    """Map a parsed IGES model without inventing or repairing geometry."""

    context = _MappingContext(model)
    context.map_geometry_entities()
    context.map_topology_entities()
    return context.build_result()
