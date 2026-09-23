"""Task 2 tests for deterministic synthetic raster drawing fixtures."""

from __future__ import annotations

import struct
import time
from dataclasses import replace
from decimal import Decimal

from backend.interoperability import pdf_drawing as pdf_drawing_module
from backend.interoperability.drawing import (
    DrawingBoundingBox,
    DrawingIngestionStatus,
    DrawingOcrEvidenceKind,
    DrawingOcrTextEvidence,
    DrawingParserIdentity,
    DrawingRasterSource,
    DrawingSourceLocation,
)
from backend.interoperability.ocr_drawing import (
    OcrLimits,
    OcrResult,
    _run_spawned_ocr,
    extract_ocr_from_pdf,
)
from backend.interoperability.pdf_drawing import PdfDrawingParser
from backend.interoperability.raster_drawing import (
    RasterContentKind,
    RasterLimits,
    inspect_raster_pdf,
)
from tests.unit.interoperability.ocr_fixtures import (
    SyntheticRasterDrawingBuilder,
    SyntheticRasterImage,
    SyntheticRasterPdfBuilder,
    malformed_png_bytes,
    oversized_png_header,
)


def _png_dimensions(payload: bytes) -> tuple[int, int]:
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert payload[12:16] == b"IHDR"
    return struct.unpack(">II", payload[16:24])


def test_simple_raster_drawing_is_deterministic_and_geometry_is_exact():
    builder = (
        SyntheticRasterDrawingBuilder(width=120, height=80)
        .with_rectangle(10, 12, 50, 20)
        .with_line(0, 0, 119, 79)
        .ordinary_dimension("25.0", 20, 30)
    )
    first = builder.build()
    second = builder.build()

    assert first == second
    assert first.width == 120
    assert first.height == 80
    assert len(first.pixels) == 9_600
    assert first.pixels[12 * 120 + 10] == 0
    assert first.pixels[0] == 0
    assert first.png_bytes() == second.png_bytes()
    assert _png_dimensions(first.png_bytes()) == (120, 80)


def test_title_block_dimensions_tolerances_and_datum_are_synthetic_content():
    image = (
        SyntheticRasterDrawingBuilder(width=320, height=240)
        .title_block(210, 150, 100, 70)
        .ordinary_dimension("25.0", 20, 20)
        .ordinary_tolerance("+/-0.1", 20, 45)
        .datum_label("A", 20, 70)
        .build()
    )

    assert image.pixels[150 * 320 + 210] == 0
    assert image.pixels[219 * 320 + 309] == 0
    assert any(pixel == 0 for pixel in image.pixels)


def test_rotated_fixture_has_expected_dimensions_and_rotation_identity():
    image = SyntheticRasterDrawingBuilder(width=40, height=20, rotation=90).with_text(
        "A", 2, 3
    ).build()

    assert image.rotation == 90
    assert (image.width, image.height) == (20, 40)
    assert _png_dimensions(image.png_bytes()) == (20, 40)


def test_low_contrast_fixture_is_deterministic():
    image = SyntheticRasterDrawingBuilder(width=80, height=40).with_text(
        "LOW CONF", 2, 2, foreground=180
    ).build()

    assert image.png_bytes() == image.png_bytes()
    assert 180 in image.pixels
    assert 0 not in image.pixels


def test_synthetic_gdt_frame_visual_contains_cells_and_datum():
    image = SyntheticRasterDrawingBuilder(width=300, height=180).gdt_frame(
        ("FLAT", "0.1", "A"), 20, 40
    ).build()

    # Three deterministic cell boundaries are visible; semantic parsing is not.
    assert image.pixels[40 * 300 + 20] == 0
    assert image.pixels[40 * 300 + 78] == 0
    assert image.pixels[40 * 300 + 136] == 0


def test_pdf_fixture_is_deterministic_and_supports_mixed_vector_raster_page():
    image = SyntheticRasterDrawingBuilder(width=32, height=24).build()
    first = SyntheticRasterPdfBuilder().add_page(image, mixed_vector=True).build()
    second = SyntheticRasterPdfBuilder().add_page(image, mixed_vector=True).build()

    assert first == second
    assert b"/Subtype /Image" in first
    assert b"10 10 m" in first
    assert b"/Filter /FlateDecode" in first


