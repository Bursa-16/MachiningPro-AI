"""Deterministic roughness lifecycle model architecture and aggregation foundation.

PHYSICS-01F: Rq target architecture and lifecycle model foundation.

Establishes three distinct response-variable contracts:

1. TARGET_A: INSTANTANEOUS_GEOMETRIC_RQ
   Single-condition theoretical surface geometry prediction.
   Implemented in surface_roughness.py (IDEAL_FEED_MARK, IDEAL_SCALLOP).

2. TARGET_B: STAGE_RQ
   Roughness at one wear/life interruption stage.
   Aggregates raw spatial readings into stage-level Rq.
   Captures wear state, cutting time, pass count, and cutting conditions.

3. TARGET_C: LIFECYCLE_AGGREGATED_RQ
   Aggregate of valid stage-level Rq values across wear progression to EOL.
   Represents the tool-life Rq evolution from initial condition to end-of-life.

Deterministic aggregation only. No empirical coefficients. No predictive fitting.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

# Fallback imports (as in surface_roughness.py)
try:
    from backend.domain.exceptions import DomainError
    from backend.domain.units import Quantity, Unit
except ImportError:

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

        def is_positive(self):
            return self.value > Decimal(0)

    class DomainError(Exception):
        pass


class RoughnessTargetType(Enum):
    """Classification of roughness response variables."""

    INSTANTANEOUS_GEOMETRIC_RQ = "instantaneous_geometric_rq"
    STAGE_RQ = "stage_rq"
    LIFECYCLE_AGGREGATED_RQ = "lifecycle_aggregated_rq"


class RoughnessLifecycleError(DomainError):
    """Roughness lifecycle calculation and validation error."""

    pass


class StageValidity(Enum):
    """Validity classification for stage observations."""

    VALID = "valid"
    INVALID_REASON_PROVIDED = "invalid_reason_provided"
    EXCLUDED_BY_FILTER = "excluded_by_filter"


@dataclass(frozen=True, slots=True)
class RawSpatialReading:
    """Single spatial roughness reading from one location on machined surface.

    Attributes:
        location: Spatial designation (e.g., "beginning", "middle", "end")
        Rq_value: Root-mean-square roughness measurement [mm]
        Ra_value: Arithmetic mean roughness measurement [mm, optional]
        measurement_unit: Unit of measurement (mm or µm)
        provenance: Source/method (e.g., "Mitutoyo SJ-210, ABNT NBR ISO 4287")
    """

    location: str
    Rq_value: Quantity
    Ra_value: Quantity | None = None
    measurement_unit: str = "mm"
    provenance: str = ""

    def __post_init__(self):
        # Validate Rq_value
        if self.Rq_value.unit not in (Unit.MM, "mm", "um", "µm"):
            raise RoughnessLifecycleError(
                f"Rq_value unit must be mm or µm, got {self.Rq_value.unit}"
            )
        if not self.Rq_value.is_positive():
            raise RoughnessLifecycleError(f"Rq_value must be positive, got {self.Rq_value}")

        # Validate Ra_value if present
        if self.Ra_value is not None:
            if self.Ra_value.unit not in (Unit.MM, "mm", "um", "µm"):
                raise RoughnessLifecycleError(
                    f"Ra_value unit must be mm or µm, got {self.Ra_value.unit}"
                )
            if not self.Ra_value.is_positive():
                raise RoughnessLifecycleError(f"Ra_value must be positive, got {self.Ra_value}")


@dataclass(frozen=True, slots=True)
class StageObservation:
    """Roughness observation at one wear/life interruption stage.

    Captures all readings and metadata for a single stage (e.g., beginning of tool life,
    middle of tool life, end of tool life) at one cutting condition.

    Attributes:
        stage_id: Unique stage identifier (e.g., "stage_0", "stage_1", "stage_2")
        tool_condition: Tool wear/condition classification
            (e.g., "new", "0.10mm_VB", "0.30mm_VB_EOL")
        wear_value: Absolute wear measurement (e.g., flank wear VB in mm)
        wear_unit: Unit of wear measurement
        cutting_time: Cumulative cutting time to this stage [min]
        cumulative_mrv: Cumulative material removal volume [mm³]
        pass_count: Number of cutting passes performed
        Vc: Cutting speed [m/min]
        fz: Feed per tooth [mm/tooth]
        ap: Axial depth [mm]
        ae: Radial width [mm]
        coating_system: Tool coating designation
        raw_readings: List of spatial readings at this stage
        stage_rq: Aggregated Rq for this stage (mean of valid spatial readings)
        stage_ra: Aggregated Ra for this stage (mean of valid spatial readings, if available)
        validity: Validity classification
        invalid_reason: Reason if stage is marked invalid
        measurement_date: When measurements were taken (ISO 8601, optional)
        provenance: Source/experimental batch reference
    """

    stage_id: str
    tool_condition: str
    wear_value: Quantity
    cutting_time: Quantity
    cumulative_mrv: Quantity
    pass_count: int
    Vc: Quantity
    fz: Quantity
    ap: Quantity
    ae: Quantity
    coating_system: str
    raw_readings: list[RawSpatialReading]
    stage_rq: Quantity  # Aggregated Rq [mm]
    stage_ra: Quantity | None = None  # Aggregated Ra [mm], optional
    validity: StageValidity = StageValidity.VALID
    invalid_reason: str = ""
    measurement_date: str = ""
    provenance: str = ""

    def __post_init__(self):
        # Validate raw_readings is not empty
        if not self.raw_readings:
            raise RoughnessLifecycleError(f"Stage {self.stage_id}: raw_readings must not be empty")

        # Validate stage_rq and stage_ra
        if self.stage_rq.unit not in (Unit.MM, Unit.MM):
            raise RoughnessLifecycleError(f"stage_rq must have unit mm, got {self.stage_rq.unit}")
        if not self.stage_rq.is_positive():
            raise RoughnessLifecycleError(f"stage_rq must be positive, got {self.stage_rq}")

        if self.stage_ra is not None:
            if self.stage_ra.unit not in (Unit.MM, Unit.MM):
                raise RoughnessLifecycleError(
                    f"stage_ra must have unit mm, got {self.stage_ra.unit}"
                )
            if not self.stage_ra.is_positive():
                raise RoughnessLifecycleError(f"stage_ra must be positive, got {self.stage_ra}")

        # Validate wear, time, MRV
        if self.wear_value.value < Decimal(0):
            raise RoughnessLifecycleError(f"wear_value must be >= 0, got {self.wear_value}")
        if self.cutting_time.value < Decimal(0):
            raise RoughnessLifecycleError(f"cutting_time must be >= 0, got {self.cutting_time}")
        if self.cumulative_mrv.value < Decimal(0):
            raise RoughnessLifecycleError(f"cumulative_mrv must be >= 0, got {self.cumulative_mrv}")
        if self.pass_count < 0:
            raise RoughnessLifecycleError(f"pass_count must be >= 0, got {self.pass_count}")


@dataclass(frozen=True, slots=True)
class LifecycleRoughnessObservation:
    """Complete lifecycle roughness observation for one replicate.

    Aggregates all stage observations from tool birth to end-of-life for
    one experimental run.

    Attributes:
        replicate_id: Unique replicate identifier
        tool_condition_initial: Tool designation at start
        coating_system: Coating designation
        cutting_combination: Cutting parameters designation (e.g., "Vc_125_fz_0.10")
        stages: List of StageObservation objects (ordered chronologically)
        lifecycle_rq: Final aggregated Rq across all valid stages
        lifecycle_ra: Final aggregated Ra across all valid stages (if available)
        eol_criterion: End-of-life criterion (e.g., "VB_max=0.30mm")
        eol_cutting_time: Cutting time at EOL
        total_mrv: Total material removal volume over tool life
        n_stages: Number of valid stages in lifecycle
        provenance: Experimental batch/source reference
    """

    replicate_id: str
    tool_condition_initial: str
    coating_system: str
    cutting_combination: str
    stages: list[StageObservation]
    lifecycle_rq: Quantity  # Aggregated Rq [mm]
    lifecycle_ra: Quantity | None = None  # Aggregated Ra [mm], optional
    eol_criterion: str = ""
    eol_cutting_time: Quantity | None = None
    total_mrv: Quantity | None = None
    n_stages: int = 0
    provenance: str = ""

    def __post_init__(self):
        # Validate stages is not empty
        if not self.stages:
            raise RoughnessLifecycleError(
                f"Replicate {self.replicate_id}: stages must not be empty"
            )

        # Validate lifecycle_rq
        if self.lifecycle_rq.unit not in (Unit.MM, Unit.MM):
            raise RoughnessLifecycleError(
                f"lifecycle_rq must have unit mm, got {self.lifecycle_rq.unit}"
            )
        if not self.lifecycle_rq.is_positive():
            raise RoughnessLifecycleError(f"lifecycle_rq must be positive, got {self.lifecycle_rq}")

        if self.lifecycle_ra is not None:
            if self.lifecycle_ra.unit not in (Unit.MM, Unit.MM):
                raise RoughnessLifecycleError(
                    f"lifecycle_ra must have unit mm, got {self.lifecycle_ra.unit}"
                )
            if not self.lifecycle_ra.is_positive():
                raise RoughnessLifecycleError(
                    f"lifecycle_ra must be positive, got {self.lifecycle_ra}"
                )

        # Validate n_stages
        if self.n_stages < 0:
            raise RoughnessLifecycleError(f"n_stages must be >= 0, got {self.n_stages}")


# ================================================================
# DETERMINISTIC AGGREGATION FUNCTIONS
# ================================================================


def aggregate_spatial_readings_to_stage_rq(
    readings: list[RawSpatialReading],
) -> tuple[Quantity, Quantity | None]:
    """Deterministically aggregate raw spatial readings to stage-level Rq/Ra.

    Computes mean Rq across valid spatial readings at one stage.
    If Ra values are present in all readings, also computes mean Ra.

    Args:
        readings: List of RawSpatialReading objects

    Returns:
        (stage_rq, stage_ra) where stage_rq is always computed, stage_ra is optional

    Raises:
        RoughnessLifecycleError: If readings is empty or contains non-finite values
    """
    if not readings:
        raise RoughnessLifecycleError("readings list must not be empty")

    # Convert all Rq values to Decimal [mm], normalizing units
    rq_values = []
    ra_values = []
    all_have_ra = True

    for reading in readings:
        # Normalize Rq to mm
        rq_mm = reading.Rq_value.value
        if reading.Rq_value.unit in ("um", "µm"):
            rq_mm = reading.Rq_value.value / Decimal(1000)
        rq_values.append(rq_mm)

        # Normalize Ra if present
        if reading.Ra_value is not None:
            ra_mm = reading.Ra_value.value
            if reading.Ra_value.unit in ("um", "µm"):
                ra_mm = reading.Ra_value.value / Decimal(1000)
            ra_values.append(ra_mm)
        else:
            all_have_ra = False

    # Compute mean Rq
    stage_rq_mm = sum(rq_values) / Decimal(len(rq_values))
    stage_rq = Quantity(value=stage_rq_mm, unit=Unit.MM)

    # Compute mean Ra if all readings have Ra
    stage_ra = None
    if all_have_ra and ra_values:
        stage_ra_mm = sum(ra_values) / Decimal(len(ra_values))
        stage_ra = Quantity(value=stage_ra_mm, unit=Unit.MM)

    return (stage_rq, stage_ra)


def aggregate_stages_to_lifecycle_rq(
    stages: list[StageObservation],
    exclude_invalid: bool = True,
) -> tuple[Quantity, Quantity | None, int]:
    """Deterministically aggregate stage-level Rq values to lifecycle Rq.

    Computes mean Rq across valid stages in wear progression to EOL.
    If all valid stages have Ra, also computes mean Ra.

    Args:
        stages: List of StageObservation objects (ordered chronologically)
        exclude_invalid: If True, exclude stages marked as invalid

    Returns:
        (lifecycle_rq, lifecycle_ra, n_valid_stages)

    Raises:
        RoughnessLifecycleError: If no valid stages remain
    """
    if not stages:
        raise RoughnessLifecycleError("stages list must not be empty")

    # Filter to valid stages if requested
    valid_stages = stages
    if exclude_invalid:
        valid_stages = [s for s in stages if s.validity == StageValidity.VALID]

    if not valid_stages:
        raise RoughnessLifecycleError("No valid stages remaining after filtering invalid stages")

    # Normalize all stage_rq to mm and aggregate
    rq_values = []
    ra_values = []
    all_have_ra = True

    for stage in valid_stages:
        # Normalize to mm
        rq_mm = stage.stage_rq.value
        if stage.stage_rq.unit in ("um", "µm"):
            rq_mm = stage.stage_rq.value / Decimal(1000)
        rq_values.append(rq_mm)

        # Normalize Ra if present
        if stage.stage_ra is not None:
            ra_mm = stage.stage_ra.value
            if stage.stage_ra.unit in ("um", "µm"):
                ra_mm = stage.stage_ra.value / Decimal(1000)
            ra_values.append(ra_mm)
        else:
            all_have_ra = False

    # Compute mean lifecycle Rq
    lifecycle_rq_mm = sum(rq_values) / Decimal(len(rq_values))
    lifecycle_rq = Quantity(value=lifecycle_rq_mm, unit=Unit.MM)

    # Compute mean lifecycle Ra if all valid stages have Ra
    lifecycle_ra = None
    if all_have_ra and ra_values:
        lifecycle_ra_mm = sum(ra_values) / Decimal(len(ra_values))
        lifecycle_ra = Quantity(value=lifecycle_ra_mm, unit=Unit.MM)

    return (lifecycle_rq, lifecycle_ra, len(valid_stages))


# ================================================================
# ARCHITECTURE DECLARATIONS
# ================================================================

ROUGHNESS_TARGET_CONTRACTS = {
    "TARGET_A": {
        "name": "INSTANTANEOUS_GEOMETRIC_RQ",
        "description": "Single-condition theoretical surface geometry prediction",
        "models": ["IDEAL_FEED_MARK", "IDEAL_SCALLOP"],
        "inputs": ["fz (or ae)", "effective_radius"],
        "outputs": ["Ra", "Rq"],
        "wear_dependent": False,
        "life_aggregation": False,
        "implementation": "surface_roughness.py (PHYSICS-01C)",
    },
    "TARGET_B": {
        "name": "STAGE_RQ",
        "description": "Roughness at one wear/life interruption stage",
        "inputs": [
            "wear_value / VB",
            "cutting_time",
            "cumulative_MRV",
            "pass_count",
            "Vc / fz / ap / ae",
            "raw_spatial_readings [location, Rq]",
        ],
        "outputs": ["stage_rq", "stage_ra"],
        "aggregation": "mean of valid spatial readings",
        "wear_dependent": True,
        "life_aggregation": False,
        "implementation": "roughness_lifecycle.py (PHYSICS-01F)",
    },
    "TARGET_C": {
        "name": "LIFECYCLE_AGGREGATED_RQ",
        "description": "Aggregate of valid stage-level Rq values across wear progression to EOL",
        "inputs": ["stages [stage_id, stage_rq, ..., validity]"],
        "outputs": ["lifecycle_rq", "lifecycle_ra"],
        "aggregation": "mean of valid stage_rq values (excluding invalid stages)",
        "wear_dependent": True,
        "life_aggregation": True,
        "implementation": "roughness_lifecycle.py (PHYSICS-01F)",
    },
}

AGGREGATION_HIERARCHY = """
Raw spatial Rq readings (at beginning/middle/end of machined surface)
    ↓ (aggregate mean)
Stage-level Rq (at one wear/life interruption)
    ↓ (aggregate mean)
Lifecycle-aggregated Rq (mean across all valid stages to EOL)
"""

VP100_LIFECYCLE_DEFINITION = {
    "eol_criterion": "VB_max = 0.30 mm (flank wear)",
    "stage_spatial_aggregation": True,
    "stage_locations": ["beginning", "middle", "end"],
    "lifecycle_aggregation": True,
    "valid_stages_for_vp100": "stages with wear progression from new to EOL",
    "rq_target_type": "LIFECYCLE_AGGREGATED_RQ",
}
