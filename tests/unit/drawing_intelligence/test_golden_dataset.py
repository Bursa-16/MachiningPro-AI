"""Golden dataset tests for EPIC_04B Phase 2 — Cases A through J.

Each case represents a representative real-world GD&T scenario.
Tests verify deterministic behavior across bonus tolerance, virtual
condition, validation rules, and setup planning.

FABRICATED_GDT_VALUE=NO
FABRICATED_ACTUAL_SIZE=NO
FABRICATED_BONUS_TOLERANCE=NO
FABRICATED_VIRTUAL_CONDITION=NO
"""

import pytest
from decimal import Decimal

from backend.drawing_intelligence.bonus_tolerance import (
    compute_bonus_tolerance,
    compute_virtual_condition,
)
from backend.drawing_intelligence.gdt_validation import validate_fcf, validate_composite_fcf
from backend.drawing_intelligence.requirements import (
    AmbiguityKind,
    CompositePositionFCF,
    DatumReference,
    DatumReferenceFrame,
    ExpandedFeatureControlFrame,
    FCFSegment,
    FeatureModifier,
    FeatureOfSize,
    FeatureOfSizeKind,
    GdtCharacteristic,
    GdtModifier,
    SegmentIntent,
)


# ------------------------------------------------------------------
# Shared fixtures
# ------------------------------------------------------------------

def _frame(primary="A", secondary=None, tertiary=None):
    sec = DatumReference(label=secondary, precedence=2, modifier=GdtModifier.NONE) if secondary else None
    ter = DatumReference(label=tertiary, precedence=3, modifier=GdtModifier.NONE) if tertiary else None
    return DatumReferenceFrame(
        primary=DatumReference(label=primary, precedence=1, modifier=GdtModifier.NONE),
        secondary=sec, tertiary=ter,
    )


def _fcf(char, tol, modifier=GdtModifier.NONE, datum=None):
    return ExpandedFeatureControlFrame(
        characteristic=char, tolerance_value=Decimal(tol), tolerance_unit="mm",
        diameter_zone=True, modifier=modifier, datum_frame=datum,
    )


def _hole(upper, lower, actual=None):
    return FeatureOfSize(
        fos_id="FOS-H", kind=FeatureOfSizeKind.INTERNAL_CYLINDRICAL,
        nominal_mm=Decimal(lower), upper_limit_mm=Decimal(upper), lower_limit_mm=Decimal(lower),
        actual_size_mm=Decimal(actual) if actual else None,
        source_req_id=None, feature_id=None,
    )


def _shaft(upper, lower, actual=None):
    return FeatureOfSize(
        fos_id="FOS-S", kind=FeatureOfSizeKind.EXTERNAL_CYLINDRICAL,
        nominal_mm=Decimal(upper), upper_limit_mm=Decimal(upper), lower_limit_mm=Decimal(lower),
        actual_size_mm=Decimal(actual) if actual else None,
        source_req_id=None, feature_id=None,
    )


def _seg(idx, tol, intent):
    return FCFSegment(
        segment_index=idx, characteristic=GdtCharacteristic.POSITION,
        tolerance_value=Decimal(tol), tolerance_unit="mm",
        diameter_zone=True, modifier=FeatureModifier.NONE,
        datum_frame=None, intent=intent,
    )


# ------------------------------------------------------------------
# Case A: Simple position with MMC on a bore (common shaft support)
# ------------------------------------------------------------------

