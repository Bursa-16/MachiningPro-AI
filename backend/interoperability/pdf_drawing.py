"""Fail-closed vector-PDF ingestion for technical drawings.

This module implements the Phase 1B process boundary, structural normalization,
and generic title-block extraction contract. Dimension and tolerance semantics
remain deliberately deferred to Task 6.
"""

from __future__ import annotations

import math
import multiprocessing
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO
from multiprocessing.connection import Connection
from typing import Any

import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException

from backend.interoperability.drawing import (
    CanonicalDrawing,
    DrawingBoundingBox,
    DrawingDimension,
    DrawingDimensionType,
    DrawingExtractionAuthority,
    DrawingIngestionDiagnostics,
    DrawingIngestionResult,
    DrawingIngestionStatus,
    DrawingMaterialNote,
    DrawingParser,
    DrawingRevision,
    DrawingSheet,
    DrawingSourceLocation,
    DrawingTitleBlock,
    DrawingTolerance,
    DrawingToleranceType,
    DrawingView,
    DrawingViewType,
)

_PARSER_ID = "machiningpro.vector-pdf"
_PARSER_VERSION = "1.0.0"
_WORKER_NAME = "machiningpro-vector-pdf-worker"
_TEXT_LINE_BASELINE_TOLERANCE_PT = Decimal("2")
_TEXT_HORIZONTAL_GAP_PT = Decimal("6")
_TEXT_BLOCK_LEFT_EDGE_TOLERANCE_PT = Decimal("3")
_TEXT_BLOCK_VERTICAL_GAP_PT = Decimal("3")
_TITLE_AXIS_TOLERANCE_PT = Decimal("0.5")
_TITLE_CONNECTION_TOLERANCE_PT = Decimal("1")
_TITLE_MAX_PAIR_DISTANCE_PT = Decimal("72")
_TITLE_MIN_LABEL_DENSITY = Decimal("0.20")
_TITLE_MIN_SCORE = 15
_TITLE_MIN_PAIR_COUNT = 2
_TITLE_ALIASES = (
    ("DRAWING NO", "drawing_number"),
    ("DRAWING NUMBER", "drawing_number"),
    ("DWG NO", "drawing_number"),
    ("DWG NUMBER", "drawing_number"),
    ("PART NO", "part_number"),
    ("PART NUMBER", "part_number"),
    ("TITLE", "part_name"),
    ("DESCRIPTION", "part_name"),
    ("PART NAME", "part_name"),
    ("MATERIAL", "material"),
    ("MATL", "material"),
    ("SCALE", "scale"),
    ("SHEET", "sheet"),
    ("SHEET NO", "sheet"),
    ("SHEET NUMBER", "sheet"),
    ("REV", "revision"),
    ("REVISION", "revision"),
    ("DRAWN", "author"),
    ("DRAWN BY", "author"),
    ("CHECKED", "checker"),
    ("CHECKED BY", "checker"),
    ("APPROVED", "approver"),
    ("APPROVED BY", "approver"),
    ("DATE", "date"),
    ("DRAWING DATE", "date"),
    ("UNIT", "unit"),
    ("UNITS", "unit"),
)
_TITLE_FIELD_ORDER = tuple(dict.fromkeys(field_key for _, field_key in _TITLE_ALIASES))
_TITLE_FIELD_KEYS = frozenset(field_key for _, field_key in _TITLE_ALIASES)
_TITLE_FIELD_CAPS = {
    "drawing_number": 128,
    "part_number": 128,
    "part_name": 256,
    "material": 256,
    "scale": 32,
    "sheet": 32,
    "revision": 32,
    "author": 128,
    "checker": 128,
    "approver": 128,
    "date": 64,
    "unit": 32,
}
_SHEET_PATTERN = re.compile(r"^(\d{1,5})(?:(?:\s+OF\s+|/)(\d{1,5}))?$")
_SCALE_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)$")
_DIMENSION_NUMBER = r"(?:\d+(?:[.,]\d+)?|\.\d+)"
_DIMENSION_UNIT = r"(?:mm|millimeters?|inches?|in|degree|deg)"
_DIMENSION_TOLERANCE_PATTERN = re.compile(
    rf"^(?P<nominal>{_DIMENSION_NUMBER})\s*"
    rf"(?:(?P<symmetric>±)\s*(?P<sym>{_DIMENSION_NUMBER})|"
    rf"\+(?P<upper>{_DIMENSION_NUMBER})\s*/\s*-?(?P<lower>{_DIMENSION_NUMBER})|"
    rf"\+(?P<unilateral_plus>{_DIMENSION_NUMBER})\s*/\s*0|"
    rf"\+0\s*/\s*-(?P<unilateral_minus>{_DIMENSION_NUMBER}))\s*"
    rf"(?P<unit>{_DIMENSION_UNIT})$",
    re.IGNORECASE,
)
_DIMENSION_TOKEN_PATTERN = re.compile(
    rf"^(?:(?P<prefix>DIA|RAD|R|Ø|⌀)\s*)?(?P<value>{_DIMENSION_NUMBER})\s*"
    rf"(?:(?P<angle>°|DEG)|(?P<unit>{_DIMENSION_UNIT}))$",
    re.IGNORECASE,
)
_DIMENSION_BARE_PATTERN = re.compile(rf"^{_DIMENSION_NUMBER}$")
_DIMENSION_MAX_TEXT = 256
_DIMENSION_BAND_PT = Decimal("12")
_DIMENSION_AXIS_MIN_PT = Decimal("6")
_DIMENSION_AXIS_TOLERANCE_PT = Decimal("0.5")
_DIMENSION_CONNECTION_TOLERANCE_PT = Decimal("2")


@dataclass(frozen=True)
class PdfDrawingLimits:
    """Resource ceilings for one vector-PDF ingestion attempt."""

    max_file_bytes: int = 67_108_864
    max_pages: int = 200
    parse_timeout_seconds: float = 10.0
    max_objects_total: int = 200_000
    max_objects_per_page: int = 20_000
    max_text_characters: int = 2_000_000
    max_text_characters_per_object: int = 4_096
    max_vector_points_total: int = 1_000_000
    max_vector_points_per_object: int = 10_000
    max_dimension_candidates: int = 20_000
    max_title_block_candidates: int = 1_000
    max_page_dimension_points: int = 20_000
    max_diagnostics_per_kind: int = 50
    max_diagnostic_characters: int = 240

    def __post_init__(self) -> None:
        integer_fields = (
            "max_file_bytes",
            "max_pages",
            "max_objects_total",
            "max_objects_per_page",
            "max_text_characters",
            "max_text_characters_per_object",
            "max_vector_points_total",
            "max_vector_points_per_object",
            "max_dimension_candidates",
            "max_title_block_candidates",
            "max_page_dimension_points",
            "max_diagnostics_per_kind",
            "max_diagnostic_characters",
        )
        for field_name in integer_fields:
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"PdfDrawingLimits.{field_name} must be an integer")
            if value <= 0:
                raise ValueError(f"PdfDrawingLimits.{field_name} must be positive")

        timeout = self.parse_timeout_seconds
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise TypeError(
                "PdfDrawingLimits.parse_timeout_seconds must be a finite number"
            )
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError(
                "PdfDrawingLimits.parse_timeout_seconds must be positive and finite"
            )
        if self.max_objects_per_page > self.max_objects_total:
            raise ValueError(
                "PdfDrawingLimits.max_objects_per_page must not exceed "
                "max_objects_total"
            )
        if self.max_vector_points_per_object > self.max_vector_points_total:
            raise ValueError(
                "PdfDrawingLimits.max_vector_points_per_object must not exceed "
                "max_vector_points_total"
            )


@dataclass(frozen=True)
class _PdfObjectRef:
    object_id: str
    page_number: int
    kind: str
    bounding_box: DrawingBoundingBox


@dataclass(frozen=True)
class _PdfTextRun:
    ref: _PdfObjectRef
    text: str


@dataclass(frozen=True)
class _PdfVectorPath:
    ref: _PdfObjectRef
    segments: tuple[tuple[tuple[Decimal, Decimal], ...], ...]


@dataclass(frozen=True)
class _PdfTextBlock:
    ref: _PdfObjectRef
    text_run_ids: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class _TextCandidate:
    source_index: int
    text: str
    bounding_box: DrawingBoundingBox


@dataclass(frozen=True)
class _VectorCandidate:
    source_index: int
    kind: str
    bounding_box: DrawingBoundingBox
    segments: tuple[tuple[tuple[Decimal, Decimal], ...], ...]


@dataclass(frozen=True)
class _TextLine:
    runs: tuple[_PdfTextRun, ...]
    bounding_box: DrawingBoundingBox
    text: str


@dataclass(frozen=True)
class _PdfPageSnapshot:
    page_number: int
    width_pt: Decimal
    height_pt: Decimal
    rotation: int
    text_runs: tuple[_PdfTextRun, ...]
    vector_paths: tuple[_PdfVectorPath, ...]
    text_blocks: tuple[_PdfTextBlock, ...]
    image_count: int


@dataclass(frozen=True)
class _PdfDocumentSnapshot:
    pdf_version: str
    pages: tuple[_PdfPageSnapshot, ...]
    object_count: int
    text_character_count: int
    vector_point_count: int


@dataclass(frozen=True)
class _TitleFieldEvidence:
    field_key: str
    value: str
    pairing_rank: int
    page_number: int
    bounding_box: DrawingBoundingBox
    source_object_ids: tuple[str, ...]
    original_text: str

    def __post_init__(self) -> None:
        if self.field_key not in _TITLE_FIELD_KEYS:
            raise ValueError("invalid title field key")
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("title field value must not be blank")
        if len(self.value) > _TITLE_FIELD_CAPS[self.field_key]:
            raise ValueError("title field value exceeds its limit")
        if self.pairing_rank not in (1, 2, 3, 4, 5):
            raise ValueError("invalid title field pairing rank")
        if self.page_number < 1:
            raise ValueError("title field page number must be positive")
        if not isinstance(self.bounding_box, DrawingBoundingBox):
            raise TypeError("title field bounding box must be DrawingBoundingBox")
        if (
            not isinstance(self.source_object_ids, tuple)
            or not self.source_object_ids
            or any(
                not isinstance(object_id, str) or not object_id.strip()
                for object_id in self.source_object_ids
            )
            or len(set(self.source_object_ids)) != len(self.source_object_ids)
        ):
            raise ValueError("title field source object IDs must be unique and nonblank")
        if not isinstance(self.original_text, str) or not self.original_text.strip():
            raise ValueError("title field original text must not be blank")
        if len(self.original_text) > 256:
            raise ValueError("title field original text exceeds its limit")


