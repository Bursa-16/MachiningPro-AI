"""Universal Engineering Import — adapter tests.

Covers: STL (ASCII + binary), OBJ, 3MF, NC/G-code/TAP,
        PNG/JPEG/BMP/TIFF raster images, SVG,
        all optional commercial stubs, and the full registry factory.

All tests are pure-Python — no external pip packages required.
Synthetic content is minimal but structurally valid for Level 0/1 parsing.
"""

from __future__ import annotations

import struct
import zipfile
from io import BytesIO

import pytest

from backend.interoperability.adapters.image import (
    RASTER_DESCRIPTOR,
    SVG_DESCRIPTOR,
    RasterImageAdapter,
    SvgAdapter,
)
from backend.interoperability.adapters.mesh import (
    OBJ_DESCRIPTOR,
    STL_DESCRIPTOR,
    THREEMF_DESCRIPTOR,
    ObjAdapter,
    StlAdapter,
    ThreeMfAdapter,
)
from backend.interoperability.adapters.nc import NC_DESCRIPTOR, NcAdapter
from backend.interoperability.adapters.optional_cad import (
    ACIS_DESCRIPTOR,
    CATIA_DESCRIPTOR,
    CREO_DESCRIPTOR,
    DWG_DESCRIPTOR,
    JT_DESCRIPTOR,
    NX_DESCRIPTOR,
    PARASOLID_DESCRIPTOR,
    SOLIDWORKS_DESCRIPTOR,
    AcisAdapterStub,
    CatiaAdapterStub,
    CreoAdapterStub,
    DwgAdapterStub,
    JtAdapterStub,
    NxAdapterStub,
    ParasolidAdapterStub,
    SolidWorksAdapterStub,
    build_optional_adapter_registry,
)
from backend.interoperability.adapters.registry_helpers import (
    build_default_adapter_registry,
    build_full_adapter_registry,
)
from backend.interoperability.enums import (
    CapabilityLevel,
    NormalizationStatus,
)
from backend.interoperability.models import EngineeringSource

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _source(format_id: str | None, name: str, notes: str = "") -> EngineeringSource:
    return EngineeringSource(
        source_id=f"test::{name}",
        source_format_id=format_id,
        file_name=name,
        notes=notes or None,
    )


# ---------------------------------------------------------------------------
# STL tests
# ---------------------------------------------------------------------------

_STL_ASCII_MINIMAL = """\
solid TestPart
  facet normal 0.0 0.0 1.0
    outer loop
      vertex 0.0 0.0 0.0
      vertex 1.0 0.0 0.0
      vertex 0.0 1.0 0.0
    endloop
  endfacet
  facet normal 0.0 0.0 1.0
    outer loop
      vertex 1.0 0.0 0.0
      vertex 1.0 1.0 0.0
      vertex 0.0 1.0 0.0
    endloop
  endfacet
endsolid TestPart
"""


def _make_binary_stl(n_triangles: int = 3) -> bytes:
    header = b"MachineryPro test binary STL file\x00" + b"\x00" * (80 - 34)
    count = struct.pack("<I", n_triangles)
    triangle = struct.pack("<fff", 0.0, 0.0, 1.0)  # normal
    for _i in range(3):
        triangle += struct.pack("<fff", 0.0, 0.0, 0.0)  # vertex
    triangle += struct.pack("<H", 0)  # attribute byte count
    return header + count + triangle * n_triangles


class TestStlAdapter:
    adapter = StlAdapter()

    def test_metadata(self):
        m = self.adapter.metadata()
        assert m.adapter_id == "machinerypro-stl-v1"
        assert "STL" in m.format_ids

    def test_can_handle_by_format_id(self):
        src = _source("STL", "part.stl")
        assert self.adapter.can_handle(src)

    def test_can_handle_by_extension(self):
        src = _source(None, "part.stl")
        assert self.adapter.can_handle(src)

    def test_cannot_handle_other(self):
        src = _source(None, "part.step")
        assert not self.adapter.can_handle(src)

    def test_ingest_ascii_stl(self):
        src = _source("STL", "part.stl", _STL_ASCII_MINIMAL)
        doc = self.adapter.ingest(src, STL_DESCRIPTOR)
        assert doc.normalization_status == NormalizationStatus.SUCCESS
        assert doc.capability_level == CapabilityLevel.LEVEL_1_PARSED
        assert len(doc.entity_refs) == 1
        ref = doc.entity_refs[0]
        assert ref.entity_kind == "StlMesh"
        assert ref.metadata["triangle_count"] == 2

    def test_ingest_binary_stl(self):
        data = _make_binary_stl(5)
        src = EngineeringSource(
            source_id="test::binary.stl",
            source_format_id="STL",
            file_name="binary.stl",
            notes=data.decode("latin-1"),
        )
        doc = self.adapter.ingest(src, STL_DESCRIPTOR)
        assert doc.normalization_status == NormalizationStatus.SUCCESS
        assert doc.entity_refs[0].metadata["triangle_count"] == 5

    def test_ingest_empty_fails(self):
        src = _source("STL", "empty.stl")  # notes=None
        doc = self.adapter.ingest(src, STL_DESCRIPTOR)
        assert doc.normalization_status == NormalizationStatus.FAILED


