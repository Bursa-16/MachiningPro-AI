"""Bounded, offline OCR evidence extraction for raster drawing pages.

Task 4 deliberately stops at typed OCR evidence.  It does not classify text or
promote it into title blocks, dimensions, tolerances, or GD&T structures.
"""

from __future__ import annotations

import multiprocessing as mp
import shutil
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pytesseract
from PIL import Image

from backend.interoperability.drawing import (
    DrawingBoundingBox,
    DrawingIngestionStatus,
    DrawingOcrEvidenceKind,
    DrawingOcrTextEvidence,
    DrawingParserIdentity,
    DrawingSourceLocation,
)
from backend.interoperability.raster_drawing import (
    RasterLimits,
    _RasterLimit,
    _RasterMalformed,
    _RasterOcrInput,
    _RasterUnsupported,
    prepare_raster_ocr_inputs,
)

_OCR_PARSER = DrawingParserIdentity(
    parser_id="tesseract-ocr",
    parser_version="5.5.3.20260724",
    preprocessing_id="ocr-preprocess-v1",
)
_ZERO = Decimal("0")
_ONE = Decimal("1")
_DEFAULT_MINIMUM_CONFIDENCE = Decimal("0.80")


@dataclass(frozen=True)
class OcrLimits:
    """Explicit Phase 1C OCR bounds."""

    max_runtime_seconds: float = 30.0
    max_tokens: int = 100_000
    max_lines: int = 100_000
    max_blocks: int = 100_000
    max_text_characters: int = 1_000_000
    max_token_length: int = 256
    max_result_bytes: int = 8 * 1024 * 1024
    minimum_confidence: Decimal = _DEFAULT_MINIMUM_CONFIDENCE

    def __post_init__(self) -> None:
        if isinstance(self.max_runtime_seconds, bool) or self.max_runtime_seconds <= 0:
            raise ValueError("OcrLimits.max_runtime_seconds must be positive")
        for name in (
            "max_tokens",
            "max_lines",
            "max_blocks",
            "max_text_characters",
            "max_token_length",
            "max_result_bytes",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"OcrLimits.{name} must be a positive int")
        if not isinstance(self.minimum_confidence, Decimal):
            raise TypeError("OcrLimits.minimum_confidence must be Decimal")
        if not self.minimum_confidence.is_finite() or not _ZERO <= self.minimum_confidence <= _ONE:
            raise ValueError("OcrLimits.minimum_confidence must be in [0, 1]")


@dataclass(frozen=True)
class OcrResult:
    """Bounded OCR result; no engine objects, pixels, paths, or raw payloads."""

    status: DrawingIngestionStatus
    evidence: tuple[DrawingOcrTextEvidence, ...] = field(default_factory=tuple)
    diagnostics: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.status, DrawingIngestionStatus):
            raise TypeError("OcrResult.status must be DrawingIngestionStatus")
        if not isinstance(self.evidence, tuple) or not isinstance(self.diagnostics, tuple):
            raise TypeError("OcrResult evidence and diagnostics must be tuples")
        if len(self.diagnostics) > 50:
            raise ValueError("OcrResult diagnostics exceed the bound")
        if any(not isinstance(code, str) or len(code) > 240 for code in self.diagnostics):
            raise ValueError("OcrResult diagnostics are invalid")
        if any(not isinstance(item, DrawingOcrTextEvidence) for item in self.evidence):
            raise TypeError("OcrResult evidence must contain typed OCR evidence")
        if self.status in (DrawingIngestionStatus.FAILED, DrawingIngestionStatus.UNSUPPORTED):
            if self.evidence:
                raise ValueError("fail-closed OCR results cannot carry evidence")


