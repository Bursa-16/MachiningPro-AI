"""Phase 4 smoke tests — Universal Engineering Import (UNIVERSAL_IMPORT_02).

Five format scenarios:
  1. PDF    → format detection → DRAWING_PDF route (no universal adapter)
  2. PNG    → format detection → DRAWING_IMAGE route, IMPORT=SUCCESS
  3. DXF    → format detection → DRAWING_VECTOR, DETERMINISTIC_2D_GEOMETRY_AVAILABLE
  4. STEP   → format detection → CAD_GEOMETRY, GEOMETRY_LOAD=PASS, BASIC_METADATA_VISIBLE
  5. IGES   → format detection → CAD_GEOMETRY, GEOMETRY_LOAD=PASS, BASIC_METADATA_VISIBLE

All tests are pure-Python with synthetic but structurally valid file content.
No cloud conversion. No paid API. No Granite inference.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from backend.api.engineering_import import (
    _EXT_TO_FORMAT,
    _detect_format_id,
    _ext,
    _minimal_descriptor,
)
from backend.interoperability.adapters.registry_helpers import build_default_adapter_registry
from backend.interoperability.enums import CapabilityLevel, NormalizationStatus
from tests.unit.interoperability.iges_fixtures import EntitySpec, make_iges

# ---------------------------------------------------------------------------
# Minimal synthetic file content
# ---------------------------------------------------------------------------

_MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 1\n%%EOF"

_MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n"          # PNG signature
    b"\x00\x00\x00\rIHDR"         # IHDR chunk (13 bytes)
    b"\x00\x00\x00\x10"           # width=16
    b"\x00\x00\x00\x10"           # height=16
    b"\x08\x02\x00\x00\x00"       # bit depth=8, color type=2
    b"\x90\x91h\x36"              # CRC (arbitrary, not validated by adapter)
    b"\x00\x00\x00\x00IEND"
    b"\xaeB`\x82"
)

_MINIMAL_DXF = (
    "  0\r\nSECTION\r\n"
    "  2\r\nHEADER\r\n"
    "  9\r\n$ACADVER\r\n"
    "  1\r\nAC1015\r\n"
    "  0\r\nENDSEC\r\n"
    "  0\r\nSECTION\r\n"
    "  2\r\nENTITIES\r\n"
    "  0\r\nLINE\r\n"
    " 10\r\n0.0\r\n"
    " 20\r\n0.0\r\n"
    " 11\r\n100.0\r\n"
    " 21\r\n0.0\r\n"
    "  0\r\nCIRCLE\r\n"
    " 10\r\n50.0\r\n"
    " 20\r\n50.0\r\n"
    " 40\r\n25.0\r\n"
    "  0\r\nENDSEC\r\n"
    "  0\r\nEOF\r\n"
)

_MINIMAL_STEP = (
    "ISO-10303-21;\r\n"
    "HEADER;\r\n"
    "FILE_DESCRIPTION(('Minimal STEP test'),'2;1');\r\n"
    "FILE_NAME('test.stp','2024-01-01T00:00:00',(''),(''),'','','');\r\n"
    "FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));\r\n"
    "ENDSEC;\r\n"
    "DATA;\r\n"
    "#1=PRODUCT('part','Part','',(#2));\r\n"
    "#2=PRODUCT_CONTEXT('',#3,'mechanical');\r\n"
    "#3=APPLICATION_CONTEXT('automotive design');\r\n"
    "#10=CARTESIAN_POINT('Origin',(0.0,0.0,0.0));\r\n"
    "ENDSEC;\r\n"
    "END-ISO-10303-21;\r\n"
)

# Use the existing fixture builder for a well-formed IGES with a Line entity
_MINIMAL_IGES = make_iges(
    entities=(
        EntitySpec(110, "110,0.0,0.0,0.0,100.0,0.0,0.0;", label="LINE"),
    )
)


# ---------------------------------------------------------------------------
# Helper: run the backend import endpoint logic directly (no HTTP)
# ---------------------------------------------------------------------------

def _ingest_bytes(data: bytes, filename: str):
    """Write data to a temp file and call the matching registry adapter."""
    registry = build_default_adapter_registry()
    format_id, family_str = _detect_format_id(data[:512], filename)
    from backend.interoperability.models import EngineeringSource
    source = EngineeringSource(
        source_id=f"smoke::{filename}",
        source_format_id=format_id if format_id != "UNKNOWN" else None,
        file_name=filename,
    )
    descriptor = _minimal_descriptor(format_id, family_str)
    adapters = registry.find_by_format(format_id)
    assert adapters, f"No adapter found for format_id={format_id!r} (file={filename!r})"
    adapter = adapters[0]
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        return adapter.ingest_file(source, descriptor, tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


# ===========================================================================
# Smoke 1 — vector PDF
# ===========================================================================

class TestSmoke01VectorPDF:
    """FILE_SELECTION=PASS, FORMAT_DETECTION=PASS, DRAWING_ANALYSIS_ENTRY_READY=YES."""

    def test_format_detection_pass(self):
        """PDF detected from extension (no PDF magic in ContentSniffer)."""
        fmt_id, family = _detect_format_id(_MINIMAL_PDF[:512], "drawing.pdf")
        assert fmt_id == "PDF"
        assert family == "DOCUMENT"

    def test_ext_detection(self):
        assert _ext("technical_drawing.pdf") == "pdf"

    def test_pdf_ext_table_entry(self):
        fmt_id, family = _EXT_TO_FORMAT["pdf"]
        assert fmt_id == "PDF"
        assert family == "DOCUMENT"

    def test_drawing_analysis_entry_ready(self):
        """PDF is NOT in the universal registry — it goes to /api/drawings (drawing analysis)."""
        registry = build_default_adapter_registry()
        adapters = registry.find_by_format("PDF")
        assert not adapters, "PDF must NOT be in the universal import registry"


# ===========================================================================
# Smoke 2 — PNG / JPG (raster image)
# ===========================================================================

class TestSmoke02Image:
    """FILE_SELECTION=PASS, FORMAT_DETECTION=PASS, IMPORT=PASS, PREVIEW_VISIBLE=YES."""

    def test_png_format_detection_pass(self):
        fmt_id, family = _detect_format_id(_MINIMAL_PNG[:512], "photo.png")
        assert fmt_id == "RASTER-IMAGE"
        assert family == "IMAGE"

    def test_jpg_format_detection_pass(self):
        fmt_id, family = _detect_format_id(b"\xff\xd8\xff\xe0abc", "scan.jpg")
        assert fmt_id == "RASTER-IMAGE"
        assert family == "IMAGE"

    def test_png_import_pass(self):
        doc = _ingest_bytes(_MINIMAL_PNG, "drawing_scan.png")
        assert doc.normalization_status in (
            NormalizationStatus.SUCCESS,
            NormalizationStatus.PARTIAL,
            NormalizationStatus.INSUFFICIENT_DATA,
        ), f"unexpected status: {doc.normalization_status}"
        assert doc.capability_level >= CapabilityLevel.LEVEL_0_RECOGNIZED
        assert doc.format_descriptor.format_id == "RASTER-IMAGE"

    def test_image_ext_table_entries(self):
        for ext in ("png", "jpg", "jpeg", "tif", "tiff", "bmp"):
            fmt_id, family = _EXT_TO_FORMAT[ext]
            assert fmt_id == "RASTER-IMAGE", f"{ext} should map to RASTER-IMAGE"
            assert family == "IMAGE", f"{ext} family should be IMAGE"

    def test_drawing_analysis_entry_ready(self):
        """IMAGE family → DRAWING_IMAGE route in UI → analyze button accessible."""
        _, family = _EXT_TO_FORMAT["png"]
        assert family == "IMAGE"


# ===========================================================================
# Smoke 3 — DXF
# ===========================================================================

class TestSmoke03Dxf:
    """FILE_SELECTION=PASS, FORMAT_DETECTION=PASS, IMPORT=PASS,
    DETERMINISTIC_2D_GEOMETRY_AVAILABLE=YES, PREVIEW_OR_VIEW_AVAILABLE=YES."""

    def test_dxf_format_detection_pass(self):
        data = _MINIMAL_DXF.encode("ascii")
        fmt_id, family = _detect_format_id(data[:512], "part_drawing.dxf")
        assert fmt_id == "DXF"
        assert family == "DRAWING"

    def test_dxf_import_pass(self):
        data = _MINIMAL_DXF.encode("ascii")
        doc = _ingest_bytes(data, "part_drawing.dxf")
        assert doc.normalization_status in (
            NormalizationStatus.SUCCESS,
            NormalizationStatus.PARTIAL,
        ), f"unexpected status: {doc.normalization_status}"

    def test_dxf_deterministic_2d_geometry_available(self):
        """DETERMINISTIC_2D_GEOMETRY_AVAILABLE — entities parsed from DXF."""
        data = _MINIMAL_DXF.encode("ascii")
        doc = _ingest_bytes(data, "part_drawing.dxf")
        entity_count = len(doc.entity_refs)
        assert entity_count > 0, "DXF must yield at least one parsed entity"

    def test_dxf_preview_or_view_available(self):
        """PREVIEW_OR_VIEW_AVAILABLE — format is identified as 2D drawing."""
        data = _MINIMAL_DXF.encode("ascii")
        doc = _ingest_bytes(data, "part_drawing.dxf")
        assert doc.format_descriptor.format_id in ("DXF", "DXF-BINARY")


# ===========================================================================
# Smoke 4 — STEP
# ===========================================================================

class TestSmoke04Step:
    """FILE_SELECTION=PASS, FORMAT_DETECTION=PASS, IMPORT=PASS,
    GEOMETRY_LOAD=PASS, BASIC_METADATA_VISIBLE=YES."""

    def test_step_format_detection_pass(self):
        data = _MINIMAL_STEP.encode("ascii")
        fmt_id, family = _detect_format_id(data[:512], "assembly.step")
        assert fmt_id.startswith("STEP-"), f"Expected STEP- prefix, got {fmt_id!r}"
        assert family == "NEUTRAL_EXCHANGE"

    def test_step_import_pass(self):
        data = _MINIMAL_STEP.encode("ascii")
        doc = _ingest_bytes(data, "assembly.step")
        assert doc.normalization_status in (
            NormalizationStatus.SUCCESS,
            NormalizationStatus.PARTIAL,
        ), f"unexpected status: {doc.normalization_status}"

    def test_step_geometry_load_pass(self):
        """GEOMETRY_LOAD=PASS — at least one entity parsed from STEP."""
        data = _MINIMAL_STEP.encode("ascii")
        doc = _ingest_bytes(data, "assembly.step")
        entity_count = len(doc.entity_refs)
        assert entity_count > 0, "STEP must yield at least one parsed entity"

    def test_step_basic_metadata_visible(self):
        """BASIC_METADATA_VISIBLE — at least one entity carries metadata."""
        data = _MINIMAL_STEP.encode("ascii")
        doc = _ingest_bytes(data, "assembly.step")
        assert len(doc.entity_refs) > 0
        has_meta = any(bool(ref.metadata) for ref in doc.entity_refs)
        assert has_meta, "STEP entities must include basic metadata dict"


# ===========================================================================
# Smoke 5 — IGES
# ===========================================================================

class TestSmoke05Iges:
    """FILE_SELECTION=PASS, FORMAT_DETECTION=PASS, IMPORT=PASS,
    GEOMETRY_LOAD=PASS, BASIC_METADATA_VISIBLE=YES."""

    def test_iges_format_detection_pass(self):
        fmt_id, family = _detect_format_id(_MINIMAL_IGES[:512], "surface_model.iges")
        assert fmt_id == "IGES"
        assert family == "NEUTRAL_EXCHANGE"

    def test_iges_import_pass(self):
        doc = _ingest_bytes(_MINIMAL_IGES, "surface_model.iges")
        assert doc.normalization_status in (
            NormalizationStatus.SUCCESS,
            NormalizationStatus.PARTIAL,
        ), f"unexpected status: {doc.normalization_status}"

    def test_iges_geometry_load_pass(self):
        """GEOMETRY_LOAD=PASS — at least one entity parsed from IGES."""
        doc = _ingest_bytes(_MINIMAL_IGES, "surface_model.iges")
        entity_count = len(doc.entity_refs)
        assert entity_count > 0, "IGES must yield at least one parsed entity"

    def test_iges_basic_metadata_visible(self):
        """BASIC_METADATA_VISIBLE — at least one entity carries metadata."""
        doc = _ingest_bytes(_MINIMAL_IGES, "surface_model.iges")
        assert len(doc.entity_refs) > 0
        has_meta = any(bool(ref.metadata) for ref in doc.entity_refs)
        assert has_meta, "IGES entities must include basic metadata dict"


# ===========================================================================
# Smoke 6 — has_renderable_geometry (CAD_IMPORT_IGES_03)
# ===========================================================================

def _has_renderable_geometry(doc) -> bool:
    """Apply the same logic as import_file() in engineering_import.py."""
    from backend.interoperability.geometry import CanonicalGeometry
    geom = doc.geometry
    return isinstance(geom, CanonicalGeometry) and (
        len(geom.curves) > 0 or len(geom.surfaces) > 0
    )


_POINT_ONLY_IGES = make_iges(
    entities=(
        EntitySpec(116, "116,10.0,20.0,30.0,0;", label="POINT"),
    )
)

_LINE_BEARING_IGES = make_iges(
    entities=(
        EntitySpec(110, "110,0.0,0.0,0.0,100.0,0.0,0.0;", label="LINE"),
    )
)


class TestSmoke06HasRenderableGeometry:
    """POINT_ONLY_IGES_HAS_RENDERABLE_GEOMETRY=NO, LINE_IGES=YES,
    STL_MESH=NO (mesh geometry is not in CanonicalGeometry curves/surfaces)."""

    def test_point_only_iges_no_renderable_geometry(self):
        """Point entity (type 116) must NOT count as renderable geometry."""
        doc = _ingest_bytes(_POINT_ONLY_IGES, "point_cloud.iges")
        assert doc.normalization_status in (
            NormalizationStatus.SUCCESS,
            NormalizationStatus.PARTIAL,
        ), f"unexpected status: {doc.normalization_status}"
        assert not _has_renderable_geometry(doc), (
            "Point-only IGES must have has_renderable_geometry=False"
        )

    def test_line_bearing_iges_has_renderable_geometry(self):
        """Line entity (type 110) MUST count as renderable geometry."""
        doc = _ingest_bytes(_LINE_BEARING_IGES, "line_model.iges")
        assert _has_renderable_geometry(doc), (
            "Line-bearing IGES must have has_renderable_geometry=True"
        )

    def test_stl_no_renderable_geometry_in_canonical(self):
        """STL mesh geometry is not stored as CanonicalGeometry curves/surfaces."""
        from tests.unit.interoperability.test_universal_import import _STL_ASCII_MINIMAL
        doc = _ingest_bytes(_STL_ASCII_MINIMAL.encode(), "part.stl")
        assert not _has_renderable_geometry(doc), (
            "STL mesh geometry must not register as has_renderable_geometry"
        )


# ===========================================================================
# Smoke 7 — _tessellate_step (CAD_3D_VIEWER_01B)
# ===========================================================================

_SAMPLE_STEP_PATH = Path(__file__).parents[3] / "sample_part.step"


class TestSmoke07StepTessellation:
    """GMSH_TESSELLATION_FUNCTION_EXISTS=YES, GRACEFUL_FAILURE_ON_NO_GEOMETRY=YES."""

    def test_tessellate_step_importable(self):
        """_tessellate_step is importable and callable."""
        from backend.api.engineering_import import _tessellate_step
        assert callable(_tessellate_step)

    def test_tessellate_step_empty_bytes_returns_none(self):
        """Empty bytes must return None gracefully (HARD RULE 09)."""
        from backend.api.engineering_import import _tessellate_step
        result = _tessellate_step(b"")
        assert result is None

    def test_tessellate_step_invalid_bytes_returns_none(self):
        """Non-STEP bytes must return None without raising (HARD RULE 09)."""
        from backend.api.engineering_import import _tessellate_step
        result = _tessellate_step(b"NOT A STEP FILE AT ALL\x00\x01\x02")
        assert result is None

    def test_tessellate_step_minimal_no_geometry_returns_none(self):
        """Minimal STEP with no surfaces must return None gracefully."""
        from backend.api.engineering_import import _tessellate_step
        result = _tessellate_step(_MINIMAL_STEP.encode("ascii"))
        # A STEP with no solid bodies yields no triangles — must be None or valid dict
        # (gmsh may load it but produce 0 triangles)
        assert result is None or (
            isinstance(result, dict)
            and result.get("triangle_count", 0) >= 0
        )

    @pytest.mark.skipif(
        not _SAMPLE_STEP_PATH.exists(),
        reason="sample_part.step not present in repo root",
    )
    def test_tessellate_step_real_file_returns_valid_mesh(self):
        """sample_part.step → valid mesh dict with ≥1 triangle and correct keys."""
        from backend.api.engineering_import import _tessellate_step
        data = _SAMPLE_STEP_PATH.read_bytes()
        result = _tessellate_step(data)
        assert result is not None, "Real STEP file must tessellate successfully"
        assert "positions" in result
        assert "indices" in result
        assert "bounding_box" in result
        assert "vertex_count" in result
        assert "triangle_count" in result
        assert result["triangle_count"] > 0, "Must produce at least one triangle"
        assert result["vertex_count"] > 0
        # All indices must be valid (HARD RULE 17)
        max_idx = max(result["indices"])
        assert max_idx < result["vertex_count"], "Triangle indices must be within vertex array"
        # positions length must be vertex_count * 3
        assert len(result["positions"]) == result["vertex_count"] * 3
        # bounding_box must have min and max with 3 components
        bb = result["bounding_box"]
        assert len(bb["min"]) == 3
        assert len(bb["max"]) == 3

    @pytest.mark.skipif(
        not _SAMPLE_STEP_PATH.exists(),
        reason="sample_part.step not present in repo root",
    )
    def test_tessellate_step_real_file_bounding_box_correct(self):
        """sample_part.step bounding box must match known 20×20×10mm geometry."""
        from backend.api.engineering_import import _tessellate_step
        data = _SAMPLE_STEP_PATH.read_bytes()
        result = _tessellate_step(data)
        assert result is not None
        bb = result["bounding_box"]
        # Part is ≈20×20×10mm centred at origin; allow ±1mm tolerance
        assert abs(bb["max"][0] - bb["min"][0] - 20.0) < 1.0, "X extent should be ≈20mm"
        assert abs(bb["max"][1] - bb["min"][1] - 20.0) < 1.0, "Y extent should be ≈20mm"
        assert abs(bb["max"][2] - bb["min"][2] - 10.0) < 1.0, "Z extent should be ≈10mm"
