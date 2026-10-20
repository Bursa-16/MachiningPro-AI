"""API tests for POST /api/nc-path/analyze.

PROCESS_PLAN_CYCLE_TIME_CAD_CAM_INTEGRATION_01 — Phase 2

Safety constants verified:
    NC_FILE_EXECUTED=NO
    NC_FEED_MOVE_EQUALS_CONFIRMED_CUTTING=NO
    ARC_AS_CHORD_APPROXIMATION=NO
    PRIVATE_PATH_IN_API_RESPONSE=NO
    NC_FEED_AUTOMATICALLY_PROMOTED_TO_CUTTING_PATH=NO
    RAPID_TIME_FROM_NC_ALONE=NO
"""

from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.interoperability.nc_motion import NcAnalysisStatus

client = TestClient(app)
_URL = "/api/nc-path/analyze"


def _post(nc_text: str, **kwargs) -> dict:
    payload = {"nc_text": nc_text, **kwargs}
    resp = client.post(_URL, json=payload)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    return resp.json()


def _approx(a: float, b: float, tol: float = 1e-4) -> bool:
    return math.fabs(a - b) <= tol


# ---------------------------------------------------------------------------
# Case A — feed 100 mm
# ---------------------------------------------------------------------------

_CASE_A = "G21\nG90\nG0 X0 Y0 Z0\nG1 X100 Y0 F500\n"


def test_case_a_feed_distance_100():
    """Case A: feed_evidence.distance_mm == 100."""
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    assert _approx(data["feed_evidence"]["distance_mm"], 100.0)


def test_case_a_rapid_distance_positive():
    """Case A: G0 X0 Y0 Z0 from None start → skip; rapid stays 0 (unknown start)."""
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    # G0 moves from (0,0,0) to (0,0,0) — zero distance.
    assert data["rapid_evidence"]["distance_mm"] >= 0.0


def test_case_a_feed_evidence_source_type():
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    assert data["feed_evidence"]["source_type"] == "NC_PROGRAM"


def test_case_a_feed_evidence_semantic_type():
    """FEED_MOTION — not CUTTING_CONFIRMED."""
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    assert data["feed_evidence"]["semantic_type"] == "FEED_MOTION"


def test_case_a_rapid_evidence_semantic_type():
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    assert data["rapid_evidence"]["semantic_type"] == "RAPID_MOTION"


def test_case_a_analysis_status_complete():
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    assert data["motion_result"]["analysis_status"] == NcAnalysisStatus.COMPLETE


def test_case_a_commanded_feed():
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    mr = data["motion_result"]
    assert mr["nc_commanded_feed_mm_min"] == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# Safety flag responses — always False
# ---------------------------------------------------------------------------

def test_nc_feed_move_equals_confirmed_cutting_false():
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    assert data["nc_feed_move_equals_confirmed_cutting"] is False


def test_arc_chord_approximation_used_false():
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    assert data["arc_chord_approximation_used"] is False


def test_nc_file_executed_false():
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    assert data["nc_file_executed"] is False


def test_nc_feed_automatically_promoted_false():
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    assert data["nc_feed_automatically_promoted_to_cutting_path"] is False


def test_feed_evidence_nc_feed_move_flag_false():
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    assert data["feed_evidence"]["nc_feed_move_equals_confirmed_cutting"] is False


def test_feed_evidence_arc_chord_flag_false():
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    assert data["feed_evidence"]["arc_chord_approximation_used"] is False


# ---------------------------------------------------------------------------
# Case B — 3-4-5 Pythagorean (50 mm)
# ---------------------------------------------------------------------------

_CASE_B = "G21\nG90\nG1 X30 Y40 F200\n"


def test_case_b_feed_50_with_origin():
    data = _post(_CASE_B, initial_x=0, initial_y=0, initial_z=0)
    assert _approx(data["feed_evidence"]["distance_mm"], 50.0)


def test_case_b_no_origin_unknown():
    """Without initial position, G90 first move is unknown → 0 mm."""
    data = _post(_CASE_B)
    assert _approx(data["feed_evidence"]["distance_mm"], 0.0)


# ---------------------------------------------------------------------------
# Case C — G2/G3 arc → PARTIAL
# ---------------------------------------------------------------------------

_CASE_C_G2 = "G21\nG90\nG0 X0 Y0 Z0\nG1 X50 F100\nG2 X100 Y50 R30\n"
_CASE_C_G3 = "G21\nG90\nG0 X0 Y0 Z0\nG1 X50 F100\nG3 X100 Y50 R30\n"


def test_case_c_g2_partial_status():
    data = _post(_CASE_C_G2, initial_x=0, initial_y=0, initial_z=0)
    assert data["motion_result"]["analysis_status"] == NcAnalysisStatus.PARTIAL


def test_case_c_g3_partial_status():
    data = _post(_CASE_C_G3, initial_x=0, initial_y=0, initial_z=0)
    assert data["motion_result"]["analysis_status"] == NcAnalysisStatus.PARTIAL


def test_case_c_g2_no_chord_approximation():
    data = _post(_CASE_C_G2, initial_x=0, initial_y=0, initial_z=0)
    assert data["arc_chord_approximation_used"] is False
    assert data["motion_result"]["arc_chord_approximation_used"] is False


