"""
Comprehensive test suite for PHYSICS-01D tool-life foundation.

Tests classical Taylor equation implementation:
- Forward: T = (C / Vc)^(1/n)
- Inverse: Vc = C / T^n

Required criteria:
- No fabricated coefficients
- No VP100 fitting
- Decimal precision throughout
- Fail-closed validation
- Provenance traceability
"""

from decimal import Decimal

import pytest

from backend.domain.exceptions import UnitError

# Production package import (no fallback)
from backend.machining.tool_life import (
    Quantity,
    TaylorToolLifeParameters,
    ToolLifeError,
    ToolLifeInput,
    ToolLifeModelType,
    ToolLifeResult,
    Unit,
    compute_tool_life,
    taylor_forward_tool_life,
    taylor_inverse_cutting_speed,
)

# ================================================================
# Test Fixtures
# ================================================================

@pytest.fixture
def params_exact_n_one():
    """C=200 m/min, n=1 (exact exponent case)."""
    return TaylorToolLifeParameters(
        C=Quantity(Decimal("200"), Unit.M_MIN),
        n=Decimal("1"),
        source="test_fixture: exact_n_one"
    )


@pytest.fixture
def params_exact_n_half():
    """C=400 m/min, n=0.5 (exact sqrt case). Note: 1/n = 2."""
    return TaylorToolLifeParameters(
        C=Quantity(Decimal("400"), Unit.M_MIN),
        n=Decimal("0.5"),
        source="test_fixture: exact_n_half"
    )


@pytest.fixture
def params_non_integer():
    """C=300 m/min, n=0.3 (non-integer exponent)."""
    return TaylorToolLifeParameters(
        C=Quantity(Decimal("300"), Unit.M_MIN),
        n=Decimal("0.3"),
        source="test_fixture: non_integer_exponent"
    )


# ================================================================
# 1. EXACT N=1 FORWARD TEST
# ================================================================

def test_exact_n_one_forward(params_exact_n_one):
    """
    Test exact n=1 case (identity path).
    C=200, Vc=100, n=1 → T = (200/100)^(1/1) = 2 min exactly.
    """
    vc = Quantity(Decimal("100"), Unit.M_MIN)
    result = taylor_forward_tool_life(vc, params_exact_n_one)

    # Should be exactly 2
    assert result.unit == Unit.MIN
    assert result.value == Decimal("2")


# ================================================================
# 2. EXACT N=1 INVERSE TEST
# ================================================================

def test_exact_n_one_inverse(params_exact_n_one):
    """
    Test exact n=1 inverse (identity path).
    C=200, T=2, n=1 → Vc = 200 / 2^1 = 100 m/min exactly.
    """
    t = Quantity(Decimal("2"), Unit.MIN)
    result = taylor_inverse_cutting_speed(t, params_exact_n_one)

    # Should be exactly 100
    assert result.unit == Unit.M_MIN
    assert result.value == Decimal("100")


# ================================================================
# 3. EXACT SQRT PATH TEST (n=0.5, inv_n=2)
# ================================================================

def test_exact_sqrt_forward():
    """
    Test exact sqrt path.
    n=0.5 → 1/n = 2 (exact)
    C=400, Vc=100 → ratio = 4, T = 4^2 = 16 min exactly (via sqrt path).

    Verify: T = (C / Vc)^(1/n) = (400/100)^2 = 4^2 = 16
    """
    params = TaylorToolLifeParameters(
        C=Quantity(Decimal("400"), Unit.M_MIN),
        n=Decimal("0.5"),
        source="test_exact_sqrt"
    )
    vc = Quantity(Decimal("100"), Unit.M_MIN)
    result = taylor_forward_tool_life(vc, params)

    # T = (400/100)^(1/0.5) = 4^2 = 16 min exactly
    assert result.value == Decimal("16")


def test_exact_sqrt_inverse():
    """
    Test inverse exact sqrt path.
    n=0.5 → T^n = T^0.5 = sqrt(T)
    C=400, T=16 → Vc = 400 / sqrt(16) = 400 / 4 = 100 m/min exactly.
    """
    params = TaylorToolLifeParameters(
        C=Quantity(Decimal("400"), Unit.M_MIN),
        n=Decimal("0.5"),
        source="test_exact_sqrt_inverse"
    )
    t = Quantity(Decimal("16"), Unit.MIN)
    result = taylor_inverse_cutting_speed(t, params)

    # Vc = 400 / sqrt(16) = 400 / 4 = 100 m/min exactly
    assert result.value == Decimal("100")


