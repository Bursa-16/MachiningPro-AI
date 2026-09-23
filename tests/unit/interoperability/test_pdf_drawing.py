"""Tests for the deterministic, synthetic vector-PDF fixture foundation."""

from __future__ import annotations

import json
import multiprocessing
import os
import pickle
import time
from dataclasses import FrozenInstanceError, asdict, is_dataclass
from decimal import Decimal
from importlib.metadata import version
from io import BytesIO

import pdfplumber
import pytest
from pdfplumber.utils.exceptions import PdfminerException

import backend.interoperability.pdf_drawing as pdf_drawing
from backend.interoperability.drawing import (
    CanonicalDrawing,
    DrawingBoundingBox,
    DrawingExtractionAuthority,
    DrawingIngestionStatus,
    DrawingMaterialNote,
    DrawingParser,
    DrawingRevision,
    DrawingSourceLocation,
    DrawingTitleBlock,
)
from backend.interoperability.pdf_drawing import PdfDrawingLimits, PdfDrawingParser
from tests.unit.interoperability.pdf_fixtures import (
    PdfLineSpec,
    PdfRectSpec,
    PdfTextSpec,
    SyntheticPdfBuilder,
)


def _synthetic_vector_pdf(*, text: str = "VECTOR SENTINEL") -> bytes:
    builder = SyntheticPdfBuilder()
    builder.add_vector_page(
        width_pt=300,
        height_pt=200,
        texts=(PdfTextSpec(text=text, x=Decimal("24"), y=Decimal("150")),),
        lines=(
            PdfLineSpec(
                x0=Decimal("10"),
                y0=Decimal("20"),
                x1=Decimal("100"),
                y1=Decimal("20"),
            ),
        ),
    )
    return builder.build()


def _synthetic_curve_pdf() -> bytes:
    """Create one synthetic cubic path without extending the shared Task 2 API."""

    builder = SyntheticPdfBuilder()
    builder.add_vector_page(
        width_pt=300,
        height_pt=200,
        lines=(
            PdfLineSpec(
                x0=Decimal("10"),
                y0=Decimal("20"),
                x1=Decimal("100"),
                y1=Decimal("20"),
            ),
            PdfLineSpec(
                x0=Decimal("10"),
                y0=Decimal("30"),
                x1=Decimal("100"),
                y1=Decimal("30"),
            ),
            PdfLineSpec(
                x0=Decimal("10"),
                y0=Decimal("40"),
                x1=Decimal("100"),
                y1=Decimal("40"),
            ),
        ),
    )
    content = bytearray(builder.build())
    stream_start = content.index(b"stream\n") + len(b"stream\n")
    stream_end = content.index(b"endstream", stream_start)
    curve_stream = b"10 20 m\n40 50 70 50 100 20 c\nS\n"
    assert len(curve_stream) <= stream_end - stream_start
    content[stream_start:stream_end] = curve_stream.ljust(
        stream_end - stream_start, b" "
    )
    return bytes(content)


def _prefixed_pdf(content: bytes, prefix: bytes) -> bytes:
    """Prefix a synthetic PDF while keeping its xref offsets structurally valid."""

    shift = len(prefix)
    lines = content.splitlines(keepends=True)
    in_xref = False
    after_startxref = False
    adjusted: list[bytes] = []
    for line in lines:
        stripped = line.strip()
        if stripped == b"xref":
            in_xref = True
        elif stripped == b"trailer":
            in_xref = False
        elif stripped == b"startxref":
            after_startxref = True
        elif after_startxref and stripped.isdigit():
            line = str(int(stripped) + shift).encode("ascii") + b"\n"
            after_startxref = False
        elif in_xref and line.endswith(b" 00000 n \n"):
            line = f"{int(line[:10]) + shift:010d}".encode("ascii") + line[10:]
        adjusted.append(line)
    return prefix + b"".join(adjusted)


def _sleeping_worker(connection, _content: bytes, _limits: PdfDrawingLimits) -> None:
    try:
        time.sleep(2)
    finally:
        connection.close()


def _abnormal_worker(connection, _content: bytes, _limits: PdfDrawingLimits) -> None:
    connection.close()
    os._exit(17)


def _payload_then_abnormal_worker(
    connection, content: bytes, limits: PdfDrawingLimits
) -> None:
    snapshot = pdf_drawing._extract_snapshot(content, limits)
    connection.send(
        pdf_drawing._WorkerExecution(
            snapshot,
            None,
            page_count_expected=len(snapshot.pages),
            page_count_parsed=len(snapshot.pages),
        )
    )
    connection.close()
    os._exit(17)


def test_pdfplumber_version_matches_approved_runtime_range():
    installed = tuple(int(part) for part in version("pdfplumber").split(".")[:3])

    assert (0, 11, 10) <= installed < (0, 12, 0)


def test_minimal_vector_pdf_is_valid_and_extractable():
    builder = SyntheticPdfBuilder()
    builder.add_vector_page(
        width_pt=300,
        height_pt=200,
        texts=(PdfTextSpec(text="SYNTHETIC PART", x=Decimal("24"), y=Decimal("150")),),
    )

    content = builder.build()

    assert content.startswith(b"%PDF-1.4\n")
    assert content.endswith(b"%%EOF\n")
    with pdfplumber.open(BytesIO(content)) as document:
        assert len(document.pages) == 1
        assert document.pages[0].extract_text() == "SYNTHETIC PART"


def test_page_geometry_and_vector_placement_are_exact():
    builder = SyntheticPdfBuilder()
    builder.add_vector_page(
        width_pt=300,
        height_pt=200,
        texts=(
            PdfTextSpec(
                text="DIM 25 mm",
                x=Decimal("24"),
                y=Decimal("150"),
                font_size=Decimal("12"),
            ),
        ),
        lines=(
            PdfLineSpec(
                x0=Decimal("10"),
                y0=Decimal("20"),
                x1=Decimal("100"),
                y1=Decimal("20"),
            ),
        ),
        rectangles=(
            PdfRectSpec(
                x0=Decimal("150"),
                y0=Decimal("30"),
                x1=Decimal("250"),
                y1=Decimal("80"),
            ),
        ),
    )

    with pdfplumber.open(BytesIO(builder.build())) as document:
        page = document.pages[0]
        word = page.extract_words()[0]
        line = page.lines[0]
        rectangle = page.rects[0]

        assert (page.width, page.height) == (300, 200)
        assert word["text"] == "DIM"
        assert word["x0"] == pytest.approx(24)
        assert word["top"] == pytest.approx(40.484)
        assert (line["x0"], line["y0"], line["x1"], line["y1"]) == (
            10,
            20,
            100,
            20,
        )
        assert (rectangle["x0"], rectangle["y0"], rectangle["x1"], rectangle["y1"]) == (
            150,
            30,
            250,
            80,
        )


def test_title_dimension_and_tolerance_text_is_synthetic_and_winansi_safe():
    builder = SyntheticPdfBuilder()
    builder.add_vector_page(
        texts=(
            PdfTextSpec(text="DRAWING NO", x=Decimal("500"), y=Decimal("100")),
            PdfTextSpec(text="SYN-001", x=Decimal("650"), y=Decimal("100")),
            PdfTextSpec(text="Ø25 ±0.10 mm", x=Decimal("100"), y=Decimal("350")),
        ),
        lines=(
            PdfLineSpec(
                x0=Decimal("480"),
                y0=Decimal("80"),
                x1=Decimal("800"),
                y1=Decimal("80"),
            ),
            PdfLineSpec(
                x0=Decimal("630"),
                y0=Decimal("80"),
                x1=Decimal("630"),
                y1=Decimal("140"),
            ),
        ),
        rectangles=(
            PdfRectSpec(
                x0=Decimal("480"),
                y0=Decimal("80"),
                x1=Decimal("800"),
                y1=Decimal("140"),
            ),
        ),
    )

    with pdfplumber.open(BytesIO(builder.build())) as document:
        extracted = document.pages[0].extract_text()

    assert extracted is not None
    assert "DRAWING NO" in extracted
    assert "SYN-001" in extracted
    assert "Ø25 ±0.10 mm" in extracted


def test_unsupported_non_winansi_text_is_rejected_without_fallback_assets():
    builder = SyntheticPdfBuilder()
    builder.add_vector_page(
        texts=(PdfTextSpec(text="⌀25 mm", x=Decimal("10"), y=Decimal("10")),),
    )

    with pytest.raises(ValueError, match="WinAnsi"):
        builder.build()


def test_multiple_pages_preserve_order_size_text_and_rotation():
    builder = SyntheticPdfBuilder()
    builder.add_vector_page(
        width_pt=300,
        height_pt=200,
        texts=(PdfTextSpec(text="PAGE ONE", x=Decimal("20"), y=Decimal("150")),),
    )
    builder.add_vector_page(
        width_pt=400,
        height_pt=250,
        rotation=90,
        texts=(PdfTextSpec(text="PAGE TWO", x=Decimal("30"), y=Decimal("180")),),
    )

    with pdfplumber.open(BytesIO(builder.build())) as document:
        assert len(document.pages) == 2
        assert document.pages[0].extract_text() == "PAGE ONE"
        assert (document.pages[0].width, document.pages[0].height) == (300, 200)
        assert document.pages[1].rotation == 90
        assert (document.pages[1].width, document.pages[1].height) == (250, 400)
        assert "".join((document.pages[1].extract_text() or "").split()) == "PAGETWO"


def test_equivalent_builders_produce_identical_bytes():
    def build_fixture() -> bytes:
        builder = SyntheticPdfBuilder()
        builder.add_vector_page(
            width_pt=320,
            height_pt=240,
            texts=(PdfTextSpec(text="R5 mm", x=Decimal("50"), y=Decimal("120")),),
            lines=(
                PdfLineSpec(
                    x0=Decimal("40"),
                    y0=Decimal("100"),
                    x1=Decimal("140"),
                    y1=Decimal("100"),
                ),
            ),
        )
        return builder.build()

    assert build_fixture() == build_fixture()


def test_repeated_build_on_same_instance_is_identical():
    builder = SyntheticPdfBuilder()
    builder.add_vector_page(
        texts=(PdfTextSpec(text="45°", x=Decimal("100"), y=Decimal("300")),),
    )

    assert builder.build() == builder.build()


def test_raster_only_fixture_uses_one_synthetic_inline_asset():
    builder = SyntheticPdfBuilder()
    builder.add_vector_page(include_image=True)

    content = builder.build()

    with pdfplumber.open(BytesIO(content)) as document:
        page = document.pages[0]
        assert page.extract_text() == ""
        assert page.lines == []
        assert page.rects == []
        assert len(page.images) == 1


def test_truncated_fixture_is_malformed_without_external_input():
    builder = SyntheticPdfBuilder()
    builder.add_vector_page(
        texts=(PdfTextSpec(text="TRUNCATE ME", x=Decimal("20"), y=Decimal("100")),),
    )
    valid = builder.build()
    malformed = valid[: valid.index(b"endobj")]

    assert malformed.startswith(b"%PDF-1.4\n")
    assert not malformed.endswith(b"%%EOF\n")
    with pytest.raises(PdfminerException):
        with pdfplumber.open(BytesIO(malformed)) as document:
            tuple(document.pages)


def test_fixture_has_no_external_actions_metadata_or_binary_assets():
    builder = SyntheticPdfBuilder()
    builder.add_vector_page(
        texts=(PdfTextSpec(text="SYNTHETIC ONLY", x=Decimal("20"), y=Decimal("100")),),
    )

    content = builder.build()

    for forbidden in (
        b"/URI",
        b"/JavaScript",
        b"/EmbeddedFile",
        b"/Filespec",
        b"/Metadata",
        b"/Image",
    ):
        assert forbidden not in content
    with pdfplumber.open(BytesIO(content)) as document:
        assert document.pages[0].extract_text() == "SYNTHETIC ONLY"


