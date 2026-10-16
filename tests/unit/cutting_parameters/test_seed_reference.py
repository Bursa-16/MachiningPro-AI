"""Tests for reference_parser and seed_reference_registry (CUTTING_PARAMETER_DATA_INTEGRATION_01).

All tests use a synthetic Markdown fixture to avoid dependency on the
external research report file (MACHININGPRO_CUTTING_PARAM_REF_PATH).

Hard Rules verified
-------------------
HR 02  VP100 and ToolLife968 data are not used as cutting parameter sources.
HR 04  ISO material group mapping is truthful.
HR 05  All records carry REFERENCE_ONLY (not AUTHORITATIVE).
HR 07  Parameters not in source are not invented (ap absent from drilling/reaming).
HR 10  No RPM records are produced.
HR 11  fz (FEED_PER_TOOTH) and fn (FEED_PER_REV) are separate ParameterTypes.
HR 12  ap (AXIAL_DEPTH_OF_CUT) only in turning and milling, never drilling/reaming.
HR 15  Provenance fields source_reference and source_document are populated.
HR 17  Duplicate record IDs are detected by registry.register().
HR 22  Ingestion is reproducible and idempotent (same file → same records).
HR 28  All records are REFERENCE_ONLY — no ML labels.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from backend.cutting_parameters.models import (
    ApplicabilityScope,
    EvidenceStatus,
    ParameterType,
)
from backend.cutting_parameters.reference_parser import (
    _parse_range,
    _tr_decimal,
    parse_reference_report,
)
from backend.cutting_parameters.registry import CuttingParameterRegistry
from backend.cutting_parameters.seed_reference import (
    _ENV_VAR,
    seed_reference_registry,
)
from backend.cutting_parameters.validation import (
    is_usable_for_authority,
    require_authoritative,
)
from backend.domain.enums import (
    IsoMaterialGroup,
    OperationType,
    ToolMaterial,
)
from backend.domain.units import Unit
from backend.empirical.exceptions import EmpiricalDataError

# ---------------------------------------------------------------------------
# Synthetic Markdown fixture — one row per operation for a fast, hermetic test
# ---------------------------------------------------------------------------

_SYNTHETIC_MD = """\
# Test Report

Some preamble text.

## Turning

| Malzeme | Tercih edilen takım | Vc, m/min | f, mm/rev | ap, mm |
|---|---|---|---|---|
| ISO P çelik | CVD/PVD karbür | 120–280 | 0,10–0,45 | 0,5–4,0 |
| ISO M paslanmaz | PVD/CVD karbür | 70–180 | 0,08–0,30 | 0,4–3,0 |
| ISO S Ti | PVD/kaplamasız karbür | 35–90 | 0,05–0,25 | 0,3–2,5 |
| ISO S Ni-HRSA | PVD karbür | 20–70 | 0,05–0,20 | 0,2–2,0 |
| ISO S Ni-HRSA | SiAlON/whisker seramik | 120–350* | 0,05–0,25 | 0,5–3,0 |
| ISO H 50–65 HRC | CBN | 80–220 | 0,05–0,20 | 0,05–0,50 |

## Milling

| Malzeme | Takım | Vc, m/min | fz, mm/diş | ap, mm |
|---|---|---|---|---|
| P | Karbür | 120–260 | 0,03–0,18 | 0,2–6 |
| M | PVD karbür | 70–180 | 0,02–0,12 | 0,2–4 |
| S Ti | PVD karbür | 35–90 | 0,02–0,10 | 0,2–3 |

## Drilling

| Malzeme | Vc, m/min | fn, mm/dev |
|---|---|---|
| P | 80–180 | 0,08–0,30 |
| M | 50–110 | 0,06–0,22 |
| Ti (→ S grubu) | 30–70 | 0,05–0,18 |

## Reaming

