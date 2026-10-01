"""Vendor-neutral VLM provider contract for Phase 1D advisory drawing evidence.

This module defines contracts only. It contains no network code, no vendor
SDK, no HTTP client, no retry execution and no response parsing. Concrete
adapters (local or, in a later governed phase, remote) implement
``VlmProvider``; the Phase 1D core owns validation, normalization and
reconciliation of whatever a provider returns.

Governing decisions (docs/superpowers/specs/2026-09-24-technical-drawing-
phase-1d-design.md): AI/VLM output is advisory only (D1); no real remote
provider ships in Phase 1D and remote use stays disabled (D3). ``VlmLocality``
is descriptive metadata; nothing here performs or enables remote access.

Deterministic-contract rules followed here, matching the repository's other
drawing modules: frozen dataclasses, ``StrEnum`` vocabularies, ``Decimal`` for
non-integer numbers, booleans rejected where integers are required, tuples for
ordered collections, bounded control-character-free strings, and no raw
image/payload bytes, paths, credentials or timestamps in any ``repr``.
"""

from __future__ import annotations

import re
import threading
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum, unique
from typing import Protocol, runtime_checkable

_MAX_IDENTIFIER_LENGTH = 128
_MAX_PROVIDER_REQUEST_REF_LENGTH = 256
_DEFAULT_MAX_OUTPUT_TOKENS = 2_048        # approved Phase 1D v1 default
_DEFAULT_MAX_RESPONSE_BYTES = 262_144     # approved Phase 1D v1 default (256 KiB)
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_AMBIGUOUS_VERSION_ALIASES = frozenset({"latest", "current", "stable", "default"})
_VERSION_TOKEN_SEPARATORS = re.compile(r"[-_.:/@\s]+")


# ---------------------------------------------------------------------------
# Vocabularies
# ---------------------------------------------------------------------------


@unique
class VlmLocality(StrEnum):
    """Where a provider runs. Descriptive metadata only; enables nothing."""

    LOCAL = "LOCAL"
    REMOTE = "REMOTE"


@unique
class VlmTaskKind(StrEnum):
    """Approved Phase 1D prompt tasks."""

    TRANSCRIBE = "TRANSCRIBE"
    GDT_CHARACTERISTIC = "GDT_CHARACTERISTIC"


@unique
class VlmErrorCode(StrEnum):
    """Stable provider failure codes; the only failure data a caller keeps."""

    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    RATE_LIMITED = "RATE_LIMITED"
    TRANSIENT = "TRANSIENT"
    REQUEST_REJECTED = "REQUEST_REJECTED"
    UNSUPPORTED = "UNSUPPORTED"
    RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_text(value: object, name: str, max_length: int) -> None:
    """Bounded, non-blank, control-character-free text."""
    _validate_unbounded_text(value, name)
    if len(value) > max_length:
        raise ValueError(f"{name} exceeds {max_length} characters")


def _validate_unbounded_text(value: object, name: str) -> None:
    """Non-blank, control-character-free text with no length policy."""
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must not be blank")
    if any(unicodedata.category(character).startswith("C") for character in value):
        raise ValueError(f"{name} must not contain control characters")


