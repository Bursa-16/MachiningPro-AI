"""Controlled-vocabulary enumerations for the interoperability layer (Stage 4A).

All enums are :class:`enum.StrEnum` for JSON-friendly, deterministic
serialization — consistent with the project-wide convention.
"""

from __future__ import annotations

from enum import StrEnum

# ---------------------------------------------------------------------------
# Engineering format families
# ---------------------------------------------------------------------------

class FormatFamily(StrEnum):
    """Top-level engineering format family classification.

    A single file may theoretically belong to more than one family (e.g.
    STEP AP242 carries both CAD geometry and PMI), but a format descriptor
    must declare its primary family.  Secondary capabilities are expressed
    through :class:`AdapterCapability` flags.
    """

    CAD = "CAD"                     # B-Rep / solid / surface geometry
    MESH = "MESH"                   # Triangulated/polygon mesh geometry
    CAM = "CAM"                     # CAM program / toolpath data
    CAE = "CAE"                     # Engineering analysis results
    DRAWING = "DRAWING"             # 2D engineering drawing
    PMI = "PMI"                     # Product/manufacturing information
    NC = "NC"                       # NC / G-code / CNC program
    NEUTRAL_EXCHANGE = "NEUTRAL_EXCHANGE"  # Open exchange formats (STEP, IGES)
    NATIVE_CAD = "NATIVE_CAD"       # Vendor-proprietary CAD
    NATIVE_CAM = "NATIVE_CAM"       # Vendor-proprietary CAM
    IMAGE = "IMAGE"                 # Raster or vector image
    DOCUMENT = "DOCUMENT"           # General engineering document (PDF, etc.)
    UNKNOWN = "UNKNOWN"             # Format family could not be determined


# ---------------------------------------------------------------------------
# Adapter capabilities
# ---------------------------------------------------------------------------

class AdapterCapability(StrEnum):
    """Declarative capability that a format adapter may claim.

    Adapters must only claim capabilities they actually implement.
    The registry does not validate claimed capabilities against behavior;
    capability claims are for discovery and caller decision-making only.
    """

    RECOGNIZE = "RECOGNIZE"                     # Identify the format
    PARSE = "PARSE"                             # Open and read raw data
    NORMALIZE = "NORMALIZE"                     # Place data into CER
    EXTRACT_GEOMETRY = "EXTRACT_GEOMETRY"       # B-rep / solid geometry
    EXTRACT_TOPOLOGY = "EXTRACT_TOPOLOGY"       # Topological structure
    EXTRACT_ASSEMBLY = "EXTRACT_ASSEMBLY"       # Assembly hierarchy
    EXTRACT_PMI = "EXTRACT_PMI"                 # GD&T / tolerances / PMI
    EXTRACT_DRAWING = "EXTRACT_DRAWING"         # 2D drawing semantics
    EXTRACT_CAM = "EXTRACT_CAM"                 # CAM operations / strategies
    EXTRACT_TOOLPATH = "EXTRACT_TOOLPATH"       # Toolpath motion data
    EXTRACT_NC = "EXTRACT_NC"                   # NC/G-code interpretation
    EXTRACT_CAE = "EXTRACT_CAE"                 # CAE result fields
    EXPORT = "EXPORT"                           # Write to target format
    CONVERT = "CONVERT"                         # Cross-format conversion
    COMPARE = "COMPARE"                         # Compare two CER documents


# ---------------------------------------------------------------------------
# Capability levels (maturity / completeness)
# ---------------------------------------------------------------------------

class CapabilityLevel(StrEnum):
    """Engineering interoperability capability maturity levels.

    Levels are cumulative: LEVEL_2 implies LEVEL_0 and LEVEL_1 were reached.
    An adapter reports the highest level it achieves for a given file.

    These levels are defined in the Universal Engineering Interoperability
    Architecture Roadmap and reproduced here as the canonical enum.
    """

    LEVEL_0_RECOGNIZED = "LEVEL_0_RECOGNIZED"
    """File extension and/or magic bytes matched to a known format."""

    LEVEL_1_PARSED = "LEVEL_1_PARSED"
    """File opened and raw data structure read without error."""

    LEVEL_2_NORMALIZED = "LEVEL_2_NORMALIZED"
    """Data placed into Canonical Engineering Representation (CER)."""

    LEVEL_3_ENGINEERING_SEMANTICS = "LEVEL_3_ENGINEERING_SEMANTICS"
    """Engineering meaning extracted: features, tolerances, operations."""

    LEVEL_4_MANUFACTURING_FEATURES = "LEVEL_4_MANUFACTURING_FEATURES"
    """Manufacturing features identified from geometry / topology."""

    LEVEL_5_PROCESS_CONTENT = "LEVEL_5_PROCESS_CONTENT"
    """CAM operations, setup, toolpath, or NC motion interpreted."""

    LEVEL_6_ENGINEERING_VALIDATED = "LEVEL_6_ENGINEERING_VALIDATED"
    """Data validated against MachineryPro engineering models."""

    LEVEL_7_CONVERTED_WITH_FIDELITY_REPORT = "LEVEL_7_CONVERTED_WITH_FIDELITY_REPORT"
    """Data exported to target format with Conversion Fidelity Report."""


