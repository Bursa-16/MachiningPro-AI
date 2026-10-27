"""Tests for GD&T Semantic Validation Rules (EPIC_04B Phase 2).

VAL-GDT-001 through VAL-GDT-010.
"""

import pytest
from decimal import Decimal

from backend.drawing_intelligence.gdt_validation import (
    validate_fcf,
    validate_composite_fcf,
    VALIDATION_RULE_IDS,
)
from backend.drawing_intelligence.requirements import (
    CompositePositionFCF,
    DatumReference,
    DatumReferenceFrame,
    ExpandedFeatureControlFrame,
    FCFSegment,
    FeatureModifier,
    FeatureOfSize,
    FeatureOfSizeKind,
    GdtCharacteristic,
    GdtModifier,
    SegmentIntent,
)
# GDT_REQUIRES_DATUM is needed by gdt_validation but already imported there; just ensuring GdtModifier usage



def _ref(label):
    return DatumReference(label=label, precedence=1, modifier=GdtModifier.NONE)


def _frame(primary="A", secondary=None, tertiary=None):
    sec = DatumReference(label=secondary, precedence=2, modifier=GdtModifier.NONE) if secondary else None
    ter = DatumReference(label=tertiary, precedence=3, modifier=GdtModifier.NONE) if tertiary else None
    return DatumReferenceFrame(primary=_ref(primary), secondary=sec, tertiary=ter)


def _fcf(char, modifier=GdtModifier.NONE, datum=None, tol="0.1"):
    return ExpandedFeatureControlFrame(
        characteristic=char, tolerance_value=Decimal(tol),
        tolerance_unit="mm", diameter_zone=True,
        modifier=modifier, datum_frame=datum,
    )


def _hole(actual=None):
    return FeatureOfSize(
        fos_id="FOS-001", kind=FeatureOfSizeKind.INTERNAL_CYLINDRICAL,
        nominal_mm=Decimal("25"), upper_limit_mm=Decimal("25.033"),
        lower_limit_mm=Decimal("25.000"),
        actual_size_mm=Decimal(actual) if actual else None,
        source_req_id=None, feature_id=None,
    )


def _segment(idx, tol, intent):
    return FCFSegment(
        segment_index=idx,
        characteristic=GdtCharacteristic.POSITION,
        tolerance_value=Decimal(tol), tolerance_unit="mm",
        diameter_zone=True,
        modifier=FeatureModifier.NONE,
        datum_frame=None,
        intent=intent,
    )


class TestVAL001FormNoDatum:
    def test_flatness_with_datum_is_error(self):
        results = validate_fcf(_fcf(GdtCharacteristic.FLATNESS, datum=_frame()), "REQ-001")
        r001 = next(r for r in results if r.rule_id == "VAL-GDT-001")
        assert r001.passed is False
        assert r001.severity == "ERROR"

    def test_flatness_no_datum_passes(self):
        results = validate_fcf(_fcf(GdtCharacteristic.FLATNESS), "REQ-001")
        r001 = next(r for r in results if r.rule_id == "VAL-GDT-001")
        assert r001.passed is True

    def test_circularity_with_datum_is_error(self):
        results = validate_fcf(_fcf(GdtCharacteristic.CIRCULARITY, datum=_frame()), "REQ-002")
        r001 = next(r for r in results if r.rule_id == "VAL-GDT-001")
        assert r001.passed is False

    def test_cylindricity_with_datum_is_error(self):
        results = validate_fcf(_fcf(GdtCharacteristic.CYLINDRICITY, datum=_frame()), "REQ-003")
        r001 = next(r for r in results if r.rule_id == "VAL-GDT-001")
        assert r001.passed is False

    def test_straightness_with_datum_is_error(self):
        results = validate_fcf(_fcf(GdtCharacteristic.STRAIGHTNESS, datum=_frame()), "REQ-004")
        r001 = next(r for r in results if r.rule_id == "VAL-GDT-001")
        assert r001.passed is False


class TestVAL002DatumRequired:
    def test_position_without_datum_is_warning(self):
        results = validate_fcf(_fcf(GdtCharacteristic.POSITION), "REQ-001")
        r002 = next(r for r in results if r.rule_id == "VAL-GDT-002")
        assert r002.passed is False
        assert r002.severity == "WARNING"

    def test_perpendicularity_without_datum_is_warning(self):
        results = validate_fcf(_fcf(GdtCharacteristic.PERPENDICULARITY), "REQ-002")
        r002 = next(r for r in results if r.rule_id == "VAL-GDT-002")
        assert r002.passed is False

    def test_position_with_datum_passes(self):
        results = validate_fcf(_fcf(GdtCharacteristic.POSITION, datum=_frame()), "REQ-003")
        r002 = next(r for r in results if r.rule_id == "VAL-GDT-002")
        assert r002.passed is True


