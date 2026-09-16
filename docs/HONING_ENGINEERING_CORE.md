# MachiningPro AI — Honing Engineering Core

**Stage:** 3K
**Status:** Implemented
**Rule ID range:** R-2901 – R-2999

---

## Content Classification

Every item in this document is explicitly classified as one of:

| Tag | Meaning |
|---|---|
| `DETERMINISTIC` | Reproducible from explicit inputs alone; no empirical coefficients |
| `GEOMETRIC_MODEL` | Exact geometry; no empirical terms |
| `EMPIRICAL` | Requires provenance-backed data; no universal value exists |
| `MANUFACTURER_DERIVED` | Sourced from honing machine/stone manufacturer guidelines |
| `STANDARD_DERIVED` | From ISO, ASME, or equivalent standards |
| `AI_ADVISORY` | AI suggestion layer; never overrides deterministic results |

---

## 1. Purpose

Stage 3K implements the deterministic kinematic and geometric foundation for
honing operations. It establishes all formulas needed to compute honing speeds,
angles, stock removal, and removed volume from explicit engineering inputs.

Stage 3K does **not** recommend cutting parameters, abrasive grades, stone
pressures, overtravels, or coolant types. Those are `EMPIRICAL` or
`MANUFACTURER_DERIVED` and belong to provenance-governed data records.

---

## 2. Engineering Authority Model

```
AUTHORITATIVE : deterministic physics (Stage 3K formulas)
SOURCE-BOUNDED: empirical data with verified Provenance (Stage 3G pattern)
ADVISORY ONLY : AI suggestions — never overrides either layer
```

---

## 3. Process Definition

Honing is a precision bore-finishing process. The honing head simultaneously
rotates (peripheral motion) and reciprocates axially (stroke motion), creating
a characteristic crosshatch pattern on the bore wall.

**Primary geometry target:** roundness, cylindricity, bore diameter.
**Secondary target:** surface texture (crosshatch angle, Ra, Rz, Rk family).

---

## 4. Crosshatch Angle Convention

**This is a critical convention. Ambiguous usage of "crosshatch angle" causes
engineering errors.**

`DETERMINISTIC` (R-2902, R-2903)

The angle computed and stored by Stage 3K is the **INCLUDED ANGLE** between
the two crossing groove families, as seen on the bore surface when unrolled flat.

```
          ← bore axis →
  ///////////////  ←── groove family A (up-strokes)
  \\\\\\\\\\\\\\\  ←── groove family B (down-strokes)
       ↑
   α_included = angle between A and B
              = 2 × arctan(v_h / v_p)
```

The **single-groove angle** (angle of one groove family relative to the bore
axis) is `α_included / 2`.

**Do not confuse the two.** Specification sheets from engine manufacturers
typically quote the included angle. Confirm before entering values.

| Application | Typical included α | Source |
|---|---|---|
| Engine cylinder (cast iron) | 30°–45° | `MANUFACTURER_DERIVED` |
| Hydraulic cylinder (sealing) | 40°–55° | `MANUFACTURER_DERIVED` |
| High-load bearing bore | 45°–60° | `MANUFACTURER_DERIVED` |

These ranges are **empirical guidelines**, not physical laws.

---

## 5. Deterministic Rule Inventory

### R-2901 — Peripheral Speed `DETERMINISTIC`

```
v_p = (π × D × n) / 1000     [m/min]
```

| Input | Unit | Constraint |
|---|---|---|
| D | MM | > 0 |
| n | RPM | > 0 |

Typical range: 15–60 m/min (long-stroke internal honing).

---

### R-2902 — Crosshatch Included Angle `DETERMINISTIC`

```
α_included = 2 × arctan(v_h / v_p)     [degrees, stored DIMENSIONLESS]
```

| Input | Unit | Constraint |
|---|---|---|
| v_h (stroke speed) | M_MIN | ≥ 0 |
| v_p (peripheral speed) | M_MIN | > 0 |

Zero stroke speed → α = 0° (pure rotation, no axial component).

---

### R-2903 — Required Stroke Speed `DETERMINISTIC`

```
v_h = v_p × tan(α_included / 2)     [m/min]
```

Inverse of R-2902. Constraints: 0° < α_included < 180°.

---

### R-2904 — Resultant Cutting Speed `DETERMINISTIC`

