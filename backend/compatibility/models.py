"""Pydantic models for the deterministic compatibility evaluation API.

FALSE_COMPATIBILITY_CLAIM=NO
FALSE_AI_CLAIM=NO
MISSING_LIMIT_AS_ZERO=NO
"""

from __future__ import annotations

from pydantic import BaseModel

VALID_OPERATIONS: frozenset[str] = frozenset({
    "milling", "drilling", "boring", "tapping", "turning", "reaming",
})

VALID_ISO_GROUPS: frozenset[str] = frozenset({"P", "M", "K", "N", "S", "H"})

_DISCLAIMER = (
    "Compatibility is evaluated against publicly available manufacturer catalog data. "
    "Results are REFERENCE_ONLY and carry no production validation. "
    "Validate all combinations through production trials before manufacturing use."
)

# Stable reason-code constants — never change these strings after release.
class RC:
    # PROCESS_SUPPORT
    PROCESS_SUPPORTED = "PROCESS_SUPPORTED"
    MACHINE_PROCESS_NOT_SUPPORTED = "MACHINE_PROCESS_NOT_SUPPORTED"
    TOOL_PROCESS_NOT_SUPPORTED = "TOOL_PROCESS_NOT_SUPPORTED"

    # MACHINE_HOLDER_INTERFACE
    MACHINE_INTERFACE_UNKNOWN = "MACHINE_SPINDLE_INTERFACE_UNKNOWN"
    MACHINE_INTERFACE_MISMATCH = "MACHINE_HOLDER_INTERFACE_MISMATCH"
    MACHINE_INTERFACE_MATCH = "MACHINE_HOLDER_INTERFACE_MATCH"

    # HOLDER_TOOL_SHANK
    SHANK_DIAMETER_UNKNOWN = "TOOL_SHANK_DIAMETER_UNKNOWN"
    HOLDER_CLAMP_RANGE_UNKNOWN = "HOLDER_CLAMP_RANGE_UNKNOWN"
    SHANK_OUT_OF_RANGE = "SHANK_DIAMETER_OUT_OF_CLAMP_RANGE"
    SHANK_IN_RANGE = "SHANK_DIAMETER_IN_CLAMP_RANGE"
    INSERT_SHAPE_UNKNOWN = "TOOL_INSERT_SHAPE_UNKNOWN"
    INSERT_SHAPE_MISMATCH = "INSERT_SHAPE_MISMATCH_FOR_HOLDER"
    INSERT_SHAPE_MATCH = "INSERT_SHAPE_MATCH_FOR_HOLDER"
    BORING_SHANK_MISMATCH = "BORING_BAR_SHANK_MISMATCH"
    BORING_SHANK_MATCH = "BORING_BAR_SHANK_MATCH"
    INTERFACE_UNRESOLVABLE = "HOLDER_TOOL_INTERFACE_MATCH_NOT_DETERMINABLE"

    # ISO_MATERIAL_GROUP
    ISO_NOT_SUPPORTED = "ISO_MATERIAL_GROUP_NOT_IN_TOOL_SPEC"
    ISO_SUPPORTED = "ISO_MATERIAL_GROUP_SUPPORTED"
    ISO_SPEC_UNKNOWN = "TOOL_ISO_GROUPS_UNKNOWN"

    # RPM rules
    RPM_NOT_REQUESTED = "VC_AND_DIAMETER_NOT_PROVIDED"
    MACHINE_RPM_LIMIT_UNKNOWN = "MACHINE_RPM_LIMIT_UNKNOWN"
    HOLDER_RPM_LIMIT_UNKNOWN = "HOLDER_RPM_LIMIT_UNKNOWN"
    TOOL_RPM_LIMIT_UNKNOWN = "TOOL_RPM_LIMIT_UNKNOWN"
    MACHINE_RPM_EXCEEDED = "REQUESTED_RPM_EXCEEDS_MACHINE_MAX"
    HOLDER_RPM_EXCEEDED = "REQUESTED_RPM_EXCEEDS_HOLDER_MAX"
    TOOL_RPM_EXCEEDED = "REQUESTED_RPM_EXCEEDS_TOOL_MAX"
    MACHINE_RPM_OK = "REQUESTED_RPM_WITHIN_MACHINE_LIMIT"
    HOLDER_RPM_OK = "REQUESTED_RPM_WITHIN_HOLDER_LIMIT"
    TOOL_RPM_OK = "REQUESTED_RPM_WITHIN_TOOL_LIMIT"


class CompatibilityRequest(BaseModel):
    """Input for a single deterministic compatibility evaluation."""

    machine_id: str
    holder_id: str
    cutting_tool_id: str
    operation: str             # lower-case operation name
    iso_material_group: str    # P / M / K / N / S / H
    cutting_speed_m_min: float | None = None   # Vc — optional, enables RPM check
    tool_diameter_mm: float | None = None      # D  — optional, enables RPM check


class RuleResult(BaseModel):
    """Result of one mandatory deterministic compatibility rule."""

    rule_id: str
    status: str         # PASS | FAIL | UNKNOWN | NOT_APPLICABLE
    reason_code: str
    detail: str | None = None


class CompatibilityResponse(BaseModel):
    """Full deterministic compatibility evaluation result."""

    overall_status: str    # COMPATIBLE | INCOMPATIBLE | INSUFFICIENT_DATA
    machine_id: str
    holder_id: str
    cutting_tool_id: str
    operation: str
    iso_material_group: str
    rule_results: list[RuleResult]
    hard_failures: list[str]          # rule_ids with FAIL status
    unknown_rules: list[str]          # rule_ids with UNKNOWN status
    missing_fields: list[str]         # catalog fields that were None and mattered
    calculated_rpm: float | None = None
    reference_guidance_available: bool = False
    disclaimer: str = _DISCLAIMER


class SchemaEntry(BaseModel):
    id: str
    display: str


class CompatibilitySchema(BaseModel):
    machines: list[SchemaEntry]
    holders: list[SchemaEntry]
    cutting_tools: list[SchemaEntry]
    valid_operations: list[str]
    valid_iso_groups: list[str]