# ---------------------------------------------------------------------------
# Adapter licensing model
# ---------------------------------------------------------------------------

class AdapterLicense(StrEnum):
    """Licensing model of the underlying adapter implementation.

    No commercial license may be required for the MachineryPro core to
    start and operate.  COMMERCIAL_SDK, VENDOR_API, and
    EXTERNAL_CONVERTER adapters are optional plugins.
    """

    OPEN_SOURCE = "OPEN_SOURCE"
    """Adapter implemented using open-source libraries only."""

    INTERNAL_PARSER = "INTERNAL_PARSER"
    """Adapter implemented using only MachineryPro-internal code (no deps)."""

    COMMERCIAL_SDK = "COMMERCIAL_SDK"
    """Requires a third-party commercial translation SDK (e.g. Datakit,
    Spatial, Theorem)."""

    VENDOR_API = "VENDOR_API"
    """Requires vendor-owned CAD/CAM/CAE software to be installed and
    licensed on the same host (e.g. NX Open, SolidWorks API, CATIA CAA)."""

    EXTERNAL_CONVERTER = "EXTERNAL_CONVERTER"
    """Data must first be converted by an external tool before ingestion.
    MachineryPro reads the converter's output, not the native format."""

    CONTROLLER_DIALECT_PLUGIN = "CONTROLLER_DIALECT_PLUGIN"
    """CNC controller-specific dialect normalizer built on top of the
    generic NC parser (no vendor license required unless explicitly noted)."""


# ---------------------------------------------------------------------------
# Fidelity event classes
# ---------------------------------------------------------------------------

class FidelityClass(StrEnum):
    """Classification of a single conversion / normalization fidelity event.

    Every normalization step that does not produce a fully PRESERVED result
    MUST record a fidelity event.  Silent semantic downgrade is prohibited.
    """

    PRESERVED = "PRESERVED"
    """Data transferred completely without loss or change."""

    PARTIALLY_PRESERVED = "PARTIALLY_PRESERVED"
    """Data transferred but with precision reduction or partial information
    loss (e.g. NURBS approximated as polynomial)."""

    LOST = "LOST"
    """Data present in the source but absent in the normalized output."""

    UNSUPPORTED = "UNSUPPORTED"
    """Data type not handled by this adapter; deliberately skipped."""

    INFERRED = "INFERRED"
    """Value not present in source; reconstructed from context, heuristics,
    or engineering knowledge.  May be incorrect."""

    RECONSTRUCTED = "RECONSTRUCTED"
    """Geometry repaired by the adapter (gap filled, self-intersection
    removed, degenerate elements cleaned)."""

    DOWNGRADED = "DOWNGRADED"
    """Semantic content reduced in richness (e.g. parameterized tolerance
    converted to a plain note; B-rep downgraded to mesh)."""


# ---------------------------------------------------------------------------
# Fidelity report completeness
# ---------------------------------------------------------------------------

class FidelityReportCompleteness(StrEnum):
    """Completeness status of a ConversionFidelityReport.

    A report that is not COMPLETE must not claim is_lossless = True.
    """

    COMPLETE = "COMPLETE"
    """All source entities were evaluated for fidelity."""

    PARTIAL = "PARTIAL"
    """Only a subset of source entities was evaluated (e.g. large file,
    streaming parse stopped early)."""

    UNKNOWN = "UNKNOWN"
    """The adapter cannot determine whether all entities were evaluated.
    Fail-closed: is_lossless must be False when completeness is UNKNOWN."""


# ---------------------------------------------------------------------------
# Normalization outcome
# ---------------------------------------------------------------------------

class NormalizationStatus(StrEnum):
    """Outcome of a normalization step (distinct from fidelity).

    Parser success != semantic fidelity.  A file may parse without error
    (SUCCESS) while still having fidelity events (PARTIAL, UNSUPPORTED).
    """

    SUCCESS = "SUCCESS"
    """All mandatory normalization steps completed without error."""

    PARTIAL = "PARTIAL"
    """Normalization completed but some entities could not be processed."""

    UNSUPPORTED = "UNSUPPORTED"
    """The format or its version is recognized but not supported by this
    adapter at the requested capability level."""

    FAILED = "FAILED"
    """A critical error prevented normalization from completing."""

    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    """Required metadata (format version, units, etc.) was absent."""
