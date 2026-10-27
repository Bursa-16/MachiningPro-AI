"""Unit tests for thread callout parser."""

import pytest
from decimal import Decimal

from backend.interoperability.thread_drawing import (
    ThreadCallout,
    ThreadOrientation,
    ThreadStandard,
    parse_thread_token,
    parse_thread_tokens,
)


class TestMetricThreads:
    def test_m10_basic(self):
        tc = parse_thread_token("M10")
        assert tc is not None
        assert tc.standard == ThreadStandard.METRIC
        assert tc.nominal_raw == "10"
        assert tc.nominal_mm == Decimal("10")

    def test_m10_coarse_pitch_inferred(self):
        tc = parse_thread_token("M10")
        assert tc.pitch_mm == Decimal("1.5")

    def test_m10_explicit_pitch(self):
        tc = parse_thread_token("M10x1.5")
        assert tc.pitch_mm == Decimal("1.5")
        assert tc.nominal_mm == Decimal("10")

    def test_m10_fine_pitch(self):
        tc = parse_thread_token("M10x1.0")
        assert tc.pitch_mm == Decimal("1.0")

    def test_m10_x1_5_6h_tolerance(self):
        tc = parse_thread_token("M10x1.5-6H")
        assert tc.tolerance_class == "6H"
        assert tc.orientation == ThreadOrientation.INTERNAL

    def test_m6_external_tolerance(self):
        tc = parse_thread_token("M6-6g")
        assert tc.tolerance_class == "6g"
        assert tc.orientation == ThreadOrientation.EXTERNAL

    def test_m3_small_size(self):
        tc = parse_thread_token("M3")
        assert tc is not None
        assert tc.nominal_mm == Decimal("3")
        assert tc.pitch_mm == Decimal("0.5")

    def test_m24_large_size(self):
        tc = parse_thread_token("M24")
        assert tc.nominal_mm == Decimal("24")
        assert tc.pitch_mm == Decimal("3.0")

    def test_m10_uppercase_x(self):
        tc = parse_thread_token("M10X1.5")
        assert tc is not None
        assert tc.pitch_mm == Decimal("1.5")

    def test_metric_unicode_times(self):
        tc = parse_thread_token("M10×1.5")
        assert tc is not None
        assert tc.pitch_mm == Decimal("1.5")

    def test_metric_comma_decimal(self):
        tc = parse_thread_token("M10x1,5")
        assert tc is not None
        assert tc.pitch_mm == Decimal("1.5")

    def test_metric_thru_suffix_not_parsed(self):
        # "M8 THRU" — THRU suffix is not consumed by the metric regex
        tc = parse_thread_token("M8 THRU")
        # Current implementation: metric regex ends with \s*$ so "M8 THRU" does not match
        assert tc is None

    def test_metric_basic_no_depth(self):
        # Depth is extracted from suffix; for clean M6, depth_mm is None
        tc = parse_thread_token("M6")
        assert tc is not None
        assert tc.depth_mm is None

    def test_m5_coarse_pitch(self):
        tc = parse_thread_token("M5")
        assert tc.pitch_mm == Decimal("0.8")

    def test_m1_coarse_pitch(self):
        tc = parse_thread_token("M1")
        assert tc.pitch_mm == Decimal("0.25")

    def test_nominal_mm_is_decimal(self):
        tc = parse_thread_token("M10")
        assert isinstance(tc.nominal_mm, Decimal)


class TestUncUnfThreads:
    def test_unc_quarter_20(self):
        tc = parse_thread_token("1/4-20 UNC")
        assert tc is not None
        assert tc.standard == ThreadStandard.UNC
        assert tc.nominal_raw == "1/4"
        assert tc.nominal_mm is None  # inch system, no fabricated mm

    def test_unf_quarter_28(self):
        tc = parse_thread_token("1/4-28 UNF")
        assert tc is not None
        assert tc.standard == ThreadStandard.UNF
        assert tc.nominal_mm is None

    def test_unc_no_mm_conversion(self):
        """FABRICATED_THREAD=NO — UNC stays as inch, no mm conversion."""
        tc = parse_thread_token("3/4-10 UNC")
        assert tc.nominal_mm is None

    def test_hash_number_unc(self):
        tc = parse_thread_token("#10-32 UNF")
        assert tc is not None
        assert tc.standard == ThreadStandard.UNF

    def test_unc_tolerance_class(self):
        tc = parse_thread_token("1/4-20 UNC - 2A")
        assert tc is not None

    def test_unef_standard(self):
        tc = parse_thread_token("1/4-32 UNEF")
        assert tc is not None
        assert tc.standard == ThreadStandard.UNEF


class TestBspThreads:
    def test_g_half_bsp(self):
        tc = parse_thread_token("G1/2")
        assert tc is not None
        assert tc.standard == ThreadStandard.BSP

    def test_r_threeeighths_bspt(self):
        tc = parse_thread_token("R3/8")
        assert tc is not None
        assert tc.standard == ThreadStandard.BSPT

    def test_bsp_nominal_mm_none(self):
        tc = parse_thread_token("G3/4")
        assert tc.nominal_mm is None


class TestNptThreads:
    def test_npt_quarter(self):
        tc = parse_thread_token("1/4 NPT")
        assert tc is not None
        assert tc.standard == ThreadStandard.NPT

    def test_nptf_threequarter(self):
        tc = parse_thread_token("3/4 NPTF")
        assert tc is not None
        assert tc.standard == ThreadStandard.NPTF

    def test_npt_nominal_mm_none(self):
        tc = parse_thread_token("1/2 NPT")
        assert tc.nominal_mm is None


class TestNonThreadTokens:
    @pytest.mark.parametrize("token", [
        "H7", "Ra 1.6", "DEBURR", "25.0", "", "  ", "ABC123", "ISO 2768-m",
    ])
    def test_returns_none(self, token):
        assert parse_thread_token(token) is None


class TestParseThreadTokensList:
    def test_multiple_tokens(self):
        tokens = ["M10x1.5", "G1/2", "NOT_THREAD", "M6"]
        results = parse_thread_tokens(tokens)
        assert len(results) == 3

    def test_empty_list(self):
        assert parse_thread_tokens([]) == []

    def test_all_invalid(self):
        assert parse_thread_tokens(["H7", "Ra3.2", "DEBURR"]) == []


class TestFabricatedThread:
    """FABRICATED_THREAD=NO — verify no geometry is fabricated."""

    def test_unc_pitch_mm_is_none(self):
        tc = parse_thread_token("1/4-20 UNC")
        assert tc.pitch_mm is None

    def test_bsp_nominal_mm_is_none(self):
        tc = parse_thread_token("G1/2")
        assert tc.nominal_mm is None

    def test_npt_nominal_mm_is_none(self):
        tc = parse_thread_token("1/4 NPT")
        assert tc.nominal_mm is None
