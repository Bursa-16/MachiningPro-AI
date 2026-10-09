"""Live drawing-analysis API for the Human Confirmation UI (HUMAN_CONFIRMATION_UI_02).

Plumbing only. Everything that decides anything is existing committed code:

    upload -> PdfDrawingParser (deterministic ingestion)
    analysis job -> R3D ``prepare_vlm_requests`` -> ``OllamaVlmProvider`` (granite3.2-vision:2b,
    loopback only) -> R3B v2 validation inside ``AiAssistedDrawingExtractor`` -> advisory evidence

A local CPU inference takes minutes, so analysis is an explicit job: ``POST`` returns a job
id at once and the browser polls ``GET``. Jobs run in-process on a background thread, one
inference at a time. This is a bounded DEMO mechanism: state lives in memory, is lost on
restart and is not a distributed worker.

Boundaries kept here:
* AI authority is ADVISORY; nothing is promoted and deterministic evidence is never written.
* Only R3B-validated evidence with ``box_basis=REGION_EXTENT`` is ever exposed; raw model
  output, model boxes, local paths, exception text and the Ollama endpoint never leave the
  server.
* No retry (``max_attempts=1``), no fallback provider or model, no cloud call.
* Review decisions are kept beside, never inside, the AI evidence, with history appended.
"""

from __future__ import annotations

import re
import secrets
import threading
import unicodedata
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum, unique
from io import BytesIO
from typing import Any, Literal

import pdfplumber
from fastapi import APIRouter, Depends, File, Header, HTTPException, Response, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from backend.api.auth import verify_token
from backend.interoperability.drawing import (
    DrawingBoundingBox,
    DrawingIngestionResult,
    DrawingIngestionStatus,
    DrawingRasterSource,
)
from backend.interoperability.pdf_drawing import PdfDrawingParser
from backend.interoperability.raster_drawing import (
    RasterDocumentSnapshot,
    RasterImageSnapshot,
    inspect_raster_pdf,
)
from backend.interoperability.vlm_assist import (
    AI_DEFAULT_AUTHORITY,
    AiAssistedDrawingExtractor,
)
from backend.interoperability.vlm_drawing import (
    DrawingVlmAssistConfig,
    DrawingVlmBoxBasis,
    DrawingVlmEvidence,
    DrawingVlmRegion,
    DrawingVlmRegionKind,
    VlmLimits,
)
from backend.interoperability.vlm_ollama import OllamaVlmConfig, OllamaVlmProvider
from backend.interoperability.vlm_provider import (
    VlmCancellation,
    VlmCapabilities,
    VlmModelIdentity,
    VlmProvider,
    VlmRequest,
    VlmResponse,
    VlmRetryPolicy,
)
from backend.interoperability.vlm_request import (
    VlmPreparationConfig,
    VlmPreparationError,
    extractor_inputs,
    prepare_vlm_requests,
)
from backend.interoperability.vlm_response import VLM_TEXT_ONLY_RESPONSE_SCHEMA_VERSION

PROMPT_CONTRACT_VERSION = "machiningpro.drawing-vlm.v1"
# A CPU run of granite3.2-vision:2b took about 160 s; allow a wide margin, never unbounded.
REQUEST_TIMEOUT_SECONDS = 600
ASSIST_TOTAL_BUDGET_SECONDS = 900

MAX_UPLOAD_BYTES = 16 * 1024 * 1024
MAX_DRAWINGS = 20
MAX_JOBS = 100
MAX_REVIEW_VALUE_CHARS = 256
PREVIEW_MAX_WIDTH_PX = 1600

_ID = re.compile(r"[0-9a-f]{32}")
_EVIDENCE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


@unique
class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    PREPARING = "PREPARING"
    ANALYZING = "ANALYZING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


ACTIVE_STATUSES = frozenset(
    {JobStatus.QUEUED, JobStatus.PREPARING, JobStatus.ANALYZING, JobStatus.VALIDATING}
)


