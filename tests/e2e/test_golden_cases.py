"""End-to-end golden dataset tests — Cases A through J.

CUSTOMER_DATA_USED=NO — all test data is synthetic.
AUTO_GENERATED_PLAN_MARKED_APPROVED=NO
"""
import json

from backend.manufacturing_plan.builder import build_manufacturing_plan
from backend.manufacturing_plan.export import export_json
from backend.manufacturing_plan.models import ManufacturingPlanStatus
from backend.manufacturing_plan.validator import ValidationCode, validate_manufacturing_plan


def _build(req_set, drawing_number="GOLDEN"):
    return build_manufacturing_plan(
        source_id="golden-test",
        optimized_plan=None,
        req_set=req_set,
        drawing_number=drawing_number,
        revision="A",
    )


def _assert_base(plan):
    assert plan.status == ManufacturingPlanStatus.DRAFT
    assert plan.AUTO_GENERATED_PLAN_MARKED_APPROVED is False
    assert plan.disclaimer != ""
    assert plan.traceability_fingerprint is not None
    assert plan.inspection_plan is not None


def _assert_exportable(plan):
    j = export_json(plan)
    data = json.loads(j)
    assert data["plan_id"] == plan.plan_id
    assert "C:\\Users" not in j


# ─── Case A: Simple Plate ─────────────────────────────────────────────────────

_CASE_A = {
    "dimensional_requirements": [
        {"requirement_id": "A1", "feature_id": "F1", "nominal_value": 100.0,
         "upper_deviation": 0.1, "lower_deviation": -0.1, "unit": "mm"},
        {"requirement_id": "A2", "feature_id": "F2", "nominal_value": 12.0,
         "upper_deviation": 0.1, "lower_deviation": -0.1, "unit": "mm"},
        {"requirement_id": "A3", "feature_id": "F3", "nominal_value": 12.0,
         "upper_deviation": 0.1, "lower_deviation": -0.1, "unit": "mm"},
    ],
    "surface_finish_requirements": [
        {"requirement_id": "A4", "feature_id": "F1", "ra_max": 3.2},
    ],
}


class TestCaseASimplePlate:
    def setup_method(self):
        self.plan = _build(_CASE_A, "CASE-A")

    def test_status_draft(self):
        _assert_base(self.plan)

    def test_characteristics_extracted(self):
        assert len(self.plan.characteristics) >= 3

    def test_inspection_plan_present(self):
        assert self.plan.inspection_plan is not None

    def test_control_plan_present(self):
        assert self.plan.control_plan is not None

    def test_export_valid(self):
        _assert_exportable(self.plan)


# ─── Case B: Precision Bore ───────────────────────────────────────────────────

_CASE_B = {
    "dimensional_requirements": [
        {"requirement_id": "B1", "feature_id": "BORE", "nominal_value": 25.0,
         "upper_deviation": 0.021, "lower_deviation": 0.0, "unit": "mm"},
    ],
    "geometric_requirements": [
        {"requirement_id": "B2", "feature_id": "BORE",
         "characteristic": "POSITION", "tolerance_value": 0.05,
         "datum_frame": {"primary": {"label": "A", "precedence": 1, "modifier": "NONE"}}},
    ],
    "surface_finish_requirements": [
        {"requirement_id": "B3", "feature_id": "BORE", "ra_max": 0.8},
    ],
}


class TestCaseBPrecisionBore:
    def setup_method(self):
        self.plan = _build(_CASE_B, "CASE-B")

    def test_status_draft(self):
        _assert_base(self.plan)

    def test_characteristics_extracted(self):
        assert len(self.plan.characteristics) >= 2

    def test_inspection_plan_present(self):
        assert self.plan.inspection_plan is not None

    def test_validation_no_v001(self):
        result = validate_manufacturing_plan(self.plan)
        v001 = [f for f in result.findings if f.code == ValidationCode.V001]
        assert len(v001) == 0

    def test_export_valid(self):
        _assert_exportable(self.plan)