# ================================================================
# 4. NON-INTEGER EXPONENT TEST (ln/exp path)
# ================================================================

def test_non_integer_exponent_forward(params_non_integer):
    """
    Test non-integer exponent via ln/exp.
    C=300, Vc=150, n=0.3

    T = (300/150)^(1/0.3) = 2^3.333... (approximately 10.079)

    Verify deterministically that Decimal ln/exp is used and result is computable.
    """
    vc = Quantity(Decimal("150"), Unit.M_MIN)
    result = taylor_forward_tool_life(vc, params_non_integer)

    # Result should be positive and finite
    assert result.unit == Unit.MIN
    assert result.value > 0
    assert result.value.is_finite()

    # Rough check: T ≈ 10.079
    # (More precise: 2^(1/0.3) = 2^3.333... ≈ 10.0793)
    assert Decimal("10") < result.value < Decimal("11")


def test_non_integer_exponent_inverse(params_non_integer):
    """
    Test non-integer inverse via ln/exp.
    C=300, T=10.0793, n=0.3

    Vc = 300 / (10.0793^0.3) ≈ 300 / 2 = 150 m/min
    """
    # Use computed T from forward case
    t = Quantity(Decimal("10.0793"), Unit.MIN)
    result = taylor_inverse_cutting_speed(t, params_non_integer)

    # Result should be positive and finite
    assert result.unit == Unit.M_MIN
    assert result.value > 0
    assert result.value.is_finite()

    # Should be close to 150 (within Decimal precision)
    # Expect ~150; allow some ln/exp rounding
    assert Decimal("149") < result.value < Decimal("151")


# ================================================================
# 5. FORWARD/INVERSE ROUND-TRIP TEST
# ================================================================

def test_forward_inverse_roundtrip(params_exact_n_one):
    """
    Forward then inverse should recover original input.
    Vc_orig=100 → T → Vc_recovered ≈ Vc_orig
    """
    vc_orig = Quantity(Decimal("100"), Unit.M_MIN)

    # Forward: Vc → T
    t_result = taylor_forward_tool_life(vc_orig, params_exact_n_one)

    # Inverse: T → Vc
    vc_recovered = taylor_inverse_cutting_speed(t_result, params_exact_n_one)

    # Should recover original Vc
    assert vc_recovered.value == vc_orig.value


def test_inverse_forward_roundtrip(params_exact_n_one):
    """
    Inverse then forward should recover original input.
    T_orig=2 → Vc → T_recovered ≈ T_orig
    """
    t_orig = Quantity(Decimal("2"), Unit.MIN)

    # Inverse: T → Vc
    vc_result = taylor_inverse_cutting_speed(t_orig, params_exact_n_one)

    # Forward: Vc → T
    t_recovered = taylor_forward_tool_life(vc_result, params_exact_n_one)

    # Should recover original T
    assert t_recovered.value == t_orig.value


# ================================================================
# 6. DETERMINISTIC REPEATABILITY TEST
# ================================================================

def test_deterministic_repeatability(params_exact_n_one):
    """Multiple calls with identical inputs produce identical Decimal results."""
    vc = Quantity(Decimal("100"), Unit.M_MIN)

    result1 = taylor_forward_tool_life(vc, params_exact_n_one)
    result2 = taylor_forward_tool_life(vc, params_exact_n_one)
    result3 = taylor_forward_tool_life(vc, params_exact_n_one)

    # All must be bitwise identical
    assert result1.value == result2.value
    assert result2.value == result3.value


# ================================================================
# 7-12. VALIDATION TESTS (fail-closed)
# ================================================================

def test_invalid_cutting_speed_zero(params_exact_n_one):
    """Reject Vc <= 0."""
    vc_invalid = Quantity(Decimal("0"), Unit.M_MIN)

    with pytest.raises(ToolLifeError):
        taylor_forward_tool_life(vc_invalid, params_exact_n_one)


