"""
Comprehensive test suite for PHYSICS-01C surface roughness engine.

15+ test cases covering:
- Exact feed-mark calculations (hand-verified)
- Exact scallop calculations (hand-verified)
- Ra ≠ Rq verification (mathematical proof)
- Unit conversions (mm to µm)
- Decimal precision and repeatability
- Fail-closed validation
- Traceability metadata
- VP100 blockage audit
"""

from decimal import Decimal

import pytest

# Import implementation
from backend.machining.surface_roughness import (
    VP100_AUDIT,
    RoughnessModelType,
    SurfaceRoughnessError,
    SurfaceRoughnessInput,
    compute_surface_roughness,
    ideal_feed_mark_roughness,
    ideal_scallop_roughness,
)

# Fallback Quantity/Unit if not available from domain
try:
    from machining.domain import Quantity, Unit
except ImportError:

    class Unit:
        MM = "mm"
        UM = "µm"

    class Quantity:
        def __init__(self, value, unit: str):
            if isinstance(value, str):
                value = Decimal(value)
            elif not isinstance(value, Decimal):
                value = Decimal(str(value))
            self.value = value
            self.unit = unit

        def __eq__(self, other):
            if isinstance(other, Quantity):
                return self.value == other.value and self.unit == other.unit
            return False

        def __repr__(self):
            return f"Quantity({self.value}, {self.unit!r})"


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def sqrt3():
    """√3 constant for manual verification."""
    return Decimal("1.7320508075688772935274463415059")


# ============================================================================
# GROUP A: EXACT FEED-MARK CASES (Hand-Verified)
# ============================================================================


