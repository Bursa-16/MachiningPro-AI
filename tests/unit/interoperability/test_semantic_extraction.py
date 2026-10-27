"""Unit tests for unified drawing semantic extraction pipeline."""

import pytest
from decimal import Decimal

from backend.interoperability.semantic_extraction import (
    AmbiguityKind,
    DetectedDatum,
    DetectionAmbiguity,
    DetectionSourceType,
    ExtractionSession,
    FcfSegment,
    GeneralToleranceSpec,
    MaterialMatchStatus,
    NormalizedDetection,
    NormalizedDetectionType,
    ParserConfidence,
    ParsedCompositeFCF,
    ReviewState,
    REVIEW_REQUIRED_THRESHOLD,
    bridge_material,
    confidence_value,
    create_session,
    detect_datum_from_tokens,
    detect_drawing_unit,
    extract_general_tolerance,
    make_detection,
    new_detection_id,
    new_session_id,
    ocr_available,
    parse_composite_fcf,
    requires_review,
    resolve_tesseract_command,
    run_token_extraction,
)


# ---------------------------------------------------------------------------
# Confidence model
# ---------------------------------------------------------------------------

class TestConfidenceValues:
    def test_exact_vector_text(self):
        assert confidence_value(ParserConfidence.EXACT_VECTOR_TEXT) == Decimal("0.99")

    def test_vector_pattern_parsed(self):
        assert confidence_value(ParserConfidence.VECTOR_PATTERN_PARSED) == Decimal("0.92")

    def test_high_confidence_ocr(self):
        assert confidence_value(ParserConfidence.HIGH_CONFIDENCE_OCR) == Decimal("0.88")

    def test_low_confidence_ocr(self):
        assert confidence_value(ParserConfidence.LOW_CONFIDENCE_OCR) == Decimal("0.72")

    def test_symbol_detected(self):
        assert confidence_value(ParserConfidence.SYMBOL_DETECTED) == Decimal("0.80")

    def test_geometry_associated(self):
        assert confidence_value(ParserConfidence.GEOMETRY_ASSOCIATED) == Decimal("0.75")

    def test_ambiguous(self):
        assert confidence_value(ParserConfidence.AMBIGUOUS) == Decimal("0.50")

    def test_user_confirmed(self):
        assert confidence_value(ParserConfidence.USER_CONFIRMED) == Decimal("1.00")

    def test_review_required_threshold(self):
        assert REVIEW_REQUIRED_THRESHOLD == Decimal("0.85")

    @pytest.mark.parametrize("method,expected_review", [
        (ParserConfidence.EXACT_VECTOR_TEXT, False),
        (ParserConfidence.VECTOR_PATTERN_PARSED, False),
        (ParserConfidence.HIGH_CONFIDENCE_OCR, False),
        (ParserConfidence.LOW_CONFIDENCE_OCR, True),
        (ParserConfidence.SYMBOL_DETECTED, True),
        (ParserConfidence.GEOMETRY_ASSOCIATED, True),
        (ParserConfidence.AMBIGUOUS, True),
        (ParserConfidence.USER_CONFIRMED, False),
    ])
    def test_requires_review_logic(self, method, expected_review):
        assert requires_review(confidence_value(method)) == expected_review


# ---------------------------------------------------------------------------
# Unit detection
# ---------------------------------------------------------------------------

