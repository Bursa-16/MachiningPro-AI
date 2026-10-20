"""Deterministic compatibility engine (MACHINE_TOOL_HOLDER_COMPATIBILITY_ENGINE_01).

Evaluates: MACHINE → TOOL HOLDER → CUTTING TOOL → OPERATION → ISO MATERIAL GROUP

Overall status derivation (three-state precedence):
  1. Any mandatory rule FAIL  → INCOMPATIBLE
  2. No FAIL + any UNKNOWN    → INSUFFICIENT_DATA
  3. All PASS / NOT_APPLICABLE → COMPATIBLE

Hard constraints enforced here:
  RPM_FORMULA_DUPLICATED=NO       — reuses spindle_speed_from_cutting_speed
  CUTTING_PARAMETERS_LIBRARY_DUPLICATED=NO — reuses existing registry
  TOOLLIFE_USED_AS_COMPATIBILITY_PREDICTOR=NO
  POWER_COMPATIBILITY_IMPLEMENTED=NO
  TORQUE_COMPATIBILITY_IMPLEMENTED=NO
  MISSING_LIMIT_AS_ZERO=NO        — absent limits → UNKNOWN, not PASS
  FALSE_COMPATIBILITY_CLAIM=NO
"""

from __future__ import annotations

import logging
import os
from decimal import Decimal

from backend.compatibility.models import (
    RC,
    VALID_ISO_GROUPS,
    VALID_OPERATIONS,
    CompatibilityRequest,
    CompatibilityResponse,
    RuleResult,
    SchemaEntry,
)
from backend.cutting_parameters.models import ApplicabilityScope
from backend.cutting_parameters.registry import CuttingParameterRegistry
from backend.cutting_parameters.seed_reference import seed_reference_registry
from backend.cutting_tools.catalog_models import CuttingToolCatalogRecord
from backend.cutting_tools.seed_catalog import get_catalog as _tool_catalog
from backend.domain.enums import IsoMaterialGroup, OperationType
from backend.domain.units import Quantity, Unit
from backend.machining.exceptions import MachiningMathError
from backend.machining.formulas import spindle_speed_from_cutting_speed
from backend.machines.catalog_models import MachineCatalogRecord
from backend.machines.seed_catalog import seed_machine_catalog
from backend.tool_holders.catalog_models import ToolHolderCatalogRecord
from backend.tool_holders.seed_catalog import get_catalog as _holder_catalog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Catalog registries — built once at module import
# ---------------------------------------------------------------------------

_MACHINES: dict[str, MachineCatalogRecord] = {}
_HOLDERS: dict[str, ToolHolderCatalogRecord] = {}
_TOOLS: dict[str, CuttingToolCatalogRecord] = {}


def _build_catalogs() -> None:
    for raw in seed_machine_catalog():
        r = MachineCatalogRecord(**raw)
        _MACHINES[r.stable_id] = r
    for h in _holder_catalog():
        _HOLDERS[h.stable_id] = h
    for t in _tool_catalog():
        _TOOLS[t.stable_id] = t


_build_catalogs()

# ---------------------------------------------------------------------------
# Cutting parameter registry — same pattern as cutting_parameters API module,
# NOT a duplication of the library (CUTTING_PARAMETERS_LIBRARY_DUPLICATED=NO)
# ---------------------------------------------------------------------------

_cp_registry: CuttingParameterRegistry | None = None
_cp_seeded_path: str | None = None


def _get_cp_registry() -> CuttingParameterRegistry:
    global _cp_registry, _cp_seeded_path
    current_path = os.environ.get("MACHININGPRO_CUTTING_PARAM_REF_PATH")
    if _cp_registry is None or (
        current_path is not None and current_path != _cp_seeded_path
    ):
        reg = CuttingParameterRegistry()
        if current_path:
            from pathlib import Path
            if Path(current_path).is_file():
                try:
                    seed_reference_registry(reg, current_path)
                except Exception as exc:
                    logger.warning("Compatibility: could not seed param registry: %s", exc)
        _cp_registry = reg
        _cp_seeded_path = current_path
    return _cp_registry


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

def get_schema_machines() -> list[SchemaEntry]:
    entries = []
    for m in sorted(_MACHINES.values(), key=lambda x: x.stable_id):
        iface = f" ({m.spindle_interface})" if m.spindle_interface else " (interface unknown)"
        rpm = f", {m.spindle_max_rpm} rpm" if m.spindle_max_rpm else ""
        entries.append(SchemaEntry(
            id=m.stable_id,
            display=f"{m.manufacturer} {m.model}{iface}{rpm}",
        ))
    return entries


