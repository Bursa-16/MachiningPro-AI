"""Domain exceptions for Machinery AI.

Fail-closed policy: invalid engineering data never silently degrades into a
default value. Everything that violates a domain invariant raises an explicit
exception derived from :class:`DomainError`.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all Machinery AI domain errors."""


class ValidationError(DomainError):
    """Raised when engineering input violates a domain invariant."""


class UnitError(ValidationError):
    """Quantity/units-layer error (base).

    Covers invalid quantity construction: a non-numeric or non-finite value,
    or an unknown unit symbol. The canonical descriptive subclass for the
    unknown-symbol case is :class:`UnknownUnitError`; both names are exported
    so the historical ``UnitError`` import path keeps working.
    """


class UnknownUnitError(UnitError):
    """Raised when a unit symbol is not part of the canonical unit model."""


class RuleError(DomainError):
    """Base class for engineering-rule infrastructure errors."""


class DuplicateRuleError(RuleError):
    """Raised when registering a rule whose rule_id already exists."""


class RuleNotFoundError(RuleError):
    """Raised when looking up a rule_id that is not registered."""