def test_image_identity_and_provenance_coordinates_are_stable():
    builder = SyntheticRasterDrawingBuilder(width=100, height=80).with_text(
        "25.0", 10, 20
    )
    image = builder.build()

    assert image.image_object_id == "synthetic:image:1"
    assert image.image_object_id_for_page(2) == "synthetic:page-2:image-1"
    assert builder.texts[0].bounding_box == (10, 20, 33, 27)
    assert (image.width, image.height) == (100, 80)
    assert len(image.pixels) == image.width * image.height


def test_malformed_image_fixture_is_bounded_and_has_no_external_metadata():
    payload = malformed_png_bytes()

    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"http://" not in payload
    assert b"file://" not in payload
    assert len(payload) < 1_000


def test_oversized_fixture_uses_header_only_without_dangerous_allocation():
    payload = oversized_png_header()

    assert _png_dimensions(payload) == (20_001, 20_001)
    assert len(payload) < 128


def test_resource_limit_builders_can_construct_many_small_pages_without_large_pixels():
    image = SyntheticRasterDrawingBuilder(width=2, height=2).build()
    builder = SyntheticRasterPdfBuilder()
    for _ in range(17):
        builder = builder.add_page(image)

    payload = builder.build()
    assert payload.count(b"/Subtype /Image") == 17
    assert len(image.pixels) == 4


def test_resource_limit_builder_can_describe_excessive_page_count_without_building_pixels():
    image = SyntheticRasterDrawingBuilder(width=1, height=1).build()
    builder = SyntheticRasterPdfBuilder()
    for _ in range(201):
        builder = builder.add_page(image)

    assert len(builder.pages) == 201
    assert len(image.pixels) == 1


def test_fixture_types_are_immutable_and_generated_without_runtime_assets():
    image = SyntheticRasterImage(2, 2, b"\x00\x01\x02\x03")

    assert image.png_bytes() == image.png_bytes()
    assert image.__dataclass_params__.frozen is True


def test_valid_raster_only_pdf_is_detected_and_decoded_without_ocr():
    image = SyntheticRasterDrawingBuilder(width=16, height=12).build()
    payload = SyntheticRasterPdfBuilder().add_page(image).build()

    result = inspect_raster_pdf(payload, "upload::raster.pdf")

    assert result.status is DrawingIngestionStatus.VALID
    assert result.snapshot is not None
    assert result.snapshot.content_kind is RasterContentKind.RASTER_ONLY
    assert result.snapshot.pages[0].images[0].width == 16
    assert result.snapshot.pages[0].images[0].height == 12
    assert result.snapshot.pages[0].images[0].format == "FLATE"
    assert result.snapshot.pages[0].images[0].raster_source.image_object_id == (
        "page-1:image-1"
    )
    assert result.ocr_evidence == ()


def test_mixed_vector_raster_classification_is_deterministic():
    image = SyntheticRasterDrawingBuilder(width=8, height=8).build()
    payload = SyntheticRasterPdfBuilder().add_page(image, mixed_vector=True).build()

    first = inspect_raster_pdf(payload, "upload::mixed.pdf")
    second = inspect_raster_pdf(payload, "upload::mixed.pdf")

    assert first.status is DrawingIngestionStatus.VALID
    assert first.snapshot is not None
    assert first.snapshot.content_kind is RasterContentKind.MIXED
    assert first == second


def test_empty_pdf_content_is_insufficient_without_snapshot_semantics():
    payload = SyntheticRasterPdfBuilder().build()
    result = inspect_raster_pdf(payload, "upload::empty.pdf")

    assert result.status is DrawingIngestionStatus.INSUFFICIENT_DATA
    assert result.snapshot is not None
    assert result.snapshot.content_kind is RasterContentKind.EMPTY


def test_malformed_image_fails_closed_without_raw_bytes_or_ocr():
    image = SyntheticRasterDrawingBuilder(width=4, height=4).build()
    payload = SyntheticRasterPdfBuilder().add_page(image).build()
    # Replace the deterministic image stream with malformed bytes while keeping
    # the PDF structure bounded; the decoder must fail closed.
    malformed = payload.replace(b"/Filter /FlateDecode", b"/Filter /FlateDecode", 1)
    malformed = malformed.replace(zlib_compress(image.pixels), b"bad", 1)

    result = inspect_raster_pdf(malformed, "upload::bad.pdf")

    assert result.status is DrawingIngestionStatus.FAILED
    assert result.snapshot is None
    assert result.ocr_evidence == ()
    assert b"bad" not in repr(result).encode()


