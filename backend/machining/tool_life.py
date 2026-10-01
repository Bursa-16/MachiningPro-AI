"""
Deterministic tool-life foundation engine for PHYSICS-01D.

Implements classical and generalized Taylor tool-life equations:
- Classical: Vc * T^n = C
- Inverse: Vc = C / T^n
- Forward: T = (C / Vc)^(1 / n)

All arithmetic uses Decimal for deterministic precision.
No empirical coefficients fabricated or fitted from golden outputs.
Fail-closed validation on missing C, n, or invalid Vc/T.

Reference:
  - Taylor, F. W. (1907): "On the Art of Cutting Metals"
  - ISO 513: Tool materials and tool life assessment
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum

# Assume domain module provides Quantity, Unit, DomainError
try:
    from backend.domain.exceptions import DomainError
    from backend.domain.units import Quantity, Unit
except ImportError:
    # Fallback for standalone testing
    class Unit:
        M_MIN = "m/min"
        MIN = "min"

    @dataclass
    class Quantity:
        value: Decimal
        unit: str

        def __post_init__(self):
            if not isinstance(self.value, Decimal):
                self.value = Decimal(str(self.value))
            if not self.value.is_finite():
                raise ValueError(f"Quantity value must be finite, got {self.value}")

    class DomainError(Exception):
        pass


class ToolLifeModelType(Enum):
    """Tool-life model classification."""
    CLASSICAL_TAYLOR = "classical_taylor"
    GENERALIZED_TAYLOR = "generalized_taylor"  # Placeholder for future
    EMPIRICAL = "empirical"  # Reserved; not implemented


class ToolLifeError(DomainError):
    """Tool-life calculation error."""
    pass


@dataclass(frozen=True, slots=True)
class TaylorToolLifeParameters:
    """
    Immutable Taylor coefficient specification.

    Attributes:
        C: Taylor constant [m/min under classical convention]
        n: Taylor exponent (dimensionless, typically 0.1 to 0.8)
        source: Provenance/source of coefficients (required)
        material_id: Optional material identifier
        tool_id: Optional tool substrate identifier
        coating_id: Optional coating identifier
        applicability_notes: Optional notes on where these coefficients apply

    Validation:
    - C must be positive and finite
    - n must be positive and finite
    - source must be non-empty string
    - No default C or n
    """

    C: Quantity
    n: Decimal
    source: str
    material_id: str | None = None
    tool_id: str | None = None
    coating_id: str | None = None
    applicability_notes: str | None = None

    def __post_init__(self):
        """Validate Taylor parameters in fail-closed manner."""
        # Validate C
        if self.C is None:
            raise ToolLifeError("C must be provided (no default)")
        if not isinstance(self.C, Quantity):
            raise ToolLifeError(f"C must be Quantity, got {type(self.C)}")
        if self.C.unit != Unit.M_MIN:
            raise ToolLifeError(
                f"C must have unit {Unit.M_MIN}, got {self.C.unit}"
            )
        if self.C.value <= 0:
            raise ToolLifeError(f"C must be > 0, got {self.C.value}")
        if not self.C.value.is_finite():
            raise ToolLifeError(f"C must be finite, got {self.C.value}")

        # Validate n
        if self.n is None:
            raise ToolLifeError("n must be provided (no default)")

        # Ensure n is Decimal
        n_val = self.n
        if not isinstance(n_val, Decimal):
            try:
                n_val = Decimal(str(n_val))
            except (InvalidOperation, ValueError, TypeError) as exc:
                raise ToolLifeError(
                    f"n must be a finite Decimal, got {n_val!r}"
                ) from exc

        # Check n is finite
        if not n_val.is_finite():
            raise ToolLifeError(f"n must be finite, got {n_val}")

        # Check n is positive
        if n_val <= 0:
            raise ToolLifeError(f"n must be > 0, got {n_val}")

        # Note: n range not restricted. Classical Taylor exponent n can vary widely
        # depending on material and cutting conditions. Documented sources support
        # n values from < 0.1 (hard materials, interrupted cutting) to > 0.8 (soft materials).
        # Validation constraint is: n > 0 and finite (verified above).

        # Validate source
        if not self.source or not isinstance(self.source, str):
            raise ToolLifeError(
                "source must be non-empty string "
                "(required for provenance traceability)"
            )


@dataclass(frozen=True, slots=True)
class ToolLifeInput:
    """
    Immutable tool-life calculation input.

    Attributes:
        cutting_speed: Vc [m/min]
        tool_life: T [min] (for inverse calculation, optional)
        parameters: TaylorToolLifeParameters
        model_type: ToolLifeModelType (default: CLASSICAL_TAYLOR)

    Validation:
    - Vc must be positive [m/min]
    - T (if provided) must be positive [min]
    - One of (Vc, T) is used depending on calculation direction
    """

    cutting_speed: Quantity | None = None
    tool_life: Quantity | None = None
    parameters: TaylorToolLifeParameters = None
    model_type: ToolLifeModelType = ToolLifeModelType.CLASSICAL_TAYLOR

    def __post_init__(self):
        """Validate tool-life input in fail-closed manner."""
        # Validate model type
        if not isinstance(self.model_type, ToolLifeModelType):
            raise ToolLifeError(f"Unsupported model_type: {self.model_type}")

        # Validate parameters
        if self.parameters is None:
            raise ToolLifeError("parameters must be provided")
        if not isinstance(self.parameters, TaylorToolLifeParameters):
            raise ToolLifeError(
                f"parameters must be TaylorToolLifeParameters, "
                f"got {type(self.parameters)}"
            )

        # At least one of cutting_speed or tool_life must be provided
        has_vc = self.cutting_speed is not None
        has_t = self.tool_life is not None

        if not has_vc and not has_t:
            raise ToolLifeError(
                "Either cutting_speed or tool_life must be provided"
            )

        # Validate cutting_speed if provided
        if has_vc:
            if self.cutting_speed.unit != Unit.M_MIN:
                raise ToolLifeError(
                    f"cutting_speed must have unit {Unit.M_MIN}, "
                    f"got {self.cutting_speed.unit}"
                )
            if self.cutting_speed.value <= 0:
                raise ToolLifeError(
                    f"cutting_speed must be > 0, got {self.cutting_speed.value}"
                )
            if not self.cutting_speed.value.is_finite():
                raise ToolLifeError(
                    f"cutting_speed must be finite, "
                    f"got {self.cutting_speed.value}"
                )

        # Validate tool_life if provided
        if has_t:
            if self.tool_life.unit != Unit.MIN:
                raise ToolLifeError(
                    f"tool_life must have unit {Unit.MIN}, "
                    f"got {self.tool_life.unit}"
                )
            if self.tool_life.value <= 0:
                raise ToolLifeError(
                    f"tool_life must be > 0, got {self.tool_life.value}"
                )
            if not self.tool_life.value.is_finite():
                raise ToolLifeError(
                    f"tool_life must be finite, got {self.tool_life.value}"
                )


@dataclass(frozen=True, slots=True)
class ToolLifeResult:
    """
    Immutable result of tool-life calculation.

    Attributes:
        predicted_tool_life: Predicted T [min] (forward calculation)
        predicted_cutting_speed: Predicted Vc [m/min] (inverse calculation)
        model_name: Human-readable model name (e.g., "ClassicalTaylor")
        model_type: ToolLifeModelType classification
        parameters_used: TaylorToolLifeParameters used in calculation
        assumptions: Geometric/material assumptions and constraints
        status: Calculation status (e.g., "DETERMINISTIC_THEORETICAL")
        provenance: Coefficient provenance from parameters.source
    """

    predicted_tool_life: Quantity | None = None
    predicted_cutting_speed: Quantity | None = None
    model_name: str = ""
    model_type: ToolLifeModelType = ToolLifeModelType.CLASSICAL_TAYLOR
    parameters_used: TaylorToolLifeParameters = None
    assumptions: str = ""
    status: str = "DETERMINISTIC_THEORETICAL"
    provenance: str = ""


# ================================================================
# Core Calculations
# ================================================================

ZERO = Decimal("0")
ONE = Decimal("1")


def taylor_forward_tool_life(
    cutting_speed: Quantity,
    parameters: TaylorToolLifeParameters,
) -> Quantity:
    r"""
    Compute tool life from cutting speed using Taylor equation.

    Equation:
        T = (C / Vc)^(1 / n)

    where:
        C = Taylor constant [m/min]
        Vc = cutting speed [m/min]
        n = Taylor exponent [dimensionless]

    Args:
        cutting_speed: Vc [m/min]
        parameters: TaylorToolLifeParameters with C, n, source

    Returns:
        Tool life T [min]

    Raises:
        ToolLifeError: if calculation fails or parameters invalid
    """
    # Validate cutting speed unit
    if cutting_speed.unit != Unit.M_MIN:
        raise ToolLifeError(
            f"Cutting speed must use unit {Unit.M_MIN}, got {cutting_speed.unit}"
        )

    if cutting_speed.value <= 0:
        raise ToolLifeError(
            f"Cutting speed must be > 0, got {cutting_speed.value} m/min"
        )

    vc_val = Decimal(str(cutting_speed.value))
    c_val = Decimal(str(parameters.C.value))
    n_val = parameters.n

    # Compute T = (C / Vc)^(1 / n)
    try:
        # Ratio C / Vc
        ratio = c_val / vc_val

        # Exponent 1 / n
        inv_n = ONE / n_val

        # Handle exact exponents to preserve precision
        if inv_n == ONE:
            # T = ratio^1 = ratio (exact)
            t_val = ratio
        elif inv_n == Decimal("0.5"):
            # T = sqrt(ratio) (use Decimal sqrt for high precision)
            t_val = ratio.sqrt()
        elif inv_n % ONE == ZERO:
            # T = ratio^(integer exponent)
            # inv_n is an exact integer (inv_n % 1 == 0)
            int_exp = int(inv_n)
            if int_exp <= 5:
                t_val = ratio ** int_exp
            else:
                # For larger exponents, use ln/exp
                ln_ratio = ratio.ln()
                t_val = (inv_n * ln_ratio).exp()
        else:
            # General non-integer exponent: use ln/exp
            # T = exp((1/n) * ln(C/Vc))
            ln_ratio = ratio.ln()
            exponent_term = inv_n * ln_ratio
            t_val = exponent_term.exp()

    except Exception as exc:
        raise ToolLifeError(
            f"Taylor forward calculation failed: C={c_val}, Vc={vc_val}, "
            f"n={n_val}, error={exc}"
        ) from exc

    return Quantity(t_val, Unit.MIN)


def taylor_inverse_cutting_speed(
    tool_life: Quantity,
    parameters: TaylorToolLifeParameters,
) -> Quantity:
    r"""
    Compute cutting speed from tool life using inverse Taylor equation.

    Equation:
        Vc = C / T^n

    where:
        C = Taylor constant [m/min]
        T = tool life [min]
        n = Taylor exponent [dimensionless]

    Args:
        tool_life: T [min]
        parameters: TaylorToolLifeParameters with C, n, source

    Returns:
        Cutting speed Vc [m/min]

    Raises:
        ToolLifeError: if calculation fails or parameters invalid
    """
    # Validate tool life unit
    if tool_life.unit != Unit.MIN:
        raise ToolLifeError(
            f"Tool life must use unit {Unit.MIN}, got {tool_life.unit}"
        )

    if tool_life.value <= 0:
        raise ToolLifeError(
            f"Tool life must be > 0, got {tool_life.value} min"
        )

    t_val = Decimal(str(tool_life.value))
    c_val = Decimal(str(parameters.C.value))
    n_val = parameters.n

    # Compute Vc = C / T^n
    try:
        # Compute T^n
        if n_val == ONE:
            # T^1 = T (exact)
            t_to_n = t_val
        elif n_val == Decimal("0.5"):
            # T^0.5 = sqrt(T)
            t_to_n = t_val.sqrt()
        elif n_val % ONE == ZERO:
            # T^(integer exponent)
            # n_val is an exact integer (n_val % 1 == 0)
            int_exp = int(n_val)
            if int_exp <= 5:
                t_to_n = t_val ** int_exp
            else:
                # For larger exponents, use ln/exp
                ln_t = t_val.ln()
                t_to_n = (n_val * ln_t).exp()
        else:
            # General non-integer exponent: use ln/exp
            # T^n = exp(n * ln(T))
            ln_t = t_val.ln()
            exponent_term = n_val * ln_t
            t_to_n = exponent_term.exp()

        # Vc = C / T^n
        vc_val = c_val / t_to_n

    except Exception as exc:
        raise ToolLifeError(
            f"Taylor inverse calculation failed: C={c_val}, T={t_val}, "
            f"n={n_val}, error={exc}"
        ) from exc

    return Quantity(vc_val, Unit.M_MIN)


# ================================================================
# High-Level Interface
# ================================================================

def compute_tool_life(tool_input: ToolLifeInput) -> ToolLifeResult:
    """
    High-level deterministic tool-life calculation.

    Routes to appropriate model (classical Taylor, etc.) and returns
    full traceability result.

    Args:
        tool_input: ToolLifeInput with validated parameters

    Returns:
        ToolLifeResult with predicted life/speed and metadata

    Raises:
        ToolLifeError: if calculation fails or required parameters missing
    """
    if tool_input.model_type == ToolLifeModelType.CLASSICAL_TAYLOR:
        return _compute_classical_taylor(tool_input)

    elif tool_input.model_type == ToolLifeModelType.EMPIRICAL:
        raise ToolLifeError("EMPIRICAL model not yet implemented")

    else:
        raise ToolLifeError(
            f"Unknown model type: {tool_input.model_type}"
        )


def _compute_classical_taylor(
    tool_input: ToolLifeInput,
) -> ToolLifeResult:
    """Compute classical Taylor tool life."""
    params = tool_input.parameters

    if tool_input.cutting_speed is not None:
        # Forward calculation: Vc → T
        predicted_t = taylor_forward_tool_life(
            tool_input.cutting_speed,
            params
        )

        assumptions = (
            "Classical Taylor equation: Vc * T^n = C. "
            "Forward calculation: T = (C / Vc)^(1/n). "
            "Assumes: sharp tool, constant cutting conditions, "
            "no chatter or vibration, stable material. "
            "Model predicts tool life at onset of wear criterion; "
            "actual tool life depends on EOL definition and measured wear state. "
            f"Coefficient source: {params.source}. "
            "Do not assume equivalence with measured production tool life."
        )

        return ToolLifeResult(
            predicted_tool_life=predicted_t,
            predicted_cutting_speed=None,
            model_name="ClassicalTaylor",
            model_type=ToolLifeModelType.CLASSICAL_TAYLOR,
            parameters_used=params,
            assumptions=assumptions,
            status="DETERMINISTIC_THEORETICAL",
            provenance=params.source
        )

    elif tool_input.tool_life is not None:
        # Inverse calculation: T → Vc
        predicted_vc = taylor_inverse_cutting_speed(
            tool_input.tool_life,
            params
        )

        assumptions = (
            "Classical Taylor equation: Vc * T^n = C. "
            "Inverse calculation: Vc = C / T^n. "
            "Assumes: sharp tool, constant cutting conditions, "
            "no chatter or vibration, stable material. "
            "Model predicts cutting speed for target tool life; "
            "actual achievable life depends on process stability and EOL criteria. "
            f"Coefficient source: {params.source}. "
            "Do not assume equivalence with measured production tool life."
        )

        return ToolLifeResult(
            predicted_tool_life=None,
            predicted_cutting_speed=predicted_vc,
            model_name="ClassicalTaylor",
            model_type=ToolLifeModelType.CLASSICAL_TAYLOR,
            parameters_used=params,
            assumptions=assumptions,
            status="DETERMINISTIC_THEORETICAL",
            provenance=params.source
        )

    else:
        raise ToolLifeError(
            "ToolLifeInput: neither cutting_speed nor tool_life provided"
        )


# VP100 Audit
VP100_AUDIT = {
    "VP100_T_EOL_DIRECTLY_COMPUTABLE": False,
    "VP100_T_EOL_MISSING_INPUTS": [
        "Taylor C (tool-life constant)",
        "Taylor n (exponent)",
        "material_id and material-specific C/n coefficients",
        "tool_substrate_id and tool-specific coefficients",
        "coating_id and coating-specific coefficients",
        "wear_criterion or EOL_definition (flank wear threshold, etc.)",
        "feed_influence (generalized model, not classical)",
        "depth_of_cut_influence (generalized model, not classical)",
    ],
    "VP100_T_EOL_STATUS": "BLOCKED (missing validated coefficients and EOL definition)",
    "REASON": (
        "VP100 provides cutting speed (Vc), feeds, depths, and measured t_eol_min. "
        "Classical Taylor tool life requires empirical coefficients C and n, "
        "which must be calibrated from production data or validated sources. "
        "C and n depend on material, tool substrate, and coating. "
        "Without these validated coefficients, T_EOL cannot be predicted. "
        "Future phase: calibrate C/n from VP100 golden T_EOL values "
        "after phase 01D foundation is established."
    ),
}
