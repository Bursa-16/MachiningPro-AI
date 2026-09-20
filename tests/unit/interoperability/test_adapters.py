"""Stage 4C: Built-in format adapter tests.

All tests are pure-Python — no pythonocc-core or ezdxf required.
Tests verify: format detection, Level 0/1 parsing, fidelity reporting,
fail-closed on corrupt/empty input, registry integration, and graceful
degradation when optional dependencies are absent.

Synthetic STEP/IGES/DXF content is minimal but structurally valid for
Level 1 parsing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.interoperability.adapters._base import ContentSniffer
from backend.interoperability.adapters.dxf import DXF_DESCRIPTOR, DxfTokenAdapter
from backend.interoperability.adapters.iges import IGES_DESCRIPTOR, IgesTokenAdapter
from backend.interoperability.adapters.registry_helpers import (
    build_default_adapter_registry,
)
from backend.interoperability.adapters.step import (
    STEP_AP203,
    STEP_AP242,
    STEP_GENERIC,
    StepTokenAdapter,
)
from backend.interoperability.enums import (
    AdapterCapability,
    CapabilityLevel,
    FidelityClass,
    FidelityReportCompleteness,
    NormalizationStatus,
)
from backend.interoperability.models import (
    CanonicalDocument,
    EngineeringSource,
)

# ---------------------------------------------------------------------------
# Synthetic test content
# ---------------------------------------------------------------------------

_STEP_AP242_MINIMAL = """\
ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('MachineryPro test fixture'),'2;1');
FILE_NAME('bracket.stp','2026-09-05','','','','','');
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF { 1 0 10303 442 1 1 4 }'));
ENDSEC;
DATA;
#1 = PRODUCT('Bracket','Bracket','$',(#2));
#2 = PRODUCT_CONTEXT('$',#3,'mechanical');
#3 = APPLICATION_CONTEXT('mechanical design');
ENDSEC;
END-ISO-10303-21;
"""

_STEP_AP203_MINIMAL = """\
ISO-10303-21;
HEADER;
FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'));
ENDSEC;
DATA;
#1 = PRODUCT('Part','Part','$',(#2));
ENDSEC;
END-ISO-10303-21;
"""

_STEP_CORRUPT = """\
NOT-A-STEP-FILE;
This is not valid STEP content.
"""

_IGES_MINIMAL = (
    # S-section (72 chars + code)
    "S" + " " * 71 + "S" + "      1\n"
    # G-section (global)
    "1H;,1H;,11Htest.iges  ,11Htest.iges  ,8,38,6,308,15,11Htest.iges;G      1\n"
    # D-section (entry for a LINE entity, type 110 — two lines per entry)
    "     110       1       0       0       0       0       0       0       0D      1\n"
    "     110       0       0       1       0       0       0               0D      2\n"
    # P-section
    "110,0.,0.,0.,1.,0.,0.;                                                 P      1\n"
    # T-section (terminator)
    "S      1G      1D      2P      1                                        T      1\n"
)

_IGES_INVALID = "This is not IGES content at all.\n"

_DXF_MINIMAL = """\
  0
SECTION
  2
HEADER
  9
$ACADVER
  1
AC1015
  0
ENDSEC
  0
SECTION
  2
ENTITIES
  0
LINE
  8
0
 10
0.0
 20
0.0
 30
0.0
 11
100.0
 21
100.0
 31
0.0
  0
CIRCLE
  8
Layer1
 10
50.0
 20
50.0
 30
0.0
 40
25.0
  0
ENDSEC
  0
