"""
tests/unit/interoperability/test_drawing.py
===========================================
Phase 1A — Canonical Technical Drawing Model & Ingestion Contract
MachiningPro AI

Tests for:
- DrawingSourceLocation construction and validation
- DrawingTolerance construction and fail-closed rules
- DrawingDatumReference
- DrawingGdtReference
- DrawingDimension (Decimal safety, unit safety)
- DrawingSurfaceFinish
- DrawingNote, DrawingMaterialNote, DrawingHeatTreatmentNote
- DrawingRevision
- DrawingTitleBlock validation
- DrawingView
- DrawingSheet validation
- CanonicalDrawing construction, immutability, duplicate datum detection
- DrawingIngestionDiagnostics
- DrawingIngestionResult fail-closed rules
- DrawingParser ABC contract (concrete stub)
- Partial ingestion result
- Unsupported / failed result carry no document
- VALID result must carry a document
"""

from __future__ import annotations

import os
import sys
from dataclasses import FrozenInstanceError, asdict
from decimal import Decimal

import pytest

# Allow import from the source tree when running from repo root:
# py -m pytest tests/unit/interoperability/test_drawing.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from backend.interoperability.drawing import (
    CanonicalDrawing,
    DrawingBoundingBox,
    DrawingDatumReference,
    DrawingDimension,
    DrawingDimensionType,
    DrawingExtractionAuthority,
    DrawingFeatureControlFrame,
    DrawingGdtCell,
    DrawingGdtCellRole,
    DrawingGdtCharacteristic,
    DrawingGdtReference,
    DrawingHeatTreatmentNote,
    DrawingIngestionDiagnostics,
    DrawingIngestionResult,
    DrawingIngestionStatus,
    DrawingMaterialNote,
    DrawingNote,
    DrawingNoteCategory,
    DrawingOcrEvidenceKind,
    DrawingOcrTextEvidence,
    DrawingParser,
    DrawingParserIdentity,
    DrawingRasterSource,
    DrawingRevision,
    DrawingSheet,
    DrawingSourceLocation,
    DrawingSurfaceFinish,
    DrawingTitleBlock,
    DrawingTolerance,
    DrawingToleranceType,
    DrawingView,
    DrawingViewType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _loc(sheet: int = 1) -> DrawingSourceLocation:
    """Minimal valid DrawingSourceLocation."""
    return DrawingSourceLocation(
        source_id="upload::part4711.pdf",
        sheet_number=sheet,
        adapter_id="test-adapter",
        adapter_version="0.1.0",
    )


def _minimal_drawing(drawing_id: str = "DRW-001") -> CanonicalDrawing:
    """Minimal valid CanonicalDrawing."""
    return CanonicalDrawing(
        drawing_id=drawing_id,
        source_id="upload::part4711.pdf",
        source_location=_loc(),
    )


def _valid_result(drawing: CanonicalDrawing | None = None) -> DrawingIngestionResult:
    if drawing is None:
        drawing = _minimal_drawing()
    return DrawingIngestionResult(
        source_id="upload::part4711.pdf",
        diagnostics=DrawingIngestionDiagnostics(
            status=DrawingIngestionStatus.VALID,
            format_detected="PDF",
            parser_id="test-adapter",
            parser_version="0.1.0",
        ),
        document=drawing,
    )


# ---------------------------------------------------------------------------
# DrawingBoundingBox
# ---------------------------------------------------------------------------

class TestDrawingBoundingBox:

    def test_valid_pdf_point_box(self):
        box = DrawingBoundingBox(
            x0=Decimal("10.25"),
            top=Decimal("20.5"),
            x1=Decimal("110.75"),
            bottom=Decimal("220.125"),
        )

        assert box == DrawingBoundingBox(
            x0=Decimal("10.25"),
            top=Decimal("20.5"),
            x1=Decimal("110.75"),
            bottom=Decimal("220.125"),
            unit="pt",
        )
        assert box.unit == "pt"

    @pytest.mark.parametrize("field_name", ("x0", "top", "x1", "bottom"))
    def test_non_decimal_coordinate_rejected(self, field_name):
        coordinates = {
            "x0": Decimal("10"),
            "top": Decimal("20"),
            "x1": Decimal("30"),
            "bottom": Decimal("40"),
        }
        coordinates[field_name] = 10

        with pytest.raises(TypeError, match=field_name):
            DrawingBoundingBox(**coordinates)

    @pytest.mark.parametrize("invalid_value", ("NaN", "Infinity", "-Infinity"))
    def test_non_finite_coordinate_rejected(self, invalid_value):
        with pytest.raises(ValueError, match="finite"):
            DrawingBoundingBox(
                x0=Decimal(invalid_value),
                top=Decimal("20"),
                x1=Decimal("30"),
                bottom=Decimal("40"),
            )

    @pytest.mark.parametrize(
        ("coordinates", "message"),
        (
            (
                {
                    "x0": Decimal("31"),
                    "top": Decimal("20"),
                    "x1": Decimal("30"),
                    "bottom": Decimal("40"),
                },
                "x0",
            ),
            (
                {
                    "x0": Decimal("10"),
                    "top": Decimal("41"),
                    "x1": Decimal("30"),
                    "bottom": Decimal("40"),
                },
                "top",
            ),
        ),
    )
    def test_inverted_coordinate_range_rejected(self, coordinates, message):
        with pytest.raises(ValueError, match=message):
            DrawingBoundingBox(**coordinates)

    def test_non_point_unit_rejected(self):
        with pytest.raises(ValueError, match="unit"):
            DrawingBoundingBox(
                x0=Decimal("10"),
                top=Decimal("20"),
                x1=Decimal("30"),
                bottom=Decimal("40"),
                unit="mm",
            )

    def test_box_is_immutable(self):
        box = DrawingBoundingBox(
            x0=Decimal("10"),
            top=Decimal("20"),
            x1=Decimal("30"),
            bottom=Decimal("40"),
        )

        with pytest.raises(FrozenInstanceError):
            box.x0 = Decimal("0")  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DrawingSourceLocation
# ---------------------------------------------------------------------------

