"""DFM / process-feasibility foundation for MachineryPro AI (Stage 3I).

Provides deterministic feasibility checks that answer:

    "Is this feature geometrically and physically compatible with this
     process condition, given this tool and machine?"

Stage 3I establishes the feasibility data-flow:

* Geometry compatibility (tool fits feature)
* Process–feature type compatibility
* Depth/diameter ratio calculation (no hard-coded thresholds)
* Machine-capability composition (reuses Stage 3H)
* Aggregate feasibility across multiple checks

No automatic tool selection, no machine recommendation, no AI.

Exports
-------
:func:`check_hole_tool_diameter`          — R-2701
:func:`check_corner_radius_tool`          — R-2702
:func:`check_slot_width_tool`             — R-2703
:func:`check_pocket_access`               — R-2704
:func:`check_process_feature_compatibility` — R-2705
:func:`check_depth_diameter_ratio`        — R-2706
:func:`compose_machine_result`            — R-2710
:func:`aggregate_feasibility`             — R-2712
:func:`foundational_dfm_rules`            — instantiate all Stage 3I rules
"""

from backend.dfm.rules import (
    AggregateFeasibilityRule,
    CornerRadiusToolRule,
    DepthDiameterRatioRule,
    HoleToolDiameterRule,
    MachineCapabilityCompositionRule,
    PocketAccessRule,
    ProcessFeatureCompatRule,
    SlotWidthToolRule,
    foundational_dfm_rules,
)
from backend.dfm.validation import (
    aggregate_feasibility,
    check_corner_radius_tool,
    check_depth_diameter_ratio,
    check_hole_tool_diameter,
    check_pocket_access,
    check_process_feature_compatibility,
    check_slot_width_tool,
    compose_machine_result,
)

__all__ = [
    "AggregateFeasibilityRule",
    "CornerRadiusToolRule",
    "DepthDiameterRatioRule",
    "HoleToolDiameterRule",
    "MachineCapabilityCompositionRule",
    "PocketAccessRule",
    "ProcessFeatureCompatRule",
    "SlotWidthToolRule",
    "aggregate_feasibility",
    "check_corner_radius_tool",
    "check_depth_diameter_ratio",
    "check_hole_tool_diameter",
    "check_pocket_access",
    "check_process_feature_compatibility",
    "check_slot_width_tool",
    "compose_machine_result",
    "foundational_dfm_rules",
]
