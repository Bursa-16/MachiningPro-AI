"""Deterministic DFM / process-feasibility validation functions (Stage 3I).

Answers questions of the form:

    "Is this feature geometrically and physically compatible with this
     process condition?"

Design principles
-----------------
* Pure functions — no side effects, no I/O, no AI.
* Fail-closed: missing required data → INSUFFICIENT_DATA, never PASS.
* No arbitrary thresholds: only geometric physics (e.g. tool must fit in
  slot) or explicitly supplied limit values.
* Feature and Tool domain models are reused unchanged.
* Stage 3H machine-capability results are composed, not duplicated.
* No tool recommendation, no machine recommendation, no process planning.

All functions return :class:`~backend.domain.result.EngineeringResult`.

Rule ID range: R-2701 – R-2712

Supported checks
----------------
R-2701  Hole / tool diameter compatibility
R-2702  Internal corner radius vs milling tool radius
R-2703  Slot width vs tool diameter
R-2704  Pocket / tool access (opening width vs tool diameter)
R-2705  Process–feature type compatibility
R-2706  Depth / diameter ratio (calculate + optional explicit-limit check)
R-2710  Machine capability composition (delegates to Stage 3H)
R-2712  Aggregate feasibility (ALL supplied check results)
"""

from __future__ import annotations

from decimal import Decimal

from backend.domain.enums import FeatureType, OperationType, ResultStatus
from backend.domain.feature import Feature
from backend.domain.result import (
    EngineeringResult,
    failure,
    insufficient_data,
    success,
    warning,
)
from backend.domain.tool import Tool
from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError

__all__ = [
    "check_hole_tool_diameter",
    "check_corner_radius_tool",
    "check_slot_width_tool",
    "check_pocket_access",
    "check_process_feature_compatibility",
    "check_depth_diameter_ratio",
    "compose_machine_result",
    "aggregate_feasibility",
]

_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_unit(q: Quantity, unit: Unit, name: str) -> None:
    if q.unit is not unit:
        raise MachiningMathError(
            f"{name} must be in {unit.value}, got {q.unit.value}"
        )


def _require_positive(v: Decimal, name: str) -> None:
    if v <= 0:
        raise MachiningMathError(
            f"{name} must be strictly positive, got {v}"
        )


def _get_dim(feature: Feature, key: str) -> Quantity | None:
    """Return feature.dimensions[key] or None."""
    return feature.dimensions.get(key)


# ---------------------------------------------------------------------------
# R-2701 — Hole / tool diameter compatibility
# ---------------------------------------------------------------------------

def check_hole_tool_diameter(
    feature: Feature,
    tool: Tool,
) -> EngineeringResult:
    """R-2701: Verify the drilling tool diameter matches the requested hole.

    For a simple drilling operation the tool diameter must equal the requested
    hole diameter.  Tolerance compensation and reaming sequences are not
    modelled here.

    The feature must carry ``dimensions["diameter"]`` in mm.

    Args:
        feature: A HOLE-type feature.  ``dimensions["diameter"]`` required.
        tool:    A DRILL-type tool.

    Returns:
        PASS              — tool diameter equals feature diameter.
        FAIL              — diameters differ.
        INSUFFICIENT_DATA — feature diameter is not provided.
    """
    rule_id = "R-2701"

    if feature.feature_type is not FeatureType.HOLE:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=(
                f"expected feature_type HOLE, got {feature.feature_type.value}",
            ),
            summary="R-2701 requires a HOLE feature",
        )

    hole_d = _get_dim(feature, "diameter")
    if hole_d is None:
        return insufficient_data(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            missing_inputs=("feature.dimensions['diameter']",),
            summary="hole diameter not specified in feature dimensions",
        )

    try:
        _require_unit(hole_d, Unit.MM, "feature diameter")
        _require_positive(hole_d.value, "feature diameter")
        _require_unit(tool.diameter, Unit.MM, "tool diameter")
    except MachiningMathError as exc:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=(str(exc),),
        )

    if tool.diameter.value != hole_d.value:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=(
                f"tool diameter {tool.diameter.value} mm ≠ "
                f"hole diameter {hole_d.value} mm "
                f"(feature {feature.feature_id!r}, tool {tool.tool_id!r})",
            ),
            outputs={
                "hole_diameter": hole_d,
                "tool_diameter": tool.diameter,
            },
            summary=(
                f"tool Ø{tool.diameter.value} mm does not match "
                f"hole Ø{hole_d.value} mm"
            ),
        )

    return success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        outputs={
            "hole_diameter": hole_d,
            "tool_diameter": tool.diameter,
        },
        summary=(
            f"tool Ø{tool.diameter.value} mm matches "
            f"hole Ø{hole_d.value} mm for feature {feature.feature_id!r}"
        ),
    )


