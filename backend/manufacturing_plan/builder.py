"""ManufacturingPlanBuilder — route → manufacturing plan conversion.

AUTO_GENERATED_PLAN_MARKED_APPROVED=NO
FABRICATED_CHARACTERISTIC=NO
FABRICATED_PROCESS_PARAMETER=NO
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from backend.manufacturing_plan.characteristic import (
    CharacteristicCriticality,
    ManufacturingCharacteristic,
    extract_characteristics_from_requirement_set,
)
from backend.manufacturing_plan.control_plan import build_control_plan
from backend.manufacturing_plan.inspection_plan import build_final_inspection_plan
from backend.manufacturing_plan.models import (
    CompletenessStatus,
    ManufacturingOperation,
    ManufacturingPlan,
    ManufacturingPlanMachine,
    ManufacturingPlanParameter,
    ManufacturingPlanStatus,
    ManufacturingPlanTool,
    ManufacturingSetup,
    NCHandoffPackage,
    OpenItem,
    OpenItemCategory,
    OpenItemSeverity,
    OpenItemStatus,
    PFMEAHook,
    PlanCompleteness,
    ProcessFlow,
    ProcessFlowNode,
    ReleaseGateStatus,
)


def _fp(data: Any) -> str:
    try:
        s = json.dumps(data, sort_keys=True, default=str)
    except Exception:
        s = str(data)
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def _g(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def build_manufacturing_plan(
    source_id: str,
    optimized_plan: Any,
    req_set: Any,
    drawing_number: str | None = None,
    revision: str | None = None,
    calibration_profile_ids: list[str] | None = None,
) -> ManufacturingPlan:
    """Convert optimized route plan into ManufacturingPlan (always DRAFT).

    AUTO_GENERATED_PLAN_MARKED_APPROVED=NO
    """
    plan_id = str(uuid.uuid4())
    warnings: list[str] = []

    characteristics = extract_characteristics_from_requirement_set(req_set)
    if not characteristics:
        warnings.append("No characteristics extracted — req_set empty or unsupported format")

    raw_steps: list[Any] = list(_g(optimized_plan, "steps") or []) if optimized_plan is not None else []

    setups = _build_setups(raw_steps, warnings)
    operations = _build_operations(raw_steps, setups, warnings)
    tool_list = _build_tool_list(operations)
    machine_list = _build_machine_list(operations, setups)
    parameter_table = _build_parameter_table(operations)

    inspection_plan = build_final_inspection_plan(plan_id, characteristics, {})
    control_plan = build_control_plan(
        plan_id, characteristics,
        [{"op_id": op.op_id, "operation_type": op.operation_type, "op_number": op.op_number}
         for op in operations],
        drawing_number, revision,
    )
    process_flow = _build_process_flow(setups, operations)
    open_items = _collect_open_items(characteristics, operations, inspection_plan)
    completeness = _compute_completeness(characteristics, operations, inspection_plan)
    release_gate = _evaluate_release_gate(completeness, open_items)
    pfmea_hooks = _build_pfmea_hooks(operations, characteristics)

    route_fp = _g(optimized_plan, "traceability_fingerprint") if optimized_plan else None
    req_fp = _fp(req_set) if req_set is not None else None
    plan_fp = _fp(plan_id + (route_fp or "") + (req_fp or ""))

    return ManufacturingPlan(
        plan_id=plan_id,
        source_id=source_id,
        drawing_number=drawing_number,
        revision=revision,
        part_id=None,
        status=ManufacturingPlanStatus.DRAFT,
        characteristics=characteristics,
        setups=setups,
        operations=operations,
        tool_list=tool_list,
        machine_list=machine_list,
        parameter_table=parameter_table,
        inspection_plan=inspection_plan,
        control_plan=control_plan,
        process_flow=process_flow,
        completeness=completeness,
        open_items=open_items,
        release_gate=release_gate,
        pfmea_hooks=pfmea_hooks,
        traceability_fingerprint=plan_fp,
        route_fingerprint=route_fp,
        requirements_fingerprint=req_fp,
        calibration_profile_ids=calibration_profile_ids or [],
        generation_warnings=warnings,
    )


def _build_setups(raw_steps: list, warnings: list) -> list[ManufacturingSetup]:
    seen: dict[int, list] = {}
    for step in raw_steps:
        sn = int(_g(step, "setup_number") or 1)
        seen.setdefault(sn, []).append(step)
    if not seen:
        seen[1] = raw_steps

    setups = []
    for sn, steps in sorted(seen.items()):
        machine_ids = list({_g(s, "machine_id") for s in steps if _g(s, "machine_id")})
        machine_id = machine_ids[0] if machine_ids else None
        machine_labels = list({_g(s, "machine_label") for s in steps if _g(s, "machine_label")})
        machine_label = machine_labels[0] if machine_labels else None
        tool_ids = tuple({
            _g(s, "cutting_tool_id") or _g(s, "tool_id")
            for s in steps
            if _g(s, "cutting_tool_id") or _g(s, "tool_id")
        })
        op_ids = tuple(str(_g(s, "step_id") or str(uuid.uuid4())) for s in steps)
        setups.append(ManufacturingSetup(
            setup_id=str(uuid.uuid4()),
            setup_number=sn,
            label=f"Setup {sn}",
            machine_id=machine_id,
            machine_label=machine_label,
            orientation_note="",
            datum_references=(),
            fixturing_note="",
            zero_reference="",
            tool_ids=tool_ids,
            holder_ids=(),
            operation_ids=op_ids,
            inspection_char_ids=(),
        ))
    return setups


def _build_operations(
    raw_steps: list,
    setups: list[ManufacturingSetup],
    warnings: list,
) -> list[ManufacturingOperation]:
    setup_id_map = {s.setup_number: s.setup_id for s in setups}
    default_setup_id = setups[0].setup_id if setups else str(uuid.uuid4())
    ops = []
    for i, step in enumerate(raw_steps):
        sn = int(_g(step, "setup_number") or 1)
        setup_id = setup_id_map.get(sn, default_setup_id)
        op_type = _g(step, "operation") or _g(step, "operation_type") or "UNKNOWN"
        if hasattr(op_type, "value"):
            op_type = op_type.value
        ops.append(ManufacturingOperation(
            op_id=str(_g(step, "step_id") or str(uuid.uuid4())),
            op_number=(i + 1) * 10,
            setup_id=setup_id,
            feature_id=_g(step, "feature_id"),
            operation_type=str(op_type),
            machine_id=_g(step, "machine_id"),
            machine_label=_g(step, "machine_label"),
            tool_id=_g(step, "cutting_tool_id") or _g(step, "tool_id"),
            holder_id=_g(step, "holder_id"),
            cutting_speed_m_min=_g(step, "cutting_speed_m_min"),
            feed_rate_mm_min=_g(step, "feed_rate_mm_min"),
            rpm=_g(step, "rpm"),
            ap_mm=_g(step, "ap_mm"),
            ae_mm=_g(step, "ae_mm"),
            coolant_note=None,
            target_tolerance=None,
            surface_finish=None,
            inspection_note=None,
            cycle_time_context=_g(step, "cycle_time"),
            capability_context=_g(step, "capability_margin"),
            surface_capability_context=None,
            parameter_source=str(_g(step, "parameter_source") or "INSUFFICIENT_DATA"),
        ))
    return ops


def _build_tool_list(operations: list[ManufacturingOperation]) -> list[ManufacturingPlanTool]:
    tool_ops: dict[str, list[str]] = {}
    for op in operations:
        if op.tool_id:
            tool_ops.setdefault(op.tool_id, []).append(op.op_id)
    return [
        ManufacturingPlanTool(
            entry_id=str(uuid.uuid4()),
            tool_id=tool_id,
            tool_label=tool_id,
            tool_type="UNKNOWN",
            holder_id=None,
            holder_label=None,
            quantity_required=1,
            operation_ids=tuple(op_ids),
        )
        for tool_id, op_ids in tool_ops.items()
    ]


def _build_machine_list(
    operations: list[ManufacturingOperation],
    setups: list[ManufacturingSetup],
) -> list[ManufacturingPlanMachine]:
    data: dict[str, dict] = {}
    for op in operations:
        if op.machine_id:
            if op.machine_id not in data:
                data[op.machine_id] = {
                    "label": op.machine_label or op.machine_id,
                    "setup_ids": set(),
                    "op_ids": [],
                }
            data[op.machine_id]["setup_ids"].add(op.setup_id)
            data[op.machine_id]["op_ids"].append(op.op_id)
    return [
        ManufacturingPlanMachine(
            entry_id=str(uuid.uuid4()),
            machine_id=mid,
            machine_label=d["label"],
            machine_type="UNKNOWN",
            setup_ids=tuple(d["setup_ids"]),
            operation_ids=tuple(d["op_ids"]),
        )
        for mid, d in data.items()
    ]


def _build_parameter_table(
    operations: list[ManufacturingOperation],
) -> list[ManufacturingPlanParameter]:
    entries = []
    for op in operations:
        if any([op.cutting_speed_m_min, op.feed_rate_mm_min, op.rpm]):
            entries.append(ManufacturingPlanParameter(
                entry_id=str(uuid.uuid4()),
                op_id=op.op_id,
                operation_type=op.operation_type,
                material_iso_group=None,
                vc_m_min=op.cutting_speed_m_min,
                fz_mm=None,
                ap_mm=op.ap_mm,
                ae_mm=op.ae_mm,
                feed_rate_mm_min=op.feed_rate_mm_min,
                rpm=op.rpm,
                source=op.parameter_source,
                confidence=op.parameter_source,
            ))
    return entries


def _build_process_flow(
    setups: list[ManufacturingSetup],
    operations: list[ManufacturingOperation],
) -> ProcessFlow:
    nodes: list[ProcessFlowNode] = []
    edges: list[tuple[str, str]] = []

    start = ProcessFlowNode(node_id=str(uuid.uuid4()), node_type="RAW_MATERIAL", label="Raw Material")
    end = ProcessFlowNode(node_id=str(uuid.uuid4()), node_type="OUTPUT", label="Completed Part")
    nodes.append(start)
    prev_id = start.node_id

    for setup in setups:
        sn = ProcessFlowNode(
            node_id=str(uuid.uuid4()), node_type="SETUP",
            label=setup.label, setup_id=setup.setup_id,
        )
        nodes.append(sn)
        edges.append((prev_id, sn.node_id))
        prev_id = sn.node_id

        for op_id in setup.operation_ids:
            op = next((o for o in operations if o.op_id == op_id), None)
            if op:
                ntype = "INSPECTION" if "INSPECT" in op.operation_type.upper() else "OPERATION"
                on = ProcessFlowNode(
                    node_id=str(uuid.uuid4()), node_type=ntype,
                    label=op.operation_type, setup_id=setup.setup_id, op_id=op.op_id,
                )
                nodes.append(on)
                edges.append((prev_id, on.node_id))
                prev_id = on.node_id

    nodes.append(end)
    edges.append((prev_id, end.node_id))

    return ProcessFlow(
        flow_id=str(uuid.uuid4()),
        nodes=nodes,
        edges=edges,
        start_node_id=start.node_id,
        end_node_id=end.node_id,
    )


def _collect_open_items(
    characteristics: list,
    operations: list[ManufacturingOperation],
    inspection_plan: Any,
) -> list[OpenItem]:
    items: list[OpenItem] = []

    for op in operations:
        if "INSPECT" in op.operation_type.upper():
            continue
        if not op.machine_id:
            items.append(OpenItem(
                item_id=str(uuid.uuid4()),
                category=OpenItemCategory.MISSING_MACHINE,
                severity=OpenItemSeverity.REVIEW_REQUIRED,
                description=f"No machine assigned for op {op.op_number} ({op.operation_type})",
                related_step_id=op.op_id,
                resolution_hint="Assign machine from machine catalog",
            ))
        if not op.tool_id:
            items.append(OpenItem(
                item_id=str(uuid.uuid4()),
                category=OpenItemCategory.MISSING_TOOL,
                severity=OpenItemSeverity.REVIEW_REQUIRED,
                description=f"No tool assigned for op {op.op_number} ({op.operation_type})",
                related_step_id=op.op_id,
                resolution_hint="Assign cutting tool from tool catalog",
            ))
        if not op.cutting_speed_m_min and not op.feed_rate_mm_min:
            items.append(OpenItem(
                item_id=str(uuid.uuid4()),
                category=OpenItemCategory.MISSING_PARAMETER,
                severity=OpenItemSeverity.ADVISORY,
                description=f"No cutting parameters for op {op.op_number} ({op.operation_type})",
                related_step_id=op.op_id,
                resolution_hint="Add cutting parameters or use calibration profiles",
            ))

    if inspection_plan:
        char_map = {c.characteristic_id: c for c in characteristics}
        for char_id in (inspection_plan.uninspected_chars or []):
            char = char_map.get(char_id)
            if char and char.criticality in (
                CharacteristicCriticality.CRITICAL,
                CharacteristicCriticality.KEY_CHARACTERISTIC,
            ):
                items.append(OpenItem(
                    item_id=str(uuid.uuid4()),
                    category=OpenItemCategory.MISSING_INSPECTION,
                    severity=OpenItemSeverity.BLOCKING,
                    description=f"CRITICAL/KEY char '{char.label}' has no inspection coverage",
                    related_char_id=char_id,
                    resolution_hint="Assign inspection method and stage",
                ))

    return items


def _compute_completeness(
    characteristics: list,
    operations: list[ManufacturingOperation],
    inspection_plan: Any,
) -> PlanCompleteness:
    pc = PlanCompleteness()
    pc.requirements_coverage = 1.0 if characteristics else 0.0

    machining = [o for o in operations if "INSPECT" not in o.operation_type.upper()]
    total = len(machining)
    if total > 0:
        pc.machine_assignment_coverage = sum(1 for o in machining if o.machine_id) / total
        pc.tool_assignment_coverage = sum(1 for o in machining if o.tool_id) / total
        pc.holder_assignment_coverage = sum(1 for o in machining if o.holder_id) / total
        pc.parameter_coverage = sum(1 for o in machining if o.cutting_speed_m_min) / total
        pc.cycle_time_coverage = sum(1 for o in machining if o.cycle_time_context) / total
        pc.operation_coverage = 1.0
    else:
        pc.operation_coverage = 1.0
        pc.machine_assignment_coverage = 0.0
        pc.tool_assignment_coverage = 0.0
        pc.holder_assignment_coverage = 1.0
        pc.parameter_coverage = 0.0
        pc.cycle_time_coverage = 0.0

    pc.feature_coverage = 1.0 if operations else 0.0
    pc.inspection_coverage = inspection_plan.coverage_rate if inspection_plan else 0.0
    pc.compute()
    return pc


def _evaluate_release_gate(
    completeness: PlanCompleteness,
    open_items: list[OpenItem],
) -> ReleaseGateStatus:
    blocking = [i for i in open_items
                if i.severity == OpenItemSeverity.BLOCKING and i.status == OpenItemStatus.OPEN]
    if blocking:
        return ReleaseGateStatus.BLOCKED
    if completeness.completeness_status == CompletenessStatus.INCOMPLETE:
        return ReleaseGateStatus.INCOMPLETE
    review_needed = [i for i in open_items
                     if i.severity == OpenItemSeverity.REVIEW_REQUIRED and i.status == OpenItemStatus.OPEN]
    if review_needed or completeness.overall_completeness < 0.80:
        return ReleaseGateStatus.REVIEW_REQUIRED
    return ReleaseGateStatus.READY_FOR_ENGINEERING_REVIEW


def _build_pfmea_hooks(
    operations: list[ManufacturingOperation],
    characteristics: list[ManufacturingCharacteristic],
) -> list[PFMEAHook]:
    hooks: list[PFMEAHook] = []
    crit = [c for c in characteristics if c.criticality in (
        CharacteristicCriticality.CRITICAL, CharacteristicCriticality.KEY_CHARACTERISTIC,
    )]
    for op in operations:
        for char in crit:
            if char.feature_id == op.feature_id or char.feature_id is None:
                hooks.append(PFMEAHook(
                    feature_id=op.feature_id or "",
                    op_id=op.op_id,
                    failure_mode_hint=f"Failure to achieve {char.label}",
                    control=f"Inspection: {char.char_type.value}",
                    severity_hint=char.criticality.value,
                ))
    return hooks


def build_nc_handoff_packages(plan: ManufacturingPlan) -> list[NCHandoffPackage]:
    """NC handoff packages. NC_FILE_EXECUTED=NO."""
    return [
        NCHandoffPackage(
            op_id=op.op_id,
            machine_id=op.machine_id,
            machine_label=op.machine_label,
            tool_id=op.tool_id,
            holder_id=op.holder_id,
            operation_type=op.operation_type,
            cutting_speed_m_min=op.cutting_speed_m_min,
            feed_rate_mm_min=op.feed_rate_mm_min,
            rpm=op.rpm,
            ap_mm=op.ap_mm,
            ae_mm=op.ae_mm,
            feature_geometry_ref=op.feature_id,
            setup_id=op.setup_id,
            datum_reference=None,
            target_tolerance=op.target_tolerance,
            surface_finish_target=op.surface_finish,
            coolant_note=op.coolant_note,
            notes=op.notes,
        )
        for op in plan.operations
        if "INSPECT" not in op.operation_type.upper()
    ]
