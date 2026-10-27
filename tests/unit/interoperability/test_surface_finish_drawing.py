"""Unit tests for surface finish annotation parser."""

import pytest
from decimal import Decimal

from backend.interoperability.surface_finish_drawing import (
    SurfaceFinishCallout,
    SurfaceFinishParameter,
    parse_surface_finish_token,
    parse_surface_finish_tokens,
)


class TestRaParser:
    def test_ra_with_space(self):
        sf = parse_surface_finish_token("Ra 1.6")
        assert sf is not None
        assert sf.parameter == SurfaceFinishParameter.Ra
        assert sf.value == Decimal("1.6")

    def test_ra_compact(self):
        sf = parse_surface_finish_token("Ra3.2")
        assert sf is not None
        assert sf.parameter == SurfaceFinishParameter.Ra
        assert sf.value == Decimal("3.2")

    def test_ra_unit_um(self):
        sf = parse_surface_finish_token("Ra 1.6 µm")
        assert sf.unit == "µm"

    def test_ra_unit_um_ascii(self):
        sf = parse_surface_finish_token("Ra 1.6 um")
        assert sf.unit == "µm"  # normalized

    def test_ra_unit_uin(self):
        sf = parse_surface_finish_token("Ra 63 µin")
        assert sf.unit == "µin"

    def test_ra_no_unit_defaults_um(self):
        sf = parse_surface_finish_token("Ra 1.6")
        assert sf.unit == "µm"

    def test_ra_0_8(self):
        sf = parse_surface_finish_token("Ra 0.8")
        assert sf.value == Decimal("0.8")

    def test_ra_6_3(self):
        sf = parse_surface_finish_token("Ra 6.3")
        assert sf.value == Decimal("6.3")

    def test_ra_12_5(self):
        sf = parse_surface_finish_token("Ra 12.5")
        assert sf.value == Decimal("12.5")

    def test_ra_comma_decimal(self):
        sf = parse_surface_finish_token("Ra 1,6")
        assert sf is not None
        assert sf.value == Decimal("1.6")


class TestRzRtRmax:
    def test_rz(self):
        sf = parse_surface_finish_token("Rz 6.3")
        assert sf is not None
        assert sf.parameter == SurfaceFinishParameter.Rz

    def test_rt(self):
        sf = parse_surface_finish_token("Rt 12.5")
        assert sf is not None
        assert sf.parameter == SurfaceFinishParameter.Rt

    def test_rmax(self):
        sf = parse_surface_finish_token("Rmax 25")
        assert sf is not None
        assert sf.parameter == SurfaceFinishParameter.Rmax

    def test_rz_compact(self):
        sf = parse_surface_finish_token("Rz6.3")
        assert sf is not None
        assert sf.parameter == SurfaceFinishParameter.Rz

    def test_rmax_compact(self):
        sf = parse_surface_finish_token("Rmax25")
        assert sf is not None
        assert sf.parameter == SurfaceFinishParameter.Rmax


class TestMachiningSymbols:
    def test_machining_required_checkmark(self):
        sf = parse_surface_finish_token("√")
        assert sf is not None
        assert sf.parameter == SurfaceFinishParameter.MACHINING_REQUIRED

    def test_machining_required_down_triangle(self):
        sf = parse_surface_finish_token("∇")
        assert sf is not None
        assert sf.parameter == SurfaceFinishParameter.MACHINING_REQUIRED

    def test_machining_required_value_none(self):
        sf = parse_surface_finish_token("√")
        assert sf.value is None
        assert sf.unit is None

    def test_machining_prohibited_text(self):
        sf = parse_surface_finish_token("NO MACHINING")
        assert sf is not None
        assert sf.parameter == SurfaceFinishParameter.MACHINING_PROHIBITED

    def test_machining_prohibited_text2(self):
        sf = parse_surface_finish_token("MACHINING PROHIBITED")
        assert sf is not None
        assert sf.parameter == SurfaceFinishParameter.MACHINING_PROHIBITED


class TestNonSurfaceFinishTokens:
    @pytest.mark.parametrize("token", [
        "H7", "M10x1.5", "DEBURR", "25.0", "", "  ", "ISO 2768-m",
        "ABC123", "G1/2",
    ])
    def test_returns_none(self, token):
        assert parse_surface_finish_token(token) is None


class TestParseSurfaceFinishTokensList:
    def test_multiple_tokens(self):
        tokens = ["Ra 1.6", "NOT_SF", "Rz 3.2", "√"]
        results = parse_surface_finish_tokens(tokens)
        assert len(results) == 3

    def test_empty_list(self):
        assert parse_surface_finish_tokens([]) == []

    def test_all_invalid(self):
        assert parse_surface_finish_tokens(["H7", "M10", "DEBURR"]) == []


class TestRawTextPreserved:
    def test_raw_text_ra_with_space(self):
        sf = parse_surface_finish_token("Ra 1.6")
        assert sf.raw_text == "Ra 1.6"

    def test_raw_text_compact(self):
        sf = parse_surface_finish_token("Ra3.2")
        assert sf.raw_text == "Ra3.2"

    def test_raw_text_machining_required(self):
        sf = parse_surface_finish_token("√")
        assert sf.raw_text == "√"


class TestFabricatedSurfaceFinish:
    """FABRICATED_SURFACE_FINISH=NO — only values explicitly parsed."""

    def test_value_not_inferred_without_number(self):
        sf = parse_surface_finish_token("Ra")
        assert sf is None  # Ra alone is not a valid callout

    def test_machining_prohibited_value_is_none(self):
        sf = parse_surface_finish_token("NO MACHINING")
        assert sf.value is None