# ---------------------------------------------------------------------------
# R-2702 — Internal corner radius vs milling tool radius
# ---------------------------------------------------------------------------

def check_corner_radius_tool(
    feature: Feature,
    tool: Tool,
) -> EngineeringResult:
    """R-2702: Verify the milling tool radius ≤ internal corner radius.

    For an internal corner (pocket or slot), the tool radius must not exceed
    the required internal corner radius.  This is geometric physics: a tool
    with a larger radius cannot machine a tighter corner.

    The feature must carry ``dimensions["corner_radius"]`` in mm.

    Args:
        feature: A feature with an internal corner (POCKET or SLOT).
                 ``dimensions["corner_radius"]`` required.
        tool:    A milling tool (END_MILL or FACE_MILL).

    Returns:
        PASS              — tool radius ≤ corner radius.
        FAIL              — tool radius > corner radius (cannot fit).
        INSUFFICIENT_DATA — corner radius not provided.
    """
    rule_id = "R-2702"

    corner_r = _get_dim(feature, "corner_radius")
    if corner_r is None:
        return insufficient_data(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            missing_inputs=("feature.dimensions['corner_radius']",),
            summary="corner radius not specified in feature dimensions",
        )

    try:
        _require_unit(corner_r, Unit.MM, "corner_radius")
        _require_positive(corner_r.value, "corner_radius")
        _require_unit(tool.diameter, Unit.MM, "tool diameter")
    except MachiningMathError as exc:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=(str(exc),),
        )

    tool_radius = tool.diameter.value / Decimal("2")

    if tool_radius > corner_r.value:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=(
                f"tool radius {tool_radius} mm > "
                f"internal corner radius {corner_r.value} mm: "
                f"tool {tool.tool_id!r} cannot machine feature {feature.feature_id!r}",
            ),
            outputs={
                "corner_radius": corner_r,
                "tool_radius": Quantity(value=tool_radius, unit=Unit.MM),
                "tool_diameter": tool.diameter,
            },
            summary=(
                f"tool radius {tool_radius} mm exceeds "
                f"corner radius {corner_r.value} mm"
            ),
        )

    clearance = corner_r.value - tool_radius
    return success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        outputs={
            "corner_radius": corner_r,
            "tool_radius": Quantity(value=tool_radius, unit=Unit.MM),
            "tool_diameter": tool.diameter,
            "corner_clearance_mm": Quantity(value=clearance, unit=Unit.MM),
        },
        summary=(
            f"tool radius {tool_radius} mm ≤ "
            f"corner radius {corner_r.value} mm: compatible"
        ),
    )


# ---------------------------------------------------------------------------
# R-2703 — Slot width vs tool diameter
# ---------------------------------------------------------------------------

