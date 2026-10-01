"""Vendor-neutral format adapter interface (Stage 4A).

Defines the abstract base class that all format-specific adapters must
implement.  No vendor logic appears here; adapters for STEP, DXF, Fanuc NC,
Mastercam, etc. are introduced in Stages 4B–4K.

Design principles
-----------------
* Each adapter self-describes its capabilities via :class:`AdapterMetadata`.
* Adapters never communicate directly with MachineryPro domain models
  (Feature, Tool, Machine, etc.).  All output goes into the CER
  (:class:`~backend.interoperability.models.CanonicalDocument`).
* No adapter may silently downgrade engineering semantics.
* The base adapter does not perform format detection; concrete adapters
  implement :meth:`can_handle` to confirm format identity via content
  inspection, not extension alone.
* Commercial/native adapters that require external software must be optional
  plugins.  The MachineryPro core must start without them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from backend.interoperability.models import (
    AdapterMetadata,
    CanonicalDocument,
    EngineeringSource,
    FormatDescriptor,
)

__all__ = ["FormatAdapter"]


class FormatAdapter(ABC):
    """Abstract base class for all engineering format adapters.

    Concrete subclasses implement format-specific ingestion.

    Adapter contract
    ----------------
    Every adapter MUST implement:

    * :meth:`metadata` — return self-description.
    * :meth:`can_handle` — confirm ability to process a specific source.
    * :meth:`ingest` — parse source and return a CanonicalDocument.

    Every adapter SHOULD implement (if it supports export):

    * :meth:`can_export` — confirm export capability for a target format.
    * :meth:`export` — convert a CanonicalDocument to a target format.

    Fail-closed ingestion
    ----------------------
    If any error prevents normalization, :meth:`ingest` must return a
    CanonicalDocument whose normalization_status is FAILED or PARTIAL —
    never silently return an incomplete document with SUCCESS status.

    Vendor independence
    -------------------
    Adapters for proprietary formats (NX, CATIA, SolidWorks, Mastercam,
    Fanuc, etc.) are valid subclasses of FormatAdapter.  The presence of
    commercial adapters in a deployment is a configuration concern, not
    an architecture violation.  However, the MachineryPro core must run
    without any commercial adapter registered.
    """

    @abstractmethod
    def metadata(self) -> AdapterMetadata:
        """Return the adapter's self-declared metadata.

        Called at registration time.  Must be stateless and side-effect-free.
        """

    @abstractmethod
    def can_handle(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor | None = None,
    ) -> bool:
        """Return True when this adapter can process the given source.

        Adapters MUST NOT rely solely on file extension for identification.
        Content sniffing (magic bytes, header inspection) is preferred where
        the source provides accessible bytes.

        When *format_descriptor* is supplied by the caller (from a registry
        lookup), the adapter may trust it as an additional signal but should
        still verify via content inspection when practical.

        Args:
            source:            Identity of the engineering data source.
            format_descriptor: Optional caller-supplied format hint.

        Returns:
            True when this adapter can handle the source.
        """

    @abstractmethod
    def ingest(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
    ) -> CanonicalDocument:
        """Parse *source* and return a CanonicalDocument.

        This is the primary ingestion entry point.

        Requirements:
        - Must return a CanonicalDocument regardless of outcome (success,
          partial, or failure).
        - Must record a ConversionFidelityReport when normalization_status
          is SUCCESS or PARTIAL.
        - Must never claim normalization_status = SUCCESS when entities
          were silently lost or downgraded.
        - Fidelity events for every adverse semantic outcome are mandatory.

        Args:
            source:            Identity and metadata of the data source.
            format_descriptor: Confirmed format descriptor.

        Returns:
            CanonicalDocument with appropriate normalization_status and
            fidelity_report.
        """

    def ingest_file(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
        content_path: Path,
    ) -> CanonicalDocument:
        """Parse a staged file without embedding its content in the source."""
        raise NotImplementedError(
            f"adapter {self.metadata().adapter_id!r} does not support "
            "staged file ingestion"
        )

    def can_export(self, target_format_id: str) -> bool:
        """Return True when this adapter supports export to *target_format_id*.

        Default implementation returns False (read-only adapter).
        Adapters that support export must override this method.

        Args:
            target_format_id: Format ID of the desired export target.
        """
        return False

    def export(
        self,
        document: CanonicalDocument,
        target_format_id: str,
        *,
        options: dict[str, object] | None = None,
    ) -> bytes:
        """Export *document* to *target_format_id*.

        Default implementation raises NotImplementedError.
        Adapters that support export must override this method.

        Returns:
            Raw bytes of the exported file in the target format.

        Raises:
            NotImplementedError: when the adapter does not support export.
        """
        raise NotImplementedError(
            f"adapter {self.metadata().adapter_id!r} does not support export "
            f"to {target_format_id!r}"
        )
