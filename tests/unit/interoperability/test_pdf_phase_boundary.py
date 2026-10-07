"""Phase 1B / 1C boundary tests.

``VectorPdfDrawingParser`` is the pure Phase 1B path and must never reach OCR,
raster decoding, GD&T recognition or any AI stage. ``PdfDrawingParser`` is the
composed compatibility path that still enriches with Phase 1C OCR and GD&T.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import asdict
from decimal import Decimal

import pytest

import backend.interoperability.ocr_drawing as ocr_drawing
import backend.interoperability.pdf_drawing as pdf_drawing
import backend.interoperability.raster_drawing as raster_drawing
from backend.interoperability.drawing import DrawingIngestionStatus, DrawingParser
from backend.interoperability.ocr_drawing import OcrResult
from backend.interoperability.pdf_drawing import (
    PdfDrawingLimits,
    PdfDrawingParser,
    VectorPdfDrawingParser,
)
from tests.unit.interoperability.ocr_fixtures import (
    SyntheticRasterDrawingBuilder,
    SyntheticRasterPdfBuilder,
)
from tests.unit.interoperability.pdf_fixtures import PdfTextSpec, SyntheticPdfBuilder
from tests.unit.interoperability.test_pdf_drawing import _title_grid_specs, _title_pdf

_SOURCE = "synthetic::boundary.pdf"


def _vector_pdf(*texts: str, include_image: bool = False) -> bytes:
    builder = SyntheticPdfBuilder()
    builder.add_vector_page(
        width_pt=300,
        height_pt=200,
        texts=tuple(
            PdfTextSpec(text=text, x=Decimal("40"), y=Decimal(str(150 - index * 25)))
            for index, text in enumerate(texts)
        ),
        include_image=include_image,
    )
    return builder.build()


def _raster_only_pdf() -> bytes:
    image = SyntheticRasterDrawingBuilder(width=40, height=40).build()
    return SyntheticRasterPdfBuilder().add_page(image).build()


@pytest.fixture
def forbidden_calls(monkeypatch):
    """Spy on every Phase 1C / later entry point; record each invocation."""
    calls: list[str] = []

    def _spy(name: str):
        def _raise(*args, **kwargs):
            calls.append(name)
            raise AssertionError(f"{name} must not run on the Phase 1B path")

        return _raise

    for module, name in (
        (pdf_drawing, "extract_ocr_from_pdf"),
        (ocr_drawing, "extract_ocr_from_pdf"),
        (raster_drawing, "prepare_raster_ocr_inputs"),
        (pdf_drawing, "recognize_feature_control_frames"),
        (pdf_drawing, "attach_feature_control_frames"),
        (pdf_drawing, "_apply_gdt"),
    ):
        monkeypatch.setattr(module, name, _spy(f"{module.__name__}.{name}"))
    return calls


class TestVectorParserIdentity:
    def test_class_hierarchy_and_exports(self):
        assert issubclass(VectorPdfDrawingParser, DrawingParser)
        assert issubclass(PdfDrawingParser, VectorPdfDrawingParser)
        assert "VectorPdfDrawingParser" in pdf_drawing.__all__

    def test_vector_class_source_has_no_later_phase_references(self):
        source = inspect.getsource(VectorPdfDrawingParser)
        for forbidden in (
            "extract_ocr_from_pdf",
            "prepare_raster_ocr_inputs",
            "pytesseract",
            "recognize_feature_control_frames",
            "attach_feature_control_frames",
            "_apply_gdt",
            "ai_provider",
        ):
            assert forbidden not in source

    def test_vector_parser_id_is_shared_and_stable(self):
        assert VectorPdfDrawingParser().parser_id() == PdfDrawingParser().parser_id()
        assert VectorPdfDrawingParser().parser_version() == PdfDrawingParser().parser_version()

    def test_limits_type_is_validated(self):
        with pytest.raises(TypeError):
            VectorPdfDrawingParser(limits=object())  # type: ignore[arg-type]


class TestPurePhase1BPath:
    def test_s01_valid_vector_pdf_succeeds(self, forbidden_calls):
        result = VectorPdfDrawingParser().parse(
            _SOURCE, "d.pdf", _vector_pdf("25 ±0.10 mm", "DIA 10 mm")
        )
        assert result.diagnostics.status is DrawingIngestionStatus.VALID
        assert result.document is not None
        assert len(result.document.all_dimensions) == 2
        assert forbidden_calls == []

    def test_s02_raster_only_never_calls_ocr(self, forbidden_calls):
        result = VectorPdfDrawingParser().parse(_SOURCE, "d.pdf", _raster_only_pdf())
        assert result.diagnostics.status is DrawingIngestionStatus.UNSUPPORTED
        assert "PDF_RASTER_ONLY" in result.diagnostics.warnings
        assert result.document is None
        assert forbidden_calls == []

    def test_s03_mixed_vector_and_raster_never_calls_ocr(self, forbidden_calls):
        result = VectorPdfDrawingParser().parse(
            _SOURCE, "d.pdf", _vector_pdf("25 mm", include_image=True)
        )
        assert result.diagnostics.status is DrawingIngestionStatus.VALID
        assert result.document is not None
        assert len(result.document.all_dimensions) == 1
        assert forbidden_calls == []

    def test_s04_never_invokes_gdt_recognition(self, forbidden_calls):
        result = VectorPdfDrawingParser().parse(
            _SOURCE, "d.pdf", _vector_pdf("25 mm", "POSITION 0.1 A")
        )
        assert result.diagnostics.status in {
            DrawingIngestionStatus.VALID,
            DrawingIngestionStatus.PARTIAL,
        }
        assert result.document is not None
        assert result.document.all_gdt_references == ()
        assert forbidden_calls == []

    def test_s05_vector_title_block_still_works(self, forbidden_calls):
        payload = _title_pdf(
            _title_grid_specs((("DRAWING NO", "D-100"), ("REV", "A"))),
            width_pt=700,
            height_pt=560,
        )
        result = VectorPdfDrawingParser().parse(_SOURCE, "d.pdf", payload)
        assert result.diagnostics.status is DrawingIngestionStatus.VALID
        assert result.document is not None
        assert result.document.title_block is not None
        assert result.document.title_block.drawing_number == "D-100"
        assert forbidden_calls == []

    def test_s06_vector_dimension_still_works(self, forbidden_calls):
        result = VectorPdfDrawingParser().parse(_SOURCE, "d.pdf", _vector_pdf("DIA 30 mm"))
        assert result.document is not None
        dimension = result.document.all_dimensions[0]
        assert (str(dimension.nominal_value), dimension.unit) == ("30", "mm")
        assert forbidden_calls == []

    def test_s07_vector_tolerance_still_works(self, forbidden_calls):
        result = VectorPdfDrawingParser().parse(
            _SOURCE, "d.pdf", _vector_pdf("25 ±0.10 mm")
        )
        assert result.document is not None
        assert len(result.document.all_tolerances) == 1
        assert forbidden_calls == []

    def test_s08_malformed_pdf_fails_closed(self, forbidden_calls):
        result = VectorPdfDrawingParser().parse(
            _SOURCE, "d.pdf", b"%PDF-1.4\ntruncated"
        )
        assert result.diagnostics.status is DrawingIngestionStatus.FAILED
        assert result.document is None
        assert forbidden_calls == []

    def test_s09_encrypted_pdf_is_unsupported(self, forbidden_calls):
        payload = b"%PDF-1.4\ntrailer\n<< /Encrypt 1 0 R >>\nstartxref\n0\n%%EOF"
        result = VectorPdfDrawingParser().parse(_SOURCE, "d.pdf", payload)
        assert result.diagnostics.status is DrawingIngestionStatus.UNSUPPORTED
        assert result.diagnostics.warnings == ("PDF_ENCRYPTED",)
        assert forbidden_calls == []

    def test_s10_resource_limit_is_enforced(self, forbidden_calls):
        payload = _vector_pdf("25 mm")
        parser = VectorPdfDrawingParser(
            limits=PdfDrawingLimits(max_file_bytes=len(payload) - 1)
        )
        result = parser.parse(_SOURCE, "d.pdf", payload)
        assert result.diagnostics.status is DrawingIngestionStatus.FAILED
        assert result.diagnostics.errors == ("PDF_RESOURCE_LIMIT",)
        assert forbidden_calls == []

    def test_s11_repeated_parse_is_deterministic(self, forbidden_calls):
        payload = _vector_pdf("25 ±0.10 mm", "DIA 10 mm")
        first = VectorPdfDrawingParser().parse(_SOURCE, "d.pdf", payload)
        second = VectorPdfDrawingParser().parse(_SOURCE, "d.pdf", payload)
        assert first == second
        assert json.dumps(asdict(first), sort_keys=True, default=str) == json.dumps(
            asdict(second), sort_keys=True, default=str
        )
        assert forbidden_calls == []

    def test_vector_output_matches_enriched_output_for_pure_vector_input(self):
        payload = _vector_pdf("25 ±0.10 mm", "DIA 10 mm")
        assert VectorPdfDrawingParser().parse(_SOURCE, "d.pdf", payload) == (
            PdfDrawingParser().parse(_SOURCE, "d.pdf", payload)
        )


class TestEnrichedPath:
    def test_s12_enriched_path_still_invokes_ocr(self, monkeypatch):
        calls: list[str] = []

        def _fake_ocr(payload, source_id):
            calls.append(source_id)
            return OcrResult(DrawingIngestionStatus.VALID, evidence=())

        monkeypatch.setattr(pdf_drawing, "extract_ocr_from_pdf", _fake_ocr)
        PdfDrawingParser().parse(_SOURCE, "d.pdf", _vector_pdf("25 mm", include_image=True))
        assert calls == [_SOURCE]

    def test_enriched_path_still_invokes_gdt(self, monkeypatch):
        calls: list[int] = []
        original = pdf_drawing.recognize_feature_control_frames

        def _spy(tokens):
            calls.append(len(tokens))
            return original(tokens)

        monkeypatch.setattr(pdf_drawing, "recognize_feature_control_frames", _spy)
        PdfDrawingParser().parse(_SOURCE, "d.pdf", _vector_pdf("25 mm"))
        assert calls

    def test_vector_path_does_not_ocr_where_enriched_does(self, monkeypatch):
        calls: list[str] = []

        def _fake_ocr(payload, source_id):
            calls.append(source_id)
            return OcrResult(DrawingIngestionStatus.VALID, evidence=())

        monkeypatch.setattr(pdf_drawing, "extract_ocr_from_pdf", _fake_ocr)
        payload = _vector_pdf("25 mm", include_image=True)
        VectorPdfDrawingParser().parse(_SOURCE, "d.pdf", payload)
        assert calls == []
        PdfDrawingParser().parse(_SOURCE, "d.pdf", payload)
        assert calls == [_SOURCE]