def check_slot_width_tool(
    feature: Feature,
    tool: Tool,
) -> EngineeringResult:
    """R-2703: Verify the tool diameter ≤ slot width.

    A milling tool must physically fit within the slot.  If the tool is
    wider than the slot, machining is geometrically impossible.

    The feature must carry ``dimensions["width"]`` in mm.

    Args:
        feature: A SLOT feature.  ``dimensions["width"]`` required.
        tool:    A milling tool.

    Returns:
        PASS              — tool diameter ≤ slot width.
        FAIL              — tool diameter > slot width.
        INSUFFICIENT_DATA — slot width not provided.
    """
    rule_id = "R-2703"

    if feature.feature_type is not FeatureType.SLOT:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=(
                f"expected feature_type SLOT, got {feature.feature_type.value}",
            ),
            summary="R-2703 requires a SLOT feature",
        )

    slot_w = _get_dim(feature, "width")
    if slot_w is None:
        return insufficient_data(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            missing_inputs=("feature.dimensions['width']",),
            summary="slot width not specified in feature dimensions",
        )

    try:
        _require_unit(slot_w, Unit.MM, "slot width")
        _require_positive(slot_w.value, "slot width")
        _require_unit(tool.diameter, Unit.MM, "tool diameter")
    except MachiningMathError as exc:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=(str(exc),),
        )

    if tool.diameter.value > slot_w.value:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=(
                f"tool diameter {tool.diameter.value} mm > "
                f"slot width {slot_w.value} mm: "
                f"tool {tool.tool_id!r} cannot fit in slot {feature.feature_id!r}",
            ),
            outputs={
                "slot_width": slot_w,
                "tool_diameter": tool.diameter,
            },
            summary=(
                f"tool Ø{tool.diameter.value} mm exceeds "
                f"slot width {slot_w.value} mm"
            ),
        )

    margin = slot_w.value - tool.diameter.value
    return success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        outputs={
            "slot_width": slot_w,
            "tool_diameter": tool.diameter,
            "width_clearance_mm": Quantity(value=margin, unit=Unit.MM),
        },
        summary=(
            f"tool Ø{tool.diameter.value} mm fits in "
            f"slot width {slot_w.value} mm (margin {margin} mm)"
        ),
    )


# ---------------------------------------------------------------------------
# R-2704 — Pocket / tool access (opening width vs tool diameter)
# ---------------------------------------------------------------------------

def check_pocket_access(
    feature: Feature,
    tool: Tool,
) -> EngineeringResult:
    """R-2704: Verify the tool fits through the pocket opening.

    If the pocket opening is smaller than the tool diameter, the tool cannot
    enter the feature.  This is geometric physics.

    The feature must carry ``dimensions["opening_width"]`` in mm.

    Args:
        feature: A POCKET feature.  ``dimensions["opening_width"]`` required.
        tool:    A milling tool.

    Returns:
        PASS              — tool diameter ≤ pocket opening.
        FAIL              — tool diameter > pocket opening.
        INSUFFICIENT_DATA — opening width not provided.
    """
    rule_id = "R-2704"

    if feature.feature_type is not FeatureType.POCKET:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=(
                f"expected feature_type POCKET, got {feature.feature_type.value}",
            ),
            summary="R-2704 requires a POCKET feature",
        )

    opening_w = _get_dim(feature, "opening_width")
    if opening_w is None:
        return insufficient_data(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            missing_inputs=("feature.dimensions['opening_width']",),
            summary="pocket opening_width not specified in feature dimensions",
        )

    try:
        _require_unit(opening_w, Unit.MM, "opening_width")
        _require_positive(opening_w.value, "opening_width")
        _require_unit(tool.diameter, Unit.MM, "tool diameter")
    except MachiningMathError as exc:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=(str(exc),),
        )

    if tool.diameter.value > opening_w.value:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=(
                f"tool diameter {tool.diameter.value} mm > "
                f"pocket opening {opening_w.value} mm: "
                f"tool {tool.tool_id!r} cannot access pocket {feature.feature_id!r}",
            ),
            outputs={
                "opening_width": opening_w,
                "tool_diameter": tool.diameter,
            },
            summary=(
                f"tool Ø{tool.diameter.value} mm exceeds "
                f"pocket opening {opening_w.value} mm"
            ),
        )

    margin = opening_w.value - tool.diameter.value
    return success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        outputs={
            "opening_width": opening_w,
            "tool_diameter": tool.diameter,
            "access_margin_mm": Quantity(value=margin, unit=Unit.MM),
        },
        summary=(
            f"tool Ø{tool.diameter.value} mm fits in "
            f"pocket opening {opening_w.value} mm"
        ),
    )


# ---------------------------------------------------------------------------
# R-2705 — Process–feature type compatibility
# ---------------------------------------------------------------------------

