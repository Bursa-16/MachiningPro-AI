"""Manufacturing note classifier for drawing text annotations.

Applies deterministic keyword rules to categorize drawing notes.
Free-form notes without a matching rule → OTHER category.

FABRICATED_NOTE=NO
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum, unique


@unique
class NoteCategory(StrEnum):
    DEBURR = "DEBURR"
    BREAK_EDGE = "BREAK_EDGE"
    HEAT_TREAT = "HEAT_TREAT"
    HARDNESS = "HARDNESS"
    COATING = "COATING"
    PLATING = "PLATING"
    CLEANLINESS = "CLEANLINESS"
    GENERAL_TOLERANCE = "GENERAL_TOLERANCE"
    INSPECTION = "INSPECTION"
    MARKING = "MARKING"
    MATERIAL = "MATERIAL"
    WELDING = "WELDING"
    PROCESS = "PROCESS"
    OTHER = "OTHER"


@dataclass(frozen=True)
class ClassifiedNote:
    raw_text: str
    category: NoteCategory
    matched_rule: str | None  # Rule ID that triggered this category
    requires_review: bool     # True for OTHER or low-confidence matches


_RULES: list[tuple[str, re.Pattern[str], NoteCategory]] = [
    ("DEBURR-1", re.compile(r"\bDEBURR\b", re.IGNORECASE), NoteCategory.DEBURR),
    (
        "BREAK-EDGE-1",
        re.compile(r"\bBREAK\s*(?:ALL\s*)?SHARP\s*EDGES?\b", re.IGNORECASE),
        NoteCategory.BREAK_EDGE,
    ),
    (
        "BREAK-EDGE-2",
        re.compile(r"\bSHARP\s*EDGES?\s*(?:TO\s*BE\s*)?(?:REMOVED|BROKEN)\b", re.IGNORECASE),
        NoteCategory.BREAK_EDGE,
    ),
    (
        "HEAT-TREAT-1",
        re.compile(r"\bHEAT\s*TREAT(?:MENT)?\b", re.IGNORECASE),
        NoteCategory.HEAT_TREAT,
    ),
    (
        "HEAT-TREAT-2",
        re.compile(  # noqa: E501
            r"\bHARDEN\b|\bCASE\s*HARDEN\b|\bCARBURIZE\b|\bNITRIDE\b"
            r"|\bANNEAL\b|\bNORMALIZE\b|\bQUENCH\b|\bTEMPER\b",
            re.IGNORECASE,
        ),
        NoteCategory.HEAT_TREAT,
    ),
    (
        "HARDNESS-1",
        re.compile(r"\b(?:HRC|HRB|HV|HB|HARDNESS)\s*\d", re.IGNORECASE),
        NoteCategory.HARDNESS,
    ),
    (
        "COATING-1",
        re.compile(
            r"\bANODIZ(?:E|ING)\b|\bPOWDER\s*COAT\b|\bPAINT\b"
            r"|\bPRIMER\b|\bCOAT(?:ING)?\b",
            re.IGNORECASE,
        ),
        NoteCategory.COATING,
    ),
    (
        "PLATING-1",
        re.compile(
            r"\bZINC\s*PLATE\b|\bCHROME\s*PLATE\b|\bNICKEL\s*PLATE\b"
            r"|\bPLATE(?:D)?\b|\bPLATING\b",
            re.IGNORECASE,
        ),
        NoteCategory.PLATING,
    ),
    (
        "CLEAN-1",
        re.compile(r"\bCLEAN(?:LINESS)?\b|\bDEGREASE\b|\bWASH\b", re.IGNORECASE),
        NoteCategory.CLEANLINESS,
    ),
    (
        "GENTOL-1",
        re.compile(r"\bISO\s*2768\b|\bGENERAL\s*TOL(?:ERANCE)?\b", re.IGNORECASE),
        NoteCategory.GENERAL_TOLERANCE,
    ),
    (
        "GENTOL-2",
        re.compile(r"\bUNLESS\s*OTHERWISE\s*STATED\b|\bUNLESS\s*NOTED\b", re.IGNORECASE),
        NoteCategory.GENERAL_TOLERANCE,
    ),
    (
        "INSPECT-1",
        re.compile(
            r"\bINSPECT\b|\bCMM\b|\bGAUGE\b|\bGAGE\b|\bINSPECTION\b|\bVERIFY\b",
            re.IGNORECASE,
        ),
        NoteCategory.INSPECTION,
    ),
    (
        "MARKING-1",
        re.compile(
            r"\bMARK\b|\bSTAMP\b|\bENGRAVE\b|\bLASER\s*MARK\b|\bIDENTIFY\b|\bLABEL\b",
            re.IGNORECASE,
        ),
        NoteCategory.MARKING,
    ),
    (
        "MATERIAL-1",
        re.compile(r"\bMATERIAL\b|\bALLOY\b|\bGRADE\b", re.IGNORECASE),
        NoteCategory.MATERIAL,
    ),
    (
        "WELD-1",
        re.compile(r"\bWELD\b|\bBRAZE\b|\bSOLDER\b|\bFUSION\b", re.IGNORECASE),
        NoteCategory.WELDING,
    ),
    (
        "PROCESS-1",
        re.compile(
            r"\bTOLERANCE\b|\bFINISH\b|\bSURFACE\b|\bDRILL\b|\bREAM\b"
            r"|\bBORE\b|\bGRIND\b|\bMILL\b|\bTURN\b",
            re.IGNORECASE,
        ),
        NoteCategory.PROCESS,
    ),
]


def classify_note(raw_text: str) -> ClassifiedNote:
    """Classify a single drawing note by deterministic keyword rules."""
    text = raw_text.strip()
    if not text:
        return ClassifiedNote(
            raw_text=raw_text,
            category=NoteCategory.OTHER,
            matched_rule=None,
            requires_review=True,
        )

    for rule_id, pattern, category in _RULES:
        if pattern.search(text):
            return ClassifiedNote(
                raw_text=raw_text,
                category=category,
                matched_rule=rule_id,
                requires_review=False,
            )

    return ClassifiedNote(
        raw_text=raw_text,
        category=NoteCategory.OTHER,
        matched_rule=None,
        requires_review=True,
    )


def classify_notes(texts: list[str]) -> list[ClassifiedNote]:
    """Classify a list of drawing note strings."""
    return [classify_note(t) for t in texts]
