"""NC program feed/spindle validation engine.

NC_FEED_SPINDLE_PROGRAM_VALIDATION_01 — Phase 2

Validates NC commanded feed and spindle values against:
  - Machine/tool/holder RPM limits
  - Calculated engineering values (Vc, fz, feed/rev)
  - Reference cutting-parameter ranges (ADVISORY only)

Safety constants enforced here:
    NC_COMMANDED_SPINDLE_SPEED_EQUALS_ACTUAL_RPM=NO
    NC_COMMANDED_FEED_EQUALS_ACTUAL_FEED=NO
    NC_COMMANDED_FEED_EQUALS_RECOMMENDED_FEED=NO
    REFERENCE_RANGE_VALIDATION_IS_OPTIMIZATION=NO
    NC_PROGRAM_AUTOMATIC_OPERATION_CLASSIFICATION=NO
    MISSING_LIMIT_AS_ZERO=NO
    MISSING_VALUE_AS_ZERO=NO
    SYNTHETIC_PARAMETER_RECORD_ADDED=NO
    FALSE_OPTIMIZATION_CLAIM=NO
    G84_PITCH_VALIDATION_IMPLEMENTED=NO
    GENERIC_FEED_WITHOUT_SPINDLE_WARNING_IMPLEMENTED=NO
    MACHINE_FEED_LIMIT_VALIDATION_IMPLEMENTED=NO
    G96_CSS_RPM_CALCULATED=NO
    SPINDLE_DIRECTION_COMPATIBILITY_CHECK_IMPLEMENTED=NO
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel

from backend.cutting_parameters.models import (
    ApplicabilityScope,
    ParameterType,
)
from backend.cutting_parameters.registry import CuttingParameterRegistry
from backend.domain.enums import IsoMaterialGroup, OperationType
from backend.domain.units import Quantity, Unit
from backend.interoperability.nc_motion import NcMotionResult
from backend.machining.exceptions import MachiningMathError
from backend.machining.formulas import (
    cutting_speed_from_spindle_speed,
    feed_per_rev_from_feed_rate,
    feed_per_tooth_from_feed_rate,
)

__all__ = [
    "NCValidationSeverity",
    "NCValidationStatus",
    "NCValidationFinding",
    "NCProgramValidationSummary",
    "validate_nc_feed_spindle",
]

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

# Operations where fz (feed per tooth) is the primary feed metric
_FZ_OPERATIONS = frozenset({
    OperationType.MILLING,
})

# Operations where feed/rev is the primary feed metric
_FEED_REV_OPERATIONS = frozenset({
    OperationType.TURNING,
    OperationType.FACING,
    OperationType.DRILLING,
    OperationType.BORING,
    OperationType.REAMING,
    OperationType.TAPPING,
    OperationType.THREADING,
})


class NCValidationSeverity(StrEnum):
    BLOCKING = "BLOCKING"
    WARNING = "WARNING"
    ADVISORY = "ADVISORY"
    INFO = "INFO"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class NCValidationStatus(StrEnum):
    WITHIN_LIMIT = "WITHIN_LIMIT"
    EXCEEDS_LIMIT = "EXCEEDS_LIMIT"
    WITHIN_REFERENCE_RANGE = "WITHIN_REFERENCE_RANGE"
    BELOW_REFERENCE_RANGE = "BELOW_REFERENCE_RANGE"
    ABOVE_REFERENCE_RANGE = "ABOVE_REFERENCE_RANGE"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_APPLICABLE = "NOT_APPLICABLE"


# ---------------------------------------------------------------------------
# Finding model
# ---------------------------------------------------------------------------


class NCValidationFinding(BaseModel):
    """One deterministic validation finding.

    message_key: i18n key for the user-facing message.
    All numeric values are raw floats with explicit units.
    """

    check_id: str
    severity: NCValidationSeverity
    status: NCValidationStatus
    observed_value: float | None = None
    observed_unit: str | None = None
    limit_or_reference: float | None = None
    limit_unit: str | None = None
    limit_source: str | None = None
    message_key: str
    limitations: list[str] = []

    # Immutable safety flags
    nc_commanded_spindle_speed_equals_actual_rpm: bool = False
    nc_commanded_feed_equals_actual_feed: bool = False


# ---------------------------------------------------------------------------
# Validation summary model
# ---------------------------------------------------------------------------


class NCProgramValidationSummary(BaseModel):
    """Deterministic NC feed/spindle validation summary.

    PATH_EVIDENCE_SHOULD_CARRY_VALIDATION_RESULTS=NO
    NC_COMMANDED_SPINDLE_SPEED_EQUALS_ACTUAL_RPM=NO
    NC_COMMANDED_FEED_EQUALS_ACTUAL_FEED=NO
    REFERENCE_RANGE_VALIDATION_IS_OPTIMIZATION=NO
    MACHINE_FEED_LIMIT_VALIDATION_IMPLEMENTED=NO
    """

    # Feed/spindle evidence from NC
    nc_commanded_feed_mm_min: float | None = None
    nc_commanded_feed_mm_rev: float | None = None
    nc_feed_mode: str | None = None
    nc_commanded_spindle_rpm: float | None = None
    nc_spindle_state: str | None = None

    # Calculated engineering values
    calculated_cutting_speed_m_min: float | None = None
    calculated_feed_per_tooth_mm: float | None = None
    calculated_feed_per_rev_mm: float | None = None

    # RPM limit findings
    machine_rpm_limit_check: NCValidationFinding | None = None
    tool_rpm_limit_check: NCValidationFinding | None = None
    holder_rpm_limit_check: NCValidationFinding | None = None
    effective_rpm_limit_check: NCValidationFinding | None = None

    # Engineering reference findings (ADVISORY)
    cutting_speed_check: NCValidationFinding | None = None
    feed_per_tooth_check: NCValidationFinding | None = None
    feed_per_rev_check: NCValidationFinding | None = None

    # Severity counters
    blocking_count: int = 0
    warning_count: int = 0
    advisory_count: int = 0
    insufficient_data_count: int = 0

    # Evidence and diagnostics
    limitations: list[str] = []
    evidence_sources: list[str] = []

    # Immutable safety flags
    nc_commanded_spindle_speed_equals_actual_rpm: bool = False
    nc_commanded_feed_equals_actual_feed: bool = False
    nc_commanded_feed_equals_recommended_feed: bool = False
    reference_range_validation_is_optimization: bool = False
    nc_program_automatic_operation_classification: bool = False
    machine_feed_limit_validation_implemented: bool = False
    g84_pitch_validation_implemented: bool = False
    generic_feed_without_spindle_warning_implemented: bool = False
    spindle_direction_compatibility_check_implemented: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _rpm_limit_check(
    check_id: str,
    limit_label: str,
    commanded_rpm: float,
    limit_rpm: int | None,
) -> NCValidationFinding:
    """Check commanded_rpm against one RPM limit.

    MISSING_LIMIT_AS_ZERO=NO — None limit → INSUFFICIENT_DATA.
    """
    if limit_rpm is None:
        return NCValidationFinding(
            check_id=check_id,
            severity=NCValidationSeverity.INSUFFICIENT_DATA,
            status=NCValidationStatus.INSUFFICIENT_DATA,
            observed_value=commanded_rpm,
            observed_unit="rpm",
            message_key="ncValRpmLimitInsuffData",
            limitations=[f"{limit_label}: max_rpm not published in catalog"],
        )
    if commanded_rpm > limit_rpm:
        return NCValidationFinding(
            check_id=check_id,
            severity=NCValidationSeverity.BLOCKING,
            status=NCValidationStatus.EXCEEDS_LIMIT,
            observed_value=commanded_rpm,
            observed_unit="rpm",
            limit_or_reference=float(limit_rpm),
            limit_unit="rpm",
            limit_source=limit_label,
            message_key="ncValRpmExceedsLimit",
        )
    return NCValidationFinding(
        check_id=check_id,
        severity=NCValidationSeverity.INFO,
        status=NCValidationStatus.WITHIN_LIMIT,
        observed_value=commanded_rpm,
        observed_unit="rpm",
        limit_or_reference=float(limit_rpm),
        limit_unit="rpm",
        limit_source=limit_label,
        message_key="ncValRpmWithinLimit",
    )


def _reference_range_check(
    check_id: str,
    value: float,
    unit_str: str,
    quantity: Quantity,
    registry: CuttingParameterRegistry,
    param_type: ParameterType,
    scope: ApplicabilityScope,
    message_key_prefix: str,
) -> NCValidationFinding:
    """Compare a derived value against matching reference records.

    REFERENCE_RANGE_VALIDATION_IS_OPTIMIZATION=NO — always ADVISORY.
    """
    records = registry.find(scope=scope, parameter_type=param_type)
    if not records:
        return NCValidationFinding(
            check_id=check_id,
            severity=NCValidationSeverity.INSUFFICIENT_DATA,
            status=NCValidationStatus.INSUFFICIENT_DATA,
            observed_value=value,
            observed_unit=unit_str,
            message_key=f"{message_key_prefix}NoRef",
            limitations=["No matching reference records for this operation/material/tool scope"],
        )

    # Use the first (sorted by record_id) matching record for comparison
    ref = records[0]
    try:
        qrange = ref.value_range
        is_within = qrange.contains(quantity)
        min_v = float(qrange.min_value.value)
        max_v = float(qrange.max_value.value)
        midref = (min_v + max_v) / 2.0

        if is_within:
            status = NCValidationStatus.WITHIN_REFERENCE_RANGE
            msg_key = f"{message_key_prefix}Within"
        elif value < min_v:
            status = NCValidationStatus.BELOW_REFERENCE_RANGE
            msg_key = f"{message_key_prefix}Below"
        else:
            status = NCValidationStatus.ABOVE_REFERENCE_RANGE
            msg_key = f"{message_key_prefix}Above"

        return NCValidationFinding(
            check_id=check_id,
            severity=NCValidationSeverity.ADVISORY,
            status=status,
            observed_value=value,
            observed_unit=unit_str,
            limit_or_reference=midref,
            limit_unit=unit_str,
            limit_source=ref.provenance.source_reference,
            message_key=msg_key,
            limitations=[
                "REFERENCE_RANGE_VALIDATION_IS_OPTIMIZATION=NO — "
                "comparison is advisory engineering guidance only"
            ],
        )
    except Exception:
        return NCValidationFinding(
            check_id=check_id,
            severity=NCValidationSeverity.INSUFFICIENT_DATA,
            status=NCValidationStatus.NOT_COMPARABLE,
            observed_value=value,
            observed_unit=unit_str,
            message_key=f"{message_key_prefix}NotComparable",
            limitations=["Unit or scope mismatch during reference comparison"],
        )


def _count_severities(findings: list[NCValidationFinding | None]) -> tuple[int, int, int, int]:
    blocking = warning = advisory = insuf = 0
    for f in findings:
        if f is None:
            continue
        if f.severity == NCValidationSeverity.BLOCKING:
            blocking += 1
        elif f.severity == NCValidationSeverity.WARNING:
            warning += 1
        elif f.severity == NCValidationSeverity.ADVISORY:
            advisory += 1
        elif f.severity == NCValidationSeverity.INSUFFICIENT_DATA:
            insuf += 1
    return blocking, warning, advisory, insuf


# ---------------------------------------------------------------------------
# Public validation function
# ---------------------------------------------------------------------------


def validate_nc_feed_spindle(
    motion_result: NcMotionResult,
    *,
    machine_spindle_max_rpm: int | None = None,
    machine_id: str | None = None,
    tool_max_rpm: int | None = None,
    tool_cutting_diameter_mm: float | None = None,
    tool_number_of_flutes: int | None = None,
    tool_id: str | None = None,
    holder_max_rpm: int | None = None,
    holder_id: str | None = None,
    operation_type: str | None = None,
    material_iso_group: str | None = None,
    cutting_param_registry: CuttingParameterRegistry | None = None,
) -> NCProgramValidationSummary:
    """Validate NC commanded feed/spindle values.

    Safety contract
    ---------------
    NC_COMMANDED_SPINDLE_SPEED_EQUALS_ACTUAL_RPM=NO
    NC_COMMANDED_FEED_EQUALS_ACTUAL_FEED=NO
    REFERENCE_RANGE_VALIDATION_IS_OPTIMIZATION=NO
    NC_PROGRAM_AUTOMATIC_OPERATION_CLASSIFICATION=NO
    MISSING_LIMIT_AS_ZERO=NO — missing limit ≠ zero or unlimited.
    MACHINE_FEED_LIMIT_VALIDATION_IMPLEMENTED=NO — no feed-axis field in catalog.
    G84_PITCH_VALIDATION_IMPLEMENTED=NO — deferred.
    GENERIC_FEED_WITHOUT_SPINDLE_WARNING_IMPLEMENTED=NO
    SPINDLE_DIRECTION_COMPATIBILITY_CHECK_IMPLEMENTED=NO
    """
    limitations: list[str] = []
    evidence_sources: list[str] = []

    # Extract evidence from motion result
    commanded_rpm = motion_result.nc_commanded_spindle_rpm
    feed_mode = motion_result.nc_feed_mode
    feed_mm_min = motion_result.nc_commanded_feed_mm_min
    feed_mm_rev = None

    # Gather feed_mm_rev from last segment that has it
    for seg in reversed(motion_result.segments):
        if seg.commanded_feed_mm_rev is not None:
            feed_mm_rev = seg.commanded_feed_mm_rev
            break

    if machine_id:
        evidence_sources.append(f"machine:{machine_id}")
    if tool_id:
        evidence_sources.append(f"cutting_tool:{tool_id}")
    if holder_id:
        evidence_sources.append(f"tool_holder:{holder_id}")
    if motion_result.parser_profile:
        evidence_sources.append(f"parser:{motion_result.parser_profile}")

    # -----------------------------------------------------------------------
    # RPM limit checks — only possible when RPM evidence exists
    # -----------------------------------------------------------------------
    machine_check: NCValidationFinding | None = None
    tool_check: NCValidationFinding | None = None
    holder_check: NCValidationFinding | None = None
    effective_check: NCValidationFinding | None = None

    if commanded_rpm is None:
        # No S word seen — all limit checks produce INSUFFICIENT_DATA
        machine_check = NCValidationFinding(
            check_id="MACHINE_RPM_LIMIT",
            severity=NCValidationSeverity.INSUFFICIENT_DATA,
            status=NCValidationStatus.INSUFFICIENT_DATA,
            message_key="ncValNoSpindleCommand",
            limitations=["S word not found in NC program"],
        )
        tool_check = NCValidationFinding(
            check_id="TOOL_RPM_LIMIT",
            severity=NCValidationSeverity.INSUFFICIENT_DATA,
            status=NCValidationStatus.INSUFFICIENT_DATA,
            message_key="ncValNoSpindleCommand",
            limitations=["S word not found in NC program"],
        )
        holder_check = NCValidationFinding(
            check_id="HOLDER_RPM_LIMIT",
            severity=NCValidationSeverity.INSUFFICIENT_DATA,
            status=NCValidationStatus.INSUFFICIENT_DATA,
            message_key="ncValNoSpindleCommand",
            limitations=["S word not found in NC program"],
        )
        effective_check = NCValidationFinding(
            check_id="EFFECTIVE_RPM_LIMIT",
            severity=NCValidationSeverity.INSUFFICIENT_DATA,
            status=NCValidationStatus.INSUFFICIENT_DATA,
            message_key="ncValNoSpindleCommand",
            limitations=["S word not found in NC program"],
        )
    else:
        # RPM evidence exists — check each limit
        machine_check = _rpm_limit_check(
            "MACHINE_RPM_LIMIT",
            f"machine:{machine_id or 'unknown'}",
            commanded_rpm,
            machine_spindle_max_rpm,
        )
        tool_check = _rpm_limit_check(
            "TOOL_RPM_LIMIT",
            f"cutting_tool:{tool_id or 'unknown'}",
            commanded_rpm,
            tool_max_rpm,
        )
        holder_check = _rpm_limit_check(
            "HOLDER_RPM_LIMIT",
            f"tool_holder:{holder_id or 'unknown'}",
            commanded_rpm,
            holder_max_rpm,
        )

        # Effective limit = min of known limits
        # MISSING_LIMIT_AS_ZERO=NO — None limits are excluded from min()
        known_limits: list[tuple[int, str]] = []
        if machine_spindle_max_rpm is not None:
            known_limits.append((machine_spindle_max_rpm, f"machine:{machine_id or 'unknown'}"))
        if tool_max_rpm is not None:
            known_limits.append((tool_max_rpm, f"cutting_tool:{tool_id or 'unknown'}"))
        if holder_max_rpm is not None:
            known_limits.append((holder_max_rpm, f"tool_holder:{holder_id or 'unknown'}"))

        if not known_limits:
            effective_check = NCValidationFinding(
                check_id="EFFECTIVE_RPM_LIMIT",
                severity=NCValidationSeverity.INSUFFICIENT_DATA,
                status=NCValidationStatus.INSUFFICIENT_DATA,
                observed_value=commanded_rpm,
                observed_unit="rpm",
                message_key="ncValEffectiveLimitInsuffData",
                limitations=["No RPM limits known for any selected equipment"],
            )
        else:
            eff_rpm, eff_source = min(known_limits, key=lambda x: x[0])
            if commanded_rpm > eff_rpm:
                effective_check = NCValidationFinding(
                    check_id="EFFECTIVE_RPM_LIMIT",
                    severity=NCValidationSeverity.BLOCKING,
                    status=NCValidationStatus.EXCEEDS_LIMIT,
                    observed_value=commanded_rpm,
                    observed_unit="rpm",
                    limit_or_reference=float(eff_rpm),
                    limit_unit="rpm",
                    limit_source=eff_source,
                    message_key="ncValEffectiveLimitExceeded",
                )
            else:
                effective_check = NCValidationFinding(
                    check_id="EFFECTIVE_RPM_LIMIT",
                    severity=NCValidationSeverity.INFO,
                    status=NCValidationStatus.WITHIN_LIMIT,
                    observed_value=commanded_rpm,
                    observed_unit="rpm",
                    limit_or_reference=float(eff_rpm),
                    limit_unit="rpm",
                    limit_source=eff_source,
                    message_key="ncValEffectiveLimitOk",
                )

    # -----------------------------------------------------------------------
    # Calculated Vc — requires G97 RPM + tool diameter
    # CUTTING_SPEED_FORMULA_DUPLICATED=NO — uses backend.machining.formulas
    # -----------------------------------------------------------------------
    vc_check: NCValidationFinding | None = None
    calc_vc: float | None = None

    if commanded_rpm is not None and tool_cutting_diameter_mm is not None:
        try:
            vc_qty = cutting_speed_from_spindle_speed(
                spindle_speed=Quantity(Decimal(str(commanded_rpm)), Unit.RPM),
                diameter=Quantity(Decimal(str(tool_cutting_diameter_mm)), Unit.MM),
            )
            calc_vc = float(vc_qty.value)
        except MachiningMathError as exc:
            limitations.append(f"Vc calculation error: {exc}")
            calc_vc = None

        if calc_vc is not None and cutting_param_registry is not None and operation_type:
            try:
                op_enum = OperationType(operation_type.lower())
            except ValueError:
                op_enum = None
            mat_enum = None
            if material_iso_group:
                try:
                    mat_enum = IsoMaterialGroup(material_iso_group)
                except ValueError:
                    pass

            scope = ApplicabilityScope(
                operation_type=op_enum,
                iso_material_group=mat_enum,
            )
            vc_check = _reference_range_check(
                "CUTTING_SPEED_REF",
                calc_vc,
                "m/min",
                Quantity(Decimal(str(calc_vc)), Unit.M_MIN),
                cutting_param_registry,
                ParameterType.CUTTING_SPEED,
                scope,
                "ncValVc",
            )
    elif commanded_rpm is not None and tool_cutting_diameter_mm is None:
        vc_check = NCValidationFinding(
            check_id="CUTTING_SPEED_REF",
            severity=NCValidationSeverity.INSUFFICIENT_DATA,
            status=NCValidationStatus.INSUFFICIENT_DATA,
            observed_value=commanded_rpm,
            observed_unit="rpm",
            message_key="ncValVcNoDiameter",
            limitations=[
                "Tool cutting_diameter_mm not available (insert tools have no singular diameter)"
            ],
        )

    # -----------------------------------------------------------------------
    # Calculated fz — requires G94 + RPM + flutes > 0 + MILLING context
    # FEED_PER_TOOTH_FORMULA_DUPLICATED=NO — uses backend.machining.formulas
    # FZ_WITHOUT_VALID_OPERATION_CONTEXT=NO
    # -----------------------------------------------------------------------
    fz_check: NCValidationFinding | None = None
    calc_fz: float | None = None

    op_for_fz: OperationType | None = None
    if operation_type:
        try:
            op_for_fz = OperationType(operation_type.lower())
        except ValueError:
            pass

    is_fz_op = op_for_fz in _FZ_OPERATIONS if op_for_fz is not None else False

    if (is_fz_op and feed_mode == "G94"
            and feed_mm_min is not None
            and commanded_rpm is not None
            and tool_number_of_flutes is not None
            and tool_number_of_flutes > 0):
        try:
            fz_qty = feed_per_tooth_from_feed_rate(
                feed_rate=Quantity(Decimal(str(feed_mm_min)), Unit.MM_MIN),
                spindle_speed=Quantity(Decimal(str(commanded_rpm)), Unit.RPM),
                tooth_count=tool_number_of_flutes,
            )
            calc_fz = float(fz_qty.value)
        except MachiningMathError as exc:
            limitations.append(f"fz calculation error: {exc}")
            calc_fz = None

        if calc_fz is not None and cutting_param_registry is not None:
            mat_enum = None
            if material_iso_group:
                try:
                    mat_enum = IsoMaterialGroup(material_iso_group)
                except ValueError:
                    pass
            scope = ApplicabilityScope(
                operation_type=op_for_fz,
                iso_material_group=mat_enum,
            )
            fz_check = _reference_range_check(
                "FEED_PER_TOOTH_REF",
                calc_fz,
                "mm/tooth",
                Quantity(Decimal(str(calc_fz)), Unit.MM_TOOTH),
                cutting_param_registry,
                ParameterType.FEED_PER_TOOTH,
                scope,
                "ncValFz",
            )
    elif op_for_fz in _FZ_OPERATIONS:
        # Milling but missing a required input
        if feed_mode == "G95":
            fz_check = NCValidationFinding(
                check_id="FEED_PER_TOOTH_REF",
                severity=NCValidationSeverity.NOT_APPLICABLE,
                status=NCValidationStatus.NOT_APPLICABLE,
                message_key="ncValFzG95NotApplicable",
                limitations=["G95 mode: F is feed/rev, not feed/min — fz cannot be derived"],
            )
        elif tool_number_of_flutes is None:
            fz_check = NCValidationFinding(
                check_id="FEED_PER_TOOTH_REF",
                severity=NCValidationSeverity.INSUFFICIENT_DATA,
                status=NCValidationStatus.INSUFFICIENT_DATA,
                message_key="ncValFzNoFlutes",
                limitations=["number_of_flutes not available in tool catalog"],
            )
        elif commanded_rpm is None:
            fz_check = NCValidationFinding(
                check_id="FEED_PER_TOOTH_REF",
                severity=NCValidationSeverity.INSUFFICIENT_DATA,
                status=NCValidationStatus.INSUFFICIENT_DATA,
                message_key="ncValFzNoRpm",
                limitations=["Commanded RPM not available"],
            )
    elif operation_type is not None:
        # Non-milling operation: fz is not applicable
        fz_check = NCValidationFinding(
            check_id="FEED_PER_TOOTH_REF",
            severity=NCValidationSeverity.NOT_APPLICABLE,
            status=NCValidationStatus.NOT_APPLICABLE,
            message_key="ncValFzNotApplicable",
        )

    # -----------------------------------------------------------------------
    # Calculated feed/rev — G95 direct or G94 + RPM for turning/drilling
    # FEED_PER_REV_FORMULA_DUPLICATED=NO — uses backend.machining.formulas
    # -----------------------------------------------------------------------
    feed_rev_check: NCValidationFinding | None = None
    calc_feed_rev: float | None = None

    op_for_frev: OperationType | None = None
    if operation_type:
        try:
            op_for_frev = OperationType(operation_type.lower())
        except ValueError:
            pass

    is_frev_op = op_for_frev in _FEED_REV_OPERATIONS if op_for_frev is not None else False

    if feed_mode == "G95" and feed_mm_rev is not None and is_frev_op:
        # G95 direct: F already in mm/rev
        calc_feed_rev = feed_mm_rev
    elif (is_frev_op and feed_mode == "G94"
          and feed_mm_min is not None
          and commanded_rpm is not None):
        try:
            fr_qty = feed_per_rev_from_feed_rate(
                feed_rate=Quantity(Decimal(str(feed_mm_min)), Unit.MM_MIN),
                spindle_speed=Quantity(Decimal(str(commanded_rpm)), Unit.RPM),
            )
            calc_feed_rev = float(fr_qty.value)
        except MachiningMathError as exc:
            limitations.append(f"feed/rev calculation error: {exc}")
            calc_feed_rev = None

    if calc_feed_rev is not None and cutting_param_registry is not None and operation_type:
        mat_enum = None
        if material_iso_group:
            try:
                mat_enum = IsoMaterialGroup(material_iso_group)
            except ValueError:
                pass
        scope = ApplicabilityScope(
            operation_type=op_for_frev,
            iso_material_group=mat_enum,
        )
        feed_rev_check = _reference_range_check(
            "FEED_PER_REV_REF",
            calc_feed_rev,
            "mm/rev",
            Quantity(Decimal(str(calc_feed_rev)), Unit.MM_REV),
            cutting_param_registry,
            ParameterType.FEED_PER_REV,
            scope,
            "ncValFeedRev",
        )
    elif is_frev_op and calc_feed_rev is None and operation_type:
        if commanded_rpm is None and feed_mode == "G94":
            feed_rev_check = NCValidationFinding(
                check_id="FEED_PER_REV_REF",
                severity=NCValidationSeverity.INSUFFICIENT_DATA,
                status=NCValidationStatus.INSUFFICIENT_DATA,
                message_key="ncValFeedRevNoRpm",
                limitations=["Commanded RPM required for feed/rev derivation from G94"],
            )
    elif operation_type is not None and not is_frev_op and op_for_frev in _FZ_OPERATIONS:
        feed_rev_check = NCValidationFinding(
            check_id="FEED_PER_REV_REF",
            severity=NCValidationSeverity.NOT_APPLICABLE,
            status=NCValidationStatus.NOT_APPLICABLE,
            message_key="ncValFeedRevNotApplicable",
        )

    # -----------------------------------------------------------------------
    # Build summary
    # -----------------------------------------------------------------------
    all_findings: list[NCValidationFinding | None] = [
        machine_check, tool_check, holder_check, effective_check,
        vc_check, fz_check, feed_rev_check,
    ]
    blocking, warning, advisory, insuf = _count_severities(all_findings)

    # Carry over parser limitations
    limitations.extend(motion_result.limitations[:5])  # first 5 only to avoid verbose duplication

    return NCProgramValidationSummary(
        nc_commanded_feed_mm_min=feed_mm_min,
        nc_commanded_feed_mm_rev=feed_mm_rev,
        nc_feed_mode=feed_mode,
        nc_commanded_spindle_rpm=commanded_rpm,
        nc_spindle_state=motion_result.nc_spindle_state,
        calculated_cutting_speed_m_min=calc_vc,
        calculated_feed_per_tooth_mm=calc_fz,
        calculated_feed_per_rev_mm=calc_feed_rev,
        machine_rpm_limit_check=machine_check,
        tool_rpm_limit_check=tool_check,
        holder_rpm_limit_check=holder_check,
        effective_rpm_limit_check=effective_check,
        cutting_speed_check=vc_check,
        feed_per_tooth_check=fz_check,
        feed_per_rev_check=feed_rev_check,
        blocking_count=blocking,
        warning_count=warning,
        advisory_count=advisory,
        insufficient_data_count=insuf,
        limitations=limitations,
        evidence_sources=evidence_sources,
        nc_commanded_spindle_speed_equals_actual_rpm=False,
        nc_commanded_feed_equals_actual_feed=False,
        nc_commanded_feed_equals_recommended_feed=False,
        reference_range_validation_is_optimization=False,
        nc_program_automatic_operation_classification=False,
        machine_feed_limit_validation_implemented=False,
        g84_pitch_validation_implemented=False,
        generic_feed_without_spindle_warning_implemented=False,
        spindle_direction_compatibility_check_implemented=False,
    )