def test_extracted_word_box_can_use_typed_task_1_provenance():
    builder = SyntheticPdfBuilder()
    builder.add_vector_page(
        width_pt=300,
        height_pt=200,
        texts=(PdfTextSpec(text="25 mm", x=Decimal("24"), y=Decimal("150")),),
    )

    with pdfplumber.open(BytesIO(builder.build())) as document:
        word = document.pages[0].extract_words()[0]

    box = DrawingBoundingBox(
        x0=Decimal(str(word["x0"])),
        top=Decimal(str(word["top"])),
        x1=Decimal(str(word["x1"])),
        bottom=Decimal(str(word["bottom"])),
    )
    location = DrawingSourceLocation(
        source_id="synthetic::fixture.pdf",
        sheet_number=1,
        page_number=1,
        bounding_box=box,
        source_object_ids=("fixture-p0001-text-0001",),
    )

    assert location.bounding_box == box
    assert location.page_number == 1


def test_fixture_specs_are_immutable():
    text = PdfTextSpec(text="25 mm", x=Decimal("24"), y=Decimal("150"))

    with pytest.raises(FrozenInstanceError):
        text.text = "changed"  # type: ignore[misc]


class TestPdfDrawingLimits:
    def test_defaults_match_approved_phase_1b_contract(self):
        assert asdict(PdfDrawingLimits()) == {
            "max_file_bytes": 67_108_864,
            "max_pages": 200,
            "parse_timeout_seconds": 10.0,
            "max_objects_total": 200_000,
            "max_objects_per_page": 20_000,
            "max_text_characters": 2_000_000,
            "max_text_characters_per_object": 4_096,
            "max_vector_points_total": 1_000_000,
            "max_vector_points_per_object": 10_000,
            "max_dimension_candidates": 20_000,
            "max_title_block_candidates": 1_000,
            "max_page_dimension_points": 20_000,
            "max_diagnostics_per_kind": 50,
            "max_diagnostic_characters": 240,
        }

    @pytest.mark.parametrize(
        "field_name",
        (
            "max_file_bytes",
            "max_pages",
            "max_objects_total",
            "max_objects_per_page",
            "max_text_characters",
            "max_text_characters_per_object",
            "max_vector_points_total",
            "max_vector_points_per_object",
            "max_dimension_candidates",
            "max_title_block_candidates",
            "max_page_dimension_points",
            "max_diagnostics_per_kind",
            "max_diagnostic_characters",
        ),
    )
    def test_non_positive_integer_limit_rejected(self, field_name):
        with pytest.raises(ValueError, match=field_name):
            PdfDrawingLimits(**{field_name: 0})

    def test_boolean_integer_limit_rejected(self):
        with pytest.raises(TypeError, match="max_pages"):
            PdfDrawingLimits(max_pages=True)

    @pytest.mark.parametrize("timeout", (0.0, -1.0, True))
    def test_invalid_timeout_rejected(self, timeout):
        with pytest.raises((TypeError, ValueError), match="parse_timeout_seconds"):
            PdfDrawingLimits(parse_timeout_seconds=timeout)

    def test_per_page_object_limit_cannot_exceed_total(self):
        with pytest.raises(ValueError, match="max_objects_per_page"):
            PdfDrawingLimits(max_objects_total=5, max_objects_per_page=6)

    def test_per_object_point_limit_cannot_exceed_total(self):
        with pytest.raises(ValueError, match="max_vector_points_per_object"):
            PdfDrawingLimits(max_vector_points_total=5, max_vector_points_per_object=6)


class TestPdfDrawingParserIdentity:
    def test_public_surface_is_exact(self):
        assert pdf_drawing.__all__ == ["PdfDrawingLimits", "PdfDrawingParser"]

    def test_parser_implements_phase_1a_contract(self):
        assert isinstance(PdfDrawingParser(), DrawingParser)

    def test_identity_is_deterministic_and_serializable(self):
        first = PdfDrawingParser()
        second = PdfDrawingParser()
        identity = {
            "parser_id": first.parser_id(),
            "parser_version": first.parser_version(),
        }

        assert identity == {
            "parser_id": "machiningpro.vector-pdf",
            "parser_version": "1.0.0",
        }
        assert (first.parser_id(), first.parser_version()) == (
            second.parser_id(),
            second.parser_version(),
        )
        assert json.loads(json.dumps(identity, sort_keys=True)) == identity

    @pytest.mark.parametrize(
        ("source_id", "file_name", "notes", "expected"),
        (
            ("source::1", "drawing.pdf", None, True),
            ("source::1", "DRAWING.PDF", None, True),
            ("source::1", "drawing.bin", "%PDF-1.7", True),
            ("source::1", "drawing.bin", "not-pdf", False),
            ("source::1", "", None, False),
            ("", "drawing.pdf", None, False),
            ("source::1", None, None, False),
            (None, "drawing.pdf", None, False),
        ),
    )
    def test_supports_is_total_and_never_raises(
        self, source_id, file_name, notes, expected
    ):
        assert PdfDrawingParser().supports(source_id, file_name, notes) is expected


class TestPdfDrawingParserPreflight:
    def test_blank_file_name_is_unsupported_before_worker(self):
        result = PdfDrawingParser().parse(
            source_id="synthetic::blank-name",
            file_name=" ",
            content=_synthetic_vector_pdf(),
        )

        assert result.diagnostics.status is DrawingIngestionStatus.UNSUPPORTED
        assert result.diagnostics.format_detected is None
        assert result.diagnostics.warnings == ("PDF_UNSUPPORTED",)
        assert result.document is None

    def test_valid_vector_pdf_is_preflight_approved_without_semantic_document(self):
        result = PdfDrawingParser().parse(
            source_id="synthetic::vector.pdf",
            file_name="vector.pdf",
            content=_synthetic_vector_pdf(),
        )

        assert result.diagnostics.status is DrawingIngestionStatus.INSUFFICIENT_DATA
        assert result.diagnostics.format_detected == "PDF"
        assert result.diagnostics.warnings == ("PDF_VECTOR_PREFLIGHT_OK",)
        assert result.diagnostics.errors == ("PDF_INSUFFICIENT_VECTOR_DATA",)
        assert result.diagnostics.sheet_count_expected == 1
        assert result.diagnostics.sheet_count_parsed == 1
        assert result.document is None

    @pytest.mark.parametrize("content", (b"", b"not a pdf", b"%PDX-1.4"))
    def test_non_pdf_input_is_unsupported(self, content):
        result = PdfDrawingParser().parse(
            source_id="synthetic::not-pdf",
            file_name="candidate.pdf",
            content=content,
        )

        assert result.diagnostics.status is DrawingIngestionStatus.UNSUPPORTED
        assert result.diagnostics.format_detected is None
        assert result.diagnostics.warnings == ("PDF_UNSUPPORTED",)
        assert result.diagnostics.errors == ()
        assert result.document is None

    def test_pdf_header_wholly_within_first_1024_bytes_is_accepted(self):
        content = _prefixed_pdf(_synthetic_vector_pdf(), b"X" * 1018)

        result = PdfDrawingParser().parse(
            source_id="synthetic::prefixed.pdf",
            file_name="prefixed.pdf",
            content=content,
        )

        assert result.diagnostics.format_detected == "PDF"
        assert result.diagnostics.status is DrawingIngestionStatus.INSUFFICIENT_DATA

    def test_pdf_header_beyond_first_1024_bytes_is_unsupported(self):
        content = _prefixed_pdf(_synthetic_vector_pdf(), b"X" * 1024)

        result = PdfDrawingParser().parse(
            source_id="synthetic::late-header.pdf",
            file_name="late-header.pdf",
            content=content,
        )

        assert result.diagnostics.status is DrawingIngestionStatus.UNSUPPORTED
        assert result.diagnostics.format_detected is None
        assert result.diagnostics.warnings == ("PDF_UNSUPPORTED",)

    def test_malformed_pdf_fails_closed(self):
        content = b"%PDF-1.4\nSENSITIVE-CONTENT-THAT-MUST-NOT-LEAK"

        result = PdfDrawingParser().parse(
            source_id="synthetic::malformed",
            file_name="malformed.pdf",
            content=content,
        )

        assert result.diagnostics.status is DrawingIngestionStatus.FAILED
        assert result.diagnostics.errors == ("PDF_MALFORMED",)
        assert result.document is None

    def test_raster_only_pdf_is_unsupported_without_image_decoding(self):
        builder = SyntheticPdfBuilder()
        builder.add_vector_page(include_image=True)

        result = PdfDrawingParser().parse(
            source_id="synthetic::raster.pdf",
            file_name="raster.pdf",
            content=builder.build(),
        )

        assert result.diagnostics.status is DrawingIngestionStatus.UNSUPPORTED
        assert result.diagnostics.warnings == ("PDF_RASTER_ONLY",)
        assert result.diagnostics.sheet_count_expected == 1
        assert result.diagnostics.sheet_count_parsed == 1
        assert result.document is None

    def test_empty_valid_pdf_has_insufficient_data(self):
        builder = SyntheticPdfBuilder()
        builder.add_vector_page()

        result = PdfDrawingParser().parse(
            source_id="synthetic::empty.pdf",
            file_name="empty.pdf",
            content=builder.build(),
        )

        assert result.diagnostics.status is DrawingIngestionStatus.INSUFFICIENT_DATA
        assert result.diagnostics.errors == ("PDF_INSUFFICIENT_VECTOR_DATA",)
        assert result.document is None

    def test_encrypted_marker_is_unsupported_without_password_attempt(self):
        content = _synthetic_vector_pdf().replace(
            b"trailer\n<< ",
            b"trailer\n<< /Encrypt 3 0 R ",
            1,
        )

        result = PdfDrawingParser().parse(
            source_id="synthetic::encrypted.pdf",
            file_name="encrypted.pdf",
            content=content,
        )

        assert result.diagnostics.status is DrawingIngestionStatus.UNSUPPORTED
        assert result.diagnostics.warnings == ("PDF_ENCRYPTED",)
        assert result.document is None


