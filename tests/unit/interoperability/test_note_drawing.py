"""Unit tests for manufacturing note classifier."""

import pytest

from backend.interoperability.note_drawing import (
    ClassifiedNote,
    NoteCategory,
    classify_note,
    classify_notes,
)


class TestDeburr:
    def test_deburr_simple(self):
        note = classify_note("DEBURR ALL EDGES")
        assert note.category == NoteCategory.DEBURR

    def test_deburr_case_insensitive(self):
        note = classify_note("deburr after machining")
        assert note.category == NoteCategory.DEBURR

    def test_deburr_requires_no_review(self):
        note = classify_note("DEBURR")
        assert not note.requires_review

    def test_deburr_matched_rule_set(self):
        note = classify_note("DEBURR")
        assert note.matched_rule == "DEBURR-1"


class TestBreakEdge:
    @pytest.mark.parametrize("text", [
        "BREAK ALL SHARP EDGES",
        "break all sharp edges",
        "BREAK SHARP EDGES",
        "SHARP EDGES TO BE REMOVED",
        "SHARP EDGE REMOVED",
        "SHARP EDGES BROKEN",
    ])
    def test_break_edge_variants(self, text):
        note = classify_note(text)
        assert note.category == NoteCategory.BREAK_EDGE

    def test_break_edge_requires_no_review(self):
        note = classify_note("BREAK ALL SHARP EDGES")
        assert not note.requires_review


class TestHeatTreat:
    @pytest.mark.parametrize("text", [
        "HEAT TREAT TO 58-62 HRC",
        "heat treatment required",
        "HARDEN AND TEMPER",
        "CASE HARDEN",
        "CARBURIZE",
        "NITRIDE",
        "ANNEAL",
        "NORMALIZE",
        "QUENCH",
        "TEMPER",
    ])
    def test_heat_treat_variants(self, text):
        note = classify_note(text)
        assert note.category in (NoteCategory.HEAT_TREAT, NoteCategory.HARDNESS)


class TestHardness:
    @pytest.mark.parametrize("text", [
        "HARDNESS 58 HRC MIN",
        "HRC 60",
        "HRB 80",
        "HV 300",
        "HB 200",
        "HARDNESS 200 HB",
    ])
    def test_hardness_variants(self, text):
        note = classify_note(text)
        assert note.category == NoteCategory.HARDNESS


class TestCoating:
    @pytest.mark.parametrize("text", [
        "ANODIZE PER MIL-A-8625",
        "ANODIZING REQUIRED",
        "POWDER COAT RAL 9005",
        "PAINT",
        "PRIMER COAT",
        "COATING REQUIRED",
    ])
    def test_coating_variants(self, text):
        note = classify_note(text)
        assert note.category == NoteCategory.COATING


class TestPlating:
    @pytest.mark.parametrize("text", [
        "ZINC PLATE PER ASTM B633",
        "CHROME PLATE",
        "NICKEL PLATE",
        "PLATED",
        "PLATING REQUIRED",
    ])
    def test_plating_variants(self, text):
        note = classify_note(text)
        assert note.category == NoteCategory.PLATING


class TestCleanliness:
    @pytest.mark.parametrize("text", [
        "CLEAN ALL MACHINED SURFACES",
        "CLEANLINESS CLASS 10",
        "DEGREASE BEFORE ASSEMBLY",
        "WASH WITH SOLVENT",
    ])
    def test_cleanliness_variants(self, text):
        note = classify_note(text)
        assert note.category == NoteCategory.CLEANLINESS


class TestGeneralTolerance:
    @pytest.mark.parametrize("text", [
        "ISO 2768 MEDIUM",
        "ISO 2768-m",
        "GENERAL TOLERANCE ISO 2768",
        "GENERAL TOL ±0.1",
        "UNLESS OTHERWISE STATED",
        "UNLESS NOTED",
    ])
    def test_general_tolerance_variants(self, text):
        note = classify_note(text)
        assert note.category == NoteCategory.GENERAL_TOLERANCE


class TestInspection:
    @pytest.mark.parametrize("text", [
        "INSPECT ALL CRITICAL DIMENSIONS",
        "CMM REQUIRED",
        "GAUGE BEFORE ASSEMBLY",
        "GAGE DIAMETER",
        "INSPECTION REQUIRED",
        "VERIFY DIMENSIONS",
    ])
    def test_inspection_variants(self, text):
        note = classify_note(text)
        assert note.category == NoteCategory.INSPECTION


class TestMarking:
    @pytest.mark.parametrize("text", [
        "MARK PART NUMBER",
        "STAMP SERIAL NUMBER",
        "ENGRAVE AS SHOWN",
        "LASER MARK",
        "IDENTIFY WITH LOT NUMBER",
        "LABEL PER DWG",
    ])
    def test_marking_variants(self, text):
        note = classify_note(text)
        assert note.category == NoteCategory.MARKING


class TestMaterial:
    @pytest.mark.parametrize("text", [
        "MATERIAL: AISI 4140",
        "ALLOY PER SPEC",
        "GRADE 316L SS",
    ])
    def test_material_variants(self, text):
        note = classify_note(text)
        assert note.category == NoteCategory.MATERIAL


class TestWelding:
    @pytest.mark.parametrize("text", [
        "WELD PER AWS D1.1",
        "BRAZE WITH SILVER SOLDER",
        "SOLDER CONNECTIONS",
        "FUSION WELD",
    ])
    def test_welding_variants(self, text):
        note = classify_note(text)
        assert note.category == NoteCategory.WELDING


class TestOtherCategory:
    def test_unknown_text_returns_other(self):
        note = classify_note("SOME RANDOM NOTE NOT MATCHING ANYTHING")
        assert note.category == NoteCategory.OTHER

    def test_other_requires_review(self):
        note = classify_note("XYZZY FROB NOZZLE")
        assert note.requires_review is True

    def test_other_matched_rule_none(self):
        note = classify_note("UNKNOWN NOTE")
        assert note.matched_rule is None

    def test_empty_text_returns_other(self):
        note = classify_note("")
        assert note.category == NoteCategory.OTHER
        assert note.requires_review is True

    def test_whitespace_only_returns_other(self):
        note = classify_note("   ")
        assert note.category == NoteCategory.OTHER


class TestClassifyNotesList:
    def test_multiple_notes(self):
        texts = ["DEBURR", "HEAT TREAT", "SOME RANDOM TEXT"]
        results = classify_notes(texts)
        assert len(results) == 3
        assert results[0].category == NoteCategory.DEBURR
        assert results[1].category == NoteCategory.HEAT_TREAT
        assert results[2].category == NoteCategory.OTHER

    def test_empty_list(self):
        assert classify_notes([]) == []

    def test_raw_text_preserved(self):
        results = classify_notes(["DEBURR ALL EDGES"])
        assert results[0].raw_text == "DEBURR ALL EDGES"
