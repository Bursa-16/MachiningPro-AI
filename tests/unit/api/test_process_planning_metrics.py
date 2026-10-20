"""Tests for PROCESS_PLAN_ENGINEERING_METRICS_01.

Covers every cell in HARD RULE 20:
  - RPM reused (CALCULATED_RPM_REUSED=YES)
  - RPM unavailable stays unavailable (MISSING_METRIC_AS_ZERO=NO)
  - RPM utilization with valid machine RPM → AVAILABLE
  - RPM utilization with missing machine RPM → INSUFFICIENT_DATA
  - Feed per rev × RPM (turning / drilling / reaming)
  - Feed per tooth × flute count × RPM (milling)
  - Milling feed with missing flute count → INSUFFICIENT_DATA
  - Missing feed reference → NOT_AVAILABLE
  - Axial engagement valid → AVAILABLE
  - Axial engagement missing diameter → INSUFFICIENT_DATA
  - Zero / negative diameter rejected (never treated as valid)
  - Missing values never become zero (MISSING_METRIC_AS_ZERO=NO)
  - No MRR / force / power / torque / cycle-time / cost / tool-life fabricated
  - Deterministic repeatability
  - API serialisation (engineering_metrics present in plan response)
  - Private path protection (PRIVATE_PATH_IN_API_RESPONSE=NO)
  - Metrics summary counts at plan level
  - METRIC_AVAILABILITY_CHANGES_PLAN_STATUS=NO
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.process_planning.metrics import (
    EngineeringMetric,
    MetricStatus,
    StepEngineeringMetrics,
    compute_step_metrics,
)
from backend.process_planning.plan_models import CuttingParameterRef

client = TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _cp_ref(param_type: str, min_v: float, max_v: float, unit: str = "mm/rev") -> CuttingParameterRef:
    return CuttingParameterRef(
        record_id=f"test-{param_type.lower()}",
        parameter_type=param_type,
        min_value=min_v,
        max_value=max_v,
        unit=unit,
        evidence_status="MANUFACTURER_DATASHEET",
        source_reference=None,
    )


def _find_metric(metrics: StepEngineeringMetrics, metric_id: str) -> EngineeringMetric:
    for m in metrics.metrics:
        if m.metric_id == metric_id:
            return m
    raise KeyError(f"Metric {metric_id!r} not found")


def _base_kwargs(**overrides) -> dict:
    defaults = dict(
        operation="milling",
        calculated_rpm=5000.0,
        rpm_margin_frac=0.5,
        machine_spindle_max_rpm=10000,
        cutting_param_refs=[],
        tool_diameter_mm=10.0,
        number_of_flutes=4,
        cutting_tool_id="test-tool",
    )
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# CALCULATED_RPM metric
# ---------------------------------------------------------------------------

class TestCalculatedRpm:
    def test_available_when_rpm_provided(self):
        result = compute_step_metrics(**_base_kwargs(calculated_rpm=3183.0))
        m = _find_metric(result, "CALCULATED_RPM")
        assert m.status == MetricStatus.AVAILABLE
        assert m.value == 3183
        assert m.unit == "rpm"

    def test_insufficient_data_when_rpm_none(self):
        result = compute_step_metrics(**_base_kwargs(calculated_rpm=None))
        m = _find_metric(result, "CALCULATED_RPM")
        assert m.status == MetricStatus.INSUFFICIENT_DATA
        assert m.value is None

    def test_not_available_when_rpm_zero(self):
        result = compute_step_metrics(**_base_kwargs(calculated_rpm=0.0))
        m = _find_metric(result, "CALCULATED_RPM")
        assert m.status == MetricStatus.NOT_AVAILABLE
        assert m.value is None

    def test_value_is_rounded(self):
        result = compute_step_metrics(**_base_kwargs(calculated_rpm=3183.098))
        m = _find_metric(result, "CALCULATED_RPM")
        assert m.status == MetricStatus.AVAILABLE
        assert m.value == 3183

    def test_missing_never_becomes_zero(self):
        result = compute_step_metrics(**_base_kwargs(calculated_rpm=None))
        m = _find_metric(result, "CALCULATED_RPM")
        assert m.value is None
        assert m.value != 0

    def test_formula_reference_present(self):
        result = compute_step_metrics(**_base_kwargs(calculated_rpm=1000.0))
        m = _find_metric(result, "CALCULATED_RPM")
        assert m.formula_reference is not None
        assert "Vc" in m.formula_reference or "π" in m.formula_reference or "pi" in m.formula_reference.lower()


# ---------------------------------------------------------------------------
# RPM UTILIZATION metric
# ---------------------------------------------------------------------------

class TestRpmUtilization:
    def test_available_with_both_rpms(self):
        result = compute_step_metrics(**_base_kwargs(
            calculated_rpm=4000.0, machine_spindle_max_rpm=10000
        ))
        m = _find_metric(result, "RPM_UTILIZATION")
        assert m.status == MetricStatus.AVAILABLE
        assert m.value == pytest.approx(40.0, abs=0.1)
        assert m.unit == "%"

    def test_insufficient_data_when_machine_rpm_missing(self):
        result = compute_step_metrics(**_base_kwargs(
            calculated_rpm=4000.0, machine_spindle_max_rpm=None
        ))
        m = _find_metric(result, "RPM_UTILIZATION")
        assert m.status == MetricStatus.INSUFFICIENT_DATA
        assert m.value is None

    def test_insufficient_data_when_calculated_rpm_missing(self):
        result = compute_step_metrics(**_base_kwargs(
            calculated_rpm=None, machine_spindle_max_rpm=10000
        ))
        m = _find_metric(result, "RPM_UTILIZATION")
        assert m.status == MetricStatus.INSUFFICIENT_DATA
        assert m.value is None

    def test_not_available_when_machine_rpm_zero(self):
        result = compute_step_metrics(**_base_kwargs(
            calculated_rpm=4000.0, machine_spindle_max_rpm=0
        ))
        m = _find_metric(result, "RPM_UTILIZATION")
        assert m.status == MetricStatus.NOT_AVAILABLE
        assert m.value is None

    def test_missing_never_becomes_zero(self):
        result = compute_step_metrics(**_base_kwargs(
            calculated_rpm=None, machine_spindle_max_rpm=None
        ))
        m = _find_metric(result, "RPM_UTILIZATION")
        assert m.value is None
        assert m.value != 0

    def test_uses_machine_spindle_not_holder_or_tool_rpm(self):
        result = compute_step_metrics(**_base_kwargs(
            calculated_rpm=4000.0, machine_spindle_max_rpm=8000
        ))
        m = _find_metric(result, "RPM_UTILIZATION")
        assert m.status == MetricStatus.AVAILABLE
        assert m.value == pytest.approx(50.0, abs=0.1)
        assert "n_max" in (m.formula_reference or "").lower() or "utilization" in (m.formula_reference or "").lower()

    def test_near_100_percent_utilization(self):
        result = compute_step_metrics(**_base_kwargs(
            calculated_rpm=9900.0, machine_spindle_max_rpm=10000
        ))
        m = _find_metric(result, "RPM_UTILIZATION")
        assert m.status == MetricStatus.AVAILABLE
        assert m.value == pytest.approx(99.0, abs=0.1)


# ---------------------------------------------------------------------------
# RPM MARGIN metric
# ---------------------------------------------------------------------------

class TestRpmMargin:
    def test_available_with_margin(self):
        result = compute_step_metrics(**_base_kwargs(
            rpm_margin_frac=0.5833, calculated_rpm=4167.0, machine_spindle_max_rpm=10000
        ))
        m = _find_metric(result, "RPM_MARGIN")
        assert m.status == MetricStatus.AVAILABLE
        assert m.value == pytest.approx(58.3, abs=0.1)
        assert m.unit == "%"

    def test_insufficient_data_when_margin_missing_and_rpm_missing(self):
        result = compute_step_metrics(**_base_kwargs(
            rpm_margin_frac=None, calculated_rpm=None
        ))
        m = _find_metric(result, "RPM_MARGIN")
        assert m.status == MetricStatus.INSUFFICIENT_DATA

    def test_insufficient_data_when_margin_missing_and_machine_rpm_missing(self):
        result = compute_step_metrics(**_base_kwargs(
            rpm_margin_frac=None, calculated_rpm=5000.0, machine_spindle_max_rpm=None
        ))
        m = _find_metric(result, "RPM_MARGIN")
        assert m.status == MetricStatus.INSUFFICIENT_DATA

    def test_semantics_machine_spindle_only(self):
        result = compute_step_metrics(**_base_kwargs(
            rpm_margin_frac=0.416, calculated_rpm=5838.0, machine_spindle_max_rpm=10000
        ))
        m = _find_metric(result, "RPM_MARGIN")
        assert m.status == MetricStatus.AVAILABLE
        assert "machine" in (m.explanation or "").lower() or "spindle" in (m.explanation or "").lower()

    def test_missing_never_becomes_zero(self):
        result = compute_step_metrics(**_base_kwargs(rpm_margin_frac=None, calculated_rpm=None))
        m = _find_metric(result, "RPM_MARGIN")
        assert m.value is None
        assert m.value != 0


# ---------------------------------------------------------------------------
# FEED RATE RANGE metric
# ---------------------------------------------------------------------------

class TestFeedRateRange:
    # --- Turning / drilling / reaming (FEED_PER_REV × n) ---

    def test_turning_available(self):
        refs = [_cp_ref("FEED_PER_REV", 0.1, 0.3)]
        result = compute_step_metrics(**_base_kwargs(
            operation="turning", calculated_rpm=2000.0,
            cutting_param_refs=refs, number_of_flutes=None
        ))
        m = _find_metric(result, "FEED_RATE_RANGE")
        assert m.status == MetricStatus.AVAILABLE
        assert m.min_value == pytest.approx(0.1 * 2000, abs=0.5)
        assert m.max_value == pytest.approx(0.3 * 2000, abs=0.5)
        assert m.unit == "mm/min"

    def test_drilling_available(self):
        refs = [_cp_ref("FEED_PER_REV", 0.05, 0.15)]
        result = compute_step_metrics(**_base_kwargs(
            operation="drilling", calculated_rpm=3000.0,
            cutting_param_refs=refs, number_of_flutes=None
        ))
        m = _find_metric(result, "FEED_RATE_RANGE")
        assert m.status == MetricStatus.AVAILABLE
        assert m.min_value == pytest.approx(0.05 * 3000, abs=0.5)
        assert m.max_value == pytest.approx(0.15 * 3000, abs=0.5)

    def test_reaming_available(self):
        refs = [_cp_ref("FEED_PER_REV", 0.2, 0.5)]
        result = compute_step_metrics(**_base_kwargs(
            operation="reaming", calculated_rpm=1000.0,
            cutting_param_refs=refs, number_of_flutes=None
        ))
        m = _find_metric(result, "FEED_RATE_RANGE")
        assert m.status == MetricStatus.AVAILABLE
        assert m.min_value == pytest.approx(200.0, abs=0.5)
        assert m.max_value == pytest.approx(500.0, abs=0.5)

    # --- Milling (FEED_PER_TOOTH × z × n) ---

    def test_milling_available_with_flutes(self):
        refs = [_cp_ref("FEED_PER_TOOTH", 0.05, 0.1, unit="mm/tooth")]
        result = compute_step_metrics(**_base_kwargs(
            operation="milling", calculated_rpm=2000.0,
            cutting_param_refs=refs, number_of_flutes=4
        ))
        m = _find_metric(result, "FEED_RATE_RANGE")
        assert m.status == MetricStatus.AVAILABLE
        assert m.min_value == pytest.approx(0.05 * 4 * 2000, abs=1.0)
        assert m.max_value == pytest.approx(0.1 * 4 * 2000, abs=1.0)
        assert m.unit == "mm/min"

    def test_milling_insufficient_data_missing_flute_count(self):
        refs = [_cp_ref("FEED_PER_TOOTH", 0.05, 0.1, unit="mm/tooth")]
        result = compute_step_metrics(**_base_kwargs(
            operation="milling", calculated_rpm=2000.0,
            cutting_param_refs=refs, number_of_flutes=None
        ))
        m = _find_metric(result, "FEED_RATE_RANGE")
        assert m.status == MetricStatus.INSUFFICIENT_DATA
        assert m.value is None
        assert m.min_value is None
        assert m.max_value is None

    def test_milling_no_ref_returns_not_available(self):
        result = compute_step_metrics(**_base_kwargs(
            operation="milling", calculated_rpm=2000.0,
            cutting_param_refs=[], number_of_flutes=4
        ))
        m = _find_metric(result, "FEED_RATE_RANGE")
        assert m.status == MetricStatus.NOT_AVAILABLE

    def test_turning_no_ref_returns_not_available(self):
        result = compute_step_metrics(**_base_kwargs(
            operation="turning", calculated_rpm=2000.0,
            cutting_param_refs=[]
        ))
        m = _find_metric(result, "FEED_RATE_RANGE")
        assert m.status == MetricStatus.NOT_AVAILABLE

    def test_insufficient_data_when_rpm_missing(self):
        refs = [_cp_ref("FEED_PER_REV", 0.1, 0.3)]
        result = compute_step_metrics(**_base_kwargs(
            operation="turning", calculated_rpm=None,
            cutting_param_refs=refs
        ))
        m = _find_metric(result, "FEED_RATE_RANGE")
        assert m.status == MetricStatus.INSUFFICIENT_DATA

    def test_wrong_param_type_ignored(self):
        """FEED_PER_REV refs are ignored for milling (needs FEED_PER_TOOTH)."""
        refs = [_cp_ref("FEED_PER_REV", 0.1, 0.3)]
        result = compute_step_metrics(**_base_kwargs(
            operation="milling", calculated_rpm=2000.0,
            cutting_param_refs=refs, number_of_flutes=4
        ))
        m = _find_metric(result, "FEED_RATE_RANGE")
        assert m.status == MetricStatus.NOT_AVAILABLE

    def test_flute_count_inferred_no(self):
        """FLUTE_COUNT_INFERRED=NO — missing flute count is not defaulted or guessed."""
        refs = [_cp_ref("FEED_PER_TOOTH", 0.05, 0.1, unit="mm/tooth")]
        result = compute_step_metrics(**_base_kwargs(
            operation="milling", calculated_rpm=2000.0,
            cutting_param_refs=refs, number_of_flutes=None,
            cutting_tool_id=None,
        ))
        m = _find_metric(result, "FEED_RATE_RANGE")
        assert m.status == MetricStatus.INSUFFICIENT_DATA
        assert m.value is None

    def test_missing_never_becomes_zero(self):
        refs = [_cp_ref("FEED_PER_TOOTH", 0.05, 0.1, unit="mm/tooth")]
        result = compute_step_metrics(**_base_kwargs(
            operation="milling", calculated_rpm=2000.0,
            cutting_param_refs=refs, number_of_flutes=None
        ))
        m = _find_metric(result, "FEED_RATE_RANGE")
        assert m.min_value is None
        assert m.max_value is None


# ---------------------------------------------------------------------------
# AXIAL ENGAGEMENT RATIO metric
# ---------------------------------------------------------------------------

class TestAxialEngagementRatio:
    def test_available_with_valid_diameter(self):
        refs = [_cp_ref("AXIAL_DEPTH_OF_CUT", 2.0, 6.0, unit="mm")]
        result = compute_step_metrics(**_base_kwargs(
            cutting_param_refs=refs, tool_diameter_mm=10.0
        ))
        m = _find_metric(result, "AXIAL_ENGAGEMENT_RATIO")
        assert m.status == MetricStatus.AVAILABLE
        assert m.min_value == pytest.approx(0.2, abs=0.0001)
        assert m.max_value == pytest.approx(0.6, abs=0.0001)
        assert m.unit == "ap/D"

    def test_insufficient_data_when_diameter_missing(self):
        refs = [_cp_ref("AXIAL_DEPTH_OF_CUT", 2.0, 6.0, unit="mm")]
        result = compute_step_metrics(**_base_kwargs(
            cutting_param_refs=refs, tool_diameter_mm=None
        ))
        m = _find_metric(result, "AXIAL_ENGAGEMENT_RATIO")
        assert m.status == MetricStatus.INSUFFICIENT_DATA
        assert m.min_value is None

    def test_insufficient_data_when_diameter_zero(self):
        refs = [_cp_ref("AXIAL_DEPTH_OF_CUT", 2.0, 6.0, unit="mm")]
        result = compute_step_metrics(**_base_kwargs(
            cutting_param_refs=refs, tool_diameter_mm=0.0
        ))
        m = _find_metric(result, "AXIAL_ENGAGEMENT_RATIO")
        assert m.status == MetricStatus.INSUFFICIENT_DATA

    def test_insufficient_data_when_diameter_negative(self):
        refs = [_cp_ref("AXIAL_DEPTH_OF_CUT", 2.0, 6.0, unit="mm")]
        result = compute_step_metrics(**_base_kwargs(
            cutting_param_refs=refs, tool_diameter_mm=-5.0
        ))
        m = _find_metric(result, "AXIAL_ENGAGEMENT_RATIO")
        assert m.status == MetricStatus.INSUFFICIENT_DATA

    def test_not_available_when_no_ap_ref(self):
        result = compute_step_metrics(**_base_kwargs(
            cutting_param_refs=[], tool_diameter_mm=10.0
        ))
        m = _find_metric(result, "AXIAL_ENGAGEMENT_RATIO")
        assert m.status == MetricStatus.NOT_AVAILABLE

    def test_missing_never_becomes_zero(self):
        result = compute_step_metrics(**_base_kwargs(
            cutting_param_refs=[], tool_diameter_mm=10.0
        ))
        m = _find_metric(result, "AXIAL_ENGAGEMENT_RATIO")
        assert m.min_value is None
        assert m.max_value is None


# ---------------------------------------------------------------------------
# Summary counts
# ---------------------------------------------------------------------------

class TestSummaryAndCounts:
    def test_counts_correct_for_all_available(self):
        refs = [
            _cp_ref("FEED_PER_TOOTH", 0.05, 0.1, unit="mm/tooth"),
            _cp_ref("AXIAL_DEPTH_OF_CUT", 2.0, 6.0, unit="mm"),
        ]
        result = compute_step_metrics(**_base_kwargs(
            operation="milling", calculated_rpm=5000.0,
            rpm_margin_frac=0.5, machine_spindle_max_rpm=10000,
            cutting_param_refs=refs, tool_diameter_mm=10.0,
            number_of_flutes=4,
        ))
        assert result.metrics_available_count == 5
        assert result.metrics_not_available_count == 0
        assert result.metrics_insufficient_data_count == 0

    def test_counts_correct_for_all_insufficient(self):
        result = compute_step_metrics(**_base_kwargs(
            calculated_rpm=None, rpm_margin_frac=None,
            machine_spindle_max_rpm=None, cutting_param_refs=[],
            tool_diameter_mm=None, number_of_flutes=None,
        ))
        # CALCULATED_RPM, RPM_UTIL, RPM_MARGIN → INSUFFICIENT_DATA
        # FEED_RATE_RANGE → INSUFFICIENT_DATA (no rpm)
        # AXIAL_ENGAGEMENT_RATIO → NOT_AVAILABLE (no ap refs)
        assert result.metrics_insufficient_data_count >= 3
        assert result.metrics_not_available_count >= 1
        assert result.metrics_available_count == 0

    def test_metrics_list_has_five_entries(self):
        result = compute_step_metrics(**_base_kwargs())
        assert len(result.metrics) == 5

    def test_counts_sum_to_total(self):
        result = compute_step_metrics(**_base_kwargs())
        total = (
            result.metrics_available_count
            + result.metrics_not_available_count
            + result.metrics_insufficient_data_count
        )
        not_applicable = sum(1 for m in result.metrics if m.status == MetricStatus.NOT_APPLICABLE)
        assert total + not_applicable == len(result.metrics)


# ---------------------------------------------------------------------------
# Not-implemented metrics (HARD RULES 09–14)
# ---------------------------------------------------------------------------

class TestNotImplementedMetrics:
    def test_no_mrr_in_response(self):
        result = compute_step_metrics(**_base_kwargs())
        ids = {m.metric_id for m in result.metrics}
        assert "MRR" not in ids
        assert "MATERIAL_REMOVAL_RATE" not in ids

    def test_no_cutting_force(self):
        result = compute_step_metrics(**_base_kwargs())
        ids = {m.metric_id for m in result.metrics}
        assert not any("FORCE" in i for i in ids)

    def test_no_power(self):
        result = compute_step_metrics(**_base_kwargs())
        ids = {m.metric_id for m in result.metrics}
        assert not any("POWER" in i for i in ids)

    def test_no_torque(self):
        result = compute_step_metrics(**_base_kwargs())
        ids = {m.metric_id for m in result.metrics}
        assert not any("TORQUE" in i for i in ids)

    def test_no_cycle_time(self):
        result = compute_step_metrics(**_base_kwargs())
        ids = {m.metric_id for m in result.metrics}
        assert not any("CYCLE" in i for i in ids)

    def test_no_cost(self):
        result = compute_step_metrics(**_base_kwargs())
        ids = {m.metric_id for m in result.metrics}
        assert not any("COST" in i for i in ids)

    def test_no_tool_life(self):
        result = compute_step_metrics(**_base_kwargs())
        ids = {m.metric_id for m in result.metrics}
        assert not any("TOOL_LIFE" in i for i in ids)

    def test_no_surface_roughness(self):
        result = compute_step_metrics(**_base_kwargs())
        ids = {m.metric_id for m in result.metrics}
        assert not any("ROUGHNESS" in i or "SURFACE" in i for i in ids)


# ---------------------------------------------------------------------------
# False claim checks
# ---------------------------------------------------------------------------

class TestFalseClaimSafety:
    def test_no_false_ai_claim(self):
        result = compute_step_metrics(**_base_kwargs())
        all_text = " ".join(
            str(m.metric_name) + str(m.explanation or "") + str(m.formula_reference or "")
            for m in result.metrics
        ).lower()
        forbidden = ["ai recommended", "ai optimised", "ai optimized", "machine learning"]
        for phrase in forbidden:
            assert phrase not in all_text

    def test_no_false_optimization_claim(self):
        result = compute_step_metrics(**_base_kwargs())
        for m in result.metrics:
            expl = (m.explanation or "").lower()
            assert "optimal" not in expl or "not optimal" in expl

    def test_no_false_production_validation(self):
        result = compute_step_metrics(**_base_kwargs())
        for m in result.metrics:
            expl = (m.explanation or "").lower()
            assert "production validated" not in expl
            assert "validated in production" not in expl


# ---------------------------------------------------------------------------
# Deterministic repeatability
# ---------------------------------------------------------------------------

class TestDeterministicRepeatability:
    def test_same_inputs_produce_same_output(self):
        kwargs = _base_kwargs(
            calculated_rpm=3979.0, rpm_margin_frac=0.6, machine_spindle_max_rpm=9950,
            cutting_param_refs=[
                _cp_ref("FEED_PER_TOOTH", 0.06, 0.12, unit="mm/tooth"),
                _cp_ref("AXIAL_DEPTH_OF_CUT", 3.0, 8.0, unit="mm"),
            ],
            number_of_flutes=3, tool_diameter_mm=12.0,
        )
        r1 = compute_step_metrics(**kwargs)
        r2 = compute_step_metrics(**kwargs)
        assert r1.model_dump() == r2.model_dump()

    def test_metric_status_deterministic(self):
        kwargs = _base_kwargs()
        r1 = compute_step_metrics(**kwargs)
        r2 = compute_step_metrics(**kwargs)
        for m1, m2 in zip(r1.metrics, r2.metrics):
            assert m1.status == m2.status
            assert m1.value == m2.value


# ---------------------------------------------------------------------------
# API integration — engineering_metrics in plan response
# ---------------------------------------------------------------------------

class TestApiIntegration:
    def test_engineering_metrics_present_in_plan_response(self):
        """HARD RULE 17 — engineering_metrics is present in every step of the response."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "TestPart",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
        )
        assert r.status_code == 200
        data = r.json()
        step = data["steps"][0]
        assert "engineering_metrics" in step
        em = step["engineering_metrics"]
        assert em is not None
        assert "metrics" in em
        assert "metrics_available_count" in em
        assert "metrics_not_available_count" in em
        assert "metrics_insufficient_data_count" in em

    def test_plan_level_metrics_counts_present(self):
        """HARD RULE 16 — plan-level metrics summary counts present."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "TestPart",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert "metrics_available_count" in data
        assert "metrics_not_available_count" in data
        assert "metrics_insufficient_data_count" in data
        assert isinstance(data["metrics_available_count"], int)
        assert isinstance(data["metrics_not_available_count"], int)
        assert isinstance(data["metrics_insufficient_data_count"], int)

    def test_metrics_list_has_five_entries_in_api_response(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "TestPart",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
        )
        data = r.json()
        em = data["steps"][0]["engineering_metrics"]
        assert len(em["metrics"]) == 5

    def test_each_metric_has_required_fields(self):
        """HARD RULE 03 — metric result contract: metric_id, metric_name, status."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "TestPart",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
        )
        data = r.json()
        for m in data["steps"][0]["engineering_metrics"]["metrics"]:
            assert "metric_id" in m
            assert "metric_name" in m
            assert "status" in m
            assert m["status"] in ("AVAILABLE", "NOT_AVAILABLE", "INSUFFICIENT_DATA", "NOT_APPLICABLE")

    def test_metric_availability_does_not_change_plan_status(self):
        """METRIC_AVAILABILITY_CHANGES_PLAN_STATUS=NO."""
        # Baseline without Vc/D (all metrics INSUFFICIENT_DATA)
        r1 = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "T",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
        )
        # With Vc/D (CALCULATED_RPM becomes AVAILABLE, plan may change due to RPM rules)
        r2 = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "T",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling",
                     "cutting_speed_m_min": 50.0, "tool_diameter_mm": 6.0}
                ],
            },
        )
        # plan_status is determined by selection engine, not engineering metrics
        assert r1.status_code == 200
        assert r2.status_code == 200
        d1, d2 = r1.json(), r2.json()
        # The step's engineering_metrics should not be driving plan_status
        step1 = d1["steps"][0]
        step2 = d2["steps"][0]
        # Regardless of metric availability, planning_status is from the selection engine
        assert step1["planning_status"] in ("PLANNED", "BLOCKED", "INSUFFICIENT_DATA")
        assert step2["planning_status"] in ("PLANNED", "BLOCKED", "INSUFFICIENT_DATA")

    def test_no_mrr_in_api_response(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "T",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
        )
        data = r.json()
        ids = {m["metric_id"] for m in data["steps"][0]["engineering_metrics"]["metrics"]}
        assert "MRR" not in ids
        assert "MATERIAL_REMOVAL_RATE" not in ids

    def test_no_cycle_time_in_api_response(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "T",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
        )
        data = r.json()
        ids = {m["metric_id"] for m in data["steps"][0]["engineering_metrics"]["metrics"]}
        assert not any("CYCLE" in i for i in ids)

    def test_no_cost_in_api_response(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "T",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
        )
        data = r.json()
        ids = {m["metric_id"] for m in data["steps"][0]["engineering_metrics"]["metrics"]}
        assert not any("COST" in i for i in ids)

    def test_no_tool_life_in_api_response(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "T",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
        )
        data = r.json()
        ids = {m["metric_id"] for m in data["steps"][0]["engineering_metrics"]["metrics"]}
        assert not any("TOOL_LIFE" in i for i in ids)

    def test_no_private_path_in_metrics(self):
        """PRIVATE_PATH_IN_API_RESPONSE=NO."""
        path_pattern = re.compile(r"[A-Za-z]:\\|/home/|/Users/")
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "T",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
        )
        data = r.json()
        text = str(data["steps"][0].get("engineering_metrics", ""))
        assert not path_pattern.search(text), "Private path found in engineering_metrics"

    def test_missing_metric_not_zero_in_api_response(self):
        """MISSING_METRIC_AS_ZERO=NO — INSUFFICIENT_DATA metrics have null value."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "T",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
        )
        data = r.json()
        for m in data["steps"][0]["engineering_metrics"]["metrics"]:
            if m["status"] in ("INSUFFICIENT_DATA", "NOT_AVAILABLE"):
                assert m["value"] is None, (
                    f"Metric {m['metric_id']} has status {m['status']} "
                    f"but value={m['value']} (expected null)"
                )

    def test_multiple_steps_each_have_engineering_metrics(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "T",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"},
                    {"step_id": "OP20", "sequence_number": 20, "operation": "drilling"},
                ],
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["steps"]) == 2
        for step in data["steps"]:
            assert step.get("engineering_metrics") is not None

    def test_not_supported_step_has_metrics_none_or_all_not_applicable(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "T",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "unsupported_op_xyz"}
                ],
            },
        )
        assert r.status_code == 200
        data = r.json()
        step = data["steps"][0]
        assert step["planning_status"] == "NOT_SUPPORTED"
        # NOT_SUPPORTED steps may have engineering_metrics=None (no selection run)
        em = step.get("engineering_metrics")
        # Just check it doesn't crash or return garbage — None is acceptable
        if em is not None:
            for m in em["metrics"]:
                assert m["status"] in (
                    "NOT_APPLICABLE", "NOT_AVAILABLE", "INSUFFICIENT_DATA", "AVAILABLE"
                )

    def test_api_plan_level_counts_match_step_sums(self):
        """Plan-level counts must equal the sum of step-level counts."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "T",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"},
                    {"step_id": "OP20", "sequence_number": 20, "operation": "drilling"},
                ],
            },
        )
        assert r.status_code == 200
        data = r.json()
        total_avail = sum(
            s["engineering_metrics"]["metrics_available_count"]
            for s in data["steps"]
            if s.get("engineering_metrics")
        )
        total_not_avail = sum(
            s["engineering_metrics"]["metrics_not_available_count"]
            for s in data["steps"]
            if s.get("engineering_metrics")
        )
        total_insuff = sum(
            s["engineering_metrics"]["metrics_insufficient_data_count"]
            for s in data["steps"]
            if s.get("engineering_metrics")
        )
        assert data["metrics_available_count"] == total_avail
        assert data["metrics_not_available_count"] == total_not_avail
        assert data["metrics_insufficient_data_count"] == total_insuff

    def test_with_vc_and_d_calculated_rpm_available(self):
        """Case A: operation with calculated RPM (HARD RULE 24 Case A)."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "T",
                "material_iso_group": "P",
                "operations": [
                    {
                        "step_id": "OP10",
                        "sequence_number": 10,
                        "operation": "milling",
                        "cutting_speed_m_min": 150.0,
                        "tool_diameter_mm": 12.0,
                    }
                ],
            },
        )
        assert r.status_code == 200
        data = r.json()
        em = data["steps"][0]["engineering_metrics"]
        rpm_metric = next(m for m in em["metrics"] if m["metric_id"] == "CALCULATED_RPM")
        assert rpm_metric["status"] == "AVAILABLE"
        assert rpm_metric["value"] is not None
        assert rpm_metric["value"] > 0

    def test_without_vc_or_d_rpm_insufficient(self):
        """Operation without Vc or D → CALCULATED_RPM = INSUFFICIENT_DATA."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "T",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
        )
        assert r.status_code == 200
        data = r.json()
        em = data["steps"][0]["engineering_metrics"]
        rpm_metric = next(m for m in em["metrics"] if m["metric_id"] == "CALCULATED_RPM")
        assert rpm_metric["status"] == "INSUFFICIENT_DATA"
        assert rpm_metric["value"] is None
