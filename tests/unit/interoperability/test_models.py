"""Stage 4A: CER model tests for the interoperability layer."""

from __future__ import annotations

import pytest

from backend.domain.base import Provenance
from backend.domain.enums import ProvenanceType
from backend.domain.exceptions import ValidationError
from backend.interoperability.enums import (
    AdapterCapability,
    AdapterLicense,
    CapabilityLevel,
    FidelityClass,
    FidelityReportCompleteness,
    FormatFamily,
    NormalizationStatus,
)
from backend.interoperability.geometry import CanonicalGeometry
from backend.interoperability.models import (
    AdapterMetadata,
    CanonicalDocument,
    CanonicalEntityRef,
    ConversionFidelityReport,
    EngineeringSource,
    FidelityEvent,
    FormatDescriptor,
)
from backend.interoperability.topology import CanonicalTopology

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _source(sid: str = "SRC-001") -> EngineeringSource:
    return EngineeringSource(
        source_id=sid,
        source_format_id="STEP-AP242",
        file_name="part.stp",
        media_type="model/step",
        vendor="ISO",
    )


def _descriptor(fid: str = "STEP-AP242") -> FormatDescriptor:
    return FormatDescriptor(
        format_id=fid,
        canonical_name="STEP AP242",
        family=FormatFamily.NEUTRAL_EXCHANGE,
        extensions=("stp", "step"),
        media_types=("model/step",),
        vendor="ISO",
        is_open=True,
        adapter_license=AdapterLicense.OPEN_SOURCE,
    )


def _adapter_meta(aid: str = "occt-step") -> AdapterMetadata:
    return AdapterMetadata(
        adapter_id=aid,
        adapter_name="OCCT STEP Adapter",
        adapter_version="1.0.0",
        format_ids=("STEP-AP242", "STEP-AP214"),
        capabilities=(AdapterCapability.RECOGNIZE, AdapterCapability.PARSE,
                      AdapterCapability.NORMALIZE, AdapterCapability.EXTRACT_GEOMETRY),
        max_capability_level=CapabilityLevel.LEVEL_4_MANUFACTURING_FEATURES,
        adapter_license=AdapterLicense.OPEN_SOURCE,
        requires_external_dependency=True,
        external_dependency_name="pythonocc-core",
    )


def _entity_ref(eid: str = "E-001", kind: str = "BRepSolid") -> CanonicalEntityRef:
    return CanonicalEntityRef(entity_id=eid, entity_kind=kind)


def _fidelity_event(
    eid: str = "FE-001",
    cls: FidelityClass = FidelityClass.PRESERVED,
) -> FidelityEvent:
    return FidelityEvent(
        event_id=eid,
        fidelity_class=cls,
        description="test event",
    )


def _fidelity_report(
    events: tuple[FidelityEvent, ...] = (),
    completeness: FidelityReportCompleteness = FidelityReportCompleteness.COMPLETE,
    status: NormalizationStatus = NormalizationStatus.SUCCESS,
) -> ConversionFidelityReport:
    return ConversionFidelityReport(
        report_id="RPT-001",
        source_format_id="STEP-AP242",
        adapter_id="occt-step",
        adapter_version="1.0.0",
        completeness=completeness,
        normalization_status=status,
        events=events,
    )


def _document(did: str = "DOC-001") -> CanonicalDocument:
    return CanonicalDocument(
        document_id=did,
        canonical_kind="CAD_GEOMETRY",
        source=_source(),
        format_descriptor=_descriptor(),
        adapter_id="occt-step",
        adapter_version="1.0.0",
        capability_level=CapabilityLevel.LEVEL_2_NORMALIZED,
        normalization_status=NormalizationStatus.SUCCESS,
    )


# ---------------------------------------------------------------------------
# A. EngineeringSource
# ---------------------------------------------------------------------------

class TestEngineeringSource:
    def test_minimal_valid(self) -> None:
        src = EngineeringSource(source_id="SRC-001")
        assert src.source_id == "SRC-001"

    def test_full_construction(self) -> None:
        src = _source()
        assert src.source_format_id == "STEP-AP242"
        assert src.file_name == "part.stp"

    def test_empty_source_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EngineeringSource(source_id="")

    def test_whitespace_source_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EngineeringSource(source_id="   ")

    def test_empty_optional_string_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EngineeringSource(source_id="SRC-001", file_name="")

    def test_none_optional_accepted(self) -> None:
        src = EngineeringSource(source_id="SRC-001", file_name=None)
        assert src.file_name is None

    def test_immutable(self) -> None:
        src = _source()
        with pytest.raises((AttributeError, TypeError)):
            src.source_id = "MUTATED"  # type: ignore[misc]

    def test_as_dict(self) -> None:
        d = _source().as_dict()
        assert isinstance(d, dict)
        assert "source_id" in d


