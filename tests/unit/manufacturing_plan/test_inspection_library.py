"""Tests for inspection method library."""
import pytest
from backend.manufacturing_plan.inspection_library import (
    InspectionMethod,
    INSPECTION_METHOD_LIBRARY,
    method_suitability,
    gage_suggestions,
    GageSuggestion,
)
from backend.manufacturing_plan.characteristic import CharacteristicType
from backend.manufacturing_plan.characteristic_links import InspectionMethodSuitability


class TestInspectionMethodEnum:
    def test_has_20_methods(self):
        assert len(InspectionMethod) == 20

    def test_unknown_present(self):
        assert InspectionMethod.UNKNOWN in InspectionMethod

    def test_cmm_present(self):
        assert InspectionMethod.CMM in InspectionMethod


class TestLibraryDict:
    def test_all_methods_in_library(self):
        for m in InspectionMethod:
            assert m in INSPECTION_METHOD_LIBRARY, f"{m} missing from library"

    def test_cmm_record(self):
        rec = INSPECTION_METHOD_LIBRARY[InspectionMethod.CMM]
        assert rec.resolution_um <= 1.0
        assert "POSITION" in rec.gdt_characteristics

    def test_caliper_range(self):
        rec = INSPECTION_METHOD_LIBRARY[InspectionMethod.CALIPER]
        assert rec.typical_range_mm[1] >= 100

    def test_thread_gauge_measurable(self):
        rec = INSPECTION_METHOD_LIBRARY[InspectionMethod.THREAD_GAUGE]
        assert CharacteristicType.THREAD in rec.measurable_types

    def test_surface_roughness_tester(self):
        rec = INSPECTION_METHOD_LIBRARY[InspectionMethod.SURFACE_ROUGHNESS_TESTER]
        assert CharacteristicType.SURFACE_FINISH in rec.measurable_types


class TestMethodSuitability:
    def test_unknown_returns_insufficient(self):
        result = method_suitability(
            InspectionMethod.UNKNOWN, CharacteristicType.DIMENSION, 50, 10
        )
        assert result == InspectionMethodSuitability.INSUFFICIENT_DATA

    def test_caliper_on_loose_tolerance(self):
        result = method_suitability(
            InspectionMethod.CALIPER, CharacteristicType.DIMENSION, 200, 50
        )
        assert result == InspectionMethodSuitability.SUITABLE

    def test_caliper_on_tight_tolerance_not_suitable(self):
        result = method_suitability(
            InspectionMethod.CALIPER, CharacteristicType.DIMENSION, 5, 10
        )
        assert result == InspectionMethodSuitability.NOT_SUITABLE

    def test_cmm_on_dimension(self):
        result = method_suitability(
            InspectionMethod.CMM, CharacteristicType.DIMENSION, 10, 25
        )
        assert result == InspectionMethodSuitability.SUITABLE

    def test_thread_gauge_on_thread(self):
        result = method_suitability(
            InspectionMethod.THREAD_GAUGE, CharacteristicType.THREAD, None, None
        )
        assert result == InspectionMethodSuitability.SUITABLE

    def test_thread_gauge_on_dimension_not_suitable(self):
        result = method_suitability(
            InspectionMethod.THREAD_GAUGE, CharacteristicType.DIMENSION, 50, 25
        )
        assert result == InspectionMethodSuitability.NOT_SUITABLE

    def test_none_method_returns_insufficient(self):
        result = method_suitability("NONEXISTENT", CharacteristicType.DIMENSION, 50, 10)
        assert result == InspectionMethodSuitability.INSUFFICIENT_DATA


class TestGageSuggestions:
    def test_surface_finish_suggests_roughness_tester(self):
        sugs = gage_suggestions(CharacteristicType.SURFACE_FINISH, None, None, None, None)
        assert len(sugs) >= 1
        assert sugs[0].method == InspectionMethod.SURFACE_ROUGHNESS_TESTER

    def test_thread_suggests_thread_gauge(self):
        sugs = gage_suggestions(CharacteristicType.THREAD, None, None, None, None)
        assert sugs[0].method == InspectionMethod.THREAD_GAUGE

    def test_hardness_suggests_hardness_tester(self):
        sugs = gage_suggestions(CharacteristicType.HARDNESS, None, None, None, None)
        assert sugs[0].method == InspectionMethod.HARDNESS_TESTER

    def test_gdt_position_suggests_cmm(self):
        sugs = gage_suggestions(CharacteristicType.GDT, 25, 10, "POSITION", None)
        methods = [s.method for s in sugs]
        assert InspectionMethod.CMM in methods

    def test_gdt_position_high_volume_includes_functional_gauge(self):
        sugs = gage_suggestions(CharacteristicType.GDT, 25, 10, "POSITION", 200)
        methods = [s.method for s in sugs]
        assert InspectionMethod.FUNCTIONAL_GAUGE in methods

    def test_dimension_loose_tolerance_caliper(self):
        sugs = gage_suggestions(CharacteristicType.DIMENSION, 25, 300, None, None)
        assert sugs[0].method == InspectionMethod.CALIPER

    def test_dimension_medium_tolerance_micrometer(self):
        sugs = gage_suggestions(CharacteristicType.DIMENSION, 25, 100, None, None)
        assert sugs[0].method == InspectionMethod.MICROMETER

    def test_dimension_tight_tolerance_cmm(self):
        sugs = gage_suggestions(CharacteristicType.DIMENSION, 25, 5, None, None)
        assert sugs[0].method == InspectionMethod.CMM

    def test_unknown_tolerance_returns_cmm(self):
        sugs = gage_suggestions(CharacteristicType.DIMENSION, 25, None, None, None)
        assert sugs[0].method == InspectionMethod.CMM
        assert sugs[0].suitability == InspectionMethodSuitability.INSUFFICIENT_DATA

    def test_coating_suggests_visual(self):
        sugs = gage_suggestions(CharacteristicType.COATING, None, None, None, None)
        assert sugs[0].method == InspectionMethod.VISUAL

    def test_returns_list_of_gage_suggestions(self):
        sugs = gage_suggestions(CharacteristicType.DIMENSION, 25, 50, None, None)
        assert all(isinstance(s, GageSuggestion) for s in sugs)
