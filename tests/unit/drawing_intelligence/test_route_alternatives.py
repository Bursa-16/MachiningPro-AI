"""Tests for route_alternatives — EPIC_04E Phase 2."""

import pytest

from backend.drawing_intelligence.route_alternatives import (
    OPERATION_CAPABILITY_EXT,
    OPERATION_TO_MACHINE_TYPES,
    ROUTE_TEMPLATES,
    ExtendedFeatureType,
    RouteTemplate,
    get_templates_for_feature,
)
from backend.domain.enums import MachineType, OperationType


class TestExtendedFeatureType:
    def test_at_least_17_values(self):
        assert len(ExtendedFeatureType) >= 17

    def test_hole_present(self):
        assert ExtendedFeatureType.HOLE == "hole"

    def test_precision_bore_present(self):
        assert ExtendedFeatureType.PRECISION_BORE == "precision_bore"

    def test_turning_diameter_present(self):
        assert ExtendedFeatureType.TURNING_DIAMETER == "turning_diameter"


class TestOperationCapabilityExt:
    def test_drilling_present(self):
        assert OperationType.DRILLING in OPERATION_CAPABILITY_EXT

    def test_all_capability_records_have_ra(self):
        for op, cap in OPERATION_CAPABILITY_EXT.items():
            assert cap.achievable_ra_um is not None, f"{op} missing Ra"

    def test_boring_better_ra_than_drilling(self):
        drill_ra = OPERATION_CAPABILITY_EXT[OperationType.DRILLING].achievable_ra_um
        bore_ra = OPERATION_CAPABILITY_EXT[OperationType.BORING].achievable_ra_um
        assert bore_ra < drill_ra


class TestOperationToMachineTypes:
    def test_drilling_maps_to_machining_center(self):
        machine_types = OPERATION_TO_MACHINE_TYPES[OperationType.DRILLING]
        # Values are MachineType enum members
        mt_values = [str(mt) for mt in machine_types]
        assert any("vmc" in mt.lower() or "hmc" in mt.lower() or "drill" in mt.lower()
                   for mt in mt_values), f"Got {mt_values}"

    def test_turning_maps_to_lathe(self):
        machine_types = OPERATION_TO_MACHINE_TYPES.get(OperationType.TURNING, ())
        assert len(machine_types) >= 1


class TestRouteTemplates:
    def test_hole_templates_exist(self):
        templates = ROUTE_TEMPLATES.get(ExtendedFeatureType.HOLE, [])
        assert len(templates) >= 3

    def test_all_templates_have_operations(self):
        for ft, templates in ROUTE_TEMPLATES.items():
            for t in templates:
                assert len(t.operations) >= 1, f"{ft}/{t.template_id} has no operations"

    def test_all_templates_have_best_ra(self):
        for ft, templates in ROUTE_TEMPLATES.items():
            for t in templates:
                assert t.best_ra_um > 0, f"{ft}/{t.template_id} best_ra_um <= 0"

    def test_best_ra_decreases_with_more_operations(self):
        hole_templates = sorted(
            ROUTE_TEMPLATES[ExtendedFeatureType.HOLE],
            key=lambda t: len(t.operations),
        )
        if len(hole_templates) >= 2:
            simple = hole_templates[0]
            complex_ = hole_templates[-1]
            assert complex_.best_ra_um <= simple.best_ra_um

    def test_all_templates_have_machine_types(self):
        for ft, templates in ROUTE_TEMPLATES.items():
            for t in templates:
                assert len(t.requires_machine_types) >= 1, (
                    f"{ft}/{t.template_id} has no machine types"
                )

    def test_gdt_capable_templates_exist(self):
        gdt_capable = any(
            t.gdt_capable
            for templates in ROUTE_TEMPLATES.values()
            for t in templates
        )
        assert gdt_capable


class TestGetTemplatesForFeature:
    def test_returns_hole_templates(self):
        templates = get_templates_for_feature("HOLE")
        assert len(templates) >= 1

    def test_filters_by_ra(self):
        # Ra 0.4 µm — only precision routes should pass
        templates = get_templates_for_feature("HOLE", required_ra_um=0.4)
        for t in templates:
            assert t.best_ra_um <= 0.4, (
                f"{t.template_id} best_ra {t.best_ra_um} > required 0.4"
            )

    def test_loose_ra_returns_more_templates(self):
        loose = get_templates_for_feature("HOLE", required_ra_um=6.3)
        tight = get_templates_for_feature("HOLE", required_ra_um=0.2)
        assert len(loose) >= len(tight)

    def test_unknown_feature_returns_empty(self):
        result = get_templates_for_feature("NONEXISTENT_FEATURE_XYZ")
        assert result == []

    def test_legacy_map_hole_type(self):
        # "hole" string maps via legacy map
        templates = get_templates_for_feature("hole")
        assert len(templates) >= 1

    def test_pocket_templates(self):
        templates = get_templates_for_feature("POCKET")
        assert len(templates) >= 2

    def test_turning_diameter_templates(self):
        templates = get_templates_for_feature("TURNING_DIAMETER")
        assert len(templates) >= 1


class TestRouteTemplate:
    def test_specialty_op_count_for_honing(self):
        hone_templates = [
            t
            for templates in ROUTE_TEMPLATES.values()
            for t in templates
            if any(
                op.operation_type == OperationType.HONING
                for op in t.operations
            )
        ]
        for t in hone_templates:
            assert t.specialty_op_count >= 1

    def test_template_ids_unique_within_feature_type(self):
        for ft, templates in ROUTE_TEMPLATES.items():
            ids = [t.template_id for t in templates]
            assert len(ids) == len(set(ids)), f"Duplicate IDs in {ft}: {ids}"

    def test_total_templates_at_least_30(self):
        total = sum(len(ts) for ts in ROUTE_TEMPLATES.values())
        assert total >= 30
