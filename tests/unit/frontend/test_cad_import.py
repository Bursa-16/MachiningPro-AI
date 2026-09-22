"""UI-1A — CAD Import page tests."""

from __future__ import annotations

import hashlib
import logging
import tempfile
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.interoperability.enums import CapabilityLevel, NormalizationStatus
from backend.interoperability.models import (
    CanonicalDocument,
    EngineeringSource,
    FormatDescriptor,
)
from backend.interoperability.orchestrator import (
    CapabilityRecord,
    FormatDetectionResult,
    ImportDiagnostics,
    ImportProvenance,
    ImportResult,
    ImportStatus,
)
from frontend.app import app
from frontend.cad_upload import MAX_CAD_UPLOAD_BYTES
from tests.unit.interoperability.iges_fixtures import EntitySpec, make_iges

_STEP_UPLOAD = b"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('CAD upload test'),'2;1');
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));
ENDSEC;
DATA;
#1=PRODUCT('Part','Part','',());
ENDSEC;
END-ISO-10303-21;
"""

_IGES_BREP_UPLOAD = make_iges(
    (
        EntitySpec(108, "108,0,0,1,0,0,0,0,0,1;"),
        EntitySpec(110, "110,0,0,0,2,0,0;"),
        EntitySpec(110, "110,2,0,0,0,2,0;"),
        EntitySpec(110, "110,0,2,0,0,0,0;"),
        EntitySpec(502, "502,3,0,0,0,2,0,0,0,2,0;", form_number=1),
        EntitySpec(
            504,
            "504,3,3,9,1,9,2,5,9,2,9,3,7,9,3,9,1;",
            form_number=1,
        ),
        EntitySpec(
            508,
            "508,3,0,11,1,1,0,0,11,2,1,0,0,11,3,1,0;",
            form_number=1,
        ),
        EntitySpec(510, "510,1,1,1,13;", form_number=1),
        EntitySpec(514, "514,1,15,1;", form_number=1),
        EntitySpec(186, "186,17,1,0;"),
    )
)

_IGES_UNSUPPORTED_UPLOAD = make_iges(
    (EntitySpec(118, "118,1,3,0,0;"),)
)


class _AdvancedDetailsParser(HTMLParser):
    """Capture the rendered accordion contract without depending on formatting."""

    def __init__(self) -> None:
        super().__init__()
        self.trigger: dict[str, str | None] = {}
        self.panel: dict[str, str | None] = {}
        self.panel_text: list[str] = []
        self.script_sources: list[str] = []
        self._panel_depth = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if tag == "button" and attributes.get("id") == "cad-import-advanced-trigger":
            self.trigger = attributes
        if tag == "div" and attributes.get("id") == "cad-import-advanced-panel":
            self.panel = attributes
            self._panel_depth = 1
        elif self._panel_depth:
            self._panel_depth += 1
        if tag == "script" and attributes.get("src"):
            self.script_sources.append(attributes["src"] or "")

    def handle_endtag(self, tag: str) -> None:
        if self._panel_depth:
            self._panel_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._panel_depth:
            self.panel_text.append(data.strip())


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


# -- Helpers ---------------------------------------------------------------

def _fake_success_result(source_id: str = "upload::test.step") -> ImportResult:
    """Build a realistic ImportResult for monkeypatching."""
    from backend.domain.base import Provenance
    from backend.domain.enums import ProvenanceType
    from backend.interoperability.enums import (
        AdapterLicense,
        FidelityReportCompleteness,
        FormatFamily,
    )
    from backend.interoperability.models import ConversionFidelityReport

    source = EngineeringSource(source_id=source_id, file_name="test.step")
    descriptor = FormatDescriptor(
        format_id="STEP-GENERIC",
        canonical_name="STEP Generic",
        family=FormatFamily.NEUTRAL_EXCHANGE,
        adapter_license=AdapterLicense.INTERNAL_PARSER,
    )
    fidelity = ConversionFidelityReport(
        report_id="rpt-1",
        source_format_id="STEP-GENERIC",
        adapter_id="step-token-adapter",
        adapter_version="4C.0",
        completeness=FidelityReportCompleteness.COMPLETE,
        normalization_status=NormalizationStatus.SUCCESS,
    )
    document = CanonicalDocument(
        document_id="doc-1",
        canonical_kind="CAD_GEOMETRY",
        source=source,
        format_descriptor=descriptor,
        adapter_id="step-token-adapter",
        adapter_version="4C.0",
        capability_level=CapabilityLevel.LEVEL_2_NORMALIZED,
        normalization_status=NormalizationStatus.SUCCESS,
        fidelity_report=fidelity,
    )
    detection = FormatDetectionResult(
        detected_format_id="STEP-GENERIC",
        detection_confidence="MEDIUM",
        detection_method="file_extension",
    )
    diag = ImportDiagnostics(
        format_detection=detection,
        adapter_candidates=("step-token-adapter",),
        selected_adapter_id="step-token-adapter",
        selection_reason="first_ordered_candidate",
        fidelity_adverse_count=0,
        has_unsupported_content=False,
        has_loss=False,
    )
    cap = CapabilityRecord(achieved_level=CapabilityLevel.LEVEL_2_NORMALIZED)
    prov = ImportProvenance(
        source_id=source_id,
        adapter_id="step-token-adapter",
        adapter_version="4C.0",
        format_id="STEP-GENERIC",
        capability_level=CapabilityLevel.LEVEL_2_NORMALIZED,
        normalization_status=NormalizationStatus.SUCCESS,
        domain_provenance=Provenance(
            source_type=ProvenanceType.USER_INPUT,
            source_reference="step-token-adapter@4C.0",
            source_document="test.step",
        ),
    )
    return ImportResult(
        import_id=f"import::{source_id}::step-token-adapter",
        status=ImportStatus.SUCCESS,
        document=document,
        diagnostics=diag,
        capability=cap,
        provenance=prov,
    )


def _fake_failed_result(source_id: str = "upload::bad.step") -> ImportResult:
    """Build a FAILED ImportResult for monkeypatching."""
    detection = FormatDetectionResult(
        detected_format_id="STEP-GENERIC",
        detection_confidence="MEDIUM",
        detection_method="file_extension",
    )
    diag = ImportDiagnostics(
        format_detection=detection,
        adapter_candidates=("step-token-adapter",),
        selected_adapter_id="step-token-adapter",
        selection_reason="adapter_raised_exception",
        fidelity_adverse_count=1,
        has_unsupported_content=False,
        has_loss=True,
        notes=("Adapter raised: malformed content",),
    )
    cap = CapabilityRecord(achieved_level=CapabilityLevel.LEVEL_0_RECOGNIZED)
    return ImportResult(
        import_id=f"import::{source_id}::step-token-adapter",
        status=ImportStatus.FAILED,
        document=None,
        diagnostics=diag,
        capability=cap,
        error_message="malformed content",
    )


@pytest.fixture()
def successful_import_html(client: TestClient) -> str:
    fake = _fake_success_result()
    with patch("frontend.routers.ui.CadImportOrchestrator") as mock_cls:
        mock_cls.return_value.import_source.return_value = fake
        response = client.post(
            "/ui/cad-import",
            files={"file": ("test.step", _STEP_UPLOAD, "application/octet-stream")},
        )
    assert response.status_code == 200
    return response.text


# -- GET /ui/cad-import ----------------------------------------------------

class TestCadImportGet:
    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/ui/cad-import")
        assert resp.status_code == 200

    def test_contains_title(self, client: TestClient) -> None:
        assert "CAD Import" in client.get("/ui/cad-import").text

    def test_contains_form(self, client: TestClient) -> None:
        html = client.get("/ui/cad-import").text
        assert 'enctype="multipart/form-data"' in html

    def test_sidebar_link_correct(self, client: TestClient) -> None:
        html = client.get("/ui/cad-import").text
        assert 'href="/ui/cad-import"' in html

    def test_shows_accepted_formats(self, client: TestClient) -> None:
        html = client.get("/ui/cad-import").text
        assert ".step" in html
        assert ".dxf" in html
        assert ".iges" in html


# -- POST /ui/cad-import: validation errors --------------------------------

class TestCadImportValidation:
    def test_empty_upload_rejected(self, client: TestClient) -> None:
        resp = client.post("/ui/cad-import")
        assert resp.status_code == 200
        assert "No file was uploaded" in resp.text

    def test_unsupported_extension_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/ui/cad-import",
            files={"file": ("model.stl", b"solid test", "application/octet-stream")},
        )
        assert resp.status_code == 200
        assert "Unsupported file extension" in resp.text

    def test_empty_file_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/ui/cad-import",
            files={"file": ("test.step", b"", "application/octet-stream")},
        )
        assert resp.status_code == 200
        assert "empty" in resp.text.lower()


# -- POST /ui/cad-import: backend integration -----------------------------

class TestCadImportOrchestration:
    def test_successful_import_shows_status(self, client: TestClient) -> None:
        fake = _fake_success_result()
        with patch(
            "frontend.routers.ui.CadImportOrchestrator"
        ) as mock_cls:
            mock_cls.return_value.import_source.return_value = fake
            resp = client.post(
                "/ui/cad-import",
                files={"file": ("test.step", _STEP_UPLOAD, "application/octet-stream")},
            )
        assert resp.status_code == 200
        html = resp.text
        assert "SUCCESS" in html
        assert "step-token-adapter" in html
        assert "STEP-GENERIC" in html

    def test_failed_import_shows_error(self, client: TestClient) -> None:
        fake = _fake_failed_result()
        with patch(
            "frontend.routers.ui.CadImportOrchestrator"
        ) as mock_cls:
            mock_cls.return_value.import_source.return_value = fake
            resp = client.post(
                "/ui/cad-import",
                files={"file": ("bad.step", _STEP_UPLOAD, "application/octet-stream")},
            )
        assert resp.status_code == 200
        html = resp.text
        assert "FAILED" in html
        assert "rejected during import validation" in html
        assert "malformed content" not in html

    def test_no_traceback_on_exception(self, client: TestClient) -> None:
        with patch(
            "frontend.routers.ui.CadImportOrchestrator"
        ) as mock_cls:
            mock_cls.return_value.import_source.side_effect = RuntimeError("boom")
            resp = client.post(
                "/ui/cad-import",
                files={"file": ("test.step", _STEP_UPLOAD, "application/octet-stream")},
            )
        assert resp.status_code == 200
        html = resp.text
        assert "Traceback" not in html
        assert "boom" not in html
        assert "internal error" in html.lower()

    def test_result_shows_real_fields(self, client: TestClient) -> None:
        fake = _fake_success_result()
        with patch(
            "frontend.routers.ui.CadImportOrchestrator"
        ) as mock_cls:
            mock_cls.return_value.import_source.return_value = fake
            resp = client.post(
                "/ui/cad-import",
                files={"file": ("test.step", _STEP_UPLOAD, "application/octet-stream")},
            )
        html = resp.text
        # All these are real fields from ImportResult
        assert "LEVEL_2_NORMALIZED" in html
        assert "SUCCESS" in html
        assert "CAD_GEOMETRY" in html
        assert "4A.0" in html

    def test_no_fake_data_generated(self, client: TestClient) -> None:
        fake = _fake_success_result()
        with patch(
            "frontend.routers.ui.CadImportOrchestrator"
        ) as mock_cls:
            mock_cls.return_value.import_source.return_value = fake
            resp = client.post(
                "/ui/cad-import",
                files={"file": ("test.step", _STEP_UPLOAD, "application/octet-stream")},
            )
        html = resp.text
        # Should NOT contain fabricated data
        assert "Loading" not in html
        assert "progress" not in html.lower() or "progress" in html.lower()
        assert "3D" not in html


class TestCadImportAdvancedDetails:
    def test_trigger_is_an_accessible_collapsed_button(
        self, successful_import_html: str
    ) -> None:
        parser = _AdvancedDetailsParser()
        parser.feed(successful_import_html)

        assert parser.trigger["type"] == "button"
        assert parser.trigger["aria-expanded"] == "false"
        assert parser.trigger["aria-controls"] == "cad-import-advanced-panel"
        assert "data-cad-import-accordion" in parser.trigger

    def test_controlled_panel_starts_hidden_with_all_detail_cards(
        self, successful_import_html: str
    ) -> None:
        parser = _AdvancedDetailsParser()
        parser.feed(successful_import_html)

        assert "hidden" in parser.panel
        panel_text = " ".join(parser.panel_text)
        assert "Adapter" in panel_text
        assert "Fidelity" in panel_text
        assert "Provenance" in panel_text

    def test_page_loads_the_accordion_behavior(
        self, successful_import_html: str
    ) -> None:
        parser = _AdvancedDetailsParser()
        parser.feed(successful_import_html)

        assert "/static/js/cad-import.js" in parser.script_sources


class TestCadImportApi:
    def test_success_response_uses_strict_safe_allowlist(self, client: TestClient) -> None:
        response = client.post(
            "/api/cad-import",
            files={"file": ("part.step", _STEP_UPLOAD, "application/octet-stream")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert set(payload) == {
            "filename",
            "detected_format",
            "file_size",
            "sha256",
            "adapter_status",
            "parse_status",
            "diagnostics",
            "geometry_summary",
            "topology_summary",
        }
        assert payload["sha256"] == hashlib.sha256(_STEP_UPLOAD).hexdigest()
        forbidden = {"document", "source", "notes", "content_path"}
        assert forbidden.isdisjoint(payload)

    def test_failed_iges_ui_does_not_echo_private_parameter_token(
        self, client: TestClient
    ) -> None:
        private_token = "RAW_PRIVATE_PAYLOAD_ABC"
        upload = make_iges(
            (EntitySpec(110, f"110,{private_token},0,0,1,2,3;"),)
        )

        response = client.post(
            "/ui/cad-import",
            files={"file": ("private.igs", upload, "model/iges")},
        )

        assert response.status_code == 200
        assert private_token not in response.text

    def test_ui_redacts_untrusted_orchestrator_error_text(
        self, client: TestClient
    ) -> None:
        private_token = "RAW_PRIVATE_PAYLOAD_ABC"
        failed = replace(_fake_failed_result(), error_message=private_token)
        with patch("frontend.routers.ui.CadImportOrchestrator") as mock_cls:
            mock_cls.return_value.import_source.return_value = failed
            response = client.post(
                "/ui/cad-import",
                files={"file": ("private.igs", _IGES_BREP_UPLOAD, "model/iges")},
            )

        assert response.status_code == 200
        assert private_token not in response.text
        assert "rejected during import validation" in response.text

    def test_level1_step_parser_is_conditional_without_occt(
        self, client: TestClient
    ) -> None:
        with patch(
            "backend.interoperability.adapters.step.StepTokenAdapter._occt_available",
            return_value=False,
        ):
            response = client.post(
                "/api/cad-import",
                files={"file": ("part.step", _STEP_UPLOAD, "model/step")},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["adapter_status"] == "CONDITIONAL"
        assert payload["parse_status"] in {"DEGRADED", "PARTIAL", "SUCCESS"}
        assert payload["geometry_summary"] is None
        assert payload["topology_summary"] is None

    def test_available_level2_result_is_live_without_fabricated_geometry(
        self, client: TestClient
    ) -> None:
        fake = _fake_success_result()
        with patch("frontend.routers.ui.CadImportOrchestrator") as mock_cls:
            mock_cls.return_value.import_source.return_value = fake
            response = client.post(
                "/api/cad-import",
                files={"file": ("part.step", _STEP_UPLOAD, "application/octet-stream")},
            )

        payload = response.json()
        assert payload["adapter_status"] == "LIVE"
        assert payload["parse_status"] == "SUCCESS"
        assert payload["geometry_summary"] is None
        assert payload["topology_summary"] is None

    def test_failed_parse_does_not_hide_live_adapter(self, client: TestClient) -> None:
        fake = _fake_failed_result()
        with patch("frontend.routers.ui.CadImportOrchestrator") as mock_cls:
            mock_cls.return_value.import_source.return_value = fake
            response = client.post(
                "/api/cad-import",
                files={"file": ("bad.step", _STEP_UPLOAD, "application/octet-stream")},
            )

        payload = response.json()
        assert payload["adapter_status"] == "LIVE"
        assert payload["parse_status"] == "FAILED"

    def test_binary_dxf_reports_unavailable_without_parser_claim(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/api/cad-import",
            files={"file": ("binary.dxf", b"AutoCAD Binary DXF\r\n", "application/dxf")},
        )

        assert response.status_code == 415
        payload = response.json()
        assert payload["adapter_status"] == "UNAVAILABLE"
        assert payload["parse_status"] == "REJECTED"

    def test_html_displays_hash_and_explicit_statuses(self, client: TestClient) -> None:
        fake = _fake_success_result()
        with patch("frontend.routers.ui.CadImportOrchestrator") as mock_cls:
            mock_cls.return_value.import_source.return_value = fake
            response = client.post(
                "/ui/cad-import",
                files={"file": ("part.step", _STEP_UPLOAD, "application/octet-stream")},
            )

        html = response.text
        assert hashlib.sha256(_STEP_UPLOAD).hexdigest() in html
        assert "Adapter Status" in html
        assert "Parse Status" in html

    def test_real_iges_upload_reports_canonical_geometry_and_topology_counts(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/api/cad-import",
            files={"file": ("triangle.igs", _IGES_BREP_UPLOAD, "model/iges")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["adapter_status"] == "LIVE"
        assert payload["parse_status"] == "SUCCESS"
        assert payload["geometry_summary"] == {
            "curve_count": 3,
            "surface_count": 1,
            "has_bounding_box": False,
            "source_unit": "MM",
            "tolerance_mm": "0.001",
        }
        assert payload["topology_summary"] == {
            "vertex_count": 3,
            "edge_count": 3,
            "loop_count": 1,
            "face_count": 1,
            "shell_count": 1,
            "body_count": 1,
        }

    def test_unsupported_iges_entity_is_bounded_and_safe_in_diagnostics(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/api/cad-import",
            files={
                "file": (
                    "unsupported.iges",
                    _IGES_UNSUPPORTED_UPLOAD,
                    "model/iges",
                )
            },
        )

        assert response.status_code == 200
        payload = response.json()
        unsupported = payload["diagnostics"]["unsupported_entities"]
        assert payload["topology_summary"] is None
        assert len(unsupported) == 1
        assert "type=118" in unsupported[0]
        assert "unsupported" in unsupported[0].lower()
        assert len(unsupported[0]) <= 240
        serialized = response.text
        assert "118,1,3,0,0" not in serialized
        assert tempfile.gettempdir() not in serialized


class TestCadImportFailClosed:
    @pytest.mark.parametrize(
        ("filename", "content", "content_type", "expected_status"),
        [
            ("empty.step", b"", "application/octet-stream", 400),
            ("model.stl", b"solid test", "application/octet-stream", 415),
            ("wrong.step", b"A" * 72 + b"S      1\n", "application/octet-stream", 415),
            ("wrong.dxf", _STEP_UPLOAD, "application/octet-stream", 415),
            ("wrong.step", _STEP_UPLOAD, "application/pdf", 415),
            ("binary.dxf", b"AutoCAD Binary DXF\r\n", "application/dxf", 415),
        ],
    )
    def test_rejected_upload_does_not_construct_orchestrator(
        self,
        client: TestClient,
        filename: str,
        content: bytes,
        content_type: str,
        expected_status: int,
    ) -> None:
        with patch("frontend.routers.ui.CadImportOrchestrator") as mock_cls:
            response = client.post(
                "/api/cad-import",
                files={"file": (filename, content, content_type)},
            )

        assert response.status_code == expected_status
        mock_cls.assert_not_called()

    def test_limit_plus_one_is_rejected_before_orchestrator(
        self, client: TestClient
    ) -> None:
        with patch("frontend.routers.ui.CadImportOrchestrator") as mock_cls:
            response = client.post(
                "/api/cad-import",
                files={
                    "file": (
                        "oversized.step",
                        b"x" * (MAX_CAD_UPLOAD_BYTES + 1),
                        "application/octet-stream",
                    )
                },
            )

        assert response.status_code == 413
        mock_cls.assert_not_called()

    def test_rejected_and_failed_requests_clean_staged_paths(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        paths: list[Path] = []
        original_factory = tempfile.NamedTemporaryFile

        def recording_factory(*args: object, **kwargs: object):
            handle = original_factory(*args, **kwargs)
            paths.append(Path(handle.name))
            return handle

        monkeypatch.setattr(
            "frontend.cad_upload.tempfile.NamedTemporaryFile", recording_factory
        )

        fake = _fake_success_result()
        with patch("frontend.routers.ui.CadImportOrchestrator") as mock_cls:
            mock_cls.return_value.import_source.return_value = fake
            assert client.post(
                "/api/cad-import",
                files={"file": ("ok.step", _STEP_UPLOAD, "application/octet-stream")},
            ).status_code == 200

        assert client.post(
            "/api/cad-import",
            files={"file": ("bad.stl", b"solid", "application/octet-stream")},
        ).status_code == 415

        with patch("frontend.routers.ui.CadImportOrchestrator") as mock_cls:
            mock_cls.return_value.import_source.return_value = _fake_failed_result()
            assert client.post(
                "/api/cad-import",
                files={"file": ("failed.step", _STEP_UPLOAD, "application/octet-stream")},
            ).status_code == 200

        with patch("frontend.routers.ui.CadImportOrchestrator") as mock_cls:
            mock_cls.return_value.import_source.side_effect = RuntimeError("secret")
            assert client.post(
                "/api/cad-import",
                files={"file": ("raised.step", _STEP_UPLOAD, "application/octet-stream")},
            ).status_code == 500

        with patch(
            "frontend.routers.ui._result_to_safe_summary",
            side_effect=RuntimeError("render secret"),
        ), patch("frontend.routers.ui.CadImportOrchestrator") as mock_cls:
            mock_cls.return_value.import_source.return_value = fake
            assert client.post(
                "/api/cad-import",
                files={"file": ("render.step", _STEP_UPLOAD, "application/octet-stream")},
            ).status_code == 500

        assert paths
        assert all(not path.exists() for path in paths)

    def test_adapter_exception_does_not_leak_upload_marker_or_path(
        self,
        client: TestClient,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        marker = "RAW_MARKER_AFTER_512"
        paths: list[Path] = []
        original_factory = tempfile.NamedTemporaryFile

        def recording_factory(*args: object, **kwargs: object):
            handle = original_factory(*args, **kwargs)
            paths.append(Path(handle.name))
            return handle

        monkeypatch.setattr(
            "frontend.cad_upload.tempfile.NamedTemporaryFile", recording_factory
        )
        caplog.set_level(logging.ERROR)
        with patch("frontend.routers.ui.CadImportOrchestrator") as mock_cls:
            mock_cls.return_value.import_source.side_effect = RuntimeError(
                f"{marker}:{paths!r}"
            )
            response = client.post(
                "/api/cad-import",
                files={
                    "file": (
                        "secret.step",
                        _STEP_UPLOAD + marker.encode(),
                        "application/octet-stream",
                    )
                },
            )

        assert response.status_code == 500
        assert marker not in response.text
        assert marker not in caplog.text
        assert paths and all(str(path) not in response.text for path in paths)
        assert all(not path.exists() for path in paths)
