# Qualification ground truth (FROZEN)

Independent scoring reference for `docs/qualification/REAL_DRAWING_DEMO_QUALIFICATION.md`
(REAL_DRAWING_QUALIFICATION_03). Every record is `FROZEN`; changing one needs a new recorded
decision and an errata entry, never an edit in place.

## Source basis

Derived only from the self-authored fixture sources, the authoring-intent records, the visible
fixture content and the frozen specification. No model, OCR, R3B, job, review or run-log output was
read. `validate_ground_truth.py` audits the imports and literals of the builder for this.

## Files

| Path | Content |
|---|---|
| `manifest.json` | index: record file, type, class, fixture hashes, record hashes, status |
| `records/<QUAL_ID>.ground_truth.json` | recognition ground truth for Q01-Q10 (`items[]`) |
| `records/<PROBE_ID>.probe_expectation.json` | probe expectations; no recognition items |
| `build_ground_truth.py` | deterministic builder (reads fixtures and the spec only) |
| `validate_ground_truth.py` | mechanical validation and independence audit |

## Item schema (recognition records)

`item_id`, `feature_type` (LINEAR_DIMENSION, DIAMETER, HOLE_CALLOUT, RADIUS, ANGLE, TOLERANCE,
TITLE_BLOCK_TEXT, GDT_TRANSCRIPTION, GENERAL_TEXT), `expected_text` (verbatim as authored),
`expected_value` / `expected_unit` (mm, inch, degree; the number as printed),
`expected_normalized_value` (canonical decimal, no unit conversion), `expected_region`,
`required_for_demo`, `scoreable`, `deterministic_expectation`, `deterministic_scoreable`, `notes`.

- Tolerances add `tolerance {kind, plus, minus, unit}` taken from the authored text.
- GD&T frames are one item (`gdt_role = FEATURE_CONTROL_FRAME`) with `cells`; a frame whose
  characteristic is not on the deterministic allowlist has `negative_case = true`.
- `expected_region` is a **reference region** in fixture raster pixels (top-left origin, `[x0, y0, x1, y1]`
  of the printed text). It is never a model box. Application semantics are unchanged: the spatial
  authority is the caller-selected region extent and a model pixel box is not allowed.
- Items with identical text (for example two "30 mm") are distinct and are told apart by region.
- `scoreable` is the AI text-scoring flag. `deterministic_scoreable` marks items whose deterministic
  expectation can be scored (RQ06 and the DET_* metrics). `deterministic_expectation` states what the
  parser GRAMMAR accepts for the authored text; it is a static readback, not a parsing result.

## Probe records

`record_type = PROBE_EXPECTATION`. `fixture_class` is `STRUCTURAL_EXPECTATION` for refusal and failure
gates (P-VEC, P-OVER, P-DOWN) and `PROBE_EXPECTATION` for the P-CROP crops. Structural probes have
no recognition ground truth. A P-CROP record only lists which Q09 item ids lie inside the crop
(with crop-local reference regions); no text is duplicated.

## Review role

`ground_truth_review.role = GROUND_TRUTH_REVIEWER` is recorded as a role only. No named reviewer is
assigned (ROLE_SEPARATION_REQUIRED = NO for the initial internal qualification) and none is invented.
