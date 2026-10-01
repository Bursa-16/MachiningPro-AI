"""Canonical Geometry / Topology Population Bridge (Stage 4E).

Implements the deterministic bridge between the Stage 4D canonical exchange
layer and the Stage 4B canonical geometry / topology layer.

Live API imports
----------------
This module targets the live repository APIs exclusively:

From backend.interoperability.geometry:
    CanonicalCurveType      (not CurveType)
    CanonicalSurfaceType    (not SurfaceType)
    CanonicalPoint3D        coordinates are Quantity(value, Unit.MM or Unit.M)
    CanonicalVector3D       components are Quantity(value, Unit.DIMENSIONLESS)
    CanonicalCurve          radius/major_radius/minor_radius are Quantity
    CanonicalSurface        radius/major_radius/minor_radius/semi_angle are Quantity
    CanonicalGeometry       no length_unit field; unit is per-Quantity
    GeometryContainerError
    BoundingBox3D

From backend.interoperability.topology:
    Orientation             (not TopologyOrientation)
    ShellClosure            (not ShellClosureStatus)
    Transform3D             translation: tuple[Decimal,Decimal,Decimal]
                            rotation: tuple[Decimal,...] (9 elements or empty)
    CanonicalVertex
    CanonicalEdge           start_vertex_id != end_vertex_id enforced
    CanonicalLoop           requires >= 3 edges
    CanonicalFace
    CanonicalShell          field is ``closure: ShellClosure``
    CanonicalBody           optional ``transform: Transform3D``
    CanonicalTopology       geometry is optional; reference integrity validated
    TopologyContainerError

From backend.domain.units:
    Quantity(value: Decimal, unit: Unit)
    Unit.MM, Unit.M, Unit.DIMENSIONLESS

No stale names appear anywhere in this module.

Design principles
-----------------
* NO FABRICATION.
* Capability is never silently upgraded.
* Stage 4B validation is never bypassed.
* Deterministic: same input → same output.
* Transform3D is accepted as explicit input and stored on CanonicalBody.
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
from backend.interoperability.enums import CapabilityLevel
from backend.interoperability.exchange import (
    CanonicalExchangeDocument,
    ExchangeDocumentStatus,
)
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
    TopologyContainerError,
    Transform3D,
)

__all__ = [
    "PopulationStatus",
    "NormalizationEligibility",
    "PopulationDiagnostic",
    "GeometryPopulationRequest",
    "TopologyPopulationRequest",
    "PopulationResult",
    "CanonicalPopulationBridge",
    "check_eligibility",
]


# ---------------------------------------------------------------------------
# Status enumerations
# ---------------------------------------------------------------------------

class PopulationStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"


class NormalizationEligibility(StrEnum):
    ELIGIBLE_GEOMETRY = "ELIGIBLE_GEOMETRY"
    ELIGIBLE_TOPOLOGY = "ELIGIBLE_TOPOLOGY"
    ELIGIBLE_WIREFRAME = "ELIGIBLE_WIREFRAME"
    METADATA_ONLY = "METADATA_ONLY"
    INELIGIBLE_FAILED = "INELIGIBLE_FAILED"
    INELIGIBLE_UNSUPPORTED = "INELIGIBLE_UNSUPPORTED"


# ---------------------------------------------------------------------------
# Diagnostic
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class PopulationDiagnostic:
    severity: str
    message: str
    entity_ref: CanonicalEntityRef | None = None

    def __post_init__(self) -> None:
        _s = object.__setattr__
        _s(self, "severity", require_non_empty_str(self.severity, "severity"))
        _s(self, "message", require_non_empty_str(self.message, "message"))
        if self.entity_ref is not None and not isinstance(
            self.entity_ref, CanonicalEntityRef
        ):
            raise ValidationError("entity_ref must be a CanonicalEntityRef or None")

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Population requests
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class GeometryPopulationRequest:
    """Explicit, caller-supplied geometry data for population.

    Coordinate strategy: all point coordinates must be supplied as
    Quantity(value, Unit.MM) or Quantity(value, Unit.M).
    Vector components must be Quantity(value, Unit.DIMENSIONLESS).
    Dimensional values (radius, etc.) must be Quantity with a length Unit.

    ``curves`` and ``surfaces`` are tuples of spec dicts.  Each spec is
    a plain Python dict with typed values ready for live API construction.
    """

    geometry_id: str
    curves: tuple[dict, ...] = ()
    surfaces: tuple[dict, ...] = ()
    bounding_box_spec: dict | None = None
    source_entity_ref: CanonicalEntityRef | None = None

    def __post_init__(self) -> None:
        _s = object.__setattr__
        _s(self, "geometry_id", require_non_empty_str(self.geometry_id, "geometry_id"))
        _s(self, "curves", tuple(self.curves or ()))
        _s(self, "surfaces", tuple(self.surfaces or ()))


@dataclass(frozen=True, slots=True)
class TopologyPopulationRequest:
    """Explicit topology data for population.

    All values must be in the live API types.
    ``transform_spec`` is an optional dict with keys:
        translation: tuple[str|Decimal, str|Decimal, str|Decimal]
        rotation: tuple[str|Decimal, ...] (9 elements) or ()
    Applied to all bodies in body_specs when present.
    """

    topology_id: str
    geometry: CanonicalGeometry
    vertex_specs: tuple[dict, ...] = ()
    edge_specs: tuple[dict, ...] = ()
    loop_specs: tuple[dict, ...] = ()
    face_specs: tuple[dict, ...] = ()
    shell_specs: tuple[dict, ...] = ()
    body_specs: tuple[dict, ...] = ()
    source_entity_ref: CanonicalEntityRef | None = None

    def __post_init__(self) -> None:
        _s = object.__setattr__
        _s(self, "topology_id", require_non_empty_str(self.topology_id, "topology_id"))
        if not isinstance(self.geometry, CanonicalGeometry):
            raise ValidationError("geometry must be a CanonicalGeometry")
        for attr in ("vertex_specs", "edge_specs", "loop_specs",
                     "face_specs", "shell_specs", "body_specs"):
            _s(self, attr, tuple(getattr(self, attr) or ()))


# ---------------------------------------------------------------------------
# Population result
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class PopulationResult:
    population_id: str
    status: PopulationStatus
    eligibility: NormalizationEligibility
    geometry: CanonicalGeometry | None
    topology: CanonicalTopology | None
    diagnostics: tuple[PopulationDiagnostic, ...]
    provenance: Provenance
    source_exchange_id: str
    notes: str | None = None

    def __post_init__(self) -> None:
        _s = object.__setattr__
        _s(self, "population_id", require_non_empty_str(self.population_id, "population_id"))
        if not isinstance(self.status, PopulationStatus):
            raise ValidationError("status must be a PopulationStatus")
        if not isinstance(self.eligibility, NormalizationEligibility):
            raise ValidationError("eligibility must be a NormalizationEligibility")
        if self.geometry is not None and not isinstance(self.geometry, CanonicalGeometry):
            raise ValidationError("geometry must be a CanonicalGeometry or None")
        if self.topology is not None and not isinstance(self.topology, CanonicalTopology):
            raise ValidationError("topology must be a CanonicalTopology or None")
        for d in self.diagnostics:
            if not isinstance(d, PopulationDiagnostic):
                raise ValidationError("diagnostics entries must be PopulationDiagnostic")
        if not isinstance(self.provenance, Provenance):
            raise ValidationError("provenance must be a Provenance")
        _s(self, "source_exchange_id",
           require_non_empty_str(self.source_exchange_id, "source_exchange_id"))
        _s(self, "notes", optional_non_empty_str(self.notes, "notes"))

    @property
    def succeeded(self) -> bool:
        return self.status in (PopulationStatus.SUCCESS, PopulationStatus.PARTIAL)

    @property
    def error_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity == "ERROR")

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity == "WARNING")

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Eligibility check
# ---------------------------------------------------------------------------

def check_eligibility(ced: CanonicalExchangeDocument) -> NormalizationEligibility:
    """Determine whether a CED is eligible for geometry/topology population."""
    if ced.exchange_status is ExchangeDocumentStatus.UNAVAILABLE:
        return NormalizationEligibility.INELIGIBLE_FAILED

    levels = list(CapabilityLevel)
    level_idx = levels.index(ced.capability_level)
    normalized_idx = levels.index(CapabilityLevel.LEVEL_2_NORMALIZED)

    if level_idx < normalized_idx:
        return NormalizationEligibility.METADATA_ONLY

    entity_kinds = {ref.entity_kind for ref in ced.entity_refs}
    has_brep = any("BRep" in k or "Solid" in k or "Shell" in k for k in entity_kinds)
    has_surface = any("Surface" in k or "Face" in k for k in entity_kinds)
    has_curve = any(
        "Curve" in k or "Edge" in k or "Wire" in k or "Line" in k
        for k in entity_kinds
    )

    if has_brep or has_surface:
        return NormalizationEligibility.ELIGIBLE_GEOMETRY
    if has_curve:
        return NormalizationEligibility.ELIGIBLE_WIREFRAME
    return NormalizationEligibility.METADATA_ONLY


# ---------------------------------------------------------------------------
# ID helpers
# ---------------------------------------------------------------------------

def _population_id(ced_id: str, request_id: str) -> str:
    return f"pop::{ced_id}::{request_id}"


def _make_provenance(ced: CanonicalExchangeDocument, step: str) -> Provenance:
    return Provenance(
        source_type=ProvenanceType.USER_INPUT,
        source_reference=f"stage4e::{step}",
        source_document=ced.ced_id,
        notes=f"population from {ced.format_id} via {ced.adapter_id}",
    )


# ---------------------------------------------------------------------------
# Quantity builders (live API)
# ---------------------------------------------------------------------------

def _q_length(value: object, field_name: str) -> Quantity:
    """Build a length Quantity in Unit.MM from a numeric-like value."""
    if isinstance(value, Quantity):
        return value
    try:
        return Quantity.of(str(value), Unit.MM)
    except Exception as exc:
        raise ValidationError(
            f"{field_name}: cannot construct length Quantity from {value!r}: {exc}"
        ) from exc


def _q_dimensionless(value: object, field_name: str) -> Quantity:
    """Build a dimensionless Quantity from a numeric-like value."""
    if isinstance(value, Quantity):
        return value
    try:
        return Quantity.of(str(value), Unit.DIMENSIONLESS)
    except Exception as exc:
        raise ValidationError(
            f"{field_name}: cannot construct dimensionless Quantity from {value!r}: {exc}"
        ) from exc


def _build_point(spec: dict, prefix: str = "") -> CanonicalPoint3D:
    """Build a CanonicalPoint3D from spec with 'x', 'y', 'z' keys.

    Values must be Quantity(MM/M) or numeric-like (converted to MM).
    """
    try:
        return CanonicalPoint3D(
            x=_q_length(spec["x"], f"{prefix}x"),
            y=_q_length(spec["y"], f"{prefix}y"),
            z=_q_length(spec["z"], f"{prefix}z"),
        )
    except KeyError as exc:
        raise ValidationError(
            f"{prefix}point spec missing required key: {exc}"
        ) from exc


def _build_vector(spec: dict, prefix: str = "") -> CanonicalVector3D:
    """Build a CanonicalVector3D from spec with 'x', 'y', 'z' keys.

    Values must be Quantity(DIMENSIONLESS) or numeric-like.
    """
    try:
        return CanonicalVector3D(
            x=_q_dimensionless(spec["x"], f"{prefix}x"),
            y=_q_dimensionless(spec["y"], f"{prefix}y"),
            z=_q_dimensionless(spec["z"], f"{prefix}z"),
        )
    except KeyError as exc:
        raise ValidationError(
            f"{prefix}vector spec missing required key: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Curve and surface builders
# ---------------------------------------------------------------------------

def _resolve_curve_type(name: str) -> CanonicalCurveType:
    try:
        return CanonicalCurveType(name.upper())
    except ValueError:
        return CanonicalCurveType.UNKNOWN


def _resolve_surface_type(name: str) -> CanonicalSurfaceType:
    try:
        return CanonicalSurfaceType(name.upper())
    except ValueError:
        return CanonicalSurfaceType.UNKNOWN


def _build_curve(spec: dict) -> CanonicalCurve:
    cid = require_non_empty_str(str(spec["curve_id"]), "curve_id")
    ctype = _resolve_curve_type(str(spec.get("curve_type", "UNKNOWN")))
    origin = _build_point(spec["origin"], "origin.") if "origin" in spec else None
    direction = _build_vector(spec["direction"], "direction.") if "direction" in spec else None
    center = _build_point(spec["center"], "center.") if "center" in spec else None
    axis = _build_vector(spec["axis"], "axis.") if "axis" in spec else None
    radius = _q_length(spec["radius"], "radius") if "radius" in spec else None
    major_radius = (
        _q_length(spec["major_radius"], "major_radius") if "major_radius" in spec else None
    )
    minor_radius = (
        _q_length(spec["minor_radius"], "minor_radius") if "minor_radius" in spec else None
    )
    return CanonicalCurve(
        curve_id=cid,
        curve_type=ctype,
        origin=origin,
        direction=direction,
        center=center,
        axis=axis,
        radius=radius,
        major_radius=major_radius,
        minor_radius=minor_radius,
    )


def _build_surface(spec: dict) -> CanonicalSurface:
    sid = require_non_empty_str(str(spec["surface_id"]), "surface_id")
    stype = _resolve_surface_type(str(spec.get("surface_type", "UNKNOWN")))
    origin = _build_point(spec["origin"], "origin.") if "origin" in spec else None
    center = _build_point(spec["center"], "center.") if "center" in spec else None
    axis = _build_vector(spec["axis"], "axis.") if "axis" in spec else None
    normal = _build_vector(spec["normal"], "normal.") if "normal" in spec else None
    radius = _q_length(spec["radius"], "radius") if "radius" in spec else None
    major_radius = (
        _q_length(spec["major_radius"], "major_radius") if "major_radius" in spec else None
    )
    minor_radius = (
        _q_length(spec["minor_radius"], "minor_radius") if "minor_radius" in spec else None
    )
    semi_angle = (
        _q_dimensionless(spec["semi_angle"], "semi_angle") if "semi_angle" in spec else None
    )
    return CanonicalSurface(
        surface_id=sid,
        surface_type=stype,
        origin=origin,
        center=center,
        axis=axis,
        normal=normal,
        radius=radius,
        major_radius=major_radius,
        minor_radius=minor_radius,
        semi_angle=semi_angle,
    )


def _build_bounding_box(spec: dict) -> BoundingBox3D:
    return BoundingBox3D(
        min_point=_build_point(spec["min_point"], "min."),
        max_point=_build_point(spec["max_point"], "max."),
    )


# ---------------------------------------------------------------------------
# Topology builders
# ---------------------------------------------------------------------------

def _resolve_orientation(name: str | None) -> Orientation:
    if name is None:
        return Orientation.UNKNOWN
    try:
        return Orientation(name.upper())
    except ValueError:
        return Orientation.UNKNOWN


def _resolve_loop_type(name: str | None) -> LoopType:
    if name is None:
        return LoopType.UNKNOWN
    try:
        return LoopType(name.upper())
    except ValueError:
        return LoopType.UNKNOWN


def _resolve_shell_closure(name: str | None) -> ShellClosure:
    if name is None:
        return ShellClosure.UNKNOWN
    try:
        return ShellClosure(name.upper())
    except ValueError:
        return ShellClosure.UNKNOWN


def _resolve_body_type(name: str | None) -> BodyType:
    if name is None:
        return BodyType.UNKNOWN
    try:
        return BodyType(name.upper())
    except ValueError:
        return BodyType.UNKNOWN


def _build_transform(spec: dict) -> Transform3D:
    """Build a Transform3D from a spec dict.

    Expected keys:
        translation: sequence of 3 numeric-like values
        rotation:    sequence of 9 numeric-like values, or empty
    """
    t_raw = spec.get("translation", (0, 0, 0))
    r_raw = spec.get("rotation", ())
    translation = tuple(Decimal(str(v)) for v in t_raw)
    rotation = tuple(Decimal(str(v)) for v in r_raw)
    return Transform3D(translation=translation, rotation=rotation)


# ---------------------------------------------------------------------------
# Main bridge class
# ---------------------------------------------------------------------------

class CanonicalPopulationBridge:
    """Deterministic bridge: Stage 4D exchange layer → Stage 4B geometry/topology.

    Uses ONLY live repository APIs:
    - CanonicalCurveType / CanonicalSurfaceType (not CurveType/SurfaceType)
    - Quantity coordinates (not raw Decimal)
    - Orientation / ShellClosure (not TopologyOrientation/ShellClosureStatus)
    - Transform3D stored on CanonicalBody
    """

    # ------------------------------------------------------------------
    # Geometry population
    # ------------------------------------------------------------------

    def populate_geometry(
        self,
        ced: CanonicalExchangeDocument,
        request: GeometryPopulationRequest,
    ) -> PopulationResult:
        if not isinstance(ced, CanonicalExchangeDocument):
            raise ValidationError("ced must be a CanonicalExchangeDocument")
        if not isinstance(request, GeometryPopulationRequest):
            raise ValidationError("request must be a GeometryPopulationRequest")

        pop_id = _population_id(ced.ced_id, request.geometry_id)
        provenance = _make_provenance(ced, "geometry")
        eligibility = check_eligibility(ced)
        diagnostics: list[PopulationDiagnostic] = []

        if eligibility in (
            NormalizationEligibility.INELIGIBLE_FAILED,
            NormalizationEligibility.INELIGIBLE_UNSUPPORTED,
        ):
            return PopulationResult(
                population_id=pop_id,
                status=PopulationStatus.UNSUPPORTED,
                eligibility=eligibility,
                geometry=None,
                topology=None,
                diagnostics=(),
                provenance=provenance,
                source_exchange_id=ced.ced_id,
                notes=f"Not eligible for geometry population: {eligibility.value}",
            )

        if eligibility is NormalizationEligibility.METADATA_ONLY:
            if not request.curves and not request.surfaces:
                return PopulationResult(
                    population_id=pop_id,
                    status=PopulationStatus.INSUFFICIENT_DATA,
                    eligibility=eligibility,
                    geometry=None,
                    topology=None,
                    diagnostics=(
                        PopulationDiagnostic(
                            severity="INFO",
                            message=(
                                f"Import at {ced.capability_level.value} "
                                "(metadata only); no explicit geometry supplied. "
                                "No fabrication performed."
                            ),
                        ),
                    ),
                    provenance=provenance,
                    source_exchange_id=ced.ced_id,
                )
            diagnostics.append(PopulationDiagnostic(
                severity="WARNING",
                message=(
                    f"Exchange document is {eligibility.value}; "
                    "populating from caller-supplied explicit specs only."
                ),
            ))

        # Build curves
        built_curves: list[CanonicalCurve] = []
        for spec in request.curves:
            try:
                built_curves.append(_build_curve(spec))
            except (ValidationError, KeyError, Exception) as exc:
                diagnostics.append(PopulationDiagnostic(
                    severity="ERROR",
                    message=f"curve {spec.get('curve_id', '?')!r}: {exc}",
                ))

        # Build surfaces
        built_surfaces: list[CanonicalSurface] = []
        for spec in request.surfaces:
            try:
                built_surfaces.append(_build_surface(spec))
            except (ValidationError, KeyError, Exception) as exc:
                diagnostics.append(PopulationDiagnostic(
                    severity="ERROR",
                    message=f"surface {spec.get('surface_id', '?')!r}: {exc}",
                ))

        # Bounding box
        bbox: BoundingBox3D | None = None
        if request.bounding_box_spec:
            try:
                bbox = _build_bounding_box(request.bounding_box_spec)
            except (ValidationError, KeyError, Exception) as exc:
                diagnostics.append(PopulationDiagnostic(
                    severity="WARNING",
                    message=f"bounding_box: {exc}",
                ))

        has_error = any(d.severity == "ERROR" for d in diagnostics)
        total_req = len(request.curves) + len(request.surfaces)
        total_built = len(built_curves) + len(built_surfaces)

        if total_req > 0 and total_built == 0:
            return PopulationResult(
                population_id=pop_id,
                status=PopulationStatus.FAILED,
                eligibility=eligibility,
                geometry=None,
                topology=None,
                diagnostics=tuple(diagnostics),
                provenance=provenance,
                source_exchange_id=ced.ced_id,
            )

        try:
            geo = CanonicalGeometry(
                geometry_id=request.geometry_id,
                curves=tuple(built_curves),
                surfaces=tuple(built_surfaces),
                bounding_box=bbox,
            )
        except (ValidationError, GeometryContainerError, Exception) as exc:
            diagnostics.append(PopulationDiagnostic(
                severity="ERROR",
                message=f"CanonicalGeometry construction: {exc}",
            ))
            return PopulationResult(
                population_id=pop_id,
                status=PopulationStatus.FAILED,
                eligibility=eligibility,
                geometry=None,
                topology=None,
                diagnostics=tuple(diagnostics),
                provenance=provenance,
                source_exchange_id=ced.ced_id,
            )

        status = (
            PopulationStatus.PARTIAL
            if (has_error or total_built < total_req)
            else PopulationStatus.SUCCESS
        )

        return PopulationResult(
            population_id=pop_id,
            status=status,
            eligibility=eligibility,
            geometry=geo,
            topology=None,
            diagnostics=tuple(diagnostics),
            provenance=provenance,
            source_exchange_id=ced.ced_id,
        )

    # ------------------------------------------------------------------
    # Topology population
    # ------------------------------------------------------------------

    def populate_topology(
        self,
        ced: CanonicalExchangeDocument,
        request: TopologyPopulationRequest,
    ) -> PopulationResult:
        if not isinstance(ced, CanonicalExchangeDocument):
            raise ValidationError("ced must be a CanonicalExchangeDocument")
        if not isinstance(request, TopologyPopulationRequest):
            raise ValidationError("request must be a TopologyPopulationRequest")

        pop_id = _population_id(ced.ced_id, request.topology_id)
        provenance = _make_provenance(ced, "topology")
        eligibility = check_eligibility(ced)
        diagnostics: list[PopulationDiagnostic] = []

        if eligibility is NormalizationEligibility.INELIGIBLE_FAILED:
            return PopulationResult(
                population_id=pop_id,
                status=PopulationStatus.INSUFFICIENT_DATA,
                eligibility=eligibility,
                geometry=None,
                topology=None,
                diagnostics=(
                    PopulationDiagnostic(
                        severity="INFO",
                        message="Import failed; topology population impossible.",
                    ),
                ),
                provenance=provenance,
                source_exchange_id=ced.ced_id,
            )

        if eligibility is NormalizationEligibility.METADATA_ONLY and not (
            request.vertex_specs or request.edge_specs
        ):
            return PopulationResult(
                population_id=pop_id,
                status=PopulationStatus.INSUFFICIENT_DATA,
                eligibility=eligibility,
                geometry=None,
                topology=None,
                diagnostics=(
                    PopulationDiagnostic(
                        severity="INFO",
                        message=(
                            f"Import at {eligibility.value}; "
                            "no explicit vertex/edge data supplied."
                        ),
                    ),
                ),
                provenance=provenance,
                source_exchange_id=ced.ced_id,
            )

        if eligibility is NormalizationEligibility.METADATA_ONLY:
            diagnostics.append(PopulationDiagnostic(
                severity="WARNING",
                message=(
                    "Exchange document is METADATA_ONLY; "
                    "populating topology from caller-supplied explicit specs only."
                ),
            ))

        # Build vertices
        vertices: list[CanonicalVertex] = []
        for spec in request.vertex_specs:
            try:
                pt = _build_point(spec, f"vertex {spec.get('vertex_id', '?')}.")
                vertices.append(CanonicalVertex(
                    vertex_id=require_non_empty_str(str(spec["vertex_id"]), "vertex_id"),
                    point=pt,
                ))
            except (ValidationError, KeyError, Exception) as exc:
                diagnostics.append(PopulationDiagnostic(
                    severity="ERROR",
                    message=f"vertex {spec.get('vertex_id', '?')!r}: {exc}",
                ))

        # Build edges
        edges: list[CanonicalEdge] = []
        for spec in request.edge_specs:
            try:
                edges.append(CanonicalEdge(
                    edge_id=require_non_empty_str(str(spec["edge_id"]), "edge_id"),
                    start_vertex_id=str(spec["start_vertex_id"]),
                    end_vertex_id=str(spec["end_vertex_id"]),
                    curve_id=str(spec["curve_id"]),
                    orientation=_resolve_orientation(spec.get("orientation")),
                ))
            except (ValidationError, KeyError, Exception) as exc:
                diagnostics.append(PopulationDiagnostic(
                    severity="ERROR",
                    message=f"edge {spec.get('edge_id', '?')!r}: {exc}",
                ))

        # Build loops (≥3 edges required by live API)
        loops: list[CanonicalLoop] = []
        for spec in request.loop_specs:
            try:
                loops.append(CanonicalLoop(
                    loop_id=require_non_empty_str(str(spec["loop_id"]), "loop_id"),
                    edge_ids=tuple(str(e) for e in spec["edge_ids"]),
                    loop_type=_resolve_loop_type(spec.get("loop_type")),
                    orientation=_resolve_orientation(spec.get("orientation")),
                ))
            except (ValidationError, KeyError, Exception) as exc:
                diagnostics.append(PopulationDiagnostic(
                    severity="ERROR",
                    message=f"loop {spec.get('loop_id', '?')!r}: {exc}",
                ))

        # Build faces
        faces: list[CanonicalFace] = []
        for spec in request.face_specs:
            try:
                faces.append(CanonicalFace(
                    face_id=require_non_empty_str(str(spec["face_id"]), "face_id"),
                    surface_id=str(spec["surface_id"]),
                    boundary_loop_ids=tuple(
                        str(lid) for lid in spec["boundary_loop_ids"]
                    ),
                    orientation=_resolve_orientation(spec.get("orientation")),
                ))
            except (ValidationError, KeyError, Exception) as exc:
                diagnostics.append(PopulationDiagnostic(
                    severity="ERROR",
                    message=f"face {spec.get('face_id', '?')!r}: {exc}",
                ))

        # Build shells — live API uses ``closure`` field (ShellClosure)
        shells: list[CanonicalShell] = []
        for spec in request.shell_specs:
            try:
                shells.append(CanonicalShell(
                    shell_id=require_non_empty_str(str(spec["shell_id"]), "shell_id"),
                    face_ids=tuple(str(fi) for fi in spec["face_ids"]),
                    closure=_resolve_shell_closure(spec.get("closure")),
                ))
            except (ValidationError, KeyError, Exception) as exc:
                diagnostics.append(PopulationDiagnostic(
                    severity="ERROR",
                    message=f"shell {spec.get('shell_id', '?')!r}: {exc}",
                ))

        # Build bodies — live API supports transform: Transform3D on CanonicalBody
        bodies: list[CanonicalBody] = []
        for spec in request.body_specs:
            try:
                transform: Transform3D | None = None
                if "transform" in spec and spec["transform"] is not None:
                    try:
                        transform = _build_transform(spec["transform"])
                    except (ValidationError, Exception) as t_exc:
                        diagnostics.append(PopulationDiagnostic(
                            severity="WARNING",
                            message=(
                                f"body {spec.get('body_id', '?')!r} transform: "
                                f"{t_exc} — stored without transform"
                            ),
                        ))
                bodies.append(CanonicalBody(
                    body_id=require_non_empty_str(str(spec["body_id"]), "body_id"),
                    body_type=_resolve_body_type(spec.get("body_type")),
                    shell_ids=tuple(str(s) for s in spec["shell_ids"]),
                    transform=transform,
                ))
            except (ValidationError, KeyError, Exception) as exc:
                diagnostics.append(PopulationDiagnostic(
                    severity="ERROR",
                    message=f"body {spec.get('body_id', '?')!r}: {exc}",
                ))

        has_error = any(d.severity == "ERROR" for d in diagnostics)

        if not vertices and not edges and not request.vertex_specs and not request.edge_specs:
            return PopulationResult(
                population_id=pop_id,
                status=PopulationStatus.INSUFFICIENT_DATA,
                eligibility=eligibility,
                geometry=None,
                topology=None,
                diagnostics=tuple(diagnostics),
                provenance=provenance,
                source_exchange_id=ced.ced_id,
                notes="No vertex/edge data; topology not populated.",
            )

        try:
            topo = CanonicalTopology(
                topology_id=request.topology_id,
                geometry=request.geometry,
                vertices=tuple(vertices),
                edges=tuple(edges),
                loops=tuple(loops),
                faces=tuple(faces),
                shells=tuple(shells),
                bodies=tuple(bodies),
            )
        except (ValidationError, TopologyContainerError, Exception) as exc:
            diagnostics.append(PopulationDiagnostic(
                severity="ERROR",
                message=f"CanonicalTopology construction: {exc}",
            ))
            return PopulationResult(
                population_id=pop_id,
                status=PopulationStatus.FAILED,
                eligibility=eligibility,
                geometry=None,
                topology=None,
                diagnostics=tuple(diagnostics),
                provenance=provenance,
                source_exchange_id=ced.ced_id,
            )

        return PopulationResult(
            population_id=pop_id,
            status=PopulationStatus.PARTIAL if has_error else PopulationStatus.SUCCESS,
            eligibility=eligibility,
            geometry=None,
            topology=topo,
            diagnostics=tuple(diagnostics),
            provenance=provenance,
            source_exchange_id=ced.ced_id,
        )