def get_schema_holders() -> list[SchemaEntry]:
    entries = []
    for h in sorted(_HOLDERS.values(), key=lambda x: x.stable_id):
        entries.append(SchemaEntry(
            id=h.stable_id,
            display=f"{h.manufacturer} {h.product_name} ({h.machine_interface_key} / {h.tool_interface_key})",
        ))
    return entries


def get_schema_tools() -> list[SchemaEntry]:
    entries = []
    for t in sorted(_TOOLS.values(), key=lambda x: x.stable_id):
        iso = "/".join(t.iso_material_groups) if t.iso_material_groups else "?"
        ops = "/".join(t.supported_operations) if t.supported_operations else "?"
        entries.append(SchemaEntry(
            id=t.stable_id,
            display=f"{t.manufacturer} {t.product_name} ({ops}, ISO {iso})",
        ))
    return entries


def get_machine_spindle_max_rpm(machine_id: str) -> int | None:
    """Return spindle_max_rpm for the given machine_id, or None if unknown."""
    rec = _MACHINES.get(machine_id)
    return rec.spindle_max_rpm if rec else None


def get_tool_number_of_flutes(cutting_tool_id: str) -> int | None:
    """Return number_of_flutes for the given cutting_tool_id, or None if unknown."""
    rec = _TOOLS.get(cutting_tool_id)
    return rec.number_of_flutes if rec else None


def get_machine_rapid_traverse_mpm(machine_id: str) -> float | None:
    """Return rapid_traverse_mpm for the given machine_id, or None if absent.

    Only 2/15 catalog machines have source-backed rapid traverse data.
    Returns None for all other machines — never fabricates a value.
    """
    rec = _MACHINES.get(machine_id)
    return rec.rapid_traverse_mpm if rec else None


# ---------------------------------------------------------------------------
# Individual rule evaluators
# ---------------------------------------------------------------------------

# Tool interface keys that use shank diameter + clamping range matching
_BORE_DIAMETER_INTERFACES: frozenset[str] = frozenset({
    "ER32", "ER40", "ER16", "HYDRAULIC", "SHRINK_FIT",
})

# Insert seat holders: map tool_interface_key → expected insert_shape_code
_INSERT_SEAT_MAP: dict[str, str] = {
    "CNMG_SEAT": "C",
    "TNMG_SEAT": "T",
    "DCMT_SEAT": "D",
}


def _rule_process_support(
    machine: MachineCatalogRecord,
    tool: CuttingToolCatalogRecord,
    operation: str,
) -> RuleResult:
    machine_ok = operation in [p.lower() for p in machine.supported_processes]
    tool_ok = operation in [op.lower() for op in tool.supported_operations]

    if not machine_ok:
        return RuleResult(
            rule_id="PROCESS_SUPPORT",
            status="FAIL",
            reason_code=RC.MACHINE_PROCESS_NOT_SUPPORTED,
            detail=(
                f"Machine '{machine.stable_id}' does not support operation '{operation}'. "
                f"Supported: {machine.supported_processes}"
            ),
        )
    if not tool_ok:
        return RuleResult(
            rule_id="PROCESS_SUPPORT",
            status="FAIL",
            reason_code=RC.TOOL_PROCESS_NOT_SUPPORTED,
            detail=(
                f"Cutting tool '{tool.stable_id}' does not support operation '{operation}'. "
                f"Supported: {tool.supported_operations}"
            ),
        )
    return RuleResult(
        rule_id="PROCESS_SUPPORT",
        status="PASS",
        reason_code=RC.PROCESS_SUPPORTED,
        detail=f"Both machine and tool support '{operation}'.",
    )


def _rule_machine_holder_interface(
    machine: MachineCatalogRecord,
    holder: ToolHolderCatalogRecord,
) -> RuleResult:
    if machine.spindle_interface is None:
        return RuleResult(
            rule_id="MACHINE_HOLDER_INTERFACE",
            status="UNKNOWN",
            reason_code=RC.MACHINE_INTERFACE_UNKNOWN,
            detail=(
                f"Machine '{machine.stable_id}' has no published spindle interface. "
                "Cannot determine compatibility."
            ),
        )
    if machine.spindle_interface != holder.machine_interface_key:
        return RuleResult(
            rule_id="MACHINE_HOLDER_INTERFACE",
            status="FAIL",
            reason_code=RC.MACHINE_INTERFACE_MISMATCH,
            detail=(
                f"Machine spindle interface '{machine.spindle_interface}' does not match "
                f"holder machine interface '{holder.machine_interface_key}'."
            ),
        )
    return RuleResult(
        rule_id="MACHINE_HOLDER_INTERFACE",
        status="PASS",
        reason_code=RC.MACHINE_INTERFACE_MATCH,
        detail=f"Interfaces match: {machine.spindle_interface}.",
    )


