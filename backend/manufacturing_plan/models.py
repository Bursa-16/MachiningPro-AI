"""Manufacturing plan core domain models.

AUTO_GENERATED_PLAN_MARKED_APPROVED=NO
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from backend.manufacturing_plan.characteristic import ManufacturingCharacteristic
from backend.manufacturing_plan.control_plan import ControlPlan
from backend.manufacturing_plan.inspection_plan import FinalInspectionPlan


class ManufacturingPlanStatus(StrEnum):
    DRAFT = "DRAFT"
    ENGINEER_REVIEWED = "ENGINEER_REVIEWED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class ChangeDriver(StrEnum):
    DRAWING_REVISION = "DRAWING_REVISION"
    CAD_UPDATE = "CAD_UPDATE"
    MATERIAL_CHANGE = "MATERIAL_CHANGE"
    MACHINE_CHANGE = "MACHINE_CHANGE"
    TOOL_CHANGE = "TOOL_CHANGE"
    ROUTE_CHANGE = "ROUTE_CHANGE"
    CALIBRATION_UPDATE = "CALIBRATION_UPDATE"
    ENGINEER_EDIT = "ENGINEER_EDIT"
    OTHER = "OTHER"


@dataclass
class PlanRevisionEntry:
    revision_id: str
    revision_number: int
    change_driver: ChangeDriver
    previous_plan_id: str | None
    new_plan_id: str
    changed_fields: list[str] = field(default_factory=list)
    engineer_note: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class ManufacturingSetup:
    setup_id: str
    setup_number: int
    label: str
    machine_id: str | None
    machine_label: str | None
    orientation_note: str
    datum_references: tuple[str, ...]
    fixturing_note: str
    zero_reference: str
    tool_ids: tuple[str, ...]
    holder_ids: tuple[str, ...]
    operation_ids: tuple[str, ...]
    inspection_char_ids: tuple[str, ...]
    notes: str = ""
    REFERENCE_ONLY: bool = True


@dataclass(frozen=True)
class ManufacturingOperation:
    op_id: str
    op_number: int
    setup_id: str
    feature_id: str | None
    operation_type: str
    machine_id: str | None
    machine_label: str | None
    tool_id: str | None
    holder_id: str | None
    cutting_speed_m_min: float | None
    feed_rate_mm_min: float | None
    rpm: float | None
    ap_mm: float | None
    ae_mm: float | None
    coolant_note: str | None
    target_tolerance: str | None
    surface_finish: str | None
    inspection_note: str | None
    cycle_time_context: Any | None
    capability_context: Any | None
    surface_capability_context: Any | None
    parameter_source: str = "INSUFFICIENT_DATA"
    notes: str = ""
    REFERENCE_ONLY: bool = True


@dataclass(frozen=True)
class ManufacturingPlanTool:
    entry_id: str
    tool_id: str | None
    tool_label: str
    tool_type: str
    holder_id: str | None
    holder_label: str | None
    quantity_required: int
    operation_ids: tuple[str, ...]
    notes: str = ""
    REFERENCE_ONLY: bool = True


@dataclass(frozen=True)
class ManufacturingPlanMachine:
    entry_id: str
    machine_id: str | None
    machine_label: str
    machine_type: str
    setup_ids: tuple[str, ...]
    operation_ids: tuple[str, ...]
    REFERENCE_ONLY: bool = True


@dataclass(frozen=True)
class ManufacturingPlanParameter:
    entry_id: str
    op_id: str
    operation_type: str
    material_iso_group: str | None
    vc_m_min: float | None
    fz_mm: float | None
    ap_mm: float | None
    ae_mm: float | None
    feed_rate_mm_min: float | None
    rpm: float | None
    source: str = "INSUFFICIENT_DATA"
    confidence: str = "INSUFFICIENT_DATA"
    notes: str = ""
    REFERENCE_ONLY: bool = True


@dataclass(frozen=True)
class ProcessFlowNode:
    node_id: str
    node_type: str
    label: str
    setup_id: str | None = None
    op_id: str | None = None
    notes: str = ""


@dataclass
class ProcessFlow:
    flow_id: str
    nodes: list[ProcessFlowNode] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)
    start_node_id: str | None = None
    end_node_id: str | None = None


class CompletenessStatus(StrEnum):
    COMPLETE = "COMPLETE"
    SUBSTANTIALLY_COMPLETE = "SUBSTANTIALLY_COMPLETE"
    PARTIALLY_COMPLETE = "PARTIALLY_COMPLETE"
    INCOMPLETE = "INCOMPLETE"


@dataclass
class PlanCompleteness:
    requirements_coverage: float = 0.0
    feature_coverage: float = 0.0
    operation_coverage: float = 0.0
    machine_assignment_coverage: float = 0.0
    tool_assignment_coverage: float = 0.0
    holder_assignment_coverage: float = 0.0
    parameter_coverage: float = 0.0
    inspection_coverage: float = 0.0
    cycle_time_coverage: float = 0.0
    overall_completeness: float = 0.0
    completeness_status: CompletenessStatus = CompletenessStatus.INCOMPLETE

    def compute(self) -> None:
        dims = [
            self.requirements_coverage,
            self.feature_coverage,
            self.operation_coverage,
            self.machine_assignment_coverage,
            self.tool_assignment_coverage,
            self.parameter_coverage,
            self.inspection_coverage,
        ]
        self.overall_completeness = sum(dims) / len(dims) if dims else 0.0
        if self.overall_completeness >= 0.95:
            self.completeness_status = CompletenessStatus.COMPLETE
        elif self.overall_completeness >= 0.80:
            self.completeness_status = CompletenessStatus.SUBSTANTIALLY_COMPLETE
        elif self.overall_completeness >= 0.50:
            self.completeness_status = CompletenessStatus.PARTIALLY_COMPLETE
        else:
            self.completeness_status = CompletenessStatus.INCOMPLETE


class OpenItemSeverity(StrEnum):
    BLOCKING = "BLOCKING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ADVISORY = "ADVISORY"


class OpenItemCategory(StrEnum):
    UNKNOWN_TOLERANCE = "UNKNOWN_TOLERANCE"
    UNRESOLVED_FEATURE = "UNRESOLVED_FEATURE"
    MISSING_MACHINE = "MISSING_MACHINE"
    MISSING_TOOL = "MISSING_TOOL"
    MISSING_HOLDER = "MISSING_HOLDER"
    MISSING_PARAMETER = "MISSING_PARAMETER"
    MISSING_INSPECTION = "MISSING_INSPECTION"
    UNKNOWN_SETUP_TIME = "UNKNOWN_SETUP_TIME"
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    OTHER = "OTHER"


class OpenItemStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    WAIVED = "WAIVED"


@dataclass
class OpenItem:
    item_id: str
    category: OpenItemCategory
    severity: OpenItemSeverity
    description: str
    related_step_id: str | None = None
    related_char_id: str | None = None
    resolution_hint: str = ""
    status: OpenItemStatus = OpenItemStatus.OPEN
    notes: str = ""


class ReleaseGateStatus(StrEnum):
    READY_FOR_ENGINEERING_REVIEW = "READY_FOR_ENGINEERING_REVIEW"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INCOMPLETE = "INCOMPLETE"
    BLOCKED = "BLOCKED"


class PFMEAHook:
    """Non-invasive hook for future PFMEA integration. PFMEA_GENERATOR_NOT_IMPLEMENTED=True."""

    def __init__(self, feature_id: str, op_id: str, failure_mode_hint: str,
                 control: str, severity_hint: str) -> None:
        self.feature_id = feature_id
        self.op_id = op_id
        self.failure_mode_hint = failure_mode_hint
        self.control = control
        self.severity_hint = severity_hint

    def to_dict(self) -> dict:
        return {
            "feature_id": self.feature_id,
            "op_id": self.op_id,
            "failure_mode_hint": self.failure_mode_hint,
            "control": self.control,
            "severity_hint": self.severity_hint,
            "PFMEA_GENERATOR_NOT_IMPLEMENTED": True,
        }


@dataclass
class NCHandoffPackage:
    op_id: str
    machine_id: str | None
    machine_label: str | None
    tool_id: str | None
    holder_id: str | None
    operation_type: str
    cutting_speed_m_min: float | None
    feed_rate_mm_min: float | None
    rpm: float | None
    ap_mm: float | None
    ae_mm: float | None
    feature_geometry_ref: str | None
    setup_id: str
    datum_reference: str | None
    target_tolerance: str | None
    surface_finish_target: str | None
    coolant_note: str | None
    notes: str = ""
    REFERENCE_ONLY: bool = True
    NC_FILE_EXECUTED: bool = False
    MACHINE_KINEMATICS_SIMULATED: bool = False


@dataclass
class ManufacturingPlan:
    plan_id: str
    source_id: str
    drawing_number: str | None
    revision: str | None
    part_id: str | None
    status: ManufacturingPlanStatus = ManufacturingPlanStatus.DRAFT

    characteristics: list[ManufacturingCharacteristic] = field(default_factory=list)
    setups: list[ManufacturingSetup] = field(default_factory=list)
    operations: list[ManufacturingOperation] = field(default_factory=list)
    tool_list: list[ManufacturingPlanTool] = field(default_factory=list)
    machine_list: list[ManufacturingPlanMachine] = field(default_factory=list)
    parameter_table: list[ManufacturingPlanParameter] = field(default_factory=list)
    inspection_plan: FinalInspectionPlan | None = None
    control_plan: ControlPlan | None = None
    process_flow: ProcessFlow | None = None

    completeness: PlanCompleteness = field(default_factory=PlanCompleteness)
    open_items: list[OpenItem] = field(default_factory=list)
    release_gate: ReleaseGateStatus = ReleaseGateStatus.INCOMPLETE

    pfmea_hooks: list[PFMEAHook] = field(default_factory=list)

    traceability_fingerprint: str | None = None
    drawing_fingerprint: str | None = None
    requirements_fingerprint: str | None = None
    route_fingerprint: str | None = None
    calibration_profile_ids: list[str] = field(default_factory=list)

    generation_warnings: list[str] = field(default_factory=list)
    revision_history: list[PlanRevisionEntry] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    disclaimer: str = (
        "REFERENCE_ONLY — advisory manufacturing plan; engineer review required; "
        "AUTO_GENERATED_PLAN_MARKED_APPROVED=NO"
    )
    AUTO_GENERATED_PLAN_MARKED_APPROVED: bool = False
