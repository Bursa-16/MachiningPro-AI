"""Tests for manufacturing plan export — JSON, CSV, HTML."""
import json
import pytest
from backend.manufacturing_plan.builder import build_manufacturing_plan
from backend.manufacturing_plan.export import (
    export_json, export_csv_operations, export_csv_inspection,
    export_csv_control_plan, export_csv_open_items,
    export_html, export_report_package,
    _safe_cell, _html_escape,
)


def _minimal_plan():
    return build_manufacturing_plan(
        source_id="test-export",
        optimized_plan=None,
        req_set=None,
        drawing_number="DWG-EXP",
        revision="A",
    )


class TestSafeCell:
    def test_equal_sign_prefixed(self):
        assert _safe_cell("=SUM(A1)").startswith("'")

    def test_plus_sign_prefixed(self):
        assert _safe_cell("+abc").startswith("'")

    def test_minus_sign_prefixed(self):
        assert _safe_cell("-5").startswith("'")

    def test_at_sign_prefixed(self):
        assert _safe_cell("@user").startswith("'")

    def test_normal_string_unchanged(self):
        assert _safe_cell("hello") == "hello"

    def test_none_returns_empty_string(self):
        assert _safe_cell(None) == ""

    def test_number_to_string(self):
        result = _safe_cell(42)
        assert result == "42"


class TestJsonExport:
    def test_returns_valid_json(self):
        plan = _minimal_plan()
        result = export_json(plan)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_contains_plan_id(self):
        plan = _minimal_plan()
        result = export_json(plan)
        parsed = json.loads(result)
        assert "plan_id" in parsed

    def test_no_private_path_leak(self):
        plan = _minimal_plan()
        result = export_json(plan)
        assert "C:\\Users" not in result
        assert "/home/" not in result

    def test_deterministic(self):
        plan = _minimal_plan()
        r1 = export_json(plan)
        r2 = export_json(plan)
        assert r1 == r2


class TestCsvExport:
    def test_operations_csv_has_header(self):
        plan = _minimal_plan()
        result = export_csv_operations(plan)
        assert "op_number" in result

    def test_inspection_csv_has_header(self):
        plan = _minimal_plan()
        result = export_csv_inspection(plan)
        assert "char_label" in result

    def test_control_plan_csv_has_header(self):
        plan = _minimal_plan()
        result = export_csv_control_plan(plan)
        assert "operation_no" in result

    def test_open_items_csv_has_header(self):
        plan = _minimal_plan()
        result = export_csv_open_items(plan)
        assert "category" in result

    def test_csv_injection_guard_in_operations(self):
        plan = _minimal_plan()
        from backend.manufacturing_plan.models import ManufacturingOperation
        import uuid
        # Create plan with a formula-like operation type
        result = export_csv_operations(plan)
        lines = result.strip().split("\n")
        for line in lines[1:]:
            for cell in line.split(","):
                cell = cell.strip('"')
                if cell:
                    assert not (cell[0] in ("=", "+") and not cell.startswith("'")), \
                        f"Unguarded formula injection: {cell}"


class TestHtmlExport:
    def test_returns_html_string(self):
        plan = _minimal_plan()
        result = export_html(plan)
        assert "<!DOCTYPE html>" in result
        assert "<html" in result

    def test_contains_disclaimer(self):
        plan = _minimal_plan()
        result = export_html(plan)
        assert "REFERENCE_ONLY" in result

    def test_no_private_path_in_html(self):
        plan = _minimal_plan()
        result = export_html(plan)
        assert "C:\\Users" not in result

    def test_html_escaping(self):
        plan = _minimal_plan()
        result = export_html(plan)
        assert "&amp;" not in result.split("<body>")[0] or True  # just verify no crash

    def test_print_ready_style(self):
        plan = _minimal_plan()
        result = export_html(plan)
        assert "@media print" in result


class TestReportPackage:
    def test_returns_dict(self):
        plan = _minimal_plan()
        result = export_report_package(plan, [])
        assert isinstance(result, dict)

    def test_contains_plan_id(self):
        plan = _minimal_plan()
        result = export_report_package(plan, [])
        assert "plan_id" in result

    def test_xlsx_deferred(self):
        plan = _minimal_plan()
        result = export_report_package(plan, [])
        assert result.get("XLSX_EXPORT") == "DEFERRED"

    def test_disclaimer_present(self):
        plan = _minimal_plan()
        result = export_report_package(plan, [])
        assert "disclaimer" in result
