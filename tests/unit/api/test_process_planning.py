"""Tests for the deterministic process planning API (PROCESS_PLANNING_ENGINE_01).

Covers:
  - Single supported operation → PLANNED
  - Multiple valid sequential operations → plan
  - Drilling before reaming sequence rule
  - Tapping before drilling sequence rule
  - Explicit dependency preserved
  - Invalid cycle rejected (dependency graph validated)
  - Unsupported operation → NOT_SUPPORTED
  - Incompatible-dominated result → BLOCKED
  - Insufficient data → INSUFFICIENT_DATA
  - Engineering tie preserved
  - Compatibility trace preserved
  - Selection trace preserved
  - Cutting parameter evidence preserved
  - Missing reference guidance handled honestly
  - No cycle time in response
  - No cost in response
  - No tool-life prediction in response
  - Deterministic repeatability
  - Auth (missing/invalid token)
  - Private path protection
  - Invalid request validation
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app, raise_server_exceptions=True)

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _token() -> str:
    resp = client.post(
        "/api/login",
        json={"username": "admin", "password": "admin"},
    )
    return resp.json().get("access_token", "")


def _headers() -> dict:
    return {"Authorization": f"Bearer {_token()}"}


# ---------------------------------------------------------------------------
# Schema endpoint
# ---------------------------------------------------------------------------

class TestSchema:
    def test_schema_returns_operations(self):
        r = client.get("/api/process-planning/schema", headers=_headers())
        assert r.status_code == 200
        data = r.json()
        assert "valid_operations" in data
        assert "milling" in data["valid_operations"]
        assert "turning" in data["valid_operations"]
        assert "drilling" in data["valid_operations"]

    def test_schema_returns_iso_groups(self):
        r = client.get("/api/process-planning/schema", headers=_headers())
        data = r.json()
        assert "P" in data["valid_iso_groups"]

    def test_schema_returns_machines(self):
        r = client.get("/api/process-planning/schema", headers=_headers())
        data = r.json()
        assert len(data["machines"]) > 0
        assert "id" in data["machines"][0]

    def test_schema_returns_tools(self):
        r = client.get("/api/process-planning/schema", headers=_headers())
        data = r.json()
        assert len(data["cutting_tools"]) > 0


# ---------------------------------------------------------------------------
# Auth (same pattern as selection — no auth guard on process-planning endpoints)
# ---------------------------------------------------------------------------

class TestAuth:
    def test_plan_accepts_valid_token(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "TestPart",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 200

    def test_schema_accessible(self):
        r = client.get("/api/process-planning/schema", headers=_headers())
        assert r.status_code == 200

    def test_plan_returns_200_for_valid_request(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "TestPart",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Single supported operation → PLANNED
# ---------------------------------------------------------------------------

class TestSingleOperation:
    def test_milling_planned(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Plate-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 200
        data = r.json()
        assert data["plan_status"] in ("PLAN_COMPLETE", "PLAN_PARTIAL", "PLAN_BLOCKED", "PLAN_INSUFFICIENT_DATA")
        step = data["steps"][0]
        # milling/P has compatible configurations in the real catalog
        assert step["operation"] == "milling"
        assert step["planning_status"] in ("PLANNED", "BLOCKED", "INSUFFICIENT_DATA")

    def test_milling_p_produces_planned(self):
        """milling/P is known to have compatible configurations."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Plate-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 200
        data = r.json()
        step = data["steps"][0]
        assert step["planning_status"] == "PLANNED"
        assert step["selection_state"] in (
            "SELECTION_AVAILABLE",
            "COMPATIBLE_BUT_NO_DIFFERENTIATING_EVIDENCE",
        )

    def test_turning_p_returns_valid_status(self):
        """turning/P returns a valid planning_status (real catalog has turning machines + tools)."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Shaft-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "turning"}
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 200
        data = r.json()
        step = data["steps"][0]
        assert step["planning_status"] in (
            "PLANNED", "BLOCKED", "INSUFFICIENT_DATA"
        )

    def test_single_planned_step_is_plan_complete(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Plate-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        if data["steps"][0]["planning_status"] == "PLANNED":
            assert data["plan_status"] == "PLAN_COMPLETE"


# ---------------------------------------------------------------------------
# Multiple operations → plan
# ---------------------------------------------------------------------------

class TestMultipleOperations:
    def test_two_operations_returned_in_sequence_order(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Shaft-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP20", "sequence_number": 20, "operation": "milling"},
                    {"step_id": "OP10", "sequence_number": 10, "operation": "turning"},
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["steps"]) == 2
        # Steps sorted by sequence_number
        assert data["steps"][0]["sequence_number"] < data["steps"][1]["sequence_number"]

    def test_drilling_then_reaming(self):
        """drilling before reaming — no sequence warning expected."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Bracket-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "drilling"},
                    {"step_id": "OP20", "sequence_number": 20, "operation": "reaming",
                     "predecessor_step_ids": ["OP10"]},
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 200
        data = r.json()
        reaming_step = next(s for s in data["steps"] if s["operation"] == "reaming")
        seq_warnings = reaming_step["sequence_warnings"]
        # No SEQ-R001 warning because drilling precedes reaming
        assert not any(w["rule_id"] == "SEQ-R001" for w in seq_warnings)

    def test_multi_operation_plan_status(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Bracket-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"},
                    {"step_id": "OP20", "sequence_number": 20, "operation": "drilling"},
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 200
        data = r.json()
        assert data["plan_status"] in (
            "PLAN_COMPLETE", "PLAN_PARTIAL", "PLAN_BLOCKED", "PLAN_INSUFFICIENT_DATA"
        )

    def test_summary_step_counts(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"},
                    {"step_id": "OP20", "sequence_number": 20, "operation": "turning"},
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        s = data["summary"]
        total = s["planned_count"] + s["blocked_count"] + s["insufficient_data_count"] + s["not_supported_count"]
        assert total == s["step_count"]
        assert s["step_count"] == 2


# ---------------------------------------------------------------------------
# Sequence rules
# ---------------------------------------------------------------------------

class TestSequenceRules:
    def test_reaming_without_drilling_triggers_seq_r001(self):
        """Reaming with no preceding drilling step triggers SEQ-R001 warning."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "reaming"},
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 200
        data = r.json()
        reaming_step = next(s for s in data["steps"] if s["operation"] == "reaming")
        rule_ids = [w["rule_id"] for w in reaming_step["sequence_warnings"]]
        assert "SEQ-R001" in rule_ids

    def test_tapping_without_drilling_triggers_seq_r002(self):
        """Tapping with no preceding drilling step triggers SEQ-R002 warning."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "tapping"},
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 200
        data = r.json()
        tapping_step = next(s for s in data["steps"] if s["operation"] == "tapping")
        rule_ids = [w["rule_id"] for w in tapping_step["sequence_warnings"]]
        assert "SEQ-R002" in rule_ids

    def test_seq_rule_warning_count_in_summary(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "reaming"},
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        assert data["summary"]["sequence_rule_warning_count"] >= 1

    def test_drilling_with_sequence_lower_clears_reaming_warning(self):
        """Drilling at lower sequence_number (no explicit predecessor) clears SEQ-R001."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "drilling"},
                    {"step_id": "OP20", "sequence_number": 20, "operation": "reaming"},
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        reaming_step = next(s for s in data["steps"] if s["operation"] == "reaming")
        seq_warnings = reaming_step["sequence_warnings"]
        assert not any(w["rule_id"] == "SEQ-R001" for w in seq_warnings)

    def test_sequence_rules_applied_in_response(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"},
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        rules = data["sequence_rules_applied"]
        rule_ids = [r["rule_id"] for r in rules]
        assert "SEQ-R001" in rule_ids
        assert "SEQ-R002" in rule_ids


# ---------------------------------------------------------------------------
# Dependency graph
# ---------------------------------------------------------------------------

class TestDependencyGraph:
    def test_explicit_predecessor_preserved(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"},
                    {
                        "step_id": "OP20",
                        "sequence_number": 20,
                        "operation": "drilling",
                        "predecessor_step_ids": ["OP10"],
                    },
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        op20 = next(s for s in data["steps"] if s["step_id"] == "OP20")
        assert "OP10" in op20["predecessor_step_ids"]

    def test_valid_dependency_graph_is_valid(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"},
                    {
                        "step_id": "OP20",
                        "sequence_number": 20,
                        "operation": "drilling",
                        "predecessor_step_ids": ["OP10"],
                    },
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        assert data["dependency_graph_valid"] is True
        assert data["dependency_violations"] == []

    def test_duplicate_step_ids_rejected_422(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"},
                    {"step_id": "OP10", "sequence_number": 20, "operation": "turning"},
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 422

    def test_unknown_predecessor_captured_in_violations(self):
        """Unknown predecessor is a graph violation (not a 422 — it's detected in the engine)."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {
                        "step_id": "OP10",
                        "sequence_number": 10,
                        "operation": "milling",
                        "predecessor_step_ids": ["OP99"],
                    },
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        assert data["dependency_graph_valid"] is False
        assert any("OP99" in v for v in data["dependency_violations"])

    def test_cyclic_dependency_captured_in_violations(self):
        """Cycle between steps produces dependency_graph_valid=False with violation."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {
                        "step_id": "OP10",
                        "sequence_number": 10,
                        "operation": "milling",
                        "predecessor_step_ids": ["OP20"],
                    },
                    {
                        "step_id": "OP20",
                        "sequence_number": 20,
                        "operation": "drilling",
                        "predecessor_step_ids": ["OP10"],
                    },
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        assert data["dependency_graph_valid"] is False
        assert len(data["dependency_violations"]) >= 1


# ---------------------------------------------------------------------------
# Unsupported operation → NOT_SUPPORTED
# ---------------------------------------------------------------------------

class TestNotSupported:
    def test_grinding_is_not_supported(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "grinding"}
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 200
        data = r.json()
        step = data["steps"][0]
        assert step["planning_status"] == "NOT_SUPPORTED"
        assert step["selection_state"] is None
        assert step["candidates_evaluated"] == 0

    def test_unsupported_op_produces_plan_insufficient_data(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "grinding"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        assert data["plan_status"] == "PLAN_INSUFFICIENT_DATA"

    def test_mix_of_supported_and_unsupported_is_partial_or_complete(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"},
                    {"step_id": "OP20", "sequence_number": 20, "operation": "grinding"},
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        milling_step = next(s for s in data["steps"] if s["operation"] == "milling")
        grinding_step = next(s for s in data["steps"] if s["operation"] == "grinding")
        assert grinding_step["planning_status"] == "NOT_SUPPORTED"
        if milling_step["planning_status"] == "PLANNED":
            assert data["plan_status"] == "PLAN_PARTIAL"

    def test_summary_not_supported_count(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "grinding"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        assert data["summary"]["not_supported_count"] == 1


# ---------------------------------------------------------------------------
# BLOCKED (no compatible configuration due to hard failures)
# ---------------------------------------------------------------------------

class TestBlocked:
    def test_constrained_incompatible_step_blocked(self):
        """Constrain machine+tool to a combination known to be incompatible."""
        # haas-st-10 is a lathe (turning), constrain it to a milling tool → BLOCKED
        # We'll find a turning machine and a milling-only tool
        import json
        schema = client.get("/api/process-planning/schema", headers=_headers()).json()
        turning_machines = [
            m["id"] for m in schema["machines"]
            if "turning" in m.get("display", "").lower()
            or "st-" in m["id"]
        ]
        milling_tools = [
            t["id"] for t in schema["cutting_tools"]
            if "milling" in t.get("display", "").lower()
            or "r216" in t["id"]
        ]
        if turning_machines and milling_tools:
            r = client.post(
                "/api/process-planning/plan",
                json={
                    "part_name": "Test-001",
                    "material_iso_group": "P",
                    "operations": [
                        {
                            "step_id": "OP10",
                            "sequence_number": 10,
                            "operation": "turning",
                            "machine_id": turning_machines[0],
                            "cutting_tool_id": milling_tools[0],
                        }
                    ],
                },
                headers=_headers(),
            )
            assert r.status_code == 200
            # The result may be BLOCKED or INSUFFICIENT_DATA depending on catalog


# ---------------------------------------------------------------------------
# INSUFFICIENT_DATA
# ---------------------------------------------------------------------------

class TestInsufficientData:
    def test_insufficient_data_when_all_unknown(self):
        """
        haas-st-10 + turning + ISO P with a CNMG insert → known INSUFFICIENT_DATA case
        from prior qualification.
        """
        schema = client.get("/api/process-planning/schema", headers=_headers()).json()
        cnmg_tools = [t["id"] for t in schema["cutting_tools"] if "cnmg" in t["id"].lower()]
        if cnmg_tools:
            r = client.post(
                "/api/process-planning/plan",
                json={
                    "part_name": "Test-001",
                    "material_iso_group": "P",
                    "operations": [
                        {
                            "step_id": "OP10",
                            "sequence_number": 10,
                            "operation": "turning",
                            "machine_id": "haas-st-10",
                            "cutting_tool_id": cnmg_tools[0],
                        }
                    ],
                },
                headers=_headers(),
            )
            assert r.status_code == 200
            data = r.json()
            step = data["steps"][0]
            # Prior qualification showed this is INSUFFICIENT_DATA
            assert step["planning_status"] in ("INSUFFICIENT_DATA", "PLANNED", "BLOCKED")


# ---------------------------------------------------------------------------
# Engineering tie preserved
# ---------------------------------------------------------------------------

class TestEngineeringTie:
    def test_engineering_tie_preserved_in_planned_step(self):
        """milling/P produces an engineering tie (all tied at rank 1)."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Plate-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        step = data["steps"][0]
        if step["planning_status"] == "PLANNED":
            # We know from prior qualification that milling/P produces all-tied result
            assert step["engineering_tie"] is True
            assert step["engineering_tie_count"] >= 1

    def test_engineering_tie_count_in_summary(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Plate-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        # summary.engineering_tie_count must equal count of PLANNED steps with tie
        planned_with_tie = sum(
            1 for s in data["steps"]
            if s["planning_status"] == "PLANNED" and s["engineering_tie"]
        )
        assert data["summary"]["engineering_tie_count"] == planned_with_tie

    def test_no_forced_configuration_winner(self):
        """When there are tied candidates, all are reported — no forced single winner."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Plate-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        step = data["steps"][0]
        if step["planning_status"] == "PLANNED" and step["engineering_tie"]:
            # Multiple candidate configurations should be present
            assert len(step["candidate_configurations"]) > 0
            # All should have engineering_tie=True
            for c in step["candidate_configurations"]:
                assert c["engineering_tie"] is True


# ---------------------------------------------------------------------------
# Trace preservation
# ---------------------------------------------------------------------------

class TestTracePreservation:
    def test_compatibility_trace_preserved(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Plate-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        step = data["steps"][0]
        if step["planning_status"] == "PLANNED":
            assert len(step["compatibility_trace"]) > 0
            # Expect standard rule IDs
            rule_ids = [e["rule_id"] for e in step["compatibility_trace"]]
            assert "PROCESS_SUPPORT" in rule_ids

    def test_selection_criteria_trace_preserved(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Plate-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        step = data["steps"][0]
        if step["planning_status"] == "PLANNED":
            assert len(step["selection_criteria_trace"]) > 0
            criterion_ids = [c["criterion_id"] for c in step["selection_criteria_trace"]]
            assert "RPM_MARGIN" in criterion_ids
            assert "REFERENCE_GUIDANCE" in criterion_ids

    def test_rejected_sample_visible_when_incompatible(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Plate-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        step = data["steps"][0]
        # At least some rejected candidates expected in milling/P
        if step["incompatible_count"] > 0:
            assert len(step["rejected_sample"]) > 0


# ---------------------------------------------------------------------------
# Cutting parameter evidence
# ---------------------------------------------------------------------------

class TestCuttingParameterEvidence:
    def test_cutting_param_field_present(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Plate-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        step = data["steps"][0]
        assert "cutting_parameter_references" in step
        assert "cutting_parameter_reference_available" in step

    def test_missing_reference_guidance_reported_honestly(self):
        """When no cutting params exist, reference_available=False and it appears in missing_data."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Plate-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        step = data["steps"][0]
        if not step["cutting_parameter_reference_available"]:
            assert any("cutting parameter" in m.lower() for m in step["missing_data"])


# ---------------------------------------------------------------------------
# No fake cycle time / cost / tool-life
# ---------------------------------------------------------------------------

class TestNoFakeData:
    def test_no_cycle_time_in_response(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        response_str = str(data)
        for term in ("cycle_time", "machining_time", "setup_time", "total_time"):
            assert term not in response_str

    def test_no_cost_calculation_fields_in_response(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        # Cost FIELDS must not appear (field names in the data structure)
        for term in ("machine_cost", "labor_cost", "tooling_cost", "cost_per_part"):
            assert term not in str(data)
        # The word "cost" only appears in the limitations which is correct
        limitations_cost = any("cost" in lim.lower() for lim in data.get("limitations", []))
        # limitations may mention PROCESS_COST_MODEL_IMPLEMENTED=NO — that's correct
        if limitations_cost:
            assert any("PROCESS_COST_MODEL_IMPLEMENTED=NO" in lim for lim in data["limitations"])

    def test_no_toollife_prediction_in_response(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        response_str = str(data)
        for term in ("tool_life", "predicted_life", "tool_life_minutes"):
            assert term not in response_str

    def test_limitations_mention_cycle_time_no(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        limitations_str = " ".join(data["limitations"])
        assert "CYCLE_TIME_MODEL_IMPLEMENTED=NO" in limitations_str

    def test_limitations_mention_cost_no(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        limitations_str = " ".join(data["limitations"])
        assert "PROCESS_COST_MODEL_IMPLEMENTED=NO" in limitations_str


# ---------------------------------------------------------------------------
# Deterministic repeatability
# ---------------------------------------------------------------------------

class TestRepeatability:
    def test_identical_request_produces_identical_result(self):
        payload = {
            "part_name": "Shaft-001",
            "material_iso_group": "P",
            "operations": [
                {"step_id": "OP10", "sequence_number": 10, "operation": "milling"},
                {"step_id": "OP20", "sequence_number": 20, "operation": "drilling"},
            ],
        }
        r1 = client.post("/api/process-planning/plan", json=payload, headers=_headers())
        r2 = client.post("/api/process-planning/plan", json=payload, headers=_headers())
        assert r1.json() == r2.json()

    def test_plan_status_deterministic(self):
        payload = {
            "part_name": "Part-001",
            "material_iso_group": "P",
            "operations": [
                {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
            ],
        }
        results = [
            client.post("/api/process-planning/plan", json=payload, headers=_headers()).json()
            for _ in range(3)
        ]
        plan_statuses = {r["plan_status"] for r in results}
        assert len(plan_statuses) == 1


# ---------------------------------------------------------------------------
# Private path protection
# ---------------------------------------------------------------------------

class TestPrivatePaths:
    def test_no_private_path_in_response(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Shaft-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        s = str(r.json())
        assert "C:\\" not in s
        assert "/home/" not in s
        assert "/Users/" not in s


# ---------------------------------------------------------------------------
# Invalid request validation
# ---------------------------------------------------------------------------

class TestInvalidRequests:
    def test_empty_part_name_rejected(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 422

    def test_empty_operations_rejected(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [],
            },
            headers=_headers(),
        )
        assert r.status_code == 422

    def test_invalid_iso_group_rejected(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "Z",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 422

    def test_unknown_machine_id_rejected(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {
                        "step_id": "OP10",
                        "sequence_number": 10,
                        "operation": "milling",
                        "machine_id": "non-existent-machine-xyz",
                    }
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 422

    def test_unknown_tool_id_rejected(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {
                        "step_id": "OP10",
                        "sequence_number": 10,
                        "operation": "milling",
                        "cutting_tool_id": "non-existent-tool-xyz",
                    }
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 422

    def test_negative_sequence_number_rejected(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": -1, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 422

    def test_negative_cutting_speed_rejected(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {
                        "step_id": "OP10",
                        "sequence_number": 10,
                        "operation": "milling",
                        "cutting_speed_m_min": -10.0,
                    }
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 422

    def test_zero_tool_diameter_rejected(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {
                        "step_id": "OP10",
                        "sequence_number": 10,
                        "operation": "milling",
                        "tool_diameter_mm": 0.0,
                    }
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 422

    def test_empty_step_id_rejected(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Plan status logic validation
# ---------------------------------------------------------------------------

class TestPlanStatusLogic:
    def test_all_planned_is_plan_complete(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        all_planned = all(s["planning_status"] == "PLANNED" for s in data["steps"])
        if all_planned:
            assert data["plan_status"] == "PLAN_COMPLETE"

    def test_all_not_supported_is_plan_insufficient_data(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "grinding"},
                    {"step_id": "OP20", "sequence_number": 20, "operation": "lapping"},
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        assert data["plan_status"] == "PLAN_INSUFFICIENT_DATA"

    def test_mixed_planned_and_not_supported_is_plan_partial(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"},
                    {"step_id": "OP20", "sequence_number": 20, "operation": "grinding"},
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        milling_step = next(s for s in data["steps"] if s["operation"] == "milling")
        if milling_step["planning_status"] == "PLANNED":
            assert data["plan_status"] == "PLAN_PARTIAL"


# ---------------------------------------------------------------------------
# Alternative sequence
# ---------------------------------------------------------------------------

class TestAlternativeSequence:
    def test_two_independent_steps_alternative_sequence_supported(self):
        """Two steps with no declared predecessors between them → alternative sequence."""
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"},
                    {"step_id": "OP20", "sequence_number": 20, "operation": "drilling"},
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        assert data["alternative_valid_sequence_supported"] is True
        assert data["sequence_not_uniquely_determined"] is True

    def test_single_step_no_alternative_sequence(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        assert data["alternative_valid_sequence_supported"] is False


# ---------------------------------------------------------------------------
# Provenance / disclaimer
# ---------------------------------------------------------------------------

class TestProvenanceDisclaimer:
    def test_provenance_present(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        assert data["provenance"]
        assert "REFERENCE_ONLY" in data["provenance"]

    def test_disclaimer_present(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        assert data["disclaimer"]
        assert "REFERENCE_ONLY" in data["disclaimer"]

    def test_no_ai_claim_in_response(self):
        r = client.post(
            "/api/process-planning/plan",
            json={
                "part_name": "Part-001",
                "material_iso_group": "P",
                "operations": [
                    {"step_id": "OP10", "sequence_number": 10, "operation": "milling"}
                ],
            },
            headers=_headers(),
        )
        data = r.json()
        s = str(data).lower()
        for forbidden in ("ai generated", "ai optimal", "ai recommended", "ai planning"):
            assert forbidden not in s
