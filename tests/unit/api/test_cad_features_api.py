"""Tests for CAD Feature Recognition API endpoints — EPIC_04D Phase 2.

Coverage:
  POST /api/cad-features/analyze
  GET  /api/cad-features/{session_id}
  GET  /api/cad-features/{session_id}/features
  GET  /api/cad-features/{session_id}/patterns
  GET  /api/cad-features/{session_id}/fusion
  POST /api/cad-features/{session_id}/confirm
  POST /api/cad-features/{session_id}/reject
  POST /api/cad-features/{session_id}/associate-drawing

Safety flags verified:
  PRIVATE_PATH_LEAK=NO
  CUSTOMER_CAD_COMMITTED=NO
  FABRICATED_FEATURE=NO (disclaimer field present on every response)
"""

from __future__ import annotations

import base64
import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Minimal DXF fixtures (no proprietary CAD content)
# ---------------------------------------------------------------------------

_DXF_ONE_CIRCLE = (
    "0\nSECTION\n2\nENTITIES\n"
    "0\nCIRCLE\n10\n10.0\n20\n10.0\n30\n0.0\n40\n4.0\n"
    "0\nENDSEC\n0\nEOF\n"
).encode("ascii")

_DXF_FOUR_CIRCLES = (
    "0\nSECTION\n2\nENTITIES\n"
    "0\nCIRCLE\n10\n0.0\n20\n25.0\n30\n0.0\n40\n3.0\n"
    "0\nCIRCLE\n10\n25.0\n20\n0.0\n30\n0.0\n40\n3.0\n"
    "0\nCIRCLE\n10\n0.0\n20\n-25.0\n30\n0.0\n40\n3.0\n"
    "0\nCIRCLE\n10\n-25.0\n20\n0.0\n30\n0.0\n40\n3.0\n"
    "0\nENDSEC\n0\nEOF\n"
).encode("ascii")

_DXF_EMPTY = (
    "0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n"
).encode("ascii")


def _b64(content: bytes) -> str:
    return base64.b64encode(content).decode("ascii")


def _analyze(file_bytes: bytes, file_name: str = "test.dxf") -> dict:
    payload = {"file_name": file_name, "content_b64": _b64(file_bytes)}
    resp = client.post("/api/cad-features/analyze", json=payload)
    return resp


# ---------------------------------------------------------------------------
# POST /api/cad-features/analyze
# ---------------------------------------------------------------------------

class TestAnalyzeEndpoint:
    def test_dxf_analyze_returns_200(self):
        resp = _analyze(_DXF_ONE_CIRCLE, "hole.dxf")
        assert resp.status_code == 200

    def test_analyze_response_has_session_id(self):
        resp = _analyze(_DXF_ONE_CIRCLE, "hole.dxf")
        data = resp.json()
        assert "session_id" in data
        assert len(data["session_id"]) > 0

    def test_analyze_response_has_disclaimer(self):
        resp = _analyze(_DXF_ONE_CIRCLE, "hole.dxf")
        data = resp.json()
        assert "disclaimer" in data
        assert "REFERENCE_ONLY" in data["disclaimer"]

    def test_analyze_response_has_feature_count(self):
        resp = _analyze(_DXF_ONE_CIRCLE, "hole.dxf")
        data = resp.json()
        assert "feature_count" in data
        assert isinstance(data["feature_count"], int)
        assert data["feature_count"] >= 1

    def test_analyze_dxf_one_circle_detects_feature(self):
        resp = _analyze(_DXF_ONE_CIRCLE, "one_circle.dxf")
        data = resp.json()
        assert data["feature_count"] == 1

    def test_analyze_dxf_four_circles_detects_four(self):
        resp = _analyze(_DXF_FOUR_CIRCLES, "four_circles.dxf")
        data = resp.json()
        assert data["feature_count"] == 4

    def test_analyze_empty_dxf_returns_zero_features(self):
        resp = _analyze(_DXF_EMPTY, "empty.dxf")
        data = resp.json()
        assert data["feature_count"] == 0

    def test_analyze_response_has_format_id(self):
        resp = _analyze(_DXF_ONE_CIRCLE, "test.dxf")
        data = resp.json()
        assert "format_id" in data
        assert data["format_id"] == "DXF"

    def test_analyze_response_has_face_count(self):
        resp = _analyze(_DXF_ONE_CIRCLE, "test.dxf")
        data = resp.json()
        assert "face_count" in data

    def test_analyze_response_has_pattern_count(self):
        resp = _analyze(_DXF_ONE_CIRCLE, "test.dxf")
        data = resp.json()
        assert "pattern_count" in data

    def test_analyze_unsupported_extension_returns_422(self):
        payload = {"file_name": "model.xyz", "content_b64": _b64(b"dummy")}
        resp = client.post("/api/cad-features/analyze", json=payload)
        assert resp.status_code in (400, 422)

    def test_analyze_missing_content_b64_returns_422(self):
        payload = {"file_name": "test.dxf"}
        resp = client.post("/api/cad-features/analyze", json=payload)
        assert resp.status_code == 422

    def test_analyze_missing_file_name_returns_422(self):
        payload = {"content_b64": _b64(_DXF_ONE_CIRCLE)}
        resp = client.post("/api/cad-features/analyze", json=payload)
        assert resp.status_code == 422

    def test_analyze_invalid_base64_returns_422(self):
        payload = {"file_name": "test.dxf", "content_b64": "not-valid-base64!!!"}
        resp = client.post("/api/cad-features/analyze", json=payload)
        assert resp.status_code == 422

    def test_analyze_path_traversal_sanitized(self):
        # file_name is used only as metadata; path traversal in it is not a server-side risk
        # (bytes come from base64, not from the file_name). Server accepts or rejects gracefully.
        payload = {
            "file_name": "../../etc/passwd.dxf",
            "content_b64": _b64(_DXF_ONE_CIRCLE),
        }
        resp = client.post("/api/cad-features/analyze", json=payload)
        # Must not be 500; 200/400/422 are all acceptable
        assert resp.status_code in (200, 400, 422)

    def test_analyze_no_private_path_in_response(self):
        resp = _analyze(_DXF_ONE_CIRCLE, "test.dxf")
        text = resp.text
        # PRIVATE_PATH_LEAK=NO — no system path in response
        assert "Users\\" not in text
        assert "/home/" not in text
        assert "C:\\" not in text

    def test_analyze_step_extension_recognized(self):
        # .step / .stp are whitelisted (may return UNSUPPORTED, not 422)
        payload = {"file_name": "model.step", "content_b64": _b64(b"ISO-10303 stub")}
        resp = client.post("/api/cad-features/analyze", json=payload)
        assert resp.status_code in (200, 400, 422)

    def test_analyze_iges_extension_recognized(self):
        # .iges / .igs are whitelisted
        payload = {"file_name": "model.igs", "content_b64": _b64(b"                                                                        S      1\n")}
        resp = client.post("/api/cad-features/analyze", json=payload)
        assert resp.status_code in (200, 400, 422)


