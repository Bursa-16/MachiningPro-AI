"""
XLSX loader for the Golden ToolLife 968 sheet.

Sheet layout (0-based row indices):
  Row 0: empty
  Row 1: title string
  Row 2: empty
  Row 3: column headers (131 columns)
  Rows 4–971: 968 data rows

Column layout (0-based):
  0–119:  sensor statistical features (20 channels × 6 stats)
  120:    FileName          — unique row identifier
  121:    NumberOfCycle     — 1-based cycle counter per tool
  122:    SampleIndex       — sensor sample position within cycle
  123:    TollIndex         — source typo for ToolIndex
  124:    MillingToolType   — '1' or '2'
  125:    ADOC              — axial depth of cut [mm]
  126:    RDOC              — radial depth of cut [mm]
  127:    HardnessMean      — workpiece hardness (unit unstated)
  128:    ToolHolderLength  — [mm]
  129:    CycleToFailure    — countdown to EOL; 0 = EOL reached
  130:    CycleToFailureNormalized — 0.0 (EOL) to 1.0 (start)

Returns:
  tuple[list[ToolLife968Observation], list[str]]
  Second element: human-readable rejection reasons.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from backend.cutting_parameters.models import EvidenceStatus
from backend.domain.base import Provenance
from backend.domain.enums import ProvenanceType
from backend.domain.units import Quantity, Unit
from backend.empirical.exceptions import EmpiricalDataError
from backend.empirical.toollife968_models import (
    TOOLLIFE968_SENSOR_FEATURE_COUNT,
    TOOLLIFE968_SHEET_NAME,
    ToolLife968Observation,
    ToolLife968SourceMeta,
)

# ---------------------------------------------------------------------------
# Source fingerprint constants
# ---------------------------------------------------------------------------

TOOLLIFE968_SOURCE_SHA256: str = (
    "ee0f0ec8a25dcac8d26e65876e5f6d64fca671f30d6a668280edc9a7dd3f153c"
)
TOOLLIFE968_EXPECTED_ROW_COUNT: int = 968
TOOLLIFE968_SOURCE_DOI: str = "10.6084/m9.figshare.28589216"

# Column indices (0-based)
_COL_FILENAME = 120
_COL_NUMBER_OF_CYCLE = 121
_COL_SAMPLE_INDEX = 122
_COL_TOLL_INDEX = 123      # source typo: "TollIndex" not "ToolIndex"
_COL_MILLING_TOOL_TYPE = 124
_COL_ADOC = 125
_COL_RDOC = 126
_COL_HARDNESS_MEAN = 127
_COL_TOOL_HOLDER_LENGTH = 128
_COL_CYCLE_TO_FAILURE = 129
_COL_CYCLE_TO_FAILURE_NORMALIZED = 130

_DATA_ROW_START = 4   # first data row (0-based in sheet rows list)
_HEADER_ROW = 3       # column header row (0-based)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _to_decimal(value: Any, field_name: str) -> Decimal | str:
    if value is None:
        return f"{field_name}: null value"
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        return f"{field_name}: cannot convert {value!r} to Decimal ({exc})"


def _to_int(value: Any, field_name: str) -> int | str:
    if value is None:
        return f"{field_name}: null value"
    try:
        return int(value)
    except (ValueError, TypeError) as exc:
        return f"{field_name}: cannot convert {value!r} to int ({exc})"


# ---------------------------------------------------------------------------
# Row parser
# ---------------------------------------------------------------------------

def _parse_row(
    source_row: int,
    row: tuple[Any, ...],
    source_meta: ToolLife968SourceMeta,
    provenance: Provenance,
) -> ToolLife968Observation | str:
    """
    Parse one data row into a ToolLife968Observation.

    Returns ToolLife968Observation on success, or a rejection reason string.
    source_row is 1-based within the data block.
    """
    # observation_id (FileName)
    obs_id_raw = row[_COL_FILENAME]
    if not obs_id_raw or not isinstance(obs_id_raw, str):
        obs_id_raw = f"row-{source_row}"
    observation_id = str(obs_id_raw).strip()

    # TollIndex → tool_index
    tool_index_v = _to_int(row[_COL_TOLL_INDEX], "TollIndex")
    if isinstance(tool_index_v, str):
        return f"row {source_row} ({observation_id}): {tool_index_v}"
    if tool_index_v < 1:
        return (
            f"row {source_row} ({observation_id}): "
            f"TollIndex must be >= 1, got {tool_index_v}"
        )

    # MillingToolType
    tool_type_raw = row[_COL_MILLING_TOOL_TYPE]
    if tool_type_raw is None:
        return f"row {source_row} ({observation_id}): MillingToolType is null"
    tool_type = str(tool_type_raw).strip()
    if tool_type not in {"1", "2"}:
        return (
            f"row {source_row} ({observation_id}): "
            f"MillingToolType must be '1' or '2', got {tool_type!r}"
        )

    # ADOC
    adoc_v = _to_decimal(row[_COL_ADOC], "ADOC")
    if isinstance(adoc_v, str):
        return f"row {source_row} ({observation_id}): {adoc_v}"
    if adoc_v <= 0:
        return f"row {source_row} ({observation_id}): ADOC must be > 0, got {adoc_v}"

    # RDOC
    rdoc_v = _to_decimal(row[_COL_RDOC], "RDOC")
    if isinstance(rdoc_v, str):
        return f"row {source_row} ({observation_id}): {rdoc_v}"
    if rdoc_v <= 0:
        return f"row {source_row} ({observation_id}): RDOC must be > 0, got {rdoc_v}"

    # HardnessMean
    hardness_v = _to_decimal(row[_COL_HARDNESS_MEAN], "HardnessMean")
    if isinstance(hardness_v, str):
        return f"row {source_row} ({observation_id}): {hardness_v}"
    if hardness_v <= 0:
        return (
            f"row {source_row} ({observation_id}): "
            f"HardnessMean must be > 0, got {hardness_v}"
        )

    # ToolHolderLength
    thl_v = _to_decimal(row[_COL_TOOL_HOLDER_LENGTH], "ToolHolderLength")
    if isinstance(thl_v, str):
        return f"row {source_row} ({observation_id}): {thl_v}"
    if thl_v <= 0:
        return (
            f"row {source_row} ({observation_id}): "
            f"ToolHolderLength must be > 0, got {thl_v}"
        )

    # NumberOfCycle
    cycle_v = _to_int(row[_COL_NUMBER_OF_CYCLE], "NumberOfCycle")
    if isinstance(cycle_v, str):
        return f"row {source_row} ({observation_id}): {cycle_v}"
    if cycle_v < 1:
        return (
            f"row {source_row} ({observation_id}): "
            f"NumberOfCycle must be >= 1, got {cycle_v}"
        )

    # SampleIndex
    sample_v = _to_int(row[_COL_SAMPLE_INDEX], "SampleIndex")
    if isinstance(sample_v, str):
        return f"row {source_row} ({observation_id}): {sample_v}"
    if sample_v < 0:
        return (
            f"row {source_row} ({observation_id}): "
            f"SampleIndex must be >= 0, got {sample_v}"
        )

    # CycleToFailure
    ctf_v = _to_int(row[_COL_CYCLE_TO_FAILURE], "CycleToFailure")
    if isinstance(ctf_v, str):
        return f"row {source_row} ({observation_id}): {ctf_v}"
    if ctf_v < 0:
        return (
            f"row {source_row} ({observation_id}): "
            f"CycleToFailure must be >= 0, got {ctf_v}"
        )

    # CycleToFailureNormalized
    ctf_norm_v = _to_decimal(
        row[_COL_CYCLE_TO_FAILURE_NORMALIZED], "CycleToFailureNormalized"
    )
    if isinstance(ctf_norm_v, str):
        return f"row {source_row} ({observation_id}): {ctf_norm_v}"
    if not (Decimal("0") <= ctf_norm_v <= Decimal("1")):
        return (
            f"row {source_row} ({observation_id}): "
            f"CycleToFailureNormalized must be in [0, 1], got {ctf_norm_v}"
        )

    # Sensor features (columns 0–119)
    sensor_features: list[float] = []
    for col_idx in range(TOOLLIFE968_SENSOR_FEATURE_COUNT):
        val = row[col_idx]
        if val is None:
            return (
                f"row {source_row} ({observation_id}): "
                f"sensor feature col[{col_idx}] is null"
            )
        try:
            sensor_features.append(float(val))
        except (ValueError, TypeError) as exc:
            return (
                f"row {source_row} ({observation_id}): "
                f"sensor feature col[{col_idx}] cannot be converted to float: {exc}"
            )

    try:
        return ToolLife968Observation(
            observation_id=observation_id,
            source=source_meta,
            source_row=source_row,
            tool_index=tool_index_v,
            tool_type=tool_type,
            adoc=Quantity(adoc_v, Unit.MM),
            rdoc=Quantity(rdoc_v, Unit.MM),
            tool_holder_length=Quantity(thl_v, Unit.MM),
            hardness_mean=hardness_v,
            cycle_number=cycle_v,
            sample_index=sample_v,
            cycle_to_failure=ctf_v,
            cycle_to_failure_normalized=ctf_norm_v,
            sensor_features=tuple(sensor_features),
            provenance=provenance,
            evidence_status=EvidenceStatus.EXPERIMENTAL,
        )
    except Exception as exc:
        return f"row {source_row} ({observation_id}): construction failed: {exc}"


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------

def load_toollife968_records(
    source_path: Path,
) -> tuple[list[ToolLife968Observation], list[str]]:
    """
    Load all observations from the Golden ToolLife 968 sheet.

    Opens the workbook read-only. Performs a SHA-256 soft check (warns but
    continues if the checksum differs). Returns (records, rejections) where
    rejections is a list of human-readable strings for rows that could not
    be parsed.

    Raises:
        FileNotFoundError: if source_path does not exist.
        EmpiricalDataError: if the required sheet is missing.
    """
    try:
        import openpyxl
    except ImportError as exc:
        raise EmpiricalDataError(
            "openpyxl is required to load ToolLife 968 data"
        ) from exc

    if not source_path.exists():
        raise FileNotFoundError(f"Source path not found: {source_path}")

    actual_sha = _sha256_file(source_path)
    rejections: list[str] = []
    if actual_sha.lower() != TOOLLIFE968_SOURCE_SHA256:
        rejections.append(
            f"SHA-256 MISMATCH: expected {TOOLLIFE968_SOURCE_SHA256}, "
            f"got {actual_sha}. Proceeding with caution."
        )

    wb = openpyxl.load_workbook(source_path, read_only=True, data_only=True)
    try:
        if TOOLLIFE968_SHEET_NAME not in wb.sheetnames:
            raise EmpiricalDataError(
                f"Sheet '{TOOLLIFE968_SHEET_NAME}' not found in workbook. "
                f"Available sheets: {wb.sheetnames}"
            )
        ws = wb[TOOLLIFE968_SHEET_NAME]
        all_rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()

    if len(all_rows) <= _DATA_ROW_START:
        raise EmpiricalDataError(
            f"Sheet has only {len(all_rows)} rows; "
            f"expected data starting at row {_DATA_ROW_START}"
        )

    header_row = all_rows[_HEADER_ROW]
    sensor_headers: tuple[str, ...] = tuple(
        str(header_row[i]) if header_row[i] is not None else f"col_{i}"
        for i in range(TOOLLIFE968_SENSOR_FEATURE_COUNT)
    )

    source_meta = ToolLife968SourceMeta(
        source_dataset="TOOLLIFE-968",
        source_filename=source_path.name,
        source_sha256=actual_sha,
        source_sheet=TOOLLIFE968_SHEET_NAME,
        doi=TOOLLIFE968_SOURCE_DOI,
        sensor_feature_headers=sensor_headers,
    )

    provenance = Provenance(
        source_type=ProvenanceType.HISTORICAL_PROCESS_DATA,
        source_reference=(
            f"Piecuch–Żabiński full-life milling dataset / "
            f"DOI: {TOOLLIFE968_SOURCE_DOI} / "
            f"sheet: {TOOLLIFE968_SHEET_NAME}"
        ),
    )

    data_rows = all_rows[_DATA_ROW_START:]
    records: list[ToolLife968Observation] = []

    for row_offset, row in enumerate(data_rows):
        source_row = row_offset + 1  # 1-based within data block
        result = _parse_row(source_row, row, source_meta, provenance)
        if isinstance(result, str):
            rejections.append(result)
        else:
            records.append(result)

    return records, rejections
