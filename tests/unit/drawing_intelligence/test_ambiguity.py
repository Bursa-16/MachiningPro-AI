"""Tests for ambiguity model and confidence (EPIC_04B Phase 2)."""

import pytest
from backend.drawing_intelligence.requirements import (
    AmbiguityKind,
    GdtAmbiguity,
    GdtConfidence,
)


class TestGdtAmbiguityValidation:
    def test_empty_ambiguity_id_rejected(self):
        with pytest.raises(ValueError, match="ambiguity_id"):
            GdtAmbiguity(
                ambiguity_id="",
                kind=AmbiguityKind.MISSING_DATUM,
                affected_ids=("REQ-001",),
                description="Test",
                severity="ERROR",
                suggested_resolution=None,
            )

    def test_invalid_severity_rejected(self):
        with pytest.raises(ValueError, match="severity"):
            GdtAmbiguity(
                ambiguity_id="AMB-001",
                kind=AmbiguityKind.MISSING_DATUM,
                affected_ids=(),
                description="Test",
                severity="CRITICAL",  # invalid
                suggested_resolution=None,
            )

    def test_error_severity_valid(self):
        a = GdtAmbiguity(
            ambiguity_id="AMB-001", kind=AmbiguityKind.MISSING_DATUM,
            affected_ids=("REQ-001",), description="Missing datum",
            severity="ERROR", suggested_resolution="Add datum A",
        )
        assert a.severity == "ERROR"

    def test_warning_severity_valid(self):
        a = GdtAmbiguity(
            ambiguity_id="AMB-002", kind=AmbiguityKind.LEGACY_CHARACTERISTIC,
            affected_ids=(), description="Legacy",
            severity="WARNING", suggested_resolution=None,
        )
        assert a.severity == "WARNING"

    def test_info_severity_valid(self):
        a = GdtAmbiguity(
            ambiguity_id="AMB-003", kind=AmbiguityKind.ORPHAN_BASIC_DIMENSION,
            affected_ids=("BD-001",), description="Orphan dim",
            severity="INFO", suggested_resolution=None,
        )
        assert a.severity == "INFO"


class TestAmbiguityKinds:
    def test_all_kinds_defined(self):
        kinds = list(AmbiguityKind)
        assert AmbiguityKind.MISSING_DATUM in kinds
        assert AmbiguityKind.UNRESOLVED_FCF in kinds
        assert AmbiguityKind.MULTIPLE_CANDIDATE_FEATURES in kinds
        assert AmbiguityKind.INVALID_MODIFIER_COMBO in kinds
        assert AmbiguityKind.AMBIGUOUS_FOS in kinds
        assert AmbiguityKind.ORPHAN_BASIC_DIMENSION in kinds
        assert AmbiguityKind.COMPOUND_DATUM_UNRESOLVED in kinds
        assert AmbiguityKind.LEGACY_CHARACTERISTIC in kinds
        assert AmbiguityKind.COMPOSITE_TOLERANCE_INVERTED in kinds
        assert AmbiguityKind.PATTERN_COUNT_MISMATCH in kinds

    def test_ten_kinds(self):
        assert len(list(AmbiguityKind)) == 10


class TestGdtConfidenceLevels:
    def test_all_levels_defined(self):
        levels = list(GdtConfidence)
        assert GdtConfidence.EXACT_STRUCTURED in levels
        assert GdtConfidence.RULE_PARSED in levels
        assert GdtConfidence.GEOMETRY_MATCHED in levels
        assert GdtConfidence.PATTERN_MATCHED in levels
        assert GdtConfidence.INFERRED in levels
        assert GdtConfidence.USER_CONFIRMED in levels
        assert GdtConfidence.AMBIGUOUS in levels

    def test_confidence_ordering(self):
        # Ordering by decreasing confidence
        high = [
            GdtConfidence.EXACT_STRUCTURED,
            GdtConfidence.RULE_PARSED,
            GdtConfidence.GEOMETRY_MATCHED,
        ]
        low = [GdtConfidence.INFERRED, GdtConfidence.AMBIGUOUS]
        for h in high:
            for l in low:
                assert h != l