@dataclass(frozen=True)
class _TitleBlockCandidate:
    page_number: int
    bounding_box: DrawingBoundingBox
    source_object_ids: tuple[str, ...]
    score: int
    recognized_field_keys: tuple[str, ...]
    field_evidence: tuple[_TitleFieldEvidence, ...]

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise ValueError("title candidate page number must be positive")
        if not isinstance(self.bounding_box, DrawingBoundingBox):
            raise TypeError("title candidate bounding box must be DrawingBoundingBox")
        if self.score < 0:
            raise ValueError("title candidate score must be nonnegative")
        if any(key not in _TITLE_FIELD_KEYS for key in self.recognized_field_keys):
            raise ValueError("title candidate has an invalid field key")
        if len(set(self.recognized_field_keys)) != len(self.recognized_field_keys):
            raise ValueError("title candidate field keys must be unique")
        if any(
            not isinstance(evidence, _TitleFieldEvidence)
            for evidence in self.field_evidence
        ):
            raise TypeError("title candidate evidence must be typed")


@dataclass(frozen=True)
class _AnalyzedTitleCandidate:
    candidate: _TitleBlockCandidate
    had_field_conflict: bool = False


@dataclass(frozen=True)
class _TitleRegion:
    page_number: int
    bounding_box: DrawingBoundingBox
    source_object_ids: tuple[str, ...]
    horizontal_segments: tuple[_AxisSegment, ...]
    vertical_segments: tuple[_AxisSegment, ...]
    cells: tuple[DrawingBoundingBox, ...]


@dataclass(frozen=True)
class _AxisSegment:
    orientation: str
    fixed: Decimal
    start: Decimal
    end: Decimal
    object_id: str


@dataclass(frozen=True)
class _WorkerExecution:
    snapshot: _PdfDocumentSnapshot | None
    failure_code: str | None
    page_count_expected: int | None = None
    page_count_parsed: int = 0
    title_candidates: tuple[_AnalyzedTitleCandidate, ...] = ()
    dimension_candidates: tuple[_DimensionCandidate, ...] = ()


@dataclass(frozen=True)
class _ToleranceCandidate:
    tolerance_type: DrawingToleranceType
    upper_value: Decimal
    lower_value: Decimal
    unit: str
    original_text: str
    bounding_box: DrawingBoundingBox
    source_object_ids: tuple[str, ...]


@dataclass(frozen=True)
class _DimensionCandidate:
    page_number: int
    nominal_value: Decimal
    unit: str
    dimension_type: DrawingDimensionType
    original_text: str
    bounding_box: DrawingBoundingBox
    source_object_ids: tuple[str, ...]
    tolerance: _ToleranceCandidate | None = None


class _ResourceLimitError(Exception):
    """Private control-flow signal; its details never cross the worker boundary."""

    def __init__(self, page_count_expected: int | None, page_count_parsed: int) -> None:
        super().__init__()
        self.page_count_expected = page_count_expected
        self.page_count_parsed = page_count_parsed


def _decimal(value: object) -> Decimal:
    try:
        converted = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError from exc
    if not converted.is_finite():
        raise ValueError
    return converted


def _bounding_box(source: dict[str, Any]) -> DrawingBoundingBox:
    return DrawingBoundingBox(
        x0=_decimal(source["x0"]),
        top=_decimal(source["top"]),
        x1=_decimal(source["x1"]),
        bottom=_decimal(source["bottom"]),
    )


def _source_points(
    source: dict[str, Any],
    *,
    maximum: int,
) -> tuple[tuple[Decimal, Decimal], ...]:
    raw_points = source.get("pts")
    if not isinstance(raw_points, (list, tuple)) or not raw_points:
        raise ValueError
    points: list[tuple[Decimal, Decimal]] = []
    for raw_point in raw_points:
        if len(points) >= maximum:
            raise _ResourceLimitError(None, 0)
        if not isinstance(raw_point, (list, tuple)) or len(raw_point) != 2:
            raise ValueError
        points.append((_decimal(raw_point[0]), _decimal(raw_point[1])))
    return tuple(points)


def _segments_for(
    kind: str,
    points: tuple[tuple[Decimal, Decimal], ...],
) -> tuple[tuple[tuple[Decimal, Decimal], ...], ...]:
    if kind == "line":
        if len(points) != 2:
            raise ValueError
        return ((points[0], points[1]),)
    if kind == "rectangle":
        if len(points) != 4:
            raise ValueError
        closed = (*points, points[0])
        return tuple((closed[index], closed[index + 1]) for index in range(4))
    if kind == "curve":
        if len(points) < 2:
            raise ValueError
        return (points,)
    raise ValueError


def _plain_decimal(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def _normalized_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value)


def _box_content(box: DrawingBoundingBox) -> str:
    return "|".join(
        _plain_decimal(value) for value in (box.x0, box.top, box.x1, box.bottom)
    )


def _object_digest(kind: str, box: DrawingBoundingBox, content: str) -> str:
    material = f"{kind}|{_box_content(box)}|{content}".encode()
    return sha256(material).hexdigest()[:16]


def _object_ref(
    *,
    page_number: int,
    kind: str,
    bounding_box: DrawingBoundingBox,
    normalized_content: str,
    duplicate_counts: dict[tuple[str, str], int],
) -> _PdfObjectRef:
    digest = _object_digest(kind, bounding_box, normalized_content)
    duplicate_key = (kind, digest)
    ordinal = duplicate_counts.get(duplicate_key, 0) + 1
    duplicate_counts[duplicate_key] = ordinal
    return _PdfObjectRef(
        object_id=f"pdf-p{page_number:04d}-{kind}-{digest}-{ordinal:04d}",
        page_number=page_number,
        kind=kind,
        bounding_box=bounding_box,
    )


def _sort_key(
    box: DrawingBoundingBox,
    kind: str,
    normalized_content: str,
    source_index: int,
) -> tuple[Decimal, Decimal, Decimal, Decimal, str, str, int]:
    return (
        box.top,
        box.x0,
        box.bottom,
        box.x1,
        kind,
        normalized_content,
        source_index,
    )


def _union_box(boxes: tuple[DrawingBoundingBox, ...]) -> DrawingBoundingBox:
    if not boxes:
        raise ValueError
    return DrawingBoundingBox(
        x0=min(box.x0 for box in boxes),
        top=min(box.top for box in boxes),
        x1=max(box.x1 for box in boxes),
        bottom=max(box.bottom for box in boxes),
    )


def _contains_disallowed_control(value: str, *, allow_newline: bool = False) -> bool:
    return any(
        unicodedata.category(character).startswith("C")
        and not (allow_newline and character == "\n")
        for character in value
    )


def _normalize_title_label(value: str) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = unicodedata.normalize("NFKC", value)
    if _contains_disallowed_control(normalized):
        return None
    normalized = normalized.upper()
    normalized = normalized.translate(str.maketrans({".": " ", "_": " ", "-": " "}))
    normalized = " ".join(normalized.split())
    if normalized.endswith(":"):
        normalized = " ".join(normalized[:-1].split())
    return normalized or None


def _title_field_key(value: str) -> str | None:
    normalized = _normalize_title_label(value)
    if normalized is None:
        return None
    return next(
        (field_key for alias, field_key in _TITLE_ALIASES if alias == normalized),
        None,
    )


def _normalize_title_value(field_key: str, value: str) -> str | None:
    if field_key not in _TITLE_FIELD_KEYS or not isinstance(value, str):
        return None
    if _contains_disallowed_control(value, allow_newline=True):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    lines = stripped.split("\n")
    if len(lines) > 1:
        if field_key not in {"part_name", "material"} or len(lines) != 2:
            return None
        if any(not line.strip() for line in lines):
            return None
        if any(_title_field_key(line.strip()) is not None for line in lines):
            return None
        if field_key == "part_name":
            canonical = " ".join(
                " ".join(unicodedata.normalize("NFKC", line).split())
                for line in lines
            )
        else:
            canonical = "\n".join(line.strip() for line in lines)
    elif field_key in {"material", "date"}:
        canonical = stripped
    else:
        canonical = " ".join(stripped.split())

    if not canonical or len(canonical) > _TITLE_FIELD_CAPS[field_key]:
        return None
    if _title_field_key(canonical) is not None:
        return None

    comparison = " ".join(unicodedata.normalize("NFKC", canonical).upper().split())
    if field_key == "sheet":
        match = _SHEET_PATTERN.fullmatch(comparison)
        if match is None:
            return None
        sheet_number = int(match.group(1))
        sheet_count = int(match.group(2)) if match.group(2) is not None else None
        if (
            sheet_number < 1
            or sheet_number > 10_000
            or (sheet_count is not None and (sheet_count < sheet_number or sheet_count > 10_000))
        ):
            return None
        return (
            str(sheet_number)
            if sheet_count is None
            else f"{sheet_number}/{sheet_count}"
        )
    if field_key == "scale":
        if comparison in {"NTS", "NOT TO SCALE"}:
            return comparison
        match = _SCALE_PATTERN.fullmatch(comparison)
        if match is None:
            return None
        left, right = (Decimal(match.group(1)), Decimal(match.group(2)))
        if left <= 0 or right <= 0:
            return None
        return f"{match.group(1)}:{match.group(2)}"
    if field_key == "unit":
        unit = {
            "MM": "mm",
            "MILLIMETER": "mm",
            "MILLIMETERS": "mm",
            "IN": "inch",
            "INCH": "inch",
            "INCHES": "inch",
        }.get(comparison)
        return unit
    return canonical


def _inline_title_pair(value: str) -> tuple[str, str] | None:
    if not isinstance(value, str) or "\n" in value or ":" not in value:
        return None
    label, raw_value = value.split(":", 1)
    field_key = _title_field_key(label)
    if field_key is None:
        return None
    canonical = _normalize_title_value(field_key, raw_value)
    if canonical is None:
        return None
    return field_key, canonical


def _inline_title_label_key(value: str) -> str | None:
    if not isinstance(value, str) or "\n" in value or ":" not in value:
        return None
    label, _ = value.split(":", 1)
    return _title_field_key(label)


def _axis_gap(
    first_start: Decimal,
    first_end: Decimal,
    second_start: Decimal,
    second_end: Decimal,
) -> Decimal:
    if first_end < second_start:
        return second_start - first_end
    if second_end < first_start:
        return first_start - second_end
    return Decimal("0")


def _within_title_distance(
    label: DrawingBoundingBox,
    value: DrawingBoundingBox,
) -> bool:
    horizontal_gap = _axis_gap(label.x0, label.x1, value.x0, value.x1)
    vertical_gap = _axis_gap(label.top, label.bottom, value.top, value.bottom)
    return max(horizontal_gap, vertical_gap) <= _TITLE_MAX_PAIR_DISTANCE_PT


