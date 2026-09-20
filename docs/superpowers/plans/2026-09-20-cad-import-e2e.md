# CAD Import End-to-End Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream STEP, IGES, and DXF uploads safely into the existing real adapters and expose a truthful, byte-safe UI/API import summary.

**Architecture:** The FastAPI boundary stages multipart data into a temporary file in bounded chunks while computing size, SHA-256, and a 512-byte detection sample. Format policy validates extension, MIME type, and magic/header before an additive file-ingestion adapter method lets the orchestrator deliver the complete staged file without embedding content or paths in domain models.

**Tech Stack:** Python 3.11, FastAPI/Starlette `UploadFile`, stdlib `tempfile`, `hashlib`, `pathlib`, existing interoperability adapters, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-09-20-cad-import-e2e-design.md`

## Global Constraints

- Maximum upload size is exactly 64 MiB (67,108,864 bytes); the first byte beyond it returns HTTP 413.
- Only STEP/STP/P21, IGES/IGS, and ASCII DXF are supported.
- Extension, content type, and magic/header must agree before adapter invocation.
- Raw CAD bytes, decoded source text, and temporary paths must not enter domain models, responses, logs, diagnostics, or errors.
- Preserve the existing `FormatAdapter.ingest()` and `CadImportOrchestrator.import_source()` calling patterns.
- Preserve all pre-existing working-tree changes and avoid unrelated formatting or refactoring.
- Do not commit, push, tag, release, delete/skip/xfail tests, or weaken assertions.

## File Structure

- Create `frontend/cad_upload.py`: bounded staging, format-signal validation, safe upload metadata, and cleanup.
- Modify `backend/interoperability/adapter.py`: additive non-abstract staged-file entry point.
- Modify `backend/interoperability/adapters/step.py`: complete-file STEP entry point sharing the existing parser.
- Modify `backend/interoperability/adapters/iges.py`: complete-file IGES entry point sharing the existing parser.
- Modify `backend/interoperability/adapters/dxf.py`: complete-file ASCII DXF entry point sharing the existing parser.
- Modify `backend/interoperability/orchestrator.py`: separate header detection and staged-file dispatch while retaining old callers.
- Modify `frontend/routers/ui.py`: shared upload execution and allowlisted UI/API result summary.
- Modify `frontend/templates/cad_import.html`: display hash, adapter status, parse status, diagnostics, and real geometry/topology availability.
- Modify `tests/unit/interoperability/test_adapter.py`: base-contract fail-closed coverage.
- Modify `tests/unit/interoperability/test_adapters.py`: post-512 full-file parser evidence for all three adapters.
- Modify `tests/unit/interoperability/test_orchestrator.py`: staged dispatch, backward compatibility, and sanitized exception coverage.
- Create `tests/unit/frontend/test_cad_upload.py`: chunking, size boundary, validation, hashing, and cleanup tests.
- Modify `tests/unit/frontend/test_cad_import.py`: UI/API integration, no-adapter-on-mismatch, status, and leak tests.

## Review Focus

- A filename containing directory separators must be reduced to a basename and never control the temporary path; Task 2 tests this.
- `application/octet-stream` must be accepted only when extension and header agree; Task 2 tests both acceptance and mismatch rejection.
- A 64 MiB file must pass while 64 MiB plus one byte must fail without an adapter call; Tasks 2 and 4 test this boundary.
- Adapter exceptions containing uploaded marker text must not leak to HTML, JSON, logs, or diagnostics; Tasks 1 and 4 test sanitization.
- Binary DXF magic must report `UNAVAILABLE` and must never be routed to the ASCII DXF adapter; Tasks 2 and 4 test this explicitly.

---

### Task 1: Add a backward-compatible complete-file adapter pathway

**Files:**

- Modify: `backend/interoperability/adapter.py`
- Modify: `backend/interoperability/adapters/step.py`
- Modify: `backend/interoperability/adapters/iges.py`
- Modify: `backend/interoperability/adapters/dxf.py`
- Modify: `backend/interoperability/orchestrator.py`
- Test: `tests/unit/interoperability/test_adapter.py`
- Test: `tests/unit/interoperability/test_adapters.py`
- Test: `tests/unit/interoperability/test_orchestrator.py`

**Interfaces:**

- Consumes: `EngineeringSource`, `FormatDescriptor`, and a caller-owned `pathlib.Path` whose lifetime covers the call.
- Produces: `FormatAdapter.ingest_file(source, format_descriptor, content_path) -> CanonicalDocument`; `detect_format(source, header_bytes=None) -> FormatDetectionResult`; `CadImportOrchestrator.import_source(..., content_path=None, header_bytes=None) -> ImportResult`.

- [ ] **Step 1: Write failing contract and staged-orchestrator tests**

Add a base-adapter test proving the new default fails closed and does not fall back to `source.notes`:

```python
def test_ingest_file_is_fail_closed_by_default(tmp_path: Path) -> None:
    adapter = _MinimalAdapter()
    path = tmp_path / "part.step"
    path.write_text("ISO-10303-21;", encoding="utf-8")
    with pytest.raises(NotImplementedError, match="staged file ingestion"):
        adapter.ingest_file(_source(), _descriptor(), path)
