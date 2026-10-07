"""Explicit Phase 1D orchestration entry point (slice R3A).

``AiAssistedDrawingExtractor`` is the only place that runs a ``VlmProvider``.
It takes an already-produced deterministic ``DrawingIngestionResult`` and
returns it unchanged inside a ``DrawingAssistedIngestionResult``; no parser
imports or calls it. Authority stays ADVISORY, there is no promotion path and
deterministic evidence is never altered.

R3A scope: explicit gating, bounded execution (attempts, deadline, backoff,
cancellation), fail-closed handling and constant diagnostic codes.

R3B scope: when the caller supplies the ``regions`` that its requests were cut
from, each response is parsed by ``parse_vlm_response`` into advisory evidence.
Any rejected response fails the whole report with no evidence. Without
``regions`` a response is validated for identity and size and then discarded.
With ``reconcile=True`` the report also carries the advisory findings produced
by ``reconcile_advisory_evidence`` (R3C); the comparison is report-only and the
deterministic result is never touched. Request preparation is a later slice.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace

from backend.interoperability.drawing import (
    DrawingExtractionAuthority,
    DrawingIngestionResult,
    DrawingIngestionStatus,
)
from backend.interoperability.vlm_drawing import (
    DrawingAdvisoryReport,
    DrawingAssistedIngestionResult,
    DrawingVlmAssistConfig,
    DrawingVlmEvidence,
    DrawingVlmRegion,
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
from backend.interoperability.vlm_reconciliation import reconcile_advisory_evidence
from backend.interoperability.vlm_response import VlmResponseError, parse_vlm_response

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
        regions: Mapping[str, DrawingVlmRegion] | None = None,
        reconcile: bool = False,
    ) -> DrawingAssistedIngestionResult:
        if not isinstance(base_result, DrawingIngestionResult):
            raise TypeError("base_result must be DrawingIngestionResult")
        if not isinstance(config, DrawingVlmAssistConfig):
            raise TypeError("config must be DrawingVlmAssistConfig")
        prepared = tuple(requests)
        if any(not isinstance(request, VlmRequest) for request in prepared):
            raise TypeError("requests must contain VlmRequest values")
        if regions is not None:
            for request in prepared:
                if not isinstance(regions.get(request.request_id), DrawingVlmRegion):
                    raise ValueError("regions must map every request_id to a DrawingVlmRegion")
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
            evidence: tuple[DrawingVlmEvidence, ...] = (),
            used_regions: tuple[DrawingVlmRegion, ...] = (),
        ) -> DrawingAssistedIngestionResult:
            report = DrawingAdvisoryReport(
                status=status,
                prompt_contract_version=prompt_version,
                model=identity,
                config_fingerprint=config_fingerprint,
                base_result_fingerprint=base_fingerprint,
                diagnostics=diagnostics,
                request_count=calls,
                regions=used_regions,
                evidence=evidence,
            )
            if reconcile and report.evidence:
                findings = tuple(
                    item.finding
                    for item in reconcile_advisory_evidence(base_result, report)
                    if item.finding is not None
                )
                report = replace(report, findings=findings)
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
        collected: list[DrawingVlmEvidence] = []
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
                if regions is not None:
                    try:
                        collected.extend(
                            parse_vlm_response(
                                response, request, regions[request.request_id], limits=limits
                            )
                        )
                    except VlmResponseError as error:
                        return finish(failed, (f"VLM_RESPONSE_{error.code.value}",), calls)
                    if len(collected) > limits.evidence_items_total:
                        return finish(failed, ("VLM_EVIDENCE_LIMIT",), calls)
                break
        if regions is None:
            return finish(
                DrawingIngestionStatus.INSUFFICIENT_DATA, ("VLM_RESPONSES_NOT_PARSED",), calls
            )
        used: dict[str, DrawingVlmRegion] = {}
        for request in prepared:
            region = regions[request.request_id]
            if used.setdefault(region.region_id, region) != region:
                raise ValueError("distinct regions must not share a region_id")
        if not collected:
            return finish(
                DrawingIngestionStatus.INSUFFICIENT_DATA,
                ("VLM_NO_CANDIDATES",),
                calls,
                used_regions=tuple(used.values()),
            )
        return finish(
            DrawingIngestionStatus.VALID,
            (),
            calls,
            evidence=tuple(collected),
            used_regions=tuple(used.values()),
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