#: Deterministic mapping from OperationType to compatible FeatureType values.
#: Only obvious, semantically unambiguous relationships are listed.
_PROCESS_FEATURE_COMPAT: dict[OperationType, frozenset[FeatureType]] = {
    OperationType.DRILLING: frozenset({FeatureType.HOLE}),
    OperationType.BORING: frozenset({FeatureType.HOLE, FeatureType.CYLINDRICAL_SURFACE}),
    OperationType.REAMING: frozenset({FeatureType.HOLE, FeatureType.CYLINDRICAL_SURFACE}),
    OperationType.TAPPING: frozenset({FeatureType.HOLE, FeatureType.THREAD}),
    OperationType.THREADING: frozenset({FeatureType.THREAD, FeatureType.CYLINDRICAL_SURFACE}),
    OperationType.MILLING: frozenset({
        FeatureType.POCKET, FeatureType.SLOT, FeatureType.PLANAR_FACE,
        FeatureType.CYLINDRICAL_SURFACE, FeatureType.GROOVE,
    }),
    OperationType.TURNING: frozenset({
        FeatureType.CYLINDRICAL_SURFACE, FeatureType.GROOVE,
        FeatureType.THREAD, FeatureType.PLANAR_FACE,
    }),
    OperationType.FACING: frozenset({FeatureType.PLANAR_FACE, FeatureType.CYLINDRICAL_SURFACE}),
    OperationType.GRINDING: frozenset({
        FeatureType.CYLINDRICAL_SURFACE, FeatureType.PLANAR_FACE,
    }),
    OperationType.HONING: frozenset({
        FeatureType.HOLE,
        FeatureType.CYLINDRICAL_SURFACE,
    }),
    OperationType.LAPPING: frozenset({
        FeatureType.PLANAR_FACE,
    }),
}


def check_process_feature_compatibility(
    feature: Feature,
    operation_type: OperationType,
) -> EngineeringResult:
    """R-2705: Check that the operation type is compatible with the feature type.

    Uses a deterministic, hard-coded compatibility table derived from
    process-engineering semantics.  Only obvious relationships are included.
    An operation type that is not in the table returns INSUFFICIENT_DATA.

    Args:
        feature:        The feature to check.
        operation_type: The intended process/operation.

    Returns:
        PASS              — operation is compatible with this feature type.
        FAIL              — operation is not compatible (geometric/semantic mismatch).
        INSUFFICIENT_DATA — operation type has no compatibility table entry.
    """
    rule_id = "R-2705"

    compatible_features = _PROCESS_FEATURE_COMPAT.get(operation_type)
    if compatible_features is None:
        return insufficient_data(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            missing_inputs=(f"compatibility table entry for {operation_type.value}",),
            summary=(
                f"no deterministic compatibility entry for operation "
                f"{operation_type.value!r}"
            ),
        )

    if feature.feature_type not in compatible_features:
        compat_names = ", ".join(sorted(f.value for f in compatible_features))
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=(
                f"operation {operation_type.value!r} is not compatible with "
                f"feature type {feature.feature_type.value!r} "
                f"(feature {feature.feature_id!r}); "
                f"compatible types: [{compat_names}]",
            ),
            summary=(
                f"{operation_type.value} cannot produce a "
                f"{feature.feature_type.value} feature"
            ),
        )

    return success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        summary=(
            f"operation {operation_type.value!r} is compatible with "
            f"feature type {feature.feature_type.value!r}"
        ),
    )


# ---------------------------------------------------------------------------
# R-2706 — Depth / diameter ratio
# ---------------------------------------------------------------------------