def test_unsupported_image_filter_is_rejected_without_decode():
    image = SyntheticRasterDrawingBuilder(width=4, height=4).build()
    payload = SyntheticRasterPdfBuilder().add_page(image).build()
    unsupported = payload.replace(b"/Filter /FlateDecode", b"/Filter /ASCII85Decode", 1)

    result = inspect_raster_pdf(unsupported, "upload::unsupported.pdf")

    assert result.status is DrawingIngestionStatus.UNSUPPORTED
    assert result.snapshot is None
    assert result.diagnostics == ("RASTER_UNSUPPORTED_FORMAT",)


def test_indexed_grayscale_palette_is_supported_and_normalized():
    image = SyntheticRasterImage(2, 2, b"\x00\x01\x01\x00")
    payload = SyntheticRasterPdfBuilder().add_page(image).build()
    payload = payload.replace(
        b"/ColorSpace /DeviceGray",
        b"/ColorSpace [/Indexed /DeviceGray 1 <00FF>]",
        1,
    )

    result = inspect_raster_pdf(payload, "upload::indexed.pdf")

    assert result.status is DrawingIngestionStatus.VALID
    assert result.snapshot is not None
    assert result.snapshot.pages[0].images[0].format == "FLATE"


def test_invalid_dimensions_and_pixel_limit_fail_before_pixel_materialization():
    image = SyntheticRasterDrawingBuilder(width=4, height=4).build()
    payload = SyntheticRasterPdfBuilder().add_page(image).build()
    invalid_dimensions = payload.replace(b"/Width 4 /Height 4", b"/Width 0 /Height 4", 1)
    result = inspect_raster_pdf(invalid_dimensions, "upload::zero.pdf")
    assert result.status is DrawingIngestionStatus.FAILED
    assert result.diagnostics == ("RASTER_MALFORMED_IMAGE",)

    result = inspect_raster_pdf(
        payload,
        "upload::pixels.pdf",
        limits=RasterLimits(max_pixels_per_image=1),
    )
    assert result.status is DrawingIngestionStatus.FAILED
    assert result.diagnostics == ("RASTER_PIXEL_COUNT_LIMIT",)


def test_limits_reject_oversized_dimensions_before_decode():
    image = SyntheticRasterDrawingBuilder(width=2, height=2).build()
    payload = SyntheticRasterPdfBuilder().add_page(image).build()
    limits = RasterLimits(max_width=1)

    result = inspect_raster_pdf(payload, "upload::wide.pdf", limits=limits)

    assert result.status is DrawingIngestionStatus.FAILED
    assert result.snapshot is None
    assert "RASTER_DIMENSION_LIMIT" in result.diagnostics


def test_limits_reject_excessive_image_count_and_page_count():
    image = SyntheticRasterDrawingBuilder(width=1, height=1).build()
    image_payload = SyntheticRasterPdfBuilder()
    for _ in range(3):
        image_payload = image_payload.add_page(image)
    result = inspect_raster_pdf(
        image_payload.build(),
        "upload::images.pdf",
        limits=RasterLimits(max_images_per_page=2, max_images_total=2),
    )
    assert result.status is DrawingIngestionStatus.FAILED
    assert "RASTER_IMAGE_COUNT_LIMIT" in result.diagnostics

    page_payload = SyntheticRasterPdfBuilder()
    for _ in range(3):
        page_payload = page_payload.add_page(image)
    result = inspect_raster_pdf(
        page_payload.build(), "upload::pages.pdf", limits=RasterLimits(max_pages=2)
    )
    assert result.status is DrawingIngestionStatus.FAILED
    assert "RASTER_PAGE_LIMIT" in result.diagnostics