def _resolve_title_field_evidence(
    evidence: tuple[_TitleFieldEvidence, ...],
    object_order: dict[str, int] | None = None,
) -> tuple[_TitleFieldEvidence | None, bool]:
    if not evidence:
        return None, False
    best_rank = min(item.pairing_rank for item in evidence)
    best = tuple(item for item in evidence if item.pairing_rank == best_rank)
    values = {item.value for item in best}
    if len(values) != 1:
        return None, True
    ordered = tuple(
        sorted(
            best,
            key=lambda item: (
                item.page_number,
                item.bounding_box.top,
                item.bounding_box.x0,
                item.bounding_box.bottom,
                item.bounding_box.x1,
                item.source_object_ids,
            ),
        )
    )
    unique_object_ids = set(
        object_id for item in ordered for object_id in item.source_object_ids
    )
    object_ids = tuple(
        sorted(
            unique_object_ids,
            key=lambda object_id: (
                object_order.get(object_id, len(object_order))
                if object_order is not None
                else 0,
                object_id,
            ),
        )
    )
    return (
        _TitleFieldEvidence(
            field_key=ordered[0].field_key,
            value=ordered[0].value,
            pairing_rank=best_rank,
            page_number=ordered[0].page_number,
            bounding_box=_union_box(tuple(item.bounding_box for item in ordered)),
            source_object_ids=object_ids,
            original_text=ordered[0].original_text,
        ),
        False,
    )


def _normalize_text_runs(
    page_number: int,
    candidates: tuple[_TextCandidate, ...],
) -> tuple[_PdfTextRun, ...]:
    ordered = sorted(
        candidates,
        key=lambda candidate: _sort_key(
            candidate.bounding_box,
            "text",
            _normalized_text(candidate.text),
            candidate.source_index,
        ),
    )
    duplicate_counts: dict[tuple[str, str], int] = {}
    return tuple(
        _PdfTextRun(
            ref=_object_ref(
                page_number=page_number,
                kind="text",
                bounding_box=candidate.bounding_box,
                normalized_content=_normalized_text(candidate.text),
                duplicate_counts=duplicate_counts,
            ),
            text=candidate.text,
        )
        for candidate in ordered
    )


def _path_content(
    segments: tuple[tuple[tuple[Decimal, Decimal], ...], ...],
) -> str:
    return ";".join(
        ",".join(f"{_plain_decimal(x)}:{_plain_decimal(y)}" for x, y in segment)
        for segment in segments
    )


def _normalize_vector_paths(
    page_number: int,
    candidates: tuple[_VectorCandidate, ...],
) -> tuple[_PdfVectorPath, ...]:
    ordered = sorted(
        candidates,
        key=lambda candidate: _sort_key(
            candidate.bounding_box,
            candidate.kind,
            _path_content(candidate.segments),
            candidate.source_index,
        ),
    )
    duplicate_counts: dict[tuple[str, str], int] = {}
    return tuple(
        _PdfVectorPath(
            ref=_object_ref(
                page_number=page_number,
                kind=candidate.kind,
                bounding_box=candidate.bounding_box,
                normalized_content=_path_content(candidate.segments),
                duplicate_counts=duplicate_counts,
            ),
            segments=candidate.segments,
        )
        for candidate in ordered
    )


def _text_lines(text_runs: tuple[_PdfTextRun, ...]) -> tuple[_TextLine, ...]:
    mutable_lines: list[list[_PdfTextRun]] = []
    ordered = sorted(
        text_runs,
        key=lambda run: (
            run.ref.bounding_box.bottom,
            run.ref.bounding_box.x0,
            run.ref.bounding_box.top,
            run.ref.object_id,
        ),
    )
    for run in ordered:
        run_box = run.ref.bounding_box
        selected: list[_PdfTextRun] | None = None
        for line in mutable_lines:
            line_box = _union_box(tuple(item.ref.bounding_box for item in line))
            baseline_delta = abs(run_box.bottom - line_box.bottom)
            horizontal_gap = run_box.x0 - line_box.x1
            if (
                baseline_delta <= _TEXT_LINE_BASELINE_TOLERANCE_PT
                and horizontal_gap <= _TEXT_HORIZONTAL_GAP_PT
            ):
                selected = line
                break
        if selected is None:
            mutable_lines.append([run])
        else:
            selected.append(run)

    lines: list[_TextLine] = []
    for mutable_line in mutable_lines:
        line_runs = tuple(
            sorted(
                mutable_line,
                key=lambda run: (
                    run.ref.bounding_box.x0,
                    run.ref.bounding_box.top,
                    run.ref.object_id,
                ),
            )
        )
        lines.append(
            _TextLine(
                runs=line_runs,
                bounding_box=_union_box(
                    tuple(run.ref.bounding_box for run in line_runs)
                ),
                text="".join(run.text for run in line_runs),
            )
        )
    return tuple(
        sorted(
            lines,
            key=lambda line: (
                line.bounding_box.top,
                line.bounding_box.x0,
                line.bounding_box.bottom,
                line.bounding_box.x1,
                line.text,
            ),
        )
    )


def _normalize_text_blocks(
    page_number: int,
    text_runs: tuple[_PdfTextRun, ...],
) -> tuple[_PdfTextBlock, ...]:
    mutable_blocks: list[list[_TextLine]] = []
    for line in _text_lines(text_runs):
        if mutable_blocks:
            previous = mutable_blocks[-1][-1]
            vertical_gap = line.bounding_box.top - previous.bounding_box.bottom
            left_delta = abs(line.bounding_box.x0 - previous.bounding_box.x0)
            if (
                Decimal("0") <= vertical_gap <= _TEXT_BLOCK_VERTICAL_GAP_PT
                and left_delta <= _TEXT_BLOCK_LEFT_EDGE_TOLERANCE_PT
            ):
                mutable_blocks[-1].append(line)
                continue
        mutable_blocks.append([line])

    duplicate_counts: dict[tuple[str, str], int] = {}
    blocks: list[_PdfTextBlock] = []
    for lines in mutable_blocks:
        line_tuple = tuple(lines)
        box = _union_box(tuple(line.bounding_box for line in line_tuple))
        text = "\n".join(line.text for line in line_tuple)
        blocks.append(
            _PdfTextBlock(
                ref=_object_ref(
                    page_number=page_number,
                    kind="text-block",
                    bounding_box=box,
                    normalized_content=_normalized_text(text),
                    duplicate_counts=duplicate_counts,
                ),
                text_run_ids=tuple(
                    run.ref.object_id for line in line_tuple for run in line.runs
                ),
                text=text,
            )
        )
    return tuple(blocks)


def _axis_segments(page: _PdfPageSnapshot) -> tuple[_AxisSegment, ...]:
    segments: list[_AxisSegment] = []
    for path in page.vector_paths:
        if path.ref.kind == "curve":
            continue
        for raw_segment in path.segments:
            if len(raw_segment) != 2:
                continue
            (x0, y0), (x1, y1) = raw_segment
            if abs(y1 - y0) <= _TITLE_AXIS_TOLERANCE_PT and x0 != x1:
                segments.append(
                    _AxisSegment(
                        orientation="horizontal",
                        fixed=(y0 + y1) / 2,
                        start=min(x0, x1),
                        end=max(x0, x1),
                        object_id=path.ref.object_id,
                    )
                )
            elif abs(x1 - x0) <= _TITLE_AXIS_TOLERANCE_PT and y0 != y1:
                segments.append(
                    _AxisSegment(
                        orientation="vertical",
                        fixed=(x0 + x1) / 2,
                        start=min(y0, y1),
                        end=max(y0, y1),
                        object_id=path.ref.object_id,
                    )
                )
    return tuple(segments)


def _point_meets_segment(
    point: tuple[Decimal, Decimal],
    segment: _AxisSegment,
) -> bool:
    x, y = point
    if segment.orientation == "horizontal":
        return (
            abs(y - segment.fixed) <= _TITLE_CONNECTION_TOLERANCE_PT
            and segment.start - _TITLE_CONNECTION_TOLERANCE_PT
            <= x
            <= segment.end + _TITLE_CONNECTION_TOLERANCE_PT
        )
    return (
        abs(x - segment.fixed) <= _TITLE_CONNECTION_TOLERANCE_PT
        and segment.start - _TITLE_CONNECTION_TOLERANCE_PT
        <= y
        <= segment.end + _TITLE_CONNECTION_TOLERANCE_PT
    )


def _segment_endpoints(
    segment: _AxisSegment,
) -> tuple[tuple[Decimal, Decimal], tuple[Decimal, Decimal]]:
    if segment.orientation == "horizontal":
        return (segment.start, segment.fixed), (segment.end, segment.fixed)
    return (segment.fixed, segment.start), (segment.fixed, segment.end)


def _segments_connected(first: _AxisSegment, second: _AxisSegment) -> bool:
    return any(
        _point_meets_segment(point, second)
        for point in _segment_endpoints(first)
    ) or any(
        _point_meets_segment(point, first)
        for point in _segment_endpoints(second)
    )


def _segment_components(
    segments: tuple[_AxisSegment, ...],
) -> tuple[tuple[_AxisSegment, ...], ...]:
    remaining = set(range(len(segments)))
    components: list[tuple[_AxisSegment, ...]] = []
    while remaining:
        seed = min(remaining)
        remaining.remove(seed)
        stack = [seed]
        component = [seed]
        while stack:
            current = stack.pop()
            connected = tuple(
                index
                for index in sorted(remaining)
                if _segments_connected(segments[current], segments[index])
            )
            for index in connected:
                remaining.remove(index)
                stack.append(index)
                component.append(index)
        components.append(tuple(segments[index] for index in sorted(component)))
    return tuple(components)


def _interval_is_covered(
    start: Decimal,
    end: Decimal,
    intervals: tuple[tuple[Decimal, Decimal], ...],
) -> bool:
    cursor = start
    for interval_start, interval_end in sorted(intervals):
        clipped_start = max(start, interval_start)
        clipped_end = min(end, interval_end)
        if clipped_end < clipped_start:
            continue
        if clipped_start > cursor + _TITLE_CONNECTION_TOLERANCE_PT:
            return False
        cursor = max(cursor, clipped_end)
        if cursor >= end - _TITLE_CONNECTION_TOLERANCE_PT:
            return True
    return cursor >= end - _TITLE_CONNECTION_TOLERANCE_PT


def _rectangle_is_covered(
    box: DrawingBoundingBox,
    horizontal: tuple[_AxisSegment, ...],
    vertical: tuple[_AxisSegment, ...],
) -> bool:
    return all(
        (
            _interval_is_covered(
                box.x0,
                box.x1,
                tuple(
                    (segment.start, segment.end)
                    for segment in horizontal
                    if abs(segment.fixed - box.top) <= _TITLE_AXIS_TOLERANCE_PT
                ),
            ),
            _interval_is_covered(
                box.x0,
                box.x1,
                tuple(
                    (segment.start, segment.end)
                    for segment in horizontal
                    if abs(segment.fixed - box.bottom)
                    <= _TITLE_AXIS_TOLERANCE_PT
                ),
            ),
            _interval_is_covered(
                box.top,
                box.bottom,
                tuple(
                    (segment.start, segment.end)
                    for segment in vertical
                    if abs(segment.fixed - box.x0) <= _TITLE_AXIS_TOLERANCE_PT
                ),
            ),
            _interval_is_covered(
                box.top,
                box.bottom,
                tuple(
                    (segment.start, segment.end)
                    for segment in vertical
                    if abs(segment.fixed - box.x1) <= _TITLE_AXIS_TOLERANCE_PT
                ),
            ),
        )
    )


