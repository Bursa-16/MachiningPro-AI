"""Bounded, deterministic Phase 1D request preparation (slice R3D).

``prepare_vlm_requests`` turns caller-SELECTED raster regions into provider-neutral
``VlmRequest`` objects. It never chooses regions, pages or documents itself, never
calls a provider, never parses a response, never reconciles and never alters the
deterministic result it is given.

Safety comes from reuse, not a second implementation: pixels are obtained through
the Phase 1C ``prepare_raster_ocr_inputs`` (declared-dimension, pixel, memory,
page and image-count limits, and the declared-versus-actual size gate before any
decode). On top of that this module enforces the governed ``VlmLimits`` crop and
payload bounds BEFORE decoding where they can be known from the region alone, and
rejects any region that is not inside the image it names.

Every failure is a stable ``VlmPreparationErrorCode``; no partial output exists.
Request identity is a SHA-256 of explicit stable inputs (source, page, region,
prompt contract, response schema, task, payload digest) with no clock, randomness,
environment or filesystem access. The only context text that can be attached is
the original text of deterministic dimensions already linked to the region's own
trigger evidence, and only in GUIDED mode under an explicit character cap; there
is no parameter through which free-form text can reach a request. The payload is
passed as bytes: no path is ever read.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum, unique
from io import BytesIO

from PIL import Image

from backend.interoperability.drawing import DrawingIngestionResult
from backend.interoperability.raster_drawing import (
    RasterLimits,
    _RasterLimit,
    _RasterMalformed,
    _RasterOcrInput,
    _RasterUnsupported,
    prepare_raster_ocr_inputs,
)
from backend.interoperability.vlm_drawing import DrawingVlmMode, DrawingVlmRegion, VlmLimits
from backend.interoperability.vlm_provider import (
    VlmModelIdentity,
    VlmRequest,
    VlmSamplingHints,
    VlmTaskKind,
)
from backend.interoperability.vlm_response import VLM_RESPONSE_SCHEMA_VERSION

_SHA256 = re.compile(r"[0-9a-f]{64}")
_MAX_IDENTIFIER_LENGTH = 128


@unique
class VlmPreparationErrorCode(StrEnum):
    """Stable rejection codes; the only failure data a caller keeps."""

    NO_REGIONS = "NO_REGIONS"
    DUPLICATE_REGION_ID = "DUPLICATE_REGION_ID"
    REQUEST_LIMIT = "REQUEST_LIMIT"
    REGION_LIMIT = "REGION_LIMIT"
    PAGE_REGION_LIMIT = "PAGE_REGION_LIMIT"
    SOURCE_MISMATCH = "SOURCE_MISMATCH"
    CROP_EDGE_LIMIT = "CROP_EDGE_LIMIT"
    CROP_PIXEL_LIMIT = "CROP_PIXEL_LIMIT"
    PDF_INPUT_INVALID = "PDF_INPUT_INVALID"
    RASTER_UNSUPPORTED = "RASTER_UNSUPPORTED"
    RASTER_MALFORMED = "RASTER_MALFORMED"
    RASTER_LIMIT = "RASTER_LIMIT"
    RASTER_FAILURE = "RASTER_FAILURE"
    REGION_SOURCE_NOT_FOUND = "REGION_SOURCE_NOT_FOUND"
    REGION_SOURCE_MISMATCH = "REGION_SOURCE_MISMATCH"
    REGION_OUTSIDE_IMAGE = "REGION_OUTSIDE_IMAGE"
    REGION_OUTSIDE_PAGE_AREA = "REGION_OUTSIDE_PAGE_AREA"
    PNG_TOO_LARGE = "PNG_TOO_LARGE"
    PAYLOAD_LIMIT = "PAYLOAD_LIMIT"
    CONTEXT_LIMIT_REQUIRED = "CONTEXT_LIMIT_REQUIRED"
    CONTEXT_TOO_LARGE = "CONTEXT_TOO_LARGE"
    CONTEXT_INVALID = "CONTEXT_INVALID"
    REQUEST_INVALID = "REQUEST_INVALID"


class VlmPreparationError(Exception):
    """Preparation rejection carrying only a stable ``VlmPreparationErrorCode``."""

    def __init__(self, code: VlmPreparationErrorCode) -> None:
        if not isinstance(code, VlmPreparationErrorCode):
            raise TypeError("VlmPreparationError.code must be VlmPreparationErrorCode")
        super().__init__(code.value)
        self.code = code

    def __repr__(self) -> str:
        return f"VlmPreparationError({self.code.value})"

    def __reduce__(self) -> tuple[type[VlmPreparationError], tuple[VlmPreparationErrorCode]]:
        return (type(self), (self.code,))


_E = VlmPreparationErrorCode


def _fail(code: VlmPreparationErrorCode) -> VlmPreparationError:
    return VlmPreparationError(code)


def _positive_int_or_none(value: object, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"VlmPreparationConfig.{name} must be a positive int or None")


@dataclass(frozen=True)
class VlmPreparationConfig:
    """Explicit preparation settings. Nothing is read from the environment.

    ``prompt_contract_version`` and ``model`` have no defaults: the prompt
    contract is governed by the caller and the model is the provider identity
    the requests are for. ``max_context_chars`` and ``max_total_payload_bytes``
    have no governed value in this repository, so they are explicit and optional;
    GUIDED mode refuses to run without a context cap.
    """

    prompt_contract_version: str
    model: VlmModelIdentity
    task_kind: VlmTaskKind = VlmTaskKind.TRANSCRIBE
    mode: DrawingVlmMode = DrawingVlmMode.BLIND
    limits: VlmLimits = VlmLimits()
    raster_limits: RasterLimits | None = None
    max_context_chars: int | None = None
    max_total_payload_bytes: int | None = None

    def __post_init__(self) -> None:
        version = self.prompt_contract_version
        if (
            not isinstance(version, str)
            or not version.strip()
            or len(version) > _MAX_IDENTIFIER_LENGTH
            or any(unicodedata.category(c).startswith("C") for c in version)
        ):
            raise ValueError("VlmPreparationConfig.prompt_contract_version is invalid")
        if not isinstance(self.model, VlmModelIdentity):
            raise TypeError("VlmPreparationConfig.model must be VlmModelIdentity")
        if not isinstance(self.task_kind, VlmTaskKind):
            raise TypeError("VlmPreparationConfig.task_kind must be VlmTaskKind")
        if not isinstance(self.mode, DrawingVlmMode):
            raise TypeError("VlmPreparationConfig.mode must be DrawingVlmMode")
        if not isinstance(self.limits, VlmLimits):
            raise TypeError("VlmPreparationConfig.limits must be VlmLimits")
        if self.raster_limits is not None and not isinstance(self.raster_limits, RasterLimits):
            raise TypeError("VlmPreparationConfig.raster_limits must be RasterLimits or None")
        _positive_int_or_none(self.max_context_chars, "max_context_chars")
        _positive_int_or_none(self.max_total_payload_bytes, "max_total_payload_bytes")


@dataclass(frozen=True)
class PreparedVlmRequest:
    """One prepared request plus the region and digest it is bound to."""

    request: VlmRequest
    region: DrawingVlmRegion
    payload_sha256: str
    schema_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.request, VlmRequest):
            raise TypeError("PreparedVlmRequest.request must be VlmRequest")
        if not isinstance(self.region, DrawingVlmRegion):
            raise TypeError("PreparedVlmRequest.region must be DrawingVlmRegion")
        if _SHA256.fullmatch(self.payload_sha256 or "") is None:
            raise ValueError("PreparedVlmRequest.payload_sha256 must be a SHA-256 hex digest")
        if hashlib.sha256(self.request.image_png).hexdigest() != self.payload_sha256:
            raise ValueError("PreparedVlmRequest.payload_sha256 must match the image payload")
        if not self.schema_version or not self.schema_version.strip():
            raise ValueError("PreparedVlmRequest.schema_version must not be blank")


def extractor_inputs(
    prepared: Sequence[PreparedVlmRequest],
) -> tuple[tuple[VlmRequest, ...], dict[str, DrawingVlmRegion]]:
    """Return ``(requests, regions)`` in the shape ``extract_candidates`` takes."""
    items = tuple(prepared)
    return (
        tuple(item.request for item in items),
        {item.request.request_id: item.region for item in items},
    )


def _check_counts(regions: tuple[DrawingVlmRegion, ...], limits: VlmLimits) -> None:
    if not regions:
        raise _fail(_E.NO_REGIONS)
    if len({region.region_id for region in regions}) != len(regions):
        raise _fail(_E.DUPLICATE_REGION_ID)
    if len(regions) > limits.regions_total:
        raise _fail(_E.REGION_LIMIT)
    if len(regions) > limits.requests_per_document:
        raise _fail(_E.REQUEST_LIMIT)
    per_page: dict[int, int] = {}
    for region in regions:
        per_page[region.page_number] = per_page.get(region.page_number, 0) + 1
    if max(per_page.values()) > limits.regions_per_page:
        raise _fail(_E.PAGE_REGION_LIMIT)


def _check_crop_bounds(region: DrawingVlmRegion, limits: VlmLimits) -> tuple[int, int]:
    x0, y0, x1, y1 = region.crop_px
    width, height = x1 - x0, y1 - y0
    if max(width, height) > limits.crop_longest_edge_px:
        raise _fail(_E.CROP_EDGE_LIMIT)
    if width * height > limits.crop_pixels:
        raise _fail(_E.CROP_PIXEL_LIMIT)
    return width, height


def _locate(
    inputs: tuple[_RasterOcrInput, ...], region: DrawingVlmRegion
) -> _RasterOcrInput:
    for candidate in inputs:
        source = candidate.raster_source
        if (
            candidate.page_number == region.page_number
            and source.image_object_id == region.raster_source.image_object_id
        ):
            if source != region.raster_source:
                raise _fail(_E.REGION_SOURCE_MISMATCH)
            return candidate
    raise _fail(_E.REGION_SOURCE_NOT_FOUND)


def _check_inside(region: DrawingVlmRegion, image: _RasterOcrInput) -> None:
    x0, y0, x1, y1 = region.crop_px
    if x1 > image.width or y1 > image.height:
        raise _fail(_E.REGION_OUTSIDE_IMAGE)
    area = image.raster_source.bounding_box
    box = region.pdf_box
    if (
        box.x0 < area.x0
        or box.x1 > area.x1
        or box.top < area.top
        or box.bottom > area.bottom
    ):
        raise _fail(_E.REGION_OUTSIDE_PAGE_AREA)


def _encode_crop(image: _RasterOcrInput, region: DrawingVlmRegion, limits: VlmLimits) -> bytes:
    with Image.frombytes("L", (image.width, image.height), image.pixels) as full:
        with full.crop(region.crop_px) as cropped:
            cropped.load()
            buffer = BytesIO()
            cropped.save(buffer, format="PNG", compress_level=9)
    payload = buffer.getvalue()
    if len(payload) > limits.crop_png_bytes:
        raise _fail(_E.PNG_TOO_LARGE)
    return payload


def _context(
    base_result: DrawingIngestionResult, region: DrawingVlmRegion, config: VlmPreparationConfig
) -> tuple[str, ...]:
    """Original text of deterministic dimensions linked to this region's own triggers."""
    if config.mode is not DrawingVlmMode.GUIDED:
        return ()
    cap = config.max_context_chars
    if cap is None:
        raise _fail(_E.CONTEXT_LIMIT_REQUIRED)
    document = base_result.document
    triggers = set(region.trigger_evidence_ids)
    texts: set[str] = set()
    for dimension in document.all_dimensions if document is not None else ():
        location = dimension.source_location
        if (
            location is None
            or location.page_number != region.page_number
            or not triggers & set(location.source_object_ids)
        ):
            continue
        text = (location.original_text or "").strip()
        if not text:
            continue
        if any(unicodedata.category(c).startswith("C") for c in text):
            raise _fail(_E.CONTEXT_INVALID)
        texts.add(text)
    ordered = tuple(sorted(texts))
    if sum(len(text) for text in ordered) > cap:
        raise _fail(_E.CONTEXT_TOO_LARGE)
    return ordered


