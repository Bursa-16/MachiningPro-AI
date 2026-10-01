"""Universal Engineering Interoperability Foundation for MachineryPro AI.

Stage 4A \u2014 establishes vendor-neutral contracts, data structures, adapter
interfaces, format capability model, source identity model, canonical-document
envelope, and conversion-fidelity semantics required by all future
CAD/CAM/CAE/drawing/PMI/NC ingestion stages.

Product-level interoperability principle (exact statement):

    "MachineryPro AI shall ingest, normalize, analyze, validate, compare and,
    where technically possible, convert the widest practical range of CAD,
    CAM, CAE, drawing, PMI and CNC/NC engineering formats without tying
    manufacturing intelligence to any single vendor format."

Non-negotiable fidelity principle (exact statement):

    "No adapter may silently downgrade engineering semantics. Any loss,
    inference, reconstruction, unsupported semantic, or confidence reduction
    must be explicitly represented in fidelity metadata."

Architecture pipeline::

    SOURCE FILE / ENGINEERING SOURCE
        \u2193
    FormatAdapter / parser (Stage 4B+)
        \u2193
    Canonical Engineering Representation (CER)   \u2190 this package
        \u2193
    Canonical Geometry / Topology (Stage 4B)
        \u2193
    Semantic Normalization (Stage 4D+)
        \u2193
    MachineryPro domain models (Stages 3A\u20133J)
        \u2193
    Deterministic engineering analysis
        \u2193
    Validation / comparison (Stage 4L+)
        \u2193
    Export / conversion + fidelity report (Stage 4M)

Vendor independence
-------------------
This package imports zero external dependencies beyond the Python stdlib
and the MachineryPro domain layer.  Commercial/native adapters for CATIA,
NX, SolidWorks, Parasolid, Mastercam, etc. are optional plugins; the
core interoperability package functions without them.

Exports
  Enums (Stage 4A): :class:`FormatFamily`, :class:`AdapterCapability`,
:class:`CapabilityLevel`, :class:`AdapterLicense`, :class:`FidelityClass`,
:class:`FidelityReportCompleteness`, :class:`NormalizationStatus`

Models (Stage 4A): :class:`EngineeringSource`, :class:`FormatDescriptor`,
:class:`AdapterMetadata`, :class:`CanonicalEntityRef`,
:class:`FidelityEvent`, :class:`ConversionFidelityReport`,
:class:`CanonicalDocument`

Adapter interface: :class:`FormatAdapter`

Registry: :class:`AdapterRegistry`, :class:`AdapterRegistryError`

Stage 4B \u2014 Canonical geometry / topology:

Enums (Stage 4B): :class:`CanonicalCurveType`, :class:`CanonicalSurfaceType`,
:class:`Orientation`, :class:`LoopType`, :class:`ShellClosure`,
:class:`BodyType`

Geometry models (Stage 4B): :class:`CanonicalPoint3D`,
:class:`CanonicalVector3D`, :class:`BoundingBox3D`, :class:`CanonicalCurve`,
:class:`CanonicalSurface`, :class:`CanonicalGeometry`

Topology models (Stage 4B): :class:`CanonicalVertex`, :class:`CanonicalEdge`,
:class:`CanonicalLoop`, :class:`CanonicalFace`, :class:`CanonicalShell`,
:class:`CanonicalBody`, :class:`Transform3D`, :class:`CanonicalTopology`
"""

from backend.interoperability.adapter import FormatAdapter
from backend.interoperability.enums import (
    AdapterCapability,
    AdapterLicense,
    CapabilityLevel,
    FidelityClass,
    FidelityReportCompleteness,
    FormatFamily,
    NormalizationStatus,
)
from backend.interoperability.geometry import (
    BoundingBox3D,
    CanonicalCurve,
    CanonicalCurveType,
    CanonicalGeometry,
    CanonicalPoint3D,
    CanonicalSurface,
    CanonicalSurfaceType,
    CanonicalVector3D,
    GeometryContainerError,
)
from backend.interoperability.models import (
    AdapterMetadata,
    CanonicalDocument,
    CanonicalEntityRef,
    ConversionFidelityReport,
    EngineeringSource,
    FidelityEvent,
    FormatDescriptor,
)
from backend.interoperability.registry import AdapterRegistry, AdapterRegistryError
from backend.interoperability.topology import (
    BodyType,
    CanonicalBody,
    CanonicalEdge,
    CanonicalFace,
    CanonicalLoop,
    CanonicalShell,
    CanonicalTopology,
    CanonicalVertex,
    LoopType,
    Orientation,
    ShellClosure,
    TopologyContainerError,
    Transform3D,
)

__all__ = [
    # Enums (Stage 4A)
    "AdapterCapability",
    "AdapterLicense",
    "CapabilityLevel",
    "FidelityClass",
    "FidelityReportCompleteness",
    "FormatFamily",
    "NormalizationStatus",
    # Models (Stage 4A)
    "AdapterMetadata",
    "CanonicalDocument",
    "CanonicalEntityRef",
    "ConversionFidelityReport",
    "EngineeringSource",
    "FidelityEvent",
    "FormatDescriptor",
    # Adapter
    "FormatAdapter",
    # Registry
    "AdapterRegistry",
    "AdapterRegistryError",
    # Stage 4B enums
    "BodyType",
    "CanonicalCurveType",
    "CanonicalSurfaceType",
    "LoopType",
    "Orientation",
    "ShellClosure",
    # Stage 4B geometry
    "BoundingBox3D",
    "CanonicalCurve",
    "CanonicalGeometry",
    "CanonicalPoint3D",
    "CanonicalSurface",
    "CanonicalVector3D",
    "GeometryContainerError",
    # Stage 4B topology
    "CanonicalBody",
    "CanonicalEdge",
    "CanonicalFace",
    "CanonicalLoop",
    "CanonicalShell",
    "CanonicalTopology",
    "CanonicalVertex",
    "TopologyContainerError",
    "Transform3D",
]