class TestIdealFeedMark:
    """Feed-mark geometric roughness tests."""

    def test_feed_mark_exact_case_01(self, sqrt3):
        """
        Test Case A1: fz = 0.10 mm, R = 1 mm
        Hand calculation:
        - h = (0.10)² / (8 * 1) = 0.01 / 8 = 0.00125 mm
        - Ra = h / 2 = 0.00125 / 2 = 0.000625 mm = 0.625 µm
        - Rq = h / √3 = 0.00125 / 1.732050808 ≈ 0.000722 mm ≈ 0.722 µm
        """
        fz = Quantity(Decimal("0.10"), Unit.MM)
        radius = Quantity(Decimal("1"), Unit.MM)

        ra_dec, rq_dec = ideal_feed_mark_roughness(fz, radius)

        # Verify exact values
        expected_h = Decimal("0.00125")
        expected_ra = Decimal("0.000625")
        expected_rq = expected_h / sqrt3

        assert ra_dec == expected_ra, f"Ra: {ra_dec} != {expected_ra}"
        assert rq_dec == expected_rq, f"Rq: {rq_dec} != {expected_rq}"
        assert ra_dec < rq_dec, f"Ra ({ra_dec}) should be < Rq ({rq_dec})"

    def test_feed_mark_exact_case_02(self, sqrt3):
        """
        Test Case A2: fz = 0.05 mm, R = 2 mm
        Hand calculation:
        - h = (0.05)² / (8 * 2) = 0.0025 / 16 = 0.00015625 mm
        - Ra = h / 2 = 0.000078125 mm = 0.0781 µm
        - Rq = h / √3 ≈ 0.0000903 mm ≈ 0.0903 µm
        """
        fz = Quantity(Decimal("0.05"), Unit.MM)
        radius = Quantity(Decimal("2"), Unit.MM)

        ra_dec, rq_dec = ideal_feed_mark_roughness(fz, radius)

        expected_h = Decimal("0.00015625")
        expected_ra = expected_h / Decimal(2)
        expected_rq = expected_h / sqrt3

        assert ra_dec == expected_ra
        assert rq_dec == expected_rq
        assert ra_dec < rq_dec

    def test_feed_mark_exact_case_03(self, sqrt3):
        """
        Test Case A3: fz = 0.20 mm, R = 0.5 mm (small radius)
        Hand calculation:
        - h = (0.20)² / (8 * 0.5) = 0.04 / 4 = 0.01 mm
        - Ra = 0.01 / 2 = 0.005 mm = 5 µm
        - Rq = 0.01 / √3 ≈ 0.00578 mm ≈ 5.78 µm
        """
        fz = Quantity(Decimal("0.20"), Unit.MM)
        radius = Quantity(Decimal("0.5"), Unit.MM)

        ra_dec, rq_dec = ideal_feed_mark_roughness(fz, radius)

        expected_h = Decimal("0.01")
        expected_ra = Decimal("0.005")
        expected_rq = expected_h / sqrt3

        assert ra_dec == expected_ra
        assert rq_dec == expected_rq
        assert abs(rq_dec - Decimal("0.005773502692")) < Decimal("0.000000001")

    def test_feed_mark_ra_not_equal_rq(self):
        """Test Case A4: Verify Ra ≠ Rq analytically for all positive inputs."""
        test_cases = [
            (Decimal("0.05"), Decimal("1")),
            (Decimal("0.10"), Decimal("2")),
            (Decimal("0.15"), Decimal("0.5")),
            (Decimal("0.20"), Decimal("5")),
        ]
        for fz_val, r_val in test_cases:
            fz = Quantity(fz_val, Unit.MM)
            radius = Quantity(r_val, Unit.MM)
            ra, rq = ideal_feed_mark_roughness(fz, radius)

            # Mathematically, for triangular profile: Ra = h/2, Rq = h/√3
            # Since √3 ≈ 1.732 > 2, we have Rq < Ra
            # Wait, check: h/√3 < h/2 ⟺ 2 < √3? No.
            # √3 ≈ 1.732 < 2 ⟹ h/√3 > h/2 ⟹ Rq > Ra
            assert ra != rq, f"Ra ({ra}) should != Rq ({rq})"
            assert ra < rq, f"Ra ({ra}) should be < Rq ({rq}) for triangular profile"

    def test_feed_mark_input_validation_zero_feed(self):
        """Test Case A5: Reject feed_per_tooth = 0."""
        fz = Quantity(Decimal("0"), Unit.MM)
        radius = Quantity(Decimal("1"), Unit.MM)

        with pytest.raises(SurfaceRoughnessError) as exc_info:
            ideal_feed_mark_roughness(fz, radius)
        assert "Feed per tooth must be > 0" in str(exc_info.value)

    def test_feed_mark_input_validation_negative_feed(self):
        """Test Case A6: Reject feed_per_tooth < 0."""
        fz = Quantity(Decimal("-0.05"), Unit.MM)
        radius = Quantity(Decimal("1"), Unit.MM)

        with pytest.raises(SurfaceRoughnessError):
            ideal_feed_mark_roughness(fz, radius)

    def test_feed_mark_input_validation_zero_radius(self):
        """Test Case A7: Reject effective_radius = 0."""
        fz = Quantity(Decimal("0.1"), Unit.MM)
        radius = Quantity(Decimal("0"), Unit.MM)

        with pytest.raises(SurfaceRoughnessError) as exc_info:
            ideal_feed_mark_roughness(fz, radius)
        assert "Effective radius must be > 0" in str(exc_info.value)


# ============================================================================
# GROUP B: EXACT SCALLOP CASES (Hand-Verified)
# ============================================================================


