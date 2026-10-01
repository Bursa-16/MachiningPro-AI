"""Deterministic machining calculations: turning, milling, drilling, grinding.

Cutting speed/feed/depth-of-cut relations, MRR, machining time and the
rotational power/torque relationship. All formulas are deterministic,
unit-explicit and fail-closed. No empirical machining constants, no
material-specific data, no manufacturer recommendations - only mathematically
derived values from explicit engineering inputs.

Stage 3B adds turning-specific geometry: external turning, boring, facing,
pass count, removed volume and turning MRR.
"""

from backend.machining.exceptions import MachiningMathError
from backend.machining.formulas import (
    cutting_speed_from_spindle_speed,
    feed_per_rev_from_feed_rate,
    feed_per_tooth_from_feed_rate,
    feed_rate_from_rpm_feed_per_rev,
    feed_rate_from_rpm_tooth_feed,
    machining_time_from_distance_feed_rate,
    milling_material_removal_rate,
    power_from_torque_rpm,
    spindle_speed_from_cutting_speed,
    spindle_speed_from_feed_rate_feed_per_rev,
    spindle_speed_from_feed_rate_tooth_feed,
    tooth_count_from_feed_rate,
    torque_from_power_rpm,
)
from backend.machining.rules import (
    CuttingSpeedFromSpindleSpeedRule,
    FeedRateFromRpmFeedPerRevRule,
    FeedRateFromRpmToothFeedRule,
    MachiningTimeRule,
    MillingMaterialRemovalRateRule,
    PowerFromTorqueRule,
    SpindleSpeedFromCuttingSpeedRule,
    TorqueFromPowerRule,
    foundational_machining_rules,
)
from backend.machining.turning import (
    equal_pass_depth,
    facing_removed_volume,
    facing_travel,
    final_diameter_boring,
    final_diameter_external,
    longitudinal_turning_time,
    pass_count,
    radial_stock_boring,
    radial_stock_external,
    removed_volume_boring,
    removed_volume_external,
    turning_mrr_direct,
    turning_mrr_from_volume_time,
)
from backend.machining.turning_rules import (
    BoringFinalDiameterRule,
    BoringRadialStockRule,
    BoringRemovedVolumeRule,
    EqualPassDepthRule,
    ExternalFinalDiameterRule,
    ExternalRadialStockRule,
    ExternalRemovedVolumeRule,
    FacingRemovedVolumeRule,
    FacingTimeRule,
    FacingTravelRule,
    LongitudinalTurningTimeRule,
    PassCountRule,
    TurningDirectMRRRule,
    TurningMRRFromVolumeTimeRule,
    foundational_turning_rules,
)

__all__ = [
    # exceptions
    "MachiningMathError",
    # Stage 3A formulas
    "cutting_speed_from_spindle_speed",
    "feed_per_rev_from_feed_rate",
    "feed_rate_from_rpm_feed_per_rev",
    "feed_rate_from_rpm_tooth_feed",
    "feed_per_tooth_from_feed_rate",
    "machining_time_from_distance_feed_rate",
    "milling_material_removal_rate",
    "power_from_torque_rpm",
    "spindle_speed_from_cutting_speed",
    "spindle_speed_from_feed_rate_feed_per_rev",
    "spindle_speed_from_feed_rate_tooth_feed",
    "tooth_count_from_feed_rate",
    "torque_from_power_rpm",
    # Stage 3B turning
    "equal_pass_depth",
    "facing_removed_volume",
    "facing_travel",
    "final_diameter_boring",
    "final_diameter_external",
    "longitudinal_turning_time",
    "pass_count",
    "radial_stock_boring",
    "radial_stock_external",
    "removed_volume_boring",
    "removed_volume_external",
    "turning_mrr_direct",
    "turning_mrr_from_volume_time",
    # Stage 3A rules
    "CuttingSpeedFromSpindleSpeedRule",
    "FeedRateFromRpmFeedPerRevRule",
    "FeedRateFromRpmToothFeedRule",
    "MachiningTimeRule",
    "MillingMaterialRemovalRateRule",
    "PowerFromTorqueRule",
    "SpindleSpeedFromCuttingSpeedRule",
    "TorqueFromPowerRule",
    "foundational_machining_rules",
    # Stage 3B turning rules
    "BoringFinalDiameterRule",
    "BoringRadialStockRule",
    "BoringRemovedVolumeRule",
    "EqualPassDepthRule",
    "ExternalFinalDiameterRule",
    "ExternalRadialStockRule",
    "ExternalRemovedVolumeRule",
    "FacingRemovedVolumeRule",
    "FacingTimeRule",
    "FacingTravelRule",
    "LongitudinalTurningTimeRule",
    "PassCountRule",
    "TurningDirectMRRRule",
    "TurningMRRFromVolumeTimeRule",
    "foundational_turning_rules",
]