# ─── Case C: Hole Pattern + Position ──────────────────────────────────────────

_CASE_C = {
    "dimensional_requirements": [
        {"requirement_id": "C1", "feature_id": f"HOLE{i}", "nominal_value": 8.0,
         "upper_deviation": 0.05, "lower_deviation": -0.05, "unit": "mm"}
        for i in range(1, 5)
    ],
    "geometric_requirements": [
        {"requirement_id": "C5", "feature_id": "HOLE_PATTERN",
         "characteristic": "POSITION", "tolerance_value": 0.2,
         "datum_frame": {"primary": {"label": "A", "precedence": 1, "modifier": "NONE"},
                         "secondary": {"label": "B", "precedence": 2, "modifier": "NONE"},
                         "tertiary": {"label": "C", "precedence": 3, "modifier": "NONE"}}},
    ],
}


class TestCaseCHolePattern:
    def setup_method(self):
        self.plan = _build(_CASE_C, "CASE-C")

    def test_status_draft(self):
        _assert_base(self.plan)

    def test_characteristics_extracted(self):
        assert len(self.plan.characteristics) >= 4

    def test_inspection_plan_present(self):
        assert self.plan.inspection_plan is not None

    def test_no_auto_approval_flag(self):
        assert self.plan.AUTO_GENERATED_PLAN_MARKED_APPROVED is False

    def test_export_valid(self):
        _assert_exportable(self.plan)


# ─── Case D: Pocket + Slot ────────────────────────────────────────────────────

_CASE_D = {
    "dimensional_requirements": [
        {"requirement_id": "D1", "feature_id": "POCKET", "nominal_value": 50.0,
         "upper_deviation": 0.1, "lower_deviation": -0.1, "unit": "mm"},
        {"requirement_id": "D2", "feature_id": "SLOT_W", "nominal_value": 8.0,
         "upper_deviation": 0.05, "lower_deviation": -0.05, "unit": "mm"},
    ],
    "surface_finish_requirements": [
        {"requirement_id": "D3", "feature_id": "POCKET", "ra_max": 1.6},
        {"requirement_id": "D4", "feature_id": "SLOT_W", "ra_max": 0.8},
    ],
}


class TestCaseDPocketSlot:
    def setup_method(self):
        self.plan = _build(_CASE_D, "CASE-D")

    def test_status_draft(self):
        _assert_base(self.plan)

    def test_characteristics_extracted(self):
        assert len(self.plan.characteristics) >= 3

    def test_inspection_plan_present(self):
        assert self.plan.inspection_plan is not None

    def test_control_plan_present(self):
        assert self.plan.control_plan is not None

    def test_export_valid(self):
        _assert_exportable(self.plan)


# ─── Case E: Turned Shaft ─────────────────────────────────────────────────────

_CASE_E = {
    "dimensional_requirements": [
        {"requirement_id": "E1", "feature_id": "OD1", "nominal_value": 40.0,
         "upper_deviation": 0.0, "lower_deviation": -0.018, "unit": "mm"},
        {"requirement_id": "E2", "feature_id": "OD2", "nominal_value": 25.0,
         "upper_deviation": 0.0, "lower_deviation": -0.013, "unit": "mm"},
        {"requirement_id": "E3", "feature_id": "GROOVE", "nominal_value": 3.0,
         "upper_deviation": 0.1, "lower_deviation": -0.1, "unit": "mm"},
    ],
    "surface_finish_requirements": [
        {"requirement_id": "E4", "feature_id": "OD1", "ra_max": 0.4},
        {"requirement_id": "E5", "feature_id": "OD2", "ra_max": 0.8},
    ],
}