EOF
"""

_DXF_INVALID = "This is not DXF content.\n"


# ---------------------------------------------------------------------------
# A. ContentSniffer
# ---------------------------------------------------------------------------

class TestContentSniffer:
    def test_sniffs_step_ap242(self) -> None:
        sample = b"ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('AP242_MIM'))"
        assert ContentSniffer.sniff(sample) == "STEP-AP242"

    def test_sniffs_step_generic(self) -> None:
        sample = b"ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('UNKNOWN'));"
        assert ContentSniffer.sniff(sample) == "STEP-GENERIC"

    def test_sniffs_dxf(self) -> None:
        sample = b"  0\nSECTION\n  2\nHEADER\n"
        assert ContentSniffer.sniff(sample) == "DXF"

    def test_unknown_returns_none(self) -> None:
        assert ContentSniffer.sniff(b"not any known format") is None

    def test_empty_bytes_returns_none(self) -> None:
        assert ContentSniffer.sniff(b"") is None


# ---------------------------------------------------------------------------
# B. StepTokenAdapter
# ---------------------------------------------------------------------------

class TestStepTokenAdapter:
    def _adapter(self) -> StepTokenAdapter:
        return StepTokenAdapter()

    def _source(self, content: str, fmt: str = "STEP-AP242") -> EngineeringSource:
        return EngineeringSource(
            source_id="SRC-001",
            source_format_id=fmt,
            file_name="bracket.stp",
            notes=content,  # content transport for testing
        )

    # Detection
    def test_can_handle_step_ap242_format_id(self) -> None:
        assert self._adapter().can_handle(self._source("x", "STEP-AP242"))

    def test_can_handle_step_ap203_format_id(self) -> None:
        assert self._adapter().can_handle(self._source("x", "STEP-AP203"))

    def test_can_handle_by_extension(self) -> None:
        source = EngineeringSource(source_id="SRC-X", file_name="part.stp")
        assert self._adapter().can_handle(source)

    def test_cannot_handle_dxf(self) -> None:
        source = EngineeringSource(source_id="SRC-X", source_format_id="DXF",
                                   file_name="part.dxf")
        assert not self._adapter().can_handle(source)

    # Metadata
    def test_metadata_adapter_id(self) -> None:
        assert self._adapter().metadata().adapter_id == "machinerypro-step-token-v1"

    def test_metadata_has_recognize_capability(self) -> None:
        assert self._adapter().metadata().supports_capability(AdapterCapability.RECOGNIZE)

    def test_metadata_has_parse_capability(self) -> None:
        assert self._adapter().metadata().supports_capability(AdapterCapability.PARSE)

    def test_metadata_format_ids_include_ap242(self) -> None:
        assert self._adapter().metadata().supports_format("STEP-AP242")

    # Level 1 ingestion
    def test_ingest_ap242_level1(self) -> None:
        adapter = self._adapter()
        doc = adapter.ingest(self._source(_STEP_AP242_MINIMAL), STEP_AP242)
        assert isinstance(doc, CanonicalDocument)
        assert doc.capability_level in (
            CapabilityLevel.LEVEL_1_PARSED,
            CapabilityLevel.LEVEL_2_NORMALIZED,
        )
        assert doc.normalization_status is NormalizationStatus.SUCCESS

    def test_ingest_ap242_has_fidelity_report(self) -> None:
        doc = self._adapter().ingest(self._source(_STEP_AP242_MINIMAL), STEP_AP242)
        assert doc.fidelity_report is not None
        assert doc.fidelity_report.source_format_id == "STEP-AP242"

    def test_ingest_ap242_entity_count(self) -> None:
        doc = self._adapter().ingest(self._source(_STEP_AP242_MINIMAL), STEP_AP242)
        # 3 entities in DATA section
        assert doc.fidelity_report.source_entity_count == 3

    def test_ingest_ap242_has_header_ref(self) -> None:
        doc = self._adapter().ingest(self._source(_STEP_AP242_MINIMAL), STEP_AP242)
        kinds = [r.entity_kind for r in doc.entity_refs]
        assert "StepHeader" in kinds

    def test_ingest_ap203_succeeds(self) -> None:
        doc = self._adapter().ingest(self._source(_STEP_AP203_MINIMAL, "STEP-AP203"), STEP_AP203)
        assert doc.normalization_status is NormalizationStatus.SUCCESS

    def test_ingest_corrupt_fails_closed(self) -> None:
        doc = self._adapter().ingest(self._source(_STEP_CORRUPT), STEP_GENERIC)
        assert doc.normalization_status is NormalizationStatus.FAILED
        assert any(e.fidelity_class is FidelityClass.LOST for e in doc.fidelity_report.events)

    def test_ingest_no_content_fails_closed(self) -> None:
        source = EngineeringSource(source_id="SRC-X", source_format_id="STEP-AP242",
                                   file_name="empty.stp")
        doc = self._adapter().ingest(source, STEP_AP242)
        assert doc.normalization_status is NormalizationStatus.FAILED

    def test_ingest_without_occt_records_unsupported(self) -> None:
        """Without pythonocc-core, geometry normalization is recorded UNSUPPORTED."""
        adapter = self._adapter()
        if adapter._occt_available():
            pytest.skip("pythonocc-core is installed; this test covers the absent case")
        doc = adapter.ingest(self._source(_STEP_AP242_MINIMAL), STEP_AP242)
        unsupported = [
            e for e in doc.fidelity_report.events
            if e.fidelity_class is FidelityClass.UNSUPPORTED
        ]
        assert unsupported, "Must record UNSUPPORTED when pythonocc-core is absent"

    def test_ingest_result_is_canonical_document(self) -> None:
        doc = self._adapter().ingest(self._source(_STEP_AP242_MINIMAL), STEP_AP242)
        assert isinstance(doc, CanonicalDocument)

    def test_ingest_document_has_source(self) -> None:
        source = self._source(_STEP_AP242_MINIMAL)
        doc = self._adapter().ingest(source, STEP_AP242)
        assert doc.source.source_id == "SRC-001"

    def test_ingest_is_deterministic(self) -> None:
        adapter = self._adapter()
        source = self._source(_STEP_AP242_MINIMAL)
        d1 = adapter.ingest(source, STEP_AP242)
        d2 = adapter.ingest(source, STEP_AP242)
        assert d1.normalization_status == d2.normalization_status
        assert d1.capability_level == d2.capability_level


# ---------------------------------------------------------------------------
# C. IgesTokenAdapter
# ---------------------------------------------------------------------------

class TestIgesTokenAdapter:
    def _adapter(self) -> IgesTokenAdapter:
        return IgesTokenAdapter()

    def _source(self, content: str) -> EngineeringSource:
        return EngineeringSource(
            source_id="SRC-IGES-001",
            source_format_id="IGES",
            file_name="part.igs",
            notes=content,
        )

    def test_can_handle_igs_extension(self) -> None:
        source = EngineeringSource(source_id="SRC-X", file_name="part.igs")
        assert self._adapter().can_handle(source)

    def test_can_handle_iges_extension(self) -> None:
        source = EngineeringSource(source_id="SRC-X", file_name="part.iges")
        assert self._adapter().can_handle(source)

    def test_cannot_handle_step(self) -> None:
        source = EngineeringSource(source_id="SRC-X", source_format_id="STEP-AP242",
                                   file_name="part.stp")
        assert not self._adapter().can_handle(source)

    def test_metadata_adapter_id(self) -> None:
        assert self._adapter().metadata().adapter_id == "machinerypro-iges-token-v1"

    def test_metadata_max_level_is_parsed(self) -> None:
        assert self._adapter().metadata().max_capability_level is CapabilityLevel.LEVEL_1_PARSED

    def test_ingest_minimal_iges_level1(self) -> None:
        doc = self._adapter().ingest(self._source(_IGES_MINIMAL), IGES_DESCRIPTOR)
        assert doc.normalization_status is NormalizationStatus.SUCCESS
        assert doc.capability_level is CapabilityLevel.LEVEL_1_PARSED

    def test_ingest_iges_has_header_ref(self) -> None:
        doc = self._adapter().ingest(self._source(_IGES_MINIMAL), IGES_DESCRIPTOR)
        kinds = [r.entity_kind for r in doc.entity_refs]
        assert "IgesHeader" in kinds

    def test_ingest_iges_entity_count(self) -> None:
        doc = self._adapter().ingest(self._source(_IGES_MINIMAL), IGES_DESCRIPTOR)
        assert doc.fidelity_report.source_entity_count == 1  # one LINE entity

    def test_ingest_iges_records_unsupported_for_geometry(self) -> None:
        doc = self._adapter().ingest(self._source(_IGES_MINIMAL), IGES_DESCRIPTOR)
        unsupported = [
            e for e in doc.fidelity_report.events
            if e.fidelity_class is FidelityClass.UNSUPPORTED
        ]
        assert unsupported

    def test_ingest_invalid_iges_fails_closed(self) -> None:
        doc = self._adapter().ingest(self._source(_IGES_INVALID), IGES_DESCRIPTOR)
        assert doc.normalization_status is NormalizationStatus.FAILED

    def test_ingest_no_content_fails_closed(self) -> None:
        source = EngineeringSource(source_id="SRC-X", source_format_id="IGES")
        doc = self._adapter().ingest(source, IGES_DESCRIPTOR)
        assert doc.normalization_status is NormalizationStatus.FAILED

    def test_ingest_fidelity_completeness_is_partial(self) -> None:
        doc = self._adapter().ingest(self._source(_IGES_MINIMAL), IGES_DESCRIPTOR)
        assert doc.fidelity_report.completeness is FidelityReportCompleteness.PARTIAL

    def test_ingest_not_lossless(self) -> None:
        """IGES Level 1 is inherently partial; is_lossless must be False."""
        doc = self._adapter().ingest(self._source(_IGES_MINIMAL), IGES_DESCRIPTOR)
        assert doc.fidelity_report.is_lossless is False


# ---------------------------------------------------------------------------
# D. DxfTokenAdapter
# ---------------------------------------------------------------------------

class TestDxfTokenAdapter:
    def _adapter(self) -> DxfTokenAdapter:
        return DxfTokenAdapter()

    def _source(self, content: str) -> EngineeringSource:
        return EngineeringSource(
            source_id="SRC-DXF-001",
            source_format_id="DXF",
            file_name="drawing.dxf",
            notes=content,
        )

    def test_can_handle_dxf_extension(self) -> None:
        source = EngineeringSource(source_id="SRC-X", file_name="drawing.dxf")
        assert self._adapter().can_handle(source)

    def test_cannot_handle_step(self) -> None:
        source = EngineeringSource(source_id="SRC-X", source_format_id="STEP-AP242")
        assert not self._adapter().can_handle(source)

    def test_metadata_adapter_id(self) -> None:
        assert self._adapter().metadata().adapter_id == "machinerypro-dxf-token-v1"

    def test_ingest_minimal_dxf_level1(self) -> None:
        doc = self._adapter().ingest(self._source(_DXF_MINIMAL), DXF_DESCRIPTOR)
        assert doc.normalization_status in (
            NormalizationStatus.SUCCESS,
            NormalizationStatus.PARTIAL,
        )
        assert doc.capability_level in (
            CapabilityLevel.LEVEL_1_PARSED,
            CapabilityLevel.LEVEL_2_NORMALIZED,
        )

    def test_ingest_dxf_has_header_ref(self) -> None:
        doc = self._adapter().ingest(self._source(_DXF_MINIMAL), DXF_DESCRIPTOR)
        kinds = [r.entity_kind for r in doc.entity_refs]
        assert "DxfHeader" in kinds

    def test_ingest_dxf_entity_count(self) -> None:
        doc = self._adapter().ingest(self._source(_DXF_MINIMAL), DXF_DESCRIPTOR)
        # 1 LINE + 1 CIRCLE = 2
        assert doc.fidelity_report.source_entity_count == 2

    def test_ingest_invalid_dxf_fails_closed(self) -> None:
        doc = self._adapter().ingest(self._source(_DXF_INVALID), DXF_DESCRIPTOR)
        assert doc.normalization_status is NormalizationStatus.FAILED

    def test_ingest_no_content_fails_closed(self) -> None:
        source = EngineeringSource(source_id="SRC-X", source_format_id="DXF")
        doc = self._adapter().ingest(source, DXF_DESCRIPTOR)
        assert doc.normalization_status is NormalizationStatus.FAILED

    def test_ingest_without_ezdxf_records_unsupported(self) -> None:
        adapter = self._adapter()
        if adapter._ezdxf_available():
            pytest.skip("ezdxf is installed; this test covers the absent case")
        doc = adapter.ingest(self._source(_DXF_MINIMAL), DXF_DESCRIPTOR)
        unsupported = [
            e for e in doc.fidelity_report.events
            if e.fidelity_class is FidelityClass.UNSUPPORTED
        ]
        assert unsupported

    def test_ingest_dxf_layer_count_in_header(self) -> None:
        doc = self._adapter().ingest(self._source(_DXF_MINIMAL), DXF_DESCRIPTOR)
        header_ref = next(r for r in doc.entity_refs if r.entity_kind == "DxfHeader")
        assert header_ref.metadata["layer_count"] >= 1


# ---------------------------------------------------------------------------
# E. Complete staged-file ingestion (regression for 512-byte truncation)
# ---------------------------------------------------------------------------

class TestCompleteFileIngestion:
    def test_step_parser_reads_entity_after_byte_512(self, tmp_path: Path) -> None:
        text = _STEP_AP242_MINIMAL.replace(
            "ENDSEC;\nEND-ISO-10303-21;",
            f"/*{'X' * 600}*/\n#999=PRODUCT('POST_512_STEP','','',());\n"
            "ENDSEC;\nEND-ISO-10303-21;",
        )
        path = tmp_path / "complete.step"
        path.write_text(text, encoding="utf-8")
        source = EngineeringSource(
            source_id="SRC-STAGED-STEP",
            source_format_id="STEP-AP242",
            file_name=path.name,
        )

        doc = StepTokenAdapter().ingest_file(source, STEP_AP242, path)

        header = next(ref for ref in doc.entity_refs if ref.entity_kind == "StepHeader")
        assert header.metadata["entity_count"] == 4
        assert doc.source.notes is None

    def test_iges_parser_reads_entity_after_byte_512(self, tmp_path: Path) -> None:
        def record(payload: str, section: str, sequence: int) -> str:
            return f"{payload[:72]:<72}{section}{sequence:7d}\n"

        padding = "".join(record(f"PADDING-{index}", "S", index) for index in range(1, 8))
        text = (
            padding
            + record("1H;,1H;,POST_512_IGES;", "G", 1)
            + record("     314       1       0       0       0       0       0       0", "D", 1)
            + record("     314       0       0       1       0       0       0", "D", 2)
            + record("314,POST_512_IGES;", "P", 1)
            + record("S      7G      1D      2P      1", "T", 1)
        )
        assert text.index("314") > 512
        path = tmp_path / "complete.iges"
        path.write_text(text, encoding="utf-8")
        source = EngineeringSource(
            source_id="SRC-STAGED-IGES",
            source_format_id="IGES",
            file_name=path.name,
        )

        doc = IgesTokenAdapter().ingest_file(source, IGES_DESCRIPTOR, path)

        header = next(ref for ref in doc.entity_refs if ref.entity_kind == "IgesHeader")
        assert header.metadata["entity_type_summary"]["Color Definition"] == 1
        assert doc.source.notes is None

    def test_dxf_parser_reads_entity_after_byte_512(self, tmp_path: Path) -> None:
        padding = "999\n" + ("X" * 600) + "\n"
        text = (
            "  0\nSECTION\n  2\nENTITIES\n"
            + padding
            + "  0\nHELIX\n  8\nPOST_512_DXF\n"
            "  0\nENDSEC\n  0\nEOF\n"
        )
        assert text.index("HELIX") > 512
        path = tmp_path / "complete.dxf"
        path.write_text(text, encoding="utf-8")
        source = EngineeringSource(
            source_id="SRC-STAGED-DXF",
            source_format_id="DXF",
            file_name=path.name,
        )

        doc = DxfTokenAdapter().ingest_file(source, DXF_DESCRIPTOR, path)

        header = next(ref for ref in doc.entity_refs if ref.entity_kind == "DxfHeader")
        assert header.metadata["entity_type_summary"]["HELIX"] == 1
        assert header.metadata["layer_count"] == 1
        assert doc.source.notes is None


# ---------------------------------------------------------------------------
# E. Registry integration
# ---------------------------------------------------------------------------

class TestRegistryIntegration:
    def test_build_default_registry_has_three_adapters(self) -> None:
        registry = build_default_adapter_registry()
        assert len(registry) == 3

    def test_registry_has_step_adapter(self) -> None:
        registry = build_default_adapter_registry()
        assert registry.has("machinerypro-step-token-v1")

    def test_registry_has_iges_adapter(self) -> None:
        registry = build_default_adapter_registry()
        assert registry.has("machinerypro-iges-token-v1")

    def test_registry_has_dxf_adapter(self) -> None:
        registry = build_default_adapter_registry()
        assert registry.has("machinerypro-dxf-token-v1")

    def test_find_by_format_step_ap242(self) -> None:
        registry = build_default_adapter_registry()
        results = registry.find_by_format("STEP-AP242")
        assert len(results) >= 1
        assert any(
            a.metadata().adapter_id == "machinerypro-step-token-v1" for a in results
        )

    def test_find_by_format_iges(self) -> None:
        registry = build_default_adapter_registry()
        results = registry.find_by_format("IGES")
        assert len(results) >= 1

    def test_find_by_format_dxf(self) -> None:
        registry = build_default_adapter_registry()
        results = registry.find_by_format("DXF")
        assert len(results) >= 1

    def test_find_by_capability_recognize(self) -> None:
        registry = build_default_adapter_registry()
        results = registry.find_by_capability(AdapterCapability.RECOGNIZE)
        assert len(results) == 3

    def test_registry_is_not_singleton(self) -> None:
        r1 = build_default_adapter_registry()
        r2 = build_default_adapter_registry()
        r1_ids = set(r1.ids())
        r2_ids = set(r2.ids())
        assert r1_ids == r2_ids  # same content
        assert r1 is not r2  # different instances

    def test_no_automatic_adapter_selection(self) -> None:
        """find_by_format returns all matching adapters; caller selects."""
        registry = build_default_adapter_registry()
        results = registry.find_by_format("STEP-AP242")
        # All STEP results are returned; registry does not auto-select best
        assert isinstance(results, tuple)
        assert len(results) >= 1
