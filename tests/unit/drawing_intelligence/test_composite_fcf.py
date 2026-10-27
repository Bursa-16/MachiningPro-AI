"""Tests for CompositePositionFCF model (EPIC_04B Phase 2)."""

import pytest
from decimal import Decimal

from backend.drawing_intelligence.requirements import (
    CompositePositionFCF,
    DatumReference,
    DatumReferenceFrame,
    FCFSegment,
    FeatureModifier,
    GdtCharacteristic,
    GdtModifier,
    SegmentIntent,
)


def _seg(idx, tol, intent, datum_labels=None):
    frame = None
    if datum_labels:
        prim = DatumReference(label=datum_labels[0], precedence=1, modifier=GdtModifier.NONE)
        sec = DatumReference(label=datum_labels[1], precedence=2, modifier=GdtModifier.NONE) if len(datum_labels) > 1 else None
        frame = DatumReferenceFrame(primary=prim, secondary=sec, tertiary=None)
    return FCFSegment(
        segment_index=idx,
        characteristic=GdtCharacteristic.POSITION,
        tolerance_value=Decimal(tol), tolerance_unit="mm",
        diameter_zone=True,
        modifier=FeatureModifier.NONE,
        datum_frame=frame,
        intent=intent,
    )


class TestFCFSegmentValidation:
    def test_negative_index_rejected(self):
        with pytest.raises(ValueError, match="segment_index"):
            FCFSegment(
                segment_index=-1,
                characteristic=GdtCharacteristic.POSITION,
                tolerance_value=Decimal("0.1"), tolerance_unit="mm",
                diameter_zone=True, modifier=FeatureModifier.NONE,
                datum_frame=None, intent=SegmentIntent.PATTERN_LOCATING_TOLERANCE_ZONE,
            )

    def test_zero_tolerance_rejected(self):
        with pytest.raises(ValueError, match="tolerance_value"):
            FCFSegment(
                segment_index=0,
                characteristic=GdtCharacteristic.POSITION,
                tolerance_value=Decimal("0"), tolerance_unit="mm",
                diameter_zone=True, modifier=FeatureModifier.NONE,
                datum_frame=None, intent=SegmentIntent.PATTERN_LOCATING_TOLERANCE_ZONE,
            )

    def test_valid_segment(self):
        s = _seg(0, "0.200", SegmentIntent.PATTERN_LOCATING_TOLERANCE_ZONE)
        assert s.tolerance_value == Decimal("0.200")
        assert s.intent == SegmentIntent.PATTERN_LOCATING_TOLERANCE_ZONE


class TestCompositePositionFCFValidation:
    def test_requires_two_segments(self):
        with pytest.raises(ValueError, match="2 segments"):
            CompositePositionFCF(
                fcf_id="COMP-001",
                segments=(_seg(0, "0.200", SegmentIntent.PATTERN_LOCATING_TOLERANCE_ZONE),),
            )

    def test_inverted_segments_rejected(self):
        with pytest.raises(ValueError, match="lower segment"):
            CompositePositionFCF(
                fcf_id="COMP-001",
                segments=(
                    _seg(0, "0.050", SegmentIntent.PATTERN_LOCATING_TOLERANCE_ZONE),
                    _seg(1, "0.200", SegmentIntent.FEATURE_RELATING_TOLERANCE_ZONE),
                ),
            )

    def test_empty_fcf_id_rejected(self):
        with pytest.raises(ValueError, match="fcf_id"):
            CompositePositionFCF(
                fcf_id="",
                segments=(
                    _seg(0, "0.200", SegmentIntent.PATTERN_LOCATING_TOLERANCE_ZONE),
                    _seg(1, "0.050", SegmentIntent.FEATURE_RELATING_TOLERANCE_ZONE),
                ),
            )

    def test_valid_two_segment(self):
        comp = CompositePositionFCF(
            fcf_id="COMP-001",
            segments=(
                _seg(0, "0.200", SegmentIntent.PATTERN_LOCATING_TOLERANCE_ZONE, ["A", "B", "C"]),
                _seg(1, "0.050", SegmentIntent.FEATURE_RELATING_TOLERANCE_ZONE, ["A"]),
            ),
        )
        assert comp.segments[0].tolerance_value == Decimal("0.200")
        assert comp.segments[1].tolerance_value == Decimal("0.050")
        assert comp.segments[0].intent == SegmentIntent.PATTERN_LOCATING_TOLERANCE_ZONE
        assert comp.segments[1].intent == SegmentIntent.FEATURE_RELATING_TOLERANCE_ZONE

    def test_equal_segment_tolerances_valid(self):
        comp = CompositePositionFCF(
            fcf_id="COMP-002",
            segments=(
                _seg(0, "0.100", SegmentIntent.PATTERN_LOCATING_TOLERANCE_ZONE),
                _seg(1, "0.100", SegmentIntent.FEATURE_RELATING_TOLERANCE_ZONE),
            ),
        )
        assert comp.segments[0].tolerance_value == comp.segments[1].tolerance_value


class TestSegmentIntent:
    def test_pltzf_value(self):
        assert SegmentIntent.PATTERN_LOCATING_TOLERANCE_ZONE.value == "PLTZF"

    def test_frtzf_value(self):
        assert SegmentIntent.FEATURE_RELATING_TOLERANCE_ZONE.value == "FRTZF"
