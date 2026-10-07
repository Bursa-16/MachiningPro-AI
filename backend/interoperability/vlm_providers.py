"""Inert Phase 1D VLM providers: a disabled provider and a deterministic mock.

Neither provider performs inference, network access, filesystem access or
random generation. They exist so the explicit Phase 1D orchestration can be
exercised and so a "no AI" configuration has a concrete, fail-closed
implementation of ``VlmProvider``. Real local and remote adapters are later
slices and are deliberately absent here.
"""

from __future__ import annotations

from collections.abc import Sequence

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

_DEFAULT_MAX_IMAGE_BYTES = 4 * 1024 * 1024
_DEFAULT_MAX_IMAGE_PIXELS = 4_194_304


def _default_capabilities() -> VlmCapabilities:
    return VlmCapabilities(
        task_kinds=tuple(VlmTaskKind),
        max_image_bytes=_DEFAULT_MAX_IMAGE_BYTES,
        max_image_pixels=_DEFAULT_MAX_IMAGE_PIXELS,
        structured_output=True,
    )


class DisabledVlmProvider:
    """Always refuses with ``DISABLED``. Never produces a response."""

    _IDENTITY = VlmModelIdentity(
        provider_id="machiningpro.disabled",
        model_id="disabled",
        model_version="1",
        locality=VlmLocality.LOCAL,
    )

    def identity(self) -> VlmModelIdentity:
        return self._IDENTITY

    def capabilities(self) -> VlmCapabilities:
        return _default_capabilities()

    def infer(
        self,
        request: VlmRequest,
        *,
        deadline_seconds: float,
        cancellation: VlmCancellation,
    ) -> VlmResponse:
        del request, deadline_seconds, cancellation
        raise VlmProviderError(VlmErrorCode.DISABLED)


class MockVlmProvider:
    """Returns fixed, pre-configured outcomes in call order.

    Each outcome is either payload bytes or a ``VlmErrorCode`` to raise. When
    the script is exhausted the provider raises ``UNAVAILABLE``. It is local
    only: a REMOTE identity is rejected at construction.
    """

    _DEFAULT_IDENTITY = VlmModelIdentity(
        provider_id="machiningpro.mock",
        model_id="mock-vlm",
        model_version="1",
        locality=VlmLocality.LOCAL,
    )

    def __init__(
        self,
        outcomes: Sequence[bytes | VlmErrorCode] = (),
        *,
        identity: VlmModelIdentity | None = None,
        capabilities: VlmCapabilities | None = None,
    ) -> None:
        resolved = identity or self._DEFAULT_IDENTITY
        if not isinstance(resolved, VlmModelIdentity):
            raise TypeError("MockVlmProvider.identity must be VlmModelIdentity")
        if resolved.locality is not VlmLocality.LOCAL:
            raise ValueError("MockVlmProvider must be LOCAL")
        resolved_capabilities = capabilities or _default_capabilities()
        if not isinstance(resolved_capabilities, VlmCapabilities):
            raise TypeError("MockVlmProvider.capabilities must be VlmCapabilities")
        script = tuple(outcomes)
        for outcome in script:
            if not isinstance(outcome, (bytes, VlmErrorCode)):
                raise TypeError("MockVlmProvider outcomes must be bytes or VlmErrorCode")
        self._identity = resolved
        self._capabilities = resolved_capabilities
        self._outcomes = script
        self._calls = 0

    @property
    def call_count(self) -> int:
        return self._calls

    def identity(self) -> VlmModelIdentity:
        return self._identity

    def capabilities(self) -> VlmCapabilities:
        return self._capabilities

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
        if self._calls >= len(self._outcomes):
            raise VlmProviderError(VlmErrorCode.UNAVAILABLE)
        outcome = self._outcomes[self._calls]
        self._calls += 1
        if isinstance(outcome, VlmErrorCode):
            raise VlmProviderError(outcome)
        return VlmResponse(
            request_id=request.request_id,
            reported_model=self._identity,
            payload=outcome,
        )


__all__ = ["DisabledVlmProvider", "MockVlmProvider"]