class TestCaseETurnedShaft:
    def setup_method(self):
        self.plan = _build(_CASE_E, "CASE-E")

    def test_status_draft(self):
        _assert_base(self.plan)

    def test_characteristics_extracted(self):
        assert len(self.plan.characteristics) >= 4

    def test_critical_surface_finish(self):
        from backend.manufacturing_plan.characteristic import CharacteristicCriticality
        critical = [c for c in self.plan.characteristics
                    if c.criticality == CharacteristicCriticality.CRITICAL]
        assert len(critical) >= 1

    def test_inspection_plan_present(self):
        assert self.plan.inspection_plan is not None

    def test_export_valid(self):
        _assert_exportable(self.plan)


# ─── Case F: Threaded Part ────────────────────────────────────────────────────

_CASE_F = {
    "dimensional_requirements": [
        {"requirement_id": "F1", "feature_id": "PILOT", "nominal_value": 18.5,
         "upper_deviation": 0.05, "lower_deviation": -0.05, "unit": "mm"},
    ],
    "thread_requirements": [
        {"requirement_id": "F2", "feature_id": "THREAD", "thread_standard": "M20x1.5-6H"},
    ],
}


class TestCaseFThreadedPart:
    def setup_method(self):
        self.plan = _build(_CASE_F, "CASE-F")

    def test_status_draft(self):
        _assert_base(self.plan)

    def test_thread_characteristic_extracted(self):
        from backend.manufacturing_plan.characteristic import CharacteristicType
        threads = [c for c in self.plan.characteristics
                   if c.char_type == CharacteristicType.THREAD]
        assert len(threads) >= 1

    def test_inspection_plan_present(self):
        assert self.plan.inspection_plan is not None

    def test_no_auto_approval_flag(self):
        assert self.plan.AUTO_GENERATED_PLAN_MARKED_APPROVED is False

    def test_export_valid(self):
        _assert_exportable(self.plan)


# ─── Case G: Surface-Finish Critical ─────────────────────────────────────────

_CASE_G = {
    "dimensional_requirements": [
        {"requirement_id": "G1", "feature_id": "F1", "nominal_value": 50.0,
         "upper_deviation": 0.2, "lower_deviation": -0.2, "unit": "mm"},
    ],
    "surface_finish_requirements": [
        {"requirement_id": "G2", "feature_id": "F1", "ra_max": 0.4},
        {"requirement_id": "G3", "feature_id": "F2", "ra_max": 0.8},
        {"requirement_id": "G4", "feature_id": "F3", "ra_max": 1.6},
    ],
}


class TestCaseGSurfaceFinish:
    def setup_method(self):
        self.plan = _build(_CASE_G, "CASE-G")

    def test_status_draft(self):
        _assert_base(self.plan)

    def test_critical_surface_finishes(self):
        from backend.manufacturing_plan.characteristic import (
            CharacteristicCriticality,
            CharacteristicType,
        )
        critical_sf = [c for c in self.plan.characteristics
                       if c.char_type == CharacteristicType.SURFACE_FINISH
                       and c.criticality == CharacteristicCriticality.CRITICAL]
        assert len(critical_sf) >= 2

    def test_inspection_plan_present(self):
        assert self.plan.inspection_plan is not None

    def test_control_plan_present(self):
        assert self.plan.control_plan is not None

    def test_export_valid(self):
        _assert_exportable(self.plan)


# ─── Case H: GD&T Heavy ───────────────────────────────────────────────────────

_CASE_H = {
    "geometric_requirements": [
        {"requirement_id": "H1", "feature_id": "FACE",
         "characteristic": "FLATNESS", "tolerance_value": 0.01},
        {"requirement_id": "H2", "feature_id": "OD",
         "characteristic": "PERPENDICULARITY", "tolerance_value": 0.02,
         "datum_frame": {"primary": {"label": "A", "precedence": 1, "modifier": "NONE"}}},
        {"requirement_id": "H3", "feature_id": "OD",
         "characteristic": "CYLINDRICITY", "tolerance_value": 0.005},
        {"requirement_id": "H4", "feature_id": "OD",
         "characteristic": "TOTAL_RUNOUT", "tolerance_value": 0.02,
         "datum_frame": {"primary": {"label": "A", "precedence": 1, "modifier": "NONE"}}},
    ],
}