| Malzeme | Vc, m/min | f, mm/dev | Radyal işleme payı, mm |
|---|---|---|---|
| P | 40–120 | 0,15–0,50 | 0,1–0,5 |
| S | 15–60 | 0,08–0,30 | 0,05–0,2 |
"""


@pytest.fixture
def synthetic_md_path(tmp_path: Path) -> Path:
    f = tmp_path / "ref_report.md"
    f.write_text(_SYNTHETIC_MD, encoding="utf-8")
    return f


@pytest.fixture
def parsed_records(synthetic_md_path: Path):
    return parse_reference_report(synthetic_md_path)


# ---------------------------------------------------------------------------
# _tr_decimal and _parse_range unit tests
# ---------------------------------------------------------------------------

class TestNumericHelpers:
    def test_tr_decimal_comma(self):
        assert _tr_decimal("0,10") == Decimal("0.10")

    def test_tr_decimal_strips_asterisk(self):
        assert _tr_decimal("2000*") == Decimal("2000")

    def test_tr_decimal_strips_plus(self):
        assert _tr_decimal("1200+") == Decimal("1200")

    def test_tr_decimal_plain(self):
        assert _tr_decimal("120") == Decimal("120")

    def test_parse_range_en_dash(self):
        lo, hi = _parse_range("120–280")
        assert lo == Decimal("120")
        assert hi == Decimal("280")

    def test_parse_range_comma_decimal(self):
        lo, hi = _parse_range("0,10–0,45")
        assert lo == Decimal("0.10")
        assert hi == Decimal("0.45")

    def test_parse_range_with_asterisk(self):
        lo, hi = _parse_range("120–350*")
        assert lo == Decimal("120")
        assert hi == Decimal("350")

    def test_parse_range_with_plus(self):
        lo, hi = _parse_range("300–1200+")
        assert lo == Decimal("300")
        assert hi == Decimal("1200")

    def test_parse_range_ascii_hyphen(self):
        lo, hi = _parse_range("80-180")
        assert lo == Decimal("80")
        assert hi == Decimal("180")


# ---------------------------------------------------------------------------
# Record count verification
# ---------------------------------------------------------------------------

class TestRecordCount:
    def test_turning_produces_3_params_per_row(self, parsed_records):
        turn_records = [r for r in parsed_records
                        if r.applicability.operation_type is OperationType.TURNING]
        # 6 rows × 3 params = 18
        assert len(turn_records) == 18

    def test_milling_produces_3_params_per_row(self, parsed_records):
        mill_records = [r for r in parsed_records
                        if r.applicability.operation_type is OperationType.MILLING]
        # 3 rows × 3 params = 9
        assert len(mill_records) == 9

    def test_drilling_produces_2_params_per_row(self, parsed_records):
        drill_records = [r for r in parsed_records
                         if r.applicability.operation_type is OperationType.DRILLING]
        # 3 rows × 2 params = 6 (no ap — Hard Rule 12)
        assert len(drill_records) == 6

    def test_reaming_produces_2_params_per_row(self, parsed_records):
        ream_records = [r for r in parsed_records
                        if r.applicability.operation_type is OperationType.REAMING]
        # 2 rows × 2 params = 4 (no ap — Hard Rule 12)
        assert len(ream_records) == 4

    def test_total_record_count(self, parsed_records):
        # 18 + 9 + 6 + 4 = 37
        assert len(parsed_records) == 37


# ---------------------------------------------------------------------------
# Evidence status — Hard Rules 05, 28, 29
# ---------------------------------------------------------------------------

class TestEvidenceStatus:
    def test_all_records_are_reference_only(self, parsed_records):
        for r in parsed_records:
            assert r.evidence_status is EvidenceStatus.REFERENCE_ONLY, (
                f"Record {r.record_id} has status {r.evidence_status}"
            )

    def test_no_record_is_authoritative(self, parsed_records):
        for r in parsed_records:
            assert not r.is_authoritative, (
                f"Record {r.record_id} claims is_authoritative=True"
            )

    def test_require_authoritative_raises_for_all_records(self, parsed_records):
        for r in parsed_records:
            with pytest.raises(EmpiricalDataError):
                require_authoritative(r)

    def test_is_usable_for_authority_false_for_all_records(self, parsed_records):
        for r in parsed_records:
            assert is_usable_for_authority(r) is False


# ---------------------------------------------------------------------------
# No ap for drilling and reaming — Hard Rule 12
# ---------------------------------------------------------------------------

class TestApRule12:
    def test_no_ap_in_drilling(self, parsed_records):
        drilling_ap = [
            r for r in parsed_records
            if r.applicability.operation_type is OperationType.DRILLING
            and r.parameter_type is ParameterType.AXIAL_DEPTH_OF_CUT
        ]
        assert drilling_ap == [], (
            "DRILLING must not have AXIAL_DEPTH_OF_CUT records (Hard Rule 12)"
        )

    def test_no_ap_in_reaming(self, parsed_records):
        reaming_ap = [
            r for r in parsed_records
            if r.applicability.operation_type is OperationType.REAMING
            and r.parameter_type is ParameterType.AXIAL_DEPTH_OF_CUT
        ]
        assert reaming_ap == [], (
            "REAMING must not have AXIAL_DEPTH_OF_CUT records (Hard Rule 12)"
        )

    def test_ap_present_in_turning(self, parsed_records):
        turning_ap = [
            r for r in parsed_records
            if r.applicability.operation_type is OperationType.TURNING
            and r.parameter_type is ParameterType.AXIAL_DEPTH_OF_CUT
        ]
        assert len(turning_ap) > 0

    def test_ap_present_in_milling(self, parsed_records):
        milling_ap = [
            r for r in parsed_records
            if r.applicability.operation_type is OperationType.MILLING
            and r.parameter_type is ParameterType.AXIAL_DEPTH_OF_CUT
        ]
        assert len(milling_ap) > 0


# ---------------------------------------------------------------------------
# Feed-type distinction — Hard Rule 11
# ---------------------------------------------------------------------------

class TestFeedTypeDistinction:
    def test_milling_uses_feed_per_tooth_not_feed_per_rev(self, parsed_records):
        mill_feeds = [
            r for r in parsed_records
            if r.applicability.operation_type is OperationType.MILLING
            and r.parameter_type in (ParameterType.FEED_PER_TOOTH, ParameterType.FEED_PER_REV)
        ]
        fz_records = [r for r in mill_feeds if r.parameter_type is ParameterType.FEED_PER_TOOTH]
        fn_records = [r for r in mill_feeds if r.parameter_type is ParameterType.FEED_PER_REV]
        assert len(fz_records) > 0, "Milling should have FEED_PER_TOOTH records"
        assert len(fn_records) == 0, "Milling must not have FEED_PER_REV records"

    def test_fz_records_use_mm_tooth_unit(self, parsed_records):
        fz_records = [r for r in parsed_records if r.parameter_type is ParameterType.FEED_PER_TOOTH]
        for r in fz_records:
            assert r.value_range.unit is Unit.MM_TOOTH, (
                f"FEED_PER_TOOTH record {r.record_id} has wrong unit {r.value_range.unit}"
            )

    def test_drilling_uses_feed_per_rev_not_feed_per_tooth(self, parsed_records):
        drill_feeds = [
            r for r in parsed_records
            if r.applicability.operation_type is OperationType.DRILLING
            and r.parameter_type in (ParameterType.FEED_PER_TOOTH, ParameterType.FEED_PER_REV)
        ]
        fn_records = [r for r in drill_feeds if r.parameter_type is ParameterType.FEED_PER_REV]
        fz_records = [r for r in drill_feeds if r.parameter_type is ParameterType.FEED_PER_TOOTH]
        assert len(fn_records) > 0, "Drilling should have FEED_PER_REV records"
        assert len(fz_records) == 0, "Drilling must not have FEED_PER_TOOTH records"

    def test_fn_records_use_mm_rev_unit(self, parsed_records):
        fn_records = [
            r for r in parsed_records
            if r.applicability.operation_type in (OperationType.DRILLING, OperationType.REAMING)
            and r.parameter_type is ParameterType.FEED_PER_REV
        ]
        for r in fn_records:
            assert r.value_range.unit is Unit.MM_REV, (
                f"FEED_PER_REV record {r.record_id} has wrong unit {r.value_range.unit}"
            )


# ---------------------------------------------------------------------------
# No RPM records — Hard Rule 10
# ---------------------------------------------------------------------------

class TestNoRPM:
    def test_no_rpm_records_produced(self, parsed_records):
        for r in parsed_records:
            assert r.value_range.unit is not Unit.RPM, (
                f"Record {r.record_id} contains an RPM value — must be calculated at runtime"
            )

    def test_cutting_speed_records_use_m_min(self, parsed_records):
        vc_records = [r for r in parsed_records if r.parameter_type is ParameterType.CUTTING_SPEED]
        assert len(vc_records) > 0
        for r in vc_records:
            assert r.value_range.unit is Unit.M_MIN


# ---------------------------------------------------------------------------
# ISO material group mapping — Hard Rule 04
# ---------------------------------------------------------------------------

class TestIsoMaterialGroupMapping:
    def test_iso_p_row_maps_to_group_p(self, parsed_records):
        p_records = [
            r for r in parsed_records
            if r.applicability.operation_type is OperationType.TURNING
            and r.applicability.iso_material_group is IsoMaterialGroup.P
        ]
        assert len(p_records) > 0

    def test_iso_s_ti_row_maps_to_group_s(self, parsed_records):
        s_ti_records = [
            r for r in parsed_records
            if r.applicability.operation_type is OperationType.TURNING
            and r.applicability.iso_material_group is IsoMaterialGroup.S
        ]
        assert len(s_ti_records) > 0

    def test_iso_h_row_maps_to_group_h(self, parsed_records):
        h_records = [
            r for r in parsed_records
            if r.applicability.operation_type is OperationType.TURNING
            and r.applicability.iso_material_group is IsoMaterialGroup.H
        ]
        assert len(h_records) > 0

    def test_turning_ti_and_ni_map_to_s_group(self, parsed_records):
        s_records = [
            r for r in parsed_records
            if r.applicability.operation_type is OperationType.TURNING
            and r.applicability.iso_material_group is IsoMaterialGroup.S
        ]
        # Ti, Ni-HRSA carbide, Ni-HRSA ceramic = 3 rows × 3 params = 9
        assert len(s_records) == 9

    def test_drilling_ti_maps_to_s_group(self, parsed_records):
        drill_s = [
            r for r in parsed_records
            if r.applicability.operation_type is OperationType.DRILLING
            and r.applicability.iso_material_group is IsoMaterialGroup.S
        ]
        assert len(drill_s) > 0


# ---------------------------------------------------------------------------
# Numeric range sanity — Hard Rule 09
# ---------------------------------------------------------------------------

class TestNumericRangeSanity:
    def test_all_min_lte_max(self, parsed_records):
        for r in parsed_records:
            assert r.value_range.min_value.value <= r.value_range.max_value.value, (
                f"Record {r.record_id}: min > max"
            )

    def test_all_values_positive(self, parsed_records):
        for r in parsed_records:
            assert r.value_range.min_value.value > 0, (
                f"Record {r.record_id}: min value is non-positive"
            )
            assert r.value_range.max_value.value > 0, (
                f"Record {r.record_id}: max value is non-positive"
            )

    def test_turning_p_vc_range_matches_source(self, parsed_records):
        turn_p_vc = [
            r for r in parsed_records
            if r.applicability.operation_type is OperationType.TURNING
            and r.applicability.iso_material_group is IsoMaterialGroup.P
            and r.parameter_type is ParameterType.CUTTING_SPEED
        ]
        assert len(turn_p_vc) == 1
        r = turn_p_vc[0]
        assert r.value_range.min_value.value == Decimal("120")
        assert r.value_range.max_value.value == Decimal("280")

    def test_milling_p_fz_range_matches_source(self, parsed_records):
        mill_p_fz = [
            r for r in parsed_records
            if r.applicability.operation_type is OperationType.MILLING
            and r.applicability.iso_material_group is IsoMaterialGroup.P
            and r.parameter_type is ParameterType.FEED_PER_TOOTH
        ]
        assert len(mill_p_fz) == 1
        r = mill_p_fz[0]
        assert r.value_range.min_value.value == Decimal("0.03")
        assert r.value_range.max_value.value == Decimal("0.18")


# ---------------------------------------------------------------------------
# Provenance / source traceability — Hard Rule 15
# ---------------------------------------------------------------------------

class TestProvenance:
    def test_source_reference_populated(self, parsed_records):
        for r in parsed_records:
            assert r.provenance.source_reference is not None, (
                f"Record {r.record_id} has no source_reference"
            )
            assert len(r.provenance.source_reference) > 0

    def test_source_document_populated(self, parsed_records):
        for r in parsed_records:
            assert r.provenance.source_document is not None, (
                f"Record {r.record_id} has no source_document"
            )

    def test_provenance_type_is_literature(self, parsed_records):
        from backend.domain.enums import ProvenanceType
        for r in parsed_records:
            assert r.provenance.source_type is ProvenanceType.LITERATURE, (
                f"Record {r.record_id} has wrong source_type {r.provenance.source_type}"
            )


# ---------------------------------------------------------------------------
# Query matching — Hard Rule 19 & 21
# ---------------------------------------------------------------------------

class TestQueryMatching:
    def test_query_by_operation_and_material_group(self, parsed_records, synthetic_md_path):
        reg = CuttingParameterRegistry()
        for r in parsed_records:
            reg.register(r)

        scope = ApplicabilityScope(
            operation_type=OperationType.MILLING,
            iso_material_group=IsoMaterialGroup.P,
        )
        results = reg.find(scope=scope)
        assert len(results) > 0
        for r in results:
            assert r.applicability.operation_type is OperationType.MILLING

    def test_empty_result_for_unknown_scope(self, parsed_records):
        reg = CuttingParameterRegistry()
        for r in parsed_records:
            reg.register(r)

        scope = ApplicabilityScope(
            operation_type=OperationType.BORING,  # not in our synthetic data
            iso_material_group=IsoMaterialGroup.P,
        )
        results = reg.find(scope=scope)
        assert results == ()

    def test_find_by_parameter_type_cutting_speed(self, parsed_records):
        reg = CuttingParameterRegistry()
        for r in parsed_records:
            reg.register(r)
        vc_results = reg.find(parameter_type=ParameterType.CUTTING_SPEED)
        assert len(vc_results) > 0
        for r in vc_results:
            assert r.parameter_type is ParameterType.CUTTING_SPEED


# ---------------------------------------------------------------------------
# Idempotent ingestion — Hard Rule 22
# ---------------------------------------------------------------------------

class TestIdempotentIngestion:
    def test_same_file_produces_same_records(self, synthetic_md_path):
        r1 = parse_reference_report(synthetic_md_path)
        r2 = parse_reference_report(synthetic_md_path)
        assert len(r1) == len(r2)
        ids1 = {r.record_id for r in r1}
        ids2 = {r.record_id for r in r2}
        assert ids1 == ids2

    def test_seed_twice_on_same_registry_raises(self, synthetic_md_path):
        reg = CuttingParameterRegistry()
        seed_reference_registry(reg, synthetic_md_path)
        with pytest.raises(EmpiricalDataError, match="already registered"):
            seed_reference_registry(reg, synthetic_md_path)

    def test_seed_on_fresh_registry_works(self, synthetic_md_path):
        reg1 = CuttingParameterRegistry()
        n1 = seed_reference_registry(reg1, synthetic_md_path)
        reg2 = CuttingParameterRegistry()
        n2 = seed_reference_registry(reg2, synthetic_md_path)
        assert n1 == n2
        assert n1 > 0

    def test_seed_returns_record_count(self, synthetic_md_path):
        reg = CuttingParameterRegistry()
        n = seed_reference_registry(reg, synthetic_md_path)
        assert n == len(reg)


# ---------------------------------------------------------------------------
# seed_reference_registry — env var handling
# ---------------------------------------------------------------------------

class TestSeedEnvVar:
    def test_missing_env_var_raises_environment_error(self, monkeypatch):
        monkeypatch.delenv(_ENV_VAR, raising=False)
        reg = CuttingParameterRegistry()
        with pytest.raises(OSError, match=_ENV_VAR):
            seed_reference_registry(reg, source_path=None)

    def test_env_var_used_as_path(self, synthetic_md_path, monkeypatch):
        monkeypatch.setenv(_ENV_VAR, str(synthetic_md_path))
        reg = CuttingParameterRegistry()
        n = seed_reference_registry(reg, source_path=None)
        assert n > 0

    def test_explicit_path_overrides_env_var(self, synthetic_md_path, monkeypatch):
        monkeypatch.setenv(_ENV_VAR, "/nonexistent/path.md")
        reg = CuttingParameterRegistry()
        n = seed_reference_registry(reg, source_path=synthetic_md_path)
        assert n > 0

    def test_nonexistent_path_raises_file_not_found(self, tmp_path):
        reg = CuttingParameterRegistry()
        with pytest.raises(FileNotFoundError):
            seed_reference_registry(reg, source_path=tmp_path / "missing.md")


# ---------------------------------------------------------------------------
# Hard Rule 02: VP100 and ToolLife968 data must NOT become parameter records
# ---------------------------------------------------------------------------

class TestNoVP100Records:
    """Verifies that VP100 empirical data cannot enter the cutting parameter
    registry via the reference parser or seed function."""

    def test_reference_parser_does_not_read_vp100_data(self, synthetic_md_path):
        records = parse_reference_report(synthetic_md_path)
        for r in records:
            # Record IDs from this seeder use REF_ prefix; VP100 would use VP100_
            assert not r.record_id.startswith("VP100_"), (
                f"VP100 record found: {r.record_id}"
            )
            assert "VP100" not in r.record_id

    def test_seed_reference_registry_produces_only_reference_only(self, synthetic_md_path):
        reg = CuttingParameterRegistry()
        seed_reference_registry(reg, synthetic_md_path)
        for r in reg.all():
            assert r.evidence_status is EvidenceStatus.REFERENCE_ONLY, (
                f"VP100/non-reference record slipped in: {r.record_id} "
                f"status={r.evidence_status}"
            )

    def test_no_vp100_record_passes_authoritative_gate(self, synthetic_md_path):
        reg = CuttingParameterRegistry()
        seed_reference_registry(reg, synthetic_md_path)
        authoritative = reg.find_authoritative()
        assert authoritative == (), (
            "Reference-seeded registry must have no authoritative records"
        )


# ---------------------------------------------------------------------------
# Duplicate-record detection — Hard Rule 17
# ---------------------------------------------------------------------------

class TestDuplicateDetection:
    def test_registry_rejects_duplicate_id(self, parsed_records):
        reg = CuttingParameterRegistry()
        reg.register(parsed_records[0])
        with pytest.raises(EmpiricalDataError, match="already registered"):
            reg.register(parsed_records[0])

    def test_all_parsed_record_ids_are_unique(self, parsed_records):
        ids = [r.record_id for r in parsed_records]
        assert len(ids) == len(set(ids)), (
            f"Duplicate record IDs found: "
            f"{[i for i in ids if ids.count(i) > 1]}"
        )


# ---------------------------------------------------------------------------
# Tool material mapping — Hard Rule 14
# ---------------------------------------------------------------------------

class TestToolMaterialMapping:
    def test_iso_p_turning_maps_to_carbide(self, parsed_records):
        p_vc = next(
            r for r in parsed_records
            if r.applicability.operation_type is OperationType.TURNING
            and r.applicability.iso_material_group is IsoMaterialGroup.P
            and r.parameter_type is ParameterType.CUTTING_SPEED
        )
        assert p_vc.applicability.tool_material is ToolMaterial.CARBIDE

    def test_iso_h_turning_maps_to_cbn(self, parsed_records):
        h_vc = next(
            r for r in parsed_records
            if r.applicability.operation_type is OperationType.TURNING
            and r.applicability.iso_material_group is IsoMaterialGroup.H
            and r.parameter_type is ParameterType.CUTTING_SPEED
        )
        assert h_vc.applicability.tool_material is ToolMaterial.CBN

    def test_reaming_has_no_tool_material(self, parsed_records):
        ream_records = [
            r for r in parsed_records
            if r.applicability.operation_type is OperationType.REAMING
        ]
        assert len(ream_records) > 0
        for r in ream_records:
            assert r.applicability.tool_material is None, (
                f"Reaming record {r.record_id} has tool_material set, "
                "but the source does not specify one"
            )


# ---------------------------------------------------------------------------
# File-not-found error
# ---------------------------------------------------------------------------

def test_parse_report_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_reference_report(tmp_path / "not_there.md")
