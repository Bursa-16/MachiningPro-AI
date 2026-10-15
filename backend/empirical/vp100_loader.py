"""VP100 dry milling dataset loader (Stage EMPIRICAL-01A).

Reads ``VP100 Detailed Results`` from the source XLSX, validates every row
against the VP100EmpiricalRecord contract, and returns a tuple of
(valid_records, rejection_log).

Design principles
-----------------
* Source SHA-256 is verified (soft check — mismatch warns, does not abort).
* Every source row is either accepted as a VP100EmpiricalRecord or logged
  with a deterministic rejection reason; no silent failures.
* Validation-artefact columns (Pred.*, *APE, *Status, Row Status) are
  explicitly excluded.
* Duplicate record_id values are rejected deterministically.
* Requires ``openpyxl`` at import time; an ImportError gives an actionable
  message.

Usage
-----
::

    from pathlib import Path
    from backend.empirical.vp100_loader import load_vp100_records

    records, rejections = load_vp100_records(Path("/path/to/VP100_BENCHMARK.xlsx"))
    print(len(records), "valid records loaded")
    for r in rejections:
        print("REJECTED:", r)
"""

from __future__ import annotations

import hashlib
import warnings
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

try:
    import openpyxl
except ImportError as _e:  # pragma: no cover
    raise ImportError(
        "openpyxl is required to load VP100 data.  "
        "Install it with:  pip install openpyxl"
    ) from _e

from backend.cutting_parameters.models import EvidenceStatus
from backend.domain.base import Provenance
from backend.domain.enums import ProvenanceType
from backend.domain.units import Quantity, Unit
from backend.empirical.models import (
    VP100_VALID_COATINGS,
    VP100_VALID_COMBINATIONS,
    VP100_VALID_TOOL_CONDITIONS,
    VP100EmpiricalRecord,
    VP100SourceMeta,
)

__all__ = [
    "VP100_SOURCE_FILENAME",
    "VP100_SOURCE_SHA256",
    "VP100_SHEET_NAME",
    "VP100_EXPECTED_SOURCE_ROW_COUNT",
    "load_vp100_records",
]

# ---------------------------------------------------------------------------
# Source fingerprint constants
# ---------------------------------------------------------------------------

VP100_SOURCE_FILENAME = "MachiningPro_AI_VP100_EXTERNAL_BENCHMARK.xlsx"

#: SHA-256 hex digest of the authoritative source XLSX (lowercase).
VP100_SOURCE_SHA256 = "ee0f0ec8a25dcac8d26e65876e5f6d64fca671f30d6a668280edc9a7dd3f153c"

VP100_SHEET_NAME = "VP100 Detailed Results"

#: Total data rows expected in the source sheet (excluding header).
VP100_EXPECTED_SOURCE_ROW_COUNT = 96

# ---------------------------------------------------------------------------
# Source column names (12 engineering columns; the rest are artefacts)
# ---------------------------------------------------------------------------

_COL_CASE_ID = "Case ID"
_COL_TOOL_CONDITION = "Tool Condition"
_COL_COATING = "Coating"
_COL_COMBINATION = "Combination"
_COL_REPLICATE = "Replicate"
_COL_VC = "Vc (m/min)"
_COL_FZ = "fz (mm/tooth)"
_COL_AP = "ap (mm)"
_COL_MRV = "Golden MRV (cm³)"   # "Golden MRV (cm³)"
_COL_T_EOL = "Golden T_EOL (min)"
_COL_RQ = "Golden Rq (µm)"       # "Golden Rq (µm)"
_COL_FX = "Golden Fx (N)"