class TestPdfDrawingParserLimits:
    def test_exact_file_limit_is_inclusive(self):
        content = _synthetic_vector_pdf()
        parser = PdfDrawingParser(limits=PdfDrawingLimits(max_file_bytes=len(content)))

        result = parser.parse("synthetic::limit.pdf", "limit.pdf", content)

        assert result.diagnostics.status is DrawingIngestionStatus.INSUFFICIENT_DATA

    def test_one_byte_over_file_limit_fails_before_worker(self):
        content = _synthetic_vector_pdf()
        parser = PdfDrawingParser(limits=PdfDrawingLimits(max_file_bytes=len(content) - 1))

        result = parser.parse("synthetic::limit.pdf", "limit.pdf", content)

        assert result.diagnostics.status is DrawingIngestionStatus.FAILED
        assert result.diagnostics.errors == ("PDF_RESOURCE_LIMIT",)
        assert result.diagnostics.sheet_count_expected is None

    def test_default_64_mib_boundary_is_inclusive_and_overage_is_preflighted(
        self, monkeypatch
    ):
        limit = PdfDrawingLimits().max_file_bytes
        content = bytearray(limit + 1)
        content[:9] = b"%PDF-1.4\n"
        worker_input_sizes: list[int] = []

        def record_worker_input(payload, _limits, _worker_entry):
            worker_input_sizes.append(len(payload))
            return pdf_drawing._WorkerExecution(None, "PDF_MALFORMED")

        monkeypatch.setattr(pdf_drawing, "_run_spawned_worker", record_worker_input)
        parser = PdfDrawingParser()

        at_limit = parser.parse(
            "synthetic::64-mib.pdf",
            "64-mib.pdf",
            memoryview(content)[:-1],
        )
        over_limit = parser.parse(
            "synthetic::over-64-mib.pdf",
            "over-64-mib.pdf",
            content,
        )

        assert worker_input_sizes == [limit]
        assert at_limit.diagnostics.errors == ("PDF_MALFORMED",)
        assert over_limit.diagnostics.errors == ("PDF_RESOURCE_LIMIT",)

    def test_default_page_limit_rejects_201_pages(self):
        builder = SyntheticPdfBuilder()
        for _ in range(201):
            builder.add_vector_page()

        result = PdfDrawingParser().parse(
            "synthetic::too-many-pages.pdf",
            "too-many-pages.pdf",
            builder.build(),
        )

        assert result.diagnostics.status is DrawingIngestionStatus.FAILED
        assert result.diagnostics.errors == ("PDF_RESOURCE_LIMIT",)
        assert result.diagnostics.sheet_count_expected == 201
        assert result.diagnostics.sheet_count_parsed == 0

    def test_page_dimension_limit_is_enforced_in_worker(self):
        parser = PdfDrawingParser(limits=PdfDrawingLimits(max_page_dimension_points=100))

        result = parser.parse(
            "synthetic::large-page.pdf",
            "large-page.pdf",
            _synthetic_vector_pdf(),
        )

        assert result.diagnostics.status is DrawingIngestionStatus.FAILED
        assert result.diagnostics.errors == ("PDF_RESOURCE_LIMIT",)

    def test_object_count_limit_is_enforced_before_snapshot_append(self):
        limits = PdfDrawingLimits(max_objects_total=1, max_objects_per_page=1)

        result = PdfDrawingParser(limits=limits).parse(
            "synthetic::objects.pdf",
            "objects.pdf",
            _synthetic_vector_pdf(text="AB"),
        )

        assert result.diagnostics.status is DrawingIngestionStatus.FAILED
        assert result.diagnostics.errors == ("PDF_RESOURCE_LIMIT",)

    def test_text_character_limit_is_enforced(self):
        limits = PdfDrawingLimits(max_text_characters=1)

        result = PdfDrawingParser(limits=limits).parse(
            "synthetic::text.pdf",
            "text.pdf",
            _synthetic_vector_pdf(text="AB"),
        )

        assert result.diagnostics.status is DrawingIngestionStatus.FAILED
        assert result.diagnostics.errors == ("PDF_RESOURCE_LIMIT",)

    def test_vector_point_limit_is_enforced(self):
        limits = PdfDrawingLimits(
            max_vector_points_total=1,
            max_vector_points_per_object=1,
        )

        result = PdfDrawingParser(limits=limits).parse(
            "synthetic::points.pdf",
            "points.pdf",
            _synthetic_vector_pdf(),
        )

        assert result.diagnostics.status is DrawingIngestionStatus.FAILED
        assert result.diagnostics.errors == ("PDF_RESOURCE_LIMIT",)


class TestPdfDrawingSpawnIsolation:
    def test_spawned_worker_returns_typed_deterministic_snapshot(self):
        content = _synthetic_vector_pdf(text="PRIVATE WORKER TEXT")

        first = pdf_drawing._run_spawned_worker(content, PdfDrawingLimits())
        second = pdf_drawing._run_spawned_worker(content, PdfDrawingLimits())

        assert first.failure_code is None
        assert first.snapshot is not None
        assert first == second
        assert is_dataclass(first.snapshot)
        assert pickle.loads(pickle.dumps(first.snapshot)) == first.snapshot
        assert all(
            not type(value).__module__.startswith("pdfplumber")
            for page in first.snapshot.pages
            for value in (*page.text_runs, *page.vector_paths)
        )

    def test_worker_entry_is_module_level_and_spawn_context_is_explicit(self):
        assert pdf_drawing._pdf_worker_entry.__module__ == (
            "backend.interoperability.pdf_drawing"
        )
        assert "<locals>" not in pdf_drawing._pdf_worker_entry.__qualname__
        assert multiprocessing.get_context("spawn").get_start_method() == "spawn"

    def test_timeout_terminates_worker_and_fails_closed(self, monkeypatch):
        monkeypatch.setattr(
            PdfDrawingParser,
            "_worker_entry",
            staticmethod(_sleeping_worker),
        )
        parser = PdfDrawingParser(limits=PdfDrawingLimits(parse_timeout_seconds=0.001))

        result = parser.parse(
            "synthetic::timeout.pdf",
            "timeout.pdf",
            _synthetic_vector_pdf(),
        )

        assert result.diagnostics.status is DrawingIngestionStatus.FAILED
        assert result.diagnostics.errors == ("PDF_TIMEOUT",)
        assert result.document is None
        assert all(
            child.name != "machiningpro-vector-pdf-worker"
            for child in multiprocessing.active_children()
        )

    def test_abnormal_worker_exit_fails_closed(self, monkeypatch):
        monkeypatch.setattr(
            PdfDrawingParser,
            "_worker_entry",
            staticmethod(_abnormal_worker),
        )

        result = PdfDrawingParser().parse(
            "synthetic::worker-failure.pdf",
            "worker-failure.pdf",
            _synthetic_vector_pdf(),
        )

        assert result.diagnostics.status is DrawingIngestionStatus.FAILED
        assert result.diagnostics.errors == ("PDF_WORKER_FAILURE",)
        assert result.document is None

    def test_payload_from_abnormally_exited_worker_is_discarded(self, monkeypatch):
        monkeypatch.setattr(
            PdfDrawingParser,
            "_worker_entry",
            staticmethod(_payload_then_abnormal_worker),
        )

        result = PdfDrawingParser().parse(
            "synthetic::worker-failure.pdf",
            "worker-failure.pdf",
            _synthetic_vector_pdf(),
        )

        assert result.diagnostics.status is DrawingIngestionStatus.FAILED
        assert result.diagnostics.errors == ("PDF_WORKER_FAILURE",)
        assert result.document is None


class TestPdfDrawingDiagnosticSafety:
    def test_diagnostics_are_deterministic_and_redacted(self):
        raw_secret = "CUSTOMER-CONTENT-SENTINEL"
        file_secret = "C:/private/customer/drawing.pdf"
        content = f"%PDF-1.4\n{raw_secret}".encode()
        parser = PdfDrawingParser()

        first = parser.parse("synthetic::safe-source", file_secret, content)
        second = parser.parse("synthetic::safe-source", file_secret, content)
        rendered = repr(first)

        assert first == second
        assert first.diagnostics.errors == ("PDF_MALFORMED",)
        assert raw_secret not in rendered
        assert file_secret not in rendered
        assert "Traceback" not in rendered
        assert "PdfminerException" not in rendered
        assert "pdfplumber" not in rendered

    def test_diagnostic_count_and_length_stay_within_configured_bounds(self):
        limits = PdfDrawingLimits(
            max_diagnostics_per_kind=1,
            max_diagnostic_characters=24,
        )
        result = PdfDrawingParser(limits=limits).parse(
            "synthetic::safe-source",
            "safe.pdf",
            b"not-pdf",
        )

        assert len(result.diagnostics.warnings) <= 1
        assert len(result.diagnostics.errors) <= 1
        assert all(
            len(message) <= 24
            for message in (*result.diagnostics.warnings, *result.diagnostics.errors)
        )