```

Add orchestrator tests that pass `header_bytes` separately from an
`EngineeringSource(notes=None)` and assert `ingest_file` receives the exact
path. Add a raising adapter whose message contains `RAW_MARKER_AFTER_512` and
assert the returned `ImportResult`, `error_message`, and diagnostics contain no
marker or path.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```text
py -m pytest tests/unit/interoperability/test_adapter.py tests/unit/interoperability/test_orchestrator.py -q
```

Expected: failures for missing `ingest_file`, unsupported `header_bytes` /
`content_path` parameters, and unsanitized adapter exceptions.

- [ ] **Step 3: Add the non-abstract base entry point and orchestrator dispatch**

Add to `FormatAdapter` without changing its abstract methods:

```python
def ingest_file(
    self,
    source: EngineeringSource,
    format_descriptor: FormatDescriptor,
    content_path: Path,
) -> CanonicalDocument:
    raise NotImplementedError(
        f"adapter {self.metadata().adapter_id!r} does not support staged file ingestion"
    )
```

Change detection to prefer an explicit header while retaining notes fallback:

```python
def detect_format(
    source: EngineeringSource,
    header_bytes: bytes | None = None,
) -> FormatDetectionResult:
    sample = header_bytes
    if sample is None and source.notes:
        sample = source.notes.encode("utf-8", errors="replace")
    if sample:
        sniffed = ContentSniffer.sniff(sample)
        ...
```

Extend `import_source` with keyword-only `content_path: Path | None = None` and
`header_bytes: bytes | None = None`. Call `selected_adapter.ingest_file(...)`
when a path is present and keep the existing `ingest(...)` path otherwise.
Replace caller-visible adapter exception text with the constant
`"Adapter execution failed"`; diagnostics may contain the adapter ID and
exception class, but not `str(exc)`.

- [ ] **Step 4: Refactor each built-in adapter around a shared text parser**

For STEP, IGES, and DXF, preserve `ingest()` and add:

```python
def ingest_file(
    self,
    source: EngineeringSource,
    format_descriptor: FormatDescriptor,
    content_path: Path,
) -> CanonicalDocument:
    text = content_path.read_text(encoding="utf-8", errors="replace")
    return self._ingest_text(source, format_descriptor, text)
