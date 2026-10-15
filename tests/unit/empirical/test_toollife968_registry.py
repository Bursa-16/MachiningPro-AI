"""Tests for ToolLife968Registry (TOOLLIFE_968_DATA_INGESTION_01)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.cutting_parameters.models import EvidenceStatus
from backend.domain.base import Provenance
from backend.domain.enums import ProvenanceType
from backend.domain.units import Quantity, Unit
from backend.empirical.exceptions import EmpiricalDataError
from backend.empirical.toollife968_models import (
    ToolLife968Observation,
    ToolLife968SourceMeta,
)
from backend.empirical.toollife968_registry import (
    ToolLife968Registry,
    get_toollife968_registry,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SENSOR_HEADERS: tuple[str, ...] = tuple(f"s_{i}" for i in range(120))

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
    source_reference="test",
)

_SENSOR_120: tuple[float, ...] = tuple(float(i) for i in range(120))


def _make_obs(
    observation_id: str,
    tool_index: int = 2,
    tool_type: str = "1",
    adoc_mm: float = 5.0,
    rdoc_mm: float = 8.0,
    cycle_number: int = 1,
    cycle_to_failure: int = 49,
    ctf_normalized: float = 1.0,
) -> ToolLife968Observation:
    return ToolLife968Observation(
        observation_id=observation_id,
        source=_SOURCE_META,
        source_row=1,
        tool_index=tool_index,
        tool_type=tool_type,
        adoc=Quantity(Decimal(str(adoc_mm)), Unit.MM),
        rdoc=Quantity(Decimal(str(rdoc_mm)), Unit.MM),
        tool_holder_length=Quantity(Decimal("80"), Unit.MM),
        hardness_mean=Decimal("36.67"),
        cycle_number=cycle_number,
        sample_index=2,
        cycle_to_failure=cycle_to_failure,
        cycle_to_failure_normalized=Decimal(str(ctf_normalized)),
        sensor_features=_SENSOR_120,
        provenance=_PROVENANCE,
        evidence_status=EvidenceStatus.EXPERIMENTAL,
    )


def _fresh_registry(*obs: ToolLife968Observation) -> ToolLife968Registry:
    reg = ToolLife968Registry()
    if obs:
        reg.register_all(list(obs))
    return reg


# ---------------------------------------------------------------------------
# Construction and seeding
# ---------------------------------------------------------------------------

class TestRegistryConstruction:
    def test_new_registry_not_seeded(self) -> None:
        reg = ToolLife968Registry()
        assert not reg.is_seeded()
        assert reg.record_count() == 0

    def test_register_all_seeds_registry(self) -> None:
        reg = _fresh_registry(_make_obs("obs-001"))
        assert reg.is_seeded()
        assert reg.record_count() == 1

    def test_register_empty_list_marks_seeded(self) -> None:
        reg = ToolLife968Registry()
        reg.register_all([])
        assert reg.is_seeded()
        assert reg.record_count() == 0

    def test_register_all_returns_count(self) -> None:
        reg = ToolLife968Registry()
        count = reg.register_all([_make_obs("obs-001"), _make_obs("obs-002")])
        assert count == 2

    def test_duplicate_id_raises_without_flag(self) -> None:
        reg = ToolLife968Registry()
        reg.register_all([_make_obs("obs-001")])
        with pytest.raises(EmpiricalDataError, match="Duplicate"):
            reg.register_all([_make_obs("obs-001")])

    def test_duplicate_id_allowed_with_flag(self) -> None:
        reg = ToolLife968Registry()
        reg.register_all([_make_obs("obs-001")])
        count = reg.register_all([_make_obs("obs-001")], allow_reregister=True)
        assert count == 1

    def test_wrong_type_raises(self) -> None:
        reg = ToolLife968Registry()
        with pytest.raises(EmpiricalDataError, match="ToolLife968Observation"):
            reg.register_all(["not-an-obs"])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# Query before seeding
# ---------------------------------------------------------------------------

class TestQueryBeforeSeeding:
    def test_get_all_before_seed_raises(self) -> None:
        reg = ToolLife968Registry()
        with pytest.raises(EmpiricalDataError, match="not been seeded"):
            reg.get_all()

    def test_get_by_id_before_seed_raises(self) -> None:
        reg = ToolLife968Registry()
        with pytest.raises(EmpiricalDataError, match="not been seeded"):
            reg.get_by_id("obs-001")

    def test_filter_before_seed_raises(self) -> None:
        reg = ToolLife968Registry()
        with pytest.raises(EmpiricalDataError, match="not been seeded"):
            reg.filter(tool_index=2)

    def test_get_by_tool_before_seed_raises(self) -> None:
        reg = ToolLife968Registry()
        with pytest.raises(EmpiricalDataError, match="not been seeded"):
            reg.get_by_tool(2)

    def test_get_eol_before_seed_raises(self) -> None:
        reg = ToolLife968Registry()
        with pytest.raises(EmpiricalDataError, match="not been seeded"):
            reg.get_eol_observations()


# ---------------------------------------------------------------------------
# get_all
# ---------------------------------------------------------------------------

class TestGetAll:
    def test_get_all_returns_all_records(self) -> None:
        r1 = _make_obs("obs-001")
        r2 = _make_obs("obs-002")
        reg = _fresh_registry(r1, r2)
        all_obs = reg.get_all()
        assert len(all_obs) == 2
        assert {o.observation_id for o in all_obs} == {"obs-001", "obs-002"}

    def test_get_all_returns_tuple(self) -> None:
        reg = _fresh_registry(_make_obs("obs-001"))
        assert isinstance(reg.get_all(), tuple)

    def test_get_all_empty_after_empty_register(self) -> None:
        reg = ToolLife968Registry()
        reg.register_all([])
        assert reg.get_all() == ()


# ---------------------------------------------------------------------------
# get_by_id
# ---------------------------------------------------------------------------

class TestGetById:
    def test_get_by_id_found(self) -> None:
        obs = _make_obs("P002_F01_C1")
        reg = _fresh_registry(obs)
        fetched = reg.get_by_id("P002_F01_C1")
        assert fetched.observation_id == "P002_F01_C1"

    def test_get_by_id_not_found_raises(self) -> None:
        reg = _fresh_registry(_make_obs("obs-001"))
        with pytest.raises(EmpiricalDataError, match="obs-999"):
            reg.get_by_id("obs-999")


# ---------------------------------------------------------------------------
# filter
# ---------------------------------------------------------------------------

class TestFilter:
    def _make_fixture_registry(self) -> ToolLife968Registry:
        records = [
            _make_obs("t2-c1-a5-r8", tool_index=2, tool_type="1", adoc_mm=5.0, rdoc_mm=8.0),
            _make_obs("t2-c2-a5-r8", tool_index=2, tool_type="2", adoc_mm=5.0, rdoc_mm=8.0),
            _make_obs("t3-c1-a10-r8", tool_index=3, tool_type="1", adoc_mm=10.0, rdoc_mm=8.0),
            _make_obs("t3-c1-a5-r4", tool_index=3, tool_type="1", adoc_mm=5.0, rdoc_mm=4.5),
            _make_obs(
                "t2-eol", tool_index=2, tool_type="1",
                cycle_number=50, cycle_to_failure=0, ctf_normalized=0.0,
            ),
        ]
        return _fresh_registry(*records)

    def test_filter_no_criteria_returns_all(self) -> None:
        reg = self._make_fixture_registry()
        assert len(reg.filter()) == 5

    def test_filter_by_tool_index(self) -> None:
        reg = self._make_fixture_registry()
        result = reg.filter(tool_index=2)
        assert len(result) == 3
        assert all(r.tool_index == 2 for r in result)

    def test_filter_by_tool_type(self) -> None:
        reg = self._make_fixture_registry()
        result = reg.filter(tool_type="2")
        assert len(result) == 1
        assert result[0].observation_id == "t2-c2-a5-r8"

    def test_filter_by_adoc(self) -> None:
        reg = self._make_fixture_registry()
        result = reg.filter(adoc_mm=10.0)
        assert len(result) == 1
        assert result[0].observation_id == "t3-c1-a10-r8"

    def test_filter_by_rdoc(self) -> None:
        reg = self._make_fixture_registry()
        result = reg.filter(rdoc_mm=4.5)
        assert len(result) == 1
        assert result[0].observation_id == "t3-c1-a5-r4"

    def test_filter_eol_only(self) -> None:
        reg = self._make_fixture_registry()
        result = reg.filter(eol_only=True)
        assert len(result) == 1
        assert result[0].observation_id == "t2-eol"
        assert result[0].is_eol is True

    def test_filter_multi_criteria(self) -> None:
        reg = self._make_fixture_registry()
        result = reg.filter(tool_index=2, tool_type="1")
        ids = {r.observation_id for r in result}
        assert ids == {"t2-c1-a5-r8", "t2-eol"}

    def test_filter_no_match_returns_empty_tuple(self) -> None:
        reg = self._make_fixture_registry()
        result = reg.filter(tool_index=999)
        assert result == ()
        assert isinstance(result, tuple)

    def test_filter_returns_tuple(self) -> None:
        reg = self._make_fixture_registry()
        assert isinstance(reg.filter(tool_index=2), tuple)


# ---------------------------------------------------------------------------
# get_by_tool and get_eol_observations
# ---------------------------------------------------------------------------

class TestGetByToolAndEol:
    def _make_tool2_registry(self) -> ToolLife968Registry:
        records = [
            _make_obs("t2-c3", tool_index=2, cycle_number=3, cycle_to_failure=47,
                      ctf_normalized=0.959),
            _make_obs("t2-c1", tool_index=2, cycle_number=1, cycle_to_failure=49,
                      ctf_normalized=1.0),
            _make_obs("t2-c2", tool_index=2, cycle_number=2, cycle_to_failure=48,
                      ctf_normalized=0.979),
            _make_obs("t3-c1", tool_index=3, cycle_number=1, cycle_to_failure=49,
                      ctf_normalized=1.0),
            _make_obs("t2-eol", tool_index=2, cycle_number=50, cycle_to_failure=0,
                      ctf_normalized=0.0),
        ]
        return _fresh_registry(*records)

    def test_get_by_tool_returns_only_that_tool(self) -> None:
        reg = self._make_tool2_registry()
        result = reg.get_by_tool(2)
        assert all(r.tool_index == 2 for r in result)
        assert len(result) == 4

    def test_get_by_tool_sorted_by_cycle_number(self) -> None:
        reg = self._make_tool2_registry()
        result = reg.get_by_tool(2)
        cycle_numbers = [r.cycle_number for r in result]
        assert cycle_numbers == sorted(cycle_numbers)

    def test_get_eol_observations_returns_eol_only(self) -> None:
        reg = self._make_tool2_registry()
        eol = reg.get_eol_observations()
        assert len(eol) == 1
        assert eol[0].observation_id == "t2-eol"
        assert all(r.is_eol for r in eol)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_toollife968_registry_returns_same_instance(self) -> None:
        r1 = get_toollife968_registry()
        r2 = get_toollife968_registry()
        assert r1 is r2
