"""
ToolLife 968 empirical dataset models.

Source: Piecuch–Żabiński full-life milling dataset
DOI: 10.6084/m9.figshare.28589216
License: CC BY (Springer Nature Figshare)

14 tools / 968 milling cycle observations / 131 features per observation.
Each observation is one milling cycle, identified by FileName (unique).

Key semantics
-------------
- CycleToFailure: countdown remaining to EOL. When 0, the tool has reached EOL.
- CycleToFailureNormalized: CycleToFailure / max(CycleToFailure for this tool).
  Range 0.0 (EOL) to 1.0 (first observation).
- TollIndex: source column has a typo ('Toll' not 'Tool'). The Python field is
  named tool_index; the source column name is preserved in loader docs only.
- VB (flank wear in mm) is NOT present in this dataset.
- Taylor C/n cannot be fitted (no cutting speed Vc column in source).
- EOL criterion: CycleToFailure == 0 (implicit; no VB threshold in source).
- total_tool_life_cycles = cycle_number + cycle_to_failure (constant per tool).
- HardnessMean units are not stated in the source; values 35–41 are consistent
  with HRC (Rockwell C) for hardened-steel milling. Do NOT assume HB.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.cutting_parameters.models import EvidenceStatus
from backend.domain.base import Provenance
from backend.domain.exceptions import ValidationError
from backend.domain.units import Quantity, Unit

# ---------------------------------------------------------------------------
# Controlled-vocabulary constants
# ---------------------------------------------------------------------------

TOOLLIFE968_VALID_TOOL_TYPES: frozenset[str] = frozenset({"1", "2"})
TOOLLIFE968_SHEET_NAME: str = "Golden ToolLife 968"
TOOLLIFE968_SENSOR_CHANNEL_COUNT: int = 20   # 8 accelerometer + 12 current
TOOLLIFE968_STATS_PER_CHANNEL: int = 6       # min, max, mean, std, skew, kurtosis
TOOLLIFE968_SENSOR_FEATURE_COUNT: int = 120  # 20 × 6
TOOLLIFE968_ENGINEERING_COL_COUNT: int = 11
TOOLLIFE968_TOTAL_COL_COUNT: int = 131       # 120 + 11


# ---------------------------------------------------------------------------
# Source metadata
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ToolLife968SourceMeta:
    """Fingerprint and provenance of the Golden ToolLife 968 source sheet."""

    source_dataset: str              # e.g. "TOOLLIFE-968"
    source_filename: str             # workbook filename
    source_sha256: str               # hex SHA-256 of the workbook file
    source_sheet: str                # "Golden ToolLife 968"
    doi: str                         # "10.6084/m9.figshare.28589216"
    sensor_feature_headers: tuple[str, ...]  # 120 column headers in source order

    def __post_init__(self) -> None:
        for field_name in (
            "source_dataset", "source_filename", "source_sha256", "source_sheet", "doi"
        ):
            value = getattr(self, field_name)
            if not value or not isinstance(value, str):
                raise ValidationError(f"{field_name} must be non-empty string")
        if len(self.sensor_feature_headers) != TOOLLIFE968_SENSOR_FEATURE_COUNT:
            raise ValidationError(
                f"sensor_feature_headers must have exactly "
                f"{TOOLLIFE968_SENSOR_FEATURE_COUNT} entries, "
                f"got {len(self.sensor_feature_headers)}"
            )

    def as_dict(self) -> dict:
        return {
            "source_dataset": self.source_dataset,
            "source_filename": self.source_filename,
            "source_sha256": self.source_sha256,
            "source_sheet": self.source_sheet,
            "doi": self.doi,
        }


# ---------------------------------------------------------------------------
# Observation record (one per milling cycle / one source row)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ToolLife968Observation:
    """
    One milling-cycle observation from the Golden ToolLife 968 dataset.

    Uniquely identified by observation_id (FileName column from source).
    Source column 'TollIndex' (typo for 'ToolIndex') is stored as tool_index.

    sensor_features: 120 float values in source column order (cols 0–119).
    Stored as float (not Decimal) because these are already computed
    statistical summaries where float64 precision is sufficient.
    """

    observation_id: str               # FileName (unique per row in source)
    source: ToolLife968SourceMeta
    source_row: int                   # 1-based data-row number

    # Experimental context
    tool_index: int                   # TollIndex (source typo: "Toll" not "Tool")
    tool_type: str                    # MillingToolType ('1' or '2')

    # Cutting conditions
    adoc: Quantity                    # ADOC – axial depth of cut [mm]
    rdoc: Quantity                    # RDOC – radial depth of cut [mm]
    tool_holder_length: Quantity      # ToolHolderLength [mm]

    # Workpiece
    hardness_mean: Decimal            # HardnessMean (unit unstated in source; ~35–41 HRC)

    # Wear progression (within tool lifecycle)
    cycle_number: int                 # NumberOfCycle (1-based per-tool counter)
    sample_index: int                 # SampleIndex (sensor sample position within cycle)
    cycle_to_failure: int             # CycleToFailure countdown (0 = EOL reached)
    cycle_to_failure_normalized: Decimal  # 0.0 (EOL) – 1.0 (first observation)

    # Sensor feature vector (120 statistical summaries, source col order 0–119)
    sensor_features: tuple[float, ...]

    provenance: Provenance
    evidence_status: EvidenceStatus

    def __post_init__(self) -> None:
        if not self.observation_id or not isinstance(self.observation_id, str):
            raise ValidationError("observation_id must be non-empty string")
        if not isinstance(self.source, ToolLife968SourceMeta):
            raise ValidationError("source must be ToolLife968SourceMeta")
        if self.source_row < 1:
            raise ValidationError(f"source_row must be >= 1, got {self.source_row}")
        if not isinstance(self.tool_index, int) or self.tool_index < 1:
            raise ValidationError(
                f"tool_index must be a positive int, got {self.tool_index!r}"
            )
        if self.tool_type not in TOOLLIFE968_VALID_TOOL_TYPES:
            raise ValidationError(
                f"tool_type must be one of {TOOLLIFE968_VALID_TOOL_TYPES}, "
                f"got {self.tool_type!r}"
            )
        if self.adoc.unit is not Unit.MM:
            raise ValidationError(
                f"adoc must carry unit MM, got {self.adoc.unit!r}"
            )
        if self.adoc.value <= 0:
            raise ValidationError(f"adoc must be > 0, got {self.adoc.value}")
        if self.rdoc.unit is not Unit.MM:
            raise ValidationError(
                f"rdoc must carry unit MM, got {self.rdoc.unit!r}"
            )
        if self.rdoc.value <= 0:
            raise ValidationError(f"rdoc must be > 0, got {self.rdoc.value}")
        if self.tool_holder_length.unit is not Unit.MM:
            raise ValidationError(
                f"tool_holder_length must carry unit MM, "
                f"got {self.tool_holder_length.unit!r}"
            )
        if self.tool_holder_length.value <= 0:
            raise ValidationError(
                f"tool_holder_length must be > 0, "
                f"got {self.tool_holder_length.value}"
            )
        if not isinstance(self.hardness_mean, Decimal):
            raise ValidationError(
                f"hardness_mean must be Decimal, got {type(self.hardness_mean)}"
            )
        if self.hardness_mean <= 0:
            raise ValidationError(
                f"hardness_mean must be > 0, got {self.hardness_mean}"
            )
        if not isinstance(self.cycle_number, int) or self.cycle_number < 1:
            raise ValidationError(
                f"cycle_number must be a positive int, got {self.cycle_number!r}"
            )
        if not isinstance(self.sample_index, int) or self.sample_index < 0:
            raise ValidationError(
                f"sample_index must be a non-negative int, got {self.sample_index!r}"
            )
        if not isinstance(self.cycle_to_failure, int) or self.cycle_to_failure < 0:
            raise ValidationError(
                f"cycle_to_failure must be a non-negative int, "
                f"got {self.cycle_to_failure!r}"
            )
        ctf_norm = self.cycle_to_failure_normalized
        if not isinstance(ctf_norm, Decimal):
            raise ValidationError(
                f"cycle_to_failure_normalized must be Decimal, got {type(ctf_norm)}"
            )
        if not (Decimal("0") <= ctf_norm <= Decimal("1")):
            raise ValidationError(
                f"cycle_to_failure_normalized must be in [0, 1], got {ctf_norm}"
            )
        if len(self.sensor_features) != TOOLLIFE968_SENSOR_FEATURE_COUNT:
            raise ValidationError(
                f"sensor_features must have exactly "
                f"{TOOLLIFE968_SENSOR_FEATURE_COUNT} elements, "
                f"got {len(self.sensor_features)}"
            )

    @property
    def is_eol(self) -> bool:
        """True when this observation is the tool's end-of-life observation."""
        return self.cycle_to_failure == 0

    @property
    def total_tool_life_cycles(self) -> int:
        """Total milling cycles for this tool: cycle_number + cycle_to_failure."""
        return self.cycle_number + self.cycle_to_failure

    def as_dict(self) -> dict:
        return {
            "observation_id": self.observation_id,
            "source_row": self.source_row,
            "tool_index": self.tool_index,
            "tool_type": self.tool_type,
            "adoc_mm": self.adoc.value,
            "rdoc_mm": self.rdoc.value,
            "tool_holder_length_mm": self.tool_holder_length.value,
            "hardness_mean": self.hardness_mean,
            "cycle_number": self.cycle_number,
            "sample_index": self.sample_index,
            "cycle_to_failure": self.cycle_to_failure,
            "cycle_to_failure_normalized": self.cycle_to_failure_normalized,
            "is_eol": self.is_eol,
            "total_tool_life_cycles": self.total_tool_life_cycles,
            "evidence_status": self.evidence_status.value,
        }