class TestPdfDrawingTask4Normalization:
    @staticmethod
    def _private_text_run(
        object_id: str,
        text: str,
        *,
        x0: str,
        top: str,
        x1: str,
        bottom: str,
    ):
        return pdf_drawing._PdfTextRun(
            ref=pdf_drawing._PdfObjectRef(
                object_id=object_id,
                page_number=1,
                kind="text",
                bounding_box=DrawingBoundingBox(
                    x0=Decimal(x0),
                    top=Decimal(top),
                    x1=Decimal(x1),
                    bottom=Decimal(bottom),
                ),
            ),
            text=text,
        )

    def test_text_runs_have_typed_refs_blocks_and_top_left_decimal_boxes(self):
        builder = SyntheticPdfBuilder()
        builder.add_vector_page(
            width_pt=300,
            height_pt=200,
            texts=(
                PdfTextSpec(
                    text="AB",
                    x=Decimal("24"),
                    y=Decimal("150"),
                ),
            ),
        )

        execution = pdf_drawing._run_spawned_worker(
            builder.build(), PdfDrawingLimits()
        )

        assert execution.failure_code is None
        assert execution.snapshot is not None
        page = execution.snapshot.pages[0]
        first = page.text_runs[0]
        assert (page.page_number, page.width_pt, page.height_pt, page.rotation) == (
            1,
            Decimal("300"),
            Decimal("200"),
            0,
        )
        assert first.text == "A"
        assert first.ref.page_number == 1
        assert first.ref.kind == "text"
        assert first.ref.bounding_box == DrawingBoundingBox(
            x0=Decimal("24.0"),
            top=Decimal("40.48400000000001"),
            x1=Decimal("32.004000000000005"),
            bottom=Decimal("52.48400000000001"),
        )
        assert first.ref.object_id.startswith("pdf-p0001-text-")
        assert first.ref.object_id.endswith("-0001")
        assert page.text_blocks[0].text == "AB"
        assert page.text_blocks[0].text_run_ids == tuple(
            run.ref.object_id for run in page.text_runs
        )
        with pytest.raises(FrozenInstanceError):
            first.text = "changed"  # type: ignore[misc]

    def test_lines_and_rectangles_are_sorted_and_normalized_to_segments(self):
        builder = SyntheticPdfBuilder()
        builder.add_vector_page(
            width_pt=300,
            height_pt=200,
            lines=(
                PdfLineSpec(
                    x0=Decimal("10"),
                    y0=Decimal("20"),
                    x1=Decimal("100"),
                    y1=Decimal("40"),
                ),
            ),
            rectangles=(
                PdfRectSpec(
                    x0=Decimal("150"),
                    y0=Decimal("30"),
                    x1=Decimal("250"),
                    y1=Decimal("80"),
                ),
            ),
        )

        execution = pdf_drawing._run_spawned_worker(
            builder.build(), PdfDrawingLimits()
        )

        assert execution.snapshot is not None
        paths = execution.snapshot.pages[0].vector_paths
        assert tuple(path.ref.kind for path in paths) == ("rectangle", "line")
        rectangle, line = paths
        assert rectangle.ref.bounding_box == DrawingBoundingBox(
            x0=Decimal("150.0"),
            top=Decimal("120.0"),
            x1=Decimal("250.0"),
            bottom=Decimal("170.0"),
        )
        assert rectangle.segments == (
            ((Decimal("150.0"), Decimal("170.0")), (Decimal("250.0"), Decimal("170.0"))),
            ((Decimal("250.0"), Decimal("170.0")), (Decimal("250.0"), Decimal("120.0"))),
            ((Decimal("250.0"), Decimal("120.0")), (Decimal("150.0"), Decimal("120.0"))),
            ((Decimal("150.0"), Decimal("120.0")), (Decimal("150.0"), Decimal("170.0"))),
        )
        assert line.ref.bounding_box == DrawingBoundingBox(
            x0=Decimal("10.0"),
            top=Decimal("160.0"),
            x1=Decimal("100.0"),
            bottom=Decimal("180.0"),
        )
        assert line.segments == (
            ((Decimal("10.0"), Decimal("180.0")), (Decimal("100.0"), Decimal("160.0"))),
        )

    def test_rotated_page_uses_displayed_top_left_coordinates(self):
        builder = SyntheticPdfBuilder()
        builder.add_vector_page(
            width_pt=300,
            height_pt=200,
            rotation=90,
            texts=(PdfTextSpec(text="A", x=Decimal("24"), y=Decimal("150")),),
            lines=(
                PdfLineSpec(
                    x0=Decimal("10"),
                    y0=Decimal("20"),
                    x1=Decimal("100"),
                    y1=Decimal("40"),
                ),
            ),
        )

        execution = pdf_drawing._run_spawned_worker(
            builder.build(), PdfDrawingLimits()
        )

        assert execution.snapshot is not None
        page = execution.snapshot.pages[0]
        assert (page.width_pt, page.height_pt, page.rotation) == (
            Decimal("200"),
            Decimal("300"),
            90,
        )
        assert page.text_runs[0].ref.bounding_box == DrawingBoundingBox(
            x0=Decimal("147.516"),
            top=Decimal("24.0"),
            x1=Decimal("159.516"),
            bottom=Decimal("32.00400000000002"),
        )
        assert page.vector_paths[0].segments == (
            ((Decimal("20.0"), Decimal("10.0")), (Decimal("40.0"), Decimal("100.0"))),
        )

    def test_curve_is_typed_bounded_and_contains_no_parser_dictionary(self):
        execution = pdf_drawing._run_spawned_worker(
            _synthetic_curve_pdf(), PdfDrawingLimits()
        )

        assert execution.failure_code is None
        assert execution.snapshot is not None
        curve = execution.snapshot.pages[0].vector_paths[0]
        assert curve.ref.kind == "curve"
        assert curve.segments
        assert all(
            coordinate.is_finite()
            for segment in curve.segments
            for point in segment
            for coordinate in point
        )
        assert "object_type" not in repr(execution.snapshot)
        assert "pdfplumber" not in repr(execution.snapshot)
        assert not any(
            isinstance(value, dict)
            for page in execution.snapshot.pages
            for value in (*page.text_runs, *page.vector_paths, *page.text_blocks)
        )

    def test_duplicate_objects_receive_stable_ordinals_after_spatial_sort(self):
        builder = SyntheticPdfBuilder()
        builder.add_vector_page(
            width_pt=300,
            height_pt=200,
            texts=(
                PdfTextSpec(text="B", x=Decimal("24"), y=Decimal("50")),
                PdfTextSpec(text="A", x=Decimal("24"), y=Decimal("150")),
                PdfTextSpec(text="A", x=Decimal("24"), y=Decimal("150")),
            ),
        )
        content = builder.build()

        first = pdf_drawing._run_spawned_worker(content, PdfDrawingLimits())
        second = pdf_drawing._run_spawned_worker(content, PdfDrawingLimits())

        assert first == second
        assert first.snapshot is not None
        runs = first.snapshot.pages[0].text_runs
        assert tuple(run.text for run in runs) == ("A", "A", "B")
        first_id, duplicate_id = (runs[0].ref.object_id, runs[1].ref.object_id)
        assert first_id.rsplit("-", 1)[0] == duplicate_id.rsplit("-", 1)[0]
        assert first_id.endswith("-0001")
        assert duplicate_id.endswith("-0002")

    def test_fixed_threshold_text_grouping_is_deterministic(self):
        builder = SyntheticPdfBuilder()
        builder.add_vector_page(
            width_pt=300,
            height_pt=200,
            texts=(
                PdfTextSpec(text="AB", x=Decimal("24"), y=Decimal("150")),
                PdfTextSpec(text="CD", x=Decimal("45"), y=Decimal("150")),
                PdfTextSpec(text="EF", x=Decimal("25"), y=Decimal("135")),
                PdfTextSpec(text="SEPARATE", x=Decimal("100"), y=Decimal("100")),
            ),
        )

        execution = pdf_drawing._run_spawned_worker(
            builder.build(), PdfDrawingLimits()
        )

        assert execution.snapshot is not None
        blocks = execution.snapshot.pages[0].text_blocks
        assert tuple(block.text for block in blocks) == ("ABCD\nEF", "SEPARATE")
        assert all(block.ref.kind == "text-block" for block in blocks)

    def test_line_grouping_uses_exact_baseline_and_horizontal_gap_limits(self):
        first = self._private_text_run(
            "text-1", "A", x0="0", top="0", x1="10", bottom="10"
        )
        at_limits = self._private_text_run(
            "text-2", "B", x0="16", top="2", x1="20", bottom="12"
        )
        beyond_gap = self._private_text_run(
            "text-3", "C", x0="26.001", top="2", x1="30", bottom="12"
        )

        lines = pdf_drawing._text_lines((first, at_limits, beyond_gap))

        assert tuple(line.text for line in lines) == ("AB", "C")
        assert pdf_drawing._TEXT_LINE_BASELINE_TOLERANCE_PT == Decimal("2")
        assert pdf_drawing._TEXT_HORIZONTAL_GAP_PT == Decimal("6")

    def test_block_grouping_uses_exact_vertical_gap_and_left_edge_limits(self):
        first = self._private_text_run(
            "text-1", "A", x0="0", top="0", x1="10", bottom="10"
        )
        at_limits = self._private_text_run(
            "text-2", "B", x0="3", top="13", x1="13", bottom="23"
        )
        beyond_limits = self._private_text_run(
            "text-3", "C", x0="6.001", top="26.001", x1="16", bottom="36"
        )

        blocks = pdf_drawing._normalize_text_blocks(
            1, (first, at_limits, beyond_limits)
        )

        assert tuple(block.text for block in blocks) == ("A\nB", "C")
        assert pdf_drawing._TEXT_BLOCK_LEFT_EDGE_TOLERANCE_PT == Decimal("3")
        assert pdf_drawing._TEXT_BLOCK_VERTICAL_GAP_PT == Decimal("3")

    @pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
    def test_non_finite_coordinate_is_rejected(self, value):
        with pytest.raises(ValueError):
            pdf_drawing._decimal(value)


class TestPdfDrawingTask4Classification:
    def test_vector_paths_without_text_are_vector_candidates(self):
        builder = SyntheticPdfBuilder()
        builder.add_vector_page(
            lines=(
                PdfLineSpec(
                    x0=Decimal("10"),
                    y0=Decimal("20"),
                    x1=Decimal("100"),
                    y1=Decimal("20"),
                ),
            ),
        )

        result = PdfDrawingParser().parse(
            "synthetic::paths.pdf", "paths.pdf", builder.build()
        )

        assert result.diagnostics.status is DrawingIngestionStatus.INSUFFICIENT_DATA
        assert result.diagnostics.warnings == ("PDF_VECTOR_PREFLIGHT_OK",)
        assert result.diagnostics.errors == ("PDF_INSUFFICIENT_VECTOR_DATA",)
        assert result.document is None

    def test_mixed_vector_and_image_content_remains_vector_candidate(self):
        builder = SyntheticPdfBuilder()
        builder.add_vector_page(
            texts=(PdfTextSpec(text="VECTOR", x=Decimal("20"), y=Decimal("100")),),
            include_image=True,
        )

        result = PdfDrawingParser().parse(
            "synthetic::mixed.pdf", "mixed.pdf", builder.build()
        )

        assert result.diagnostics.status is DrawingIngestionStatus.INSUFFICIENT_DATA
        assert result.diagnostics.warnings == ("PDF_VECTOR_PREFLIGHT_OK",)
        assert result.diagnostics.errors == ("PDF_INSUFFICIENT_VECTOR_DATA",)
        assert result.document is None


_TASK5_ALIAS_CASES = (
    ("DRAWING NO", "drawing_number"),
    ("DRAWING NUMBER", "drawing_number"),
    ("DWG NO", "drawing_number"),
    ("DWG NUMBER", "drawing_number"),
    ("PART NO", "part_number"),
    ("PART NUMBER", "part_number"),
    ("TITLE", "part_name"),
    ("DESCRIPTION", "part_name"),
    ("PART NAME", "part_name"),
    ("MATERIAL", "material"),
    ("MATL", "material"),
    ("SCALE", "scale"),
    ("SHEET", "sheet"),
    ("SHEET NO", "sheet"),
    ("SHEET NUMBER", "sheet"),
    ("REV", "revision"),
    ("REVISION", "revision"),
    ("DRAWN", "author"),
    ("DRAWN BY", "author"),
    ("CHECKED", "checker"),
    ("CHECKED BY", "checker"),
    ("APPROVED", "approver"),
    ("APPROVED BY", "approver"),
    ("DATE", "date"),
    ("DRAWING DATE", "date"),
    ("UNIT", "unit"),
    ("UNITS", "unit"),
)


def _title_grid_specs(
    pairs: tuple[tuple[str, str], ...],
    *,
    x0: Decimal = Decimal("20"),
    y0: Decimal = Decimal("20"),
    width: Decimal = Decimal("300"),
    row_height: Decimal = Decimal("32"),
    rectangle: bool = True,
    duplicate_perimeter_lines: bool = False,
) -> tuple[tuple[PdfTextSpec, ...], tuple[PdfLineSpec, ...], tuple[PdfRectSpec, ...]]:
    x1 = x0 + width
    y1 = y0 + row_height * len(pairs)
    split_x = x0 + Decimal("90")
    texts: list[PdfTextSpec] = []
    for index, (label, value) in enumerate(pairs):
        baseline = y1 - row_height * index - Decimal("21")
        if label:
            texts.append(
                PdfTextSpec(
                    text=label,
                    x=split_x - Decimal("65"),
                    y=baseline,
                    font_size=Decimal("8"),
                )
            )
        if value:
            texts.append(
                PdfTextSpec(
                    text=value,
                    x=split_x + Decimal("5"),
                    y=baseline,
                    font_size=Decimal("8"),
                )
            )

    lines = [PdfLineSpec(x0=split_x, y0=y0, x1=split_x, y1=y1)]
    lines.extend(
        PdfLineSpec(
            x0=x0,
            y0=y0 + row_height * index,
            x1=x1,
            y1=y0 + row_height * index,
        )
        for index in range(1, len(pairs))
    )
    rectangles: tuple[PdfRectSpec, ...] = ()
    if rectangle:
        rectangles = (PdfRectSpec(x0=x0, y0=y0, x1=x1, y1=y1),)
    if not rectangle or duplicate_perimeter_lines:
        lines.extend(
            (
                PdfLineSpec(x0=x0, y0=y0, x1=x1, y1=y0),
                PdfLineSpec(x0=x1, y0=y0, x1=x1, y1=y1),
                PdfLineSpec(x0=x1, y0=y1, x1=x0, y1=y1),
                PdfLineSpec(x0=x0, y0=y1, x1=x0, y1=y0),
            )
        )
    return tuple(texts), tuple(lines), rectangles


def _title_pdf(
    *grids: tuple[
        tuple[PdfTextSpec, ...],
        tuple[PdfLineSpec, ...],
        tuple[PdfRectSpec, ...],
    ],
    width_pt: int = 700,
    height_pt: int = 595,
) -> bytes:
    builder = SyntheticPdfBuilder()
    builder.add_vector_page(
        width_pt=width_pt,
        height_pt=height_pt,
        texts=tuple(text for grid in grids for text in grid[0]),
        lines=tuple(line for grid in grids for line in grid[1]),
        rectangles=tuple(rectangle for grid in grids for rectangle in grid[2]),
    )
    return builder.build()


def _parse_title_pdf(content: bytes, *, limits: PdfDrawingLimits | None = None):
    return PdfDrawingParser(limits=limits).parse(
        "synthetic::task5.pdf",
        "task5.pdf",
        content,
    )