@unique
class ErrorCode(StrEnum):
    """Structured, UI-safe failure codes. No stack traces or vendor text are ever returned."""

    AI_DISABLED = "AI_DISABLED"
    OLLAMA_UNAVAILABLE = "OLLAMA_UNAVAILABLE"
    MODEL_NOT_AVAILABLE = "MODEL_NOT_AVAILABLE"
    REQUEST_TIMEOUT = "REQUEST_TIMEOUT"
    R3B_VALIDATION_FAILURE = "R3B_VALIDATION_FAILURE"
    INVALID_DRAWING = "INVALID_DRAWING"
    INVALID_REGION = "INVALID_REGION"
    JOB_INTERNAL_ERROR = "JOB_INTERNAL_ERROR"


_SAFE_MESSAGE = {
    ErrorCode.AI_DISABLED: "AI analysis is disabled.",
    ErrorCode.OLLAMA_UNAVAILABLE: "The local AI service is unavailable.",
    ErrorCode.MODEL_NOT_AVAILABLE: "The AI model is unavailable.",
    ErrorCode.REQUEST_TIMEOUT: "AI analysis timed out.",
    ErrorCode.R3B_VALIDATION_FAILURE: "The AI response failed validation and was discarded.",
    ErrorCode.INVALID_DRAWING: "The drawing could not be used.",
    ErrorCode.INVALID_REGION: "The selected region could not be analysed.",
    ErrorCode.JOB_INTERNAL_ERROR: "AI analysis could not be completed.",
}

_DIAGNOSTIC_TO_ERROR = {
    "VLM_DISABLED": ErrorCode.AI_DISABLED,
    "VLM_UNSUPPORTED": ErrorCode.AI_DISABLED,
    "VLM_REMOTE_NOT_SUPPORTED": ErrorCode.AI_DISABLED,
    "VLM_UNAVAILABLE": ErrorCode.OLLAMA_UNAVAILABLE,
    "VLM_TRANSIENT": ErrorCode.OLLAMA_UNAVAILABLE,
    "VLM_RATE_LIMITED": ErrorCode.OLLAMA_UNAVAILABLE,
    "VLM_TIMEOUT": ErrorCode.REQUEST_TIMEOUT,
    "VLM_BUDGET_EXHAUSTED": ErrorCode.REQUEST_TIMEOUT,
    # A missing Ollama model answers HTTP 404, which the provider reports as REQUEST_REJECTED.
    "VLM_REQUEST_REJECTED": ErrorCode.MODEL_NOT_AVAILABLE,
    "VLM_MODEL_MISMATCH": ErrorCode.R3B_VALIDATION_FAILURE,
    "VLM_OVERSIZED_INPUT": ErrorCode.INVALID_REGION,
}


def classify_diagnostics(diagnostics: tuple[str, ...]) -> ErrorCode:
    first = diagnostics[0] if diagnostics else ""
    if first.startswith("VLM_RESPONSE_"):
        return ErrorCode.R3B_VALIDATION_FAILURE
    return _DIAGNOSTIC_TO_ERROR.get(first, ErrorCode.JOB_INTERNAL_ERROR)


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class ApiFailure(Exception):
    """Internal: becomes an HTTP error with a structured ``error_code`` body."""

    def __init__(self, status: int, code: str, **extra: Any) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.extra = extra

    def http(self) -> HTTPException:
        return HTTPException(self.status, detail={"error_code": self.code, **self.extra})


# ---------------------------------------------------------------------------
# Provider wiring (committed provider, committed configuration mechanism)
# ---------------------------------------------------------------------------


def default_provider_factory() -> VlmProvider:
    """Ollama only, explicitly selected by ``MACHININGPRO_AI_PROVIDER=ollama``.

    Raises ``OllamaConfigurationError`` when Ollama is not selected or the endpoint is not
    loopback. The model comes from ``MACHININGPRO_OLLAMA_MODEL`` (default Granite) and the
    CPU profile (num_gpu=0, num_ctx=8192, temperature=0, stream=false) is fixed in the
    provider. There is no API key and no other provider.
    """
    config = OllamaVlmConfig.from_environment()
    return OllamaVlmProvider(replace(config, timeout_seconds=float(REQUEST_TIMEOUT_SECONDS)))


