# MachiningPro AI — Machining Math Foundation (Stage 3A)

**Status:** implemented

## Purpose

Stage 3A implements the deterministic mathematical foundation used by later
turning, milling and drilling modules. It calculates mathematically derived
values from explicit engineering inputs only.

**This stage does NOT recommend machining parameters.** It computes what the
math demands from what the caller provides.

## Architecture

```text
backend/machining/
    exceptions.py   MachiningMathError (derives from ValidationError)
    formulas.py     Pure deterministic functions returning Quantity
    rules.py        EngineeringRule wrappers returning EngineeringResult
    __init__.py     Re-exports
```

### Result contract

Two layers, both reusable:

1. **formulas.py** — pure functions returning `Quantity`. Use these when you
   just need a value. They validate units and physical bounds, fail closed
   on any violation, and use `Decimal` throughout.

2. **rules.py** — `EngineeringRule` subclasses that wrap each formula and
   return `EngineeringResult`. Use these for rule-registry participation,
   provenance, and the fail-closed `evaluate()` contract.

Both layers share the same validation logic; the rule layer only adds the
envelope.

## Formulas

### Symbol definitions

| Symbol | Meaning | Unit |
|--------|---------|------|
| Vc     | Cutting speed | m/min |
| n      | Spindle speed | rpm |
| D      | Tool/workpiece diameter | mm |
| f      | Feed per revolution | mm/rev |
| fr     | Feed rate | mm/min |
| z      | Tooth count | dimensionless (positive integer) |
| fz     | Feed per tooth | mm/tooth |
| ap     | Axial depth of cut | mm |
| ae     | Radial width of cut | mm |
| MRR    | Material removal rate | mm3/min |
| L      | Travel distance | mm |
| t      | Machining time | min |
| P      | Power | kW |
| T      | Torque | Nm |

### Cutting speed <-> spindle speed

```
n = (1000 * Vc) / (pi * D)        [Vc: m/min, D: mm, n: rpm]
Vc = (pi * D * n) / 1000
```

Validity: D > 0; Vc >= 0; n >= 0.

### Turning / drilling feed

```
fr = n * f                          [n: rpm, f: mm/rev, fr: mm/min]
f = fr / n                          [n > 0]
n = fr / f                          [f > 0]
```

### Milling feed

```
fr = n * z * fz                     [n: rpm, z: positive int, fz: mm/tooth]
fz = fr / (n * z)                   [n > 0, z > 0]
n = fr / (z * fz)                   [z > 0, fz > 0]
z = fr / (n * fz)                   [result must be positive integer]
```

### Material removal rate (milling)

```
MRR = ap * ae * fr                  [ap: mm, ae: mm, fr: mm/min, MRR: mm3/min]
```

### Machining time

```
t = L / fr                          [L: mm >= 0, fr: mm/min > 0, t: min]
```

### Power / torque (rotational SI relation)

SI derivation: P(W) = T(Nm) * omega(rad/s), omega = 2*pi*n/60.
With P in kW:

```
T = (P * 60000) / (2 * pi * n)     [P: kW, n: rpm > 0, T: Nm]
P = (2 * pi * n * T) / 60000        [T: Nm, n: rpm >= 0, P: kW]
```

Constant 60000 = 60 (s/min) * 1000 (W/kW).

## Precision policy

- Pi is a 50-significant-digit `Decimal` literal (far exceeds any
  engineering requirement).
- All intermediate arithmetic stays in `Decimal` — binary float is never
  introduced inside a formula.
- Division uses exact `Decimal` arithmetic; callers needing rounded display
  values can quantize the result.

## Failure conditions

All formulas fail closed (raise `MachiningMathError`) for:

- Wrong unit for any argument
- Zero denominator where division is required
- Negative values where physically impossible (diameter, spindle speed
  in inverse relations, distances, depths, power, torque)
- Non-positive or non-integer tooth count
- Zero cutting speed is valid (produces zero rpm); zero diameter is not
- Zero feed rate in time calculation is invalid; zero distance is valid
  (produces zero time)

Nothing is silently clamped, normalized, or guessed.

## What Stage 3A deliberately does NOT calculate

- Cutting-speed recommendations (no material data)
- Feed recommendations (no tool/process data)
- Material-specific parameters
- Specific cutting force (Kc) or cutting-force prediction
- Taylor tool-life equations
- Surface-roughness prediction
- Heat generation or chatter analysis
- Turning MRR (deferred — needs explicit modeling choice)
- Rapid moves, acceleration, tool changes, dwell, setup time
- CAM, G-code, AI/RAG, database, API, frontend

These belong to later stages.

## Rule IDs

| ID | Formula | Domain |
|----|---------|--------|
| R-2001 | n = 1000*Vc/(pi*D) | machining.speed |
| R-2002 | Vc = pi*D*n/1000 | machining.speed |
| R-2003 | fr = n*f | machining.feed |
| R-2004 | f = fr/n | machining.feed |
| R-2005 | n = fr/f | machining.feed |
| R-2006 | fr = n*z*fz | machining.feed.milling |
| R-2007 | fz = fr/(n*z) | machining.feed.milling |
| R-2008 | n = fr/(z*fz) | machining.feed.milling |
| R-2009 | z = fr/(n*fz) | machining.feed.milling |
| R-2010 | MRR = ap*ae*fr | machining.removal |
| R-2011 | t = L/fr | machining.time |
| R-2012 | T = P*60000/(2*pi*n) | machining.power |
| R-2013 | P = 2*pi*n*T/60000 | machining.power |

## Units added

`MM3_MIN = "mm3/min"` and `MIN = "min"` added to `backend.domain.units.Unit`.

## Out of scope

- Empirical machining constants
- Material-specific cutting speeds
- Kc / specific cutting force tables
- Tool-life constants (Taylor coefficients)
- Efficiency assumptions
- Machine-specific constants
- Manufacturer recommendations
- Any value not explicitly supplied as a function input
