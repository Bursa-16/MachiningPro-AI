# ruff: noqa: E501
"""HUMAN_CONFIRMATION_UI_02: live analysis API. The Ollama HTTP transport is always mocked.

The real committed path runs end to end (R3D -> OllamaVlmProvider -> R3B v2 -> evidence);
only the socket underneath the provider is replaced, so no model is ever contacted.
"""

from __future__ import annotations

import ast
import http.client
import json
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import backend.api.drawing_analysis as drawing_analysis
from backend.api.app import app
from backend.api.auth import LoginRequest, authenticate
from backend.api.drawing_analysis import (
    AnalysisService,
    ErrorCode,
    JobStatus,
    classify_diagnostics,
    get_service,
)
from backend.interoperability.drawing import (
    CanonicalDrawing,
    DrawingDimension,
    DrawingDimensionType,
    DrawingExtractionAuthority,
    DrawingIngestionDiagnostics,
    DrawingIngestionResult,
    DrawingIngestionStatus,
    DrawingSourceLocation,
)
from backend.interoperability.pdf_drawing import PdfDrawingParser as RealPdfDrawingParser
from backend.interoperability.vlm_ollama import (
    OllamaConfigurationError,
    OllamaTransportFailure,
    OllamaVlmConfig,
    OllamaVlmProvider,
)
from backend.interoperability.vlm_provider import VlmErrorCode
from backend.interoperability.vlm_response import VLM_RESPONSE_SCHEMA_VERSION
from tests.unit.interoperability.ocr_fixtures import (
    SyntheticRasterDrawingBuilder,
    SyntheticRasterPdfBuilder,
)

_SECRET = "test-secret-key-at-least-32-characters-long"


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    """The provider's HTTP layer must never open a connection (the test client itself needs a
    loopback socketpair on Windows, so raw sockets are left alone)."""

    def _blocked(*args, **kwargs):
        raise AssertionError("real network access is forbidden in tests")

    monkeypatch.setattr(http.client.HTTPConnection, "connect", _blocked)
    monkeypatch.setattr(http.client.HTTPSConnection, "connect", _blocked)


def _pdf() -> bytes:
    image = (
        SyntheticRasterDrawingBuilder(width=480, height=320)
        .with_rectangle(40, 60, 320, 192)
        .with_text("100 MM", 150, 20, scale=3)
        .with_text("HOLE 20 MM", 130, 200, scale=2)
        .build()
    )
    return SyntheticRasterPdfBuilder().add_page(image).build()


_PDF = _pdf()


class StubParser:
    """Deterministic ingestion stand-in so most tests stay fast; one test uses the real one."""

    def parse(self, source_id, file_name, content, notes=None):
        dimension = DrawingDimension(
            dimension_id="det-dim-1",
            nominal_value=Decimal("100"),
            unit="mm",
            dimension_type=DrawingDimensionType.LINEAR,
            source_location=DrawingSourceLocation(
                source_id=source_id,
                page_number=1,
                original_text="100 mm",
                adapter_id="tesseract-ocr",
                adapter_version="1",
                authority=DrawingExtractionAuthority.EXTRACTED,
                source_object_ids=("t1",),
            ),
        )
        return DrawingIngestionResult(
            source_id=source_id,
            diagnostics=DrawingIngestionDiagnostics(
                status=DrawingIngestionStatus.VALID,
                format_detected="PDF",
                parser_id="machiningpro.vector-pdf",
                parser_version="1.0.0",
            ),
            document=CanonicalDrawing(
                drawing_id="pdf-drawing-ui02", source_id=source_id, all_dimensions=(dimension,)
            ),
        )


@pytest.fixture(autouse=True)
def _stub_parser(monkeypatch):
    monkeypatch.setattr(drawing_analysis, "PdfDrawingParser", StubParser)


def _item(**overrides) -> dict:
    item = {
        "candidate_type": "TEXT",
        "value": "100 MM",
        "legibility": "CLEAR",
        "confidence": 1,
        "evidence_reference": None,
    }
    item.update(overrides)
    return item


def _chat(items=None, *, text=None, **overrides) -> bytes:
    content = text if text is not None else json.dumps({"items": [_item()] if items is None else items})
    body = {"message": {"role": "assistant", "content": content}, "done": True}
    body.update(overrides)
    return json.dumps(body).encode()