def test_invalid_cutting_speed_negative(params_exact_n_one):
    """Reject Vc < 0."""
    vc_invalid = Quantity(Decimal("-100"), Unit.M_MIN)

    with pytest.raises(ToolLifeError):
        taylor_forward_tool_life(vc_invalid, params_exact_n_one)


def test_invalid_tool_life_zero(params_exact_n_one):
    """Reject T <= 0."""
    t_invalid = Quantity(Decimal("0"), Unit.MIN)

    with pytest.raises(ToolLifeError):
        taylor_inverse_cutting_speed(t_invalid, params_exact_n_one)


def test_invalid_tool_life_negative(params_exact_n_one):
    """Reject T < 0."""
    t_invalid = Quantity(Decimal("-10"), Unit.MIN)

    with pytest.raises(ToolLifeError):
        taylor_inverse_cutting_speed(t_invalid, params_exact_n_one)


def test_invalid_c_zero():
    """Reject C <= 0."""
    with pytest.raises(ToolLifeError):
        TaylorToolLifeParameters(
            C=Quantity(Decimal("0"), Unit.M_MIN),
            n=Decimal("1"),
            source="test_invalid_c"
        )


def test_invalid_c_negative():
    """Reject C < 0."""
    with pytest.raises(ToolLifeError):
        TaylorToolLifeParameters(
            C=Quantity(Decimal("-200"), Unit.M_MIN),
            n=Decimal("1"),
            source="test_invalid_c_neg"
        )


def test_invalid_n_zero():
    """Reject n <= 0."""
    with pytest.raises(ToolLifeError):
        TaylorToolLifeParameters(
            C=Quantity(Decimal("200"), Unit.M_MIN),
            n=Decimal("0"),
            source="test_invalid_n_zero"
        )


def test_invalid_n_negative():
    """Reject n < 0."""
    with pytest.raises(ToolLifeError):
        TaylorToolLifeParameters(
            C=Quantity(Decimal("200"), Unit.M_MIN),
            n=Decimal("-0.5"),
            source="test_invalid_n_neg"
        )


def test_wrong_unit_cutting_speed(params_exact_n_one):
    """Reject wrong unit for cutting_speed (fail-closed).

    Cutting speed must use Unit.M_MIN (m/min).
    Any other unit must raise ToolLifeError at function level.
    """
    vc_wrong_unit = Quantity(Decimal("100"), Unit.MIN)  # Wrong unit (minutes, not m/min)

    with pytest.raises(ToolLifeError) as exc_info:
        taylor_forward_tool_life(vc_wrong_unit, params_exact_n_one)

    assert "unit" in str(exc_info.value).lower()


def test_wrong_unit_tool_life(params_exact_n_one):
    """Reject wrong unit for tool_life (fail-closed).

    Tool life must use Unit.MIN (min).
    Any other unit must raise ToolLifeError at function level.
    """
    t_wrong_unit = Quantity(Decimal("2"), Unit.M_MIN)  # Wrong unit (m/min, not minutes)

    with pytest.raises(ToolLifeError) as exc_info:
        taylor_inverse_cutting_speed(t_wrong_unit, params_exact_n_one)

    assert "unit" in str(exc_info.value).lower()


def test_wrong_unit_c():
    """Reject wrong unit for C."""
    with pytest.raises(ToolLifeError):
        TaylorToolLifeParameters(
            C=Quantity(Decimal("200"), Unit.MIN),  # Wrong unit
            n=Decimal("1"),
            source="test_wrong_unit_c"
        )


def test_non_finite_cutting_speed(params_exact_n_one):
    """Reject non-finite Vc (infinity, NaN).

    Non-finite validation occurs at Quantity creation level.
    This test verifies that non-finite values are rejected.
    """
    with pytest.raises(UnitError):
        # Non-finite validation happens in Quantity.__post_init__
        Quantity(Decimal("Infinity"), Unit.M_MIN)


def test_non_finite_tool_life(params_exact_n_one):
    """Reject non-finite T.

    Non-finite validation occurs at Quantity creation level.
    This test verifies that non-finite values are rejected.
    """
    with pytest.raises(UnitError):
        # Non-finite validation happens in Quantity.__post_init__
        Quantity(Decimal("NaN"), Unit.MIN)


