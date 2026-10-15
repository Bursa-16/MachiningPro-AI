"""Tests for ToolLife 968 XLSX loader (TOOLLIFE_968_DATA_INGESTION_01).

Unit tests use _parse_row directly (no XLSX file needed).
Integration tests load from the actual source path (skipped when unavailable).

Source data fingerprints verified:
  - FileName "P002_F01_C1": TollIndex=2, NumberOfCycle=1, SampleIndex=2,
    ADOC=5, RDOC=8, HardnessMean=36.67, ToolHolderLength=80,
    CycleToFailure=49, CycleToFailureNormalized=1.0
  - TollIndex=11: 1 observation only (CycleToFailure=0 at cycle 1)
  - TollIndex=9: max CycleToFailure=149 (longest-lived tool, 150 cycles)
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from backend.cutting_parameters.models import EvidenceStatus
from backend.domain.base import Provenance
from backend.domain.enums import ProvenanceType
from backend.domain.units import Unit
from backend.empirical.toollife968_loader import (
    TOOLLIFE968_EXPECTED_ROW_COUNT,
    TOOLLIFE968_SOURCE_SHA256,
    _parse_row,
    load_toollife968_records,
)
from backend.empirical.toollife968_models import (
    TOOLLIFE968_SENSOR_FEATURE_COUNT,
    TOOLLIFE968_SHEET_NAME,
    ToolLife968SourceMeta,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SENSOR_HEADERS: tuple[str, ...] = tuple(f"sensor_{i}" for i in range(120))

_SOURCE_META = ToolLife968SourceMeta(
    source_dataset="TOOLLIFE-968",
    source_filename="MachiningPro_AI_VP100_EXTERNAL_BENCHMARK.xlsx",
    source_sha256=TOOLLIFE968_SOURCE_SHA256,
    source_sheet=TOOLLIFE968_SHEET_NAME,
    doi="10.6084/m9.figshare.28589216",
    sensor_feature_headers=_SENSOR_HEADERS,
)

_PROVENANCE = Provenance(
    source_type=ProvenanceType.HISTORICAL_PROCESS_DATA,
    source_reference="test fixture",
)

# Verbatim values for data row 1 (FileName=P002_F01_C1)
_SENSOR_120 = tuple(float(-20620 + i) for i in range(120))

def _make_raw_row(
    filename: str = "P002_F01_C1",
    number_of_cycle: int = 1,
    sample_index: int = 2,
    toll_index: int = 2,
    milling_tool_type: str = "1",
    adoc: int | float = 5,
    rdoc: int | float = 8,
    hardness_mean: float = 36.67,
    tool_holder_length: int = 80,
    cycle_to_failure: int = 49,
    ctf_normalized: float = 1.0,
    sensor_values: tuple = _SENSOR_120,
) -> tuple:
    """Build a raw row tuple matching the sheet column layout."""
    row = list(sensor_values)  # cols 0–119
    row.append(filename)           # 120 FileName
    row.append(number_of_cycle)    # 121 NumberOfCycle
    row.append(sample_index)       # 122 SampleIndex
    row.append(toll_index)         # 123 TollIndex
    row.append(milling_tool_type)  # 124 MillingToolType
    row.append(adoc)               # 125 ADOC
    row.append(rdoc)               # 126 RDOC
    row.append(hardness_mean)      # 127 HardnessMean
    row.append(tool_holder_length) # 128 ToolHolderLength
    row.append(cycle_to_failure)   # 129 CycleToFailure
    row.append(ctf_normalized)     # 130 CycleToFailureNormalized
    return tuple(row)


# ---------------------------------------------------------------------------
# _parse_row unit tests (no XLSX needed)
# ---------------------------------------------------------------------------

class TestParseRow:
    def test_parse_first_row_ok(self) -> None:
        row = _make_raw_row()
        result = _parse_row(1, row, _SOURCE_META, _PROVENANCE)
        assert not isinstance(result, str), f"Rejected: {result}"
        assert result.observation_id == "P002_F01_C1"
        assert result.tool_index == 2
        assert result.tool_type == "1"
        assert result.adoc.value == Decimal("5")
        assert result.adoc.unit is Unit.MM
        assert result.rdoc.value == Decimal("8")
        assert result.rdoc.unit is Unit.MM
        assert result.tool_holder_length.value == Decimal("80")
        assert result.tool_holder_length.unit is Unit.MM
        assert result.cycle_number == 1
        assert result.sample_index == 2
        assert result.cycle_to_failure == 49
        assert result.cycle_to_failure_normalized == Decimal("1.0")
        assert result.source_row == 1
        assert result.evidence_status is EvidenceStatus.EXPERIMENTAL
        assert len(result.sensor_features) == TOOLLIFE968_SENSOR_FEATURE_COUNT

    def test_eol_row_parsed_correctly(self) -> None:
        """CTF=0 at cycle 50: EOL row for tool 2."""
        row = _make_raw_row(
            filename="P002_F50_C1",
            number_of_cycle=50,
            cycle_to_failure=0,
            ctf_normalized=0.0,
        )
        result = _parse_row(50, row, _SOURCE_META, _PROVENANCE)
        assert not isinstance(result, str), f"Rejected: {result}"
        assert result.is_eol is True
        assert result.cycle_to_failure == 0

    def test_degenerate_tool11_ctf0_cycle1(self) -> None:
        """TollIndex=11: CTF=0 at first cycle."""
        row = _make_raw_row(
            filename="P011_F01_C1",
            toll_index=11,
            number_of_cycle=1,
            cycle_to_failure=0,
            ctf_normalized=0.0,
        )
        result = _parse_row(1, row, _SOURCE_META, _PROVENANCE)
        assert not isinstance(result, str), f"Rejected: {result}"
        assert result.tool_index == 11
        assert result.is_eol is True
        assert result.total_tool_life_cycles == 1

    def test_tool9_first_cycle_ctf149(self) -> None:
        """TollIndex=9: CTF=149 at first cycle → total life 150 cycles."""
        row = _make_raw_row(
            filename="P009_F01_C1",
            toll_index=9,
            number_of_cycle=1,
            cycle_to_failure=149,
            ctf_normalized=1.0,
        )
        result = _parse_row(1, row, _SOURCE_META, _PROVENANCE)
        assert not isinstance(result, str), f"Rejected: {result}"
        assert result.total_tool_life_cycles == 150

    def test_tool_type_2_accepted(self) -> None:
        row = _make_raw_row(milling_tool_type="2")
        result = _parse_row(1, row, _SOURCE_META, _PROVENANCE)
        assert not isinstance(result, str)
        assert result.tool_type == "2"

    def test_sensor_features_stored_as_float(self) -> None:
        row = _make_raw_row()
        result = _parse_row(1, row, _SOURCE_META, _PROVENANCE)
        assert not isinstance(result, str)
        assert all(isinstance(v, float) for v in result.sensor_features)

    def test_null_filename_falls_back_to_row_id(self) -> None:
        row = _make_raw_row(filename=None)
        result = _parse_row(7, row, _SOURCE_META, _PROVENANCE)
        assert not isinstance(result, str)
        assert result.observation_id == "row-7"

    def test_null_toll_index_returns_rejection(self) -> None:
        row = _make_raw_row(toll_index=None)
        result = _parse_row(1, row, _SOURCE_META, _PROVENANCE)
        assert isinstance(result, str)
        assert "TollIndex" in result

    def test_zero_toll_index_returns_rejection(self) -> None:
        row = _make_raw_row(toll_index=0)
        result = _parse_row(1, row, _SOURCE_META, _PROVENANCE)
        assert isinstance(result, str)
        assert "TollIndex" in result

    def test_invalid_tool_type_returns_rejection(self) -> None:
        row = _make_raw_row(milling_tool_type="3")
        result = _parse_row(1, row, _SOURCE_META, _PROVENANCE)
        assert isinstance(result, str)
        assert "MillingToolType" in result

    def test_zero_adoc_returns_rejection(self) -> None:
        row = _make_raw_row(adoc=0)
        result = _parse_row(1, row, _SOURCE_META, _PROVENANCE)
        assert isinstance(result, str)
        assert "ADOC" in result

    def test_zero_rdoc_returns_rejection(self) -> None:
        row = _make_raw_row(rdoc=0)
        result = _parse_row(1, row, _SOURCE_META, _PROVENANCE)
        assert isinstance(result, str)
        assert "RDOC" in result

    def test_null_hardness_returns_rejection(self) -> None:
        row = _make_raw_row(hardness_mean=None)
        result = _parse_row(1, row, _SOURCE_META, _PROVENANCE)
        assert isinstance(result, str)
        assert "HardnessMean" in result

    def test_negative_cycle_to_failure_returns_rejection(self) -> None:
        row = _make_raw_row(cycle_to_failure=-1)
        result = _parse_row(1, row, _SOURCE_META, _PROVENANCE)
        assert isinstance(result, str)
        assert "CycleToFailure" in result

    def test_ctf_normalized_above_one_returns_rejection(self) -> None:
        row = _make_raw_row(ctf_normalized=1.001)
        result = _parse_row(1, row, _SOURCE_META, _PROVENANCE)
        assert isinstance(result, str)
        assert "CycleToFailureNormalized" in result

    def test_null_sensor_feature_returns_rejection(self) -> None:
        bad_sensors = list(_SENSOR_120)
        bad_sensors[5] = None
        row = _make_raw_row(sensor_values=tuple(bad_sensors))
        result = _parse_row(1, row, _SOURCE_META, _PROVENANCE)
        assert isinstance(result, str)
        assert "sensor feature" in result.lower()

    def test_zero_cycle_number_returns_rejection(self) -> None:
        row = _make_raw_row(number_of_cycle=0)
        result = _parse_row(1, row, _SOURCE_META, _PROVENANCE)
        assert isinstance(result, str)
        assert "NumberOfCycle" in result

    def test_integer_sensor_values_accepted_as_float(self) -> None:
        """openpyxl returns int for some sensor cells — must parse to float."""
        int_sensors = tuple(int(i) for i in range(120))
        row = _make_raw_row(sensor_values=int_sensors)
        result = _parse_row(1, row, _SOURCE_META, _PROVENANCE)
        assert not isinstance(result, str)
        assert all(isinstance(v, float) for v in result.sensor_features)


# ---------------------------------------------------------------------------
# Source schema constants
# ---------------------------------------------------------------------------

class TestSourceConstants:
    def test_expected_row_count(self) -> None:
        assert TOOLLIFE968_EXPECTED_ROW_COUNT == 968

    def test_sha256_is_lowercase_hex(self) -> None:
        sha = TOOLLIFE968_SOURCE_SHA256
        assert len(sha) == 64
        assert sha == sha.lower()
        assert all(c in "0123456789abcdef" for c in sha)

    def test_sheet_name(self) -> None:
        assert TOOLLIFE968_SHEET_NAME == "Golden ToolLife 968"


# ---------------------------------------------------------------------------
# Integration test — requires actual XLSX on D: drive
# ---------------------------------------------------------------------------

_TOOLLIFE968_SOURCE_PATH = Path(
    r"D:\makina_ogrenmesi\MachiningPro_ AI"
    r"\MachiningPro_AI_VP100_EXTERNAL_BENCHMARK.xlsx"
)

_SKIP_IF_NO_XLSX = pytest.mark.skipif(
    not _TOOLLIFE968_SOURCE_PATH.exists(),
    reason=f"ToolLife 968 source XLSX not available at {_TOOLLIFE968_SOURCE_PATH}",
)


@_SKIP_IF_NO_XLSX
class TestLoadToolLife968RecordsIntegration:
    def test_loads_exactly_968_records(self) -> None:
        records, rejections = load_toollife968_records(_TOOLLIFE968_SOURCE_PATH)
        sha_rejections = [r for r in rejections if "SHA" in r]
        assert sha_rejections == [], f"SHA mismatch: {sha_rejections}"
        parse_rejections = [r for r in rejections if "SHA" not in r]
        assert parse_rejections == [], f"Parse rejections: {parse_rejections}"
        assert len(records) == TOOLLIFE968_EXPECTED_ROW_COUNT

    def test_all_observation_ids_unique(self) -> None:
        records, _ = load_toollife968_records(_TOOLLIFE968_SOURCE_PATH)
        ids = [r.observation_id for r in records]
        assert len(ids) == len(set(ids))

    def test_first_record_matches_source_row_1(self) -> None:
        records, _ = load_toollife968_records(_TOOLLIFE968_SOURCE_PATH)
        r = records[0]
        assert r.observation_id == "P002_F01_C1"
        assert r.tool_index == 2
        assert r.tool_type == "1"
        assert r.adoc.value == Decimal("5")
        assert r.adoc.unit is Unit.MM
        assert r.rdoc.value == Decimal("8")
        assert r.cycle_number == 1
        assert r.sample_index == 2
        assert r.cycle_to_failure == 49
        assert r.cycle_to_failure_normalized == Decimal("1.0")

    def test_exactly_14_eol_observations(self) -> None:
        """One EOL per tool; 14 tools → 14 EOL rows."""
        records, _ = load_toollife968_records(_TOOLLIFE968_SOURCE_PATH)
        eol_records = [r for r in records if r.is_eol]
        assert len(eol_records) == 14

    def test_14_distinct_tool_indices(self) -> None:
        records, _ = load_toollife968_records(_TOOLLIFE968_SOURCE_PATH)
        tool_indices = {r.tool_index for r in records}
        assert len(tool_indices) == 14
        expected = {2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 101, 102, 103, 105}
        assert tool_indices == expected

    def test_tool11_single_observation_is_eol(self) -> None:
        """TollIndex=11: exactly 1 observation, CTF=0."""
        records, _ = load_toollife968_records(_TOOLLIFE968_SOURCE_PATH)
        tool11 = [r for r in records if r.tool_index == 11]
        assert len(tool11) == 1
        assert tool11[0].is_eol is True
        assert tool11[0].cycle_to_failure == 0

    def test_tool9_has_most_observations(self) -> None:
        """TollIndex=9: 149 observations (longest-lived)."""
        records, _ = load_toollife968_records(_TOOLLIFE968_SOURCE_PATH)
        tool9 = [r for r in records if r.tool_index == 9]
        assert len(tool9) == 149

    def test_all_adoc_values_are_5_or_10(self) -> None:
        records, _ = load_toollife968_records(_TOOLLIFE968_SOURCE_PATH)
        adoc_values = {float(r.adoc.value) for r in records}
        assert adoc_values == {5.0, 10.0}

    def test_all_rdoc_values_are_4_5_or_8(self) -> None:
        records, _ = load_toollife968_records(_TOOLLIFE968_SOURCE_PATH)
        rdoc_values = {float(r.rdoc.value) for r in records}
        assert rdoc_values == {4.5, 8.0}

    def test_all_sensor_feature_vectors_length_120(self) -> None:
        records, _ = load_toollife968_records(_TOOLLIFE968_SOURCE_PATH)
        for rec in records:
            assert len(rec.sensor_features) == TOOLLIFE968_SENSOR_FEATURE_COUNT

    def test_all_evidence_status_experimental(self) -> None:
        records, _ = load_toollife968_records(_TOOLLIFE968_SOURCE_PATH)
        for rec in records:
            assert rec.evidence_status is EvidenceStatus.EXPERIMENTAL

    def test_total_tool_life_consistent_per_tool(self) -> None:
        """total_tool_life_cycles must be constant for all observations of a tool."""
        records, _ = load_toollife968_records(_TOOLLIFE968_SOURCE_PATH)
        from collections import defaultdict
        totals: dict[int, set[int]] = defaultdict(set)
        for rec in records:
            totals[rec.tool_index].add(rec.total_tool_life_cycles)
        for tool_index, life_set in totals.items():
            assert len(life_set) == 1, (
                f"TollIndex={tool_index}: inconsistent total_tool_life_cycles: {life_set}"
            )

    def test_file_not_found_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_toollife968_records(Path("/does/not/exist/file.xlsx"))

    def test_idempotent_reload(self) -> None:
        r1, rej1 = load_toollife968_records(_TOOLLIFE968_SOURCE_PATH)
        r2, rej2 = load_toollife968_records(_TOOLLIFE968_SOURCE_PATH)
        assert len(r1) == len(r2)
        assert rej1 == rej2
