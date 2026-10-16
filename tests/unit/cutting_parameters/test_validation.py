"""Tests for cutting-parameter authority validation (Stage 3G)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.cutting_parameters.models import (
    ApplicabilityScope,
    CuttingParameterRecord,
    EvidenceStatus,
    ParameterType,
    QuantityRange,
)
from backend.cutting_parameters.validation import (
    ACCEPTABLE_AUTHORITATIVE_SOURCE_TYPES,
    REJECTED_SOURCE_TYPES,
    is_usable_for_authority,
    require_authoritative,
)
from backend.domain.base import Provenance
from backend.domain.enums import IsoMaterialGroup, OperationType, ProvenanceType
from backend.domain.units import Quantity, Unit
from backend.empirical.exceptions import EmpiricalDataError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _vc_record(
    evidence: EvidenceStatus = EvidenceStatus.AUTHORITATIVE,
    source_type: ProvenanceType = ProvenanceType.MANUFACTURER_DATA,
    source_ref: str | None = "Sandvik catalogue",
) -> CuttingParameterRecord:
    return CuttingParameterRecord(
        record_id="TEST_VAL",
        parameter_type=ParameterType.CUTTING_SPEED,
        value_range=QuantityRange(
            min_value=Quantity(Decimal("100"), Unit.M_MIN),
            max_value=Quantity(Decimal("200"), Unit.M_MIN),
        ),
        applicability=ApplicabilityScope(
            operation_type=OperationType.TURNING,
            iso_material_group=IsoMaterialGroup.P,
        ),
        provenance=Provenance(
            source_type=source_type,
            source_reference=source_ref,
        ),
        evidence_status=evidence,
    )


def _ref_only_record() -> CuttingParameterRecord:
    return CuttingParameterRecord(
        record_id="REF_TEST",
        parameter_type=ParameterType.CUTTING_SPEED,
        value_range=QuantityRange(
            min_value=Quantity(Decimal("120"), Unit.M_MIN),
            max_value=Quantity(Decimal("280"), Unit.M_MIN),
        ),
        applicability=ApplicabilityScope(),
        provenance=Provenance(
            source_type=ProvenanceType.LITERATURE,
            source_reference="research report",
        ),
        evidence_status=EvidenceStatus.REFERENCE_ONLY,
    )


# ---------------------------------------------------------------------------
# Source type sets
# ---------------------------------------------------------------------------

class TestSourceTypeSets:
    def test_acceptable_includes_manufacturer_data(self):
        assert ProvenanceType.MANUFACTURER_DATA in ACCEPTABLE_AUTHORITATIVE_SOURCE_TYPES

    def test_acceptable_includes_literature(self):
        assert ProvenanceType.LITERATURE in ACCEPTABLE_AUTHORITATIVE_SOURCE_TYPES

    def test_acceptable_does_not_include_ai_suggestion(self):
        assert ProvenanceType.AI_SUGGESTION not in ACCEPTABLE_AUTHORITATIVE_SOURCE_TYPES

    def test_rejected_includes_ai_suggestion(self):
        assert ProvenanceType.AI_SUGGESTION in REJECTED_SOURCE_TYPES

    def test_rejected_includes_unknown(self):
        assert ProvenanceType.UNKNOWN in REJECTED_SOURCE_TYPES

    def test_rejected_does_not_include_manufacturer(self):
        assert ProvenanceType.MANUFACTURER_DATA not in REJECTED_SOURCE_TYPES


# ---------------------------------------------------------------------------
# is_usable_for_authority
# ---------------------------------------------------------------------------

class TestIsUsableForAuthority:
    def test_authoritative_record_passes(self):
        r = _vc_record(
            evidence=EvidenceStatus.AUTHORITATIVE,
            source_type=ProvenanceType.MANUFACTURER_DATA,
            source_ref="Sandvik catalogue",
        )
        assert is_usable_for_authority(r) is True

    def test_experimental_record_passes(self):
        r = _vc_record(
            evidence=EvidenceStatus.EXPERIMENTAL,
            source_type=ProvenanceType.HISTORICAL_PROCESS_DATA,
            source_ref="shop floor experiment",
        )
        assert is_usable_for_authority(r) is True

    def test_reference_only_fails(self):
        r = _ref_only_record()
        assert is_usable_for_authority(r) is False

    def test_unverified_fails(self):
        r = CuttingParameterRecord(
            record_id="UNVER",
            parameter_type=ParameterType.CUTTING_SPEED,
            value_range=QuantityRange(
                min_value=Quantity(Decimal("100"), Unit.M_MIN),
                max_value=Quantity(Decimal("200"), Unit.M_MIN),
            ),
            applicability=ApplicabilityScope(),
            provenance=Provenance(
                source_type=ProvenanceType.LITERATURE,
                source_reference="some ref",
            ),
            evidence_status=EvidenceStatus.UNVERIFIED,
        )
        assert is_usable_for_authority(r) is False


# ---------------------------------------------------------------------------
# require_authoritative
# ---------------------------------------------------------------------------

class TestRequireAuthoritative:
    def test_passes_authoritative_record_through(self):
        r = _vc_record()
        result = require_authoritative(r)
        assert result is r

    def test_raises_on_reference_only(self):
        r = _ref_only_record()
        with pytest.raises(EmpiricalDataError, match="evidence_status"):
            require_authoritative(r)

    def test_error_message_is_specific(self):
        r = _ref_only_record()
        with pytest.raises(EmpiricalDataError) as exc_info:
            require_authoritative(r)
        msg = str(exc_info.value)
        assert "REFERENCE_ONLY" in msg
        assert "REF_TEST" in msg

    def test_reference_only_is_never_authoritative(self):
        """Hard Rule 29: CASE_D records are REFERENCE_ONLY and must never pass
        as authoritative engineering inputs."""
        records_from_seed = [_ref_only_record()]
        for r in records_from_seed:
            assert not r.is_authoritative
            with pytest.raises(EmpiricalDataError):
                require_authoritative(r)