class TestVAL003ModifierOnFos:
    def test_mmc_without_fos_is_error(self):
        results = validate_fcf(_fcf(GdtCharacteristic.POSITION, modifier=GdtModifier.MMC), "REQ-001")
        r003 = next(r for r in results if r.rule_id == "VAL-GDT-003")
        assert r003.passed is False
        assert r003.severity == "ERROR"

    def test_mmc_with_fos_passes(self):
        results = validate_fcf(
            _fcf(GdtCharacteristic.POSITION, modifier=GdtModifier.MMC),
            "REQ-001", fos=_hole()
        )
        r003 = next(r for r in results if r.rule_id == "VAL-GDT-003")
        assert r003.passed is True

    def test_lmc_without_fos_is_error(self):
        results = validate_fcf(_fcf(GdtCharacteristic.POSITION, modifier=GdtModifier.LMC), "REQ-001")
        r003 = next(r for r in results if r.rule_id == "VAL-GDT-003")
        assert r003.passed is False

    def test_rfs_no_fos_passes(self):
        results = validate_fcf(_fcf(GdtCharacteristic.POSITION, modifier=GdtModifier.NONE), "REQ-001")
        r003 = next(r for r in results if r.rule_id == "VAL-GDT-003")
        assert r003.passed is True


class TestVAL004FormModifier:
    def test_flatness_mmc_is_error(self):
        results = validate_fcf(_fcf(GdtCharacteristic.FLATNESS, modifier=GdtModifier.MMC), "REQ-001")
        r004 = next(r for r in results if r.rule_id == "VAL-GDT-004")
        assert r004.passed is False
        assert r004.severity == "ERROR"

    def test_circularity_lmc_is_error(self):
        results = validate_fcf(_fcf(GdtCharacteristic.CIRCULARITY, modifier=GdtModifier.LMC), "REQ-001")
        r004 = next(r for r in results if r.rule_id == "VAL-GDT-004")
        assert r004.passed is False

    def test_position_mmc_passes_val004(self):
        results = validate_fcf(
            _fcf(GdtCharacteristic.POSITION, modifier=GdtModifier.MMC),
            "REQ-001", fos=_hole()
        )
        r004 = next(r for r in results if r.rule_id == "VAL-GDT-004")
        assert r004.passed is True


class TestVAL006CompositeFcf:
    def test_correct_order_passes(self):
        comp = CompositePositionFCF(
            fcf_id="COMP-001",
            segments=(
                _segment(0, "0.200", SegmentIntent.PATTERN_LOCATING_TOLERANCE_ZONE),
                _segment(1, "0.050", SegmentIntent.FEATURE_RELATING_TOLERANCE_ZONE),
            ),
        )
        results = validate_composite_fcf(comp)
        r006 = next(r for r in results if r.rule_id == "VAL-GDT-006")
        assert r006.passed is True

    def test_inverted_tolerance_is_error(self):
        # Lower > upper is rejected by CompositePositionFCF itself
        with pytest.raises(ValueError, match="lower segment"):
            CompositePositionFCF(
                fcf_id="COMP-002",
                segments=(
                    _segment(0, "0.050", SegmentIntent.PATTERN_LOCATING_TOLERANCE_ZONE),
                    _segment(1, "0.200", SegmentIntent.FEATURE_RELATING_TOLERANCE_ZONE),
                ),
            )

    def test_equal_tolerances_accepted(self):
        comp = CompositePositionFCF(
            fcf_id="COMP-003",
            segments=(
                _segment(0, "0.100", SegmentIntent.PATTERN_LOCATING_TOLERANCE_ZONE),
                _segment(1, "0.100", SegmentIntent.FEATURE_RELATING_TOLERANCE_ZONE),
            ),
        )
        results = validate_composite_fcf(comp)
        r006 = next(r for r in results if r.rule_id == "VAL-GDT-006")
        assert r006.passed is True


class TestVAL007TotalRunout:
    def test_total_runout_without_datum_is_warning(self):
        results = validate_fcf(_fcf(GdtCharacteristic.TOTAL_RUNOUT), "REQ-001")
        r007 = next(r for r in results if r.rule_id == "VAL-GDT-007")
        assert r007.passed is False
        assert r007.severity == "WARNING"

    def test_total_runout_with_datum_passes(self):
        results = validate_fcf(_fcf(GdtCharacteristic.TOTAL_RUNOUT, datum=_frame()), "REQ-001")
        r007 = next(r for r in results if r.rule_id == "VAL-GDT-007")
        assert r007.passed is True

    def test_other_char_not_applicable(self):
        results = validate_fcf(_fcf(GdtCharacteristic.FLATNESS), "REQ-001")
        r007 = next(r for r in results if r.rule_id == "VAL-GDT-007")
        assert r007.passed is True


class TestVAL008LegacyCharacteristics:
    def test_concentricity_info_advisory(self):
        results = validate_fcf(_fcf(GdtCharacteristic.CONCENTRICITY, datum=_frame()), "REQ-001")
        r008 = next(r for r in results if r.rule_id == "VAL-GDT-008")
        assert r008.passed is True   # advisory only
        assert r008.severity == "INFO"
        assert "deprecated" in r008.message.lower()

    def test_symmetry_info_advisory(self):
        results = validate_fcf(_fcf(GdtCharacteristic.SYMMETRY, datum=_frame()), "REQ-001")
        r008 = next(r for r in results if r.rule_id == "VAL-GDT-008")
        assert r008.severity == "INFO"

    def test_position_not_legacy(self):
        results = validate_fcf(_fcf(GdtCharacteristic.POSITION, datum=_frame()), "REQ-001")
        r008 = next(r for r in results if r.rule_id == "VAL-GDT-008")
        assert "not applicable" in r008.message


class TestValidationRuleIdsComplete:
    def test_all_rules_defined(self):
        for rule_id in VALIDATION_RULE_IDS:
            assert rule_id.startswith("VAL-GDT-")
        assert len(VALIDATION_RULE_IDS) == 10