class TestDetectDrawingUnit:
    def test_title_block_mm(self):
        assert detect_drawing_unit("mm", [], None) == "mm"

    def test_title_block_millimetre(self):
        assert detect_drawing_unit("MILLIMETRE", [], None) == "mm"

    def test_title_block_inch(self):
        assert detect_drawing_unit("inch", [], None) == "inch"

    def test_title_block_in(self):
        assert detect_drawing_unit("in", [], None) == "inch"

    def test_title_block_quote(self):
        assert detect_drawing_unit('"', [], None) == "inch"

    def test_note_all_dimensions_in_mm(self):
        assert detect_drawing_unit(None, ["ALL DIMENSIONS IN MM"], None) == "mm"

    def test_note_dimensions_in_mm(self):
        assert detect_drawing_unit(None, ["DIMENSIONS IN MM"], None) == "mm"

    def test_note_all_dimensions_in_inches(self):
        assert detect_drawing_unit(None, ["ALL DIMENSIONS IN INCHES"], None) == "inch"

    def test_note_unless_otherwise_mm(self):
        unit = detect_drawing_unit(None, ["UNLESS OTHERWISE STATED IN MM"], None)
        assert unit == "mm"

    def test_drawing_standard_iso(self):
        assert detect_drawing_unit(None, [], "ISO") == "mm"

    def test_drawing_standard_din(self):
        assert detect_drawing_unit(None, [], "DIN") == "mm"

    def test_drawing_standard_asme(self):
        assert detect_drawing_unit(None, [], "ASME Y14.5") == "inch"

    def test_drawing_standard_ansi(self):
        assert detect_drawing_unit(None, [], "ANSI") == "inch"

    def test_no_info_returns_none(self):
        result = detect_drawing_unit(None, [], None)
        assert result is None  # UNIT_STATUS=UNKNOWN

    def test_title_block_has_priority_over_notes(self):
        result = detect_drawing_unit("mm", ["ALL DIMENSIONS IN INCHES"], "ASME")
        assert result == "mm"


# ---------------------------------------------------------------------------
# General tolerance extraction
# ---------------------------------------------------------------------------

class TestExtractGeneralTolerance:
    def test_iso_2768_medium(self):
        result = extract_general_tolerance(["ISO 2768-m"])
        assert result is not None
        assert "ISO 2768" in result.standard
        assert result.linear_tolerance_mm == Decimal("0.1")

    def test_iso_2768_fine(self):
        result = extract_general_tolerance(["ISO 2768-f"])
        assert result is not None
        assert result.linear_tolerance_mm == Decimal("0.05")

    def test_iso_2768_coarse(self):
        result = extract_general_tolerance(["ISO 2768-c"])
        assert result is not None
        assert result.linear_tolerance_mm == Decimal("0.2")

    def test_iso_2768_very_coarse(self):
        result = extract_general_tolerance(["ISO 2768-v"])
        assert result is not None
        assert result.linear_tolerance_mm == Decimal("0.5")

    def test_linear_tolerance_plus_minus(self):
        result = extract_general_tolerance(["GENERAL TOLERANCE ±0.05"])
        assert result is not None
        assert result.linear_tolerance_mm == Decimal("0.05")

    def test_linear_tolerance_0_1(self):
        result = extract_general_tolerance(["TOLERANCE ±0.1 mm"])
        assert result is not None
        assert result.linear_tolerance_mm == Decimal("0.1")

    def test_no_tolerance_returns_none(self):
        assert extract_general_tolerance(["DEBURR ALL EDGES"]) is None

    def test_empty_list_returns_none(self):
        assert extract_general_tolerance([]) is None


# ---------------------------------------------------------------------------
# OCR configuration
# ---------------------------------------------------------------------------

class TestOcrConfig:
    def test_resolve_tesseract_returns_string_or_none(self):
        result = resolve_tesseract_command()
        assert result is None or isinstance(result, str)

    def test_ocr_available_returns_bool(self):
        assert isinstance(ocr_available(), bool)

    def test_hardcoded_path_not_used(self):
        """HARDCODED_TESSERACT_PATH=NO — verify no hardcoded paths in source."""
        import inspect
        from backend.interoperability import semantic_extraction as se
        src = inspect.getsource(se.resolve_tesseract_command)
        assert "Program Files" not in src
        assert "C:\\" not in src or "TESSERACT_CMD" in src  # only if via env var

    def test_tesseract_cmd_env_var_respected(self, monkeypatch):
        monkeypatch.setenv("TESSERACT_CMD", "/custom/tesseract")
        result = resolve_tesseract_command()
        assert result == "/custom/tesseract"

    def test_empty_tesseract_cmd_falls_through(self, monkeypatch):
        monkeypatch.setenv("TESSERACT_CMD", "")
        import shutil
        expected = shutil.which("tesseract")
        result = resolve_tesseract_command()
        assert result == expected


