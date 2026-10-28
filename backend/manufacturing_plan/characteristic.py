"""Manufacturing characteristic model — extracted from drawing requirements.

FABRICATED_CHARACTERISTIC=NO
FABRICATED_SAFETY_CRITICALITY=NO
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum


class CharacteristicType(StrEnum):
    DIMENSION = "DIMENSION"
    FIT = "FIT"
    GDT = "GDT"
    SURFACE_FINISH = "SURFACE_FINISH"
    THREAD = "THREAD"
    MATERIAL = "MATERIAL"
    HARDNESS = "HARDNESS"
    COATING = "COATING"
    SPECIAL_NOTE = "SPECIAL_NOTE"


class CharacteristicCriticality(StrEnum):
    STANDARD = "STANDARD"
    IMPORTANT = "IMPORTANT"
    CRITICAL = "CRITICAL"
    KEY_CHARACTERISTIC = "KEY_CHARACTERISTIC"  # engineer-designated only; never auto-assigned
    UNKNOWN = "UNKNOWN"


class CharacteristicReviewStatus(StrEnum):
    PENDING = "PENDING"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"


@dataclass(frozen=True)
class ManufacturingCharacteristic:
    characteristic_id: str
    source_requirement_id: str | None
    feature_id: str | None
    char_type: CharacteristicType
    label: str
    nominal_value: float | None = None
    upper_limit: float | None = None
    lower_limit: float | None = None
    unit: str | None = None
    specification: str | None = None
    gdt_characteristic: str | None = None
    criticality: CharacteristicCriticality = CharacteristicCriticality.UNKNOWN
    source_confidence: str = "EXTRACTED"
    review_status: CharacteristicReviewStatus = CharacteristicReviewStatus.PENDING
    notes: str = ""


def _assign_criticality(
    char_type: CharacteristicType,
    gdt_characteristic: str | None,
    tolerance_um: float | None,
    has_mmc_lmc: bool,
    ra_um: float | None,
) -> CharacteristicCriticality:
    """Deterministic criticality from explicit evidence. FABRICATED_SAFETY_CRITICALITY=NO."""
    if char_type == CharacteristicType.GDT:
        if gdt_characteristic in ("POSITION", "CONCENTRICITY", "TOTAL_RUNOUT"):
            if tolerance_um is not None and tolerance_um < 100:
                return CharacteristicCriticality.CRITICAL
            return CharacteristicCriticality.IMPORTANT
        if gdt_characteristic in (
            "CIRCULAR_RUNOUT", "STRAIGHTNESS", "FLATNESS", "CIRCULARITY",
            "CYLINDRICITY", "PERPENDICULARITY", "ANGULARITY", "PARALLELISM",
            "PROFILE_OF_A_LINE", "PROFILE_OF_A_SURFACE",
        ):
            return CharacteristicCriticality.IMPORTANT
    if has_mmc_lmc:
        return CharacteristicCriticality.CRITICAL
    if char_type == CharacteristicType.FIT:
        return CharacteristicCriticality.CRITICAL
    if char_type == CharacteristicType.SURFACE_FINISH:
        if ra_um is not None and ra_um <= 0.8:
            return CharacteristicCriticality.CRITICAL
        if ra_um is not None and ra_um <= 1.6:
            return CharacteristicCriticality.IMPORTANT
    if char_type == CharacteristicType.THREAD:
        return CharacteristicCriticality.IMPORTANT
    if char_type == CharacteristicType.DIMENSION:
        if tolerance_um is not None and tolerance_um < 25:
            return CharacteristicCriticality.CRITICAL
        if tolerance_um is not None and tolerance_um < 100:
            return CharacteristicCriticality.IMPORTANT
    if char_type in (CharacteristicType.MATERIAL, CharacteristicType.HARDNESS,
                     CharacteristicType.COATING):
        return CharacteristicCriticality.IMPORTANT
    return CharacteristicCriticality.STANDARD


def extract_characteristics_from_requirement_set(req_set: object) -> list[ManufacturingCharacteristic]:
    """Extract characteristics from DrawingRequirementSet (dict or object).

    Accepts the real DrawingRequirementSet object or a flat dict with either the
    real field names (dimensional, surface_finish, threads, geometric) or the
    test/API dict names (dimensional_requirements, surface_finish_requirements,
    thread_requirements, geometric_requirements).

    Returns empty list for None/empty — never raises on missing fields.
    FABRICATED_CHARACTERISTIC=NO
    """
    if req_set is None:
        return []

    def _get(obj: object, key: str, default: object = None) -> object:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _getm(obj: object, *keys: str, default: object = None) -> object:
        """Return first non-None value across candidate key names."""
        for key in keys:
            val = _get(obj, key)
            if val is not None:
                return val
        return default

    chars: list[ManufacturingCharacteristic] = []

    # Dimensional — real: "dimensional", dict: "dimensional_requirements"
    for dim in (_getm(req_set, "dimensional", "dimensional_requirements") or []):
        nom = _getm(dim, "nominal_value", "nominal_mm")
        upper = _getm(dim, "tolerance_upper", "upper_deviation", "upper_deviation_mm")
        lower = _getm(dim, "tolerance_lower", "lower_deviation", "lower_deviation_mm")
        if upper is not None:
            try:
                upper = float(upper)
            except (TypeError, ValueError):
                upper = None
        if lower is not None:
            try:
                lower = float(lower)
            except (TypeError, ValueError):
                lower = None
        if nom is not None:
            try:
                nom = float(nom)
            except (TypeError, ValueError):
                nom = None
        tol_um = abs(upper - lower) * 1000 if upper is not None and lower is not None else None
        crit = _assign_criticality(CharacteristicType.DIMENSION, None, tol_um, False, None)
        req_id = _getm(dim, "req_id", "requirement_id")
        feat_id = _getm(dim, "feature_id", "feature_ref")
        chars.append(ManufacturingCharacteristic(
            characteristic_id=str(uuid.uuid4()),
            source_requirement_id=str(req_id) if req_id is not None else None,
            feature_id=str(feat_id) if feat_id is not None else None,
            char_type=CharacteristicType.DIMENSION,
            label=_get(dim, "label") or f"Dimension {nom}",
            nominal_value=nom,
            upper_limit=upper,
            lower_limit=lower,
            unit=str(_getm(dim, "unit") or "mm"),
            specification=_get(dim, "specification"),
            criticality=crit,
            source_confidence="EXTRACTED",
        ))

    # Geometric (GD&T) — real: "geometric", dict: "geometric_requirements"
    for geo in (_getm(req_set, "geometric", "geometric_requirements") or []):
        # Support both bare characteristic string and nested fcf object
        gdt_char = _getm(geo, "characteristic", "gdt_characteristic")
        if gdt_char is None:
            fcf = _get(geo, "fcf")
            if fcf is not None:
                raw = _get(fcf, "characteristic")
                gdt_char = raw.value if hasattr(raw, "value") else raw
        elif hasattr(gdt_char, "value"):
            gdt_char = gdt_char.value
        tol_val = _getm(geo, "tolerance_value_mm", "tolerance_value")
        if tol_val is not None:
            try:
                tol_val = float(tol_val)
            except (TypeError, ValueError):
                tol_val = None
        tol_um = tol_val * 1000 if tol_val is not None else None
        has_mod = bool(_getm(geo, "modifier", "has_modifier"))
        crit = _assign_criticality(CharacteristicType.GDT, gdt_char, tol_um, has_mod, None)
        req_id = _getm(geo, "req_id", "requirement_id")
        feat_id = _getm(geo, "feature_id", "feature_ref")
        chars.append(ManufacturingCharacteristic(
            characteristic_id=str(uuid.uuid4()),
            source_requirement_id=str(req_id) if req_id is not None else None,
            feature_id=str(feat_id) if feat_id is not None else None,
            char_type=CharacteristicType.GDT,
            label=_get(geo, "label") or f"GD&T {gdt_char}",
            nominal_value=tol_val,
            unit="mm",
            specification=_get(geo, "specification"),
            gdt_characteristic=str(gdt_char) if gdt_char is not None else None,
            criticality=crit,
            source_confidence="EXTRACTED",
        ))

    # Surface finish — real: "surface_finish", dict: "surface_finish_requirements"
    for sf in (_getm(req_set, "surface_finish", "surface_finish_requirements") or []):
        ra = _getm(sf, "ra_um", "ra_max", "ra")
        if ra is not None:
            try:
                ra = float(ra)
            except (TypeError, ValueError):
                ra = None
        crit = _assign_criticality(CharacteristicType.SURFACE_FINISH, None, None, False, ra)
        req_id = _getm(sf, "req_id", "requirement_id")
        feat_id = _getm(sf, "feature_id", "feature_ref")
        chars.append(ManufacturingCharacteristic(
            characteristic_id=str(uuid.uuid4()),
            source_requirement_id=str(req_id) if req_id is not None else None,
            feature_id=str(feat_id) if feat_id is not None else None,
            char_type=CharacteristicType.SURFACE_FINISH,
            label=_get(sf, "label") or f"Ra {ra} µm",
            nominal_value=ra,
            unit="µm",
            specification=_get(sf, "specification"),
            criticality=crit,
            source_confidence="EXTRACTED",
        ))

    # Threads — real: "threads", dict: "thread_requirements"
    for th in (_getm(req_set, "threads", "thread_requirements") or []):
        req_id = _getm(th, "req_id", "requirement_id")
        feat_id = _getm(th, "feature_id", "feature_ref")
        desig = _getm(th, "designation", "thread_standard", "thread_designation")
        chars.append(ManufacturingCharacteristic(
            characteristic_id=str(uuid.uuid4()),
            source_requirement_id=str(req_id) if req_id is not None else None,
            feature_id=str(feat_id) if feat_id is not None else None,
            char_type=CharacteristicType.THREAD,
            label=_get(th, "label") or f"Thread {desig or ''}",
            specification=_get(th, "specification"),
            criticality=CharacteristicCriticality.IMPORTANT,
            source_confidence="EXTRACTED",
        ))

    # Material — real: "material", dict: "material_requirements"
    for mat in (_getm(req_set, "material", "material_requirements") or []):
        req_id = _getm(mat, "req_id", "requirement_id")
        chars.append(ManufacturingCharacteristic(
            characteristic_id=str(uuid.uuid4()),
            source_requirement_id=str(req_id) if req_id is not None else None,
            feature_id=None,
            char_type=CharacteristicType.MATERIAL,
            label=_get(mat, "label") or f"Material {_getm(mat, 'grade', 'material_grade') or ''}",
            specification=_get(mat, "specification"),
            criticality=CharacteristicCriticality.IMPORTANT,
            source_confidence="EXTRACTED",
        ))

    # Heat treatment → HARDNESS — real: "heat_treatment", dict: "heat_treatment_requirements"
    for ht in (_getm(req_set, "heat_treatment", "heat_treatment_requirements") or []):
        req_id = _getm(ht, "req_id", "requirement_id")
        chars.append(ManufacturingCharacteristic(
            characteristic_id=str(uuid.uuid4()),
            source_requirement_id=str(req_id) if req_id is not None else None,
            feature_id=None,
            char_type=CharacteristicType.HARDNESS,
            label=_get(ht, "label") or "Heat Treatment",
            specification=_get(ht, "specification"),
            criticality=CharacteristicCriticality.IMPORTANT,
            source_confidence="EXTRACTED",
        ))

    return chars
