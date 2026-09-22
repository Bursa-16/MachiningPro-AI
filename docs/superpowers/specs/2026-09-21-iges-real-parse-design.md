# CAD-IMPORT-IGES-REAL-PARSE-01 Design

**Date:** 2026-09-21  
**Status:** Draft for review  
**Scope:** Real, fail-closed IGES geometry and topology ingestion

## Intent

Replace the current IGES section-inventory implementation with a strict parser
that derives canonical geometry and topology from the uploaded file's actual
Global, Directory Entry, and Parameter Data records. A successful supported
IGES file must reach `LEVEL_2_NORMALIZED`, carry real `CanonicalGeometry` and
`CanonicalTopology` objects in its `CanonicalDocument`, and expose truthful
geometry/topology summaries in the CAD Import UI.

No production path may fabricate coordinates, substitute a fixed example
part, infer success from an entity histogram, or silently ignore unsupported
geometry that affects the resulting model.

## Existing-System Findings

The current behavior is deterministic and has five concrete causes:

1. `IgesTokenAdapter.metadata()` caps the adapter at
   `LEVEL_1_PARSED`.
2. `_parse_iges_sections()` only inventories section letters and reads the
   first eight columns of alternating D records as an entity-type histogram.
   It does not parse Directory Entry fields, Parameter Data, continuations, or
   entity references.
3. Every otherwise successful IGES import unconditionally records an adverse
   event saying that Level 2 requires `pythonocc-core`.
4. The existing minimal IGES fixture does not place its P-section marker at
   column 73, so the parser records a second adverse event saying that the
   Parameter section is missing. The current code therefore reproduces the
   observed count of two adverse events exactly.
5. `CanonicalDocument` has no geometry/topology payload fields and
   `AdapterSession._extra_canonical_payloads` is unused. The UI therefore
   guesses availability from `CanonicalEntityRef.entity_kind` strings rather
   than inspecting canonical data.

Separately, the existing 41 population-test failures originate in an unrelated
working-tree edit to `backend/interoperability/population.py`: the edit reads
`ExchangeDocumentStatus.UNSUPPORTED`, but the live enum only defines `READY`,
`PARTIAL`, and `UNAVAILABLE`. This task must not modify or mask that edit.

## Constraints and Non-Goals

- Keep the MachineryPro core dependency-free beyond its current project
  dependencies. OCCT/OCP is not available in the Python 3.14 environment and
  is not added by this task.
- Parse the explicitly supported IGES subset in pure Python. Files requiring
  other geometric entities remain truthful, explicit unsupported outcomes.
- Preserve all unrelated modified and untracked user files. In particular,
  do not edit `backend/interoperability/population.py` or
  `backend/interoperability/normalization.py`.
- Do not add mesh tessellation, CAD healing, Boolean reconstruction,
  manufacturing-feature recognition, or an IGES exporter.
- Do not commit, push, tag, or release without a later explicit instruction.

## Architecture

### 1. Low-level IGES parser

Add `backend/interoperability/iges_parser.py`. It owns the file-format grammar
and returns immutable parsed IGES records; it does not construct canonical
domain objects.

The parser operates on ASCII bytes so column positions remain byte-accurate.
It will:

- reject binary, compressed, NUL-containing, and non-ASCII inputs;
- accept CRLF or LF physical line endings after stripping only the terminator;
- require each fixed record to be exactly 80 bytes;
- validate section order, section sequence numbers, and Terminate counts;
- require S, G, D, P, and T for geometry-bearing imports;
- parse Global-section parameter and record delimiters, including Hollerith
  strings without splitting inside their payload;
- extract model scale, unit flag/name, minimum resolution, maximum coordinate,
  IGES version, and creation/application metadata;
- parse each two-line Directory Entry into named fields, including parameter
  pointer, structure/view/transform/label pointers, status, form, and parameter
  line count;
- join Parameter Data records by Directory Entry pointer and line count, then
  parse typed scalar, Hollerith, and DE-reference parameters;
- reject duplicate pointers, invalid even DE pointers, missing continuations,
  dangling references, invalid numeric values, and cyclic reference traversal.

