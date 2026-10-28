"""Tests for calibration precedence resolver — EPIC_04F.

CALIBRATION_PRECEDENCE_IMPLEMENTED=YES
CALIBRATION_AUDIT_TRACE_IMPLEMENTED=YES
"""

import pytest

from backend.calibration.models import (
    CalibrationConfidence,
    CalibrationSource,
    CalibrationValue,
)
from backend.calibration.resolver import CalibrationContext, resolve_calibration_value
from backend.calibration.shop_profile import ShopCalibrationProfile


class TestCalibrationContext:
    def test_empty_context_has_no_candidates(self):
        ctx = CalibrationContext()
        assert ctx.candidates == []

    def test_add_user_override(self):
        ctx = CalibrationContext()
        ctx.add_user_override(5.0, notes="test")
        assert len(ctx.candidates) == 1
        assert ctx.candidates[0].source == CalibrationSource.USER_OVERRIDE

    def test_add_reference(self):
        ctx = CalibrationContext()
        ctx.add_reference(3.0, source=CalibrationSource.LITERATURE_REFERENCE)
        assert ctx.candidates[0].source == CalibrationSource.LITERATURE_REFERENCE

    def test_add_shop_profile_extracts_field(self):
        ctx = CalibrationContext()
        profile = ShopCalibrationProfile(label="test", atc_time_sec=6.0)
        ctx.add_shop_profile(profile, "atc_time_sec")
        assert len(ctx.candidates) == 1
        assert ctx.candidates[0].value == 6.0

    def test_add_shop_profile_missing_field_skipped(self):
        ctx = CalibrationContext()
        profile = ShopCalibrationProfile(label="test", atc_time_sec=None)
        ctx.add_shop_profile(profile, "atc_time_sec")
        assert len(ctx.candidates) == 0

    def test_candidates_sorted_by_precedence(self):
        ctx = CalibrationContext()
        ctx.add_reference(3.0, source=CalibrationSource.GLOBAL_REFERENCE)
        ctx.add_user_override(5.0)
        ctx.add_reference(4.0, source=CalibrationSource.LITERATURE_REFERENCE)
        cands = ctx.candidates
        assert cands[0].source == CalibrationSource.USER_OVERRIDE


class TestResolveCalibrationValue:
    def test_user_override_wins(self):
        ctx = CalibrationContext()
        ctx.add_user_override(5.0)
        ctx.add_reference(3.0, source=CalibrationSource.LITERATURE_REFERENCE)
        result = resolve_calibration_value(ctx, "atc_time_sec")
        assert result.resolved_source == CalibrationSource.USER_OVERRIDE
        assert result.resolved_value == 5.0

    def test_shop_validated_over_literature(self):
        ctx = CalibrationContext()
        ctx.add_reference(3.0, source=CalibrationSource.LITERATURE_REFERENCE)
        profile = ShopCalibrationProfile(label="test", atc_time_sec=4.5)
        ctx.add_shop_profile(profile, "atc_time_sec")
        result = resolve_calibration_value(ctx)
        assert result.resolved_source == CalibrationSource.SHOP_VALIDATED
        assert result.resolved_value == pytest.approx(4.5)

    def test_empty_context_insufficient_data(self):
        ctx = CalibrationContext()
        result = resolve_calibration_value(ctx, "atc_time")
        assert result.resolved_source == CalibrationSource.INSUFFICIENT_DATA
        assert result.resolved_value is None

    def test_rejected_sources_populated(self):
        ctx = CalibrationContext()
        ctx.add_user_override(5.0)
        ctx.add_reference(3.0, source=CalibrationSource.LITERATURE_REFERENCE)
        result = resolve_calibration_value(ctx)
        assert len(result.rejected_sources) == 1
        assert result.rejected_sources[0]["source"] == CalibrationSource.LITERATURE_REFERENCE.value

    def test_single_candidate_no_rejected(self):
        ctx = CalibrationContext()
        ctx.add_reference(3.0, source=CalibrationSource.GLOBAL_REFERENCE)
        result = resolve_calibration_value(ctx)
        assert result.rejected_sources == []

    def test_confidence_propagated(self):
        ctx = CalibrationContext()
        ctx.add_user_override(5.0)
        result = resolve_calibration_value(ctx)
        assert result.confidence == CalibrationConfidence.HIGH

    def test_audit_trace_implemented(self):
        ctx = CalibrationContext()
        ctx.add_user_override(5.0)
        ctx.add_reference(3.0, source=CalibrationSource.LITERATURE_REFERENCE)
        result = resolve_calibration_value(ctx)
        # Audit trace: resolved + rejected
        assert result.resolved_value is not None
        assert len(result.rejected_sources) >= 1

    def test_none_value_not_added(self):
        ctx = CalibrationContext()
        ctx.add(CalibrationValue(
            value=None,
            source=CalibrationSource.USER_OVERRIDE,
            confidence=CalibrationConfidence.HIGH,
        ))
        assert len(ctx.candidates) == 0