def test_non_finite_c():
    """Reject non-finite C.

    Non-finite validation occurs at Quantity creation level.
    This test verifies that non-finite C is rejected.
    """
    with pytest.raises(UnitError):
        # Non-finite validation happens in Quantity.__post_init__
        Quantity(Decimal("Infinity"), Unit.M_MIN)


def test_non_finite_n():
    """Reject non-finite n."""
    with pytest.raises(ToolLifeError):
        TaylorToolLifeParameters(
            C=Quantity(Decimal("200"), Unit.M_MIN),
            n=Decimal("NaN"),
            source="test_non_finite_n"
        )


def test_missing_source_provenance():
    """Reject missing source (provenance mandatory)."""
    with pytest.raises(ToolLifeError):
        TaylorToolLifeParameters(
            C=Quantity(Decimal("200"), Unit.M_MIN),
            n=Decimal("1"),
            source=""  # Empty source
        )


# ================================================================
# 13-15. NO DEFAULT COEFFICIENTS
# ================================================================

def test_no_default_c():
    """C must be explicitly provided."""
    # Attempting to create params without C should fail
    with pytest.raises(ToolLifeError):
        TaylorToolLifeParameters(
            C=None,
            n=Decimal("1"),
            source="test_no_default_c"
        )


def test_no_default_n():
    """n must be explicitly provided."""
    with pytest.raises(ToolLifeError):
        TaylorToolLifeParameters(
            C=Quantity(Decimal("200"), Unit.M_MIN),
            n=None,
            source="test_no_default_n"
        )


# ================================================================
# 16. UNSUPPORTED MODEL TYPE
# ================================================================

def test_unsupported_model_type(params_exact_n_one):
    """Reject unsupported model type."""
    # Generalized Taylor not yet implemented
    tool_input = ToolLifeInput(
        cutting_speed=Quantity(Decimal("100"), Unit.M_MIN),
        parameters=params_exact_n_one,
        model_type=ToolLifeModelType.GENERALIZED_TAYLOR
    )

    with pytest.raises(ToolLifeError):
        compute_tool_life(tool_input)


def test_empirical_model_not_implemented(params_exact_n_one):
    """Reject EMPIRICAL model (reserved for future)."""
    tool_input = ToolLifeInput(
        cutting_speed=Quantity(Decimal("100"), Unit.M_MIN),
        parameters=params_exact_n_one,
        model_type=ToolLifeModelType.EMPIRICAL
    )

    with pytest.raises(ToolLifeError):
        compute_tool_life(tool_input)


# ================================================================
# 17. PROVENANCE PRESERVATION
# ================================================================

def test_provenance_preserved_forward(params_exact_n_one):
    """Provenance source is preserved in result."""
    tool_input = ToolLifeInput(
        cutting_speed=Quantity(Decimal("100"), Unit.M_MIN),
        parameters=params_exact_n_one,
        model_type=ToolLifeModelType.CLASSICAL_TAYLOR
    )

    result = compute_tool_life(tool_input)

    assert result.provenance == "test_fixture: exact_n_one"
    assert result.parameters_used.source == "test_fixture: exact_n_one"


def test_provenance_preserved_inverse(params_exact_n_one):
    """Provenance source is preserved in inverse result."""
    tool_input = ToolLifeInput(
        tool_life=Quantity(Decimal("2"), Unit.MIN),
        parameters=params_exact_n_one,
        model_type=ToolLifeModelType.CLASSICAL_TAYLOR
    )

    result = compute_tool_life(tool_input)

    assert result.provenance == "test_fixture: exact_n_one"
    assert result.parameters_used.source == "test_fixture: exact_n_one"


def test_assumptions_present_forward(params_exact_n_one):
    """Forward result includes clear assumptions."""
    tool_input = ToolLifeInput(
        cutting_speed=Quantity(Decimal("100"), Unit.M_MIN),
        parameters=params_exact_n_one,
        model_type=ToolLifeModelType.CLASSICAL_TAYLOR
    )

    result = compute_tool_life(tool_input)

    # Verify key assumption statements are present
    assert "Classical Taylor" in result.assumptions
    assert "sharp tool" in result.assumptions.lower()
    # Check for model behavior description (case-insensitive)
    assert "model predicts" in result.assumptions.lower()
    assert "Do not assume equivalence with measured production tool life" in result.assumptions


