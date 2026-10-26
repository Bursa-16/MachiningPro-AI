# Material Intelligence Foundation

EPIC_01_MATERIAL_INTELLIGENCE_FOUNDATION  
Phase 2 — Implementation complete

## Architecture Overview

In-memory material catalog seeded at startup from `backend/materials/seed_catalog.py`.
Follows the same singleton registry pattern as MachineCatalog (`backend/machines/`).

```
backend/materials/
  __init__.py          — module marker
  models.py            — Pydantic API models (MaterialRecord, MaterialDetail, ...)
  catalog.py           — MaterialCatalog in-memory registry + search
  seed_catalog.py      — 19 MVP material records with provenance
  validation.py        — validation rules (no zero fill, no implausible values)
  import_pipeline.py   — JSON/CSV import with dry-run and idempotent load

backend/api/materials.py  — 6 REST endpoints registered in app.py
frontend/app/src/
  types/materials.ts        — TypeScript type definitions
  services/materials.ts     — API client functions
  pages/MaterialLibraryPage.tsx  — Browse UI with search, ISO filter, detail drawer
```

## Dataset Scope (19 MVP Records)

| ISO Group | Count | Materials |
|-----------|-------|-----------|
| P — Steel | 8 | C45, 42CrMo4, 16MnCr5, 20MnCr5, S355JR, S355J2, S235JR, Ck45 |
| M — Stainless | 3 | X5CrNi18-10/304, X2CrNiMo17-12-2/316L, 17-4PH/630 |
| K — Cast Iron | 2 | EN-GJL-250/GG25, EN-GJS-400-15/GGG40 |
| N — Non-Ferrous | 4 | 6061-T6, 6082-T6, 7075-T6, CuZn39Pb3/CW614N |
| S — Superalloys | 2 | Ti-6Al-4V (S_TITANIUM), Inconel 718 (S_NICKEL_HRSA) |

## Confidence Model

Every engineering value carries explicit confidence via `DataConfidence` enum:

| Level | Meaning |
|-------|---------|
| VERIFIED_STANDARD | Value from EN/DIN/ASTM/AMS published standard |
| MANUFACTURER_REFERENCE | From OEM datasheet |
| GENERAL_INDUSTRY | General industry reference; REFERENCE_ONLY badge in UI |
| ESTIMATED | Computed or interpolated; REFERENCE_ONLY badge in UI |
| UNKNOWN | Source unknown |

## Provenance Policy

- All hardness values from: EN 10083-1:2006, EN 10083-3:2006, EN 1561:2011, EN 1563:2011, ASTM B209, AMS 5662
- Strength values from: EN 10025:2004, EN 10083 series, ASTM A240, ASTM A564
- Density values from: Smithells Metals Reference Book (engineering handbooks)
- Cutting parameter envelopes: Programlar Kesici Takımlar general industry synthesis — REFERENCE_ONLY
- Tool compatibility: Programlar Sandvik matrix synthesis — REFERENCE_ONLY

## Condition-Aware Hardness Model

The same grade (e.g. 42CrMo4) has dramatically different behavior depending on heat treatment:
- Annealed: 190–225 HB
- Q+T 850°C/600°C: 260–310 HB

Hardness is stored per condition, never on the parent material record.
Hardness scale conversion is **not performed** — HB, HRC, HRB, HV remain in their native scales.

## Critical ISO S Group Constraint

ISO S must always be differentiated:
- `S_TITANIUM` — Ti alloys (low vc, thermal issues, CBN not suitable)
- `S_NICKEL_HRSA` — Nickel superalloys like Inconel (extreme work hardening, VERY_HIGH tool wear)

Never leave S group as `UNSPECIFIED` — the validation layer rejects it.

## Limitations (REFERENCE_ONLY Data)

**Cutting parameter envelopes are general industry reference data:**
- NOT OEM catalog values
- NOT validated for specific machine configurations
- NOT suitable for direct production use without manufacturer validation
- Vc ranges represent wide general industry envelopes, not recommended starting points

**Tool compatibility ratings:**
- From general industry synthesis
- NOT certified Sandvik/Kennametal/Iscar recommendations
- Conditional ratings require application-specific verification

## API Endpoints

```
GET /api/materials              — list with optional iso_group, family, search filters
GET /api/materials/iso-groups   — ISO 513 group metadata
GET /api/materials/summary      — aggregate statistics
GET /api/materials/search?q=    — full-text search
GET /api/materials/{id}         — full detail
GET /api/materials/{id}/machinability      — machinability + tool compat
GET /api/materials/{id}/cutting-context   — cutting parameter envelopes
```

## Process Planning Integration

`ProcessPlanRequest` now accepts optional `material_id: str | None`.
When provided:
- Looks up material from catalog
- Adds machinability advisory to plan limitations (REFERENCE_ONLY, additive)
- Never fails the plan if material lookup fails (try/except, additive only)

Engineering review also adds material Vc advisory to limitations when `material_iso_group` is set.

## Future Integration Points

- [ ] Material-specific cutting parameter selection (replace ISO-group-level defaults)
- [ ] Tool-material compatibility check integration with selection engine
- [ ] User-uploaded material records with provenance tracking
- [ ] Export to process plan BOM
- [ ] Link to Taylor coefficient data for tool life calculation