class TestIdealScallop:
    """Scallop/step-over geometric roughness tests."""

    def test_scallop_exact_case_01(self, sqrt3):
        """
        Test Case B1: ae = 2 mm, R = 10 mm
        Hand calculation:
        - h = (2)² / (8 * 10) = 4 / 80 = 0.05 mm
        - Ra = h / 2 = 0.025 mm = 25 µm
        - Rq = h / √3 = 0.05 / 1.732... ≈ 0.0289 mm ≈ 28.9 µm
        """
        ae = Quantity(Decimal("2"), Unit.MM)
        radius = Quantity(Decimal("10"), Unit.MM)

        ra_dec, rq_dec = ideal_scallop_roughness(ae, radius)

        expected_h = Decimal("0.05")
        expected_ra = Decimal("0.025")
        expected_rq = expected_h / sqrt3

        assert ra_dec == expected_ra
        assert rq_dec == expected_rq
        assert ra_dec < rq_dec

    def test_scallop_exact_case_02(self, sqrt3):
        """
        Test Case B2: ae = 1 mm, R = 5 mm
        Hand calculation:
        - h = (1)² / (8 * 5) = 1 / 40 = 0.025 mm
        - Ra = 0.0125 mm = 12.5 µm
        - Rq = 0.025 / √3 ≈ 0.01443 mm ≈ 14.43 µm
        """
        ae = Quantity(Decimal("1"), Unit.MM)
        radius = Quantity(Decimal("5"), Unit.MM)

        ra_dec, rq_dec = ideal_scallop_roughness(ae, radius)

        expected_h = Decimal("0.025")
        expected_ra = Decimal("0.0125")
        expected_rq = expected_h / sqrt3

        assert ra_dec == expected_ra
        assert rq_dec == expected_rq

    def test_scallop_geometric_constraint_valid(self):
        """Test Case B3: Verify stepover < 2*radius is accepted."""
        # Valid: ae = 1.9, R = 1.0 (ae < 2R = 2.0)
        ae = Quantity(Decimal("1.9"), Unit.MM)
        radius = Quantity(Decimal("1.0"), Unit.MM)

        # Should not raise
        ra_dec, rq_dec = ideal_scallop_roughness(ae, radius)
        assert ra_dec > 0
        assert rq_dec > 0

    def test_scallop_geometric_constraint_boundary(self):
        """Test Case B4: Reject stepover = 2*radius (boundary, fails-closed)."""
        ae = Quantity(Decimal("2.0"), Unit.MM)
        radius = Quantity(Decimal("1.0"), Unit.MM)

        with pytest.raises(SurfaceRoughnessError) as exc_info:
            ideal_scallop_roughness(ae, radius)
        assert "Geometric impossibility" in str(exc_info.value)

    def test_scallop_geometric_constraint_exceeded(self):
        """Test Case B5: Reject stepover > 2*radius (invalid geometry)."""
        ae = Quantity(Decimal("2.1"), Unit.MM)
        radius = Quantity(Decimal("1.0"), Unit.MM)

        with pytest.raises(SurfaceRoughnessError):
            ideal_scallop_roughness(ae, radius)

    def test_scallop_input_validation_zero_stepover(self):
        """Test Case B6: Reject stepover = 0."""
        ae = Quantity(Decimal("0"), Unit.MM)
        radius = Quantity(Decimal("5"), Unit.MM)

        with pytest.raises(SurfaceRoughnessError):
            ideal_scallop_roughness(ae, radius)

    def test_scallop_input_validation_zero_radius(self):
        """Test Case B7: Reject radius = 0."""
        ae = Quantity(Decimal("1"), Unit.MM)
        radius = Quantity(Decimal("0"), Unit.MM)

        with pytest.raises(SurfaceRoughnessError):
            ideal_scallop_roughness(ae, radius)


# ============================================================================
# GROUP C: RA ≠ RQ VERIFICATION (Mathematical Proof)
# ============================================================================


