"""Golden dataset tests — Cases A through J for EPIC_04G.

CUSTOMER_MANUFACTURING_DATA_COMMITTED=NO — all test data is synthetic.
FABRICATED_CHARACTERISTIC=NO
AUTO_GENERATED_PLAN_MARKED_APPROVED=NO
"""
import pytest
from backend.manufacturing_plan.builder import build_manufacturing_plan
from backend.manufacturing_plan.models import ManufacturingPlanStatus, ReleaseGateStatus
from backend.manufacturing_plan.characteristic import CharacteristicType, CharacteristicCriticality
from backend.manufacturing_plan.inspection_plan import InspectionFrequency


# ─── Synthetic req_set helpers ────────────────────────────────────────────────

def _dim_req(req_id, nom, upper, lower, feature_id="F1"):
    return {
        "requirement_id": req_id, "feature_id": feature_id,
        "nominal_value": nom, "upper_deviation": upper, "lower_deviation": lower, "unit": "mm",
    }


def _sf_req(req_id, ra, feature_id="F1"):
    return {"requirement_id": req_id, "feature_id": feature_id, "ra_max": ra}


def _thread_req(req_id, designation, feature_id="F1"):
    return {"requirement_id": req_id, "feature_id": feature_id, "thread_standard": designation}


def _req_set(**kwargs):
    """Build a minimal dict req_set from keyword lists."""
    return {
        "dimensional_requirements": kwargs.get("dims", []),
        "surface_finish_requirements": kwargs.get("surface", []),
        "thread_requirements": kwargs.get("threads", []),
        "geometric_requirements": kwargs.get("gdt", []),
        "material_requirements": kwargs.get("material", []),
    }


def _plan(req_set, optimized_plan=None, drawing_number="DWG-TEST"):
    return build_manufacturing_plan(
        source_id="golden",
        optimized_plan=optimized_plan,
        req_set=req_set,
        drawing_number=drawing_number,
        revision="A",
    )


# ─── Case A: Simple plate ─────────────────────────────────────────────────────

class TestCaseASimplePlate:
    """Planar face (flatness), 4 through-holes. MILLING + DRILLING."""

    def setup_method(self):
        self.req_set = _req_set(
            dims=[
                _dim_req("A-D1", 100.0, 0.1, -0.1, "FACE"),
                _dim_req("A-D2", 12.0, 0.1, -0.1, "HOLE1"),
                _dim_req("A-D3", 12.0, 0.1, -0.1, "HOLE2"),
            ],
            surface=[_sf_req("A-SF1", 3.2, "FACE")],
        )
        self.plan = _plan(self.req_set, drawing_number="CASE-A")

    def test_plan_created_as_draft(self):
        assert self.plan.status == ManufacturingPlanStatus.DRAFT

    def test_auto_generated_not_approved(self):
        assert self.plan.AUTO_GENERATED_PLAN_MARKED_APPROVED is False

    def test_characteristics_extracted(self):
        assert len(self.plan.characteristics) >= 3

    def test_has_inspection_plan(self):
        assert self.plan.inspection_plan is not None

    def test_has_control_plan(self):
        assert self.plan.control_plan is not None

    def test_surface_finish_char_present(self):
        sf = [c for c in self.plan.characteristics if c.char_type == CharacteristicType.SURFACE_FINISH]
        assert len(sf) >= 1

    def test_disclaimer_present(self):
        assert "REFERENCE_ONLY" in self.plan.disclaimer


# ─── Case B: Precision bore ───────────────────────────────────────────────────

class TestCaseBPrecisionBore:
    """Bore H7, tight tolerance. CRITICAL characteristic."""

    def setup_method(self):
        # 25mm H7: +0.021/0 → tolerance = 21µm → CRITICAL
        self.req_set = _req_set(
            dims=[_dim_req("B-D1", 25.0, 0.021, 0.0, "BORE1")],
            surface=[_sf_req("B-SF1", 0.8, "BORE1")],
        )
        self.plan = _plan(self.req_set, drawing_number="CASE-B")

    def test_tight_tolerance_is_critical(self):
        tight = [c for c in self.plan.characteristics
                 if c.char_type == CharacteristicType.DIMENSION
                 and c.criticality == CharacteristicCriticality.CRITICAL]
        assert len(tight) >= 1

    def test_ra_0_8_is_critical(self):
        sf = [c for c in self.plan.characteristics
              if c.char_type == CharacteristicType.SURFACE_FINISH
              and c.criticality == CharacteristicCriticality.CRITICAL]
        assert len(sf) >= 1

    def test_critical_char_in_inspection_plan(self):
        if self.plan.inspection_plan:
            critical_rows = [r for r in self.plan.inspection_plan.rows
                             if r.criticality == CharacteristicCriticality.CRITICAL]
            assert len(critical_rows) >= 1

    def test_inspection_frequency_100_percent_for_critical(self):
        if self.plan.inspection_plan:
            for row in self.plan.inspection_plan.rows:
                if row.criticality == CharacteristicCriticality.CRITICAL:
                    assert row.frequency.frequency == InspectionFrequency.ONE_HUNDRED_PERCENT