class TestCaseHGdtHeavy:
    def setup_method(self):
        self.plan = _build(_CASE_H, "CASE-H")

    def test_status_draft(self):
        _assert_base(self.plan)

    def test_gdt_characteristics_extracted(self):
        from backend.manufacturing_plan.characteristic import CharacteristicType
        gdt = [c for c in self.plan.characteristics
               if c.char_type == CharacteristicType.GDT]
        assert len(gdt) >= 3

    def test_inspection_plan_present(self):
        assert self.plan.inspection_plan is not None

    def test_no_auto_approval_flag(self):
        assert self.plan.AUTO_GENERATED_PLAN_MARKED_APPROVED is False

    def test_export_valid(self):
        _assert_exportable(self.plan)


# ─── Case I: Multi-Setup ──────────────────────────────────────────────────────

_CASE_I = {
    "dimensional_requirements": [
        {"requirement_id": "I1", "feature_id": f"F{i}", "nominal_value": 20.0,
         "upper_deviation": 0.05, "lower_deviation": -0.05, "unit": "mm"}
        for i in range(1, 5)
    ],
    "geometric_requirements": [
        {"requirement_id": "I5", "feature_id": "F2",
         "characteristic": "POSITION", "tolerance_value": 0.1,
         "datum_frame": {"primary": {"label": "A", "precedence": 1, "modifier": "NONE"},
                         "secondary": {"label": "B", "precedence": 2, "modifier": "NONE"}}},
    ],
}


class TestCaseIMultiSetup:
    def setup_method(self):
        self.plan = _build(_CASE_I, "CASE-I")

    def test_status_draft(self):
        _assert_base(self.plan)

    def test_characteristics_extracted(self):
        assert len(self.plan.characteristics) >= 4

    def test_inspection_plan_present(self):
        assert self.plan.inspection_plan is not None

    def test_no_auto_approval_flag(self):
        assert self.plan.AUTO_GENERATED_PLAN_MARKED_APPROVED is False

    def test_export_valid(self):
        _assert_exportable(self.plan)


# ─── Case J: Mixed Turning/Milling ────────────────────────────────────────────

_CASE_J = {
    "dimensional_requirements": [
        {"requirement_id": "J1", "feature_id": "OD_MAIN", "nominal_value": 40.0,
         "upper_deviation": 0.0, "lower_deviation": -0.016, "unit": "mm"},
        {"requirement_id": "J2", "feature_id": "POCKET_D", "nominal_value": 30.0,
         "upper_deviation": 0.1, "lower_deviation": -0.1, "unit": "mm"},
        {"requirement_id": "J3", "feature_id": "HOLE", "nominal_value": 8.0,
         "upper_deviation": 0.05, "lower_deviation": -0.05, "unit": "mm"},
    ],
    "thread_requirements": [
        {"requirement_id": "J4", "feature_id": "PORT_THREAD", "thread_standard": "M10x1.5-6H"},
    ],
    "surface_finish_requirements": [
        {"requirement_id": "J5", "feature_id": "OD_MAIN", "ra_max": 0.8},
    ],
}


class TestCaseJMixedTurningMilling:
    def setup_method(self):
        self.plan = _build(_CASE_J, "CASE-J")

    def test_status_draft(self):
        _assert_base(self.plan)

    def test_characteristics_extracted(self):
        assert len(self.plan.characteristics) >= 4

    def test_inspection_plan_present(self):
        assert self.plan.inspection_plan is not None

    def test_control_plan_present(self):
        assert self.plan.control_plan is not None

    def test_export_valid(self):
        _assert_exportable(self.plan)