class TestRaNotEqualRq:
    """Verify Ra ≠ Rq for both models across valid domains."""

    def test_feed_mark_ra_less_than_rq(self):
        """Test Case C1: For triangular profile, Ra < Rq (proven)."""
        test_cases = [
            (Decimal("0.05"), Decimal("1")),
            (Decimal("0.10"), Decimal("2")),
            (Decimal("0.15"), Decimal("3")),
        ]
        for fz_val, r_val in test_cases:
            fz = Quantity(fz_val, Unit.MM)
            radius = Quantity(r_val, Unit.MM)
            ra, rq = ideal_feed_mark_roughness(fz, radius)

            assert ra < rq, f"Feed-mark: Ra ({ra}) must be < Rq ({rq}) for fz={fz_val}, R={r_val}"

    def test_scallop_ra_less_than_rq(self):
        """Test Case C2: For scallop profile, Ra < Rq (proven)."""
        test_cases = [
            (Decimal("1.0"), Decimal("5")),
            (Decimal("2.0"), Decimal("10")),
            (Decimal("0.5"), Decimal("4")),
        ]
        for ae_val, r_val in test_cases:
            ae = Quantity(ae_val, Unit.MM)
            radius = Quantity(r_val, Unit.MM)
            ra, rq = ideal_scallop_roughness(ae, radius)

            assert ra < rq, f"Scallop: Ra ({ra}) must be < Rq ({rq}) for ae={ae_val}, R={r_val}"


# ============================================================================
# GROUP D: UNIT CONVERSION (MM TO µM)
# ============================================================================


class TestUnitConversion:
    """Verify unit conversion: 1 mm = 1000 µm."""

    def test_feed_mark_conversion_to_micrometers(self):
        """Test Case D1: fz=0.10mm, R=1mm → Ra=0.625µm (manual conversion)."""
        fz = Quantity(Decimal("0.10"), Unit.MM)
        radius = Quantity(Decimal("1"), Unit.MM)

        ra_mm, rq_mm = ideal_feed_mark_roughness(fz, radius)

        # Manual conversion: mm → µm (multiply by 1000)
        ra_um = ra_mm * Decimal("1000")
        rq_um = rq_mm * Decimal("1000")

        assert ra_um == Decimal("0.625"), f"Ra: {ra_um} µm != 0.625 µm"
        # Rq ≈ 0.722 µm
        assert abs(rq_um - Decimal("0.722")) < Decimal("0.01")

    def test_scallop_conversion_to_micrometers(self):
        """Test Case D2: ae=2mm, R=10mm → Ra=25µm (manual conversion)."""
        ae = Quantity(Decimal("2"), Unit.MM)
        radius = Quantity(Decimal("10"), Unit.MM)

        ra_mm, rq_mm = ideal_scallop_roughness(ae, radius)

        ra_um = ra_mm * Decimal("1000")
        rq_um = rq_mm * Decimal("1000")

        assert ra_um == Decimal("25"), f"Ra: {ra_um} µm != 25 µm"
        # Rq ≈ 28.9 µm
        assert abs(rq_um - Decimal("28.9")) < Decimal("1")


# ============================================================================
# GROUP E: PRECISION & REPEATABILITY (Decimal Arithmetic)
# ============================================================================


class TestDecimalPrecision:
    """Verify deterministic Decimal arithmetic (no float leakage)."""

    def test_feed_mark_deterministic_repeatability(self):
        """Test Case E1: Multiple calls with same inputs → identical results."""
        fz = Quantity(Decimal("0.10"), Unit.MM)
        radius = Quantity(Decimal("1"), Unit.MM)

        results = [ideal_feed_mark_roughness(fz, radius) for _ in range(5)]

        # All results must be identical
        for i, (ra, rq) in enumerate(results[1:], 1):
            assert ra == results[0][0], f"Ra differs at call {i}"
            assert rq == results[0][1], f"Rq differs at call {i}"

    def test_scallop_deterministic_repeatability(self):
        """Test Case E2: Scallop calculation is deterministic."""
        ae = Quantity(Decimal("2"), Unit.MM)
        radius = Quantity(Decimal("10"), Unit.MM)

        results = [ideal_scallop_roughness(ae, radius) for _ in range(5)]

        for i, (ra, rq) in enumerate(results[1:], 1):
            assert ra == results[0][0], f"Ra differs at call {i}"
            assert rq == results[0][1], f"Rq differs at call {i}"

    def test_decimal_type_precision(self):
        """Test Case E3: Results are Decimal type (not float approximations)."""
        fz = Quantity(Decimal("0.10"), Unit.MM)
        radius = Quantity(Decimal("1"), Unit.MM)

        ra, rq = ideal_feed_mark_roughness(fz, radius)

        assert isinstance(ra, Decimal), f"Ra is {type(ra)}, not Decimal"
        assert isinstance(rq, Decimal), f"Rq is {type(rq)}, not Decimal"