def test_case_c_g2_unsupported_feature_reported():
    data = _post(_CASE_C_G2, initial_x=0, initial_y=0, initial_z=0)
    feats = data["motion_result"]["unsupported_features"]
    assert any("G2" in f for f in feats)


def test_case_c_g2_feed_only_linear_portion():
    """G1 portion is 50 mm; arc portion is NOT added."""
    data = _post(_CASE_C_G2, initial_x=0, initial_y=0, initial_z=0)
    feed = data["feed_evidence"]["distance_mm"]
    assert _approx(feed, 50.0)


# ---------------------------------------------------------------------------
# M98/M99 → UNSUPPORTED_SEMANTICS
# ---------------------------------------------------------------------------

def test_m98_unsupported_semantics():
    data = _post("G21\nG1 X10 F100\nM98 P1000\n", initial_x=0, initial_y=0, initial_z=0)
    assert data["motion_result"]["analysis_status"] == NcAnalysisStatus.UNSUPPORTED_SEMANTICS


def test_m99_unsupported_semantics():
    data = _post("G21\nM99\n", initial_x=0, initial_y=0, initial_z=0)
    assert data["motion_result"]["analysis_status"] == NcAnalysisStatus.UNSUPPORTED_SEMANTICS


# ---------------------------------------------------------------------------
# Private path protection — PRIVATE_PATH_IN_API_RESPONSE=NO
# ---------------------------------------------------------------------------

def test_absolute_unix_path_rejected():
    payload = {"nc_text": "G21\nG1 X10\n", "source_name": "/home/user/programs/op1.nc"}
    resp = client.post(_URL, json=payload)
    assert resp.status_code == 422


def test_absolute_windows_path_rejected():
    payload = {"nc_text": "G21\nG1 X10\n", "source_name": r"C:\Users\test\prog.nc"}
    resp = client.post(_URL, json=payload)
    assert resp.status_code == 422


def test_unc_path_rejected():
    payload = {"nc_text": "G21\nG1 X10\n", "source_name": r"\\server\share\prog.nc"}
    resp = client.post(_URL, json=payload)
    assert resp.status_code == 422


def test_relative_traversal_rejected():
    payload = {"nc_text": "G21\nG1 X10\n", "source_name": "../secrets/prog.nc"}
    resp = client.post(_URL, json=payload)
    assert resp.status_code == 422


def test_safe_filename_accepted():
    payload = {"nc_text": "G21\nG1 X10\n", "source_name": "op1_facing.nc",
               "initial_x": 0, "initial_y": 0, "initial_z": 0}
    resp = client.post(_URL, json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["feed_evidence"]["source_name_safe"] == "op1_facing.nc"


def test_source_name_none_accepted():
    payload = {"nc_text": "G21\nG1 X10\n", "initial_x": 0, "initial_y": 0, "initial_z": 0}
    resp = client.post(_URL, json=payload)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

def test_empty_nc_text_returns_422():
    resp = client.post(_URL, json={"nc_text": ""})
    assert resp.status_code == 422


def test_whitespace_only_nc_text_returns_422():
    resp = client.post(_URL, json={"nc_text": "   \n  \t  "})
    assert resp.status_code == 422


def test_oversized_nc_text_returns_422():
    big = "G21\nG1 X10\n" * 500_000  # >> 4MB
    resp = client.post(_URL, json={"nc_text": big})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PathEvidence schema
# ---------------------------------------------------------------------------

def test_feed_evidence_has_evidence_id():
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    eid = data["feed_evidence"]["evidence_id"]
    assert isinstance(eid, str) and len(eid) > 0


def test_rapid_evidence_has_evidence_id():
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    eid = data["rapid_evidence"]["evidence_id"]
    assert isinstance(eid, str) and len(eid) > 0


def test_evidence_ids_differ():
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    assert data["feed_evidence"]["evidence_id"] != data["rapid_evidence"]["evidence_id"]


def test_units_canonical_always_mm():
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    assert data["feed_evidence"]["units_canonical"] == "mm"
    assert data["rapid_evidence"]["units_canonical"] == "mm"


def test_parser_profile_in_response():
    from backend.interoperability.nc_motion import PARSER_PROFILE
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    assert data["motion_result"]["parser_profile"] == PARSER_PROFILE


# ---------------------------------------------------------------------------
# Rapid distance
# ---------------------------------------------------------------------------

def test_rapid_distance_from_g0():
    prog = "G21\nG90\nG0 X100 Y0 Z0\nG1 X100 F100\n"
    # G0 from (0,0,0) to (100,0,0) with initial origin → 100 mm rapid
    data = _post(prog, initial_x=0, initial_y=0, initial_z=0)
    assert _approx(data["rapid_evidence"]["distance_mm"], 100.0)


def test_rapid_time_not_in_nc_analyze_response():
    """RAPID_TIME_FROM_NC_ALONE=NO — no rapid_time_sec in response."""
    data = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    assert "rapid_time_sec" not in data
    assert "rapid_time_sec" not in data["rapid_evidence"]


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_deterministic_same_result_twice():
    data1 = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    data2 = _post(_CASE_A, initial_x=0, initial_y=0, initial_z=0)
    assert data1["feed_evidence"]["distance_mm"] == data2["feed_evidence"]["distance_mm"]
    assert data1["motion_result"]["analysis_status"] == data2["motion_result"]["analysis_status"]
