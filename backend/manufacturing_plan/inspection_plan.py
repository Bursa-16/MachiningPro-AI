"""Inspection stage, frequency, and plan models.

FABRICATED_INSPECTION_CAPABILITY=NO
FABRICATED_INSPECTION_FREQUENCY=NO
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


class InspectionStage(StrEnum):
    IN_PROCESS = "IN_PROCESS"
    POST_OPERATION = "POST_OPERATION"
    FIRST_ARTICLE = "FIRST_ARTICLE"
    PATROL = "PATROL"
    FINAL = "FINAL"
    SETUP_APPROVAL = "SETUP_APPROVAL"
    USER_DEFINED = "USER_DEFINED"


class InspectionFrequency(StrEnum):
    ONE_HUNDRED_PERCENT = "ONE_HUNDRED_PERCENT"
    FIRST_OFF = "FIRST_OFF"
    PER_SETUP = "PER_SETUP"
    PER_BATCH = "PER_BATCH"
    SAMPLE = "SAMPLE"
    USER_DEFINED = "USER_DEFINED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class InspectionFrequencySpec:
    frequency: InspectionFrequency
    sample_size: int | None = None
    batch_size: int | None = None
    notes: str = ""


class FAIStatus(StrEnum):
    REQUIRED = "REQUIRED"
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"
    WAIVED = "WAIVED"


@dataclass
class FirstArticleInspection:
    fai_id: str
    plan_id: str
    drawing_number: str | None
    revision: str | None
    char_ids_to_inspect: list[str]
    scope_note: str = "All characteristics from drawing"
    status: FAIStatus = FAIStatus.REQUIRED
    engineer_note: str = ""
    REFERENCE_ONLY: bool = True
    AS9102_COMPLIANCE_CLAIMED: bool = False
    PPAP_COMPLIANCE_CLAIMED: bool = False


@dataclass(frozen=True)
class InspectionPlanRow:
    row_id: str
    char_id: str
    char_label: str
    char_type: CharacteristicType
    criticality: CharacteristicCriticality
    feature_ref: str | None
    op_id: str | None
    inspection_op_id: str | None
    stage: InspectionStage
    method: InspectionMethod
    gage_suggestion: str | None
    frequency: InspectionFrequencySpec
    acceptance_criterion: str | None
    source: str = "LITERATURE_REFERENCE"
    confidence: str = "LITERATURE_REFERENCE"
    status: str = "COVERED"


@dataclass
class FinalInspectionPlan:
    plan_id: str
    manufacturing_plan_id: str
    rows: list[InspectionPlanRow]
    coverage_rate: float = 0.0
    uninspected_chars: list[str] = field(default_factory=list)
    disclaimer: str = "REFERENCE_ONLY — advisory inspection plan; engineer review required"

    def compute_coverage(self, all_char_ids: list[str]) -> None:
        covered = {r.char_id for r in self.rows if r.status != "UNINSPECTED"}
        total = len(all_char_ids)
        self.coverage_rate = len(covered) / total if total > 0 else 1.0
        self.uninspected_chars = [c for c in all_char_ids if c not in covered]


def _assign_stage(char: ManufacturingCharacteristic) -> InspectionStage:
    if char.criticality in (CharacteristicCriticality.KEY_CHARACTERISTIC,
                             CharacteristicCriticality.CRITICAL):
        return InspectionStage.POST_OPERATION
    if char.char_type in (CharacteristicType.THREAD, CharacteristicType.SURFACE_FINISH):
        return InspectionStage.POST_OPERATION
    return InspectionStage.FINAL


def _assign_frequency(char: ManufacturingCharacteristic) -> InspectionFrequencySpec:
    """FABRICATED_INSPECTION_FREQUENCY=NO — no invented sample sizes."""
    if char.criticality in (CharacteristicCriticality.KEY_CHARACTERISTIC,
                             CharacteristicCriticality.CRITICAL):
        return InspectionFrequencySpec(InspectionFrequency.ONE_HUNDRED_PERCENT)
    if char.criticality == CharacteristicCriticality.IMPORTANT:
        return InspectionFrequencySpec(InspectionFrequency.PER_SETUP)
    if char.criticality == CharacteristicCriticality.STANDARD:
        return InspectionFrequencySpec(InspectionFrequency.FIRST_OFF)
    return InspectionFrequencySpec(InspectionFrequency.UNKNOWN)


def _pick_method(char: ManufacturingCharacteristic) -> InspectionMethod:
    tol_um: float | None = None
    if char.upper_limit is not None and char.lower_limit is not None:
        tol_um = abs(char.upper_limit - char.lower_limit) * 1000
    elif char.nominal_value is not None and char.char_type == CharacteristicType.GDT:
        tol_um = char.nominal_value * 1000

    sugs = gage_suggestions(char.char_type, char.nominal_value, tol_um, char.gdt_characteristic, None)
    if sugs:
        return sugs[0].method
    return InspectionMethod.UNKNOWN


def build_final_inspection_plan(
    manufacturing_plan_id: str,
    characteristics: list[ManufacturingCharacteristic],
    operation_id_map: dict[str, str] | None = None,
) -> FinalInspectionPlan:
    """Build FinalInspectionPlan from characteristics.

    FABRICATED_INSPECTION_CAPABILITY=NO — method selection from library only.
    """
    rows: list[InspectionPlanRow] = []

    for char in characteristics:
        method = _pick_method(char)
        stage = _assign_stage(char)
        freq = _assign_frequency(char)
        op_id = (operation_id_map or {}).get(char.characteristic_id)

        tol_um: float | None = None
        if char.upper_limit is not None and char.lower_limit is not None:
            tol_um = abs(char.upper_limit - char.lower_limit) * 1000
        elif char.nominal_value is not None and char.char_type == CharacteristicType.GDT:
            tol_um = char.nominal_value * 1000

        sugs = gage_suggestions(char.char_type, char.nominal_value, tol_um, char.gdt_characteristic, None)
        gage_note = sugs[0].method.value if sugs else None
        status = "COVERED" if method != InspectionMethod.UNKNOWN else "PARTIALLY_COVERED"

        rows.append(InspectionPlanRow(
            row_id=str(uuid.uuid4()),
            char_id=char.characteristic_id,
            char_label=char.label,
            char_type=char.char_type,
            criticality=char.criticality,
            feature_ref=char.feature_id,
            op_id=op_id,
            inspection_op_id=None,
            stage=stage,
            method=method,
            gage_suggestion=gage_note,
            frequency=freq,
            acceptance_criterion=char.specification,
            status=status,
        ))

    plan = FinalInspectionPlan(
        plan_id=str(uuid.uuid4()),
        manufacturing_plan_id=manufacturing_plan_id,
        rows=rows,
    )
    plan.compute_coverage([c.characteristic_id for c in characteristics])
    return plan