```
v_c = √(v_p² + v_h²)     [m/min]
```

Vector magnitude of peripheral and stroke components. At least one must be > 0.
Typical range: 12–120 m/min (0.2–2 m/s).

---

### R-2905 — Radial Stock Removal `DETERMINISTIC / GEOMETRIC_MODEL`

```
s_radial = (D_final − D_initial) / 2     [mm]
```

For internal bore honing: D_final > D_initial (bore is enlarged).

---

### R-2906 — Removed Volume `GEOMETRIC_MODEL`

```
V = (π / 4) × (D_final² − D_initial²) × L     [mm³]
```

Exact cylindrical annulus geometry. No empirical coefficients.

---

## 6. Validation Rules

### R-2951 — Peripheral Speed Upper-Bound Warning `EMPIRICAL`

Warns when v_p > 60 m/min.

This 60 m/min threshold is **empirical** (honing handbook practice). It is
not derived from first principles. Some short-bore or superfinishing
applications legitimately exceed it. Status: WARNING, not FAIL.

### R-2952 — Crosshatch Angle Bounds `EMPIRICAL`

Requires 20° ≤ α_included ≤ 60°.

These bounds are **empirical**, drawn from engine-manufacturer specifications.
Status: FAIL (outside this range the crosshatch pattern loses its functional
oil-retention or sealing properties for the applications this range covers).

### R-2953 — Positive Stock `Physical constraint`

Requires D_final > D_initial. Physical: honing can only enlarge a bore.
Status: FAIL.

---

## 7. What Stage 3K Does NOT Implement

### Overtravel `EMPIRICAL / MANUFACTURER_DERIVED`

The "overtravel = stone_length / 3" rule is a manufacturer-derived guideline,
not a universal physical law. It depends on bore geometry, stone stiffness,
and machine configuration. It is **not** implemented as a deterministic rule.

### Stone-length ratio `MANUFACTURER_DERIVED`

The "stone length ≤ 70% of bore length" guideline is similarly empirical.

### Stone/abrasive selection `EMPIRICAL / MANUFACTURER_DERIVED`

Grit size, bond type, and abrasive material are empirical and must come
from provenance-verified manufacturer data records (Stage 3G pattern).

### Cycle time `EMPIRICAL`

Cycle time requires a radial MRR (material removal rate per unit time), which
is empirical — it depends on stone pressure, abrasive hardness, workpiece
material, and cooling. Not modelled deterministically.

### Surface parameters `MEASURED / SPECIFIED`

Ra, Rz, Rk, Rpk, Rvk, Mr1, Mr2 are:
- **MEASURED** when reporting actual surface texture
- **SPECIFIED** when stating a target
- **NOT calculated** deterministically from honing kinematics alone
  (no deterministic formula maps v_p / v_h directly to Ra)

### AI advisory `AI_ADVISORY`

Process sequence recommendations, parameter tuning, and material-abrasive
compatibility suggestions are AI_ADVISORY and never override deterministic results.

---

## 8. Backend Module Structure

```
backend/machining/
    honing.py           ← pure deterministic functions (R-2901–R-2906)
    honing_rules.py     ← EngineeringRule wrappers (R-2901–R-2953)

tests/unit/machining/
    test_honing.py      ← 9 test classes, 40+ assertions
```

---

## 9. References

| Reference | Classification | Used for |
|---|---|---|
| Schwarz, E. (Ed.), Handbook of Machining and Metalworking Calculations, McGraw-Hill, 2001 | `STANDARD_DERIVED` | Kinematic formulas |
| Performance impact of honing dynamics, ScienceDirect 2012 | `STANDARD_DERIVED` | α = 2×arctan(v_h/v_p) derivation |
| Barnes Honing — Stroke Honing Impact on Bore Shapes | `MANUFACTURER_DERIVED` | Overtravel, barrel/bellmouth guidelines |
| Sunnen Products Company honing handbook | `MANUFACTURER_DERIVED` | Peripheral speed guideline |
| ISO 74344 | `STANDARD_DERIVED` | Surface texture for honed surfaces |
| ISO 13565-2 | `STANDARD_DERIVED` | Rk / Rpk / Rvk parameter definitions |
| Engine manufacturer specifications (generic) | `MANUFACTURER_DERIVED` | Crosshatch angle range 30°–45° |
