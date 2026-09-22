"""Strict IGES 5.x geometry and topology adapter.

The adapter parses byte-accurate fixed records in pure Python and reaches
Level 2 only when the declared supported subset produces real canonical
geometry. Unsupported semantic dependencies are reported explicitly.
"""

from __future__ import annotations

from pathlib import Path

from backend.interoperability.adapter import FormatAdapter
from backend.interoperability.adapters._base import AdapterSession, make_uid
from backend.interoperability.enums import (
    AdapterCapability,
    AdapterLicense,
    CapabilityLevel,
    FidelityClass,
    FidelityReportCompleteness,
    FormatFamily,
)
from backend.interoperability.iges_mapping import map_iges_model
from backend.interoperability.iges_parser import IgesParseError, parse_iges_bytes
from backend.interoperability.models import (
    AdapterMetadata,
    CanonicalDocument,
    CanonicalEntityRef,
    EngineeringSource,
    FormatDescriptor,
)

__all__ = ["IGES_DESCRIPTOR", "IgesTokenAdapter"]

_ADAPTER_ID = "machinerypro-iges-token-v1"
_ADAPTER_VERSION = "2.0.0"

IGES_DESCRIPTOR = FormatDescriptor(
    format_id="IGES",
    canonical_name="IGES 5.x",
    family=FormatFamily.NEUTRAL_EXCHANGE,
    extensions=("igs", "iges"),
    media_types=("model/iges",),
    vendor="ANSI",
    is_open=True,
    is_proprietary=False,
    adapter_license=AdapterLicense.INTERNAL_PARSER,
    notes="ANSI/ASME Y14.26M — Initial Graphics Exchange Specification",
)

_IGES_ENTITY_NAMES: dict[int, str] = {
    100: "Circular Arc",
    108: "Plane",
    110: "Line",
    116: "Point",
    118: "Ruled Surface",
    123: "Direction",
    124: "Transformation Matrix",
    126: "Rational B-Spline Curve",
    128: "Rational B-Spline Surface",
    141: "Boundary",
    142: "Curve on Parametric Surface",
    143: "Bounded Surface",
    144: "Trimmed Surface",
    186: "Manifold Solid B-Rep Object",
    190: "Plane Surface",
    192: "Right Circular Cylindrical Surface",
    194: "Right Circular Conical Surface",
    196: "Spherical Surface",
    198: "Toroidal Surface",
    212: "General Note",
    314: "Color Definition",
    502: "Vertex List",
    504: "Edge List",
    508: "Loop",
    510: "Face",
    514: "Shell",
}


