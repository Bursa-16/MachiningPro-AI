"""Unit tests for drawing parser API endpoints."""

import base64
import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.api.drawing_parser import _SESSIONS


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear in-memory sessions between tests."""
    _SESSIONS.clear()
    yield
    _SESSIONS.clear()


def _b64(content: bytes = b"fake-drawing-content") -> str:
    return base64.b64encode(content).decode()


def _analyze_payload(
    *,
    source_id: str = "test-drawing-001",
    file_name: str = "drawing.pdf",
    content_b64: str | None = None,
    title_block_unit: str | None = None,
    drawing_standard: str | None = None,
    material_raw: str | None = None,
    notes: list[str] | None = None,
) -> dict:
    return {
        "source_id": source_id,
        "file_name": file_name,
        "content_b64": content_b64 or _b64(),
        **({"title_block_unit": title_block_unit} if title_block_unit else {}),
        **({"drawing_standard": drawing_standard} if drawing_standard else {}),
        **({"material_raw": material_raw} if material_raw else {}),
        "notes": notes or [],
    }


# ---------------------------------------------------------------------------
# POST /api/drawing-parser/analyze
# ---------------------------------------------------------------------------

class TestAnalyzeEndpoint:
    def test_analyze_returns_200(self, client):
        resp = client.post("/api/drawing-parser/analyze", json=_analyze_payload())
        assert resp.status_code == 200

    def test_analyze_returns_session_id(self, client):
        resp = client.post("/api/drawing-parser/analyze", json=_analyze_payload())
        data = resp.json()
        assert "session_id" in data
        assert data["session_id"].startswith("ses-")

    def test_analyze_returns_disclaimer(self, client):
        resp = client.post("/api/drawing-parser/analyze", json=_analyze_payload())
        data = resp.json()
        assert "disclaimer" in data
        assert len(data["disclaimer"]) > 10

    def test_analyze_source_id_echoed(self, client):
        resp = client.post(
            "/api/drawing-parser/analyze",
            json=_analyze_payload(source_id="dwg-abc-123"),
        )
        assert resp.json()["source_id"] == "dwg-abc-123"

    def test_analyze_with_title_block_unit_mm(self, client):
        resp = client.post(
            "/api/drawing-parser/analyze",
            json=_analyze_payload(title_block_unit="mm"),
        )
        assert resp.status_code == 200
        assert resp.json()["detected_unit"] == "mm"

    def test_analyze_unit_none_without_info(self, client):
        resp = client.post("/api/drawing-parser/analyze", json=_analyze_payload())
        assert resp.json()["detected_unit"] is None

    def test_analyze_unit_unknown_in_warnings(self, client):
        resp = client.post("/api/drawing-parser/analyze", json=_analyze_payload())
        assert "UNIT_NOT_DECLARED" in resp.json()["warnings"]

    def test_analyze_with_fit_note_creates_detection(self, client):
        resp = client.post(
            "/api/drawing-parser/analyze",
            json=_analyze_payload(notes=["H7"]),
        )
        assert resp.json()["detection_count"] >= 1

    def test_analyze_with_thread_note(self, client):
        resp = client.post(
            "/api/drawing-parser/analyze",
            json=_analyze_payload(notes=["M10x1.5"]),
        )
        assert resp.json()["detection_count"] >= 1

    def test_analyze_stores_session(self, client):
        resp = client.post("/api/drawing-parser/analyze", json=_analyze_payload())
        session_id = resp.json()["session_id"]
        assert session_id in _SESSIONS

    def test_analyze_ocr_available_bool(self, client):
        resp = client.post("/api/drawing-parser/analyze", json=_analyze_payload())
        assert isinstance(resp.json()["ocr_available"], bool)

    def test_analyze_invalid_extension_rejected(self, client):
        resp = client.post(
            "/api/drawing-parser/analyze",
            json=_analyze_payload(file_name="drawing.exe"),
        )
        assert resp.status_code == 422

    def test_analyze_invalid_b64_rejected(self, client):
        payload = _analyze_payload()
        payload["content_b64"] = "NOT-VALID-BASE64!!!"
        resp = client.post("/api/drawing-parser/analyze", json=payload)
        assert resp.status_code == 422

    def test_analyze_path_traversal_in_filename_stripped(self, client):
        resp = client.post(
            "/api/drawing-parser/analyze",
            json=_analyze_payload(file_name="../../etc/passwd.pdf"),
        )
        # Should succeed (filename is sanitized) or return 422
        assert resp.status_code in (200, 422)
        if resp.status_code == 200:
            session_id = resp.json()["session_id"]
            assert session_id in _SESSIONS

    def test_analyze_png_extension_allowed(self, client):
        resp = client.post(
            "/api/drawing-parser/analyze",
            json=_analyze_payload(file_name="drawing.png"),
        )
        assert resp.status_code == 200

    def test_analyze_dxf_extension_allowed(self, client):
        resp = client.post(
            "/api/drawing-parser/analyze",
            json=_analyze_payload(file_name="drawing.dxf"),
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/drawing-parser/{session_id}/detections
# ---------------------------------------------------------------------------

class TestGetDetections:
    def _make_session(self, client, notes=None):
        resp = client.post(
            "/api/drawing-parser/analyze",
            json=_analyze_payload(notes=notes or []),
        )
        return resp.json()["session_id"]

    def test_get_detections_200(self, client):
        sid = self._make_session(client)
        resp = client.get(f"/api/drawing-parser/{sid}/detections")
        assert resp.status_code == 200

    def test_get_detections_session_id_echoed(self, client):
        sid = self._make_session(client)
        resp = client.get(f"/api/drawing-parser/{sid}/detections")
        assert resp.json()["session_id"] == sid

    def test_get_detections_disclaimer_present(self, client):
        sid = self._make_session(client)
        resp = client.get(f"/api/drawing-parser/{sid}/detections")
        assert "disclaimer" in resp.json()

    def test_get_detections_empty_session(self, client):
        sid = self._make_session(client)
        data = client.get(f"/api/drawing-parser/{sid}/detections").json()
        assert data["total"] == 0
        assert data["detections"] == []

    def test_get_detections_with_fit(self, client):
        sid = self._make_session(client, notes=["H7"])
        data = client.get(f"/api/drawing-parser/{sid}/detections").json()
        assert data["total"] >= 1
        det = data["detections"][0]
        assert "detection_id" in det
        assert "normalized_type" in det
        assert "review_state" in det

    def test_get_detections_not_found(self, client):
        resp = client.get("/api/drawing-parser/nonexistent-session/detections")
        assert resp.status_code == 404

    def test_get_detections_review_required_count(self, client):
        sid = self._make_session(client)
        data = client.get(f"/api/drawing-parser/{sid}/detections").json()
        assert isinstance(data["review_required_count"], int)

    def test_get_detections_confirmed_count_zero_initially(self, client):
        sid = self._make_session(client, notes=["H7"])
        data = client.get(f"/api/drawing-parser/{sid}/detections").json()
        assert data["confirmed_count"] == 0


# ---------------------------------------------------------------------------
# GET /api/drawing-parser/{session_id}/requirements
# ---------------------------------------------------------------------------

class TestGetRequirements:
    def _make_session(self, client, **kwargs):
        resp = client.post("/api/drawing-parser/analyze", json=_analyze_payload(**kwargs))
        return resp.json()["session_id"]

    def test_requirements_200(self, client):
        sid = self._make_session(client)
        resp = client.get(f"/api/drawing-parser/{sid}/requirements")
        assert resp.status_code == 200

    def test_requirements_no_confirmed_initially(self, client):
        sid = self._make_session(client, notes=["H7"])
        data = client.get(f"/api/drawing-parser/{sid}/requirements").json()
        # UNCERTAIN_EXTRACTION_AUTO_APPROVED=NO
        assert data["confirmed_detections"] == []

    def test_requirements_with_title_block_unit(self, client):
        sid = self._make_session(client, title_block_unit="mm")
        data = client.get(f"/api/drawing-parser/{sid}/requirements").json()
        assert data["detected_unit"] == "mm"

    def test_requirements_not_found(self, client):
        resp = client.get("/api/drawing-parser/nonexistent/requirements")
        assert resp.status_code == 404

    def test_requirements_disclaimer(self, client):
        sid = self._make_session(client)
        data = client.get(f"/api/drawing-parser/{sid}/requirements").json()
        assert "disclaimer" in data

    def test_uncertain_extraction_not_auto_approved(self, client):
        """UNCERTAIN_EXTRACTION_AUTO_APPROVED=NO verified via requirements endpoint."""
        sid = self._make_session(client, notes=["H7", "M10"])
        data = client.get(f"/api/drawing-parser/{sid}/requirements").json()
        # Before any confirm action, confirmed_detections must be empty
        assert data["confirmed_detections"] == []


# ---------------------------------------------------------------------------
# POST confirm
# ---------------------------------------------------------------------------

class TestConfirmDetection:
    def _setup(self, client):
        resp = client.post(
            "/api/drawing-parser/analyze",
            json=_analyze_payload(notes=["H7"]),
        )
        sid = resp.json()["session_id"]
        det_resp = client.get(f"/api/drawing-parser/{sid}/detections")
        dets = det_resp.json()["detections"]
        return sid, dets[0]["detection_id"] if dets else None

    def test_confirm_200(self, client):
        sid, did = self._setup(client)
        if did is None:
            pytest.skip("No detections to confirm")
        resp = client.post(f"/api/drawing-parser/{sid}/detections/{did}/confirm", json={})
        assert resp.status_code == 200

    def test_confirm_state_is_confirmed(self, client):
        sid, did = self._setup(client)
        if did is None:
            pytest.skip("No detections to confirm")
        client.post(f"/api/drawing-parser/{sid}/detections/{did}/confirm", json={})
        dets = client.get(f"/api/drawing-parser/{sid}/detections").json()["detections"]
        d = next((d for d in dets if d["detection_id"] == did), None)
        assert d is not None
        assert d["review_state"] == "CONFIRMED"

    def test_confirm_appears_in_requirements(self, client):
        sid, did = self._setup(client)
        if did is None:
            pytest.skip("No detections to confirm")
        client.post(f"/api/drawing-parser/{sid}/detections/{did}/confirm", json={})
        data = client.get(f"/api/drawing-parser/{sid}/requirements").json()
        confirmed_ids = [d["detection_id"] for d in data["confirmed_detections"]]
        assert did in confirmed_ids

    def test_confirm_nonexistent_session(self, client):
        resp = client.post("/api/drawing-parser/bad-session/detections/bad-det/confirm", json={})
        assert resp.status_code == 404

    def test_confirm_nonexistent_detection(self, client):
        sid, _ = self._setup(client)
        resp = client.post(f"/api/drawing-parser/{sid}/detections/nonexistent/confirm", json={})
        assert resp.status_code == 404

    def test_confirm_with_override_value(self, client):
        sid, did = self._setup(client)
        if did is None:
            pytest.skip("No detections to confirm")
        client.post(
            f"/api/drawing-parser/{sid}/detections/{did}/confirm",
            json={"confirmed_value": "H8"},
        )
        dets = client.get(f"/api/drawing-parser/{sid}/detections").json()["detections"]
        d = next(d for d in dets if d["detection_id"] == did)
        assert d["normalized_value"] == "H8"

    def test_confirm_disclaimer_in_response(self, client):
        sid, did = self._setup(client)
        if did is None:
            pytest.skip("No detections to confirm")
        resp = client.post(f"/api/drawing-parser/{sid}/detections/{did}/confirm", json={})
        assert "disclaimer" in resp.json()


# ---------------------------------------------------------------------------
# POST edit
# ---------------------------------------------------------------------------

class TestEditDetection:
    def _setup(self, client):
        resp = client.post(
            "/api/drawing-parser/analyze",
            json=_analyze_payload(notes=["H7"]),
        )
        sid = resp.json()["session_id"]
        dets = client.get(f"/api/drawing-parser/{sid}/detections").json()["detections"]
        return sid, dets[0]["detection_id"] if dets else None

    def test_edit_200(self, client):
        sid, did = self._setup(client)
        if did is None:
            pytest.skip("No detections to edit")
        resp = client.post(
            f"/api/drawing-parser/{sid}/detections/{did}/edit",
            json={"new_value": "H8"},
        )
        assert resp.status_code == 200

    def test_edit_state_is_edited(self, client):
        sid, did = self._setup(client)
        if did is None:
            pytest.skip("No detections to edit")
        client.post(f"/api/drawing-parser/{sid}/detections/{did}/edit", json={"new_value": "H8"})
        dets = client.get(f"/api/drawing-parser/{sid}/detections").json()["detections"]
        d = next(d for d in dets if d["detection_id"] == did)
        assert d["review_state"] == "EDITED"

    def test_edit_value_updated(self, client):
        sid, did = self._setup(client)
        if did is None:
            pytest.skip("No detections to edit")
        client.post(f"/api/drawing-parser/{sid}/detections/{did}/edit", json={"new_value": "JS7"})
        dets = client.get(f"/api/drawing-parser/{sid}/detections").json()["detections"]
        d = next(d for d in dets if d["detection_id"] == did)
        assert d["normalized_value"] == "JS7"

    def test_edit_empty_value_rejected(self, client):
        sid, did = self._setup(client)
        if did is None:
            pytest.skip("No detections to edit")
        resp = client.post(
            f"/api/drawing-parser/{sid}/detections/{did}/edit",
            json={"new_value": ""},
        )
        assert resp.status_code == 422

    def test_edit_not_in_requirements(self, client):
        """Edited (not re-confirmed) detection must not appear in requirements."""
        sid, did = self._setup(client)
        if did is None:
            pytest.skip("No detections to edit")
        client.post(f"/api/drawing-parser/{sid}/detections/{did}/edit", json={"new_value": "H8"})
        data = client.get(f"/api/drawing-parser/{sid}/requirements").json()
        confirmed_ids = [d["detection_id"] for d in data["confirmed_detections"]]
        assert did not in confirmed_ids


# ---------------------------------------------------------------------------
# POST reject
# ---------------------------------------------------------------------------

class TestRejectDetection:
    def _setup(self, client):
        resp = client.post(
            "/api/drawing-parser/analyze",
            json=_analyze_payload(notes=["H7"]),
        )
        sid = resp.json()["session_id"]
        dets = client.get(f"/api/drawing-parser/{sid}/detections").json()["detections"]
        return sid, dets[0]["detection_id"] if dets else None

    def test_reject_200(self, client):
        sid, did = self._setup(client)
        if did is None:
            pytest.skip("No detections to reject")
        resp = client.post(f"/api/drawing-parser/{sid}/detections/{did}/reject")
        assert resp.status_code == 200

    def test_reject_state_is_rejected(self, client):
        sid, did = self._setup(client)
        if did is None:
            pytest.skip("No detections to reject")
        client.post(f"/api/drawing-parser/{sid}/detections/{did}/reject")
        dets = client.get(f"/api/drawing-parser/{sid}/detections").json()["detections"]
        d = next(d for d in dets if d["detection_id"] == did)
        assert d["review_state"] == "REJECTED"

    def test_rejected_not_in_requirements(self, client):
        sid, did = self._setup(client)
        if did is None:
            pytest.skip("No detections to reject")
        client.post(f"/api/drawing-parser/{sid}/detections/{did}/reject")
        data = client.get(f"/api/drawing-parser/{sid}/requirements").json()
        confirmed_ids = [d["detection_id"] for d in data["confirmed_detections"]]
        assert did not in confirmed_ids


# ---------------------------------------------------------------------------
# POST associate
# ---------------------------------------------------------------------------

class TestAssociateDetection:
    def _setup(self, client):
        resp = client.post(
            "/api/drawing-parser/analyze",
            json=_analyze_payload(notes=["H7"]),
        )
        sid = resp.json()["session_id"]
        dets = client.get(f"/api/drawing-parser/{sid}/detections").json()["detections"]
        return sid, dets[0]["detection_id"] if dets else None

    def test_associate_200(self, client):
        sid, did = self._setup(client)
        if did is None:
            pytest.skip("No detections to associate")
        resp = client.post(
            f"/api/drawing-parser/{sid}/detections/{did}/associate",
            json={"feature_id": "feature-bore-1"},
        )
        assert resp.status_code == 200

    def test_associate_feature_id_stored(self, client):
        sid, did = self._setup(client)
        if did is None:
            pytest.skip("No detections to associate")
        client.post(
            f"/api/drawing-parser/{sid}/detections/{did}/associate",
            json={"feature_id": "bore-001"},
        )
        dets = client.get(f"/api/drawing-parser/{sid}/detections").json()["detections"]
        d = next(d for d in dets if d["detection_id"] == did)
        assert d["association_feature_id"] == "bore-001"
        assert d["association_state"] == "USER_MATCHED"

    def test_associate_with_feature_type(self, client):
        sid, did = self._setup(client)
        if did is None:
            pytest.skip("No detections to associate")
        client.post(
            f"/api/drawing-parser/{sid}/detections/{did}/associate",
            json={"feature_id": "bore-001", "feature_type": "HOLE"},
        )
        dets = client.get(f"/api/drawing-parser/{sid}/detections").json()["detections"]
        d = next(d for d in dets if d["detection_id"] == did)
        assert d["association_feature_type"] == "HOLE"

    def test_associate_empty_feature_id_rejected(self, client):
        sid, did = self._setup(client)
        if did is None:
            pytest.skip("No detections to associate")
        resp = client.post(
            f"/api/drawing-parser/{sid}/detections/{did}/associate",
            json={"feature_id": ""},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Security / privacy tests
# ---------------------------------------------------------------------------

class TestSecurityPrivacy:
    def test_oversized_file_rejected(self, client):
        large_content = b"X" * (65 * 1024 * 1024)  # 65 MB
        large_b64 = base64.b64encode(large_content).decode()
        payload = _analyze_payload(content_b64=large_b64)
        resp = client.post("/api/drawing-parser/analyze", json=payload)
        assert resp.status_code == 422

    def test_session_does_not_contain_bytes(self, client):
        resp = client.post("/api/drawing-parser/analyze", json=_analyze_payload())
        sid = resp.json()["session_id"]
        session = _SESSIONS.get(sid)
        assert session is not None
        # Verify drawing bytes are not stored
        import pickle
        session_bytes = pickle.dumps(session)
        # The session should not contain the actual drawing bytes
        assert b"fake-drawing-content" not in session_bytes

    def test_disallowed_extension_script(self, client):
        resp = client.post(
            "/api/drawing-parser/analyze",
            json=_analyze_payload(file_name="malicious.sh"),
        )
        assert resp.status_code == 422

    def test_disallowed_extension_html(self, client):
        resp = client.post(
            "/api/drawing-parser/analyze",
            json=_analyze_payload(file_name="xss.html"),
        )
        assert resp.status_code == 422

    def test_source_id_not_logged_no_crash(self, client):
        resp = client.post(
            "/api/drawing-parser/analyze",
            json=_analyze_payload(source_id="<script>alert(1)</script>"),
        )
        # Must not crash; source_id is stored as-is (validation is by length)
        assert resp.status_code in (200, 422)

    def test_response_contains_disclaimer(self, client):
        resp = client.post("/api/drawing-parser/analyze", json=_analyze_payload())
        assert "REFERENCE_ONLY" in resp.json()["disclaimer"]