# ============================================================================
# GROUP F: VALIDATION TESTS (Fail-Closed)
# ============================================================================


class TestValidation:
    """Comprehensive fail-closed validation."""

    def test_input_validation_wrong_units_feed_mark(self):
        """Test Case F1: Reject wrong units for feed_per_tooth."""
        fz_wrong = Quantity(Decimal("0.10"), "µm")  # Wrong unit
        radius = Quantity(Decimal("1"), Unit.MM)

        with pytest.raises(SurfaceRoughnessError) as exc_info:
            SurfaceRoughnessInput(
                feed_per_tooth=fz_wrong,
                effective_radius=radius,
                model_type=RoughnessModelType.IDEAL_FEED_MARK,
            )
        assert "must be in mm" in str(exc_info.value)

    def test_input_validation_wrong_units_scallop(self):
        """Test Case F2: Reject wrong units for stepover."""
        ae_wrong = Quantity(Decimal("2"), "inches")  # Wrong unit
        radius = Quantity(Decimal("10"), Unit.MM)

        with pytest.raises(SurfaceRoughnessError):
            SurfaceRoughnessInput(
                stepover=ae_wrong,
                effective_radius=radius,
                model_type=RoughnessModelType.IDEAL_SCALLOP,
            )

    def test_input_validation_missing_feed_mark_geometry(self):
        """Test Case F3: Missing feed_per_tooth for IDEAL_FEED_MARK."""
        radius = Quantity(Decimal("1"), Unit.MM)

        with pytest.raises(SurfaceRoughnessError) as exc_info:
            SurfaceRoughnessInput(
                effective_radius=radius, model_type=RoughnessModelType.IDEAL_FEED_MARK
            )
        assert "feed_per_tooth required" in str(exc_info.value)

    def test_input_validation_missing_scallop_geometry(self):
        """Test Case F4: Missing stepover for IDEAL_SCALLOP."""
        radius = Quantity(Decimal("10"), Unit.MM)

        with pytest.raises(SurfaceRoughnessError):
            SurfaceRoughnessInput(
                effective_radius=radius, model_type=RoughnessModelType.IDEAL_SCALLOP
            )

    def test_input_validation_unsupported_model(self):
        """Test Case F5: Unsupported model type."""
        radius = Quantity(Decimal("1"), Unit.MM)

        with pytest.raises(SurfaceRoughnessError) as exc_info:
            SurfaceRoughnessInput(effective_radius=radius, model_type=RoughnessModelType.EMPIRICAL)
        assert "EMPIRICAL model not yet implemented" in str(exc_info.value)


# ============================================================================
# GROUP G: TRACEABILITY (Metadata)
# ============================================================================


