# Real IGES Geometry and Topology Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan.

**Goal:** Replace the token-inventory IGES adapter with a strict, resource-bounded parser and mapper that derives canonical geometry and topology from the file's actual IGES parameters, reports unsupported entities explicitly, and drives truthful CAD Import UI summaries.

**Architecture:** Add a pure-Python fixed-record parser (`iges_parser.py`) and a separate canonical mapper (`iges_mapping.py`). The adapter remains the policy boundary: it turns structural parse failures into failed imports, mapping limitations into explicit fidelity events, and only advertises Level 2 when real canonical geometry was emitted. `CanonicalDocument` and `AdapterSession` gain optional typed geometry/topology payloads; the UI reads these payloads directly instead of guessing from entity names.

**Tech Stack:** Python 3.14, frozen dataclasses, `Decimal`, existing interoperability domain models, pytest, FastAPI/Jinja frontend tests.

**Approved design:** [`docs/superpowers/specs/2026-09-21-iges-real-parse-design.md`](../specs/2026-09-21-iges-real-parse-design.md)

## Non-negotiable constraints

- Do not edit, restore, stage, or otherwise normalize the user's existing changes in `backend/interoperability/population.py`, `backend/interoperability/normalization.py`, `backend/dfm/validation.py`, `frontend/templates/public_base.html`, or any unrelated untracked file.
- Do not use `git reset`, `git checkout --`, broad formatters, or repository-wide autofixes.
- Do not create fake geometry, a hard-coded sample part, or a success fallback. Test fixtures may serialize explicit IGES parameters, but production output must be derived only from the uploaded bytes.
- Do not add a CAD-kernel dependency. The first supported subset is parsed and mapped deterministically in Python.
- Do not create a commit, push, tag, or release. The user's prohibition overrides any normal commit cadence in execution skills.
- Run only the targeted tests listed below until the user separately requests a full suite.

## Root cause to preserve in regression tests

The current `IgesTokenAdapter` only counts S/G/D/P/T records and reads the entity-type field from alternating Directory records. It never parses Global delimiters, Directory pairs, Parameter Data, entity references, units, transforms, geometry, or topology. Its metadata caps capability at `LEVEL_1_PARSED`, and it unconditionally emits the “pythonocc-core required” adverse event. The legacy minimal fixture also places its P marker outside column 73, producing the second “lacks a Parameter section” event. The new tests must demonstrate both old failure modes before production code changes.

The unrelated 41-test baseline is already isolated to the user's dirty `backend/interoperability/population.py`: line 304 references the nonexistent `ExchangeDocumentStatus.UNSUPPORTED`. Preserve that failure and re-run the focused population file only as an evidence check; do not modify it in this task.

## File map

### New files

- `backend/interoperability/iges_parser.py` — physical records, Global/Directory/Parameter parsing, value tokenization, validation, reference graph, resource limits.
- `backend/interoperability/iges_mapping.py` — supported entity decoders, unit/transform application, canonical geometry/topology construction, explicit mapping issues.
- `tests/unit/interoperability/iges_fixtures.py` — test-only 80-column record writer and small parameter-authored IGES documents.
- `tests/unit/interoperability/test_iges_parser.py` — grammar, validation, encoding, bounds, references.
- `tests/unit/interoperability/test_iges_mapping.py` — curves, surfaces, B-Rep, units, transforms, unsupported fail-closed behavior.

### Modified files

- `backend/interoperability/models.py` — optional typed `geometry` and `topology` fields on `CanonicalDocument`.
- `backend/interoperability/adapters/_base.py` — session setters and document passthrough.
- `backend/interoperability/adapters/iges.py` — use parser/mapper; remove unconditional kernel adverse event; truthful capability/completeness.
- `frontend/routers/ui.py` — summarize real canonical payload counts and bounded unsupported-entity diagnostics.
- `tests/unit/interoperability/test_models.py` — document payload validation/serialization.
- `tests/unit/interoperability/test_adapters.py` — real Level 2 IGES adapter outcomes and explicit failure cases.
- `tests/unit/interoperability/test_orchestrator.py` — end-to-end imported document payload/status.
- `tests/unit/frontend/test_cad_import.py` — UI Geometry/Topology and unsupported entity regression coverage.

