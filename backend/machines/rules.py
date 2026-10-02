"""EngineeringRule wrappers for machine-capability validation (Stage 3H).

Rule ID range: R-2601 – R-2605.

Each rule wraps a pure function from
:mod:`backend.machines.validation` in the
:class:`~backend.core.rules.base.EngineeringRule` interface so that
machine-capability checks can participate in the rule registry, carry
provenance, and return :class:`~backend.domain.result.EngineeringResult`
envelopes — consistent with the pattern established in Stages 3A–3F.

Inputs
------
Every rule expects the following named inputs in the ``inputs`` mapping:

``machine``
    A registered :class:`~backend.domain.machine.Machine` instance.

``<capability-specific quantity>``
    The value to validate against the machine (e.g. ``requested_rpm``).

Missing inputs always produce ``INSUFFICIENT_DATA`` (fail closed).
Validation errors produce ``FAIL`` results.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.core.rules.base import EngineeringRule
from backend.domain.result import EngineeringResult, failure
from backend.machines import validation as _v
from backend.machining.exceptions import MachiningMathError

__all__ = [
    "SpindleSpeedCapabilityRule",
    "FeedRateCapabilityRule",
    "PowerCapabilityRule",
    "TorqueCapabilityRule",
    "WorkEnvelopeCapabilityRule",
    "foundational_machine_rules",
]

_VERSION = "1.0.0"
_SOURCE = "MachineryPro AI Stage 3H machine capability validation"


def _err(rule_id: str, exc: Exception) -> EngineeringResult:
    return failure(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=_VERSION,
        violations=(str(exc),),
    )


# ---------------------------------------------------------------------------
# R-2601 — Spindle speed
# ---------------------------------------------------------------------------

class SpindleSpeedCapabilityRule(EngineeringRule):
    """R-2601: requested_rpm ∈ [machine.spindle_speed_min, machine.spindle_speed_max]."""

    rule_id = "R-2601"
    rule_version = _VERSION
    description = "Validate requested spindle speed against machine RPM range."
    domain = "machine.capability.spindle_speed"
    required_inputs = ("machine", "requested_rpm")
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            return _v.check_spindle_speed(
                inputs["machine"], inputs["requested_rpm"]
            )
        except (MachiningMathError, Exception) as exc:
            return _err(self.rule_id, exc)


# ---------------------------------------------------------------------------
# R-2602 — Feed rate
# ---------------------------------------------------------------------------

class FeedRateCapabilityRule(EngineeringRule):
    """R-2602: requested_feed_rate <= machine.feed_rate_max.

    Returns INSUFFICIENT_DATA when machine.feed_rate_max is None.
    """

    rule_id = "R-2602"
    rule_version = _VERSION
    description = "Validate requested feed rate against machine feed rate limit."
    domain = "machine.capability.feed_rate"
    required_inputs = ("machine", "requested_feed_rate")
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            return _v.check_feed_rate(
                inputs["machine"], inputs["requested_feed_rate"]
            )
        except Exception as exc:
            return _err(self.rule_id, exc)


# ---------------------------------------------------------------------------
# R-2603 — Power
# ---------------------------------------------------------------------------

class PowerCapabilityRule(EngineeringRule):
    """R-2603: required_power <= machine.spindle_power."""

    rule_id = "R-2603"
    rule_version = _VERSION
    description = "Validate required spindle power against machine power rating."
    domain = "machine.capability.power"
    required_inputs = ("machine", "required_power")
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            return _v.check_power(
                inputs["machine"], inputs["required_power"]
            )
        except Exception as exc:
            return _err(self.rule_id, exc)


# ---------------------------------------------------------------------------
# R-2604 — Torque
# ---------------------------------------------------------------------------

class TorqueCapabilityRule(EngineeringRule):
    """R-2604: required_torque <= machine.spindle_torque.

    Returns INSUFFICIENT_DATA when machine.spindle_torque is None.
    """

    rule_id = "R-2604"
    rule_version = _VERSION
    description = "Validate required torque against machine spindle torque limit."
    domain = "machine.capability.torque"
    required_inputs = ("machine", "required_torque")
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            return _v.check_torque(
                inputs["machine"], inputs["required_torque"]
            )
        except Exception as exc:
            return _err(self.rule_id, exc)


# ---------------------------------------------------------------------------
# R-2605 — Work envelope
# ---------------------------------------------------------------------------

class WorkEnvelopeCapabilityRule(EngineeringRule):
    """R-2605: requested_value <= machine.working_envelope[dimension_key].

    Returns INSUFFICIENT_DATA when the dimension_key is absent from the
    machine's working_envelope.

    Required inputs: machine, dimension_key, requested_value.
    """

    rule_id = "R-2605"
    rule_version = _VERSION
    description = (
        "Validate a requested axis dimension against the machine work envelope."
    )
    domain = "machine.capability.work_envelope"
    required_inputs = ("machine", "dimension_key", "requested_value")
    source_reference = _SOURCE

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            return _v.check_work_envelope_dimension(
                inputs["machine"],
                inputs["dimension_key"],
                inputs["requested_value"],
            )
        except Exception as exc:
            return _err(self.rule_id, exc)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def foundational_machine_rules() -> tuple[EngineeringRule, ...]:
    """Instantiate the Stage 3H machine-capability rules for registration."""
    return (
        SpindleSpeedCapabilityRule(),
        FeedRateCapabilityRule(),
        PowerCapabilityRule(),
        TorqueCapabilityRule(),
        WorkEnvelopeCapabilityRule(),
    )
