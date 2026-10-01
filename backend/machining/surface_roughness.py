"""
Deterministic surface-roughness foundation engine for PHYSICS-01C.

Implements geometric roughness models based on tool geometry:
- Model A: Ideal Feed-Mark (triangular feed profile, turning-like)
- Model B: Milling Scallop Height (step-over geometry)

All arithmetic uses Decimal for deterministic precision.
Ra and Rq are computed independently; no assumption Ra == Rq.
Canonical units: mm (internal), explicit conversion to µm documented.

Reference:
  - Whitehouse & Archard (1970): Geometric profiles and roughness
  - Greenfield (1997): Milling roughness fundamentals
  - ISO 4287 (Ra/Rq definitions)
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

# Assume domain module provides Quantity, Unit, DomainError
# In real integration, import from machining.domain
try:
    from machining.domain import DomainError, Quantity, Unit
except ImportError:
    # Fallback for standalone testing
    class Unit:
        MM = "mm"
        UM = "µm"

    @dataclass
    class Quantity:
        value: Decimal
        unit: str

        def __post_init__(self):
            if not isinstance(self.value, Decimal):
                self.value = Decimal(str(self.value))

    class DomainError(Exception):
        pass


class RoughnessModelType(Enum):
    """Roughness model classification."""

    IDEAL_FEED_MARK = "ideal_feed_mark"
    IDEAL_SCALLOP = "ideal_scallop"
    EMPIRICAL = "empirical"  # Reserved; not implemented


class SurfaceRoughnessError(DomainError):
    """Surface roughness calculation error."""

    pass


@dataclass
class SurfaceRoughnessInput:
    """
    Input parameters for surface roughness calculation.

    Validates:
    - No zero/negative values
    - Correct units (mm)
    - Model-specific geometry requirements
    """

    feed_per_tooth: Quantity | None = None
    effective_radius: Quantity | None = None
    stepover: Quantity | None = None
    model_type: RoughnessModelType = RoughnessModelType.IDEAL_FEED_MARK

    def __post_init__(self):
        """Validate inputs in fail-closed manner."""
        # Validate model type
        if not isinstance(self.model_type, RoughnessModelType):
            raise SurfaceRoughnessError(f"Unsupported model_type: {self.model_type}")

        # Route to model-specific validation
        if self.model_type == RoughnessModelType.IDEAL_FEED_MARK:
            self._validate_feed_mark()
        elif self.model_type == RoughnessModelType.IDEAL_SCALLOP:
            self._validate_scallop()
        elif self.model_type == RoughnessModelType.EMPIRICAL:
            raise SurfaceRoughnessError("EMPIRICAL model not yet implemented")

    def _validate_feed_mark(self):
        """Validate IDEAL_FEED_MARK inputs."""
        if self.feed_per_tooth is None:
            raise SurfaceRoughnessError("feed_per_tooth required for IDEAL_FEED_MARK")
        if self.effective_radius is None:
            raise SurfaceRoughnessError("effective_radius required for IDEAL_FEED_MARK")

        # Check units
        if self.feed_per_tooth.unit not in (Unit.MM, "mm"):
            raise SurfaceRoughnessError(
                f"feed_per_tooth must be in mm, got {self.feed_per_tooth.unit}"
            )
        if self.effective_radius.unit not in (Unit.MM, "mm"):
            raise SurfaceRoughnessError(
                f"effective_radius must be in mm, got {self.effective_radius.unit}"
            )

        # Check positive values
        if self.feed_per_tooth.value <= 0:
            raise SurfaceRoughnessError(
                f"feed_per_tooth must be > 0, got {self.feed_per_tooth.value}"
            )
        if self.effective_radius.value <= 0:
            raise SurfaceRoughnessError(
                f"effective_radius must be > 0, got {self.effective_radius.value}"
            )

    def _validate_scallop(self):
        """Validate IDEAL_SCALLOP inputs."""
        if self.stepover is None:
            raise SurfaceRoughnessError("stepover required for IDEAL_SCALLOP")
        if self.effective_radius is None:
            raise SurfaceRoughnessError("effective_radius required for IDEAL_SCALLOP")

        # Check units
        if self.stepover.unit not in (Unit.MM, "mm"):
            raise SurfaceRoughnessError(f"stepover must be in mm, got {self.stepover.unit}")
        if self.effective_radius.unit not in (Unit.MM, "mm"):
            raise SurfaceRoughnessError(
                f"effective_radius must be in mm, got {self.effective_radius.unit}"
            )

        # Check positive values
        if self.stepover.value <= 0:
            raise SurfaceRoughnessError(f"stepover must be > 0, got {self.stepover.value}")
        if self.effective_radius.value <= 0:
            raise SurfaceRoughnessError(
                f"effective_radius must be > 0, got {self.effective_radius.value}"
            )

        # Geometric constraint: stepover < 2*radius
        ae_val = self.stepover.value
        r_val = self.effective_radius.value
        if ae_val >= 2 * r_val:
            raise SurfaceRoughnessError(
                f"Geometric impossibility: stepover ({ae_val}) >= 2*radius ({2 * r_val})"
            )


@dataclass
class SurfaceRoughnessResult:
    """
    Result of surface roughness calculation.

    Attributes:
        Ra: Arithmetic mean roughness [mm] or None if not derivable
        Rq: Root-mean-square roughness [mm] or None if not derivable
        Rz: Ten-point height [mm] or None if reserved for future
        model_name: Human-readable model name
        model_type: RoughnessModelType classification
        assumptions: Geometric assumptions, waveform, domain limits
        Ra_derivable: Whether Ra is computable for this model
        Rq_derivable: Whether Rq is computable for this model
        status: Calculation status (e.g., "THEORETICAL_GEOMETRIC")
    """

    Ra: Quantity | None = None
    Rq: Quantity | None = None
    Rz: Quantity | None = None
    model_name: str = ""
    model_type: RoughnessModelType = RoughnessModelType.IDEAL_FEED_MARK
    assumptions: str = ""
    Ra_derivable: bool = True
    Rq_derivable: bool = True
    status: str = "THEORETICAL_GEOMETRIC"


def ideal_feed_mark_roughness(fz: Quantity, radius: Quantity) -> tuple[Decimal, Decimal]:
    """
    Compute Ra and Rq for ideal feed-mark profile.

    Geometric model:
    - Tool traces triangular feed-mark profile on workpiece
    - Peak height: h = fz²/(8R)
    - Ra = h/2 = fz²/(16R)
    - Rq = h/√3 = fz²/(8√3·R)

    Note: Ra ≠ Rq for triangular profile (mathematically derived)

    Args:
        fz: Feed per tooth [mm]
        radius: Effective nose/tool radius [mm]

    Returns:
        (Ra_decimal, Rq_decimal) in mm

    Raises:
        SurfaceRoughnessError: If inputs invalid
    """
    if fz.value <= 0:
        raise SurfaceRoughnessError(f"Feed per tooth must be > 0, got {fz.value} mm")
    if radius.value <= 0:
        raise SurfaceRoughnessError(f"Effective radius must be > 0, got {radius.value} mm")

    fz_val = Decimal(str(fz.value))
    r_val = Decimal(str(radius.value))

    # h = fz² / (8R)
    h = (fz_val**2) / (Decimal(8) * r_val)

    # Ra = h/2 = fz² / (16R)
    ra = h / Decimal(2)

    # Rq = h/√3
    # √3 ≈ 1.7320508075688772935274463415059...
    sqrt3 = Decimal("1.7320508075688772935274463415059")
    rq = h / sqrt3

    return (ra, rq)


def ideal_scallop_roughness(stepover: Quantity, radius: Quantity) -> tuple[Decimal, Decimal]:
    """
    Compute Ra and Rq for milling scallop (step-over) profile.

    Geometric model:
    - Ball-end or corner radius tool with step-over distance (ae)
    - Creates cusp/scallop between passes
    - Peak height: h = ae²/(8R_corner)
    - Ra ≈ h/2 (triangular cusp approximation)
    - Rq ≈ h/√3 (approximation; empirical factor may apply)

    Valid domain: stepover < 2*radius (geometric constraint)

    Args:
        stepover: Step-over distance (ae) [mm]
        radius: Corner or ball radius [mm]

    Returns:
        (Ra_decimal, Rq_decimal) in mm

    Raises:
        SurfaceRoughnessError: If inputs invalid
    """
    if stepover.value <= 0:
        raise SurfaceRoughnessError(f"Stepover must be > 0, got {stepover.value} mm")
    if radius.value <= 0:
        raise SurfaceRoughnessError(f"Corner radius must be > 0, got {radius.value} mm")

    ae_val = Decimal(str(stepover.value))
    r_val = Decimal(str(radius.value))

    # Geometric constraint: ae < 2R
    if ae_val >= 2 * r_val:
        raise SurfaceRoughnessError(
            f"Geometric impossibility: stepover ({ae_val}) >= 2*radius ({2 * r_val}) mm"
        )

    # h = ae² / (8R)
    h = (ae_val**2) / (Decimal(8) * r_val)

    # Ra = h/2
    ra = h / Decimal(2)

    # Rq = h/√3
    sqrt3 = Decimal("1.7320508075688772935274463415059")
    rq = h / sqrt3

    return (ra, rq)


def compute_surface_roughness(input_spec: SurfaceRoughnessInput) -> SurfaceRoughnessResult:
    """
    Dispatcher for surface roughness calculation.

    Routes input to appropriate geometric model and returns
    full traceability result with Ra/Rq computed independently.

    Args:
        input_spec: Validated SurfaceRoughnessInput

    Returns:
        SurfaceRoughnessResult with Ra, Rq, metadata

    Raises:
        SurfaceRoughnessError: If model routing fails
    """
    # Input validation happens in SurfaceRoughnessInput.__post_init__

    if input_spec.model_type == RoughnessModelType.IDEAL_FEED_MARK:
        return _compute_feed_mark(input_spec)

    elif input_spec.model_type == RoughnessModelType.IDEAL_SCALLOP:
        return _compute_scallop(input_spec)

    elif input_spec.model_type == RoughnessModelType.EMPIRICAL:
        raise SurfaceRoughnessError("EMPIRICAL model not yet implemented")

    else:
        raise SurfaceRoughnessError(f"Unknown model type: {input_spec.model_type}")


def _compute_feed_mark(input_spec: SurfaceRoughnessInput) -> SurfaceRoughnessResult:
    """Compute IDEAL_FEED_MARK roughness."""
    ra_dec, rq_dec = ideal_feed_mark_roughness(
        input_spec.feed_per_tooth, input_spec.effective_radius
    )

    # Convert Decimal to Quantity [mm]
    ra_qty = Quantity(value=ra_dec, unit=Unit.MM)
    rq_qty = Quantity(value=rq_dec, unit=Unit.MM)

    assumptions = (
        "Geometric model: triangular feed-mark profile traced by nose radius. "
        "Peak height h = fz²/(8R). Ra = h/2 = fz²/(16R). Rq = h/√3 = fz²/(8√3·R). "
        "Assumes: constant feed per tooth, linear tool path, no wear, no vibration, "
        "rigid machine. Ra ≠ Rq analytically for triangular profile. "
        "Canonical unit: mm; 1 mm = 1000 µm. Domain: fz > 0, radius > 0."
    )

    return SurfaceRoughnessResult(
        Ra=ra_qty,
        Rq=rq_qty,
        Rz=None,
        model_name="IdealFeedMark",
        model_type=RoughnessModelType.IDEAL_FEED_MARK,
        assumptions=assumptions,
        Ra_derivable=True,
        Rq_derivable=True,
        status="THEORETICAL_GEOMETRIC",
    )


def _compute_scallop(input_spec: SurfaceRoughnessInput) -> SurfaceRoughnessResult:
    """Compute IDEAL_SCALLOP roughness."""
    ra_dec, rq_dec = ideal_scallop_roughness(input_spec.stepover, input_spec.effective_radius)

    # Convert Decimal to Quantity [mm]
    ra_qty = Quantity(value=ra_dec, unit=Unit.MM)
    rq_qty = Quantity(value=rq_dec, unit=Unit.MM)

    assumptions = (
        "Geometric model: ball-end or corner radius tool with step-over distance (ae). "
        "Creates cusp between adjacent passes. Peak height h = ae²/(8R_corner). "
        "Ra ≈ h/2 (triangular cusp approximation). Rq ≈ h/√3 (approximation). "
        "Assumes: constant step-over, perpendicular passes, no taper, rigid tool. "
        "Empirical factor may apply (reserved for calibration). "
        "Ra ≠ Rq analytically. Canonical unit: mm; 1 mm = 1000 µm. "
        "Domain: stepover > 0, radius > 0, stepover < 2*radius."
    )

    return SurfaceRoughnessResult(
        Ra=ra_qty,
        Rq=rq_qty,
        Rz=None,
        model_name="IdealScallop",
        model_type=RoughnessModelType.IDEAL_SCALLOP,
        assumptions=assumptions,
        Ra_derivable=True,
        Rq_derivable=True,
        status="THEORETICAL_GEOMETRIC",
    )


# VP100 Audit
VP100_AUDIT = {
    "VP100_RQ_DIRECTLY_COMPUTABLE": False,
    "VP100_RQ_MISSING_INPUTS": [
        "tool_diameter or tool_radius",
        "stepover or ae (axial engagement)",
        "effective_cutting_edge_radius or nose_radius",
        "tool_geometry_definition (ball, corner, flat)",
        "engagement_geometry (radial depth, tool path)",
    ],
    "VP100_RQ_STATUS": "BLOCKED (missing required tool geometry)",
    "REASON": (
        "VP100 provides cutting speed (Vc), feeds, depths. "
        "Surface roughness requires geometric tool parameters: "
        "nose radius, corner radius, step-over distance. "
        "These are not derivable from cutting conditions alone. "
        "Future phase: learn VP100 coefficients → geometry mapping (empirical calibration)."
    ),
}