## Public interfaces

`backend/interoperability/iges_parser.py` will expose this bounded, immutable result contract:

```python
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

IgesParameter = Decimal | int | str | None


class IgesParseError(ValueError):
    def __init__(self, message: str, *, section: str | None = None, sequence: int | None = None) -> None:
        super().__init__(message)
        self.section = section
        self.sequence = sequence


@dataclass(frozen=True, slots=True)
class IgesLimits:
    max_file_bytes: int = 64 * 1024 * 1024
    max_records: int = 800_000
    max_entities: int = 100_000
    max_parameter_bytes_per_entity: int = 4 * 1024 * 1024
    max_parameters_per_entity: int = 1_000_000
    max_control_points: int = 250_000
    max_reference_depth: int = 128


@dataclass(frozen=True, slots=True)
class IgesGlobalSection:
    parameter_delimiter: str
    record_delimiter: str
    model_scale: Decimal
    unit_flag: int
    unit_name: str
    millimetres_per_model_unit: Decimal
    minimum_resolution: Decimal | None
    maximum_coordinate: Decimal | None
    version: int | None


@dataclass(frozen=True, slots=True)
class IgesDirectoryEntry:
    de_pointer: int
    entity_type: int
    parameter_data_pointer: int
    structure_pointer: int
    line_font_pattern: int
    level: int
    view_pointer: int
    transformation_matrix_pointer: int
    label_display_associativity: int
    status_number: str
    line_weight: int
    color_number: int
    parameter_line_count: int
    form_number: int
    entity_label: str
    entity_subscript: int


@dataclass(frozen=True, slots=True)
class IgesEntity:
    directory: IgesDirectoryEntry
    parameters: tuple[IgesParameter, ...]


@dataclass(frozen=True, slots=True)
class IgesModel:
    global_section: IgesGlobalSection
    entities: tuple[IgesEntity, ...]
    entities_by_pointer: MappingProxyType
    section_counts: MappingProxyType


def parse_iges_bytes(data: bytes, *, limits: IgesLimits = IgesLimits()) -> IgesModel:
    records = _split_physical_records(data, limits)
    sections = _validate_sections(records, limits)
    global_section = _parse_global(sections["G"], limits)
    directories = _parse_directory_entries(sections["D"], limits)
    entities = _parse_parameter_data(sections["P"], directories, global_section, limits)
    entities_by_pointer = MappingProxyType(
        {entity.directory.de_pointer: entity for entity in entities}
    )
    _validate_reference_graph(entities_by_pointer, limits)
    return IgesModel(
        global_section=global_section,
        entities=entities,
        entities_by_pointer=entities_by_pointer,
        section_counts=MappingProxyType(
            {name: len(section_records) for name, section_records in sections.items()}
        ),
    )
```

`backend/interoperability/iges_mapping.py` will expose:

```python
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


def map_iges_model(model: IgesModel) -> IgesMappingResult:
    context = _MappingContext(model)
    context.map_geometry_entities()
    context.map_topology_entities()
    return context.build_result()
```

Stable IDs are derived from odd Directory Entry pointers: `iges-de-0000001`, `curve-de-0000001`, `surface-de-0000009`, and analogous topology IDs. Every length is converted with `Decimal` to `Unit.MM`; no binary float conversion is allowed at the source boundary.

## Task 1: RED — canonical payload contract

**Files:**

- Modify: `tests/unit/interoperability/test_models.py`
- Modify: `tests/unit/interoperability/test_adapters.py`
- Modify: `backend/interoperability/models.py`
- Modify: `backend/interoperability/adapters/_base.py`

### Step 1: Add failing document tests

Add tests that construct a minimal real `CanonicalGeometry` and `CanonicalTopology`, then assert:

