"""Bounded raster evidence detection for Phase 1C.

This module discovers and validates embedded PDF image objects only.  It does
not OCR, interpret pixels semantically, or place pixel buffers in public
results.  Pillow objects and decoded bytes exist only transiently while a
worker validates an image against the explicit Phase 1C limits.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum, unique
from io import BytesIO
from typing import Any

import pdfplumber
from PIL import Image

from backend.interoperability.drawing import (
    DrawingBoundingBox,
    DrawingIngestionStatus,
    DrawingOcrTextEvidence,
    DrawingParserIdentity,
    DrawingRasterSource,
)

_PARSER_IDENTITY = DrawingParserIdentity(
    parser_id="raster-drawing",
    parser_version="1.0",
    preprocessing_id="ocr-preprocess-v1",
)


@unique
class RasterContentKind(StrEnum):
    """Deterministic page/document content classification."""

    VECTOR_ONLY = "VECTOR_ONLY"
    RASTER_ONLY = "RASTER_ONLY"
    MIXED = "MIXED"
    EMPTY = "EMPTY"


@dataclass(frozen=True)
class RasterLimits:
    """Exact Phase 1C v1 raster resource limits."""

    max_file_bytes: int = 64 * 1024 * 1024
    max_pages: int = 200
    max_images_per_page: int = 16
    max_images_total: int = 512
    max_width: int = 20_000
    max_height: int = 20_000
    max_pixels_per_image: int = 25_000_000
    max_total_pixels: int = 100_000_000
    max_decoded_memory_bytes: int = 512 * 1024 * 1024
    max_result_bytes: int = 8 * 1024 * 1024

    def __post_init__(self) -> None:
        values = (
            ("max_file_bytes", self.max_file_bytes),
            ("max_pages", self.max_pages),
            ("max_images_per_page", self.max_images_per_page),
            ("max_images_total", self.max_images_total),
            ("max_width", self.max_width),
            ("max_height", self.max_height),
            ("max_pixels_per_image", self.max_pixels_per_image),
            ("max_total_pixels", self.max_total_pixels),
            ("max_decoded_memory_bytes", self.max_decoded_memory_bytes),
            ("max_result_bytes", self.max_result_bytes),
        )
        for name, value in values:
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"RasterLimits.{name} must be int")
            if value <= 0:
                raise ValueError(f"RasterLimits.{name} must be positive")
        if self.max_images_per_page > self.max_images_total:
            raise ValueError("max_images_per_page must not exceed max_images_total")
        if self.max_pixels_per_image > self.max_total_pixels:
            raise ValueError("max_pixels_per_image must not exceed max_total_pixels")


@dataclass(frozen=True)
class RasterImageSnapshot:
    """Public metadata for one validated image object; never includes pixels."""

    raster_source: DrawingRasterSource
    width: int
    height: int
    format: str
    rotation: int

    def __post_init__(self) -> None:
        if not isinstance(self.raster_source, DrawingRasterSource):
            raise TypeError("RasterImageSnapshot.raster_source must be DrawingRasterSource")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("RasterImageSnapshot dimensions must be positive")
        if self.format not in {"FLATE", "JPEG", "JPEG2000"}:
            raise ValueError("RasterImageSnapshot.format is not approved")
        if self.rotation not in (0, 90, 180, 270):
            raise ValueError("RasterImageSnapshot.rotation must be 0, 90, 180, or 270")


@dataclass(frozen=True)
class RasterPageSnapshot:
    """Bounded page-level raster/vector classification and image snapshots."""

    page_number: int
    width_pt: Decimal
    height_pt: Decimal
    rotation: int
    content_kind: RasterContentKind
    images: tuple[RasterImageSnapshot, ...] = field(default_factory=tuple)
    vector_object_count: int = 0

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise ValueError("RasterPageSnapshot.page_number must be >= 1")
        for name, value in (("width_pt", self.width_pt), ("height_pt", self.height_pt)):
            if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
                raise ValueError(f"RasterPageSnapshot.{name} must be positive finite Decimal")
        if self.rotation not in (0, 90, 180, 270):
            raise ValueError("RasterPageSnapshot.rotation must be 0, 90, 180, or 270")
        if not isinstance(self.content_kind, RasterContentKind):
            raise TypeError("RasterPageSnapshot.content_kind must be RasterContentKind")
        if not isinstance(self.images, tuple):
            raise TypeError("RasterPageSnapshot.images must be a tuple")
        if self.vector_object_count < 0:
            raise ValueError("RasterPageSnapshot.vector_object_count must be non-negative")


@dataclass(frozen=True)
class RasterDocumentSnapshot:
    """Immutable bounded raster snapshot containing no decoded bytes."""

    source_id: str
    content_kind: RasterContentKind
    pages: tuple[RasterPageSnapshot, ...]
    total_images: int
    total_pixels: int

    def __post_init__(self) -> None:
        if not self.source_id or not self.source_id.strip():
            raise ValueError("RasterDocumentSnapshot.source_id must not be blank")
        if not isinstance(self.content_kind, RasterContentKind):
            raise TypeError("RasterDocumentSnapshot.content_kind must be RasterContentKind")
        if not isinstance(self.pages, tuple):
            raise TypeError("RasterDocumentSnapshot.pages must be a tuple")
        if self.total_images < 0 or self.total_pixels < 0:
            raise ValueError("RasterDocumentSnapshot totals must be non-negative")


@dataclass(frozen=True)
class RasterInspectionResult:
    """Status, bounded diagnostics, and optional raster snapshot."""

    status: DrawingIngestionStatus
    diagnostics: tuple[str, ...] = field(default_factory=tuple)
    snapshot: RasterDocumentSnapshot | None = None
    ocr_evidence: tuple[DrawingOcrTextEvidence, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.status, DrawingIngestionStatus):
            raise TypeError("RasterInspectionResult.status must be DrawingIngestionStatus")
        if not isinstance(self.diagnostics, tuple):
            raise TypeError("RasterInspectionResult.diagnostics must be a tuple")
        if len(self.diagnostics) > 50:
            raise ValueError("RasterInspectionResult diagnostics exceed the bound")
        if any(not isinstance(code, str) or len(code) > 240 for code in self.diagnostics):
            raise ValueError("RasterInspectionResult diagnostics are invalid")
        if self.snapshot is not None and not isinstance(
            self.snapshot, RasterDocumentSnapshot
        ):
            raise TypeError("RasterInspectionResult.snapshot must be RasterDocumentSnapshot")
        if self.ocr_evidence:
            raise ValueError("Task 3 must not emit OCR evidence")
        if self.status in (
            DrawingIngestionStatus.FAILED,
            DrawingIngestionStatus.UNSUPPORTED,
        ) and self.snapshot is not None:
            raise ValueError("fail-closed raster results must not carry a snapshot")


@dataclass(frozen=True)
class _RasterOcrInput:
    """Private worker input; pixel bytes never appear in public results."""

    page_number: int
    rotation: int
    raster_source: DrawingRasterSource
    width: int
    height: int
    pixels: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if len(self.pixels) != self.width * self.height:
            raise ValueError("_RasterOcrInput pixel buffer does not match dimensions")


class _RasterUnsupported(Exception):
    pass


class _RasterMalformed(Exception):
    pass


class _RasterLimit(Exception):
    def __init__(self, code: str) -> None:
        self.code = code


def inspect_raster_pdf(
    content: bytes,
    source_id: str,
    *,
    limits: RasterLimits | None = None,
) -> RasterInspectionResult:
    """Inspect embedded PDF image objects without OCR or semantic interpretation."""

    active_limits = limits or RasterLimits()
    if not isinstance(content, bytes):
        return _failure("PDF_INPUT_INVALID")
    if len(content) > active_limits.max_file_bytes:
        return _failure("PDF_FILE_LIMIT")
    if not content[:1024].find(b"%PDF-") >= 0:
        return _unsupported("PDF_UNSUPPORTED")
    if not source_id or not source_id.strip():
        return _failure("PDF_SOURCE_ID_INVALID")

    try:
        with pdfplumber.open(BytesIO(content)) as document:
            page_count = len(document.pages)
            if page_count > active_limits.max_pages:
                raise _RasterLimit("RASTER_PAGE_LIMIT")
            pages: list[RasterPageSnapshot] = []
            total_images = 0
            total_pixels = 0
            unsupported_count = 0
            malformed_count = 0
            for page_number, page in enumerate(document.pages, start=1):
                images = _sorted_images(page.images)
                if len(images) > active_limits.max_images_per_page:
                    raise _RasterLimit("RASTER_PAGE_IMAGE_LIMIT")
                total_images += len(images)
                if total_images > active_limits.max_images_total:
                    raise _RasterLimit("RASTER_IMAGE_COUNT_LIMIT")
                vector_object_count = sum(
                    len(getattr(page, name, ()) or ())
                    for name in ("chars", "lines", "rects", "curves")
                )
                snapshots: list[RasterImageSnapshot] = []
                for image_index, image in enumerate(images, start=1):
                    try:
                        snapshot, pixel_count, _ = _inspect_image(
                            image,
                            source_id,
                            page_number,
                            image_index,
                            page.rotation or 0,
                            active_limits,
                        )
                        total_pixels += pixel_count
                        if total_pixels > active_limits.max_total_pixels:
                            raise _RasterLimit("RASTER_PIXEL_COUNT_LIMIT")
                        if total_pixels * 4 > active_limits.max_decoded_memory_bytes:
                            raise _RasterLimit("RASTER_MEMORY_LIMIT")
                        snapshots.append(snapshot)
                    except _RasterUnsupported:
                        unsupported_count += 1
                    except _RasterMalformed:
                        malformed_count += 1
                if snapshots or vector_object_count:
                    if snapshots and vector_object_count:
                        kind = RasterContentKind.MIXED
                    elif snapshots:
                        kind = RasterContentKind.RASTER_ONLY
                    else:
                        kind = RasterContentKind.VECTOR_ONLY
                    pages.append(
                        RasterPageSnapshot(
                            page_number=page_number,
                            width_pt=_decimal(page.width),
                            height_pt=_decimal(page.height),
                            rotation=int(page.rotation or 0),
                            content_kind=kind,
                            images=tuple(snapshots),
                            vector_object_count=vector_object_count,
                        )
                    )
            if not pages and malformed_count:
                return _failure("RASTER_MALFORMED_IMAGE")
            if not pages and unsupported_count:
                return _unsupported("RASTER_UNSUPPORTED_FORMAT")
            if not pages:
                snapshot = RasterDocumentSnapshot(
                    source_id=source_id,
                    content_kind=RasterContentKind.EMPTY,
                    pages=tuple(),
                    total_images=total_images,
                    total_pixels=total_pixels,
                )
                return RasterInspectionResult(
                    status=DrawingIngestionStatus.INSUFFICIENT_DATA,
                    snapshot=snapshot,
                    diagnostics=("RASTER_EMPTY",),
                )
            document_kind = _document_kind(pages)
            snapshot = RasterDocumentSnapshot(
                source_id=source_id,
                content_kind=document_kind,
                pages=tuple(pages),
                total_images=sum(len(page.images) for page in pages),
                total_pixels=total_pixels,
            )
            if len(repr(snapshot).encode("utf-8")) > active_limits.max_result_bytes:
                raise _RasterLimit("RASTER_RESULT_LIMIT")
            diagnostics: list[str] = []
            if unsupported_count:
                diagnostics.append("RASTER_UNSUPPORTED_FORMAT")
            if malformed_count:
                diagnostics.append("RASTER_MALFORMED_IMAGE")
            if unsupported_count or malformed_count:
                status = (
                    DrawingIngestionStatus.PARTIAL
                    if snapshot.total_images
                    or snapshot.content_kind is RasterContentKind.VECTOR_ONLY
                    else DrawingIngestionStatus.UNSUPPORTED
                )
                return RasterInspectionResult(
                    status=status,
                    diagnostics=tuple(diagnostics),
                    snapshot=snapshot if status is DrawingIngestionStatus.PARTIAL else None,
                )
            return RasterInspectionResult(
                status=DrawingIngestionStatus.VALID,
                snapshot=snapshot,
            )
    except _RasterLimit as exc:
        return _failure(exc.code)
    except _RasterUnsupported:
        return _unsupported("RASTER_UNSUPPORTED_FORMAT")
    except _RasterMalformed:
        return _failure("RASTER_MALFORMED_IMAGE")
    except Exception:
        return _failure("RASTER_WORKER_FAILURE")


def prepare_raster_ocr_inputs(
    content: bytes,
    source_id: str,
    *,
    limits: RasterLimits | None = None,
) -> tuple[_RasterOcrInput, ...]:
    """Prepare bounded decoded pixels for the private OCR worker boundary."""

    active_limits = limits or RasterLimits()
    if not isinstance(content, bytes) or len(content) > active_limits.max_file_bytes:
        raise _RasterLimit("PDF_FILE_LIMIT")
    if content[:1024].find(b"%PDF-") < 0:
        raise _RasterUnsupported
    with pdfplumber.open(BytesIO(content)) as document:
        if len(document.pages) > active_limits.max_pages:
            raise _RasterLimit("RASTER_PAGE_LIMIT")
        inputs: list[_RasterOcrInput] = []
        total_pixels = 0
        total_images = 0
        for page_number, page in enumerate(document.pages, start=1):
            images = _sorted_images(page.images)
            if len(images) > active_limits.max_images_per_page:
                raise _RasterLimit("RASTER_PAGE_IMAGE_LIMIT")
            total_images += len(images)
            if total_images > active_limits.max_images_total:
                raise _RasterLimit("RASTER_IMAGE_COUNT_LIMIT")
            for image_index, image in enumerate(images, start=1):
                snapshot, pixel_count, pixels = _inspect_image(
                    image,
                    source_id,
                    page_number,
                    image_index,
                    int(page.rotation or 0),
                    active_limits,
                )
                total_pixels += pixel_count
                if total_pixels > active_limits.max_total_pixels:
                    raise _RasterLimit("RASTER_PIXEL_COUNT_LIMIT")
                if total_pixels * 4 > active_limits.max_decoded_memory_bytes:
                    raise _RasterLimit("RASTER_MEMORY_LIMIT")
                inputs.append(
                    _RasterOcrInput(
                        page_number=page_number,
                        rotation=snapshot.rotation,
                        raster_source=snapshot.raster_source,
                        width=snapshot.width,
                        height=snapshot.height,
                        pixels=pixels,
                    )
                )
        if not inputs:
            raise _RasterUnsupported
        return tuple(inputs)


def _inspect_image(
    image: dict[str, Any],
    source_id: str,
    page_number: int,
    image_index: int,
    rotation: int,
    limits: RasterLimits,
) -> tuple[RasterImageSnapshot, int, bytes]:
    width, height = _image_dimensions(image)
    if width > limits.max_width or height > limits.max_height:
        raise _RasterLimit("RASTER_DIMENSION_LIMIT")
    pixels = width * height
    if pixels <= 0:
        raise _RasterMalformed
    if pixels > limits.max_pixels_per_image:
        raise _RasterLimit("RASTER_PIXEL_COUNT_LIMIT")
    if pixels * 4 > limits.max_decoded_memory_bytes:
        raise _RasterLimit("RASTER_MEMORY_LIMIT")
    encoding = _image_encoding(image)
    stream = image.get("stream")
    if stream is None:
        raise _RasterMalformed
    decoded_pixels = _decode_image(
        stream,
        width,
        height,
        encoding,
        image.get("colorspace"),
        image.get("bits"),
    )
    bbox = DrawingBoundingBox(
        x0=_decimal(image.get("x0")),
        top=_decimal(image.get("top")),
        x1=_decimal(image.get("x1")),
        bottom=_decimal(image.get("bottom")),
    )
    object_id = f"page-{page_number}:image-{image_index}"
    raster_source = DrawingRasterSource(
        source_id=source_id,
        page_number=page_number,
        image_object_id=object_id,
        bounding_box=bbox,
        parser_identity=_PARSER_IDENTITY,
        image_format=encoding,
    )
    return (
        RasterImageSnapshot(
            raster_source=raster_source,
            width=width,
            height=height,
            format=encoding,
            rotation=rotation,
        ),
        pixels,
        decoded_pixels,
    )


def _decode_image(
    stream: Any,
    width: int,
    height: int,
    encoding: str,
    colorspace: Any,
    bits: Any,
) -> bytes:
    if bits != 8:
        raise _RasterUnsupported
    try:
        data = stream.get_data()
    except Exception as exc:
        raise _RasterMalformed from exc
    try:
        if encoding == "FLATE":
            colorspace_text = str(colorspace)
            if isinstance(colorspace, list) and colorspace and "Indexed" in str(colorspace[0]):
                if len(colorspace) < 4 or not isinstance(colorspace[3], bytes):
                    raise _RasterUnsupported
                high_value = colorspace[2]
                if (
                    not isinstance(high_value, int)
                    or high_value < 0
                    or high_value > 255
                ):
                    raise _RasterMalformed
                palette = colorspace[3]
                base_name = str(colorspace[1]) if len(colorspace) > 1 else ""
                channels = 1 if "DeviceGray" in base_name else 3
                if len(palette) < (high_value + 1) * channels:
                    raise _RasterMalformed
                if len(data) != width * height or any(
                    index > high_value for index in data
                ):
                    raise _RasterMalformed
                indexed = Image.frombytes("P", (width, height), data)
                if channels == 1:
                    palette_bytes = bytes(
                        value for value in palette[: high_value + 1]
                    )
                else:
                    palette_bytes = palette[: (high_value + 1) * 3]
                indexed.putpalette(palette_bytes + bytes(768 - len(palette_bytes)))
                image = indexed
            elif "DeviceGray" in colorspace_text:
                if len(data) != width * height:
                    raise _RasterMalformed
                image = Image.frombytes("L", (width, height), data)
            elif "DeviceRGB" in colorspace_text:
                if len(data) != width * height * 3:
                    raise _RasterMalformed
                image = Image.frombytes("RGB", (width, height), data)
            else:
                raise _RasterUnsupported
        else:
            with Image.open(BytesIO(data)) as image_file:
                if getattr(image_file, "n_frames", 1) != 1:
                    raise _RasterUnsupported
                image_file.load()
                image = image_file.copy()
        if image.size != (width, height):
            raise _RasterMalformed
        normalized = image.convert("L")
        normalized.load()
        decoded_pixels = normalized.tobytes()
        normalized.close()
    except Image.DecompressionBombError as exc:
        raise _RasterLimit("RASTER_PIXEL_COUNT_LIMIT") from exc
    except (OSError, ValueError, zlib.error) as exc:
        raise _RasterMalformed from exc
    finally:
        try:
            image.close()
        except UnboundLocalError:
            pass
    return decoded_pixels


def _image_dimensions(image: dict[str, Any]) -> tuple[int, int]:
    source_size = image.get("srcsize")
    if not isinstance(source_size, tuple) or len(source_size) != 2:
        raise _RasterMalformed
    width, height = source_size
    if isinstance(width, bool) or isinstance(height, bool):
        raise _RasterMalformed
    try:
        width, height = int(width), int(height)
    except (TypeError, ValueError) as exc:
        raise _RasterMalformed from exc
    if width <= 0 or height <= 0:
        raise _RasterMalformed
    return width, height


def _image_encoding(image: dict[str, Any]) -> str:
    stream = image.get("stream")
    filters = getattr(stream, "attrs", {}).get("Filter") if stream is not None else None
    text = str(filters)
    if "DCTDecode" in text:
        return "JPEG"
    if "JPXDecode" in text:
        return "JPEG2000"
    if "FlateDecode" in text:
        return "FLATE"
    raise _RasterUnsupported


def _sorted_images(images: Any) -> tuple[dict[str, Any], ...]:
    return tuple(
        sorted(
            (image for image in images if isinstance(image, dict)),
            key=lambda image: (
                _safe_sort_number(image.get("top")),
                _safe_sort_number(image.get("x0")),
                _safe_sort_number(image.get("bottom")),
                _safe_sort_number(image.get("x1")),
                str(image.get("name", "")),
            ),
        )
    )


def _safe_sort_number(value: Any) -> Decimal:
    try:
        number = Decimal(str(value))
    except Exception:
        return Decimal("Infinity")
    return number if number.is_finite() else Decimal("Infinity")


def _decimal(value: Any) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise _RasterMalformed from exc
    if not result.is_finite():
        raise _RasterMalformed
    return result


def _document_kind(pages: list[RasterPageSnapshot]) -> RasterContentKind:
    has_raster = any(page.images for page in pages)
    has_vector = any(page.vector_object_count for page in pages)
    if has_raster and has_vector:
        return RasterContentKind.MIXED
    if has_raster:
        return RasterContentKind.RASTER_ONLY
    if has_vector:
        return RasterContentKind.VECTOR_ONLY
    return RasterContentKind.EMPTY


def _failure(code: str) -> RasterInspectionResult:
    return RasterInspectionResult(status=DrawingIngestionStatus.FAILED, diagnostics=(code,))


def _unsupported(code: str) -> RasterInspectionResult:
    return RasterInspectionResult(
        status=DrawingIngestionStatus.UNSUPPORTED,
        diagnostics=(code,),
    )


__all__ = [
    "RasterContentKind",
    "RasterDocumentSnapshot",
    "RasterImageSnapshot",
    "RasterInspectionResult",
    "RasterLimits",
    "RasterPageSnapshot",
    "inspect_raster_pdf",
]
