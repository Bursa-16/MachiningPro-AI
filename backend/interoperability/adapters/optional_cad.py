"""Optional-adapter architecture for proprietary / commercial CAD formats.

This module defines STUB adapters for vendor-native and commercial formats.
Each stub:

1. Declares full AdapterMetadata so the registry knows the format exists.
2. Implements can_handle() from extension only (content sniffing impossible
   without the vendor SDK).
3. ingest() always returns a LEVEL_0_RECOGNIZED document with an UNSUPPORTED
   fidelity event explaining the missing dependency.
4. The adapter_license signals the commercial/vendor requirement clearly.

Supported formats:
  DWG   — Autodesk DWG (requires ODA File Converter, LibreCAD, ezdxf-pro, or Teigha)
  X_T   — Parasolid XT (requires Siemens Parasolid SDK)
  SAT   — ACIS SAT/SAB (requires Spatial 3D ACIS or Autodesk Platform SDK)
  JT    — JT Open (requires Siemens JT Open Toolkit)
  SLDPRT — SolidWorks (requires SolidWorks API or eDrawings SDK)
  CATPART — CATIA V5/V6 (requires CATIA CAA or Datakit CrossManager)
  PRT_NX — Siemens NX (requires NX Open API or Datakit)
  PRT_CREO — Creo / Pro/ENGINEER (requires PTC Creo API)

These stubs are registered in the optional registry; they are NOT included
in ``build_default_adapter_registry()`` and the MachineryPro core starts
without them.  Deployments with vendor SDKs replace each stub with a
fully-implemented subclass.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from backend.interoperability.adapter import FormatAdapter

if TYPE_CHECKING:
    from backend.interoperability.registry import AdapterRegistry
from backend.interoperability.adapters._base import AdapterSession, make_uid
from backend.interoperability.enums import (
    AdapterCapability,
    AdapterLicense,
    CapabilityLevel,
    FidelityReportCompleteness,
    FormatFamily,
)
from backend.interoperability.models import (
    AdapterMetadata,
    CanonicalDocument,
    CanonicalEntityRef,
    EngineeringSource,
    FormatDescriptor,
)

__all__ = [
    "DWG_DESCRIPTOR",
    "PARASOLID_DESCRIPTOR",
    "ACIS_DESCRIPTOR",
    "JT_DESCRIPTOR",
    "SOLIDWORKS_DESCRIPTOR",
    "CATIA_DESCRIPTOR",
    "NX_DESCRIPTOR",
    "CREO_DESCRIPTOR",
    "DwgAdapterStub",
    "ParasolidAdapterStub",
    "AcisAdapterStub",
    "JtAdapterStub",
    "SolidWorksAdapterStub",
    "CatiaAdapterStub",
    "NxAdapterStub",
    "CreoAdapterStub",
    "build_optional_adapter_registry",
]


# ---------------------------------------------------------------------------
# Format descriptors
# ---------------------------------------------------------------------------

DWG_DESCRIPTOR = FormatDescriptor(
    format_id="DWG",
    canonical_name="AutoCAD DWG",
    family=FormatFamily.DRAWING,
    extensions=("dwg",),
    media_types=("image/vnd.dwg",),
    vendor="Autodesk",
    is_open=False,
    is_proprietary=True,
    requires_commercial_sdk=True,
    adapter_license=AdapterLicense.COMMERCIAL_SDK,
    notes=(
        "AutoCAD DWG binary format. Requires ODA File Converter (free), "
        "ezdxf DWG reader (commercial), or Teigha/Open Design SDK."
    ),
)

PARASOLID_DESCRIPTOR = FormatDescriptor(
    format_id="PARASOLID-XT",
    canonical_name="Parasolid XT",
    family=FormatFamily.CAD,
    extensions=("x_t", "x_b", "xmt_txt", "xmt_bin"),
    media_types=(),
    vendor="Siemens",
    is_open=False,
    is_proprietary=True,
    requires_commercial_sdk=True,
    adapter_license=AdapterLicense.COMMERCIAL_SDK,
    notes="Siemens Parasolid kernel geometry format. Requires Parasolid SDK.",
)

ACIS_DESCRIPTOR = FormatDescriptor(
    format_id="ACIS-SAT",
    canonical_name="ACIS SAT/SAB",
    family=FormatFamily.CAD,
    extensions=("sat", "sab"),
    media_types=(),
    vendor="Spatial",
    is_open=False,
    is_proprietary=True,
    requires_commercial_sdk=True,
    adapter_license=AdapterLicense.COMMERCIAL_SDK,
    notes="ACIS solid model format (SAT = ASCII, SAB = binary). Requires Spatial 3D ACIS SDK.",
)

JT_DESCRIPTOR = FormatDescriptor(
    format_id="JT",
    canonical_name="JT Open",
    family=FormatFamily.CAD,
    extensions=("jt",),
    media_types=("model/jt",),
    vendor="Siemens",
    is_open=True,
    is_proprietary=False,
    requires_commercial_sdk=True,
    adapter_license=AdapterLicense.COMMERCIAL_SDK,
    notes=(
        "ISO 14306:2012 JT. Free spec; practical read requires JT Open Toolkit "
        "or Datakit CrossManager."
    ),
)

SOLIDWORKS_DESCRIPTOR = FormatDescriptor(
    format_id="SLDPRT",
    canonical_name="SolidWorks Part",
    family=FormatFamily.NATIVE_CAD,
    extensions=("sldprt", "sldasm", "slddrw"),
    media_types=(),
    vendor="Dassault Systèmes",
    is_open=False,
    is_proprietary=True,
    requires_commercial_sdk=True,
    adapter_license=AdapterLicense.VENDOR_API,
    notes=(
        "SolidWorks native format (.sldprt/.sldasm/.slddrw). "
        "Requires SolidWorks API (SOLIDWORKS installed) or eDrawings SDK."
    ),
)

CATIA_DESCRIPTOR = FormatDescriptor(
    format_id="CATPART",
    canonical_name="CATIA V5/V6",
    family=FormatFamily.NATIVE_CAD,
    extensions=("catpart", "catproduct", "catdrawing"),
    media_types=(),
    vendor="Dassault Systèmes",
    is_open=False,
    is_proprietary=True,
    requires_commercial_sdk=True,
    adapter_license=AdapterLicense.VENDOR_API,
    notes=(
        "CATIA V5/V6 native format. Requires CATIA CAA V5 API or "
        "Datakit CrossManager."
    ),
)

NX_DESCRIPTOR = FormatDescriptor(
    format_id="PRT-NX",
    canonical_name="Siemens NX Part",
    family=FormatFamily.NATIVE_CAD,
    extensions=("prt",),
    media_types=(),
    vendor="Siemens",
    is_open=False,
    is_proprietary=True,
    requires_commercial_sdk=True,
    adapter_license=AdapterLicense.VENDOR_API,
    notes=(
        "Siemens NX/Unigraphics .prt format. Requires NX Open API "
        "or Datakit CrossManager."
    ),
)

CREO_DESCRIPTOR = FormatDescriptor(
    format_id="PRT-CREO",
    canonical_name="Creo / Pro/ENGINEER Part",
    family=FormatFamily.NATIVE_CAD,
    extensions=("prt", "asm", "drw"),
    media_types=(),
    vendor="PTC",
    is_open=False,
    is_proprietary=True,
    requires_commercial_sdk=True,
    adapter_license=AdapterLicense.VENDOR_API,
    notes=(
        "PTC Creo / Pro/ENGINEER native format. "
        "Requires Creo Parametric API or Datakit CrossManager."
    ),
)


# ---------------------------------------------------------------------------
# Stub base class
# ---------------------------------------------------------------------------

class _OptionalAdapterStub(FormatAdapter):
    """Base for optional commercial/vendor adapter stubs.

    Returns LEVEL_0_RECOGNIZED with an explicit UNSUPPORTED fidelity event
    so downstream code has a documented, traceable failure record.

    Subclasses override _ADAPTER_ID, _ADAPTER_NAME, _FORMAT_IDS,
    _DESCRIPTOR, _EXTENSIONS, _INSTALL_HINT, and _LICENSE.
    """

    _ADAPTER_ID: str
    _ADAPTER_NAME: str
    _ADAPTER_VERSION: str = "1.0.0"
    _FORMAT_IDS: tuple[str, ...]
    _DESCRIPTOR: FormatDescriptor
    _EXTENSIONS: frozenset[str]
    _INSTALL_HINT: str
    _LICENSE: AdapterLicense

    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            adapter_id=self._ADAPTER_ID,
            adapter_name=self._ADAPTER_NAME,
            adapter_version=self._ADAPTER_VERSION,
            format_ids=self._FORMAT_IDS,
            capabilities=(AdapterCapability.RECOGNIZE,),
            max_capability_level=CapabilityLevel.LEVEL_0_RECOGNIZED,
            adapter_license=self._LICENSE,
            requires_external_dependency=True,
            external_dependency_name=self._INSTALL_HINT,
            notes=(
                f"Stub adapter — {self._INSTALL_HINT} required for full ingestion. "
                "Returns UNSUPPORTED until replaced with a vendor-SDK implementation."
            ),
        )

    def can_handle(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor | None = None,
    ) -> bool:
        if source.source_format_id in self._FORMAT_IDS:
            return True
        if format_descriptor and format_descriptor.format_id in self._FORMAT_IDS:
            return True
        if source.file_name:
            ext = source.file_name.rsplit(".", 1)[-1].lower() if "." in source.file_name else ""
            if ext in self._EXTENSIONS:
                return True
        return False

    def ingest(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
    ) -> CanonicalDocument:
        return self._ingest_stub(source, format_descriptor)

    def ingest_file(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
        content_path: Path,
    ) -> CanonicalDocument:
        return self._ingest_stub(source, format_descriptor)

    def _ingest_stub(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
    ) -> CanonicalDocument:
        session = AdapterSession(source, format_descriptor, self.metadata())
        session.mark_unsupported()
        session.record_unsupported(
            f"{format_descriptor.canonical_name} ingestion requires "
            f"{self._INSTALL_HINT}. "
            f"Install the SDK and replace this stub with a full adapter. "
            f"Adapter ID: {self._ADAPTER_ID}"
        )
        session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)

        ref = CanonicalEntityRef(
            entity_id=make_uid("STUB-"),
            entity_kind="UnsupportedFormatPlaceholder",
            metadata={
                "format_id": format_descriptor.format_id,
                "stub_adapter_id": self._ADAPTER_ID,
                "install_hint": self._INSTALL_HINT,
            },
        )
        session.add_entity_ref(ref)
        return session.build()


# ---------------------------------------------------------------------------
# Concrete stub adapters
# ---------------------------------------------------------------------------

class DwgAdapterStub(_OptionalAdapterStub):
    _ADAPTER_ID = "machinerypro-dwg-stub-v1"
    _ADAPTER_NAME = "MachineryPro DWG Adapter (Stub)"
    _FORMAT_IDS = ("DWG",)
    _DESCRIPTOR = DWG_DESCRIPTOR
    _EXTENSIONS = frozenset(("dwg",))
    _INSTALL_HINT = "ODA File Converter or ezdxf commercial DWG reader"
    _LICENSE = AdapterLicense.COMMERCIAL_SDK


class ParasolidAdapterStub(_OptionalAdapterStub):
    _ADAPTER_ID = "machinerypro-parasolid-stub-v1"
    _ADAPTER_NAME = "MachineryPro Parasolid XT Adapter (Stub)"
    _FORMAT_IDS = ("PARASOLID-XT",)
    _DESCRIPTOR = PARASOLID_DESCRIPTOR
    _EXTENSIONS = frozenset(("x_t", "x_b", "xmt_txt", "xmt_bin"))
    _INSTALL_HINT = "Siemens Parasolid SDK"
    _LICENSE = AdapterLicense.COMMERCIAL_SDK


class AcisAdapterStub(_OptionalAdapterStub):
    _ADAPTER_ID = "machinerypro-acis-stub-v1"
    _ADAPTER_NAME = "MachineryPro ACIS SAT/SAB Adapter (Stub)"
    _FORMAT_IDS = ("ACIS-SAT",)
    _DESCRIPTOR = ACIS_DESCRIPTOR
    _EXTENSIONS = frozenset(("sat", "sab"))
    _INSTALL_HINT = "Spatial 3D ACIS Modeler SDK or Autodesk Platform SDK"
    _LICENSE = AdapterLicense.COMMERCIAL_SDK


class JtAdapterStub(_OptionalAdapterStub):
    _ADAPTER_ID = "machinerypro-jt-stub-v1"
    _ADAPTER_NAME = "MachineryPro JT Adapter (Stub)"
    _FORMAT_IDS = ("JT",)
    _DESCRIPTOR = JT_DESCRIPTOR
    _EXTENSIONS = frozenset(("jt",))
    _INSTALL_HINT = "Siemens JT Open Toolkit or Datakit CrossManager"
    _LICENSE = AdapterLicense.COMMERCIAL_SDK


class SolidWorksAdapterStub(_OptionalAdapterStub):
    _ADAPTER_ID = "machinerypro-solidworks-stub-v1"
    _ADAPTER_NAME = "MachineryPro SolidWorks Adapter (Stub)"
    _FORMAT_IDS = ("SLDPRT",)
    _DESCRIPTOR = SOLIDWORKS_DESCRIPTOR
    _EXTENSIONS = frozenset(("sldprt", "sldasm", "slddrw"))
    _INSTALL_HINT = "SolidWorks API (SOLIDWORKS installed) or eDrawings SDK"
    _LICENSE = AdapterLicense.VENDOR_API


class CatiaAdapterStub(_OptionalAdapterStub):
    _ADAPTER_ID = "machinerypro-catia-stub-v1"
    _ADAPTER_NAME = "MachineryPro CATIA V5/V6 Adapter (Stub)"
    _FORMAT_IDS = ("CATPART",)
    _DESCRIPTOR = CATIA_DESCRIPTOR
    _EXTENSIONS = frozenset(("catpart", "catproduct", "catdrawing"))
    _INSTALL_HINT = "CATIA CAA V5 API or Datakit CrossManager"
    _LICENSE = AdapterLicense.VENDOR_API


class NxAdapterStub(_OptionalAdapterStub):
    _ADAPTER_ID = "machinerypro-nx-stub-v1"
    _ADAPTER_NAME = "MachineryPro Siemens NX Adapter (Stub)"
    _FORMAT_IDS = ("PRT-NX",)
    _DESCRIPTOR = NX_DESCRIPTOR
    _EXTENSIONS = frozenset(("prt",))
    _INSTALL_HINT = "Siemens NX Open API or Datakit CrossManager"
    _LICENSE = AdapterLicense.VENDOR_API


class CreoAdapterStub(_OptionalAdapterStub):
    _ADAPTER_ID = "machinerypro-creo-stub-v1"
    _ADAPTER_NAME = "MachineryPro Creo/Pro-E Adapter (Stub)"
    _FORMAT_IDS = ("PRT-CREO",)
    _DESCRIPTOR = CREO_DESCRIPTOR
    _EXTENSIONS = frozenset(("prt", "asm", "drw"))
    _INSTALL_HINT = "PTC Creo Parametric API or Datakit CrossManager"
    _LICENSE = AdapterLicense.VENDOR_API


# ---------------------------------------------------------------------------
# Optional registry factory
# ---------------------------------------------------------------------------

def build_optional_adapter_registry() -> AdapterRegistry:
    """Create an AdapterRegistry with all optional commercial/vendor stubs.

    Returns a registry separate from the default one.  Deployments that
    install vendor SDKs replace stubs with full adapter implementations.
    """
    from backend.interoperability.registry import AdapterRegistry

    registry = AdapterRegistry()
    for stub_cls in (
        DwgAdapterStub,
        ParasolidAdapterStub,
        AcisAdapterStub,
        JtAdapterStub,
        SolidWorksAdapterStub,
        CatiaAdapterStub,
        NxAdapterStub,
        CreoAdapterStub,
    ):
        registry.register(stub_cls())
    return registry