class FakeTransport:
    def __init__(self, status=200, body=None, error=None, on_call=None):
        self.status, self.body, self.error, self.on_call = status, body or _chat(), error, on_call
        self.calls: list[dict] = []

    def __call__(self, host, port, path, headers, body, timeout, max_response_bytes):
        self.calls.append({"host": host, "port": port, "path": path, "body": json.loads(body)})
        if self.on_call:
            self.on_call()
        if self.error is not None:
            raise self.error
        return self.status, self.body


class ManualRunner:
    """Collects job tasks so a test decides when (and whether) the job runs."""

    def __init__(self):
        self.tasks = []

    def __call__(self, task):
        self.tasks.append(task)

    def run_all(self):
        while self.tasks:
            self.tasks.pop(0)()


def _provider_factory(transport, config=None):
    return lambda: OllamaVlmProvider(config or OllamaVlmConfig(), transport=transport)


@pytest.fixture
def auth(monkeypatch):
    monkeypatch.setenv("MACHININGPRO_DEV_USERNAME", "engineer-1")
    monkeypatch.setenv("MACHININGPRO_DEV_PASSWORD", "pw-for-tests")
    monkeypatch.setenv("MACHININGPRO_DEV_JWT_SECRET", _SECRET)
    token = authenticate(LoginRequest(username="engineer-1", password="pw-for-tests")).token
    return {"Authorization": f"Bearer {token}"}


def _make(transport=None, *, runner=None, config=None):
    transport = transport or FakeTransport()
    runner = runner or (lambda task: task())
    service = AnalysisService(
        provider_factory=_provider_factory(transport, config),
        runner=runner,
        clock=lambda: "2026-10-08T12:00:00.000Z",
    )
    app.dependency_overrides[get_service] = lambda: service
    return service, transport, TestClient(app)


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.clear()


def _upload(client, headers, content=_PDF, name="drawing.pdf"):
    return client.post("/api/drawings", files={"file": (name, content, "application/pdf")}, headers=headers)


def _start(client, headers, drawing_id, **body):
    payload = {"ai_enabled": True, **body}
    return client.post(f"/api/drawings/{drawing_id}/analysis", json=payload, headers=headers)


def _job(client, headers, drawing_id, job_id):
    return client.get(f"/api/drawings/{drawing_id}/analysis/{job_id}", headers=headers).json()


# ---------------------------------------------------------------------------
# Auth, upload and the deterministic result
# ---------------------------------------------------------------------------


