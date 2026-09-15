# MachiningPro AI — Turning Core (Stage 3B)

**Status:** implemented

## Purpose

Stage 3B implements deterministic turning-specific engineering calculations.
All values are computed from EXPLICIT INPUTS. No parameter recommendations.

## Scope

1. External longitudinal turning geometry
2. Basic internal boring geometry
3. Facing
4. Radial stock removal
5. Depth-of-cut / diameter relationships
6. Pass count from explicit maximum depth-per-pass
7. Cutting/travel distance
8. Turning machining time
9. Removed volume (exact cylindrical annulus geometry)
10. Turning material removal rate (exact geometric)

## Architecture

```text
backend/machining/
    turning.py          Pure deterministic turning functions returning Quantity
    turning_rules.py    EngineeringRule wrappers (R-2101..R-2114)
```

Reuses Stage 3A formulas (`feed_rate_from_rpm_feed_per_rev`,
`machining_time_from_distance_feed_rate`) — no duplication.

## External Longitudinal Turning

```
radial_stock = (D_initial - D_final) / 2
D_final = D_initial - 2 * radial_depth
```

Validation: D_initial > 0, D_final > 0, D_final <= D_initial.

## Internal Boring

```
radial_stock = (D_final - D_initial) / 2
D_final = D_initial + 2 * radial_depth
```

Validation: D_initial > 0, D_final > 0, D_final >= D_initial.

## Pass Count

```
pass_count = ceil(total_radial_stock / max_radial_depth_per_pass)
equal_pass_depth = total_radial_stock / pass_count
```

`max_radial_depth_per_pass` is an explicit INPUT. Zero stock -> zero passes.
Equal pass depth never exceeds the supplied maximum.

## Removed Volume (Exact Geometry)

External turning:
```
V = (pi / 4) * (D_initial^2 - D_final^2) * L
```

Boring:
```
V = (pi / 4) * (D_final^2 - D_initial^2) * L
```

Facing (with explicit face depth):
```
V = (pi / 4) * (D_outer^2 - D_inner^2) * face_depth
```

## Turning Material Removal Rate

Average MRR from volume and time:
```
MRR = removed_volume / machining_time
```

Direct geometric average MRR:
```
MRR = (pi / 4) * (D_initial^2 - D_final^2) * feed_rate
```

This is a geometric material-removal rate, not cutting-force or power prediction.

## Longitudinal Turning Time

```
effective_travel = machining_length + approach_allowance + overtravel_allowance
feed_rate = rpm * feed_per_rev
time = effective_travel / feed_rate
```

No hidden default allowances. Zero allowances must be explicit.

## Facing

```
radial_travel = (D_outer - D_inner) / 2
effective_travel = radial_travel + explicit_allowances
time = effective_travel / feed_rate
```

**Limitation:** For constant-rpm facing, cutting speed changes continuously
with diameter. Stage 3B does NOT model CSS/G96 machine behavior.

## Units Added

`MM3 = "mm3"` added to `backend.domain.units.Unit`.

## Rule IDs

| ID | Calculation | Domain |
|----|-------------|--------|
| R-2101 | radial_stock = (D0-D1)/2 | turning.external.geometry |
| R-2102 | D1 = D0 - 2*ap | turning.external.geometry |
| R-2103 | radial_stock = (D1-D0)/2 | turning.boring.geometry |
| R-2104 | D1 = D0 + 2*ap | turning.boring.geometry |
| R-2105 | pass_count = ceil(stock/max_depth) | turning.external.passes |
| R-2106 | equal_pass_depth = stock/pass_count | turning.external.passes |
| R-2107 | V = (pi/4)*(D0^2-D1^2)*L | turning.external.volume |
| R-2108 | V = (pi/4)*(D1^2-D0^2)*L | turning.boring.volume |
| R-2109 | time = travel/feed_rate | turning.external.time |
| R-2110 | MRR = volume/time | turning.external.mrr |
| R-2111 | MRR = (pi/4)*(D0^2-D1^2)*fr | turning.external.mrr |
| R-2112 | facing_travel = (D_outer-D_inner)/2 + allowances | turning.facing.geometry |
| R-2113 | facing_time = travel/feed_rate | turning.facing.time |
| R-2114 | V = (pi/4)*(D_outer^2-D_inner^2)*face_depth | turning.facing.volume |

## Validation Rules

Fail closed for:
- Negative diameters
- Zero physically-required diameters
- External final diameter > initial diameter
- Boring final diameter < initial diameter
- Negative machining length, allowances, depth
- Depth removing more material than geometry permits
- Zero denominator
- Invalid feed/rpm where used in time calculation
- Non-positive maximum pass depth
- Incompatible units

Zero remains valid where physically meaningful (zero stock, zero travel,
zero volume, zero time from zero travel).

## What Stage 3B Does NOT Recommend

- Cutting speed
- Feed
- Depth of cut
- Pass depth
- Tool / insert
- Machine
- Coolant

All such values must be explicit inputs.

## Out of Scope

- Material-specific Vc
- Feed recommendations
- ap recommendations
- Insert selection
- Toolholder selection
- Machine selection
- CSS / G96 control strategy
- Threading, grooving, parting
- Taper turning, contour turning
- Tool nose radius compensation
- Cutting forces, Kc
- Tool life
- Chatter, deflection
- Surface roughness prediction
- CAM, G-code
- AI / RAG
- Database, API, frontend
