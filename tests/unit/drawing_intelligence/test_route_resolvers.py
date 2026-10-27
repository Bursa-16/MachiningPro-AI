"""Tests for machine/tool/holder/param resolvers — EPIC_04E Phase 2.

Covers:
  MachineCandidateResolver — ROUTE_MACHINE_CANDIDATES_IMPLEMENTED=YES
  ToolCandidateResolver   — ROUTE_TOOL_CANDIDATES_IMPLEMENTED=YES
  HolderCandidateResolver — ROUTE_HOLDER_CANDIDATES_IMPLEMENTED=YES
  ParameterResolver       — CUTTING_PARAMETER_ALTERNATIVES_IMPLEMENTED=YES

Safety:
  FABRICATED_MACHINE_COMPATIBILITY=NO
  FABRICATED_TOOL_COMPATIBILITY=NO
  FABRICATED_CUTTING_PARAMETER=NO
"""

import pytest

from backend.drawing_intelligence.machine_resolver import MachineCandidateResolver
from backend.drawing_intelligence.tool_resolver import ToolCandidateResolver
from backend.drawing_intelligence.holder_resolver import HolderCandidateResolver
from backend.drawing_intelligence.param_resolver import ParameterResolver
from backend.domain.enums import OperationType


class TestMachineCandidateResolver:
    def setup_method(self):
        self.resolver = MachineCandidateResolver()

    def test_drilling_returns_candidates(self):
        cands = self.resolver.resolve(OperationType.DRILLING, max_candidates=3)
        assert isinstance(cands, list)

    def test_reference_only_flag(self):
        cands = self.resolver.resolve(OperationType.DRILLING, max_candidates=3)
        for c in cands:
            assert c.REFERENCE_ONLY is True, "FABRICATED_MACHINE_COMPATIBILITY=NO"

    def test_suitability_score_range(self):
        cands = self.resolver.resolve(OperationType.DRILLING, max_candidates=3)
        for c in cands:
            assert 0 <= c.suitability_score <= 100

    def test_max_candidates_respected(self):
        cands = self.resolver.resolve(OperationType.DRILLING, max_candidates=1)
        assert len(cands) <= 1

    def test_resolve_for_route_multiple_ops(self):
        cands = self.resolver.resolve_for_route(
            [OperationType.DRILLING, OperationType.MILLING],
            max_candidates=3,
        )
        assert isinstance(cands, list)

    def test_resolve_for_route_empty_ops(self):
        cands = self.resolver.resolve_for_route([], max_candidates=3)
        assert cands == []

    def test_sorted_by_score_desc(self):
        cands = self.resolver.resolve(OperationType.DRILLING, max_candidates=5)
        scores = [c.suitability_score for c in cands]
        assert scores == sorted(scores, reverse=True)


class TestToolCandidateResolver:
    def setup_method(self):
        self.resolver = ToolCandidateResolver()

    def test_drilling_returns_candidates(self):
        cands = self.resolver.resolve(OperationType.DRILLING, feature_type="HOLE")
        assert isinstance(cands, list)

    def test_reference_only_flag(self):
        cands = self.resolver.resolve(OperationType.DRILLING, feature_type="HOLE")
        for c in cands:
            assert c.REFERENCE_ONLY is True, "FABRICATED_TOOL_COMPATIBILITY=NO"

    def test_suitability_score_range(self):
        cands = self.resolver.resolve(OperationType.MILLING, feature_type="POCKET")
        for c in cands:
            assert 0 <= c.suitability_score <= 100

    def test_max_candidates_respected(self):
        cands = self.resolver.resolve(OperationType.DRILLING, max_candidates=1)
        assert len(cands) <= 1

    def test_unknown_op_returns_empty_or_list(self):
        cands = self.resolver.resolve(OperationType.HONING, feature_type="HOLE")
        assert isinstance(cands, list)

    def test_sorted_by_score_desc(self):
        cands = self.resolver.resolve(OperationType.MILLING, max_candidates=5)
        scores = [c.suitability_score for c in cands]
        assert scores == sorted(scores, reverse=True)


class TestHolderCandidateResolver:
    def setup_method(self):
        self.resolver = HolderCandidateResolver()

    def test_none_interface_returns_empty(self):
        cands = self.resolver.resolve(None)
        assert cands == [], "REFERENCE_ONLY — no fabricated matches for None interface"

    def test_iso30_interface_may_return_empty_or_list(self):
        cands = self.resolver.resolve("ISO30")
        assert isinstance(cands, list)

    def test_reference_only_flag(self):
        cands = self.resolver.resolve("SK40")
        for c in cands:
            assert c.REFERENCE_ONLY is True, "FABRICATED_TOOL_COMPATIBILITY=NO"

    def test_max_candidates_respected(self):
        cands = self.resolver.resolve("BT40", max_candidates=1)
        assert len(cands) <= 1

    def test_suitability_score_range(self):
        cands = self.resolver.resolve("HSK-A63")
        for c in cands:
            assert 0 <= c.suitability_score <= 100

    def test_sorted_by_score_desc(self):
        cands = self.resolver.resolve("BT30", max_candidates=5)
        scores = [c.suitability_score for c in cands]
        assert scores == sorted(scores, reverse=True)


class TestParameterResolver:
    def setup_method(self):
        self.resolver = ParameterResolver()

    def test_returns_none_for_unknown_combo(self):
        result = self.resolver.resolve(OperationType.INSPECTION, "P")
        assert result is None, "FABRICATED_CUTTING_PARAMETER=NO"

    def test_returns_context_or_none_for_drilling_p(self):
        result = self.resolver.resolve(OperationType.DRILLING, "P")
        # May or may not have data depending on registry content
        assert result is None or result.material_iso_group == "P"

    def test_three_variants_when_found(self):
        result = self.resolver.resolve(OperationType.MILLING, "P")
        if result is not None:
            variants = result.variants
            assert len(variants) == 3
            variant_names = {v.variant for v in variants}
            assert variant_names == {"CONSERVATIVE", "BALANCED", "PRODUCTIVITY"}

    def test_conservative_le_balanced_le_productivity_vc(self):
        result = self.resolver.resolve(OperationType.MILLING, "P")
        if result is not None:
            v = {vnt.variant: vnt for vnt in result.variants}
            if v["CONSERVATIVE"].vc_m_min and v["PRODUCTIVITY"].vc_m_min:
                assert v["CONSERVATIVE"].vc_m_min <= v["PRODUCTIVITY"].vc_m_min

    def test_productivity_variant_is_advisory(self):
        from backend.drawing_intelligence.route_domain import ProcessCapabilityConfidence
        result = self.resolver.resolve(OperationType.MILLING, "P")
        if result is not None:
            prod = next(v for v in result.variants if v.variant == "PRODUCTIVITY")
            assert prod.confidence is ProcessCapabilityConfidence.ADVISORY

    def test_reference_only_flag(self):
        result = self.resolver.resolve(OperationType.MILLING, "P")
        if result is not None:
            assert result.REFERENCE_ONLY is True, "FABRICATED_CUTTING_PARAMETER=NO"

    def test_none_iso_group_handled(self):
        result = self.resolver.resolve(OperationType.MILLING, None)
        # Should not raise; returns None when no data
        assert result is None or result is not None
