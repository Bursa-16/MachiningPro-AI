# CAD Import End-to-End Design

## Purpose

Connect the existing STEP/STP, IGES/IGS, and DXF adapters to real multipart
uploads without treating the first 512 bytes as the full document. The upload
boundary must enforce a 64 MiB limit, reject inconsistent format signals before
adapter execution, keep raw CAD content out of domain and response models, and
return an honest summary of parsing and optional geometry capability.

## Existing Failure and Evidence

`frontend/routers/ui.py` currently calls `await file.read()`, which loads the
entire upload into memory. It then decodes only `content_bytes[:512]` into
`EngineeringSource.notes`. `CadImportOrchestrator.detect_format()` sniffs that
field, while `StepTokenAdapter`, `IgesTokenAdapter`, and `DxfTokenAdapter` also
use `source.notes` as their parsing input. The header-sized detection sample is
therefore incorrectly reused as the complete document, truncating every file
larger than 512 bytes at the adapter boundary.

## Scope

The supported upload formats are limited to:

- STEP: `.step`, `.stp`, and the existing `.p21` alias
- IGES: `.iges` and `.igs`
- ASCII DXF: `.dxf`

Binary DXF is detectable but is not parsed by the existing DXF token adapter;
it must be reported as unavailable rather than accepted as a successful parse.
PDF, STL, OBJ, 3MF, and other formats remain unsupported and are not advertised
or routed to placeholder adapters.

## Upload Boundary

The frontend application will stage each `UploadFile` into a uniquely named
temporary file. It will read in 1 MiB chunks, update a SHA-256 digest, retain at
most the first 512 bytes for format detection, and count bytes as they are
written. The write stops immediately when the cumulative size exceeds
67,108,864 bytes. Oversized uploads return HTTP 413 deterministically.

Empty files are rejected. The temporary file is deleted in a `finally` block
covering successful parsing, validation failures, adapter failures, and
unexpected exceptions. Cleanup errors may be logged using the generated
temporary filename only; uploaded bytes, decoded content, and caller-controlled
content are never logged.

The new flow does not call `UploadFile.read()` without an explicit chunk size.
Adapters may load the staged file as text only after the upload boundary has
enforced the 64 MiB cap. This makes parser memory use bounded rather than
uncontrolled while preserving the existing text-oriented parsers.

## Format Validation

Validation combines three independent signals:

1. The normalized filename extension.
2. The normalized multipart content type.
3. Magic/header detection from the first 512 bytes.

Generic transport media types such as `application/octet-stream` and
`text/plain` are accepted only when extension and magic/header agree. A
format-specific media type must match the same family as the extension and
header. Missing, unsupported, ambiguous, or contradictory signals fail closed
before registry lookup or adapter invocation.

STEP application-protocol variants detected from the header are compatible
with every accepted STEP extension. IGES aliases map to `IGES`. ASCII DXF maps
to `DXF`. `DXF-BINARY` has no live parser in this phase and produces an
unavailable result without invoking the ASCII adapter.

## Content Handoff and Backward Compatibility

`EngineeringSource` remains an identity/metadata model and receives no raw
bytes, decoded CAD text, or temporary filesystem path. The real upload flow
sets only safe fields such as filename, media type, and `sha256:<hex>` checksum.

`FormatAdapter` receives an additive, non-abstract file-ingestion entry point.
Its default implementation fails closed so third-party adapters that implement
only the existing `ingest(source, descriptor)` contract remain constructible
and keep their old behavior. The STEP, IGES, and DXF adapters override the new
entry point, read the complete staged file, and reuse their existing parsing
logic. Their existing `ingest()` methods and notes-based test/direct-call path
remain available for backward compatibility.

`CadImportOrchestrator.import_source()` retains its existing call signature and
behavior when no staged content is supplied. A new keyword-only staged-file
argument selects the file-ingestion entry point. Format detection accepts the
separate 512-byte header sample; the sample is never copied into the domain
source. Registry selection and the existing `ImportResult` contract remain
compatible.

## Result Contract

Both the HTML flow and a JSON upload endpoint use the same import service and
produce a safe summary containing:

- `filename`
- `detected_format`
- `file_size`
- `sha256`
- `adapter_status`
- `parse_status`
- `diagnostics`
- geometry/topology summary fields when the adapter actually produced them

`adapter_status` is one of:

- `LIVE`: a usable adapter ran and the requested capability is available.
- `CONDITIONAL`: the built-in token parser ran, but optional geometry/topology
  capability depends on an unavailable package or an unimplemented bridge.
- `UNAVAILABLE`: no safe parser exists for the detected format or the selected
  adapter cannot consume staged content.

`parse_status` is derived from the existing `ImportStatus`; adapter presence
does not turn malformed input into success. Missing `pythonocc-core` or `ezdxf`
must not produce fabricated geometry/topology. Geometry summaries are omitted
or explicitly unavailable when no real geometry was extracted.

The response is built from an allowlist. It never serializes
`CanonicalDocument.source.notes`, staged paths, raw bytes, decoded source text,
or exception strings that may contain source content.

## Error Semantics

- More than 64 MiB: HTTP 413; adapter is not called.
- Empty upload: validation failure; adapter is not called.
- Unsupported extension: unsupported-format failure; adapter is not called.
- Extension, media type, or header mismatch: fail-closed validation failure;
  adapter is not called.
- Malformed but consistently identified content: adapter runs and returns a
  real failed/partial parse result.
- Missing optional geometry dependency: parsing may remain successful at Level
  1, but adapter status is conditional and geometry is not claimed.
- Unexpected adapter exception: sanitized failure response; staged file is
  still removed.

Existing HTML validation responses remain compatible where practical. The
oversize case is the required exception and always carries status 413. The JSON
endpoint uses explicit client-error status codes while sharing the same safe
diagnostic payload.

## Testing Strategy

Tests follow red-green-refactor cycles and cover:

- STEP, IGES, and DXF fixtures with a unique semantic marker after byte 512;
  assertions on real parser output prove the complete file reached the adapter.
- Exact 64 MiB acceptance and 64 MiB plus one byte rejection with HTTP 413.
- Extension/header and content-type/header mismatches, with a spy proving no
  adapter invocation.
- Unsupported format, empty file, malformed content, and binary DXF.
- Success-path and every error-path temporary-file cleanup.
- Absence of raw marker/content and temporary paths from domain serialization,
  HTML/JSON responses, logs, diagnostics, and error strings.
- Accurate `LIVE`, `CONDITIONAL`, and `UNAVAILABLE` reporting.
- Backward compatibility for direct notes-based adapter calls and existing
  orchestrator callers.

Final verification runs exactly:

```text
py -m pytest tests/unit/interoperability -q
py -m pytest tests/unit/frontend -q
py -m pytest -q
py -m ruff check backend frontend tests
git diff --check
git status --short
```

Any environment or unrelated baseline failure is reported verbatim and is not
presented as success.

## Change Isolation

The working tree already contains user changes, including changes in
`backend/interoperability/orchestrator.py`, `normalization.py`, and
`population.py`. Implementation will patch only the lines required for this
feature and will not revert or reformat unrelated work. No commit, push, tag,
release, test deletion, skip, xfail, or assertion weakening is permitted.

## Remaining Deliberate Limitations

- The 64 MiB cap bounds upload and parser memory but does not convert the
  existing token parsers into incremental parsers.
- STEP and IGES geometry still depend on the existing optional OCCT path and
  incomplete canonical bridge.
- DXF geometry still depends on `ezdxf`; binary DXF remains unavailable.
- PDF, STL, OBJ, 3MF, and proprietary CAD formats remain future work.
