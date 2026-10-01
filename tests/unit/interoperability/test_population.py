"""Stage 4E: Canonical geometry/topology population bridge tests.

Targets live repository APIs exclusively:
    CanonicalCurveType / CanonicalSurfaceType (not CurveType/SurfaceType)
    Orientation / ShellClosure (not TopologyOrientation/ShellClosureStatus)
    Quantity coordinates (not raw Decimal)
    Transform3D with Decimal translation/rotation
    GeometryContainerError / TopologyContainerError
    CanonicalLoop requires >= 3 edges
    CanonicalEdge requires distinct start/end vertices
    CanonicalShell uses field ``closure`` (not ``closure_status``)
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.domain.base import Provenance
from backend.domain.exceptions import ValidationError
from backend.domain.units import Quantity, Unit
from backend.interoperability.enums import (
    CapabilityLevel,
    FormatFamily,
    NormalizationStatus,
)
from backend.interoperability.exchange import (
    CanonicalExchangeDocument,
    ExchangeDocumentStatus,
    build_exchange_document,
)
from backend.interoperability.geometry import (
    CanonicalCurveType,
    CanonicalGeometry,
    CanonicalSurfaceType,
    GeometryContainerError,
)
from backend.interoperability.models import (
    CanonicalEntityRef,
    EngineeringSource,
)
from backend.interoperability.orchestrator import CadImportOrchestrator
from backend.interoperability.population import (
    CanonicalPopulationBridge,
    GeometryPopulationRequest,
    NormalizationEligibility,
    PopulationResult,
    PopulationStatus,
    TopologyPopulationRequest,
    check_eligibility,
)
from backend.interoperability.topology import (
    BodyType,
    LoopType,
    Orientation,
    ShellClosure,
    TopologyContainerError,
    Transform3D,
)

# ---------------------------------------------------------------------------
# Quantity helpers
# ---------------------------------------------------------------------------

def _mm(v: str) -> Quantity:
    return Quantity.of(v, Unit.MM)


def _d1(v: str) -> Quantity:
    return Quantity.of(v, Unit.DIMENSIONLESS)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _make_ced(
    capability_level: CapabilityLevel = CapabilityLevel.LEVEL_1_PARSED,
    status: ExchangeDocumentStatus = ExchangeDocumentStatus.READY,
    entity_refs: tuple[CanonicalEntityRef, ...] = (),
    format_id: str = "STEP-AP242",
    adapter_id: str = "test-adapter",
    source_id: str = "SRC-001",
    is_lossless: bool = False,
) -> CanonicalExchangeDocument:
    return CanonicalExchangeDocument(
        ced_id=f"ced::import::{source_id}::{adapter_id}",
        exchange_status=status,
        source_id=source_id,
        format_id=format_id,
        adapter_id=adapter_id,
        capability_level=capability_level,
        normalization_status=NormalizationStatus.SUCCESS,
        entity_count=len(entity_refs),
        entity_refs=entity_refs,
        canonical_document=None,
        is_lossless=is_lossless,
        summary="test CED",
    )


def _metadata_only_ced(source_id: str = "SRC-001") -> CanonicalExchangeDocument:
    return _make_ced(
        capability_level=CapabilityLevel.LEVEL_1_PARSED,
        entity_refs=(
            CanonicalEntityRef(entity_id="HDR-001", entity_kind="StepHeader",
                               metadata={"entity_count": 3}),
        ),
        source_id=source_id,
    )


def _level2_ced_surfaces(source_id: str = "SRC-001") -> CanonicalExchangeDocument:
    return _make_ced(
        capability_level=CapabilityLevel.LEVEL_2_NORMALIZED,
        entity_refs=(
            CanonicalEntityRef(entity_id="SURF-001", entity_kind="CanonicalSurface"),
        ),
        source_id=source_id,
        is_lossless=True,
    )


def _failed_ced(source_id: str = "SRC-FAILED") -> CanonicalExchangeDocument:
    return _make_ced(
        capability_level=CapabilityLevel.LEVEL_0_RECOGNIZED,
        status=ExchangeDocumentStatus.UNAVAILABLE,
        source_id=source_id,
    )


def _bridge() -> CanonicalPopulationBridge:
    return CanonicalPopulationBridge()


def _empty_geo_req(geo_id: str = "GEO-001") -> GeometryPopulationRequest:
    return GeometryPopulationRequest(geometry_id=geo_id)


def _minimal_geo() -> CanonicalGeometry:
    """A geometry with one curve and one surface for topology tests."""
    from backend.interoperability.geometry import CanonicalCurve, CanonicalSurface
    return CanonicalGeometry(
        geometry_id="GEO-TOPO",
        curves=(CanonicalCurve(curve_id="C-001", curve_type=CanonicalCurveType.LINE),),
        surfaces=(CanonicalSurface(surface_id="S-001", surface_type=CanonicalSurfaceType.PLANE),),
    )


# ---------------------------------------------------------------------------
# A. Eligibility
# ---------------------------------------------------------------------------

class TestEligibility:
    def test_failed_ced_ineligible(self) -> None:
        ced = _failed_ced()
        assert check_eligibility(ced) is NormalizationEligibility.INELIGIBLE_FAILED

    def test_level1_metadata_only(self) -> None:
        ced = _metadata_only_ced()
        assert check_eligibility(ced) is NormalizationEligibility.METADATA_ONLY

    def test_level0_metadata_only(self) -> None:
        ced = _make_ced(capability_level=CapabilityLevel.LEVEL_0_RECOGNIZED)
        assert check_eligibility(ced) is NormalizationEligibility.METADATA_ONLY

    def test_level2_surface_entities_eligible_geometry(self) -> None:
        ced = _level2_ced_surfaces()
        assert check_eligibility(ced) is NormalizationEligibility.ELIGIBLE_GEOMETRY

    def test_level2_curve_entities_eligible_wireframe(self) -> None:
        ced = _make_ced(
            capability_level=CapabilityLevel.LEVEL_2_NORMALIZED,
            entity_refs=(CanonicalEntityRef(entity_id="C-001", entity_kind="CanonicalCurve"),),
        )
        assert check_eligibility(ced) is NormalizationEligibility.ELIGIBLE_WIREFRAME

    def test_deterministic(self) -> None:
        ced = _metadata_only_ced()
        assert check_eligibility(ced) == check_eligibility(ced)

    def test_ready_not_failed(self) -> None:
        ced = _metadata_only_ced()
        elig = check_eligibility(ced)
        assert elig is not NormalizationEligibility.INELIGIBLE_FAILED


# ---------------------------------------------------------------------------
# B. Geometry — eligibility gating
# ---------------------------------------------------------------------------

class TestGeometryEligibilityGating:
    def test_metadata_only_no_specs_insufficient(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        result = b.populate_geometry(ced, _empty_geo_req())
        assert result.status is PopulationStatus.INSUFFICIENT_DATA
        assert result.geometry is None

    def test_failed_ced_unsupported(self) -> None:
        b = _bridge()
        ced = _failed_ced()
        result = b.populate_geometry(ced, _empty_geo_req())
        assert result.status is PopulationStatus.UNSUPPORTED
        assert result.geometry is None

    def test_always_returns_population_result(self) -> None:
        b = _bridge()
        result = b.populate_geometry(_metadata_only_ced(), _empty_geo_req())
        assert isinstance(result, PopulationResult)

    def test_insufficient_has_info_diagnostic(self) -> None:
        b = _bridge()
        result = b.populate_geometry(_metadata_only_ced(), _empty_geo_req())
        assert any(d.severity == "INFO" for d in result.diagnostics)


# ---------------------------------------------------------------------------
# C. Geometry — Quantity coordinates (live API)
# ---------------------------------------------------------------------------

class TestGeometryQuantityCoordinates:
    def test_plane_surface_with_quantity_origin(self) -> None:
        """Origin must be Quantity(MM) not raw Decimal."""
        b = _bridge()
        ced = _metadata_only_ced()
        req = GeometryPopulationRequest(
            geometry_id="GEO-001",
            surfaces=({"surface_id": "S-001", "surface_type": "PLANE",
                       "origin": {"x": "0", "y": "0", "z": "0"},
                       "normal": {"x": "0", "y": "0", "z": "1"}},),
        )
        result = b.populate_geometry(ced, req)
        assert result.geometry is not None
        s = result.geometry.surfaces[0]
        assert s.surface_type is CanonicalSurfaceType.PLANE
        # origin and normal are Quantity-based
        assert s.origin.x.unit is Unit.MM
        assert s.normal.x.unit is Unit.DIMENSIONLESS

    def test_cylinder_with_quantity_radius(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        req = GeometryPopulationRequest(
            geometry_id="GEO-001",
            surfaces=({"surface_id": "S-CYL", "surface_type": "CYLINDER",
                       "radius": "5.0"},),
        )
        result = b.populate_geometry(ced, req)
        assert result.geometry is not None
        s = result.geometry.surfaces[0]
        assert s.surface_type is CanonicalSurfaceType.CYLINDER
        # radius is a Quantity with MM unit
        assert isinstance(s.radius, Quantity)
        assert s.radius.unit is Unit.MM
        from decimal import Decimal
        assert s.radius.value == Decimal("5.0")

    def test_line_curve_with_quantity_direction(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        req = GeometryPopulationRequest(
            geometry_id="GEO-001",
            curves=({"curve_id": "C-001", "curve_type": "LINE",
                     "origin": {"x": "0", "y": "0", "z": "0"},
                     "direction": {"x": "1", "y": "0", "z": "0"}},),
        )
        result = b.populate_geometry(ced, req)
        assert result.geometry is not None
        c = result.geometry.curves[0]
        assert c.curve_type is CanonicalCurveType.LINE
        assert c.origin.x.unit is Unit.MM
        assert c.direction.x.unit is Unit.DIMENSIONLESS

    def test_circle_with_quantity_radius(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        req = GeometryPopulationRequest(
            geometry_id="GEO-001",
            curves=({"curve_id": "C-CIRCLE", "curve_type": "CIRCLE",
                     "center": {"x": "0", "y": "0", "z": "0"},
                     "axis": {"x": "0", "y": "0", "z": "1"},
                     "radius": "25.0"},),
        )
        result = b.populate_geometry(ced, req)
        assert result.geometry is not None
        c = result.geometry.curves[0]
        assert c.curve_type is CanonicalCurveType.CIRCLE
        assert isinstance(c.radius, Quantity)
        assert c.radius.unit is Unit.MM

    def test_torus_major_minor_radius_quantity(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        req = GeometryPopulationRequest(
            geometry_id="GEO-001",
            surfaces=({"surface_id": "S-TOR", "surface_type": "TORUS",
                       "major_radius": "20.0",
                       "minor_radius": "5.0"},),
        )
        result = b.populate_geometry(ced, req)
        assert result.geometry is not None
        s = result.geometry.surfaces[0]
        assert isinstance(s.major_radius, Quantity)
        assert isinstance(s.minor_radius, Quantity)
        assert s.major_radius.unit is Unit.MM

    def test_cylinder_is_not_classified_as_hole(self) -> None:
        """Core principle: geometry ≠ manufacturing feature."""
        b = _bridge()
        ced = _metadata_only_ced()
        req = GeometryPopulationRequest(
            geometry_id="GEO-001",
            surfaces=({"surface_id": "S-CYL", "surface_type": "CYLINDER",
                       "radius": "5.0"},),
        )
        result = b.populate_geometry(ced, req)
        assert result.geometry is not None
        s = result.geometry.surfaces[0]
        assert s.surface_type is CanonicalSurfaceType.CYLINDER
        assert not hasattr(s, "is_hole")
        assert not hasattr(s, "feature_type")

    def test_negative_radius_fails(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        req = GeometryPopulationRequest(
            geometry_id="GEO-001",
            surfaces=({"surface_id": "S-BAD", "surface_type": "CYLINDER",
                       "radius": "-5.0"},),
        )
        result = b.populate_geometry(ced, req)
        assert result.status is PopulationStatus.FAILED
        assert result.geometry is None

    def test_invalid_curve_spec_skipped_partial(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        req = GeometryPopulationRequest(
            geometry_id="GEO-001",
            curves=(
                {"curve_id": "C-GOOD", "curve_type": "LINE"},
                {"MISSING_REQUIRED": True},  # no curve_id
            ),
        )
        result = b.populate_geometry(ced, req)
        assert result.status is PopulationStatus.PARTIAL
        assert result.geometry is not None
        assert result.error_count >= 1

    def test_geometry_id_preserved(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        req = GeometryPopulationRequest(
            geometry_id="MY-GEO-999",
            surfaces=({"surface_id": "S-001", "surface_type": "PLANE"},),
        )
        result = b.populate_geometry(ced, req)
        assert result.geometry is not None
        assert result.geometry.geometry_id == "MY-GEO-999"

    def test_deterministic(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        req = GeometryPopulationRequest(
            geometry_id="GEO-001",
            surfaces=({"surface_id": "S-001", "surface_type": "PLANE"},),
        )
        r1 = b.populate_geometry(ced, req)
        r2 = b.populate_geometry(ced, req)
        assert r1.status == r2.status
        if r1.geometry:
            assert ([s.surface_id for s in r1.geometry.surfaces] ==
                    [s.surface_id for s in r2.geometry.surfaces])


# ---------------------------------------------------------------------------
# D. Geometry — bounding box
# ---------------------------------------------------------------------------

class TestBoundingBox:
    def test_bounding_box_quantity_coordinates(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        req = GeometryPopulationRequest(
            geometry_id="GEO-001",
            surfaces=({"surface_id": "S-001", "surface_type": "PLANE"},),
            bounding_box_spec={
                "min_point": {"x": "0", "y": "0", "z": "0"},
                "max_point": {"x": "10", "y": "20", "z": "30"},
            },
        )
        result = b.populate_geometry(ced, req)
        assert result.geometry is not None
        bb = result.geometry.bounding_box
        assert bb is not None
        assert bb.size_x.value == Decimal("10")
        assert bb.size_x.unit is Unit.MM


# ---------------------------------------------------------------------------
# E. Topology — explicit connectivity (live API)
# ---------------------------------------------------------------------------

class TestTopologyExplicit:
    def test_metadata_only_no_specs_insufficient(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        geo = _minimal_geo()
        req = TopologyPopulationRequest(topology_id="TOPO-001", geometry=geo)
        result = b.populate_topology(ced, req)
        assert result.status is PopulationStatus.INSUFFICIENT_DATA

    def test_explicit_vertices_and_edges(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        geo = _minimal_geo()
        req = TopologyPopulationRequest(
            topology_id="TOPO-001",
            geometry=geo,
            vertex_specs=(
                {"vertex_id": "V-001", "x": "0", "y": "0", "z": "0"},
                {"vertex_id": "V-002", "x": "10", "y": "0", "z": "0"},
            ),
            edge_specs=(
                {"edge_id": "E-001", "start_vertex_id": "V-001",
                 "end_vertex_id": "V-002", "curve_id": "C-001"},
            ),
        )
        result = b.populate_topology(ced, req)
        assert result.topology is not None
        assert len(result.topology.vertices) == 2
        assert len(result.topology.edges) == 1

    def test_vertex_coordinates_are_quantity(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        geo = _minimal_geo()
        req = TopologyPopulationRequest(
            topology_id="TOPO-001",
            geometry=geo,
            vertex_specs=(
                {"vertex_id": "V-001", "x": "5", "y": "3", "z": "1"},
                {"vertex_id": "V-002", "x": "10", "y": "0", "z": "0"},
            ),
            edge_specs=(
                {"edge_id": "E-001", "start_vertex_id": "V-001",
                 "end_vertex_id": "V-002", "curve_id": "C-001"},
            ),
        )
        result = b.populate_topology(ced, req)
        assert result.topology is not None
        v = result.topology.get_vertex("V-001")
        assert isinstance(v.point.x, Quantity)
        assert v.point.x.unit is Unit.MM
        assert v.point.x.value == Decimal("5")

    def test_edge_same_vertex_fails(self) -> None:
        """Live API: edge start_vertex_id must differ from end_vertex_id."""
        b = _bridge()
        ced = _metadata_only_ced()
        geo = _minimal_geo()
        req = TopologyPopulationRequest(
            topology_id="TOPO-001",
            geometry=geo,
            vertex_specs=(
                {"vertex_id": "V-001", "x": "0", "y": "0", "z": "0"},
                {"vertex_id": "V-002", "x": "1", "y": "0", "z": "0"},
            ),
            edge_specs=(
                {"edge_id": "E-BAD", "start_vertex_id": "V-001",
                 "end_vertex_id": "V-001",  # same vertex
                 "curve_id": "C-001"},
            ),
        )
        result = b.populate_topology(ced, req)
        assert result.error_count >= 1

    def test_loop_requires_3_edges_live_api(self) -> None:
        """Live API: CanonicalLoop requires >= 3 edges."""
        b = _bridge()
        ced = _metadata_only_ced()
        geo = _minimal_geo()
        req = TopologyPopulationRequest(
            topology_id="TOPO-001",
            geometry=geo,
            vertex_specs=(
                {"vertex_id": "V-001", "x": "0", "y": "0", "z": "0"},
                {"vertex_id": "V-002", "x": "1", "y": "0", "z": "0"},
            ),
            edge_specs=(
                {"edge_id": "E-001", "start_vertex_id": "V-001",
                 "end_vertex_id": "V-002", "curve_id": "C-001"},
            ),
            loop_specs=(
                {"loop_id": "L-001", "edge_ids": ["E-001", "E-001B"]},  # only 2 edges
            ),
        )
        result = b.populate_topology(ced, req)
        # Loop with < 3 edges must fail
        assert result.error_count >= 1

    def test_orientation_is_live_orientation_enum(self) -> None:
        """Orientation (not TopologyOrientation) must be used."""
        b = _bridge()
        ced = _metadata_only_ced()
        geo = _minimal_geo()
        req = TopologyPopulationRequest(
            topology_id="TOPO-001",
            geometry=geo,
            vertex_specs=(
                {"vertex_id": "V-001", "x": "0", "y": "0", "z": "0"},
                {"vertex_id": "V-002", "x": "1", "y": "0", "z": "0"},
            ),
            edge_specs=(
                {"edge_id": "E-001", "start_vertex_id": "V-001",
                 "end_vertex_id": "V-002", "curve_id": "C-001",
                 "orientation": "FORWARD"},
            ),
        )
        result = b.populate_topology(ced, req)
        assert result.topology is not None
        e = result.topology.get_edge("E-001")
        assert e.orientation is Orientation.FORWARD

    def test_shell_uses_closure_field_not_closure_status(self) -> None:
        """Live CanonicalShell has field ``closure``, not ``closure_status``."""
        from backend.interoperability.topology import CanonicalShell
        sh = CanonicalShell(
            shell_id="SH-001",
            face_ids=("F-001",),
            closure=ShellClosure.CLOSED,
        )
        # Must have .closure, not .closure_status
        assert hasattr(sh, "closure")
        assert not hasattr(sh, "closure_status")
        assert sh.closure is ShellClosure.CLOSED

    def test_duplicate_vertex_fails(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        geo = _minimal_geo()
        req = TopologyPopulationRequest(
            topology_id="TOPO-001",
            geometry=geo,
            vertex_specs=(
                {"vertex_id": "V-DUP", "x": "0", "y": "0", "z": "0"},
                {"vertex_id": "V-DUP", "x": "1", "y": "0", "z": "0"},
            ),
        )
        result = b.populate_topology(ced, req)
        assert result.status is PopulationStatus.FAILED

    def test_dangling_edge_reference_fails(self) -> None:
        """Loop referencing a non-existent edge → TopologyContainerError → FAILED."""
        b = _bridge()
        ced = _metadata_only_ced()
        geo = _minimal_geo()
        req = TopologyPopulationRequest(
            topology_id="TOPO-001",
            geometry=geo,
            vertex_specs=(
                {"vertex_id": "V-001", "x": "0", "y": "0", "z": "0"},
                {"vertex_id": "V-002", "x": "1", "y": "0", "z": "0"},
            ),
            edge_specs=(
                {"edge_id": "E-001", "start_vertex_id": "V-001",
                 "end_vertex_id": "V-002", "curve_id": "C-001"},
            ),
            loop_specs=(
                {"loop_id": "L-001", "edge_ids": ["E-GHOST", "E-GHOST2", "E-GHOST3"]},
            ),
        )
        result = b.populate_topology(ced, req)
        assert result.status is PopulationStatus.FAILED

    def test_topology_deterministic(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        geo = _minimal_geo()
        req = TopologyPopulationRequest(
            topology_id="TOPO-001",
            geometry=geo,
            vertex_specs=(
                {"vertex_id": "V-Z", "x": "1", "y": "0", "z": "0"},
                {"vertex_id": "V-A", "x": "0", "y": "0", "z": "0"},
            ),
            edge_specs=(
                {"edge_id": "E-001", "start_vertex_id": "V-Z",
                 "end_vertex_id": "V-A", "curve_id": "C-001"},
            ),
        )
        r1 = b.populate_topology(ced, req)
        r2 = b.populate_topology(ced, req)
        assert r1.status == r2.status


# ---------------------------------------------------------------------------
# F. Transform3D
# ---------------------------------------------------------------------------

class TestTransform3D:
    def test_identity_transform(self) -> None:
        t = Transform3D()
        assert len(t.translation) == 3
        assert all(v == Decimal(0) for v in t.translation)
        assert len(t.rotation) == 0

    def test_explicit_translation(self) -> None:
        t = Transform3D(
            translation=(Decimal("10"), Decimal("20"), Decimal("30")),
        )
        assert t.translation[0] == Decimal("10")

    def test_full_rotation_matrix(self) -> None:
        identity = tuple(Decimal("1") if i in (0, 4, 8) else Decimal("0")
                         for i in range(9))
        t = Transform3D(
            translation=(Decimal("0"), Decimal("0"), Decimal("0")),
            rotation=identity,
        )
        assert len(t.rotation) == 9

    def test_wrong_rotation_size_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Transform3D(rotation=(Decimal("1"), Decimal("0")))  # 2 elements, not 9

    def test_non_decimal_translation_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Transform3D(translation=(1.0, 2.0, 3.0))  # float not Decimal

    def test_non_finite_translation_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Transform3D(translation=(Decimal("inf"), Decimal("0"), Decimal("0")))

    def test_transform_on_body(self) -> None:
        """Transform3D is stored on CanonicalBody.transform field."""
        b = _bridge()
        ced = _metadata_only_ced()
        geo = _minimal_geo()
        req = TopologyPopulationRequest(
            topology_id="TOPO-001",
            geometry=geo,
            vertex_specs=(
                {"vertex_id": "V-001", "x": "0", "y": "0", "z": "0"},
                {"vertex_id": "V-002", "x": "1", "y": "0", "z": "0"},
            ),
            edge_specs=(
                {"edge_id": "E-001", "start_vertex_id": "V-001",
                 "end_vertex_id": "V-002", "curve_id": "C-001"},
            ),
            shell_specs=(),
            body_specs=(
                {
                    "body_id": "B-001",
                    "body_type": "SOLID",
                    "shell_ids": [],  # no shells → body construction will fail
                    "transform": {
                        "translation": ("10", "0", "0"),
                        "rotation": (),
                    },
                },
            ),
        )
        result = b.populate_topology(ced, req)
        # Body with no shell_ids fails (empty) — recorded as ERROR
        assert result.error_count >= 1

    def test_transform_stored_on_body_when_valid(self) -> None:
        """When body has valid shells, transform is stored."""
        # Build a minimal valid topology manually and verify transform field
        from backend.interoperability.geometry import CanonicalCurve, CanonicalSurface
        from backend.interoperability.topology import (
            CanonicalBody,
            CanonicalEdge,
            CanonicalFace,
            CanonicalLoop,
            CanonicalShell,
            CanonicalTopology,
            CanonicalVertex,
        )
        geo = CanonicalGeometry(
            geometry_id="GEO-T",
            curves=(CanonicalCurve(curve_id="C-001", curve_type=CanonicalCurveType.LINE),),
            surfaces=(
                CanonicalSurface("S-001", surface_type=CanonicalSurfaceType.PLANE),
            ),
        )
        t = Transform3D(translation=(Decimal("5"), Decimal("0"), Decimal("0")))
        from backend.interoperability.geometry import CanonicalPoint3D as _CP3D
        v1 = CanonicalVertex("V-001", _CP3D(_mm("0"), _mm("0"), _mm("0")))
        v2 = CanonicalVertex("V-002", _CP3D(_mm("1"), _mm("0"), _mm("0")))
        v3 = CanonicalVertex("V-003", _CP3D(_mm("1"), _mm("1"), _mm("0")))
        e1 = CanonicalEdge("E-001", "V-001", "V-002", "C-001")
        e2 = CanonicalEdge("E-002", "V-002", "V-003", "C-001")
        e3 = CanonicalEdge("E-003", "V-003", "V-001", "C-001")
        lp = CanonicalLoop("L-001", ("E-001", "E-002", "E-003"), LoopType.OUTER)
        f = CanonicalFace("F-001", "S-001", ("L-001",))
        sh = CanonicalShell("SH-001", ("F-001",), closure=ShellClosure.CLOSED)
        body = CanonicalBody(
            body_id="B-001",
            body_type=BodyType.SOLID,
            shell_ids=("SH-001",),
            transform=t,
        )
        topo = CanonicalTopology(
            topology_id="TOPO-T",
            geometry=geo,
            vertices=(v1, v2, v3),
            edges=(e1, e2, e3),
            loops=(lp,),
            faces=(f,),
            shells=(sh,),
            bodies=(body,),
        )
        b_obj = topo.get_body("B-001")
        assert b_obj.transform is not None
        assert b_obj.transform.translation[0] == Decimal("5")


# ---------------------------------------------------------------------------
# G. Provenance
# ---------------------------------------------------------------------------

class TestProvenance:
    def test_provenance_is_provenance_object(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        result = b.populate_geometry(ced, _empty_geo_req())
        assert isinstance(result.provenance, Provenance)

    def test_source_exchange_id_matches_ced(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced("SRC-X")
        result = b.populate_geometry(ced, _empty_geo_req())
        assert result.source_exchange_id == ced.ced_id

    def test_provenance_references_ced_id(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        result = b.populate_geometry(ced, _empty_geo_req())
        assert ced.ced_id in (result.provenance.source_document or "")

    def test_stage4e_in_provenance_reference(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        result = b.populate_geometry(ced, _empty_geo_req())
        assert "stage4e" in (result.provenance.source_reference or "")

    def test_population_id_deterministic(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced("STABLE")
        req = _empty_geo_req()
        r1 = b.populate_geometry(ced, req)
        r2 = b.populate_geometry(ced, req)
        assert r1.population_id == r2.population_id

    def test_population_id_contains_ced_id(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        result = b.populate_geometry(ced, _empty_geo_req())
        assert ced.ced_id in result.population_id


# ---------------------------------------------------------------------------
# H. Fidelity — capability never upgraded
# ---------------------------------------------------------------------------

class TestFidelityPropagation:
    def test_metadata_only_no_geometry_produced(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        result = b.populate_geometry(ced, _empty_geo_req())
        assert result.geometry is None
        assert result.status in (
            PopulationStatus.INSUFFICIENT_DATA,
            PopulationStatus.UNSUPPORTED,
        )

    def test_failed_import_no_geometry(self) -> None:
        b = _bridge()
        ced = _failed_ced()
        result = b.populate_geometry(ced, _empty_geo_req())
        assert result.geometry is None

    def test_no_fabricated_coordinates(self) -> None:
        """Empty specs → no geometry; no placeholder zeros invented."""
        b = _bridge()
        ced = _metadata_only_ced()
        result = b.populate_geometry(ced, _empty_geo_req())
        assert result.geometry is None

    def test_result_immutable(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        result = b.populate_geometry(ced, _empty_geo_req())
        with pytest.raises((AttributeError, TypeError)):
            result.status = PopulationStatus.SUCCESS  # type: ignore[misc]


# ---------------------------------------------------------------------------
# I. GeometryContainerError / TopologyContainerError
# ---------------------------------------------------------------------------

class TestContainerErrors:
    def test_geometry_container_error_is_validation_error(self) -> None:
        from backend.domain.exceptions import ValidationError
        assert issubclass(GeometryContainerError, ValidationError)

    def test_topology_container_error_is_validation_error(self) -> None:
        from backend.domain.exceptions import ValidationError
        assert issubclass(TopologyContainerError, ValidationError)

    def test_geometry_container_error_on_missing_curve(self) -> None:
        geo = CanonicalGeometry(geometry_id="GEO-001")
        with pytest.raises(GeometryContainerError):
            geo.get_curve("MISSING")

    def test_topology_container_error_on_missing_vertex(self) -> None:
        from backend.interoperability.topology import CanonicalTopology
        topo = CanonicalTopology(topology_id="TOPO-001")
        with pytest.raises(TopologyContainerError):
            topo.get_vertex("MISSING")


# ---------------------------------------------------------------------------
# J. Stale-name scan
# ---------------------------------------------------------------------------

class TestStaleNameScan:
    def _code_lines(self) -> list[str]:
        """Return non-comment, non-docstring lines of production module."""
        import inspect

        import backend.interoperability.population as mod
        src = inspect.getsource(mod)
        code_lines = []
        in_docstring = False
        for line in src.splitlines():
            stripped = line.strip()
            # Toggle docstring state
            if stripped.startswith('"""') or stripped.startswith("'''"):
                count = stripped.count('"""') + stripped.count("'''")
                if count >= 2:
                    continue  # single-line docstring
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            # Skip comment lines
            if stripped.startswith("#"):
                continue
            code_lines.append(line)
        return code_lines

    def test_imports_use_canonical_curve_type(self) -> None:
        """Production imports use CanonicalCurveType, not CurveType."""
        from backend.interoperability.geometry import CanonicalCurveType
        from backend.interoperability.population import _resolve_curve_type
        result = _resolve_curve_type("LINE")
        assert result is CanonicalCurveType.LINE

    def test_imports_use_canonical_surface_type(self) -> None:
        """Production imports use CanonicalSurfaceType, not SurfaceType."""
        from backend.interoperability.geometry import CanonicalSurfaceType
        from backend.interoperability.population import _resolve_surface_type
        result = _resolve_surface_type("PLANE")
        assert result is CanonicalSurfaceType.PLANE

    def test_topology_orientation_not_imported(self) -> None:
        """Population module must not import TopologyOrientation."""
        import backend.interoperability.population as mod
        assert not hasattr(mod, "TopologyOrientation")

    def test_shell_closure_status_not_imported(self) -> None:
        """Population module must not import ShellClosureStatus."""
        import backend.interoperability.population as mod
        assert not hasattr(mod, "ShellClosureStatus")

    def test_no_neutral_geometry_in_production_module(self) -> None:
        import inspect

        import backend.interoperability.population as mod
        src = inspect.getsource(mod)
        assert "NEUTRAL_GEOMETRY" not in src

    def test_quantity_coordinates_used(self) -> None:
        """Coordinates must be Quantity, not raw Decimal."""
        import backend.interoperability.population as mod
        assert hasattr(mod, "_q_length")
        assert hasattr(mod, "_q_dimensionless")

    def test_orientation_enum_used(self) -> None:
        """Orientation (live enum) is imported and used."""
        import backend.interoperability.population as mod
        from backend.interoperability.topology import Orientation
        assert mod.Orientation is Orientation

    def test_shell_closure_enum_used(self) -> None:
        """ShellClosure (live enum) is imported and used."""
        import backend.interoperability.population as mod
        from backend.interoperability.topology import ShellClosure
        assert mod.ShellClosure is ShellClosure


