"""Tests for PROCESS_PLAN_CYCLE_TIME_FOUNDATION_01.

Test-contract guarantees:
    CUTTING_TIME_FORMULA_DUPLICATED=NO
    PATH_LENGTH_GUESSED=NO
    FEED_RANGE_MIDPOINT_ASSUMED=NO
    DWELL_TIME_GUESSED=NO
    TOOL_CHANGE_TIME_GUESSED=NO
    DRILL_TRAVEL_ALLOWANCE_GUESSED=NO
    REAM_TRAVEL_ALLOWANCE_GUESSED=NO
    TURNING_PASS_COUNT_INFERRED=NO
    MILLING_PATH_GENERATION_IMPLEMENTED=NO
    KNOWN_SUBTOTAL_MISLABELED_AS_TOTAL=NO
    CYCLE_TIME_AVAILABILITY_CHANGES_PLAN_STATUS=NO
    PRIVATE_LOCAL_PATH_VISIBLE=NO
"""

from __future__ import annotations

import json
import math

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.process_planning.cycle_time import (
    CycleTimeScope,
    CycleTimeStatus,
    StepCycleTime,
    TimeComponentStatus,
    compute_step_cycle_time,
)
from backend.process_planning.metrics import EngineeringMetric, MetricStatus

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _feed_metric(
    min_val: float,
    max_val: float,
    status: MetricStatus = MetricStatus.AVAILABLE,
) -> EngineeringMetric:
    return EngineeringMetric(
        metric_id="FEED_RATE_RANGE",
        metric_name="Feed Rate Range",
        status=status,
        min_value=min_val,
        max_value=max_val,
        unit="mm/min",
    )


def _plan_body(
    operation: str = "DRILLING",
    iso_group: str = "P",
    path_mm: float | None = None,
    rapid_mm: float | None = None,
    dwell_s: float | None = None,
    machine_id: str | None = None,
) -> dict:
    step: dict = {
        "step_id": "OP10",
        "sequence_number": 10,
        "operation": operation,
    }
    if path_mm is not None:
        step["cutting_path_length_mm"] = path_mm
        step["cutting_path_source"] = "USER_INPUT"
    if rapid_mm is not None:
        step["rapid_distance_mm"] = rapid_mm
    if dwell_s is not None:
        step["dwell_sec"] = dwell_s
    if machine_id is not None:
        step["machine_id"] = machine_id
    return {
        "part_name": "Test Part",
        "material_iso_group": iso_group,
        "operations": [step],
    }


# ---------------------------------------------------------------------------
# 1. Canonical formula is reused, not duplicated
# ---------------------------------------------------------------------------

def test_canonical_formula_module_imported():
    """FEED_FORMULA_DUPLICATED=NO — machining_time_from_distance_feed_rate must be
    used by cycle_time module, not re-implemented inline."""
    import inspect
    from backend.process_planning import cycle_time as ct_mod
    from backend.machining.formulas import machining_time_from_distance_feed_rate
    source = inspect.getsource(ct_mod)
    assert "machining_time_from_distance_feed_rate" in source
    # Must not contain the bare formula string t = L / fr implemented directly
    assert "t = distance / feed" not in source
    assert "t = path / feed" not in source
    assert "time_min = path_mm / feed" not in source


# ---------------------------------------------------------------------------
# 2–6. Cutting time: explicit path + feed
# ---------------------------------------------------------------------------

def test_explicit_path_fixed_feed_returns_available():
    fm = _feed_metric(100.0, 100.0)  # single-value feed
    result = compute_step_cycle_time(
        cutting_path_length_mm=100.0,
        cutting_path_source="USER_INPUT",
        feed_rate_metric=fm,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=None,
        dwell_sec=None,
    )
    assert result.cutting_time is not None
    assert result.cutting_time.status == TimeComponentStatus.AVAILABLE
    # t = 100mm / 100 mm/min = 1 min = 60 s
    assert result.cutting_time.time_sec_min == pytest.approx(60.0, rel=1e-4)
    assert result.cutting_time.time_sec_max == pytest.approx(60.0, rel=1e-4)


