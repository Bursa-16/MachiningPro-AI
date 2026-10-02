"""Rule registry: deterministic, in-memory home of engineering rules.

The registry:

* rejects duplicate ``rule_id`` at registration (fail closed);
* exposes every registered rule;
* supports lookup by ``rule_id`` and fails explicitly (``RuleNotFoundError``)
  for unknown ids;
* remains fully deterministic — no AI calls, no network calls, no I/O.

Rule registration is code-level only at Stage 2. ``config/rules/*.yaml`` is a
future declarative metadata source; nothing here loads or executes it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.core.rules.base import EngineeringRule
from backend.domain.exceptions import (
    DuplicateRuleError,
    RuleNotFoundError,
)

__all__ = ["RuleRegistry"]

Mapper = dict[str, EngineeringRule] | None


@dataclass
class RuleRegistry:
    """In-memory registry of deterministic engineering rules.

    ``rules`` is intentionally private and only mutated through
    :meth:`register` so duplicate-rule rejection cannot be bypassed.
    """

    _rules: Mapper = field(default_factory=dict, init=False)

    def register(self, rule: EngineeringRule) -> EngineeringRule:
        """Register ``rule``; raise :class:`DuplicateRuleError` if its id exists."""
        if not isinstance(rule, EngineeringRule):
            raise TypeError("only EngineeringRule instances can be registered")
        if rule.rule_id in self._rules:
            raise DuplicateRuleError(
                f"rule id {rule.rule_id!r} is already registered"
            )
        self._rules[rule.rule_id] = rule
        return rule

    def get(self, rule_id: str) -> EngineeringRule:
        """Look up a rule by id; fail explicitly when unknown."""
        rule = self._rules.get(rule_id)
        if rule is None:
            raise RuleNotFoundError(f"no rule registered with id {rule_id!r}")
        return rule

    def has(self, rule_id: str) -> bool:
        """True when ``rule_id`` is registered."""
        return rule_id in self._rules

    def ids(self) -> tuple[str, ...]:
        """Registered rule ids in stable registration order."""
        return tuple(self._rules)

    def all(self) -> tuple[EngineeringRule, ...]:
        """All registered rules in stable registration order."""
        return tuple(self._rules.values())

    def __contains__(self, rule_id: str) -> bool:
        return self.has(rule_id)

    def __len__(self) -> int:
        return len(self._rules)

    def __iter__(self):
        return iter(self._rules.values())