def extract_ocr_from_pdf(
    content: bytes,
    source_id: str,
    *,
    limits: OcrLimits | None = None,
    raster_limits: RasterLimits | None = None,
) -> OcrResult:
    """Extract confidence-gated OCR evidence from embedded raster PDF objects."""

    active_limits = limits or OcrLimits()
    try:
        inputs = prepare_raster_ocr_inputs(content, source_id, limits=raster_limits)
    except _RasterUnsupported:
        return OcrResult(
            DrawingIngestionStatus.UNSUPPORTED,
            diagnostics=("RASTER_UNSUPPORTED_FORMAT",),
        )
    except _RasterMalformed:
        return OcrResult(DrawingIngestionStatus.FAILED, diagnostics=("RASTER_MALFORMED_IMAGE",))
    except _RasterLimit as exc:
        return OcrResult(DrawingIngestionStatus.FAILED, diagnostics=(exc.code,))
    except Exception:
        return OcrResult(DrawingIngestionStatus.FAILED, diagnostics=("RASTER_WORKER_FAILURE",))
    return _run_spawned_ocr(inputs, active_limits)


def _run_spawned_ocr(
    inputs: tuple[_RasterOcrInput, ...],
    limits: OcrLimits,
    *,
    worker_entry: Callable[..., None] | None = None,
) -> OcrResult:
    try:
        command = _resolve_tesseract_command()
    except _OcrEngineUnavailable:
        return OcrResult(
            DrawingIngestionStatus.FAILED,
            diagnostics=("OCR_ENGINE_UNAVAILABLE",),
        )
    target = worker_entry or _ocr_worker_entry
    context = mp.get_context("spawn")
    try:
        receiver, sender = context.Pipe(duplex=False)
    except OSError:
        return OcrResult(
            DrawingIngestionStatus.FAILED,
            diagnostics=("OCR_WORKER_FAILURE",),
        )
    process = context.Process(target=target, args=(sender, inputs, limits, command))
    try:
        process.start()
        sender.close()
        if not receiver.poll(limits.max_runtime_seconds):
            if process.is_alive():
                process.terminate()
            process.join(timeout=2.0)
            return OcrResult(DrawingIngestionStatus.FAILED, diagnostics=("OCR_TIMEOUT",))
        payload = receiver.recv()
        process.join(timeout=2.0)
        if process.exitcode != 0:
            return OcrResult(DrawingIngestionStatus.FAILED, diagnostics=("OCR_WORKER_FAILURE",))
        if not isinstance(payload, tuple) or len(payload) != 2:
            return OcrResult(DrawingIngestionStatus.FAILED, diagnostics=("OCR_WORKER_FAILURE",))
        evidence, diagnostics = payload
        if not isinstance(evidence, tuple) or not isinstance(diagnostics, tuple):
            return OcrResult(DrawingIngestionStatus.FAILED, diagnostics=("OCR_WORKER_FAILURE",))
        if len(repr(payload).encode("utf-8")) > limits.max_result_bytes:
            return OcrResult(DrawingIngestionStatus.FAILED, diagnostics=("OCR_RESULT_LIMIT",))
        fail_closed_codes = {
            "OCR_RESOURCE_LIMIT",
            "OCR_ENGINE_UNAVAILABLE",
            "OCR_WORKER_FAILURE",
        }
        status = (
            DrawingIngestionStatus.FAILED
            if any(code in fail_closed_codes for code in diagnostics)
            else DrawingIngestionStatus.VALID
            if evidence
            else DrawingIngestionStatus.INSUFFICIENT_DATA
        )
        result = OcrResult(status, evidence=evidence, diagnostics=diagnostics)
        return result
    except (OSError, EOFError, BrokenPipeError):
        if process.is_alive():
            process.terminate()
        process.join(timeout=2.0)
        return OcrResult(DrawingIngestionStatus.FAILED, diagnostics=("OCR_WORKER_FAILURE",))
    finally:
        receiver.close()
        try:
            sender.close()
        except (OSError, AttributeError):
            pass


