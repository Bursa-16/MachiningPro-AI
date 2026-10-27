"""Bonus Tolerance and Virtual Condition Calculators (EPIC_04B Phase 2).

Deterministic calculations. Only computed when all required inputs exist.

FABRICATED_ACTUAL_SIZE=NO
FABRICATED_BONUS_TOLERANCE=NO
FABRICATED_VIRTUAL_CONDITION=NO
MISSING_VALUE_AS_ZERO=NO
"""

from __future__ import annotations

from decimal import Decimal

from backend.drawing_intelligence.requirements import (
    BonusToleranceResult,
    ExpandedFeatureControlFrame,
    FeatureOfSize,
    FeatureOfSizeKind,
    GdtModifier,
    VirtualConditionResult,
)

__all__ = [
    "BonusToleranceCalculator",
    "VirtualConditionCalculator",
    "compute_bonus_tolerance",
    "compute_virtual_condition",
]


class BonusToleranceCalculator:
    """Deterministic bonus tolerance computation.

    Prerequisites — ALL must hold:
    1. fcf.modifier is MMC or LMC
    2. fos.is_true_fos is True
    3. fos.actual_size_mm is not None  ← HARD GATE — never fabricate
    4. fos.upper_limit_mm and lower_limit_mm are not None

    Returns computed=False (INSUFFICIENT_DATA) when any prerequisite fails.
    """

    def compute(
        self,
        fcf: ExpandedFeatureControlFrame,
        fos: FeatureOfSize,
    ) -> BonusToleranceResult:
        stated = fcf.tolerance_value

        if fcf.modifier not in (GdtModifier.MMC, GdtModifier.LMC):
            return BonusToleranceResult(
                computed=False,
                stated_tolerance=stated,
                bonus_amount=None,
                total_tolerance=None,
                actual_size_mm=None,
                mmc_or_lmc_size_mm=None,
                reason_not_computed="Modifier is not MMC or LMC",
            )

        if not fos.is_true_fos:
            return BonusToleranceResult(
                computed=False,
                stated_tolerance=stated,
                bonus_amount=None,
                total_tolerance=None,
                actual_size_mm=None,
                mmc_or_lmc_size_mm=None,
                reason_not_computed="Feature is not a true feature-of-size",
            )

        if fos.actual_size_mm is None:
            return BonusToleranceResult(
                computed=False,
                stated_tolerance=stated,
                bonus_amount=None,
                total_tolerance=None,
                actual_size_mm=None,
                mmc_or_lmc_size_mm=None,
                reason_not_computed=(
                    "INSUFFICIENT_DATA: actual_size_mm is None — "
                    "bonus tolerance requires a measured or known actual size"
                ),
            )

        if fos.upper_limit_mm is None or fos.lower_limit_mm is None:
            return BonusToleranceResult(
                computed=False,
                stated_tolerance=stated,
                bonus_amount=None,
                total_tolerance=None,
                actual_size_mm=fos.actual_size_mm,
                mmc_or_lmc_size_mm=None,
                reason_not_computed="INSUFFICIENT_DATA: size limits not available",
            )

        actual = fos.actual_size_mm
        upper = fos.upper_limit_mm
        lower = fos.lower_limit_mm
        modifier = fcf.modifier
        kind = fos.kind

        bonus, ref_size = _compute_bonus(actual, upper, lower, modifier, kind)

        if bonus < Decimal(0):
            bonus = Decimal(0)

        return BonusToleranceResult(
            computed=True,
            stated_tolerance=stated,
            bonus_amount=bonus,
            total_tolerance=stated + bonus,
            actual_size_mm=actual,
            mmc_or_lmc_size_mm=ref_size,
            reason_not_computed=None,
        )


