"""Empirical-data-layer exceptions for MachineryPro AI.

These exceptions are distinct from :class:`~backend.domain.exceptions.ValidationError`
(which covers *input* validation) and
:class:`~backend.machining.exceptions.MachiningMathError` (which covers
formula-level contract violations).

:class:`EmpiricalDataError` signals a *data-availability* failure: the
empirical engineering catalog does not contain what was requested, or what
it contains cannot be used in the requested context (missing provenance,
unsupported applicability scope, etc.).

Fail-closed policy: an :class:`EmpiricalDataError` must never be silently
swallowed or converted into a default value by downstream code.
"""

from __future__ import annotations

from backend.domain.exceptions import DomainError

__all__ = ["EmpiricalDataError"]


class EmpiricalDataError(DomainError):
    """Raised when an empirical engineering data lookup or validation fails.

    Covers:

    * exact-ID lookup that finds no record
    * a record that lacks acceptable provenance for authoritative use
    * a record whose applicability scope does not match the query context
    * a duplicate-ID registration attempt

    This is a *data-availability* failure, not a mathematical or input
    error — keep it separate from :class:`~backend.domain.exceptions.ValidationError`.
    """