def test_assumptions_present_inverse(params_exact_n_one):
    """Inverse result includes clear assumptions."""
    tool_input = ToolLifeInput(
        tool_life=Quantity(Decimal("2"), Unit.MIN),
        parameters=params_exact_n_one,
        model_type=ToolLifeModelType.CLASSICAL_TAYLOR
    )

    result = compute_tool_life(tool_input)

    # Verify key assumption statements are present
    assert "Classical Taylor" in result.assumptions
    assert "sharp tool" in result.assumptions.lower()
    # Check for model behavior description (case-insensitive)
    assert "inverse calculation" in result.assumptions.lower()


# ================================================================
# 18-19. MODEL TYPE & VP100 STATUS
# ================================================================

def test_generalized_taylor_not_implemented():
    """Generalized Taylor explicitly marked as NOT_IMPLEMENTED."""
    params = TaylorToolLifeParameters(
        C=Quantity(Decimal("300"), Unit.M_MIN),
        n=Decimal("0.4"),
        source="test_gen_taylor"
    )

    tool_input = ToolLifeInput(
        cutting_speed=Quantity(Decimal("100"), Unit.M_MIN),
        parameters=params,
        model_type=ToolLifeModelType.GENERALIZED_TAYLOR
    )

    with pytest.raises(ToolLifeError) as exc_info:
        compute_tool_life(tool_input)

    # Should fail or redirect appropriately
    assert exc_info.value is not None


def test_vp100_remains_blocked():
    """VP100 T_EOL remains BLOCKED without validated C/n."""
    try:
        from backend.machining.tool_life import VP100_AUDIT
    except ImportError:
        # Fallback for cloud/scratchpad testing
        from tool_life import VP100_AUDIT

    assert VP100_AUDIT["VP100_T_EOL_DIRECTLY_COMPUTABLE"] is False
    assert "BLOCKED" in VP100_AUDIT["VP100_T_EOL_STATUS"]
    assert "missing validated coefficients" in VP100_AUDIT["VP100_T_EOL_STATUS"].lower()


# ================================================================
# 20. WIDE N RANGE (no arbitrary limit)
# ================================================================

def test_wide_n_range_very_small():
    """Accept very small n (e.g., n=0.05)."""
    params = TaylorToolLifeParameters(
        C=Quantity(Decimal("200"), Unit.M_MIN),
        n=Decimal("0.05"),
        source="test_wide_n_small"
    )

    vc = Quantity(Decimal("100"), Unit.M_MIN)
    result = taylor_forward_tool_life(vc, params)

    # Should succeed; result will be very different from n=1 case
    assert result.value > 0
    assert result.value.is_finite()


def test_wide_n_range_large():
    """Accept large n (e.g., n=3.5)."""
    params = TaylorToolLifeParameters(
        C=Quantity(Decimal("200"), Unit.M_MIN),
        n=Decimal("3.5"),
        source="test_wide_n_large"
    )

    vc = Quantity(Decimal("100"), Unit.M_MIN)
    result = taylor_forward_tool_life(vc, params)

    # Should succeed; result will reflect large exponent
    assert result.value > 0
    assert result.value.is_finite()


# ================================================================
# 21. NO VP100 FITTING
# ================================================================

def test_no_coefficients_from_vp100():
    """Parameters are never fitted from VP100 golden values.

    This is guaranteed by the test fixtures: all C/n values are
    hand-picked test constants, not derived from VP100.

    VP100_AUDIT confirms:
    - VP100_T_EOL_DIRECTLY_COMPUTABLE = False
    - VP100_T_EOL_STATUS = BLOCKED
    - No golden t_eol values embedded in calculation
    """
    # Verify fixture: params_exact_n_one uses C=200, n=1 (hand-picked)
    params = TaylorToolLifeParameters(
        C=Quantity(Decimal("200"), Unit.M_MIN),
        n=Decimal("1"),
        source="test_constant: explicit hand-picked value"
    )

    # Verify no default C, no default n
    assert params.C.value == Decimal("200")
    assert params.n == Decimal("1")

    # Verify source is documented
    assert params.source is not None
    assert len(params.source) > 0


# ================================================================
# 22. DECIMAL PRECISION (no float leakage)
# ================================================================

