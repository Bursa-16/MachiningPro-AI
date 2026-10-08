"""Strict, fail-closed parser for Phase 1D VLM provider responses (slice R3B).

A provider response is untrusted bytes. This module turns it into validated,
advisory ``DrawingVlmEvidence`` or rejects the WHOLE response with a stable
``VlmResponseErrorCode``; it never returns partial evidence and never copies
provider text anywhere except the verbatim ``raw_candidate``.

The response is one JSON object with a closed set of keys. Anything unknown,
missing, mistyped, duplicated or out of range is a rejection. Models supply no
normalized values and no rationale text: normalization and reconciliation are
computed by MachiningPro in later slices. Confidence is accepted only as a JSON
number already in [0, 1] (the existing ``DrawingSourceLocation`` contract); a
percentage or a string is rejected rather than reinterpreted.

Nothing here performs I/O, reads the environment or touches deterministic
drawing data. Evidence authority is always ``ADVISORY``.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from decimal import Decimal
from enum import StrEnum, unique
from typing import Any

from backend.interoperability.drawing import (
    DrawingBoundingBox,
    DrawingExtractionAuthority,
    DrawingParserIdentity,
    DrawingSourceLocation,
)
from backend.interoperability.vlm_drawing import (
    DrawingVlmBoxBasis,
    DrawingVlmEvidence,
    DrawingVlmEvidenceKind,
    DrawingVlmLegibility,
    DrawingVlmRegion,
    DrawingVlmValidationStatus,
    VlmLimits,
)
from backend.interoperability.vlm_provider import VlmRequest, VlmResponse

VLM_RESPONSE_SCHEMA_VERSION = "machiningpro.drawing-vlm.response.v1"
# v2 is text-only: the model returns no box and the evidence receives the deterministic
# R3D region extent (box_basis=REGION_EXTENT). v1 is unchanged and still requires a box.
VLM_TEXT_ONLY_RESPONSE_SCHEMA_VERSION = "machiningpro.drawing-vlm.response.v2"
_ACCEPTED_SCHEMA_VERSIONS = frozenset(
    {VLM_RESPONSE_SCHEMA_VERSION, VLM_TEXT_ONLY_RESPONSE_SCHEMA_VERSION}
)

_ADAPTER_ID = "machiningpro.vlm-assist"
_PARSER_IDENTITY = DrawingParserIdentity(_ADAPTER_ID, "1.0.0")
_ZERO = Decimal("0")
_ONE = Decimal("1")
_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "request_id",
        "prompt_contract_version",
        "provider_id",
        "model_id",
        "model_version",
        "items",
    }
)
_ITEM_REQUIRED_KEYS = frozenset({"candidate_type", "value", "legibility", "box"})
_TEXT_ONLY_ITEM_REQUIRED_KEYS = frozenset({"candidate_type", "value", "legibility"})
_ITEM_OPTIONAL_KEYS = frozenset({"confidence", "evidence_reference"})


@unique
class VlmResponseErrorCode(StrEnum):
    """Stable rejection codes; the only failure data a caller keeps."""

    TOO_LARGE = "TOO_LARGE"
    NOT_UTF8 = "NOT_UTF8"
    NOT_JSON = "NOT_JSON"
    DUPLICATE_KEY = "DUPLICATE_KEY"
    NON_FINITE_NUMBER = "NON_FINITE_NUMBER"
    TOP_LEVEL_TYPE = "TOP_LEVEL_TYPE"
    MISSING_FIELD = "MISSING_FIELD"
    UNKNOWN_FIELD = "UNKNOWN_FIELD"
    SCHEMA_VERSION = "SCHEMA_VERSION"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    ITEMS_INVALID = "ITEMS_INVALID"
    TOO_MANY_ITEMS = "TOO_MANY_ITEMS"
    CANDIDATE_TYPE = "CANDIDATE_TYPE"
    VALUE_INVALID = "VALUE_INVALID"
    LEGIBILITY = "LEGIBILITY"
    CONFIDENCE = "CONFIDENCE"
    BOX = "BOX"
    EVIDENCE_REFERENCE = "EVIDENCE_REFERENCE"
    PROVENANCE_INVALID = "PROVENANCE_INVALID"
    REGION_EXTENT = "REGION_EXTENT"


class VlmResponseError(Exception):
    """Response rejection carrying only a stable ``VlmResponseErrorCode``."""

    def __init__(self, code: VlmResponseErrorCode) -> None:
        if not isinstance(code, VlmResponseErrorCode):
            raise TypeError("VlmResponseError.code must be VlmResponseErrorCode")
        super().__init__(code.value)
        self.code = code

    def __repr__(self) -> str:
        return f"VlmResponseError({self.code.value})"

    def __reduce__(self) -> tuple[type[VlmResponseError], tuple[VlmResponseErrorCode]]:
        return (type(self), (self.code,))


def _reject(code: VlmResponseErrorCode) -> VlmResponseError:
    return VlmResponseError(code)


def _reject_constant(_name: str) -> Any:
    raise VlmResponseError(VlmResponseErrorCode.NON_FINITE_NUMBER)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VlmResponseError(VlmResponseErrorCode.DUPLICATE_KEY)
        result[key] = value
    return result


def _decode(payload: bytes) -> object:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _reject(VlmResponseErrorCode.NOT_UTF8) from exc
    try:
        return json.loads(
            text,
            parse_float=Decimal,
            parse_constant=_reject_constant,
            object_pairs_hook=_strict_object,
        )
    except VlmResponseError:
        raise
    except (ValueError, RecursionError) as exc:
        raise _reject(VlmResponseErrorCode.NOT_JSON) from exc


def _check_keys(
    mapping: dict[str, Any], required: frozenset[str], optional: frozenset[str] = frozenset()
) -> None:
    keys = set(mapping)
    if required - keys:
        raise _reject(VlmResponseErrorCode.MISSING_FIELD)
    if keys - required - optional:
        raise _reject(VlmResponseErrorCode.UNKNOWN_FIELD)


def _has_control_characters(value: str) -> bool:
    return any(unicodedata.category(character).startswith("C") for character in value)


def _text(value: object, code: VlmResponseErrorCode, max_length: int | None = None) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or _has_control_characters(value)
        or (max_length is not None and len(value) > max_length)
    ):
        raise _reject(code)
    return value


def _confidence(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise _reject(VlmResponseErrorCode.CONFIDENCE)
    number = Decimal(value)
    if not number.is_finite() or not _ZERO <= number <= _ONE:
        raise _reject(VlmResponseErrorCode.CONFIDENCE)
    return number


def _box_px(value: object, width_px: int, height_px: int) -> tuple[int, int, int, int]:
    if not isinstance(value, list) or len(value) != 4:
        raise _reject(VlmResponseErrorCode.BOX)
    if any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        raise _reject(VlmResponseErrorCode.BOX)
    x0, y0, x1, y1 = value
    if not (0 <= x0 < x1 <= width_px and 0 <= y0 < y1 <= height_px):
        raise _reject(VlmResponseErrorCode.BOX)
    return x0, y0, x1, y1


def _pdf_box(
    box: tuple[int, int, int, int], request: VlmRequest, region: DrawingVlmRegion
) -> DrawingBoundingBox:
    base = region.pdf_box
    scale_x = (base.x1 - base.x0) / Decimal(request.image_width_px)
    scale_y = (base.bottom - base.top) / Decimal(request.image_height_px)
    x0, y0, x1, y1 = box
    return DrawingBoundingBox(
        x0=base.x0 + Decimal(x0) * scale_x,
        top=base.top + Decimal(y0) * scale_y,
        x1=base.x0 + Decimal(x1) * scale_x,
        bottom=base.top + Decimal(y1) * scale_y,
    )


def _region_extent(request: VlmRequest, region: DrawingVlmRegion) -> DrawingBoundingBox:
    """The deterministic R3D region box, validated before it is attached to AI evidence.

    The region must have non-zero area and its pixel crop must match the image the model
    saw. Nothing is repaired or replaced: an invalid region rejects the response.
    """
    box = region.pdf_box
    x0, y0, x1, y1 = region.crop_px
    if (
        not (box.x0 < box.x1 and box.top < box.bottom)
        or x1 - x0 != request.image_width_px
        or y1 - y0 != request.image_height_px
    ):
        raise _reject(VlmResponseErrorCode.REGION_EXTENT)
    return box


def _evidence_id(request: VlmRequest, region: DrawingVlmRegion, sample: int, index: int) -> str:
    seed = "\x1f".join((request.request_id, region.region_id, str(sample), str(index)))
    return "vlm-ev-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


def parse_vlm_response(
    response: VlmResponse,
    request: VlmRequest,
    region: DrawingVlmRegion,
    *,
    limits: VlmLimits,
    sample_index: int = 0,
) -> tuple[DrawingVlmEvidence, ...]:
    """Validate ``response`` and return advisory evidence, or raise ``VlmResponseError``.

    The whole response is rejected on any defect; no partial evidence exists.
    """
    if not isinstance(response, VlmResponse) or not isinstance(request, VlmRequest):
        raise TypeError("response and request must be VlmResponse and VlmRequest")
    if not isinstance(region, DrawingVlmRegion) or not isinstance(limits, VlmLimits):
        raise TypeError("region and limits must be DrawingVlmRegion and VlmLimits")
    if response.request_id != request.request_id or response.reported_model != request.model:
        raise _reject(VlmResponseErrorCode.IDENTITY_MISMATCH)
    if len(response.payload) > min(limits.response_bytes, request.max_response_bytes):
        raise _reject(VlmResponseErrorCode.TOO_LARGE)

    document = _decode(response.payload)
    if not isinstance(document, dict):
        raise _reject(VlmResponseErrorCode.TOP_LEVEL_TYPE)
    _check_keys(document, _TOP_LEVEL_KEYS)
    schema_version = document["schema_version"]
    if not isinstance(schema_version, str) or schema_version not in _ACCEPTED_SCHEMA_VERSIONS:
        raise _reject(VlmResponseErrorCode.SCHEMA_VERSION)
    text_only = schema_version == VLM_TEXT_ONLY_RESPONSE_SCHEMA_VERSION
    required_item_keys = _TEXT_ONLY_ITEM_REQUIRED_KEYS if text_only else _ITEM_REQUIRED_KEYS
    box_basis = (
        DrawingVlmBoxBasis.REGION_EXTENT if text_only else DrawingVlmBoxBasis.MODEL_PIXEL_BOX
    )
    model = request.model
    if (
        document["request_id"] != request.request_id
        or document["prompt_contract_version"] != request.prompt_contract_version
        or document["provider_id"] != model.provider_id
        or document["model_id"] != model.model_id
        or document["model_version"] != model.model_version
    ):
        raise _reject(VlmResponseErrorCode.IDENTITY_MISMATCH)

    items = document["items"]
    if not isinstance(items, list):
        raise _reject(VlmResponseErrorCode.ITEMS_INVALID)
    if len(items) > limits.items_per_response:
        raise _reject(VlmResponseErrorCode.TOO_MANY_ITEMS)

    evidence: list[DrawingVlmEvidence] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise _reject(VlmResponseErrorCode.ITEMS_INVALID)
        _check_keys(item, required_item_keys, _ITEM_OPTIONAL_KEYS)
        try:
            kind = DrawingVlmEvidenceKind(item["candidate_type"])
        except (ValueError, TypeError) as exc:
            raise _reject(VlmResponseErrorCode.CANDIDATE_TYPE) from exc
        value = _text(item["value"], VlmResponseErrorCode.VALUE_INVALID, limits.raw_candidate_chars)
        try:
            legibility = DrawingVlmLegibility(item["legibility"])
        except (ValueError, TypeError) as exc:
            raise _reject(VlmResponseErrorCode.LEGIBILITY) from exc
        confidence = _confidence(item.get("confidence"))
        if text_only:
            box = _region_extent(request, region)
        else:
            pixel_box = _box_px(item["box"], request.image_width_px, request.image_height_px)
            box = _pdf_box(pixel_box, request, region)
        reference = item.get("evidence_reference")
        if reference is not None and (
            not isinstance(reference, str) or reference not in region.trigger_evidence_ids
        ):
            raise _reject(VlmResponseErrorCode.EVIDENCE_REFERENCE)
        evidence_id = _evidence_id(request, region, sample_index, index)
        object_ids = [region.raster_source.image_object_id, region.region_id, evidence_id]
        if reference is not None and reference not in object_ids:
            object_ids.append(reference)
        try:
            location = DrawingSourceLocation(
                source_id=region.raster_source.source_id,
                page_number=region.page_number,
                original_text=value,
                adapter_id=_ADAPTER_ID,
                adapter_version=f"{model.model_id}@{model.model_version}",
                confidence=confidence,
                authority=DrawingExtractionAuthority.ADVISORY,
                bounding_box=box,
                source_object_ids=tuple(object_ids),
            )
            evidence.append(
                DrawingVlmEvidence(
                    evidence_id=evidence_id,
                    evidence_kind=kind,
                    raw_candidate=value,
                    legibility=legibility,
                    source_location=location,
                    parser_identity=_PARSER_IDENTITY,
                    model=model,
                    prompt_contract_version=request.prompt_contract_version,
                    region_id=region.region_id,
                    request_id=request.request_id,
                    sample_index=sample_index,
                    validation_status=DrawingVlmValidationStatus.VALID,
                    reported_confidence=confidence,
                    box_basis=box_basis,
                )
            )
        except (TypeError, ValueError) as exc:
            raise _reject(VlmResponseErrorCode.PROVENANCE_INVALID) from exc
    return tuple(evidence)


__all__ = [
    "VLM_RESPONSE_SCHEMA_VERSION",
    "VLM_TEXT_ONLY_RESPONSE_SCHEMA_VERSION",
    "VlmResponseError",
    "VlmResponseErrorCode",
    "parse_vlm_response",
]