def _ocr_worker_entry(
    sender: Any,
    inputs: tuple[_RasterOcrInput, ...],
    limits: OcrLimits,
    tesseract_command: str,
) -> None:
    try:
        pytesseract.pytesseract.tesseract_cmd = tesseract_command
        evidence = _extract_worker_evidence(inputs, limits)
        diagnostics = ("OCR_NO_CONFIDENT_EVIDENCE",) if not evidence else ()
        sender.send((evidence, diagnostics))
    except _OcrLimit:
        sender.send(((), ("OCR_RESOURCE_LIMIT",)))
    except _OcrEngineUnavailable:
        sender.send(((), ("OCR_ENGINE_UNAVAILABLE",)))
    except Exception:
        sender.send(((), ("OCR_WORKER_FAILURE",)))
    finally:
        sender.close()


def _extract_worker_evidence(
    inputs: tuple[_RasterOcrInput, ...], limits: OcrLimits
) -> tuple[DrawingOcrTextEvidence, ...]:
    words: list[tuple[DrawingOcrTextEvidence, tuple[int, int, int, int]]] = []
    total_chars = 0
    for raster_input in inputs:
        with Image.frombytes(
            "L", (raster_input.width, raster_input.height), raster_input.pixels
        ) as image:
            data = pytesseract.image_to_data(
                image,
                lang="eng",
                config="--oem 1 --psm 6",
                output_type=pytesseract.Output.DICT,
            )
        rows = len(data.get("text", ()))
        for index in range(rows):
            text = unicodedata.normalize("NFC", str(data["text"][index] or "")).strip()
            if not text:
                continue
            if len(text) > limits.max_token_length:
                raise _OcrLimit
            confidence = _normalize_confidence(data.get("conf", ())[index])
            if confidence < limits.minimum_confidence:
                continue
            left = int(data.get("left", (0,))[index])
            top = int(data.get("top", (0,))[index])
            width = int(data.get("width", (0,))[index])
            height = int(data.get("height", (0,))[index])
            if width <= 0 or height <= 0:
                continue
            block = int(data.get("block_num", (0,))[index])
            paragraph = int(data.get("par_num", (0,))[index])
            line = int(data.get("line_num", (0,))[index])
            word_num_data = data.get("word_num")
            word = int(word_num_data[index]) if word_num_data is not None else index
            child_id = (
                f"{raster_input.raster_source.image_object_id}:"
                f"word-{block}-{paragraph}-{line}-{word}"
            )
            box = _map_box(raster_input, left, top, width, height)
            location = DrawingSourceLocation(
                source_id=raster_input.raster_source.source_id,
                page_number=raster_input.page_number,
                original_text=text,
                adapter_id="tesseract-ocr",
                adapter_version="5.5.3.20260724",
                confidence=confidence,
                bounding_box=box,
                source_object_ids=(raster_input.raster_source.image_object_id, child_id),
            )
            words.append(
                (
                    DrawingOcrTextEvidence(
                        evidence_id=child_id,
                        text=text,
                        evidence_kind=DrawingOcrEvidenceKind.WORD,
                        confidence=confidence,
                        raster_source=raster_input.raster_source,
                        source_location=location,
                        parser_identity=_OCR_PARSER,
                    ),
                    (block, paragraph, line, word),
                )
            )
            total_chars += len(text)
            if len(words) > limits.max_tokens or total_chars > limits.max_text_characters:
                raise _OcrLimit
    if not words:
        return ()
    line_groups: dict[tuple[str, int, int, int], list[DrawingOcrTextEvidence]] = {}
    block_groups: dict[tuple[str, int], list[DrawingOcrTextEvidence]] = {}
    for item, (block, paragraph, line, _word) in words:
        image_id = item.raster_source.image_object_id
        line_groups.setdefault((image_id, block, paragraph, line), []).append(item)
        block_groups.setdefault((image_id, block), []).append(item)
    if len(line_groups) > limits.max_lines or len(block_groups) > limits.max_blocks:
        raise _OcrLimit
    aggregates: list[DrawingOcrTextEvidence] = [item for item, _ in words]
    for key, members in sorted(line_groups.items()):
        aggregates.append(
            _aggregate_evidence(
                members,
                DrawingOcrEvidenceKind.LINE,
                f"line-{key[1]}-{key[2]}-{key[3]}",
            )
        )
    for key, members in sorted(block_groups.items()):
        aggregates.append(
            _aggregate_evidence(
                members, DrawingOcrEvidenceKind.BLOCK, f"block-{key[1]}"
            )
        )
    if len(aggregates) > 100_000:
        raise _OcrLimit
    return tuple(sorted(aggregates, key=_evidence_sort_key))


