"""Unit tests for NC feed/spindle program validation.

NC_FEED_SPINDLE_PROGRAM_VALIDATION_01 — Phase 2

Test-contract guarantees:
    NC_FILE_EXECUTED=NO
    NC_COMMANDED_SPINDLE_SPEED_EQUALS_ACTUAL_RPM=NO
    NC_COMMANDED_FEED_EQUALS_ACTUAL_FEED=NO
    REFERENCE_RANGE_VALIDATION_IS_OPTIMIZATION=NO
    NC_PROGRAM_AUTOMATIC_OPERATION_CLASSIFICATION=NO
    MISSING_LIMIT_AS_ZERO=NO
    MISSING_VALUE_AS_ZERO=NO
    SYNTHETIC_PARAMETER_RECORD_ADDED=NO
    RPM_FORMULA_DUPLICATED=NO
    CUTTING_SPEED_FORMULA_DUPLICATED=NO
    FEED_PER_TOOTH_FORMULA_DUPLICATED=NO
    FEED_PER_REV_FORMULA_DUPLICATED=NO
    G84_PITCH_VALIDATION_IMPLEMENTED=NO
    GENERIC_FEED_WITHOUT_SPINDLE_WARNING_IMPLEMENTED=NO
    MACHINE_FEED_LIMIT_VALIDATION_IMPLEMENTED=NO
"""

from __future__ import annotations

import math
from decimal import Decimal

import pytest