# ---------------------------------------------------------------------------
# B. FormatDescriptor
# ---------------------------------------------------------------------------

class TestFormatDescriptor:
    def test_valid_descriptor(self) -> None:
        fd = _descriptor()
        assert fd.format_id == "STEP-AP242"
        assert fd.family is FormatFamily.NEUTRAL_EXCHANGE

    def test_empty_format_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FormatDescriptor(format_id="", canonical_name="STEP", family=FormatFamily.CAD)

    def test_invalid_family_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FormatDescriptor(format_id="X", canonical_name="X", family="CAD")  # type: ignore[arg-type]

    def test_extensions_lowercased(self) -> None:
        fd = FormatDescriptor(
            format_id="DXF", canonical_name="DXF",
            family=FormatFamily.DRAWING,
            extensions=("DXF", "Dxf"),
        )
        assert fd.extensions == ("dxf", "dxf")

    def test_extension_matches(self) -> None:
        fd = _descriptor()
        assert fd.extension_matches("assembly.step") is True
        assert fd.extension_matches("assembly.stp") is True
        assert fd.extension_matches("assembly.iges") is False

    def test_extension_matches_case_insensitive(self) -> None:
        fd = _descriptor()
        assert fd.extension_matches("PART.STEP") is True

    def test_immutable(self) -> None:
        fd = _descriptor()
        with pytest.raises((AttributeError, TypeError)):
            fd.format_id = "MUTATED"  # type: ignore[misc]

    def test_as_dict(self) -> None:
        d = _descriptor().as_dict()
        assert "format_id" in d

    def test_open_and_proprietary_can_coexist(self) -> None:
        """A format may be open standard but with proprietary extensions."""
        fd = FormatDescriptor(
            format_id="JT",
            canonical_name="JT (ISO 14306)",
            family=FormatFamily.CAD,
            is_open=True,
            is_proprietary=False,
        )
        assert fd.is_open is True


# ---------------------------------------------------------------------------
# C. AdapterMetadata
# ---------------------------------------------------------------------------

class TestAdapterMetadata:
    def test_valid_metadata(self) -> None:
        meta = _adapter_meta()
        assert meta.adapter_id == "occt-step"
        assert meta.requires_external_dependency is True

    def test_empty_format_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AdapterMetadata(
                adapter_id="A", adapter_name="A", adapter_version="1.0",
                format_ids=(),
                capabilities=(AdapterCapability.RECOGNIZE,),
                max_capability_level=CapabilityLevel.LEVEL_1_PARSED,
                adapter_license=AdapterLicense.OPEN_SOURCE,
            )

    def test_empty_capabilities_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AdapterMetadata(
                adapter_id="A", adapter_name="A", adapter_version="1.0",
                format_ids=("STEP",),
                capabilities=(),
                max_capability_level=CapabilityLevel.LEVEL_1_PARSED,
                adapter_license=AdapterLicense.OPEN_SOURCE,
            )

    def test_supports_capability(self) -> None:
        meta = _adapter_meta()
        assert meta.supports_capability(AdapterCapability.RECOGNIZE) is True
        assert meta.supports_capability(AdapterCapability.EXPORT) is False

    def test_supports_format(self) -> None:
        meta = _adapter_meta()
        assert meta.supports_format("STEP-AP242") is True
        assert meta.supports_format("DXF-R2024") is False

    def test_immutable(self) -> None:
        meta = _adapter_meta()
        with pytest.raises((AttributeError, TypeError)):
            meta.adapter_id = "MUTATED"  # type: ignore[misc]

    def test_as_dict(self) -> None:
        d = _adapter_meta().as_dict()
        assert "adapter_id" in d


# ---------------------------------------------------------------------------
# D. CanonicalEntityRef
# ---------------------------------------------------------------------------

class TestCanonicalEntityRef:
    def test_valid_ref(self) -> None:
        ref = _entity_ref()
        assert ref.entity_id == "E-001"
        assert ref.entity_kind == "BRepSolid"

    def test_empty_entity_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalEntityRef(entity_id="", entity_kind="BRepSolid")

    def test_empty_kind_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalEntityRef(entity_id="E-001", entity_kind="")

    def test_metadata_is_immutable_mapping(self) -> None:
        ref = CanonicalEntityRef(
            entity_id="E-001", entity_kind="Face",
            metadata={"color": "red"}
        )
        assert ref.metadata["color"] == "red"
        with pytest.raises(TypeError):
            ref.metadata["color"] = "blue"  # type: ignore[index]

    def test_immutable(self) -> None:
        ref = _entity_ref()
        with pytest.raises((AttributeError, TypeError)):
            ref.entity_id = "MUTATED"  # type: ignore[misc]

    def test_as_dict(self) -> None:
        d = _entity_ref().as_dict()
        assert "entity_id" in d