```python
document = CanonicalDocument(
    document_id="doc-iges",
    canonical_kind=CanonicalKind.PART,
    source=source,
    format_descriptor=descriptor,
    adapter_id="iges.token",
    adapter_version="2.0.0",
    capability_level=AdapterCapabilityLevel.LEVEL_2_NORMALIZED,
    normalization_status=NormalizationStatus.SUCCESS,
    geometry=geometry,
    topology=topology,
)
assert document.geometry is geometry
assert document.topology is topology
assert document.as_dict()["geometry"]["geometry_id"] == "geometry-iges"
```

Add negative tests passing `object()` to both fields and expecting `ValidationError` with the field name.

### Step 2: Run RED

Run:

```powershell
py -m pytest tests/unit/interoperability/test_models.py tests/unit/interoperability/test_adapters.py -q
```

Expected: new tests fail because `CanonicalDocument` has no `geometry`/`topology` keyword and `AdapterSession` cannot carry them.

### Step 3: Implement the minimum contract

In `models.py`, add optional fields and local runtime checks to avoid import cycles:

```python
geometry: object | None = None
topology: object | None = None
```

Inside `__post_init__`, locally import `CanonicalGeometry` and `CanonicalTopology`, reject any non-`None` mismatch, and require `topology.geometry is geometry` when both are present.

In `AdapterSession.__init__`, add `_geometry` and `_topology`. Add typed `set_geometry()` and `set_topology()` methods that reject calls after `build()`, and pass both fields to `CanonicalDocument` in `build()`.

### Step 4: Run GREEN and inspect scope

Run the same pytest command, then:

```powershell
git diff --check -- backend/interoperability/models.py backend/interoperability/adapters/_base.py tests/unit/interoperability/test_models.py tests/unit/interoperability/test_adapters.py
git status --short
```

Expected: targeted tests pass; dirty user files remain modified but byte-for-byte untouched by this task.

## Task 2: RED — physical records and Global section

**Files:**

- Create: `tests/unit/interoperability/iges_fixtures.py`
- Create: `tests/unit/interoperability/test_iges_parser.py`
- Create: `backend/interoperability/iges_parser.py`

### Step 1: Create test-only record builders

The fixture writer must place data in columns 1–72, the section letter in column 73, and the seven-digit sequence in columns 74–80:

```python
def record(payload: str, section: str, sequence: int) -> bytes:
    assert len(section) == 1
    encoded = f"{payload:<72.72}{section}{sequence:07d}".encode("ascii")
    assert len(encoded) == 80
    return encoded


def join_records(*records: bytes, newline: bytes = b"\n", final_newline: bool = True) -> bytes:
    body = newline.join(records)
    return body + newline if final_newline else body
```

Add helpers that accept explicit Global parameters, Directory fields, and Parameter strings. They may format test input but may not compute expected geometry.

### Step 2: Add RED grammar tests

Cover all of these cases:

- exact 80-column LF, CRLF, and missing-final-newline records;
- reject 79/81-column records and non-ASCII bytes;
- section order S→G→D→P→T and monotonic per-section sequences;
- Terminate counts must equal observed S/G/D/P counts;
- Global parameter/record delimiters including Hollerith strings containing comma or semicolon;
- model scale, unit flag/name, minimum resolution, maximum coordinate, and version;
- reject zero/negative/non-finite scale, unknown unit, malformed Decimal exponent, and conflicting unit flag/name;
- `max_file_bytes` and `max_records` boundaries.

The key Hollerith assertion is:

```python
model = parse_iges_bytes(iges_with_global_strings("12Hcomma,value", "14Hsemi;colon-ok"))
assert model.global_section.parameter_delimiter == ","
assert model.global_section.record_delimiter == ";"
```

### Step 3: Run RED

```powershell
py -m pytest tests/unit/interoperability/test_iges_parser.py -q
```

Expected: collection fails because `iges_parser.py` does not exist.

### Step 4: Implement the physical tokenizer and Global decoder

