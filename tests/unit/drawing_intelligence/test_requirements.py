"""Tests for drawing_intelligence.requirements (EPIC_04 Phase 2)."""

import pytest
from decimal import Decimal

from backend.drawing_intelligence.requirements import (
    DatumReference,
    DatumReferenceFrame,
    DimensionalRequirement,
    DrawingRequirementSet,
    ExpandedFeatureControlFrame,
    GdtCharacteristic,
    GdtModifier,
    GDT_REQUIRES_DATUM,
    GDT_CYLINDRICAL_CONTEXT,
    GeometricRequirement,
    HeatTreatmentRequirement,
    MaterialRequirement,
    RequirementExtractionStatus,
    SurfaceFinishRequirement,
    ThreadRequirement,
)


# ---------------------------------------------------------------------------
# GdtCharacteristic
# ---------------------------------------------------------------------------

class TestGdtCharacteristic:
    def test_all_14_characteristics(self):
        chars = [c for c in GdtCharacteristic if c != GdtCharacteristic.UNKNOWN]
        assert len(chars) == 14

    def test_phase1c_chars_present(self):
        assert GdtCharacteristic.FLATNESS in GdtCharacteristic
        assert GdtCharacteristic.CIRCULARITY in GdtCharacteristic
        assert GdtCharacteristic.POSITION in GdtCharacteristic
        assert GdtCharacteristic.SYMMETRY in GdtCharacteristic

    def test_new_chars_present(self):
        assert GdtCharacteristic.STRAIGHTNESS in GdtCharacteristic
        assert GdtCharacteristic.CYLINDRICITY in GdtCharacteristic
        assert GdtCharacteristic.PERPENDICULARITY in GdtCharacteristic
        assert GdtCharacteristic.ANGULARITY in GdtCharacteristic
        assert GdtCharacteristic.PARALLELISM in GdtCharacteristic
        assert GdtCharacteristic.CONCENTRICITY in GdtCharacteristic
        assert GdtCharacteristic.CIRCULAR_RUNOUT in GdtCharacteristic
        assert GdtCharacteristic.TOTAL_RUNOUT in GdtCharacteristic
        assert GdtCharacteristic.PROFILE_OF_A_LINE in GdtCharacteristic
        assert GdtCharacteristic.PROFILE_OF_A_SURFACE in GdtCharacteristic

    def test_requires_datum_set(self):
        # POSITION and SYMMETRY must require datum
        assert GdtCharacteristic.POSITION in GDT_REQUIRES_DATUM
        assert GdtCharacteristic.SYMMETRY in GDT_REQUIRES_DATUM

    def test_cylindrical_context_set(self):
        assert GdtCharacteristic.CIRCULARITY in GDT_CYLINDRICAL_CONTEXT
        assert GdtCharacteristic.CYLINDRICITY in GDT_CYLINDRICAL_CONTEXT

    def test_form_chars_not_require_datum(self):
        assert GdtCharacteristic.FLATNESS not in GDT_REQUIRES_DATUM
        assert GdtCharacteristic.STRAIGHTNESS not in GDT_REQUIRES_DATUM


# ---------------------------------------------------------------------------
# GdtModifier
# ---------------------------------------------------------------------------

class TestGdtModifier:
    def test_all_modifiers(self):
        mods = list(GdtModifier)
        assert len(mods) >= 7

    def test_values(self):
        assert GdtModifier.MMC == "MMC"
        assert GdtModifier.LMC == "LMC"
        assert GdtModifier.RFS == "RFS"


# ---------------------------------------------------------------------------
# DatumReference
# ---------------------------------------------------------------------------

class TestDatumReference:
    def test_valid(self):
        dr = DatumReference(label="A", precedence=1)
        assert dr.label == "A"
        assert dr.precedence == 1
        assert dr.modifier == GdtModifier.NONE

    def test_empty_label_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            DatumReference(label="", precedence=1)

    def test_invalid_precedence(self):
        with pytest.raises(ValueError, match="precedence"):
            DatumReference(label="A", precedence=0)
        with pytest.raises(ValueError, match="precedence"):
            DatumReference(label="A", precedence=4)

    def test_with_modifier(self):
        dr = DatumReference(label="B", precedence=2, modifier=GdtModifier.MMC)
        assert dr.modifier == GdtModifier.MMC


# ---------------------------------------------------------------------------
# DatumReferenceFrame
# ---------------------------------------------------------------------------

