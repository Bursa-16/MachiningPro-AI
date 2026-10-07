"""Explicit Phase 1D orchestration entry point (slice R3A).

``AiAssistedDrawingExtractor`` is the only place that runs a ``VlmProvider``.
It takes an already-produced deterministic ``DrawingIngestionResult`` and
returns it unchanged inside a ``DrawingAssistedIngestionResult``; no parser
imports or calls it. Authority stays ADVISORY, there is no promotion path and
deterministic evidence is never altered.

R3A scope: explicit gating, bounded execution (attempts, deadline, backoff,
cancellation), fail-closed handling and constant diagnostic codes. Response
parsing, evidence creation, reconciliation and request preparation are later
slices, so a provider response is validated for identity and size and then
discarded; the report carries no evidence and no findings.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Sequence

from backend.interoperability.drawing import (
    DrawingExtractionAuthority,
    DrawingIngestionResult,
    DrawingIngestionStatus,
)
from backend.interoperability.vlm_drawing import (
    DrawingAdvisoryReport,
    DrawingAssistedIngestionResult,
    DrawingVlmAssistConfig,
)
from backend.interoperability.vlm_provider import (
    VlmCancellation,
    VlmErrorCode,
    VlmLocality,
    VlmProvider,
    VlmProviderError,
    VlmRequest,
    VlmResponse,
    VlmRetryPolicy,
)

AI_DEFAULT_AUTHORITY = DrawingExtractionAuthority.ADVISORY
AUTO_PROMOTION_ALLOWED = False
DETERMINISTIC_EVIDENCE_OVERWRITE_ALLOWED = False

_NO_PROMPT_VERSION = "none"
_UNSUPPORTED_CODES = frozenset({VlmErrorCode.DISABLED, VlmErrorCode.UNSUPPORTED})


class AiAssistedDrawingExtractor:
    """Runs one explicitly supplied provider over caller-prepared requests."""

    def __init__(
        self,
        provider: VlmProvider,
        *,
        retry_policy: VlmRetryPolicy | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not isinstance(provider, VlmProvider):
            raise TypeError("provider must implement VlmProvider")
        if retry_policy is not None and not isinstance(retry_policy, VlmRetryPolicy):
            raise TypeError("retry_policy must be VlmRetryPolicy or None")
        self._provider = provider
        self._retry_policy = retry_policy or VlmRetryPolicy()
        self._monotonic = monotonic
        self._sleep = sleep

    def extract_candidates(
        self,
        base_result: DrawingIngestionResult,
        requests: Sequence[VlmRequest],
        *,
        config: DrawingVlmAssistConfig,
    ) -> DrawingAssistedIngestionResult:
        if not isinstance(base_result, DrawingIngestionResult):
            raise TypeError("base_result must be DrawingIngestionResult")
        if not isinstance(config, DrawingVlmAssistConfig):
            raise TypeError("config must be DrawingVlmAssistConfig")
        prepared = tuple(requests)
        if any(not isinstance(request, VlmRequest) for request in prepared):
            raise TypeError("requests must contain VlmRequest values")
        if not config.enabled:
            return DrawingAssistedIngestionResult(result=base_result)

        versions = {request.prompt_contract_version for request in prepared}
        if len(versions) > 1:
            raise ValueError("requests must share one prompt contract version")
        prompt_version = next(iter(versions)) if versions else _NO_PROMPT_VERSION
        identity = self._provider.identity()
        config_fingerprint = _fingerprint(config)
        base_fingerprint = _fingerprint(base_result)

        def finish(
            status: DrawingIngestionStatus,
            diagnostics: tuple[str, ...],
            calls: int,
        ) -> DrawingAssistedIngestionResult:
            report = DrawingAdvisoryReport(
                status=status,
                prompt_contract_version=prompt_version,
                model=identity,
                config_fingerprint=config_fingerprint,
                base_result_fingerprint=base_fingerprint,
                diagnostics=diagnostics,
                request_count=calls,
            )
            return DrawingAssistedIngestionResult(result=base_result, advisory=report)

        failed = DrawingIngestionStatus.FAILED
        unsupported = DrawingIngestionStatus.UNSUPPORTED
        limits = config.limits

        # R3A has no remote capability: a REMOTE provider is refused before any call.
        if identity.locality is not VlmLocality.LOCAL:
            return finish(unsupported, ("VLM_REMOTE_NOT_SUPPORTED",), 0)
        if config.allowed_provider_ids and identity.provider_id not in config.allowed_provider_ids:
            return finish(unsupported, ("VLM_PROVIDER_NOT_ALLOWED",), 0)
        if not prepared:
            return finish(DrawingIngestionStatus.INSUFFICIENT_DATA, ("VLM_NO_REQUESTS",), 0)
        if len(prepared) > limits.requests_per_document:
            return finish(failed, ("VLM_REQUEST_LIMIT",), 0)

        capabilities = self._provider.capabilities()
        for request in prepared:
            if request.model != identity:
                return finish(failed, ("VLM_MODEL_MISMATCH",), 0)
            if request.task_kind not in capabilities.task_kinds:
                return finish(unsupported, ("VLM_TASK_UNSUPPORTED",), 0)
            pixels = request.image_width_px * request.image_height_px
            if (
                len(request.image_png) > min(capabilities.max_image_bytes, limits.crop_png_bytes)
                or pixels > min(capabilities.max_image_pixels, limits.crop_pixels)
                or max(request.image_width_px, request.image_height_px)
                > limits.crop_longest_edge_px
            ):
                return finish(failed, ("VLM_OVERSIZED_INPUT",), 0)

        max_attempts = min(self._retry_policy.max_attempts, limits.attempts_per_request)
        cancellation = VlmCancellation()
        started = self._monotonic()
        calls = 0
        for request in prepared:
            attempt = 0
            while True:
                attempt += 1
                remaining = limits.assist_total_budget_seconds - (self._monotonic() - started)
                if remaining <= 0:
                    cancellation.cancel()
                    return finish(failed, ("VLM_BUDGET_EXHAUSTED",), calls)
                deadline = float(min(limits.request_timeout_seconds, remaining))
                calls += 1
                try:
                    response = self._provider.infer(
                        request, deadline_seconds=deadline, cancellation=cancellation
                    )
                except VlmProviderError as error:
                    code = error.code
                    if code in self._retry_policy.retry_on:
                        if attempt >= max_attempts:
                            return finish(
                                failed, (f"VLM_{code.value}", "VLM_RETRY_EXHAUSTED"), calls
                            )
                        wait = float(self._retry_policy.backoff_seconds[attempt - 1])
                        if wait >= limits.assist_total_budget_seconds - (
                            self._monotonic() - started
                        ):
                            cancellation.cancel()
                            return finish(failed, ("VLM_BUDGET_EXHAUSTED",), calls)
                        self._sleep(wait)
                        continue
                    status = unsupported if code in _UNSUPPORTED_CODES else failed
                    return finish(status, (f"VLM_{code.value}",), calls)
                except Exception:
                    return finish(failed, ("VLM_PROVIDER_FAILURE",), calls)
                problem = _response_problem(response, request, identity, limits.response_bytes)
                if problem is not None:
                    return finish(failed, (problem,), calls)
                break
        return finish(
            DrawingIngestionStatus.INSUFFICIENT_DATA, ("VLM_RESPONSES_NOT_PARSED",), calls
        )


def _response_problem(
    response: object,
    request: VlmRequest,
    identity: object,
    response_limit: int,
) -> str | None:
    if not isinstance(response, VlmResponse):
        return "VLM_RESPONSE_INVALID"
    if response.request_id != request.request_id or response.reported_model != identity:
        return "VLM_RESPONSE_MISMATCH"
    if not response.payload:
        return "VLM_RESPONSE_EMPTY"
    if len(response.payload) > min(request.max_response_bytes, response_limit):
        return "VLM_RESPONSE_TOO_LARGE"
    return None


def _fingerprint(value: object) -> str:
    return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()


__all__ = [
    "AI_DEFAULT_AUTHORITY",
    "AUTO_PROMOTION_ALLOWED",
    "AiAssistedDrawingExtractor",
    "DETERMINISTIC_EVIDENCE_OVERWRITE_ALLOWED",
]