def _closed_rectangles(
    segments: tuple[_AxisSegment, ...],
) -> tuple[DrawingBoundingBox, ...]:
    horizontal = tuple(
        segment for segment in segments if segment.orientation == "horizontal"
    )
    vertical = tuple(
        segment for segment in segments if segment.orientation == "vertical"
    )
    x_values = tuple(sorted({segment.fixed for segment in vertical}))
    y_values = tuple(sorted({segment.fixed for segment in horizontal}))
    rectangles: list[DrawingBoundingBox] = []
    for top_index, top in enumerate(y_values):
        for bottom in y_values[top_index + 1 :]:
            side_x_values = tuple(
                x
                for x in x_values
                if _interval_is_covered(
                    top,
                    bottom,
                    tuple(
                        (segment.start, segment.end)
                        for segment in vertical
                        if abs(segment.fixed - x) <= _TITLE_AXIS_TOLERANCE_PT
                    ),
                )
            )
            for left_index, x0 in enumerate(side_x_values):
                for x1 in side_x_values[left_index + 1 :]:
                    box = DrawingBoundingBox(
                        x0=x0,
                        top=top,
                        x1=x1,
                        bottom=bottom,
                    )
                    if _rectangle_is_covered(box, horizontal, vertical):
                        rectangles.append(box)
    return tuple(
        sorted(
            set(rectangles),
            key=lambda box: (box.top, box.x0, box.bottom, box.x1),
        )
    )


def _strictly_contains(
    outer: DrawingBoundingBox,
    inner: DrawingBoundingBox,
) -> bool:
    return outer != inner and (
        outer.x0 <= inner.x0
        and outer.top <= inner.top
        and outer.x1 >= inner.x1
        and outer.bottom >= inner.bottom
    )


def _title_regions(page: _PdfPageSnapshot) -> tuple[_TitleRegion, ...]:
    segments = _axis_segments(page)
    object_order = {
        path.ref.object_id: index for index, path in enumerate(page.vector_paths)
    }
    explicit_boxes = {
        path.ref.bounding_box
        for path in page.vector_paths
        if path.ref.kind == "rectangle"
    }
    connected_boxes: set[DrawingBoundingBox] = set()
    for component in _segment_components(segments):
        closed = _closed_rectangles(component)
        connected_boxes.update(
            box
            for box in closed
            if not any(_strictly_contains(other, box) for other in closed)
        )
    candidate_boxes = explicit_boxes | connected_boxes

    regions: dict[
        tuple[int, DrawingBoundingBox, tuple[str, ...]], _TitleRegion
    ] = {}
    for box in sorted(
        candidate_boxes,
        key=lambda item: (item.top, item.x0, item.bottom, item.x1),
    ):
        contained = tuple(
            segment
            for segment in segments
            if (
                box.top - _TITLE_CONNECTION_TOLERANCE_PT
                <= segment.fixed
                <= box.bottom + _TITLE_CONNECTION_TOLERANCE_PT
                and box.x0 - _TITLE_CONNECTION_TOLERANCE_PT
                <= segment.start
                <= segment.end
                <= box.x1 + _TITLE_CONNECTION_TOLERANCE_PT
            )
            if segment.orientation == "horizontal"
        ) + tuple(
            segment
            for segment in segments
            if (
                box.x0 - _TITLE_CONNECTION_TOLERANCE_PT
                <= segment.fixed
                <= box.x1 + _TITLE_CONNECTION_TOLERANCE_PT
                and box.top - _TITLE_CONNECTION_TOLERANCE_PT
                <= segment.start
                <= segment.end
                <= box.bottom + _TITLE_CONNECTION_TOLERANCE_PT
            )
            if segment.orientation == "vertical"
        )
        boundary = {
            index
            for index, segment in enumerate(contained)
            if (
                segment.orientation == "horizontal"
                and (
                    abs(segment.fixed - box.top) <= _TITLE_AXIS_TOLERANCE_PT
                    or abs(segment.fixed - box.bottom) <= _TITLE_AXIS_TOLERANCE_PT
                )
            )
            or (
                segment.orientation == "vertical"
                and (
                    abs(segment.fixed - box.x0) <= _TITLE_AXIS_TOLERANCE_PT
                    or abs(segment.fixed - box.x1) <= _TITLE_AXIS_TOLERANCE_PT
                )
            )
        }
        connected_indices = set(boundary)
        stack = list(sorted(boundary))
        while stack:
            current = stack.pop()
            for index, segment in enumerate(contained):
                if index in connected_indices:
                    continue
                if _segments_connected(contained[current], segment):
                    connected_indices.add(index)
                    stack.append(index)
        component = tuple(contained[index] for index in sorted(connected_indices))
        horizontal = tuple(
            segment for segment in component if segment.orientation == "horizontal"
        )
        vertical = tuple(
            segment for segment in component if segment.orientation == "vertical"
        )
        if len(horizontal) < 3 or len(vertical) < 3:
            continue
        if not _rectangle_is_covered(box, horizontal, vertical):
            continue
        horizontal_separators = tuple(
            segment
            for segment in horizontal
            if box.top + _TITLE_AXIS_TOLERANCE_PT
            < segment.fixed
            < box.bottom - _TITLE_AXIS_TOLERANCE_PT
        )
        vertical_separators = tuple(
            segment
            for segment in vertical
            if box.x0 + _TITLE_AXIS_TOLERANCE_PT
            < segment.fixed
            < box.x1 - _TITLE_AXIS_TOLERANCE_PT
        )
        if not horizontal_separators or not vertical_separators:
            continue
        source_ids = tuple(
            sorted(
                {segment.object_id for segment in component},
                key=lambda object_id: (object_order[object_id], object_id),
            )
        )
        region = _TitleRegion(
            page_number=page.page_number,
            bounding_box=box,
            source_object_ids=source_ids,
            horizontal_segments=horizontal,
            vertical_segments=vertical,
            cells=_closed_rectangles(component),
        )
        regions[(page.page_number, box, source_ids)] = region
    return tuple(
        sorted(
            regions.values(),
            key=lambda region: (
                region.page_number,
                region.bounding_box.top,
                region.bounding_box.x0,
                region.bounding_box.bottom,
                region.bounding_box.x1,
                region.source_object_ids,
            ),
        )
    )


def _box_center_is_inside(
    inner: DrawingBoundingBox,
    outer: DrawingBoundingBox,
) -> bool:
    center_x = (inner.x0 + inner.x1) / 2
    center_y = (inner.top + inner.bottom) / 2
    return outer.x0 <= center_x <= outer.x1 and outer.top <= center_y <= outer.bottom


def _cell_for(
    box: DrawingBoundingBox,
    region: _TitleRegion,
) -> DrawingBoundingBox:
    center_x = (box.x0 + box.x1) / 2
    center_y = (box.top + box.bottom) / 2
    containing = tuple(
        cell
        for cell in region.cells
        if cell.x0 <= center_x <= cell.x1 and cell.top <= center_y <= cell.bottom
    )
    return min(
        containing,
        default=region.bounding_box,
        key=lambda cell: (
            (cell.x1 - cell.x0) * (cell.bottom - cell.top),
            cell.top,
            cell.x0,
            cell.bottom,
            cell.x1,
        ),
    )


def _box_is_within_cell(
    box: DrawingBoundingBox,
    cell: DrawingBoundingBox,
) -> bool:
    return (
        cell.x0 <= box.x0 <= box.x1 <= cell.x1
        and cell.top <= box.top <= box.bottom <= cell.bottom
    )


def _cell_is_immediately_right(
    label_cell: DrawingBoundingBox,
    value_cell: DrawingBoundingBox,
) -> bool:
    return (
        abs(label_cell.x1 - value_cell.x0) <= _TITLE_AXIS_TOLERANCE_PT
        and min(label_cell.bottom, value_cell.bottom)
        > max(label_cell.top, value_cell.top)
    )


def _cell_is_immediately_below(
    label_cell: DrawingBoundingBox,
    value_cell: DrawingBoundingBox,
) -> bool:
    return (
        abs(label_cell.bottom - value_cell.top) <= _TITLE_AXIS_TOLERANCE_PT
        and min(label_cell.x1, value_cell.x1) > max(label_cell.x0, value_cell.x0)
    )


def _ordered_object_ids(
    object_ids: tuple[str, ...],
    object_order: dict[str, int],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            set(object_ids),
            key=lambda object_id: (object_order.get(object_id, len(object_order)), object_id),
        )
    )


def _canonical_dimension_unit(value: str) -> str | None:
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    return {
        "mm": "mm",
        "millimeter": "mm",
        "millimeters": "mm",
        "in": "inch",
        "inch": "inch",
        "inches": "inch",
        "degree": "degree",
        "deg": "degree",
    }.get(normalized)


def _parse_dimension_decimal(value: str) -> Decimal | None:
    token = value.strip()
    if token.count(",") and token.count("."):
        return None
    if token.count(",") > 1:
        return None
    if "," in token:
        integer_part, fractional_part = token.split(",", 1)
        if len(fractional_part) == 3 and len(integer_part) >= 1:
            return None
        token = token.replace(",", ".")
    try:
        parsed = Decimal(token)
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed < 0:
        return None
    return parsed


def _dimension_text_copy(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.replace("\n", " ").split())


def _dimension_title_regions(
    snapshot: _PdfDocumentSnapshot,
) -> tuple[_TitleRegion, ...]:
    return tuple(region for page in snapshot.pages for region in _title_regions(page))


def _dimension_unit_fallback(
    title_candidates: tuple[_AnalyzedTitleCandidate, ...],
) -> str | None:
    if not title_candidates:
        return None
    highest = title_candidates[0].candidate.score
    selected = tuple(
        item for item in title_candidates if item.candidate.score == highest
    )
    if len(selected) != 1:
        return None
    units = tuple(
        evidence.value
        for evidence in selected[0].candidate.field_evidence
        if evidence.field_key == "unit"
    )
    return units[0] if len(set(units)) == 1 else None


def _dimension_text_is_excluded(
    block: _PdfTextBlock,
    regions: tuple[_TitleRegion, ...],
) -> bool:
    return any(
        region.page_number == block.ref.page_number
        and _box_center_is_inside(block.ref.bounding_box, region.bounding_box)
        for region in regions
    )


def _text_within_dimension_band(
    block: DrawingBoundingBox,
    segment: _AxisSegment,
) -> bool:
    if segment.orientation == "horizontal":
        return (
            _axis_gap(segment.fixed, segment.fixed, block.top, block.bottom)
            <= _DIMENSION_BAND_PT
        )
    return (
        _axis_gap(segment.fixed, segment.fixed, block.x0, block.x1)
        <= _DIMENSION_BAND_PT
    )


def _point_distance_to_endpoint(
    point: tuple[Decimal, Decimal],
    segment: _AxisSegment,
) -> Decimal:
    endpoints = _segment_endpoints(segment)
    return min(
        max(abs(point[0] - endpoint[0]), abs(point[1] - endpoint[1]))
        for endpoint in endpoints
    )