class TestAuthAndUpload:
    def test_every_endpoint_requires_a_valid_bearer_token(self, auth):
        _, _, client = _make()
        for method, url, kwargs in [
            ("post", "/api/drawings", {"files": {"file": ("a.pdf", _PDF, "application/pdf")}}),
            ("get", "/api/drawings/" + "0" * 32, {}),
            ("get", "/api/drawings/" + "0" * 32 + "/pages/1/preview", {}),
            ("post", "/api/drawings/" + "0" * 32 + "/analysis", {"json": {"ai_enabled": True}}),
            ("get", "/api/drawings/" + "0" * 32 + "/analysis/" + "1" * 32, {}),
            ("put", "/api/drawings/x/analysis/y/reviews/z", {"json": {"action": "ACCEPT"}}),
        ]:
            assert getattr(client, method)(url, **kwargs).status_code == 401, url
        bad = {"Authorization": "Bearer not-a-token"}
        assert client.get("/api/drawings/" + "0" * 32, headers=bad).status_code == 401

    def test_ui02_upload_returns_the_deterministic_result_and_regions(self, auth):
        _, _, client = _make()
        response = _upload(client, auth)
        assert response.status_code == 201
        body = response.json()
        assert len(body["drawing_id"]) == 32
        assert body["deterministic"]["status"] == "VALID"
        assert body["deterministic"]["items"] == [
            {"id": "det-dim-1", "label": "LINEAR", "value": "100 mm", "source": "tesseract-ocr"}
        ]
        (page,) = body["pages"]
        assert (page["page_number"], page["images"]) == (
            1,
            [{"index": 1, "width_px": 480, "height_px": 320}],
        )
        assert client.get(f"/api/drawings/{body['drawing_id']}", headers=auth).json() == body

    def test_the_real_deterministic_parser_runs_on_upload(self, auth, monkeypatch):
        monkeypatch.setattr(drawing_analysis, "PdfDrawingParser", RealPdfDrawingParser)
        _, _, client = _make()
        response = _upload(client, auth)
        assert response.status_code == 201
        assert response.json()["deterministic"]["status"] in {"VALID", "PARTIAL", "INSUFFICIENT_DATA"}
        assert response.json()["pages"][0]["images"]

    @pytest.mark.parametrize("content", [b"", b"not a pdf", b"GIF89a" + b"0" * 100])
    def test_non_pdf_uploads_are_rejected(self, auth, content):
        _, _, client = _make()
        response = _upload(client, auth, content)
        assert response.status_code == 422
        assert response.json()["detail"] == {"error_code": "INVALID_DRAWING"}

    def test_oversized_uploads_are_rejected(self, auth, monkeypatch):
        monkeypatch.setattr(drawing_analysis, "MAX_UPLOAD_BYTES", 1024)
        _, _, client = _make()
        assert _upload(client, auth, b"%PDF-" + b"0" * 4096).status_code == 413

    def test_a_parser_crash_is_a_structured_failure_without_text(self, auth, monkeypatch):
        class Crash:
            def parse(self, *args, **kwargs):
                raise RuntimeError("secret internal path C:/x/y")

        monkeypatch.setattr(drawing_analysis, "PdfDrawingParser", Crash)
        _, _, client = _make()
        response = _upload(client, auth)
        assert response.status_code == 422
        assert "secret" not in response.text and "C:/" not in response.text

    def test_ui02_t16_no_arbitrary_filesystem_path_is_accepted(self, auth):
        _, _, client = _make()
        drawing_id = _upload(client, auth).json()["drawing_id"]
        for body in (
            {"ai_enabled": True, "path": "C:/Windows/win.ini"},
            {"ai_enabled": True, "file_path": "../../etc/passwd"},
            {"ai_enabled": True, "url": "http://example.com/a.pdf"},
        ):
            assert client.post(f"/api/drawings/{drawing_id}/analysis", json=body, headers=auth).status_code == 422
        for bad_id in ("../../etc/passwd", "C:\\x", "%2e%2e", "a" * 31, "G" * 32):
            assert client.get(f"/api/drawings/{bad_id}", headers=auth).status_code == 404
        assert not any(
            isinstance(node, ast.Call) and getattr(node.func, "id", "") == "open"
            for node in ast.walk(ast.parse(Path(drawing_analysis.__file__).read_text(encoding="utf-8")))
        )

    def test_the_preview_is_a_png_of_the_stored_drawing(self, auth):
        _, _, client = _make()
        drawing_id = _upload(client, auth).json()["drawing_id"]
        response = client.get(f"/api/drawings/{drawing_id}/pages/1/preview", headers=auth)
        assert response.status_code == 200
        assert response.content.startswith(b"\x89PNG")
        assert client.get(f"/api/drawings/{drawing_id}/pages/9/preview", headers=auth).status_code == 404


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


