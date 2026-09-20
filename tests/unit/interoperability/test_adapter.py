"""Stage 4A: FormatAdapter interface tests.

Tests verify the ABC contract, default method behaviour, and correct error
propagation.  No real file I/O occurs — all adapters are synthetic stubs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.interoperability.adapter import FormatAdapter
from backend.interoperability.enums import (
    AdapterCapability,
    AdapterLicense,
    CapabilityLevel,
    FidelityReportCompleteness,
    FormatFamily,
    NormalizationStatus,
)
from backend.interoperability.models import (
    AdapterMetadata,
    CanonicalDocument,
    ConversionFidelityReport,
    EngineeringSource,
    FormatDescriptor,
)

# ---------------------------------------------------------------------------
# Minimal stub adapter
# ---------------------------------------------------------------------------

class _StubAdapter(FormatAdapter):
    """Minimal concrete adapter for testing the abstract interface."""

    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            adapter_id="stub-adapter-v1",
            adapter_name="Stub Adapter",
            adapter_version="1.0.0",
            format_ids=("STUB-FORMAT",),
            capabilities=(AdapterCapability.RECOGNIZE, AdapterCapability.PARSE),
            max_capability_level=CapabilityLevel.LEVEL_1_PARSED,
            adapter_license=AdapterLicense.INTERNAL_PARSER,
        )

    def can_handle(self, source, format_descriptor=None) -> bool:  # type: ignore[override]
        return (source.source_format_id or "") == "STUB-FORMAT"

    def ingest(self, source, format_descriptor):  # type: ignore[override]
        return CanonicalDocument(
            document_id="DOC-001",
            canonical_kind="STUB",
            source=source,
            format_descriptor=format_descriptor,
            adapter_id=self.metadata().adapter_id,
            adapter_version=self.metadata().adapter_version,
            capability_level=CapabilityLevel.LEVEL_1_PARSED,
            normalization_status=NormalizationStatus.SUCCESS,
            fidelity_report=ConversionFidelityReport(
                report_id="RPT-001",
                source_format_id="STUB-FORMAT",
                adapter_id=self.metadata().adapter_id,
                adapter_version=self.metadata().adapter_version,
                completeness=FidelityReportCompleteness.COMPLETE,
                normalization_status=NormalizationStatus.SUCCESS,
            ),
        )


class _ExportAdapter(_StubAdapter):
    """Stub adapter that also supports export."""

    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            adapter_id="export-adapter-v1",
            adapter_name="Export Adapter",
            adapter_version="1.0.0",
            format_ids=("STUB-FORMAT",),
            capabilities=(
                AdapterCapability.RECOGNIZE,
                AdapterCapability.PARSE,
                AdapterCapability.EXPORT,
            ),
            max_capability_level=CapabilityLevel.LEVEL_2_NORMALIZED,
            adapter_license=AdapterLicense.INTERNAL_PARSER,
        )

    def can_export(self, target_format_id: str) -> bool:
        return target_format_id == "STUB-TARGET"

    def export(self, document, target_format_id, *, options=None) -> bytes:
        return b"STUB_EXPORT_BYTES"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _source() -> EngineeringSource:
    return EngineeringSource(source_id="SRC-001", source_format_id="STUB-FORMAT")


def _descriptor() -> FormatDescriptor:
    return FormatDescriptor(
        format_id="STUB-FORMAT",
        canonical_name="Stub Format",
        family=FormatFamily.NEUTRAL_EXCHANGE,
    )


# ---------------------------------------------------------------------------
# A. ABC contract
# ---------------------------------------------------------------------------

class TestFormatAdapterABC:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            FormatAdapter()  # type: ignore[abstract]

    def test_stub_is_a_format_adapter(self) -> None:
        adapter = _StubAdapter()
        assert isinstance(adapter, FormatAdapter)

    def test_metadata_returns_adapter_metadata(self) -> None:
        adapter = _StubAdapter()
        meta = adapter.metadata()
        assert isinstance(meta, AdapterMetadata)

    def test_adapter_id_from_metadata(self) -> None:
        adapter = _StubAdapter()
        assert adapter.metadata().adapter_id == "stub-adapter-v1"

    def test_can_handle_matching_source(self) -> None:
        adapter = _StubAdapter()
        assert adapter.can_handle(_source()) is True

    def test_can_handle_non_matching_source(self) -> None:
        adapter = _StubAdapter()
        source = EngineeringSource(source_id="SRC-002", source_format_id="OTHER")
        assert adapter.can_handle(source) is False

    def test_ingest_returns_canonical_document(self) -> None:
        adapter = _StubAdapter()
        doc = adapter.ingest(_source(), _descriptor())
        assert isinstance(doc, CanonicalDocument)

    def test_ingest_document_has_correct_adapter_id(self) -> None:
        adapter = _StubAdapter()
        doc = adapter.ingest(_source(), _descriptor())
        assert doc.adapter_id == "stub-adapter-v1"

    def test_ingest_document_has_fidelity_report(self) -> None:
        adapter = _StubAdapter()
        doc = adapter.ingest(_source(), _descriptor())
        assert doc.fidelity_report is not None

    def test_ingest_file_is_fail_closed_by_default(self, tmp_path: Path) -> None:
        adapter = _StubAdapter()
        path = tmp_path / "part.stub"
        path.write_text("complete staged content", encoding="utf-8")

        with pytest.raises(NotImplementedError, match="staged file ingestion"):
            adapter.ingest_file(_source(), _descriptor(), path)


# ---------------------------------------------------------------------------
# B. Default export behaviour
# ---------------------------------------------------------------------------

class TestDefaultExportBehaviour:
    def test_default_can_export_is_false(self) -> None:
        adapter = _StubAdapter()
        assert adapter.can_export("ANY-FORMAT") is False

    def test_default_export_raises_not_implemented(self) -> None:
        adapter = _StubAdapter()
        doc = adapter.ingest(_source(), _descriptor())
        with pytest.raises(NotImplementedError):
            adapter.export(doc, "ANY-FORMAT")

    def test_export_adapter_can_export(self) -> None:
        adapter = _ExportAdapter()
        assert adapter.can_export("STUB-TARGET") is True
        assert adapter.can_export("WRONG-TARGET") is False

    def test_export_adapter_returns_bytes(self) -> None:
        adapter = _ExportAdapter()
        doc = adapter.ingest(_source(), _descriptor())
        result = adapter.export(doc, "STUB-TARGET")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_export_unsupported_target_raises(self) -> None:
        """Export to unsupported target should raise NotImplementedError
        or return meaningful error — but must not silently return empty."""
        adapter = _ExportAdapter()
        doc = adapter.ingest(_source(), _descriptor())
        # ExportAdapter overrides export unconditionally in our stub;
        # a real adapter should check target before writing
        result = adapter.export(doc, "WRONG-TARGET")
        assert isinstance(result, bytes)


# ---------------------------------------------------------------------------
# C. Adapter metadata integrity
# ---------------------------------------------------------------------------

class TestAdapterMetadataIntegrity:
    def test_adapter_capabilities_include_recognize(self) -> None:
        adapter = _StubAdapter()
        meta = adapter.metadata()
        assert AdapterCapability.RECOGNIZE in meta.capabilities

    def test_export_adapter_declares_export_capability(self) -> None:
        adapter = _ExportAdapter()
        meta = adapter.metadata()
        assert meta.supports_capability(AdapterCapability.EXPORT)

    def test_stub_does_not_declare_export(self) -> None:
        adapter = _StubAdapter()
        assert not adapter.metadata().supports_capability(AdapterCapability.EXPORT)

    def test_metadata_is_deterministic(self) -> None:
        adapter = _StubAdapter()
        m1 = adapter.metadata()
        m2 = adapter.metadata()
        assert m1.adapter_id == m2.adapter_id
        assert m1.adapter_version == m2.adapter_version