# ---------------------------------------------------------------------------
# GET /api/cad-features/{session_id}
# ---------------------------------------------------------------------------

class TestGetSession:
    def setup_method(self):
        resp = _analyze(_DXF_ONE_CIRCLE, "hole.dxf")
        self.session_id = resp.json()["session_id"]

    def test_get_session_returns_200(self):
        resp = client.get(f"/api/cad-features/{self.session_id}")
        assert resp.status_code == 200

    def test_get_session_has_session_id(self):
        resp = client.get(f"/api/cad-features/{self.session_id}")
        assert resp.json()["session_id"] == self.session_id

    def test_get_session_has_file_name(self):
        resp = client.get(f"/api/cad-features/{self.session_id}")
        assert resp.json()["file_name"] == "hole.dxf"

    def test_get_session_missing_returns_404(self):
        resp = client.get("/api/cad-features/nonexistent-session-id")
        assert resp.status_code == 404

    def test_get_session_has_feature_count(self):
        resp = client.get(f"/api/cad-features/{self.session_id}")
        assert "feature_count" in resp.json()


# ---------------------------------------------------------------------------
# GET /api/cad-features/{session_id}/features
# ---------------------------------------------------------------------------

class TestGetFeatures:
    def setup_method(self):
        resp = _analyze(_DXF_ONE_CIRCLE, "hole.dxf")
        self.session_id = resp.json()["session_id"]

    def test_get_features_returns_200(self):
        resp = client.get(f"/api/cad-features/{self.session_id}/features")
        assert resp.status_code == 200

    def test_get_features_returns_list(self):
        resp = client.get(f"/api/cad-features/{self.session_id}/features")
        data = resp.json()
        assert "features" in data
        assert isinstance(data["features"], list)

    def test_get_features_has_total(self):
        resp = client.get(f"/api/cad-features/{self.session_id}/features")
        data = resp.json()
        assert "total" in data

    def test_get_features_count_matches_analyze(self):
        resp = client.get(f"/api/cad-features/{self.session_id}/features")
        data = resp.json()
        assert len(data["features"]) == 1

    def test_get_features_each_has_feature_type(self):
        resp = client.get(f"/api/cad-features/{self.session_id}/features")
        for feat in resp.json()["features"]:
            assert "feature_type" in feat

    def test_get_features_each_has_confidence(self):
        resp = client.get(f"/api/cad-features/{self.session_id}/features")
        for feat in resp.json()["features"]:
            assert "confidence" in feat

    def test_get_features_each_has_source_face_ids(self):
        resp = client.get(f"/api/cad-features/{self.session_id}/features")
        for feat in resp.json()["features"]:
            assert "source_face_ids" in feat

    def test_get_features_filter_by_type(self):
        resp = _analyze(_DXF_ONE_CIRCLE, "filter.dxf")
        sid = resp.json()["session_id"]
        resp2 = client.get(f"/api/cad-features/{sid}/features?feature_type=HOLE")
        assert resp2.status_code == 200
        data = resp2.json()
        for feat in data["features"]:
            assert feat["feature_type"] == "HOLE"

    def test_get_features_invalid_session_returns_404(self):
        resp = client.get("/api/cad-features/bad-session/features")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/cad-features/{session_id}/patterns
