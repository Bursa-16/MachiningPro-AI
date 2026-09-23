"""Focused Phase 1C Task 6 GD&T grammar tests."""

from decimal import Decimal

from backend.interoperability.drawing import (
    CanonicalDrawing,
    DrawingBoundingBox,
    DrawingExtractionAuthority,
    DrawingGdtReference,
    DrawingIngestionStatus,
    DrawingParserIdentity,
    DrawingSourceLocation,
)
from backend.interoperability.gdt_drawing import (
    GdtTokenEvidence,
    GdtTokenSource,
    attach_feature_control_frames,
    map_feature_control_frames,
    recognize_feature_control_frames,
)


def _token(
    text: str,
    x: int,
    *,
    source: GdtTokenSource = GdtTokenSource.VECTOR,
    confidence: str = "0.95",
):
    box = DrawingBoundingBox(Decimal(x), Decimal("10"), Decimal(x + 20), Decimal("30"))
    parser = DrawingParserIdentity("vector-gdt", "1.0")
    location = DrawingSourceLocation(
        source_id="synthetic::gdt",
        page_number=1,
        adapter_id=parser.parser_id,
        adapter_version=parser.parser_version,
        authority=DrawingExtractionAuthority.EXTRACTED,
        confidence=Decimal(confidence),
        bounding_box=box,
        source_object_ids=(f"obj-{x}",),
    )
    return GdtTokenEvidence(
        evidence_id=f"obj-{x}",
        text=text,
        source_kind=source,
        confidence=Decimal(confidence),
        source_location=location,
        parser_identity=parser,
    )


def test_each_approved_characteristic_builds_a_frame():
    for characteristic in ("FLATNESS", "CIRCULARITY", "POSITION", "SYMMETRY"):
        result = recognize_feature_control_frames(
            (_token(characteristic, 0), _token("0.10 mm", 25), _token("A", 50))
        )
        assert result.status is DrawingIngestionStatus.VALID
        assert len(result.frames) == 1
        frame = result.frames[0]
        assert frame.characteristic.value == characteristic
        assert frame.tolerance_value == Decimal("0.10")
        assert frame.tolerance_unit == "mm"
        assert frame.datum_references[0].datum_label == "A"


def test_diameter_and_multiple_datums_are_typed_and_ordered():
    result = recognize_feature_control_frames(
        (_token("POSITION", 0), _token("DIA 0.05 mm", 25), _token("A", 50), _token("B", 75))
    )
    frame = result.frames[0]
    assert frame.diameter_applied is True
    assert tuple(d.datum_label for d in frame.datum_references) == ("A", "B")
    assert tuple(cell.cell_index for cell in frame.cells) == tuple(range(len(frame.cells)))


def test_malformed_unsupported_or_low_confidence_evidence_is_omitted():
    for tokens in (
        (_token("POSITION", 0), _token("0.1", 25), _token("A", 50)),
        (_token("POSITION", 0), _token("0.1 mm", 25), _token("MMC", 50)),
        (_token("POSITION", 0, confidence="0.89"), _token("0.1 mm", 25), _token("A", 50)),
        (_token("UNKNOWN", 0), _token("0.1 mm", 25), _token("A", 50)),
    ):
        result = recognize_feature_control_frames(tokens)
        assert result.frames == ()
        assert result.status is DrawingIngestionStatus.INSUFFICIENT_DATA


def test_vector_ocr_duplicates_merge_and_conflicts_are_omitted():
    vector = (_token("FLATNESS", 0), _token("0.10 mm", 25), _token("A", 50))
    ocr = tuple(
        _token(item.text, x, source=GdtTokenSource.OCR)
        for item, x in zip(vector, (0, 25, 50), strict=True)
    )
    merged = recognize_feature_control_frames(vector + ocr)
    assert merged.status is DrawingIngestionStatus.VALID
    assert len(merged.frames) == 1
    assert len(merged.frames[0].source_location.source_object_ids) >= 3

    conflict = recognize_feature_control_frames(
        vector
        + (
            _token("FLATNESS", 1, source=GdtTokenSource.OCR),
            _token("0.20 mm", 26, source=GdtTokenSource.OCR),
            _token("A", 51, source=GdtTokenSource.OCR),
        )
    )
    assert conflict.frames == ()
    assert "GDT_EVIDENCE_CONFLICT" in conflict.diagnostics


def test_ocr_may_supplement_a_missing_vector_cell():
    result = recognize_feature_control_frames(
        (
            _token("POSITION", 0),
            _token("0.05 mm", 25),
            _token("A", 50, source=GdtTokenSource.OCR),
        )
    )
    assert result.status is DrawingIngestionStatus.VALID
    assert tuple(d.datum_label for d in result.frames[0].datum_references) == ("A",)


def test_repeated_processing_is_deterministic_and_does_not_expose_raw_payloads():
    tokens = (_token("SYMMETRY", 0), _token("0.10 mm", 25), _token("A", 50))
    first = recognize_feature_control_frames(tokens)
    second = recognize_feature_control_frames(tokens)
    assert first == second
    assert "bytes" not in repr(first).lower()
    assert "traceback" not in repr(first).lower()


def test_task7_maps_frames_to_typed_references_and_attaches_canonically():
    recognition = recognize_feature_control_frames(
        (_token("POSITION", 0), _token("DIA 0.05 mm", 25), _token("A", 50))
    )
    references = map_feature_control_frames(recognition.frames)
    assert len(references) == 1
    reference = references[0]
    assert isinstance(reference, DrawingGdtReference)
    assert reference.feature_control_frame is recognition.frames[0]
    assert reference.symbol_type == "POSITION"
    assert reference.tolerance_value == Decimal("0.05")
    assert reference.tolerance_unit == "mm"
    assert reference.source_location == recognition.frames[0].source_location

    document = CanonicalDrawing(drawing_id="drawing-1", source_id="synthetic::gdt")
    assembled = attach_feature_control_frames(document, recognition.frames)
    assert assembled is not document
    assert assembled.all_gdt_references == references
    assert assembled.all_dimensions == document.all_dimensions
    assert assembled.all_tolerances == document.all_tolerances


def test_task7_mapping_omits_unrecognized_empty_frames_and_is_deterministic():
    first = map_feature_control_frames(())
    second = map_feature_control_frames(())
    assert first == second == ()


def test_task7_attachment_preserves_existing_gdt_references():
    existing = DrawingGdtReference(gdt_id="existing", symbol_type="legacy")
    document = CanonicalDrawing(
        drawing_id="drawing-1",
        source_id="synthetic::gdt",
        all_gdt_references=(existing,),
    )
    recognition = recognize_feature_control_frames(
        (_token("FLATNESS", 0), _token("0.10 mm", 25))
    )
    assembled = attach_feature_control_frames(document, recognition.frames)
    assert tuple(item.gdt_id for item in assembled.all_gdt_references) == (
        "existing",
        recognition.frames[0].frame_id,
    )