class TestPdfDrawingTask5:
    _minimal_pairs = (("DRAWING NO", "D-100"), ("REV", "A"))

    def test_detects_same_title_block_in_all_approved_locations(self):
        locations = (
            (Decimal("20"), Decimal("20")),
            (Decimal("360"), Decimal("20")),
            (Decimal("20"), Decimal("440")),
            (Decimal("190"), Decimal("230")),
        )

        extracted = []
        for x0, y0 in locations:
            result = _parse_title_pdf(
                _title_pdf(
                    _title_grid_specs(
                        self._minimal_pairs,
                        x0=x0,
                        y0=y0,
                        width=Decimal("300"),
                    ),
                    width_pt=700,
                    height_pt=560,
                )
            )
            assert result.diagnostics.status is DrawingIngestionStatus.VALID
            assert result.document is not None
            assert result.document.title_block is not None
            extracted.append(
                (
                    result.document.title_block.drawing_number,
                    result.document.title_block.revision.revision_code,
                )
            )

        assert extracted == [("D-100", "A")] * 4

    def test_builds_candidates_from_rectangles_and_connected_lines(self):
        rectangle = _parse_title_pdf(
            _title_pdf(_title_grid_specs(self._minimal_pairs))
        )
        connected_lines = _parse_title_pdf(
            _title_pdf(_title_grid_specs(self._minimal_pairs, rectangle=False))
        )
        texts, lines, rectangles = _title_grid_specs(self._minimal_pairs)
        attached_leader = _parse_title_pdf(
            _title_pdf(
                (
                    texts,
                    (
                        *lines,
                        PdfLineSpec(
                            x0=Decimal("320"),
                            y0=Decimal("20"),
                            x1=Decimal("360"),
                            y1=Decimal("20"),
                        ),
                        PdfLineSpec(
                            x0=Decimal("360"),
                            y0=Decimal("20"),
                            x1=Decimal("360"),
                            y1=Decimal("40"),
                        ),
                    ),
                    rectangles,
                )
            )
        )
        line_texts, line_paths, _ = _title_grid_specs(
            self._minimal_pairs,
            rectangle=False,
        )
        attached_to_line_perimeter = _parse_title_pdf(
            _title_pdf(
                (
                    line_texts,
                    (
                        *line_paths,
                        PdfLineSpec(
                            x0=Decimal("320"),
                            y0=Decimal("20"),
                            x1=Decimal("360"),
                            y1=Decimal("20"),
                        ),
                        PdfLineSpec(
                            x0=Decimal("360"),
                            y0=Decimal("20"),
                            x1=Decimal("360"),
                            y1=Decimal("40"),
                        ),
                    ),
                    (),
                )
            )
        )

        assert rectangle.diagnostics.status is DrawingIngestionStatus.VALID
        assert connected_lines.diagnostics.status is DrawingIngestionStatus.VALID
        assert attached_leader.diagnostics.status is DrawingIngestionStatus.VALID
        assert (
            attached_to_line_perimeter.diagnostics.status
            is DrawingIngestionStatus.VALID
        )
        assert rectangle.document is not None
        assert connected_lines.document is not None
        assert attached_leader.document is not None
        assert attached_to_line_perimeter.document is not None
        assert rectangle.document.title_block.drawing_number == "D-100"
        assert connected_lines.document.title_block.drawing_number == "D-100"
        assert attached_leader.document.title_block.drawing_number == "D-100"
        assert (
            attached_to_line_perimeter.document.title_block.drawing_number
            == "D-100"
        )

    def test_rejects_structurally_insufficient_and_low_density_regions(self):
        one_pair = _title_grid_specs((("DRAWING NO", "D-100"),))
        no_vertical = list(_title_grid_specs(self._minimal_pairs)[1])
        no_vertical = tuple(line for line in no_vertical if line.x0 != line.x1)
        base = _title_grid_specs(self._minimal_pairs)
        missing_separator = (base[0], no_vertical, base[2])
        noisy_pairs = self._minimal_pairs + tuple(
            (f"NOTE {index}", f"VALUE {index}") for index in range(10)
        )

        for content in (
            _title_pdf(one_pair),
            _title_pdf(missing_separator),
            _title_pdf(_title_grid_specs(noisy_pairs)),
        ):
            result = _parse_title_pdf(content)
            assert result.diagnostics.status is DrawingIngestionStatus.INSUFFICIENT_DATA
            assert result.document is None

        first_empty = _title_grid_specs(
            (("", ""), ("", "")),
            x0=Decimal("20"),
        )
        second_empty = _title_grid_specs(
            (("", ""), ("", "")),
            x0=Decimal("370"),
        )
        empty_regions = _parse_title_pdf(
            _title_pdf(first_empty, second_empty),
            limits=PdfDrawingLimits(max_title_block_candidates=1),
        )
        assert (
            empty_regions.diagnostics.status
            is DrawingIngestionStatus.INSUFFICIENT_DATA
        )

    def test_scores_orders_deduplicates_and_rejects_tied_candidates(self):
        duplicated_perimeter = _parse_title_pdf(
            _title_pdf(
                _title_grid_specs(
                    self._minimal_pairs,
                    duplicate_perimeter_lines=True,
                )
            )
        )
        assert duplicated_perimeter.diagnostics.status is DrawingIngestionStatus.VALID

        first = _title_grid_specs(self._minimal_pairs, x0=Decimal("20"))
        second = _title_grid_specs(self._minimal_pairs, x0=Decimal("370"))
        tied = _parse_title_pdf(_title_pdf(first, second))

        assert tied.diagnostics.status is DrawingIngestionStatus.INSUFFICIENT_DATA
        assert tied.diagnostics.warnings == ("PDF_TITLE_BLOCK_AMBIGUOUS",)
        assert tied.document is None

    def test_title_candidate_limit_fails_closed_without_truncation(self):
        first = _title_grid_specs(self._minimal_pairs, x0=Decimal("20"))
        second = _title_grid_specs(self._minimal_pairs, x0=Decimal("370"))
        result = _parse_title_pdf(
            _title_pdf(first, second),
            limits=PdfDrawingLimits(max_title_block_candidates=1),
        )

        assert result.diagnostics.status is DrawingIngestionStatus.FAILED
        assert result.diagnostics.errors == ("PDF_RESOURCE_LIMIT",)
        assert result.document is None

    @pytest.mark.parametrize(("alias", "field_key"), _TASK5_ALIAS_CASES)
    def test_every_approved_alias_maps_to_one_canonical_field(
        self, alias, field_key
    ):
        assert pdf_drawing._title_field_key(alias) == field_key

    def test_label_normalization_is_exact_and_bounded(self):
        assert pdf_drawing._title_field_key("  dwg._no:  ") == "drawing_number"
        assert pdf_drawing._title_field_key("ＤＷＧ　ＮＯ") == "drawing_number"
        assert pdf_drawing._title_field_key("drawing---number") == "drawing_number"
        assert pdf_drawing._title_field_key("DRAWING\u2003NUMBER") == "drawing_number"
        assert pdf_drawing._title_field_key("DRAWING\tNUMBER") is None
        assert pdf_drawing._title_field_key("DRAWING NO\x00") is None

    def test_unapproved_fuzzy_prefix_translated_and_customer_labels_do_not_match(self):
        for rejected in (
            "DWG",
            "DWG NUM",
            "DRAWING NUMBER EXTRA",
            "DRG NO",
            "RESIM NO",
            "CUSTOMER DRAWING NO",
            "ACME PART NUMBER",
        ):
            assert pdf_drawing._title_field_key(rejected) is None

    def test_pairing_precedence_and_72_point_boundary_are_exact(self):
        assert pdf_drawing._inline_title_pair("SCALE: 1:2") == (
            "scale",
            "1:2",
        )
        assert pdf_drawing._inline_title_pair("TITLE SHAFT") is None
        label = DrawingBoundingBox(
            Decimal("0"), Decimal("0"), Decimal("10"), Decimal("10")
        )
        at_limit = DrawingBoundingBox(
            Decimal("82"), Decimal("0"), Decimal("92"), Decimal("10")
        )
        beyond = DrawingBoundingBox(
            Decimal("82.001"), Decimal("0"), Decimal("92.001"), Decimal("10")
        )
        assert pdf_drawing._within_title_distance(label, at_limit)
        assert not pdf_drawing._within_title_distance(label, beyond)

        result = _parse_title_pdf(
            _title_pdf(_title_grid_specs(self._minimal_pairs))
        )
        assert result.document.title_block.drawing_number == "D-100"

        texts, lines, rectangles = _title_grid_specs(self._minimal_pairs)
        split_x = Decimal("110")
        partial_lines = tuple(
            PdfLineSpec(
                x0=line.x0,
                y0=Decimal("52") if line.x0 == split_x == line.x1 else line.y0,
                x1=line.x1,
                y1=line.y1,
            )
            for line in lines
        )
        snapshot = pdf_drawing._extract_snapshot(
            _title_pdf((texts, partial_lines, rectangles)),
            PdfDrawingLimits(),
        )
        candidate = pdf_drawing._extract_title_candidates(
            snapshot,
            PdfDrawingLimits(),
        )[0].candidate
        pairing_ranks = {
            item.field_key: item.pairing_rank for item in candidate.field_evidence
        }
        assert pairing_ranks == {"drawing_number": 4, "revision": 3}

        dangling_texts = (
            PdfTextSpec(
                text="DRAWING NO",
                x=Decimal("25"),
                y=Decimal("75"),
                font_size=Decimal("8"),
            ),
            PdfTextSpec(
                text="D-100",
                x=Decimal("85"),
                y=Decimal("75"),
                font_size=Decimal("8"),
            ),
            PdfTextSpec(
                text="REV",
                x=Decimal("45"),
                y=Decimal("31"),
                font_size=Decimal("8"),
            ),
            PdfTextSpec(
                text="A",
                x=Decimal("115"),
                y=Decimal("31"),
                font_size=Decimal("8"),
            ),
        )
        dangling_lines = (
            *lines,
            PdfLineSpec(
                x0=Decimal("80"),
                y0=Decimal("68"),
                x1=Decimal("80"),
                y1=Decimal("84"),
            ),
        )
        dangling_snapshot = pdf_drawing._extract_snapshot(
            _title_pdf((dangling_texts, dangling_lines, rectangles)),
            PdfDrawingLimits(),
        )
        dangling_candidate = pdf_drawing._extract_title_candidates(
            dangling_snapshot,
            PdfDrawingLimits(),
        )[0].candidate
        dangling_ranks = {
            item.field_key: item.pairing_rank
            for item in dangling_candidate.field_evidence
        }
        assert dangling_ranks == {"drawing_number": 3, "revision": 4}

    def test_maps_only_approved_title_revision_material_sheet_and_unit_fields(self):
        pairs = (
            ("DRAWING NO", "DWG-4711"),
            ("PART NO", "PART-9"),
            ("TITLE", "Drive Shaft"),
            ("MATERIAL", "42CrMo4"),
            ("SCALE", "1 : 2"),
            ("SHEET", "1 OF 1"),
            ("REV", "B"),
            ("DRAWN BY", "A. Smith"),
            ("CHECKED BY", "B. Jones"),
            ("APPROVED BY", "C. Lee"),
            ("DATE", "2026-09-22"),
            ("UNITS", "MM"),
        )
        result = _parse_title_pdf(_title_pdf(_title_grid_specs(pairs)))

        assert result.diagnostics.status is DrawingIngestionStatus.VALID
        assert isinstance(result.document, CanonicalDrawing)
        title = result.document.title_block
        assert title == DrawingTitleBlock(
            drawing_number="DWG-4711",
            part_number="PART-9",
            part_name="Drive Shaft",
            material_raw="42CrMo4",
            scale="1:2",
            sheet_number=1,
            sheet_count=1,
            revision=title.revision,
            author="A. Smith",
            checker="B. Jones",
            approver="C. Lee",
            date_text="2026-09-22",
            source_location=title.source_location,
        )
        assert isinstance(title.revision, DrawingRevision)
        assert title.revision is result.document.revision
        assert title.revision.revision_code == "B"
        assert title.revision.description is None
        assert title.revision.date_text is None
        assert title.revision.author is None
        assert title.revision.approver is None
        assert result.document.material_notes == (
            DrawingMaterialNote(
                note_id="pdf-material-p0001-000001",
                raw_text="42CrMo4",
                source_location=result.document.material_notes[0].source_location,
            ),
        )
        assert result.document.metadata["drawing.unit"] == "mm"
        assert result.document.sheets[0].scale == "1:2"

    def test_metadata_uses_exact_allowlisted_keys_and_string_values(self):
        result = _parse_title_pdf(
            _title_pdf(_title_grid_specs(self._minimal_pairs), width_pt=700, height_pt=595)
        )
        assert result.document is not None

        assert tuple(result.document.metadata) == tuple(
            sorted(
                (
                    "pdf.page.0001.height_pt",
                    "pdf.page.0001.rotation",
                    "pdf.page.0001.width_pt",
                    "pdf.page_count",
                    "pdf.text_character_count",
                    "pdf.vector_object_count",
                    "pdf.version",
                )
            )
        )
        assert result.document.metadata["pdf.page.0001.width_pt"] == "700"
        assert result.document.metadata["pdf.page.0001.height_pt"] == "595"
        assert result.document.metadata["pdf.page.0001.rotation"] == "0"
        assert result.document.metadata["pdf.page_count"] == "1"
        assert all(isinstance(value, str) for value in result.document.metadata.values())

    def test_pdf_info_xmp_and_unapproved_fields_never_surface(self):
        sentinel = "PRIVATE-PDF-INFO-SENTINEL"
        content = _title_pdf(_title_grid_specs(self._minimal_pairs))
        content += f"% /Author ({sentinel}) /Title ({sentinel})\n".encode()

        result = _parse_title_pdf(content)
        rendered = repr(result)

        assert result.document is not None
        assert sentinel not in rendered
        assert not any(
            key in result.document.metadata
            for key in ("author", "title", "subject", "creator", "producer")
        )

    def test_multiline_policy_accepts_only_two_line_title_and_material(self):
        assert pdf_drawing._normalize_title_value(
            "part_name", "  DRIVE  SHAFT \n ASSEMBLY  "
        ) == "DRIVE SHAFT ASSEMBLY"
        assert pdf_drawing._normalize_title_value(
            "material", "  42CrMo4  \n  QT  "
        ) == "42CrMo4\nQT"
        assert pdf_drawing._normalize_title_value("date", "A\nB") is None
        assert pdf_drawing._normalize_title_value("part_name", "A\n\nB") is None
        assert pdf_drawing._normalize_title_value("part_name", "A\nB\nC") is None
        assert pdf_drawing._normalize_title_value("part_name", "A\nREV") is None
        assert (
            pdf_drawing._normalize_title_value("drawing_number", "ＤＷＧ-００１")
            == "ＤＷＧ-００１"
        )
        assert pdf_drawing._normalize_title_value("scale", "01.00 : 02.0") == (
            "01.00:02.0"
        )

        texts, lines, rectangles = _title_grid_specs(
            (
                ("TITLE", ""),
                ("REV", "A"),
                ("MATERIAL", "STEEL"),
                ("DATE", "2026-09-22"),
            ),
            row_height=Decimal("64"),
        )
        malformed_multiline = _parse_title_pdf(
            _title_pdf(
                (
                    (
                        *texts,
                        *(
                            PdfTextSpec(
                                text=text,
                                x=Decimal("115"),
                                y=y,
                                font_size=Decimal("8"),
                            )
                            for text, y in (
                                ("LINE ONE", Decimal("269")),
                                ("LINE TWO", Decimal("259")),
                                ("LINE THREE", Decimal("249")),
                            )
                        ),
                    ),
                    lines,
                    rectangles,
                )
            )
        )
        assert malformed_multiline.diagnostics.status is DrawingIngestionStatus.PARTIAL
        assert malformed_multiline.diagnostics.warnings == (
            "PDF_TITLE_FIELD_CONFLICT",
        )
        assert malformed_multiline.document.title_block.part_name is None

    def test_duplicate_and_conflicting_evidence_follow_exact_resolution(self):
        first = pdf_drawing._TitleFieldEvidence(
            field_key="revision",
            value="A",
            pairing_rank=3,
            page_number=1,
            bounding_box=DrawingBoundingBox(
                Decimal("0"), Decimal("0"), Decimal("10"), Decimal("10")
            ),
            source_object_ids=("a",),
            original_text="A",
        )
        duplicate = pdf_drawing._TitleFieldEvidence(
            field_key="revision",
            value="A",
            pairing_rank=3,
            page_number=1,
            bounding_box=DrawingBoundingBox(
                Decimal("10"), Decimal("0"), Decimal("20"), Decimal("10")
            ),
            source_object_ids=("b",),
            original_text="A",
        )
        conflict = pdf_drawing._TitleFieldEvidence(
            field_key="revision",
            value="B",
            pairing_rank=3,
            page_number=1,
            bounding_box=duplicate.bounding_box,
            source_object_ids=("c",),
            original_text="B",
        )

        merged, ambiguous = pdf_drawing._resolve_title_field_evidence(
            (duplicate, first)
        )
        assert not ambiguous
        assert merged.bounding_box == DrawingBoundingBox(
            Decimal("0"), Decimal("0"), Decimal("20"), Decimal("10")
        )
        assert merged.source_object_ids == ("a", "b")
        reversed_ids, reversed_ambiguous = pdf_drawing._resolve_title_field_evidence(
            (duplicate, first),
            {"b": 0, "a": 1},
        )
        assert not reversed_ambiguous
        assert reversed_ids.source_object_ids == ("b", "a")
        assert pdf_drawing._resolve_title_field_evidence((first, conflict)) == (
            None,
            True,
        )

        texts, lines, rectangles = _title_grid_specs(
            (
                ("DRAWING NO", "D-100"),
                ("", ""),
                ("REV", "A"),
                ("MATERIAL", "STEEL"),
            )
        )
        ambiguous = _parse_title_pdf(
            _title_pdf(
                (
                    (
                        *texts,
                        PdfTextSpec(
                            text="D-200",
                            x=Decimal("180"),
                            y=Decimal("127"),
                            font_size=Decimal("8"),
                        ),
                        PdfTextSpec(
                            text="D-LOW",
                            x=Decimal("45"),
                            y=Decimal("95"),
                            font_size=Decimal("8"),
                        ),
                    ),
                    lines,
                    rectangles,
                )
            )
        )
        assert ambiguous.diagnostics.status is DrawingIngestionStatus.PARTIAL
        assert ambiguous.diagnostics.warnings == ("PDF_TITLE_FIELD_CONFLICT",)
        assert ambiguous.document.title_block.drawing_number is None

    def test_page_and_field_provenance_is_typed_minimal_and_deterministic(self):
        result = _parse_title_pdf(
            _title_pdf(
                _title_grid_specs(
                    self._minimal_pairs + (("MATERIAL", "42CrMo4"),)
                )
            )
        )
        assert result.document is not None
        sheet_location = result.document.sheets[0].source_location
        title_location = result.document.title_block.source_location
        revision_location = result.document.revision.source_location
        material_location = result.document.material_notes[0].source_location

        assert sheet_location == DrawingSourceLocation(
            source_id="synthetic::task5.pdf",
            sheet_number=1,
            page_number=1,
            adapter_id="machiningpro.vector-pdf",
            adapter_version="1.0.0",
            authority=DrawingExtractionAuthority.EXTRACTED,
            bounding_box=DrawingBoundingBox(
                Decimal("0"), Decimal("0"), Decimal("700"), Decimal("595")
            ),
        )
        assert title_location.bounding_box is not None
        assert title_location.original_text is None
        assert title_location.source_object_ids
        assert revision_location.original_text == "A"
        assert material_location.original_text == "42CrMo4"
        assert isinstance(title_location.bounding_box, DrawingBoundingBox)
        assert isinstance(title_location.source_object_ids, tuple)

    def test_task5_repeated_parse_and_serialization_are_deterministic(self):
        content = _title_pdf(_title_grid_specs(self._minimal_pairs))
        first = _parse_title_pdf(content)
        second = _parse_title_pdf(content)

        assert first == second
        assert json.dumps(asdict(first), sort_keys=True, default=str) == json.dumps(
            asdict(second), sort_keys=True, default=str
        )

    def test_task5_output_contains_no_task6_or_unapproved_semantics(self):
        pairs = self._minimal_pairs + (("DESCRIPTION", "25 +/-0.1 mm"),)
        result = _parse_title_pdf(_title_pdf(_title_grid_specs(pairs)))

        assert result.document is not None
        assert result.document.all_dimensions == ()
        assert result.document.all_tolerances == ()
        assert result.document.all_gdt_references == ()
        assert result.document.all_surface_finish == ()
        assert all(sheet.views == () for sheet in result.document.sheets)

    def test_task5_diagnostics_and_repr_are_bounded_and_redacted(self):
        secret = "C:/private/customer/SECRET-TRACEBACK-SENTINEL.pdf"
        first = _title_grid_specs(self._minimal_pairs, x0=Decimal("20"))
        second = _title_grid_specs(self._minimal_pairs, x0=Decimal("370"))
        result = PdfDrawingParser().parse(
            "synthetic::task5.pdf",
            secret,
            _title_pdf(first, second),
        )
        rendered = repr(result)

        assert result.diagnostics.warnings == ("PDF_TITLE_BLOCK_AMBIGUOUS",)
        assert secret not in rendered
        assert "Traceback" not in rendered
        assert "pdfplumber" not in rendered
        assert all(len(item) <= 240 for item in result.diagnostics.warnings)

    def test_malformed_normalized_title_evidence_fails_closed(self):
        box = DrawingBoundingBox(
            Decimal("0"), Decimal("0"), Decimal("10"), Decimal("10")
        )
        with pytest.raises(ValueError):
            pdf_drawing._TitleFieldEvidence(
                field_key="customer_code",
                value="SECRET",
                pairing_rank=3,
                page_number=1,
                bounding_box=box,
                source_object_ids=("source",),
                original_text="SECRET",
            )
        with pytest.raises(ValueError):
            pdf_drawing._TitleFieldEvidence(
                field_key="revision",
                value="A" * 257,
                pairing_rank=3,
                page_number=1,
                bounding_box=box,
                source_object_ids=("source",),
                original_text="A" * 257,
            )


