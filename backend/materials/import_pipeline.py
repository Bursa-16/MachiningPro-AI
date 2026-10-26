"""Import pipeline for material catalog records (EPIC_01).

Supports JSON and CSV import with dry-run validation, idempotent load,
and explicit rejection of records that fail validation.

FABRICATED_MATERIAL_PROPERTY=NO
PROPRIETARY_DATA_IMPORTED_WITHOUT_REVIEW=NO
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from io import StringIO
from typing import Any

from backend.materials.validation import validate_material_record, validate_no_fabrication

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    accepted: int
    rejected: int
    skipped_duplicate: int
    errors: list[dict]
    dry_run: bool


def import_from_json(
    json_text: str,
    *,
    dry_run: bool = True,
    existing_ids: set[str] | None = None,
) -> tuple[list[dict], ImportResult]:
    """Parse and validate material records from a JSON array string.

    Returns (valid_records, result). When dry_run=True, no catalog mutation occurs.
    The caller is responsible for loading valid_records into the catalog.
    """
    existing_ids = existing_ids or set()
    try:
        raw_records: list[Any] = json.loads(json_text)
    except json.JSONDecodeError as exc:
        return [], ImportResult(accepted=0, rejected=1, skipped_duplicate=0,
                                errors=[{"code": "JSON_PARSE_ERROR", "message": str(exc)}],
                                dry_run=dry_run)

    if not isinstance(raw_records, list):
        return [], ImportResult(accepted=0, rejected=1, skipped_duplicate=0,
                                errors=[{"code": "NOT_A_LIST", "message": "JSON root must be an array of records"}],
                                dry_run=dry_run)

    return _process_records(raw_records, dry_run=dry_run, existing_ids=existing_ids)


def import_from_csv(
    csv_text: str,
    *,
    dry_run: bool = True,
    existing_ids: set[str] | None = None,
) -> tuple[list[dict], ImportResult]:
    """Parse and validate material records from CSV.

    CSV must have headers matching MaterialRecord fields.
    Numeric fields that are empty strings become None.
    """
    existing_ids = existing_ids or set()
    reader = csv.DictReader(StringIO(csv_text))
    raw_records = []
    for row in reader:
        cleaned: dict[str, Any] = {}
        for k, v in row.items():
            if v == "" or v is None:
                cleaned[k] = None
            else:
                cleaned[k] = v
        raw_records.append(cleaned)

    return _process_records(raw_records, dry_run=dry_run, existing_ids=existing_ids)


def _process_records(
    raw_records: list[dict],
    *,
    dry_run: bool,
    existing_ids: set[str],
) -> tuple[list[dict], ImportResult]:
    accepted: list[dict] = []
    errors: list[dict] = []
    rejected = 0
    skipped_duplicate = 0
    seen_ids: set[str] = set()

    for idx, raw in enumerate(raw_records):
        mid = raw.get("material_id", f"<unknown-{idx}>")

        if mid in existing_ids or mid in seen_ids:
            skipped_duplicate += 1
            logger.debug("Skipping duplicate material_id: %r", mid)
            continue

        issues = validate_material_record(raw) + validate_no_fabrication(raw)
        if issues:
            rejected += 1
            errors.append({
                "material_id": mid,
                "issues": [
                    {"field": i.field, "code": i.code, "message": i.message}
                    for i in issues
                ],
            })
            logger.warning("Rejected material %r: %d validation issues", mid, len(issues))
            continue

        seen_ids.add(mid)
        accepted.append(raw)

    result = ImportResult(
        accepted=len(accepted),
        rejected=rejected,
        skipped_duplicate=skipped_duplicate,
        errors=errors,
        dry_run=dry_run,
    )
    logger.info(
        "Import %s: accepted=%d, rejected=%d, duplicate=%d",
        "DRY_RUN" if dry_run else "COMMITTED",
        result.accepted, result.rejected, result.skipped_duplicate,
    )
    return accepted, result
