"""Machining-math-specific exceptions.

Stage 3A uses :class:`MachiningMathError` for formula-level contract
violations (wrong unit, zero denominator, physically impossible negative
given the formula, invalid tooth count). It derives from
:class:`~backend.domain.exceptions.ValidationError` so the existing fail-closed
policy is preserved.
"""

from __future__ import annotations

from backend.domain.exceptions import ValidationError

__all__ = ["MachiningMathError"]


class MachiningMathError(ValidationError):
    """Raised when a deterministic machining formula receives invalid input.

    Examples: wrong unit for a formula argument, a zero denominator where
    division is required, a negative diameter, a non-positive-non-integer
    tooth count. The existing :class:`ValidationError` /
    :class:`DomainError` hierarchy is reused; this subclass only identifies
    the machining-math layer as the source.
    """