# ---------------------------------------------------------------------------
# E. FidelityEvent
# ---------------------------------------------------------------------------

class TestFidelityEvent:
    def test_preserved_event(self) -> None:
        ev = _fidelity_event()
        assert ev.fidelity_class is FidelityClass.PRESERVED
        assert ev.is_adverse is False

    def test_lost_event_is_adverse(self) -> None:
        ev = _fidelity_event(cls=FidelityClass.LOST)
        assert ev.is_adverse is True

    def test_downgraded_event_is_adverse(self) -> None:
        ev = _fidelity_event(cls=FidelityClass.DOWNGRADED)
        assert ev.is_adverse is True

    def test_inferred_event_is_adverse(self) -> None:
        ev = _fidelity_event(cls=FidelityClass.INFERRED)
        assert ev.is_adverse is True

    def test_empty_description_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FidelityEvent(
                event_id="FE-001", fidelity_class=FidelityClass.PRESERVED,
                description=""
            )

    def test_invalid_fidelity_class_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FidelityEvent(
                event_id="FE-001", fidelity_class="PRESERVED",  # type: ignore[arg-type]
                description="test"
            )

    def test_with_entity_refs(self) -> None:
        ev = FidelityEvent(
            event_id="FE-001",
            fidelity_class=FidelityClass.DOWNGRADED,
            description="NURBS downgraded to tessellation",
            source_entity_ref=_entity_ref("E-SRC"),
            target_entity_ref=_entity_ref("E-TGT", "MeshBody"),
            source_semantic="NURBS surface (exact)",
            target_semantic="Triangulated mesh (approximate)",
        )
        assert ev.source_entity_ref.entity_id == "E-SRC"
        assert ev.target_entity_ref.entity_id == "E-TGT"

    def test_immutable(self) -> None:
        ev = _fidelity_event()
        with pytest.raises((AttributeError, TypeError)):
            ev.event_id = "MUTATED"  # type: ignore[misc]

    def test_as_dict(self) -> None:
        d = _fidelity_event().as_dict()
        assert "event_id" in d


# ---------------------------------------------------------------------------
# F. ConversionFidelityReport
# ---------------------------------------------------------------------------