class TestDatumReferenceFrame:
    def test_primary_only(self):
        primary = DatumReference("A", 1)
        drf = DatumReferenceFrame(primary=primary)
        assert drf.secondary is None
        assert drf.tertiary is None
        assert drf.labels == ("A",)

    def test_primary_secondary(self):
        drf = DatumReferenceFrame(
            primary=DatumReference("A", 1),
            secondary=DatumReference("B", 2),
        )
        assert drf.labels == ("A", "B")

    def test_primary_secondary_tertiary(self):
        drf = DatumReferenceFrame(
            primary=DatumReference("A", 1),
            secondary=DatumReference("B", 2),
            tertiary=DatumReference("C", 3),
        )
        assert drf.labels == ("A", "B", "C")

    def test_tertiary_without_secondary_rejected(self):
        with pytest.raises(ValueError, match="tertiary requires secondary"):
            DatumReferenceFrame(
                primary=DatumReference("A", 1),
                tertiary=DatumReference("C", 3),
            )


# ---------------------------------------------------------------------------
# ExpandedFeatureControlFrame
# ---------------------------------------------------------------------------

class TestExpandedFeatureControlFrame:
    def test_valid_flatness(self):
        fcf = ExpandedFeatureControlFrame(
            characteristic=GdtCharacteristic.FLATNESS,
            tolerance_value=Decimal("0.05"),
            tolerance_unit="mm",
        )
        assert fcf.characteristic == GdtCharacteristic.FLATNESS
        assert fcf.tolerance_value == Decimal("0.05")

    def test_zero_tolerance_rejected(self):
        with pytest.raises(ValueError, match="must be > 0"):
            ExpandedFeatureControlFrame(
                characteristic=GdtCharacteristic.FLATNESS,
                tolerance_value=Decimal("0"),
                tolerance_unit="mm",
            )

    def test_negative_tolerance_rejected(self):
        with pytest.raises(ValueError):
            ExpandedFeatureControlFrame(
                characteristic=GdtCharacteristic.POSITION,
                tolerance_value=Decimal("-0.01"),
                tolerance_unit="mm",
            )

    def test_with_datum_frame(self):
        drf = DatumReferenceFrame(primary=DatumReference("A", 1))
        fcf = ExpandedFeatureControlFrame(
            characteristic=GdtCharacteristic.POSITION,
            tolerance_value=Decimal("0.1"),
            tolerance_unit="mm",
            datum_frame=drf,
        )
        assert fcf.datum_frame is drf

    def test_diameter_zone_flag(self):
        fcf = ExpandedFeatureControlFrame(
            characteristic=GdtCharacteristic.POSITION,
            tolerance_value=Decimal("0.05"),
            tolerance_unit="mm",
            diameter_zone=True,
        )
        assert fcf.diameter_zone is True


# ---------------------------------------------------------------------------
# DimensionalRequirement
# ---------------------------------------------------------------------------

class TestDimensionalRequirement:
    def test_valid(self):
        req = DimensionalRequirement(
            req_id="D-0001",
            dimension_type="DIAMETER",
            nominal_value=Decimal("25"),
            unit="mm",
        )
        assert req.nominal_value == Decimal("25")
        assert not req.has_tolerance

    def test_with_tolerance(self):
        req = DimensionalRequirement(
            req_id="D-0002",
            dimension_type="DIAMETER",
            nominal_value=Decimal("25"),
            unit="mm",
            tolerance_upper=Decimal("0.021"),
            tolerance_lower=Decimal("-0.000"),
        )
        assert req.has_tolerance

    def test_symmetric_bilateral_tolerance(self):
        req = DimensionalRequirement(
            req_id="D-0003",
            dimension_type="LINEAR",
            nominal_value=Decimal("50"),
            unit="mm",
            tolerance_upper=Decimal("0.1"),
            tolerance_lower=Decimal("-0.1"),
        )
        assert req.bilateral_tolerance == Decimal("0.2")

    def test_asymmetric_tolerance_no_bilateral(self):
        req = DimensionalRequirement(
            req_id="D-0004",
            dimension_type="LINEAR",
            nominal_value=Decimal("50"),
            unit="mm",
            tolerance_upper=Decimal("0.05"),
            tolerance_lower=Decimal("-0.1"),
        )
        assert req.bilateral_tolerance is None

    def test_empty_req_id_rejected(self):
        with pytest.raises(ValueError, match="req_id"):
            DimensionalRequirement(
                req_id="",
                dimension_type="DIAMETER",
                nominal_value=Decimal("10"),
                unit="mm",
            )


# ---------------------------------------------------------------------------
# SurfaceFinishRequirement
# ---------------------------------------------------------------------------