def _aggregate_evidence(
    members: list[DrawingOcrTextEvidence],
    kind: DrawingOcrEvidenceKind,
    suffix: str,
) -> DrawingOcrTextEvidence:
    ordered = sorted(members, key=_evidence_sort_key)
    first = ordered[0]
    boxes = [item.source_location.bounding_box for item in ordered]
    valid_boxes = [box for box in boxes if box is not None]
    box = DrawingBoundingBox(
        x0=min(item.x0 for item in valid_boxes),
        top=min(item.top for item in valid_boxes),
        x1=max(item.x1 for item in valid_boxes),
        bottom=max(item.bottom for item in valid_boxes),
    )
    evidence_id = f"{first.raster_source.image_object_id}:{suffix}"
    confidence = min(item.confidence for item in ordered)
    source_ids = tuple(
        [first.raster_source.image_object_id, evidence_id]
        + [item.evidence_id for item in ordered]
    )
    location = DrawingSourceLocation(
        source_id=first.raster_source.source_id,
        page_number=first.raster_source.page_number,
        original_text=" ".join(item.text for item in ordered),
        adapter_id="tesseract-ocr",
        adapter_version="5.5.3.20260724",
        confidence=confidence,
        bounding_box=box,
        source_object_ids=source_ids,
    )
    return DrawingOcrTextEvidence(
        evidence_id=evidence_id,
        text=location.original_text or first.text,
        evidence_kind=kind,
        confidence=confidence,
        raster_source=first.raster_source,
        source_location=location,
        parser_identity=_OCR_PARSER,
    )


def _map_box(
    raster_input: _RasterOcrInput, left: int, top: int, width: int, height: int
) -> DrawingBoundingBox:
    source_box = raster_input.raster_source.bounding_box
    scale_x = (source_box.x1 - source_box.x0) / Decimal(raster_input.width)
    scale_y = (source_box.bottom - source_box.top) / Decimal(raster_input.height)
    return DrawingBoundingBox(
        x0=source_box.x0 + Decimal(left) * scale_x,
        top=source_box.top + Decimal(top) * scale_y,
        x1=source_box.x0 + Decimal(left + width) * scale_x,
        bottom=source_box.top + Decimal(top + height) * scale_y,
    )


def _evidence_sort_key(item: DrawingOcrTextEvidence) -> tuple[Any, ...]:
    box = item.source_location.bounding_box
    return (
        item.raster_source.page_number,
        box.top if box else _ZERO,
        box.x0 if box else _ZERO,
        box.bottom if box else _ZERO,
        box.x1 if box else _ZERO,
        item.text,
        item.evidence_id,
    )


def _normalize_confidence(value: Any) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return _ZERO
    if not parsed.is_finite() or parsed < _ZERO or parsed > Decimal("100"):
        return _ZERO
    return (parsed / Decimal("100")).quantize(Decimal("0.000001"))


def _resolve_tesseract_command() -> str:
    command = shutil.which("tesseract")
    if command:
        return command
    default = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
    if default.is_file():
        return str(default)
    raise _OcrEngineUnavailable


class _OcrLimit(Exception):
    pass


class _OcrEngineUnavailable(Exception):
    pass


__all__ = ["OcrLimits", "OcrResult", "extract_ocr_from_pdf"]
