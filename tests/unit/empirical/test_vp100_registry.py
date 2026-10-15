"""Tests for VP100EmpiricalRegistry (Stage EMPIRICAL-01A)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.cutting_parameters.models import EvidenceStatus
from backend.domain.base import Provenance
from backend.domain.enums import ProvenanceType
from backend.domain.units import Quantity, Unit
from backend.empirical.exceptions import EmpiricalDataError
from backend.empirical.models import VP100EmpiricalRecord, VP100SourceMeta
from backend.empirical.registry import VP100EmpiricalRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SOURCE_META = VP100SourceMeta(
    source_dataset="VP100-EXTERNAL-BENCHMARK",
    source_filename="MachiningPro_AI_VP100_EXTERNAL_BENCHMARK.xlsx",
    source_sha256="ee0f0ec8a25dcac8d26e65876e5f6d64fca671f30d6a668280edc9a7dd3f153c",
    source_sheet="VP100 Detailed Results",
)

_PROVENANCE = Provenance(
    source_type=ProvenanceType.HISTORICAL_PROCESS_DATA,
    source_reference="test",
)


def _make_record(
    record_id: str,
    tool_condition: str = "C0",
    coating: str = "Uncoated",
    combination: str = "A",
    replicate: int = 1,
) -> VP100EmpiricalRecord:
    return VP100EmpiricalRecord(
        record_id=record_id,
        source=_SOURCE_META,
        source_row=1,
        tool_condition=tool_condition,
        coating=coating,
        combination=combination,
        replicate=replicate,
        vc=Quantity(Decimal("125"), Unit.M_MIN),
        fz=Quantity(Decimal("0.1"), Unit.MM_TOOTH),
        ap=Quantity(Decimal("0.7"), Unit.MM),
        mrv=Quantity(Decimal("14"), Unit.CM3),
        t_eol=Quantity(Decimal("6.33"), Unit.MIN),
        rq=Quantity(Decimal("1.84"), Unit.RQ_UM),
        fx=Quantity(Decimal("330"), Unit.N),
        provenance=_PROVENANCE,
        evidence_status=EvidenceStatus.EXPERIMENTAL,
    )


def _fresh_registry(*records: VP100EmpiricalRecord) -> VP100EmpiricalRegistry:
    reg = VP100EmpiricalRegistry()
    if records:
        reg.register_all(list(records))
    return reg


# ---------------------------------------------------------------------------
# Construction and seeding
# ---------------------------------------------------------------------------

class TestRegistryConstruction:
    def test_new_registry_not_seeded(self) -> None:
        reg = VP100EmpiricalRegistry()
        assert not reg.is_seeded()
        assert reg.record_count() == 0

    def test_register_all_seeds_registry(self) -> None:
        reg = _fresh_registry(_make_record("VP100-001"))
        assert reg.is_seeded()
        assert reg.record_count() == 1

    def test_register_empty_list_marks_seeded(self) -> None:
        reg = VP100EmpiricalRegistry()
        reg.register_all([])
        assert reg.is_seeded()
        assert reg.record_count() == 0

    def test_register_all_returns_count(self) -> None:
        reg = VP100EmpiricalRegistry()
        count = reg.register_all([_make_record("VP100-001"), _make_record("VP100-002")])
        assert count == 2

    def test_duplicate_id_raises_without_flag(self) -> None:
        reg = VP100EmpiricalRegistry()
        reg.register_all([_make_record("VP100-001")])
        with pytest.raises(EmpiricalDataError, match="Duplicate"):
            reg.register_all([_make_record("VP100-001")])

    def test_duplicate_id_allowed_with_flag(self) -> None:
        reg = VP100EmpiricalRegistry()
        reg.register_all([_make_record("VP100-001")])
        count = reg.register_all([_make_record("VP100-001")], allow_reregister=True)
        assert count == 1

    def test_wrong_type_raises(self) -> None:
        reg = VP100EmpiricalRegistry()
        with pytest.raises(EmpiricalDataError, match="VP100EmpiricalRecord"):
            reg.register_all(["not-a-record"])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# Query before seeding
# ---------------------------------------------------------------------------

class TestQueryBeforeSeeding:
    def test_get_all_before_seed_raises(self) -> None:
        reg = VP100EmpiricalRegistry()
        with pytest.raises(EmpiricalDataError, match="not been seeded"):
            reg.get_all()

    def test_get_by_id_before_seed_raises(self) -> None:
        reg = VP100EmpiricalRegistry()
        with pytest.raises(EmpiricalDataError, match="not been seeded"):
            reg.get_by_id("VP100-001")

    def test_filter_before_seed_raises(self) -> None:
        reg = VP100EmpiricalRegistry()
        with pytest.raises(EmpiricalDataError, match="not been seeded"):
            reg.filter(tool_condition="C0")


# ---------------------------------------------------------------------------
# get_all
# ---------------------------------------------------------------------------

class TestGetAll:
    def test_get_all_returns_all_records(self) -> None:
        r1 = _make_record("VP100-001")
        r2 = _make_record("VP100-002")
        reg = _fresh_registry(r1, r2)
        all_recs = reg.get_all()
        assert len(all_recs) == 2
        assert {r.record_id for r in all_recs} == {"VP100-001", "VP100-002"}

    def test_get_all_returns_tuple(self) -> None:
        reg = _fresh_registry(_make_record("VP100-001"))
        assert isinstance(reg.get_all(), tuple)

    def test_get_all_empty_after_empty_register(self) -> None:
        reg = VP100EmpiricalRegistry()
        reg.register_all([])
        assert reg.get_all() == ()


# ---------------------------------------------------------------------------
# get_by_id
# ---------------------------------------------------------------------------

class TestGetById:
    def test_get_by_id_found(self) -> None:
        rec = _make_record("VP100-042")
        reg = _fresh_registry(rec)
        fetched = reg.get_by_id("VP100-042")
        assert fetched.record_id == "VP100-042"

    def test_get_by_id_not_found_raises(self) -> None:
        reg = _fresh_registry(_make_record("VP100-001"))
        with pytest.raises(EmpiricalDataError, match="VP100-999"):
            reg.get_by_id("VP100-999")


# ---------------------------------------------------------------------------
# filter
# ---------------------------------------------------------------------------

class TestFilter:
    def _make_fixture_registry(self) -> VP100EmpiricalRegistry:
        records = [
            _make_record("r-C0-A-1", "C0", "Uncoated", "A", 1),
            _make_record("r-C0-A-2", "C0", "Uncoated", "A", 2),
            _make_record("r-C0-B-1", "C0", "Uncoated", "B", 1),
            _make_record("r-C1-A-1", "C1", "TiN", "A", 1),
            _make_record("r-C2-A-1", "C2", "AlTiN", "A", 1),
        ]
        return _fresh_registry(*records)

    def test_filter_no_criteria_returns_all(self) -> None:
        reg = self._make_fixture_registry()
        assert len(reg.filter()) == 5

    def test_filter_by_tool_condition(self) -> None:
        reg = self._make_fixture_registry()
        result = reg.filter(tool_condition="C0")
        assert len(result) == 3
        assert all(r.tool_condition == "C0" for r in result)

    def test_filter_by_coating(self) -> None:
        reg = self._make_fixture_registry()
        result = reg.filter(coating="TiN")
        assert len(result) == 1
        assert result[0].record_id == "r-C1-A-1"

    def test_filter_by_combination(self) -> None:
        reg = self._make_fixture_registry()
        result = reg.filter(combination="B")
        assert len(result) == 1
        assert result[0].record_id == "r-C0-B-1"

    def test_filter_by_replicate(self) -> None:
        reg = self._make_fixture_registry()
        result = reg.filter(replicate=2)
        assert len(result) == 1
        assert result[0].record_id == "r-C0-A-2"

    def test_filter_multi_criteria(self) -> None:
        reg = self._make_fixture_registry()
        result = reg.filter(tool_condition="C0", combination="A")
        assert len(result) == 2
        assert all(r.combination == "A" and r.tool_condition == "C0" for r in result)

    def test_filter_no_match_returns_empty_tuple(self) -> None:
        reg = self._make_fixture_registry()
        result = reg.filter(tool_condition="C3")
        assert result == ()
        assert isinstance(result, tuple)

    def test_filter_returns_tuple(self) -> None:
        reg = self._make_fixture_registry()
        assert isinstance(reg.filter(tool_condition="C0"), tuple)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_vp100_registry_returns_same_instance(self) -> None:
        from backend.empirical.registry import get_vp100_registry
        r1 = get_vp100_registry()
        r2 = get_vp100_registry()
        assert r1 is r2