_REQUIRED_COLUMNS = (
    _COL_CASE_ID, _COL_TOOL_CONDITION, _COL_COATING, _COL_COMBINATION,
    _COL_REPLICATE, _COL_VC, _COL_FZ, _COL_AP,
    _COL_MRV, _COL_T_EOL, _COL_RQ, _COL_FX,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().lower()


def _to_decimal(value: Any, field_name: str, row_id: str) -> Decimal | str:
    """Convert to Decimal; return error string on failure."""
    if value is None:
        return f"{row_id}: {field_name} is null"
    if isinstance(value, bool):
        return f"{row_id}: {field_name} is bool (not numeric)"
    try:
        d = Decimal(str(value))
        if not d.is_finite():
            return f"{row_id}: {field_name} is not finite ({value!r})"
        return d
    except (InvalidOperation, ValueError):
        return f"{row_id}: {field_name} cannot be parsed as decimal ({value!r})"


def _parse_row(
    row_index: int,
    row_data: dict[str, Any],
    source_meta: VP100SourceMeta,
    provenance: Provenance,
) -> VP100EmpiricalRecord | str:
    """Parse one source row into a VP100EmpiricalRecord or return a rejection reason."""
    rid = str(row_data.get(_COL_CASE_ID, f"row-{row_index}")).strip()

    # Categorical fields
    tool_cond = row_data.get(_COL_TOOL_CONDITION)
    if not isinstance(tool_cond, str) or tool_cond not in VP100_VALID_TOOL_CONDITIONS:
        return f"{rid}: tool_condition {tool_cond!r} not in {sorted(VP100_VALID_TOOL_CONDITIONS)}"

    coating = row_data.get(_COL_COATING)
    if not isinstance(coating, str) or coating not in VP100_VALID_COATINGS:
        return f"{rid}: coating {coating!r} not in {sorted(VP100_VALID_COATINGS)}"

    combination = row_data.get(_COL_COMBINATION)
    if not isinstance(combination, str) or combination not in VP100_VALID_COMBINATIONS:
        return f"{rid}: combination {combination!r} not in {sorted(VP100_VALID_COMBINATIONS)}"

    replicate_raw = row_data.get(_COL_REPLICATE)
    try:
        replicate = int(replicate_raw)  # type: ignore[arg-type]
        if replicate < 1:
            return f"{rid}: replicate {replicate} is < 1"
    except (TypeError, ValueError):
        return f"{rid}: replicate {replicate_raw!r} is not an integer"

    # Numeric fields — parse then range-check
    vc_d = _to_decimal(row_data.get(_COL_VC), "Vc", rid)
    if isinstance(vc_d, str):
        return vc_d
    if vc_d <= 0:
        return f"{rid}: Vc={vc_d} is not positive"

    fz_d = _to_decimal(row_data.get(_COL_FZ), "fz", rid)
    if isinstance(fz_d, str):
        return fz_d
    if fz_d <= 0:
        return f"{rid}: fz={fz_d} is not positive"

    ap_d = _to_decimal(row_data.get(_COL_AP), "ap", rid)
    if isinstance(ap_d, str):
        return ap_d
    if ap_d <= 0:
        return f"{rid}: ap={ap_d} is not positive"

    mrv_d = _to_decimal(row_data.get(_COL_MRV), "MRV", rid)
    if isinstance(mrv_d, str):
        return mrv_d
    if mrv_d <= 0:
        return f"{rid}: MRV={mrv_d} is not positive"

    t_eol_d = _to_decimal(row_data.get(_COL_T_EOL), "T_EOL", rid)
    if isinstance(t_eol_d, str):
        return t_eol_d
    if t_eol_d <= 0:
        return f"{rid}: T_EOL={t_eol_d} is not positive"

    rq_d = _to_decimal(row_data.get(_COL_RQ), "Rq", rid)
    if isinstance(rq_d, str):
        return rq_d
    if rq_d <= 0:
        return f"{rid}: Rq={rq_d} is not positive"

    fx_d = _to_decimal(row_data.get(_COL_FX), "Fx", rid)
    if isinstance(fx_d, str):
        return fx_d
    if fx_d <= 0:
        return f"{rid}: Fx={fx_d} is not positive"

    try:
        return VP100EmpiricalRecord(
            record_id=rid,
            source=source_meta,
            source_row=row_index,
            tool_condition=tool_cond,
            coating=coating,
            combination=combination,
            replicate=replicate,
            vc=Quantity(vc_d, Unit.M_MIN),
            fz=Quantity(fz_d, Unit.MM_TOOTH),
            ap=Quantity(ap_d, Unit.MM),
            mrv=Quantity(mrv_d, Unit.CM3),
            t_eol=Quantity(t_eol_d, Unit.MIN),
            rq=Quantity(rq_d, Unit.RQ_UM),
            fx=Quantity(fx_d, Unit.N),
            provenance=provenance,
            evidence_status=EvidenceStatus.EXPERIMENTAL,
        )
    except Exception as exc:  # noqa: BLE001
        return f"{rid}: construction failed — {exc}"


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------


def load_vp100_records(
    source_path: Path,
) -> tuple[list[VP100EmpiricalRecord], list[str]]:
    """Load and validate all VP100 empirical records from the source XLSX.

    Parameters
    ----------
    source_path:
        Absolute path to the VP100 XLSX workbook.

    Returns
    -------
    records:
        All successfully validated VP100EmpiricalRecord instances, in source
        row order.
    rejections:
        Human-readable rejection reasons for every row that failed
        validation.  Empty list when all rows pass.

    Raises
    ------
    FileNotFoundError
        When *source_path* does not exist.
    ValueError
        When the expected sheet is missing from the workbook.
    """
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"VP100 source not found: {source_path}")

    # SHA-256 check (soft: warn, do not abort)
    actual_sha256 = _sha256_of_file(source_path)
    if actual_sha256 != VP100_SOURCE_SHA256:
        warnings.warn(
            f"VP100 source SHA-256 mismatch.\n"
            f"  Expected: {VP100_SOURCE_SHA256}\n"
            f"  Actual:   {actual_sha256}\n"
            "Records will still be loaded but traceability may be affected.",
            stacklevel=2,
        )

    source_meta = VP100SourceMeta(
        source_dataset="VP100-EXTERNAL-BENCHMARK",
        source_filename=source_path.name,
        source_sha256=actual_sha256,
        source_sheet=VP100_SHEET_NAME,
    )

    provenance = Provenance(
        source_type=ProvenanceType.HISTORICAL_PROCESS_DATA,
        source_reference=(
            f"{VP100_SOURCE_FILENAME} / {VP100_SHEET_NAME} "
            f"(SHA-256: {actual_sha256[:16]}…)"
        ),
        source_document=str(source_path),
        notes="VP100 kuru freze DOE verisi: 4 takım koşulu × 8 kombinasyon × 3 tekrar",
    )

    wb = openpyxl.load_workbook(source_path, read_only=True, data_only=True)
    if VP100_SHEET_NAME not in wb.sheetnames:
        wb.close()
        raise ValueError(
            f"Sheet {VP100_SHEET_NAME!r} not found in {source_path.name}. "
            f"Available: {wb.sheetnames}"
        )

    ws = wb[VP100_SHEET_NAME]
    all_rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not all_rows:
        return [], ["Source sheet is empty"]

    # Normalise header — strip BOM / nbsp / extra spaces
    raw_header = all_rows[0]
    header = [
        (str(h).strip().replace(" ", " ") if h is not None else "")
        for h in raw_header
    ]

    # Check required columns are present
    missing = [c for c in _REQUIRED_COLUMNS if c not in header]
    if missing:
        return [], [f"Required columns missing from header: {missing}"]

    data_rows = [r for r in all_rows[1:] if any(c is not None for c in r)]

    records: list[VP100EmpiricalRecord] = []
    rejections: list[str] = []
    seen_ids: set[str] = set()

    for row_index, raw_row in enumerate(data_rows, start=1):
        row_dict = dict(zip(header, raw_row, strict=False))
        result = _parse_row(row_index, row_dict, source_meta, provenance)
        if isinstance(result, str):
            rejections.append(result)
        else:
            if result.record_id in seen_ids:
                rejections.append(f"{result.record_id}: duplicate record_id (row {row_index})")
            else:
                seen_ids.add(result.record_id)
                records.append(result)

    return records, rejections