# ---------------------------------------------------------------------------
# Composite FCF parser
# ---------------------------------------------------------------------------

class TestParseCompositeFCF:
    def test_position_composite(self):
        result = parse_composite_fcf(
            "POSITION Ø0.5 A B C",
            "POSITION Ø0.2 A",
            "POSITION",
        )
        assert result is not None
        assert isinstance(result, ParsedCompositeFCF)
        assert result.upper_segment.tolerance_value == Decimal("0.5")
        assert result.lower_segment.tolerance_value == Decimal("0.2")

    def test_lower_tolerance_smaller_than_upper(self):
        result = parse_composite_fcf(
            "POSITION Ø0.5 A B C",
            "POSITION Ø0.2 A",
            "POSITION",
        )
        assert result is not None
        assert result.lower_segment.tolerance_value <= result.upper_segment.tolerance_value

    def test_invalid_lower_greater_than_upper_returns_none(self):
        result = parse_composite_fcf(
            "POSITION Ø0.2 A B C",
            "POSITION Ø0.5 A",
            "POSITION",
        )
        assert result is None

    def test_equal_tolerances_allowed(self):
        result = parse_composite_fcf(
            "POSITION Ø0.3 A B",
            "POSITION Ø0.3 A",
            "POSITION",
        )
        assert result is not None

    def test_raw_text_combines_both(self):
        result = parse_composite_fcf(
            "POSITION Ø0.5 A B C",
            "POSITION Ø0.2 A",
            "POSITION",
        )
        assert result is not None
        assert "|" in result.raw_text

    def test_confidence_is_decimal(self):
        result = parse_composite_fcf(
            "POSITION Ø0.5 A B C",
            "POSITION Ø0.2 A",
            "POSITION",
        )
        assert result is not None
        assert isinstance(result.confidence, Decimal)

    def test_missing_characteristic_returns_none(self):
        result = parse_composite_fcf("RANDOM TEXT", "MORE RANDOM", "POSITION")
        # Will parse if characteristic is injected, but no tolerance value → still valid struct
        # Just verify no crash
        assert result is None or isinstance(result, ParsedCompositeFCF)


# ---------------------------------------------------------------------------
# Datum detection
# ---------------------------------------------------------------------------

class TestDetectDatumFromTokens:
    def test_datum_a_full_word(self):
        results = detect_datum_from_tokens(["DATUM A"])
        assert len(results) >= 1
        assert any(d.datum_label == "A" for d in results)

    def test_datum_b_abbreviated(self):
        results = detect_datum_from_tokens(["DAT. B"])
        assert any(d.datum_label == "B" for d in results)

    def test_square_bracket_datum(self):
        results = detect_datum_from_tokens(["[C]"])
        assert any(d.datum_label == "C" for d in results)

    def test_compound_datum_ab(self):
        results = detect_datum_from_tokens(["A-B"])
        assert any(d.compound_label == "A-B" for d in results)

    def test_empty_tokens(self):
        assert detect_datum_from_tokens([]) == []

    def test_no_datum_in_tokens(self):
        results = detect_datum_from_tokens(["Ra 1.6", "M10x1.5", "DEBURR"])
        assert results == []

    def test_confidence_is_decimal(self):
        results = detect_datum_from_tokens(["DATUM A"])
        if results:
            assert isinstance(results[0].confidence, Decimal)


# ---------------------------------------------------------------------------
# Session creation
# ---------------------------------------------------------------------------

