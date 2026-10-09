"""Universal Engineering Import adapters for MachineryPro AI.

Built-in pure-Python adapters (no mandatory external dependencies):

CAD neutral exchange:
* :class:`StepTokenAdapter`   — STEP AP203/AP214/AP242
* :class:`IgesTokenAdapter`   — IGES 5.x
* :class:`DxfTokenAdapter`    — DXF R12–R2024

Mesh:
* :class:`StlAdapter`         — STL (ASCII + binary)
* :class:`ObjAdapter`         — Wavefront OBJ
* :class:`ThreeMfAdapter`     — 3MF (ZIP + XML)

NC programs:
* :class:`NcAdapter`          — NC / G-code / TAP (ISO 6983-1)

Raster / vector images:
* :class:`RasterImageAdapter` — PNG / JPG / JPEG / TIFF / BMP
* :class:`SvgAdapter`         — SVG 1.1/2.0

Optional commercial/vendor stubs (returned by
``build_full_adapter_registry``; NOT in the default registry):
DWG, Parasolid XT, ACIS SAT/SAB, JT, SolidWorks, CATIA V5/V6,
Siemens NX, Creo/Pro-E.

All adapters honour the FormatAdapter contract and produce
``CanonicalDocument`` envelopes with ``ConversionFidelityReport``.
No adapter performs manufacturing-feature recognition.
No adapter contacts external services; bytes are supplied by the caller.
"""

from backend.interoperability.adapters.dxf import DxfTokenAdapter
from backend.interoperability.adapters.iges import IgesTokenAdapter
from backend.interoperability.adapters.image import RasterImageAdapter, SvgAdapter
from backend.interoperability.adapters.mesh import ObjAdapter, StlAdapter, ThreeMfAdapter
from backend.interoperability.adapters.nc import NcAdapter
from backend.interoperability.adapters.registry_helpers import (
    build_default_adapter_registry,
    build_full_adapter_registry,
)
from backend.interoperability.adapters.step import StepTokenAdapter

__all__ = [
    # CAD neutral exchange
    "DxfTokenAdapter",
    "IgesTokenAdapter",
    "StepTokenAdapter",
    # Mesh
    "ObjAdapter",
    "StlAdapter",
    "ThreeMfAdapter",
    # NC
    "NcAdapter",
    # Images
    "RasterImageAdapter",
    "SvgAdapter",
    # Registry factories
    "build_default_adapter_registry",
    "build_full_adapter_registry",
]