class TestCaseA_PositionMmcBore:
    """Ø25 H7/g6 bore. POSITION ⌀0.1 at MMC. Actual = 25.020."""

    fcf = _fcf(GdtCharacteristic.POSITION, "0.100", GdtModifier.MMC, _frame("A", "B"))
    fos = _hole("25.021", "25.000", "25.020")

    def test_bonus_computed(self):
        r = compute_bonus_tolerance(self.fcf, self.fos)
        assert r.computed is True

    def test_bonus_amount(self):
        # actual=25.020, MMC_hole=25.000 → bonus = 0.020
        r = compute_bonus_tolerance(self.fcf, self.fos)
        assert r.bonus_amount == Decimal("0.020")

    def test_total_tolerance(self):
        # stated=0.100 + bonus=0.020 → total=0.120
        r = compute_bonus_tolerance(self.fcf, self.fos)
        assert r.total_tolerance == Decimal("0.120")

    def test_virtual_condition(self):
        # Internal MMC: VC = MMC(25.000) − tol(0.100) = 24.900
        r = compute_virtual_condition(self.fcf, self.fos)
        assert r.computed is True
        assert r.virtual_condition_mm == Decimal("24.900")

    def test_position_requires_datum(self):
        results = validate_fcf(self.fcf, "CASE-A-REQ")
        r002 = next(r for r in results if r.rule_id == "VAL-GDT-002")
        assert r002.passed is True  # datum present

    def test_mmc_on_fos_passes_val003(self):
        results = validate_fcf(self.fcf, "CASE-A-REQ", fos=self.fos)
        r003 = next(r for r in results if r.rule_id == "VAL-GDT-003")
        assert r003.passed is True


# ------------------------------------------------------------------
# Case B: Flatness with MMC — invalid combination
# ------------------------------------------------------------------

class TestCaseB_FlatnessMmcInvalid:
    """Flatness 0.05 MMC — invalid (form cannot use material condition)."""

    fcf = _fcf(GdtCharacteristic.FLATNESS, "0.050", GdtModifier.MMC)

    def test_val004_rejects_form_with_mmc(self):
        results = validate_fcf(self.fcf, "CASE-B-REQ")
        r004 = next(r for r in results if r.rule_id == "VAL-GDT-004")
        assert r004.passed is False
        assert r004.severity == "ERROR"


# ------------------------------------------------------------------
# Case C: Form tolerance with datum — invalid
# ------------------------------------------------------------------

class TestCaseC_CylindricityWithDatum:
    """CYLINDRICITY 0.005 |A| — invalid (form cannot reference datum)."""

    fcf = _fcf(GdtCharacteristic.CYLINDRICITY, "0.005", datum=_frame("A"))

    def test_val001_rejects_form_with_datum(self):
        results = validate_fcf(self.fcf, "CASE-C-REQ")
        r001 = next(r for r in results if r.rule_id == "VAL-GDT-001")
        assert r001.passed is False


# ------------------------------------------------------------------
# Case D: External shaft position with LMC
# ------------------------------------------------------------------

class TestCaseD_ShaftPositionLmc:
    """Ø20 shaft, POSITION ⌀0.050 at LMC. Actual = 19.990."""

    fcf = _fcf(GdtCharacteristic.POSITION, "0.050", GdtModifier.LMC, _frame("A"))
    fos = _shaft("20.000", "19.979", "19.990")

    def test_bonus_computed(self):
        r = compute_bonus_tolerance(self.fcf, self.fos)
        assert r.computed is True

    def test_bonus_amount(self):
        # LMC shaft=19.979, actual=19.990 → bonus = 19.990 − 19.979 = 0.011
        r = compute_bonus_tolerance(self.fcf, self.fos)
        assert r.bonus_amount == Decimal("0.011")

    def test_virtual_condition_lmc_shaft(self):
        # External LMC: VC = LMC(19.979) − tol(0.050) = 19.929
        r = compute_virtual_condition(self.fcf, self.fos)
        assert r.computed is True
        assert r.virtual_condition_mm == Decimal("19.929")


# ------------------------------------------------------------------
# Case E: No actual size → bonus not computed (FABRICATED_ACTUAL_SIZE=NO)
# ------------------------------------------------------------------

class TestCaseE_NoActualSizeGate:
    """No actual size → bonus must not be computed."""

    fcf = _fcf(GdtCharacteristic.POSITION, "0.100", GdtModifier.MMC, _frame("A"))
    fos = _hole("25.021", "25.000")  # no actual

    def test_bonus_not_computed(self):
        r = compute_bonus_tolerance(self.fcf, self.fos)
        assert r.computed is False

    def test_reason_mentions_insufficient_data(self):
        r = compute_bonus_tolerance(self.fcf, self.fos)
        assert "INSUFFICIENT_DATA" in r.reason_not_computed

    def test_safe_total_returns_stated(self):
        r = compute_bonus_tolerance(self.fcf, self.fos)
        assert r.safe_total == Decimal("0.100")


