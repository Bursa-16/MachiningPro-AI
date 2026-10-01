"""EngineeringRule wrappers for deterministic threading calculations (Stage 3E).

Rule ID range: R-2401 onward.

Rule families:

  R-2401..R-2405  Threading calculation rules (deterministic wrappers)
  R-2410..R-2413  Threading validation rules

All validation rules are PHYSICAL_CONSTRAINT.
Stage 3E introduces ZERO arbitrary policy thresholds.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from backend.core.rules.base import EngineeringRule
from backend.domain.result import EngineeringResult, failure, success, warning
from backend.domain.units import Quantity, Unit
from backend.machining import threading
from backend.machining.exceptions import MachiningMathError

__all__ = [
    # calculation rules
    "LeadFromPitchRule",
    "PitchFromLeadRule",
    "ThreadFeedRateRule",
    "ThreadingMachiningTimeRule",
    "ThreadingRevolutionsRule",
    # validation rules
    "ThreadFeedConsistencyRule",
    "EffectiveTravelNotLessThanThreadLengthRule",
    "SingleStartLeadEqualsPitchRule",
    "ZeroThreadLengthRule",
    # collection
    "foundational_threading_rules",
]


def _fer(rule_id: str, version: str, exc: MachiningMathError) -> EngineeringResult:
    return failure(
        result_id=f"{rule_id}.result",
        rule_id=rule_id,
        rule_version=version,
        violations=(str(exc),),
    )


# ---------------------------------------------------------------------------
# Calculation rules
# ---------------------------------------------------------------------------

class LeadFromPitchRule(EngineeringRule):
    """R-2401: lead = pitch × starts."""
    rule_id = "R-2401"
    rule_version = "1.0.0"
    description = "Compute thread lead from pitch and number of starts."
    domain = "threading.geometry"
    required_inputs = ("pitch",)
    source_reference = "machining-ai Stage 3E threading geometry"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = threading.lead_from_pitch(
                inputs["pitch"],
                inputs.get("number_of_starts", 1),
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"lead": result},
            summary=f"lead {result}",
        )


class PitchFromLeadRule(EngineeringRule):
    """R-2402: pitch = lead / starts."""
    rule_id = "R-2402"
    rule_version = "1.0.0"
    description = "Compute thread pitch from lead and number of starts."
    domain = "threading.geometry"
    required_inputs = ("lead",)
    source_reference = "machining-ai Stage 3E threading geometry"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = threading.pitch_from_lead(
                inputs["lead"],
                inputs.get("number_of_starts", 1),
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"pitch": result},
            summary=f"pitch {result}",
        )


class ThreadFeedRateRule(EngineeringRule):
    """R-2403: Vf = n × lead."""
    rule_id = "R-2403"
    rule_version = "1.0.0"
    description = "Compute synchronized threading feed rate."
    domain = "threading.feed"
    required_inputs = ("spindle_speed", "lead")
    source_reference = "machining-ai Stage 3E threading feed (composed from Stage 3A)"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = threading.thread_feed_rate(
                inputs["spindle_speed"], inputs["lead"]
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"feed_rate": result},
            summary=f"feed_rate {result}",
        )


class ThreadingMachiningTimeRule(EngineeringRule):
    """R-2404: t = L_eff / (n × lead)."""
    rule_id = "R-2404"
    rule_version = "1.0.0"
    description = "Compute threading machining time."
    domain = "threading.time"
    required_inputs = ("spindle_speed", "lead", "thread_length")
    source_reference = "machining-ai Stage 3E threading time (composed from Stage 3A)"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = threading.threading_machining_time(
                inputs["spindle_speed"],
                inputs["lead"],
                inputs["thread_length"],
                inputs.get("approach_allowance"),
                inputs.get("overtravel_allowance"),
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"time": result},
            summary=f"time {result}",
        )


class ThreadingRevolutionsRule(EngineeringRule):
    """R-2405: revolutions = effective_travel / lead."""
    rule_id = "R-2405"
    rule_version = "1.0.0"
    description = "Compute revolutions required for threading."
    domain = "threading.geometry"
    required_inputs = ("effective_travel", "lead")
    source_reference = "machining-ai Stage 3E threading revolutions"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        try:
            result = threading.threading_revolutions(
                inputs["effective_travel"], inputs["lead"]
            )
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            outputs={"revolutions": result},
            summary=f"revolutions {result}",
        )


# ---------------------------------------------------------------------------
# Validation rules (all PHYSICAL_CONSTRAINT — zero policy thresholds)
# ---------------------------------------------------------------------------

class ThreadFeedConsistencyRule(EngineeringRule):
    """R-2410: verify Vf = n × lead consistency.

    Classification: PHYSICAL_CONSTRAINT.
    """
    rule_id = "R-2410"
    rule_version = "1.0.0"
    description = "Verify threading feed-rate / spindle-speed / lead consistency."
    domain = "threading.feed.validation"
    required_inputs = ("feed_rate", "spindle_speed", "lead")
    source_reference = "threading kinematics: Vf = n × lead"

    _TOLERANCE = Decimal("0.001")

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        vf: Quantity = inputs["feed_rate"]
        n: Quantity = inputs["spindle_speed"]
        lead: Quantity = inputs["lead"]

        try:
            expected_vf = threading.thread_feed_rate(n, lead)
        except MachiningMathError as exc:
            return _fer(self.rule_id, self.rule_version, exc)

        if expected_vf.value == Decimal("0") and vf.value == Decimal("0"):
            return success(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                summary="all zero — consistent",
            )
        if expected_vf.value == Decimal("0"):
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=(
                    f"expected Vf = 0 from n×lead but got {vf.value} mm/min",
                ),
            )
        relative_error = abs(vf.value - expected_vf.value) / expected_vf.value
        if relative_error > self._TOLERANCE:
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=(
                    f"feed rate inconsistency: given Vf = {vf.value} mm/min, "
                    f"computed n×lead = {expected_vf.value} mm/min, "
                    f"relative error = {relative_error}",
                ),
            )
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            summary=f"Vf consistent within {self._TOLERANCE}",
        )


class EffectiveTravelNotLessThanThreadLengthRule(EngineeringRule):
    """R-2411: effective travel >= thread length.

    Classification: PHYSICAL_CONSTRAINT.
    """
    rule_id = "R-2411"
    rule_version = "1.0.0"
    description = "Verify effective threading travel is not less than thread length."
    domain = "threading.geometry.validation"
    required_inputs = ("thread_length", "effective_travel")
    source_reference = "threading geometry: travel >= thread_length"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        length: Quantity = inputs["thread_length"]
        travel: Quantity = inputs["effective_travel"]
        if length.unit is not Unit.MM:
            return _fer(
                self.rule_id, self.rule_version,
                MachiningMathError(
                    f"thread_length must be in mm, got {length.unit.value}"
                ),
            )
        if travel.unit is not Unit.MM:
            return _fer(
                self.rule_id, self.rule_version,
                MachiningMathError(
                    f"effective_travel must be in mm, got {travel.unit.value}"
                ),
            )
        if travel.value < length.value:
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=(
                    f"effective_travel ({travel.value} mm) < thread_length "
                    f"({length.value} mm)",
                ),
            )
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            summary="effective_travel >= thread_length",
        )


class SingleStartLeadEqualsPitchRule(EngineeringRule):
    """R-2412: for single-start threads, lead must equal pitch.

    Classification: PHYSICAL_CONSTRAINT.
    """
    rule_id = "R-2412"
    rule_version = "1.0.0"
    description = "Verify lead equals pitch for single-start threads."
    domain = "threading.geometry.validation"
    required_inputs = ("pitch", "lead", "number_of_starts")
    source_reference = "thread geometry: single-start → lead = pitch"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        pitch: Quantity = inputs["pitch"]
        lead: Quantity = inputs["lead"]
        starts: int = inputs["number_of_starts"]

        if not isinstance(starts, int) or isinstance(starts, bool) or starts <= 0:
            return _fer(
                self.rule_id, self.rule_version,
                MachiningMathError(
                    f"number_of_starts must be a positive integer, got {starts}"
                ),
            )
        if starts != 1:
            return success(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                summary=f"multi-start ({starts}); rule applies to single-start only",
            )
        if pitch.unit is not Unit.MM_REV or lead.unit is not Unit.MM_REV:
            return _fer(
                self.rule_id, self.rule_version,
                MachiningMathError("pitch and lead must both be in mm/rev"),
            )
        if lead.value != pitch.value:
            return failure(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                violations=(
                    f"single-start thread: lead ({lead.value}) != pitch "
                    f"({pitch.value})",
                ),
            )
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            summary="single-start: lead == pitch",
        )


class ZeroThreadLengthRule(EngineeringRule):
    """R-2413: warn when thread length is zero.

    Classification: PHYSICAL_CONSTRAINT.
    """
    rule_id = "R-2413"
    rule_version = "1.0.0"
    description = "Warn when thread length is zero."
    domain = "threading.geometry.validation"
    required_inputs = ("thread_length",)
    source_reference = "threading geometry: zero length produces no thread"

    def _evaluate(self, inputs: Mapping[str, Any]) -> EngineeringResult:
        length: Quantity = inputs["thread_length"]
        if length.unit is not Unit.MM:
            return _fer(
                self.rule_id, self.rule_version,
                MachiningMathError(
                    f"thread_length must be in mm, got {length.unit.value}"
                ),
            )
        if length.value == Decimal("0"):
            return warning(
                result_id=f"{self.rule_id}.result",
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                warnings=("thread_length is zero; no thread will be produced",),
                summary="zero thread length warning",
            )
        return success(
            result_id=f"{self.rule_id}.result",
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            summary="thread_length > 0",
        )


def foundational_threading_rules() -> tuple[EngineeringRule, ...]:
    """Instantiate the Stage 3E threading rules for registration."""
    return (
        LeadFromPitchRule(),
        PitchFromLeadRule(),
        ThreadFeedRateRule(),
        ThreadingMachiningTimeRule(),
        ThreadingRevolutionsRule(),
        ThreadFeedConsistencyRule(),
        EffectiveTravelNotLessThanThreadLengthRule(),
        SingleStartLeadEqualsPitchRule(),
        ZeroThreadLengthRule(),
    )