class TestTraceability:
    """Verify result traceability and metadata."""

    def test_feed_mark_result_metadata(self):
        """Test Case G1: IDEAL_FEED_MARK result includes all metadata."""
        input_spec = SurfaceRoughnessInput(
            feed_per_tooth=Quantity(Decimal("0.10"), Unit.MM),
            effective_radius=Quantity(Decimal("1"), Unit.MM),
            model_type=RoughnessModelType.IDEAL_FEED_MARK,
        )

        result = compute_surface_roughness(input_spec)

        assert result.Ra is not None
        assert result.Rq is not None
        assert result.Rz is None  # Not implemented yet
        assert result.model_name == "IdealFeedMark"
        assert result.model_type == RoughnessModelType.IDEAL_FEED_MARK
        assert result.Ra_derivable is True
        assert result.Rq_derivable is True
        assert result.status == "THEORETICAL_GEOMETRIC"
        assert len(result.assumptions) > 0
        assert "triangular" in result.assumptions.lower()

    def test_scallop_result_metadata(self):
        """Test Case G2: IDEAL_SCALLOP result includes all metadata."""
        input_spec = SurfaceRoughnessInput(
            stepover=Quantity(Decimal("2"), Unit.MM),
            effective_radius=Quantity(Decimal("10"), Unit.MM),
            model_type=RoughnessModelType.IDEAL_SCALLOP,
        )

        result = compute_surface_roughness(input_spec)

        assert result.Ra is not None
        assert result.Rq is not None
        assert result.model_name == "IdealScallop"
        assert result.model_type == RoughnessModelType.IDEAL_SCALLOP
        assert result.status == "THEORETICAL_GEOMETRIC"
        assert "cusp" in result.assumptions.lower() or "scallop" in result.assumptions.lower()


# ============================================================================
# GROUP H: VP100 BLOCKAGE AUDIT
# ============================================================================


class TestVP100Audit:
    """Verify VP100 inputs are insufficient for roughness calculation."""

    def test_vp100_audit_missing_inputs(self):
        """Test Case H1: VP100_AUDIT reports required geometry."""
        assert VP100_AUDIT["VP100_RQ_DIRECTLY_COMPUTABLE"] is False

        required = VP100_AUDIT["VP100_RQ_MISSING_INPUTS"]
        assert "tool_diameter" in str(required).lower() or "tool_radius" in str(required).lower()
        assert "stepover" in str(required).lower() or "ae" in str(required).lower()
        assert len(required) >= 3

    def test_vp100_audit_status(self):
        """Test Case H2: VP100_RQ_STATUS is BLOCKED."""
        assert "BLOCKED" in VP100_AUDIT["VP100_RQ_STATUS"]

    def test_vp100_roughness_not_derivable_without_geometry(self):
        """Test Case H3: Verify practical blockage (no silent defaults)."""
        # Create input with only VP100-typical data (hypothetical)
        # In practice, VP100 provides Vc, feed, depth.
        # We can't compute roughness without radius/stepover.

        # Attempt to compute without geometry should fail
        with pytest.raises(SurfaceRoughnessError):
            # Missing tool geometry
            SurfaceRoughnessInput(
                model_type=RoughnessModelType.IDEAL_FEED_MARK
                # No feed_per_tooth or effective_radius
            )


# ============================================================================
# INTEGRATION TEST
# ============================================================================


class TestIntegration:
    """End-to-end workflow tests."""

    def test_full_workflow_feed_mark(self):
        """Test Case I1: Complete feed-mark workflow."""
        # Create input
        input_spec = SurfaceRoughnessInput(
            feed_per_tooth=Quantity(Decimal("0.10"), Unit.MM),
            effective_radius=Quantity(Decimal("1"), Unit.MM),
            model_type=RoughnessModelType.IDEAL_FEED_MARK,
        )

        # Compute
        result = compute_surface_roughness(input_spec)

        # Verify output
        assert result.Ra.value == Decimal("0.000625")
        assert result.Ra.unit in (Unit.MM, "mm")
        assert result.Rq.value > result.Ra.value
        assert result.Ra_derivable is True
        assert result.Rq_derivable is True

    def test_full_workflow_scallop(self):
        """Test Case I2: Complete scallop workflow."""
        input_spec = SurfaceRoughnessInput(
            stepover=Quantity(Decimal("2"), Unit.MM),
            effective_radius=Quantity(Decimal("10"), Unit.MM),
            model_type=RoughnessModelType.IDEAL_SCALLOP,
        )

        result = compute_surface_roughness(input_spec)

        assert result.Ra.value == Decimal("0.025")
        assert result.Ra.unit in (Unit.MM, "mm")
        assert result.Rq.value > result.Ra.value


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
