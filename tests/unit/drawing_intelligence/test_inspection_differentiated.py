"""Tests for differentiated inspection methods (EPIC_04B Phase 2)."""

import pytest
from decimal import Decimal

from backend.drawing_intelligence.inspection_foundation import (
    InspectionMethod,
    InspectionPlanner,
    InspectionTrigger,
    build_inspection_plan,
)
from backend.drawing_intelligence.requirements import (
    DatumReference,
    DatumReferenceFrame,
    DrawingRequirementSet,
    ExpandedFeatureControlFrame,
    GeometricRequirement,
    GdtCharacteristic,
    GdtModifier,
    RequirementExtractionStatus,
)


def _drf(label="A"):
    return DatumReferenceFrame(
        primary=DatumReference(label=label, precedence=1, modifier=GdtModifier.NONE),
        secondary=None, tertiary=None,
    )


def _fcf(char, tol="0.1", modifier=GdtModifier.NONE, datum=None):
    return ExpandedFeatureControlFrame(
        characteristic=char, tolerance_value=Decimal(tol),
        tolerance_unit="mm", diameter_zone=True,
        modifier=modifier, datum_frame=datum,
    )


def _geom(req_id, char, tol="0.1", modifier=GdtModifier.NONE, datum=None):
    return GeometricRequirement(
        req_id=req_id, feature_ref="F-001",
        fcf=_fcf(char, tol, modifier, datum),
    )


def _req_set(*geom_reqs):
    return DrawingRequirementSet(
        source_id="SRC-001", drawing_number="DWG-001", revision="A",
        extraction_status=RequirementExtractionStatus.COMPLETE,
        dimensional=(), geometric=tuple(geom_reqs), surface_finish=(), threads=(),
        material=None, heat_treatment=(),
    )


class TestDifferentiatedInspectionMethods:
    """INS-R-001 no longer maps everything to CMM — uses differentiated methods."""

    def test_circularity_uses_roundness_tester(self):
        plan = build_inspection_plan(_req_set(_geom("R1", GdtCharacteristic.CIRCULARITY)))
        step = next(s for s in plan.steps if s.requirement_ref == "R1")
        assert step.method == InspectionMethod.ROUNDNESS_TESTER

    def test_cylindricity_uses_cmm(self):
        plan = build_inspection_plan(_req_set(_geom("R2", GdtCharacteristic.CYLINDRICITY)))
        step = next(s for s in plan.steps if s.requirement_ref == "R2")
        assert step.method == InspectionMethod.CMM

    def test_circular_runout_uses_dial_indicator(self):
        plan = build_inspection_plan(_req_set(
            _geom("R3", GdtCharacteristic.CIRCULAR_RUNOUT, datum=_drf("A"))
        ))
        step = next(s for s in plan.steps if s.requirement_ref == "R3")
        assert step.method == InspectionMethod.DIAL_INDICATOR_V_BLOCK

    def test_total_runout_uses_dial_indicator(self):
        plan = build_inspection_plan(_req_set(
            _geom("R4", GdtCharacteristic.TOTAL_RUNOUT, datum=_drf("A"))
        ))
        step = next(s for s in plan.steps if s.requirement_ref == "R4")
        assert step.method == InspectionMethod.DIAL_INDICATOR_V_BLOCK

    def test_profile_of_surface_uses_contour_scan(self):
        plan = build_inspection_plan(_req_set(
            _geom("R5", GdtCharacteristic.PROFILE_OF_A_SURFACE, datum=_drf("A"))
        ))
        step = next(s for s in plan.steps if s.requirement_ref == "R5")
        assert step.method == InspectionMethod.CMM_CONTOUR_SCAN

    def test_profile_of_line_uses_contour_scan(self):
        plan = build_inspection_plan(_req_set(
            _geom("R6", GdtCharacteristic.PROFILE_OF_A_LINE, datum=_drf("A"))
        ))
        step = next(s for s in plan.steps if s.requirement_ref == "R6")
        assert step.method == InspectionMethod.CMM_CONTOUR_SCAN

    def test_position_uses_cmm(self):
        plan = build_inspection_plan(_req_set(
            _geom("R7", GdtCharacteristic.POSITION, datum=_drf("A"))
        ))
        step = next(s for s in plan.steps if s.requirement_ref == "R7")
        assert step.method == InspectionMethod.CMM

    def test_perpendicularity_uses_cmm(self):
        plan = build_inspection_plan(_req_set(
            _geom("R8", GdtCharacteristic.PERPENDICULARITY, datum=_drf("A"))
        ))
        step = next(s for s in plan.steps if s.requirement_ref == "R8")
        assert step.method == InspectionMethod.CMM

    def test_flatness_uses_cmm(self):
        plan = build_inspection_plan(_req_set(_geom("R9", GdtCharacteristic.FLATNESS)))
        step = next(s for s in plan.steps if s.requirement_ref == "R9")
        assert step.method == InspectionMethod.CMM


class TestMmcModifierAddsPreInspection:
    """INS-R-008: MMC/LMC modifier → additional size inspection step."""

    def test_mmc_adds_size_measurement_step(self):
        plan = build_inspection_plan(_req_set(
            _geom("R10", GdtCharacteristic.POSITION, tol="0.1",
                  modifier=GdtModifier.MMC, datum=_drf("A"))
        ))
        methods = [s.method for s in plan.steps]
        assert InspectionMethod.SIZE_MEASUREMENT in methods

    def test_lmc_adds_size_measurement_step(self):
        plan = build_inspection_plan(_req_set(
            _geom("R11", GdtCharacteristic.POSITION, tol="0.1",
                  modifier=GdtModifier.LMC, datum=_drf("A"))
        ))
        methods = [s.method for s in plan.steps]
        assert InspectionMethod.SIZE_MEASUREMENT in methods

    def test_rfs_no_extra_size_step(self):
        plan = build_inspection_plan(_req_set(
            _geom("R12", GdtCharacteristic.POSITION, tol="0.1",
                  modifier=GdtModifier.NONE, datum=_drf("A"))
        ))
        methods = [s.method for s in plan.steps]
        assert InspectionMethod.SIZE_MEASUREMENT not in methods

    def test_mmc_size_step_rationale_mentions_modifier(self):
        plan = build_inspection_plan(_req_set(
            _geom("R13", GdtCharacteristic.POSITION, tol="0.1",
                  modifier=GdtModifier.MMC, datum=_drf("A"))
        ))
        size_step = next(s for s in plan.steps if s.method == InspectionMethod.SIZE_MEASUREMENT)
        assert "MMC" in size_step.rationale


class TestInspectionTriggers:
    def test_gdt_step_has_gdt_trigger(self):
        plan = build_inspection_plan(_req_set(_geom("R1", GdtCharacteristic.FLATNESS)))
        gdt_steps = [s for s in plan.steps if s.trigger == InspectionTrigger.GDT_REQUIREMENT]
        assert len(gdt_steps) >= 1


class TestInspectionHasCmmProperty:
    def test_position_plan_has_cmm(self):
        plan = build_inspection_plan(_req_set(
            _geom("R1", GdtCharacteristic.POSITION, datum=_drf("A"))
        ))
        assert plan.has_cmm is True

    def test_only_circularity_has_no_cmm(self):
        plan = build_inspection_plan(_req_set(_geom("R1", GdtCharacteristic.CIRCULARITY)))
        assert plan.has_cmm is False
