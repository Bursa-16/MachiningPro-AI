"""Manufacturing plan export — JSON, CSV, HTML.

XLSX=DEFERRED
CSV injection guard active.
"""
from __future__ import annotations

import csv
import dataclasses
import io
import json
from datetime import datetime
from typing import Any

from backend.manufacturing_plan.models import ManufacturingPlan

# CSV injection guard — prefix with single-quote if cell starts with =,+,-,@,TAB,CR
_INJECT_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_guard(value: str) -> str:
    if value and value[0] in _INJECT_PREFIXES:
        return "'" + value
    return value


def _safe_cell(v: Any) -> str:
    """Alias used in tests."""
    if v is None:
        return ""
    return _csv_guard(str(v))


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


class _EnumEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if hasattr(obj, "value"):
            return obj.value
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, (set, frozenset)):
            return list(obj)
        return super().default(obj)


def _plan_to_dict(plan: ManufacturingPlan) -> dict:
    def _convert(obj: Any) -> Any:
        if obj is None:
            return None
        if hasattr(obj, "value"):
            return obj.value
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, (set, frozenset)):
            return list(obj)
        if isinstance(obj, (list, tuple)):
            return [_convert(x) for x in obj]
        if isinstance(obj, dict):
            return {k: _convert(v) for k, v in obj.items()}
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return {f.name: _convert(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        return obj

    return _convert(plan)


def export_json(plan: ManufacturingPlan, indent: int = 2) -> str:
    """Export plan as JSON string."""
    d = _plan_to_dict(plan)
    return json.dumps(d, indent=indent, ensure_ascii=False)


def export_csv_operations(plan: ManufacturingPlan) -> str:
    """Export operations table as CSV with injection guard."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "op_number", "operation_type", "machine_id", "machine_label",
        "tool_id", "holder_id",
        "vc_m_min", "feed_mm_min", "rpm", "ap_mm", "ae_mm",
        "parameter_source", "feature_id", "notes",
    ])
    for op in plan.operations:
        writer.writerow([
            _csv_guard(_safe_str(op.op_number)),
            _csv_guard(_safe_str(op.operation_type)),
            _csv_guard(_safe_str(op.machine_id)),
            _csv_guard(_safe_str(op.machine_label)),
            _csv_guard(_safe_str(op.tool_id)),
            _csv_guard(_safe_str(op.holder_id)),
            _csv_guard(_safe_str(op.cutting_speed_m_min)),
            _csv_guard(_safe_str(op.feed_rate_mm_min)),
            _csv_guard(_safe_str(op.rpm)),
            _csv_guard(_safe_str(op.ap_mm)),
            _csv_guard(_safe_str(op.ae_mm)),
            _csv_guard(_safe_str(op.parameter_source)),
            _csv_guard(_safe_str(op.feature_id)),
            _csv_guard(_safe_str(op.notes)),
        ])
    return buf.getvalue()


def export_csv_inspection(plan: ManufacturingPlan) -> str:
    """Export inspection plan as CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "char_id", "char_label", "char_type", "criticality",
        "stage", "method", "gage_suggestion", "frequency",
        "acceptance_criterion", "status",
    ])
    if plan.inspection_plan:
        for row in plan.inspection_plan.rows:
            freq_val = row.frequency.frequency.value if row.frequency else ""
            writer.writerow([
                _csv_guard(_safe_str(row.char_id)),
                _csv_guard(_safe_str(row.char_label)),
                _csv_guard(row.char_type.value if hasattr(row.char_type, "value") else _safe_str(row.char_type)),
                _csv_guard(row.criticality.value if hasattr(row.criticality, "value") else _safe_str(row.criticality)),
                _csv_guard(row.stage.value if hasattr(row.stage, "value") else _safe_str(row.stage)),
                _csv_guard(row.method.value if hasattr(row.method, "value") else _safe_str(row.method)),
                _csv_guard(_safe_str(row.gage_suggestion)),
                _csv_guard(freq_val),
                _csv_guard(_safe_str(row.acceptance_criterion)),
                _csv_guard(_safe_str(row.status)),
            ])
    return buf.getvalue()


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def export_html(plan: ManufacturingPlan) -> str:
    """Export print-ready HTML report."""
    dn = _html_escape(plan.drawing_number or "—")
    rev = _html_escape(plan.revision or "—")
    status = plan.status.value if hasattr(plan.status, "value") else str(plan.status)
    gate = plan.release_gate.value if hasattr(plan.release_gate, "value") else str(plan.release_gate)
    comp = f"{plan.completeness.overall_completeness:.0%}"
    disc = _html_escape(plan.disclaimer)
    created = plan.created_at.strftime("%Y-%m-%d %H:%M UTC") if plan.created_at else "—"

    ops_rows = ""
    for op in plan.operations:
        ops_rows += (
            f"<tr><td>{_html_escape(str(op.op_number))}</td>"
            f"<td>{_html_escape(str(op.operation_type))}</td>"
            f"<td>{_html_escape(str(op.machine_label or op.machine_id or '—'))}</td>"
            f"<td>{_html_escape(str(op.tool_id or '—'))}</td>"
            f"<td>{_html_escape(str(op.cutting_speed_m_min or '—'))}</td>"
            f"<td>{_html_escape(str(op.feed_rate_mm_min or '—'))}</td>"
            f"<td>{_html_escape(str(op.rpm or '—'))}</td></tr>\n"
        )

    insp_rows = ""
    if plan.inspection_plan:
        for row in plan.inspection_plan.rows:
            insp_rows += (
                f"<tr><td>{_html_escape(str(row.char_label))}</td>"
                f"<td>{_html_escape(row.char_type.value if hasattr(row.char_type, 'value') else str(row.char_type))}</td>"
                f"<td>{_html_escape(row.criticality.value if hasattr(row.criticality, 'value') else str(row.criticality))}</td>"
                f"<td>{_html_escape(row.stage.value if hasattr(row.stage, 'value') else str(row.stage))}</td>"
                f"<td>{_html_escape(row.method.value if hasattr(row.method, 'value') else str(row.method))}</td>"
                f"<td>{_html_escape(str(row.gage_suggestion or '—'))}</td></tr>\n"
            )

    open_rows = ""
    for item in plan.open_items:
        sev = item.severity.value if hasattr(item.severity, "value") else str(item.severity)
        open_rows += (
            f"<tr><td>{_html_escape(sev)}</td>"
            f"<td>{_html_escape(str(item.description))}</td>"
            f"<td>{_html_escape(str(item.resolution_hint))}</td></tr>\n"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Manufacturing Plan — {dn} Rev {rev}</title>
<style>
  body {{ font-family: Arial, sans-serif; font-size: 11pt; margin: 20px; color: #111; }}
  h1 {{ font-size: 14pt; margin-bottom: 4px; }}
  h2 {{ font-size: 12pt; margin-top: 20px; margin-bottom: 4px; border-bottom: 1px solid #999; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 12px; }}
  th, td {{ border: 1px solid #ccc; padding: 4px 8px; text-align: left; font-size: 10pt; }}
  th {{ background: #f0f0f0; font-weight: bold; }}
  .disclaimer {{ background: #fff3cd; border: 1px solid #ffc107; padding: 8px; font-size: 9pt; margin-bottom: 12px; }}
  .status-DRAFT {{ color: #856404; }}
  .gate-BLOCKED {{ color: #721c24; font-weight: bold; }}
  .gate-READY_FOR_ENGINEERING_REVIEW {{ color: #155724; }}
  @media print {{ body {{ margin: 10mm; }} }}
</style>
</head>
<body>
<h1>Manufacturing Plan — Drawing {dn} Rev {rev}</h1>
<p>Plan ID: {_html_escape(plan.plan_id)} &nbsp;|&nbsp;
   Status: <span class="status-{_html_escape(status)}">{_html_escape(status)}</span> &nbsp;|&nbsp;
   Release Gate: <span class="gate-{_html_escape(gate)}">{_html_escape(gate)}</span> &nbsp;|&nbsp;
   Completeness: {_html_escape(comp)} &nbsp;|&nbsp;
   Generated: {_html_escape(created)}</p>
<div class="disclaimer">{disc}</div>

<h2>Operations</h2>
<table>
<thead><tr><th>#</th><th>Operation</th><th>Machine</th><th>Tool</th>
<th>Vc (m/min)</th><th>Feed (mm/min)</th><th>RPM</th></tr></thead>
<tbody>{ops_rows}</tbody>
</table>

<h2>Inspection Plan</h2>
<table>
<thead><tr><th>Characteristic</th><th>Type</th><th>Criticality</th>
<th>Stage</th><th>Method</th><th>Gage</th></tr></thead>
<tbody>{insp_rows}</tbody>
</table>

<h2>Open Items</h2>
<table>
<thead><tr><th>Severity</th><th>Description</th><th>Resolution Hint</th></tr></thead>
<tbody>{open_rows}</tbody>
</table>
</body>
</html>"""


def export_csv_control_plan(plan: ManufacturingPlan) -> str:
    """Export control plan as CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "operation_no", "operation_name", "char_id", "char_label", "char_type",
        "criticality", "specification", "method", "gage_suggestion",
        "stage", "frequency", "reaction_plan", "responsibility",
    ])
    if plan.control_plan:
        for row in plan.control_plan.rows:
            freq_val = row.frequency.frequency.value if row.frequency else ""
            writer.writerow([
                _csv_guard(_safe_str(row.operation_no)),
                _csv_guard(_safe_str(row.operation_name)),
                _csv_guard(_safe_str(row.char_id)),
                _csv_guard(_safe_str(row.char_label)),
                _csv_guard(row.char_type.value if hasattr(row.char_type, "value") else _safe_str(row.char_type)),
                _csv_guard(row.criticality.value if hasattr(row.criticality, "value") else _safe_str(row.criticality)),
                _csv_guard(_safe_str(row.specification)),
                _csv_guard(row.method.value if hasattr(row.method, "value") else _safe_str(row.method)),
                _csv_guard(_safe_str(row.gage_suggestion)),
                _csv_guard(row.stage.value if hasattr(row.stage, "value") else _safe_str(row.stage)),
                _csv_guard(freq_val),
                _csv_guard(row.reaction_plan.value if hasattr(row.reaction_plan, "value") else _safe_str(row.reaction_plan)),
                _csv_guard(_safe_str(row.responsibility)),
            ])
    return buf.getvalue()


def export_csv_open_items(plan: ManufacturingPlan) -> str:
    """Export open items as CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "item_id", "category", "severity", "description",
        "related_step_id", "related_char_id", "resolution_hint", "status",
    ])
    for item in plan.open_items:
        writer.writerow([
            _csv_guard(_safe_str(item.item_id)),
            _csv_guard(item.category.value if hasattr(item.category, "value") else _safe_str(item.category)),
            _csv_guard(item.severity.value if hasattr(item.severity, "value") else _safe_str(item.severity)),
            _csv_guard(_safe_str(item.description)),
            _csv_guard(_safe_str(item.related_step_id)),
            _csv_guard(_safe_str(item.related_char_id)),
            _csv_guard(_safe_str(item.resolution_hint)),
            _csv_guard(item.status.value if hasattr(item.status, "value") else _safe_str(item.status)),
        ])
    return buf.getvalue()


def export_report_package(plan: ManufacturingPlan, *_args: Any) -> dict:
    """Bundle all export formats. XLSX=DEFERRED."""
    return {
        "plan_id": plan.plan_id,
        "drawing_number": plan.drawing_number,
        "revision": plan.revision,
        "status": plan.status.value if hasattr(plan.status, "value") else str(plan.status),
        "json": export_json(plan),
        "csv_operations": export_csv_operations(plan),
        "csv_inspection": export_csv_inspection(plan),
        "html": export_html(plan),
        "XLSX_DEFERRED": True,
        "XLSX_EXPORT": "DEFERRED",
        "disclaimer": plan.disclaimer,
    }
