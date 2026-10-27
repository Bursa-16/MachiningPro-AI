"""Tests for FeaturePattern model (EPIC_04B Phase 2)."""

import pytest
from decimal import Decimal

from backend.drawing_intelligence.requirements import (
    FeaturePattern,
    PatternKind,
)


class TestFeaturePatternValidation:
    def test_empty_pattern_id_rejected(self):
        with pytest.raises(ValueError, match="pattern_id"):
            FeaturePattern(
                pattern_id="", kind=PatternKind.CIRCULAR,
                member_feature_ids=("F-001", "F-002"),
                count=2, pattern_fcf_id=None,
            )

    def test_zero_count_rejected(self):
        with pytest.raises(ValueError, match="count"):
            FeaturePattern(
                pattern_id="PAT-001", kind=PatternKind.CIRCULAR,
                member_feature_ids=(),
                count=0, pattern_fcf_id=None,
            )

    def test_valid_circular_pattern(self):
        pat = FeaturePattern(
            pattern_id="PAT-001",
            kind=PatternKind.CIRCULAR,
            member_feature_ids=("F-001", "F-002", "F-003", "F-004"),
            count=4,
            pattern_fcf_id="FCF-001",
            basic_pcd_mm=Decimal("50.0"),
        )
        assert pat.count == 4
        assert pat.kind == PatternKind.CIRCULAR
        assert pat.basic_pcd_mm == Decimal("50.0")

    def test_valid_linear_pattern(self):
        pat = FeaturePattern(
            pattern_id="PAT-002",
            kind=PatternKind.LINEAR,
            member_feature_ids=("F-005", "F-006"),
            count=2,
            pattern_fcf_id=None,
            basic_spacing_mm=Decimal("25.0"),
        )
        assert pat.basic_spacing_mm == Decimal("25.0")

    def test_count_one_valid(self):
        pat = FeaturePattern(
            pattern_id="PAT-003",
            kind=PatternKind.IRREGULAR,
            member_feature_ids=("F-001",),
            count=1,
            pattern_fcf_id=None,
        )
        assert pat.count == 1

    def test_individual_fcf_ids_optional(self):
        pat = FeaturePattern(
            pattern_id="PAT-004",
            kind=PatternKind.RECTANGULAR,
            member_feature_ids=("F-001", "F-002", "F-003", "F-004"),
            count=4,
            pattern_fcf_id="FCF-001",
            individual_fcf_ids=("FCF-002", "FCF-003"),
        )
        assert len(pat.individual_fcf_ids) == 2


class TestPatternKinds:
    def test_all_kinds_defined(self):
        kinds = list(PatternKind)
        assert PatternKind.LINEAR in kinds
        assert PatternKind.CIRCULAR in kinds
        assert PatternKind.RECTANGULAR in kinds
        assert PatternKind.IRREGULAR in kinds