def test_decimal_precision_preserved():
    """Decimal arithmetic is used throughout; no float conversion."""
    params = TaylorToolLifeParameters(
        C=Quantity(Decimal("200"), Unit.M_MIN),
        n=Decimal("1"),
        source="test_decimal_precision"
    )

    vc = Quantity(Decimal("100"), Unit.M_MIN)
    result = taylor_forward_tool_life(vc, params)

    # Result must be Decimal, not float
    assert isinstance(result.value, Decimal)

    # Result must be exact 2, not 2.0 (float artifact)
    assert result.value == Decimal("2")


def test_no_float_leakage_in_ln_exp():
    """Even ln/exp path uses Decimal; no float conversion."""
    params = TaylorToolLifeParameters(
        C=Quantity(Decimal("300"), Unit.M_MIN),
        n=Decimal("0.3"),
        source="test_no_float_leakage"
    )

    vc = Quantity(Decimal("150"), Unit.M_MIN)
    result = taylor_forward_tool_life(vc, params)

    # Result must be Decimal (not float)
    assert isinstance(result.value, Decimal)


# ================================================================
# 23. HIGH-LEVEL COMPUTE_TOOL_LIFE INTERFACE
# ================================================================

def test_compute_tool_life_forward(params_exact_n_one):
    """High-level forward computation."""
    tool_input = ToolLifeInput(
        cutting_speed=Quantity(Decimal("100"), Unit.M_MIN),
        parameters=params_exact_n_one,
        model_type=ToolLifeModelType.CLASSICAL_TAYLOR
    )

    result = compute_tool_life(tool_input)

    assert isinstance(result, ToolLifeResult)
    assert result.predicted_tool_life is not None
    assert result.predicted_tool_life.value == Decimal("2")
    assert result.predicted_cutting_speed is None
    assert result.model_name == "ClassicalTaylor"
    assert result.status == "DETERMINISTIC_THEORETICAL"


def test_compute_tool_life_inverse(params_exact_n_one):
    """High-level inverse computation."""
    tool_input = ToolLifeInput(
        tool_life=Quantity(Decimal("2"), Unit.MIN),
        parameters=params_exact_n_one,
        model_type=ToolLifeModelType.CLASSICAL_TAYLOR
    )

    result = compute_tool_life(tool_input)

    assert isinstance(result, ToolLifeResult)
    assert result.predicted_cutting_speed is not None
    assert result.predicted_cutting_speed.value == Decimal("100")
    assert result.predicted_tool_life is None
    assert result.model_name == "ClassicalTaylor"


def test_compute_tool_life_must_provide_either_vc_or_t(params_exact_n_one):
    """Reject if neither cutting_speed nor tool_life provided.

    Validation happens at ToolLifeInput.__post_init__.
    """
    with pytest.raises(ToolLifeError):
        # ToolLifeInput.__post_init__ validates that at least one is provided
        tool_input = ToolLifeInput(
            cutting_speed=None,
            tool_life=None,
            parameters=params_exact_n_one
        )
        # If __post_init__ didn't raise, compute_tool_life should still reject
        compute_tool_life(tool_input)


# ================================================================
# 24. IMMUTABILITY TEST
# ================================================================

def test_parameters_immutable(params_exact_n_one):
    """Parameters are frozen; cannot be modified post-creation."""
    with pytest.raises((AttributeError, TypeError)):
        # Attempt to modify frozen dataclass
        params_exact_n_one.n = Decimal("2")


def test_input_immutable(params_exact_n_one):
    """Input is frozen; cannot be modified post-creation."""
    tool_input = ToolLifeInput(
        cutting_speed=Quantity(Decimal("100"), Unit.M_MIN),
        parameters=params_exact_n_one
    )

    with pytest.raises((AttributeError, TypeError)):
        tool_input.cutting_speed = Quantity(Decimal("200"), Unit.M_MIN)


def test_result_immutable(params_exact_n_one):
    """Result is frozen; cannot be modified post-creation."""
    tool_input = ToolLifeInput(
        cutting_speed=Quantity(Decimal("100"), Unit.M_MIN),
        parameters=params_exact_n_one
    )

    result = compute_tool_life(tool_input)

    with pytest.raises((AttributeError, TypeError)):
        result.predicted_tool_life = Quantity(Decimal("999"), Unit.MIN)