def check_depth_diameter_ratio(
    feature: Feature,
    explicit_limit: Decimal | None = None,
) -> EngineeringResult:
    """R-2706: Calculate depth/diameter ratio; optionally validate against limit.

    The depth/diameter ratio is a common process-capability indicator for
    holes and pockets.  This function calculates the ratio deterministically
    from feature dimensions.

    IMPORTANT — no threshold is hard-coded.  The ratio is ALWAYS reported.
    A PASS/FAIL against an explicit limit is possible ONLY when
    *explicit_limit* is supplied.  Without it, a WARNING is returned with
    the calculated ratio so the caller can decide.

    The feature must carry:
    - ``dimensions["depth"]`` in mm
    - ``dimensions["diameter"]`` in mm (for holes)
      OR ``dimensions["width"]`` in mm (for pockets/slots)

    Args:
        feature:        Feature with depth and diameter/width dimensions.
        explicit_limit: Optional caller-supplied Decimal threshold for the
                        depth/diameter ratio.  Must be > 0 if provided.
                        Comes from governed empirical data or machine spec —
                        never invented by this function.

    Returns:
        PASS              — ratio ≤ explicit_limit (only when limit is supplied).
        WARNING           — ratio calculated but no limit supplied; caller decides.
        FAIL              — ratio > explicit_limit.
        INSUFFICIENT_DATA — depth or reference dimension not in feature.
    """
    rule_id = "R-2706"

    depth = _get_dim(feature, "depth")
    diameter = _get_dim(feature, "diameter") or _get_dim(feature, "width")

    missing: list[str] = []
    if depth is None:
        missing.append("feature.dimensions['depth']")
    if diameter is None:
        missing.append("feature.dimensions['diameter'] or ['width']")

    if missing:
        return insufficient_data(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            missing_inputs=tuple(missing),
            summary="depth or reference dimension not provided",
        )

    try:
        _require_unit(depth, Unit.MM, "depth")
        _require_positive(depth.value, "depth")
        _require_unit(diameter, Unit.MM, "diameter/width")  # type: ignore[arg-type]
        _require_positive(diameter.value, "diameter/width")  # type: ignore[union-attr]
    except MachiningMathError as exc:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=(str(exc),),
        )

    ratio = depth.value / diameter.value  # type: ignore[union-attr]
    ratio_qty = Quantity(value=ratio.quantize(Decimal("0.0001")), unit=Unit.DIMENSIONLESS)

    if explicit_limit is not None:
        if explicit_limit <= 0:
            return failure(
                result_id=f"{rule_id}.result",
                rule_id=rule_id,
                rule_version=_VERSION,
                violations=("explicit_limit must be strictly positive",),
            )
        if ratio > explicit_limit:
            return failure(
                result_id=f"{rule_id}.result",
                rule_id=rule_id,
                rule_version=_VERSION,
                violations=(
                    f"depth/diameter ratio {ratio.quantize(Decimal('0.0001'))} "
                    f"exceeds explicit limit {explicit_limit} "
                    f"for feature {feature.feature_id!r}",
                ),
                outputs={
                    "depth": depth,
                    "reference_dimension": diameter,  # type: ignore[dict-item]
                    "depth_diameter_ratio": ratio_qty,
                },
                summary=f"depth/diameter ratio {ratio:.4f} > limit {explicit_limit}",
            )
        margin = explicit_limit - ratio
        return success(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            outputs={
                "depth": depth,
                "reference_dimension": diameter,  # type: ignore[dict-item]
                "depth_diameter_ratio": ratio_qty,
                "ratio_margin": Quantity(
                    value=margin.quantize(Decimal("0.0001")),
                    unit=Unit.DIMENSIONLESS,
                ),
            },
            summary=(
                f"depth/diameter ratio {ratio:.4f} ≤ limit {explicit_limit}"
            ),
        )

    # No explicit limit — report ratio as WARNING so the caller can decide.
    return warning(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        warnings=(
            f"depth/diameter ratio is {ratio.quantize(Decimal('0.0001'))} "
            "for feature "
            f"{feature.feature_id!r}; no authoritative limit was supplied "
            "— caller must evaluate acceptability",
        ),
        outputs={
            "depth": depth,
            "reference_dimension": diameter,  # type: ignore[dict-item]
            "depth_diameter_ratio": ratio_qty,
        },
        summary=(
            f"depth/diameter ratio {ratio:.4f} calculated; "
            "no limit → caller decides"
        ),
    )


# ---------------------------------------------------------------------------
# R-2710 — Machine capability composition
# ---------------------------------------------------------------------------