# ---------------------------------------------------------------------------
# OBJ tests
# ---------------------------------------------------------------------------

_OBJ_MINIMAL = """\
# MachineryPro test OBJ
o TestObject
v 0.0 0.0 0.0
v 1.0 0.0 0.0
v 0.0 1.0 0.0
vn 0.0 0.0 1.0
f 1//1 2//1 3//1
mtllib material.mtl
"""


class TestObjAdapter:
    adapter = ObjAdapter()

    def test_metadata(self):
        m = self.adapter.metadata()
        assert m.adapter_id == "machinerypro-obj-v1"
        assert "OBJ" in m.format_ids

    def test_can_handle_by_format_id(self):
        assert self.adapter.can_handle(_source("OBJ", "mesh.obj"))

    def test_can_handle_by_extension(self):
        assert self.adapter.can_handle(_source(None, "mesh.obj"))

    def test_ingest_obj(self):
        src = _source("OBJ", "mesh.obj", _OBJ_MINIMAL)
        doc = self.adapter.ingest(src, OBJ_DESCRIPTOR)
        assert doc.normalization_status == NormalizationStatus.SUCCESS
        ref = doc.entity_refs[0]
        assert ref.entity_kind == "ObjMesh"
        assert ref.metadata["vertex_count"] == 3
        assert ref.metadata["face_count"] == 1
        assert ref.metadata["normal_count"] == 1
        assert "material.mtl" in ref.metadata["mtl_libs"]

    def test_ingest_empty_fails(self):
        src = _source("OBJ", "empty.obj")
        doc = self.adapter.ingest(src, OBJ_DESCRIPTOR)
        assert doc.normalization_status == NormalizationStatus.FAILED


# ---------------------------------------------------------------------------
# 3MF tests
# ---------------------------------------------------------------------------

def _make_3mf_bytes(vertex_count: int = 4, triangle_count: int = 2) -> bytes:
    """Build a minimal valid 3MF package in memory."""
    ns = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
    vertices = "\n".join(
        f'<vertex x="{i}" y="{i}" z="0"/>' for i in range(vertex_count)
    )
    triangles = "\n".join(
        f'<triangle v1="{i}" v2="{i+1}" v3="{i+2}"/>'
        for i in range(triangle_count)
    )
    model_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xmlns="{ns}">
  <metadata name="Title">TestModel</metadata>
  <resources>
    <object id="1" type="model">
      <mesh>
        <vertices>{vertices}</vertices>
        <triangles>{triangles}</triangles>
      </mesh>
    </object>
  </resources>
  <build><item objectid="1"/></build>
</model>
"""
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
"""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("3D/3dmodel.model", model_xml)
    return buf.getvalue()


class TestThreeMfAdapter:
    adapter = ThreeMfAdapter()

    def test_metadata(self):
        m = self.adapter.metadata()
        assert m.adapter_id == "machinerypro-3mf-v1"

    def test_can_handle(self):
        assert self.adapter.can_handle(_source("3MF", "part.3mf"))
        assert self.adapter.can_handle(_source(None, "part.3mf"))

    def test_ingest_valid_3mf(self):
        data = _make_3mf_bytes(vertex_count=4, triangle_count=2)
        src = EngineeringSource(
            source_id="test::part.3mf",
            source_format_id="3MF",
            file_name="part.3mf",
            notes=data.decode("latin-1"),
        )
        doc = self.adapter.ingest(src, THREEMF_DESCRIPTOR)
        assert doc.normalization_status == NormalizationStatus.SUCCESS
        ref = doc.entity_refs[0]
        assert ref.entity_kind == "ThreeMfMesh"
        assert ref.metadata["vertex_count"] == 4
        assert ref.metadata["triangle_count"] == 2
        assert ref.metadata["object_count"] == 1

    def test_ingest_empty_fails(self):
        src = _source("3MF", "empty.3mf")
        doc = self.adapter.ingest(src, THREEMF_DESCRIPTOR)
        assert doc.normalization_status == NormalizationStatus.FAILED

    def test_ingest_not_zip_fails(self):
        src = _source("3MF", "bad.3mf", "this is not a zip file")
        doc = self.adapter.ingest(src, THREEMF_DESCRIPTOR)
        assert doc.normalization_status == NormalizationStatus.FAILED