Implement `_split_physical_records`, `_parse_record`, `_validate_sections`, a Hollerith-aware `_tokenize_parameter_stream`, `_parse_decimal`, and `_parse_global`. Normalize `D` exponents to `E` only after lexical validation. Never use `float` for source numeric values.

Use this unit table and reject everything else:

```python
_MM_PER_UNIT_FLAG = {
    1: Decimal("25.4"),
    2: Decimal("1"),
    4: Decimal("304.8"),
    5: Decimal("1609344"),
    6: Decimal("1000"),
    7: Decimal("1000000"),
    8: Decimal("0.0254"),
    9: Decimal("0.001"),
    10: Decimal("10"),
    11: Decimal("0.0000254"),
}
```

Apply `model_scale * millimetres_per_model_unit` exactly once when mapping, not during tokenization.

### Step 5: Run GREEN

Run the parser test file and `git diff --check` for the three task files.

## Task 3: RED — Directory, Parameter Data, and reference integrity

**Files:**

- Modify: `tests/unit/interoperability/test_iges_parser.py`
- Modify: `backend/interoperability/iges_parser.py`

### Step 1: Add failing DE/P tests

Add tests proving:

- every Directory entity consumes two consecutive D records and gets the odd first-record pointer;
- both D records repeat the same entity type;
- fixed-width integer fields and status number are validated;
- the P record Directory pointer (columns 65–72) exists and is odd;
- each entity consumes exactly `parameter_line_count` P records starting at `parameter_data_pointer`;
- the first parameter equals the Directory entity type;
- continuations may split Hollerith and numeric tokens across P records;
- duplicate pointers, overlapping parameter ranges, missing ranges, wrong line counts, dangling references, and reference cycles fail with section and sequence context;
- entity/parameter/control-point/reference-depth limits fail closed.

Reference graph checks cover DE transformation pointers and all supported schema reference fields; ordinary integers are not globally guessed to be references.

### Step 2: Run RED

```powershell
py -m pytest tests/unit/interoperability/test_iges_parser.py -q
```

Expected: new DE/P and graph assertions fail while Task 2 tests remain green.

### Step 3: Implement DE/P assembly

Parse the two 72-column Directory payloads by eight-character fields. Group 64-column P payloads by their 8-column DE pointer, validate physical P sequence numbers, then concatenate before Hollerith-aware tokenization. Build a `MappingProxyType` keyed by DE pointer.

Add explicit reference schemas for the supported entities rather than treating every integer parameter as a pointer. Validate transforms (124), boundary relations (142/143/144), and B-Rep relations (502/504/508/510/514/186), with DFS colors and `max_reference_depth`.

### Step 4: Run GREEN

Run only `test_iges_parser.py`, followed by `git diff --check` on its two files.

## Task 4: RED — real curves, surfaces, units, and transforms

**Files:**

- Create: `tests/unit/interoperability/test_iges_mapping.py`
- Create: `backend/interoperability/iges_mapping.py`

### Step 1: Add failing geometry mapping tests

Author IGES fixtures with deliberately non-round parameter values so hard-coded output cannot pass. Assert exact `Decimal`-derived `Quantity` values for:

- 100 Circular Arc: Z plane, center, start/end parameters, radius;
- 110 Line: two endpoints and normalized direction;
- 116 Point: XYZ;
- 126 Rational B-Spline Curve: degree, knot vector, weights, control points, parameter interval;
- 108 Plane and 190 Plane Surface;
- 128 Rational B-Spline Surface: U/V degree, U/V knots, weights, control-point grid, parameter ranges;
- 192 Cylinder, 194 Cone, 196 Sphere, 198 Torus;
- 124 transform matrix applied once to positions and directions;
- inches, feet, metres, millimetres, and model scale converted exactly to millimetres;
- minimum resolution exposed as canonical metadata in millimetres.

