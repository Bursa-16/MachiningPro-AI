"""Control plan foundation.

AUTONOMOUS_NONCONFORMANCE_DISPOSITION=NO
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from backend.manufacturing_plan.characteristic import (
    CharacteristicCriticality,
    CharacteristicType,
    ManufacturingCharacteristic,
)
from backend.manufacturing_plan.inspection_library import InspectionMethod, gage_suggestions
from backend.manufacturing_plan.inspection_plan import (
    InspectionFrequencySpec,
    InspectionStage,
    _assign_frequency,
    _assign_stage,
    _pick_method,
)


class ReactionPlan(StrEnum):
    STOP_AND_REVIEW = "STOP_AND_REVIEW"
    SEGREGATE = "SEGREGATE"
    REMEASURE = "REMEASURE"
    ADJUST_PROCESS = "ADJUST_PROCESS"
    ESCALATE = "ESCALATE"
    CUSTOM = "CUSTOM"
    UNKNOWN = "UNKNOWN"


class ControlPlanStatus(StrEnum):
    DRAFT = "DRAFT"
    ENGINEER_REVIEWED = "ENGINEER_REVIEWED"
    APPROVED = "APPROVED"


@dataclass(frozen=True)
class ControlPlanRow:
    row_id: str
    operation_no: str
    operation_name: str
    char_id: str
    char_label: str
    char_type: CharacteristicType
    criticality: CharacteristicCriticality
    specification: str | None
    method: InspectionMethod
    gage_suggestion: str | None
    stage: InspectionStage
    frequency: InspectionFrequencySpec
    reaction_plan: ReactionPlan
    responsibility: str | None
    record_reference: str | None
    notes: str = ""


@dataclass
class ControlPlan:
    plan_id: str
    manufacturing_plan_id: str
    drawing_number: str | None
    revision: str | None
    rows: list[ControlPlanRow] = field(default_factory=list)
    status: ControlPlanStatus = ControlPlanStatus.DRAFT
    disclaimer: str = "REFERENCE_ONLY — advisory control plan; engineer review required"
    AUTONOMOUS_NONCONFORMANCE_DISPOSITION: bool = False


def _assign_reaction(criticality: CharacteristicCriticality) -> ReactionPlan:
    if criticality == CharacteristicCriticality.KEY_CHARACTERISTIC:
        return ReactionPlan.STOP_AND_REVIEW
    if criticality == CharacteristicCriticality.CRITICAL:
        return ReactionPlan.SEGREGATE
    return ReactionPlan.REMEASURE


def _assign_responsibility(criticality: CharacteristicCriticality) -> str:
    if criticality in (CharacteristicCriticality.KEY_CHARACTERISTIC,
                       CharacteristicCriticality.CRITICAL):
        return "QC"
    return "OPERATOR"


def build_control_plan(
    manufacturing_plan_id: str,
    characteristics: list[ManufacturingCharacteristic],
    operation_sheets: list,
    drawing_number: str | None = None,
    revision: str | None = None,
) -> ControlPlan:
    """AUTONOMOUS_NONCONFORMANCE_DISPOSITION=NO."""
    rows: list[ControlPlanRow] = []

    for char in characteristics:
        method = _pick_method(char)
        stage = _assign_stage(char)
        freq = _assign_frequency(char)
        reaction = _assign_reaction(char.criticality)
        responsibility = _assign_responsibility(char.criticality)

        tol_um: float | None = None
        if char.upper_limit is not None and char.lower_limit is not None:
            tol_um = abs(char.upper_limit - char.lower_limit) * 1000
        elif char.nominal_value is not None and char.char_type == CharacteristicType.GDT:
            tol_um = char.nominal_value * 1000

        sugs = gage_suggestions(char.char_type, char.nominal_value, tol_um, char.gdt_characteristic, None)
        gage_note = sugs[0].method.value if sugs else None

        rows.append(ControlPlanRow(
            row_id=str(uuid.uuid4()),
            operation_no="-",
            operation_name="FINAL",
            char_id=char.characteristic_id,
            char_label=char.label,
            char_type=char.char_type,
            criticality=char.criticality,
            specification=char.specification,
            method=method,
            gage_suggestion=gage_note,
            stage=stage,
            frequency=freq,
            reaction_plan=reaction,
            responsibility=responsibility,
            record_reference=None,
        ))

    return ControlPlan(
        plan_id=str(uuid.uuid4()),
        manufacturing_plan_id=manufacturing_plan_id,
        drawing_number=drawing_number,
        revision=revision,
        rows=rows,
        status=ControlPlanStatus.DRAFT,
    )
