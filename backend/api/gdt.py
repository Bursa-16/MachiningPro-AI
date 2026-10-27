"""GD&T Advanced Intelligence API (EPIC_04B Phase 3).

5 bounded endpoints:

  GET  /api/gdt/schema
  POST /api/gdt/validate
  POST /api/gdt/interpret
  POST /api/gdt/bonus-tolerance
  POST /api/gdt/virtual-condition

Security invariants:
  FABRICATED_GDT_VALUE=NO
  FABRICATED_ACTUAL_SIZE=NO
  FABRICATED_BONUS_TOLERANCE=NO
  FABRICATED_VIRTUAL_CONDITION=NO
  AUTO_INTERPRETATION_MARKED_APPROVED=NO
  PRIVATE_PATH_LEAK=NO
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.drawing_intelligence.bonus_tolerance import (
    BonusToleranceCalculator,
    VirtualConditionCalculator,
)
from backend.drawing_intelligence.gdt_validation import (
    VALIDATION_RULE_IDS,
    GdtValidationResult,
    validate_fcf,
)
from backend.drawing_intelligence.inspection_foundation import InspectionMethod
from backend.drawing_intelligence.requirements import (
    AmbiguityKind,
    DatumBoundaryModifier,
    DatumReference,
    DatumReferenceFrame,
    ExpandedFeatureControlFrame,
    FeatureModifier,
    FeatureOfSize,
    FeatureOfSizeKind,
    GdtCharacteristic,
    GdtConfidence,
    GdtModifier,
    ToleranceZoneGeometry,
    zone_geometry_for,
)

router = APIRouter(prefix="/api/gdt", tags=["gdt"])

_DISCLAIMER = (
    "GD&T interpretation is REFERENCE_ONLY — DRAFT status. "
    "AUTO_INTERPRETATION_MARKED_APPROVED=NO. "
    "All interpretations require engineering review before manufacturing use."
)


# ---------------------------------------------------------------------------
# Shared converters
# ---------------------------------------------------------------------------

def _dec(v: float | None, field: str) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation as exc:
        raise HTTPException(400, f"Invalid numeric value for {field}: {v}") from exc


def _req_dec(v: float | None, field: str) -> Decimal:
    d = _dec(v, field)
    if d is None:
        raise HTTPException(400, f"{field} is required")
    return d


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class DatumRefIn(BaseModel):
    label: str
    precedence: int
    modifier: str = "NONE"


class DatumFrameIn(BaseModel):
    primary: DatumRefIn
    secondary: DatumRefIn | None = None
    tertiary: DatumRefIn | None = None


class FcfIn(BaseModel):
    characteristic: str
    tolerance_value: float
    tolerance_unit: str = "mm"
    diameter_zone: bool = False
    modifier: str = "NONE"
    datum_frame: DatumFrameIn | None = None
    source_fcf_id: str | None = None


class FosIn(BaseModel):
    fos_id: str
    kind: str
    nominal_mm: float | None = None
    upper_limit_mm: float | None = None
    lower_limit_mm: float | None = None
    actual_size_mm: float | None = None
    source_req_id: str | None = None
    feature_id: str | None = None


class ValidateRequest(BaseModel):
    req_id: str
    fcf: FcfIn
    fos: FosIn | None = None


class InterpretRequest(BaseModel):
    req_id: str
    fcf: FcfIn
    fos: FosIn | None = None


class BonusToleranceRequest(BaseModel):
    req_id: str
    fcf: FcfIn
    fos: FosIn


class VirtualConditionRequest(BaseModel):
    req_id: str
    fcf: FcfIn
    fos: FosIn


class CompositeFcfSegmentIn(BaseModel):
    segment_id: str
    intent: str
    fcf: FcfIn


class CompositeValidateRequest(BaseModel):
    fcf_id: str
    segments: list[CompositeFcfSegmentIn]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ValidationFindingOut(BaseModel):
    rule_id: str
    passed: bool
    severity: str
    message: str
    ambiguity_kind: str | None = None
    ambiguity_description: str | None = None
    suggested_resolution: str | None = None


class ValidationOut(BaseModel):
    req_id: str
    overall: str          # VALID | INVALID | INSUFFICIENT_DATA
    findings: list[ValidationFindingOut]
    disclaimer: str


class ToleranceZoneOut(BaseModel):
    geometry: str
    diameter_zone: bool
    value_mm: float
    unit: str


class DatumRefOut(BaseModel):
    label: str
    precedence: int
    modifier: str


class DatumFrameOut(BaseModel):
    primary: DatumRefOut
    secondary: DatumRefOut | None = None
    tertiary: DatumRefOut | None = None


class FosOut(BaseModel):
    fos_id: str
    kind: str
    nominal_mm: float | None
    upper_limit_mm: float | None
    lower_limit_mm: float | None
    mmc_size_mm: float | None
    lmc_size_mm: float | None
    actual_size_mm: float | None
    is_true_fos: bool


class ProcessImplicationOut(BaseModel):
    rule_id: str
    description: str
    severity: str = "INFO"


class InspectionImplicationOut(BaseModel):
    method: str
    rationale: str
    for_modifier: bool = False


class InterpretOut(BaseModel):
    req_id: str
    characteristic: str
    tolerance_value: float
    tolerance_unit: str
    modifier: str
    modifier_description: str
    diameter_zone: bool
    tolerance_zone: ToleranceZoneOut
    datum_frame: DatumFrameOut | None
    fos_context: FosOut | None
    process_implications: list[ProcessImplicationOut]
    inspection_implications: list[InspectionImplicationOut]
    ambiguities: list[dict[str, Any]]
    confidence: str
    approval_status: str    # always "PENDING_REVIEW"
    disclaimer: str


class BonusToleranceOut(BaseModel):
    req_id: str
    computed: bool
    stated_tolerance_mm: float
    bonus_amount_mm: float | None
    total_tolerance_mm: float | None
    actual_size_mm: float | None
    mmc_or_lmc_size_mm: float | None
    reason_not_computed: str | None
    disclaimer: str


class VirtualConditionOut(BaseModel):
    req_id: str
    computed: bool
    virtual_condition_mm: float | None
    description: str
    disclaimer: str


class SchemaOut(BaseModel):
    characteristics: list[str]
    feature_modifiers: list[str]
    datum_boundary_modifiers: list[str]
    tolerance_zone_geometries: list[str]
    feature_of_size_kinds: list[str]
    confidence_states: list[str]
    ambiguity_kinds: list[str]
    inspection_methods: list[str]
    validation_rule_ids: list[str]
    disclaimer: str


# ---------------------------------------------------------------------------
# Domain converters
# ---------------------------------------------------------------------------

def _build_datum_ref(d: DatumRefIn) -> DatumReference:
    try:
        mod = GdtModifier(d.modifier.upper())
    except ValueError:
        mod = GdtModifier.NONE
    return DatumReference(label=d.label, precedence=d.precedence, modifier=mod)


def _build_datum_frame(df: DatumFrameIn) -> DatumReferenceFrame:
    return DatumReferenceFrame(
        primary=_build_datum_ref(df.primary),
        secondary=_build_datum_ref(df.secondary) if df.secondary else None,
        tertiary=_build_datum_ref(df.tertiary) if df.tertiary else None,
    )


def _build_fcf(f: FcfIn, req_id: str) -> ExpandedFeatureControlFrame:
    try:
        char = GdtCharacteristic(f.characteristic.upper())
    except ValueError:
        char = GdtCharacteristic.UNKNOWN
    try:
        mod = GdtModifier(f.modifier.upper())
    except ValueError:
        mod = GdtModifier.NONE
    tol = _req_dec(f.tolerance_value, f"fcf.tolerance_value for {req_id}")
    if tol <= Decimal(0):
        raise HTTPException(400, f"fcf.tolerance_value must be > 0 for {req_id}")
    return ExpandedFeatureControlFrame(
        characteristic=char,
        tolerance_value=tol,
        tolerance_unit=f.tolerance_unit,
        diameter_zone=f.diameter_zone,
        modifier=mod,
        datum_frame=_build_datum_frame(f.datum_frame) if f.datum_frame else None,
        source_fcf_id=f.source_fcf_id,
    )


def _build_fos(f: FosIn) -> FeatureOfSize:
    try:
        kind = FeatureOfSizeKind(f.kind.upper())
    except ValueError:
        kind = FeatureOfSizeKind.UNKNOWN
    nom = _dec(f.nominal_mm, "fos.nominal_mm")
    upper = _dec(f.upper_limit_mm, "fos.upper_limit_mm")
    lower = _dec(f.lower_limit_mm, "fos.lower_limit_mm")
    actual = _dec(f.actual_size_mm, "fos.actual_size_mm")
    try:
        return FeatureOfSize(
            fos_id=f.fos_id,
            kind=kind,
            nominal_mm=nom,
            upper_limit_mm=upper,
            lower_limit_mm=lower,
            actual_size_mm=actual,
            source_req_id=f.source_req_id,
            feature_id=f.feature_id,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def _datum_ref_out(d: DatumReference) -> DatumRefOut:
    return DatumRefOut(label=d.label, precedence=d.precedence, modifier=d.modifier.value)


def _datum_frame_out(df: DatumReferenceFrame | None) -> DatumFrameOut | None:
    if df is None:
        return None
    return DatumFrameOut(
        primary=_datum_ref_out(df.primary),
        secondary=_datum_ref_out(df.secondary) if df.secondary else None,
        tertiary=_datum_ref_out(df.tertiary) if df.tertiary else None,
    )


def _fos_out(fos: FeatureOfSize) -> FosOut:
    def _f(v: Decimal | None) -> float | None:
        return float(v) if v is not None else None
    return FosOut(
        fos_id=fos.fos_id,
        kind=fos.kind.value,
        nominal_mm=_f(fos.nominal_mm),
        upper_limit_mm=_f(fos.upper_limit_mm),
        lower_limit_mm=_f(fos.lower_limit_mm),
        mmc_size_mm=_f(fos.mmc_size_mm),
        lmc_size_mm=_f(fos.lmc_size_mm),
        actual_size_mm=_f(fos.actual_size_mm),
        is_true_fos=fos.is_true_fos,
    )


_MODIFIER_DESCRIPTIONS: dict[str, str] = {
    "NONE": "RFS — Regardless of Feature Size (default)",
    "MMC": "MMC — Maximum Material Condition",
    "LMC": "LMC — Least Material Condition",
    "RFS": "RFS — Regardless of Feature Size",
    "PROJECTED": "Projected Tolerance Zone",
    "FREE_STATE": "Free State",
    "TANGENT_PLANE": "Tangent Plane",
    "UNEQUAL": "Unequal Bilateral Tolerance Zone",
}


def _findings_out(results: list[GdtValidationResult]) -> list[ValidationFindingOut]:
    out: list[ValidationFindingOut] = []
    for r in results:
        out.append(ValidationFindingOut(
            rule_id=r.rule_id,
            passed=r.passed,
            severity=r.severity,
            message=r.message,
            ambiguity_kind=r.ambiguity.kind.value if r.ambiguity else None,
            ambiguity_description=r.ambiguity.description if r.ambiguity else None,
            suggested_resolution=(
                r.ambiguity.suggested_resolution if r.ambiguity else None
            ),
        ))
    return out


def _overall_status(findings: list[ValidationFindingOut]) -> str:
    has_error = any(f.severity == "ERROR" and not f.passed for f in findings)
    if has_error:
        return "INVALID"
    return "VALID"


# ---------------------------------------------------------------------------
# Process and inspection implication derivation
# ---------------------------------------------------------------------------

_TIGHT_POSITION_MM = Decimal("0.1")
_VERY_TIGHT_POSITION_MM = Decimal("0.05")
_TIGHT_PERP_MM = Decimal("0.05")


def _process_implications(fcf: ExpandedFeatureControlFrame) -> list[ProcessImplicationOut]:
    out: list[ProcessImplicationOut] = []
    char = fcf.characteristic
    tol = fcf.tolerance_value

    if char == GdtCharacteristic.POSITION and tol <= _TIGHT_POSITION_MM:
        if tol <= _VERY_TIGHT_POSITION_MM:
            out.append(ProcessImplicationOut(
                rule_id="R-RT-GDT-001",
                description=(
                    f"POSITION ⌀{tol} mm — very tight; prefer boring + reaming; "
                    "jig boring may be required"
                ),
                severity="WARNING",
            ))
        else:
            out.append(ProcessImplicationOut(
                rule_id="R-RT-GDT-001",
                description=(
                    f"POSITION ⌀{tol} mm — tight; "
                    "prefer boring over drilling for final pass"
                ),
                severity="INFO",
            ))

    if char == GdtCharacteristic.PERPENDICULARITY and tol <= _TIGHT_PERP_MM:
        out.append(ProcessImplicationOut(
            rule_id="R-RT-GDT-002",
            description=(
                f"PERPENDICULARITY {tol} mm — add surface grinding or "
                "precision boring in final setup"
            ),
            severity="INFO",
        ))

    if char == GdtCharacteristic.CYLINDRICITY:
        out.append(ProcessImplicationOut(
            rule_id="R-RT-GDT-003",
            description=f"CYLINDRICITY {tol} mm — route should include cylindrical grinding",
            severity="INFO",
        ))

    if char in (GdtCharacteristic.CIRCULAR_RUNOUT, GdtCharacteristic.TOTAL_RUNOUT):
        out.append(ProcessImplicationOut(
            rule_id="R-RT-GDT-004",
            description=(
                f"{char.value} {tol} mm — all runout-controlled surfaces "
                "must be machined in one chucking"
            ),
            severity="WARNING",
        ))

    if char == GdtCharacteristic.PROFILE_OF_A_SURFACE:
        out.append(ProcessImplicationOut(
            rule_id="R-RT-GDT-005",
            description=(
                f"PROFILE_OF_A_SURFACE {tol} mm — include surface finishing "
                "in final route step"
            ),
            severity="INFO",
        ))

    if fcf.modifier in (GdtModifier.MMC, GdtModifier.LMC):
        out.append(ProcessImplicationOut(
            rule_id="R-RT-GDT-006",
            description=(
                f"{fcf.modifier.value} modifier — 100% size inspection required "
                "before GD&T conformance check"
            ),
            severity="INFO",
        ))

    return out


def _inspection_implications(fcf: ExpandedFeatureControlFrame) -> list[InspectionImplicationOut]:
    from backend.drawing_intelligence.inspection_foundation import _inspection_method_for
    method, rationale_tpl = _inspection_method_for(fcf.characteristic, fcf)
    formatted = rationale_tpl.format(
        char=fcf.characteristic.value,
        tol=fcf.tolerance_value,
        unit=fcf.tolerance_unit,
    )
    out = [InspectionImplicationOut(method=method.value, rationale=formatted)]
    if fcf.modifier in (GdtModifier.MMC, GdtModifier.LMC):
        out.append(InspectionImplicationOut(
            method=InspectionMethod.SIZE_MEASUREMENT.value,
            rationale=(
                f"{fcf.modifier.value} modifier on {fcf.characteristic.value}: "
                "100% actual size measurement required before GD&T conformance check"
            ),
            for_modifier=True,
        ))
    return out


# ---------------------------------------------------------------------------
# GET /api/gdt/schema
# ---------------------------------------------------------------------------

@router.get("/schema", response_model=SchemaOut)
async def get_gdt_schema() -> SchemaOut:
    """Return supported GD&T enum values and rule IDs.

    Does not imply certification to a GD&T standard. All values are
    REFERENCE_ONLY. Engineering review required before manufacturing use.
    """
    return SchemaOut(
        characteristics=[c.value for c in GdtCharacteristic if c != GdtCharacteristic.UNKNOWN],
        feature_modifiers=[m.value for m in FeatureModifier],
        datum_boundary_modifiers=[m.value for m in DatumBoundaryModifier],
        tolerance_zone_geometries=[g.value for g in ToleranceZoneGeometry],
        feature_of_size_kinds=[
            k.value for k in FeatureOfSizeKind if k != FeatureOfSizeKind.UNKNOWN
        ],
        confidence_states=[c.value for c in GdtConfidence],
        ambiguity_kinds=[k.value for k in AmbiguityKind],
        inspection_methods=[m.value for m in InspectionMethod],
        validation_rule_ids=list(VALIDATION_RULE_IDS),
        disclaimer=_DISCLAIMER,
    )


# ---------------------------------------------------------------------------
# POST /api/gdt/validate
# ---------------------------------------------------------------------------

@router.post("/validate", response_model=ValidationOut)
async def validate_gdt(req: ValidateRequest) -> ValidationOut:
    """Validate a Feature Control Frame and optional FOS against semantic rules.

    Returns VALID, INVALID, or INSUFFICIENT_DATA with structured findings.
    """
    fcf = _build_fcf(req.fcf, req.req_id)
    fos = _build_fos(req.fos) if req.fos else None

    findings_domain = validate_fcf(fcf, req.req_id, fos)
    findings = _findings_out(findings_domain)
    overall = _overall_status(findings)

    return ValidationOut(
        req_id=req.req_id,
        overall=overall,
        findings=findings,
        disclaimer=_DISCLAIMER,
    )


# ---------------------------------------------------------------------------
# POST /api/gdt/interpret
# ---------------------------------------------------------------------------

@router.post("/interpret", response_model=InterpretOut)
async def interpret_gdt(req: InterpretRequest) -> InterpretOut:
    """Return structured interpretation of a Feature Control Frame.

    All returned interpretations have approval_status=PENDING_REVIEW.
    AUTO_INTERPRETATION_MARKED_APPROVED=NO.
    """
    fcf = _build_fcf(req.fcf, req.req_id)
    fos = _build_fos(req.fos) if req.fos else None

    zone_geom = zone_geometry_for(fcf.characteristic, fcf.diameter_zone)

    findings_domain = validate_fcf(fcf, req.req_id, fos)
    ambiguities: list[dict[str, Any]] = []
    for r in findings_domain:
        if r.ambiguity is not None:
            ambiguities.append({
                "ambiguity_id": r.ambiguity.ambiguity_id,
                "kind": r.ambiguity.kind.value,
                "severity": r.ambiguity.severity,
                "description": r.ambiguity.description,
                "suggested_resolution": r.ambiguity.suggested_resolution,
            })

    confidence = (
        GdtConfidence.AMBIGUOUS if ambiguities else GdtConfidence.RULE_PARSED
    ).value

    return InterpretOut(
        req_id=req.req_id,
        characteristic=fcf.characteristic.value,
        tolerance_value=float(fcf.tolerance_value),
        tolerance_unit=fcf.tolerance_unit,
        modifier=fcf.modifier.value,
        modifier_description=_MODIFIER_DESCRIPTIONS.get(fcf.modifier.value, fcf.modifier.value),
        diameter_zone=fcf.diameter_zone,
        tolerance_zone=ToleranceZoneOut(
            geometry=zone_geom.value,
            diameter_zone=fcf.diameter_zone,
            value_mm=float(fcf.tolerance_value),
            unit=fcf.tolerance_unit,
        ),
        datum_frame=_datum_frame_out(fcf.datum_frame),
        fos_context=_fos_out(fos) if fos else None,
        process_implications=_process_implications(fcf),
        inspection_implications=_inspection_implications(fcf),
        ambiguities=ambiguities,
        confidence=confidence,
        approval_status="PENDING_REVIEW",
        disclaimer=_DISCLAIMER,
    )


# ---------------------------------------------------------------------------
# POST /api/gdt/bonus-tolerance
# ---------------------------------------------------------------------------

@router.post("/bonus-tolerance", response_model=BonusToleranceOut)
async def calc_bonus_tolerance(req: BonusToleranceRequest) -> BonusToleranceOut:
    """Compute bonus tolerance for an MMC/LMC FCF + FOS pair.

    Returns INSUFFICIENT_DATA when actual_size_mm is absent.
    FABRICATED_ACTUAL_SIZE=NO — actual size must come from the caller.
    """
    fcf = _build_fcf(req.fcf, req.req_id)
    fos = _build_fos(req.fos)
    result = BonusToleranceCalculator().compute(fcf, fos)

    def _f(v: Decimal | None) -> float | None:
        return float(v) if v is not None else None

    return BonusToleranceOut(
        req_id=req.req_id,
        computed=result.computed,
        stated_tolerance_mm=float(result.stated_tolerance),
        bonus_amount_mm=_f(result.bonus_amount),
        total_tolerance_mm=_f(result.total_tolerance),
        actual_size_mm=_f(result.actual_size_mm),
        mmc_or_lmc_size_mm=_f(result.mmc_or_lmc_size_mm),
        reason_not_computed=result.reason_not_computed,
        disclaimer=_DISCLAIMER,
    )


# ---------------------------------------------------------------------------
# POST /api/gdt/virtual-condition
# ---------------------------------------------------------------------------

@router.post("/virtual-condition", response_model=VirtualConditionOut)
async def calc_virtual_condition(req: VirtualConditionRequest) -> VirtualConditionOut:
    """Compute virtual condition for an MMC/LMC cylindrical FOS.

    Distinguishes internal (hole) vs external (shaft) features.
    FABRICATED_VIRTUAL_CONDITION=NO.
    """
    fcf = _build_fcf(req.fcf, req.req_id)
    fos = _build_fos(req.fos)
    result = VirtualConditionCalculator().compute(fcf, fos)

    return VirtualConditionOut(
        req_id=req.req_id,
        computed=result.computed,
        virtual_condition_mm=(
            float(result.virtual_condition_mm)
            if result.virtual_condition_mm is not None else None
        ),
        description=result.description,
        disclaimer=_DISCLAIMER,
    )