class IgesTokenAdapter(FormatAdapter):
    """Fail-closed IGES adapter for an explicitly supported Level 2 subset."""

    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            adapter_id=_ADAPTER_ID,
            adapter_name="MachineryPro IGES Canonical Adapter",
            adapter_version=_ADAPTER_VERSION,
            format_ids=("IGES",),
            capabilities=(
                AdapterCapability.RECOGNIZE,
                AdapterCapability.PARSE,
                AdapterCapability.NORMALIZE,
                AdapterCapability.EXTRACT_GEOMETRY,
                AdapterCapability.EXTRACT_TOPOLOGY,
            ),
            max_capability_level=CapabilityLevel.LEVEL_2_NORMALIZED,
            adapter_license=AdapterLicense.INTERNAL_PARSER,
            requires_external_dependency=False,
            notes=(
                "Strict fixed-record IGES parser with canonical geometry and "
                "B-Rep mapping for the declared supported subset."
            ),
        )

    def can_handle(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor | None = None,
    ) -> bool:
        if source.source_format_id == "IGES":
            return True
        if format_descriptor and format_descriptor.format_id == "IGES":
            return True
        if source.file_name:
            lower = source.file_name.lower()
            if lower.endswith((".igs", ".iges")):
                return True
        return False

    def ingest(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
    ) -> CanonicalDocument:
        if source.notes is None:
            return self._ingest_bytes(source, format_descriptor, None)
        try:
            content = source.notes.encode("ascii")
        except UnicodeEncodeError:
            content = source.notes.encode("utf-8")
        return self._ingest_bytes(source, format_descriptor, content)

    def ingest_file(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
        content_path: Path,
    ) -> CanonicalDocument:
        """Ingest the complete bounded upload from its staged path."""

        try:
            content = content_path.read_bytes()
        except OSError:
            session = AdapterSession(source, format_descriptor, self.metadata())
            session.mark_failed()
            session.record(
                FidelityClass.LOST,
                "Unable to read staged IGES content",
            )
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()
        return self._ingest_bytes(source, format_descriptor, content)

    def _ingest_bytes(
        self,
        source: EngineeringSource,
        format_descriptor: FormatDescriptor,
        content: bytes | None,
    ) -> CanonicalDocument:
        session = AdapterSession(source, format_descriptor, self.metadata())
        if not content:
            session.mark_failed()
            session.record(FidelityClass.LOST, "No IGES content provided")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        try:
            model = parse_iges_bytes(content)
        except IgesParseError as exc:
            session.mark_failed()
            session.record(FidelityClass.LOST, f"IGES parse error: {exc}")
            session.set_fidelity_completeness(FidelityReportCompleteness.UNKNOWN)
            return session.build()

        session.mark_parsed()
        session.set_source_entity_count(len(model.entities))
        entity_counts: dict[int, int] = {}
        for entity in model.entities:
            entity_type = entity.directory.entity_type
            entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1

        session.add_entity_ref(
            CanonicalEntityRef(
                entity_id=make_uid("IGES-HEADER-"),
                entity_kind="IgesHeader",
                metadata={
                    "sections": tuple(model.section_counts),
                    "entity_count": len(model.entities),
                    "entity_type_summary": {
                        _IGES_ENTITY_NAMES.get(entity_type, f"type_{entity_type}"): count
                        for entity_type, count in entity_counts.items()
                    },
                    "source_unit": model.global_section.unit_name,
                    "model_scale": model.global_section.model_scale,
                    "minimum_resolution": model.global_section.minimum_resolution,
                    "source_file_name": model.global_section.file_name,
                    "native_system_id": model.global_section.native_system_id,
                    "preprocessor_version": (
                        model.global_section.preprocessor_version
                    ),
                    "creation_timestamp": (
                        model.global_section.creation_timestamp
                    ),
                    "modified_timestamp": (
                        model.global_section.modified_timestamp
                    ),
                    "iges_version": model.global_section.version,
                },
            )
        )

        mapping = map_iges_model(model)
        for ref in mapping.entity_refs:
            session.add_entity_ref(ref)
        if mapping.geometry is not None:
            session.set_geometry(mapping.geometry)
            session.mark_normalized()
        if mapping.topology is not None:
            session.set_topology(mapping.topology)

        refs_by_source = {
            ref.source_entity_id: ref
            for ref in mapping.entity_refs
            if ref.source_entity_id is not None
        }
        for issue in mapping.issues:
            description = (
                f"IGES DE={issue.de_pointer} type={issue.entity_type} "
                f"form={issue.form_number}: {issue.reason}"
            )
            if "unsupported" in issue.reason.lower():
                fidelity_class = FidelityClass.UNSUPPORTED
            elif issue.fatal:
                fidelity_class = FidelityClass.LOST
            else:
                fidelity_class = FidelityClass.PARTIALLY_PRESERVED
            session.record(
                fidelity_class,
                description,
                source_ref=refs_by_source.get(str(issue.de_pointer)),
            )

        invalid_fatal_issue = any(
            issue.fatal and "unsupported" not in issue.reason.lower()
            for issue in mapping.issues
        )
        unsupported_fatal_issue = any(
            issue.fatal and "unsupported" in issue.reason.lower()
            for issue in mapping.issues
        )
        if invalid_fatal_issue:
            session.mark_failed()
            session.set_fidelity_completeness(FidelityReportCompleteness.PARTIAL)
        elif unsupported_fatal_issue:
            session.mark_unsupported()
            session.set_fidelity_completeness(FidelityReportCompleteness.PARTIAL)
        elif mapping.issues:
            session.mark_partial()
            session.set_fidelity_completeness(FidelityReportCompleteness.PARTIAL)
        elif mapping.geometry is None:
            session.record_unsupported(
                "IGES file contains no supported geometry entities"
            )
            session.mark_partial()
            session.set_fidelity_completeness(FidelityReportCompleteness.PARTIAL)
        else:
            session.set_fidelity_completeness(FidelityReportCompleteness.COMPLETE)
        return session.build()
