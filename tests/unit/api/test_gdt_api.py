"""Tests for GD&T Advanced Intelligence API endpoints (EPIC_04B Phase 3).

Coverage:
  GET  /api/gdt/schema
  POST /api/gdt/validate
  POST /api/gdt/interpret
  POST /api/gdt/bonus-tolerance
  POST /api/gdt/virtual-condition

Safety flags verified:
  FABRICATED_ACTUAL_SIZE=NO
  FABRICATED_BONUS_TOLERANCE=NO
  FABRICATED_VIRTUAL_CONDITION=NO
  AUTO_INTERPRETATION_MARKED_APPROVED=NO
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FCF_POSITION_MMC = {
    "characteristic": "POSITION",
    "tolerance_value": 0.05,
    "diameter_zone": True,
    "modifier": "MMC",
    "datum_frame": {
        "primary": {"label": "A", "precedence": 1},
        "secondary": {"label": "B", "precedence": 2},
        "tertiary": {"label": "C", "precedence": 3},
    },
}

_FCF_FLATNESS = {
    "characteristic": "FLATNESS",
    "tolerance_value": 0.02,
    "diameter_zone": False,
    "modifier": "NONE",
}

_FCF_CIRCULARITY = {
    "characteristic": "CIRCULARITY",
    "tolerance_value": 0.01,
    "diameter_zone": False,
    "modifier": "NONE",
}

_FCF_RUNOUT = {
    "characteristic": "CIRCULAR_RUNOUT",
    "tolerance_value": 0.03,
    "diameter_zone": False,
    "modifier": "NONE",
    "datum_frame": {"primary": {"label": "A", "precedence": 1}},
}

_FCF_PROFILE = {
    "characteristic": "PROFILE_OF_A_SURFACE",
    "tolerance_value": 0.1,
    "diameter_zone": False,
    "modifier": "NONE",
}

_FOS_INTERNAL = {
    "fos_id": "FOS-H001",
    "kind": "INTERNAL_CYLINDRICAL",
    "nominal_mm": 25.0,
    "upper_limit_mm": 25.021,
    "lower_limit_mm": 25.000,
    "actual_size_mm": None,
}

_FOS_INTERNAL_WITH_ACTUAL = {
    "fos_id": "FOS-H002",
    "kind": "INTERNAL_CYLINDRICAL",
    "nominal_mm": 25.0,
    "upper_limit_mm": 25.021,
    "lower_limit_mm": 25.000,
    "actual_size_mm": 25.010,
}

_FOS_EXTERNAL = {
    "fos_id": "FOS-S001",
    "kind": "EXTERNAL_CYLINDRICAL",
    "nominal_mm": 20.0,
    "upper_limit_mm": 20.000,
    "lower_limit_mm": 19.987,
    "actual_size_mm": 19.995,
}


# ---------------------------------------------------------------------------
# GET /api/gdt/schema
# ---------------------------------------------------------------------------

class TestGdtSchema:
    def test_schema_200(self):
        r = client.get("/api/gdt/schema")
        assert r.status_code == 200

    def test_schema_has_characteristics(self):
        r = client.get("/api/gdt/schema")
        data = r.json()
        assert "POSITION" in data["characteristics"]
        assert "FLATNESS" in data["characteristics"]
        assert "CIRCULAR_RUNOUT" in data["characteristics"]

    def test_schema_has_modifiers(self):
        r = client.get("/api/gdt/schema")
        data = r.json()
        assert "MMC" in data["feature_modifiers"]
        assert "LMC" in data["feature_modifiers"]
        assert "RFS" in data["feature_modifiers"]

    def test_schema_has_datum_boundary_modifiers(self):
        r = client.get("/api/gdt/schema")
        data = r.json()
        assert "MMB" in data["datum_boundary_modifiers"]
        assert "RMB" in data["datum_boundary_modifiers"]

    def test_schema_has_fos_kinds(self):
        r = client.get("/api/gdt/schema")
        data = r.json()
        assert "INTERNAL_CYLINDRICAL" in data["feature_of_size_kinds"]
        assert "EXTERNAL_CYLINDRICAL" in data["feature_of_size_kinds"]

    def test_schema_has_validation_rules(self):
        r = client.get("/api/gdt/schema")
        data = r.json()
        assert "VAL-GDT-001" in data["validation_rule_ids"]
        assert "VAL-GDT-006" in data["validation_rule_ids"]

    def test_schema_has_inspection_methods(self):
        r = client.get("/api/gdt/schema")
        data = r.json()
        assert "CMM" in data["inspection_methods"]
        assert "ROUNDNESS_TESTER" in data["inspection_methods"]

    def test_schema_has_disclaimer(self):
        r = client.get("/api/gdt/schema")
        data = r.json()
        assert "REFERENCE_ONLY" in data["disclaimer"]

    def test_schema_unknown_not_in_characteristics(self):
        r = client.get("/api/gdt/schema")
        data = r.json()
        assert "UNKNOWN" not in data["characteristics"]


# ---------------------------------------------------------------------------
# POST /api/gdt/validate
# ---------------------------------------------------------------------------

class TestGdtValidate:
    def test_position_mmc_with_datum_and_fos_valid(self):
        # MMC with FOS context → VALID (VAL-GDT-003 requires FOS)
        r = client.post("/api/gdt/validate", json={
            "req_id": "T-001",
            "fcf": _FCF_POSITION_MMC,
            "fos": _FOS_INTERNAL,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["overall"] == "VALID"
        assert data["req_id"] == "T-001"

    def test_flatness_no_datum_valid(self):
        r = client.post("/api/gdt/validate", json={
            "req_id": "T-002",
            "fcf": _FCF_FLATNESS,
        })
        assert r.status_code == 200
        assert r.json()["overall"] == "VALID"

    def test_flatness_with_datum_invalid(self):
        fcf = {**_FCF_FLATNESS, "datum_frame": {"primary": {"label": "A", "precedence": 1}}}
        r = client.post("/api/gdt/validate", json={
            "req_id": "T-003",
            "fcf": fcf,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["overall"] == "INVALID"
        rule_ids = [f["rule_id"] for f in data["findings"]]
        assert "VAL-GDT-001" in rule_ids

    def test_position_no_datum_warning(self):
        fcf = {**_FCF_POSITION_MMC, "datum_frame": None}
        r = client.post("/api/gdt/validate", json={
            "req_id": "T-004",
            "fcf": fcf,
        })
        assert r.status_code == 200
        # VAL-GDT-002 is WARNING not ERROR, so overall may still be VALID
        data = r.json()
        findings = data["findings"]
        val002 = next((f for f in findings if f["rule_id"] == "VAL-GDT-002"), None)
        assert val002 is not None
        assert val002["severity"] == "WARNING"

    def test_mmc_on_non_fos_invalid(self):
        r = client.post("/api/gdt/validate", json={
            "req_id": "T-005",
            "fcf": _FCF_POSITION_MMC,
            "fos": {
                "fos_id": "FOS-X",
                "kind": "NON_FEATURE_OF_SIZE",
            },
        })
        assert r.status_code == 200
        data = r.json()
        assert data["overall"] == "INVALID"

    def test_circularity_valid(self):
        r = client.post("/api/gdt/validate", json={
            "req_id": "T-006",
            "fcf": _FCF_CIRCULARITY,
        })
        assert r.status_code == 200
        assert r.json()["overall"] == "VALID"

    def test_findings_have_structured_fields(self):
        r = client.post("/api/gdt/validate", json={
            "req_id": "T-007",
            "fcf": _FCF_FLATNESS,
            "fos": None,
        })
        data = r.json()
        for f in data["findings"]:
            assert "rule_id" in f
            assert "passed" in f
            assert "severity" in f
            assert "message" in f

    def test_response_has_disclaimer(self):
        r = client.post("/api/gdt/validate", json={
            "req_id": "T-008",
            "fcf": _FCF_POSITION_MMC,
        })
        data = r.json()
        assert "disclaimer" in data
        assert "REFERENCE_ONLY" in data["disclaimer"]

    def test_zero_tolerance_rejected(self):
        r = client.post("/api/gdt/validate", json={
            "req_id": "T-009",
            "fcf": {**_FCF_POSITION_MMC, "tolerance_value": 0.0},
        })
        assert r.status_code == 400

    def test_legacy_concentricity_advisory(self):
        r = client.post("/api/gdt/validate", json={
            "req_id": "T-010",
            "fcf": {
                "characteristic": "CONCENTRICITY",
                "tolerance_value": 0.02,
                "diameter_zone": False,
                "modifier": "NONE",
                "datum_frame": {"primary": {"label": "A", "precedence": 1}},
            },
        })
        assert r.status_code == 200
        data = r.json()
        findings = data["findings"]
        val008 = next((f for f in findings if f["rule_id"] == "VAL-GDT-008"), None)
        assert val008 is not None
        assert val008["severity"] == "INFO"


# ---------------------------------------------------------------------------
# POST /api/gdt/interpret
# ---------------------------------------------------------------------------

class TestGdtInterpret:
    def test_interpret_200(self):
        r = client.post("/api/gdt/interpret", json={
            "req_id": "I-001",
            "fcf": _FCF_POSITION_MMC,
        })
        assert r.status_code == 200

    def test_approval_status_pending(self):
        r = client.post("/api/gdt/interpret", json={
            "req_id": "I-002",
            "fcf": _FCF_POSITION_MMC,
        })
        data = r.json()
        assert data["approval_status"] == "PENDING_REVIEW"

    def test_characteristic_returned(self):
        r = client.post("/api/gdt/interpret", json={
            "req_id": "I-003",
            "fcf": _FCF_POSITION_MMC,
        })
        data = r.json()
        assert data["characteristic"] == "POSITION"

    def test_modifier_description_returned(self):
        r = client.post("/api/gdt/interpret", json={
            "req_id": "I-004",
            "fcf": _FCF_POSITION_MMC,
        })
        data = r.json()
        assert "MMC" in data["modifier_description"]

    def test_tolerance_zone_returned(self):
        r = client.post("/api/gdt/interpret", json={
            "req_id": "I-005",
            "fcf": _FCF_POSITION_MMC,
        })
        data = r.json()
        tz = data["tolerance_zone"]
        assert tz["geometry"] is not None
        assert tz["value_mm"] == pytest.approx(0.05)

    def test_datum_frame_returned(self):
        r = client.post("/api/gdt/interpret", json={
            "req_id": "I-006",
            "fcf": _FCF_POSITION_MMC,
        })
        data = r.json()
        df = data["datum_frame"]
        assert df is not None
        assert df["primary"]["label"] == "A"
        assert df["secondary"]["label"] == "B"

    def test_fos_context_returned_when_provided(self):
        r = client.post("/api/gdt/interpret", json={
            "req_id": "I-007",
            "fcf": _FCF_POSITION_MMC,
            "fos": _FOS_INTERNAL,
        })
        data = r.json()
        fos = data["fos_context"]
        assert fos is not None
        assert fos["kind"] == "INTERNAL_CYLINDRICAL"
        assert fos["is_true_fos"] is True

    def test_fos_context_null_when_absent(self):
        r = client.post("/api/gdt/interpret", json={
            "req_id": "I-008",
            "fcf": _FCF_POSITION_MMC,
        })
        assert r.json()["fos_context"] is None

    def test_process_implications_tight_position(self):
        r = client.post("/api/gdt/interpret", json={
            "req_id": "I-009",
            "fcf": {**_FCF_POSITION_MMC, "tolerance_value": 0.04},
        })
        data = r.json()
        rule_ids = [p["rule_id"] for p in data["process_implications"]]
        assert "R-RT-GDT-001" in rule_ids

    def test_inspection_implications_returned(self):
        r = client.post("/api/gdt/interpret", json={
            "req_id": "I-010",
            "fcf": _FCF_POSITION_MMC,
        })
        data = r.json()
        assert len(data["inspection_implications"]) > 0
        methods = [i["method"] for i in data["inspection_implications"]]
        assert "CMM" in methods

    def test_inspection_mmc_size_step_returned(self):
        r = client.post("/api/gdt/interpret", json={
            "req_id": "I-011",
            "fcf": _FCF_POSITION_MMC,
        })
        data = r.json()
        methods = [i["method"] for i in data["inspection_implications"]]
        assert "SIZE_MEASUREMENT" in methods

    def test_circularity_roundness_tester(self):
        r = client.post("/api/gdt/interpret", json={
            "req_id": "I-012",
            "fcf": _FCF_CIRCULARITY,
        })
        data = r.json()
        methods = [i["method"] for i in data["inspection_implications"]]
        assert "ROUNDNESS_TESTER" in methods

    def test_runout_process_implication(self):
        r = client.post("/api/gdt/interpret", json={
            "req_id": "I-013",
            "fcf": _FCF_RUNOUT,
        })
        data = r.json()
        rule_ids = [p["rule_id"] for p in data["process_implications"]]
        assert "R-RT-GDT-004" in rule_ids

    def test_profile_surface_inspection(self):
        r = client.post("/api/gdt/interpret", json={
            "req_id": "I-014",
            "fcf": _FCF_PROFILE,
        })
        data = r.json()
        methods = [i["method"] for i in data["inspection_implications"]]
        assert "CMM_CONTOUR_SCAN" in methods

    def test_confidence_ambiguous_when_invalid(self):
        # FLATNESS with datum → ambiguity → AMBIGUOUS confidence
        fcf = {**_FCF_FLATNESS, "datum_frame": {"primary": {"label": "A", "precedence": 1}}}
        r = client.post("/api/gdt/interpret", json={
            "req_id": "I-015",
            "fcf": fcf,
        })
        data = r.json()
        assert data["confidence"] == "AMBIGUOUS"

    def test_ambiguities_list_populated_on_invalid(self):
        fcf = {**_FCF_FLATNESS, "datum_frame": {"primary": {"label": "A", "precedence": 1}}}
        r = client.post("/api/gdt/interpret", json={
            "req_id": "I-016",
            "fcf": fcf,
        })
        data = r.json()
        assert len(data["ambiguities"]) > 0

    def test_disclaimer_present(self):
        r = client.post("/api/gdt/interpret", json={
            "req_id": "I-017",
            "fcf": _FCF_POSITION_MMC,
        })
        assert "REFERENCE_ONLY" in r.json()["disclaimer"]

    def test_fos_mmc_lmc_derived_sizes(self):
        r = client.post("/api/gdt/interpret", json={
            "req_id": "I-018",
            "fcf": _FCF_POSITION_MMC,
            "fos": _FOS_INTERNAL,
        })
        fos = r.json()["fos_context"]
        # Internal: MMC = lower limit = 25.0
        assert fos["mmc_size_mm"] == pytest.approx(25.0)
        # Internal: LMC = upper limit = 25.021
        assert fos["lmc_size_mm"] == pytest.approx(25.021)


# ---------------------------------------------------------------------------
# POST /api/gdt/bonus-tolerance
# ---------------------------------------------------------------------------

class TestGdtBonusTolerance:
    def test_no_actual_size_returns_not_computed(self):
        r = client.post("/api/gdt/bonus-tolerance", json={
            "req_id": "B-001",
            "fcf": _FCF_POSITION_MMC,
            "fos": _FOS_INTERNAL,  # actual_size_mm is None
        })
        assert r.status_code == 200
        data = r.json()
        assert data["computed"] is False
        assert "INSUFFICIENT_DATA" in (data["reason_not_computed"] or "")

    def test_actual_size_provided_computes(self):
        r = client.post("/api/gdt/bonus-tolerance", json={
            "req_id": "B-002",
            "fcf": _FCF_POSITION_MMC,
            "fos": _FOS_INTERNAL_WITH_ACTUAL,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["computed"] is True
        assert data["bonus_amount_mm"] is not None
        assert data["total_tolerance_mm"] is not None

    def test_internal_mmc_bonus_formula(self):
        # Internal MMC hole: bonus = actual − MMC_size
        # FOS: nominal=25, upper=25.021, lower=25.000, actual=25.010
        # MMC = 25.000, stated=0.05
        # bonus = 25.010 − 25.000 = 0.010, total = 0.050 + 0.010 = 0.060
        r = client.post("/api/gdt/bonus-tolerance", json={
            "req_id": "B-003",
            "fcf": _FCF_POSITION_MMC,
            "fos": _FOS_INTERNAL_WITH_ACTUAL,
        })
        data = r.json()
        assert data["computed"] is True
        assert data["bonus_amount_mm"] == pytest.approx(0.010, abs=1e-6)
        assert data["total_tolerance_mm"] == pytest.approx(0.060, abs=1e-6)

    def test_external_mmc_computes(self):
        r = client.post("/api/gdt/bonus-tolerance", json={
            "req_id": "B-004",
            "fcf": {**_FCF_POSITION_MMC, "modifier": "MMC"},
            "fos": _FOS_EXTERNAL,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["computed"] is True

    def test_rfs_not_computed(self):
        r = client.post("/api/gdt/bonus-tolerance", json={
            "req_id": "B-005",
            "fcf": {**_FCF_POSITION_MMC, "modifier": "NONE"},
            "fos": _FOS_INTERNAL_WITH_ACTUAL,
        })
        data = r.json()
        assert data["computed"] is False

    def test_response_has_stated_tolerance(self):
        r = client.post("/api/gdt/bonus-tolerance", json={
            "req_id": "B-006",
            "fcf": _FCF_POSITION_MMC,
            "fos": _FOS_INTERNAL_WITH_ACTUAL,
        })
        data = r.json()
        assert data["stated_tolerance_mm"] == pytest.approx(0.05)

    def test_disclaimer_present(self):
        r = client.post("/api/gdt/bonus-tolerance", json={
            "req_id": "B-007",
            "fcf": _FCF_POSITION_MMC,
            "fos": _FOS_INTERNAL,
        })
        assert "REFERENCE_ONLY" in r.json()["disclaimer"]

    def test_missing_fos_returns_422(self):
        r = client.post("/api/gdt/bonus-tolerance", json={
            "req_id": "B-008",
            "fcf": _FCF_POSITION_MMC,
        })
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/gdt/virtual-condition
# ---------------------------------------------------------------------------

class TestGdtVirtualCondition:
    def test_internal_mmc_computes(self):
        # Internal MMC: VC = MMC_size − tolerance = 25.000 − 0.05 = 24.950
        r = client.post("/api/gdt/virtual-condition", json={
            "req_id": "V-001",
            "fcf": _FCF_POSITION_MMC,
            "fos": _FOS_INTERNAL,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["computed"] is True
        assert data["virtual_condition_mm"] == pytest.approx(24.950, abs=1e-6)

    def test_external_mmc_computes(self):
        # External MMC: VC = MMC_size + tolerance = 20.000 + 0.05 = 20.050
        r = client.post("/api/gdt/virtual-condition", json={
            "req_id": "V-002",
            "fcf": _FCF_POSITION_MMC,
            "fos": _FOS_EXTERNAL,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["computed"] is True
        assert data["virtual_condition_mm"] == pytest.approx(20.050, abs=1e-6)

    def test_rfs_not_computed(self):
        r = client.post("/api/gdt/virtual-condition", json={
            "req_id": "V-003",
            "fcf": {**_FCF_POSITION_MMC, "modifier": "NONE"},
            "fos": _FOS_INTERNAL,
        })
        data = r.json()
        assert data["computed"] is False

    def test_non_cylindrical_not_computed(self):
        r = client.post("/api/gdt/virtual-condition", json={
            "req_id": "V-004",
            "fcf": _FCF_POSITION_MMC,
            "fos": {
                "fos_id": "FOS-W",
                "kind": "WIDTH",
                "upper_limit_mm": 10.0,
                "lower_limit_mm": 9.98,
            },
        })
        data = r.json()
        assert data["computed"] is False

    def test_description_returned(self):
        r = client.post("/api/gdt/virtual-condition", json={
            "req_id": "V-005",
            "fcf": _FCF_POSITION_MMC,
            "fos": _FOS_INTERNAL,
        })
        data = r.json()
        assert data["description"] is not None
        assert len(data["description"]) > 0

    def test_disclaimer_present(self):
        r = client.post("/api/gdt/virtual-condition", json={
            "req_id": "V-006",
            "fcf": _FCF_POSITION_MMC,
            "fos": _FOS_INTERNAL,
        })
        assert "REFERENCE_ONLY" in r.json()["disclaimer"]

    def test_missing_fos_returns_422(self):
        r = client.post("/api/gdt/virtual-condition", json={
            "req_id": "V-007",
            "fcf": _FCF_POSITION_MMC,
        })
        assert r.status_code == 422

    def test_internal_lmc_computes(self):
        # Internal LMC: VC = LMC_size + tolerance = 25.021 + 0.05 = 25.071
        r = client.post("/api/gdt/virtual-condition", json={
            "req_id": "V-008",
            "fcf": {**_FCF_POSITION_MMC, "modifier": "LMC"},
            "fos": _FOS_INTERNAL,
        })
        data = r.json()
        assert data["computed"] is True
        assert data["virtual_condition_mm"] == pytest.approx(25.071, abs=1e-6)


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------

class TestGdtErrorModel:
    def test_invalid_tolerance_value_400(self):
        r = client.post("/api/gdt/interpret", json={
            "req_id": "E-001",
            "fcf": {**_FCF_POSITION_MMC, "tolerance_value": -1.0},
        })
        assert r.status_code == 400

    def test_missing_req_id_422(self):
        r = client.post("/api/gdt/interpret", json={
            "fcf": _FCF_POSITION_MMC,
        })
        assert r.status_code == 422

    def test_missing_fcf_422(self):
        r = client.post("/api/gdt/validate", json={
            "req_id": "E-003",
        })
        assert r.status_code == 422

    def test_invalid_fos_size_limits_400(self):
        r = client.post("/api/gdt/bonus-tolerance", json={
            "req_id": "E-004",
            "fcf": _FCF_POSITION_MMC,
            "fos": {
                "fos_id": "FOS-BAD",
                "kind": "INTERNAL_CYLINDRICAL",
                "upper_limit_mm": 24.0,
                "lower_limit_mm": 25.0,  # lower > upper → bad
                "actual_size_mm": 24.5,
            },
        })
        assert r.status_code == 400
