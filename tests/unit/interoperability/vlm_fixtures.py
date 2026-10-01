"""Deterministic, offline fake VLM providers for Phase 1D tests.

No fake here opens a socket, performs HTTP or imports a vendor SDK. Every
fake honors ``VlmCancellation`` and raises only ``VlmProviderError``.
"""

from __future__ import annotations

import struct
import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from backend.interoperability.vlm_provider import (
    VlmCancellation,
    VlmCapabilities,
    VlmErrorCode,
    VlmLocality,
    VlmModelIdentity,
    VlmProviderError,
    VlmRequest,
    VlmResponse,
    VlmTaskKind,
)

FAKE_PROMPT_CONTRACT_VERSION = "machiningpro.drawing-vlm.v1"


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def tiny_png(width: int = 2, height: int = 2, value: int = 255) -> bytes:
    """Deterministic 8-bit grayscale PNG built with the standard library."""
    raw = b"".join(b"\x00" + bytes([value]) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw, 9))
        + _png_chunk(b"IEND", b"")
    )


def make_identity(
    *,
    provider_id: str = "fake.local",
    model_id: str = "fake-vlm",
    model_version: str = "2026-09-24",
    locality: VlmLocality = VlmLocality.LOCAL,
) -> VlmModelIdentity:
    return VlmModelIdentity(
        provider_id=provider_id,
        model_id=model_id,
        model_version=model_version,
        locality=locality,
    )


def make_capabilities() -> VlmCapabilities:
    return VlmCapabilities(
        task_kinds=(VlmTaskKind.TRANSCRIBE, VlmTaskKind.GDT_CHARACTERISTIC),
        max_image_bytes=4 * 1024 * 1024,
        max_image_pixels=4_194_304,
        structured_output=True,
    )


def make_request(
    request_id: str = "vlm-req-000000000000000000000001",
    *,
    model: VlmModelIdentity | None = None,
    task_kind: VlmTaskKind = VlmTaskKind.TRANSCRIBE,
    context_text: tuple[str, ...] = (),
) -> VlmRequest:
    return VlmRequest(
        request_id=request_id,
        prompt_contract_version=FAKE_PROMPT_CONTRACT_VERSION,
        task_kind=task_kind,
        model=model or make_identity(),
        image_png=tiny_png(),
        image_width_px=2,
        image_height_px=2,
        context_text=context_text,
    )


@dataclass(frozen=True)
class RecordedCall:
    request: VlmRequest
    deadline_seconds: float
    cancellation: VlmCancellation


class _FakeBase:
    def __init__(
        self,
        identity: VlmModelIdentity | None = None,
        capabilities: VlmCapabilities | None = None,
    ) -> None:
        self._identity = identity or make_identity()
        self._capabilities = capabilities or make_capabilities()

    def identity(self) -> VlmModelIdentity:
        return self._identity

    def capabilities(self) -> VlmCapabilities:
        return self._capabilities

    def _respond(self, request: VlmRequest, payload: bytes) -> VlmResponse:
        return VlmResponse(
            request_id=request.request_id,
            reported_model=self._identity,
            payload=payload,
        )


class ScriptedVlmProvider(_FakeBase):
    """Returns scripted outcomes in call order: payload bytes or an error code."""

    def __init__(
        self,
        outcomes: Sequence[bytes | VlmErrorCode],
        *,
        identity: VlmModelIdentity | None = None,
        capabilities: VlmCapabilities | None = None,
    ) -> None:
        super().__init__(identity, capabilities)
        self._outcomes = list(outcomes)
        self.calls = 0

    def infer(
        self,
        request: VlmRequest,
        *,
        deadline_seconds: float,
        cancellation: VlmCancellation,
    ) -> VlmResponse:
        del deadline_seconds
        if cancellation.is_cancelled():
            raise VlmProviderError(VlmErrorCode.CANCELLED)
        if self.calls >= len(self._outcomes):
            raise VlmProviderError(VlmErrorCode.UNAVAILABLE)
        outcome = self._outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, VlmErrorCode):
            raise VlmProviderError(outcome)
        return self._respond(request, outcome)


class ReplayVlmProvider(_FakeBase):
    """Returns the recorded payload for a request ID; identical on every call."""

    def __init__(
        self,
        payloads: Mapping[str, bytes],
        *,
        identity: VlmModelIdentity | None = None,
        capabilities: VlmCapabilities | None = None,
    ) -> None:
        super().__init__(identity, capabilities)
        self._payloads = dict(payloads)

    def infer(
        self,
        request: VlmRequest,
        *,
        deadline_seconds: float,
        cancellation: VlmCancellation,
    ) -> VlmResponse:
        del deadline_seconds
        if cancellation.is_cancelled():
            raise VlmProviderError(VlmErrorCode.CANCELLED)
        payload = self._payloads.get(request.request_id)
        if payload is None:
            raise VlmProviderError(VlmErrorCode.REQUEST_REJECTED)
        return self._respond(request, payload)


class FailingVlmProvider(_FakeBase):
    """Always raises ``VlmProviderError`` with one fixed code."""

    def __init__(
        self,
        code: VlmErrorCode,
        *,
        identity: VlmModelIdentity | None = None,
        capabilities: VlmCapabilities | None = None,
    ) -> None:
        super().__init__(identity, capabilities)
        self.code = code
        self.calls = 0

    def infer(
        self,
        request: VlmRequest,
        *,
        deadline_seconds: float,
        cancellation: VlmCancellation,
    ) -> VlmResponse:
        del request, deadline_seconds, cancellation
        self.calls += 1
        raise VlmProviderError(self.code)


class SpyVlmProvider:
    """Records every call, then delegates to another provider."""

    def __init__(self, inner: _FakeBase) -> None:
        self._inner = inner
        self.recorded: list[RecordedCall] = []

    def identity(self) -> VlmModelIdentity:
        return self._inner.identity()

    def capabilities(self) -> VlmCapabilities:
        return self._inner.capabilities()

    def infer(
        self,
        request: VlmRequest,
        *,
        deadline_seconds: float,
        cancellation: VlmCancellation,
    ) -> VlmResponse:
        self.recorded.append(RecordedCall(request, deadline_seconds, cancellation))
        return self._inner.infer(
            request, deadline_seconds=deadline_seconds, cancellation=cancellation
        )