def test_explicit_path_feed_range_returns_time_range():
    fm = _feed_metric(50.0, 200.0)
    result = compute_step_cycle_time(
        cutting_path_length_mm=100.0,
        cutting_path_source="USER_INPUT",
        feed_rate_metric=fm,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=None,
        dwell_sec=None,
    )
    assert result.cutting_time is not None
    assert result.cutting_time.status == TimeComponentStatus.AVAILABLE
    # Fastest: 100/200 mm/min = 0.5 min = 30 s
    assert result.cutting_time.time_sec_min == pytest.approx(30.0, rel=1e-4)
    # Slowest: 100/50 mm/min = 2 min = 120 s
    assert result.cutting_time.time_sec_max == pytest.approx(120.0, rel=1e-4)


def test_fastest_time_uses_max_feed():
    """FEED_RANGE_MIDPOINT_ASSUMED=NO — fastest corresponds to max feed."""
    fm = _feed_metric(50.0, 400.0)
    result = compute_step_cycle_time(
        cutting_path_length_mm=200.0,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=None,
        dwell_sec=None,
    )
    ct = result.cutting_time
    assert ct is not None
    # t_fastest = 200 / 400 * 60 = 30 s
    assert ct.time_sec_min == pytest.approx(30.0, rel=1e-4)


def test_slowest_time_uses_min_feed():
    fm = _feed_metric(50.0, 400.0)
    result = compute_step_cycle_time(
        cutting_path_length_mm=200.0,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=None,
        dwell_sec=None,
    )
    ct = result.cutting_time
    assert ct is not None
    # t_slowest = 200 / 50 * 60 = 240 s
    assert ct.time_sec_max == pytest.approx(240.0, rel=1e-4)


def test_no_midpoint_assumed():
    """Midpoint feed would give 60 s; actual range must be [30, 240]."""
    fm = _feed_metric(50.0, 400.0)
    result = compute_step_cycle_time(
        cutting_path_length_mm=200.0,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=None,
        dwell_sec=None,
    )
    ct = result.cutting_time
    assert ct is not None
    midpoint_feed = (50.0 + 400.0) / 2.0
    midpoint_time_sec = 200.0 / midpoint_feed * 60.0
    assert ct.time_sec_min != pytest.approx(midpoint_time_sec, rel=1e-3)
    assert ct.time_sec_max != pytest.approx(midpoint_time_sec, rel=1e-3)


# ---------------------------------------------------------------------------
# 7. Missing path → INSUFFICIENT_DATA
# ---------------------------------------------------------------------------

def test_missing_path_insufficient_data():
    fm = _feed_metric(100.0, 200.0)
    result = compute_step_cycle_time(
        cutting_path_length_mm=None,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=None,
        dwell_sec=None,
    )
    assert result.status == CycleTimeStatus.INSUFFICIENT_DATA
    assert result.cutting_time is not None
    assert result.cutting_time.status == TimeComponentStatus.INSUFFICIENT_DATA
    assert "cutting_path_length_mm" in result.cutting_time.missing_inputs
    assert "cutting_path_length_mm" in result.missing_inputs
    # No zero value exposed
    assert result.cutting_time.time_sec_min is None
    assert result.cutting_time.time_sec_max is None


# ---------------------------------------------------------------------------
# 8–9. Validation: negative and zero path rejected
# ---------------------------------------------------------------------------

