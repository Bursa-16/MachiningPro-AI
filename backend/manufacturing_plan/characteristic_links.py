"""Operation ↔ Characteristic and Inspection ↔ Characteristic links."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum

from backend.manufacturing_plan.characteristic import (
    CharacteristicType,
    ManufacturingCharacteristic,
)


class OperationCharacteristicRole(StrEnum):
    CREATES = "CREATES"
    CONTROLS = "CONTROLS"
    CONTRIBUTES = "CONTRIBUTES"
    REFERENCES = "REFERENCES"
    VERIFIES = "VERIFIES"


class InspectionMethodSuitability(StrEnum):
    SUITABLE = "SUITABLE"
    CONDITIONAL = "CONDITIONAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_SUITABLE = "NOT_SUITABLE"


@dataclass(frozen=True)
class OperationCharacteristicLink:
    link_id: str
    step_id: str
    operation_type: str
    char_id: str
    char_type: CharacteristicType
    role: OperationCharacteristicRole
    notes: str = ""


@dataclass(frozen=True)
class InspectionCharacteristicLink:
    link_id: str
    inspection_step_id: str
    char_id: str
    char_type: CharacteristicType
    method: str
    suitability: InspectionMethodSuitability
    covers_char_fully: bool
    notes: str = ""


_OP_ROLE_MAP: dict[str, OperationCharacteristicRole] = {
    "DRILLING": OperationCharacteristicRole.CREATES,
    "REAMING": OperationCharacteristicRole.CONTROLS,
    "BORING": OperationCharacteristicRole.CONTROLS,
    "FINISH_BORING": OperationCharacteristicRole.CONTROLS,
    "MILLING": OperationCharacteristicRole.CREATES,
    "ROUGH_MILLING": OperationCharacteristicRole.CONTRIBUTES,
    "FINISH_MILLING": OperationCharacteristicRole.CONTROLS,
    "ROUGH_TURNING": OperationCharacteristicRole.CONTRIBUTES,
    "FINISH_TURNING": OperationCharacteristicRole.CONTROLS,
    "TURNING": OperationCharacteristicRole.CONTROLS,
    "GRINDING": OperationCharacteristicRole.CONTROLS,
    "HONING": OperationCharacteristicRole.CONTROLS,
    "TAPPING": OperationCharacteristicRole.CREATES,
    "THREADING": OperationCharacteristicRole.CREATES,
    "INSPECTION": OperationCharacteristicRole.VERIFIES,
}


def build_operation_characteristic_links(
    steps: list,
    characteristics: list[ManufacturingCharacteristic],
) -> list[OperationCharacteristicLink]:
    """Build OperationCharacteristicLink list. DETERMINISTIC: same inputs → same links."""
    links: list[OperationCharacteristicLink] = []
    char_by_feature: dict[str, list[ManufacturingCharacteristic]] = {}
    for char in characteristics:
        key = char.feature_id or "_global"
        char_by_feature.setdefault(key, []).append(char)

    for step in steps:
        def _g(obj: object, k: str) -> object:
            return obj.get(k) if isinstance(obj, dict) else getattr(obj, k, None)

        step_id = str(_g(step, "step_id") or str(uuid.uuid4()))
        op_type = _g(step, "operation") or _g(step, "operation_type") or "UNKNOWN"
        if hasattr(op_type, "value"):
            op_type = op_type.value
        op_type = str(op_type).upper()
        is_inspection = bool(_g(step, "is_inspection"))
        feature_id = _g(step, "feature_id")

        role = (
            OperationCharacteristicRole.VERIFIES
            if is_inspection
            else _OP_ROLE_MAP.get(op_type, OperationCharacteristicRole.CONTRIBUTES)
        )

        feature_chars = list(char_by_feature.get(feature_id or "_global", []))
        if feature_id:
            feature_chars = feature_chars + char_by_feature.get("_global", [])

        for char in feature_chars:
            links.append(OperationCharacteristicLink(
                link_id=str(uuid.uuid4()),
                step_id=step_id,
                operation_type=op_type,
                char_id=char.characteristic_id,
                char_type=char.char_type,
                role=role,
            ))

    return links


def build_inspection_characteristic_links(
    inspection_steps: list,
    characteristics: list[ManufacturingCharacteristic],
) -> list[InspectionCharacteristicLink]:
    """Build InspectionCharacteristicLink for each inspection step."""
    from backend.manufacturing_plan.inspection_library import method_suitability

    links: list[InspectionCharacteristicLink] = []
    char_by_feature: dict[str, list[ManufacturingCharacteristic]] = {}
    for char in characteristics:
        key = char.feature_id or "_global"
        char_by_feature.setdefault(key, []).append(char)

    for step in inspection_steps:
        def _g(obj: object, k: str) -> object:
            return obj.get(k) if isinstance(obj, dict) else getattr(obj, k, None)

        step_id = str(_g(step, "step_id") or str(uuid.uuid4()))
        method = str(_g(step, "method") or "UNKNOWN")
        if hasattr(method, "value"):
            method = method.value
        feature_id = _g(step, "feature_id")
        feature_chars = list(char_by_feature.get(feature_id or "_global", []))

        for char in feature_chars:
            tol_um: float | None = None
            if char.upper_limit is not None and char.lower_limit is not None:
                tol_um = abs(char.upper_limit - char.lower_limit) * 1000
            elif char.nominal_value is not None and char.char_type == CharacteristicType.GDT:
                tol_um = char.nominal_value * 1000

            suit = method_suitability(method, char.char_type, tol_um, None)
            covers = suit == InspectionMethodSuitability.SUITABLE

            links.append(InspectionCharacteristicLink(
                link_id=str(uuid.uuid4()),
                inspection_step_id=step_id,
                char_id=char.characteristic_id,
                char_type=char.char_type,
                method=method,
                suitability=suit,
                covers_char_fully=covers,
            ))

    return links

# Aliases for backward compatibility with tests
build_operation_char_links = build_operation_characteristic_links
build_inspection_char_links = build_inspection_characteristic_links