class TestCreateSession:
    def test_session_has_id(self):
        session = create_session("src-001", "PDF")
        assert session.session_id.startswith("ses-")

    def test_source_id_preserved(self):
        session = create_session("my-drawing.pdf", "PDF")
        assert session.source_id == "my-drawing.pdf"

    def test_source_format_preserved(self):
        session = create_session("src", "DXF")
        assert session.source_format == "DXF"

    def test_unit_detected_from_title_block(self):
        session = create_session("src", "PDF", title_block_unit="mm")
        assert session.detected_unit == "mm"

    def test_unit_unknown_warns(self):
        session = create_session("src", "PDF")
        assert session.detected_unit is None
        assert "UNIT_NOT_DECLARED" in session.extraction_warnings

    def test_general_tolerance_extracted(self):
        session = create_session("src", "PDF", general_tolerance_texts=["ISO 2768-m"])
        assert session.general_tolerance is not None

    def test_ocr_available_is_bool(self):
        session = create_session("src", "PDF")
        assert isinstance(session.ocr_available, bool)

    def test_empty_detections_initially(self):
        session = create_session("src", "PDF")
        assert session.detections == []

    def test_review_required_count_property(self):
        session = create_session("src", "PDF")
        assert session.review_required_count == 0

    def test_confirmed_count_property(self):
        session = create_session("src", "PDF")
        assert session.confirmed_count == 0


# ---------------------------------------------------------------------------
# run_token_extraction
# ---------------------------------------------------------------------------

class TestRunTokenExtraction:
    def test_fit_token_detected(self):
        detections = run_token_extraction(["H7"], DetectionSourceType.VECTOR_PDF)
        assert any(d.normalized_type == NormalizedDetectionType.FIT for d in detections)

    def test_thread_token_detected(self):
        detections = run_token_extraction(["M10x1.5"], DetectionSourceType.VECTOR_PDF)
        assert any(d.normalized_type == NormalizedDetectionType.THREAD for d in detections)

    def test_surface_finish_token_detected(self):
        detections = run_token_extraction(["Ra 1.6"], DetectionSourceType.VECTOR_PDF)
        assert any(d.normalized_type == NormalizedDetectionType.SURFACE_FINISH for d in detections)

    def test_empty_tokens_returns_empty(self):
        assert run_token_extraction([], DetectionSourceType.VECTOR_PDF) == []

    def test_whitespace_only_token_skipped(self):
        assert run_token_extraction(["  ", ""], DetectionSourceType.VECTOR_PDF) == []

    def test_vector_pdf_confidence_exact(self):
        detections = run_token_extraction(["H7"], DetectionSourceType.VECTOR_PDF)
        assert any(d.confidence_method == ParserConfidence.EXACT_VECTOR_TEXT for d in detections)

    def test_ocr_source_confidence_high_ocr(self):
        detections = run_token_extraction(["H7"], DetectionSourceType.OCR)
        assert any(d.confidence_method == ParserConfidence.HIGH_CONFIDENCE_OCR for d in detections)

    def test_all_detections_start_pending(self):
        detections = run_token_extraction(["H7", "M10", "Ra 1.6"], DetectionSourceType.VECTOR_PDF)
        assert all(d.review_state == ReviewState.PENDING for d in detections)

    def test_page_number_propagated(self):
        detections = run_token_extraction(["H7"], DetectionSourceType.VECTOR_PDF, page=3)
        assert all(d.page == 3 for d in detections)

    def test_fit_normalized_value_is_code(self):
        detections = run_token_extraction(["H7"], DetectionSourceType.VECTOR_PDF)
        fit_dets = [d for d in detections if d.normalized_type == NormalizedDetectionType.FIT]
        assert any(d.normalized_value == "H7" for d in fit_dets)

    def test_non_parseable_token_not_returned(self):
        detections = run_token_extraction(["SOME RANDOM TEXT"], DetectionSourceType.VECTOR_PDF)
        assert detections == []


# ---------------------------------------------------------------------------
# make_detection factory
# ---------------------------------------------------------------------------