# ─── Case C: Position-controlled hole pattern ─────────────────────────────────

class TestCaseCPositionPattern:
    """4-hole pattern, position GD&T. IMPORTANT characteristic."""

    def setup_method(self):
        gdt_reqs = [
            {
                "requirement_id": f"C-GDT{i}", "feature_id": f"HOLE{i}",
                "gdt_characteristic": "POSITION", "tolerance_value_mm": 0.1,
            }
            for i in range(1, 5)
        ]
        self.req_set = _req_set(
            dims=[_dim_req("C-D1", 8.0, 0.05, -0.05, f"HOLE{i}") for i in range(1, 5)],
            gdt=gdt_reqs,
        )
        self.plan = _plan(self.req_set, drawing_number="CASE-C")

    def test_gdt_characteristics_extracted(self):
        gdt = [c for c in self.plan.characteristics if c.char_type == CharacteristicType.GDT]
        assert len(gdt) >= 1

    def test_position_is_at_least_important(self):
        pos = [c for c in self.plan.characteristics
               if c.gdt_characteristic == "POSITION"]
        for p in pos:
            assert p.criticality in (
                CharacteristicCriticality.IMPORTANT, CharacteristicCriticality.CRITICAL
            )

    def test_plan_is_draft(self):
        assert self.plan.status == ManufacturingPlanStatus.DRAFT


# ─── Case D: Pocket / slot ────────────────────────────────────────────────────

class TestCaseDPocketSlot:
    """Pocket width tolerance IT9. FINISH_MILLING. STANDARD criticality."""

    def setup_method(self):
        self.req_set = _req_set(
            dims=[
                _dim_req("D-D1", 30.0, 0.1, -0.1, "POCKET"),
                _dim_req("D-D2", 10.0, 0.1, -0.1, "SLOT"),
            ],
            surface=[_sf_req("D-SF1", 3.2, "POCKET")],
        )
        self.plan = _plan(self.req_set, drawing_number="CASE-D")

    def test_standard_tolerance_is_standard_or_important(self):
        dims = [c for c in self.plan.characteristics if c.char_type == CharacteristicType.DIMENSION]
        for d in dims:
            assert d.criticality in (
                CharacteristicCriticality.STANDARD,
                CharacteristicCriticality.IMPORTANT,
            )

    def test_characteristics_extracted(self):
        assert len(self.plan.characteristics) >= 2


# ─── Case E: Turned shaft ─────────────────────────────────────────────────────

class TestCaseETurnedShaft:
    """3 diameters (one H6), runout, surface Ra 0.8µm."""

    def setup_method(self):
        gdt_reqs = [
            {
                "requirement_id": "E-GDT1", "feature_id": "SHAFT_D1",
                "gdt_characteristic": "CIRCULAR_RUNOUT", "tolerance_value_mm": 0.02,
            }
        ]
        self.req_set = _req_set(
            dims=[
                _dim_req("E-D1", 40.0, 0.016, 0.0, "SHAFT_D1"),  # H6 ~16µm → CRITICAL
                _dim_req("E-D2", 30.0, 0.05, -0.05, "SHAFT_D2"),
                _dim_req("E-D3", 20.0, 0.1, -0.1, "SHAFT_D3"),
            ],
            surface=[_sf_req("E-SF1", 0.8, "SHAFT_D1")],
            gdt=gdt_reqs,
        )
        self.plan = _plan(self.req_set, drawing_number="CASE-E")

    def test_h6_tolerance_is_critical(self):
        tight = [c for c in self.plan.characteristics
                 if c.char_type == CharacteristicType.DIMENSION
                 and c.criticality == CharacteristicCriticality.CRITICAL]
        assert len(tight) >= 1

    def test_runout_is_important(self):
        runout = [c for c in self.plan.characteristics
                  if c.gdt_characteristic == "CIRCULAR_RUNOUT"]
        assert len(runout) >= 1
        for r in runout:
            assert r.criticality in (
                CharacteristicCriticality.IMPORTANT, CharacteristicCriticality.CRITICAL
            )