def _bare_dimension_geometry_cue(
    page: _PdfPageSnapshot,
    block: _PdfTextBlock,
) -> tuple[tuple[str, ...], DrawingBoundingBox] | None:
    axis_segments = _axis_segments(page)
    path_by_id = {path.ref.object_id: path for path in page.vector_paths}
    matches: list[tuple[_AxisSegment, tuple[_AxisSegment, _AxisSegment]]] = []
    for dimension_line in axis_segments:
        if dimension_line.end - dimension_line.start < _DIMENSION_AXIS_MIN_PT:
            continue
        if not _text_within_dimension_band(block.ref.bounding_box, dimension_line):
            continue
        perpendicular = tuple(
            candidate
            for candidate in axis_segments
            if candidate.object_id != dimension_line.object_id
            and candidate.orientation != dimension_line.orientation
        )
        endpoints = _segment_endpoints(dimension_line)
        assignments: list[tuple[_AxisSegment, _AxisSegment]] = []
        for first in perpendicular:
            for second in perpendicular:
                if first.object_id >= second.object_id:
                    continue
                for ordered in ((first, second), (second, first)):
                    if all(
                        any(
                            max(
                                abs(point[0] - endpoint[0]),
                                abs(point[1] - endpoint[1]),
                            ) <= _DIMENSION_CONNECTION_TOLERANCE_PT
                            for point in _segment_endpoints(extension)
                        )
                        for endpoint, extension in zip(
                            endpoints, ordered, strict=True
                        )
                    ):
                        assignments.append(ordered)
        if len(assignments) == 1:
            matches.append((dimension_line, assignments[0]))
    if len(matches) != 1:
        return None
    dimension_line, extensions = matches[0]
    ids = (block.ref.object_id, dimension_line.object_id, *(item.object_id for item in extensions))
    object_order = {
        object_id: index
        for index, object_id in enumerate(
            [run.ref.object_id for run in page.text_runs]
            + [path.ref.object_id for path in page.vector_paths]
        )
    }
    return _ordered_object_ids(ids, object_order), _union_box(
        (
            block.ref.bounding_box,
            *(_path_box(path_by_id[item.object_id]) for item in extensions),
            path_by_id[dimension_line.object_id].ref.bounding_box,
        )
    )


def _path_box(path: _PdfVectorPath) -> DrawingBoundingBox:
    return path.ref.bounding_box


def _parse_tolerance(
    match: re.Match[str],
    unit: str,
    original_text: str,
    box: DrawingBoundingBox,
    source_object_ids: tuple[str, ...],
) -> _ToleranceCandidate | None:
    symmetric = match.group("sym")
    if symmetric is not None:
        amount = _parse_dimension_decimal(symmetric)
        if amount is None or amount <= 0:
            return None
        return _ToleranceCandidate(
            DrawingToleranceType.SYMMETRIC, amount, -amount, unit,
            original_text, box, source_object_ids,
        )
    upper_text = match.group("upper")
    lower_text = match.group("lower")
    if upper_text is not None and lower_text is not None:
        upper = _parse_dimension_decimal(upper_text)
        lower = _parse_dimension_decimal(lower_text)
        if upper is None or lower is None or (upper == 0 and lower == 0):
            return None
        if upper == 0:
            kind = DrawingToleranceType.UNILATERAL_MINUS
        elif lower == 0:
            kind = DrawingToleranceType.UNILATERAL_PLUS
        else:
            kind = DrawingToleranceType.ASYMMETRIC
        return _ToleranceCandidate(
            kind, upper, -lower, unit, original_text, box, source_object_ids
        )
    unilateral_plus = match.group("unilateral_plus")
    if unilateral_plus is not None:
        upper = _parse_dimension_decimal(unilateral_plus)
        if upper is None or upper <= 0:
            return None
        return _ToleranceCandidate(
            DrawingToleranceType.UNILATERAL_PLUS, upper, Decimal("0"), unit,
            original_text, box, source_object_ids,
        )
    unilateral_minus = match.group("unilateral_minus")
    if unilateral_minus is not None:
        lower = _parse_dimension_decimal(unilateral_minus)
        if lower is None or lower <= 0:
            return None
        return _ToleranceCandidate(
            DrawingToleranceType.UNILATERAL_MINUS, Decimal("0"), -lower, unit,
            original_text, box, source_object_ids,
        )
    return None


def _extract_dimension_candidates(
    snapshot: _PdfDocumentSnapshot,
    limits: PdfDrawingLimits,
    title_candidates: tuple[_AnalyzedTitleCandidate, ...] = (),
) -> tuple[_DimensionCandidate, ...]:
    title_regions = _dimension_title_regions(snapshot)
    fallback_unit = _dimension_unit_fallback(title_candidates)
    candidates: list[_DimensionCandidate] = []
    for page in snapshot.pages:
        page_regions = tuple(
            region
            for region in title_regions
            if region.page_number == page.page_number
        )
        for block in page.text_blocks:
            original = block.text.strip()
            if not original or len(original) > _DIMENSION_MAX_TEXT:
                continue
            if _dimension_text_is_excluded(block, page_regions):
                continue
            text = _dimension_text_copy(original)
            cue_box: DrawingBoundingBox | None = None
            source_ids: tuple[str, ...] = (block.ref.object_id, *block.text_run_ids)
            tolerance_match = _DIMENSION_TOLERANCE_PATTERN.fullmatch(text)
            token_match = _DIMENSION_TOKEN_PATTERN.fullmatch(text)
            tolerance = None
            dimension_type = DrawingDimensionType.LINEAR
            unit = None
            value_text = None
            if tolerance_match is not None:
                unit = _canonical_dimension_unit(tolerance_match.group("unit"))
                value_text = tolerance_match.group("nominal")
                tolerance = _parse_tolerance(
                    tolerance_match,
                    unit or "",
                    original,
                    block.ref.bounding_box,
                    (block.ref.object_id, *block.text_run_ids),
                ) if unit is not None else None
                if tolerance is None:
                    continue
            elif token_match is not None:
                value_text = token_match.group("value")
                if token_match.group("angle") is not None:
                    unit = "degree"
                    dimension_type = DrawingDimensionType.ANGULAR
                else:
                    unit = _canonical_dimension_unit(token_match.group("unit") or "")
                    prefix = (token_match.group("prefix") or "").upper()
                    if prefix in {"R", "RAD"}:
                        dimension_type = DrawingDimensionType.RADIAL
                    elif prefix in {"DIA", "Ø", "⌀"}:
                        dimension_type = DrawingDimensionType.DIAMETRAL
                if unit is None:
                    continue
            elif _DIMENSION_BARE_PATTERN.fullmatch(text) is not None:
                cue = _bare_dimension_geometry_cue(page, block)
                if cue is None or fallback_unit is None:
                    continue
                unit = fallback_unit
                value_text = text
                source_ids, cue_box = cue
            else:
                continue
            value = _parse_dimension_decimal(value_text or "")
            if value is None or unit is None:
                continue
            if cue_box is None:
                cue_box = block.ref.bounding_box
            candidates.append(
                _DimensionCandidate(
                    page_number=page.page_number,
                    nominal_value=value,
                    unit=unit,
                    dimension_type=dimension_type,
                    original_text=original[:_DIMENSION_MAX_TEXT],
                    bounding_box=cue_box,
                    source_object_ids=source_ids,
                    tolerance=tolerance,
                )
            )
            if len(candidates) > limits.max_dimension_candidates:
                raise _ResourceLimitError(len(snapshot.pages), page.page_number)
    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.page_number,
                item.bounding_box.top,
                item.bounding_box.x0,
                item.bounding_box.bottom,
                item.bounding_box.x1,
                _dimension_text_copy(item.original_text),
                item.source_object_ids,
            ),
        )
    )


def _canonical_dimension_pair(
    source_id: str,
    candidate: _DimensionCandidate,
    ordinal: int,
) -> tuple[DrawingDimension, DrawingTolerance | None]:
    """Map one accepted evidence item without adding geometry semantics."""

    location = _source_location(
        source_id,
        candidate.page_number,
        bounding_box=candidate.bounding_box,
        source_object_ids=candidate.source_object_ids,
        original_text=candidate.original_text,
    )
    tolerance = None
    if candidate.tolerance is not None:
        evidence = candidate.tolerance
        tolerance = DrawingTolerance(
            tolerance_id=f"pdf-tol-p{candidate.page_number:04d}-{ordinal:06d}",
            tolerance_type=evidence.tolerance_type,
            unit=evidence.unit,
            upper_value=evidence.upper_value,
            lower_value=evidence.lower_value,
            source_location=_source_location(
                source_id,
                candidate.page_number,
                bounding_box=evidence.bounding_box,
                source_object_ids=evidence.source_object_ids,
                original_text=evidence.original_text,
            ),
        )
    dimension = DrawingDimension(
        dimension_id=f"pdf-dim-p{candidate.page_number:04d}-{ordinal:06d}",
        nominal_value=candidate.nominal_value,
        unit=candidate.unit,
        dimension_type=candidate.dimension_type,
        tolerance=tolerance,
        referenced_entity_ids=(),
        source_location=location,
    )
    return dimension, tolerance


def _evidence_from_blocks(
    *,
    field_key: str,
    canonical_value: str,
    pairing_rank: int,
    page_number: int,
    blocks: tuple[_PdfTextBlock, ...],
    object_order: dict[str, int],
) -> _TitleFieldEvidence:
    return _TitleFieldEvidence(
        field_key=field_key,
        value=canonical_value,
        pairing_rank=pairing_rank,
        page_number=page_number,
        bounding_box=_union_box(tuple(block.ref.bounding_box for block in blocks)),
        source_object_ids=_ordered_object_ids(
            tuple(object_id for block in blocks for object_id in block.text_run_ids),
            object_order,
        ),
        original_text=canonical_value,
    )


def _adjacent_run_evidence(
    page: _PdfPageSnapshot,
    block: _PdfTextBlock,
    object_order: dict[str, int],
) -> _TitleFieldEvidence | None:
    if "\n" in block.text or _title_field_key(block.text) is not None:
        return None
    runs_by_id = {run.ref.object_id: run for run in page.text_runs}
    runs = tuple(runs_by_id[object_id] for object_id in block.text_run_ids)
    matches: list[tuple[int, str, str, str | None]] = []
    for split_at in range(1, len(runs)):
        field_key = _title_field_key("".join(run.text for run in runs[:split_at]))
        if field_key is None:
            continue
        raw_value = "".join(run.text for run in runs[split_at:])
        matches.append(
            (
                split_at,
                field_key,
                raw_value,
                _normalize_title_value(field_key, raw_value),
            )
        )
    if not matches:
        return None
    split_at, field_key, _, canonical = max(matches, key=lambda match: match[0])
    if canonical is None:
        return None
    label_box = _union_box(tuple(run.ref.bounding_box for run in runs[:split_at]))
    value_box = _union_box(tuple(run.ref.bounding_box for run in runs[split_at:]))
    if not _within_title_distance(label_box, value_box):
        return None
    return _TitleFieldEvidence(
        field_key=field_key,
        value=canonical,
        pairing_rank=2,
        page_number=page.page_number,
        bounding_box=_union_box((label_box, value_box)),
        source_object_ids=_ordered_object_ids(block.text_run_ids, object_order),
        original_text=canonical,
    )