Because `CanonicalSurface` has one generic `degree`/`knots` slot, preserve the full type-128 tensor structure in immutable metadata keys `u_degree`, `v_degree`, `u_knots`, `v_knots`, `control_point_grid_shape`, `u_parameter_range`, and `v_parameter_range`; use the common canonical fields only where they remain unambiguous. The test must ensure no U/V data is discarded.

### Step 2: Add failing unsupported tests

Use an unsupported geometry entity such as type 118 and assert:

```python
assert result.geometry is None
assert result.topology is None
assert result.issues[0].entity_type == 118
assert result.issues[0].fatal is True
assert "unsupported" in result.issues[0].reason.lower()
```

An unsupported presentation/annotation entity independent of supported geometry may retain the valid geometry, but must produce a non-fatal explicit issue. Never silently omit an unsupported entity that can affect geometry or topology.

### Step 3: Run RED

```powershell
py -m pytest tests/unit/interoperability/test_iges_mapping.py -q
```

Expected: collection fails because `iges_mapping.py` does not exist.

### Step 4: Implement mapping helpers

Create strict per-entity decoders such as `_map_arc_100`, `_map_line_110`, `_map_point_116`, `_map_transform_124`, `_map_bspline_curve_126`, `_map_plane_108`, `_map_bspline_surface_128`, and analytic surface mappers. Each decoder validates parameter count, integer flags, knot monotonicity, positive radii, nonzero directions, finite bounded Decimals, and referenced entity type before constructing canonical objects.

Use this conversion boundary:

```python
def _length_mm(value: Decimal, global_section: IgesGlobalSection) -> Quantity:
    scaled = value * global_section.model_scale * global_section.millimetres_per_model_unit
    return Quantity(value=scaled, unit=Unit.MM)
```

Keep transformation math in `Decimal`. Reject singular/unsupported projective transforms and cycles; do not repair them.

### Step 5: Run GREEN

Run parser and mapping test files together so schema/reference validation and canonical mapping stay aligned.

## Task 5: RED — B-Rep topology mapping

**Files:**

- Modify: `tests/unit/interoperability/test_iges_mapping.py`
- Modify: `backend/interoperability/iges_mapping.py`

### Step 1: Add a parameter-authored topology fixture

Construct a test-only triangular face graph from actual records: 502 Vertex List, three 110 curves, 504 Edge List, 508 Loop, a supported base surface, 510 Face, 514 Shell, and 186 Manifold Solid. Every expected vertex coordinate, edge endpoint, orientation, loop order, face/surface reference, shell membership, and body membership must be derived by the mapper from fixture parameters.

Add separate 141 Boundary/143 Bounded Surface and 142 Curve on Parametric Surface/144 Trimmed Surface fixtures and assert their boundary/base-surface references are preserved.

### Step 2: Add fail-closed graph tests

Cover:

- 504 references a missing vertex list or curve;
- 508 has fewer than three supported edge uses, a repeated edge, or an unsupported vertex-use member;
- 510 references an unsupported surface or loop;
- 514 contains an unsupported face;
- 186 references a missing shell or void shell;
- an unsupported entity appears anywhere in a B-Rep dependency chain.

For these cases, do not emit a partial `CanonicalTopology`. Keep independent supported geometry only if it is truthful and mark the issue `affects_topology=True`.

### Step 3: Run RED

```powershell
py -m pytest tests/unit/interoperability/test_iges_mapping.py -q
```

Expected: geometry tests remain green and new topology tests fail.

### Step 4: Implement dependency-ordered topology mapping

Decode vertex lists first, then edge lists, loops, faces, shells, and solids. Create `CanonicalTopology` only after all references validate. Use source orientation flags; do not infer loop closure, shell closure, or solidness from counts. Declare `ShellClosure.CLOSED` and `BodyType.SOLID` only for a valid type-186 chain whose shell orientation data is complete; otherwise report an issue and keep the classification fail-closed.

### Step 5: Run GREEN

Run `test_iges_parser.py` and `test_iges_mapping.py` together, then `git diff --check` for the mapper and tests.