class TestJobs:
    def test_ui02_t01_start_returns_a_job_id_without_running_inference(self, auth):
        runner = ManualRunner()
        _, transport, client = _make(runner=runner)
        drawing_id = _upload(client, auth).json()["drawing_id"]
        response = _start(client, auth, drawing_id)
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "QUEUED" and len(body["job_id"]) == 32 and body["reused"] is False
        assert transport.calls == [], "inference has not started when the request returns"
        assert body["findings"] == [] and body["finding_count"] is None
        assert len(runner.tasks) == 1

    def test_ui02_t02_a_duplicate_start_returns_the_active_job(self, auth):
        runner = ManualRunner()
        _, transport, client = _make(runner=runner)
        drawing_id = _upload(client, auth).json()["drawing_id"]
        first = _start(client, auth, drawing_id)
        second = _start(client, auth, drawing_id)
        assert second.status_code == 200
        assert second.json()["job_id"] == first.json()["job_id"] and second.json()["reused"] is True
        assert len(runner.tasks) == 1
        runner.run_all()
        assert len(transport.calls) == 1
        third = _start(client, auth, drawing_id)  # after completion a new explicit job is allowed
        assert third.status_code == 202 and third.json()["job_id"] != first.json()["job_id"]

    def test_ui02_t03_the_job_moves_through_real_states(self, auth):
        runner = ManualRunner()
        seen: list[str] = []
        holder = {}

        def probe():
            seen.append(holder["service"]._jobs[holder["job"]].status.value)

        service, transport, client = _make(FakeTransport(on_call=probe), runner=runner)
        holder["service"] = service
        drawing_id = _upload(client, auth).json()["drawing_id"]
        job_id = _start(client, auth, drawing_id).json()["job_id"]
        holder["job"] = job_id
        assert _job(client, auth, drawing_id, job_id)["status"] == "QUEUED"
        runner.run_all()
        assert seen == ["ANALYZING"], "the HTTP call happens in the ANALYZING state"
        done = _job(client, auth, drawing_id, job_id)
        assert done["status"] == "COMPLETED" and done["progress_phase"] is None
        assert done["started_at"] and done["completed_at"] and done["finding_count"] == 1
        assert JobStatus.VALIDATING.value == "VALIDATING"

    def test_the_status_never_carries_a_percentage(self, auth):
        runner = ManualRunner()
        _, _, client = _make(runner=runner)
        drawing_id = _upload(client, auth).json()["drawing_id"]
        view = _start(client, auth, drawing_id).json()
        assert not {k for k in view if "percent" in k or "progress_pct" in k or k == "progress"}
        assert "progress_phase" in view

    def test_jobs_run_one_inference_at_a_time(self, auth):
        runner = ManualRunner()
        service, _, client = _make(runner=runner)
        first_drawing = _upload(client, auth).json()["drawing_id"]
        second_drawing = _upload(client, auth).json()["drawing_id"]
        _start(client, auth, first_drawing)
        _start(client, auth, second_drawing)
        assert len(runner.tasks) == 2
        assert service._model_lock.locked() is False
        runner.run_all()
        assert all(job.status is JobStatus.COMPLETED for job in service._jobs.values())

    def test_ai_must_be_requested_explicitly(self, auth):
        _, transport, client = _make()
        drawing_id = _upload(client, auth).json()["drawing_id"]
        assert _start(client, auth, drawing_id, ai_enabled=False).status_code == 400
        assert client.post(f"/api/drawings/{drawing_id}/analysis", json={}, headers=auth).status_code == 422
        assert transport.calls == []

    def test_uploading_never_starts_ai(self, auth):
        _, transport, client = _make()
        _upload(client, auth)
        assert transport.calls == []

    def test_an_unselected_provider_is_a_structured_ai_disabled(self, auth, monkeypatch):
        monkeypatch.delenv("MACHININGPRO_AI_PROVIDER", raising=False)
        service = AnalysisService(runner=lambda task: task())  # the default (environment) factory
        app.dependency_overrides[get_service] = lambda: service
        client = TestClient(app)
        drawing_id = _upload(client, auth).json()["drawing_id"]
        response = _start(client, auth, drawing_id)
        assert response.status_code == 503
        assert response.json()["detail"] == {"error_code": "AI_DISABLED"}
        assert service._jobs == {}

    def test_the_default_factory_is_ollama_only_loopback_and_keyless(self, monkeypatch):
        monkeypatch.setenv("MACHININGPRO_AI_PROVIDER", "ollama")
        provider = drawing_analysis.default_provider_factory()
        assert provider.identity().provider_id == "ollama.chat"
        assert provider.identity().model_id == "granite3.2-vision:2b"
        assert provider._config.timeout_seconds >= 600
        assert drawing_analysis.ASSIST_TOTAL_BUDGET_SECONDS >= 900
        monkeypatch.setenv("MACHININGPRO_OLLAMA_BASE_URL", "http://192.168.1.5:11434")
        with pytest.raises(OllamaConfigurationError):
            drawing_analysis.default_provider_factory()
        monkeypatch.setenv("MACHININGPRO_AI_PROVIDER", "openai")
        monkeypatch.delenv("MACHININGPRO_OLLAMA_BASE_URL", raising=False)
        with pytest.raises(OllamaConfigurationError):
            drawing_analysis.default_provider_factory()

    @pytest.mark.parametrize(
        "body",
        [
            {"page_number": 2},
            {"image_index": 3},
            {"page_number": 0},
            {"crop_px": [0, 0, 0, 10]},
            {"crop_px": [10, 10, 5, 5]},
            {"crop_px": [0, 0, 9999, 320]},
            {"crop_px": [0, 0, 10]},
        ],
    )
    def test_invalid_regions_are_rejected_before_any_job(self, auth, body):
        service, transport, client = _make()
        drawing_id = _upload(client, auth).json()["drawing_id"]
        response = _start(client, auth, drawing_id, **body)
        assert response.status_code == 422
        assert response.json()["detail"] == {"error_code": "INVALID_REGION"}
        assert service._jobs == {} and transport.calls == []

    def test_an_r3d_rejection_fails_the_job_without_calling_the_model(self, auth, monkeypatch):
        from backend.interoperability.vlm_request import (
            VlmPreparationError,
            VlmPreparationErrorCode,
        )

        def reject(*args, **kwargs):
            raise VlmPreparationError(VlmPreparationErrorCode.CROP_EDGE_LIMIT)

        monkeypatch.setattr(drawing_analysis, "prepare_vlm_requests", reject)
        _, transport, client = _make()
        drawing_id = _upload(client, auth).json()["drawing_id"]
        job_id = _start(client, auth, drawing_id).json()["job_id"]
        done = _job(client, auth, drawing_id, job_id)
        assert done["status"] == "FAILED" and done["error_code"] == "INVALID_REGION"
        assert transport.calls == []

    def test_a_sub_region_is_analysed_as_a_source_region(self, auth):
        _, transport, client = _make()
        drawing_id = _upload(client, auth).json()["drawing_id"]
        job_id = _start(client, auth, drawing_id, crop_px=[10, 20, 110, 70]).json()["job_id"]
        done = _job(client, auth, drawing_id, job_id)
        assert done["status"] == "COMPLETED"
        assert done["region"] == {
            "region_id": "region-p1-10-20-110-70",
            "x0": 10.0, "top": 20.0, "x1": 110.0, "bottom": 70.0, "unit": "pt",
        }
        assert done["findings"][0]["box"] == {
            "x0": 10.0, "top": 20.0, "x1": 110.0, "bottom": 70.0, "unit": "pt",
        }