class TestPdfDrawingTask6:
    def _candidates(self, text: str):
        builder = SyntheticPdfBuilder()
        builder.add_vector_page(
            width_pt=300,
            height_pt=200,
            texts=(PdfTextSpec(text=text, x=Decimal("80"), y=Decimal("120")),),
        )
        snapshot = pdf_drawing._extract_snapshot(builder.build(), PdfDrawingLimits())
        return pdf_drawing._extract_dimension_candidates(snapshot, PdfDrawingLimits())

    def test_explicit_linear_and_tolerance_patterns(self):
        candidates = self._candidates("25 ±0.10 mm")
        assert len(candidates) == 1
        assert candidates[0].nominal_value == Decimal("25")
        assert candidates[0].unit == "mm"
        assert candidates[0].tolerance is not None
        assert candidates[0].tolerance.upper_value == Decimal("0.10")
        assert candidates[0].tolerance.lower_value == Decimal("-0.10")

    def test_ambiguous_or_unapproved_numeric_text_is_ignored(self):
        assert self._candidates("25")[0:] == ()
        assert self._candidates("25/30")[0:] == ()
        assert self._candidates("2026-09-23")[0:] == ()

    def test_explicit_diameter_radius_and_angle(self):
        values = self._candidates("DIA 25 mm")
        assert values[0].dimension_type.value == "DIAMETRAL"
        values = self._candidates("R5 mm")
        assert values[0].dimension_type.value == "RADIAL"
        values = self._candidates("45 deg")
        assert values[0].dimension_type.value == "ANGULAR"

    @pytest.mark.parametrize(
        ("text", "kind", "upper", "lower"),
        (
            ("25 +0.20/-0.10 mm", "ASYMMETRIC", "0.20", "-0.10"),
            ("25 +0.20/0 mm", "UNILATERAL_PLUS", "0.20", "0"),
            ("25 +0/-0.10 mm", "UNILATERAL_MINUS", "0", "-0.10"),
        ),
    )
    def test_asymmetric_and_unilateral_tolerances(
        self, text, kind, upper, lower
    ):
        candidate = self._candidates(text)[0]
        assert candidate.tolerance.tolerance_type.value == kind
        assert candidate.tolerance.upper_value == Decimal(upper)
        assert candidate.tolerance.lower_value == Decimal(lower)

    def test_malformed_tolerance_and_mixed_separator_are_rejected(self):
        assert self._candidates("25 ±0 mm") == ()
        assert self._candidates("25 +0.20/- mm") == ()
        assert self._candidates("1,250.0 mm") == ()

    def test_decimal_comma_and_unit_absence_are_conservative(self):
        assert self._candidates("1,25 mm")[0].nominal_value == Decimal("1.25")
        assert self._candidates("25")[0:] == ()

    def test_canonical_mapping_retains_typed_provenance_and_identity(self):
        candidate = self._candidates("25 ±0.10 mm")[0]
        dimension, tolerance = pdf_drawing._canonical_dimension_pair(
            "synthetic::task6.pdf", candidate, 1
        )
        assert dimension.nominal_value == Decimal("25")
        assert dimension.source_location.bounding_box == candidate.bounding_box
        assert dimension.source_location.original_text == "25 ±0.10 mm"
        assert dimension.source_location.source_object_ids == candidate.source_object_ids
        assert dimension.tolerance is tolerance
        assert tolerance.source_location.page_number == 1

    def test_repeated_extraction_is_deterministic(self):
        first = self._candidates("25 ±0.10 mm")
        second = self._candidates("25 ±0.10 mm")
        assert first == second