# ---------------------------------------------------------------------------
# K. Stage 4A–4D regression
# ---------------------------------------------------------------------------

class TestStage4Regression:
    def test_orchestrated_import_ced_eligible_check(self) -> None:
        content = (
            "ISO-10303-21;\nHEADER;\n"
            "FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));\n"
            "ENDSEC;\nDATA;\n#1=PRODUCT('P','P','',(#2));\nENDSEC;\nEND-ISO-10303-21;\n"
        )
        src = EngineeringSource(source_id="REG-SRC", source_format_id="STEP-AP242",
                                notes=content)
        orc = CadImportOrchestrator()
        result = orc.import_source(src)
        ced = build_exchange_document(result)
        elig = check_eligibility(ced)
        assert elig is NormalizationEligibility.METADATA_ONLY

    def test_format_family_neutral_exchange_preserved(self) -> None:
        assert hasattr(FormatFamily, "NEUTRAL_EXCHANGE")
        assert not hasattr(FormatFamily, "NEUTRAL_GEOMETRY")

    def test_canonical_curve_type_not_curve_type(self) -> None:
        from backend.interoperability.geometry import CanonicalCurveType
        assert hasattr(CanonicalCurveType, "LINE")
        # Old name must not exist
        try:
            from backend.interoperability.geometry import CurveType
            # If it imports, it must only be an alias
            assert CurveType is CanonicalCurveType, "CurveType must not be a separate class"
        except ImportError:
            pass  # correct: CurveType doesn't exist

    def test_orientation_not_topology_orientation(self) -> None:
        from backend.interoperability.topology import Orientation
        assert hasattr(Orientation, "FORWARD")
        assert hasattr(Orientation, "UNKNOWN")

    def test_shell_closure_not_shell_closure_status(self) -> None:
        from backend.interoperability.topology import ShellClosure
        assert hasattr(ShellClosure, "CLOSED")
        assert hasattr(ShellClosure, "UNKNOWN")

    def test_transform3d_exists_in_topology(self) -> None:
        from backend.interoperability.topology import Transform3D
        t = Transform3D()
        assert len(t.translation) == 3

    def test_geometry_container_error_exists(self) -> None:
        assert issubclass(GeometryContainerError, Exception)

    def test_topology_container_error_exists(self) -> None:
        assert issubclass(TopologyContainerError, Exception)

    def test_modules_import_without_error(self) -> None:
        import backend.interoperability.exchange  # noqa: F401
        import backend.interoperability.orchestrator  # noqa: F401
        import backend.interoperability.population  # noqa: F401

    def test_population_result_frozen(self) -> None:
        b = _bridge()
        ced = _metadata_only_ced()
        result = b.populate_geometry(ced, _empty_geo_req())
        with pytest.raises((AttributeError, TypeError)):
            result.status = PopulationStatus.SUCCESS  # type: ignore[misc]