def _rule_holder_tool_shank(
    holder: ToolHolderCatalogRecord,
    tool: CuttingToolCatalogRecord,
) -> RuleResult:
    key = holder.tool_interface_key

    if key in _BORE_DIAMETER_INTERFACES:
        if tool.shank_diameter_mm is None:
            return RuleResult(
                rule_id="HOLDER_TOOL_SHANK",
                status="UNKNOWN",
                reason_code=RC.SHANK_DIAMETER_UNKNOWN,
                detail=f"Cutting tool '{tool.stable_id}' has no published shank diameter.",
            )
        if holder.clamping_range_min_mm is None or holder.clamping_range_max_mm is None:
            return RuleResult(
                rule_id="HOLDER_TOOL_SHANK",
                status="UNKNOWN",
                reason_code=RC.HOLDER_CLAMP_RANGE_UNKNOWN,
                detail=(
                    f"Holder '{holder.stable_id}' has no published clamping range. "
                    "MISSING_LIMIT_AS_ZERO=NO: absent limit is not treated as 0."
                ),
            )
        lo = holder.clamping_range_min_mm
        hi = holder.clamping_range_max_mm
        d = tool.shank_diameter_mm
        if not (lo <= d <= hi):
            return RuleResult(
                rule_id="HOLDER_TOOL_SHANK",
                status="FAIL",
                reason_code=RC.SHANK_OUT_OF_RANGE,
                detail=(
                    f"Tool shank {d} mm is outside holder clamping range "
                    f"[{lo}, {hi}] mm."
                ),
            )
        return RuleResult(
            rule_id="HOLDER_TOOL_SHANK",
            status="PASS",
            reason_code=RC.SHANK_IN_RANGE,
            detail=(
                f"Tool shank {d} mm is within holder clamping range "
                f"[{lo}, {hi}] mm."
            ),
        )

    if key in _INSERT_SEAT_MAP:
        expected = _INSERT_SEAT_MAP[key]
        if tool.insert_shape_code is None:
            return RuleResult(
                rule_id="HOLDER_TOOL_SHANK",
                status="UNKNOWN",
                reason_code=RC.INSERT_SHAPE_UNKNOWN,
                detail=f"Cutting tool '{tool.stable_id}' has no published insert shape code.",
            )
        if tool.insert_shape_code != expected:
            return RuleResult(
                rule_id="HOLDER_TOOL_SHANK",
                status="FAIL",
                reason_code=RC.INSERT_SHAPE_MISMATCH,
                detail=(
                    f"Holder requires insert shape '{expected}'; "
                    f"tool has '{tool.insert_shape_code}'."
                ),
            )
        return RuleResult(
            rule_id="HOLDER_TOOL_SHANK",
            status="PASS",
            reason_code=RC.INSERT_SHAPE_MATCH,
            detail=f"Insert shape '{expected}' matches holder seat type '{key}'.",
        )

    if key == "BORING_BAR_25":
        if tool.shank_diameter_mm is None:
            return RuleResult(
                rule_id="HOLDER_TOOL_SHANK",
                status="UNKNOWN",
                reason_code=RC.SHANK_DIAMETER_UNKNOWN,
                detail=f"Cutting tool '{tool.stable_id}' has no published shank diameter.",
            )
        target = 25.0
        if abs(tool.shank_diameter_mm - target) > 0.1:
            return RuleResult(
                rule_id="HOLDER_TOOL_SHANK",
                status="FAIL",
                reason_code=RC.BORING_SHANK_MISMATCH,
                detail=(
                    f"Holder expects 25 mm boring bar shank; "
                    f"tool shank is {tool.shank_diameter_mm} mm."
                ),
            )
        return RuleResult(
            rule_id="HOLDER_TOOL_SHANK",
            status="PASS",
            reason_code=RC.BORING_SHANK_MATCH,
            detail="Tool shank diameter matches 25 mm boring bar holder.",
        )

    if key == "SHELL_MILL_ARBOR":
        # No shell mill bodies in the cutting tool catalog — cannot evaluate
        return RuleResult(
            rule_id="HOLDER_TOOL_SHANK",
            status="UNKNOWN",
            reason_code=RC.INTERFACE_UNRESOLVABLE,
            detail=(
                f"Shell mill arbor compatibility requires a shell mill cutter body. "
                "The cutting tool catalog does not contain shell mill bodies; "
                "compatibility cannot be determined from available data."
            ),
        )

    return RuleResult(
        rule_id="HOLDER_TOOL_SHANK",
        status="UNKNOWN",
        reason_code=RC.INTERFACE_UNRESOLVABLE,
        detail=f"Tool interface key '{key}' is not resolvable against this tool type.",
    )