def _compute_bonus(
    actual: Decimal,
    upper: Decimal,
    lower: Decimal,
    modifier: GdtModifier,
    kind: FeatureOfSizeKind,
) -> tuple[Decimal, Decimal]:
    """Return (bonus_amount, reference_size)."""
    if kind == FeatureOfSizeKind.INTERNAL_CYLINDRICAL:
        # Hole: MMC = smallest (lower), LMC = largest (upper)
        if modifier == GdtModifier.MMC:
            ref = lower    # MMC hole size
            bonus = actual - ref
        else:              # LMC
            ref = upper    # LMC hole size
            bonus = ref - actual
    elif kind == FeatureOfSizeKind.EXTERNAL_CYLINDRICAL:
        # Shaft: MMC = largest (upper), LMC = smallest (lower)
        if modifier == GdtModifier.MMC:
            ref = upper    # MMC shaft size
            bonus = ref - actual
        else:              # LMC
            ref = lower    # LMC shaft size
            bonus = actual - ref
    else:
        # Width or other FOS — use upper/lower analogously to external
        if modifier == GdtModifier.MMC:
            ref = upper
            bonus = ref - actual
        else:
            ref = lower
            bonus = actual - ref
    return bonus, ref


class VirtualConditionCalculator:
    """Deterministic virtual condition computation.

    Internal feature (hole), MMC: VC = MMC_size − geometric_tolerance
    Internal feature, LMC:        VC = LMC_size + geometric_tolerance
    External feature (shaft), MMC: VC = MMC_size + geometric_tolerance
    External feature, LMC:         VC = LMC_size − geometric_tolerance
    RFS: not applicable (no fixed boundary).
    """

    def compute(
        self,
        fcf: ExpandedFeatureControlFrame,
        fos: FeatureOfSize,
    ) -> VirtualConditionResult:
        if fcf.modifier not in (GdtModifier.MMC, GdtModifier.LMC):
            return VirtualConditionResult(
                computed=False,
                virtual_condition_mm=None,
                description="Virtual condition not applicable for RFS modifier",
            )

        if not fos.is_true_fos:
            return VirtualConditionResult(
                computed=False,
                virtual_condition_mm=None,
                description="INSUFFICIENT_DATA: feature is not a true feature-of-size",
            )

        if fos.upper_limit_mm is None or fos.lower_limit_mm is None:
            return VirtualConditionResult(
                computed=False,
                virtual_condition_mm=None,
                description="INSUFFICIENT_DATA: size limits not available",
            )

        tol = fcf.tolerance_value
        kind = fos.kind
        modifier = fcf.modifier

        if kind == FeatureOfSizeKind.INTERNAL_CYLINDRICAL:
            mmc = fos.lower_limit_mm
            lmc = fos.upper_limit_mm
            if modifier == GdtModifier.MMC:
                vc = mmc - tol
                desc = f"Internal MMC: VC = MMC({mmc}) − tolerance({tol}) = {vc}"
            else:
                vc = lmc + tol
                desc = f"Internal LMC: VC = LMC({lmc}) + tolerance({tol}) = {vc}"
        elif kind == FeatureOfSizeKind.EXTERNAL_CYLINDRICAL:
            mmc = fos.upper_limit_mm
            lmc = fos.lower_limit_mm
            if modifier == GdtModifier.MMC:
                vc = mmc + tol
                desc = f"External MMC: VC = MMC({mmc}) + tolerance({tol}) = {vc}"
            else:
                vc = lmc - tol
                desc = f"External LMC: VC = LMC({lmc}) − tolerance({tol}) = {vc}"
        else:
            return VirtualConditionResult(
                computed=False,
                virtual_condition_mm=None,
                description="INSUFFICIENT_DATA: virtual condition requires cylindrical FOS",
            )

        return VirtualConditionResult(
            computed=True,
            virtual_condition_mm=vc,
            description=desc,
        )


def compute_bonus_tolerance(
    fcf: ExpandedFeatureControlFrame,
    fos: FeatureOfSize,
) -> BonusToleranceResult:
    """Convenience function."""
    return BonusToleranceCalculator().compute(fcf, fos)


def compute_virtual_condition(
    fcf: ExpandedFeatureControlFrame,
    fos: FeatureOfSize,
) -> VirtualConditionResult:
    """Convenience function."""
    return VirtualConditionCalculator().compute(fcf, fos)