# ---------------------------------------------------------------------------
# Results: only validated, advisory, region-extent evidence
# ---------------------------------------------------------------------------


class TestResults:
    def _run(self, auth, transport=None):
        service, transport, client = _make(transport)
        drawing_id = _upload(client, auth).json()["drawing_id"]
        job_id = _start(client, auth, drawing_id).json()["job_id"]
        return service, transport, client, drawing_id, job_id, _job(client, auth, drawing_id, job_id)

    def test_ui02_t04_t11_t12_a_completed_job_exposes_validated_advisory_evidence(self, auth):
        _, transport, _, _, _, done = self._run(auth)
        assert done["status"] == "COMPLETED" and done["finding_count"] == 1
        (finding,) = done["findings"]
        assert finding["original_value"] == "100 MM"
        assert finding["authority"] == "ADVISORY"
        assert finding["box_basis"] == "REGION_EXTENT"
        assert finding["provider_id"] == "ollama.chat"
        assert finding["model_id"] == "granite3.2-vision:2b"
        assert finding["schema_version"] == "machiningpro.drawing-vlm.response.v2"
        assert finding["prompt_contract_version"] == "machiningpro.drawing-vlm.v1"
        assert finding["confidence"] == 1.0
        assert finding["region_id"] == done["region"]["region_id"]
        assert finding["box"] == {k: done["region"][k] for k in ("x0", "top", "x1", "bottom", "unit")}
        assert finding["reconciliation"] in {"CORROBORATED", "ADVISORY_ONLY"}
        assert len(transport.calls) == 1, "exactly one model call, no retry"

    def test_ui02_t13_the_model_is_never_asked_for_and_never_returns_a_pixel_box(self, auth):
        _, transport, _, _, _, done = self._run(auth)
        sent = transport.calls[0]["body"]
        item_props = sent["format"]["properties"]["items"]["items"]["properties"]
        assert "box" not in item_props
        assert "box" not in sent["messages"][0]["content"].lower()
        assert all("box" not in f or f["box_basis"] == "REGION_EXTENT" for f in done["findings"])

    def test_the_granite_cpu_profile_loopback_and_no_key_are_used(self, auth):
        _, transport, _, _, _, _ = self._run(auth)
        call = transport.calls[0]
        assert (call["host"], call["port"], call["path"]) == ("127.0.0.1", 11434, "/api/chat")
        assert call["body"]["model"] == "granite3.2-vision:2b"
        options = call["body"]["options"]
        assert (options["num_gpu"], options["num_ctx"], options["temperature"]) == (0, 8192, 0)
        assert call["body"]["stream"] is False

    def test_a_v1_selection_is_discarded_because_it_would_carry_a_model_box(self, auth):
        legacy = OllamaVlmConfig(response_schema_version=VLM_RESPONSE_SCHEMA_VERSION)
        item = _item(box=[0, 0, 100, 50])
        service, transport, client = _make(FakeTransport(body=_chat([item])), config=legacy)
        drawing_id = _upload(client, auth).json()["drawing_id"]
        job_id = _start(client, auth, drawing_id).json()["job_id"]
        done = _job(client, auth, drawing_id, job_id)
        assert done["status"] == "FAILED" and done["error_code"] == "R3B_VALIDATION_FAILURE"
        assert done["findings"] == []

    def test_no_findings_completes_with_zero_items(self, auth):
        _, _, _, _, _, done = self._run(auth, FakeTransport(body=_chat([])))
        assert done["status"] == "COMPLETED" and done["finding_count"] == 0
        assert done["findings"] == [] and done["error_code"] is None

    @pytest.mark.parametrize(
        ("transport", "code"),
        [
            (FakeTransport(error=ConnectionRefusedError()), "OLLAMA_UNAVAILABLE"),
            (FakeTransport(status=404, body=b'{"error":"model not found"}'), "MODEL_NOT_AVAILABLE"),
            (FakeTransport(error=OllamaTransportFailure(VlmErrorCode.TIMEOUT)), "REQUEST_TIMEOUT"),
            (FakeTransport(status=500), "OLLAMA_UNAVAILABLE"),
            (FakeTransport(body=_chat(text="not json at all")), "R3B_VALIDATION_FAILURE"),
            (FakeTransport(body=_chat([_item(candidate_type="WELD")])), "R3B_VALIDATION_FAILURE"),
            (FakeTransport(body=_chat([_item(evidence_reference="HOLE 20 MM")])), "R3B_VALIDATION_FAILURE"),
            (FakeTransport(body=_chat([{**_item(), "box": [0, 0, 1, 1]}])), "R3B_VALIDATION_FAILURE"),
        ],
    )
    def test_ui02_t05_to_t09_failures_are_structured_and_expose_no_evidence(self, auth, transport, code):
        _, transport, _, _, _, done = self._run(auth, transport)
        assert done["status"] == "FAILED" and done["error_code"] == code
        assert done["findings"] == [] and done["reviews"] == {} and done["finding_count"] is None
        assert done["error_message"] and "Traceback" not in json.dumps(done)
        assert len(transport.calls) <= 1, "no automatic retry on a failure"

    def test_raw_model_output_and_internals_never_reach_the_client(self, auth):
        secret_text = "SECRET-MODEL-TEXT-/home/user/x"
        _, _, _, _, _, done = self._run(auth, FakeTransport(body=_chat(text=secret_text)))
        blob = json.dumps(done)
        assert secret_text not in blob and "11434" not in blob and "127.0.0.1" not in blob
        assert "C:\\" not in blob and "upload::" not in blob

    def test_an_unexpected_exception_becomes_job_internal_error(self, auth):
        class Boom:
            def identity(self):
                return OllamaVlmProvider(OllamaVlmConfig()).identity()

            def capabilities(self):
                return OllamaVlmProvider(OllamaVlmConfig()).capabilities()

            def infer(self, *args, **kwargs):
                raise RuntimeError("boom with /secret/path")

        service = AnalysisService(provider_factory=lambda: Boom(), runner=lambda t: t())
        app.dependency_overrides[get_service] = lambda: service
        client = TestClient(app)
        drawing_id = _upload(client, auth).json()["drawing_id"]
        job_id = _start(client, auth, drawing_id).json()["job_id"]
        done = _job(client, auth, drawing_id, job_id)
        assert done["status"] == "FAILED"
        assert done["error_code"] in {"JOB_INTERNAL_ERROR", "OLLAMA_UNAVAILABLE"}
        assert "boom" not in json.dumps(done) and "/secret" not in json.dumps(done)

    def test_ui02_t10_the_deterministic_result_survives_every_ai_failure(self, auth):
        service, transport, client, drawing_id, _, done = self._run(
            auth, FakeTransport(error=ConnectionRefusedError())
        )
        assert done["status"] == "FAILED"
        summary = client.get(f"/api/drawings/{drawing_id}", headers=auth).json()
        assert summary["deterministic"]["items"][0]["value"] == "100 mm"
        assert client.get(f"/api/drawings/{drawing_id}/pages/1/preview", headers=auth).status_code == 200

    def test_ui02_t14_no_openai_or_cloud_path_exists(self):
        source = Path(drawing_analysis.__file__).read_text(encoding="utf-8")
        imported = {
            node.module
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not [m for m in imported if "vlm_openai" in m]
        for banned in ("OpenAi", "openai", "api.openai", "OPENAI_API_KEY", "anthropic"):
            assert banned not in source

    def test_ui02_t15_the_job_policy_has_a_single_attempt(self):
        source = Path(drawing_analysis.__file__).read_text(encoding="utf-8")
        assert "max_attempts=1" in source

    def test_the_classifier_maps_diagnostics_to_safe_codes(self):
        assert classify_diagnostics(("VLM_UNAVAILABLE",)) is ErrorCode.OLLAMA_UNAVAILABLE
        assert classify_diagnostics(("VLM_TIMEOUT",)) is ErrorCode.REQUEST_TIMEOUT
        assert classify_diagnostics(("VLM_REQUEST_REJECTED",)) is ErrorCode.MODEL_NOT_AVAILABLE
        assert classify_diagnostics(("VLM_RESPONSE_BOX",)) is ErrorCode.R3B_VALIDATION_FAILURE
        assert classify_diagnostics(("VLM_DISABLED",)) is ErrorCode.AI_DISABLED
        assert classify_diagnostics(("anything",)) is ErrorCode.JOB_INTERNAL_ERROR
        assert classify_diagnostics(()) is ErrorCode.JOB_INTERNAL_ERROR

    def test_unknown_jobs_and_drawings_are_404(self, auth):
        _, _, client = _make()
        drawing_id = _upload(client, auth).json()["drawing_id"]
        assert client.get(f"/api/drawings/{drawing_id}/analysis/{'0' * 32}", headers=auth).status_code == 404
        assert client.get(f"/api/drawings/{'0' * 32}/analysis/{'0' * 32}", headers=auth).status_code == 404


# ---------------------------------------------------------------------------
# Review decisions
# ---------------------------------------------------------------------------


class TestReview:
    def _completed(self, auth):
        service, transport, client = _make(
            FakeTransport(body=_chat([_item(), _item(value="HOLE 20 MM")]))
        )
        drawing_id = _upload(client, auth).json()["drawing_id"]
        job_id = _start(client, auth, drawing_id).json()["job_id"]
        done = _job(client, auth, drawing_id, job_id)
        evidence = [f["evidence_id"] for f in done["findings"]]
        return service, client, drawing_id, job_id, evidence, done

    def _put(self, client, auth, ids, evidence_id, **body):
        drawing_id, job_id = ids
        return client.put(
            f"/api/drawings/{drawing_id}/analysis/{job_id}/reviews/{evidence_id}",
            json=body,
            headers=auth,
        )

    def test_ui02_t22_everything_starts_pending_nothing_is_auto_accepted(self, auth):
        _, _, _, _, evidence, done = self._completed(auth)
        assert len(evidence) == 2
        assert {r["status"] for r in done["reviews"].values()} == {"PENDING_REVIEW"}
        assert all(r["reviewed_by"] is None and r["history"] == [] for r in done["reviews"].values())

    def test_ui02_t17_accept_preserves_the_original_ai_evidence(self, auth):
        _, client, drawing_id, job_id, evidence, before = self._completed(auth)
        response = self._put(client, auth, (drawing_id, job_id), evidence[0], action="ACCEPT")
        assert response.status_code == 200
        record = response.json()
        assert record["status"] == "ACCEPTED" and record["original_ai_value"] == "100 MM"
        assert record["reviewed_value"] is None
        assert record["reviewed_by"] == "engineer-1", "identity comes from the token, not the body"
        after = _job(client, auth, drawing_id, job_id)
        assert after["findings"] == before["findings"], "the AI evidence itself is unchanged"
        assert after["reviews"][evidence[1]]["status"] == "PENDING_REVIEW"

    def test_ui02_t18_reject_preserves_the_original_ai_evidence(self, auth):
        _, client, drawing_id, job_id, evidence, before = self._completed(auth)
        record = self._put(client, auth, (drawing_id, job_id), evidence[0], action="REJECT").json()
        assert record["status"] == "REJECTED" and record["original_ai_value"] == "100 MM"
        after = _job(client, auth, drawing_id, job_id)
        assert after["findings"] == before["findings"]
        assert after["reviews"][evidence[0]]["history"][0]["status"] == "REJECTED"

    def test_ui02_t19_t20_edit_keeps_the_ai_value_and_stores_the_human_value_apart(self, auth):
        _, client, drawing_id, job_id, evidence, before = self._completed(auth)
        record = self._put(
            client, auth, (drawing_id, job_id), evidence[0], action="EDIT", value="  100 mm "
        ).json()
        assert record["status"] == "EDITED"
        assert record["original_ai_value"] == "100 MM" and record["reviewed_value"] == "100 mm"
        after = _job(client, auth, drawing_id, job_id)
        assert after["findings"][0]["original_value"] == "100 MM"
        assert after["findings"] == before["findings"]

    @pytest.mark.parametrize(
        ("value", "reason"),
        [(None, "BLANK"), ("   ", "BLANK"), ("x" * 257, "TOO_LONG"), ("a\x00b", "CONTROL_CHARACTERS"),
         ("100 MM", "UNCHANGED")],
    )
    def test_invalid_edits_change_nothing(self, auth, value, reason):
        _, client, drawing_id, job_id, evidence, _ = self._completed(auth)
        response = self._put(client, auth, (drawing_id, job_id), evidence[0], action="EDIT", value=value)
        assert response.status_code == 422
        assert response.json()["detail"] == {"error_code": "INVALID_REVIEW_VALUE", "reason": reason}
        record = _job(client, auth, drawing_id, job_id)["reviews"][evidence[0]]
        assert record["status"] == "PENDING_REVIEW" and record["history"] == []

    def test_history_is_append_only_and_a_decision_can_be_changed(self, auth):
        _, client, drawing_id, job_id, evidence, _ = self._completed(auth)
        ids = (drawing_id, job_id)
        self._put(client, auth, ids, evidence[0], action="ACCEPT")
        self._put(client, auth, ids, evidence[0], action="EDIT", value="100 mm")
        last = self._put(client, auth, ids, evidence[0], action="REJECT").json()
        assert [e["status"] for e in last["history"]] == ["ACCEPTED", "EDITED", "REJECTED"]
        assert last["status"] == "REJECTED" and last["reviewed_value"] is None
        assert last["original_ai_value"] == "100 MM"

    def test_ui02_t21_review_cannot_touch_the_deterministic_result(self, auth):
        _, client, drawing_id, job_id, evidence, _ = self._completed(auth)
        before = client.get(f"/api/drawings/{drawing_id}", headers=auth).json()
        self._put(client, auth, (drawing_id, job_id), evidence[0], action="EDIT", value="999 mm")
        assert client.get(f"/api/drawings/{drawing_id}", headers=auth).json() == before

    def test_review_requires_a_completed_job_a_known_finding_and_a_known_action(self, auth):
        runner = ManualRunner()
        _, _, client = _make(runner=runner)
        drawing_id = _upload(client, auth).json()["drawing_id"]
        job_id = _start(client, auth, drawing_id).json()["job_id"]
        queued = self._put(client, auth, (drawing_id, job_id), "vlm-ev-x", action="ACCEPT")
        assert queued.status_code == 409
        runner.run_all()
        assert self._put(client, auth, (drawing_id, job_id), "vlm-ev-missing", action="ACCEPT").status_code == 404
        evidence = _job(client, auth, drawing_id, job_id)["findings"][0]["evidence_id"]
        assert self._put(client, auth, (drawing_id, job_id), evidence, action="ACCEPT_ALL").status_code == 422
        # reviewer field is now accepted (no longer extra-forbidden); auth identity is still from JWT
        assert self._put(client, auth, (drawing_id, job_id), evidence, action="ACCEPT", reviewer="evil").status_code == 200

    def test_client_reviewer_field_is_ignored_jwt_identity_is_authoritative(self, auth):
        """Regression: reviewer supplied by the client must not become the recorded identity."""
        _, client, drawing_id, job_id, evidence, _ = self._completed(auth)
        response = self._put(client, auth, (drawing_id, job_id), evidence[0], action="ACCEPT", reviewer="evil")
        assert response.status_code == 200
        record = response.json()
        assert record["reviewed_by"] == "engineer-1", "JWT sub must be used, not the client-supplied reviewer"
        assert record["reviewed_by"] != "evil"

    def test_a_failed_job_has_no_reviewable_evidence(self, auth):
        service, transport, client = _make(FakeTransport(error=ConnectionRefusedError()))
        drawing_id = _upload(client, auth).json()["drawing_id"]
        job_id = _start(client, auth, drawing_id).json()["job_id"]
        response = self._put(client, auth, (drawing_id, job_id), "vlm-ev-x", action="ACCEPT")
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# Regression anchors
# ---------------------------------------------------------------------------


def test_the_existing_health_and_login_endpoints_are_unchanged():
    client = TestClient(app)
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.post("/api/login", json={"username": "x", "password": "y"}).status_code == 401


def test_authority_constants_are_unchanged():
    import backend.interoperability.vlm_assist as vlm_assist

    assert vlm_assist.AI_DEFAULT_AUTHORITY is DrawingExtractionAuthority.ADVISORY
    assert vlm_assist.AUTO_PROMOTION_ALLOWED is False
    assert vlm_assist.DETERMINISTIC_EVIDENCE_OVERWRITE_ALLOWED is False
