"""Process Risk Model — EPIC_04E Phase 2.

Deterministic, transparent risk flag generation.
No AI risk scoring — all flags derived from engineering rules.

PROCESS_RISK_MODEL_IMPLEMENTED=YES
BLACK_BOX_AI_SCORE_USED=NO
"""

from __future__ import annotations

from backend.drawing_intelligence.route_alternatives import RouteTemplate
from backend.drawing_intelligence.route_domain import (
    OverallRiskLevel,
    RiskCategory,
    RiskFlag,
    RiskSeverity,
    RouteRisk,
)

__all__ = ["RouteRiskEvaluator", "evaluate_route_risk"]

_SEVERITY_WEIGHT = {
    RiskSeverity.CRITICAL: 4,
    RiskSeverity.HIGH: 3,
    RiskSeverity.MEDIUM: 2,
    RiskSeverity.LOW: 1,
}


def _overall_risk(flags: list[RiskFlag]) -> OverallRiskLevel:
    if not flags:
        return OverallRiskLevel.LOW
    if any(f.severity is RiskSeverity.CRITICAL for f in flags):
        return OverallRiskLevel.CRITICAL
    if any(f.severity is RiskSeverity.HIGH for f in flags):
        return OverallRiskLevel.HIGH
    if any(f.severity is RiskSeverity.MEDIUM for f in flags):
        return OverallRiskLevel.MEDIUM
    return OverallRiskLevel.LOW


class RouteRiskEvaluator:
    """Generates risk flags for a process route.

    PROCESS_RISK_MODEL_IMPLEMENTED=YES
    Each flag has an explicit category and mitigation note.
    """

    def evaluate(
        self,
        template: RouteTemplate,
        feature_id: str | None,
        required_ra_um: float | None = None,
        setup_count: int = 1,
        has_tight_position: bool = False,
        has_runout: bool = False,
        has_profile: bool = False,
        material_machinability: str | None = None,
        machine_candidates_empty: bool = False,
        tool_candidates_empty: bool = False,
        has_inspection: bool = False,
    ) -> RouteRisk:
        """Return RouteRisk with all applicable flags."""
        flags: list[RiskFlag] = []
        flag_idx = [0]

        def _flag(
            cat: RiskCategory,
            sev: RiskSeverity,
            desc: str,
            mitigation: str,
        ) -> None:
            flag_idx[0] += 1
            flags.append(RiskFlag(
                flag_id=f"RF-{flag_idx[0]:04d}",
                category=cat,
                severity=sev,
                description=desc,
                affected_feature_id=feature_id,
                mitigation_note=mitigation,
            ))

        # --- Tight tolerance ---
        if required_ra_um is not None and required_ra_um <= 0.4:
            sev = RiskSeverity.HIGH if required_ra_um <= 0.1 else RiskSeverity.MEDIUM
            _flag(
                RiskCategory.TIGHT_TOLERANCE,
                sev,
                f"Required Ra {required_ra_um} µm is tight — process capability must be verified",
                "Use toolholder with ≤ 3 µm runout; verify spindle condition before run.",
            )

        # --- Complex GD&T ---
        if has_tight_position:
            _flag(
                RiskCategory.COMPLEX_GDT,
                RiskSeverity.MEDIUM,
                "Tight position tolerance requires careful fixture setup and machining sequence",
                "Use a jig bore or precision boring head; verify fixture repeatability.",
            )
        if has_runout:
            _flag(
                RiskCategory.COMPLEX_GDT,
                RiskSeverity.HIGH,
                "Runout control requires all affected features to be machined in the same setup",
                "Do not rechuck between datum and runout-controlled diameter.",
            )
        if has_profile:
            _flag(
                RiskCategory.COMPLEX_GDT,
                RiskSeverity.MEDIUM,
                "Profile of a surface requires 5-axis capability and accurate toolpath",
                "Validate CAM toolpath against GD&T zone before machining.",
            )

        # --- Setup count ---
        if setup_count > 3:
            _flag(
                RiskCategory.SETUP_COUNT,
                RiskSeverity.MEDIUM,
                f"{setup_count} setups increase cumulative positioning error",
                "Consolidate setups where possible; use datum transfer probing between setups.",
            )

        # --- Specialty operations ---
        if template.specialty_op_count > 0:
            _flag(
                RiskCategory.UNKNOWN_CAPABILITY,
                RiskSeverity.MEDIUM,
                f"Route includes {template.specialty_op_count} specialty operation(s) "
                f"(honing, lapping, or grinding) that may require external processing",
                "Confirm availability and lead time for specialty operations.",
            )

        # --- Material difficulty ---
        if material_machinability in ("VERY_LOW", "LOW", "EXTREME"):
            _flag(
                RiskCategory.MATERIAL_DIFFICULTY,
                RiskSeverity.HIGH,
                f"Material machinability is {material_machinability} — "
                "cutting parameters must be de-rated",
                "Consult tool manufacturer for material-specific parameters; "
                "reduce cutting speed 20–30%.",
            )
        elif material_machinability == "MODERATE":
            _flag(
                RiskCategory.MATERIAL_DIFFICULTY,
                RiskSeverity.LOW,
                "Material machinability is MODERATE — standard parameters apply with caution",
                "Monitor tool wear; adjust feed on first part.",
            )

        # --- Machine uncertainty ---
        if machine_candidates_empty:
            _flag(
                RiskCategory.MACHINE_UNCERTAINTY,
                RiskSeverity.HIGH,
                "No machine candidates found in catalog for this route",
                "Verify machine availability on shop floor; catalog may be incomplete.",
            )

        # --- Tool uncertainty ---
        if tool_candidates_empty:
            _flag(
                RiskCategory.TOOL_UNCERTAINTY,
                RiskSeverity.MEDIUM,
                "No tool candidates found in catalog for this route",
                "Source appropriate tooling; catalog may be incomplete.",
            )

        # --- Inspection complexity ---
        if has_inspection and (has_tight_position or has_runout):
            _flag(
                RiskCategory.INSPECTION_COMPLEXITY,
                RiskSeverity.MEDIUM,
                "Tight GD&T features require CMM or dedicated gauge for inspection",
                "Plan for CMM measurement before releasing part.",
            )

        return RouteRisk(
            flags=tuple(flags),
            overall_risk=_overall_risk(flags),
        )


def evaluate_route_risk(
    template: RouteTemplate,
    feature_id: str | None = None,
    **kwargs,
) -> RouteRisk:
    return RouteRiskEvaluator().evaluate(template, feature_id, **kwargs)
