"""VP100 dry milling empirical observation records (Stage EMPIRICAL-01A).

Source-traceable experimental data model for the VP100 kuru freze
(dry face milling) DOE dataset.

Authority model
---------------
VP100EmpiricalRecord instances carry EXPERIMENTAL evidence status.  They
represent measured observations from a controlled DOE and may be promoted
to AUTHORITATIVE after engineering sign-off.

Validation artefacts
--------------------
Columns ``Pred.*``, ``*APE``, ``*Status``, and ``Row Status`` in the source
workbook are artefacts of a prior validation run (executed when the physics
engine was not yet implemented; all results were ``NOT_IMPLEMENTED``).
They are intentionally excluded from this model and must not be ingested.

DOE structure
-------------
4 tool conditions (C0–C3, each with a different coating system)
× 8 cutting-parameter combinations (A–H, 2³ factorial: 2 Vc × 2 fz × 2 ap)
× 3 replicates
= 96 observations

Source workbook
---------------
``MachiningPro_AI_VP100_EXTERNAL_BENCHMARK.xlsx``
Sheet: ``VP100 Detailed Results``
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.cutting_parameters.models import EvidenceStatus
from backend.domain.base import (
    Provenance,
    entity_as_dict,
    require_non_empty_str,
    require_positive_quantity,
)
from backend.domain.exceptions import ValidationError
from backend.domain.units import Quantity, Unit

__all__ = [
    "VP100SourceMeta",
    "VP100EmpiricalRecord",
    "VP100_VALID_TOOL_CONDITIONS",
    "VP100_VALID_COATINGS",
    "VP100_VALID_COMBINATIONS",
]

# ---------------------------------------------------------------------------
# Controlled vocabulary
# ---------------------------------------------------------------------------

#: Tool condition labels as they appear in the source workbook.
#: C0=Uncoated, C1=TiN, C2=AlTiN, C3=AlTiN/TiSiXN.
VP100_VALID_TOOL_CONDITIONS: frozenset[str] = frozenset({"C0", "C1", "C2", "C3"})

#: Coating labels as they appear in the source workbook.
VP100_VALID_COATINGS: frozenset[str] = frozenset(
    {"Uncoated", "TiN", "AlTiN", "AlTiN/TiSiXN"}
)

#: DOE combination identifiers (2³ factorial design, A–H).
VP100_VALID_COMBINATIONS: frozenset[str] = frozenset("ABCDEFGH")


# ---------------------------------------------------------------------------
# Dataset-level source fingerprint
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VP100SourceMeta:
    """Dataset-level provenance fingerprint for the VP100 XLSX source.

    Constructed once at load time and shared across all records so that the
    full source fingerprint travels with every empirical observation.
    """

    source_dataset: str    # logical dataset name, e.g. "VP100-EXTERNAL-BENCHMARK"
    source_filename: str   # XLSX filename, e.g. "MachiningPro_AI_VP100_EXTERNAL_BENCHMARK.xlsx"
    source_sha256: str     # SHA-256 hex digest of the source XLSX (lowercase)
    source_sheet: str      # sheet name, e.g. "VP100 Detailed Results"

    def __post_init__(self) -> None:
        for fname in ("source_dataset", "source_filename", "source_sha256", "source_sheet"):
            val = getattr(self, fname)
            if not isinstance(val, str) or not val.strip():
                raise ValidationError(
                    f"VP100SourceMeta.{fname} must be a non-empty string"
                )

    def as_dict(self) -> dict:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Empirical observation record
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VP100EmpiricalRecord:
    """One empirical observation from the VP100 dry milling DOE.

    Cutting inputs (vc, fz, ap) are the controlled DOE variables.
    Measured outputs (mrv, t_eol, rq, fx) are the observed responses.

    Unit conventions
    ----------------
    vc   → Unit.M_MIN   (m/min)
    fz   → Unit.MM_TOOTH (mm/tooth)
    ap   → Unit.MM      (mm)
    mrv  → Unit.CM3     (cm³  — material removal volume at tool EOL)
    t_eol→ Unit.MIN     (min)
    rq   → Unit.RQ_UM   (Rq µm — surface roughness; distinct from Ra)
    fx   → Unit.N       (N — cutting force X-component)
    """

    record_id: str           # source Case ID, e.g. "VP100-001"
    source: VP100SourceMeta
    source_row: int          # 1-based data row (row 1 = first data row after header)

    # Experimental context
    tool_condition: str      # C0 / C1 / C2 / C3
    coating: str             # Uncoated / TiN / AlTiN / AlTiN/TiSiXN
    combination: str         # A–H (DOE factorial cell)
    replicate: int           # 1–3

    # Controlled inputs
    vc: Quantity             # m/min
    fz: Quantity             # mm/tooth
    ap: Quantity             # mm

    # Measured outputs
    mrv: Quantity            # cm³ — material removal volume at tool end-of-life
    t_eol: Quantity          # min — tool end-of-life time
    rq: Quantity             # Rq µm — surface roughness (NOT Ra)
    fx: Quantity             # N — cutting force X

    provenance: Provenance
    evidence_status: EvidenceStatus

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "record_id", require_non_empty_str(self.record_id, "record_id")
        )
        if not isinstance(self.source, VP100SourceMeta):
            raise ValidationError("source must be a VP100SourceMeta")
        if not isinstance(self.source_row, int) or self.source_row < 1:
            raise ValidationError("source_row must be a positive integer")
        if self.tool_condition not in VP100_VALID_TOOL_CONDITIONS:
            raise ValidationError(
                f"tool_condition {self.tool_condition!r} is not in "
                f"{sorted(VP100_VALID_TOOL_CONDITIONS)}"
            )
        if self.coating not in VP100_VALID_COATINGS:
            raise ValidationError(
                f"coating {self.coating!r} is not in {sorted(VP100_VALID_COATINGS)}"
            )
        if self.combination not in VP100_VALID_COMBINATIONS:
            raise ValidationError(
                f"combination {self.combination!r} is not in "
                f"{sorted(VP100_VALID_COMBINATIONS)}"
            )
        if not isinstance(self.replicate, int) or self.replicate < 1:
            raise ValidationError("replicate must be a positive integer")
        # Cutting inputs
        require_positive_quantity(self.vc, "vc")
        if self.vc.unit is not Unit.M_MIN:
            raise ValidationError(f"vc must carry unit {Unit.M_MIN!r}; got {self.vc.unit!r}")
        require_positive_quantity(self.fz, "fz")
        if self.fz.unit is not Unit.MM_TOOTH:
            raise ValidationError(f"fz must carry unit {Unit.MM_TOOTH!r}; got {self.fz.unit!r}")
        require_positive_quantity(self.ap, "ap")
        if self.ap.unit is not Unit.MM:
            raise ValidationError(f"ap must carry unit {Unit.MM!r}; got {self.ap.unit!r}")
        # Measured outputs
        require_positive_quantity(self.mrv, "mrv")
        if self.mrv.unit is not Unit.CM3:
            raise ValidationError(f"mrv must carry unit {Unit.CM3!r}; got {self.mrv.unit!r}")
        require_positive_quantity(self.t_eol, "t_eol")
        if self.t_eol.unit is not Unit.MIN:
            raise ValidationError(f"t_eol must carry unit {Unit.MIN!r}; got {self.t_eol.unit!r}")
        require_positive_quantity(self.rq, "rq")
        if self.rq.unit is not Unit.RQ_UM:
            raise ValidationError(f"rq must carry unit {Unit.RQ_UM!r}; got {self.rq.unit!r}")
        require_positive_quantity(self.fx, "fx")
        if self.fx.unit is not Unit.N:
            raise ValidationError(f"fx must carry unit {Unit.N!r}; got {self.fx.unit!r}")
        if not isinstance(self.provenance, Provenance):
            raise ValidationError("provenance must be a Provenance")
        if not isinstance(self.evidence_status, EvidenceStatus):
            raise ValidationError("evidence_status must be an EvidenceStatus")

    @property
    def is_uncoated(self) -> bool:
        """True when tool_condition is C0 (uncoated tool class)."""
        return self.tool_condition == "C0"

    def as_dict(self) -> dict:
        return entity_as_dict(self)