class TestConversionFidelityReport:
    def test_complete_no_events_is_lossless(self) -> None:
        rpt = _fidelity_report()
        assert rpt.is_lossless is True

    def test_partial_completeness_not_lossless(self) -> None:
        rpt = _fidelity_report(completeness=FidelityReportCompleteness.PARTIAL)
        assert rpt.is_lossless is False

    def test_unknown_completeness_not_lossless(self) -> None:
        rpt = _fidelity_report(completeness=FidelityReportCompleteness.UNKNOWN)
        assert rpt.is_lossless is False

    def test_lost_event_not_lossless(self) -> None:
        rpt = _fidelity_report(events=(_fidelity_event(cls=FidelityClass.LOST),))
        assert rpt.is_lossless is False

    def test_downgraded_event_not_lossless(self) -> None:
        rpt = _fidelity_report(events=(_fidelity_event(cls=FidelityClass.DOWNGRADED),))
        assert rpt.is_lossless is False

    def test_inferred_event_not_lossless(self) -> None:
        rpt = _fidelity_report(events=(_fidelity_event(cls=FidelityClass.INFERRED),))
        assert rpt.is_lossless is False

    def test_preserved_event_still_lossless(self) -> None:
        rpt = _fidelity_report(events=(_fidelity_event(cls=FidelityClass.PRESERVED),))
        assert rpt.is_lossless is True

    def test_has_loss(self) -> None:
        rpt = _fidelity_report(events=(_fidelity_event(cls=FidelityClass.LOST),))
        assert rpt.has_loss is True

    def test_has_inference(self) -> None:
        rpt = _fidelity_report(events=(_fidelity_event(cls=FidelityClass.INFERRED),))
        assert rpt.has_inference is True

    def test_adverse_events_filtered(self) -> None:
        events = (
            _fidelity_event("FE-1", FidelityClass.PRESERVED),
            _fidelity_event("FE-2", FidelityClass.LOST),
            _fidelity_event("FE-3", FidelityClass.DOWNGRADED),
        )
        rpt = _fidelity_report(events=events)
        adverse = rpt.adverse_events
        assert len(adverse) == 2
        assert all(e.fidelity_class != FidelityClass.PRESERVED for e in adverse)

    def test_counts_by_class(self) -> None:
        events = (
            _fidelity_event("FE-1", FidelityClass.PRESERVED),
            _fidelity_event("FE-2", FidelityClass.LOST),
        )
        rpt = _fidelity_report(events=events)
        counts = rpt.counts_by_class()
        assert counts["PRESERVED"] == 1
        assert counts["LOST"] == 1

    def test_negative_entity_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ConversionFidelityReport(
                report_id="RPT", source_format_id="STEP",
                adapter_id="A", adapter_version="1.0",
                completeness=FidelityReportCompleteness.COMPLETE,
                normalization_status=NormalizationStatus.SUCCESS,
                source_entity_count=-1,
            )

    def test_bool_entity_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ConversionFidelityReport(
                report_id="RPT", source_format_id="STEP",
                adapter_id="A", adapter_version="1.0",
                completeness=FidelityReportCompleteness.COMPLETE,
                normalization_status=NormalizationStatus.SUCCESS,
                source_entity_count=True,  # type: ignore[arg-type]
            )

    def test_invalid_event_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ConversionFidelityReport(
                report_id="RPT", source_format_id="STEP",
                adapter_id="A", adapter_version="1.0",
                completeness=FidelityReportCompleteness.COMPLETE,
                normalization_status=NormalizationStatus.SUCCESS,
                events=("not-an-event",),  # type: ignore[arg-type]
            )

    def test_immutable(self) -> None:
        rpt = _fidelity_report()
        with pytest.raises((AttributeError, TypeError)):
            rpt.report_id = "MUTATED"  # type: ignore[misc]

    def test_deterministic(self) -> None:
        rpt = _fidelity_report()
        assert rpt.counts_by_class() == rpt.counts_by_class()


# ---------------------------------------------------------------------------
# G. CanonicalDocument
# ---------------------------------------------------------------------------

