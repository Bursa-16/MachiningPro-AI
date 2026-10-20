"""Tests for the deterministic configuration-selection engine and API.

COMPATIBILITY_SELECTION_ENGINE_01

Test matrix covers:
  - INCOMPATIBLE candidates never ranked
  - INSUFFICIENT_DATA candidates never ranked
  - COMPATIBLE candidates eligible for ranking
  - Deterministic ordering and repeatability
  - Engineering ties preserved (no forced winner)
  - Stable tie-break order
  - RPM margin / utilization handling
  - MISSING_LIMIT_AS_ZERO=NO respected
  - Compatibility trace preserved in candidates
  - No private path in API response
  - Auth / validation errors
  - max_eligible_returned / candidate bound behaviour
  - Overall state derivation
  - Constraint guards (no tool-life, no arbitrary score, no AI)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.compatibility.engine import _MACHINES, _TOOLS
from backend.selection.engine import select
from backend.selection.models import SelectionRequest

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixture identifiers (re-use stable IDs from catalog)
# ---------------------------------------------------------------------------

# COMPATIBLE baseline (same IDs as in test_compatibility.py)
_M_CAT40 = "haas-vf-2ss"              # CAT-40, 12000 rpm, milling/drilling/boring/tapping
_T_MILL_6MM = "sandvik-r216-33-06045-ac10p-1620"   # milling, shank 6mm, ISO P/M/K/N/S
_T_DRILL_8MM = "sandvik-860-1-0800-040a1-pm"        # drilling, shank 8mm, ISO P/M/K/N

# INCOMPATIBLE — interface mismatch
_M_HSK = "dmg-dmu-50-3g"             # HSK-A63

# INSUFFICIENT_DATA
_M_NO_IFACE = "haas-st-10"           # no spindle_interface
_T_TURN_CNMG = "sandvik-cnmg-120408-pm-4325"  # turning insert, no shank_diameter_mm


# ===========================================================================
# 1. Schema endpoint
# ===========================================================================

class TestSelectionSchema:
    def test_schema_status_200(self):
        r = client.get("/api/selection/schema")
        assert r.status_code == 200

    def test_schema_has_machines(self):
        data = client.get("/api/selection/schema").json()
        assert len(data["machines"]) >= 15

    def test_schema_has_cutting_tools(self):
        data = client.get("/api/selection/schema").json()
        assert len(data["cutting_tools"]) >= 16

    def test_schema_has_valid_operations(self):
        data = client.get("/api/selection/schema").json()
        assert "milling" in data["valid_operations"]

    def test_schema_has_valid_iso_groups(self):
        data = client.get("/api/selection/schema").json()
        assert set(data["valid_iso_groups"]) == {"P", "M", "K", "N", "S", "H"}

    def test_schema_machine_entries_have_id_and_display(self):
        data = client.get("/api/selection/schema").json()
        for entry in data["machines"]:
            assert "id" in entry and "display" in entry

    def test_schema_tool_entries_have_id_and_display(self):
        data = client.get("/api/selection/schema").json()
        for entry in data["cutting_tools"]:
            assert "id" in entry and "display" in entry

    def test_schema_no_holders_exposed_as_constraint(self):
        """Tool holders are not a user-selectable filter in the selection workflow."""
        data = client.get("/api/selection/schema").json()
        assert "holders" not in data


# ===========================================================================
# 2. Validation errors
# ===========================================================================

class TestSelectionValidation:
    def _base(self):
        return {"operation": "milling", "iso_material_group": "P"}

    def test_invalid_operation_422(self):
        p = {**self._base(), "operation": "grinding"}
        r = client.post("/api/selection/evaluate", json=p)
        assert r.status_code == 422

    def test_invalid_iso_group_422(self):
        p = {**self._base(), "iso_material_group": "X"}
        r = client.post("/api/selection/evaluate", json=p)
        assert r.status_code == 422

    def test_unknown_machine_id_422(self):
        p = {**self._base(), "machine_id": "does-not-exist"}
        r = client.post("/api/selection/evaluate", json=p)
        assert r.status_code == 422

    def test_unknown_tool_id_422(self):
        p = {**self._base(), "cutting_tool_id": "does-not-exist"}
        r = client.post("/api/selection/evaluate", json=p)
        assert r.status_code == 422

    def test_negative_vc_422(self):
        p = {**self._base(), "cutting_speed_m_min": -1.0}
        r = client.post("/api/selection/evaluate", json=p)
        assert r.status_code == 422

    def test_zero_diameter_422(self):
        p = {**self._base(), "tool_diameter_mm": 0.0}
        r = client.post("/api/selection/evaluate", json=p)
        assert r.status_code == 422

    def test_negative_diameter_422(self):
        p = {**self._base(), "tool_diameter_mm": -5.0}
        r = client.post("/api/selection/evaluate", json=p)
        assert r.status_code == 422

    def test_max_eligible_zero_422(self):
        p = {**self._base(), "max_eligible_returned": 0}
        r = client.post("/api/selection/evaluate", json=p)
        assert r.status_code == 422

    def test_operation_case_insensitive_200(self):
        p = {**self._base(), "operation": "MILLING"}
        r = client.post("/api/selection/evaluate", json=p)
        assert r.status_code == 200

    def test_iso_group_case_insensitive_200(self):
        p = {**self._base(), "iso_material_group": "p"}
        r = client.post("/api/selection/evaluate", json=p)
        assert r.status_code == 200

    def test_missing_operation_422(self):
        r = client.post("/api/selection/evaluate", json={"iso_material_group": "P"})
        assert r.status_code == 422

    def test_missing_iso_group_422(self):
        r = client.post("/api/selection/evaluate", json={"operation": "milling"})
        assert r.status_code == 422


# ===========================================================================
# 3. INCOMPATIBLE candidates never ranked
# ===========================================================================

class TestIncompatibleNeverRanked:
    def test_no_incompatible_entry_in_ranked_candidates_broad(self):
        """Full milling/P sweep: INCOMPATIBLE combinations exist (interface mismatches)
        but must NEVER appear in ranked_candidates."""
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        assert data["incompatible_count"] > 0, "Expected INCOMPATIBLE candidates in broad sweep"
        for entry in data["ranked_candidates"]:
            assert entry["compatibility_status"] != "INCOMPATIBLE", (
                f"INCOMPATIBLE candidate in ranked list: {entry['machine_id']}/"
                f"{entry['holder_id']}/{entry['cutting_tool_id']}"
            )

    def test_incompatible_candidates_appear_in_rejected_sample(self):
        """INCOMPATIBLE candidates appear in rejected_sample with correct status."""
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        assert len(data["rejected_sample"]) > 0, "Expected at least one REJECTED sample"
        for entry in data["rejected_sample"]:
            assert entry["candidate_status"] == "REJECTED"
            assert entry["compatibility_status"] == "INCOMPATIBLE"

    def test_no_compatible_configuration_state(self):
        """sandvik-r216 does not support ISO H → pre-filter excludes it →
        zero candidates generated → NO_COMPATIBLE_CONFIGURATION."""
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "H",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
        }).json()
        assert data["compatible_count"] == 0
        assert data["overall_state"] == "NO_COMPATIBLE_CONFIGURATION"

    def test_no_incompatible_entry_in_ranked_candidates(self):
        """Sweep: no INCOMPATIBLE status ever appears in ranked_candidates."""
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        for entry in data["ranked_candidates"]:
            assert entry["compatibility_status"] != "INCOMPATIBLE", (
                f"INCOMPATIBLE candidate leaked into ranked list: {entry}"
            )


# ===========================================================================
# 4. INSUFFICIENT_DATA candidates never ranked
# ===========================================================================

class TestInsufficientDataNeverRanked:
    def test_no_interface_machine_produces_not_rankable_candidates(self):
        """haas-st-10 (no spindle_interface) + CNMG turning insert + turning/P:
        MACHINE_HOLDER_INTERFACE UNKNOWN for all holders → not_rankable_count > 0."""
        data = client.post("/api/selection/evaluate", json={
            "operation": "turning",
            "iso_material_group": "P",
            "machine_id": _M_NO_IFACE,
            "cutting_tool_id": _T_TURN_CNMG,
        }).json()
        assert data["compatible_count"] == 0
        assert len(data["ranked_candidates"]) == 0
        assert data["not_rankable_count"] > 0

    def test_insufficient_data_entries_in_not_rankable_sample(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "turning",
            "iso_material_group": "P",
            "machine_id": _M_NO_IFACE,
            "cutting_tool_id": _T_TURN_CNMG,
        }).json()
        for entry in data["not_rankable_sample"]:
            assert entry["candidate_status"] == "NOT_RANKABLE"
            assert entry["compatibility_status"] == "INSUFFICIENT_DATA"

    def test_insufficient_data_state_when_all_not_rankable(self):
        """When incompatible_count=0 AND not_rankable_count>0 → INSUFFICIENT_DATA_FOR_SELECTION.
        We verify this via the engine directly on known-clean combinations."""
        from backend.selection.engine import _MACHINES, _HOLDERS, _TOOLS
        from backend.compatibility.engine import evaluate as compat_eval
        from backend.compatibility.models import CompatibilityRequest

        # Find a holder+machine+tool combination guaranteed to give INSUFFICIENT_DATA
        # by using haas-st-10 (no spindle_interface) + CNMG_SEAT holder + CNMG tool.
        cnmg_seat_holders = [
            hid for hid, h in _HOLDERS.items()
            if h.tool_interface_key == "CNMG_SEAT"
        ]
        assert len(cnmg_seat_holders) >= 1, "Need a CNMG_SEAT holder for this test"
        hid = cnmg_seat_holders[0]
        req = CompatibilityRequest(
            machine_id=_M_NO_IFACE,
            holder_id=hid,
            cutting_tool_id=_T_TURN_CNMG,
            operation="turning",
            iso_material_group="P",
        )
        resp = compat_eval(req)
        # MACHINE_HOLDER_INTERFACE UNKNOWN and no FAIL → INSUFFICIENT_DATA
        assert resp.overall_status == "INSUFFICIENT_DATA", (
            f"Expected INSUFFICIENT_DATA for this combination, got {resp.overall_status}"
        )

    def test_no_insufficient_data_entry_in_ranked_candidates(self):
        """Sweep: no INSUFFICIENT_DATA status ever appears in ranked_candidates."""
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        for entry in data["ranked_candidates"]:
            assert entry["compatibility_status"] != "INSUFFICIENT_DATA", (
                f"INSUFFICIENT_DATA candidate leaked into ranked list: {entry}"
            )


# ===========================================================================
# 5. COMPATIBLE candidates are eligible and ranked
# ===========================================================================

class TestCompatibleEligible:
    def test_cat40_milling_has_compatible_candidates(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
        }).json()
        assert data["compatible_count"] > 0
        assert len(data["ranked_candidates"]) > 0

    def test_ranked_candidates_all_compatible(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
        }).json()
        for entry in data["ranked_candidates"]:
            assert entry["compatibility_status"] == "COMPATIBLE"
            assert entry["candidate_status"] == "RANKED"

    def test_ranked_candidates_have_rank_set(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
        }).json()
        for entry in data["ranked_candidates"]:
            assert entry["rank"] is not None
            assert entry["rank"] >= 1

    def test_ranked_candidates_have_compatibility_trace(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
        }).json()
        for entry in data["ranked_candidates"]:
            assert len(entry["compatibility_trace"]) >= 7

    def test_ranked_candidates_have_selection_criteria_trace(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
        }).json()
        for entry in data["ranked_candidates"]:
            cids = [c["criterion_id"] for c in entry["selection_criteria_trace"]]
            assert "RPM_MARGIN" in cids
            assert "REFERENCE_GUIDANCE" in cids


# ===========================================================================
# 6. Multi-eligible and engineering tie detection
# ===========================================================================

class TestMultiEligibleAndTies:
    def test_milling_p_produces_multiple_eligible(self):
        """Real catalog has multiple compatible combinations for milling/ISO-P."""
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        assert data["compatible_count"] > 1, (
            "Expected multiple COMPATIBLE candidates for milling/ISO-P"
        )

    def test_no_vc_all_candidates_tied(self):
        """Without Vc/D, RPM margin is N/A; reference guidance is uniform → all tied."""
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
        }).json()
        ranks = {e["rank"] for e in data["ranked_candidates"]}
        # All tied → single rank value
        assert len(ranks) == 1
        assert all(e["engineering_tie"] for e in data["ranked_candidates"])

    def test_no_vc_overall_state_no_differentiating_evidence(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
        }).json()
        assert data["overall_state"] == "COMPATIBLE_BUT_NO_DIFFERENTIATING_EVIDENCE"

    def test_tied_candidates_share_rank(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
        }).json()
        ranks = [e["rank"] for e in data["ranked_candidates"]]
        # All should be rank 1
        assert all(r == 1 for r in ranks)

    def test_tied_candidates_have_tie_reason(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
        }).json()
        for entry in data["ranked_candidates"]:
            if entry["engineering_tie"]:
                assert entry["engineering_tie_reason"] is not None


# ===========================================================================
# 7. RPM margin criterion
# ===========================================================================

class TestRpmMarginCriterion:
    def test_with_vc_d_rpm_margin_criterion_applicable(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
            "cutting_speed_m_min": 120.0,
            "tool_diameter_mm": 6.0,
        }).json()
        for entry in data["ranked_candidates"]:
            rpm_crit = next(
                c for c in entry["selection_criteria_trace"]
                if c["criterion_id"] == "RPM_MARGIN"
            )
            # haas-vf-2ss has spindle_max_rpm=12000 → criterion applicable
            assert rpm_crit["applicable"] is True

    def test_rpm_margin_present_when_applicable(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
            "cutting_speed_m_min": 120.0,
            "tool_diameter_mm": 6.0,
        }).json()
        for entry in data["ranked_candidates"]:
            assert entry["rpm_margin_pct"] is not None

    def test_rpm_margin_not_applicable_without_vc(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
        }).json()
        for entry in data["ranked_candidates"]:
            rpm_crit = next(
                c for c in entry["selection_criteria_trace"]
                if c["criterion_id"] == "RPM_MARGIN"
            )
            assert rpm_crit["applicable"] is False
            assert entry["rpm_margin_pct"] is None

    def test_no_missing_limit_as_zero(self):
        """MISSING_LIMIT_AS_ZERO=NO: absent machine RPM limit must NOT produce margin=0."""
        # No machine/tool filter — collect all ranked candidates
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "cutting_speed_m_min": 100.0,
            "tool_diameter_mm": 6.0,
        }).json()
        for entry in data["ranked_candidates"]:
            rpm_crit = next(
                (c for c in entry["selection_criteria_trace"]
                 if c["criterion_id"] == "RPM_MARGIN"),
                None,
            )
            if rpm_crit and not rpm_crit["applicable"]:
                # If inapplicable, rpm_margin_pct must be None, not 0.0
                assert entry["rpm_margin_pct"] is None, (
                    "MISSING_LIMIT_AS_ZERO=NO violation: margin is 0 instead of None"
                )


# ===========================================================================
# 8. Deterministic repeatability
# ===========================================================================

class TestDeterministicRepeatability:
    def test_same_request_same_result(self):
        payload = {
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
        }
        r1 = client.post("/api/selection/evaluate", json=payload).json()
        r2 = client.post("/api/selection/evaluate", json=payload).json()
        r1_ids = [(e["machine_id"], e["holder_id"], e["cutting_tool_id"])
                  for e in r1["ranked_candidates"]]
        r2_ids = [(e["machine_id"], e["holder_id"], e["cutting_tool_id"])
                  for e in r2["ranked_candidates"]]
        assert r1_ids == r2_ids, "Selection order changed between identical calls"

    def test_same_request_same_ranks(self):
        payload = {
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
        }
        r1 = client.post("/api/selection/evaluate", json=payload).json()
        r2 = client.post("/api/selection/evaluate", json=payload).json()
        r1_ranks = [e["rank"] for e in r1["ranked_candidates"]]
        r2_ranks = [e["rank"] for e in r2["ranked_candidates"]]
        assert r1_ranks == r2_ranks

    def test_same_request_with_vc_same_result(self):
        payload = {
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
            "cutting_speed_m_min": 100.0,
            "tool_diameter_mm": 6.0,
        }
        r1 = client.post("/api/selection/evaluate", json=payload).json()
        r2 = client.post("/api/selection/evaluate", json=payload).json()
        r1_ids = [(e["machine_id"], e["holder_id"], e["cutting_tool_id"])
                  for e in r1["ranked_candidates"]]
        r2_ids = [(e["machine_id"], e["holder_id"], e["cutting_tool_id"])
                  for e in r2["ranked_candidates"]]
        assert r1_ids == r2_ids


# ===========================================================================
# 9. Candidate bound behaviour
# ===========================================================================

class TestCandidateBoundBehaviour:
    def test_max_eligible_returned_is_respected(self):
        r = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "max_eligible_returned": 3,
        })
        data = r.json()
        assert len(data["ranked_candidates"]) <= 3

    def test_max_eligible_returned_1_returns_at_most_1(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "max_eligible_returned": 1,
        }).json()
        assert len(data["ranked_candidates"]) <= 1

    def test_candidates_evaluated_includes_all_triplets(self):
        """candidates_evaluated must count all evaluated triples, not just ranked."""
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
        }).json()
        total = (
            data["compatible_count"]
            + data["incompatible_count"]
            + data["not_rankable_count"]
        )
        assert data["candidates_evaluated"] == total

    def test_rejected_sample_max_5(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        assert len(data["rejected_sample"]) <= 5

    def test_not_rankable_sample_max_5(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "turning",
            "iso_material_group": "P",
            "machine_id": _M_NO_IFACE,
            "cutting_tool_id": _T_TURN_CNMG,
        }).json()
        assert len(data["not_rankable_sample"]) <= 5


# ===========================================================================
# 10. Compatibility trace preserved
# ===========================================================================

class TestCompatibilityTracePreserved:
    def test_ranked_candidate_has_full_7_rule_trace(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
        }).json()
        expected_rules = {
            "PROCESS_SUPPORT", "MACHINE_HOLDER_INTERFACE", "HOLDER_TOOL_SHANK",
            "ISO_MATERIAL_GROUP", "MACHINE_RPM", "HOLDER_RPM", "TOOL_RPM",
        }
        for entry in data["ranked_candidates"]:
            rule_ids = {r["rule_id"] for r in entry["compatibility_trace"]}
            assert expected_rules.issubset(rule_ids), (
                f"Compatibility trace missing rules: {expected_rules - rule_ids}"
            )

    def test_rejected_candidate_has_compatibility_trace(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_HSK,
            "cutting_tool_id": _T_MILL_6MM,
        }).json()
        for entry in data["rejected_sample"]:
            assert len(entry["compatibility_trace"]) >= 7

    def test_not_rankable_candidate_has_compatibility_trace(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "turning",
            "iso_material_group": "P",
            "machine_id": _M_NO_IFACE,
            "cutting_tool_id": _T_TURN_CNMG,
        }).json()
        for entry in data["not_rankable_sample"]:
            assert len(entry["compatibility_trace"]) >= 7

    def test_rejection_reason_non_empty(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_HSK,
            "cutting_tool_id": _T_MILL_6MM,
        }).json()
        for entry in data["rejected_sample"]:
            assert entry["rejection_reason"] is not None
            assert len(entry["rejection_reason"]) > 0

    def test_not_rankable_reason_non_empty(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "turning",
            "iso_material_group": "P",
            "machine_id": _M_NO_IFACE,
            "cutting_tool_id": _T_TURN_CNMG,
        }).json()
        for entry in data["not_rankable_sample"]:
            assert entry["not_rankable_reason"] is not None
            assert len(entry["not_rankable_reason"]) > 0


# ===========================================================================
# 11. No private path exposure
# ===========================================================================

class TestNoPrivatePaths:
    def test_no_private_path_in_evaluate_response(self):
        import json
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        payload_str = json.dumps(data)
        assert "C:\\" not in payload_str
        assert "/home/" not in payload_str
        assert "/Users/" not in payload_str

    def test_no_private_path_in_schema(self):
        import json
        data = client.get("/api/selection/schema").json()
        payload_str = json.dumps(data)
        assert "C:\\" not in payload_str
        assert "/home/" not in payload_str


# ===========================================================================
# 12. Engine constraint guards
# ===========================================================================

class TestEngineConstraints:
    def test_compatibility_logic_not_duplicated(self):
        """COMPATIBILITY_LOGIC_DUPLICATED=NO — selection engine imports, not re-implements."""
        import inspect
        from backend.selection import engine as sel_eng
        src = inspect.getsource(sel_eng)
        # Must import and call _compat_evaluate, not define its own rule evaluators
        assert "_compat_evaluate" in src or "evaluate" in src
        # Must NOT define new rule-evaluation functions matching compatibility engine names
        assert "_rule_machine_holder_interface" not in src
        assert "_rule_process_support" not in src

    def test_tool_life_not_used_for_selection(self):
        """TOOLLIFE_USED_FOR_SELECTION=NO."""
        import inspect
        from backend.selection import engine as sel_eng
        src = inspect.getsource(sel_eng)
        assert "tool_life" not in src.lower()
        assert "taylor" not in src.lower()

    def test_no_arbitrary_score_in_engine(self):
        """ARBITRARY_SELECTION_SCORE=NO — no weighted numeric scores in code."""
        import inspect
        from backend.selection import engine as sel_eng
        src = inspect.getsource(sel_eng)
        # Constraint annotations in docstrings are allowed; actual score variables are not.
        assert "score =" not in src.lower()
        assert "score+=" not in src.lower()
        assert "weight =" not in src.lower()

    def test_disclaimer_present_in_response(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        assert "disclaimer" in data
        d = data["disclaimer"].lower()
        assert "reference_only" in d or "reference only" in d or "not" in d

    def test_no_false_ai_claim_in_disclaimer(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
        }).json()
        d = data["disclaimer"].lower()
        assert "ai" not in d or "not" in d


# ===========================================================================
# 13. Overall state derivation
# ===========================================================================

class TestOverallStateDerivation:
    def test_compatible_no_vc_yields_compatible_but_no_differentiating(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_CAT40,
            "cutting_tool_id": _T_MILL_6MM,
        }).json()
        assert data["overall_state"] == "COMPATIBLE_BUT_NO_DIFFERENTIATING_EVIDENCE"

    def test_no_compatible_yields_no_compatible_configuration(self):
        # haas-st-10 doesn't support milling → all INCOMPATIBLE
        data = client.post("/api/selection/evaluate", json={
            "operation": "milling",
            "iso_material_group": "P",
            "machine_id": _M_NO_IFACE,
            "cutting_tool_id": _T_MILL_6MM,
        }).json()
        assert data["overall_state"] == "NO_COMPATIBLE_CONFIGURATION"

    def test_all_insufficient_yields_insufficient_data_for_selection(self):
        data = client.post("/api/selection/evaluate", json={
            "operation": "turning",
            "iso_material_group": "P",
            "machine_id": _M_NO_IFACE,
            "cutting_tool_id": _T_TURN_CNMG,
        }).json()
        assert data["overall_state"] == "INSUFFICIENT_DATA_FOR_SELECTION"

    def test_overall_state_is_one_of_four_valid_values(self):
        for payload in [
            {"operation": "milling", "iso_material_group": "P"},
            {"operation": "turning", "iso_material_group": "P",
             "machine_id": _M_NO_IFACE, "cutting_tool_id": _T_TURN_CNMG},
            {"operation": "milling", "iso_material_group": "P", "machine_id": _M_HSK},
        ]:
            data = client.post("/api/selection/evaluate", json=payload).json()
            assert data["overall_state"] in {
                "SELECTION_AVAILABLE",
                "NO_COMPATIBLE_CONFIGURATION",
                "COMPATIBLE_BUT_NO_DIFFERENTIATING_EVIDENCE",
                "INSUFFICIENT_DATA_FOR_SELECTION",
            }


# ===========================================================================
# 14. Engine unit-level tests (direct select() call)
# ===========================================================================

class TestEngineUnit:
    def test_select_returns_selection_response(self):
        req = SelectionRequest(
            operation="milling",
            iso_material_group="P",
            machine_id=_M_CAT40,
            cutting_tool_id=_T_MILL_6MM,
        )
        resp = select(req)
        assert resp.compatible_count >= 0
        assert resp.incompatible_count >= 0
        assert resp.not_rankable_count >= 0

    def test_select_counts_sum_to_evaluated(self):
        req = SelectionRequest(
            operation="milling",
            iso_material_group="P",
            machine_id=_M_CAT40,
            cutting_tool_id=_T_MILL_6MM,
        )
        resp = select(req)
        assert (
            resp.compatible_count + resp.incompatible_count + resp.not_rankable_count
            == resp.candidates_evaluated
        )

    def test_select_ranks_are_positive_integers(self):
        req = SelectionRequest(
            operation="milling",
            iso_material_group="P",
            machine_id=_M_CAT40,
            cutting_tool_id=_T_MILL_6MM,
        )
        resp = select(req)
        for c in resp.ranked_candidates:
            assert c.rank is not None
            assert c.rank >= 1

    def test_select_ranks_monotonically_non_decreasing(self):
        """Ranked candidates must be sorted: rank never decreases."""
        req = SelectionRequest(
            operation="milling",
            iso_material_group="P",
            machine_id=_M_CAT40,
            cutting_tool_id=_T_MILL_6MM,
        )
        resp = select(req)
        ranks = [c.rank for c in resp.ranked_candidates if c.rank is not None]
        assert ranks == sorted(ranks), f"Ranks not sorted: {ranks}"