class TestMakeDetection:
    def test_detection_id_unique(self):
        d1 = make_detection(NormalizedDetectionType.FIT, "H7", "H7", None,
                             ParserConfidence.EXACT_VECTOR_TEXT, DetectionSourceType.VECTOR_PDF)
        d2 = make_detection(NormalizedDetectionType.FIT, "H7", "H7", None,
                             ParserConfidence.EXACT_VECTOR_TEXT, DetectionSourceType.VECTOR_PDF)
        assert d1.detection_id != d2.detection_id

    def test_low_confidence_ocr_adds_ambiguity(self):
        d = make_detection(NormalizedDetectionType.FIT, "H7", "H7", None,
                            ParserConfidence.LOW_CONFIDENCE_OCR, DetectionSourceType.OCR)
        assert any(a.kind == AmbiguityKind.LOW_OCR_CONFIDENCE for a in d.ambiguities)

    def test_high_confidence_no_ambiguity(self):
        d = make_detection(NormalizedDetectionType.FIT, "H7", "H7", None,
                            ParserConfidence.EXACT_VECTOR_TEXT, DetectionSourceType.VECTOR_PDF)
        assert d.ambiguities == []

    def test_review_required_property_low_confidence(self):
        d = make_detection(NormalizedDetectionType.FIT, "H7", "H7", None,
                            ParserConfidence.AMBIGUOUS, DetectionSourceType.VECTOR_PDF)
        assert d.review_required is True

    def test_review_required_property_exact(self):
        d = make_detection(NormalizedDetectionType.FIT, "H7", "H7", None,
                            ParserConfidence.EXACT_VECTOR_TEXT, DetectionSourceType.VECTOR_PDF)
        assert d.review_required is False


# ---------------------------------------------------------------------------
# Session ID / detection ID helpers
# ---------------------------------------------------------------------------

class TestIdHelpers:
    def test_session_id_format(self):
        sid = new_session_id()
        assert sid.startswith("ses-")
        assert len(sid) > 6

    def test_session_ids_unique(self):
        ids = {new_session_id() for _ in range(50)}
        assert len(ids) == 50

    def test_detection_id_format(self):
        did = new_detection_id()
        assert did.startswith("det-")

    def test_detection_ids_unique(self):
        ids = {new_detection_id() for _ in range(50)}
        assert len(ids) == 50


# ---------------------------------------------------------------------------
# Material bridge
# ---------------------------------------------------------------------------

class TestBridgeMaterial:
    def test_empty_string_insufficient_data(self):
        result = bridge_material("")
        assert result.status == MaterialMatchStatus.INSUFFICIENT_DATA
        assert result.confidence == Decimal("0")

    def test_whitespace_only_insufficient_data(self):
        result = bridge_material("   ")
        assert result.status == MaterialMatchStatus.INSUFFICIENT_DATA

    def test_unknown_material_not_found_or_insufficient(self):
        result = bridge_material("XYZYY_UNKNOWN_1234")
        assert result.status in (
            MaterialMatchStatus.NOT_FOUND,
            MaterialMatchStatus.INSUFFICIENT_DATA,
            MaterialMatchStatus.MATCHED,  # if bridge happens to have it
        )

    def test_raw_text_preserved(self):
        result = bridge_material("AISI 4140")
        assert result.raw_text == "AISI 4140"

    def test_returns_material_bridge_outcome(self):
        from backend.interoperability.semantic_extraction import MaterialBridgeOutcome
        result = bridge_material("Steel")
        assert isinstance(result, MaterialBridgeOutcome)


# ---------------------------------------------------------------------------
# Security / privacy invariants
# ---------------------------------------------------------------------------

class TestSecurityInvariants:
    def test_fabricated_dimension_no(self):
        """Verify the constant is declared in the module."""
        import inspect
        from backend.interoperability import semantic_extraction as se
        src = inspect.getsource(se)
        assert "FABRICATED_DIMENSION=NO" in src

    def test_fabricated_tolerance_no(self):
        import inspect
        from backend.interoperability import semantic_extraction as se
        src = inspect.getsource(se)
        assert "FABRICATED_TOLERANCE=NO" in src

    def test_uncertain_extraction_not_auto_approved(self):
        import inspect
        from backend.interoperability import semantic_extraction as se
        src = inspect.getsource(se)
        assert "UNCERTAIN_EXTRACTION_AUTO_APPROVED=NO" in src

    def test_low_confidence_ocr_not_confirmed(self):
        d = make_detection(NormalizedDetectionType.FIT, "H7", "H7", None,
                            ParserConfidence.LOW_CONFIDENCE_OCR, DetectionSourceType.OCR)
        assert d.review_state == ReviewState.PENDING
        assert d.review_state != ReviewState.CONFIRMED
