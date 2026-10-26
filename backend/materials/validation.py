"""Validation rules for material catalog records (EPIC_01).

FABRICATED_MATERIAL_PROPERTY=NO
MISSING_VALUE_AS_ZERO=NO
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    code: str
    message: str


def validate_material_record(raw: dict) -> list[ValidationIssue]:
    """Validate a raw material record dict. Returns list of issues (empty = valid)."""
    issues: list[ValidationIssue] = []

    def _err(field: str, code: str, msg: str) -> None:
        issues.append(ValidationIssue(field=field, code=code, message=msg))

    # Required identity fields
    for field in ("material_id", "designation", "iso_group", "iso_subgroup", "material_family"):
        if not raw.get(field):
            _err(field, "REQUIRED_FIELD_MISSING", f"{field} is required and must be non-empty")

    # ISO group must be P/M/K/N/S/H
    iso_group = raw.get("iso_group", "")
    if iso_group and iso_group not in ("P", "M", "K", "N", "S", "H"):
        _err("iso_group", "INVALID_ISO_GROUP", f"iso_group must be P/M/K/N/S/H; got {iso_group!r}")

    # S group must not be left as UNSPECIFIED subgroup — must differentiate Ti vs Ni
    iso_subgroup = raw.get("iso_subgroup", "")
    if iso_group == "S" and iso_subgroup not in ("S_TITANIUM", "S_NICKEL_HRSA"):
        _err("iso_subgroup", "S_GROUP_NOT_DIFFERENTIATED",
             "ISO S must use S_TITANIUM or S_NICKEL_HRSA — never leave undifferentiated")

    # No zero-filled optional numeric fields
    for field in ("density_kg_m3", "elastic_modulus_gpa", "thermal_conductivity_w_mk"):
        val = raw.get(field)
        if val == 0.0 or val == 0:
            _err(field, "ZERO_FOR_MISSING", f"{field}=0 is not allowed — use None for unknown values")

    # Conditions validation
    for idx, cond in enumerate(raw.get("conditions", [])):
        if not cond.get("condition_code"):
            _err(f"conditions[{idx}].condition_code", "REQUIRED_FIELD_MISSING", "condition_code required")
        for hv in cond.get("hardness", []):
            if hv.get("scale") not in ("HB", "HRC", "HRB", "HV"):
                _err(f"conditions[{idx}].hardness.scale", "INVALID_HARDNESS_SCALE",
                     f"Hardness scale must be HB/HRC/HRB/HV; got {hv.get('scale')!r}")
            if hv.get("value_min", 0) <= 0 or hv.get("value_max", 0) <= 0:
                _err(f"conditions[{idx}].hardness.value", "NON_POSITIVE_HARDNESS",
                     "Hardness values must be positive")
            if hv.get("value_min", 0) > hv.get("value_max", 0):
                _err(f"conditions[{idx}].hardness.range", "HARDNESS_RANGE_INVERTED",
                     "value_min must not exceed value_max")

    # Cutting references: non-zero, non-negative speeds
    for idx, cut in enumerate(raw.get("cutting_references", [])):
        for field in ("vc_min_m_min", "vc_max_m_min"):
            val = cut.get(field)
            if val is not None and val <= 0:
                _err(f"cutting_references[{idx}].{field}", "NON_POSITIVE_VC",
                     f"{field} must be positive when provided")

    return issues


def validate_no_fabrication(raw: dict) -> list[ValidationIssue]:
    """Check that no obviously fabricated values are present.

    Fabrication heuristics:
    - Tensile strength > 3500 MPa (no known machineable material exceeds this)
    - Density outside 1500–22000 kg/m3
    """
    issues: list[ValidationIssue] = []

    for cond in raw.get("conditions", []):
        ts = cond.get("tensile_strength_mpa")
        if ts is not None and ts > 3500:
            issues.append(ValidationIssue(
                field="tensile_strength_mpa",
                code="IMPLAUSIBLE_VALUE",
                message=f"tensile_strength_mpa={ts} exceeds 3500 MPa — likely fabricated",
            ))

    density = raw.get("density_kg_m3")
    if density is not None and not (1500 <= density <= 22000):
        issues.append(ValidationIssue(
            field="density_kg_m3",
            code="IMPLAUSIBLE_VALUE",
            message=f"density_kg_m3={density} is outside 1500–22000 kg/m3",
        ))

    return issues