def _adjacent_run_label_key(
    page: _PdfPageSnapshot,
    block: _PdfTextBlock,
) -> str | None:
    if "\n" in block.text or _title_field_key(block.text) is not None:
        return None
    runs_by_id = {run.ref.object_id: run for run in page.text_runs}
    runs = tuple(runs_by_id[object_id] for object_id in block.text_run_ids)
    matches = tuple(
        (split_at, field_key)
        for split_at in range(1, len(runs))
        if (
            field_key := _title_field_key(
                "".join(run.text for run in runs[:split_at])
            )
        )
        is not None
    )
    return max(matches, default=(0, None), key=lambda match: match[0])[1]


def _analyze_title_region(
    page: _PdfPageSnapshot,
    region: _TitleRegion,
) -> _AnalyzedTitleCandidate | None:
    blocks = tuple(
        block
        for block in page.text_blocks
        if block.text.strip() and _box_center_is_inside(block.ref.bounding_box, region.bounding_box)
    )
    if len(blocks) < 4:
        return None
    object_order = {
        run.ref.object_id: index for index, run in enumerate(page.text_runs)
    }
    cells: dict[DrawingBoundingBox, list[_PdfTextBlock]] = {}
    for block in blocks:
        cells.setdefault(_cell_for(block.ref.bounding_box, region), []).append(block)

    recognized_blocks: set[str] = set()
    recognized_keys: set[str] = set()
    evidence: list[_TitleFieldEvidence] = []
    exact_labels: list[tuple[_PdfTextBlock, str, DrawingBoundingBox]] = []
    for block in blocks:
        inline_label_key = _inline_title_label_key(block.text)
        if inline_label_key is not None:
            recognized_blocks.add(block.ref.object_id)
            recognized_keys.add(inline_label_key)
        inline_pair = _inline_title_pair(block.text)
        if inline_pair is not None:
            field_key, canonical = inline_pair
            evidence.append(
                _evidence_from_blocks(
                    field_key=field_key,
                    canonical_value=canonical,
                    pairing_rank=1,
                    page_number=page.page_number,
                    blocks=(block,),
                    object_order=object_order,
                )
            )
        adjacent_label_key = _adjacent_run_label_key(page, block)
        if adjacent_label_key is not None:
            recognized_blocks.add(block.ref.object_id)
            recognized_keys.add(adjacent_label_key)
        adjacent = _adjacent_run_evidence(page, block, object_order)
        if adjacent is not None:
            evidence.append(adjacent)
        field_key = _title_field_key(block.text)
        if field_key is not None:
            recognized_blocks.add(block.ref.object_id)
            recognized_keys.add(field_key)
            cell = _cell_for(block.ref.bounding_box, region)
            if _box_is_within_cell(block.ref.bounding_box, cell):
                exact_labels.append((block, field_key, cell))

    label_block_ids = {block.ref.object_id for block, _, _ in exact_labels}
    ambiguous_ranks: dict[str, int] = {}
    for label, field_key, label_cell in exact_labels:
        target_cells_by_rank = (
            (3, (label_cell,)),
            (
                4,
                tuple(
                    cell
                    for cell in cells
                    if _cell_is_immediately_right(label_cell, cell)
                ),
            ),
            (
                5,
                tuple(
                    cell
                    for cell in cells
                    if _cell_is_immediately_below(label_cell, cell)
                ),
            ),
        )
        for pairing_rank, target_cells in target_cells_by_rank:
            values = tuple(
                block
                for target_cell in target_cells
                for block in cells.get(target_cell, ())
                if (
                    block.ref.object_id not in label_block_ids
                    and _box_is_within_cell(block.ref.bounding_box, target_cell)
                    and _inline_title_label_key(block.text) is None
                    and _title_field_key(block.text) is None
                )
            )
            if len(values) > 1:
                ambiguous_ranks[field_key] = min(
                    pairing_rank,
                    ambiguous_ranks.get(field_key, pairing_rank),
                )
                break
            if not values:
                continue
            value = values[0]
            if not _within_title_distance(label.ref.bounding_box, value.ref.bounding_box):
                continue
            canonical = _normalize_title_value(field_key, value.text)
            if canonical is None:
                if "\n" in value.text:
                    ambiguous_ranks[field_key] = min(
                        pairing_rank,
                        ambiguous_ranks.get(field_key, pairing_rank),
                    )
                    break
                continue
            evidence.append(
                _evidence_from_blocks(
                    field_key=field_key,
                    canonical_value=canonical,
                    pairing_rank=pairing_rank,
                    page_number=page.page_number,
                    blocks=(label, value),
                    object_order=object_order,
                )
            )
            break

    if Decimal(len(recognized_blocks)) / Decimal(len(blocks)) < _TITLE_MIN_LABEL_DENSITY:
        return None
    resolved: list[_TitleFieldEvidence] = []
    had_field_conflict = False
    for field_key in _TITLE_FIELD_ORDER:
        field_evidence = tuple(
            item for item in evidence if item.field_key == field_key
        )
        ambiguous_rank = ambiguous_ranks.get(field_key)
        best_evidence_rank = min(
            (item.pairing_rank for item in field_evidence),
            default=None,
        )
        if ambiguous_rank is not None and (
            best_evidence_rank is None or ambiguous_rank <= best_evidence_rank
        ):
            selected, conflicted = None, True
        else:
            selected, conflicted = _resolve_title_field_evidence(
                field_evidence,
                object_order,
            )
        had_field_conflict = had_field_conflict or conflicted
        if selected is not None:
            resolved.append(selected)
    pair_count = len(resolved)
    score = (
        4
        + 2
        + min(18, 3 * len(recognized_keys))
        + min(12, 2 * pair_count)
    )
    if score < _TITLE_MIN_SCORE or pair_count < _TITLE_MIN_PAIR_COUNT:
        return None
    text_ids = tuple(
        object_id for item in resolved for object_id in item.source_object_ids
    )
    candidate = _TitleBlockCandidate(
        page_number=page.page_number,
        bounding_box=region.bounding_box,
        source_object_ids=(
            *region.source_object_ids,
            *_ordered_object_ids(text_ids, object_order),
        ),
        score=score,
        recognized_field_keys=tuple(
            field_key for field_key in _TITLE_FIELD_ORDER if field_key in recognized_keys
        ),
        field_evidence=tuple(resolved),
    )
    return _AnalyzedTitleCandidate(
        candidate=candidate,
        had_field_conflict=had_field_conflict,
    )


def _extract_title_candidates(
    snapshot: _PdfDocumentSnapshot,
    limits: PdfDrawingLimits,
) -> tuple[_AnalyzedTitleCandidate, ...]:
    regions = tuple(
        region
        for page in snapshot.pages
        for region in _title_regions(page)
        if sum(
            1
            for block in page.text_blocks
            if block.text.strip()
            and _box_center_is_inside(block.ref.bounding_box, region.bounding_box)
        )
        >= 4
    )
    if len(regions) > limits.max_title_block_candidates:
        raise _ResourceLimitError(len(snapshot.pages), len(snapshot.pages))
    pages_by_number = {page.page_number: page for page in snapshot.pages}
    analyzed = tuple(
        candidate
        for region in regions
        if (
            candidate := _analyze_title_region(
                pages_by_number[region.page_number],
                region,
            )
        )
        is not None
    )
    return tuple(
        sorted(
            analyzed,
            key=lambda analyzed_candidate: (
                -analyzed_candidate.candidate.score,
                analyzed_candidate.candidate.page_number,
                analyzed_candidate.candidate.bounding_box.top,
                analyzed_candidate.candidate.bounding_box.x0,
                analyzed_candidate.candidate.bounding_box.bottom,
                analyzed_candidate.candidate.bounding_box.x1,
                analyzed_candidate.candidate.source_object_ids,
            ),
        )
    )


def _source_location(
    source_id: str,
    page_number: int,
    *,
    bounding_box: DrawingBoundingBox | None = None,
    source_object_ids: tuple[str, ...] = (),
    original_text: str | None = None,
) -> DrawingSourceLocation:
    return DrawingSourceLocation(
        source_id=source_id,
        sheet_number=page_number,
        page_number=page_number,
        original_text=original_text,
        adapter_id=_PARSER_ID,
        adapter_version=_PARSER_VERSION,
        authority=DrawingExtractionAuthority.EXTRACTED,
        bounding_box=bounding_box,
        source_object_ids=source_object_ids,
    )


def _technical_metadata(
    snapshot: _PdfDocumentSnapshot,
    unit: str | None,
) -> dict[str, str]:
    entries = {
        "pdf.page_count": str(len(snapshot.pages)),
        "pdf.text_character_count": str(snapshot.text_character_count),
        "pdf.vector_object_count": str(
            sum(len(page.vector_paths) for page in snapshot.pages)
        ),
        "pdf.version": snapshot.pdf_version,
    }
    if unit is not None:
        entries["drawing.unit"] = unit
    for page in snapshot.pages:
        prefix = f"pdf.page.{page.page_number:04d}"
        entries[f"{prefix}.width_pt"] = _plain_decimal(page.width_pt)
        entries[f"{prefix}.height_pt"] = _plain_decimal(page.height_pt)
        entries[f"{prefix}.rotation"] = str(page.rotation)
    return dict(sorted(entries.items()))


