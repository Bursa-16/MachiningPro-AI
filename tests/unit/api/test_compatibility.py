"""Tests for the deterministic compatibility evaluation engine and API.

MACHINE_TOOL_HOLDER_COMPATIBILITY_ENGINE_01

Test matrix covers:
  - COMPATIBLE / INCOMPATIBLE / INSUFFICIENT_DATA outcomes
  - All seven mandatory rule types
  - Validation error paths (bad IDs, invalid operation/ISO, bad numeric inputs)
  - Reason-code stability
  - Engine constraints: MISSING_LIMIT_AS_ZERO=NO, three-state precedence
  - Schema and reason-codes endpoints
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.compatibility.engine import _MACHINES, _HOLDERS, _TOOLS, evaluate
from backend.compatibility.models import (
    VALID_ISO_GROUPS,
    VALID_OPERATIONS,
    CompatibilityRequest,
    RC,
)

client = TestClient(app)

# ---------------------------------------------------------------------------
# Known test-fixture IDs (deterministic catalog — no env var required)
# ---------------------------------------------------------------------------

# COMPATIBLE baseline
_M_CAT40 = "haas-vf-2ss"              # CAT-40, 12000 rpm, milling/drilling/boring/tapping
_H_CAT40_ER32 = "kennametal-cat40-er32-collet-chuck"  # CAT-40 / ER32 / [2, 20 mm]
_T_MILL_6MM = "sandvik-r216-33-06045-ac10p-1620"      # milling, shank 6mm, ISO P/M/K/N/S

# INCOMPATIBLE — interface mismatch
_M_HSK = "dmg-dmu-50-3g"             # HSK-A63

# INCOMPATIBLE — process mismatch (turning tool)
_T_TURN_CNMG = "sandvik-cnmg-120408-pm-4325"  # turning/facing only, ISO P/M/K

# INCOMPATIBLE — shank out of range
_H_SHRINK_8MM = "haimer-cat40-power-clamp-ng-08"  # CAT-40 / SHRINK_FIT / [8, 8 mm]

# INSUFFICIENT_DATA — machine with no spindle_interface
_M_NO_IFACE = "haas-st-10"           # turning, drilling, NO spindle_interface
_T_DRILL_8MM = "sandvik-860-1-0800-040a1-pm"  # drilling, shank 8mm, ISO P/M/K/N

# CNMG seat holder (BMT65 — no matching machine)
_H_BMT65_CNMG = "sandvik-bmt65-pclnr-2525m-12"  # BMT65 / CNMG_SEAT


# ===========================================================================
# 1. Catalog data integrity
# ===========================================================================

class TestCatalogData:
    def test_machine_catalog_non_empty(self):
        assert len(_MACHINES) >= 15

    def test_holder_catalog_non_empty(self):
        assert len(_HOLDERS) >= 17

    def test_tool_catalog_non_empty(self):
        assert len(_TOOLS) >= 16

    def test_baseline_machine_exists(self):
        assert _M_CAT40 in _MACHINES

    def test_baseline_holder_exists(self):
        assert _H_CAT40_ER32 in _HOLDERS

    def test_baseline_tool_exists(self):
        assert _T_MILL_6MM in _TOOLS

    def test_hsk_machine_exists(self):
        assert _M_HSK in _MACHINES

    def test_baseline_machine_interface_is_cat40(self):
        assert _MACHINES[_M_CAT40].spindle_interface == "CAT-40"

    def test_hsk_machine_interface_is_hska63(self):
        assert _MACHINES[_M_HSK].spindle_interface == "HSK-A63"

    def test_no_interface_machine_has_none(self):
        assert _MACHINES[_M_NO_IFACE].spindle_interface is None

    def test_holder_machine_interface_key_non_empty(self):
        for h in _HOLDERS.values():
            assert h.machine_interface_key, f"holder {h.stable_id} missing machine_interface_key"

    def test_holder_tool_interface_key_non_empty(self):
        for h in _HOLDERS.values():
            assert h.tool_interface_key, f"holder {h.stable_id} missing tool_interface_key"

    def test_no_missing_limit_as_zero(self):
        """MISSING_LIMIT_AS_ZERO=NO — clamping_range fields must be None or positive."""
        for h in _HOLDERS.values():
            if h.clamping_range_min_mm is not None:
                assert h.clamping_range_min_mm > 0, (
                    f"holder {h.stable_id} clamping_range_min_mm is 0 (zero-as-missing)"
                )
            if h.clamping_range_max_mm is not None:
                assert h.clamping_range_max_mm > 0, (
                    f"holder {h.stable_id} clamping_range_max_mm is 0 (zero-as-missing)"
                )

    def test_no_spindle_max_rpm_as_zero(self):
        for m in _MACHINES.values():
            if m.spindle_max_rpm is not None:
                assert m.spindle_max_rpm > 0

    def test_valid_operations_set(self):
        assert "milling" in VALID_OPERATIONS
        assert "drilling" in VALID_OPERATIONS
        assert "turning" in VALID_OPERATIONS
        assert "reaming" in VALID_OPERATIONS

    def test_valid_iso_groups_set(self):
        assert VALID_ISO_GROUPS == frozenset({"P", "M", "K", "N", "S", "H"})


# ===========================================================================
# 2. Schema endpoint
# ===========================================================================

class TestSchemaEndpoint:
    def test_schema_status_200(self):
        r = client.get("/api/compatibility/schema")
        assert r.status_code == 200

    def test_schema_has_machines(self):
        data = client.get("/api/compatibility/schema").json()
        assert len(data["machines"]) >= 15

    def test_schema_has_holders(self):
        data = client.get("/api/compatibility/schema").json()
        assert len(data["holders"]) >= 17

    def test_schema_has_cutting_tools(self):
        data = client.get("/api/compatibility/schema").json()
        assert len(data["cutting_tools"]) >= 16

    def test_schema_valid_operations(self):
        data = client.get("/api/compatibility/schema").json()
        ops = data["valid_operations"]
        assert "milling" in ops
        assert "drilling" in ops
        assert "turning" in ops

    def test_schema_valid_iso_groups(self):
        data = client.get("/api/compatibility/schema").json()
        assert set(data["valid_iso_groups"]) == {"P", "M", "K", "N", "S", "H"}

    def test_schema_machine_entries_have_id_and_display(self):
        data = client.get("/api/compatibility/schema").json()
        for entry in data["machines"]:
            assert "id" in entry
            assert "display" in entry
            assert len(entry["id"]) > 0
            assert len(entry["display"]) > 0

    def test_schema_holder_entries_have_id_and_display(self):
        data = client.get("/api/compatibility/schema").json()
        for entry in data["holders"]:
            assert "id" in entry and "display" in entry

    def test_schema_tool_entries_have_id_and_display(self):
        data = client.get("/api/compatibility/schema").json()
        for entry in data["cutting_tools"]:
            assert "id" in entry and "display" in entry


# ===========================================================================
# 3. Reason-codes endpoint
# ===========================================================================

class TestReasonCodesEndpoint:
    def test_reason_codes_status_200(self):
        r = client.get("/api/compatibility/reason-codes")
        assert r.status_code == 200

    def test_reason_codes_non_empty(self):
        data = client.get("/api/compatibility/reason-codes").json()
        assert len(data) >= 20

    def test_process_reason_codes_present(self):
        data = client.get("/api/compatibility/reason-codes").json()
        codes = set(data.values())
        assert RC.PROCESS_SUPPORTED in codes
        assert RC.MACHINE_PROCESS_NOT_SUPPORTED in codes
        assert RC.TOOL_PROCESS_NOT_SUPPORTED in codes

    def test_interface_reason_codes_present(self):
        data = client.get("/api/compatibility/reason-codes").json()
        codes = set(data.values())
        assert RC.MACHINE_INTERFACE_MISMATCH in codes
        assert RC.MACHINE_INTERFACE_MATCH in codes
        assert RC.MACHINE_INTERFACE_UNKNOWN in codes

    def test_rpm_reason_codes_present(self):
        data = client.get("/api/compatibility/reason-codes").json()
        codes = set(data.values())
        assert RC.RPM_NOT_REQUESTED in codes
        assert RC.MACHINE_RPM_EXCEEDED in codes
        assert RC.MACHINE_RPM_OK in codes

    def test_no_private_path_in_reason_codes(self):
        data = client.get("/api/compatibility/reason-codes").json()
        for v in data.values():
            assert "\\" not in v and "/" not in v, (
                f"PRIVATE_PATH_IN_API_RESPONSE=YES violation: {v!r}"
            )


# ===========================================================================
# 4. COMPATIBLE evaluation
# ===========================================================================

class TestCompatibleEvaluation:
    def _payload(self, **overrides):
        base = {
            "machine_id": _M_CAT40,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_MILL_6MM,
            "operation": "milling",
            "iso_material_group": "P",
        }
        base.update(overrides)
        return base

    def test_compatible_status_200(self):
        r = client.post("/api/compatibility/evaluate", json=self._payload())
        assert r.status_code == 200

    def test_compatible_overall_status(self):
        data = client.post("/api/compatibility/evaluate", json=self._payload()).json()
        assert data["overall_status"] == "COMPATIBLE"

    def test_compatible_no_hard_failures(self):
        data = client.post("/api/compatibility/evaluate", json=self._payload()).json()
        assert data["hard_failures"] == []

    def test_compatible_no_unknown_rules(self):
        data = client.post("/api/compatibility/evaluate", json=self._payload()).json()
        assert data["unknown_rules"] == []

    def test_compatible_process_rule_pass(self):
        data = client.post("/api/compatibility/evaluate", json=self._payload()).json()
        proc = next(r for r in data["rule_results"] if r["rule_id"] == "PROCESS_SUPPORT")
        assert proc["status"] == "PASS"

    def test_compatible_machine_interface_rule_pass(self):
        data = client.post("/api/compatibility/evaluate", json=self._payload()).json()
        iface = next(r for r in data["rule_results"] if r["rule_id"] == "MACHINE_HOLDER_INTERFACE")
        assert iface["status"] == "PASS"

    def test_compatible_shank_rule_pass(self):
        data = client.post("/api/compatibility/evaluate", json=self._payload()).json()
        shank = next(r for r in data["rule_results"] if r["rule_id"] == "HOLDER_TOOL_SHANK")
        assert shank["status"] == "PASS"

    def test_compatible_iso_rule_pass(self):
        data = client.post("/api/compatibility/evaluate", json=self._payload()).json()
        iso = next(r for r in data["rule_results"] if r["rule_id"] == "ISO_MATERIAL_GROUP")
        assert iso["status"] == "PASS"

    def test_compatible_rpm_rules_not_applicable_when_no_vc(self):
        data = client.post("/api/compatibility/evaluate", json=self._payload()).json()
        rpm_rules = [r for r in data["rule_results"] if "RPM" in r["rule_id"]]
        assert all(r["status"] == "NOT_APPLICABLE" for r in rpm_rules)
        assert all(r["reason_code"] == RC.RPM_NOT_REQUESTED for r in rpm_rules)

    def test_compatible_no_calculated_rpm_when_no_vc(self):
        data = client.post("/api/compatibility/evaluate", json=self._payload()).json()
        assert data["calculated_rpm"] is None

    def test_compatible_seven_rules_present(self):
        data = client.post("/api/compatibility/evaluate", json=self._payload()).json()
        rule_ids = [r["rule_id"] for r in data["rule_results"]]
        for expected in [
            "PROCESS_SUPPORT", "MACHINE_HOLDER_INTERFACE", "HOLDER_TOOL_SHANK",
            "ISO_MATERIAL_GROUP", "MACHINE_RPM", "HOLDER_RPM", "TOOL_RPM",
        ]:
            assert expected in rule_ids

    def test_compatible_disclaimer_present(self):
        data = client.post("/api/compatibility/evaluate", json=self._payload()).json()
        assert len(data["disclaimer"]) > 20
        assert "REFERENCE_ONLY" in data["disclaimer"] or "reference" in data["disclaimer"].lower()

    def test_compatible_ids_in_response(self):
        data = client.post("/api/compatibility/evaluate", json=self._payload()).json()
        assert data["machine_id"] == _M_CAT40
        assert data["holder_id"] == _H_CAT40_ER32
        assert data["cutting_tool_id"] == _T_MILL_6MM

    def test_compatible_different_iso_group(self):
        data = client.post("/api/compatibility/evaluate", json=self._payload(iso_material_group="M")).json()
        assert data["overall_status"] == "COMPATIBLE"

    def test_compatible_drilling_with_drill_tool(self):
        # haas-vf-2ss + kennametal-cat40-er32 + sandvik-860-1-0800-040a1-pm (drilling, 8mm)
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_CAT40,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_DRILL_8MM,
            "operation": "drilling",
            "iso_material_group": "P",
        }).json()
        assert data["overall_status"] == "COMPATIBLE"


# ===========================================================================
# 5. INCOMPATIBLE evaluations
# ===========================================================================

class TestIncompatibleEvaluation:
    def test_interface_mismatch_is_incompatible(self):
        # HSK-A63 machine + CAT-40 holder → FAIL
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_HSK,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_MILL_6MM,
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        assert data["overall_status"] == "INCOMPATIBLE"

    def test_interface_mismatch_hard_failure_rule_id(self):
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_HSK,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_MILL_6MM,
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        assert "MACHINE_HOLDER_INTERFACE" in data["hard_failures"]

    def test_interface_mismatch_reason_code(self):
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_HSK,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_MILL_6MM,
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        iface = next(r for r in data["rule_results"] if r["rule_id"] == "MACHINE_HOLDER_INTERFACE")
        assert iface["reason_code"] == RC.MACHINE_INTERFACE_MISMATCH

    def test_tool_process_not_supported_is_incompatible(self):
        # milling operation with a turning-only tool
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_CAT40,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_TURN_CNMG,
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        assert data["overall_status"] == "INCOMPATIBLE"

    def test_tool_process_not_supported_reason_code(self):
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_CAT40,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_TURN_CNMG,
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        proc = next(r for r in data["rule_results"] if r["rule_id"] == "PROCESS_SUPPORT")
        assert proc["reason_code"] == RC.TOOL_PROCESS_NOT_SUPPORTED

    def test_shank_out_of_range_is_incompatible(self):
        # 6mm shank tool + 8mm shrink-fit holder → FAIL
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_CAT40,
            "holder_id": _H_SHRINK_8MM,
            "cutting_tool_id": _T_MILL_6MM,
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        assert data["overall_status"] == "INCOMPATIBLE"

    def test_shank_out_of_range_reason_code(self):
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_CAT40,
            "holder_id": _H_SHRINK_8MM,
            "cutting_tool_id": _T_MILL_6MM,
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        shank = next(r for r in data["rule_results"] if r["rule_id"] == "HOLDER_TOOL_SHANK")
        assert shank["reason_code"] == RC.SHANK_OUT_OF_RANGE

    def test_iso_group_not_supported_is_incompatible(self):
        # sandvik-r216 supports P/M/K/N/S but NOT H
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_CAT40,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_MILL_6MM,
            "operation": "milling",
            "iso_material_group": "H",
        }).json()
        assert data["overall_status"] == "INCOMPATIBLE"

    def test_iso_group_not_supported_reason_code(self):
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_CAT40,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_MILL_6MM,
            "operation": "milling",
            "iso_material_group": "H",
        }).json()
        iso = next(r for r in data["rule_results"] if r["rule_id"] == "ISO_MATERIAL_GROUP")
        assert iso["reason_code"] == RC.ISO_NOT_SUPPORTED

    def test_rpm_exceeded_is_incompatible(self):
        # haas-vf-2ss max 12000 rpm; Vc=500 m/min + D=6mm → ~26526 rpm > 12000
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_CAT40,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_MILL_6MM,
            "operation": "milling",
            "iso_material_group": "P",
            "cutting_speed_m_min": 500.0,
            "tool_diameter_mm": 6.0,
        }).json()
        assert data["overall_status"] == "INCOMPATIBLE"

    def test_rpm_exceeded_reason_code(self):
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_CAT40,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_MILL_6MM,
            "operation": "milling",
            "iso_material_group": "P",
            "cutting_speed_m_min": 500.0,
            "tool_diameter_mm": 6.0,
        }).json()
        machine_rpm = next(r for r in data["rule_results"] if r["rule_id"] == "MACHINE_RPM")
        assert machine_rpm["reason_code"] == RC.MACHINE_RPM_EXCEEDED

    def test_rpm_exceeded_calculated_rpm_in_response(self):
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_CAT40,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_MILL_6MM,
            "operation": "milling",
            "iso_material_group": "P",
            "cutting_speed_m_min": 500.0,
            "tool_diameter_mm": 6.0,
        }).json()
        assert data["calculated_rpm"] is not None
        assert data["calculated_rpm"] > 12000


# ===========================================================================
# 6. INSUFFICIENT_DATA evaluations
# ===========================================================================

class TestInsufficientDataEvaluation:
    def test_no_machine_interface_gives_insufficient_data(self):
        # haas-st-10 has spindle_interface=None
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_NO_IFACE,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_DRILL_8MM,
            "operation": "drilling",
            "iso_material_group": "P",
        }).json()
        assert data["overall_status"] == "INSUFFICIENT_DATA"

    def test_no_machine_interface_unknown_rule_listed(self):
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_NO_IFACE,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_DRILL_8MM,
            "operation": "drilling",
            "iso_material_group": "P",
        }).json()
        assert "MACHINE_HOLDER_INTERFACE" in data["unknown_rules"]

    def test_no_machine_interface_missing_field_noted(self):
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_NO_IFACE,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_DRILL_8MM,
            "operation": "drilling",
            "iso_material_group": "P",
        }).json()
        assert any("spindle_interface" in f for f in data["missing_fields"])

    def test_machine_interface_unknown_reason_code(self):
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_NO_IFACE,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_DRILL_8MM,
            "operation": "drilling",
            "iso_material_group": "P",
        }).json()
        iface = next(r for r in data["rule_results"] if r["rule_id"] == "MACHINE_HOLDER_INTERFACE")
        assert iface["reason_code"] == RC.MACHINE_INTERFACE_UNKNOWN

    def test_tool_rpm_unknown_when_vc_provided(self):
        # All tools have max_rpm=None; when Vc+D provided, TOOL_RPM → UNKNOWN
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_CAT40,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_MILL_6MM,
            "operation": "milling",
            "iso_material_group": "P",
            "cutting_speed_m_min": 120.0,
            "tool_diameter_mm": 6.0,
        }).json()
        tool_rpm = next(r for r in data["rule_results"] if r["rule_id"] == "TOOL_RPM")
        assert tool_rpm["status"] == "UNKNOWN"
        assert tool_rpm["reason_code"] == RC.TOOL_RPM_LIMIT_UNKNOWN

    def test_rpm_provided_gives_insufficient_when_tool_limit_unknown(self):
        # Vc low enough that machine/holder pass, but tool has no max_rpm → INSUFFICIENT
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_CAT40,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_MILL_6MM,
            "operation": "milling",
            "iso_material_group": "P",
            "cutting_speed_m_min": 100.0,
            "tool_diameter_mm": 6.0,
        }).json()
        assert data["overall_status"] == "INSUFFICIENT_DATA"

    def test_shell_mill_arbor_holder_is_insufficient_data(self):
        # Shell mill arbor holder + any non-shell-mill tool → UNKNOWN HOLDER_TOOL_SHANK
        shell_holders = [
            sid for sid, h in _HOLDERS.items()
            if h.tool_interface_key == "SHELL_MILL_ARBOR"
        ]
        assert len(shell_holders) >= 1
        sh = shell_holders[0]
        h = _HOLDERS[sh]
        # Find a machine matching this holder's machine_interface_key
        matching_machines = [
            sid for sid, m in _MACHINES.items()
            if m.spindle_interface == h.machine_interface_key
        ]
        if not matching_machines:
            pytest.skip("No machine matching shell mill arbor holder interface")
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": matching_machines[0],
            "holder_id": sh,
            "cutting_tool_id": _T_MILL_6MM,
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        shank = next(r for r in data["rule_results"] if r["rule_id"] == "HOLDER_TOOL_SHANK")
        assert shank["status"] == "UNKNOWN"
        assert shank["reason_code"] == RC.INTERFACE_UNRESOLVABLE


# ===========================================================================
# 7. Three-state precedence validation
# ===========================================================================

class TestThreeStatePrecedence:
    def test_fail_beats_unknown(self):
        """FAIL present → INCOMPATIBLE even if other rules are UNKNOWN."""
        # haas-st-10 (no iface → MACHINE_HOLDER_INTERFACE UNKNOWN)
        # + CAT-40 holder (MACHINE_HOLDER_INTERFACE UNKNOWN)
        # + turning tool (if operation=milling → TOOL_PROCESS FAIL)
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_NO_IFACE,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_TURN_CNMG,
            "operation": "milling",    # machine supports milling? check st-10...
            "iso_material_group": "P",
        }).json()
        # haas-st-10 does NOT support milling → PROCESS_SUPPORT FAIL → INCOMPATIBLE
        assert data["overall_status"] == "INCOMPATIBLE"

    def test_all_pass_na_gives_compatible(self):
        req = CompatibilityRequest(
            machine_id=_M_CAT40,
            holder_id=_H_CAT40_ER32,
            cutting_tool_id=_T_MILL_6MM,
            operation="milling",
            iso_material_group="P",
        )
        resp = evaluate(req)
        assert resp.overall_status == "COMPATIBLE"
        assert resp.hard_failures == []
        assert resp.unknown_rules == []

    def test_incompatible_response_has_hard_failures(self):
        req = CompatibilityRequest(
            machine_id=_M_HSK,
            holder_id=_H_CAT40_ER32,
            cutting_tool_id=_T_MILL_6MM,
            operation="milling",
            iso_material_group="P",
        )
        resp = evaluate(req)
        assert resp.overall_status == "INCOMPATIBLE"
        assert len(resp.hard_failures) >= 1

    def test_insufficient_data_response_has_unknown_rules(self):
        req = CompatibilityRequest(
            machine_id=_M_NO_IFACE,
            holder_id=_H_CAT40_ER32,
            cutting_tool_id=_T_DRILL_8MM,
            operation="drilling",
            iso_material_group="P",
        )
        resp = evaluate(req)
        assert resp.overall_status == "INSUFFICIENT_DATA"
        assert len(resp.unknown_rules) >= 1

    def test_overall_status_exactly_three_values(self):
        """overall_status must be one of exactly three values."""
        for payload in [
            {"machine_id": _M_CAT40, "holder_id": _H_CAT40_ER32,
             "cutting_tool_id": _T_MILL_6MM, "operation": "milling", "iso_material_group": "P"},
            {"machine_id": _M_HSK, "holder_id": _H_CAT40_ER32,
             "cutting_tool_id": _T_MILL_6MM, "operation": "milling", "iso_material_group": "P"},
            {"machine_id": _M_NO_IFACE, "holder_id": _H_CAT40_ER32,
             "cutting_tool_id": _T_DRILL_8MM, "operation": "drilling", "iso_material_group": "P"},
        ]:
            data = client.post("/api/compatibility/evaluate", json=payload).json()
            assert data["overall_status"] in {
                "COMPATIBLE", "INCOMPATIBLE", "INSUFFICIENT_DATA"
            }


# ===========================================================================
# 8. Validation error paths
# ===========================================================================

class TestValidationErrors:
    def _base(self):
        return {
            "machine_id": _M_CAT40,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_MILL_6MM,
            "operation": "milling",
            "iso_material_group": "P",
        }

    def test_unknown_machine_id_returns_422(self):
        p = {**self._base(), "machine_id": "does-not-exist"}
        r = client.post("/api/compatibility/evaluate", json=p)
        assert r.status_code == 422

    def test_unknown_holder_id_returns_422(self):
        p = {**self._base(), "holder_id": "does-not-exist"}
        r = client.post("/api/compatibility/evaluate", json=p)
        assert r.status_code == 422

    def test_unknown_cutting_tool_id_returns_422(self):
        p = {**self._base(), "cutting_tool_id": "does-not-exist"}
        r = client.post("/api/compatibility/evaluate", json=p)
        assert r.status_code == 422

    def test_invalid_operation_returns_422(self):
        p = {**self._base(), "operation": "grinding"}
        r = client.post("/api/compatibility/evaluate", json=p)
        assert r.status_code == 422

    def test_invalid_iso_group_returns_422(self):
        p = {**self._base(), "iso_material_group": "X"}
        r = client.post("/api/compatibility/evaluate", json=p)
        assert r.status_code == 422

    def test_negative_vc_returns_422(self):
        p = {**self._base(), "cutting_speed_m_min": -1.0}
        r = client.post("/api/compatibility/evaluate", json=p)
        assert r.status_code == 422

    def test_zero_diameter_returns_422(self):
        p = {**self._base(), "tool_diameter_mm": 0.0}
        r = client.post("/api/compatibility/evaluate", json=p)
        assert r.status_code == 422

    def test_negative_diameter_returns_422(self):
        p = {**self._base(), "tool_diameter_mm": -5.0}
        r = client.post("/api/compatibility/evaluate", json=p)
        assert r.status_code == 422

    def test_operation_case_insensitive(self):
        p = {**self._base(), "operation": "MILLING"}
        r = client.post("/api/compatibility/evaluate", json=p)
        assert r.status_code == 200

    def test_iso_group_case_insensitive(self):
        p = {**self._base(), "iso_material_group": "p"}
        r = client.post("/api/compatibility/evaluate", json=p)
        assert r.status_code == 200

    def test_missing_required_field_machine_id(self):
        p = {k: v for k, v in self._base().items() if k != "machine_id"}
        r = client.post("/api/compatibility/evaluate", json=p)
        assert r.status_code == 422

    def test_missing_required_field_operation(self):
        p = {k: v for k, v in self._base().items() if k != "operation"}
        r = client.post("/api/compatibility/evaluate", json=p)
        assert r.status_code == 422

    def test_both_vc_and_diameter_trigger_rpm_rules(self):
        p = {**self._base(), "cutting_speed_m_min": 120.0, "tool_diameter_mm": 6.0}
        data = client.post("/api/compatibility/evaluate", json=p).json()
        rpm_rules = [r for r in data["rule_results"] if "RPM" in r["rule_id"]]
        assert all(r["status"] != "NOT_APPLICABLE" for r in rpm_rules)

    def test_only_vc_without_diameter_uses_not_applicable(self):
        # Only Vc without diameter → RPM rules NOT_APPLICABLE
        p = {**self._base(), "cutting_speed_m_min": 120.0}
        data = client.post("/api/compatibility/evaluate", json=p).json()
        rpm_rules = [r for r in data["rule_results"] if "RPM" in r["rule_id"]]
        assert all(r["status"] == "NOT_APPLICABLE" for r in rpm_rules)


# ===========================================================================
# 9. Engine constraint guards
# ===========================================================================

class TestEngineConstraints:
    def test_rpm_formula_not_duplicated(self):
        """RPM_FORMULA_DUPLICATED=NO — engine imports spindle_speed_from_cutting_speed."""
        from backend.compatibility import engine as eng
        import inspect
        src = inspect.getsource(eng)
        assert "spindle_speed_from_cutting_speed" in src

    def test_tool_life_not_imported(self):
        """TOOLLIFE_USED_AS_COMPATIBILITY_PREDICTOR=NO."""
        from backend.compatibility import engine as eng
        import inspect
        src = inspect.getsource(eng)
        assert "tool_life" not in src.lower()
        assert "taylor" not in src.lower()

    def test_power_not_implemented(self):
        """POWER_COMPATIBILITY_IMPLEMENTED=NO."""
        req = CompatibilityRequest(
            machine_id=_M_CAT40,
            holder_id=_H_CAT40_ER32,
            cutting_tool_id=_T_MILL_6MM,
            operation="milling",
            iso_material_group="P",
        )
        resp = evaluate(req)
        rule_ids = [r.rule_id for r in resp.rule_results]
        assert not any("POWER" in rid for rid in rule_ids)

    def test_torque_not_implemented(self):
        """TORQUE_COMPATIBILITY_IMPLEMENTED=NO."""
        req = CompatibilityRequest(
            machine_id=_M_CAT40,
            holder_id=_H_CAT40_ER32,
            cutting_tool_id=_T_MILL_6MM,
            operation="milling",
            iso_material_group="P",
        )
        resp = evaluate(req)
        rule_ids = [r.rule_id for r in resp.rule_results]
        assert not any("TORQUE" in rid for rid in rule_ids)

    def test_missing_limit_not_zero(self):
        """MISSING_LIMIT_AS_ZERO=NO — UNKNOWN rules have no zero-limit assumption."""
        req = CompatibilityRequest(
            machine_id=_M_NO_IFACE,
            holder_id=_H_CAT40_ER32,
            cutting_tool_id=_T_DRILL_8MM,
            operation="drilling",
            iso_material_group="P",
        )
        resp = evaluate(req)
        iface = next(r for r in resp.rule_results if r.rule_id == "MACHINE_HOLDER_INTERFACE")
        assert iface.status == "UNKNOWN"

    def test_no_false_compatibility_claim_in_response(self):
        """FALSE_COMPATIBILITY_CLAIM=NO — response must not claim production compatibility."""
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_CAT40,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_MILL_6MM,
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        disclaimer = data["disclaimer"].lower()
        assert "reference" in disclaimer or "not" in disclaimer

    def test_no_private_path_in_evaluate_response(self):
        """PRIVATE_PATH_IN_API_RESPONSE=NO."""
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_CAT40,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_MILL_6MM,
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        import json
        payload_str = json.dumps(data)
        assert "C:\\" not in payload_str
        assert "/home/" not in payload_str

    def test_seven_mandatory_rules_always_present(self):
        mandatory = {
            "PROCESS_SUPPORT", "MACHINE_HOLDER_INTERFACE", "HOLDER_TOOL_SHANK",
            "ISO_MATERIAL_GROUP", "MACHINE_RPM", "HOLDER_RPM", "TOOL_RPM",
        }
        for payload in [
            {"machine_id": _M_CAT40, "holder_id": _H_CAT40_ER32,
             "cutting_tool_id": _T_MILL_6MM, "operation": "milling", "iso_material_group": "P"},
            {"machine_id": _M_HSK, "holder_id": _H_CAT40_ER32,
             "cutting_tool_id": _T_MILL_6MM, "operation": "milling", "iso_material_group": "P"},
            {"machine_id": _M_NO_IFACE, "holder_id": _H_CAT40_ER32,
             "cutting_tool_id": _T_DRILL_8MM, "operation": "drilling", "iso_material_group": "P"},
        ]:
            data = client.post("/api/compatibility/evaluate", json=payload).json()
            rule_ids = {r["rule_id"] for r in data["rule_results"]}
            assert mandatory.issubset(rule_ids), f"Missing rules in: {rule_ids}"


# ===========================================================================
# 10. Cross-domain audit
# ===========================================================================

class TestCrossDomainAudit:
    """Audit of real catalog combinations — verifies plausible coverage."""

    def test_at_least_one_compatible_combination(self):
        compatible_count = 0
        for mid, m in _MACHINES.items():
            if m.spindle_interface is None:
                continue
            for hid, h in _HOLDERS.items():
                if h.machine_interface_key != m.spindle_interface:
                    continue
                for tid, t in _TOOLS.items():
                    if not t.supported_operations:
                        continue
                    if not t.iso_material_groups:
                        continue
                    op = t.supported_operations[0]
                    if op not in m.supported_processes:
                        continue
                    iso = t.iso_material_groups[0]
                    req = CompatibilityRequest(
                        machine_id=mid, holder_id=hid, cutting_tool_id=tid,
                        operation=op, iso_material_group=iso,
                    )
                    resp = evaluate(req)
                    if resp.overall_status == "COMPATIBLE":
                        compatible_count += 1
                        if compatible_count >= 3:
                            break
                if compatible_count >= 3:
                    break
            if compatible_count >= 3:
                break
        assert compatible_count >= 1, "Expected at least one COMPATIBLE combination in catalog"

    def test_at_least_one_incompatible_combination(self):
        # HSK + CAT-40 is guaranteed incompatible
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_HSK,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_MILL_6MM,
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        assert data["overall_status"] == "INCOMPATIBLE"

    def test_at_least_one_insufficient_data_combination(self):
        data = client.post("/api/compatibility/evaluate", json={
            "machine_id": _M_NO_IFACE,
            "holder_id": _H_CAT40_ER32,
            "cutting_tool_id": _T_DRILL_8MM,
            "operation": "drilling",
            "iso_material_group": "P",
        }).json()
        assert data["overall_status"] == "INSUFFICIENT_DATA"
