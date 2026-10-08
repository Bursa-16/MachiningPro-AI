# Qualification fixtures

Self-authored synthetic drawings for `docs/qualification/REAL_DRAWING_DEMO_QUALIFICATION.md`
(REAL_DRAWING_QUALIFICATION_02). No customer, OEM, proprietary or downloaded material is used.

| Folder | Content |
|---|---|
| `sources/` | `<QUAL_ID>.drawing.json` (canonical primitive list, hashed) and `<QUAL_ID>.svg` (viewable) |
| `raster/` | `<QUAL_ID>.png`: 8-bit grayscale raster used as the qualification image |
| `pdf/` | `<QUAL_ID>.pdf`: one page embedding the raster (never vector-only) and the probe PDFs |
| `provenance/` | one provenance record per fixture and probe, with SHA-256 hashes |
| `authoring_intent/` | what was deliberately drawn, per drawing |
| `manifest.json` | index of every fixture with its hashes |

**Authoring intent is not ground truth.** `authoring_intent/` records what the generator drew. The
scored ground truth is authored, independently reviewed and frozen later under `ground_truth/`.

**Provenance sign-off is pending.** Author, ground-truth reviewer and provenance approver are
recorded as `PENDING`; no person is named by the generator.

Regenerate and validate (repository root):

```
python docs/qualification/fixtures/generate_fixtures.py
python docs/qualification/fixtures/validate_fixtures.py
```

Output is byte-identical for a given Pillow version (the version is recorded in each record).

Git note: the repository ignores `*.pdf`. The PDFs here are reproducible from the generator and are
identified by the recorded SHA-256; committing the PDFs themselves needs a deliberate, recorded
exception (see section 16 of the specification).
