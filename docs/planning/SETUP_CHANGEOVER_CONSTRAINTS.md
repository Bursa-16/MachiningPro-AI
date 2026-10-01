# Sequence-Dependent Setup/Changeover Constraints (PLANNING-01G)

## Status

This is the first stage that actually charges setup/changeover time in the
CP-SAT model. Before this stage, `backend/planning/solver_models.py` and
`backend/planning/optimizer_adapter.py` contained **no setup/changeover
modeling of any kind** — `optimizer_adapter.py`'s own module docstring
explicitly disclaimed it ("Explicitly NOT implemented here: the setup
matrix ... Those are later stages"), and `backend.planning.models.SetupMatrix`
existed only as an unused, standalone data type. This document describes
what this stage adds, from scratch, with direct-adjacency correctness built
in from the start rather than retrofitted onto a pre-existing (and, per the
originating ticket, allegedly defective) model.

## The problem this model solves

A naive "setup between any earlier operation and any later operation on the
same machine" model is wrong: for a machine sequence `A -> B -> C`, only the
transitions `A -> B` and `B -> C` are real changeovers. `A -> C` is not a
changeover at all — `B` is physically on the machine between them. Charging
`setup(A, C)` in that situation is a modeling defect, not a conservative
approximation: it can make a genuinely feasible schedule appear infeasible,
or under-utilize machine time that was never actually needed.

**The requirement:** setup/changeover time applies *only* between two
operations that end up directly, immediately consecutive on the same
machine in the solved schedule. Never between an operation and some other,
non-adjacent operation that merely comes later in the same machine's
sequence.

## Data model (unchanged, PLANNING-01C)

`backend.planning.models.SetupMatrix` is the source of truth for setup
durations: one matrix per machine, an exact `(from_setup_key,
to_setup_key) -> timedelta` lookup via `SetupMatrix.lookup()`. A missing
transition either raises `UnknownSetupTransitionError` (`policy =
MissingTransitionPolicy.NOT_ALLOWED`, the default) or falls back to a
configured `default_duration` (`policy = MissingTransitionPolicy.
DEFAULT_FALLBACK`). This stage does not change `SetupMatrix` at all — it
wires it into the solver pipeline for the first time.

## Opt-in, two levels

Setup-aware scheduling is opt-in at two levels, both defaulting to "off" so
existing (PLANNING-01B/E/F) callers and tests are entirely unaffected:

1. **Per problem** — `scheduler.schedule_routing(..., setup_keys=None,
   setup_matrices=None)`. Both are `None` by default. Supplying one without
   the other raises `InvalidSolverProblemError` immediately — they must be
   supplied together, or both omitted.
2. **Per machine** — `setup_matrices` is `machine_id -> SetupMatrix`. A
   machine with no entry here never has setup charged for operations placed
   on it, even when the overall problem is setup-aware. This mirrors the
   existing per-machine opt-in pattern calendar-awareness
   (`machine_calendars`) already uses in this codebase.

`setup_keys` is `operation_id -> setup_key` (only operations that could
actually reach a setup-aware machine need an entry — enforced, see below).

## Resolution: static data, resolved before the solver ever runs

Every *candidate* setup transition — every ordered pair of operations that
could conceivably both land on the same setup-aware machine (i.e. that
machine appears in both operations' eligible sets) — is resolved via
`SetupMatrix.lookup()` in Python, in `scheduler._resolve_setup_matrix_seconds()`,
**before** a `SolverProblem` is even constructed. *Whether* a transition is
resolvable is static data, not a solver decision, so it is validated
statically: an unresolvable transition under `NOT_ALLOWED` raises
`UnknownSetupTransitionError` at build time, never mid-solve. *Which* pairs
end up actually adjacent, in contrast, **is** a solver decision — that is
the whole point of the direct-adjacency model below.

The resolved result is a plain, solver-neutral structure —
`SolverProblem.setup_matrix_seconds: Mapping[str, Mapping[tuple[str, str], int]]`
(`machine_id -> {(from_key, to_key): seconds}`) — so `optimizer_adapter.py`
never needs to know about `SetupMatrix`, `MissingTransitionPolicy`, or
`UnknownSetupTransitionError` at all. This preserves the existing
solver-isolation boundary: `optimizer_adapter.py` remains the only module
in the package allowed to import `ortools`, and `solver_models.py` remains
free of any dependency on the domain/policy layer.

## The direct-adjacency model: `AddCircuit` per setup-aware machine

For each machine with an entry in `setup_matrix_seconds`, every operation
that could be assigned there (i.e. it already has a `presence` boolean from
the existing eligibility/calendar-filtering logic) becomes a node in a
single CP-SAT `AddCircuit` constraint, together with one synthetic **depot**
node representing "machine idle" / "sequence start-or-end":

- **Self-loop** (`node -> node`) — the operation is *not* assigned to this
  machine. The literal is simply that operation's existing `presence`
  boolean, negated — no separate variable, so this stays consistent with
  `AddExactlyOne`'s own assignment decision by construction.
- **`depot -> operation`** — this operation is first in the machine's
  sequence. No setup constraint of any kind is attached to this arc — this
  *is* the first-operation-no-initial-setup policy: it is not a special
  case handled elsewhere, it falls out of there being nothing to enforce
  here.
- **`operation -> depot`** — this operation is last.
- **`operation_i -> operation_j`** (both real, distinct) — `operation_j`
  immediately follows `operation_i`. Setup is enforced
  `OnlyEnforceIf` this exact arc literal:
  `start[j] >= end[i] + setup(i, j)`.
- **`depot -> depot`** (self-loop) — the machine is entirely unused (no
  candidate operation was assigned to it at all).

`AddCircuit` requires the true arcs to form a single Hamiltonian circuit
over every node whose self-loop is false, with excluded nodes self-looping
instead. This is what makes **"no subtours" a structural property of the
model** rather than something checked after the fact: two or more disjoint
sub-cycles among the same machine's operations are not representable in a
single circuit at all — there is nothing to detect and forbid, because it
cannot be expressed in the first place.

Because a setup constraint is written **only** on a real `operation_i ->
operation_j` arc, and an arc only exists between two nodes that are
genuinely, immediately consecutive in the one circuit the machine's
sequence forms, a non-adjacent pair (some other operation sits between
them) is never joined by an arc at all — no setup constraint of any kind is
ever written for that pair. This is the entire fix, expressed as a modeling
fact rather than a runtime filter.

`AddNoOverlap` (from PLANNING-01B) still runs unconditionally for every
machine, setup-aware or not. On a setup-aware machine it is redundant with
what the circuit + setup-gap constraints already imply (a single, strictly
time-increasing chain), but redundant is not wrong, and leaving it
unconditional means machines untouched by this stage keep exactly their
prior behavior.

## Horizon safety

The CP-SAT variable-domain upper bound (`horizon`) is widened by
`len(operations) * SolverProblem.max_setup_seconds` — a safe, deliberately
loose upper bound (even a fully serial chain of every operation on one
machine, each preceded by the single largest observed setup duration, never
needs more room than that). This is exactly `0` when `setup_matrix_seconds`
is empty, so setup-unaware problems get precisely the same horizon as
before this stage existed.

## Independent post-solve validation

`scheduler._validate_solver_solution()` re-derives, purely from each
machine's *achieved* timeline (assignments sorted by `start`), which pairs
of operations actually ended up immediately consecutive, and re-verifies
the required setup gap for exactly those pairs — never any other pair. This
is deliberately independent of whichever CP-SAT circuit arcs the solver
internally chose (`SolverSolution` does not expose them at all): "adjacent"
here means "adjacent in the achieved schedule," which is the only
definition that matters for correctness, and it never trusts the solver's
own `OPTIMAL`/`FEASIBLE` claim alone — consistent with how every other
post-solve check in this module already works (see
`docs/planning/FINITE_CAPACITY_SCHEDULER.md`).

This check also produces the `{operation_id: required_setup_duration}`
mapping used to populate `ScheduleOperation.setup_start`/`setup_end`: the
changeover is modeled as finishing exactly at the later operation's
`start_time` (never later), spanning back by exactly the required duration.
A zero-duration transition is not recorded as a changeover window (`None`/
`None`) — `ScheduleOperation` itself requires `setup_end` strictly after
`setup_start` whenever both are set, and a zero-length transition is not a
changeover event worth recording.

## PLANNING-01G P1 fix: the setup span itself is calendar/maintenance-aware

The original version of this stage constrained only each operation's own
processing interval to lie inside a single availability window. That left a
real defect: for a realized transition `A -> B`, the required setup span
`[start(B) - setup(A, B), start(B))` was never itself checked against
calendar-available time. A plain timing gap
(`start[j] >= end[i] + setup(i, j)`) is *necessary* but not *sufficient* —
it is trivially satisfied by any idle time at all, calendar-available or
not, so a large overnight/shift-closure/maintenance gap could silently
"absorb" the required setup for free, without the model ever verifying the
setup itself happens during available machine time.

**Solver fix** (`optimizer_adapter.py`): for the same per-machine
availability-window containment already computed for each operation's own
processing interval (`chosen_windows_by_op_machine`), the setup-arc
constraint now also requires, `OnlyEnforceIf` both the arc literal and the
successor's chosen-window indicator, that the setup start
(`start[j] - setup_seconds`) not precede that same window's start offset.
Combined with the pre-existing requirement that the successor's own
processing interval fit inside that one window, this forces the entire
combined block — setup span through the successor's end — into a single
availability window; it can never be split across two windows. No new
calendar normalization is introduced; this reuses the existing
solver-facing `SolverAvailabilityWindow` structure and the window-choice
booleans already built for per-operation containment.

**Post-solve validation fix** (`scheduler.py`): `_validate_solver_solution()`
now additionally re-derives, for every consecutive realized transition with
a nonzero required setup duration, `setup_start = later.start - required`
and independently verifies that `[setup_start, later.end)` fits entirely
inside one of that machine's normalized availability windows (boundary-
inclusive at both ends: a setup starting exactly at a window's start, or a
successor ending exactly at a window's end, is allowed). This does not
trust CP-SAT's own `OPTIMAL`/`FEASIBLE` claim for this property any more
than any other post-solve check in this module does — it raises
`SchedulerResultValidationError` (no new exception type) if the check
fails, whether or not the solver believed the solution was valid.

Neither fix touches `AddCircuit`, the public `schedule_routing()` setup
API (`setup_keys`/`setup_matrices`), `SetupMatrix`, or
`MissingTransitionPolicy`.

## What is preserved unchanged

- **No forced machine assignment / alternative-machine flexibility** — the
  circuit's arcs are built from each machine's existing `presence`
  booleans; nothing about `AddExactlyOne` or the calendar-filtered
  candidate pool changes.
- **Asymmetric setup** — `(from_key, to_key)` and `(to_key, from_key)` are
  independent matrix entries; nothing here assumes symmetry.
- **Eligibility / calendar integration** — a node only exists in a
  machine's circuit if it already has a `presence` boolean, i.e. it
  survived both eligibility and (when calendar-aware) window filtering.
- **Independent post-solve validation** — extended, not replaced (see
  above).
- **First-operation-no-initial-setup policy** — a structural consequence of
  the `depot -> operation` arc carrying no setup constraint, not a special
  case.

## What is explicitly still not implemented

Tool/fixture/operator/material capacity constraints, rescheduling, a frozen
horizon, multi-objective optimization, and a fallback solver remain out of
scope for this stage, exactly as `optimizer_adapter.py`'s module docstring
has always said.