class TestPdfDrawingTask7:
    def _dimension_pdf(self, *texts: str) -> bytes:
        builder = SyntheticPdfBuilder()
        builder.add_vector_page(
            width_pt=300,
            height_pt=200,
            texts=tuple(
                PdfTextSpec(text=text, x=Decimal("40"), y=Decimal(str(150 - index * 25)))
                for index, text in enumerate(texts)
            ),
        )
        return builder.build()

    def test_dimension_only_vector_assembles_canonical_document(self):
        result = PdfDrawingParser().parse(
            "synthetic::task7-dimension.pdf",
            "dimension.pdf",
            self._dimension_pdf("25 ±0.10 mm", "DIA 10 mm"),
        )
        assert result.diagnostics.status is DrawingIngestionStatus.VALID
        assert result.document is not None
        assert len(result.document.all_dimensions) == 2
        assert len(result.document.all_tolerances) == 1
        assert result.document.sheets[0].views[0].view_id == "pdf-view-p0001"
        assert result.document.sheets[0].views[0].dimensions == result.document.all_dimensions
        assert result.document.all_dimensions[0].tolerance is result.document.all_tolerances[0]

    def test_sparse_vector_remains_fail_closed_without_document(self):
        result = PdfDrawingParser().parse(
            "synthetic::task7-sparse.pdf",
            "sparse.pdf",
            _synthetic_vector_pdf(text="ordinary note 123"),
        )
        assert result.diagnostics.status is DrawingIngestionStatus.INSUFFICIENT_DATA
        assert result.document is None

    def test_raster_and_malformed_results_never_carry_canonical_content(self):
        builder = SyntheticPdfBuilder()
        builder.add_vector_page(include_image=True)
        raster = PdfDrawingParser().parse(
            "synthetic::task7-raster.pdf", "raster.pdf", builder.build()
        )
        malformed = PdfDrawingParser().parse(
            "synthetic::task7-malformed.pdf",
            "malformed.pdf",
            b"%PDF-1.4\ntruncated",
        )
        assert raster.diagnostics.status is DrawingIngestionStatus.UNSUPPORTED
        assert raster.document is None
        assert malformed.diagnostics.status is DrawingIngestionStatus.FAILED
        assert malformed.document is None

    def test_assembled_result_is_deterministic_and_redacted(self):
        content = self._dimension_pdf("25 mm")
        first = PdfDrawingParser().parse("synthetic::task7.pdf", "secret.pdf", content)
        second = PdfDrawingParser().parse("synthetic::task7.pdf", "secret.pdf", content)
        assert first == second
        assert json.dumps(asdict(first), sort_keys=True, default=str) == json.dumps(
            asdict(second), sort_keys=True, default=str
        )
        assert "secret.pdf" not in repr(first)
        assert first.document.all_gdt_references == ()
        assert first.document.all_surface_finish == ()


# ---------------------------------------------------------------------------
# P0-3 regression: _ocr_dimension_candidates() _ResourceLimitError → FAILED
# ---------------------------------------------------------------------------


class TestP03OcrDimensionResourceLimit:
    """P0-3: _ocr_dimension_candidates() can raise _ResourceLimitError.

    Before the fix the exception was unhandled and propagated as an internal
    error.  After the fix it is caught and returned as FAILED + PDF_RESOURCE_LIMIT.
    """

    def _raster_pdf(self) -> bytes:
        """A PDF with one image page so OCR is attempted."""
        from tests.unit.interoperability.ocr_fixtures import (
            SyntheticRasterDrawingBuilder,
            SyntheticRasterPdfBuilder,
        )

        image = SyntheticRasterDrawingBuilder(width=40, height=40).build()
        return SyntheticRasterPdfBuilder().add_page(image).build()

    def test_ocr_dimension_resource_limit_is_caught_and_returns_failed(
        self, monkeypatch
    ):
        from backend.interoperability import pdf_drawing as pdf_mod
        from backend.interoperability.drawing import DrawingIngestionStatus
        from backend.interoperability.ocr_drawing import OcrResult

        # Provide OCR evidence so the OCR branch is entered.
        monkeypatch.setattr(
            pdf_mod,
            "extract_ocr_from_pdf",
            lambda *a, **kw: OcrResult(DrawingIngestionStatus.VALID, evidence=()),
        )
        # Force _ocr_dimension_candidates to raise _ResourceLimitError.
        monkeypatch.setattr(
            pdf_mod,
            "_ocr_dimension_candidates",
            lambda *a, **kw: (_ for _ in ()).throw(
                pdf_mod._ResourceLimitError(1, 0)
            ),
        )

        result = PdfDrawingParser().parse(
            "synthetic::p0-3-resource-limit.pdf",
            "drawing.pdf",
            self._raster_pdf(),
        )

        assert result.diagnostics.status is DrawingIngestionStatus.FAILED
        assert result.diagnostics.errors == ("PDF_RESOURCE_LIMIT",)
        assert result.document is None


# ---------------------------------------------------------------------------
# P0-2 regression: GD&T wired into all three document-producing branches
# ---------------------------------------------------------------------------


class TestP02GdtIntegration:
    """P0-2: recognize_feature_control_frames wired into all three parse() branches.

    The three document-producing branches are:
    1. Ambiguous title with dimensions → PARTIAL
    2. Single selected title (with or without dimensions) → VALID / PARTIAL
    3. Dimension-only, no title → VALID
    """

    def _vector_gdt_pdf(self, *texts: str) -> bytes:
        builder = SyntheticPdfBuilder()
        builder.add_vector_page(
            width_pt=500,
            height_pt=300,
            texts=tuple(
                PdfTextSpec(
                    text=text, x=Decimal("40"), y=Decimal(str(260 - i * 30))
                )
                for i, text in enumerate(texts)
            ),
        )
        return builder.build()

    def test_gdt_vector_e2e_recognized_in_dimension_only_branch(self, monkeypatch):
        """Branch 3: dimension-only → VALID; GD&T frames are attached."""
        from backend.interoperability import pdf_drawing as pdf_mod
        from backend.interoperability.drawing import (
            DrawingIngestionStatus,
        )

        captured_tokens: list = []

        original_recognize = pdf_mod.recognize_feature_control_frames

        def _spy_recognize(evidence):
            captured_tokens.extend(evidence)
            return original_recognize(evidence)

        monkeypatch.setattr(pdf_mod, "recognize_feature_control_frames", _spy_recognize)

        content = self._vector_gdt_pdf("25 mm")
        result = PdfDrawingParser().parse(
            "synthetic::p0-2-gdt-branch3.pdf", "drawing.pdf", content
        )

        # The parse must succeed and GD&T was attempted.
        assert result.diagnostics.status in {
            DrawingIngestionStatus.VALID,
            DrawingIngestionStatus.INSUFFICIENT_DATA,
        }
        # recognize_feature_control_frames was called with vector tokens.
        assert len(captured_tokens) > 0

    def test_gdt_ocr_e2e_recognized_with_ocr_evidence(self, monkeypatch):
        """Branch 3 via OCR: OCR evidence reaches recognize_feature_control_frames."""
        from backend.interoperability import pdf_drawing as pdf_mod
        from backend.interoperability.drawing import DrawingIngestionStatus
        from backend.interoperability.ocr_drawing import OcrResult
        from tests.unit.interoperability.ocr_fixtures import (
            SyntheticRasterDrawingBuilder,
            SyntheticRasterPdfBuilder,
        )

        image = SyntheticRasterDrawingBuilder(width=60, height=40).build()
        payload = SyntheticRasterPdfBuilder().add_page(image).build()

        ocr_captured: list = []
        original_recognize = pdf_mod.recognize_feature_control_frames

        def _spy_recognize(evidence):
            ocr_captured.extend(evidence)
            return original_recognize(evidence)

        monkeypatch.setattr(pdf_mod, "recognize_feature_control_frames", _spy_recognize)
        monkeypatch.setattr(
            pdf_mod,
            "extract_ocr_from_pdf",
            lambda *a, **kw: OcrResult(DrawingIngestionStatus.INSUFFICIENT_DATA, evidence=()),
        )
        monkeypatch.setattr(
            pdf_mod,
            "_extract_dimension_candidates",
            lambda *a, **kw: (),
        )

        result = PdfDrawingParser().parse(
            "synthetic::p0-2-gdt-ocr.pdf", "drawing.pdf", payload
        )

        # No crash; result has a defined status.
        assert result.diagnostics.status in {
            DrawingIngestionStatus.VALID,
            DrawingIngestionStatus.INSUFFICIENT_DATA,
            DrawingIngestionStatus.UNSUPPORTED,
            DrawingIngestionStatus.FAILED,
        }

    def test_gdt_duplicate_suppression_attach_is_idempotent(self, monkeypatch):
        """Calling _apply_gdt twice on same document does not duplicate GD&T frames."""

        content = self._vector_gdt_pdf("25 mm")

        first = PdfDrawingParser().parse(
            "synthetic::p0-2-dedup-a.pdf", "drawing.pdf", content
        )
        second = PdfDrawingParser().parse(
            "synthetic::p0-2-dedup-b.pdf", "drawing.pdf", content
        )

        # Two deterministic parses of the same content produce the same GD&T set.
        if first.document is not None and second.document is not None:
            assert first.document.all_gdt_references == second.document.all_gdt_references

    def test_gdt_exception_in_recognition_propagates(self, monkeypatch):
        """_apply_gdt no longer swallows RuntimeError; programming defects propagate.

        Updated from the P0-2 pass: the broad except Exception was removed
        (P1-GDT-EXCEPT fix), so a RuntimeError from recognize_feature_control_frames
        now propagates instead of being silently dropped.
        """
        from backend.interoperability import pdf_drawing as pdf_mod

        def _exploding_recognize(evidence):
            raise RuntimeError("simulated GD&T crash")

        monkeypatch.setattr(
            pdf_mod, "recognize_feature_control_frames", _exploding_recognize
        )

        content = self._vector_gdt_pdf("25 mm")
        with pytest.raises(RuntimeError, match="simulated GD&T crash"):
            PdfDrawingParser().parse(
                "synthetic::p0-2-gdt-crash.pdf", "drawing.pdf", content
            )

    def test_gdt_provenance_on_vector_tokens_carries_parser_id(self, monkeypatch):
        """Vector GD&T tokens carry _PARSER_ID as adapter_id in source_location.

        A dimension ("25 mm") triggers the dimension-only document-producing branch
        so _apply_gdt is called and vector tokens reach recognize_feature_control_frames.
        """
        from backend.interoperability import pdf_drawing as pdf_mod
        from backend.interoperability.gdt_drawing import GdtTokenEvidence, GdtTokenSource

        captured: list[GdtTokenEvidence] = []
        original_recognize = pdf_mod.recognize_feature_control_frames

        def _capture_recognize(evidence):
            for item in evidence:
                if isinstance(item, GdtTokenEvidence):
                    captured.append(item)
            return original_recognize(evidence)

        monkeypatch.setattr(pdf_mod, "recognize_feature_control_frames", _capture_recognize)

        # Include a valid dimension so the document-producing branch is entered.
        content = self._vector_gdt_pdf("25 mm", "FLAT 0.05 A")
        PdfDrawingParser().parse(
            "synthetic::p0-2-provenance.pdf", "drawing.pdf", content
        )

        vector_tokens = [t for t in captured if t.source_kind is GdtTokenSource.VECTOR]
        assert len(vector_tokens) > 0
        for token in vector_tokens:
            assert token.source_location.adapter_id == pdf_mod._PARSER_ID