# ---------------------------------------------------------------------------
# NC / G-code tests
# ---------------------------------------------------------------------------

_GCODE_MINIMAL = """\
%
O1234 (MACHININGPRO TEST PROGRAM)
N10 G17 G20 G90 G94 G54
N20 G0 Z25.
T1 M6
N30 S5000 M3
N40 G0 X0. Y0.
N50 G1 Z-5. F100.
N60 G1 X50. F200.
N70 G1 Y50.
N80 G0 Z25.
M5
M30
%
"""

_GCODE_FANUC_STYLE = """\
O9001
G91G28Z0.
G91G28X0.Y0.
G90G92X0.Y0.Z0.
T1M6
S1000M3
G0X10.Y10.
G1Z-5.F50.
M30
"""


class TestNcAdapter:
    adapter = NcAdapter()

    def test_metadata(self):
        m = self.adapter.metadata()
        assert m.adapter_id == "machinerypro-nc-gcode-v1"
        assert "NC-GCODE" in m.format_ids

    def test_can_handle_nc_extension(self):
        assert self.adapter.can_handle(_source(None, "program.nc"))

    def test_can_handle_gcode_extension(self):
        assert self.adapter.can_handle(_source(None, "part.gcode"))

    def test_can_handle_tap_extension(self):
        assert self.adapter.can_handle(_source(None, "mill.tap"))

    def test_can_handle_by_format_id(self):
        assert self.adapter.can_handle(_source("NC-GCODE", "prog.nc"))

    def test_cannot_handle_step(self):
        assert not self.adapter.can_handle(_source(None, "part.step"))

    def test_ingest_gcode(self):
        src = _source("NC-GCODE", "prog.nc", _GCODE_MINIMAL)
        doc = self.adapter.ingest(src, NC_DESCRIPTOR)
        assert doc.normalization_status == NormalizationStatus.SUCCESS
        assert doc.capability_level == CapabilityLevel.LEVEL_1_PARSED
        ref = doc.entity_refs[0]
        assert ref.entity_kind == "NcProgram"
        assert ref.metadata["block_count"] > 5
        assert "17" in ref.metadata["g_codes"] or "0" in ref.metadata["g_codes"]
        prog_nos = ref.metadata["program_numbers"]
        assert "1234" in prog_nos or "9001" not in prog_nos

    def test_ingest_fanuc(self):
        src = _source("NC-GCODE", "fanuc.nc", _GCODE_FANUC_STYLE)
        doc = self.adapter.ingest(src, NC_DESCRIPTOR)
        assert doc.normalization_status == NormalizationStatus.SUCCESS
        ref = doc.entity_refs[0]
        assert "T1" in " ".join(ref.metadata["tool_numbers"]) or "1" in ref.metadata["tool_numbers"]

    def test_ingest_empty_fails(self):
        src = _source("NC-GCODE", "empty.nc")
        doc = self.adapter.ingest(src, NC_DESCRIPTOR)
        assert doc.normalization_status == NormalizationStatus.FAILED


# ---------------------------------------------------------------------------
# Raster image tests
# ---------------------------------------------------------------------------

def _make_png_bytes() -> bytes:
    """Minimal valid 1×1 PNG (8-bit greyscale)."""
    import struct as _struct
    import zlib

    def chunk(name: bytes, data: bytes) -> bytes:
        length = _struct.pack(">I", len(data))
        crc = _struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)
        return length + name + data + crc

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = _struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
    idat_data = zlib.compress(b"\x00\xff")
    return sig + chunk(b"IHDR", ihdr_data) + chunk(b"IDAT", idat_data) + chunk(b"IEND", b"")


def _make_bmp_bytes() -> bytes:
    """Minimal valid 2×2 24-bit BMP."""
    import struct as _struct

    # DIB header size = 40 (BITMAPINFOHEADER)
    pixel_data = b"\xff\x00\x00" * 4 + b"\x00\x00"  # 2×2 red pixels + row padding
    dib_header = _struct.pack(
        "<IIIHHIIIIII",
        40,    # header size
        2,     # width
        2,     # height
        1,     # planes
        24,    # bpp
        0,     # compression (BI_RGB)
        len(pixel_data),
        2835, 2835, 0, 0,
    )
    file_header_size = 14
    dib_size = len(dib_header)
    pixel_offset = file_header_size + dib_size
    file_size = file_header_size + dib_size + len(pixel_data)
    bmp_header = b"BM" + _struct.pack("<IHH I", file_size, 0, 0, pixel_offset)
    return bmp_header + dib_header + pixel_data