## Task 6: RED — adapter and orchestrator integration

**Files:**

- Modify: `tests/unit/interoperability/test_adapters.py`
- Modify: `tests/unit/interoperability/test_orchestrator.py`
- Modify: `backend/interoperability/adapters/iges.py`

### Step 1: Replace token-only expectations with outcome tests

Add tests for four policy outcomes:

1. Fully supported geometry/topology → `LEVEL_2_NORMALIZED`, `SUCCESS`, `COMPLETE`, payloads present, no adverse event.
2. Supported geometry plus independent unsupported annotation → Level 2, `PARTIAL`, explicit `UNSUPPORTED` fidelity event naming entity type/form/reason.
3. Unsupported geometry/B-Rep dependency → no false topology, `PARTIAL` or failed normalization according to whether independent geometry survives, explicit adverse event.
4. Malformed structural input → `FAILED`, `LOST`, no geometry/topology.

Add a regression that the old malformed `_IGES_MINIMAL` fixture no longer establishes successful parsing; either replace it with a valid 80-column fixture where success is intended or assert its structural failure explicitly.

### Step 2: Run RED

```powershell
py -m pytest tests/unit/interoperability/test_adapters.py tests/unit/interoperability/test_orchestrator.py -q
```

Expected: current adapter remains Level 1 and emits the unconditional kernel event.

### Step 3: Integrate parser and mapper

Update adapter metadata to a new adapter version and maximum `LEVEL_2_NORMALIZED`. Read staged files as bytes, parse strictly, map, attach canonical payloads, and add entity refs. Convert each `IgesMappingIssue` to a bounded fidelity event that includes DE pointer, entity type, form, and reason.

Delete the unconditional pythonocc-core adverse event. Capability rules must be data-driven:

- call `mark_parsed()` only after structural parsing succeeds;
- call `mark_normalized()` only when non-empty canonical geometry exists;
- call `mark_complete()` only when all semantically relevant entities are supported and topology dependencies are intact;
- on `IgesParseError`, record a lost event and `mark_failed()`;
- never report Level 2 for inventory-only output.

### Step 4: Run GREEN

Run the two integration files plus parser/mapping tests. Inspect a focused diff only:

```powershell
git diff -- backend/interoperability/adapters/iges.py backend/interoperability/models.py backend/interoperability/adapters/_base.py backend/interoperability/iges_parser.py backend/interoperability/iges_mapping.py tests/unit/interoperability
```

Verify user-owned `population.py` and `normalization.py` diffs did not change.

## Task 7: RED — truthful CAD Import UI summaries

**Files:**

- Modify: `tests/unit/frontend/test_cad_import.py`
- Modify: `frontend/routers/ui.py`

### Step 1: Add failing frontend tests

Post a valid supported IGES fixture and assert the rendered response contains actual, nonzero Geometry and Topology summaries. Include exact counts from the fixture, source unit/tolerance information, and `LEVEL_2_NORMALIZED`/success status.

Post an unsupported-entity fixture and assert the response names the entity type and reason while not claiming unavailable topology is available. Verify the safe summary does not expose staged paths, raw P records, file bytes, or unbounded exception text.

### Step 2: Run RED

```powershell
py -m pytest tests/unit/frontend/test_cad_import.py -q
```

Expected: `_entity_summaries()` still guesses by `entity_kind`, so real payload counts are absent.

### Step 3: Read canonical payloads directly

Replace heuristic name checks with direct counts:

```python
geometry = document.geometry
geometry_summary = None if geometry is None else {
    "curve_count": len(geometry.curves),
    "surface_count": len(geometry.surfaces),
    "has_bounding_box": geometry.bounding_box is not None,
    "source_unit": geometry.metadata.get("iges_source_unit"),
    "tolerance_mm": geometry.metadata.get("iges_minimum_resolution_mm"),
}

topology = document.topology
topology_summary = None if topology is None else {
    "vertex_count": len(topology.vertices),
    "edge_count": len(topology.edges),
    "loop_count": len(topology.loops),
    "face_count": len(topology.faces),
    "shell_count": len(topology.shells),
    "body_count": len(topology.bodies),
}
```