The parser returns an `IgesModel` containing `IgesGlobalSection`, ordered
`IgesDirectoryEntry` objects, and `IgesEntity` objects keyed by their odd
Directory Entry sequence pointer.

### 2. Canonical IGES mapper

Add `backend/interoperability/iges_mapping.py`. It converts an `IgesModel` into
an immutable result containing:

- `CanonicalGeometry`;
- optional `CanonicalTopology`;
- one `CanonicalEntityRef` per mapped or explicitly unsupported source entity;
- fidelity diagnostics tied to source DE pointers;
- supported/unsupported entity counts and source-unit metadata.

IDs are deterministic and derived from the Directory Entry pointer, for
example `IGES-DE-000001`, `IGES-CURVE-000001`, and `IGES-FACE-000021`.

Coordinates and lengths come only from parsed parameters. Global model scale
and unit declarations are applied to every length quantity. Geometry is stored
in millimetres using exact `Decimal` conversion factors. Global minimum
resolution is converted to millimetres and retained in geometry/document
metadata as source tolerance. Unknown or contradictory unit declarations are
fail-closed.

Directory Entry transformation matrices are resolved before mapping.
Transforms are applied to points and vectors, with cycle and reference checks;
missing or unsupported transforms invalidate the affected entity.

### 3. Supported entity subset

The first implementation supports these actual IGES parameter schemas:

| Category | IGES entity | Canonical output |
|---|---:|---|
| Curve | 100 Circular Arc | `CanonicalCurve` ARC/CIRCLE |
| Curve | 110 Line | `CanonicalCurve` LINE |
| Point | 116 Point | topology vertex source / entity reference |
| Curve | 126 Rational B-Spline Curve | BSPLINE or NURBS curve |
| Transform | 124 Transformation Matrix | applied placement |
| Surface | 108 Plane | PLANE surface |
| Surface | 128 Rational B-Spline Surface | BSPLINE or NURBS surface |
| Surface | 190 Plane Surface | PLANE surface |
| Surface | 192 Right Circular Cylindrical Surface | CYLINDER surface |
| Surface | 194 Right Circular Conical Surface | CONE surface |
| Surface | 196 Spherical Surface | SPHERE surface |
| Surface | 198 Toroidal Surface | TORUS surface |
| Boundary | 141 Boundary | validated model/parameter curve collection |
| Boundary | 142 Curve on Parametric Surface | validated surface/curve relationship |
| Boundary | 143 Bounded Surface | validated surface and boundary relationships |
| Boundary | 144 Trimmed Surface | validated surface and trimming loops |
| B-Rep | 502 Vertex List | `CanonicalVertex` records |
| B-Rep | 504 Edge List | `CanonicalEdge` records |
| B-Rep | 508 Loop | `CanonicalLoop` records |
| B-Rep | 510 Face | `CanonicalFace` records |
| B-Rep | 514 Shell | `CanonicalShell` records |
| B-Rep | 186 Manifold Solid B-Rep Object | `CanonicalBody` SOLID |

A supported entity whose required referenced entity or parameter form is not
supported is treated as unsupported with the precise DE pointer, entity type,
form number, and reason.

### 4. Fail-closed fidelity policy

Outcomes are separated by impact:

- malformed physical records, invalid section structure, impossible numeric
  data, unknown units, resource-limit violations, or corrupt mandatory
  references: normalization `FAILED`, no canonical geometry/topology;
- unsupported geometry/topology participating in a requested B-Rep chain:
  affected topology is not emitted, normalization `PARTIAL` or `UNSUPPORTED`,
  and the event identifies the source entity and reason;
- independently supported geometry alongside unreferenced presentation or
  annotation entities: supported geometry may be emitted, but the document is
  `PARTIAL/DEGRADED` and each unsupported type is reported;
- a fully supported model with no adverse events: `LEVEL_2_NORMALIZED`,
  normalization `SUCCESS`, fidelity completeness `COMPLETE`.

Unsupported events are preserved in the fidelity report and copied into safe
UI/API diagnostics as bounded strings. Raw file content, paths, tracebacks, and
unbounded parameter payloads are never exposed.

### 5. Canonical document propagation