class _PhaseReportingProvider:
    """Instrumentation only: reports real phases around the delegated ``infer`` call."""

    def __init__(
        self,
        inner: VlmProvider,
        on_start: Callable[[], None],
        on_finish: Callable[[], None],
    ) -> None:
        self._inner = inner
        self._on_start = on_start
        self._on_finish = on_finish

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
        self._on_start()
        response = self._inner.infer(
            request, deadline_seconds=deadline_seconds, cancellation=cancellation
        )
        self._on_finish()
        return response


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


@dataclass
class _Drawing:
    drawing_id: str
    source_id: str
    content: bytes
    base_result: DrawingIngestionResult
    snapshot: RasterDocumentSnapshot | None


@dataclass
class _Job:
    job_id: str
    drawing_id: str
    page_number: int
    image_index: int
    crop_px: tuple[int, int, int, int]
    requested_by: str | None
    created_at: str
    provider: VlmProvider = field(repr=False)
    status: JobStatus = JobStatus.QUEUED
    started_at: str | None = None
    completed_at: str | None = None
    error_code: ErrorCode | None = None
    findings: list[dict[str, Any]] = field(default_factory=list)
    region: dict[str, Any] | None = None
    reviews: dict[str, dict[str, Any]] = field(default_factory=dict)


Runner = Callable[[Callable[[], None]], None]


def thread_runner(task: Callable[[], None]) -> None:
    threading.Thread(target=task, name="drawing-analysis", daemon=True).start()


def _decimal_float(value: Decimal) -> float:
    return float(value)


def _box_json(box: DrawingBoundingBox) -> dict[str, Any]:
    return {
        "x0": _decimal_float(box.x0),
        "top": _decimal_float(box.top),
        "x1": _decimal_float(box.x1),
        "bottom": _decimal_float(box.bottom),
        "unit": box.unit,
    }


