"""Deterministic Geometry Normalization and Transform Service (Stage 4F).

Provides deterministic, copy-based application of Transform3D to canonical
geometry and topology objects from Stage 4B.

Transform convention
--------------------
Transform3D stores:
    translation: tuple[Decimal, Decimal, Decimal]   — added to point coords
    rotation:    tuple[Decimal, ...]                — 9 Decimals, row-major 3x3

Row-major means the matrix rows are stored in order:
    [r0, r1, r2,   r3, r4, r5,   r6, r7, r8]
    row0 = (r0, r1, r2)
    row1 = (r3, r4, r5)
    row2 = (r6, r7, r8)

Point application (rigid body):
    p'x = r0*px + r1*py + r2*pz + tx
    p'y = r3*px + r4*py + r5*pz + ty
    p'z = r6*px + r7*py + r8*pz + tz

Vector application (direction — no translation):
    v'x = r0*vx + r1*vy + r2*vz
    v'y = r3*vx + r4*vy + r5*vz
    v'z = r6*vx + r7*vy + r8*vz

Empty rotation (len==0) means identity rotation.

Coordinate units are preserved: input Quantity unit is carried through.
Translation is interpreted in the same length unit as the input point.
Scalar geometric values (radius, semi_angle) are invariant under rigid body.

Body transform modes
--------------------
PRESERVE_PLACEMENT  — body.transform metadata is retained; geometry NOT re-baked.
BAKE_TRANSFORM      — body.transform is applied to all constituent vertex points;
                      body.transform is cleared to identity afterward.

Stage 4F does NOT implement:
- CAD healing, topology sewing, vertex merge, B-Rep repair
- NURBS work, feature recognition, DFM, CAM
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from backend.domain.base import (
    Provenance,
    entity_as_dict,
    optional_non_empty_str,
    require_non_empty_str,
)
from backend.domain.enums import ProvenanceType
from backend.domain.exceptions import ValidationError
from backend.domain.units import Quantity, Unit
from backend.interoperability.geometry import (
    BoundingBox3D,
    CanonicalCurve,
    CanonicalGeometry,
    CanonicalPoint3D,
    CanonicalSurface,
    CanonicalVector3D,
    GeometryContainerError,
)
from backend.interoperability.topology import (
    CanonicalBody,
    CanonicalTopology,
    CanonicalVertex,
    TopologyContainerError,
    Transform3D,
)

__all__ = [
    "TransformApplicationMode",
    "NormalizationDiagnostic",
    "GeometryNormalizationResult",
    "TopologyNormalizationResult",
    "apply_transform_to_point",
    "apply_transform_to_vector",
    "apply_transform_to_geometry",
    "apply_transform_to_topology",
    "normalize_geometry_units",
]

_ZERO = Decimal(0)
_ONE = Decimal(1)

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TransformApplicationMode(StrEnum):
    """How a Transform3D on CanonicalBody is handled."""
    PRESERVE_PLACEMENT = "PRESERVE_PLACEMENT"
    """body.transform is kept as placement metadata; geometry is NOT modified."""
    BAKE_TRANSFORM = "BAKE_TRANSFORM"
    """body.transform is applied to constituent vertex coordinates;
    body.transform on the result is cleared (identity)."""


# ---------------------------------------------------------------------------
# Diagnostic
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class NormalizationDiagnostic:
    severity: str
    message: str
    entity_id: str | None = None

    def __post_init__(self) -> None:
        _s = object.__setattr__
        _s(self, "severity", require_non_empty_str(self.severity, "severity"))
        _s(self, "message", require_non_empty_str(self.message, "message"))
        _s(self, "entity_id", optional_non_empty_str(self.entity_id, "entity_id"))

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class GeometryNormalizationResult:
    source_geometry_id: str
    output_geometry: CanonicalGeometry | None
    applied_transform: Transform3D | None
    is_lossless: bool
    diagnostics: tuple[NormalizationDiagnostic, ...]
    provenance: Provenance
    notes: str | None = None

    def __post_init__(self) -> None:
        _s = object.__setattr__
        _s(self, "source_geometry_id",
           require_non_empty_str(self.source_geometry_id, "source_geometry_id"))
        if self.output_geometry is not None and not isinstance(
            self.output_geometry, CanonicalGeometry
        ):
            raise ValidationError("output_geometry must be CanonicalGeometry or None")
        if self.applied_transform is not None and not isinstance(
            self.applied_transform, Transform3D
        ):
            raise ValidationError("applied_transform must be Transform3D or None")
        if not isinstance(self.provenance, Provenance):
            raise ValidationError("provenance must be a Provenance")
        _s(self, "notes", optional_non_empty_str(self.notes, "notes"))

    @property
    def succeeded(self) -> bool:
        return self.output_geometry is not None

    @property
    def error_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity == "ERROR")

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


@dataclass(frozen=True, slots=True)
class TopologyNormalizationResult:
    source_topology_id: str
    output_topology: CanonicalTopology | None
    output_geometry: CanonicalGeometry | None
    applied_transform: Transform3D | None
    transform_mode: TransformApplicationMode
    is_lossless: bool
    diagnostics: tuple[NormalizationDiagnostic, ...]
    provenance: Provenance
    notes: str | None = None

    def __post_init__(self) -> None:
        _s = object.__setattr__
        _s(self, "source_topology_id",
           require_non_empty_str(self.source_topology_id, "source_topology_id"))
        if not isinstance(self.transform_mode, TransformApplicationMode):
            raise ValidationError("transform_mode must be a TransformApplicationMode")
        if not isinstance(self.provenance, Provenance):
            raise ValidationError("provenance must be a Provenance")
        _s(self, "notes", optional_non_empty_str(self.notes, "notes"))

    @property
    def succeeded(self) -> bool:
        return self.output_topology is not None

    @property
    def error_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity == "ERROR")

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Internal math (Decimal-based, no floating point)
# ---------------------------------------------------------------------------

def _identity_rotation() -> tuple[Decimal, ...]:
    return (_ONE, _ZERO, _ZERO,
            _ZERO, _ONE, _ZERO,
            _ZERO, _ZERO, _ONE)


def _mat_apply_point(
    rotation: tuple[Decimal, ...],
    px: Decimal, py: Decimal, pz: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """Apply row-major 3x3 rotation to a point (no translation)."""
    r = rotation
    ox = r[0] * px + r[1] * py + r[2] * pz
    oy = r[3] * px + r[4] * py + r[5] * pz
    oz = r[6] * px + r[7] * py + r[8] * pz
    return ox, oy, oz


def _effective_rotation(t: Transform3D) -> tuple[Decimal, ...]:
    if len(t.rotation) == 0:
        return _identity_rotation()
    return t.rotation  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Point transform
# ---------------------------------------------------------------------------

def apply_transform_to_point(
    point: CanonicalPoint3D,
    transform: Transform3D,
) -> CanonicalPoint3D:
    """Apply a rigid Transform3D to a CanonicalPoint3D.

    Translation is in the same length unit as the point coordinates.
    Rotation is dimensionless (scale-preserving).
    The output point has the same unit as the input.

    Args:
        point:     Source point with Quantity coordinates (MM or M).
        transform: Rigid body transform (rotation + translation).

    Returns:
        New CanonicalPoint3D with transformed coordinates, same unit.
    """
    if not isinstance(point, CanonicalPoint3D):
        raise ValidationError("point must be a CanonicalPoint3D")
    if not isinstance(transform, Transform3D):
        raise ValidationError("transform must be a Transform3D")

    rot = _effective_rotation(transform)
    px, py, pz = point.x.value, point.y.value, point.z.value
    ox, oy, oz = _mat_apply_point(rot, px, py, pz)

    # Add translation (same length unit as input)
    tx, ty, tz = transform.translation
    ox += tx
    oy += ty
    oz += tz

    unit = point.unit
    return CanonicalPoint3D(
        x=Quantity(value=ox, unit=unit),
        y=Quantity(value=oy, unit=unit),
        z=Quantity(value=oz, unit=unit),
    )


# ---------------------------------------------------------------------------
# Vector transform
# ---------------------------------------------------------------------------

def apply_transform_to_vector(
    vector: CanonicalVector3D,
    transform: Transform3D,
) -> CanonicalVector3D:
    """Apply rotation portion of a Transform3D to a CanonicalVector3D.

    Translation is NOT applied to direction vectors.
    Dimensionless unit is preserved.

    Args:
        vector:    Source direction vector (Unit.DIMENSIONLESS).
        transform: Rigid body transform (only rotation is applied).

    Returns:
        New CanonicalVector3D with rotated components.
    """
    if not isinstance(vector, CanonicalVector3D):
        raise ValidationError("vector must be a CanonicalVector3D")
    if not isinstance(transform, Transform3D):
        raise ValidationError("transform must be a Transform3D")

    rot = _effective_rotation(transform)
    vx, vy, vz = vector.x.value, vector.y.value, vector.z.value
    ox, oy, oz = _mat_apply_point(rot, vx, vy, vz)

    return CanonicalVector3D(
        x=Quantity(value=ox, unit=Unit.DIMENSIONLESS),
        y=Quantity(value=oy, unit=Unit.DIMENSIONLESS),
        z=Quantity(value=oz, unit=Unit.DIMENSIONLESS),
    )


# ---------------------------------------------------------------------------
# Curve / Surface transform helpers
# ---------------------------------------------------------------------------

def _transform_curve(curve: CanonicalCurve, t: Transform3D) -> CanonicalCurve:
    """Return a new CanonicalCurve with transformed positional fields."""
    origin = apply_transform_to_point(curve.origin, t) if curve.origin is not None else None
    center = apply_transform_to_point(curve.center, t) if curve.center is not None else None
    direction = (
        apply_transform_to_vector(curve.direction, t)
        if curve.direction is not None else None
    )
    axis = (
        apply_transform_to_vector(curve.axis, t)
        if curve.axis is not None else None
    )
    # Scalar values (radius etc.) are invariant under rigid body transform
    return CanonicalCurve(
        curve_id=curve.curve_id,
        curve_type=curve.curve_type,
        source_entity_ref=curve.source_entity_ref,
        origin=origin,
        direction=direction,
        center=center,
        axis=axis,
        radius=curve.radius,
        major_radius=curve.major_radius,
        minor_radius=curve.minor_radius,
        degree=curve.degree,
        control_points=tuple(
            apply_transform_to_point(p, t) for p in curve.control_points
        ),
        knots=curve.knots,
        weights=curve.weights,
    )


def _transform_surface(surface: CanonicalSurface, t: Transform3D) -> CanonicalSurface:
    """Return a new CanonicalSurface with transformed positional fields."""
    origin = apply_transform_to_point(surface.origin, t) if surface.origin is not None else None
    center = apply_transform_to_point(surface.center, t) if surface.center is not None else None
    axis = (
        apply_transform_to_vector(surface.axis, t)
        if surface.axis is not None else None
    )
    normal = (
        apply_transform_to_vector(surface.normal, t)
        if surface.normal is not None else None
    )
    control_points = tuple(
        apply_transform_to_point(p, t) for p in surface.control_points
    )
    # Scalar values are invariant under rigid body transform
    return CanonicalSurface(
        surface_id=surface.surface_id,
        surface_type=surface.surface_type,
        source_entity_ref=surface.source_entity_ref,
        origin=origin,
        center=center,
        axis=axis,
        normal=normal,
        radius=surface.radius,
        major_radius=surface.major_radius,
        minor_radius=surface.minor_radius,
        semi_angle=surface.semi_angle,
        degree=surface.degree,
        control_points=control_points,
        knots=surface.knots,
        weights=surface.weights,
    )


# ---------------------------------------------------------------------------
# Bounding box recomputation
# ---------------------------------------------------------------------------

def _recompute_aabb(
    bbox: BoundingBox3D,
    t: Transform3D,
) -> BoundingBox3D:
    """Transform all 8 corners of bbox and return new axis-aligned bounding box."""
    mn = bbox.min_point
    mx = bbox.max_point
    unit = mn.unit
    xs = (mn.x.value, mx.x.value)
    ys = (mn.y.value, mx.y.value)
    zs = (mn.z.value, mx.z.value)

    corners: list[tuple[Decimal, Decimal, Decimal]] = []
    for cx in xs:
        for cy in ys:
            for cz in zs:
                p = CanonicalPoint3D(
                    x=Quantity(value=cx, unit=unit),
                    y=Quantity(value=cy, unit=unit),
                    z=Quantity(value=cz, unit=unit),
                )
                tp = apply_transform_to_point(p, t)
                corners.append((tp.x.value, tp.y.value, tp.z.value))

    min_x = min(c[0] for c in corners)
    min_y = min(c[1] for c in corners)
    min_z = min(c[2] for c in corners)
    max_x = max(c[0] for c in corners)
    max_y = max(c[1] for c in corners)
    max_z = max(c[2] for c in corners)

    return BoundingBox3D(
        min_point=CanonicalPoint3D(
            x=Quantity(value=min_x, unit=unit),
            y=Quantity(value=min_y, unit=unit),
            z=Quantity(value=min_z, unit=unit),
        ),
        max_point=CanonicalPoint3D(
            x=Quantity(value=max_x, unit=unit),
            y=Quantity(value=max_y, unit=unit),
            z=Quantity(value=max_z, unit=unit),
        ),
    )


# ---------------------------------------------------------------------------
# Geometry transform
# ---------------------------------------------------------------------------

def apply_transform_to_geometry(
    geometry: CanonicalGeometry,
    transform: Transform3D,
    *,
    source_ref: str = "stage4f::geometry",
) -> GeometryNormalizationResult:
    """Apply a rigid Transform3D to a CanonicalGeometry.

    All curves and surfaces have their positional fields transformed.
    Scalar dimensions (radius, semi_angle) are unchanged.
    Bounding box is recomputed from 8 transformed corners.
    geometry_id is preserved.

    Args:
        geometry:   Source canonical geometry.
        transform:  Rigid body transform.
        source_ref: Provenance source_reference string.

    Returns:
        GeometryNormalizationResult — always.
    """
    if not isinstance(geometry, CanonicalGeometry):
        raise ValidationError("geometry must be a CanonicalGeometry")
    if not isinstance(transform, Transform3D):
        raise ValidationError("transform must be a Transform3D")

    provenance = Provenance(
        source_type=ProvenanceType.USER_INPUT,
        source_reference=source_ref,
        source_document=geometry.geometry_id,
        notes="Stage 4F rigid transform applied",
    )
    diagnostics: list[NormalizationDiagnostic] = []

    # Transform curves
    transformed_curves: list = []
    for curve in geometry.ordered_curves:
        try:
            transformed_curves.append(_transform_curve(curve, transform))
        except (ValidationError, Exception) as exc:
            diagnostics.append(NormalizationDiagnostic(
                severity="ERROR",
                message=f"curve {curve.curve_id!r}: {exc}",
                entity_id=curve.curve_id,
            ))

    # Transform surfaces
    transformed_surfaces: list = []
    for surface in geometry.ordered_surfaces:
        try:
            transformed_surfaces.append(_transform_surface(surface, transform))
        except (ValidationError, Exception) as exc:
            diagnostics.append(NormalizationDiagnostic(
                severity="ERROR",
                message=f"surface {surface.surface_id!r}: {exc}",
                entity_id=surface.surface_id,
            ))

    # Bounding box
    new_bbox: BoundingBox3D | None = None
    if geometry.bounding_box is not None:
        try:
            new_bbox = _recompute_aabb(geometry.bounding_box, transform)
        except (ValidationError, Exception) as exc:
            diagnostics.append(NormalizationDiagnostic(
                severity="WARNING",
                message=f"bounding_box recomputation failed: {exc}",
            ))

    has_error = any(d.severity == "ERROR" for d in diagnostics)

    if has_error and not transformed_curves and not transformed_surfaces:
        return GeometryNormalizationResult(
            source_geometry_id=geometry.geometry_id,
            output_geometry=None,
            applied_transform=transform,
            is_lossless=False,
            diagnostics=tuple(diagnostics),
            provenance=provenance,
        )

    try:
        output = CanonicalGeometry(
            geometry_id=geometry.geometry_id,
            curves=tuple(transformed_curves),
            surfaces=tuple(transformed_surfaces),
            bounding_box=new_bbox,
            source_entity_ref=geometry.source_entity_ref,
        )
    except (ValidationError, GeometryContainerError, Exception) as exc:
        diagnostics.append(NormalizationDiagnostic(
            severity="ERROR",
            message=f"CanonicalGeometry construction: {exc}",
        ))
        return GeometryNormalizationResult(
            source_geometry_id=geometry.geometry_id,
            output_geometry=None,
            applied_transform=transform,
            is_lossless=False,
            diagnostics=tuple(diagnostics),
            provenance=provenance,
        )

    is_lossless = not has_error
    return GeometryNormalizationResult(
        source_geometry_id=geometry.geometry_id,
        output_geometry=output,
        applied_transform=transform,
        is_lossless=is_lossless,
        diagnostics=tuple(diagnostics),
        provenance=provenance,
    )


# ---------------------------------------------------------------------------
# Unit normalization
# ---------------------------------------------------------------------------

_MM_PER_M = Decimal("1000")


def _convert_quantity_to_unit(q: Quantity, target: Unit) -> Quantity:
    """Convert a length Quantity to target unit. Only MM<->M supported."""
    if q.unit is target:
        return q
    if q.unit is Unit.MM and target is Unit.M:
        return Quantity(value=q.value / _MM_PER_M, unit=Unit.M)
    if q.unit is Unit.M and target is Unit.MM:
        return Quantity(value=q.value * _MM_PER_M, unit=Unit.MM)
    raise ValidationError(
        f"Unit conversion from {q.unit!r} to {target!r} is not supported"
    )


def _convert_point(p: CanonicalPoint3D, target: Unit) -> CanonicalPoint3D:
    if p.unit is target:
        return p
    return CanonicalPoint3D(
        x=_convert_quantity_to_unit(p.x, target),
        y=_convert_quantity_to_unit(p.y, target),
        z=_convert_quantity_to_unit(p.z, target),
    )


def _normalize_curve_units(curve: CanonicalCurve, target: Unit) -> CanonicalCurve:
    origin = _convert_point(curve.origin, target) if curve.origin is not None else None
    center = _convert_point(curve.center, target) if curve.center is not None else None
    radius = _convert_quantity_to_unit(curve.radius, target) if curve.radius is not None else None
    major_r = (
        _convert_quantity_to_unit(curve.major_radius, target)
        if curve.major_radius is not None else None
    )
    minor_r = (
        _convert_quantity_to_unit(curve.minor_radius, target)
        if curve.minor_radius is not None else None
    )
    cps = tuple(_convert_point(p, target) for p in curve.control_points)
    return CanonicalCurve(
        curve_id=curve.curve_id,
        curve_type=curve.curve_type,
        source_entity_ref=curve.source_entity_ref,
        origin=origin,
        direction=curve.direction,
        center=center,
        axis=curve.axis,
        radius=radius,
        major_radius=major_r,
        minor_radius=minor_r,
        degree=curve.degree,
        control_points=cps,
        knots=curve.knots,
        weights=curve.weights,
    )


def _normalize_surface_units(surface: CanonicalSurface, target: Unit) -> CanonicalSurface:
    origin = _convert_point(surface.origin, target) if surface.origin is not None else None
    center = _convert_point(surface.center, target) if surface.center is not None else None
    radius = (
        _convert_quantity_to_unit(surface.radius, target)
        if surface.radius is not None else None
    )
    major_r = (
        _convert_quantity_to_unit(surface.major_radius, target)
        if surface.major_radius is not None else None
    )
    minor_r = (
        _convert_quantity_to_unit(surface.minor_radius, target)
        if surface.minor_radius is not None else None
    )
    cps = tuple(_convert_point(p, target) for p in surface.control_points)
    return CanonicalSurface(
        surface_id=surface.surface_id,
        surface_type=surface.surface_type,
        source_entity_ref=surface.source_entity_ref,
        origin=origin,
        center=center,
        axis=surface.axis,
        normal=surface.normal,
        radius=radius,
        major_radius=major_r,
        minor_radius=minor_r,
        semi_angle=surface.semi_angle,
        degree=surface.degree,
        control_points=cps,
        knots=surface.knots,
        weights=surface.weights,
    )


def normalize_geometry_units(
    geometry: CanonicalGeometry,
    target_unit: Unit,
    *,
    source_ref: str = "stage4f::unit_normalization",
) -> GeometryNormalizationResult:
    """Convert all length coordinates in geometry to target_unit (MM or M).

    Dimensionless values (vectors, semi_angle, knots, weights) are unchanged.
    geometry_id is preserved.

    Args:
        geometry:    Source canonical geometry.
        target_unit: Target length unit (Unit.MM or Unit.M).
        source_ref:  Provenance source_reference string.

    Returns:
        GeometryNormalizationResult — always.
    """
    if not isinstance(geometry, CanonicalGeometry):
        raise ValidationError("geometry must be a CanonicalGeometry")
    if target_unit not in (Unit.MM, Unit.M):
        raise ValidationError(
            f"target_unit must be Unit.MM or Unit.M, got {target_unit!r}"
        )

    provenance = Provenance(
        source_type=ProvenanceType.USER_INPUT,
        source_reference=source_ref,
        source_document=geometry.geometry_id,
        notes=f"Stage 4F unit normalization to {target_unit!r}",
    )
    diagnostics: list[NormalizationDiagnostic] = []

    curves = []
    for curve in geometry.ordered_curves:
        try:
            curves.append(_normalize_curve_units(curve, target_unit))
        except (ValidationError, Exception) as exc:
            diagnostics.append(NormalizationDiagnostic(
                severity="ERROR",
                message=f"curve {curve.curve_id!r}: {exc}",
                entity_id=curve.curve_id,
            ))

    surfaces = []
    for surface in geometry.ordered_surfaces:
        try:
            surfaces.append(_normalize_surface_units(surface, target_unit))
        except (ValidationError, Exception) as exc:
            diagnostics.append(NormalizationDiagnostic(
                severity="ERROR",
                message=f"surface {surface.surface_id!r}: {exc}",
                entity_id=surface.surface_id,
            ))

    bbox: BoundingBox3D | None = None
    if geometry.bounding_box is not None:
        try:
            bbox = BoundingBox3D(
                min_point=_convert_point(geometry.bounding_box.min_point, target_unit),
                max_point=_convert_point(geometry.bounding_box.max_point, target_unit),
            )
        except (ValidationError, Exception) as exc:
            diagnostics.append(NormalizationDiagnostic(
                severity="WARNING",
                message=f"bounding_box conversion failed: {exc}",
            ))

    has_error = any(d.severity == "ERROR" for d in diagnostics)
    try:
        output = CanonicalGeometry(
            geometry_id=geometry.geometry_id,
            curves=tuple(curves),
            surfaces=tuple(surfaces),
            bounding_box=bbox,
            source_entity_ref=geometry.source_entity_ref,
        )
    except (ValidationError, Exception) as exc:
        diagnostics.append(NormalizationDiagnostic(
            severity="ERROR",
            message=f"CanonicalGeometry construction: {exc}",
        ))
        return GeometryNormalizationResult(
            source_geometry_id=geometry.geometry_id,
            output_geometry=None,
            applied_transform=None,
            is_lossless=False,
            diagnostics=tuple(diagnostics),
            provenance=provenance,
        )

    return GeometryNormalizationResult(
        source_geometry_id=geometry.geometry_id,
        output_geometry=output,
        applied_transform=None,
        is_lossless=not has_error,
        diagnostics=tuple(diagnostics),
        provenance=provenance,
    )


# ---------------------------------------------------------------------------
# Topology transform
# ---------------------------------------------------------------------------

def apply_transform_to_topology(
    topology: CanonicalTopology,
    transform: Transform3D,
    *,
    mode: TransformApplicationMode = TransformApplicationMode.BAKE_TRANSFORM,
    source_ref: str = "stage4f::topology",
) -> TopologyNormalizationResult:
    """Apply a rigid Transform3D to a CanonicalTopology.

    Vertex points are transformed. Edge/loop/face/shell/body references and
    IDs are unchanged (topology connectivity is preserved).

    Modes:
        BAKE_TRANSFORM      — vertex coordinates are updated; CanonicalBody.transform
                              is set to identity (None) on output bodies.
        PRESERVE_PLACEMENT  — vertex coordinates are NOT updated; the transform is
                              recorded in CanonicalBody.transform for each body;
                              topology geometry is returned unchanged.

    Args:
        topology:  Source canonical topology.
        transform: Rigid body transform to apply.
        mode:      Whether to bake or preserve body placement.
        source_ref: Provenance source_reference string.

    Returns:
        TopologyNormalizationResult — always.
    """
    if not isinstance(topology, CanonicalTopology):
        raise ValidationError("topology must be a CanonicalTopology")
    if not isinstance(transform, Transform3D):
        raise ValidationError("transform must be a Transform3D")
    if not isinstance(mode, TransformApplicationMode):
        raise ValidationError("mode must be a TransformApplicationMode")

    provenance = Provenance(
        source_type=ProvenanceType.USER_INPUT,
        source_reference=source_ref,
        source_document=topology.topology_id,
        notes=f"Stage 4F topology transform ({mode.value})",
    )
    diagnostics: list[NormalizationDiagnostic] = []

    if mode is TransformApplicationMode.PRESERVE_PLACEMENT:
        # Tag each body with the transform; geometry and vertices unchanged
        new_bodies = []
        for body in topology.bodies:
            new_bodies.append(CanonicalBody(
                body_id=body.body_id,
                body_type=body.body_type,
                shell_ids=body.shell_ids,
                bounding_box=body.bounding_box,
                transform=transform,
                source_entity_ref=body.source_entity_ref,
            ))
        try:
            out_topo = CanonicalTopology(
                topology_id=topology.topology_id,
                geometry=topology.geometry,
                vertices=topology.vertices,
                edges=topology.edges,
                loops=topology.loops,
                faces=topology.faces,
                shells=topology.shells,
                bodies=tuple(new_bodies),
                source_entity_ref=topology.source_entity_ref,
            )
        except (ValidationError, TopologyContainerError, Exception) as exc:
            diagnostics.append(NormalizationDiagnostic(
                severity="ERROR",
                message=f"CanonicalTopology construction: {exc}",
            ))
            return TopologyNormalizationResult(
                source_topology_id=topology.topology_id,
                output_topology=None,
                output_geometry=None,
                applied_transform=transform,
                transform_mode=mode,
                is_lossless=False,
                diagnostics=tuple(diagnostics),
                provenance=provenance,
            )
        return TopologyNormalizationResult(
            source_topology_id=topology.topology_id,
            output_topology=out_topo,
            output_geometry=None,
            applied_transform=transform,
            transform_mode=mode,
            is_lossless=True,
            diagnostics=tuple(diagnostics),
            provenance=provenance,
        )

    # BAKE_TRANSFORM: transform all vertex coordinates
    new_vertices = []
    for vertex in topology.vertices:
        try:
            new_pt = apply_transform_to_point(vertex.point, transform)
            new_vertices.append(CanonicalVertex(
                vertex_id=vertex.vertex_id,
                point=new_pt,
                source_entity_ref=vertex.source_entity_ref,
            ))
        except (ValidationError, Exception) as exc:
            diagnostics.append(NormalizationDiagnostic(
                severity="ERROR",
                message=f"vertex {vertex.vertex_id!r}: {exc}",
                entity_id=vertex.vertex_id,
            ))
            new_vertices.append(vertex)  # keep original on failure

    # Transform geometry if present
    new_geometry = topology.geometry
    if topology.geometry is not None:
        geo_result = apply_transform_to_geometry(topology.geometry, transform)
        if geo_result.succeeded:
            new_geometry = geo_result.output_geometry
        else:
            diagnostics.extend(geo_result.diagnostics)

    # Bodies: clear transform (it is now baked)
    new_bodies = []
    for body in topology.bodies:
        new_bodies.append(CanonicalBody(
            body_id=body.body_id,
            body_type=body.body_type,
            shell_ids=body.shell_ids,
            bounding_box=body.bounding_box,
            transform=None,  # baked
            source_entity_ref=body.source_entity_ref,
        ))

    has_error = any(d.severity == "ERROR" for d in diagnostics)

    try:
        out_topo = CanonicalTopology(
            topology_id=topology.topology_id,
            geometry=new_geometry,
            vertices=tuple(new_vertices),
            edges=topology.edges,
            loops=topology.loops,
            faces=topology.faces,
            shells=topology.shells,
            bodies=tuple(new_bodies),
            source_entity_ref=topology.source_entity_ref,
        )
    except (ValidationError, TopologyContainerError, Exception) as exc:
        diagnostics.append(NormalizationDiagnostic(
            severity="ERROR",
            message=f"CanonicalTopology construction: {exc}",
        ))
        return TopologyNormalizationResult(
            source_topology_id=topology.topology_id,
            output_topology=None,
            output_geometry=new_geometry,
            applied_transform=transform,
            transform_mode=mode,
            is_lossless=False,
            diagnostics=tuple(diagnostics),
            provenance=provenance,
        )

    return TopologyNormalizationResult(
        source_topology_id=topology.topology_id,
        output_topology=out_topo,
        output_geometry=new_geometry,
        applied_transform=transform,
        transform_mode=mode,
        is_lossless=not has_error,
        diagnostics=tuple(diagnostics),
        provenance=provenance,
    )