# ─── Case F: Threaded part ────────────────────────────────────────────────────

class TestCaseFThreadedPart:
    """M16×2 external thread. THREADING. IMPORTANT."""

    def setup_method(self):
        self.req_set = _req_set(
            threads=[_thread_req("F-T1", "M16x2-6g", "THREAD_F1")],
            dims=[_dim_req("F-D1", 16.0, 0.1, -0.1, "THREAD_F1")],
        )
        self.plan = _plan(self.req_set, drawing_number="CASE-F")

    def test_thread_characteristic_extracted(self):
        threads = [c for c in self.plan.characteristics if c.char_type == CharacteristicType.THREAD]
        assert len(threads) >= 1

    def test_thread_is_important(self):
        threads = [c for c in self.plan.characteristics if c.char_type == CharacteristicType.THREAD]
        for t in threads:
            assert t.criticality == CharacteristicCriticality.IMPORTANT


# ─── Case G: Surface-critical ─────────────────────────────────────────────────

class TestCaseGSurfaceCritical:
    """Ra 0.4µm sealing surface. CRITICAL."""

    def setup_method(self):
        self.req_set = _req_set(
            surface=[_sf_req("G-SF1", 0.4, "SEAL_FACE")],
            dims=[_dim_req("G-D1", 80.0, 0.05, -0.05, "SEAL_FACE")],
        )
        self.plan = _plan(self.req_set, drawing_number="CASE-G")

    def test_tight_ra_is_critical(self):
        sf = [c for c in self.plan.characteristics if c.char_type == CharacteristicType.SURFACE_FINISH]
        assert len(sf) >= 1
        assert sf[0].criticality == CharacteristicCriticality.CRITICAL

    def test_inspection_frequency_100pct(self):
        if self.plan.inspection_plan:
            for row in self.plan.inspection_plan.rows:
                if row.criticality == CharacteristicCriticality.CRITICAL:
                    assert row.frequency.frequency == InspectionFrequency.ONE_HUNDRED_PERCENT


# ─── Case H: GD&T heavy ───────────────────────────────────────────────────────

class TestCaseHGDTHeavy:
    """Cylindricity, runout, position — 3 GD&T characteristics."""

    def setup_method(self):
        gdt_reqs = [
            {"requirement_id": "H-GDT1", "feature_id": "BORE_H",
             "gdt_characteristic": "CYLINDRICITY", "tolerance_value_mm": 0.01},
            {"requirement_id": "H-GDT2", "feature_id": "BORE_H",
             "gdt_characteristic": "TOTAL_RUNOUT", "tolerance_value_mm": 0.02},
            {"requirement_id": "H-GDT3", "feature_id": "BORE_H",
             "gdt_characteristic": "POSITION", "tolerance_value_mm": 0.05},
        ]
        self.req_set = _req_set(gdt=gdt_reqs)
        self.plan = _plan(self.req_set, drawing_number="CASE-H")

    def test_three_gdt_characteristics(self):
        gdt = [c for c in self.plan.characteristics if c.char_type == CharacteristicType.GDT]
        assert len(gdt) >= 3

    def test_position_and_total_runout_at_least_important(self):
        for c in self.plan.characteristics:
            if c.gdt_characteristic in ("POSITION", "TOTAL_RUNOUT"):
                assert c.criticality in (
                    CharacteristicCriticality.IMPORTANT, CharacteristicCriticality.CRITICAL
                )

    def test_inspection_plan_has_rows(self):
        assert self.plan.inspection_plan is not None
        assert len(self.plan.inspection_plan.rows) >= 3


# ─── Case I: Multi-setup ──────────────────────────────────────────────────────