def compose_machine_result(
    machine_result: EngineeringResult,
) -> EngineeringResult:
    """R-2710: Wrap a Stage 3H machine-capability result in a DFM envelope.

    This function does NOT re-evaluate machine capability.  It maps the
    Stage 3H result status into the DFM context, preserving all outputs
    and violations.

    Args:
        machine_result: A result from any Stage 3H check function
                        (check_spindle_speed, check_feed_rate, etc.).

    Returns:
        PASS              — the machine result was PASS.
        FAIL              — the machine result was FAIL.
        INSUFFICIENT_DATA — the machine result was INSUFFICIENT_DATA.
        WARNING           — the machine result was WARNING.
    """
    rule_id = "R-2710"

    # Re-emit with the R-2710 wrapper ID, preserving all data.
    status = machine_result.status

    if status is ResultStatus.PASS:
        return success(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            outputs=dict(machine_result.outputs),
            summary=f"machine capability check passed: {machine_result.summary}",
        )
    if status is ResultStatus.WARNING:
        return warning(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            warnings=machine_result.warnings or (
                f"machine capability warning: {machine_result.summary}",
            ),
            outputs=dict(machine_result.outputs),
            summary=f"machine capability warning: {machine_result.summary}",
        )
    if status is ResultStatus.FAIL:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=machine_result.violations or (
                f"machine capability check failed: {machine_result.summary}",
            ),
            outputs=dict(machine_result.outputs),
            summary=f"machine capability check failed: {machine_result.summary}",
        )
    # INSUFFICIENT_DATA
    return insufficient_data(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        missing_inputs=machine_result.missing_inputs or (
            "machine capability data unavailable",
        ),
        summary=(
            f"machine capability data insufficient: {machine_result.summary}"
        ),
    )


# ---------------------------------------------------------------------------
# R-2712 — Aggregate feasibility
# ---------------------------------------------------------------------------

def aggregate_feasibility(
    results: tuple[EngineeringResult, ...],
) -> EngineeringResult:
    """R-2712: Aggregate multiple individual check results into one status.

    Aggregation semantics:
    - FAIL if any result is FAIL (physical violation is definitive).
    - INSUFFICIENT_DATA if no FAIL exists but at least one INSUFFICIENT_DATA.
    - WARNING if no FAIL or INSUFFICIENT_DATA but at least one WARNING.
    - PASS only when ALL supplied results are PASS.

    Partial information can NEVER produce PASS.

    Args:
        results: Tuple of EngineeringResult instances from any Stage 3I or
                 Stage 3H check.  Empty tuple → INSUFFICIENT_DATA.

    Returns:
        Aggregated EngineeringResult with rule_id R-2712.
    """
    rule_id = "R-2712"

    if not results:
        return insufficient_data(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            missing_inputs=("at_least_one_check_result",),
            summary="no check results supplied — feasibility cannot be determined",
        )

    all_violations: list[str] = []
    all_missing: list[str] = []
    all_warnings: list[str] = []
    has_fail = False
    has_insufficient = False
    has_warning = False

    for result in results:
        if result.status is ResultStatus.FAIL:
            has_fail = True
            all_violations.extend(result.violations)
        elif result.status is ResultStatus.INSUFFICIENT_DATA:
            has_insufficient = True
            all_missing.extend(result.missing_inputs)
        elif result.status is ResultStatus.WARNING:
            has_warning = True
            all_warnings.extend(result.warnings)

    if has_fail:
        return failure(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            violations=tuple(all_violations),
            summary=(
                f"aggregate feasibility: FAIL "
                f"({sum(1 for r in results if r.status is ResultStatus.FAIL)} "
                f"check(s) failed out of {len(results)})"
            ),
        )

    if has_insufficient:
        return insufficient_data(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            missing_inputs=tuple(all_missing) or ("unspecified capability data",),
            summary=(
                f"aggregate feasibility: INSUFFICIENT_DATA "
                f"({sum(1 for r in results if r.status is ResultStatus.INSUFFICIENT_DATA)} "
                f"check(s) could not evaluate)"
            ),
        )

    if has_warning:
        return warning(
            result_id=f"{rule_id}.result",
            rule_id=rule_id,
            rule_version=_VERSION,
            warnings=tuple(all_warnings),
            summary=f"aggregate feasibility: WARNING ({len(results)} checks, all non-failing)",
        )

    return success(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        summary=f"aggregate feasibility: PASS (all {len(results)} checks passed)",
    )