class AnalysisService:
    """In-process demo store and job runner. Not a distributed worker."""

    def __init__(
        self,
        *,
        provider_factory: Callable[[], VlmProvider] = default_provider_factory,
        runner: Runner = thread_runner,
        clock: Callable[[], str] = now_iso,
    ) -> None:
        self._provider_factory = provider_factory
        self._runner = runner
        self._clock = clock
        self._lock = threading.RLock()
        self._model_lock = threading.Lock()  # one local inference at a time
        self._drawings: OrderedDict[str, _Drawing] = OrderedDict()
        self._jobs: OrderedDict[str, _Job] = OrderedDict()

    # -- drawings ----------------------------------------------------------------------

    def upload(self, content: bytes) -> dict[str, Any]:
        if len(content) > MAX_UPLOAD_BYTES:
            raise ApiFailure(413, ErrorCode.INVALID_DRAWING.value)
        if not content or content[:1024].find(b"%PDF-") < 0:
            raise ApiFailure(422, ErrorCode.INVALID_DRAWING.value)
        drawing_id = secrets.token_hex(16)
        source_id = f"upload::{drawing_id}.pdf"
        raster = inspect_raster_pdf(content, source_id)
        try:
            base = PdfDrawingParser().parse(source_id, f"{drawing_id}.pdf", content)
        except Exception:  # noqa: BLE001 - fail closed; no parser text reaches the client
            raise ApiFailure(422, ErrorCode.INVALID_DRAWING.value) from None
        snapshot = raster.snapshot
        has_images = snapshot is not None and any(page.images for page in snapshot.pages)
        if base.diagnostics.status in (
            DrawingIngestionStatus.FAILED,
            DrawingIngestionStatus.UNSUPPORTED,
        ) and not has_images:
            raise ApiFailure(422, ErrorCode.INVALID_DRAWING.value)
        with self._lock:
            self._drawings[drawing_id] = _Drawing(drawing_id, source_id, content, base, snapshot)
            self._evict()
        return self.drawing_summary(drawing_id)

    def _evict(self) -> None:
        while len(self._drawings) > MAX_DRAWINGS:
            for old_id in list(self._drawings):
                if not any(
                    job.drawing_id == old_id and job.status in ACTIVE_STATUSES
                    for job in self._jobs.values()
                ):
                    del self._drawings[old_id]
                    for job_id in [j for j, v in self._jobs.items() if v.drawing_id == old_id]:
                        del self._jobs[job_id]
                    break
            else:
                break
        while len(self._jobs) > MAX_JOBS:
            for job_id, job in self._jobs.items():
                if job.status not in ACTIVE_STATUSES:
                    del self._jobs[job_id]
                    break
            else:
                break

    def _drawing(self, drawing_id: str) -> _Drawing:
        drawing = self._drawings.get(drawing_id) if _ID.fullmatch(drawing_id or "") else None
        if drawing is None:
            raise ApiFailure(404, "NOT_FOUND")
        return drawing

    def drawing_summary(self, drawing_id: str) -> dict[str, Any]:
        with self._lock:
            drawing = self._drawing(drawing_id)
            result = drawing.base_result
            document = result.document
            items = []
            for dimension in document.all_dimensions if document is not None else ():
                location = dimension.source_location
                text = (location.original_text if location else None) or (
                    f"{dimension.nominal_value} {dimension.unit}"
                )
                items.append(
                    {
                        "id": dimension.dimension_id,
                        "label": dimension.dimension_type.value,
                        "value": text,
                        "source": location.adapter_id if location else "deterministic",
                    }
                )
            pages = []
            if drawing.snapshot is not None:
                for page in drawing.snapshot.pages:
                    pages.append(
                        {
                            "page_number": page.page_number,
                            "width_pt": float(page.width_pt),
                            "height_pt": float(page.height_pt),
                            "images": [
                                {"index": index, "width_px": image.width, "height_px": image.height}
                                for index, image in enumerate(page.images, start=1)
                            ],
                        }
                    )
            return {
                "drawing_id": drawing.drawing_id,
                "deterministic": {
                    "status": result.diagnostics.status.value,
                    "diagnostics": list(result.diagnostics.warnings)
                    + list(result.diagnostics.errors),
                    "items": items,
                },
                "pages": pages,
            }

    def preview_png(self, drawing_id: str, page_number: int) -> bytes:
        with self._lock:
            drawing = self._drawing(drawing_id)
        try:
            with pdfplumber.open(BytesIO(drawing.content)) as document:
                if not 1 <= page_number <= len(document.pages):
                    raise ApiFailure(404, "NOT_FOUND")
                page = document.pages[page_number - 1]
                dpi = max(36.0, min(144.0, PREVIEW_MAX_WIDTH_PX / float(page.width) * 72.0))
                image = page.to_image(resolution=dpi).original
                buffer = BytesIO()
                image.convert("RGB").save(buffer, format="PNG")
                return buffer.getvalue()
        except ApiFailure:
            raise
        except Exception:  # noqa: BLE001
            raise ApiFailure(422, "PREVIEW_UNAVAILABLE") from None

    # -- jobs --------------------------------------------------------------------------

    def start_analysis(
        self,
        drawing_id: str,
        *,
        ai_enabled: bool,
        page_number: int,
        image_index: int,
        crop_px: list[int] | None,
        requested_by: str | None,
    ) -> tuple[dict[str, Any], bool]:
        if ai_enabled is not True:
            raise ApiFailure(400, "AI_NOT_REQUESTED")
        with self._lock:
            drawing = self._drawing(drawing_id)
            for job in self._jobs.values():  # duplicate start returns the active job
                if job.drawing_id == drawing_id and job.status in ACTIVE_STATUSES:
                    return self._view(job), True
            image = self._image(drawing, page_number, image_index)
            crop = self._crop(image, crop_px)
            try:
                provider = self._provider_factory()
            except Exception:  # noqa: BLE001 - not selected / not loopback / misconfigured
                raise ApiFailure(503, ErrorCode.AI_DISABLED.value) from None
            job = _Job(
                job_id=secrets.token_hex(16),
                drawing_id=drawing_id,
                page_number=page_number,
                image_index=image_index,
                crop_px=crop,
                requested_by=requested_by,
                created_at=self._clock(),
                provider=provider,
            )
            self._jobs[job.job_id] = job
            self._evict()
            view = self._view(job)
        self._runner(lambda: self._run(job.job_id))
        return view, False

    @staticmethod
    def _image(drawing: _Drawing, page_number: int, image_index: int) -> RasterImageSnapshot:
        snapshot = drawing.snapshot
        if snapshot is None or not 1 <= page_number <= len(snapshot.pages):
            raise ApiFailure(422, ErrorCode.INVALID_REGION.value)
        images = snapshot.pages[page_number - 1].images
        if not 1 <= image_index <= len(images):
            raise ApiFailure(422, ErrorCode.INVALID_REGION.value)
        return images[image_index - 1]

    @staticmethod
    def _crop(image: RasterImageSnapshot, crop_px: list[int] | None) -> tuple[int, int, int, int]:
        if crop_px is None:
            return (0, 0, image.width, image.height)
        if len(crop_px) != 4 or any(isinstance(v, bool) or not isinstance(v, int) for v in crop_px):
            raise ApiFailure(422, ErrorCode.INVALID_REGION.value)
        x0, y0, x1, y1 = crop_px
        if not (0 <= x0 < x1 <= image.width and 0 <= y0 < y1 <= image.height):
            raise ApiFailure(422, ErrorCode.INVALID_REGION.value)
        return (x0, y0, x1, y1)

    def job_view(self, drawing_id: str, job_id: str) -> dict[str, Any]:
        with self._lock:
            self._drawing(drawing_id)
            job = self._jobs.get(job_id) if _ID.fullmatch(job_id or "") else None
            if job is None or job.drawing_id != drawing_id:
                raise ApiFailure(404, "NOT_FOUND")
            return self._view(job)

    def _view(self, job: _Job) -> dict[str, Any]:
        completed = job.status is JobStatus.COMPLETED
        return {
            "job_id": job.job_id,
            "drawing_id": job.drawing_id,
            "status": job.status.value,
            "progress_phase": job.status.value if job.status in ACTIVE_STATUSES else None,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "error_code": job.error_code.value if job.error_code else None,
            "error_message": _SAFE_MESSAGE[job.error_code] if job.error_code else None,
            "finding_count": len(job.findings) if completed else None,
            "region": job.region if completed else None,
            "findings": [dict(f) for f in job.findings] if completed else [],
            "reviews": {k: _copy_record(v) for k, v in job.reviews.items()} if completed else {},
        }

    def _set(self, job: _Job, status: JobStatus) -> None:
        with self._lock:
            if job.status in ACTIVE_STATUSES:
                job.status = status

    def _fail(self, job: _Job, code: ErrorCode) -> None:
        with self._lock:
            job.status = JobStatus.FAILED
            job.error_code = code
            job.findings = []
            job.reviews = {}
            job.completed_at = self._clock()

    def _run(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            drawing = self._drawings.get(job.drawing_id) if job else None
        if job is None or drawing is None:
            return
        with self._model_lock:
            with self._lock:
                job.started_at = self._clock()
            self._set(job, JobStatus.PREPARING)
            try:
                self._execute(job, drawing)
            except ApiFailure as failure:
                self._fail(job, ErrorCode(failure.code))
            except Exception:  # noqa: BLE001 - never leak exception text
                self._fail(job, ErrorCode.JOB_INTERNAL_ERROR)

    def _execute(self, job: _Job, drawing: _Drawing) -> None:
        image = self._image(drawing, job.page_number, job.image_index)
        region = _build_region(image, job.page_number, job.crop_px)
        provider = job.provider
        preparation = VlmPreparationConfig(
            prompt_contract_version=PROMPT_CONTRACT_VERSION, model=provider.identity()
        )
        try:
            prepared = prepare_vlm_requests(
                drawing.base_result, drawing.content, [region], config=preparation
            )
        except VlmPreparationError:
            raise ApiFailure(422, ErrorCode.INVALID_REGION.value) from None
        requests, regions = extractor_inputs(prepared)

        reporting = _PhaseReportingProvider(
            provider,
            on_start=lambda: self._set(job, JobStatus.ANALYZING),
            on_finish=lambda: self._set(job, JobStatus.VALIDATING),
        )
        extractor = AiAssistedDrawingExtractor(
            reporting, retry_policy=VlmRetryPolicy(max_attempts=1, backoff_seconds=())
        )
        assist = DrawingVlmAssistConfig(
            enabled=True,
            limits=VlmLimits(
                request_timeout_seconds=REQUEST_TIMEOUT_SECONDS,
                assist_total_budget_seconds=ASSIST_TOTAL_BUDGET_SECONDS,
            ),
        )
        outcome = extractor.extract_candidates(
            drawing.base_result, list(requests), config=assist, regions=regions, reconcile=True
        )
        advisory = outcome.advisory
        if advisory is None:
            raise ApiFailure(500, ErrorCode.JOB_INTERNAL_ERROR.value)

        if advisory.status is DrawingIngestionStatus.VALID:
            evidence = advisory.evidence
        elif advisory.diagnostics == ("VLM_NO_CANDIDATES",):
            evidence = ()
        else:
            failed = advisory.status in (
                DrawingIngestionStatus.FAILED,
                DrawingIngestionStatus.UNSUPPORTED,
            )
            code = (
                classify_diagnostics(advisory.diagnostics)
                if failed
                else ErrorCode.JOB_INTERNAL_ERROR
            )
            raise ApiFailure(500, code.value)

        # Fail closed: only the text-only contract with deterministic region geometry may reach
        # the UI. A model-supplied pixel box (legacy v1 selection) is discarded unseen.
        if any(item.box_basis is not DrawingVlmBoxBasis.REGION_EXTENT for item in evidence):
            raise ApiFailure(500, ErrorCode.R3B_VALIDATION_FAILURE.value)

        statuses = {
            evidence_id: finding.status.value
            for finding in advisory.findings
            for evidence_id in finding.ai_evidence_ids
        }
        findings = [_finding_json(item, statuses.get(item.evidence_id)) for item in evidence]
        reviews = {
            item["evidence_id"]: {
                "evidence_id": item["evidence_id"],
                "status": "PENDING_REVIEW",
                "original_ai_value": item["original_value"],
                "reviewed_value": None,
                "reviewed_by": None,
                "reviewed_at": None,
                "history": [],
            }
            for item in findings
        }
        with self._lock:
            job.region = {"region_id": region.region_id, **_box_json(region.pdf_box)}
            job.findings = findings
            job.reviews = reviews
            job.status = JobStatus.COMPLETED
            job.completed_at = self._clock()

    # -- review ------------------------------------------------------------------------

    def review(
        self,
        drawing_id: str,
        job_id: str,
        evidence_id: str,
        *,
        action: str,
        value: str | None,
        reviewer: str | None,
    ) -> dict[str, Any]:
        with self._lock:
            self._drawing(drawing_id)
            job = self._jobs.get(job_id) if _ID.fullmatch(job_id or "") else None
            if job is None or job.drawing_id != drawing_id:
                raise ApiFailure(404, "NOT_FOUND")
            if job.status is not JobStatus.COMPLETED:
                raise ApiFailure(409, "JOB_NOT_COMPLETED")
            record = job.reviews.get(evidence_id) if _EVIDENCE_ID.fullmatch(evidence_id) else None
            if record is None:
                raise ApiFailure(404, "NOT_FOUND")
            reviewed_value: str | None = None
            if action == "ACCEPT":
                status = "ACCEPTED"
            elif action == "REJECT":
                status = "REJECTED"
            else:
                status = "EDITED"
                reviewed_value = _validated_edit(value, record["original_ai_value"])
            event = {
                "status": status,
                "reviewed_value": reviewed_value,
                "reviewed_by": reviewer,
                "reviewed_at": self._clock(),
            }
            record["status"] = status
            record["reviewed_value"] = reviewed_value
            record["reviewed_by"] = reviewer
            record["reviewed_at"] = event["reviewed_at"]
            record["history"].append(event)
            return _copy_record(record)


def _copy_record(record: dict[str, Any]) -> dict[str, Any]:
    return {**record, "history": [dict(event) for event in record["history"]]}


def _validated_edit(value: str | None, original: str) -> str:
    if value is None:
        raise ApiFailure(422, "INVALID_REVIEW_VALUE", reason="BLANK")
    text = value.strip()
    if not text:
        raise ApiFailure(422, "INVALID_REVIEW_VALUE", reason="BLANK")
    if len(text) > MAX_REVIEW_VALUE_CHARS:
        raise ApiFailure(422, "INVALID_REVIEW_VALUE", reason="TOO_LONG")
    if any(unicodedata.category(c).startswith("C") for c in text):
        raise ApiFailure(422, "INVALID_REVIEW_VALUE", reason="CONTROL_CHARACTERS")
    if text == original:
        raise ApiFailure(422, "INVALID_REVIEW_VALUE", reason="UNCHANGED")
    return text


def _build_region(
    image: RasterImageSnapshot, page_number: int, crop: tuple[int, int, int, int]
) -> DrawingVlmRegion:
    """A caller-selected region: the pixel crop plus its proportional page-point box."""
    source: DrawingRasterSource = image.raster_source
    area = source.bounding_box
    x0, y0, x1, y1 = crop
    scale_x = (area.x1 - area.x0) / Decimal(image.width)
    scale_y = (area.bottom - area.top) / Decimal(image.height)
    pdf_box = DrawingBoundingBox(
        x0=area.x0 + Decimal(x0) * scale_x,
        top=area.top + Decimal(y0) * scale_y,
        x1=area.x0 + Decimal(x1) * scale_x,
        bottom=area.top + Decimal(y1) * scale_y,
    )
    whole = crop == (0, 0, image.width, image.height)
    return DrawingVlmRegion(
        region_id=f"region-p{page_number}-{x0}-{y0}-{x1}-{y1}",
        kind=DrawingVlmRegionKind.IMAGE_OVERVIEW if whole else DrawingVlmRegionKind.OCR_REVIEW,
        page_number=page_number,
        raster_source=source,
        crop_px=crop,
        pdf_box=pdf_box,
        trigger_evidence_ids=(),
    )


def _finding_json(item: DrawingVlmEvidence, reconciliation: str | None) -> dict[str, Any]:
    box = item.source_location.bounding_box
    return {
        "evidence_id": item.evidence_id,
        "candidate_type": item.evidence_kind.value,
        "original_value": item.raw_candidate,
        "legibility": item.legibility.value,
        "confidence": float(item.reported_confidence)
        if item.reported_confidence is not None
        else None,
        "authority": AI_DEFAULT_AUTHORITY.value,
        "provider_id": item.model.provider_id,
        "model_id": item.model.model_id,
        "model_version": item.model.model_version,
        "region_id": item.region_id,
        "request_id": item.request_id,
        "prompt_contract_version": item.prompt_contract_version,
        "schema_version": VLM_TEXT_ONLY_RESPONSE_SCHEMA_VERSION,
        "box_basis": item.box_basis.value,
        "box": _box_json(box) if box is not None else None,
        "reconciliation": reconciliation,
    }


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

_default_service = AnalysisService()


def get_service() -> AnalysisService:
    return _default_service


def require_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """Bearer token from the existing login; fails closed with 401."""
    scheme, _, token = (authorization or "").partition(" ")
    payload = verify_token(token.strip()) if scheme.lower() == "bearer" and token.strip() else None
    if payload is None:
        raise HTTPException(401, detail={"error_code": "UNAUTHENTICATED"})
    return payload


class AnalysisRequest(BaseModel):
    """Only logical identifiers: no path, URL or file name is accepted."""

    model_config = ConfigDict(extra="forbid")

    ai_enabled: bool
    page_number: int = 1
    image_index: int = 1
    crop_px: list[int] | None = None


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["ACCEPT", "REJECT", "EDIT"]
    value: str | None = None
    reviewer: str | None = None  # accepted but ignored; auth user from JWT is used


router = APIRouter(prefix="/api/drawings", tags=["drawing-analysis"])


def _guard(call: Callable[[], Any]) -> Any:
    try:
        return call()
    except ApiFailure as failure:
        raise failure.http() from None


def _read_limited(upload: UploadFile) -> bytes:
    data = upload.file.read(MAX_UPLOAD_BYTES + 1)
    return data


@router.post("", status_code=201)
def upload_drawing(
    file: UploadFile = File(...),  # noqa: B008
    _user: dict[str, Any] = Depends(require_user),  # noqa: B008
    service: AnalysisService = Depends(get_service),  # noqa: B008
) -> dict[str, Any]:
    return _guard(lambda: service.upload(_read_limited(file)))


@router.get("/{drawing_id}")
def get_drawing(
    drawing_id: str,
    _user: dict[str, Any] = Depends(require_user),  # noqa: B008
    service: AnalysisService = Depends(get_service),  # noqa: B008
) -> dict[str, Any]:
    return _guard(lambda: service.drawing_summary(drawing_id))


@router.get("/{drawing_id}/pages/{page_number}/preview")
def get_preview(
    drawing_id: str,
    page_number: int,
    _user: dict[str, Any] = Depends(require_user),  # noqa: B008
    service: AnalysisService = Depends(get_service),  # noqa: B008
) -> Response:
    png = _guard(lambda: service.preview_png(drawing_id, page_number))
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/{drawing_id}/analysis")
def start_analysis(
    drawing_id: str,
    body: AnalysisRequest,
    user: dict[str, Any] = Depends(require_user),  # noqa: B008
    service: AnalysisService = Depends(get_service),  # noqa: B008
) -> JSONResponse:
    view, reused = _guard(
        lambda: service.start_analysis(
            drawing_id,
            ai_enabled=body.ai_enabled,
            page_number=body.page_number,
            image_index=body.image_index,
            crop_px=body.crop_px,
            requested_by=user.get("sub"),
        )
    )
    return JSONResponse({**view, "reused": reused}, status_code=200 if reused else 202)


@router.get("/{drawing_id}/analysis/{job_id}")
def get_analysis(
    drawing_id: str,
    job_id: str,
    _user: dict[str, Any] = Depends(require_user),  # noqa: B008
    service: AnalysisService = Depends(get_service),  # noqa: B008
) -> dict[str, Any]:
    return _guard(lambda: service.job_view(drawing_id, job_id))


@router.put("/{drawing_id}/analysis/{job_id}/reviews/{evidence_id}")
def put_review(
    drawing_id: str,
    job_id: str,
    evidence_id: str,
    body: ReviewRequest,
    user: dict[str, Any] = Depends(require_user),  # noqa: B008
    service: AnalysisService = Depends(get_service),  # noqa: B008
) -> dict[str, Any]:
    return _guard(
        lambda: service.review(
            drawing_id,
            job_id,
            evidence_id,
            action=body.action,
            value=body.value,
            reviewer=user.get("sub"),
        )
    )


__all__ = [
    "ASSIST_TOTAL_BUDGET_SECONDS",
    "ACTIVE_STATUSES",
    "AnalysisService",
    "ErrorCode",
    "JobStatus",
    "PROMPT_CONTRACT_VERSION",
    "REQUEST_TIMEOUT_SECONDS",
    "classify_diagnostics",
    "default_provider_factory",
    "get_service",
    "router",
    "thread_runner",
]
