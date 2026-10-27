# GD&T Intelligence API

EPIC_04B Phase 3 — Advanced GD&T Intelligence API and UI

## Overview

Five bounded API endpoints expose the GD&T intelligence domain models
implemented in EPIC_04B Phase 2 (bonus tolerance, virtual condition, validation
rules, datum reference frames, composite FCFs).

**Safety invariants (always enforced):**
- `FABRICATED_GDT_VALUE=NO`
- `FABRICATED_ACTUAL_SIZE=NO` — actual_size_mm must come from the caller
- `FABRICATED_BONUS_TOLERANCE=NO`
- `FABRICATED_VIRTUAL_CONDITION=NO`
- `AUTO_INTERPRETATION_MARKED_APPROVED=NO` — all interpretations return `approval_status=PENDING_REVIEW`

All endpoints return `disclaimer: "Results are REFERENCE_ONLY"`.

---

## Endpoints

### GET /api/gdt/schema

Returns the supported GD&T capabilities.

**Response:**
```json
{
  "characteristics": ["POSITION", "PERPENDICULARITY", "FLATNESS", ...],
  "feature_modifiers": ["NONE", "MMC", "LMC", "RFS", ...],
  "datum_boundary_modifiers": ["RMB", "MMB", "LMB"],
  "tolerance_zone_geometries": ["CYLINDRICAL", "TWO_PARALLEL_PLANES", ...],
  "feature_of_size_kinds": ["INTERNAL_CYLINDRICAL", "EXTERNAL_CYLINDRICAL", ...],
  "confidence_states": ["EXACT_STRUCTURED", "RULE_PARSED", ...],
  "ambiguity_kinds": ["MISSING_DATUM", "INVALID_MODIFIER_COMBO", ...],
  "inspection_methods": ["CMM", "ROUNDNESS_TESTER", ...],
  "validation_rule_ids": ["VAL-GDT-001", ..., "VAL-GDT-010"],
  "disclaimer": "..."
}
```

---

### POST /api/gdt/validate

Validates a Feature Control Frame against semantic rules VAL-GDT-001 to VAL-GDT-010.

**Request:**
```json
{
  "req_id": "GDT-001",
  "fcf": {
    "characteristic": "POSITION",
    "tolerance_value": 0.05,
    "diameter_zone": true,
    "modifier": "MMC",
    "datum_frame": {"primary": {"label": "A", "precedence": 1}}
  },
  "fos": {
    "fos_id": "FOS-H001",
    "kind": "INTERNAL_CYLINDRICAL",
    "upper_limit_mm": 25.021,
    "lower_limit_mm": 25.000
  }
}
```

**Response:**
```json
{
  "req_id": "GDT-001",
  "overall": "VALID",
  "findings": [
    {
      "rule_id": "VAL-GDT-003",
      "passed": true,
      "severity": "INFO",
      "message": "VAL-GDT-003 passed for GDT-001",
      "ambiguity_kind": null,
      "suggested_resolution": null
    }
  ],
  "disclaimer": "..."
}
```

`overall` values: `VALID` | `INVALID` | `INSUFFICIENT_DATA`

---

### POST /api/gdt/interpret

Returns structured interpretation of an FCF with process and inspection implications.

**Response includes:**
- `characteristic`, `tolerance_value`, `modifier_description`
- `tolerance_zone` — geometry type and dimensions
- `datum_frame` — primary/secondary/tertiary with boundary modifiers
- `fos_context` — FOS kind, limits, derived MMC/LMC sizes
- `process_implications` — R-RT-GDT-001 through R-RT-GDT-006 route constraints
- `inspection_implications` — differentiated inspection methods (CMM, roundness tester, etc.)
- `ambiguities` — detected semantic issues
- `confidence` — `RULE_PARSED` or `AMBIGUOUS`
- `approval_status` — always `PENDING_REVIEW`

---

### POST /api/gdt/bonus-tolerance

Computes bonus tolerance for an MMC/LMC FCF + FOS pair.

Returns `computed=false` with `reason_not_computed="INSUFFICIENT_DATA: actual_size_mm is None"`
when actual size is absent. **The caller must supply the measured actual size.**

**Formula (ASME Y14.5-2018):**
- Internal MMC: bonus = actual − MMC_size
- Internal LMC: bonus = LMC_size − actual
- External MMC: bonus = MMC_size − actual
- External LMC: bonus = actual − LMC_size
- Total = stated_tolerance + bonus

---

### POST /api/gdt/virtual-condition

Computes the virtual condition boundary for a cylindrical FOS.

**Formula:**
- Internal MMC: VC = MMC_size − geometric_tolerance
- Internal LMC: VC = LMC_size + geometric_tolerance
- External MMC: VC = MMC_size + geometric_tolerance
- External LMC: VC = LMC_size − geometric_tolerance
- RFS: not applicable (computed=false)

---

## GD&T Intelligence Panel (Frontend)

Route: `/app/planning-quality/gdt-intelligence`

The panel provides five tabs:

| Tab | Description |
|-----|-------------|
| Interpret FCF | Full structured interpretation with process/inspection implications |
| Validate FCF | Semantic rule validation (VAL-GDT-001–010) |
| Calculate Bonus | Bonus tolerance with actual size input |
| Calculate Virtual Condition | VC for internal/external cylindrical features |
| Supported Capabilities | Schema listing |

### Engineer Review Workflow

Every interpretation starts at `PENDING_REVIEW`. The engineer must:
1. **Confirm** — marks the interpretation as reviewed and accepted
2. **Edit** — returns to PENDING_REVIEW for re-submission
3. **Reject** — marks interpretation as not valid for this feature

`AUTO_INTERPRETATION_MARKED_APPROVED=NO` — the system never auto-approves.

---

## Validation Rules

| Rule | Severity | Description |
|------|----------|-------------|
| VAL-GDT-001 | ERROR | Form tolerances must NOT reference a datum |
| VAL-GDT-002 | WARNING | Location/orientation/runout SHOULD have a datum |
| VAL-GDT-003 | ERROR | MMC/LMC only valid on true feature-of-size |
| VAL-GDT-004 | ERROR | Form tolerances cannot carry MMC/LMC |
| VAL-GDT-006 | ERROR | Composite FCF lower segment must be ≤ upper |
| VAL-GDT-007 | WARNING | TOTAL_RUNOUT without datum axis |
| VAL-GDT-008 | INFO | Legacy characteristic advisory (CONCENTRICITY/SYMMETRY) |

---

## Limitations

- Virtual condition is computed for CYLINDRICAL FOS only (internal/external)
- Bonus tolerance requires the caller to supply the measured actual size
- All results are REFERENCE_ONLY — DRAFT status
- Engineering review is required before manufacturing use
- The system does not enforce full GD&T standards compliance

## Human Confirmation Policy

No GD&T interpretation generated by MachiningPro AI becomes approved without
explicit engineer confirmation. This applies even when all validation rules pass.
`AUTO_INTERPRETATION_MARKED_APPROVED=NO` is enforced at the API level.