def _request_id(
    source_id: str, region: DrawingVlmRegion, config: VlmPreparationConfig, digest: str
) -> str:
    seed = "\x1f".join(
        (
            source_id,
            str(region.page_number),
            region.region_id,
            config.prompt_contract_version,
            VLM_RESPONSE_SCHEMA_VERSION,
            config.task_kind.value,
            digest,
        )
    )
    return "vlm-req-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def prepare_vlm_requests(
    base_result: DrawingIngestionResult,
    pdf_bytes: bytes,
    regions: Sequence[DrawingVlmRegion],
    *,
    config: VlmPreparationConfig,
) -> tuple[PreparedVlmRequest, ...]:
    """Prepare one request per caller-selected region, or raise ``VlmPreparationError``.

    Output is sorted by ``(page_number, region_id)`` so it does not depend on the
    order of ``regions``. ``base_result`` is only read.
    """
    if not isinstance(base_result, DrawingIngestionResult):
        raise TypeError("base_result must be DrawingIngestionResult")
    if not isinstance(config, VlmPreparationConfig):
        raise TypeError("config must be VlmPreparationConfig")
    selected = tuple(regions)
    if any(not isinstance(region, DrawingVlmRegion) for region in selected):
        raise TypeError("regions must contain DrawingVlmRegion values")
    limits = config.limits

    _check_counts(selected, limits)
    source_id = base_result.source_id
    if any(region.raster_source.source_id != source_id for region in selected):
        raise _fail(_E.SOURCE_MISMATCH)
    sizes = {region.region_id: _check_crop_bounds(region, limits) for region in selected}
    if config.mode is DrawingVlmMode.GUIDED and config.max_context_chars is None:
        raise _fail(_E.CONTEXT_LIMIT_REQUIRED)
    if not isinstance(pdf_bytes, bytes):
        raise _fail(_E.PDF_INPUT_INVALID)

    try:
        inputs = prepare_raster_ocr_inputs(pdf_bytes, source_id, limits=config.raster_limits)
    except _RasterUnsupported as exc:
        raise _fail(_E.RASTER_UNSUPPORTED) from exc
    except _RasterMalformed as exc:
        raise _fail(_E.RASTER_MALFORMED) from exc
    except _RasterLimit as exc:
        raise _fail(_E.RASTER_LIMIT) from exc
    except Exception as exc:
        raise _fail(_E.RASTER_FAILURE) from exc

    prepared: list[PreparedVlmRequest] = []
    total_bytes = 0
    for region in sorted(selected, key=lambda item: (item.page_number, item.region_id)):
        image = _locate(inputs, region)
        _check_inside(region, image)
        payload = _encode_crop(image, region, limits)
        total_bytes += len(payload)
        cap = config.max_total_payload_bytes
        if cap is not None and total_bytes > cap:
            raise _fail(_E.PAYLOAD_LIMIT)
        digest = hashlib.sha256(payload).hexdigest()
        width, height = sizes[region.region_id]
        try:
            request = VlmRequest(
                request_id=_request_id(source_id, region, config, digest),
                prompt_contract_version=config.prompt_contract_version,
                task_kind=config.task_kind,
                model=config.model,
                image_png=payload,
                image_width_px=width,
                image_height_px=height,
                context_text=_context(base_result, region, config),
                sampling=VlmSamplingHints(max_output_tokens=limits.output_tokens_hint),
                max_response_bytes=limits.response_bytes,
            )
        except (TypeError, ValueError) as exc:
            raise _fail(_E.REQUEST_INVALID) from exc
        prepared.append(
            PreparedVlmRequest(
                request=request,
                region=region,
                payload_sha256=digest,
                schema_version=VLM_RESPONSE_SCHEMA_VERSION,
            )
        )
    return tuple(prepared)


__all__ = [
    "PreparedVlmRequest",
    "VlmPreparationConfig",
    "VlmPreparationError",
    "VlmPreparationErrorCode",
    "extractor_inputs",
    "prepare_vlm_requests",
]