def _validate_positive_int(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int")
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _validate_non_negative_decimal(value: object, name: str) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be Decimal")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


# ---------------------------------------------------------------------------
# Identity, capabilities and sampling
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VlmModelIdentity:
    """Pinned provider/model identity. Contains no credentials or timestamps."""

    provider_id: str
    model_id: str
    model_version: str
    locality: VlmLocality

    def __post_init__(self) -> None:
        _validate_text(self.provider_id, "VlmModelIdentity.provider_id", _MAX_IDENTIFIER_LENGTH)
        _validate_text(self.model_id, "VlmModelIdentity.model_id", _MAX_IDENTIFIER_LENGTH)
        _validate_text(
            self.model_version, "VlmModelIdentity.model_version", _MAX_IDENTIFIER_LENGTH
        )
        # A version is a floating alias when it is, or ends in, an alias word:
        # "latest", "v2-latest", "model:stable", "model@latest". An alias word
        # elsewhere in an explicit version ("model-stable-20260924") is allowed.
        tokens = [
            token
            for token in _VERSION_TOKEN_SEPARATORS.split(self.model_version)
            if token
        ]
        if tokens and tokens[-1].casefold() in _AMBIGUOUS_VERSION_ALIASES:
            raise ValueError("VlmModelIdentity.model_version must be an explicitly pinned version")
        if not isinstance(self.locality, VlmLocality):
            raise TypeError("VlmModelIdentity.locality must be VlmLocality")


@dataclass(frozen=True)
class VlmCapabilities:
    """Immutable provider capabilities.

    ``task_kinds`` is a set semantically; it is stored in ``VlmTaskKind``
    declaration order so equality and ``repr`` are deterministic.
    """

    task_kinds: tuple[VlmTaskKind, ...]
    max_image_bytes: int
    max_image_pixels: int
    structured_output: bool

    def __post_init__(self) -> None:
        if not isinstance(self.task_kinds, tuple) or not self.task_kinds:
            raise ValueError("VlmCapabilities.task_kinds must be a non-empty tuple")
        if any(not isinstance(kind, VlmTaskKind) for kind in self.task_kinds):
            raise TypeError("VlmCapabilities.task_kinds must contain VlmTaskKind values")
        if len(set(self.task_kinds)) != len(self.task_kinds):
            raise ValueError("VlmCapabilities.task_kinds must not contain duplicates")
        declaration_order = tuple(VlmTaskKind)
        object.__setattr__(
            self,
            "task_kinds",
            tuple(sorted(self.task_kinds, key=declaration_order.index)),
        )
        _validate_positive_int(self.max_image_bytes, "VlmCapabilities.max_image_bytes")
        _validate_positive_int(self.max_image_pixels, "VlmCapabilities.max_image_pixels")
        if not isinstance(self.structured_output, bool):
            raise TypeError("VlmCapabilities.structured_output must be bool")


@dataclass(frozen=True)
class VlmSamplingHints:
    """Sampling hints passed to a provider.

    Hints only: a provider may ignore them, and MachiningPro never assumes a
    provider is deterministic because of them.
    """

    temperature: Decimal = Decimal("0")
    max_output_tokens: int = _DEFAULT_MAX_OUTPUT_TOKENS
    seed: int | None = None

    def __post_init__(self) -> None:
        _validate_non_negative_decimal(self.temperature, "VlmSamplingHints.temperature")
        _validate_positive_int(self.max_output_tokens, "VlmSamplingHints.max_output_tokens")
        if self.seed is not None and (
            isinstance(self.seed, bool) or not isinstance(self.seed, int)
        ):
            raise TypeError("VlmSamplingHints.seed must be int or None")


# ---------------------------------------------------------------------------
# Request / response
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VlmRequest:
    """One provider request.

    Carries only an opaque request ID, the prompt contract version, the task,
    the pinned model, one PNG image and optional context text. It has no
    field for a path, file name, source ID, drawing ID, environment value,
    credential or timestamp. Request IDs are created by the caller (a later
    Phase 1D task), never here. ``image_png`` is excluded from ``repr``.
    """

    request_id: str
    prompt_contract_version: str
    task_kind: VlmTaskKind
    model: VlmModelIdentity
    image_png: bytes = field(repr=False)
    image_width_px: int
    image_height_px: int
    context_text: tuple[str, ...] = ()
    sampling: VlmSamplingHints = field(default_factory=VlmSamplingHints)
    max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES

    def __post_init__(self) -> None:
        _validate_text(self.request_id, "VlmRequest.request_id", _MAX_IDENTIFIER_LENGTH)
        _validate_text(
            self.prompt_contract_version,
            "VlmRequest.prompt_contract_version",
            _MAX_IDENTIFIER_LENGTH,
        )
        if not isinstance(self.task_kind, VlmTaskKind):
            raise TypeError("VlmRequest.task_kind must be VlmTaskKind")
        if not isinstance(self.model, VlmModelIdentity):
            raise TypeError("VlmRequest.model must be VlmModelIdentity")
        if not isinstance(self.image_png, bytes):
            raise TypeError("VlmRequest.image_png must be bytes")
        if not self.image_png.startswith(_PNG_SIGNATURE):
            raise ValueError("VlmRequest.image_png must be PNG data")
        _validate_positive_int(self.image_width_px, "VlmRequest.image_width_px")
        _validate_positive_int(self.image_height_px, "VlmRequest.image_height_px")
        if not isinstance(self.context_text, tuple):
            raise TypeError("VlmRequest.context_text must be tuple[str, ...]")
        # Structural checks only. Operational size limits belong to the later
        # VlmLimits / orchestration layer, not to this provider contract.
        for item in self.context_text:
            _validate_unbounded_text(item, "VlmRequest.context_text item")
        if not isinstance(self.sampling, VlmSamplingHints):
            raise TypeError("VlmRequest.sampling must be VlmSamplingHints")
        _validate_positive_int(self.max_response_bytes, "VlmRequest.max_response_bytes")


@dataclass(frozen=True)
class VlmResponse:
    """Raw provider response.

    ``payload`` is the provider's raw bytes; it is never parsed or normalized
    in this module and is excluded from ``repr``. ``provider_request_ref`` is
    audit-only metadata and must never become part of deterministic identity.
    """

    request_id: str
    reported_model: VlmModelIdentity
    payload: bytes = field(repr=False)
    provider_request_ref: str | None = None

    def __post_init__(self) -> None:
        _validate_text(self.request_id, "VlmResponse.request_id", _MAX_IDENTIFIER_LENGTH)
        if not isinstance(self.reported_model, VlmModelIdentity):
            raise TypeError("VlmResponse.reported_model must be VlmModelIdentity")
        if not isinstance(self.payload, bytes):
            raise TypeError("VlmResponse.payload must be bytes")
        if self.provider_request_ref is not None:
            _validate_text(
                self.provider_request_ref,
                "VlmResponse.provider_request_ref",
                _MAX_PROVIDER_REQUEST_REF_LENGTH,
            )


# ---------------------------------------------------------------------------
# Cancellation and errors
# ---------------------------------------------------------------------------


class VlmCancellation:
    """Thread-safe, one-way cancellation flag backed by ``threading.Event``."""

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Request cancellation. Idempotent."""
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def __repr__(self) -> str:
        return f"VlmCancellation(cancelled={self.is_cancelled()})"


class VlmProviderError(Exception):
    """Provider failure carrying only a stable ``VlmErrorCode``.

    No free-text message is accepted, so vendor or exception text can never
    flow into deterministic results; ``str(error)`` is the code value.
    """

    def __init__(self, code: VlmErrorCode) -> None:
        if not isinstance(code, VlmErrorCode):
            raise TypeError("VlmProviderError.code must be VlmErrorCode")
        super().__init__(code.value)
        self.code = code

    def __repr__(self) -> str:
        return f"VlmProviderError({self.code.value})"

    def __reduce__(self) -> tuple[type[VlmProviderError], tuple[VlmErrorCode]]:
        return (type(self), (self.code,))


# ---------------------------------------------------------------------------
# Provider protocol and retry policy
# ---------------------------------------------------------------------------


@runtime_checkable
class VlmProvider(Protocol):
    """Contract every VLM adapter implements.

    ``infer`` must honor ``deadline_seconds`` and ``cancellation`` and must
    raise ``VlmProviderError`` (never a vendor exception) on failure. Retries
    are the caller's responsibility, governed by ``VlmRetryPolicy``.
    """

    def identity(self) -> VlmModelIdentity: ...

    def capabilities(self) -> VlmCapabilities: ...

    def infer(
        self,
        request: VlmRequest,
        *,
        deadline_seconds: float,
        cancellation: VlmCancellation,
    ) -> VlmResponse: ...


@dataclass(frozen=True)
class VlmRetryPolicy:
    """Declarative retry policy; this module never executes retries.

    ``backoff_seconds[i]`` is the fixed wait before attempt ``i + 2``, so it
    holds exactly ``max_attempts - 1`` values. There is no jitter.
    """

    max_attempts: int = 2
    retry_on: tuple[VlmErrorCode, ...] = (
        VlmErrorCode.TRANSIENT,
        VlmErrorCode.RATE_LIMITED,
    )
    backoff_seconds: tuple[Decimal, ...] = (Decimal("1"),)

    def __post_init__(self) -> None:
        _validate_positive_int(self.max_attempts, "VlmRetryPolicy.max_attempts")
        if not isinstance(self.retry_on, tuple):
            raise TypeError("VlmRetryPolicy.retry_on must be a tuple")
        if any(not isinstance(code, VlmErrorCode) for code in self.retry_on):
            raise TypeError("VlmRetryPolicy.retry_on must contain VlmErrorCode values")
        if len(set(self.retry_on)) != len(self.retry_on):
            raise ValueError("VlmRetryPolicy.retry_on must not contain duplicates")
        if not isinstance(self.backoff_seconds, tuple):
            raise TypeError("VlmRetryPolicy.backoff_seconds must be a tuple")
        for value in self.backoff_seconds:
            _validate_non_negative_decimal(value, "VlmRetryPolicy.backoff_seconds item")
        if len(self.backoff_seconds) != self.max_attempts - 1:
            raise ValueError(
                "VlmRetryPolicy.backoff_seconds must hold exactly max_attempts - 1 values"
            )


__all__ = [
    "VlmCancellation",
    "VlmCapabilities",
    "VlmErrorCode",
    "VlmLocality",
    "VlmModelIdentity",
    "VlmProvider",
    "VlmProviderError",
    "VlmRequest",
    "VlmResponse",
    "VlmRetryPolicy",
    "VlmSamplingHints",
    "VlmTaskKind",
]
