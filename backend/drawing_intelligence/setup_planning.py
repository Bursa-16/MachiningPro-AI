"""Advanced Datum Setup Planning (EPIC_04B Phase 2).

Generates SetupPlanHint from DRF and GD&T requirements.

Deterministic: no AI inference.
FABRICATED_DATUM=NO
"""

from __future__ import annotations

from backend.drawing_intelligence.requirements import (
    DatumReferenceFrame,
    DrawingRequirementSet,
    GdtCharacteristic,
    SetupPlanHint,
)

__all__ = [
    "SetupPlanner",
    "build_setup_hints",
]

_RUNOUT_CHARS = frozenset({
    GdtCharacteristic.CIRCULAR_RUNOUT,
    GdtCharacteristic.TOTAL_RUNOUT,
})

_TIGHT_POSITION_MM = 0.05  # Position tighter than this triggers same-setup preference


class SetupPlanner:
    """Generates bounded setup planning hints from DRF and GD&T requirements."""

    def plan(
        self,
        req_set: DrawingRequirementSet,
        drf: DatumReferenceFrame | None = None,
    ) -> SetupPlanHint:
        same_setup: list[str] = []
        warnings: list[str] = []

        primary_label = ""
        primary_note = ""
        secondary_label = None
        secondary_note = None
        tertiary_label = None
        tertiary_note = None

        if drf is not None:
            primary_label = drf.primary.label
            primary_note = _datum_setup_note(primary_label, "primary")

            if drf.secondary is not None:
                secondary_label = drf.secondary.label
                secondary_note = _datum_setup_note(secondary_label, "secondary")

            if drf.tertiary is not None:
                tertiary_label = drf.tertiary.label
                tertiary_note = _datum_setup_note(tertiary_label, "tertiary")

        # Collect same-setup requirements
        for geom in req_set.geometric:
            fcf = geom.fcf
            char = fcf.characteristic

            # Runout: all runout-controlled features must share one setup
            if char in _RUNOUT_CHARS:
                same_setup.append(geom.req_id)
                if char == GdtCharacteristic.TOTAL_RUNOUT:
                    warnings.append(
                        f"TOTAL_RUNOUT {geom.req_id}: all controlled surfaces must be "
                        "processed in one chucking about the datum axis"
                    )

            # Tight position: prefer same setup
            if char == GdtCharacteristic.POSITION:
                from decimal import Decimal
                if fcf.tolerance_value < Decimal(str(_TIGHT_POSITION_MM)):
                    same_setup.append(geom.req_id)

        # Determine primary label from geometric requirements if no DRF provided
        if not primary_label and req_set.geometric:
            for geom in req_set.geometric:
                if geom.fcf.datum_frame is not None:
                    primary_label = geom.fcf.datum_frame.primary.label
                    primary_note = _datum_setup_note(primary_label, "primary")
                    if geom.fcf.datum_frame.secondary:
                        secondary_label = geom.fcf.datum_frame.secondary.label
                        secondary_note = _datum_setup_note(secondary_label, "secondary")
                    if geom.fcf.datum_frame.tertiary:
                        tertiary_label = geom.fcf.datum_frame.tertiary.label
                        tertiary_note = _datum_setup_note(tertiary_label, "tertiary")
                    break

        return SetupPlanHint(
            source_id=req_set.source_id,
            primary_datum_label=primary_label or "UNKNOWN",
            primary_setup_note=primary_note or "Primary datum to be established first",
            secondary_datum_label=secondary_label,
            secondary_setup_note=secondary_note,
            tertiary_datum_label=tertiary_label,
            tertiary_setup_note=tertiary_note,
            same_setup_requirements=tuple(sorted(set(same_setup))),
            access_warnings=tuple(warnings),
        )


def _datum_setup_note(label: str, precedence: str) -> str:
    notes = {
        "primary": (
            f"Datum {label} (primary): establish reference surface first. "
            "Constrains translation and two rotations."
        ),
        "secondary": (
            f"Datum {label} (secondary): locate center axis after primary. "
            "Constrains remaining translations."
        ),
        "tertiary": (
            f"Datum {label} (tertiary): clocking datum — constrains final rotation (Rz)."
        ),
    }
    return notes.get(precedence, f"Datum {label} ({precedence})")


def build_setup_hints(
    req_set: DrawingRequirementSet,
    drf: DatumReferenceFrame | None = None,
) -> SetupPlanHint:
    """Convenience function."""
    return SetupPlanner().plan(req_set, drf)