Extend `CanonicalDocument` with optional `geometry: CanonicalGeometry | None`
and `topology: CanonicalTopology | None` fields. Validate their types while
keeping defaults `None`, preserving all existing constructors.

Extend `AdapterSession` with explicit setters for geometry and topology and
pass those values through `build()`. The IGES adapter will use the new parser
and mapper, add mapped entity references, and mark Level 2 only when actual
canonical geometry exists.

`population.py` remains a separate downstream bridge for callers that provide
population requests. The IGES adapter does not route through the dirty bridge
or alter its user-owned changes. `normalization.py` also remains untouched;
unit conversion is deterministic at the IGES mapping boundary.

### 6. Orchestrator and UI

The orchestrator retains its selection/status logic. It will receive the
adapter's real Level 2 document and derive `SUCCESS`, `PARTIAL`, `DEGRADED`, or
`FAILED` from its normalization and fidelity data.

Replace `_entity_summaries()` heuristics with direct summaries:

- Geometry: curve count, surface count, optional bounding-box availability,
  source unit, and converted tolerance;
- Topology: vertex, edge, loop, face, shell, and body counts.

The public summary remains allowlisted and bounded. Detailed unsupported
entity diagnostics include only type, form, DE pointer, and safe reason.

## Resource and Security Limits

Existing upload size, MIME, extension, hashing, temporary-file cleanup, and
content-sniffing controls remain unchanged. The parser adds explicit limits:

- maximum physical records derived from the existing upload byte limit;
- maximum Directory Entry/entity count;
- maximum Parameter Data bytes per entity;
- maximum parsed parameters, control points, knot values, and weights;
- maximum reference traversal depth and cycle detection;
- finite `Decimal` values only, with bounded exponent and Hollerith length;
- no recursion based on untrusted file depth;
- no dynamic imports, evaluation, shell execution, or external file lookup.

Limits are named constants and tested at the boundary and boundary-plus-one.

## Test-Driven Implementation

Tests are written and observed failing before production changes.

### Parser tests

- valid custom delimiters and Hollerith values;
- Global unit, scale, resolution, version, and tolerance extraction;
- paired Directory Entries and multi-line Parameter Data;
- DE pointer and transformation resolution;
- invalid length, section order/count, sequence number, encoding, numeric,
  continuation, duplicate, dangling, cyclic, and limit cases.

### Mapping tests

- every listed curve, surface, boundary, and B-Rep entity uses literal IGES
  parameters and produces hand-derived canonical values;
- inch/metre/millimetre conversion and tolerance propagation;
- transformation application;
- unsupported entity/type/form messages and fail-closed propagation;
- no output geometry when required parameters or references are invalid;
- deterministic canonical IDs and ordering.

### Integration and UI tests

- adapter and orchestrator reach Level 2 only with real mapped content;
- staged-file parsing reads the full bounded file;
- `CanonicalDocument` preserves geometry/topology;
- UI/API display real geometry/topology counts and safe diagnostics;
- existing STEP, DXF, CAD upload, and frontend behavior remains unchanged;
- the unrelated population suite is run and its known 41 failures are reported
  separately rather than hidden or modified.

Targeted verification includes the affected interoperability model, geometry,
topology, adapter, orchestrator, CAD upload/import, and frontend test files plus
Ruff checks for changed Python files.

## Remaining Limitations

- The parser supports fixed-record ASCII IGES only. Binary and compressed IGES
  remain explicitly unsupported.
- Entities outside the declared table are reported, not approximated.
- No geometric healing, sewing, Boolean reconstruction, or manifold proof is
  attempted beyond explicit IGES B-Rep relationships.
- Trimmed and bounded surfaces preserve validated relationships; the canonical
  model does not evaluate or tessellate their parameter-space curves.
- Very broad real-world IGES coverage still benefits from an optional OCCT
  integration in a later, separately packaged task.

## References

- NIST, *Initial Graphics Exchange Specification*, fixed-record sections and
  Directory/Parameter data organization:
  https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nbsir86-3359.pdf
- Open CASCADE `IGESControl_Reader` documentation, for a possible later kernel
  integration:
  https://dev.opencascade.org/doc/occt-7.6.0/refman/html/_i_g_e_s_control___reader_8hxx.html