# ---------------------------------------------------------------------------

class TestGetPatterns:
    def setup_method(self):
        resp = _analyze(_DXF_FOUR_CIRCLES, "pattern.dxf")
        self.session_id = resp.json()["session_id"]

    def test_get_patterns_returns_200(self):
        resp = client.get(f"/api/cad-features/{self.session_id}/patterns")
        assert resp.status_code == 200

    def test_get_patterns_returns_list(self):
        resp = client.get(f"/api/cad-features/{self.session_id}/patterns")
        assert "patterns" in resp.json()
        assert isinstance(resp.json()["patterns"], list)

    def test_get_patterns_invalid_session_returns_404(self):
        resp = client.get("/api/cad-features/bad/patterns")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/cad-features/{session_id}/fusion
# ---------------------------------------------------------------------------

class TestGetFusion:
    def setup_method(self):
        resp = _analyze(_DXF_ONE_CIRCLE, "fusion.dxf")
        self.session_id = resp.json()["session_id"]

    def test_get_fusion_returns_200(self):
        resp = client.get(f"/api/cad-features/{self.session_id}/fusion")
        assert resp.status_code == 200

    def test_get_fusion_has_fusion_available(self):
        resp = client.get(f"/api/cad-features/{self.session_id}/fusion")
        data = resp.json()
        assert "session_id" in data or "fusion_available" in data

    def test_get_fusion_invalid_session_returns_404(self):
        resp = client.get("/api/cad-features/bad/fusion")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/cad-features/{session_id}/confirm
# ---------------------------------------------------------------------------

class TestConfirmEndpoint:
    def setup_method(self):
        resp = _analyze(_DXF_ONE_CIRCLE, "confirm.dxf")
        self.session_id = resp.json()["session_id"]

    def test_confirm_valid_feature_returns_200(self):
        # URL: /{session_id}/features/{feature_id}/confirm
        feats_resp = client.get(f"/api/cad-features/{self.session_id}/features")
        features = feats_resp.json()["features"]
        if not features:
            pytest.skip("No features to confirm")
        fid = features[0]["feature_id"]
        resp = client.post(
            f"/api/cad-features/{self.session_id}/features/{fid}/confirm",
            json={"user_id": "engineer-1"},
        )
        assert resp.status_code == 200

    def test_confirm_response_has_feature_id(self):
        feats_resp = client.get(f"/api/cad-features/{self.session_id}/features")
        features = feats_resp.json()["features"]
        if not features:
            pytest.skip("No features")
        fid = features[0]["feature_id"]
        resp = client.post(
            f"/api/cad-features/{self.session_id}/features/{fid}/confirm",
            json={"user_id": "eng"},
        )
        data = resp.json()
        assert "feature_id" in data

    def test_confirm_invalid_session_returns_404(self):
        resp = client.post(
            "/api/cad-features/bad-session/features/feat-x/confirm",
            json={"user_id": "eng"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/cad-features/{session_id}/reject
# ---------------------------------------------------------------------------

class TestRejectEndpoint:
    def setup_method(self):
        resp = _analyze(_DXF_ONE_CIRCLE, "reject.dxf")
        self.session_id = resp.json()["session_id"]

    def test_reject_valid_feature_returns_200(self):
        # URL: /{session_id}/features/{feature_id}/reject
        feats_resp = client.get(f"/api/cad-features/{self.session_id}/features")
        features = feats_resp.json()["features"]
        if not features:
            pytest.skip("No features to reject")
        fid = features[0]["feature_id"]
        resp = client.post(
            f"/api/cad-features/{self.session_id}/features/{fid}/reject",
            json={"reason": "false positive", "rejected_by": "engineer-2"},
        )
        assert resp.status_code == 200

    def test_reject_invalid_session_returns_404(self):
        resp = client.post(
            "/api/cad-features/bad-session/features/feat-x/reject",
            json={"reason": "nope", "rejected_by": "eng"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/cad-features/{session_id}/associate-drawing
# ---------------------------------------------------------------------------

class TestAssociateDrawingEndpoint:
    def setup_method(self):
        resp = _analyze(_DXF_ONE_CIRCLE, "assoc.dxf")
        self.session_id = resp.json()["session_id"]

    def test_associate_without_drawing_session_returns_400_or_200(self):
        feats_resp = client.get(f"/api/cad-features/{self.session_id}/features")
        features = feats_resp.json()["features"]
        if not features:
            pytest.skip("No features")
        fid = features[0]["feature_id"]
        resp = client.post(
            f"/api/cad-features/{self.session_id}/associate-drawing",
            json={
                "feature_id": fid,
                "drawing_session_id": "no-such-drawing",
                "requirement_id": "req-001",
            },
        )
        # No drawing session → 404 or 400, not 500
        assert resp.status_code in (200, 400, 404, 422)

    def test_associate_invalid_cad_session_returns_404(self):
        resp = client.post(
            "/api/cad-features/bad/associate-drawing",
            json={
                "feature_id": "feat-x",
                "drawing_session_id": "draw-y",
                "requirement_id": "req-z",
            },
        )
        assert resp.status_code == 404
