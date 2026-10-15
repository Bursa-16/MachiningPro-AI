"""Tests for VP100EmpiricalRecord and VP100SourceMeta (Stage EMPIRICAL-01A).

Uses verbatim values from VP100-001, VP100-009, VP100-049 in the source
workbook to verify correct model construction and validation behaviour.

Rq semantics: Rq (root-mean-square roughness) is stored as Unit.RQ_UM and
must NOT be confused with Ra (arithmetic mean roughness, Unit.RA_UM).
"""

from decimal import Decimal

import pytest

from backend.cutting_parameters.models import EvidenceStatus
from backend.domain.base import Provenance
from backend.domain.enums import ProvenanceType
from backend.domain.exceptions import ValidationError
from backend.domain.units import Quantity, Unit
from backend.empirical.models import (
    VP100_VALID_COATINGS,
    VP100_VALID_COMBINATIONS,
    VP100_VALID_TOOL_CONDITIONS,
    VP100EmpiricalRecord,
    VP100SourceMeta,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SOURCE_META = VP100SourceMeta(
    source_dataset="VP100-EXTERNAL-BENCHMARK",
    source_filename="MachiningPro_AI_VP100_EXTERNAL_BENCHMARK.xlsx",
    source_sha256="ee0f0ec8a25dcac8d26e65876e5f6d64fca671f30d6a668280edc9a7dd3f153c",
    source_sheet="VP100 Detailed Results",
)

_PROVENANCE = Provenance(
    source_type=ProvenanceType.HISTORICAL_PROCESS_DATA,
    source_reference="VP100-EXTERNAL-BENCHMARK / VP100 Detailed Results",
)


def _make_record(
    record_id: str = "VP100-001",
    tool_condition: str = "C0",
    coating: str = "Uncoated",
    combination: str = "A",
    replicate: int = 1,
    vc: str = "125",
    fz: str = "0.1",
    ap: str = "0.7",
    mrv: str = "14",
    t_eol: str = "6.33345078963702",
    rq: str = "1.83866666666667",
    fx: str = "329.892681068343",
) -> VP100EmpiricalRecord:
    """Construct a valid record from string-typed decimal values."""
    return VP100EmpiricalRecord(
        record_id=record_id,
        source=_SOURCE_META,
        source_row=1,
        tool_condition=tool_condition,
        coating=coating,
        combination=combination,
        replicate=replicate,
        vc=Quantity(Decimal(vc), Unit.M_MIN),
        fz=Quantity(Decimal(fz), Unit.MM_TOOTH),
        ap=Quantity(Decimal(ap), Unit.MM),
        mrv=Quantity(Decimal(mrv), Unit.CM3),
        t_eol=Quantity(Decimal(t_eol), Unit.MIN),
        rq=Quantity(Decimal(rq), Unit.RQ_UM),
        fx=Quantity(Decimal(fx), Unit.N),
        provenance=_PROVENANCE,
        evidence_status=EvidenceStatus.EXPERIMENTAL,
    )


# ---------------------------------------------------------------------------
# VP100SourceMeta tests
# ---------------------------------------------------------------------------

class TestVP100SourceMeta:
    def test_construction_ok(self) -> None:
        meta = _SOURCE_META
        assert meta.source_dataset == "VP100-EXTERNAL-BENCHMARK"
        assert meta.source_sheet == "VP100 Detailed Results"

    def test_empty_field_raises(self) -> None:
        with pytest.raises(ValidationError, match="source_dataset"):
            VP100SourceMeta(
                source_dataset="",
                source_filename="f.xlsx",
                source_sha256="abc",
                source_sheet="sheet",
            )

    def test_as_dict_serializable(self) -> None:
        d = _SOURCE_META.as_dict()
        assert d["source_sha256"] == _SOURCE_META.source_sha256


# ---------------------------------------------------------------------------
# VP100EmpiricalRecord — happy-path construction
# ---------------------------------------------------------------------------

class TestVP100EmpiricalRecordHappyPath:
    def test_vp100_001_verbatim_values(self) -> None:
        """VP100-001: verbatim values from source workbook row 1."""
        rec = _make_record()
        assert rec.record_id == "VP100-001"
        assert rec.tool_condition == "C0"
        assert rec.coating == "Uncoated"
        assert rec.combination == "A"
        assert rec.replicate == 1
        assert rec.vc.value == Decimal("125")
        assert rec.vc.unit is Unit.M_MIN
        assert rec.fz.value == Decimal("0.1")
        assert rec.fz.unit is Unit.MM_TOOTH
        assert rec.ap.value == Decimal("0.7")
        assert rec.ap.unit is Unit.MM
        assert rec.mrv.value == Decimal("14")
        assert rec.mrv.unit is Unit.CM3
        assert rec.rq.unit is Unit.RQ_UM   # Rq ≠ Ra: must be RQ_UM
        assert rec.fx.unit is Unit.N
        assert rec.evidence_status is EvidenceStatus.EXPERIMENTAL

    def test_vp100_009_low_mrv(self) -> None:
        """VP100-009: mrv=7 (tool failed after half the standard volume)."""
        rec = _make_record(
            record_id="VP100-009",
            tool_condition="C0",
            coating="Uncoated",
            combination="C",
            replicate=3,
            vc="125",
            fz="0.2",
            ap="0.7",
            mrv="7",
            t_eol="1.58336269740926",
            rq="1.05733333333333",
            fx="423.746200633084",
        )
        assert rec.record_id == "VP100-009"
        assert rec.mrv.value == Decimal("7")

    def test_vp100_049_altIN_long_life(self) -> None:
        """VP100-049: AlTiN coating; T_EOL > 50 min shows coating effect."""
        rec = _make_record(
            record_id="VP100-049",
            tool_condition="C2",
            coating="AlTiN",
            combination="A",
            replicate=1,
            vc="125",
            fz="0.1",
            ap="0.7",
            mrv="112",
            t_eol="50.6676063170962",
            rq="0.166875",
            fx="272.45566769468",
        )
        assert rec.tool_condition == "C2"
        assert rec.coating == "AlTiN"
        assert not rec.is_uncoated

    def test_is_uncoated_property(self) -> None:
        assert _make_record(tool_condition="C0").is_uncoated is True
        assert (
            _make_record(record_id="VP100-025", tool_condition="C1", coating="TiN").is_uncoated
            is False
        )

    def test_all_tool_conditions_accepted(self) -> None:
        coatings_by_cond = {"C0": "Uncoated", "C1": "TiN", "C2": "AlTiN", "C3": "AlTiN/TiSiXN"}
        for cond, coat in coatings_by_cond.items():
            rec = _make_record(
                record_id=f"VP100-{cond}",
                tool_condition=cond,
                coating=coat,
            )
            assert rec.tool_condition == cond

    def test_all_combinations_accepted(self) -> None:
        for combo in "ABCDEFGH":
            rec = _make_record(record_id=f"VP100-{combo}", combination=combo)
            assert rec.combination == combo

    def test_as_dict_roundtrip(self) -> None:
        rec = _make_record()
        d = rec.as_dict()
        assert d["record_id"] == "VP100-001"
        assert str(d["vc"]) == "125"
        assert str(d["rq"]) == "1.83866666666667"


# ---------------------------------------------------------------------------
# Unit semantics — Rq must NOT accept Ra_um
# ---------------------------------------------------------------------------

class TestRqUnitSemantics:
    def test_rq_field_requires_rq_um_not_ra_um(self) -> None:
        """Rq is stored as RQ_UM; Ra_um is a different unit — must be rejected."""
        with pytest.raises(ValidationError, match="rq must carry unit"):
            VP100EmpiricalRecord(
                record_id="VP100-unit-test",
                source=_SOURCE_META,
                source_row=1,
                tool_condition="C0",
                coating="Uncoated",
                combination="A",
                replicate=1,
                vc=Quantity(Decimal("125"), Unit.M_MIN),
                fz=Quantity(Decimal("0.1"), Unit.MM_TOOTH),
                ap=Quantity(Decimal("0.7"), Unit.MM),
                mrv=Quantity(Decimal("14"), Unit.CM3),
                t_eol=Quantity(Decimal("6.33"), Unit.MIN),
                rq=Quantity(Decimal("1.84"), Unit.RA_UM),   # WRONG unit
                fx=Quantity(Decimal("330"), Unit.N),
                provenance=_PROVENANCE,
                evidence_status=EvidenceStatus.EXPERIMENTAL,
            )

    def test_mrv_field_requires_cm3_not_mm3(self) -> None:
        """MRV is in cm³ (CM3); supplying mm³ (MM3) must be rejected."""
        with pytest.raises(ValidationError, match="mrv must carry unit"):
            VP100EmpiricalRecord(
                record_id="VP100-unit-test",
                source=_SOURCE_META,
                source_row=1,
                tool_condition="C0",
                coating="Uncoated",
                combination="A",
                replicate=1,
                vc=Quantity(Decimal("125"), Unit.M_MIN),
                fz=Quantity(Decimal("0.1"), Unit.MM_TOOTH),
                ap=Quantity(Decimal("0.7"), Unit.MM),
                mrv=Quantity(Decimal("14000"), Unit.MM3),   # WRONG unit
                t_eol=Quantity(Decimal("6.33"), Unit.MIN),
                rq=Quantity(Decimal("1.84"), Unit.RQ_UM),
                fx=Quantity(Decimal("330"), Unit.N),
                provenance=_PROVENANCE,
                evidence_status=EvidenceStatus.EXPERIMENTAL,
            )


# ---------------------------------------------------------------------------
# Validation — rejection cases
# ---------------------------------------------------------------------------

class TestVP100EmpiricalRecordValidation:
    def test_invalid_tool_condition(self) -> None:
        with pytest.raises(ValidationError, match="tool_condition"):
            _make_record(tool_condition="C5")

    def test_invalid_coating(self) -> None:
        with pytest.raises(ValidationError, match="coating"):
            _make_record(coating="TiAlN")  # slightly different spelling

    def test_invalid_combination(self) -> None:
        with pytest.raises(ValidationError, match="combination"):
            _make_record(combination="Z")

    def test_invalid_replicate_zero(self) -> None:
        with pytest.raises(ValidationError, match="replicate"):
            _make_record(replicate=0)

    def test_empty_record_id(self) -> None:
        with pytest.raises(ValidationError):
            _make_record(record_id="")

    def test_negative_vc_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_record(vc="-125")

    def test_controlled_vocabulary_constants(self) -> None:
        assert VP100_VALID_TOOL_CONDITIONS == {"C0", "C1", "C2", "C3"}
        assert VP100_VALID_COATINGS == {"Uncoated", "TiN", "AlTiN", "AlTiN/TiSiXN"}
        assert VP100_VALID_COMBINATIONS == set("ABCDEFGH")