def _build_title_document(
    source_id: str,
    content: bytes,
    snapshot: _PdfDocumentSnapshot,
    analyzed: _AnalyzedTitleCandidate,
) -> tuple[CanonicalDrawing, bool]:
    candidate = analyzed.candidate
    fields = {item.field_key: item for item in candidate.field_evidence}
    revision_evidence = fields.get("revision")
    revision = None
    if revision_evidence is not None:
        revision = DrawingRevision(
            revision_code=revision_evidence.value,
            source_location=_source_location(
                source_id,
                candidate.page_number,
                bounding_box=revision_evidence.bounding_box,
                source_object_ids=revision_evidence.source_object_ids,
                original_text=revision_evidence.value,
            ),
        )

    material_evidence = fields.get("material")
    material_notes: tuple[DrawingMaterialNote, ...] = ()
    if material_evidence is not None:
        material_notes = (
            DrawingMaterialNote(
                note_id=f"pdf-material-p{candidate.page_number:04d}-000001",
                raw_text=material_evidence.value,
                source_location=_source_location(
                    source_id,
                    candidate.page_number,
                    bounding_box=material_evidence.bounding_box,
                    source_object_ids=material_evidence.source_object_ids,
                    original_text=material_evidence.value,
                ),
            ),
        )

    declared_sheet_number = None
    declared_sheet_count = None
    sheet_evidence = fields.get("sheet")
    if sheet_evidence is not None:
        sheet_parts = sheet_evidence.value.split("/", 1)
        declared_sheet_number = int(sheet_parts[0])
        if len(sheet_parts) == 2:
            declared_sheet_count = int(sheet_parts[1])

    scale = fields.get("scale")
    sheets = tuple(
        DrawingSheet(
            sheet_number=page.page_number,
            sheet_count=len(snapshot.pages),
            scale=(
                scale.value
                if scale is not None and page.page_number == candidate.page_number
                else None
            ),
            source_location=_source_location(
                source_id,
                page.page_number,
                bounding_box=DrawingBoundingBox(
                    x0=Decimal("0"),
                    top=Decimal("0"),
                    x1=page.width_pt,
                    bottom=page.height_pt,
                ),
            ),
        )
        for page in snapshot.pages
    )
    title_location = _source_location(
        source_id,
        candidate.page_number,
        bounding_box=candidate.bounding_box,
        source_object_ids=candidate.source_object_ids,
    )
    title_block = DrawingTitleBlock(
        drawing_number=(
            fields["drawing_number"].value if "drawing_number" in fields else None
        ),
        part_number=fields["part_number"].value if "part_number" in fields else None,
        part_name=fields["part_name"].value if "part_name" in fields else None,
        material_raw=material_evidence.value if material_evidence is not None else None,
        scale=scale.value if scale is not None else None,
        sheet_number=declared_sheet_number,
        sheet_count=declared_sheet_count,
        revision=revision,
        author=fields["author"].value if "author" in fields else None,
        checker=fields["checker"].value if "checker" in fields else None,
        approver=fields["approver"].value if "approver" in fields else None,
        date_text=fields["date"].value if "date" in fields else None,
        source_location=title_location,
    )
    unit = fields.get("unit")
    sheet_mismatch = sheet_evidence is not None and (
        declared_sheet_number != candidate.page_number
        or (
            declared_sheet_count is not None
            and declared_sheet_count != len(snapshot.pages)
        )
    )
    document = CanonicalDrawing(
        drawing_id=f"pdf-drawing-{sha256(content).hexdigest()[:24]}",
        source_id=source_id,
        sheets=sheets,
        title_block=title_block,
        revision=revision,
        material_notes=material_notes,
        metadata=_technical_metadata(snapshot, unit.value if unit is not None else None),
        source_location=DrawingSourceLocation(
            source_id=source_id,
            adapter_id=_PARSER_ID,
            adapter_version=_PARSER_VERSION,
            authority=DrawingExtractionAuthority.EXTRACTED,
        ),
    )
    return document, sheet_mismatch


def _page_location(
    source_id: str,
    page: _PdfPageSnapshot,
) -> DrawingSourceLocation:
    source_object_ids = tuple(
        sorted(
            (
                *(run.ref.object_id for run in page.text_runs),
                *(path.ref.object_id for path in page.vector_paths),
            )
        )
    )
    return _source_location(
        source_id,
        page.page_number,
        bounding_box=DrawingBoundingBox(
            x0=Decimal("0"),
            top=Decimal("0"),
            x1=page.width_pt,
            bottom=page.height_pt,
        ),
        source_object_ids=source_object_ids,
    )


def _base_dimension_document(
    source_id: str,
    content: bytes,
    snapshot: _PdfDocumentSnapshot,
) -> CanonicalDrawing:
    sheets = tuple(
        DrawingSheet(
            sheet_number=page.page_number,
            sheet_count=len(snapshot.pages),
            source_location=_page_location(source_id, page),
        )
        for page in snapshot.pages
    )
    return CanonicalDrawing(
        drawing_id=f"pdf-drawing-{sha256(content).hexdigest()[:24]}",
        source_id=source_id,
        sheets=sheets,
        metadata=_technical_metadata(snapshot, None),
        source_location=_source_location(source_id, 1),
    )


def _assemble_dimension_content(
    document: CanonicalDrawing,
    source_id: str,
    snapshot: _PdfDocumentSnapshot,
    candidates: tuple[_DimensionCandidate, ...],
) -> CanonicalDrawing:
    dimensions_by_page: dict[int, list[DrawingDimension]] = {}
    tolerances: list[DrawingTolerance] = []
    page_ordinals: dict[int, int] = {}
    for candidate in candidates:
        page_ordinals[candidate.page_number] = page_ordinals.get(candidate.page_number, 0) + 1
        dimension, tolerance = _canonical_dimension_pair(
            source_id,
            candidate,
            page_ordinals[candidate.page_number],
        )
        dimensions_by_page.setdefault(candidate.page_number, []).append(dimension)
        if tolerance is not None:
            tolerances.append(tolerance)

    sheets: list[DrawingSheet] = []
    flat_dimensions: list[DrawingDimension] = []
    for sheet in document.sheets:
        page_dimensions = tuple(dimensions_by_page.get(sheet.sheet_number, ()))
        flat_dimensions.extend(page_dimensions)
        views: tuple[DrawingView, ...] = ()
        if page_dimensions:
            boxes = tuple(
                dimension.source_location.bounding_box
                for dimension in page_dimensions
                if dimension.source_location is not None
                and dimension.source_location.bounding_box is not None
            )
            object_ids = tuple(
                object_id
                for dimension in page_dimensions
                if dimension.source_location is not None
                for object_id in dimension.source_location.source_object_ids
            )
            view_location = _source_location(
                source_id,
                sheet.sheet_number,
                bounding_box=_union_box(boxes),
                source_object_ids=tuple(dict.fromkeys(object_ids)),
            )
            views = (
                DrawingView(
                    view_id=f"pdf-view-p{sheet.sheet_number:04d}",
                    view_type=DrawingViewType.UNKNOWN,
                    dimensions=page_dimensions,
                    source_location=view_location,
                ),
            )
        sheets.append(
            DrawingSheet(
                sheet_number=sheet.sheet_number,
                sheet_count=sheet.sheet_count,
                size=sheet.size,
                scale=sheet.scale,
                views=views,
                notes=sheet.notes,
                datum_references=sheet.datum_references,
                source_location=sheet.source_location,
            )
        )
    return CanonicalDrawing(
        drawing_id=document.drawing_id,
        source_id=document.source_id,
        sheets=tuple(sheets),
        title_block=document.title_block,
        revision=document.revision,
        material_notes=document.material_notes,
        heat_treatment_notes=document.heat_treatment_notes,
        all_dimensions=tuple(flat_dimensions),
        all_tolerances=tuple(tolerances),
        all_datum_references=(),
        all_gdt_references=(),
        all_surface_finish=(),
        metadata=document.metadata,
        source_location=document.source_location,
    )


def _pdf_version(content: bytes) -> str:
    header_start = content[:1024].find(b"%PDF-")
    version = content[header_start + 5 : header_start + 8]
    try:
        decoded = version.decode("ascii")
    except UnicodeDecodeError:
        return "unknown"
    return decoded if decoded and all(char in "0123456789." for char in decoded) else "unknown"


def _extract_snapshot(content: bytes, limits: PdfDrawingLimits) -> _PdfDocumentSnapshot:
    pages: list[_PdfPageSnapshot] = []
    object_count = 0
    text_character_count = 0
    vector_point_count = 0

    with pdfplumber.open(BytesIO(content)) as document:
        page_count = len(document.pages)
        if page_count > limits.max_pages:
            raise _ResourceLimitError(page_count, 0)

        for page_number, page in enumerate(document.pages, start=1):
            width = _decimal(page.width)
            height = _decimal(page.height)
            rotation = int(page.rotation or 0)
            if (
                width <= 0
                or height <= 0
                or width > limits.max_page_dimension_points
                or height > limits.max_page_dimension_points
            ):
                raise _ResourceLimitError(page_count, page_number - 1)
            if rotation not in (0, 90, 180, 270):
                raise ValueError

            chars = tuple(page.chars)
            lines = tuple(page.lines)
            rectangles = tuple(page.rects)
            curves = tuple(page.curves)
            images = tuple(page.images)
            page_object_count = (
                len(chars) + len(lines) + len(rectangles) + len(curves) + len(images)
            )
            if page_object_count > limits.max_objects_per_page:
                raise _ResourceLimitError(page_count, page_number - 1)
            if object_count + page_object_count > limits.max_objects_total:
                raise _ResourceLimitError(page_count, page_number - 1)

            text_candidates: list[_TextCandidate] = []
            for source_index, char in enumerate(chars, start=1):
                text = char.get("text")
                if not isinstance(text, str):
                    raise ValueError
                if len(text) > limits.max_text_characters_per_object:
                    raise _ResourceLimitError(page_count, page_number - 1)
                text_character_count += len(text)
                if text_character_count > limits.max_text_characters:
                    raise _ResourceLimitError(page_count, page_number - 1)
                text_candidates.append(
                    _TextCandidate(
                        source_index=source_index,
                        text=text,
                        bounding_box=_bounding_box(char),
                    )
                )

            vector_candidates: list[_VectorCandidate] = []
            vector_sources = (
                *(("line", line) for line in lines),
                *(("rectangle", rect) for rect in rectangles),
                *(("curve", curve) for curve in curves),
            )
            for source_index, (kind, source) in enumerate(vector_sources, start=1):
                box = _bounding_box(source)
                try:
                    points = _source_points(
                        source,
                        maximum=limits.max_vector_points_per_object,
                    )
                except _ResourceLimitError as exc:
                    raise _ResourceLimitError(page_count, page_number - 1) from exc
                segments = _segments_for(kind, points)
                vector_point_count += len(points)
                if vector_point_count > limits.max_vector_points_total:
                    raise _ResourceLimitError(page_count, page_number - 1)
                vector_candidates.append(
                    _VectorCandidate(
                        source_index=source_index,
                        kind=kind,
                        bounding_box=box,
                        segments=segments,
                    )
                )

            text_runs = _normalize_text_runs(page_number, tuple(text_candidates))
            vector_paths = _normalize_vector_paths(page_number, tuple(vector_candidates))
            text_blocks = _normalize_text_blocks(page_number, text_runs)

            object_count += page_object_count
            pages.append(
                _PdfPageSnapshot(
                    page_number=page_number,
                    width_pt=width,
                    height_pt=height,
                    rotation=rotation,
                    text_runs=text_runs,
                    vector_paths=vector_paths,
                    text_blocks=text_blocks,
                    image_count=len(images),
                )
            )

    return _PdfDocumentSnapshot(
        pdf_version=_pdf_version(content),
        pages=tuple(pages),
        object_count=object_count,
        text_character_count=text_character_count,
        vector_point_count=vector_point_count,
    )


