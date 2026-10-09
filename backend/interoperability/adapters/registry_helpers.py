"""Registry factory helpers for built-in and optional format adapters.

Provides factory functions that populate :class:`AdapterRegistry` instances
with the built-in pure-Python adapters and (separately) the optional
commercial/vendor stubs.

Usage::

    from backend.interoperability.adapters import build_default_adapter_registry

    registry = build_default_adapter_registry()
    adapters = registry.find_by_format("STEP-AP242")

    from backend.interoperability.adapters import build_full_adapter_registry
    full = build_full_adapter_registry()   # includes commercial stubs
"""

from __future__ import annotations

from backend.interoperability.adapters.dxf import DxfTokenAdapter
from backend.interoperability.adapters.iges import IgesTokenAdapter
from backend.interoperability.adapters.image import RasterImageAdapter, SvgAdapter
from backend.interoperability.adapters.mesh import ObjAdapter, StlAdapter, ThreeMfAdapter
from backend.interoperability.adapters.nc import NcAdapter
from backend.interoperability.adapters.step import StepTokenAdapter
from backend.interoperability.registry import AdapterRegistry

__all__ = ["build_default_adapter_registry", "build_full_adapter_registry"]


def build_default_adapter_registry() -> AdapterRegistry:
    """Create an AdapterRegistry with all built-in open-format adapters.

    Includes adapters for:
    - STEP AP203/AP214/AP242 (neutral exchange)
    - IGES 5.x (neutral exchange)
    - DXF R12–R2024 (2D drawing)
    - STL / OBJ / 3MF (mesh)
    - NC / G-code / TAP (NC programs)
    - PNG / JPG / TIFF / BMP (raster images)
    - SVG (vector images)

    Commercial/native-CAD adapters are NOT included; they are optional plugins.
    The registry is NOT a singleton; callers own and manage their instance.
    """
    registry = AdapterRegistry()
    registry.register(StepTokenAdapter())
    registry.register(IgesTokenAdapter())
    registry.register(DxfTokenAdapter())
    registry.register(StlAdapter())
    registry.register(ObjAdapter())
    registry.register(ThreeMfAdapter())
    registry.register(NcAdapter())
    registry.register(RasterImageAdapter())
    registry.register(SvgAdapter())
    return registry


def build_full_adapter_registry() -> AdapterRegistry:
    """Create an AdapterRegistry with all built-in adapters PLUS optional stubs.

    Adds stubs for: DWG, Parasolid XT, ACIS SAT, JT, SolidWorks,
    CATIA V5/V6, Siemens NX, Creo/Pro-E.

    Each stub returns LEVEL_0_RECOGNIZED with an UNSUPPORTED fidelity event
    until replaced by a vendor-SDK implementation.
    """
    from backend.interoperability.adapters.optional_cad import (
        AcisAdapterStub,
        CatiaAdapterStub,
        CreoAdapterStub,
        DwgAdapterStub,
        JtAdapterStub,
        NxAdapterStub,
        ParasolidAdapterStub,
        SolidWorksAdapterStub,
    )

    registry = build_default_adapter_registry()
    registry.register(DwgAdapterStub())
    registry.register(ParasolidAdapterStub())
    registry.register(AcisAdapterStub())
    registry.register(JtAdapterStub())
    registry.register(SolidWorksAdapterStub())
    registry.register(CatiaAdapterStub())
    registry.register(NxAdapterStub())
    registry.register(CreoAdapterStub())
    return registry