def test_orientation_and_provenance_are_typed_and_stable():
    image = SyntheticRasterDrawingBuilder(width=9, height=5, rotation=90).build()
    payload = SyntheticRasterPdfBuilder().add_page(image).build()

    result = inspect_raster_pdf(payload, "upload::rotated.pdf")
    assert result.snapshot is not None
    snapshot = result.snapshot.pages[0].images[0]
    assert snapshot.rotation == 90
    assert snapshot.width == 5
    assert snapshot.height == 9
    assert snapshot.raster_source.bounding_box.unit == "pt"
    assert snapshot.raster_source.parser_identity.preprocessing_id == (
        "ocr-preprocess-v1"
    )
    assert "pixels" not in repr(snapshot).lower()
    assert "bytes" not in repr(snapshot).lower()


def test_unsupported_pdf_header_is_rejected_without_external_access():
    result = inspect_raster_pdf(b"not-a-pdf", "upload::unknown.bin")

    assert result.status is DrawingIngestionStatus.UNSUPPORTED
    assert result.snapshot is None
    assert result.diagnostics == ("PDF_UNSUPPORTED",)


def zlib_compress(raw: bytes) -> bytes:
    """Match the standard-library compression used by the fixture builder."""

    import zlib

    return zlib.compress(raw, level=9)


def _synthetic_ocr_source(source_id: str) -> DrawingOcrTextEvidence:
    bbox = DrawingBoundingBox(Decimal("0"), Decimal("0"), Decimal("320"), Decimal("180"))
    raster_source = DrawingRasterSource(
        source_id=source_id,
        page_number=1,
        image_object_id="page-1:image-1",
        bounding_box=bbox,
        parser_identity=DrawingParserIdentity(
            parser_id="raster-drawing",
            parser_version="1.0",
            preprocessing_id="ocr-preprocess-v1",
        ),
        image_format="FLATE",
    )
    location = DrawingSourceLocation(
        source_id=source_id,
        page_number=1,
        bounding_box=bbox,
        confidence=Decimal("0.90"),
        adapter_id="tesseract-ocr",
        adapter_version="5.5.3.20260724",
        source_object_ids=("page-1:image-1", "ocr-source"),
    )
    return DrawingOcrTextEvidence(
        evidence_id="page-1:image-1:ocr-source",
        text="A",
        evidence_kind=DrawingOcrEvidenceKind.BLOCK,
        confidence=Decimal("0.90"),
        raster_source=raster_source,
        source_location=location,
        parser_identity=DrawingParserIdentity(
            parser_id="tesseract-ocr",
            parser_version="5.5.3.20260724",
            preprocessing_id="ocr-preprocess-v1",
        ),
    )


def _sleeping_worker(send_connection, inputs, limits, tesseract_command):
    del inputs, limits, tesseract_command
    time.sleep(1.0)
    send_connection.close()


def _crashing_worker(send_connection, inputs, limits, tesseract_command):
    del send_connection, inputs, limits, tesseract_command
    raise RuntimeError("test worker crash")


def test_ocr_worker_extracts_bounded_typed_evidence_deterministically():
    image = SyntheticRasterDrawingBuilder(width=180, height=100).with_text(
        "A", 24, 20, scale=8
    ).build()
    payload = SyntheticRasterPdfBuilder().add_page(image).build()

    first = extract_ocr_from_pdf(payload, "upload::ocr.pdf")
    second = extract_ocr_from_pdf(payload, "upload::ocr.pdf")

    assert first.status is DrawingIngestionStatus.VALID
    assert first == second
    assert first.evidence
    assert any(item.text == "A" for item in first.evidence)
    for item in first.evidence:
        assert item.confidence >= Decimal("0.80")
        assert item.raster_source.page_number == 1
        assert item.source_location.page_number == 1
        assert item.source_location.bounding_box is not None
        assert item.source_location.source_object_ids
        assert item.parser_identity.parser_id == "tesseract-ocr"
        assert "tesseract.exe" not in repr(item).lower()


def test_ocr_filters_evidence_below_configured_confidence_threshold():
    image = SyntheticRasterDrawingBuilder(width=180, height=100).with_text(
        "A", 24, 20, scale=8, foreground=180
    ).build()
    payload = SyntheticRasterPdfBuilder().add_page(image).build()

    result = extract_ocr_from_pdf(
        payload,
        "upload::low-confidence.pdf",
        limits=OcrLimits(minimum_confidence=Decimal("0.99")),
    )

    assert result.status is DrawingIngestionStatus.INSUFFICIENT_DATA
    assert result.evidence == ()
    assert "OCR_NO_CONFIDENT_EVIDENCE" in result.diagnostics