class TestSurfaceFinishRequirement:
    def test_ra_only(self):
        sf = SurfaceFinishRequirement(req_id="SF-0001", ra_um=Decimal("1.6"))
        assert sf.ra_um == Decimal("1.6")
        assert not sf.requires_grinding
        assert sf.requires_finishing

    def test_grinding_threshold(self):
        sf = SurfaceFinishRequirement(req_id="SF-0002", ra_um=Decimal("0.4"))
        assert sf.requires_grinding
        assert sf.requires_finishing

    def test_ra_boundary_0_8(self):
        sf = SurfaceFinishRequirement(req_id="SF-0003", ra_um=Decimal("0.8"))
        assert sf.requires_grinding
        assert sf.requires_finishing

    def test_both_ra_rz(self):
        sf = SurfaceFinishRequirement(req_id="SF-0004", ra_um=Decimal("3.2"), rz_um=Decimal("12.5"))
        assert sf.ra_um == Decimal("3.2")
        assert sf.rz_um == Decimal("12.5")

    def test_neither_ra_nor_rz_rejected(self):
        with pytest.raises(ValueError, match="ra_um or rz_um"):
            SurfaceFinishRequirement(req_id="SF-0005")

    def test_zero_ra_rejected(self):
        with pytest.raises(ValueError, match="ra_um must be > 0"):
            SurfaceFinishRequirement(req_id="SF-0006", ra_um=Decimal("0"))


# ---------------------------------------------------------------------------
# ThreadRequirement
# ---------------------------------------------------------------------------

class TestThreadRequirement:
    def test_metric_rh(self):
        t = ThreadRequirement(
            req_id="T-0001",
            designation="M12x1.75",
            hand="RH",
        )
        assert t.is_metric
        assert t.requires_tapping

    def test_lh(self):
        t = ThreadRequirement(req_id="T-0002", designation="M8x1.25", hand="LH")
        assert t.hand == "LH"

    def test_invalid_hand(self):
        with pytest.raises(ValueError, match="RH.*LH"):
            ThreadRequirement(req_id="T-0003", hand="X")

    def test_non_metric(self):
        t = ThreadRequirement(req_id="T-0004", designation="G1/4")
        assert not t.is_metric


# ---------------------------------------------------------------------------
# MaterialRequirement
# ---------------------------------------------------------------------------

class TestMaterialRequirement:
    def test_valid(self):
        m = MaterialRequirement(req_id="MAT-0001", raw_designation="42CrMo4")
        assert m.raw_designation == "42CrMo4"
        assert m.match_confidence == "NONE"

    def test_empty_designation_rejected(self):
        with pytest.raises(ValueError, match="raw_designation"):
            MaterialRequirement(req_id="MAT-0002", raw_designation="")

    def test_invalid_confidence_rejected(self):
        with pytest.raises(ValueError, match="match_confidence"):
            MaterialRequirement(
                req_id="MAT-0003",
                raw_designation="Steel",
                match_confidence="GOOD",
            )


# ---------------------------------------------------------------------------
# DrawingRequirementSet
# ---------------------------------------------------------------------------

class TestDrawingRequirementSet:
    def _make(self, **kwargs):
        defaults = {
            "source_id": "dwg-001",
            "drawing_number": "DWG-100",
            "revision": "A",
            "extraction_status": RequirementExtractionStatus.COMPLETE,
            "dimensional": (),
            "geometric": (),
            "surface_finish": (),
            "threads": (),
            "material": None,
            "heat_treatment": (),
        }
        defaults.update(kwargs)
        return DrawingRequirementSet(**defaults)

    def test_empty_set(self):
        rs = self._make()
        assert rs.requirement_count == 0
        assert not rs.has_gdt
        assert not rs.has_threads

    def test_has_gdt(self):
        drf = DatumReferenceFrame(primary=DatumReference("A", 1))
        fcf = ExpandedFeatureControlFrame(
            characteristic=GdtCharacteristic.FLATNESS,
            tolerance_value=Decimal("0.05"),
            tolerance_unit="mm",
        )
        geom = GeometricRequirement(req_id="G-0001", fcf=fcf)
        rs = self._make(geometric=(geom,))
        assert rs.has_gdt
        assert rs.requirement_count == 1

    def test_fingerprint_stable(self):
        rs = self._make()
        fp1 = rs.fingerprint
        fp2 = rs.fingerprint
        assert fp1 == fp2
        assert len(fp1) == 16

    def test_empty_source_id_rejected(self):
        with pytest.raises(ValueError, match="source_id"):
            self._make(source_id="  ")

    def test_requirement_count(self):
        dim = DimensionalRequirement(
            req_id="D-0001",
            dimension_type="DIAMETER",
            nominal_value=Decimal("10"),
            unit="mm",
        )
        sf = SurfaceFinishRequirement(req_id="SF-0001", ra_um=Decimal("1.6"))
        rs = self._make(dimensional=(dim,), surface_finish=(sf,))
        assert rs.requirement_count == 2