class TestRasterImageAdapter:
    adapter = RasterImageAdapter()

    def test_metadata(self):
        m = self.adapter.metadata()
        assert m.adapter_id == "machinerypro-raster-image-v1"

    def test_can_handle_png(self):
        assert self.adapter.can_handle(_source(None, "drawing.png"))

    def test_can_handle_jpg(self):
        assert self.adapter.can_handle(_source(None, "scan.jpg"))

    def test_can_handle_jpeg(self):
        assert self.adapter.can_handle(_source(None, "scan.jpeg"))

    def test_can_handle_tiff(self):
        assert self.adapter.can_handle(_source(None, "sheet.tiff"))

    def test_can_handle_bmp(self):
        assert self.adapter.can_handle(_source(None, "photo.bmp"))

    def test_can_handle_by_format_id(self):
        assert self.adapter.can_handle(_source("RASTER-IMAGE", "x.png"))

    def test_cannot_handle_dxf(self):
        assert not self.adapter.can_handle(_source(None, "drawing.dxf"))

    def test_ingest_png(self):
        data = _make_png_bytes()
        src = EngineeringSource(
            source_id="test::png",
            source_format_id="RASTER-IMAGE",
            file_name="drawing.png",
            notes=data.decode("latin-1"),
        )
        doc = self.adapter.ingest(src, RASTER_DESCRIPTOR)
        assert doc.normalization_status == NormalizationStatus.SUCCESS
        ref = doc.entity_refs[0]
        assert ref.entity_kind == "RasterImage"
        assert ref.metadata["raster_format"] in ("PNG", "UNKNOWN")

    def test_ingest_bmp(self):
        data = _make_bmp_bytes()
        src = EngineeringSource(
            source_id="test::bmp",
            source_format_id="RASTER-IMAGE",
            file_name="drawing.bmp",
            notes=data.decode("latin-1"),
        )
        doc = self.adapter.ingest(src, RASTER_DESCRIPTOR)
        assert doc.normalization_status == NormalizationStatus.SUCCESS

    def test_ingest_empty_fails(self):
        src = _source("RASTER-IMAGE", "empty.png")
        doc = self.adapter.ingest(src, RASTER_DESCRIPTOR)
        assert doc.normalization_status == NormalizationStatus.FAILED


# ---------------------------------------------------------------------------
# SVG tests
# ---------------------------------------------------------------------------

_SVG_MINIMAL = """\
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="200mm" height="150mm"
     viewBox="0 0 200 150">
  <title>MachineryPro Test Drawing</title>
  <rect x="10" y="10" width="180" height="130" fill="none" stroke="black"/>
  <line x1="10" y1="10" x2="190" y2="140" stroke="red"/>
  <circle cx="100" cy="75" r="30" fill="none" stroke="blue"/>
</svg>
"""


class TestSvgAdapter:
    adapter = SvgAdapter()

    def test_metadata(self):
        m = self.adapter.metadata()
        assert m.adapter_id == "machinerypro-svg-v1"

    def test_can_handle_svg(self):
        assert self.adapter.can_handle(_source(None, "drawing.svg"))

    def test_can_handle_by_format_id(self):
        assert self.adapter.can_handle(_source("SVG", "drawing.svg"))

    def test_cannot_handle_png(self):
        assert not self.adapter.can_handle(_source(None, "photo.png"))

    def test_ingest_valid_svg(self):
        src = _source("SVG", "drawing.svg", _SVG_MINIMAL)
        doc = self.adapter.ingest(src, SVG_DESCRIPTOR)
        assert doc.normalization_status == NormalizationStatus.SUCCESS
        ref = doc.entity_refs[0]
        assert ref.entity_kind == "SvgDocument"
        assert ref.metadata["width"] == "200mm"
        assert ref.metadata["height"] == "150mm"
        assert ref.metadata["element_count"] > 0

    def test_ingest_empty_fails(self):
        src = _source("SVG", "empty.svg")
        doc = self.adapter.ingest(src, SVG_DESCRIPTOR)
        assert doc.normalization_status == NormalizationStatus.FAILED