def _rule_iso_material_group(
    tool: CuttingToolCatalogRecord,
    iso_group: str,
) -> RuleResult:
    if not tool.iso_material_groups:
        return RuleResult(
            rule_id="ISO_MATERIAL_GROUP",
            status="UNKNOWN",
            reason_code=RC.ISO_SPEC_UNKNOWN,
            detail=f"Cutting tool '{tool.stable_id}' has no published ISO material groups.",
        )
    if iso_group not in tool.iso_material_groups:
        return RuleResult(
            rule_id="ISO_MATERIAL_GROUP",
            status="FAIL",
            reason_code=RC.ISO_NOT_SUPPORTED,
            detail=(
                f"ISO group '{iso_group}' is not in the tool's published material groups: "
                f"{tool.iso_material_groups}."
            ),
        )
    return RuleResult(
        rule_id="ISO_MATERIAL_GROUP",
        status="PASS",
        reason_code=RC.ISO_SUPPORTED,
        detail=f"ISO group '{iso_group}' is in tool's published material groups.",
    )


def _rule_rpm(
    rule_id: str,
    max_rpm: int | None,
    requested_rpm: float,
    entity_name: str,
    unknown_code: str,
    exceeded_code: str,
    ok_code: str,
) -> RuleResult:
    if max_rpm is None:
        return RuleResult(
            rule_id=rule_id,
            status="UNKNOWN",
            reason_code=unknown_code,
            detail=(
                f"'{entity_name}' has no published max RPM. "
                "MISSING_LIMIT_AS_ZERO=NO: absent limit is not treated as zero."
            ),
        )
    if requested_rpm > max_rpm:
        return RuleResult(
            rule_id=rule_id,
            status="FAIL",
            reason_code=exceeded_code,
            detail=(
                f"Requested {requested_rpm:.0f} rpm exceeds "
                f"'{entity_name}' max {max_rpm} rpm."
            ),
        )
    return RuleResult(
        rule_id=rule_id,
        status="PASS",
        reason_code=ok_code,
        detail=(
            f"Requested {requested_rpm:.0f} rpm is within "
            f"'{entity_name}' max {max_rpm} rpm."
        ),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(req: CompatibilityRequest) -> CompatibilityResponse:
    """Run all mandatory compatibility rules and derive the three-state result."""
    machine = _MACHINES[req.machine_id]
    holder = _HOLDERS[req.holder_id]
    tool = _TOOLS[req.cutting_tool_id]

    rules: list[RuleResult] = []
    missing_fields: list[str] = []

    # 1 — PROCESS_SUPPORT
    rules.append(_rule_process_support(machine, tool, req.operation))

    # 2 — MACHINE_HOLDER_INTERFACE
    r = _rule_machine_holder_interface(machine, holder)
    rules.append(r)
    if r.status == "UNKNOWN" and machine.spindle_interface is None:
        missing_fields.append(f"machine.spindle_interface ({req.machine_id})")

    # 3 — HOLDER_TOOL_SHANK
    r = _rule_holder_tool_shank(holder, tool)
    rules.append(r)
    if r.status == "UNKNOWN":
        if tool.shank_diameter_mm is None and holder.tool_interface_key in _BORE_DIAMETER_INTERFACES:
            missing_fields.append(f"tool.shank_diameter_mm ({req.cutting_tool_id})")
        if (
            holder.clamping_range_min_mm is None or holder.clamping_range_max_mm is None
        ) and holder.tool_interface_key in _BORE_DIAMETER_INTERFACES:
            missing_fields.append(f"holder.clamping_range ({req.holder_id})")
        if tool.insert_shape_code is None and holder.tool_interface_key in _INSERT_SEAT_MAP:
            missing_fields.append(f"tool.insert_shape_code ({req.cutting_tool_id})")

    # 4 — ISO_MATERIAL_GROUP
    rules.append(_rule_iso_material_group(tool, req.iso_material_group))

    # 5–7 — RPM rules (NOT_APPLICABLE when no Vc/D provided)
    calculated_rpm: float | None = None
    vc = req.cutting_speed_m_min
    d = req.tool_diameter_mm

    if vc is None or d is None:
        na_detail = "Vc and diameter not provided."
        for rule_id in ("MACHINE_RPM", "HOLDER_RPM", "TOOL_RPM"):
            rules.append(RuleResult(
                rule_id=rule_id,
                status="NOT_APPLICABLE",
                reason_code=RC.RPM_NOT_REQUESTED,
                detail=na_detail,
            ))
    else:
        try:
            qty = spindle_speed_from_cutting_speed(
                cutting_speed=Quantity(value=Decimal(str(vc)), unit=Unit.M_MIN),
                diameter=Quantity(value=Decimal(str(d)), unit=Unit.MM),
            )
            calculated_rpm = float(qty.value)
        except MachiningMathError as exc:
            for rule_id in ("MACHINE_RPM", "HOLDER_RPM", "TOOL_RPM"):
                rules.append(RuleResult(
                    rule_id=rule_id,
                    status="UNKNOWN",
                    reason_code=RC.MACHINE_RPM_LIMIT_UNKNOWN,
                    detail=f"RPM calculation failed: {exc}",
                ))
        else:
            rules.append(_rule_rpm(
                "MACHINE_RPM", machine.spindle_max_rpm, calculated_rpm,
                req.machine_id,
                RC.MACHINE_RPM_LIMIT_UNKNOWN, RC.MACHINE_RPM_EXCEEDED, RC.MACHINE_RPM_OK,
            ))
            rules.append(_rule_rpm(
                "HOLDER_RPM", holder.max_rpm, calculated_rpm,
                req.holder_id,
                RC.HOLDER_RPM_LIMIT_UNKNOWN, RC.HOLDER_RPM_EXCEEDED, RC.HOLDER_RPM_OK,
            ))
            rules.append(_rule_rpm(
                "TOOL_RPM", tool.max_rpm, calculated_rpm,
                req.cutting_tool_id,
                RC.TOOL_RPM_LIMIT_UNKNOWN, RC.TOOL_RPM_EXCEEDED, RC.TOOL_RPM_OK,
            ))
            # Note missing RPM limits
            if machine.spindle_max_rpm is None:
                missing_fields.append(f"machine.spindle_max_rpm ({req.machine_id})")
            if holder.max_rpm is None:
                missing_fields.append(f"holder.max_rpm ({req.holder_id})")
            if tool.max_rpm is None:
                missing_fields.append(f"tool.max_rpm ({req.cutting_tool_id})")

    # 8 — Cutting parameter reference (informational, NOT a hard rule)
    ref_available = False
    try:
        reg = _get_cp_registry()
        if len(reg) > 0:
            try:
                op_enum = OperationType(req.operation.lower())
                iso_enum = IsoMaterialGroup(req.iso_material_group.upper())
                scope = ApplicabilityScope(
                    operation_type=op_enum,
                    iso_material_group=iso_enum,
                )
                matches = reg.find(scope=scope)
                ref_available = len(matches) > 0
            except (ValueError, Exception):
                pass
    except Exception:
        pass

    # Derive overall status (three-state precedence)
    hard_failures = [r.rule_id for r in rules if r.status == "FAIL"]
    unknown_rules = [r.rule_id for r in rules if r.status == "UNKNOWN"]

    if hard_failures:
        overall = "INCOMPATIBLE"
    elif unknown_rules:
        overall = "INSUFFICIENT_DATA"
    else:
        overall = "COMPATIBLE"

    return CompatibilityResponse(
        overall_status=overall,
        machine_id=req.machine_id,
        holder_id=req.holder_id,
        cutting_tool_id=req.cutting_tool_id,
        operation=req.operation,
        iso_material_group=req.iso_material_group,
        rule_results=rules,
        hard_failures=hard_failures,
        unknown_rules=unknown_rules,
        missing_fields=sorted(set(missing_fields)),
        calculated_rpm=calculated_rpm,
        reference_guidance_available=ref_available,
    )