def test_negative_path_rejected_via_api():
    resp = client.post(
        "/api/process-planning/plan",
        content=json.dumps(_plan_body(path_mm=-10.0)),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422


def test_zero_path_rejected_via_api():
    resp = client.post(
        "/api/process-planning/plan",
        content=json.dumps(_plan_body(path_mm=0.0)),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422


def test_non_finite_path_rejected_by_validator():
    """NaN / infinity rejected by Pydantic field validator."""
    from pydantic import ValidationError
    from backend.process_planning.plan_models import OperationStepRequest

    with pytest.raises(ValidationError):
        OperationStepRequest(
            step_id="OP10",
            sequence_number=10,
            operation="DRILLING",
            cutting_path_length_mm=float("inf"),
        )

    with pytest.raises(ValidationError):
        OperationStepRequest(
            step_id="OP10",
            sequence_number=10,
            operation="DRILLING",
            cutting_path_length_mm=float("nan"),
        )


# ---------------------------------------------------------------------------
# 10. Missing feed → INSUFFICIENT_DATA, no zero value
# ---------------------------------------------------------------------------

def test_missing_feed_insufficient_data():
    result = compute_step_cycle_time(
        cutting_path_length_mm=100.0,
        cutting_path_source=None,
        feed_rate_metric=None,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=None,
        dwell_sec=None,
    )
    assert result.status == CycleTimeStatus.INSUFFICIENT_DATA
    ct = result.cutting_time
    assert ct is not None
    assert ct.status == TimeComponentStatus.INSUFFICIENT_DATA
    # No zero placeholder
    assert ct.time_sec_min is None
    assert ct.time_sec_max is None


def test_feed_not_available_status_gives_insufficient():
    fm = _feed_metric(100.0, 200.0, status=MetricStatus.NOT_AVAILABLE)
    result = compute_step_cycle_time(
        cutting_path_length_mm=100.0,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=None,
        dwell_sec=None,
    )
    assert result.cutting_time is not None
    assert result.cutting_time.status == TimeComponentStatus.INSUFFICIENT_DATA
    assert result.cutting_time.time_sec_min is None


# ---------------------------------------------------------------------------
# 12–13. Dwell
# ---------------------------------------------------------------------------

def test_dwell_included_only_when_supplied():
    fm = _feed_metric(100.0, 200.0)
    result = compute_step_cycle_time(
        cutting_path_length_mm=100.0,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=None,
        dwell_sec=30.0,
    )
    assert result.dwell_time is not None
    assert result.dwell_time.status == TimeComponentStatus.AVAILABLE
    assert result.dwell_time.time_sec_min == pytest.approx(30.0, rel=1e-4)


def test_dwell_absent_no_guessed_component():
    fm = _feed_metric(100.0, 200.0)
    result = compute_step_cycle_time(
        cutting_path_length_mm=100.0,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=None,
        dwell_sec=None,
    )
    assert result.dwell_time is None
    assert all(c.component_type != "DWELL" for c in result.components)


def test_zero_dwell_not_added_as_component():
    """dwell_sec=0 must not create a dwell component (DWELL_TIME_GUESSED=NO)."""
    fm = _feed_metric(100.0, 200.0)
    result = compute_step_cycle_time(
        cutting_path_length_mm=100.0,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=None,
        dwell_sec=0.0,
    )
    assert result.dwell_time is None


# ---------------------------------------------------------------------------
# 14–16. Rapid time
# ---------------------------------------------------------------------------

def test_rapid_time_with_source_backed_haas_machine():
    """haas-vf-2ss has rapid_traverse_mpm=30.5 → validated source-backed value."""
    fm = _feed_metric(100.0, 200.0)
    result = compute_step_cycle_time(
        cutting_path_length_mm=100.0,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=500.0,
        machine_rapid_traverse_mpm=30.5,  # Haas VF-2SS catalog value
        dwell_sec=None,
    )
    assert result.rapid_time is not None
    assert result.rapid_time.status == TimeComponentStatus.AVAILABLE
    # t = 500mm / (30.5*1000 mm/min) * 60 s/min
    expected = 500.0 / (30.5 * 1000.0) * 60.0
    assert result.rapid_time.time_sec_min == pytest.approx(expected, rel=1e-3)


def test_rapid_missing_machine_rapid_is_insufficient():
    fm = _feed_metric(100.0, 200.0)
    result = compute_step_cycle_time(
        cutting_path_length_mm=100.0,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=500.0,
        machine_rapid_traverse_mpm=None,  # 13/15 machines don't have this
        dwell_sec=None,
    )
    assert result.rapid_time is not None
    assert result.rapid_time.status == TimeComponentStatus.INSUFFICIENT_DATA
    # No zero value
    assert result.rapid_time.time_sec_min is None
    assert "machine_rapid_traverse_mpm" in result.rapid_time.missing_inputs


def test_rapid_distance_absent_no_guessed_component():
    fm = _feed_metric(100.0, 200.0)
    result = compute_step_cycle_time(
        cutting_path_length_mm=100.0,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=30.5,
        dwell_sec=None,
    )
    assert result.rapid_time is None
    assert all(c.component_type != "RAPID" for c in result.components)


# ---------------------------------------------------------------------------
# 17–20. No geometry inference
# ---------------------------------------------------------------------------

def test_turning_pass_count_not_inferred_via_api():
    """TURNING_PASS_COUNT_INFERRED=NO — TURNING without path → INSUFFICIENT_DATA."""
    resp = client.post(
        "/api/process-planning/plan",
        content=json.dumps(_plan_body(operation="TURNING", path_mm=None)),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    step = data["steps"][0]
    ct = step.get("cycle_time")
    assert ct is not None
    assert ct["status"] == "INSUFFICIENT_DATA"


def test_drilling_travel_allowance_not_inferred():
    """DRILL_TRAVEL_ALLOWANCE_GUESSED=NO — no auto tip-allowance added."""
    resp = client.post(
        "/api/process-planning/plan",
        content=json.dumps(_plan_body(operation="DRILLING", path_mm=None)),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    step = data["steps"][0]
    ct = step.get("cycle_time")
    assert ct is not None
    assert ct["status"] == "INSUFFICIENT_DATA"
    assert ct["cutting_time"]["time_sec_min"] is None


def test_reaming_travel_allowance_not_inferred():
    """REAM_TRAVEL_ALLOWANCE_GUESSED=NO."""
    resp = client.post(
        "/api/process-planning/plan",
        content=json.dumps(_plan_body(operation="REAMING", path_mm=None)),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    step = data["steps"][0]
    ct = step.get("cycle_time")
    assert ct is not None
    assert ct["status"] == "INSUFFICIENT_DATA"


def test_milling_path_not_generated():
    """MILLING_PATH_GENERATION_IMPLEMENTED=NO — no automatic path computed from feature."""
    resp = client.post(
        "/api/process-planning/plan",
        content=json.dumps(_plan_body(operation="FACE_MILLING", path_mm=None)),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    step = data["steps"][0]
    ct = step.get("cycle_time")
    # If FACE_MILLING is NOT_SUPPORTED, cycle_time may be None — that also proves
    # no milling path was generated. If it is PLANNED/BLOCKED, must be INSUFFICIENT_DATA.
    if ct is not None:
        assert ct["status"] == "INSUFFICIENT_DATA"
        assert ct["cutting_time"]["time_sec_min"] is None


# ---------------------------------------------------------------------------
# 21–22. No guessed overhead times
# ---------------------------------------------------------------------------

def test_tool_change_time_not_guessed():
    """TOOL_CHANGE_TIME_GUESSED=NO — tool_change_time must always be null."""
    fm = _feed_metric(100.0, 200.0)
    result = compute_step_cycle_time(
        cutting_path_length_mm=100.0,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=None,
        dwell_sec=None,
    )
    assert result.tool_change_time is None
    assert all(c.component_type != "TOOL_CHANGE" for c in result.components)


def test_setup_time_not_guessed():
    """SETUP_TIME_MODEL_IMPLEMENTED=NO — no SETUP component."""
    fm = _feed_metric(100.0, 200.0)
    result = compute_step_cycle_time(
        cutting_path_length_mm=100.0,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=None,
        dwell_sec=None,
    )
    assert all(c.component_type != "SETUP" for c in result.components)


# ---------------------------------------------------------------------------
# 23. Known subtotal ≠ total cycle time
# ---------------------------------------------------------------------------

def test_known_subtotal_is_not_total():
    """KNOWN_SUBTOTAL_MISLABELED_AS_TOTAL=NO — total_cycle_time must be None."""
    fm = _feed_metric(100.0, 200.0)
    result = compute_step_cycle_time(
        cutting_path_length_mm=100.0,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=None,
        dwell_sec=None,
    )
    assert result.known_subtotal_sec_min is not None
    assert result.total_cycle_time is None
    # Serialized form must also show null
    serialized = result.model_dump()
    assert serialized["total_cycle_time"] is None


def test_known_subtotal_sum_of_available_components():
    fm = _feed_metric(100.0, 100.0)   # single value: 60 s
    result = compute_step_cycle_time(
        cutting_path_length_mm=100.0,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=500.0,
        machine_rapid_traverse_mpm=30.5,
        dwell_sec=10.0,
    )
    assert result.known_subtotal_sec_min is not None
    cutting_sec = 60.0
    rapid_sec = 500.0 / (30.5 * 1000.0) * 60.0
    dwell_sec = 10.0
    expected = cutting_sec + rapid_sec + dwell_sec
    assert result.known_subtotal_sec_min == pytest.approx(expected, rel=1e-3)


# ---------------------------------------------------------------------------
# 24. Cycle-time status does NOT alter planning status
# ---------------------------------------------------------------------------

def test_cycle_time_does_not_alter_planning_status():
    """CYCLE_TIME_AVAILABILITY_CHANGES_PLAN_STATUS=NO."""
    body_with_path = _plan_body(operation="DRILLING", path_mm=50.0)
    body_no_path = _plan_body(operation="DRILLING", path_mm=None)

    resp_with = client.post(
        "/api/process-planning/plan",
        content=json.dumps(body_with_path),
        headers={"Content-Type": "application/json"},
    )
    resp_without = client.post(
        "/api/process-planning/plan",
        content=json.dumps(body_no_path),
        headers={"Content-Type": "application/json"},
    )
    assert resp_with.status_code == 200
    assert resp_without.status_code == 200
    data_with = resp_with.json()
    data_without = resp_without.json()
    step_with = data_with["steps"][0]
    step_without = data_without["steps"][0]
    # Planning status must be identical regardless of path input
    assert step_with["planning_status"] == step_without["planning_status"]
    assert data_with["plan_status"] == data_without["plan_status"]


# ---------------------------------------------------------------------------
# 25. Plan-level total not from incomplete steps
# ---------------------------------------------------------------------------

def test_plan_level_counts_present():
    """Plan response must include cycle_time_{complete,partial,insufficient}_count."""
    resp = client.post(
        "/api/process-planning/plan",
        content=json.dumps(_plan_body()),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "cycle_time_complete_count" in data
    assert "cycle_time_partial_count" in data
    assert "cycle_time_insufficient_count" in data


def test_plan_level_total_not_from_incomplete():
    """total_cycle_time at step level must be None when not all components are known."""
    resp = client.post(
        "/api/process-planning/plan",
        content=json.dumps(_plan_body(path_mm=100.0)),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for step in data["steps"]:
        ct = step.get("cycle_time")
        if ct:
            assert ct["total_cycle_time"] is None


# ---------------------------------------------------------------------------
# 26. Deterministic repeatability
# ---------------------------------------------------------------------------

def test_deterministic_repeatability():
    fm = _feed_metric(80.0, 320.0)
    r1 = compute_step_cycle_time(
        cutting_path_length_mm=150.0,
        cutting_path_source="USER_INPUT",
        feed_rate_metric=fm,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=None,
        dwell_sec=None,
    )
    r2 = compute_step_cycle_time(
        cutting_path_length_mm=150.0,
        cutting_path_source="USER_INPUT",
        feed_rate_metric=fm,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=None,
        dwell_sec=None,
    )
    assert r1.cutting_time is not None
    assert r2.cutting_time is not None
    assert r1.cutting_time.time_sec_min == r2.cutting_time.time_sec_min
    assert r1.cutting_time.time_sec_max == r2.cutting_time.time_sec_max
    assert r1.status == r2.status


# ---------------------------------------------------------------------------
# 27. API serialization
# ---------------------------------------------------------------------------

def test_api_cycle_time_in_response():
    """cycle_time field must be present in each step's API response."""
    resp = client.post(
        "/api/process-planning/plan",
        content=json.dumps(_plan_body()),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["steps"]) >= 1
    for step in data["steps"]:
        assert "cycle_time" in step


def test_api_cycle_time_insufficient_when_no_path():
    resp = client.post(
        "/api/process-planning/plan",
        content=json.dumps(_plan_body(operation="DRILLING", path_mm=None)),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for step in data["steps"]:
        if step.get("cycle_time"):
            assert step["cycle_time"]["status"] == "INSUFFICIENT_DATA"
            assert step["cycle_time"]["cutting_time"]["time_sec_min"] is None


def test_negative_rapid_rejected_via_api():
    body = _plan_body()
    body["operations"][0]["rapid_distance_mm"] = -5.0
    resp = client.post(
        "/api/process-planning/plan",
        content=json.dumps(body),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422


def test_negative_dwell_rejected_via_api():
    body = _plan_body()
    body["operations"][0]["dwell_sec"] = -1.0
    resp = client.post(
        "/api/process-planning/plan",
        content=json.dumps(body),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 28. Private path protection
# ---------------------------------------------------------------------------

def test_private_path_not_in_response():
    """PRIVATE_LOCAL_PATH_VISIBLE=NO — no filesystem paths in cycle_time output."""
    resp = client.post(
        "/api/process-planning/plan",
        content=json.dumps(_plan_body(path_mm=100.0)),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    body_str = resp.text
    assert "C:\\" not in body_str
    assert "Users\\" not in body_str
    assert "/home/" not in body_str


# ---------------------------------------------------------------------------
# 29. EN/TR i18n parity
# ---------------------------------------------------------------------------

def test_en_tr_i18n_parity():
    """EN_RUNTIME_I18N=PASS TR_RUNTIME_I18N=PASS — both locales must have all keys."""
    import importlib
    en_mod = importlib.import_module("backend.i18n.en") if False else None  # noqa: F841
    # Read via filesystem
    import ast
    import pathlib
    base = pathlib.Path(__file__).parents[3] / "frontend" / "app" / "src" / "i18n"
    en_src = (base / "en.ts").read_text(encoding="utf-8")
    tr_src = (base / "tr.ts").read_text(encoding="utf-8")

    cycle_time_keys = [
        "ppTimeAnalysis", "ppCycleTime", "ppCalculatedCuttingTime",
        "ppKnownSubtotal", "ppTotalCycleTime", "ppCycleTimeComplete",
        "ppCycleTimePartial", "ppCycleTimeInsuffData", "ppCuttingPathLength",
        "ppRapidDistance", "ppRapidTime", "ppDwellTime", "ppToolChangeTime",
        "ppExplicitInputsOnly", "ppCuttingOnly", "ppPathLengthRequired",
        "ppFeedRateUnavailable", "ppRapidDataUnavailable",
    ]
    for key in cycle_time_keys:
        assert key in en_src, f"EN missing key: {key}"
        assert key in tr_src, f"TR missing key: {key}"


# ---------------------------------------------------------------------------
# Scope and status correctness
# ---------------------------------------------------------------------------

def test_scope_cutting_only_when_no_extras():
    fm = _feed_metric(100.0, 200.0)
    result = compute_step_cycle_time(
        cutting_path_length_mm=100.0,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=None,
        dwell_sec=None,
    )
    assert result.scope == CycleTimeScope.CUTTING_ONLY


def test_scope_cutting_plus_noncutting_when_rapid_provided():
    fm = _feed_metric(100.0, 200.0)
    result = compute_step_cycle_time(
        cutting_path_length_mm=100.0,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=200.0,
        machine_rapid_traverse_mpm=30.5,
        dwell_sec=None,
    )
    assert result.scope == CycleTimeScope.CUTTING_PLUS_EXPLICIT_NONCUTTING


def test_complete_status_when_cutting_available():
    fm = _feed_metric(100.0, 200.0)
    result = compute_step_cycle_time(
        cutting_path_length_mm=100.0,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=None,
        machine_rapid_traverse_mpm=None,
        dwell_sec=None,
    )
    assert result.status == CycleTimeStatus.COMPLETE


def test_partial_status_when_cutting_ok_but_rapid_missing_rate():
    fm = _feed_metric(100.0, 200.0)
    result = compute_step_cycle_time(
        cutting_path_length_mm=100.0,
        cutting_path_source=None,
        feed_rate_metric=fm,
        rapid_distance_mm=200.0,
        machine_rapid_traverse_mpm=None,  # no rapid rate
        dwell_sec=None,
    )
    assert result.status == CycleTimeStatus.PARTIAL
    assert result.cutting_time is not None
    assert result.cutting_time.status == TimeComponentStatus.AVAILABLE
    assert result.rapid_time is not None
    assert result.rapid_time.status == TimeComponentStatus.INSUFFICIENT_DATA