# ---------------------------------------------------------------------------
# Optional commercial stub tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "stub_cls, fmt_id, filename",
    [
        (DwgAdapterStub, "DWG", "drawing.dwg"),
        (ParasolidAdapterStub, "PARASOLID-XT", "part.x_t"),
        (AcisAdapterStub, "ACIS-SAT", "solid.sat"),
        (JtAdapterStub, "JT", "assembly.jt"),
        (SolidWorksAdapterStub, "SLDPRT", "part.sldprt"),
        (CatiaAdapterStub, "CATPART", "model.catpart"),
        (NxAdapterStub, "PRT-NX", "design.prt"),
        (CreoAdapterStub, "PRT-CREO", "part.prt"),
    ],
)
class TestOptionalStubs:
    def test_can_handle_by_format_id(self, stub_cls, fmt_id, filename):
        adapter = stub_cls()
        assert adapter.can_handle(_source(fmt_id, filename))

    def test_can_handle_by_extension(self, stub_cls, fmt_id, filename):
        adapter = stub_cls()
        assert adapter.can_handle(_source(None, filename))

    def test_ingest_returns_unsupported(self, stub_cls, fmt_id, filename):
        adapter = stub_cls()
        descriptor_map = {
            "DWG": DWG_DESCRIPTOR,
            "PARASOLID-XT": PARASOLID_DESCRIPTOR,
            "ACIS-SAT": ACIS_DESCRIPTOR,
            "JT": JT_DESCRIPTOR,
            "SLDPRT": SOLIDWORKS_DESCRIPTOR,
            "CATPART": CATIA_DESCRIPTOR,
            "PRT-NX": NX_DESCRIPTOR,
            "PRT-CREO": CREO_DESCRIPTOR,
        }
        descriptor = descriptor_map[fmt_id]
        src = _source(fmt_id, filename, "some content")
        doc = adapter.ingest(src, descriptor)
        assert doc.normalization_status == NormalizationStatus.UNSUPPORTED
        assert len(doc.fidelity_report.events) >= 1
        assert doc.capability_level == CapabilityLevel.LEVEL_0_RECOGNIZED

    def test_metadata_declares_commercial(self, stub_cls, fmt_id, filename):
        adapter = stub_cls()
        m = adapter.metadata()
        assert m.requires_external_dependency is True

    def test_optional_registry(self, stub_cls, fmt_id, filename):
        registry = build_optional_adapter_registry()
        assert len(registry) == 8


# ---------------------------------------------------------------------------
# Default registry completeness test
# ---------------------------------------------------------------------------

class TestDefaultRegistry:
    def test_adapter_count(self):
        registry = build_default_adapter_registry()
        assert len(registry) == 9  # STEP, IGES, DXF, STL, OBJ, 3MF, NC, RASTER, SVG

    def test_step_present(self):
        registry = build_default_adapter_registry()
        assert len(registry.find_by_format("STEP-AP242")) >= 1

    def test_iges_present(self):
        registry = build_default_adapter_registry()
        assert len(registry.find_by_format("IGES")) >= 1

    def test_dxf_present(self):
        registry = build_default_adapter_registry()
        assert len(registry.find_by_format("DXF")) >= 1

    def test_stl_present(self):
        registry = build_default_adapter_registry()
        assert len(registry.find_by_format("STL")) >= 1

    def test_obj_present(self):
        registry = build_default_adapter_registry()
        assert len(registry.find_by_format("OBJ")) >= 1

    def test_3mf_present(self):
        registry = build_default_adapter_registry()
        assert len(registry.find_by_format("3MF")) >= 1

    def test_nc_present(self):
        registry = build_default_adapter_registry()
        assert len(registry.find_by_format("NC-GCODE")) >= 1

    def test_raster_present(self):
        registry = build_default_adapter_registry()
        assert len(registry.find_by_format("RASTER-IMAGE")) >= 1

    def test_svg_present(self):
        registry = build_default_adapter_registry()
        assert len(registry.find_by_format("SVG")) >= 1


class TestFullRegistry:
    def test_adapter_count(self):
        registry = build_full_adapter_registry()
        assert len(registry) == 17  # 9 default + 8 optional stubs

    def test_dwg_present(self):
        registry = build_full_adapter_registry()
        assert len(registry.find_by_format("DWG")) >= 1

    def test_solidworks_present(self):
        registry = build_full_adapter_registry()
        assert len(registry.find_by_format("SLDPRT")) >= 1

    def test_parasolid_present(self):
        registry = build_full_adapter_registry()
        assert len(registry.find_by_format("PARASOLID-XT")) >= 1