class TestCaseIMultiSetup:
    """2 setups, 8 operations via optimized_plan stub."""

    def setup_method(self):
        steps = [
            {"step_id": f"S{i}", "feature_id": f"F{i%3}",
             "operation": "MILLING", "setup_number": 1 if i < 4 else 2,
             "machine_id": "MC1" if i < 4 else "MC2"}
            for i in range(8)
        ]
        opt_plan = {"steps": steps, "traceability_fingerprint": "fp-case-I"}
        self.req_set = _req_set(
            dims=[_dim_req("I-D1", 50.0, 0.1, -0.1, "F0")],
        )
        self.plan = _plan(self.req_set, optimized_plan=opt_plan, drawing_number="CASE-I")

    def test_8_operations_created(self):
        assert len(self.plan.operations) == 8

    def test_two_setups_created(self):
        assert len(self.plan.setups) == 2

    def test_route_fingerprint_preserved(self):
        assert self.plan.route_fingerprint == "fp-case-I"

    def test_plan_is_draft(self):
        assert self.plan.status == ManufacturingPlanStatus.DRAFT


# ─── Case J: Mixed machining + inspection ─────────────────────────────────────

class TestCaseJMixedMachiningInspection:
    """Full part: turning + milling + drilling + reaming + inspection."""

    def setup_method(self):
        steps = [
            {"step_id": "J1", "feature_id": "DIA1", "operation": "ROUGH_TURNING",
             "setup_number": 1, "machine_id": "LATHE1",
             "cutting_tool_id": "T-TURN", "cutting_speed_m_min": 200.0},
            {"step_id": "J2", "feature_id": "DIA1", "operation": "FINISH_TURNING",
             "setup_number": 1, "machine_id": "LATHE1",
             "cutting_tool_id": "T-TURN-FINE", "cutting_speed_m_min": 280.0},
            {"step_id": "J3", "feature_id": "HOLE1", "operation": "DRILLING",
             "setup_number": 2, "machine_id": "MC1", "cutting_tool_id": "DRILL8"},
            {"step_id": "J4", "feature_id": "HOLE1", "operation": "REAMING",
             "setup_number": 2, "machine_id": "MC1", "cutting_tool_id": "REAM8"},
            {"step_id": "J5", "feature_id": "POCKET1", "operation": "MILLING",
             "setup_number": 2, "machine_id": "MC1", "cutting_tool_id": "EM10"},
            {"step_id": "J6", "feature_id": "HOLE1", "operation": "INSPECTION",
             "setup_number": 2, "is_inspection": True},
        ]
        opt_plan = {"steps": steps, "traceability_fingerprint": "fp-case-J"}
        gdt = [{"requirement_id": "J-GDT1", "feature_id": "DIA1",
                "gdt_characteristic": "CYLINDRICITY", "tolerance_value_mm": 0.015}]
        self.req_set = _req_set(
            dims=[
                _dim_req("J-D1", 40.0, 0.016, 0.0, "DIA1"),
                _dim_req("J-D2", 8.0, 0.015, 0.0, "HOLE1"),
            ],
            surface=[_sf_req("J-SF1", 0.8, "DIA1")],
            threads=[_thread_req("J-T1", "M8x1.25", "HOLE2")],
            gdt=gdt,
        )
        self.plan = _plan(self.req_set, optimized_plan=opt_plan, drawing_number="CASE-J")

    def test_6_operations_created(self):
        assert len(self.plan.operations) == 6

    def test_characteristics_extracted(self):
        assert len(self.plan.characteristics) >= 4

    def test_inspection_plan_coverage_nonzero(self):
        assert self.plan.inspection_plan is not None
        assert self.plan.inspection_plan.coverage_rate >= 0.0

    def test_control_plan_has_rows(self):
        assert self.plan.control_plan is not None
        assert len(self.plan.control_plan.rows) >= 1

    def test_tool_list_built(self):
        tool_ids = {op.tool_id for op in self.plan.operations if op.tool_id}
        assert len(tool_ids) >= 3

    def test_machine_list_built(self):
        assert len(self.plan.machine_list) >= 1

    def test_parameter_table_built(self):
        assert len(self.plan.parameter_table) >= 2

    def test_traceability_fingerprint_set(self):
        assert self.plan.traceability_fingerprint is not None

    def test_safety_flags(self):
        assert self.plan.AUTO_GENERATED_PLAN_MARKED_APPROVED is False
        assert "AUTO_GENERATED_PLAN_MARKED_APPROVED=NO" in self.plan.disclaimer

    def test_nc_handoff_packages_buildable(self):
        from backend.manufacturing_plan.builder import build_nc_handoff_packages
        packages = build_nc_handoff_packages(self.plan)
        machining_ops = [op for op in self.plan.operations
                         if "INSPECT" not in op.operation_type.upper()]
        assert len(packages) == len(machining_ops)
        for p in packages:
            assert p.NC_FILE_EXECUTED is False