class TestDrawingSourceLocation:

    def test_minimal_construction(self):
        loc = DrawingSourceLocation(source_id="upload::test.pdf")
        assert loc.source_id == "upload::test.pdf"
        assert loc.sheet_number is None
        assert loc.confidence is None
        assert loc.authority is DrawingExtractionAuthority.EXTRACTED
        assert loc.bounding_box is None
        assert loc.source_object_ids == ()

    def test_full_construction(self):
        loc = DrawingSourceLocation(
            source_id="upload::test.pdf",
            sheet_number=2,
            page_number=2,
            view_id="v-001",
            original_text="Ø25.0",
            adapter_id="pdf-adapter",
            adapter_version="1.0.0",
            confidence=Decimal("0.92"),
            authority=DrawingExtractionAuthority.DECLARED,
        )
        assert loc.sheet_number == 2
        assert loc.confidence == Decimal("0.92")
        assert loc.authority is DrawingExtractionAuthority.DECLARED

    def test_blank_source_id_rejected(self):
        with pytest.raises(ValueError, match="source_id"):
            DrawingSourceLocation(source_id="")

    def test_whitespace_source_id_rejected(self):
        with pytest.raises(ValueError, match="source_id"):
            DrawingSourceLocation(source_id="   ")

    def test_sheet_number_zero_rejected(self):
        with pytest.raises(ValueError, match="sheet_number"):
            DrawingSourceLocation(source_id="upload::x.pdf", sheet_number=0)

    def test_sheet_number_negative_rejected(self):
        with pytest.raises(ValueError, match="sheet_number"):
            DrawingSourceLocation(source_id="upload::x.pdf", sheet_number=-1)

    def test_page_number_zero_rejected(self):
        with pytest.raises(ValueError, match="page_number"):
            DrawingSourceLocation(source_id="upload::x.pdf", page_number=0)

    def test_confidence_out_of_range_high(self):
        with pytest.raises(ValueError, match="confidence"):
            DrawingSourceLocation(source_id="s", confidence=Decimal("1.1"))

    def test_confidence_out_of_range_low(self):
        with pytest.raises(ValueError, match="confidence"):
            DrawingSourceLocation(source_id="s", confidence=Decimal("-0.1"))

    def test_confidence_boundary_zero(self):
        loc = DrawingSourceLocation(source_id="s", confidence=Decimal("0"))
        assert loc.confidence == Decimal("0")

    def test_confidence_boundary_one(self):
        loc = DrawingSourceLocation(source_id="s", confidence=Decimal("1"))
        assert loc.confidence == Decimal("1")

    @pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
    def test_confidence_rejects_non_finite_values(self, value):
        with pytest.raises(ValueError, match="confidence"):
            DrawingSourceLocation(source_id="s", confidence=value)

    def test_immutability(self):
        loc = DrawingSourceLocation(source_id="upload::test.pdf")
        with pytest.raises((AttributeError, TypeError)):
            loc.source_id = "other"  # type: ignore[misc]

    def test_equality(self):
        loc1 = DrawingSourceLocation(source_id="upload::a.pdf", sheet_number=1)
        loc2 = DrawingSourceLocation(source_id="upload::a.pdf", sheet_number=1)
        assert loc1 == loc2

    def test_inequality(self):
        loc1 = DrawingSourceLocation(source_id="upload::a.pdf", sheet_number=1)
        loc2 = DrawingSourceLocation(source_id="upload::b.pdf", sheet_number=1)
        assert loc1 != loc2

    def test_spatial_and_object_provenance_retained(self):
        box = DrawingBoundingBox(
            x0=Decimal("10.25"),
            top=Decimal("20.5"),
            x1=Decimal("110.75"),
            bottom=Decimal("220.125"),
        )

        loc = DrawingSourceLocation(
            source_id="upload::test.pdf",
            sheet_number=2,
            page_number=3,
            bounding_box=box,
            source_object_ids=("pdf-p0003-text-a1-0001", "pdf-p0003-line-b2-0001"),
        )

        assert loc.page_number == 3
        assert loc.bounding_box is box
        assert loc.source_object_ids == (
            "pdf-p0003-text-a1-0001",
            "pdf-p0003-line-b2-0001",
        )

    def test_raw_bounding_box_mapping_rejected(self):
        with pytest.raises(TypeError, match="bounding_box"):
            DrawingSourceLocation(
                source_id="upload::test.pdf",
                bounding_box={
                    "x0": "10",
                    "top": "20",
                    "x1": "30",
                    "bottom": "40",
                },  # type: ignore[arg-type]
            )

    def test_mutable_source_object_ids_rejected(self):
        with pytest.raises(TypeError, match="source_object_ids"):
            DrawingSourceLocation(
                source_id="upload::test.pdf",
                source_object_ids=["pdf-p0001-text-a1-0001"],  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize(
        ("source_object_ids", "error_type"),
        (
            (("",), ValueError),
            (("   ",), ValueError),
            (("object-1", "object-1"), ValueError),
            (("object-1", 2), TypeError),
        ),
    )
    def test_malformed_source_object_ids_rejected(self, source_object_ids, error_type):
        with pytest.raises(error_type, match="source_object_ids"):
            DrawingSourceLocation(
                source_id="upload::test.pdf",
                source_object_ids=source_object_ids,
            )

    def test_spatial_provenance_serializes_deterministically(self):
        loc = DrawingSourceLocation(
            source_id="upload::test.pdf",
            sheet_number=2,
            page_number=3,
            bounding_box=DrawingBoundingBox(
                x0=Decimal("10.25"),
                top=Decimal("20.5"),
                x1=Decimal("110.75"),
                bottom=Decimal("220.125"),
            ),
            source_object_ids=("text-1", "line-1"),
        )

        assert asdict(loc) == {
            "source_id": "upload::test.pdf",
            "sheet_number": 2,
            "page_number": 3,
            "view_id": None,
            "original_text": None,
            "adapter_id": None,
            "adapter_version": None,
            "confidence": None,
            "authority": DrawingExtractionAuthority.EXTRACTED,
            "bounding_box": {
                "x0": Decimal("10.25"),
                "top": Decimal("20.5"),
                "x1": Decimal("110.75"),
                "bottom": Decimal("220.125"),
                "unit": "pt",
            },
            "source_object_ids": ("text-1", "line-1"),
        }


# ---------------------------------------------------------------------------
# DrawingTolerance
# ---------------------------------------------------------------------------

class TestDrawingTolerance:

    def test_symmetric_construction(self):
        t = DrawingTolerance(
            tolerance_id="tol-001",
            tolerance_type=DrawingToleranceType.SYMMETRIC,
            unit="mm",
            upper_value=Decimal("0.05"),
            lower_value=Decimal("-0.05"),
        )
        assert t.upper_value == Decimal("0.05")

    def test_asymmetric_construction(self):
        t = DrawingTolerance(
            tolerance_id="tol-002",
            tolerance_type=DrawingToleranceType.ASYMMETRIC,
            unit="mm",
            upper_value=Decimal("0.1"),
            lower_value=Decimal("-0.02"),
        )
        assert t.lower_value == Decimal("-0.02")

    def test_blank_id_rejected(self):
        with pytest.raises(ValueError, match="tolerance_id"):
            DrawingTolerance(
                tolerance_id="",
                tolerance_type=DrawingToleranceType.SYMMETRIC,
                unit="mm",
            )

    def test_blank_unit_rejected(self):
        with pytest.raises(ValueError, match="unit"):
            DrawingTolerance(
                tolerance_id="t1",
                tolerance_type=DrawingToleranceType.SYMMETRIC,
                unit="",
            )

    def test_float_upper_value_rejected(self):
        with pytest.raises(TypeError, match="Decimal"):
            DrawingTolerance(
                tolerance_id="t1",
                tolerance_type=DrawingToleranceType.SYMMETRIC,
                unit="mm",
                upper_value=0.05,  # type: ignore[arg-type]
            )

    def test_float_lower_value_rejected(self):
        with pytest.raises(TypeError, match="Decimal"):
            DrawingTolerance(
                tolerance_id="t1",
                tolerance_type=DrawingToleranceType.SYMMETRIC,
                unit="mm",
                lower_value=-0.05,  # type: ignore[arg-type]
            )

    def test_symmetric_magnitude_mismatch_rejected(self):
        with pytest.raises(ValueError, match="SYMMETRIC"):
            DrawingTolerance(
                tolerance_id="t1",
                tolerance_type=DrawingToleranceType.SYMMETRIC,
                unit="mm",
                upper_value=Decimal("0.05"),
                lower_value=Decimal("-0.03"),
            )

    def test_immutability(self):
        t = DrawingTolerance(
            tolerance_id="t1",
            tolerance_type=DrawingToleranceType.UNKNOWN,
            unit="mm",
        )
        with pytest.raises((AttributeError, TypeError)):
            t.unit = "inch"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DrawingDatumReference
# ---------------------------------------------------------------------------

class TestDrawingDatumReference:

    def test_construction(self):
        d = DrawingDatumReference(datum_label="A")
        assert d.datum_label == "A"
        assert d.referenced_entity_id is None

    def test_blank_label_rejected(self):
        with pytest.raises(ValueError, match="datum_label"):
            DrawingDatumReference(datum_label="")

    def test_whitespace_label_rejected(self):
        with pytest.raises(ValueError, match="datum_label"):
            DrawingDatumReference(datum_label="   ")

    def test_with_entity_ref(self):
        d = DrawingDatumReference(
            datum_label="B",
            referenced_entity_id="face-0042",
        )
        assert d.referenced_entity_id == "face-0042"

    def test_immutability(self):
        d = DrawingDatumReference(datum_label="C")
        with pytest.raises((AttributeError, TypeError)):
            d.datum_label = "D"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DrawingGdtReference
# ---------------------------------------------------------------------------

class TestDrawingGdtReference:

    def test_minimal_construction(self):
        g = DrawingGdtReference(gdt_id="gdt-001")
        assert g.gdt_id == "gdt-001"
        assert g.tolerance_value is None

    def test_full_construction(self):
        datum_a = DrawingDatumReference(datum_label="A")
        g = DrawingGdtReference(
            gdt_id="gdt-002",
            symbol_type="cylindricity",
            tolerance_value=Decimal("0.02"),
            tolerance_unit="mm",
            datum_references=(datum_a,),
        )
        assert g.tolerance_value == Decimal("0.02")
        assert len(g.datum_references) == 1

    def test_blank_id_rejected(self):
        with pytest.raises(ValueError, match="gdt_id"):
            DrawingGdtReference(gdt_id="")

    def test_float_tolerance_rejected(self):
        with pytest.raises(TypeError, match="Decimal"):
            DrawingGdtReference(
                gdt_id="g1",
                tolerance_value=0.02,  # type: ignore[arg-type]
            )

    def test_tolerance_value_without_unit_rejected(self):
        with pytest.raises(ValueError, match="tolerance_unit"):
            DrawingGdtReference(
                gdt_id="g1",
                tolerance_value=Decimal("0.02"),
                tolerance_unit=None,
            )

    def test_tolerance_unit_without_value_is_ok(self):
        # unit without value is allowed (might be partially extracted)
        g = DrawingGdtReference(gdt_id="g1", tolerance_unit="mm")
        assert g.tolerance_unit == "mm"


# ---------------------------------------------------------------------------
# Phase 1C typed OCR/raster/GD&T evidence
# ---------------------------------------------------------------------------

def _phase_1c_box() -> DrawingBoundingBox:
    return DrawingBoundingBox(
        x0=Decimal("10"), top=Decimal("20"),
        x1=Decimal("110"), bottom=Decimal("40"),
    )


def _phase_1c_location(*source_ids: str) -> DrawingSourceLocation:
    return DrawingSourceLocation(
        source_id="upload::phase1c.pdf",
        page_number=1,
        adapter_id="pdf-ocr",
        adapter_version="1.0",
        confidence=Decimal("0.95"),
        bounding_box=_phase_1c_box(),
        source_object_ids=source_ids,
    )


def _phase_1c_parser() -> DrawingParserIdentity:
    return DrawingParserIdentity(
        parser_id="ocr-drawing",
        parser_version="1.0",
        preprocessing_id="ocr-preprocess-v1",
    )


class TestPhase1CTypedEvidence:

    def test_raster_source_and_ocr_provenance_are_frozen_and_retained(self):
        raster = DrawingRasterSource(
            source_id="upload::phase1c.pdf",
            page_number=1,
            image_object_id="page-1:image-1",
            bounding_box=_phase_1c_box(),
            image_format="png",
            parser_identity=_phase_1c_parser(),
        )
        evidence = DrawingOcrTextEvidence(
            evidence_id="page-1:image-1:word-1",
            text="25.0",
            evidence_kind=DrawingOcrEvidenceKind.WORD,
            confidence=Decimal("0.95"),
            raster_source=raster,
            source_location=_phase_1c_location("page-1:image-1", "page-1:image-1:word-1"),
            parser_identity=_phase_1c_parser(),
        )

        assert evidence.raster_source.image_object_id == "page-1:image-1"
        assert evidence.source_location.bounding_box == _phase_1c_box()
        assert evidence.parser_identity.preprocessing_id == "ocr-preprocess-v1"
        with pytest.raises(FrozenInstanceError):
            evidence.text = "changed"  # type: ignore[misc]
        serialized = asdict(evidence)
        assert "raw_bytes" not in serialized
        assert "path" not in repr(serialized).lower()

    def test_raster_source_rejects_invalid_page_and_box(self):
        with pytest.raises(ValueError, match="page_number"):
            DrawingRasterSource(
                source_id="s", page_number=0, image_object_id="img",
                bounding_box=_phase_1c_box(), parser_identity=_phase_1c_parser(),
            )
        with pytest.raises(TypeError, match="DrawingBoundingBox"):
            DrawingRasterSource(
                source_id="s", page_number=1, image_object_id="img",
                bounding_box="box", parser_identity=_phase_1c_parser(),  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize(
        "value",
        [Decimal("-0.01"), Decimal("1.01"), Decimal("NaN"), Decimal("Infinity")],
    )
    def test_ocr_confidence_rejects_invalid_values(self, value):
        raster = DrawingRasterSource(
            source_id="s", page_number=1, image_object_id="img",
            bounding_box=_phase_1c_box(), parser_identity=_phase_1c_parser(),
        )
        with pytest.raises(ValueError, match="confidence"):
            DrawingOcrTextEvidence(
                evidence_id="word-1", text="A",
                evidence_kind=DrawingOcrEvidenceKind.WORD,
                confidence=value, raster_source=raster,
                source_location=_phase_1c_location("img"),
                parser_identity=_phase_1c_parser(),
            )

    def test_gdt_frame_construction_is_deterministic_and_typed(self):
        cell = DrawingGdtCell(
            cell_index=0,
            role=DrawingGdtCellRole.CHARACTERISTIC,
            normalized_text="flatness",
            confidence=Decimal("0.95"),
            source_location=_phase_1c_location("frame-1:cell-0"),
            parser_identity=_phase_1c_parser(),
        )
        frame = DrawingFeatureControlFrame(
            frame_id="frame-1",
            cells=(cell,),
            characteristic=DrawingGdtCharacteristic.FLATNESS,
            tolerance_value=Decimal("0.10"),
            tolerance_unit="mm",
            datum_references=(
                DrawingDatumReference(
                    "A", source_location=_phase_1c_location("datum-A")
                ),
            ),
            source_location=_phase_1c_location("frame-1"),
            parser_identity=_phase_1c_parser(),
            confidence=Decimal("0.95"),
        )
        equivalent = DrawingFeatureControlFrame(
            frame_id="frame-1",
            cells=(cell,),
            characteristic=DrawingGdtCharacteristic.FLATNESS,
            tolerance_value=Decimal("0.10"), tolerance_unit="mm",
            datum_references=(
                DrawingDatumReference(
                    "A", source_location=_phase_1c_location("datum-A")
                ),
            ),
            source_location=_phase_1c_location("frame-1"),
            parser_identity=_phase_1c_parser(), confidence=Decimal("0.95"),
        )
        assert frame == equivalent
        assert asdict(frame) == asdict(equivalent)
        assert frame.modifier.value == "NONE"

    def test_gdt_frame_rejects_malformed_cells_and_datum_labels(self):
        cell = DrawingGdtCell(
            cell_index=1, role=DrawingGdtCellRole.UNKNOWN, normalized_text="x",
            confidence=Decimal("0.9"), source_location=_phase_1c_location("c"),
            parser_identity=_phase_1c_parser(),
        )
        with pytest.raises(ValueError, match="cell_index"):
            DrawingFeatureControlFrame(
                frame_id="frame", cells=(cell,), source_location=_phase_1c_location("f"),
                parser_identity=_phase_1c_parser(), confidence=Decimal("0.9"),
            )
        valid_cell = DrawingGdtCell(
            cell_index=0, role=DrawingGdtCellRole.DATUM, normalized_text="A",
            confidence=Decimal("0.9"), source_location=_phase_1c_location("c"),
            parser_identity=_phase_1c_parser(),
        )
        with pytest.raises(ValueError, match="datum"):
            DrawingFeatureControlFrame(
                frame_id="frame", cells=(valid_cell,),
                datum_references=(DrawingDatumReference("A1"),),
                source_location=_phase_1c_location("f"),
                parser_identity=_phase_1c_parser(), confidence=Decimal("0.9"),
            )


# ---------------------------------------------------------------------------
# DrawingDimension
# ---------------------------------------------------------------------------

class TestDrawingDimension:

    def test_construction(self):
        dim = DrawingDimension(
            dimension_id="dim-001",
            nominal_value=Decimal("25.0"),
            unit="mm",
            dimension_type=DrawingDimensionType.DIAMETRAL,
        )
        assert dim.nominal_value == Decimal("25.0")
        assert dim.dimension_type is DrawingDimensionType.DIAMETRAL

    def test_blank_id_rejected(self):
        with pytest.raises(ValueError, match="dimension_id"):
            DrawingDimension(dimension_id="", nominal_value=Decimal("10"), unit="mm")

    def test_float_nominal_rejected(self):
        with pytest.raises(TypeError, match="Decimal"):
            DrawingDimension(
                dimension_id="d1",
                nominal_value=25.0,  # type: ignore[arg-type]
                unit="mm",
            )

    def test_blank_unit_rejected(self):
        with pytest.raises(ValueError, match="unit"):
            DrawingDimension(dimension_id="d1", nominal_value=Decimal("10"), unit="")

    def test_with_tolerance(self):
        tol = DrawingTolerance(
            tolerance_id="t1",
            tolerance_type=DrawingToleranceType.SYMMETRIC,
            unit="mm",
            upper_value=Decimal("0.05"),
            lower_value=Decimal("-0.05"),
        )
        dim = DrawingDimension(
            dimension_id="d1",
            nominal_value=Decimal("50"),
            unit="mm",
            tolerance=tol,
        )
        assert dim.tolerance is not None
        assert dim.tolerance.tolerance_id == "t1"

    def test_immutability(self):
        dim = DrawingDimension(
            dimension_id="d1", nominal_value=Decimal("10"), unit="mm"
        )
        with pytest.raises((AttributeError, TypeError)):
            dim.unit = "inch"  # type: ignore[misc]

    def test_with_entity_refs(self):
        dim = DrawingDimension(
            dimension_id="d1",
            nominal_value=Decimal("20"),
            unit="mm",
            referenced_entity_ids=("face-001", "face-002"),
        )
        assert len(dim.referenced_entity_ids) == 2


# ---------------------------------------------------------------------------
# DrawingSurfaceFinish
# ---------------------------------------------------------------------------

class TestDrawingSurfaceFinish:

    def test_minimal_construction(self):
        sf = DrawingSurfaceFinish(finish_id="sf-001")
        assert sf.finish_id == "sf-001"
        assert sf.value is None

    def test_full_construction(self):
        sf = DrawingSurfaceFinish(
            finish_id="sf-002",
            parameter="Ra",
            value=Decimal("1.6"),
            unit="µm",
            referenced_entity_ids=("face-003",),
            raw_text="Ra 1.6",
        )
        assert sf.value == Decimal("1.6")
        assert sf.unit == "µm"

    def test_blank_id_rejected(self):
        with pytest.raises(ValueError, match="finish_id"):
            DrawingSurfaceFinish(finish_id="")

    def test_float_value_rejected(self):
        with pytest.raises(TypeError, match="Decimal"):
            DrawingSurfaceFinish(
                finish_id="sf1",
                value=1.6,  # type: ignore[arg-type]
            )

    def test_value_without_unit_rejected(self):
        with pytest.raises(ValueError, match="unit"):
            DrawingSurfaceFinish(
                finish_id="sf1",
                value=Decimal("1.6"),
                unit=None,
            )

    def test_unit_without_value_allowed(self):
        sf = DrawingSurfaceFinish(finish_id="sf1", unit="µm")
        assert sf.unit == "µm"
        assert sf.value is None


# ---------------------------------------------------------------------------
# DrawingNote / DrawingMaterialNote / DrawingHeatTreatmentNote
# ---------------------------------------------------------------------------

class TestDrawingNote:

    def test_construction(self):
        n = DrawingNote(note_id="n-001", raw_text="GENERAL TOLERANCE ISO 2768-m")
        assert n.category is DrawingNoteCategory.UNKNOWN

    def test_material_category(self):
        n = DrawingNote(
            note_id="n-002",
            raw_text="EN 10083-2 42CrMo4",
            category=DrawingNoteCategory.MATERIAL,
        )
        assert n.category is DrawingNoteCategory.MATERIAL

    def test_blank_id_rejected(self):
        with pytest.raises(ValueError, match="note_id"):
            DrawingNote(note_id="", raw_text="some text")

    def test_blank_text_rejected(self):
        with pytest.raises(ValueError, match="raw_text"):
            DrawingNote(note_id="n1", raw_text="")

    def test_whitespace_text_rejected(self):
        with pytest.raises(ValueError, match="raw_text"):
            DrawingNote(note_id="n1", raw_text="   ")


class TestDrawingMaterialNote:

    def test_construction(self):
        m = DrawingMaterialNote(note_id="mn-001", raw_text="St 52-3")
        assert m.normalized_identifier is None

    def test_with_normalized_id(self):
        m = DrawingMaterialNote(
            note_id="mn-002",
            raw_text="42CrMo4",
            normalized_identifier="EN 10083-2 42CrMo4",
        )
        assert m.normalized_identifier == "EN 10083-2 42CrMo4"

    def test_blank_raw_text_rejected(self):
        with pytest.raises(ValueError, match="raw_text"):
            DrawingMaterialNote(note_id="mn1", raw_text="")


class TestDrawingHeatTreatmentNote:

    def test_construction(self):
        h = DrawingHeatTreatmentNote(note_id="ht-001", raw_text="HRC 55-60")
        assert h.raw_text == "HRC 55-60"

    def test_blank_text_rejected(self):
        with pytest.raises(ValueError, match="raw_text"):
            DrawingHeatTreatmentNote(note_id="ht1", raw_text="")


# ---------------------------------------------------------------------------
# DrawingRevision
# ---------------------------------------------------------------------------

class TestDrawingRevision:

    def test_construction(self):
        r = DrawingRevision(revision_code="A")
        assert r.revision_code == "A"
        assert r.author is None

    def test_full_construction(self):
        r = DrawingRevision(
            revision_code="B",
            description="Updated tolerances",
            date_text="2026-09-01",
            author="J. Smith",
            approver="M. Müller",
        )
        assert r.approver == "M. Müller"

    def test_blank_code_rejected(self):
        with pytest.raises(ValueError, match="revision_code"):
            DrawingRevision(revision_code="")

    def test_whitespace_code_rejected(self):
        with pytest.raises(ValueError, match="revision_code"):
            DrawingRevision(revision_code="   ")

    def test_immutability(self):
        r = DrawingRevision(revision_code="A")
        with pytest.raises((AttributeError, TypeError)):
            r.revision_code = "B"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DrawingTitleBlock
# ---------------------------------------------------------------------------

class TestDrawingTitleBlock:

    def test_minimal_construction(self):
        tb = DrawingTitleBlock()
        assert tb.drawing_number is None

    def test_full_construction(self):
        rev = DrawingRevision(revision_code="C")
        tb = DrawingTitleBlock(
            drawing_number="DWG-4711",
            part_number="P-4711",
            part_name="Flansch",
            material_raw="42CrMo4",
            scale="1:1",
            sheet_number=1,
            sheet_count=3,
            revision=rev,
            author="A. Engineer",
        )
        assert tb.drawing_number == "DWG-4711"
        assert tb.sheet_count == 3

    def test_sheet_number_exceeds_count_rejected(self):
        with pytest.raises(ValueError, match="sheet_number"):
            DrawingTitleBlock(sheet_number=5, sheet_count=3)

    def test_sheet_number_zero_rejected(self):
        with pytest.raises(ValueError, match="sheet_number"):
            DrawingTitleBlock(sheet_number=0, sheet_count=1)

    def test_sheet_count_zero_rejected(self):
        with pytest.raises(ValueError, match="sheet_count"):
            DrawingTitleBlock(sheet_number=1, sheet_count=0)

    def test_partial_sheet_info_allowed(self):
        # sheet_number without sheet_count is PARTIAL — allowed
        tb = DrawingTitleBlock(sheet_number=1)
        assert tb.sheet_number == 1
        assert tb.sheet_count is None

    def test_immutability(self):
        tb = DrawingTitleBlock()
        with pytest.raises((AttributeError, TypeError)):
            tb.drawing_number = "X"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DrawingView
# ---------------------------------------------------------------------------

class TestDrawingView:

    def test_minimal_construction(self):
        v = DrawingView(view_id="v-001")
        assert v.view_type is DrawingViewType.UNKNOWN
        assert len(v.dimensions) == 0

    def test_with_content(self):
        dim = DrawingDimension(
            dimension_id="d1", nominal_value=Decimal("30"), unit="mm"
        )
        v = DrawingView(
            view_id="v-front",
            view_type=DrawingViewType.FRONT,
            name="FRONT VIEW",
            scale="1:1",
            dimensions=(dim,),
        )
        assert v.view_type is DrawingViewType.FRONT
        assert len(v.dimensions) == 1

    def test_blank_id_rejected(self):
        with pytest.raises(ValueError, match="view_id"):
            DrawingView(view_id="")

    def test_immutability(self):
        v = DrawingView(view_id="v-001")
        with pytest.raises((AttributeError, TypeError)):
            v.view_id = "v-002"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DrawingSheet
# ---------------------------------------------------------------------------

class TestDrawingSheet:

    def test_minimal_construction(self):
        s = DrawingSheet(sheet_number=1)
        assert len(s.views) == 0

    def test_with_views(self):
        v = DrawingView(view_id="v-001", view_type=DrawingViewType.FRONT)
        s = DrawingSheet(
            sheet_number=1,
            sheet_count=2,
            size="A3",
            scale="1:2",
            views=(v,),
        )
        assert s.size == "A3"
        assert len(s.views) == 1

    def test_sheet_number_zero_rejected(self):
        with pytest.raises(ValueError, match="sheet_number"):
            DrawingSheet(sheet_number=0)

    def test_sheet_number_negative_rejected(self):
        with pytest.raises(ValueError, match="sheet_number"):
            DrawingSheet(sheet_number=-1)

    def test_sheet_number_exceeds_count_rejected(self):
        with pytest.raises(ValueError, match="sheet_number"):
            DrawingSheet(sheet_number=4, sheet_count=3)

    def test_sheet_count_zero_rejected(self):
        with pytest.raises(ValueError, match="sheet_count"):
            DrawingSheet(sheet_number=1, sheet_count=0)

    def test_immutability(self):
        s = DrawingSheet(sheet_number=1)
        with pytest.raises((AttributeError, TypeError)):
            s.sheet_number = 2  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CanonicalDrawing
# ---------------------------------------------------------------------------

class TestCanonicalDrawing:

    def test_minimal_construction(self):
        d = _minimal_drawing()
        assert d.drawing_id == "DRW-001"
        assert d.sheet_count == 0
        assert not d.has_title_block
        assert not d.has_revision

    def test_blank_drawing_id_rejected(self):
        with pytest.raises(ValueError, match="drawing_id"):
            CanonicalDrawing(drawing_id="", source_id="upload::x.pdf")

    def test_blank_source_id_rejected(self):
        with pytest.raises(ValueError, match="source_id"):
            CanonicalDrawing(drawing_id="D1", source_id="")

    def test_sheet_count_property(self):
        s1 = DrawingSheet(sheet_number=1, sheet_count=2)
        s2 = DrawingSheet(sheet_number=2, sheet_count=2)
        d = CanonicalDrawing(
            drawing_id="D1",
            source_id="upload::x.pdf",
            sheets=(s1, s2),
        )
        assert d.sheet_count == 2

    def test_has_title_block_true(self):
        tb = DrawingTitleBlock(drawing_number="DWG-001")
        d = CanonicalDrawing(
            drawing_id="D1",
            source_id="s1",
            title_block=tb,
        )
        assert d.has_title_block

    def test_has_revision_true(self):
        rev = DrawingRevision(revision_code="B")
        d = CanonicalDrawing(drawing_id="D1", source_id="s1", revision=rev)
        assert d.has_revision

    def test_duplicate_datum_labels_rejected(self):
        datum_a1 = DrawingDatumReference(datum_label="A")
        datum_a2 = DrawingDatumReference(datum_label="A")
        with pytest.raises(ValueError, match="duplicate datum label"):
            CanonicalDrawing(
                drawing_id="D1",
                source_id="s1",
                all_datum_references=(datum_a1, datum_a2),
            )

    def test_distinct_datum_labels_accepted(self):
        datum_a = DrawingDatumReference(datum_label="A")
        datum_b = DrawingDatumReference(datum_label="B")
        d = CanonicalDrawing(
            drawing_id="D1",
            source_id="s1",
            all_datum_references=(datum_a, datum_b),
        )
        assert len(d.all_datum_references) == 2

    def test_immutability(self):
        d = _minimal_drawing()
        with pytest.raises((AttributeError, TypeError)):
            d.drawing_id = "MODIFIED"  # type: ignore[misc]

    def test_equality_same(self):
        d1 = _minimal_drawing("D1")
        d2 = _minimal_drawing("D1")
        assert d1 == d2

    def test_equality_different_id(self):
        d1 = _minimal_drawing("D1")
        d2 = _minimal_drawing("D2")
        assert d1 != d2

    def test_full_drawing_construction(self):
        loc = _loc()
        dim = DrawingDimension(
            dimension_id="dim-001",
            nominal_value=Decimal("120"),
            unit="mm",
            source_location=loc,
        )
        tol = DrawingTolerance(
            tolerance_id="tol-001",
            tolerance_type=DrawingToleranceType.SYMMETRIC,
            unit="mm",
            upper_value=Decimal("0.1"),
            lower_value=Decimal("-0.1"),
        )
        datum_a = DrawingDatumReference(datum_label="A", source_location=loc)
        sf = DrawingSurfaceFinish(
            finish_id="sf-001",
            parameter="Ra",
            value=Decimal("1.6"),
            unit="µm",
        )
        mat = DrawingMaterialNote(note_id="mn-001", raw_text="42CrMo4")
        ht = DrawingHeatTreatmentNote(note_id="ht-001", raw_text="HRC 55-60")
        rev = DrawingRevision(revision_code="A", date_text="2026-09-01")
        tb = DrawingTitleBlock(
            drawing_number="DWG-4711",
            part_name="Flansch",
            material_raw="42CrMo4",
            revision=rev,
        )
        view = DrawingView(
            view_id="v-front",
            view_type=DrawingViewType.FRONT,
            dimensions=(dim,),
        )
        sheet = DrawingSheet(
            sheet_number=1,
            sheet_count=1,
            size="A3",
            views=(view,),
        )
        d = CanonicalDrawing(
            drawing_id="DWG-4711",
            source_id="upload::flansch.pdf",
            sheets=(sheet,),
            title_block=tb,
            revision=rev,
            material_notes=(mat,),
            heat_treatment_notes=(ht,),
            all_dimensions=(dim,),
            all_tolerances=(tol,),
            all_datum_references=(datum_a,),
            all_surface_finish=(sf,),
            metadata={"pdf_version": "1.4", "page_count": "1"},
            source_location=loc,
        )
        assert d.sheet_count == 1
        assert d.has_title_block
        assert d.has_revision
        assert len(d.all_dimensions) == 1
        assert len(d.material_notes) == 1


# ---------------------------------------------------------------------------
# DrawingIngestionDiagnostics
# ---------------------------------------------------------------------------

class TestDrawingIngestionDiagnostics:

    def test_valid_status(self):
        diag = DrawingIngestionDiagnostics(status=DrawingIngestionStatus.VALID)
        assert diag.status is DrawingIngestionStatus.VALID
        assert diag.sheet_count_parsed == 0

    def test_failed_with_errors(self):
        diag = DrawingIngestionDiagnostics(
            status=DrawingIngestionStatus.FAILED,
            errors=("File corrupt", "Unexpected EOF"),
        )
        assert len(diag.errors) == 2

    def test_partial_with_warnings(self):
        diag = DrawingIngestionDiagnostics(
            status=DrawingIngestionStatus.PARTIAL,
            warnings=("Title block not found",),
            sheet_count_expected=3,
            sheet_count_parsed=2,
        )
        assert diag.sheet_count_parsed == 2

    def test_immutability(self):
        diag = DrawingIngestionDiagnostics(status=DrawingIngestionStatus.VALID)
        with pytest.raises((AttributeError, TypeError)):
            diag.status = DrawingIngestionStatus.FAILED  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DrawingIngestionResult — fail-closed rules
# ---------------------------------------------------------------------------

class TestDrawingIngestionResult:

    def test_valid_with_document(self):
        result = _valid_result()
        assert result.succeeded
        assert not result.failed
        assert result.document is not None

    def test_partial_with_document(self):
        drawing = _minimal_drawing()
        result = DrawingIngestionResult(
            source_id="upload::x.pdf",
            diagnostics=DrawingIngestionDiagnostics(
                status=DrawingIngestionStatus.PARTIAL,
                warnings=("Title block missing",),
            ),
            document=drawing,
        )
        assert result.succeeded

    def test_partial_without_document_allowed(self):
        # PARTIAL can have no document if truly nothing was extractable
        result = DrawingIngestionResult(
            source_id="upload::x.pdf",
            diagnostics=DrawingIngestionDiagnostics(
                status=DrawingIngestionStatus.PARTIAL,
            ),
            document=None,
        )
        assert result.succeeded

    def test_failed_must_not_carry_document(self):
        drawing = _minimal_drawing()
        with pytest.raises(ValueError, match="FAILED"):
            DrawingIngestionResult(
                source_id="upload::x.pdf",
                diagnostics=DrawingIngestionDiagnostics(
                    status=DrawingIngestionStatus.FAILED,
                ),
                document=drawing,
            )

    def test_unsupported_must_not_carry_document(self):
        drawing = _minimal_drawing()
        with pytest.raises(ValueError, match="UNSUPPORTED"):
            DrawingIngestionResult(
                source_id="upload::x.pdf",
                diagnostics=DrawingIngestionDiagnostics(
                    status=DrawingIngestionStatus.UNSUPPORTED,
                ),
                document=drawing,
            )

    def test_insufficient_data_must_not_carry_document(self):
        drawing = _minimal_drawing()
        with pytest.raises(ValueError, match="INSUFFICIENT_DATA"):
            DrawingIngestionResult(
                source_id="upload::x.pdf",
                diagnostics=DrawingIngestionDiagnostics(
                    status=DrawingIngestionStatus.INSUFFICIENT_DATA,
                ),
                document=drawing,
            )

    def test_valid_must_carry_document(self):
        with pytest.raises(ValueError, match="VALID"):
            DrawingIngestionResult(
                source_id="upload::x.pdf",
                diagnostics=DrawingIngestionDiagnostics(
                    status=DrawingIngestionStatus.VALID,
                ),
                document=None,
            )

    def test_blank_source_id_rejected(self):
        with pytest.raises(ValueError, match="source_id"):
            DrawingIngestionResult(
                source_id="",
                diagnostics=DrawingIngestionDiagnostics(
                    status=DrawingIngestionStatus.FAILED,
                ),
            )

    def test_failed_result_properties(self):
        result = DrawingIngestionResult(
            source_id="upload::x.pdf",
            diagnostics=DrawingIngestionDiagnostics(
                status=DrawingIngestionStatus.FAILED,
                errors=("Corrupt file",),
            ),
        )
        assert result.failed
        assert not result.succeeded
        assert result.document is None

    def test_immutability(self):
        result = _valid_result()
        with pytest.raises((AttributeError, TypeError)):
            result.source_id = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DrawingParser ABC contract (concrete stub for contract testing)
# ---------------------------------------------------------------------------

class _StubDrawingParser(DrawingParser):
    """Minimal concrete implementation of DrawingParser for contract tests."""

    def parser_id(self) -> str:
        return "stub-parser"

    def parser_version(self) -> str:
        return "0.0.1"

    def supports(
        self,
        source_id: str,
        file_name: str,
        notes: str | None = None,
    ) -> bool:
        return file_name.lower().endswith(".stub")

    def parse(
        self,
        source_id: str,
        file_name: str,
        content: bytes,
        notes: str | None = None,
    ) -> DrawingIngestionResult:
        if not file_name.lower().endswith(".stub"):
            return DrawingIngestionResult(
                source_id=source_id,
                diagnostics=DrawingIngestionDiagnostics(
                    status=DrawingIngestionStatus.UNSUPPORTED,
                    format_detected=None,
                    parser_id=self.parser_id(),
                    parser_version=self.parser_version(),
                ),
            )
        drawing = CanonicalDrawing(
            drawing_id=f"stub::{file_name}",
            source_id=source_id,
        )
        return DrawingIngestionResult(
            source_id=source_id,
            diagnostics=DrawingIngestionDiagnostics(
                status=DrawingIngestionStatus.VALID,
                format_detected="STUB",
                parser_id=self.parser_id(),
                parser_version=self.parser_version(),
            ),
            document=drawing,
        )


class TestDrawingParserContract:

    def setup_method(self) -> None:
        self.parser = _StubDrawingParser()

    def test_parser_id_returns_string(self):
        assert isinstance(self.parser.parser_id(), str)
        assert len(self.parser.parser_id()) > 0

    def test_parser_version_returns_string(self):
        assert isinstance(self.parser.parser_version(), str)

    def test_supports_true_for_stub(self):
        assert self.parser.supports("upload::x.stub", "drawing.stub")

    def test_supports_false_for_pdf(self):
        assert not self.parser.supports("upload::x.pdf", "drawing.pdf")

    def test_parse_valid_stub_file(self):
        result = self.parser.parse(
            source_id="upload::drawing.stub",
            file_name="drawing.stub",
            content=b"stub content",
        )
        assert result.succeeded
        assert result.document is not None
        assert result.diagnostics.format_detected == "STUB"
        assert result.diagnostics.parser_id == "stub-parser"

    def test_parse_unsupported_file_returns_unsupported(self):
        result = self.parser.parse(
            source_id="upload::drawing.pdf",
            file_name="drawing.pdf",
            content=b"%PDF-1.4",
        )
        assert result.diagnostics.status is DrawingIngestionStatus.UNSUPPORTED
        assert result.document is None
        assert result.failed

    def test_parse_with_notes(self):
        result = self.parser.parse(
            source_id="upload::drawing.stub",
            file_name="drawing.stub",
            content=b"stub",
            notes="stub header hint",
        )
        assert result.succeeded

    def test_abc_cannot_be_instantiated_directly(self):
        with pytest.raises(TypeError):
            DrawingParser()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Provenance / source location integration
# ---------------------------------------------------------------------------

class TestProvenanceIntegration:
    """
    Verify that source location propagates correctly through composed models.
    """

    def test_dimension_carries_source_location(self):
        box = DrawingBoundingBox(
            x0=Decimal("120.25"),
            top=Decimal("80.5"),
            x1=Decimal("168.75"),
            bottom=Decimal("96.25"),
        )
        loc = DrawingSourceLocation(
            source_id="upload::part.pdf",
            sheet_number=2,
            page_number=2,
            view_id="v-top",
            original_text="Ø50 ±0.05",
            adapter_id="pdf-adapter",
            adapter_version="1.0.0",
            confidence=Decimal("0.95"),
            authority=DrawingExtractionAuthority.EXTRACTED,
            bounding_box=box,
            source_object_ids=("pdf-p0002-text-a1-0001", "pdf-p0002-line-b2-0001"),
        )
        dim = DrawingDimension(
            dimension_id="d-50",
            nominal_value=Decimal("50"),
            unit="mm",
            dimension_type=DrawingDimensionType.DIAMETRAL,
            source_location=loc,
        )
        assert dim.source_location is not None
        assert dim.source_location.source_id == "upload::part.pdf"
        assert dim.source_location.view_id == "v-top"
        assert dim.source_location.confidence == Decimal("0.95")
        assert dim.source_location.authority is DrawingExtractionAuthority.EXTRACTED
        assert dim.source_location.bounding_box is box
        assert dim.source_location.source_object_ids == (
            "pdf-p0002-text-a1-0001",
            "pdf-p0002-line-b2-0001",
        )

    def test_drawing_source_id_matches_result_source_id(self):
        source_id = "upload::flange-4711.pdf"
        drawing = CanonicalDrawing(drawing_id="DWG-4711", source_id=source_id)
        result = DrawingIngestionResult(
            source_id=source_id,
            diagnostics=DrawingIngestionDiagnostics(
                status=DrawingIngestionStatus.VALID,
            ),
            document=drawing,
        )
        assert result.source_id == drawing.source_id

    def test_advisory_authority_not_authoritative(self):
        """ADVISORY authority must not reach DECLARED status."""
        loc = DrawingSourceLocation(
            source_id="s",
            authority=DrawingExtractionAuthority.ADVISORY,
        )
        # Can be stored — but consumer must check authority before use
        assert loc.authority is DrawingExtractionAuthority.ADVISORY
        assert loc.authority is not DrawingExtractionAuthority.DECLARED
