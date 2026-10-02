"""Machine capability model: spindle power/torque/speed, envelope, accuracy.

Stage 3H establishes the deterministic machine-capability validation layer:
a catalog of Machine instances and pure validation functions that check
requested engineering values against explicit machine limits.

No production machine data is included.  All machine limits come from
explicit, provenance-carrying Machine entities supplied by the caller.

Exports
-------
:class:`MachineCatalog`                — register and look up machines.
:func:`check_spindle_speed`            — R-2601
:func:`check_feed_rate`                — R-2602
:func:`check_power`                    — R-2603
:func:`check_torque`                   — R-2604
:func:`check_work_envelope_dimension`  — R-2605
:func:`foundational_machine_rules`     — instantiate all Stage 3H rules.
"""

from backend.machines.catalog import MachineCatalog
from backend.machines.rules import (
    FeedRateCapabilityRule,
    PowerCapabilityRule,
    SpindleSpeedCapabilityRule,
    TorqueCapabilityRule,
    WorkEnvelopeCapabilityRule,
    foundational_machine_rules,
)
from backend.machines.validation import (
    check_feed_rate,
    check_power,
    check_spindle_speed,
    check_torque,
    check_work_envelope_dimension,
)

__all__ = [
    "FeedRateCapabilityRule",
    "MachineCatalog",
    "PowerCapabilityRule",
    "SpindleSpeedCapabilityRule",
    "TorqueCapabilityRule",
    "WorkEnvelopeCapabilityRule",
    "check_feed_rate",
    "check_power",
    "check_spindle_speed",
    "check_torque",
    "check_work_envelope_dimension",
    "foundational_machine_rules",
]