```

Move each current parse body into `_ingest_text(...)`. Existing `ingest()`
obtains `source.notes` exactly as before and calls the same helper. Do not put
the text or path back into `EngineeringSource`. Keep STEP's OCCT temporary-file
cleanup and DXF's optional `ezdxf` behavior intact.

- [ ] **Step 5: Add real post-512 parser evidence**

Create complete staged files for each adapter:

```python
marker = "RAW_MARKER_AFTER_512"
step_text = _STEP_AP242_MINIMAL.replace(
    "ENDSEC;\nEND-ISO-10303-21;",
    f"/*{'X' * 600}*/\n#999=PRODUCT('{marker}','','',());\nENDSEC;\nEND-ISO-10303-21;",
)
```

Assert the STEP header entity count includes `#999`. For IGES, place a valid
type-110 D-section pair after at least 512 bytes of valid S/G records and assert
the `IgesHeader` summary contains one `Line`. For DXF, place a `LINE` entity and
layer named `RAW_MARKER_AFTER_512` after 512 bytes of group-code `999` comments
and assert `DxfHeader.metadata["entity_type_summary"]["LINE"] == 1` and the
layer count reflects the marker layer. In every case assert
`document.source.notes is None`.

- [ ] **Step 6: Run adapter and orchestrator tests and verify GREEN**

Run:

```text
py -m pytest tests/unit/interoperability/test_adapter.py tests/unit/interoperability/test_adapters.py tests/unit/interoperability/test_orchestrator.py -q
```

Expected: all pass; the pre-existing direct notes-based tests remain green.

### Task 2: Stream, hash, validate, and clean uploaded CAD files

**Files:**

- Create: `frontend/cad_upload.py`
- Create: `tests/unit/frontend/test_cad_upload.py`

**Interfaces:**

- Consumes: an object implementing async `read(size: int) -> bytes` plus `filename` and `content_type` attributes.
- Produces: async context manager `stage_cad_upload(file) -> AsyncIterator[StagedCadUpload]`; a validated temporary path and safe metadata valid only inside the context.

- [ ] **Step 1: Write failing tests for chunking, boundaries, hashing, and cleanup**

Define a test upload object that records every requested read size and can
generate repeated chunks without allocating a 64 MiB payload. Tests must assert:

```python
assert upload.read_sizes and set(upload.read_sizes) == {UPLOAD_CHUNK_BYTES}
assert staged.file_size == MAX_CAD_UPLOAD_BYTES
assert staged.sha256 == hashlib.sha256(expected_bytes).hexdigest()
assert not staged.path.exists()  # after leaving the context
```

Use a sparse/repeating async reader for exact-limit and limit-plus-one cases.
Assert `UploadRejected.status_code == 413` for the latter and that cleanup also
occurs when the context body raises.

- [ ] **Step 2: Write failing format-policy tests**

Cover all extension aliases, generic MIME acceptance, format-specific MIME
acceptance, `.step` containing IGES, `.dxf` containing STEP, PDF MIME with STEP
magic, unsupported `.stl`, empty content, binary DXF, and a filename such as
`..\\unsafe\\part.step`. Assert rejected exceptions contain only fixed safe
messages and never fixture bytes.

- [ ] **Step 3: Run the new test module and verify RED**

Run:

```text
py -m pytest tests/unit/frontend/test_cad_upload.py -q
```

Expected: import failure because `frontend.cad_upload` does not exist.

- [ ] **Step 4: Implement the staging types and constants**

Create:

```python
MAX_CAD_UPLOAD_BYTES = 64 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024
SNIFF_BYTES = 512

@dataclass(frozen=True, slots=True)
class StagedCadUpload:
    path: Path
    filename: str
    content_type: str
    file_size: int
    sha256: str
    header_bytes: bytes
    detected_format: str

class UploadRejected(Exception):
    def __init__(self, status_code: int, safe_message: str) -> None:
        super().__init__(safe_message)
        self.status_code = status_code
        self.safe_message = safe_message
```

Normalize filenames with `PurePosixPath(filename.replace("\\", "/")).name`.
Write chunks to `NamedTemporaryFile(delete=False)` while updating `hashlib.sha256`
and the first-512-byte buffer. On every exit call `Path.unlink(missing_ok=True)`.