class TestCanonicalDocument:
    def test_minimal_valid_document(self) -> None:
        doc = _document()
        assert doc.document_id == "DOC-001"
        assert doc.canonical_kind == "CAD_GEOMETRY"

    def test_empty_document_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalDocument(
                document_id="",
                canonical_kind="CAD_GEOMETRY",
                source=_source(),
                format_descriptor=_descriptor(),
                adapter_id="A",
                adapter_version="1.0",
                capability_level=CapabilityLevel.LEVEL_1_PARSED,
                normalization_status=NormalizationStatus.SUCCESS,
            )

    def test_invalid_source_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalDocument(
                document_id="DOC-001",
                canonical_kind="CAD_GEOMETRY",
                source="not-a-source",  # type: ignore[arg-type]
                format_descriptor=_descriptor(),
                adapter_id="A",
                adapter_version="1.0",
                capability_level=CapabilityLevel.LEVEL_1_PARSED,
                normalization_status=NormalizationStatus.SUCCESS,
            )

    def test_invalid_entity_ref_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalDocument(
                document_id="DOC-001",
                canonical_kind="CAD_GEOMETRY",
                source=_source(),
                format_descriptor=_descriptor(),
                adapter_id="A",
                adapter_version="1.0",
                capability_level=CapabilityLevel.LEVEL_1_PARSED,
                normalization_status=NormalizationStatus.SUCCESS,
                entity_refs=("not-a-ref",),  # type: ignore[arg-type]
            )

    def test_ordered_entity_refs(self) -> None:
        refs = (
            _entity_ref("E-C"), _entity_ref("E-A"), _entity_ref("E-B")
        )
        doc = CanonicalDocument(
            document_id="DOC-001",
            canonical_kind="CAD_GEOMETRY",
            source=_source(),
            format_descriptor=_descriptor(),
            adapter_id="A",
            adapter_version="1.0",
            capability_level=CapabilityLevel.LEVEL_2_NORMALIZED,
            normalization_status=NormalizationStatus.SUCCESS,
            entity_refs=refs,
        )
        ordered = doc.ordered_entity_refs
        assert [r.entity_id for r in ordered] == ["E-A", "E-B", "E-C"]

    def test_is_lossless_no_report_false(self) -> None:
        doc = _document()
        assert doc.fidelity_report is None
        assert doc.is_lossless is False

    def test_is_lossless_with_complete_no_adverse(self) -> None:
        rpt = _fidelity_report()
        doc = CanonicalDocument(
            document_id="DOC-001",
            canonical_kind="CAD_GEOMETRY",
            source=_source(),
            format_descriptor=_descriptor(),
            adapter_id="A",
            adapter_version="1.0",
            capability_level=CapabilityLevel.LEVEL_2_NORMALIZED,
            normalization_status=NormalizationStatus.SUCCESS,
            fidelity_report=rpt,
        )
        assert doc.is_lossless is True

    def test_is_lossless_with_lost_event_false(self) -> None:
        rpt = _fidelity_report(events=(_fidelity_event(cls=FidelityClass.LOST),))
        doc = CanonicalDocument(
            document_id="DOC-001",
            canonical_kind="CAD_GEOMETRY",
            source=_source(),
            format_descriptor=_descriptor(),
            adapter_id="A",
            adapter_version="1.0",
            capability_level=CapabilityLevel.LEVEL_2_NORMALIZED,
            normalization_status=NormalizationStatus.SUCCESS,
            fidelity_report=rpt,
        )
        assert doc.is_lossless is False

    def test_provenance_accepted(self) -> None:
        prov = Provenance(
            source_type=ProvenanceType.USER_INPUT,
            source_reference="test-fixture",
        )
        doc = CanonicalDocument(
            document_id="DOC-001",
            canonical_kind="CAD_GEOMETRY",
            source=_source(),
            format_descriptor=_descriptor(),
            adapter_id="A",
            adapter_version="1.0",
            capability_level=CapabilityLevel.LEVEL_2_NORMALIZED,
            normalization_status=NormalizationStatus.SUCCESS,
            provenance=prov,
        )
        assert doc.provenance is not None

    def test_schema_version_required(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalDocument(
                document_id="DOC-001",
                canonical_kind="CAD_GEOMETRY",
                source=_source(),
                format_descriptor=_descriptor(),
                adapter_id="A",
                adapter_version="1.0",
                capability_level=CapabilityLevel.LEVEL_1_PARSED,
                normalization_status=NormalizationStatus.SUCCESS,
                schema_version="",
            )

    def test_immutable(self) -> None:
        doc = _document()
        with pytest.raises((AttributeError, TypeError)):
            doc.document_id = "MUTATED"  # type: ignore[misc]

    def test_deterministic_ordered_refs(self) -> None:
        refs = (_entity_ref("E-Z"), _entity_ref("E-A"))
        doc = CanonicalDocument(
            document_id="DOC-001",
            canonical_kind="CAD_GEOMETRY",
            source=_source(),
            format_descriptor=_descriptor(),
            adapter_id="A",
            adapter_version="1.0",
            capability_level=CapabilityLevel.LEVEL_2_NORMALIZED,
            normalization_status=NormalizationStatus.SUCCESS,
            entity_refs=refs,
        )
        o1 = doc.ordered_entity_refs
        o2 = doc.ordered_entity_refs
        assert [r.entity_id for r in o1] == [r.entity_id for r in o2]

    def test_as_dict(self) -> None:
        d = _document().as_dict()
        assert isinstance(d, dict)
        assert "document_id" in d

    def test_preserves_canonical_geometry_and_topology_payloads(self) -> None:
        geometry = CanonicalGeometry(geometry_id="geometry-iges")
        topology = CanonicalTopology(
            topology_id="topology-iges",
            geometry=geometry,
        )

        document = CanonicalDocument(
            document_id="doc-iges",
            canonical_kind="CAD_GEOMETRY",
            source=_source(),
            format_descriptor=_descriptor(),
            adapter_id="iges.token",
            adapter_version="2.0.0",
            capability_level=CapabilityLevel.LEVEL_2_NORMALIZED,
            normalization_status=NormalizationStatus.SUCCESS,
            geometry=geometry,
            topology=topology,
        )

        assert document.geometry is geometry
        assert document.topology is topology
        assert document.as_dict()["geometry"]["geometry_id"] == "geometry-iges"

    @pytest.mark.parametrize("field_name", ["geometry", "topology"])
    def test_rejects_invalid_canonical_payload_type(self, field_name: str) -> None:
        with pytest.raises(ValidationError, match=field_name):
            CanonicalDocument(
                document_id="doc-iges",
                canonical_kind="CAD_GEOMETRY",
                source=_source(),
                format_descriptor=_descriptor(),
                adapter_id="iges.token",
                adapter_version="2.0.0",
                capability_level=CapabilityLevel.LEVEL_2_NORMALIZED,
                normalization_status=NormalizationStatus.SUCCESS,
                **{field_name: object()},
            )
