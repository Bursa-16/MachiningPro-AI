# MachiningPro AI — Lapping Engineering Core

**Stage:** 3L
**Status:** Implemented
**Rule ID range:** R-3001 – R-3099

---

## Content Classification

| Tag | Meaning |
|---|---|
| `DETERMINISTIC` | Reproducible from explicit inputs alone |
| `GEOMETRIC_MODEL` | Exact geometry; no empirical terms |
| `EMPIRICAL` | Requires provenance-backed data; no universal value |
| `MANUFACTURER_DERIVED` | From machine/abrasive manufacturer guidelines |
| `STANDARD_DERIVED` | From ISO or equivalent |
| `AI_ADVISORY` | AI suggestion; never overrides deterministic results |

---

## 1. Purpose

Stage 3L implements the deterministic calculation foundation for lapping
operations: pressure, volume, thickness, MRR from measurement, and cycle time.

It also provides a clearly named **empirical evaluator** for the Preston model
(`estimate_lapping_removal_rate_preston`) with mandatory provenance gating.

Stage 3L does **not** recommend abrasive grades, slurry concentrations, plate
materials, or Preston coefficients. Those are `EMPIRICAL` and belong to
provenance-verified Stage 3G data records.

---

## 2. Engineering Authority Model

Same as Stage 3K:

```
AUTHORITATIVE : deterministic physics (R-3001–R-3005)
SOURCE-BOUNDED: provenance-verified empirical data (Stage 3G pattern)
ADVISORY ONLY : AI suggestions — never overrides
```

---

## 3. Thickness Unit Convention

All thickness values use **MM** (millimetres), not micrometres.

Reason: `Unit.UM` is not in the current Unit enum.

**Conversion at call site:** 1 µm = 0.001 mm.

```python
# 3 µm target removal:
removed_thickness = Quantity.of("0.003", Unit.MM)
```

---

## 4. Deterministic Rule Inventory

### R-3001 — Contact Pressure `DETERMINISTIC`

```
P = F / A     [MPa]   (1 N/mm² ≡ 1 MPa — exact dimensional identity)
```

| Input | Supply as | Constraint |
|---|---|---|
| F (normal force) | Quantity[N] | > 0 |
| A (contact area) | Decimal (mm²) | > 0 |

Note: `contact_area` is supplied as raw `Decimal` because `Unit.MM2` is not
in the current Unit enum.

---

### R-3002 — Removed Volume `GEOMETRIC_MODEL`

```
V = A × Δh     [mm³]
```

| Input | Supply as | Constraint |
|---|---|---|
| A (contact area) | Decimal (mm²) | > 0 |
| Δh (removed thickness) | Quantity[MM] | > 0 |

---

### R-3003 — Volumetric MRR from Measurement `DETERMINISTIC`

```
MRR_vol = V / t     [mm³/min]
```

**This is NOT the Preston model.** This computes MRR from a **measured**
removal volume and measured time. Use it for process characterization and
K_p calibration. Use `estimate_lapping_removal_rate_preston` for prediction.

---

### R-3004 — Removed Thickness `DETERMINISTIC`

```
Δh = V / A     [mm]
```

Inverse of R-3002. Round-trip consistent: R-3002 then R-3004 recovers Δh.

---

### R-3005 — Cycle Time `DETERMINISTIC`

```
t = V_target / MRR_vol     [min]
```

The caller is responsible for the provenance of `MRR_vol`. It may come from:
- R-3003 (measured) — deterministic given measurements
- `estimate_lapping_removal_rate_preston` — empirical; requires R-3053 first

---

## 5. Preston Empirical Evaluator

### `estimate_lapping_removal_rate_preston` `EMPIRICAL`

```
MRR_vol = K_p × P × v_r
```

**Model type:** EMPIRICAL. Not deterministic engineering truth.

| Parameter | Meaning | Requirement |
|---|---|---|
| K_p | Preston coefficient | MANDATORY — no default |
| P | Lapping pressure (MPa) | > 0 |
| v_r | Relative speed (m/min) | > 0 |
| k_provenance | Provenance record | source_reference must be non-None |

**Fail-closed:** missing or unverified K_p → `MachiningMathError`.

**Linearity caveat:** Preston assumes linear MRR dependence on P and v_r.
Non-linear behaviour at high pressure or speed is not modelled.

**K_p applicability:** K_p depends on workpiece material, abrasive type,
grit size, plate material, and slurry concentration. No global K_p exists.
Every K_p record must come from a calibrated, source-attributed test.

---

## 6. Validation Rules

### R-3051 — Pressure Range Warning `EMPIRICAL`

Warns when P < 0.005 MPa or P > 0.200 MPa.

This range is an **empirical guideline** for metal workpieces. Ceramics and
optics may legitimately fall outside it. Status: WARNING, not FAIL.

### R-3052 — Stock Removal Tolerance Guard `Physical constraint`

Fails when removed_thickness > max_allowance. Over-lapping is irreversible.
Status: FAIL.

### R-3053 — Preston K_p Provenance Guard `Architectural`

Fails when `kp_provenance_verified` is not True. Must be evaluated before
calling `estimate_lapping_removal_rate_preston`.

---

## 7. What Stage 3L Does NOT Implement

### Preston coefficient (K_p) `EMPIRICAL / MANUFACTURER_DERIVED`

No global or default K_p. Every K_p must arrive from a provenance-verified
`CuttingParameterRecord` (Stage 3G pattern, future `ParameterType.PRESTON_K`).

### Abrasive / plate / slurry selection `EMPIRICAL / MANUFACTURER_DERIVED`

Grit size, slurry concentration, plate material — all empirical; out of scope.

### Flatness / parallelism / TTV `MEASURED`

These are measurement results, not deterministic outputs of the lapping model.

### CMP chemical models `EMPIRICAL`

Chemical-mechanical planarization adds chemical reaction terms not modelled here.

### AI advisory `AI_ADVISORY`

Process sequence suggestions, K_p estimation aids — advisory, not authoritative.

---

## 8. Backend Module Structure

```
backend/machining/
    lapping.py          ← pure deterministic functions + Preston evaluator
    lapping_rules.py    ← EngineeringRule wrappers (R-3001–R-3053)

tests/unit/machining/
    test_lapping.py     ← 9 test classes, 40+ assertions including Preston guard
```

---

## 9. References

| Reference | Classification | Used for |
|---|---|---|
| Preston, F.W. (1927). Theory and Design of Plate Glass Polishing Machines. J. Soc. Glass Tech. 11, 214–256 | `STANDARD_DERIVED` | Preston MRR equation — original derivation |
| Deja, M. et al. (2020). Materials 13(6), 1343 | `STANDARD_DERIVED` | K_p model, modified Preston forms |
| Lapmaster-Wolters lapping application guide | `MANUFACTURER_DERIVED` | Plate material, pressure ranges |
| precision-surface.com — What is Lapping | `MANUFACTURER_DERIVED` | Process fundamentals |