- [ ] **Step 5: Implement fail-closed signal agreement**

Use explicit family maps for extensions and media types. Treat only
`application/octet-stream` and `text/plain` as generic. Call
`ContentSniffer.sniff(header_bytes)` and require extension family, explicit MIME
family, and sniffed family to agree. Reject `DXF-BINARY` with a fixed safe
message and HTTP 415. Set `detected_format` to the specific STEP AP result or
the canonical `IGES` / `DXF` value.

- [ ] **Step 6: Run the upload tests and verify GREEN**

Run:

```text
py -m pytest tests/unit/frontend/test_cad_upload.py -q
```

Expected: all pass with no warnings.

### Task 3: Build one allowlisted import summary for HTML and JSON

**Files:**

- Modify: `frontend/routers/ui.py`
- Modify: `frontend/templates/cad_import.html`
- Modify: `tests/unit/frontend/test_cad_import.py`

**Interfaces:**

- Consumes: `UploadFile`, `StagedCadUpload`, and existing `ImportResult`.
- Produces: `_execute_cad_import(file) -> dict[str, object]`, HTML `/ui/cad-import`, and JSON `POST /api/cad-import`.

- [ ] **Step 1: Write failing UI/API response tests**

Add tests asserting both endpoints expose only:

```python
{
    "filename", "detected_format", "file_size", "sha256",
    "adapter_status", "parse_status", "diagnostics",
    "geometry_summary", "topology_summary",
}
```

The actual summary may include existing safe display fields for HTML, but the
JSON endpoint must use an explicit allowlist and must not include `document`,
`source`, `notes`, `content_path`, or raw content. Assert a real upload's SHA-256
matches the request bytes.

- [ ] **Step 2: Write failing adapter-status and no-fabrication tests**

Assert:

- A selected Level-1 token adapter with missing/unimplemented geometry is
  `CONDITIONAL`.
- A selected adapter that parses at the real available target is `LIVE`.
- Unsupported/binary/no-staged-file adapters are `UNAVAILABLE`.
- Malformed input has a failed `parse_status` even when adapter status is live.
- Geometry/topology summaries are `None` unless real matching entity references
  exist; no placeholder counts or 3D claims appear.

- [ ] **Step 3: Run focused frontend tests and verify RED**

Run:

```text
py -m pytest tests/unit/frontend/test_cad_import.py -q
```

Expected: failures for missing JSON endpoint and new result fields.

- [ ] **Step 4: Implement shared execution and safe summary construction**

Inside `ui.py`, use one helper:

```python
async def _execute_cad_import(file: UploadFile) -> dict[str, object]:
    async with stage_cad_upload(file) as staged:
        source = EngineeringSource(
            source_id=f"upload::{staged.filename}",
            file_name=staged.filename,
            media_type=staged.content_type,
            checksum=f"sha256:{staged.sha256}",
        )
        result = CadImportOrchestrator().import_source(
            source,
            content_path=staged.path,
            header_bytes=staged.header_bytes,
        )
        return _result_to_safe_summary(result, staged)
```

Compute geometry/topology summaries only from actual entity-reference kinds.
Return SHA-256 as the bare lowercase hex digest. Diagnostics are fixed field
names and sanitized values from `ImportResult`, never a recursive `as_dict()`.

- [ ] **Step 5: Wire HTML and JSON error semantics**

The HTML endpoint renders `UploadRejected.safe_message` and uses its status
code only for 413 while preserving existing 200 validation-page behavior for
other user errors. The JSON endpoint returns the safe summary on completion and
`{"detail": safe_message}` with the rejection status for validation failures.
Unexpected failures return a fixed internal-error message with no exception
text. Both paths use the same `_execute_cad_import` helper.

- [ ] **Step 6: Update the template**