def _pdf_worker_entry(
    connection: Connection,
    content: bytes,
    limits: PdfDrawingLimits,
) -> None:
    """Importable spawned-worker entry point with a typed, bounded output."""

    try:
        snapshot = _extract_snapshot(content, limits)
        title_candidates = _extract_title_candidates(snapshot, limits)
        dimension_candidates = _extract_dimension_candidates(
            snapshot, limits, title_candidates
        )
        result = _WorkerExecution(
            snapshot=snapshot,
            failure_code=None,
            page_count_expected=len(snapshot.pages),
            page_count_parsed=len(snapshot.pages),
            title_candidates=title_candidates,
            dimension_candidates=dimension_candidates,
        )
    except _ResourceLimitError as exc:
        result = _WorkerExecution(
            snapshot=None,
            failure_code="PDF_RESOURCE_LIMIT",
            page_count_expected=exc.page_count_expected,
            page_count_parsed=exc.page_count_parsed,
        )
    except (PdfminerException, InvalidOperation, KeyError, TypeError, ValueError):
        result = _WorkerExecution(snapshot=None, failure_code="PDF_MALFORMED")
    except Exception:
        result = _WorkerExecution(snapshot=None, failure_code="PDF_WORKER_FAILURE")

    try:
        connection.send(result)
    except (BrokenPipeError, EOFError, OSError):
        pass
    finally:
        connection.close()


def _stop_worker(process: multiprocessing.Process) -> None:
    if process.is_alive():
        process.terminate()
        process.join(1.0)
    if process.is_alive() and hasattr(process, "kill"):
        process.kill()
        process.join(1.0)


def _run_spawned_worker(
    content: bytes,
    limits: PdfDrawingLimits,
    worker_entry: Callable[[Connection, bytes, PdfDrawingLimits], None] = _pdf_worker_entry,
) -> _WorkerExecution:
    """Run PDF inspection in a fresh process and fail closed on IPC anomalies."""

    context = multiprocessing.get_context("spawn")
    receive_connection, send_connection = context.Pipe(duplex=False)
    process = context.Process(
        name=_WORKER_NAME,
        target=worker_entry,
        args=(send_connection, content, limits),
    )
    try:
        process.start()
        send_connection.close()
        if not receive_connection.poll(limits.parse_timeout_seconds):
            _stop_worker(process)
            return _WorkerExecution(snapshot=None, failure_code="PDF_TIMEOUT")
        try:
            result = receive_connection.recv()
        except (EOFError, OSError):
            result = None
        process.join(1.0)
        if process.is_alive():
            _stop_worker(process)
            return _WorkerExecution(snapshot=None, failure_code="PDF_WORKER_FAILURE")
        if process.exitcode != 0:
            return _WorkerExecution(snapshot=None, failure_code="PDF_WORKER_FAILURE")
        if not isinstance(result, _WorkerExecution):
            return _WorkerExecution(snapshot=None, failure_code="PDF_WORKER_FAILURE")
        return result
    except (OSError, RuntimeError):
        _stop_worker(process)
        return _WorkerExecution(snapshot=None, failure_code="PDF_WORKER_FAILURE")
    finally:
        send_connection.close()
        receive_connection.close()
        _stop_worker(process)


def _declares_encryption(content: bytes) -> bool:
    tail = content[-1_048_576:]
    trailer_position = tail.rfind(b"trailer")
    if trailer_position >= 0:
        trailer = tail[trailer_position :]
        startxref_position = trailer.find(b"startxref")
        if startxref_position >= 0:
            trailer = trailer[:startxref_position]
        if b"/Encrypt" in trailer:
            return True
    return b"/Type /XRef" in tail and b"/Encrypt" in tail


class PdfDrawingParser(DrawingParser):
    """Vector-PDF parser foundation with no semantic extraction."""

    _worker_entry = staticmethod(_pdf_worker_entry)

    def __init__(self, *, limits: PdfDrawingLimits | None = None) -> None:
        if limits is not None and not isinstance(limits, PdfDrawingLimits):
            raise TypeError("limits must be PdfDrawingLimits or None")
        self.limits = limits or PdfDrawingLimits()

    def parser_id(self) -> str:
        return _PARSER_ID

    def parser_version(self) -> str:
        return _PARSER_VERSION

    def supports(
        self,
        source_id: str,
        file_name: str,
        notes: str | None = None,
    ) -> bool:
        try:
            if not isinstance(source_id, str) or not source_id.strip():
                return False
            if not isinstance(file_name, str) or not file_name.strip():
                return False
            if file_name.lower().endswith(".pdf"):
                return True
            return isinstance(notes, str) and notes.startswith("%PDF-")
        except Exception:
            return False

    def parse(
        self,
        source_id: str,
        file_name: str,
        content: bytes,
        notes: str | None = None,
    ) -> DrawingIngestionResult:
        del notes
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("source_id must not be blank")
        if not isinstance(file_name, str) or not file_name.strip():
            return self._result(
                source_id,
                DrawingIngestionStatus.UNSUPPORTED,
                format_detected=None,
                warnings=("PDF_UNSUPPORTED",),
            )
        if not isinstance(content, (bytes, bytearray, memoryview)):
            return self._result(
                source_id,
                DrawingIngestionStatus.UNSUPPORTED,
                format_detected=None,
                warnings=("PDF_UNSUPPORTED",),
            )
        if memoryview(content).nbytes > self.limits.max_file_bytes:
            return self._result(
                source_id,
                DrawingIngestionStatus.FAILED,
                format_detected=None,
                errors=("PDF_RESOURCE_LIMIT",),
            )
        payload = bytes(content)
        if payload[:1024].find(b"%PDF-") < 0:
            return self._result(
                source_id,
                DrawingIngestionStatus.UNSUPPORTED,
                format_detected=None,
                warnings=("PDF_UNSUPPORTED",),
            )
        if _declares_encryption(payload):
            return self._result(
                source_id,
                DrawingIngestionStatus.UNSUPPORTED,
                format_detected="PDF",
                warnings=("PDF_ENCRYPTED",),
            )

        execution = _run_spawned_worker(payload, self.limits, self._worker_entry)
        if execution.failure_code is not None:
            return self._result(
                source_id,
                DrawingIngestionStatus.FAILED,
                format_detected="PDF",
                errors=(execution.failure_code,),
                sheet_count_expected=execution.page_count_expected,
                sheet_count_parsed=execution.page_count_parsed,
            )

        snapshot = execution.snapshot
        if snapshot is None:
            return self._result(
                source_id,
                DrawingIngestionStatus.FAILED,
                format_detected="PDF",
                errors=("PDF_WORKER_FAILURE",),
            )
        image_count = sum(page.image_count for page in snapshot.pages)
        has_vector_evidence = any(
            page.text_runs or page.vector_paths for page in snapshot.pages
        )
        if image_count and not has_vector_evidence:
            return self._result(
                source_id,
                DrawingIngestionStatus.UNSUPPORTED,
                format_detected="PDF",
                warnings=("PDF_RASTER_ONLY",),
                sheet_count_expected=len(snapshot.pages),
                sheet_count_parsed=len(snapshot.pages),
            )
        if execution.title_candidates:
            highest_score = execution.title_candidates[0].candidate.score
            highest = tuple(
                candidate
                for candidate in execution.title_candidates
                if candidate.candidate.score == highest_score
            )
            if len(highest) > 1:
                if execution.dimension_candidates:
                    document = _assemble_dimension_content(
                        _base_dimension_document(source_id, payload, snapshot),
                        source_id,
                        snapshot,
                        execution.dimension_candidates,
                    )
                    return self._result(
                        source_id,
                        DrawingIngestionStatus.PARTIAL,
                        format_detected="PDF",
                        warnings=("PDF_TITLE_BLOCK_AMBIGUOUS",),
                        sheet_count_expected=len(snapshot.pages),
                        sheet_count_parsed=len(snapshot.pages),
                        document=document,
                    )
                return self._result(
                    source_id,
                    DrawingIngestionStatus.INSUFFICIENT_DATA,
                    format_detected="PDF",
                    warnings=("PDF_TITLE_BLOCK_AMBIGUOUS",),
                    errors=("PDF_INSUFFICIENT_VECTOR_DATA",),
                    sheet_count_expected=len(snapshot.pages),
                    sheet_count_parsed=len(snapshot.pages),
                )
            selected = highest[0]
            document, sheet_mismatch = _build_title_document(
                source_id,
                payload,
                snapshot,
                selected,
            )
            if execution.dimension_candidates:
                document = _assemble_dimension_content(
                    document,
                    source_id,
                    snapshot,
                    execution.dimension_candidates,
                )
            warnings = tuple(
                warning
                for present, warning in (
                    (selected.had_field_conflict, "PDF_TITLE_FIELD_CONFLICT"),
                    (sheet_mismatch, "PDF_TITLE_SHEET_MISMATCH"),
                )
                if present
            )
            return self._result(
                source_id,
                (
                    DrawingIngestionStatus.PARTIAL
                    if warnings
                    else DrawingIngestionStatus.VALID
                ),
                format_detected="PDF",
                warnings=warnings,
                sheet_count_expected=len(snapshot.pages),
                sheet_count_parsed=len(snapshot.pages),
                document=document,
            )
        if execution.dimension_candidates:
            document = _assemble_dimension_content(
                _base_dimension_document(source_id, payload, snapshot),
                source_id,
                snapshot,
                execution.dimension_candidates,
            )
            return self._result(
                source_id,
                DrawingIngestionStatus.VALID,
                format_detected="PDF",
                warnings=("PDF_VECTOR_PREFLIGHT_OK",) if has_vector_evidence else (),
                sheet_count_expected=len(snapshot.pages),
                sheet_count_parsed=len(snapshot.pages),
                document=document,
            )
        return self._result(
            source_id,
            DrawingIngestionStatus.INSUFFICIENT_DATA,
            format_detected="PDF",
            warnings=("PDF_VECTOR_PREFLIGHT_OK",) if has_vector_evidence else (),
            errors=("PDF_INSUFFICIENT_VECTOR_DATA",),
            sheet_count_expected=len(snapshot.pages),
            sheet_count_parsed=len(snapshot.pages),
        )

    def _result(
        self,
        source_id: str,
        status: DrawingIngestionStatus,
        *,
        format_detected: str | None,
        warnings: tuple[str, ...] = (),
        errors: tuple[str, ...] = (),
        sheet_count_expected: int | None = None,
        sheet_count_parsed: int = 0,
        document: CanonicalDrawing | None = None,
    ) -> DrawingIngestionResult:
        bounded_warnings = tuple(
            message[: self.limits.max_diagnostic_characters]
            for message in warnings[: self.limits.max_diagnostics_per_kind]
        )
        bounded_errors = tuple(
            message[: self.limits.max_diagnostic_characters]
            for message in errors[: self.limits.max_diagnostics_per_kind]
        )
        return DrawingIngestionResult(
            source_id=source_id,
            diagnostics=DrawingIngestionDiagnostics(
                status=status,
                format_detected=format_detected,
                parser_id=self.parser_id(),
                parser_version=self.parser_version(),
                warnings=bounded_warnings,
                errors=bounded_errors,
                sheet_count_expected=sheet_count_expected,
                sheet_count_parsed=sheet_count_parsed,
            ),
            document=document,
        )


__all__ = ["PdfDrawingLimits", "PdfDrawingParser"]
