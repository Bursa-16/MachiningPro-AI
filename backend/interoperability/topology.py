"""Vendor-neutral canonical topology model (Stage 4B).

Establishes the deterministic, immutable, vendor-neutral topological
entities (vertex, edge, loop, face, shell, body) and the topology
container that future format adapters will populate.

Stage 4B provides DATA MODELS + VALIDATION only.  No parsing, no kernel,
no manifold proof, no Boolean operations, no feature recognition.

Architecture position
---------------------

    SOURCE FORMAT
        ↓
    FORMAT ADAPTER / PARSER (Stage 4C+)
        ↓
    CANONICAL ENGINEERING REPRESENTATION (CER)   ← Stage 4A
        ↓
    CANONICAL GEOMETRY                            (sibling module: geometry)
        ↓
    CANONICAL TOPOLOGY                            ← this module
        ↓
    SEMANTIC NORMALIZATION (Stage 4D+)
        ↓
    MANUFACTURING FEATURE RECOGNITION (Stage 4D+)
        ↓
    MachineryPro domain Feature
        ↓
    DFM / Process Planning / CAM / Validation

Geometry vs topology
--------------------

* Geometry (sibling module) stores mathematical shape descriptors.
* Topology (this module) stores connectivity / adjacency / containment.
* Topology references geometry by stable ID; it never embeds full
  geometric objects inside topology entities.
* Edge → Curve, Vertex → Point, Face → Surface, Loop → ordered Edges,
    Shell → Faces, Body → Shells.  References are validated.

Determinism
-----------

* All models are ``@dataclass(frozen=True, slots=True)``.
* Iterables are normalized to tuples; order is preserved where topology
  semantics demand it (boundary loops) and sorted by ID elsewhere.
* Duplicate IDs are rejected; dangling references are rejected.
* No silent topology repair.

Non-goals
---------

* No manifold proof.
* No face-face intersection.
* No Boolean operations.
* No watertight-solid proof.
* No geometric healing.
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
from backend.interoperability.geometry import BoundingBox3D, CanonicalPoint3D

__all__ = [
    "BodyType",
    "CanonicalBody",
    "CanonicalEdge",
    "CanonicalFace",
    "CanonicalLoop",
    "CanonicalShell",
    "CanonicalTopology",
    "CanonicalVertex",
    "LoopType",
    "Orientation",
    "ShellClosure",
    "TopologyContainerError",
    "Transform3D",
]


class TopologyContainerError(ValidationError):
    """Raised for structural failures inside the canonical topology container."""


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Orientation(StrEnum):
    """Vendor-neutral edge / face / loop orientation.

    Kept intentionally narrow.  No OpenCASCADE-specific values.
    """

    FORWARD = "FORWARD"
    REVERSED = "REVERSED"
    INTERNAL = "INTERNAL"
    EXTERNAL = "EXTERNAL"
    UNKNOWN = "UNKNOWN"


class LoopType(StrEnum):
    """Boundary loop classification.

    * OUTER : outer / external boundary.
    * INNER : inner / hole boundary.
    * UNKNOWN: caller could not determine.
    """

    OUTER = "OUTER"
    INNER = "INNER"
    UNKNOWN = "UNKNOWN"


class ShellClosure(StrEnum):
    """Whether a shell is known to form a closed 2-manifold.

    Stage 4B never infers closure from face count alone; closure is
    set explicitly only when the adapter is certain.
    """

    OPEN = "OPEN"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


class BodyType(StrEnum):
    """Topological classification of a body.

    * SOLID  : closed volume body.
    * SHEET  : 2D surface body (no thickness implied).
    * WIRE   : wireframe / curve network only.
    * COMPOUND: heterogeneous aggregation (no canonical volume).
    * UNKNOWN : caller could not determine.
    """

    SOLID = "SOLID"
    SHEET = "SHEET"
    WIRE = "WIRE"
    COMPOUND = "COMPOUND"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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


def _normalize_str_id_tuple(
    values: Iterable[str], field_name: str
) -> tuple[str, ...]:
    out: list[str] = []
    for i, v in enumerate(values):
        if not isinstance(v, str) or not v.strip():
            raise ValidationError(
                f"{field_name}[{i}] must be a non-empty string, got {v!r}"
            )
        out.append(v.strip())
    return tuple(out)


def _require_unique_ids(
    items: Iterable[object],
    id_attr: str,
    field_name: str,
) -> None:
    seen: set[str] = set()
    for item in items:
        if not hasattr(item, id_attr):
            raise ValidationError(
                f"{field_name}: item lacks identifier attribute {id_attr!r}"
            )
        key = getattr(item, id_attr)
        if not isinstance(key, str) or not key.strip():
            raise ValidationError(
                f"{field_name}: identifier {key!r} is not a non-empty string"
            )
        if key in seen:
            raise ValidationError(
                f"{field_name}: duplicate identifier {key!r}"
            )
        seen.add(key)


def _coerce_orientation(value: Orientation | str, field_name: str) -> Orientation:
    if isinstance(value, Orientation):
        return value
    if isinstance(value, str):
        try:
            return Orientation(value)
        except ValueError as exc:
            raise ValidationError(
                f"{field_name} must be an Orientation, got {value!r}"
            ) from exc
    raise ValidationError(f"{field_name} must be an Orientation, got {value!r}")


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Transform3D:
    """A minimal deterministic 3D rigid placement.

    ``translation`` is a length Quantity (one quantity per axis); the
    container holds an explicit length unit.  ``rotation`` is a 3x3
    row-major matrix stored as a tuple of nine Decimals (unitless).

    Stage 4B does NOT perform matrix math; the rotation matrix is stored
    verbatim.  It is the caller's responsibility to ensure the matrix
    is orthogonal) when the transform is used.  No Euler-angle
    conventions are assumed.
    """

    translation: tuple[Decimal, Decimal, Decimal] = (Decimal(0), Decimal(0), Decimal(0))
    rotation: tuple[Decimal, ...] = ()
    translation_unit_length: bool = True
    metadata: MappingProxyType = field(default_factory=_empty_mappingproxy)

    def __post_init__(self) -> None:
        if len(self.translation) != 3:
            raise ValidationError(
                "translation must be a sequence of three Decimals"
            )
        cleaned_t: list[Decimal] = []
        for i, v in enumerate(self.translation):
            if not isinstance(v, Decimal):
                raise ValidationError(
                    f"translation[{i}] must be a Decimal, got {type(v).__name__}"
                )
            if not v.is_finite():
                raise ValidationError(
                    f"translation[{i}] must be finite, got {v}"
                )
            cleaned_t.append(v)
        if len(self.rotation) not in (0, 9):
            raise ValidationError(
                "rotation must be a 3x3 row-major matrix (9 Decimals) or empty"
            )
        cleaned_r: list[Decimal] = []
        for i, v in enumerate(self.rotation):
            if not isinstance(v, Decimal):
                raise ValidationError(
                    f"rotation[{i}] must be a Decimal, got {type(v).__name__}"
                )
            if not v.is_finite():
                raise ValidationError(
                    f"rotation[{i}] must be finite, got {v}"
                )
            cleaned_r.append(v)
        object.__setattr__(self, "translation", tuple(cleaned_t))
        object.__setattr__(self, "rotation", tuple(cleaned_r))
        object.__setattr__(self, "metadata", _normalize_immutable_mapping(self.metadata))

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Vertex
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CanonicalVertex:
    """A 0D topological vertex positioned by a CanonicalPoint3D.

    Geometry is referenced by composition: the vertex owns its point.
    No vertex ID is shared by reference-only here; each vertex carries
    the point data it is positioned at.
    """

    vertex_id: str
    point: CanonicalPoint3D
    source_entity_ref: str | None = None
    metadata: MappingProxyType = field(default_factory=_empty_mappingproxy)

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "vertex_id", require_non_empty_str(self.vertex_id, "vertex_id"))
        if not isinstance(self.point, CanonicalPoint3D):
            raise ValidationError("point must be a CanonicalPoint3D")
        _set(
            self,
            "source_entity_ref",
            optional_non_empty_str(self.source_entity_ref, "source_entity_ref"),
        )
        _set(self, "metadata", _normalize_immutable_mapping(self.metadata))

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Edge
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CanonicalEdge:
    """A 1D topological edge connecting two vertices and bound to a curve.

    References are by stable ID, not by object.  Dangling references are
    rejected by :class:`CanonicalTopology` at construction.
    """

    edge_id: str
    start_vertex_id: str
    end_vertex_id: str
    curve_id: str
    orientation: Orientation = Orientation.UNKNOWN
    source_entity_ref: str | None = None
    metadata: MappingProxyType = field(default_factory=_empty_mappingproxy)

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "edge_id", require_non_empty_str(self.edge_id, "edge_id"))
        _set(
            self,
            "start_vertex_id",
            require_non_empty_str(self.start_vertex_id, "start_vertex_id"),
        )
        _set(self, "end_vertex_id", require_non_empty_str(self.end_vertex_id, "end_vertex_id"))
        if self.start_vertex_id == self.end_vertex_id:
            raise ValidationError(
                "edge start and end vertex must differ"
            )
        _set(self, "curve_id", require_non_empty_str(self.curve_id, "curve_id"))
        _set(self, "orientation", _coerce_orientation(self.orientation, "orientation"))
        _set(
            self,
            "source_entity_ref",
            optional_non_empty_str(self.source_entity_ref, "source_entity_ref"),
        )
        _set(self, "metadata", _normalize_immutable_mapping(self.metadata))

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Loop
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CanonicalLoop:
    """An ordered closed chain of edges bounding a face.

    The order of ``edge_ids`` carries topology semantics; it is preserved
    verbatim from construction.  Duplicate edge references within the
    same loop are rejected.

    Stage 4B does NOT attempt to repair invalid loops; if the source
    data does not form a closed chain, the loop is stored as-is and
    flagged via metadata if the caller wishes.
    """

    loop_id: str
    edge_ids: tuple[str, ...]
    loop_type: LoopType = LoopType.UNKNOWN
    orientation: Orientation = Orientation.UNKNOWN
    source_entity_ref: str | None = None
    metadata: MappingProxyType = field(default_factory=_empty_mappingproxy)

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "loop_id", require_non_empty_str(self.loop_id, "loop_id"))
        if len(self.edge_ids) < 3:
            raise ValidationError(
                "loop must reference at least 3 edges, got "
                f"{len(self.edge_ids)}"
            )
        _set(
            self,
            "edge_ids",
            _normalize_str_id_tuple(self.edge_ids, "edge_ids"),
        )
        # Reject duplicate edge references within the same loop.
        seen: set[str] = set()
        for eid in self.edge_ids:
            if eid in seen:
                raise ValidationError(
                    f"loop edge_ids contains duplicate reference {eid!r}"
                )
            seen.add(eid)
        if not isinstance(self.loop_type, LoopType):
            try:
                _set(self, "loop_type", LoopType(self.loop_type))
            except (ValueError, TypeError) as exc:
                raise ValidationError(
                    f"loop_type must be a LoopType, got {self.loop_type!r}"
                ) from exc
        _set(self, "orientation", _coerce_orientation(self.orientation, "orientation"))
        _set(
            self,
            "source_entity_ref",
            optional_non_empty_str(self.source_entity_ref, "source_entity_ref"),
        )
        _set(self, "metadata", _normalize_immutable_mapping(self.metadata))

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Face
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CanonicalFace:
    """A 2D topological face bound to a surface and one or more loops.

    The surface is referenced by ID; loops are referenced by ID.  Order
    of loops within a face is preserved verbatim; the first loop is
    typically the outer boundary but the topology container does NOT
    rely on that ordering.
    """

    face_id: str
    surface_id: str
    boundary_loop_ids: tuple[str, ...]
    orientation: Orientation = Orientation.UNKNOWN
    source_entity_ref: str | None = None
    metadata: MappingProxyType = field(default_factory=_empty_mappingproxy)

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "face_id", require_non_empty_str(self.face_id, "face_id"))
        _set(self, "surface_id", require_non_empty_str(self.surface_id, "surface_id"))
        if not self.boundary_loop_ids:
            raise ValidationError(
                "face must reference at least one boundary loop"
            )
        _set(
            self,
            "boundary_loop_ids",
            _normalize_str_id_tuple(self.boundary_loop_ids, "boundary_loop_ids"),
        )
        seen: set[str] = set()
        for lid in self.boundary_loop_ids:
            if lid in seen:
                raise ValidationError(
                    f"face boundary_loop_ids contains duplicate reference {lid!r}"
                )
            seen.add(lid)
        _set(self, "orientation", _coerce_orientation(self.orientation, "orientation"))
        _set(
            self,
            "source_entity_ref",
            optional_non_empty_str(self.source_entity_ref, "source_entity_ref"),
        )
        _set(self, "metadata", _normalize_immutable_mapping(self.metadata))

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Shell
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CanonicalShell:
    """A connected set of faces forming a (possibly open) 2-manifold region.

    Stage 4B does NOT infer closure from the number or arrangement of
    faces.  ``closure`` is recorded explicitly; UNKNOWN is the default
    and is the fail-closed stance.
    """

    shell_id: str
    face_ids: tuple[str, ...]
    closure: ShellClosure = ShellClosure.UNKNOWN
    is_oriented: bool = False
    source_entity_ref: str | None = None
    metadata: MappingProxyType = field(default_factory=_empty_mappingproxy)

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "shell_id", require_non_empty_str(self.shell_id, "shell_id"))
        if not self.face_ids:
            raise ValidationError("shell must reference at least one face")
        _set(
            self,
            "face_ids",
            _normalize_str_id_tuple(self.face_ids, "face_ids"),
        )
        seen: set[str] = set()
        for fid in self.face_ids:
            if fid in seen:
                raise ValidationError(
                    f"shell face_ids contains duplicate reference {fid!r}"
                )
            seen.add(fid)
        if not isinstance(self.closure, ShellClosure):
            try:
                _set(self, "closure", ShellClosure(self.closure))
            except (ValueError, TypeError) as exc:
                raise ValidationError(
                    f"closure must be a ShellClosure, got {self.closure!r}"
                ) from exc
        if isinstance(self.is_oriented, bool) is False:
            raise ValidationError("is_oriented must be a bool")
        _set(
            self,
            "source_entity_ref",
            optional_non_empty_str(self.source_entity_ref, "source_entity_ref"),
        )
        _set(self, "metadata", _normalize_immutable_mapping(self.metadata))

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Body
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CanonicalBody:
    """A complete topological body composed of one or more shells.

    ``body_type`` is declared by the caller; Stage 4B does NOT infer it
    from the topology graph.  A SOLID body should only be declared
    SOLID when the adapter knows the shell(s) form a watertight volume.
    """

    body_id: str
    body_type: BodyType
    shell_ids: tuple[str, ...]
    bounding_box: BoundingBox3D | None = None
    transform: Transform3D | None = None
    source_entity_ref: str | None = None
    metadata: MappingProxyType = field(default_factory=_empty_mappingproxy)

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "body_id", require_non_empty_str(self.body_id, "body_id"))
        if not isinstance(self.body_type, BodyType):
            try:
                _set(self, "body_type", BodyType(self.body_type))
            except (ValueError, TypeError) as exc:
                raise ValidationError(
                    f"body_type must be a BodyType, got {self.body_type!r}"
                ) from exc
        if not self.shell_ids:
            raise ValidationError("body must reference at least one shell")
        _set(
            self,
            "shell_ids",
            _normalize_str_id_tuple(self.shell_ids, "shell_ids"),
        )
        seen: set[str] = set()
        for sid in self.shell_ids:
            if sid in seen:
                raise ValidationError(
                    f"body shell_ids contains duplicate reference {sid!r}"
                )
            seen.add(sid)
        if self.bounding_box is not None and not isinstance(
            self.bounding_box, BoundingBox3D
        ):
            raise ValidationError("bounding_box must be a BoundingBox3D or None")
        if self.transform is not None and not isinstance(self.transform, Transform3D):
            raise ValidationError("transform must be a Transform3D or None")
        _set(
            self,
            "source_entity_ref",
            optional_non_empty_str(self.source_entity_ref, "source_entity_ref"),
        )
        _set(self, "metadata", _normalize_immutable_mapping(self.metadata))

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Topology container
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CanonicalTopology:
    """Container for canonical topology of a document.

    Validation
    ----------
    * All entity IDs are unique within their class.
    * Every reference inside topology points to an existing entity:
        Edge.curve_id          -> Curve
        Edge.start_vertex_id   -> Vertex
        Edge.end_vertex_id     -> Vertex
        Loop.edge_ids          -> Edge (all)
        Face.surface_id        -> Surface
        Face.boundary_loop_ids -> Loop (all)
        Shell.face_ids         -> Face (all)
        Body.shell_ids         -> Shell (all)

    Determinism
    -----------
    * Accessor methods return entities sorted by ID.
    * No silent topology repair.
    """

    topology_id: str
    vertices: tuple[CanonicalVertex, ...] = ()
    edges: tuple[CanonicalEdge, ...] = ()
    loops: tuple[CanonicalLoop, ...] = ()
    faces: tuple[CanonicalFace, ...] = ()
    shells: tuple[CanonicalShell, ...] = ()
    bodies: tuple[CanonicalBody, ...] = ()
    geometry: object | None = None  # CanonicalGeometry | None; kept loose to avoid import cycle
    source_entity_ref: str | None = None
    metadata: MappingProxyType = field(default_factory=_empty_mappingproxy)

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "topology_id", require_non_empty_str(self.topology_id, "topology_id"))
        for name, expected in (
            ("vertices", CanonicalVertex),
            ("edges", CanonicalEdge),
            ("loops", CanonicalLoop),
            ("faces", CanonicalFace),
            ("shells", CanonicalShell),
            ("bodies", CanonicalBody),
        ):
            items = list(getattr(self, name))
            for i, item in enumerate(items):
                if not isinstance(item, expected):
                    raise ValidationError(
                        f"{name}[{i}] must be a {expected.__name__}"
                    )
            _set(self, name, tuple(items))
        _require_unique_ids(self.vertices, "vertex_id", "vertices")
        _require_unique_ids(self.edges, "edge_id", "edges")
        _require_unique_ids(self.loops, "loop_id", "loops")
        _require_unique_ids(self.faces, "face_id", "faces")
        _require_unique_ids(self.shells, "shell_id", "shells")
        _require_unique_ids(self.bodies, "body_id", "bodies")

        # Optional link to CanonicalGeometry (typed as object to avoid an
        # import cycle).
        if self.geometry is not None:
            from backend.interoperability.geometry import CanonicalGeometry as _CG
            if not isinstance(self.geometry, _CG):
                raise ValidationError(
                    "geometry must be a CanonicalGeometry or None"
                )
        _set(
            self,
            "source_entity_ref",
            optional_non_empty_str(self.source_entity_ref, "source_entity_ref"),
        )
        _set(self, "metadata", _normalize_immutable_mapping(self.metadata))

        # Reference integrity
        self._validate_references()

    # ------------------------------------------------------------------
    # Reference integrity
    # ------------------------------------------------------------------
    def _validate_references(self) -> None:
        vertex_ids = {v.vertex_id for v in self.vertices}
        edge_ids = {e.edge_id for e in self.edges}
        loop_ids = {loop.loop_id for loop in self.loops}
        face_ids = {f.face_id for f in self.faces}
        shell_ids = {s.shell_id for s in self.shells}

        for e in self.edges:
            if e.start_vertex_id not in vertex_ids:
                raise TopologyContainerError(
                    f"edge {e.edge_id!r} start_vertex_id "
                    f"{e.start_vertex_id!r} not found in vertices"
                )
            if e.end_vertex_id not in vertex_ids:
                raise TopologyContainerError(
                    f"edge {e.edge_id!r} end_vertex_id "
                    f"{e.end_vertex_id!r} not found in vertices"
                )
            if self.geometry is not None and not self.geometry.has_curve(e.curve_id):
                raise TopologyContainerError(
                    f"edge {e.edge_id!r} curve_id "
                    f"{e.curve_id!r} not found in geometry curves"
                )

        for lp in self.loops:
            for eid in lp.edge_ids:
                if eid not in edge_ids:
                    raise TopologyContainerError(
                        f"loop {lp.loop_id!r} references missing edge {eid!r}"
                    )

        for f in self.faces:
            if self.geometry is not None and not self.geometry.has_surface(f.surface_id):
                raise TopologyContainerError(
                    f"face {f.face_id!r} surface_id "
                    f"{f.surface_id!r} not found in geometry surfaces"
                )
            for lid in f.boundary_loop_ids:
                if lid not in loop_ids:
                    raise TopologyContainerError(
                        f"face {f.face_id!r} references missing loop {lid!r}"
                    )

        for s in self.shells:
            for fid in s.face_ids:
                if fid not in face_ids:
                    raise TopologyContainerError(
                        f"shell {s.shell_id!r} references missing face {fid!r}"
                    )

        for b in self.bodies:
            for sid in b.shell_ids:
                if sid not in shell_ids:
                    raise TopologyContainerError(
                        f"body {b.body_id!r} references missing shell {sid!r}"
                    )

    # ------------------------------------------------------------------
    # Deterministic accessors
    # ------------------------------------------------------------------
    @property
    def ordered_vertices(self) -> tuple[CanonicalVertex, ...]:
        return tuple(sorted(self.vertices, key=lambda v: v.vertex_id))

    @property
    def ordered_edges(self) -> tuple[CanonicalEdge, ...]:
        return tuple(sorted(self.edges, key=lambda e: e.edge_id))

    @property
    def ordered_loops(self) -> tuple[CanonicalLoop, ...]:
        return tuple(sorted(self.loops, key=lambda loop: loop.loop_id))

    @property
    def ordered_faces(self) -> tuple[CanonicalFace, ...]:
        return tuple(sorted(self.faces, key=lambda f: f.face_id))

    @property
    def ordered_shells(self) -> tuple[CanonicalShell, ...]:
        return tuple(sorted(self.shells, key=lambda s: s.shell_id))

    @property
    def ordered_bodies(self) -> tuple[CanonicalBody, ...]:
        return tuple(sorted(self.bodies, key=lambda b: b.body_id))

    def get_vertex(self, vertex_id: str) -> CanonicalVertex:
        for v in self.ordered_vertices:
            if v.vertex_id == vertex_id:
                return v
        raise TopologyContainerError(f"vertex_id {vertex_id!r} not found")

    def get_edge(self, edge_id: str) -> CanonicalEdge:
        for e in self.ordered_edges:
            if e.edge_id == edge_id:
                return e
        raise TopologyContainerError(f"edge_id {edge_id!r} not found")

    def get_loop(self, loop_id: str) -> CanonicalLoop:
        for lp in self.ordered_loops:
            if lp.loop_id == loop_id:
                return lp
        raise TopologyContainerError(f"loop_id {loop_id!r} not found")

    def get_face(self, face_id: str) -> CanonicalFace:
        for f in self.ordered_faces:
            if f.face_id == face_id:
                return f
        raise TopologyContainerError(f"face_id {face_id!r} not found")

    def get_shell(self, shell_id: str) -> CanonicalShell:
        for s in self.ordered_shells:
            if s.shell_id == shell_id:
                return s
        raise TopologyContainerError(f"shell_id {shell_id!r} not found")

    def get_body(self, body_id: str) -> CanonicalBody:
        for b in self.ordered_bodies:
            if b.body_id == body_id:
                return b
        raise TopologyContainerError(f"body_id {body_id!r} not found")

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)