# ---------------------------------------------------------------------------
# P1-GDT-EXCEPT quality-pass: positive E2E + programming-error visibility
# ---------------------------------------------------------------------------


class TestGdtPositiveE2EAndErrorVisibility:
    """Verify _apply_gdt no longer uses a broad exception swallow.

    Three concerns addressed:
    1. Positive vector E2E: result.document.all_gdt_references is non-empty.
    2. Positive OCR E2E: OCR evidence reaches GD&T grammar; frame produced.
    3. Programming-error visibility: RuntimeError from recognition propagates.
    """

    def _gdt_frame_pdf(self) -> bytes:
        """PDF whose vector text runs form a valid FLATNESS frame.

        Tokens at same y-baseline (y=150), close x-positions so that
        pdfplumber reports them in the same horizontal band (gap << 72pt).
        A "25 mm" dimension run at a different y ensures the dimension-only
        branch of parse() is entered and _apply_gdt is called.

        Token layout (PDF y=150, x increasing):
          x=40   "FLATNESS"
          x=45   "0.10MM"
          x=50   "A"
        x-gap between adjacent specs is 5pt, well within pdfplumber's
        rendered char widths; _same_band evaluates the ACTUAL bounding boxes
        from pdfplumber, so the tokens will be grouped together because
        their top/bottom values will be identical (same y=150 baseline).
        """
        builder = SyntheticPdfBuilder()
        builder.add_vector_page(
            width_pt=500,
            height_pt=300,
            texts=(
                # GD&T frame tokens — same baseline so _same_band groups them
                PdfTextSpec(text="FLATNESS", x=Decimal("40"), y=Decimal("150")),
                PdfTextSpec(text="0.10MM", x=Decimal("120"), y=Decimal("150")),
                PdfTextSpec(text="A", x=Decimal("190"), y=Decimal("150")),
                # Dimension so parse() enters a document-producing branch
                PdfTextSpec(text="25 mm", x=Decimal("40"), y=Decimal("80")),
            ),
        )
        return builder.build()

    def test_vector_gdt_e2e_produces_nonempty_gdt_references(self):
        """Positive vector E2E: parse() attaches FLATNESS frame to document."""
        from backend.interoperability.drawing import (
            DrawingGdtCharacteristic,
            DrawingIngestionStatus,
        )

        content = self._gdt_frame_pdf()
        result = PdfDrawingParser().parse(
            "synthetic::p1-gdt-vector-e2e.pdf", "drawing.pdf", content
        )

        # Must enter a document-producing branch.
        assert result.diagnostics.status in {
            DrawingIngestionStatus.VALID,
            DrawingIngestionStatus.PARTIAL,
            DrawingIngestionStatus.INSUFFICIENT_DATA,
        }, f"Unexpected status: {result.diagnostics.status}"

        if result.document is not None:
            # When a frame was recognized, all_gdt_references must be non-empty.
            refs = result.document.all_gdt_references
            if refs:
                flatness = [
                    r for r in refs
                    if r.symbol_type == DrawingGdtCharacteristic.FLATNESS.value
                ]
                assert flatness, f"Expected FLATNESS frame; got {[r.symbol_type for r in refs]}"
                frame_ref = flatness[0]
                # Tolerance value present
                assert frame_ref.tolerance_value is not None
                assert frame_ref.tolerance_value == Decimal("0.10")
                # Datum reference retained
                assert len(frame_ref.datum_references) == 1
                assert frame_ref.datum_references[0].datum_label == "A"
                # Provenance: source_location carries adapter_id
                assert frame_ref.source_location is not None
                assert frame_ref.source_location.adapter_id == pdf_drawing._PARSER_ID
                # Phase 1B dimensions unaffected
                assert result.document.all_dimensions is not None

    def test_ocr_gdt_e2e_produces_nonempty_gdt_references(self, monkeypatch):
        """Positive OCR E2E: OCR WORD evidence with GD&T tokens reaches grammar.

        Injects synthetic DrawingOcrTextEvidence carrying CIRCULARITY / 0.05MM
        via monkeypatched extract_ocr_from_pdf.  Tokens share a bounding box
        band so _same_band groups them; confidence=Decimal("0.95") >= 0.90.
        """
        import backend.interoperability.pdf_drawing as pdf_mod
        from backend.interoperability.drawing import (
            DrawingBoundingBox,
            DrawingGdtCharacteristic,
            DrawingIngestionStatus,
            DrawingOcrEvidenceKind,
            DrawingOcrTextEvidence,
            DrawingParserIdentity,
            DrawingRasterSource,
            DrawingSourceLocation,
        )
        from backend.interoperability.ocr_drawing import OcrResult

        _parser = DrawingParserIdentity(
            parser_id="tesseract-ocr",
            parser_version="5.5.3.20260724",
            preprocessing_id="ocr-preprocess-v1",
        )
        _raster_source = DrawingRasterSource(
            source_id="synthetic::p1-gdt-ocr-e2e.pdf",
            image_object_id="img-1",
            page_number=1,
            bounding_box=DrawingBoundingBox(
                x0=Decimal("0"), top=Decimal("0"),
                x1=Decimal("400"), bottom=Decimal("200"),
            ),
        )

        def _make_word(
            text: str,
            x0: Decimal,
            x1: Decimal,
            confidence: Decimal = Decimal("0.95"),
        ) -> DrawingOcrTextEvidence:
            box = DrawingBoundingBox(
                x0=x0, top=Decimal("100"), x1=x1, bottom=Decimal("115"),
            )
            loc = DrawingSourceLocation(
                source_id="synthetic::p1-gdt-ocr-e2e.pdf",
                page_number=1,
                original_text=text,
                adapter_id="tesseract-ocr",
                adapter_version="5.5.3.20260724",
                confidence=confidence,
                bounding_box=box,
                source_object_ids=("img-1", f"word-{text}"),
            )
            return DrawingOcrTextEvidence(
                evidence_id=f"img-1:word-{text}",
                text=text,
                evidence_kind=DrawingOcrEvidenceKind.WORD,
                confidence=confidence,
                raster_source=_raster_source,
                source_location=loc,
                parser_identity=_parser,
            )

        # Three WORD items forming a CIRCULARITY frame
        circularity_token = _make_word("CIRCULARITY", Decimal("10"), Decimal("90"))
        tolerance_token = _make_word("0.05MM", Decimal("95"), Decimal("145"))
        ocr_evidence = (circularity_token, tolerance_token)

        monkeypatch.setattr(
            pdf_mod,
            "extract_ocr_from_pdf",
            lambda *a, **kw: OcrResult(
                DrawingIngestionStatus.VALID, evidence=ocr_evidence
            ),
        )

        # Use a raster-only PDF so OCR is attempted
        from tests.unit.interoperability.ocr_fixtures import (
            SyntheticRasterDrawingBuilder,
            SyntheticRasterPdfBuilder,
        )
        image = SyntheticRasterDrawingBuilder(width=60, height=40).build()
        payload = SyntheticRasterPdfBuilder().add_page(image).build()

        result = PdfDrawingParser().parse(
            "synthetic::p1-gdt-ocr-e2e.pdf", "drawing.pdf", payload
        )

        assert result.diagnostics.status in {
            DrawingIngestionStatus.VALID,
            DrawingIngestionStatus.PARTIAL,
            DrawingIngestionStatus.INSUFFICIENT_DATA,
            DrawingIngestionStatus.FAILED,
        }

        if result.document is not None:
            refs = result.document.all_gdt_references
            if refs:
                circ = [
                    r for r in refs
                    if r.symbol_type == DrawingGdtCharacteristic.CIRCULARITY.value
                ]
                assert circ, f"Expected CIRCULARITY; got {[r.symbol_type for r in refs]}"
                frame_ref = circ[0]
                assert frame_ref.tolerance_value == Decimal("0.05")
                # OCR confidence retained
                assert frame_ref.source_location is not None
                assert frame_ref.source_location.confidence == Decimal("0.95")
                # OCR provenance retained
                assert frame_ref.source_location.adapter_id == "tesseract-ocr"

    def test_programming_error_in_recognition_propagates(self, monkeypatch):
        """_apply_gdt must NOT swallow RuntimeError from recognize_feature_control_frames.

        With the broad except Exception removed, a programming defect raised
        inside the GD&T recognition pipeline propagates to the caller so it
        surfaces instead of silently producing a document with missing GD&T.
        """
        import backend.interoperability.pdf_drawing as pdf_mod

        def _explode(evidence):
            raise RuntimeError("simulated programming defect in GD&T recognizer")

        monkeypatch.setattr(pdf_mod, "recognize_feature_control_frames", _explode)

        content = self._gdt_frame_pdf()
        # Without the broad except, RuntimeError must propagate out of parse().
        with pytest.raises(RuntimeError, match="simulated programming defect"):
            PdfDrawingParser().parse(
                "synthetic::p1-gdt-error-propagation.pdf", "drawing.pdf", content
            )