Expose at most 20 unsupported issue summaries, each truncated to 240 characters, through the existing safe display contract. Do not render raw parameter streams.

### Step 4: Run GREEN

Run `test_cad_import.py` only, then `git diff --check` on `frontend/routers/ui.py` and its test.

## Task 8: Targeted regression and security verification

**Files:** all files listed in this plan; no unrelated files.

### Step 1: Run the complete targeted interoperability set

```powershell
py -m pytest tests/unit/interoperability/test_iges_parser.py tests/unit/interoperability/test_iges_mapping.py tests/unit/interoperability/test_models.py tests/unit/interoperability/test_adapters.py tests/unit/interoperability/test_orchestrator.py -q
```

Expected: all pass.

### Step 2: Run CAD Import/frontend regression

```powershell
py -m pytest tests/unit/frontend/test_cad_import.py tests/unit/frontend/test_layout_scrolling.py -q
```

Expected: all pass; prior accordion/scroll behavior remains intact.

### Step 3: Run lint only on task files

```powershell
py -m ruff check backend/interoperability/iges_parser.py backend/interoperability/iges_mapping.py backend/interoperability/adapters/iges.py backend/interoperability/adapters/_base.py backend/interoperability/models.py frontend/routers/ui.py tests/unit/interoperability/iges_fixtures.py tests/unit/interoperability/test_iges_parser.py tests/unit/interoperability/test_iges_mapping.py tests/unit/interoperability/test_models.py tests/unit/interoperability/test_adapters.py tests/unit/interoperability/test_orchestrator.py tests/unit/frontend/test_cad_import.py
```

Do not pass `--fix`; manually correct only task-owned findings.

### Step 4: Re-confirm the unrelated 41-failure baseline

```powershell
py -m pytest tests/unit/interoperability/test_population.py -q --tb=short
```

Expected: the same 41 failures remain rooted at the user's dirty `backend/interoperability/population.py` reference to `ExchangeDocumentStatus.UNSUPPORTED`. If the failure shape differs, stop and investigate; do not alter the file.

### Step 5: Final integrity checks

```powershell
git diff --check -- backend/interoperability/models.py backend/interoperability/adapters/_base.py backend/interoperability/adapters/iges.py backend/interoperability/iges_parser.py backend/interoperability/iges_mapping.py frontend/routers/ui.py tests/unit/interoperability tests/unit/frontend/test_cad_import.py
git status --short
```

Compare the final status with the starting status. Report only task files as changed by this implementation, separately list the preserved pre-existing user changes, supported entity types, targeted test counts, the known 41 unrelated failures, and these limitations:

- fixed-record ASCII IGES only;
- supported entity subset only; unsupported semantic dependencies fail closed;
- no geometry healing, sewing, booleans, tessellation, or kernel-level manifold proof;
- type-128 U/V tensor details are preserved in canonical immutable metadata because the current generic surface model has single-axis degree/knot fields;
- topology is emitted only for a fully validated supported dependency graph.

Do not commit, push, tag, or release.

## Plan self-review

- **Requirement coverage:** Global, Directory, Parameter, references, curves, surfaces, B-Rep, units, tolerance, transforms, UI, security limits, and explicit unsupported behavior each have a RED test before production work.
- **No success simulation:** all expected geometry/topology values come from explicit test-file parameters; production has no sample-part fallback.
- **Fail-closed boundary:** malformed structure and semantic dependency failures never emit a false complete topology.
- **Dirty-tree safety:** the four known modified user files are excluded from every implementation and lint target; the population failure is observed, not repaired.
- **Verification scope:** only targeted tests run; full-suite execution and all VCS publication actions remain excluded.
- **Design gap handled:** type-128 U/V information is retained losslessly in immutable canonical metadata without inventing unsupported fields or flattening away semantics.
