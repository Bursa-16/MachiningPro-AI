"""Conservative Phase 1C GD&T token and feature-control-frame grammar."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum, unique
from hashlib import sha256
from typing import Any

from backend.interoperability.drawing import (
    CanonicalDrawing,
    DrawingBoundingBox,
    DrawingDatumReference,
    DrawingFeatureControlFrame,
    DrawingGdtCell,
    DrawingGdtCellRole,
    DrawingGdtCharacteristic,
    DrawingGdtModifier,
    DrawingGdtReference,
    DrawingIngestionStatus,
    DrawingOcrTextEvidence,
    DrawingParserIdentity,
    DrawingSourceLocation,
)

_MIN_FRAME_CONFIDENCE = Decimal("0.90")
_MAX_TOKENS = 5_000
_MAX_CELLS = 32
_MAX_SPATIAL_GAP = Decimal("72")
_MAX_VERTICAL_DELTA = Decimal("12")
_VALUE_PATTERN = r"(?:\d+(?:[.,]\d+)?|\.\d+)"
_TOLERANCE_PATTERN = re.compile(
    rf"^(?P<diameter>DIA|Ø|⌀)?\s*(?P<value>{_VALUE_PATTERN})\s*(?P<unit>MM|IN|INCH|INCHES)$",
    re.IGNORECASE,
)


@unique
class GdtTokenSource(StrEnum):
    VECTOR = "VECTOR"
    OCR = "OCR"


@dataclass(frozen=True)
class GdtTokenEvidence:
    """Typed, bounded token input accepted by the Task 6 grammar."""

    evidence_id: str
    text: str
    source_kind: GdtTokenSource
    confidence: Decimal
    source_location: DrawingSourceLocation
    parser_identity: DrawingParserIdentity

    def __post_init__(self) -> None:
        if not self.evidence_id.strip():
            raise ValueError("GdtTokenEvidence.evidence_id must not be blank")
        if not self.text.strip() or len(self.text) > 256:
            raise ValueError("GdtTokenEvidence.text is outside its bound")
        if not isinstance(self.source_kind, GdtTokenSource):
            raise TypeError("GdtTokenEvidence.source_kind must be GdtTokenSource")
        if not isinstance(self.confidence, Decimal) or not self.confidence.is_finite():
            raise ValueError("GdtTokenEvidence.confidence must be finite Decimal")
        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError("GdtTokenEvidence.confidence must be in [0, 1]")
        if not isinstance(self.source_location, DrawingSourceLocation):
            raise TypeError("GdtTokenEvidence.source_location must be DrawingSourceLocation")
        if not isinstance(self.parser_identity, DrawingParserIdentity):
            raise TypeError("GdtTokenEvidence.parser_identity must be DrawingParserIdentity")


@dataclass(frozen=True)
class GdtRecognitionResult:
    status: DrawingIngestionStatus
    frames: tuple[DrawingFeatureControlFrame, ...] = field(default_factory=tuple)
    diagnostics: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.status, DrawingIngestionStatus):
            raise TypeError("GdtRecognitionResult.status must be DrawingIngestionStatus")
        if not isinstance(self.frames, tuple) or not isinstance(self.diagnostics, tuple):
            raise TypeError("GdtRecognitionResult fields must be tuples")
        if len(self.frames) > _MAX_TOKENS or len(self.diagnostics) > 50:
            raise ValueError("GdtRecognitionResult exceeds bounds")
        if any(len(code) > 240 for code in self.diagnostics):
            raise ValueError("GdtRecognitionResult diagnostic exceeds bound")


def recognize_feature_control_frames(
    evidence: Sequence[GdtTokenEvidence | DrawingOcrTextEvidence],
) -> GdtRecognitionResult:
    """Recognize only explicit four-characteristic, single-segment frames."""

    if len(evidence) > _MAX_TOKENS:
        return GdtRecognitionResult(
            DrawingIngestionStatus.FAILED, diagnostics=("GDT_CANDIDATE_LIMIT",)
        )
    tokens = tuple(_coerce_token(item) for item in evidence)
    tokens = tuple(item for item in tokens if item is not None)
    candidates: list[DrawingFeatureControlFrame] = []
    diagnostics: set[str] = set()
    for group in _spatial_groups(tokens):
        frame, diagnostic = _build_frame(_coalesce_tokens(group))
        if frame is not None:
            candidates.append(frame)
        elif diagnostic is not None:
            diagnostics.add(diagnostic)
    merged, merge_diagnostics = _reconcile(candidates)
    diagnostics.update(merge_diagnostics)
    diagnostics_tuple = tuple(sorted(diagnostics))
    status = DrawingIngestionStatus.VALID if merged else DrawingIngestionStatus.INSUFFICIENT_DATA
    return GdtRecognitionResult(status, frames=merged, diagnostics=diagnostics_tuple)


def map_feature_control_frames(
    frames: Sequence[DrawingFeatureControlFrame],
) -> tuple[DrawingGdtReference, ...]:
    """Map accepted Task 6 frames into the existing typed GD&T aggregate."""

    materialized = tuple(frames)
    if any(not isinstance(frame, DrawingFeatureControlFrame) for frame in materialized):
        raise TypeError("frames must contain DrawingFeatureControlFrame values")
    ordered = tuple(sorted(materialized, key=_frame_sort_key))
    references: list[DrawingGdtReference] = []
    for frame in ordered:
        if frame.characteristic is None:
            continue
        references.append(
            DrawingGdtReference(
                gdt_id=frame.frame_id,
                symbol_type=frame.characteristic.value,
                tolerance_value=frame.tolerance_value,
                tolerance_unit=frame.tolerance_unit,
                datum_references=frame.datum_references,
                source_location=frame.source_location,
                feature_control_frame=frame,
            )
        )
    return tuple(references)


def attach_feature_control_frames(
    document: CanonicalDrawing,
    frames: Sequence[DrawingFeatureControlFrame],
) -> CanonicalDrawing:
    """Return a copy of ``document`` with only accepted GD&T references attached."""

    if not isinstance(document, CanonicalDrawing):
        raise TypeError("document must be CanonicalDrawing")
    mapped = map_feature_control_frames(frames)
    references_by_id = {reference.gdt_id: reference for reference in document.all_gdt_references}
    references_by_id.update({reference.gdt_id: reference for reference in mapped})
    references = tuple(
        sorted(references_by_id.values(), key=_reference_sort_key)
    )
    return CanonicalDrawing(
        drawing_id=document.drawing_id,
        source_id=document.source_id,
        sheets=document.sheets,
        title_block=document.title_block,
        revision=document.revision,
        material_notes=document.material_notes,
        heat_treatment_notes=document.heat_treatment_notes,
        all_dimensions=document.all_dimensions,
        all_tolerances=document.all_tolerances,
        all_datum_references=document.all_datum_references,
        all_gdt_references=references,
        all_surface_finish=document.all_surface_finish,
        metadata=document.metadata,
        source_location=document.source_location,
    )


def _coerce_token(item: GdtTokenEvidence | DrawingOcrTextEvidence) -> GdtTokenEvidence | None:
    if isinstance(item, GdtTokenEvidence):
        return item
    if not isinstance(item, DrawingOcrTextEvidence):
        raise TypeError("GD&T evidence must be typed vector or OCR evidence")
    return GdtTokenEvidence(
        evidence_id=item.evidence_id,
        text=item.text,
        source_kind=GdtTokenSource.OCR,
        confidence=item.confidence,
        source_location=item.source_location,
        parser_identity=item.parser_identity,
    )


def _spatial_groups(
    tokens: tuple[GdtTokenEvidence, ...],
) -> tuple[tuple[GdtTokenEvidence, ...], ...]:
    ordered = sorted(tokens, key=_sort_key)
    groups: list[list[GdtTokenEvidence]] = []
    for token in ordered:
        box = token.source_location.bounding_box
        if box is None:
            continue
        if not groups:
            groups.append([token])
            continue
        previous = groups[-1][-1].source_location.bounding_box
        if previous is not None and _same_band(previous, box):
            groups[-1].append(token)
        else:
            groups.append([token])
    return tuple(tuple(group) for group in groups)


def _same_band(first: DrawingBoundingBox, second: DrawingBoundingBox) -> bool:
    vertical = min(first.bottom, second.bottom) - max(first.top, second.top)
    horizontal_gap = max(Decimal("0"), second.x0 - first.x1)
    return vertical >= -_MAX_VERTICAL_DELTA and horizontal_gap <= _MAX_SPATIAL_GAP


def _coalesce_tokens(
    tokens: tuple[GdtTokenEvidence, ...],
) -> tuple[GdtTokenEvidence, ...]:
    """Merge agreeing vector/OCR cells while retaining every source object ID."""

    result: list[GdtTokenEvidence] = []
    for token in sorted(tokens, key=_sort_key):
        normalized = _normalize(token.text)
        match_index = next(
            (
                index
                for index, existing in enumerate(result)
                if _normalize(existing.text) == normalized
                and _evidence_adjacent(existing, token)
            ),
            None,
        )
        if match_index is None:
            result.append(token)
        else:
            result[match_index] = _merge_tokens(result[match_index], token)
    return tuple(result)


def _evidence_adjacent(first: GdtTokenEvidence, second: GdtTokenEvidence) -> bool:
    one = first.source_location.bounding_box
    two = second.source_location.bounding_box
    if one is None or two is None:
        return False
    return not (
        one.x1 < two.x0
        or two.x1 < one.x0
        or one.bottom < two.top
        or two.bottom < one.top
    )


def _merge_tokens(
    first: GdtTokenEvidence,
    second: GdtTokenEvidence,
) -> GdtTokenEvidence:
    ids = tuple(
        dict.fromkeys(
            (
                *first.source_location.source_object_ids,
                *second.source_location.source_object_ids,
            )
        )
    )
    first_box = first.source_location.bounding_box
    second_box = second.source_location.bounding_box
    location = DrawingSourceLocation(
        source_id=first.source_location.source_id,
        page_number=first.source_location.page_number,
        adapter_id=first.parser_identity.parser_id,
        adapter_version=first.parser_identity.parser_version,
        confidence=min(first.confidence, second.confidence),
        bounding_box=_union_box((first_box, second_box)),
        source_object_ids=ids,
    )
    source_kind = (
        GdtTokenSource.VECTOR
        if first.source_kind is GdtTokenSource.VECTOR
        or second.source_kind is GdtTokenSource.VECTOR
        else GdtTokenSource.OCR
    )
    return GdtTokenEvidence(
        evidence_id=min(first.evidence_id, second.evidence_id),
        text=first.text,
        source_kind=source_kind,
        confidence=min(first.confidence, second.confidence),
        source_location=location,
        parser_identity=first.parser_identity,
    )


def _build_frame(
    tokens: tuple[GdtTokenEvidence, ...],
) -> tuple[DrawingFeatureControlFrame | None, str | None]:
    if not tokens:
        return None, "GDT_FRAME_GRAMMAR_REJECTED"
    ordered = tuple(sorted(tokens, key=_sort_key))
    normalized = tuple(_normalize(item.text) for item in ordered)
    characteristic = _characteristic(normalized[0])
    # A band that does not start with an allowlisted characteristic is not a
    # frame candidate (ordinary drawing text). It is classified before the
    # size check so GDT_FRAME_GRAMMAR_REJECTED always means a rejected
    # characteristic-led candidate.
    if characteristic is None:
        return None, "GDT_UNSUPPORTED_CHARACTERISTIC"
    if len(tokens) < 2 or len(tokens) > _MAX_CELLS:
        return None, "GDT_FRAME_GRAMMAR_REJECTED"
    if any(token.confidence < _MIN_FRAME_CONFIDENCE for token in ordered):
        return None, "GDT_LOW_CONFIDENCE"
    tolerance_value: Decimal | None = None
    tolerance_unit: str | None = None
    diameter = False
    datum_tokens: list[GdtTokenEvidence] = []
    cells: list[DrawingGdtCell] = []
    for index, token in enumerate(ordered):
        text = _normalize(token.text)
        role = DrawingGdtCellRole.UNKNOWN
        if index == 0:
            role = DrawingGdtCellRole.CHARACTERISTIC
        elif _is_unsupported_modifier(text):
            return None, "GDT_UNSUPPORTED_MODIFIER"
        elif _parse_tolerance(text) is not None:
            if tolerance_value is not None:
                return None, "GDT_EVIDENCE_CONFLICT"
            parsed_tolerance = _parse_tolerance(text)
            if parsed_tolerance is None:
                return None, "GDT_MALFORMED_TOLERANCE"
            tolerance_value, tolerance_unit, diameter = parsed_tolerance
            role = DrawingGdtCellRole.TOLERANCE
        elif re.fullmatch(r"[A-Z]", text):
            datum_tokens.append(token)
            role = DrawingGdtCellRole.DATUM
        else:
            return None, "GDT_FRAME_GRAMMAR_REJECTED"
        cells.append(
            DrawingGdtCell(
                cell_index=index,
                role=role,
                normalized_text=text,
                confidence=token.confidence,
                source_location=token.source_location,
                parser_identity=token.parser_identity,
            )
        )
    if tolerance_value is None or tolerance_unit is None:
        return None, "GDT_MISSING_TOLERANCE"
    frame_box = _union_box(tuple(token.source_location.bounding_box for token in ordered))
    source_ids = tuple(
        dict.fromkeys(
            object_id
            for token in ordered
            for object_id in token.source_location.source_object_ids
        )
    )
    source_location = DrawingSourceLocation(
        source_id=ordered[0].source_location.source_id,
        page_number=ordered[0].source_location.page_number,
        adapter_id=ordered[0].parser_identity.parser_id,
        adapter_version=ordered[0].parser_identity.parser_version,
        confidence=min(token.confidence for token in ordered),
        bounding_box=frame_box,
        source_object_ids=source_ids,
    )
    datums = tuple(
        DrawingDatumReference(
            datum_label=_normalize(token.text),
            source_location=token.source_location,
        )
        for token in datum_tokens
    )
    frame_id = "gdt-" + sha256(
        "|".join((str(ordered[0].source_location.page_number), *normalized, *source_ids)).encode()
    ).hexdigest()[:24]
    return (
        DrawingFeatureControlFrame(
            frame_id=frame_id,
            cells=tuple(cells),
            characteristic=characteristic,
            tolerance_value=tolerance_value,
            tolerance_unit=tolerance_unit,
            diameter_applied=diameter,
            datum_references=datums,
            source_location=source_location,
            parser_identity=ordered[0].parser_identity,
            confidence=min(token.confidence for token in ordered),
            modifier=DrawingGdtModifier.NONE,
        ),
        None,
    )


def _reconcile(
    candidates: list[DrawingFeatureControlFrame],
) -> tuple[tuple[DrawingFeatureControlFrame, ...], tuple[str, ...]]:
    kept: list[DrawingFeatureControlFrame | None] = []
    diagnostics: set[str] = set()
    for candidate in sorted(candidates, key=_frame_sort_key):
        matches = [
            index
            for index, existing in enumerate(kept)
            if existing is not None and _frames_overlap(existing, candidate)
        ]
        if not matches:
            kept.append(candidate)
            continue
        for index in matches:
            existing = kept[index]
            if _frame_signature(existing) != _frame_signature(candidate):
                diagnostics.add("GDT_EVIDENCE_CONFLICT")
                kept[index] = None  # type: ignore[assignment]
            else:
                kept[index] = _merge_frames(existing, candidate)
    return tuple(frame for frame in kept if frame is not None), tuple(sorted(diagnostics))


def _merge_frames(
    first: DrawingFeatureControlFrame,
    second: DrawingFeatureControlFrame,
) -> DrawingFeatureControlFrame:
    ids = tuple(
        dict.fromkeys(
            (
                *first.source_location.source_object_ids,
                *second.source_location.source_object_ids,
            )
        )
    )
    location = DrawingSourceLocation(
        source_id=first.source_location.source_id,
        page_number=first.source_location.page_number,
        adapter_id=first.parser_identity.parser_id,
        adapter_version=first.parser_identity.parser_version,
        confidence=min(first.confidence, second.confidence),
        bounding_box=_union_box(
            (first.source_location.bounding_box, second.source_location.bounding_box)
        ),
        source_object_ids=ids,
    )
    cells = tuple(
        _merge_cells(first_cell, second_cell)
        for first_cell, second_cell in zip(first.cells, second.cells, strict=True)
    )
    return DrawingFeatureControlFrame(
        frame_id=first.frame_id,
        cells=cells,
        characteristic=first.characteristic,
        tolerance_value=first.tolerance_value,
        tolerance_unit=first.tolerance_unit,
        diameter_applied=first.diameter_applied,
        datum_references=first.datum_references,
        source_location=location,
        parser_identity=first.parser_identity,
        confidence=min(first.confidence, second.confidence),
        modifier=DrawingGdtModifier.NONE,
    )


def _merge_cells(first: DrawingGdtCell, second: DrawingGdtCell) -> DrawingGdtCell:
    ids = tuple(
        dict.fromkeys(
            (
                *first.source_location.source_object_ids,
                *second.source_location.source_object_ids,
            )
        )
    )
    location = DrawingSourceLocation(
        source_id=first.source_location.source_id,
        page_number=first.source_location.page_number,
        adapter_id=first.parser_identity.parser_id,
        adapter_version=first.parser_identity.parser_version,
        confidence=min(first.confidence, second.confidence),
        bounding_box=_union_box(
            (first.source_location.bounding_box, second.source_location.bounding_box)
        ),
        source_object_ids=ids,
    )
    return DrawingGdtCell(
        cell_index=first.cell_index,
        role=first.role,
        normalized_text=first.normalized_text,
        confidence=min(first.confidence, second.confidence),
        source_location=location,
        parser_identity=first.parser_identity,
    )


def _frame_signature(frame: DrawingFeatureControlFrame) -> tuple[Any, ...]:
    return (
        frame.characteristic,
        frame.tolerance_value,
        frame.tolerance_unit,
        frame.diameter_applied,
        tuple(item.datum_label for item in frame.datum_references),
        tuple(cell.normalized_text for cell in frame.cells),
    )


def _reference_sort_key(reference: DrawingGdtReference) -> tuple[Any, ...]:
    location = reference.source_location
    box = location.bounding_box if location is not None else None
    return (
        location.page_number if location is not None and location.page_number is not None else 0,
        box.top if box is not None else Decimal("0"),
        box.x0 if box is not None else Decimal("0"),
        reference.gdt_id,
    )


def _frames_overlap(first: DrawingFeatureControlFrame, second: DrawingFeatureControlFrame) -> bool:
    if first.source_location.page_number != second.source_location.page_number:
        return False
    one = first.source_location.bounding_box
    two = second.source_location.bounding_box
    if one is None or two is None:
        return False
    return not (one.x1 < two.x0 or two.x1 < one.x0 or one.bottom < two.top or two.bottom < one.top)


def _characteristic(text: str) -> DrawingGdtCharacteristic | None:
    try:
        return DrawingGdtCharacteristic(text)
    except ValueError:
        return None


def _parse_tolerance(text: str) -> tuple[Decimal, str, bool] | None:
    match = _TOLERANCE_PATTERN.fullmatch(text)
    if match is None:
        return None
    try:
        value = Decimal(match.group("value").replace(",", "."))
    except InvalidOperation:
        return None
    if not value.is_finite() or value <= 0:
        return None
    unit = match.group("unit").lower()
    unit = "inch" if unit in {"in", "inch", "inches"} else "mm"
    return value, unit, bool(match.group("diameter"))


def _is_unsupported_modifier(text: str) -> bool:
    return text in {"MMC", "LMC", "RFS"}


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).upper().split())


def _sort_key(token: GdtTokenEvidence) -> tuple[Any, ...]:
    box = token.source_location.bounding_box
    if box is None:
        return (
            token.source_location.page_number or 0,
            Decimal("0"),
            Decimal("0"),
            token.evidence_id,
        )
    return (
        token.source_location.page_number or 0,
        box.top,
        box.x0,
        box.bottom,
        box.x1,
        token.evidence_id,
    )


def _frame_sort_key(frame: DrawingFeatureControlFrame) -> tuple[Any, ...]:
    box = frame.source_location.bounding_box
    return (
        frame.source_location.page_number or 0,
        box.top if box else Decimal("0"),
        box.x0 if box else Decimal("0"),
        frame.frame_id,
    )


def _union_box(boxes: tuple[DrawingBoundingBox | None, ...]) -> DrawingBoundingBox:
    valid = tuple(box for box in boxes if box is not None)
    if not valid:
        raise ValueError("GD&T evidence requires bounding boxes")
    return DrawingBoundingBox(
        x0=min(box.x0 for box in valid),
        top=min(box.top for box in valid),
        x1=max(box.x1 for box in valid),
        bottom=max(box.bottom for box in valid),
    )


__all__ = [
    "attach_feature_control_frames",
    "GdtRecognitionResult",
    "GdtTokenEvidence",
    "GdtTokenSource",
    "map_feature_control_frames",
    "recognize_feature_control_frames",
]