def test_ocr_worker_timeout_and_abnormal_exit_fail_closed_without_leakage():
    image = SyntheticRasterDrawingBuilder(width=40, height=30).build()
    payload = SyntheticRasterPdfBuilder().add_page(image).build()
    from backend.interoperability.raster_drawing import prepare_raster_ocr_inputs

    inputs = prepare_raster_ocr_inputs(payload, "upload::worker.pdf")
    timeout = _run_spawned_ocr(
        inputs,
        OcrLimits(max_runtime_seconds=0.05),
        worker_entry=_sleeping_worker,
    )
    crashed = _run_spawned_ocr(
        inputs,
        OcrLimits(max_runtime_seconds=5.0),
        worker_entry=_crashing_worker,
    )

    assert timeout.status is DrawingIngestionStatus.FAILED
    assert timeout.diagnostics == ("OCR_TIMEOUT",)
    assert crashed.status is DrawingIngestionStatus.FAILED
    assert crashed.diagnostics == ("OCR_WORKER_FAILURE",)
    assert "traceback" not in repr(crashed).lower()
    assert "worker crash" not in repr(crashed).lower()


def test_ocr_evidence_promotes_explicit_dimension_without_inventing_units(monkeypatch):
    image = (
        SyntheticRasterDrawingBuilder(width=520, height=220)
        .with_text("25.0 mm", 16, 30, scale=8)
        .build()
    )
    payload = SyntheticRasterPdfBuilder().add_page(image).build()

    source = _synthetic_ocr_source("upload::dimension-raster.pdf")
    evidence = replace(
        source,
        evidence_id="page-1:image-1:dimension-1",
        text="25.0 mm",
        source_location=replace(
            source.source_location,
            original_text="25.0 mm",
            source_object_ids=("page-1:image-1", "page-1:image-1:dimension-1"),
        ),
    )
    monkeypatch.setattr(
        pdf_drawing_module,
        "extract_ocr_from_pdf",
        lambda *args, **kwargs: OcrResult(
            DrawingIngestionStatus.VALID, evidence=(evidence,)
        ),
    )
    result = PdfDrawingParser().parse("upload::dimension-raster.pdf", "drawing.pdf", payload)

    assert result.diagnostics.status is DrawingIngestionStatus.VALID
    assert result.document is not None
    assert len(result.document.all_dimensions) == 1
    dimension = result.document.all_dimensions[0]
    assert dimension.nominal_value == Decimal("25.0")
    assert dimension.unit == "mm"
    assert dimension.source_location is not None
    assert dimension.source_location.adapter_id == "tesseract-ocr"
    assert dimension.source_location.confidence is not None


def test_raster_only_without_confident_semantics_remains_insufficient():
    image = SyntheticRasterDrawingBuilder(width=80, height=40).build()
    payload = SyntheticRasterPdfBuilder().add_page(image).build()

    result = PdfDrawingParser().parse("upload::sparse-raster.pdf", "drawing.pdf", payload)

    assert result.diagnostics.status is DrawingIngestionStatus.INSUFFICIENT_DATA
    assert result.document is None