# ------------------------------------------------------------------
# Case F: Circular runout — total runout without datum
# ------------------------------------------------------------------

class TestCaseF_TotalRunoutNoDatum:
    """TOTAL_RUNOUT 0.010 — no datum → warning."""

    fcf = _fcf(GdtCharacteristic.TOTAL_RUNOUT, "0.010")

    def test_val007_flags_missing_datum(self):
        results = validate_fcf(self.fcf, "CASE-F-REQ")
        r007 = next(r for r in results if r.rule_id == "VAL-GDT-007")
        assert r007.passed is False
        assert r007.severity == "WARNING"


# ------------------------------------------------------------------
# Case G: Composite FCF — correct order
# ------------------------------------------------------------------

class TestCaseG_CompositePosition:
    """POSITION composite: PLTZF ⌀0.300 | A|B|C, FRTZF ⌀0.050 | A."""

    comp = CompositePositionFCF(
        fcf_id="COMP-CASE-G",
        segments=(
            _seg(0, "0.300", SegmentIntent.PATTERN_LOCATING_TOLERANCE_ZONE),
            _seg(1, "0.050", SegmentIntent.FEATURE_RELATING_TOLERANCE_ZONE),
        ),
    )

    def test_segment_count(self):
        assert len(self.comp.segments) == 2

    def test_pltzf_larger(self):
        assert self.comp.segments[0].tolerance_value > self.comp.segments[1].tolerance_value

    def test_val006_passes(self):
        results = validate_composite_fcf(self.comp)
        r006 = next(r for r in results if r.rule_id == "VAL-GDT-006")
        assert r006.passed is True


# ------------------------------------------------------------------
# Case H: Concentricity — legacy advisory
# ------------------------------------------------------------------

class TestCaseH_LegacyConcentricity:
    """CONCENTRICITY 0.030 |A| — legacy, should produce INFO advisory."""

    fcf = _fcf(GdtCharacteristic.CONCENTRICITY, "0.030", datum=_frame("A"))

    def test_val008_info_advisory(self):
        results = validate_fcf(self.fcf, "CASE-H-REQ")
        r008 = next(r for r in results if r.rule_id == "VAL-GDT-008")
        assert r008.severity == "INFO"
        assert r008.passed is True

    def test_advisory_mentions_position(self):
        results = validate_fcf(self.fcf, "CASE-H-REQ")
        r008 = next(r for r in results if r.rule_id == "VAL-GDT-008")
        assert "POSITION" in r008.message.upper() or "coaxial" in r008.message.lower()


# ------------------------------------------------------------------
# Case I: Position without datum — warning
# ------------------------------------------------------------------

class TestCaseI_PositionNoDatum:
    """POSITION 0.100 — no datum reference → VAL-GDT-002 warning."""

    fcf = _fcf(GdtCharacteristic.POSITION, "0.100")

    def test_val002_warning(self):
        results = validate_fcf(self.fcf, "CASE-I-REQ")
        r002 = next(r for r in results if r.rule_id == "VAL-GDT-002")
        assert r002.passed is False
        assert r002.severity == "WARNING"
        assert r002.ambiguity is not None
        assert r002.ambiguity.kind == AmbiguityKind.MISSING_DATUM


# ------------------------------------------------------------------
# Case J: RFS modifier — no bonus, no virtual condition
# ------------------------------------------------------------------

class TestCaseJ_RfsNoBonusNoVC:
    """POSITION ⌀0.050 RFS — bonus not applicable."""

    fcf = _fcf(GdtCharacteristic.POSITION, "0.050", GdtModifier.NONE, _frame("A"))
    fos = _hole("25.021", "25.000", "25.015")

    def test_rfs_bonus_not_computed(self):
        r = compute_bonus_tolerance(self.fcf, self.fos)
        assert r.computed is False
        assert "not MMC or LMC" in r.reason_not_computed

    def test_rfs_vc_not_applicable(self):
        r = compute_virtual_condition(self.fcf, self.fos)
        assert r.computed is False
        assert "not applicable" in r.description.lower()