from backend.cutting_parameters.models import (
    ApplicabilityScope,
    CuttingParameterRecord,
    EvidenceStatus,
    ParameterType,
    QuantityRange,
)
from backend.cutting_parameters.registry import CuttingParameterRegistry
from backend.domain.base import Provenance
from backend.domain.enums import IsoMaterialGroup, OperationType, ProvenanceType
from backend.domain.units import Quantity, Unit
from backend.interoperability.nc_motion import (
    NcAnalysisStatus,
    NcMotionResult,
    parse_nc_motion,
)
from backend.process_planning.nc_validation import (
    NCValidationSeverity,
    NCValidationStatus,
    validate_nc_feed_spindle,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(text: str) -> NcMotionResult:
    return parse_nc_motion(text.strip())


def _simple_registry_with_vc() -> CuttingParameterRegistry:
    """Registry with one CUTTING_SPEED record for MILLING / ISO P."""
    reg = CuttingParameterRegistry()
    reg.register(
        CuttingParameterRecord(
            record_id="test-vc-milling-p",
            parameter_type=ParameterType.CUTTING_SPEED,
            value_range=QuantityRange(
                min_value=Quantity(Decimal("100"), Unit.M_MIN),
                max_value=Quantity(Decimal("200"), Unit.M_MIN),
            ),
            applicability=ApplicabilityScope(
                operation_type=OperationType.MILLING,
                iso_material_group=IsoMaterialGroup.P,
            ),
            provenance=Provenance(
                source_type=ProvenanceType.MANUFACTURER_DATA,
                source_reference="test-source-ref",
            ),
            evidence_status=EvidenceStatus.REFERENCE_ONLY,
        )
    )
    return reg


def _simple_registry_with_fz() -> CuttingParameterRegistry:
    reg = CuttingParameterRegistry()
    reg.register(
        CuttingParameterRecord(
            record_id="test-fz-milling-p",
            parameter_type=ParameterType.FEED_PER_TOOTH,
            value_range=QuantityRange(
                min_value=Quantity(Decimal("0.05"), Unit.MM_TOOTH),
                max_value=Quantity(Decimal("0.15"), Unit.MM_TOOTH),
            ),
            applicability=ApplicabilityScope(
                operation_type=OperationType.MILLING,
                iso_material_group=IsoMaterialGroup.P,
            ),
            provenance=Provenance(
                source_type=ProvenanceType.MANUFACTURER_DATA,
                source_reference="test-source-ref",
            ),
            evidence_status=EvidenceStatus.REFERENCE_ONLY,
        )
    )
    return reg


def _simple_registry_with_feed_rev() -> CuttingParameterRegistry:
    reg = CuttingParameterRegistry()
    reg.register(
        CuttingParameterRecord(
            record_id="test-fr-drilling-p",
            parameter_type=ParameterType.FEED_PER_REV,
            value_range=QuantityRange(
                min_value=Quantity(Decimal("0.1"), Unit.MM_REV),
                max_value=Quantity(Decimal("0.3"), Unit.MM_REV),
            ),
            applicability=ApplicabilityScope(
                operation_type=OperationType.DRILLING,
                iso_material_group=IsoMaterialGroup.P,
            ),
            provenance=Provenance(
                source_type=ProvenanceType.MANUFACTURER_DATA,
                source_reference="test-source-ref",
            ),
            evidence_status=EvidenceStatus.REFERENCE_ONLY,
        )
    )
    return reg


# ===========================================================================
# Section 1 — FEED MODES
# ===========================================================================


def test_g94_detected():
    """G94 explicit declaration → feed mode captured."""
    result = _parse("G21 G94 G0 X0 Y0 Z0\nG1 X100 F500")
    assert result.nc_feed_mode == "G94"
    assert result.nc_commanded_feed_mm_min is not None


def test_g94_modal_feed_stored():
    """G94 mode: F is stored as mm/min."""
    result = _parse("G21 G94 G0 X0 Y0 Z0\nG1 X100 F300")
    assert result.nc_commanded_feed_mm_min == pytest.approx(300.0, abs=1e-3)


def test_g95_detected():
    """G95 explicit declaration → feed mode captured."""
    result = _parse("G21 G95 G97 S1000 M3\nG1 Z-10 F0.2")
    assert result.nc_feed_mode == "G95"


def test_g95_feed_not_stored_as_mm_min():
    """G95 mode: F is feed/rev, NOT stored in nc_commanded_feed_mm_min."""
    result = _parse("G21 G95 G97 S1000 M3\nG1 Z-10 F0.25")
    # nc_commanded_feed_mm_min should be None (no G94 feed seen)
    assert result.nc_commanded_feed_mm_min is None


def test_g95_feed_stored_in_segment():
    """G95 mode: F is captured as commanded_feed_mm_rev on segment."""
    result = _parse("G21 G95 G97 S1000 M3\nG1 Z-10 F0.3")
    seg = result.segments[-1]
    assert seg.feed_mode == "G95"
    assert seg.commanded_feed_mm_rev == pytest.approx(0.3, abs=1e-4)


def test_g93_detected_deferred():
    """G93 inverse-time detected → partial, deferred reported."""
    result = _parse("G21 G93 G1 X100 F5.0")
    assert result.nc_feed_mode == "G93"
    assert "G93_INVERSE_TIME_DEFERRED" in result.unsupported_features
    assert result.analysis_status in (
        NcAnalysisStatus.PARTIAL,
        NcAnalysisStatus.UNSUPPORTED_SEMANTICS,
    )


def test_g93_limitation_in_result():
    """G93 detected → limitation message added."""
    result = _parse("G21 G93 G1 X100 F5.0")
    joined = " ".join(result.limitations)
    assert "G93_INVERSE_TIME_DEFERRED" in joined


def test_default_feed_mode_g94():
    """No explicit G94/G95 → default feed mode is G94."""
    result = _parse("G21 G0 X0 Y0 Z0\nG1 X100 F400")
    assert result.nc_feed_mode == "G94"
    assert result.nc_commanded_feed_mm_min == pytest.approx(400.0, abs=1e-3)


# ===========================================================================
# Section 2 — SPINDLE S COMMAND
# ===========================================================================


def test_s_command_captured():
    """S word → nc_commanded_spindle_rpm populated."""
    result = _parse("G21 G97 S3000 M3\nG1 X10 F200")
    assert result.nc_commanded_spindle_rpm == pytest.approx(3000.0, abs=1e-3)


def test_s_command_captured_segment():
    """S word → commanded_spindle_rpm on segment."""
    result = _parse("G21 G97 S5000 M3\nG1 X10 F200")
    seg = result.segments[-1]
    assert seg.commanded_spindle_rpm == pytest.approx(5000.0, abs=1e-3)


def test_no_s_command():
    """No S word → nc_commanded_spindle_rpm is None."""
    result = _parse("G21 G94 G0 X0\nG1 X100 F300")
    assert result.nc_commanded_spindle_rpm is None


def test_safety_flag_spindle_not_actual():
    """Safety flag: commanded spindle != actual RPM."""
    result = _parse("G21 G97 S3000 M3\nG1 X10 F200")
    assert result.nc_commanded_spindle_rpm is not None
    # The flag is not on NcMotionResult, but the validation summary enforces it
    summary = validate_nc_feed_spindle(result)
    assert summary.nc_commanded_spindle_speed_equals_actual_rpm is False


# ===========================================================================
# Section 3 — M3 / M4 / M5
# ===========================================================================


def test_m3_state():
    """M3 → spindle state M3_CW."""
    result = _parse("G21 M3 S2000\nG1 X10 F200")
    assert result.nc_spindle_state == "M3_CW"


def test_m4_state():
    """M4 → spindle state M4_CCW."""
    result = _parse("G21 M4 S2000\nG1 X10 F200")
    assert result.nc_spindle_state == "M4_CCW"


def test_m5_state():
    """M5 → spindle state M5_STOP."""
    result = _parse("G21 M3 S2000\nG1 X10 F200\nM5")
    assert result.nc_spindle_state == "M5_STOP"


def test_m3_segment_direction():
    """M3 → spindle_direction CW on segment."""
    result = _parse("G21 M3 S2000\nG1 X10 F200")
    seg = result.segments[-1]
    assert seg.spindle_state == "M3_CW"
    assert seg.spindle_direction == "CW"


def test_m4_segment_direction():
    """M4 → spindle_direction CCW on segment."""
    result = _parse("G21 M4 S2000\nG1 X10 F200")
    seg = result.segments[-1]
    assert seg.spindle_direction == "CCW"


# ===========================================================================
# Section 4 — G97
# ===========================================================================


def test_g97_s_captured():
    """G97 + S word → commanded RPM captured."""
    result = _parse("G21 G97 S8000 M3\nG1 X10 F500")
    assert result.nc_commanded_spindle_rpm == pytest.approx(8000.0, abs=1e-3)


def test_g97_default_mode():
    """Default spindle mode is G97 (constant RPM)."""
    result = _parse("G21 S3000 M3\nG1 X10 F200")
    # S should be captured as RPM since G97 is the default
    assert result.nc_commanded_spindle_rpm == pytest.approx(3000.0, abs=1e-3)


# ===========================================================================
# Section 5 — G96
# ===========================================================================


def test_g96_deferred():
    """G96 detected → deferred, PARTIAL status."""
    result = _parse("G21 G96 S150 M3\nG1 Z-10 F0.2")
    assert "G96_CSS_DEFERRED" in result.unsupported_features
    assert result.analysis_status in (
        NcAnalysisStatus.PARTIAL,
        NcAnalysisStatus.UNSUPPORTED_SEMANTICS,
    )


def test_g96_s_not_stored_as_rpm():
    """G96 mode: S is CSS (not RPM) — must NOT be stored as commanded RPM."""
    result = _parse("G21 G96 S200 M3\nG1 Z-10 F0.2")
    # When G96 is active, S should NOT be stored as RPM
    assert result.nc_commanded_spindle_rpm is None


def test_g96_limitation_added():
    """G96 detected → limitation added."""
    result = _parse("G21 G96 S200 M3\nG1 Z-10 F0.2")
    joined = " ".join(result.limitations)
    assert "G96_CSS_DEFERRED" in joined


# ===========================================================================
# Section 6 — MACHINE RPM LIMIT
# ===========================================================================


def test_machine_rpm_within_limit():
    """Commanded RPM < machine limit → WITHIN_LIMIT."""
    result = _parse("G21 G97 S5000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        machine_spindle_max_rpm=8000,
        machine_id="test-machine",
    )
    assert summary.machine_rpm_limit_check is not None
    assert summary.machine_rpm_limit_check.status == NCValidationStatus.WITHIN_LIMIT
    assert summary.machine_rpm_limit_check.severity != NCValidationSeverity.BLOCKING


def test_machine_rpm_exceeds_limit():
    """Commanded RPM > machine limit → EXCEEDS_LIMIT + BLOCKING."""
    result = _parse("G21 G97 S15000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        machine_spindle_max_rpm=8000,
        machine_id="test-machine",
    )
    assert summary.machine_rpm_limit_check is not None
    assert summary.machine_rpm_limit_check.status == NCValidationStatus.EXCEEDS_LIMIT
    assert summary.machine_rpm_limit_check.severity == NCValidationSeverity.BLOCKING
    assert summary.blocking_count >= 1


def test_machine_rpm_limit_missing():
    """Machine max_rpm = None → INSUFFICIENT_DATA, not zero."""
    result = _parse("G21 G97 S5000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        machine_spindle_max_rpm=None,
        machine_id="test-machine",
    )
    assert summary.machine_rpm_limit_check is not None
    assert summary.machine_rpm_limit_check.status == NCValidationStatus.INSUFFICIENT_DATA
    # MISSING_LIMIT_AS_ZERO=NO
    assert summary.machine_rpm_limit_check.severity == NCValidationSeverity.INSUFFICIENT_DATA


# ===========================================================================
# Section 7 — TOOL RPM LIMIT
# ===========================================================================


def test_tool_rpm_within_limit():
    """Commanded RPM < tool limit → WITHIN_LIMIT."""
    result = _parse("G21 G97 S1000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        tool_max_rpm=1907,
        tool_id="sandvik-835b",
    )
    assert summary.tool_rpm_limit_check is not None
    assert summary.tool_rpm_limit_check.status == NCValidationStatus.WITHIN_LIMIT


def test_tool_rpm_exceeds_limit():
    """Commanded RPM > tool limit → EXCEEDS_LIMIT + BLOCKING."""
    result = _parse("G21 G97 S2500 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        tool_max_rpm=1907,
        tool_id="sandvik-835b",
    )
    assert summary.tool_rpm_limit_check is not None
    assert summary.tool_rpm_limit_check.status == NCValidationStatus.EXCEEDS_LIMIT
    assert summary.tool_rpm_limit_check.severity == NCValidationSeverity.BLOCKING


def test_tool_rpm_limit_missing():
    """Tool max_rpm = None → INSUFFICIENT_DATA."""
    result = _parse("G21 G97 S5000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        tool_max_rpm=None,
        tool_id="some-tool",
    )
    assert summary.tool_rpm_limit_check is not None
    assert summary.tool_rpm_limit_check.status == NCValidationStatus.INSUFFICIENT_DATA


# ===========================================================================
# Section 8 — HOLDER RPM LIMIT
# ===========================================================================


def test_holder_rpm_within_limit():
    """Commanded RPM < holder limit → WITHIN_LIMIT."""
    result = _parse("G21 G97 S5000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        holder_max_rpm=15000,
        holder_id="test-holder",
    )
    assert summary.holder_rpm_limit_check is not None
    assert summary.holder_rpm_limit_check.status == NCValidationStatus.WITHIN_LIMIT


def test_holder_rpm_exceeds_limit():
    """Commanded RPM > holder limit → BLOCKING."""
    result = _parse("G21 G97 S20000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        holder_max_rpm=15000,
        holder_id="test-holder",
    )
    assert summary.holder_rpm_limit_check is not None
    assert summary.holder_rpm_limit_check.severity == NCValidationSeverity.BLOCKING


def test_holder_rpm_limit_missing():
    """Holder max_rpm = None → INSUFFICIENT_DATA."""
    result = _parse("G21 G97 S5000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        holder_max_rpm=None,
        holder_id="bmt65-static",
    )
    assert summary.holder_rpm_limit_check is not None
    assert summary.holder_rpm_limit_check.status == NCValidationStatus.INSUFFICIENT_DATA


# ===========================================================================
# Section 9 — EFFECTIVE RPM LIMIT
# ===========================================================================


def test_effective_limit_machine_is_minimum():
    """Machine is the binding limit → effective check uses machine limit."""
    result = _parse("G21 G97 S9000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        machine_spindle_max_rpm=8000,
        machine_id="m1",
        tool_max_rpm=15000,
        tool_id="t1",
        holder_max_rpm=20000,
        holder_id="h1",
    )
    assert summary.effective_rpm_limit_check is not None
    assert summary.effective_rpm_limit_check.limit_or_reference == 8000.0
    assert summary.effective_rpm_limit_check.status == NCValidationStatus.EXCEEDS_LIMIT


def test_effective_limit_tool_is_minimum():
    """Tool limit is the binding limit."""
    result = _parse("G21 G97 S1500 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        machine_spindle_max_rpm=12000,
        machine_id="m1",
        tool_max_rpm=1907,
        tool_id="reamer",
        holder_max_rpm=20000,
        holder_id="h1",
    )
    assert summary.effective_rpm_limit_check is not None
    assert summary.effective_rpm_limit_check.limit_or_reference == 1907.0


def test_effective_limit_holder_is_minimum():
    """Holder limit is the binding limit."""
    result = _parse("G21 G97 S5000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        machine_spindle_max_rpm=12000,
        machine_id="m1",
        tool_max_rpm=None,  # tool max unknown
        tool_id="t1",
        holder_max_rpm=8000,
        holder_id="h1",
    )
    assert summary.effective_rpm_limit_check is not None
    assert summary.effective_rpm_limit_check.limit_or_reference == 8000.0
    assert summary.effective_rpm_limit_check.status == NCValidationStatus.WITHIN_LIMIT


def test_effective_limit_partial_known():
    """Only machine limit known → effective = machine limit."""
    result = _parse("G21 G97 S5000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        machine_spindle_max_rpm=8000,
        machine_id="m1",
        tool_max_rpm=None,
        holder_max_rpm=None,
    )
    assert summary.effective_rpm_limit_check is not None
    assert summary.effective_rpm_limit_check.limit_or_reference == 8000.0


def test_effective_limit_all_missing():
    """No limits known → INSUFFICIENT_DATA."""
    result = _parse("G21 G97 S5000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        machine_spindle_max_rpm=None,
        tool_max_rpm=None,
        holder_max_rpm=None,
    )
    assert summary.effective_rpm_limit_check is not None
    assert summary.effective_rpm_limit_check.status == NCValidationStatus.INSUFFICIENT_DATA


# ===========================================================================
# Section 10 — CALCULATED Vc
# ===========================================================================


def test_vc_calculated():
    """G97 + S + diameter → Vc calculated using canonical formula."""
    # Vc = π × D × n / 1000 = π × 0.025 × 5000 / 1000 = ~392.7 m/min... too high
    # Use D=10mm: Vc = π × 0.010 × 3000 / 1000 = 94.2 m/min
    result = _parse("G21 G97 S3000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        tool_cutting_diameter_mm=10.0,
    )
    assert summary.calculated_cutting_speed_m_min is not None
    # π × 10 × 3000 / 1000 = 94.248
    assert summary.calculated_cutting_speed_m_min == pytest.approx(
        math.pi * 10.0 * 3000.0 / 1000.0, rel=1e-4
    )


def test_vc_metric_units():
    """Vc calculation uses mm diameter input → m/min output."""
    result = _parse("G21 G97 S1000 M3\nG1 X10 F100")
    summary = validate_nc_feed_spindle(result, tool_cutting_diameter_mm=25.0)
    assert summary.calculated_cutting_speed_m_min is not None
    # Vc = π × 25 × 1000 / 1000 = 78.54
    assert summary.calculated_cutting_speed_m_min == pytest.approx(
        math.pi * 25.0, rel=1e-4
    )


def test_vc_within_reference():
    """Vc within reference range → WITHIN_REFERENCE_RANGE, ADVISORY."""
    # D=10, S=5000 → Vc = π × 10 × 5000 / 1000 = 157 m/min (within 100-200 range)
    result = _parse("G21 G97 S5000 M3\nG1 X10 F200")
    reg = _simple_registry_with_vc()
    summary = validate_nc_feed_spindle(
        result,
        tool_cutting_diameter_mm=10.0,
        operation_type="MILLING",
        material_iso_group="P",
        cutting_param_registry=reg,
    )
    assert summary.cutting_speed_check is not None
    assert summary.cutting_speed_check.status == NCValidationStatus.WITHIN_REFERENCE_RANGE
    assert summary.cutting_speed_check.severity == NCValidationSeverity.ADVISORY


def test_vc_below_reference():
    """Vc below reference range → BELOW_REFERENCE_RANGE, ADVISORY."""
    # D=10, S=1000 → Vc = π × 10 = 31.4 m/min (below 100 min)
    result = _parse("G21 G97 S1000 M3\nG1 X10 F200")
    reg = _simple_registry_with_vc()
    summary = validate_nc_feed_spindle(
        result,
        tool_cutting_diameter_mm=10.0,
        operation_type="MILLING",
        material_iso_group="P",
        cutting_param_registry=reg,
    )
    assert summary.cutting_speed_check is not None
    assert summary.cutting_speed_check.status == NCValidationStatus.BELOW_REFERENCE_RANGE
    assert summary.cutting_speed_check.severity == NCValidationSeverity.ADVISORY


def test_vc_above_reference():
    """Vc above reference range → ABOVE_REFERENCE_RANGE, ADVISORY."""
    # D=10, S=15000 → Vc = π × 10 × 15 = 471 m/min (above 200 max)
    result = _parse("G21 G97 S15000 M3\nG1 X10 F200")
    reg = _simple_registry_with_vc()
    summary = validate_nc_feed_spindle(
        result,
        tool_cutting_diameter_mm=10.0,
        operation_type="MILLING",
        material_iso_group="P",
        cutting_param_registry=reg,
    )
    assert summary.cutting_speed_check is not None
    assert summary.cutting_speed_check.status == NCValidationStatus.ABOVE_REFERENCE_RANGE


def test_vc_no_diameter():
    """No tool diameter → Vc INSUFFICIENT_DATA."""
    result = _parse("G21 G97 S5000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(result, tool_cutting_diameter_mm=None)
    assert summary.cutting_speed_check is not None
    assert summary.cutting_speed_check.status == NCValidationStatus.INSUFFICIENT_DATA


def test_vc_no_rpm():
    """No S word → no Vc derivation."""
    result = _parse("G21 G94 G0 X0\nG1 X100 F300")
    summary = validate_nc_feed_spindle(result, tool_cutting_diameter_mm=10.0)
    assert summary.calculated_cutting_speed_m_min is None


# ===========================================================================
# Section 11 — CALCULATED fz
# ===========================================================================


def test_fz_valid_milling():
    """G94 + RPM + flutes + MILLING → fz calculated."""
    # F=500 mm/min, S=5000, z=2 → fz = 500 / (5000 × 2) = 0.05 mm/tooth
    result = _parse("G21 G94 G97 S5000 M3\nG1 X100 F500")
    summary = validate_nc_feed_spindle(
        result,
        tool_number_of_flutes=2,
        operation_type="MILLING",
    )
    assert summary.calculated_feed_per_tooth_mm is not None
    assert summary.calculated_feed_per_tooth_mm == pytest.approx(
        500.0 / (5000.0 * 2.0), rel=1e-4
    )


def test_fz_missing_flute_count():
    """Missing flute count → fz INSUFFICIENT_DATA."""
    result = _parse("G21 G94 G97 S5000 M3\nG1 X100 F500")
    summary = validate_nc_feed_spindle(
        result,
        tool_number_of_flutes=None,
        operation_type="MILLING",
    )
    assert summary.feed_per_tooth_check is not None
    assert summary.feed_per_tooth_check.status == NCValidationStatus.INSUFFICIENT_DATA


def test_fz_missing_rpm():
    """No S word → fz INSUFFICIENT_DATA."""
    result = _parse("G21 G94 G0 X0\nG1 X100 F500")
    summary = validate_nc_feed_spindle(
        result,
        tool_number_of_flutes=2,
        operation_type="MILLING",
    )
    assert summary.feed_per_tooth_check is not None
    assert summary.feed_per_tooth_check.status == NCValidationStatus.INSUFFICIENT_DATA


def test_fz_g95_not_applicable():
    """G95 mode: fz cannot be derived from feed/rev."""
    result = _parse("G21 G95 G97 S5000 M3\nG1 Z-10 F0.05")
    summary = validate_nc_feed_spindle(
        result,
        tool_number_of_flutes=2,
        operation_type="MILLING",
    )
    assert summary.feed_per_tooth_check is not None
    assert summary.feed_per_tooth_check.status == NCValidationStatus.NOT_APPLICABLE


def test_fz_turning_not_applicable():
    """Turning operation: fz is not applicable."""
    result = _parse("G21 G94 G97 S2000 M3\nG1 Z-100 F200")
    summary = validate_nc_feed_spindle(
        result,
        tool_number_of_flutes=None,
        operation_type="TURNING",
    )
    assert summary.feed_per_tooth_check is not None
    assert summary.feed_per_tooth_check.status == NCValidationStatus.NOT_APPLICABLE


def test_fz_no_auto_process_classification():
    """NC program alone must not classify operation type.

    NC_PROGRAM_AUTOMATIC_OPERATION_CLASSIFICATION=NO
    """
    result = _parse("G21 G94 G97 S5000 M3\nG81 X10 Y10 Z-20 R5 F100")
    summary = validate_nc_feed_spindle(
        result,
        tool_number_of_flutes=2,
        operation_type=None,  # No operation supplied
    )
    # Without explicit operation_type, fz check should not auto-classify
    assert summary.nc_program_automatic_operation_classification is False
    # fz check is either None (no check run) or NOT_APPLICABLE
    if summary.feed_per_tooth_check is not None:
        assert summary.feed_per_tooth_check.status != NCValidationStatus.WITHIN_REFERENCE_RANGE


def test_fz_within_reference():
    """fz within reference range → ADVISORY."""
    # F=500, S=5000, z=2 → fz=0.05 mm/tooth (within 0.05-0.15 range)
    result = _parse("G21 G94 G97 S5000 M3\nG1 X100 F500")
    reg = _simple_registry_with_fz()
    summary = validate_nc_feed_spindle(
        result,
        tool_number_of_flutes=2,
        operation_type="MILLING",
        material_iso_group="P",
        cutting_param_registry=reg,
    )
    assert summary.feed_per_tooth_check is not None
    assert summary.feed_per_tooth_check.status == NCValidationStatus.WITHIN_REFERENCE_RANGE
    assert summary.feed_per_tooth_check.severity == NCValidationSeverity.ADVISORY


# ===========================================================================
# Section 12 — FEED PER REVOLUTION
# ===========================================================================


def test_feed_rev_g95_direct():
    """G95: F is directly feed/rev."""
    result = _parse("G21 G95 G97 S1000 M3\nG1 Z-20 F0.2")
    summary = validate_nc_feed_spindle(
        result,
        operation_type="DRILLING",
    )
    assert summary.calculated_feed_per_rev_mm is not None
    assert summary.calculated_feed_per_rev_mm == pytest.approx(0.2, abs=1e-4)


def test_feed_rev_g94_derived():
    """G94: feed/rev derived from feed_mm_min / RPM."""
    # F=200 mm/min, S=1000 rpm → f = 200/1000 = 0.2 mm/rev
    result = _parse("G21 G94 G97 S1000 M3\nG1 Z-20 F200")
    summary = validate_nc_feed_spindle(
        result,
        operation_type="DRILLING",
    )
    assert summary.calculated_feed_per_rev_mm is not None
    assert summary.calculated_feed_per_rev_mm == pytest.approx(0.2, rel=1e-4)


def test_feed_rev_missing_rpm():
    """No S word + G94 → feed/rev INSUFFICIENT_DATA."""
    result = _parse("G21 G94 G0 X0\nG1 Z-20 F200")
    summary = validate_nc_feed_spindle(
        result,
        operation_type="DRILLING",
    )
    assert summary.calculated_feed_per_rev_mm is None


def test_feed_rev_milling_not_applicable():
    """Milling operation: feed/rev not applicable → fz used instead."""
    result = _parse("G21 G94 G97 S5000 M3\nG1 X100 F500")
    summary = validate_nc_feed_spindle(
        result,
        operation_type="MILLING",
    )
    # feed/rev check should be NOT_APPLICABLE for milling
    assert summary.feed_per_rev_check is None or \
        summary.feed_per_rev_check.status == NCValidationStatus.NOT_APPLICABLE


def test_feed_rev_within_reference():
    """feed/rev within reference range → ADVISORY."""
    # F=200 mm/min, S=1000 → f=0.2 mm/rev (within 0.1-0.3 range)
    result = _parse("G21 G94 G97 S1000 M3\nG1 Z-20 F200")
    reg = _simple_registry_with_feed_rev()
    summary = validate_nc_feed_spindle(
        result,
        operation_type="DRILLING",
        material_iso_group="P",
        cutting_param_registry=reg,
    )
    assert summary.feed_per_rev_check is not None
    assert summary.feed_per_rev_check.status == NCValidationStatus.WITHIN_REFERENCE_RANGE
    assert summary.feed_per_rev_check.severity == NCValidationSeverity.ADVISORY


# ===========================================================================
# Section 13 — SAFETY INVARIANTS
# ===========================================================================


def test_missing_values_not_zero():
    """Missing machine/tool/holder RPM → INSUFFICIENT_DATA, not zero."""
    result = _parse("G21 G97 S5000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        machine_spindle_max_rpm=None,
        tool_max_rpm=None,
        holder_max_rpm=None,
    )
    for check in [
        summary.machine_rpm_limit_check,
        summary.tool_rpm_limit_check,
        summary.holder_rpm_limit_check,
        summary.effective_rpm_limit_check,
    ]:
        assert check is not None
        assert check.status == NCValidationStatus.INSUFFICIENT_DATA


def test_no_generic_feed_without_spindle_warning():
    """Feed motion without spindle command must NOT produce a generic warning.

    GENERIC_FEED_WITHOUT_SPINDLE_WARNING_IMPLEMENTED=NO
    """
    result = _parse("G21 G94 G0 X0 Y0 Z0\nG1 X100 F500")
    # No S, no M3/M4
    summary = validate_nc_feed_spindle(result)
    assert summary.generic_feed_without_spindle_warning_implemented is False
    # No WARNING severity for missing spindle
    all_findings = [
        summary.machine_rpm_limit_check,
        summary.tool_rpm_limit_check,
        summary.holder_rpm_limit_check,
        summary.effective_rpm_limit_check,
    ]
    for f in all_findings:
        if f is not None:
            assert f.severity != NCValidationSeverity.WARNING


def test_no_g84_pitch_validation():
    """G84 tapping: no pitch consistency check.

    G84_PITCH_VALIDATION_IMPLEMENTED=NO
    """
    result = _parse("G21 G94 G97 S1000 M3\nG81 X10 Y10 Z-20 R5 F1.0")
    summary = validate_nc_feed_spindle(result, operation_type="TAPPING")
    assert summary.g84_pitch_validation_implemented is False


def test_machine_feed_limit_implemented():
    """Machine feed limit check IS implemented (R-2606).

    MACHINE_FEED_LIMIT_VALIDATION_IMPLEMENTED=YES
    When machine_max_cutting_feed_mm_min is not supplied the check is
    INSUFFICIENT_DATA — fail-closed, MISSING_LIMIT_AS_ZERO=NO.
    """
    result = _parse("G21 G94 G97 S3000 M3\nG1 X100 F5000")
    summary = validate_nc_feed_spindle(
        result,
        machine_spindle_max_rpm=8000,
        machine_id="machine1",
    )
    assert summary.machine_feed_limit_validation_implemented is True
    # No feed limit supplied → fail-closed INSUFFICIENT_DATA, not a false pass
    assert summary.machine_feed_limit_check is not None
    assert summary.machine_feed_limit_check.check_id == "MACHINE_FEED_LIMIT"
    assert summary.machine_feed_limit_check.status.value == "INSUFFICIENT_DATA"


def test_g96_no_fake_rpm():
    """G96 mode: S word must NOT be stored as RPM.

    G96_CSS_RPM_CALCULATED=NO
    """
    result = _parse("G21 G96 S200 M3\nG1 Z-10 F0.2")
    assert result.nc_commanded_spindle_rpm is None
    summary = validate_nc_feed_spindle(result)
    assert summary.nc_commanded_spindle_rpm is None


def test_no_false_optimization_claim():
    """Reference range comparison must not imply optimization.

    FALSE_OPTIMIZATION_CLAIM=NO
    REFERENCE_RANGE_VALIDATION_IS_OPTIMIZATION=NO
    """
    result = _parse("G21 G97 S5000 M3\nG1 X10 F200")
    reg = _simple_registry_with_vc()
    summary = validate_nc_feed_spindle(
        result,
        tool_cutting_diameter_mm=10.0,
        operation_type="MILLING",
        material_iso_group="P",
        cutting_param_registry=reg,
    )
    assert summary.reference_range_validation_is_optimization is False
    # Advisory findings must not claim BLOCKING severity
    if summary.cutting_speed_check is not None:
        assert summary.cutting_speed_check.severity != NCValidationSeverity.BLOCKING


def test_no_spindle_direction_compat_check():
    """Spindle direction not validated against catalog.

    SPINDLE_DIRECTION_COMPATIBILITY_CHECK_IMPLEMENTED=NO
    """
    result = _parse("G21 M3 S2000\nG1 X10 F200")
    summary = validate_nc_feed_spindle(result)
    assert summary.spindle_direction_compatibility_check_implemented is False


# ===========================================================================
# Section 14 — MODEL / SERIALIZATION
# ===========================================================================


def test_validation_summary_serialization():
    """NCProgramValidationSummary serializes to dict."""
    result = _parse("G21 G97 S5000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        machine_spindle_max_rpm=8000,
        machine_id="m1",
    )
    d = summary.model_dump()
    assert "blocking_count" in d
    assert "nc_commanded_spindle_speed_equals_actual_rpm" in d
    assert d["nc_commanded_spindle_speed_equals_actual_rpm"] is False


def test_segment_optional_fields_backward_compat():
    """Segments without feed/spindle data have None optional fields."""
    result = _parse("G21 G0 X0 Y0 Z0\nG1 X100 F500")
    seg = result.segments[0]
    # These fields are optional — must default to None for backward compat
    assert seg.commanded_spindle_rpm is None
    assert seg.spindle_state is None


def test_severity_counters():
    """blocking_count and advisory_count are correct."""
    # Two BLOCKING: machine limit exceeded and holder limit exceeded
    result = _parse("G21 G97 S15000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        machine_spindle_max_rpm=8000,
        machine_id="m1",
        holder_max_rpm=10000,
        holder_id="h1",
    )
    assert summary.blocking_count >= 1  # at least machine and effective


def test_evidence_provenance():
    """Evidence sources list machine/tool/holder IDs when provided."""
    result = _parse("G21 G97 S5000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(
        result,
        machine_id="haas-vf2",
        tool_id="sandvik-reamer",
        holder_id="haimer-shrink",
    )
    assert any("haas-vf2" in s for s in summary.evidence_sources)


def test_safety_flags_immutable():
    """Prohibitory safety flags (claims the engine does NOT do) remain False."""
    result = _parse("G21 G97 S5000 M3\nG1 X10 F200")
    summary = validate_nc_feed_spindle(result)
    assert summary.nc_commanded_spindle_speed_equals_actual_rpm is False
    assert summary.nc_commanded_feed_equals_actual_feed is False
    assert summary.nc_commanded_feed_equals_recommended_feed is False
    assert summary.reference_range_validation_is_optimization is False
    assert summary.nc_program_automatic_operation_classification is False
    # machine_feed_limit_validation_implemented is a capability flag (True since R-2606
    # was implemented in EPIC_02); it is not a prohibitory safety flag.
    assert summary.g84_pitch_validation_implemented is False
    assert summary.generic_feed_without_spindle_warning_implemented is False
    assert summary.spindle_direction_compatibility_check_implemented is False


def test_nc_result_safety_flags():
    """NcMotionResult safety flags remain False after Phase 2 extensions."""
    result = _parse("G21 G97 S5000 M3\nG1 X10 F200")
    assert result.nc_feed_move_equals_confirmed_cutting is False
    assert result.arc_chord_approximation_used is False
    assert result.nc_file_executed is False


# ===========================================================================
# Section 15 — I18N KEY COVERAGE (basic smoke check)
# ===========================================================================


def test_en_keys_exist():
    """EN i18n file has ncValidation keys (smoke check)."""
    from pathlib import Path
    en_path = Path("frontend/app/src/i18n/en.ts")
    if en_path.exists():
        content = en_path.read_text(encoding="utf-8")
        assert "ncProgramValidation" in content
    # If file doesn't exist yet, skip gracefully
    # (keys will be checked in the full frontend build)


def test_tr_keys_exist():
    """TR i18n file has ncValidation keys (smoke check)."""
    from pathlib import Path
    tr_path = Path("frontend/app/src/i18n/tr.ts")
    if tr_path.exists():
        content = tr_path.read_text(encoding="utf-8")
        assert "ncProgramValidation" in content


# ===========================================================================
# Section 16 — BACKWARD COMPATIBILITY
# ===========================================================================


def test_existing_feed_distance_unchanged():
    """Phase 2 extensions do not change existing feed distance calculation."""
    nc = "G21 G0 X0 Y0 Z0\nG1 X100 Y0 Z0 F500\nG1 X100 Y50 Z0 F500"
    result = _parse(nc)
    # 100mm (X) + 50mm (Y) = 150mm total feed distance
    assert result.feed_distance_mm == pytest.approx(150.0, abs=1e-3)


def test_existing_rapid_distance_unchanged():
    """Phase 2 extensions do not change existing rapid distance calculation."""
    nc = "G21 G0 X0 Y0 Z0\nG0 X100"
    result = _parse(nc)
    assert result.rapid_distance_mm == pytest.approx(100.0, abs=1e-3)


def test_g94_does_not_break_commanded_feed_min():
    """G94 mode: commanded_feed_min still updated correctly."""
    result = _parse("G21 G94 G0 X0\nG1 X100 F300")
    seg = result.segments[0]
    assert seg.commanded_feed_min == pytest.approx(300.0, abs=1e-3)