Display filename, detected format, size, SHA-256, adapter status, parse status,
safe diagnostics, and geometry/topology availability. Keep existing real
`ImportResult` fields, remove no existing supported-format labels, and do not
introduce claims for PDF/STL/OBJ/3MF.

- [ ] **Step 7: Run focused frontend tests and verify GREEN**

Run:

```text
py -m pytest tests/unit/frontend/test_cad_import.py tests/unit/frontend/test_cad_upload.py -q
```

Expected: all pass.

### Task 4: Prove fail-closed routing, byte non-leakage, and cleanup end to end

**Files:**

- Modify: `tests/unit/frontend/test_cad_import.py`
- Modify: `tests/unit/interoperability/test_orchestrator.py`

**Interfaces:**

- Consumes: the completed upload, validation, orchestrator, and adapter pathways.
- Produces: regression evidence covering all mandatory security/error paths.

- [ ] **Step 1: Add a no-adapter-on-rejection matrix**

Patch the orchestrator constructor and parameterize empty content, unsupported
extension, STEP/IGES mismatch, STEP/DXF mismatch, incompatible MIME, binary DXF,
and limit-plus-one. For every case assert the constructor/import method was not
called. Assert the oversized response status is exactly 413.

- [ ] **Step 2: Add success and failure cleanup evidence**

Patch only the temporary-file factory/location so tests can record generated
paths. Exercise successful import, validation rejection, adapter-returned
failure, adapter exception, and result-rendering exception. After each request,
assert every recorded path no longer exists.

- [ ] **Step 3: Add raw-byte and path leakage tests**

Use `RAW_MARKER_AFTER_512` in input and in a deliberately raised adapter
exception. Inspect response bytes, `caplog.text`, `repr(result)`,
`result.as_dict()`, diagnostics, and error messages. Assert the marker, decoded
fixture fragments, and staged absolute path are absent. Assert filename, size,
and SHA-256 remain present.

- [ ] **Step 4: Run the affected suites and verify GREEN**

Run:

```text
py -m pytest tests/unit/interoperability -q
py -m pytest tests/unit/frontend -q
```

Expected: both suites pass; no existing test is skipped or weakened.

### Task 5: Run all quality gates and report exact evidence

**Files:**

- Inspect only: all changed files and test output.

**Interfaces:**

- Consumes: completed implementation.
- Produces: exact quality-gate results and the required final report sections.

- [ ] **Step 1: Run the mandatory verification commands separately**

Run exactly:

```text
py -m pytest tests/unit/interoperability -q
py -m pytest tests/unit/frontend -q
py -m pytest -q
py -m ruff check backend frontend tests
git diff --check
git status --short
```

Record exit code and complete failure details for every non-zero command. Do not
describe environment or unrelated repository failures as passing.

- [ ] **Step 2: Inspect the final scoped diff**

Run:

```text
git diff -- backend/interoperability/adapter.py backend/interoperability/adapters/step.py backend/interoperability/adapters/iges.py backend/interoperability/adapters/dxf.py backend/interoperability/orchestrator.py frontend/cad_upload.py frontend/routers/ui.py frontend/templates/cad_import.html tests/unit/interoperability/test_adapter.py tests/unit/interoperability/test_adapters.py tests/unit/interoperability/test_orchestrator.py tests/unit/frontend/test_cad_upload.py tests/unit/frontend/test_cad_import.py
git diff --stat
```

Confirm unrelated user changes in normalization, population, DFM, templates,
and untracked files were not modified or removed.

- [ ] **Step 3: Produce the required final report without repository mutations**

Use these exact headings:

```text
ROOT_CAUSE
FILES_CHANGED
TESTS_ADDED
FORMAT_STATUS
QUALITY_GATES
REMAINING_LIMITATIONS
GIT_DIFF_STAT
FINAL_STATUS
```

Include the real command outcomes and note that no commit, push, tag, or release
was performed.
