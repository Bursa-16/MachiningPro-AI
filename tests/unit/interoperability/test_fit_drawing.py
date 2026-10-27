"""Unit tests for ISO 286-1 fit callout parser."""

import pytest
from decimal import Decimal

from backend.interoperability.fit_drawing import (
    FitCallout,
    FitClass,
    FitParseStatus,
    parse_fit_token,
    parse_fit_tokens,
)


class TestFitClass:
    def test_hole_uppercase_deviation(self):
        _, callouts = parse_fit_token("H7")
        assert callouts[0].fit_class == FitClass.HOLE

    def test_shaft_lowercase_deviation(self):
        _, callouts = parse_fit_token("g6")
        assert callouts[0].fit_class == FitClass.SHAFT

    def test_js7_deviation_uppercase_start(self):
        _, callouts = parse_fit_token("JS7")
        assert callouts[0].fit_class == FitClass.HOLE

    def test_f8_uppercase(self):
        _, callouts = parse_fit_token("F8")
        assert callouts[0].fit_class == FitClass.HOLE

    def test_k5_lowercase(self):
        _, callouts = parse_fit_token("k5")
        assert callouts[0].fit_class == FitClass.SHAFT


class TestParseSingleFit:
    @pytest.mark.parametrize("token,expected_code,expected_grade", [
        ("H7", "H7", 7),
        ("g6", "g6", 6),
        ("JS7", "JS7", 7),
        ("H11", "H11", 11),
        ("h6", "h6", 6),
        ("F8", "F8", 8),
        ("k5", "k5", 5),
        ("n6", "n6", 6),
        ("p6", "p6", 6),
        ("r5", "r5", 5),
        ("s6", "s6", 6),
        ("u6", "u6", 6),
    ])
    def test_valid_fit_codes(self, token, expected_code, expected_grade):
        status, callouts = parse_fit_token(token)
        assert status == FitParseStatus.PARSED
        assert len(callouts) == 1
        assert callouts[0].fit_code == expected_code
        assert callouts[0].grade == expected_grade

    def test_whitespace_stripped(self):
        status, callouts = parse_fit_token("  H7  ")
        assert status == FitParseStatus.PARSED
        assert callouts[0].fit_code == "H7"

    def test_raw_text_preserved(self):
        _, callouts = parse_fit_token("H7")
        assert callouts[0].raw_text == "H7"

    def test_grade_zero(self):
        status, _ = parse_fit_token("H0")
        assert status == FitParseStatus.PARSED

    def test_grade_18(self):
        status, _ = parse_fit_token("H18")
        assert status == FitParseStatus.PARSED

    def test_grade_19_invalid(self):
        status, callouts = parse_fit_token("H19")
        assert status == FitParseStatus.NO_FIT

    def test_empty_token(self):
        status, callouts = parse_fit_token("")
        assert status == FitParseStatus.NO_FIT
        assert callouts == []

    def test_non_fit_token(self):
        status, callouts = parse_fit_token("DEBURR ALL SHARP EDGES")
        assert status == FitParseStatus.NO_FIT

    def test_number_only(self):
        status, callouts = parse_fit_token("25")
        assert status == FitParseStatus.NO_FIT

    def test_dimension_without_fit(self):
        status, callouts = parse_fit_token("25.0")
        assert status == FitParseStatus.NO_FIT


class TestCombinedFit:
    def test_h7_g6_combined_slash(self):
        status, callouts = parse_fit_token("H7/g6")
        assert status == FitParseStatus.PARSED
        assert len(callouts) == 2
        assert callouts[0].fit_code == "H7"
        assert callouts[0].fit_class == FitClass.HOLE
        assert callouts[1].fit_code == "g6"
        assert callouts[1].fit_class == FitClass.SHAFT

    def test_h7_g6_mating_code_set(self):
        _, callouts = parse_fit_token("H7/g6")
        assert callouts[0].mating_fit_code == "g6"

    def test_combined_dash_separator(self):
        status, callouts = parse_fit_token("H7-g6")
        assert status == FitParseStatus.PARSED
        assert len(callouts) == 2

    def test_combined_raw_text_is_full(self):
        _, callouts = parse_fit_token("H7/g6")
        assert callouts[0].raw_text == "H7/g6"

    def test_f8_h7_combined(self):
        status, callouts = parse_fit_token("F8/h7")
        assert status == FitParseStatus.PARSED

    def test_combined_both_hole(self):
        status, callouts = parse_fit_token("H7/H6")
        assert status == FitParseStatus.PARSED


class TestDimensionPlusFit:
    def test_diameter_prefix_h7(self):
        status, callouts = parse_fit_token("Ø25 H7")
        assert status == FitParseStatus.PARSED
        assert len(callouts) == 1
        assert callouts[0].fit_code == "H7"
        assert callouts[0].nominal_mm == Decimal("25")

    def test_no_diameter_symbol(self):
        status, callouts = parse_fit_token("25 H7")
        assert status == FitParseStatus.PARSED
        assert callouts[0].nominal_mm == Decimal("25")

    def test_decimal_nominal(self):
        status, callouts = parse_fit_token("Ø12.5 H7")
        assert status == FitParseStatus.PARSED
        assert callouts[0].nominal_mm == Decimal("12.5")

    def test_comma_decimal_separator(self):
        status, callouts = parse_fit_token("Ø25,0 H7")
        assert status == FitParseStatus.PARSED
        assert callouts[0].nominal_mm == Decimal("25.0")

    def test_compact_no_space(self):
        status, callouts = parse_fit_token("Ø25H7")
        assert status == FitParseStatus.PARSED
        assert callouts[0].nominal_mm == Decimal("25")


class TestParseFitTokensList:
    def test_multiple_tokens(self):
        tokens = ["H7", "g6", "NOT_A_FIT", "JS7"]
        callouts = parse_fit_tokens(tokens)
        assert len(callouts) == 3
        codes = [c.fit_code for c in callouts]
        assert "H7" in codes
        assert "g6" in codes
        assert "JS7" in codes

    def test_empty_list(self):
        assert parse_fit_tokens([]) == []

    def test_all_invalid(self):
        assert parse_fit_tokens(["DEBURR", "25mm", "M10x1.5"]) == []

    def test_combined_fit_counts_as_two(self):
        callouts = parse_fit_tokens(["H7/g6"])
        assert len(callouts) == 2


class TestFabricatedFitLimits:
    """Verify FABRICATED_FIT_LIMITS=NO — no numerical limits returned."""

    def test_no_numerical_upper_limit(self):
        _, callouts = parse_fit_token("H7")
        c = callouts[0]
        assert not hasattr(c, "upper_limit_mm")
        assert not hasattr(c, "lower_limit_mm")

    def test_fit_callout_has_no_tolerance_values(self):
        _, callouts = parse_fit_token("g6")
        c = callouts[0]
        fields = {f.name for f in c.__dataclass_fields__.values()} if hasattr(c, '__dataclass_fields__') else set(vars(c).keys())
        assert "tolerance_upper_mm" not in fields
        assert "tolerance_lower_mm" not in fields