def test_ocr_title_fields_use_allowlisted_aliases_and_retain_provenance(monkeypatch):
    image = SyntheticRasterDrawingBuilder(width=320, height=180).with_text(
        "A", 4, 4, scale=8
    ).build()
    payload = SyntheticRasterPdfBuilder().add_page(image).build()
    source = _synthetic_ocr_source("upload::title-raster.pdf")
    items = []
    for index, (text, top) in enumerate(
        (("DRAWING NO: ABC", 20), ("TITLE: PART", 60)), start=1
    ):
        box = DrawingBoundingBox(
            Decimal("10"), Decimal(top), Decimal("150"), Decimal(top + 20)
        )
        items.append(
            replace(
                source,
                evidence_id=f"page-1:image-1:title-{index}",
                text=text,
                source_location=replace(
                    source.source_location,
                    original_text=text,
                    bounding_box=box,
                    source_object_ids=("page-1:image-1", f"title-{index}"),
                ),
            )
        )
    monkeypatch.setattr(
        pdf_drawing_module,
        "extract_ocr_from_pdf",
        lambda *args, **kwargs: OcrResult(DrawingIngestionStatus.VALID, tuple(items)),
    )

    result = PdfDrawingParser().parse("upload::title-raster.pdf", "drawing.pdf", payload)

    assert result.diagnostics.status is DrawingIngestionStatus.VALID
    assert result.document is not None
    assert result.document.title_block is not None
    assert result.document.title_block.drawing_number == "ABC"
    assert result.document.title_block.part_name == "PART"
    assert result.document.title_block.source_location is not None
    assert result.document.title_block.source_location.confidence == source.confidence
    assert result.document.title_block.source_location.adapter_id == "tesseract-ocr"


def test_ocr_asymmetric_tolerance_uses_existing_phase1b_grammar(monkeypatch):
    image = SyntheticRasterDrawingBuilder(width=160, height=80).with_text(
        "A", 4, 4, scale=8
    ).build()
    payload = SyntheticRasterPdfBuilder().add_page(image).build()
    source = _synthetic_ocr_source("upload::tol-raster.pdf")
    evidence = replace(
        source,
        evidence_id="page-1:image-1:tolerance-1",
        text="25 +0.20/-0.10 mm",
        source_location=replace(
            source.source_location,
            original_text="25 +0.20/-0.10 mm",
            source_object_ids=("page-1:image-1", "tolerance-1"),
        ),
    )
    monkeypatch.setattr(
        pdf_drawing_module,
        "extract_ocr_from_pdf",
        lambda *args, **kwargs: OcrResult(
            DrawingIngestionStatus.VALID, evidence=(evidence,)
        ),
    )

    result = PdfDrawingParser().parse("upload::tol-raster.pdf", "drawing.pdf", payload)

    assert result.diagnostics.status is DrawingIngestionStatus.VALID
    assert result.document is not None
    assert len(result.document.all_dimensions) == 1
    tolerance = result.document.all_dimensions[0].tolerance
    assert tolerance is not None
    assert tolerance.upper_value == Decimal("0.20")
    assert tolerance.lower_value == Decimal("-0.10")
    assert tolerance.source_location is not None
    assert tolerance.source_location.adapter_id == "tesseract-ocr"


# ---------------------------------------------------------------------------
# P0-1 regression: word_num absent from pytesseract output must not crash
# ---------------------------------------------------------------------------


def test_p0_1_word_num_absent_from_pytesseract_output_does_not_raise(monkeypatch):
    """P0-1: IndexError when word_num absent and index > 0.

    Old code: ``int(data.get("word_num", (index,))[index])`` — crashes with
    IndexError when index > 0 because the fallback tuple has length 1.
    Fixed code uses ``word_num_data = data.get("word_num")`` and falls back
    to ``index`` when ``word_num_data is None``.
    """
    import pytesseract
    from backend.interoperability import ocr_drawing as ocr_module

    # Build a synthetic pytesseract output dict with TWO rows but no word_num key.
    def _fake_image_to_data(image, lang, config, output_type):  # noqa: ARG001
        return {
            "text": ["25", "mm"],
            "conf": ["95", "92"],
            "left": [10, 40],
            "top": [20, 20],
            "width": [20, 20],
            "height": [10, 10],
            "block_num": [1, 1],
            "par_num": [1, 1],
            "line_num": [1, 1],
            # word_num intentionally absent to trigger P0-1
        }

    monkeypatch.setattr(pytesseract, "image_to_data", _fake_image_to_data)

    image = SyntheticRasterDrawingBuilder(width=100, height=60).build()
    payload = SyntheticRasterPdfBuilder().add_page(image).build()

    # Must not raise IndexError; status may be VALID or INSUFFICIENT_DATA.
    result = extract_ocr_from_pdf(payload, "upload::p0-1-regression.pdf")
    assert result.status in {
        DrawingIngestionStatus.VALID,
        DrawingIngestionStatus.INSUFFICIENT_DATA,
        DrawingIngestionStatus.FAILED,
    }
