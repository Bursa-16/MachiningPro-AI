"""Tests for ToolLife968Observation and ToolLife968SourceMeta (TOOLLIFE_968_DATA_INGESTION_01).

Verbatim fixture values sourced from Golden ToolLife 968, data rows 1 and 2
(FileName P002_F01_C1 and P002_F01_C2).

Key semantics verified:
- CycleToFailure is a countdown (0 = EOL).
- total_tool_life_cycles = cycle_number + cycle_to_failure.
- is_eol is True only when cycle_to_failure == 0.
- VB not present — no VB field.
- Taylor C/n not present — no such field.
- sensor_features: exactly 120 float values.
- hardness_mean: Decimal, unit unstated in source.
- adoc, rdoc, tool_holder_length: Unit.MM required.
- TollIndex typo: stored as tool_index in the model.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.cutting_parameters.models import EvidenceStatus
from backend.domain.base import Provenance
from backend.domain.enums import ProvenanceType
from backend.domain.exceptions import ValidationError
from backend.domain.units import Quantity, Unit
from backend.empirical.toollife968_models import (
    TOOLLIFE968_SENSOR_FEATURE_COUNT,
    TOOLLIFE968_TOTAL_COL_COUNT,
    TOOLLIFE968_VALID_TOOL_TYPES,
    ToolLife968Observation,
    ToolLife968SourceMeta,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SENSOR_HEADERS: tuple[str, ...] = tuple(f"sensor_{i}" for i in range(120))

_SOURCE_META = ToolLife968SourceMeta(
    source_dataset="TOOLLIFE-968",
    source_filename="MachiningPro_AI_VP100_EXTERNAL_BENCHMARK.xlsx",
    source_sha256="ee0f0ec8a25dcac8d26e65876e5f6d64fca671f30d6a668280edc9a7dd3f153c",
    source_sheet="Golden ToolLife 968",
    doi="10.6084/m9.figshare.28589216",
    sensor_feature_headers=_SENSOR_HEADERS,
)

_PROVENANCE = Provenance(
    source_type=ProvenanceType.HISTORICAL_PROCESS_DATA,
    source_reference="test fixture",
)

_SENSOR_FEATURES_120: tuple[float, ...] = tuple(float(i) for i in range(120))


def _make_obs(
    observation_id: str = "P002_F01_C1",
    tool_index: int = 2,
    tool_type: str = "1",
    adoc_mm: str = "5",
    rdoc_mm: str = "8",
    thl_mm: str = "80",
    hardness: str = "36.67",
    cycle_number: int = 1,
    sample_index: int = 2,
    cycle_to_failure: int = 49,
    ctf_normalized: str = "1.0",
    sensor_features: tuple[float, ...] = _SENSOR_FEATURES_120,
) -> ToolLife968Observation:
    return ToolLife968Observation(
        observation_id=observation_id,
        source=_SOURCE_META,
        source_row=1,
        tool_index=tool_index,
        tool_type=tool_type,
        adoc=Quantity(Decimal(adoc_mm), Unit.MM),
        rdoc=Quantity(Decimal(rdoc_mm), Unit.MM),
        tool_holder_length=Quantity(Decimal(thl_mm), Unit.MM),
        hardness_mean=Decimal(hardness),
        cycle_number=cycle_number,
        sample_index=sample_index,
        cycle_to_failure=cycle_to_failure,
        cycle_to_failure_normalized=Decimal(ctf_normalized),
        sensor_features=sensor_features,
        provenance=_PROVENANCE,
        evidence_status=EvidenceStatus.EXPERIMENTAL,
    )


# ---------------------------------------------------------------------------
# ToolLife968SourceMeta
# ---------------------------------------------------------------------------

class TestToolLife968SourceMeta:
    def test_construction_ok(self) -> None:
        meta = _SOURCE_META
        assert meta.source_dataset == "TOOLLIFE-968"
        assert meta.source_sheet == "Golden ToolLife 968"
        assert meta.doi == "10.6084/m9.figshare.28589216"
        assert len(meta.sensor_feature_headers) == 120

    def test_empty_source_dataset_raises(self) -> None:
        with pytest.raises(ValidationError, match="source_dataset"):
            ToolLife968SourceMeta(
                source_dataset="",
                source_filename="f.xlsx",
                source_sha256="abc",
                source_sheet="sheet",
                doi="doi",
                sensor_feature_headers=_SENSOR_HEADERS,
            )

    def test_wrong_sensor_header_count_raises(self) -> None:
        with pytest.raises(ValidationError, match="sensor_feature_headers"):
            ToolLife968SourceMeta(
                source_dataset="TOOLLIFE-968",
                source_filename="f.xlsx",
                source_sha256="abc",
                source_sheet="sheet",
                doi="doi",
                sensor_feature_headers=tuple(f"s_{i}" for i in range(10)),  # wrong
            )

    def test_as_dict_contains_sha(self) -> None:
        d = _SOURCE_META.as_dict()
        assert d["source_sha256"] == _SOURCE_META.source_sha256
        assert "sensor_feature_headers" not in d


# ---------------------------------------------------------------------------
# ToolLife968Observation — happy path (verbatim source values)
# ---------------------------------------------------------------------------

class TestToolLife968ObservationHappyPath:
    def test_first_row_verbatim_values(self) -> None:
        """P002_F01_C1: first data row, TollIndex=2, NumberOfCycle=1, CTF=49."""
        obs = _make_obs()
        assert obs.observation_id == "P002_F01_C1"
        assert obs.tool_index == 2
        assert obs.tool_type == "1"
        assert obs.adoc.value == Decimal("5")
        assert obs.adoc.unit is Unit.MM
        assert obs.rdoc.value == Decimal("8")
        assert obs.rdoc.unit is Unit.MM
        assert obs.tool_holder_length.value == Decimal("80")
        assert obs.tool_holder_length.unit is Unit.MM
        assert obs.hardness_mean == Decimal("36.67")
        assert obs.cycle_number == 1
        assert obs.sample_index == 2
        assert obs.cycle_to_failure == 49
        assert obs.cycle_to_failure_normalized == Decimal("1.0")
        assert len(obs.sensor_features) == 120
        assert obs.evidence_status is EvidenceStatus.EXPERIMENTAL

    def test_tool_type_2_accepted(self) -> None:
        obs = _make_obs(tool_type="2")
        assert obs.tool_type == "2"

    def test_all_valid_tool_types_accepted(self) -> None:
        for tt in TOOLLIFE968_VALID_TOOL_TYPES:
            obs = _make_obs(tool_type=tt)
            assert obs.tool_type == tt

    def test_eol_observation_cycle_to_failure_zero(self) -> None:
        """TollIndex=2, NumberOfCycle=50 → CTF=0 (EOL)."""
        obs = _make_obs(
            observation_id="P002_F50_C1",
            cycle_number=50,
            cycle_to_failure=0,
            ctf_normalized="0.0",
        )
        assert obs.is_eol is True
        assert obs.cycle_to_failure == 0

    def test_non_eol_is_not_eol(self) -> None:
        obs = _make_obs(cycle_to_failure=49)
        assert obs.is_eol is False

    def test_total_tool_life_cycles_formula(self) -> None:
        """total_tool_life_cycles = cycle_number + cycle_to_failure."""
        obs = _make_obs(cycle_number=1, cycle_to_failure=49)
        assert obs.total_tool_life_cycles == 50

    def test_total_tool_life_eol_row(self) -> None:
        """At EOL: total = cycle_number + 0 = cycle_number."""
        obs = _make_obs(
            cycle_number=50,
            cycle_to_failure=0,
            ctf_normalized="0.0",
        )
        assert obs.total_tool_life_cycles == 50

    def test_degenerate_tool11_single_cycle(self) -> None:
        """TollIndex=11: only 1 observation, CTF=0 at cycle 1."""
        obs = _make_obs(
            observation_id="P011_F01_C1",
            tool_index=11,
            cycle_number=1,
            cycle_to_failure=0,
            ctf_normalized="0.0",
        )
        assert obs.is_eol is True
        assert obs.total_tool_life_cycles == 1

    def test_tool9_longest_lifecycle(self) -> None:
        """TollIndex=9: 149 observations, max CTF=149."""
        obs = _make_obs(
            observation_id="P009_F01_C1",
            tool_index=9,
            cycle_number=1,
            cycle_to_failure=149,
            ctf_normalized="1.0",
        )
        assert obs.total_tool_life_cycles == 150

    def test_as_dict_contains_expected_keys(self) -> None:
        obs = _make_obs()
        d = obs.as_dict()
        assert d["observation_id"] == "P002_F01_C1"
        assert d["tool_index"] == 2
        assert d["is_eol"] is False
        assert d["total_tool_life_cycles"] == 50
        assert d["evidence_status"] == EvidenceStatus.EXPERIMENTAL.value
        assert "sensor_features" not in d  # sensor_features excluded from dict

    def test_sensor_features_exactly_120(self) -> None:
        obs = _make_obs()
        assert len(obs.sensor_features) == TOOLLIFE968_SENSOR_FEATURE_COUNT

    def test_sensor_features_are_float(self) -> None:
        obs = _make_obs()
        assert all(isinstance(v, float) for v in obs.sensor_features)

    def test_source_meta_attached(self) -> None:
        obs = _make_obs()
        assert obs.source is _SOURCE_META
        assert obs.source.doi == "10.6084/m9.figshare.28589216"


# ---------------------------------------------------------------------------
# ToolLife968Observation — dataset design assertions
# ---------------------------------------------------------------------------

class TestDatasetDesignAssertions:
    def test_no_vb_field(self) -> None:
        """VB (flank wear) is not present in this dataset."""
        obs = _make_obs()
        assert not hasattr(obs, "vb")
        assert not hasattr(obs, "flank_wear")

    def test_no_taylor_fields(self) -> None:
        """No cutting speed Vc → no Taylor C/n fields."""
        obs = _make_obs()
        assert not hasattr(obs, "vc")
        assert not hasattr(obs, "taylor_c")
        assert not hasattr(obs, "taylor_n")

    def test_hardness_is_decimal_not_quantity(self) -> None:
        """hardness_mean is raw Decimal (unit unstated in source)."""
        obs = _make_obs()
        assert isinstance(obs.hardness_mean, Decimal)
        assert not hasattr(obs.hardness_mean, "unit")

    def test_sensor_features_count_matches_constant(self) -> None:
        assert TOOLLIFE968_SENSOR_FEATURE_COUNT == 120
        assert TOOLLIFE968_TOTAL_COL_COUNT == 131


# ---------------------------------------------------------------------------
# ToolLife968Observation — validation / rejection
# ---------------------------------------------------------------------------

class TestToolLife968ObservationValidation:
    def test_empty_observation_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make_obs(observation_id="")

    def test_tool_index_zero_raises(self) -> None:
        with pytest.raises(ValidationError, match="tool_index"):
            _make_obs(tool_index=0)

    def test_tool_index_negative_raises(self) -> None:
        with pytest.raises(ValidationError, match="tool_index"):
            _make_obs(tool_index=-1)

    def test_invalid_tool_type_raises(self) -> None:
        with pytest.raises(ValidationError, match="tool_type"):
            _make_obs(tool_type="3")

    def test_adoc_zero_raises(self) -> None:
        with pytest.raises(ValidationError, match="adoc"):
            _make_obs(adoc_mm="0")

    def test_adoc_wrong_unit_raises(self) -> None:
        with pytest.raises(ValidationError, match="adoc"):
            ToolLife968Observation(
                observation_id="test",
                source=_SOURCE_META,
                source_row=1,
                tool_index=2,
                tool_type="1",
                adoc=Quantity(Decimal("5"), Unit.M_MIN),  # wrong unit
                rdoc=Quantity(Decimal("8"), Unit.MM),
                tool_holder_length=Quantity(Decimal("80"), Unit.MM),
                hardness_mean=Decimal("36.67"),
                cycle_number=1,
                sample_index=2,
                cycle_to_failure=49,
                cycle_to_failure_normalized=Decimal("1.0"),
                sensor_features=_SENSOR_FEATURES_120,
                provenance=_PROVENANCE,
                evidence_status=EvidenceStatus.EXPERIMENTAL,
            )

    def test_rdoc_zero_raises(self) -> None:
        with pytest.raises(ValidationError, match="rdoc"):
            _make_obs(rdoc_mm="0")

    def test_tool_holder_length_zero_raises(self) -> None:
        with pytest.raises(ValidationError, match="tool_holder_length"):
            _make_obs(thl_mm="0")

    def test_hardness_mean_zero_raises(self) -> None:
        with pytest.raises(ValidationError, match="hardness_mean"):
            _make_obs(hardness="0")

    def test_cycle_number_zero_raises(self) -> None:
        with pytest.raises(ValidationError, match="cycle_number"):
            _make_obs(cycle_number=0)

    def test_sample_index_negative_raises(self) -> None:
        with pytest.raises(ValidationError, match="sample_index"):
            _make_obs(sample_index=-1)

    def test_cycle_to_failure_negative_raises(self) -> None:
        with pytest.raises(ValidationError, match="cycle_to_failure"):
            _make_obs(cycle_to_failure=-1)

    def test_ctf_normalized_above_one_raises(self) -> None:
        with pytest.raises(ValidationError, match="cycle_to_failure_normalized"):
            _make_obs(ctf_normalized="1.001")

    def test_ctf_normalized_negative_raises(self) -> None:
        with pytest.raises(ValidationError, match="cycle_to_failure_normalized"):
            _make_obs(ctf_normalized="-0.001")

    def test_wrong_sensor_feature_count_raises(self) -> None:
        with pytest.raises(ValidationError, match="sensor_features"):
            _make_obs(sensor_features=tuple(float(i) for i in range(10)))

    def test_source_row_zero_raises(self) -> None:
        with pytest.raises(ValidationError, match="source_row"):
            ToolLife968Observation(
                observation_id="test",
                source=_SOURCE_META,
                source_row=0,  # invalid
                tool_index=2,
                tool_type="1",
                adoc=Quantity(Decimal("5"), Unit.MM),
                rdoc=Quantity(Decimal("8"), Unit.MM),
                tool_holder_length=Quantity(Decimal("80"), Unit.MM),
                hardness_mean=Decimal("36.67"),
                cycle_number=1,
                sample_index=2,
                cycle_to_failure=49,
                cycle_to_failure_normalized=Decimal("1.0"),
                sensor_features=_SENSOR_FEATURES_120,
                provenance=_PROVENANCE,
                evidence_status=EvidenceStatus.EXPERIMENTAL,
            )
