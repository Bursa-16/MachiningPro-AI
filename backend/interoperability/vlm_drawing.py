"""Phase 1D AI/VLM advisory evidence contracts (Task 2: types and validation only).

This module defines the typed, immutable contracts for VLM assistance:
configuration, operational limits, regions, evidence, findings, the advisory
report and the assisted-ingestion wrapper. It contains no behavior: no region
planning, cropping, response parsing, provider calls, normalization or
reconciliation, and no network code.

Governing decisions (docs/superpowers/specs/2026-09-24-technical-drawing-
phase-1d-design.md):

* D1 — AI/VLM output is advisory only and never modifies ``CanonicalDrawing``.
  Every piece of VLM evidence carries ``DrawingExtractionAuthority.ADVISORY``.
* D2 — the future ``parse_with_assistance`` entry point is additive.
* D3 — no remote provider ships in Phase 1D. Remote-related configuration
  fields exist structurally only; nothing here enables remote access.

Existing canonical types are reused (``DrawingSourceLocation``,
``DrawingBoundingBox``, ``DrawingParserIdentity``, ``DrawingDimension``,
``DrawingDatumReference``, ``DrawingGdtCharacteristic``,
``DrawingIngestionStatus``, ``DrawingIngestionResult``, ``DrawingRasterSource``).
``drawing.py`` is unchanged and ``GdtTokenSource`` is intentionally not
extended, so VLM evidence can never enter deterministic GD&T recognition.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum, unique

from backend.interoperability.drawing import (
    DrawingBoundingBox,
    DrawingDatumReference,
    DrawingDimension,
    DrawingExtractionAuthority,
    DrawingGdtCharacteristic,
    DrawingIngestionResult,
    DrawingIngestionStatus,
    DrawingParserIdentity,
    DrawingRasterSource,
    DrawingSourceLocation,
)
from backend.interoperability.vlm_provider import VlmModelIdentity

_MAX_IDENTIFIER_LENGTH = 128
_MAX_DIAGNOSTICS = 50            # existing drawing diagnostics contract (50 × 240)
_MAX_DIAGNOSTIC_LENGTH = 240
_FINGERPRINT_PATTERN = re.compile(r"[0-9a-f]{64}")   # lowercase SHA-256 hex
_DATUM_LABEL_PATTERN = re.compile(r"[A-Z]")
_ZERO = Decimal("0")
_ONE = Decimal("1")


# ---------------------------------------------------------------------------
# Vocabularies (approved design values only)
# ---------------------------------------------------------------------------


@unique
class DrawingEvidenceOrigin(StrEnum):
    """Origin of a piece of evidence referenced by a finding."""

    VECTOR = "VECTOR"
    OCR = "OCR"
    AI_VLM = "AI_VLM"


@unique
class DrawingVlmMode(StrEnum):
    """BLIND sends no OCR/vector text to the model; GUIDED may send region text."""

    BLIND = "BLIND"
    GUIDED = "GUIDED"


@unique
class DrawingVlmRegionKind(StrEnum):
    OCR_REVIEW = "OCR_REVIEW"
    TITLE_BLOCK = "TITLE_BLOCK"
    GDT_CANDIDATE = "GDT_CANDIDATE"
    IMAGE_OVERVIEW = "IMAGE_OVERVIEW"


@unique
class DrawingVlmEvidenceKind(StrEnum):
    TEXT = "TEXT"
    TITLE_FIELD = "TITLE_FIELD"
    DIMENSION = "DIMENSION"
    DATUM_LABEL = "DATUM_LABEL"
    GDT_CHARACTERISTIC = "GDT_CHARACTERISTIC"
    NOTE = "NOTE"


@unique
class DrawingVlmLegibility(StrEnum):
    CLEAR = "CLEAR"
    DEGRADED = "DEGRADED"
    ILLEGIBLE = "ILLEGIBLE"


@unique
class DrawingVlmValidationStatus(StrEnum):
    VALID = "VALID"
    REJECTED = "REJECTED"


@unique
class DrawingVlmReconciliationStatus(StrEnum):
    CORROBORATED = "CORROBORATED"
    RECOVERY_CANDIDATE = "RECOVERY_CANDIDATE"
    CONFLICT = "CONFLICT"
    ADVISORY_ONLY = "ADVISORY_ONLY"
    REJECTED = "REJECTED"
    UNSTABLE = "UNSTABLE"


@unique
class DrawingVlmRationale(StrEnum):
    """Rationale categories computed by MachiningPro; never supplied by a model."""

    EXACT_MATCH = "EXACT_MATCH"
    OCR_BELOW_THRESHOLD = "OCR_BELOW_THRESHOLD"
    DETERMINISTIC_OMITTED = "DETERMINISTIC_OMITTED"
    NO_DETERMINISTIC_EVIDENCE = "NO_DETERMINISTIC_EVIDENCE"
    VALUE_MISMATCH = "VALUE_MISMATCH"
    DECIMAL_MISMATCH = "DECIMAL_MISMATCH"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    TOLERANCE_MISMATCH = "TOLERANCE_MISMATCH"
    CHARACTER_MISMATCH = "CHARACTER_MISMATCH"
    GRAMMAR_REJECTED = "GRAMMAR_REJECTED"
    UNIT_NOT_EVIDENCED = "UNIT_NOT_EVIDENCED"
    BARE_NUMBER = "BARE_NUMBER"
    INSIDE_TITLE_BLOCK = "INSIDE_TITLE_BLOCK"
    IDENTIFIER_CONTEXT = "IDENTIFIER_CONTEXT"
    LABEL_NOT_EVIDENCED = "LABEL_NOT_EVIDENCED"
    OUTSIDE_REGION = "OUTSIDE_REGION"
    UNSUPPORTED_KIND = "UNSUPPORTED_KIND"
    SAMPLE_DISAGREEMENT = "SAMPLE_DISAGREEMENT"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_text(value: object, name: str, max_length: int | None = None) -> None:
    """Non-blank, control-character-free text, optionally length-bounded."""
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must not be blank")
    if max_length is not None and len(value) > max_length:
        raise ValueError(f"{name} exceeds {max_length} characters")
    if any(unicodedata.category(character).startswith("C") for character in value):
        raise ValueError(f"{name} must not contain control characters")


def _validate_identifier(value: object, name: str) -> None:
    _validate_text(value, name, _MAX_IDENTIFIER_LENGTH)


def _validate_int(value: object, name: str, *, minimum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")


def _validate_unit_decimal(value: object, name: str) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be Decimal")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    if not _ZERO <= value <= _ONE:
        raise ValueError(f"{name} must be in [0, 1]")


def _validate_identifier_tuple(
    value: object, name: str, *, allow_empty: bool = True
) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be a tuple")
    if not allow_empty and not value:
        raise ValueError(f"{name} must not be empty")
    for item in value:
        _validate_identifier(item, f"{name} item")
    if len(set(value)) != len(value):
        raise ValueError(f"{name} must not contain duplicates")


def _validate_typed_tuple(value: object, name: str, item_type: type) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be a tuple")
    if any(not isinstance(item, item_type) for item in value):
        raise TypeError(f"{name} must contain {item_type.__name__} values")


# ---------------------------------------------------------------------------
# Operational limits and assistance configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VlmLimits:
    """Approved configurable v1 operational/resource defaults.

    These are resource bounds, not engineering truth thresholds. Time values
    are whole seconds; byte and pixel values are exact counts.
    """

    ocr_review_floor: Decimal = Decimal("0.50")
    pages_considered: int = 10
    regions_per_page: int = 16
    regions_total: int = 64
    crop_longest_edge_px: int = 2_048
    crop_pixels: int = 4_194_304
    crop_png_bytes: int = 4 * 1024 * 1024
    requests_per_document: int = 64
    samples_per_region: int = 1
    maximum_samples_per_region: int = 3
    attempts_per_request: int = 2
    response_bytes: int = 256 * 1024
    output_tokens_hint: int = 2_048
    items_per_response: int = 200
    evidence_items_total: int = 5_000
    raw_candidate_chars: int = 256
    request_timeout_seconds: int = 30
    assist_total_budget_seconds: int = 120
    crop_worker_timeout_seconds: int = 30
    region_padding_px: int = 8
    diagnostics_max_count: int = _MAX_DIAGNOSTICS
    diagnostic_max_chars: int = _MAX_DIAGNOSTIC_LENGTH

    def __post_init__(self) -> None:
        _validate_unit_decimal(self.ocr_review_floor, "VlmLimits.ocr_review_floor")
        for name in (
            "pages_considered",
            "regions_per_page",
            "regions_total",
            "crop_longest_edge_px",
            "crop_pixels",
            "crop_png_bytes",
            "requests_per_document",
            "samples_per_region",
            "maximum_samples_per_region",
            "attempts_per_request",
            "response_bytes",
            "output_tokens_hint",
            "items_per_response",
            "evidence_items_total",
            "raw_candidate_chars",
            "request_timeout_seconds",
            "assist_total_budget_seconds",
            "crop_worker_timeout_seconds",
            "diagnostics_max_count",
            "diagnostic_max_chars",
        ):
            _validate_int(getattr(self, name), f"VlmLimits.{name}", minimum=1)
        # Zero padding is explicitly safe: the crop is then the evidence box.
        _validate_int(self.region_padding_px, "VlmLimits.region_padding_px", minimum=0)
        if self.regions_per_page > self.regions_total:
            raise ValueError("VlmLimits.regions_per_page must not exceed regions_total")
        if self.samples_per_region > self.maximum_samples_per_region:
            raise ValueError(
                "VlmLimits.samples_per_region must not exceed maximum_samples_per_region"
            )
        if self.request_timeout_seconds > self.assist_total_budget_seconds:
            raise ValueError(
                "VlmLimits.request_timeout_seconds must not exceed assist_total_budget_seconds"
            )
        if self.crop_worker_timeout_seconds > self.assist_total_budget_seconds:
            raise ValueError(
                "VlmLimits.crop_worker_timeout_seconds must not exceed "
                "assist_total_budget_seconds"
            )


@dataclass(frozen=True)
class DrawingVlmAssistConfig:
    """Call-scoped VLM assistance configuration. Conservative by default.

    Nothing here reads environment variables. The remote-related fields are
    structural only (D3): no Phase 1D code path enables a remote provider.
    ``allowed_provider_ids`` is set-like and stored in sorted order so equal
    configurations are equal and print identically.
    """

    enabled: bool = False
    mode: DrawingVlmMode = DrawingVlmMode.BLIND
    limits: VlmLimits = field(default_factory=VlmLimits)
    allow_remote: bool = False
    allowed_provider_ids: tuple[str, ...] = ()
    remote_allow_title_block: bool = False
    assist_on_insufficient_data: bool = False
    require_audit_for_remote: bool = True

    def __post_init__(self) -> None:
        for name in (
            "enabled",
            "allow_remote",
            "remote_allow_title_block",
            "assist_on_insufficient_data",
            "require_audit_for_remote",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"DrawingVlmAssistConfig.{name} must be bool")
        if not isinstance(self.mode, DrawingVlmMode):
            raise TypeError("DrawingVlmAssistConfig.mode must be DrawingVlmMode")
        if not isinstance(self.limits, VlmLimits):
            raise TypeError("DrawingVlmAssistConfig.limits must be VlmLimits")
        _validate_identifier_tuple(
            self.allowed_provider_ids, "DrawingVlmAssistConfig.allowed_provider_ids"
        )
        object.__setattr__(self, "allowed_provider_ids", tuple(sorted(self.allowed_provider_ids)))


# ---------------------------------------------------------------------------
# Region
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DrawingVlmRegion:
    """One raster region that may be sent to a provider. No image bytes."""

    region_id: str
    kind: DrawingVlmRegionKind
    page_number: int
    raster_source: DrawingRasterSource
    crop_px: tuple[int, int, int, int]
    pdf_box: DrawingBoundingBox
    trigger_evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier(self.region_id, "DrawingVlmRegion.region_id")
        if not isinstance(self.kind, DrawingVlmRegionKind):
            raise TypeError("DrawingVlmRegion.kind must be DrawingVlmRegionKind")
        _validate_int(self.page_number, "DrawingVlmRegion.page_number", minimum=1)
        if not isinstance(self.raster_source, DrawingRasterSource):
            raise TypeError("DrawingVlmRegion.raster_source must be DrawingRasterSource")
        if self.raster_source.page_number != self.page_number:
            raise ValueError("DrawingVlmRegion.page_number must match raster_source page")
        if not isinstance(self.crop_px, tuple) or len(self.crop_px) != 4:
            raise TypeError("DrawingVlmRegion.crop_px must be a tuple of 4 ints")
        for value in self.crop_px:
            _validate_int(value, "DrawingVlmRegion.crop_px item", minimum=0)
        x0, y0, x1, y1 = self.crop_px
        if x1 <= x0 or y1 <= y0:
            raise ValueError("DrawingVlmRegion.crop_px must satisfy x1 > x0 and y1 > y0")
        if not isinstance(self.pdf_box, DrawingBoundingBox):
            raise TypeError("DrawingVlmRegion.pdf_box must be DrawingBoundingBox")
        _validate_identifier_tuple(
            self.trigger_evidence_ids, "DrawingVlmRegion.trigger_evidence_ids"
        )


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DrawingVlmEvidence:
    """One VLM proposal after validation. Advisory by construction.

    ``raw_candidate`` is the model transcription, kept verbatim; its length
    limit is the configurable ``VlmLimits.raw_candidate_chars`` and is
    enforced by the validation stage, not by this contract. Normalized fields
    are computed by MachiningPro only (never taken from a model) and are
    never canonical. There is no field for a provider payload, image bytes,
    path, credential or timestamp.
    """

    evidence_id: str
    evidence_kind: DrawingVlmEvidenceKind
    raw_candidate: str
    legibility: DrawingVlmLegibility
    source_location: DrawingSourceLocation
    parser_identity: DrawingParserIdentity
    model: VlmModelIdentity
    prompt_contract_version: str
    region_id: str
    request_id: str
    sample_index: int
    validation_status: DrawingVlmValidationStatus
    normalized_candidate: str | None = None
    field_key: str | None = None
    normalized_dimension: DrawingDimension | None = None
    normalized_characteristic: DrawingGdtCharacteristic | None = None
    normalized_datum: DrawingDatumReference | None = None
    reported_confidence: Decimal | None = None
    rejection_rationale: DrawingVlmRationale | None = None

    def __post_init__(self) -> None:
        _validate_identifier(self.evidence_id, "DrawingVlmEvidence.evidence_id")
        if not isinstance(self.evidence_kind, DrawingVlmEvidenceKind):
            raise TypeError("DrawingVlmEvidence.evidence_kind must be DrawingVlmEvidenceKind")
        _validate_text(self.raw_candidate, "DrawingVlmEvidence.raw_candidate")
        if not isinstance(self.legibility, DrawingVlmLegibility):
            raise TypeError("DrawingVlmEvidence.legibility must be DrawingVlmLegibility")
        self._validate_provenance()
        if not isinstance(self.parser_identity, DrawingParserIdentity):
            raise TypeError("DrawingVlmEvidence.parser_identity must be DrawingParserIdentity")
        if not isinstance(self.model, VlmModelIdentity):
            raise TypeError("DrawingVlmEvidence.model must be VlmModelIdentity")
        _validate_identifier(
            self.prompt_contract_version, "DrawingVlmEvidence.prompt_contract_version"
        )
        _validate_identifier(self.region_id, "DrawingVlmEvidence.region_id")
        _validate_identifier(self.request_id, "DrawingVlmEvidence.request_id")
        _validate_int(self.sample_index, "DrawingVlmEvidence.sample_index", minimum=0)
        if self.reported_confidence is not None:
            _validate_unit_decimal(
                self.reported_confidence, "DrawingVlmEvidence.reported_confidence"
            )
        if self.source_location.confidence != self.reported_confidence:
            raise ValueError(
                "DrawingVlmEvidence.source_location.confidence must mirror reported_confidence"
            )
        self._validate_normalized_fields()
        self._validate_status()

    def _validate_provenance(self) -> None:
        location = self.source_location
        if not isinstance(location, DrawingSourceLocation):
            raise TypeError("DrawingVlmEvidence.source_location must be DrawingSourceLocation")
        if location.authority is not DrawingExtractionAuthority.ADVISORY:
            raise ValueError("DrawingVlmEvidence.source_location.authority must be ADVISORY")
        if location.page_number is None:
            raise ValueError("DrawingVlmEvidence.source_location.page_number is required")
        if location.original_text != self.raw_candidate:
            raise ValueError(
                "DrawingVlmEvidence.source_location.original_text must equal raw_candidate"
            )
        for required in (self.region_id, self.evidence_id):
            if required not in location.source_object_ids:
                raise ValueError(
                    "DrawingVlmEvidence.source_location.source_object_ids must include "
                    "region_id and evidence_id"
                )

    def _validate_normalized_fields(self) -> None:
        kind = self.evidence_kind
        if self.normalized_candidate is not None:
            _validate_text(
                self.normalized_candidate, "DrawingVlmEvidence.normalized_candidate"
            )
        if self.field_key is not None:
            _validate_identifier(self.field_key, "DrawingVlmEvidence.field_key")
            if kind is not DrawingVlmEvidenceKind.TITLE_FIELD:
                raise ValueError("DrawingVlmEvidence.field_key is only valid for TITLE_FIELD")
        if self.normalized_dimension is not None:
            if not isinstance(self.normalized_dimension, DrawingDimension):
                raise TypeError(
                    "DrawingVlmEvidence.normalized_dimension must be DrawingDimension"
                )
            if kind is not DrawingVlmEvidenceKind.DIMENSION:
                raise ValueError(
                    "DrawingVlmEvidence.normalized_dimension is only valid for DIMENSION"
                )
        if self.normalized_characteristic is not None:
            if not isinstance(self.normalized_characteristic, DrawingGdtCharacteristic):
                raise TypeError(
                    "DrawingVlmEvidence.normalized_characteristic must be "
                    "DrawingGdtCharacteristic"
                )
            if kind is not DrawingVlmEvidenceKind.GDT_CHARACTERISTIC:
                raise ValueError(
                    "DrawingVlmEvidence.normalized_characteristic is only valid for "
                    "GDT_CHARACTERISTIC"
                )
        if self.normalized_datum is not None:
            if not isinstance(self.normalized_datum, DrawingDatumReference):
                raise TypeError(
                    "DrawingVlmEvidence.normalized_datum must be DrawingDatumReference"
                )
            if kind is not DrawingVlmEvidenceKind.DATUM_LABEL:
                raise ValueError(
                    "DrawingVlmEvidence.normalized_datum is only valid for DATUM_LABEL"
                )
            if _DATUM_LABEL_PATTERN.fullmatch(self.normalized_datum.datum_label) is None:
                raise ValueError(
                    "DrawingVlmEvidence.normalized_datum label must be one uppercase letter"
                )

    def _validate_status(self) -> None:
        if not isinstance(self.validation_status, DrawingVlmValidationStatus):
            raise TypeError(
                "DrawingVlmEvidence.validation_status must be DrawingVlmValidationStatus"
            )
        if self.rejection_rationale is not None and not isinstance(
            self.rejection_rationale, DrawingVlmRationale
        ):
            raise TypeError(
                "DrawingVlmEvidence.rejection_rationale must be DrawingVlmRationale"
            )
        if self.validation_status is DrawingVlmValidationStatus.VALID:
            if self.rejection_rationale is not None:
                raise ValueError("VALID evidence must not carry a rejection_rationale")
            if self.source_location.bounding_box is None:
                raise ValueError("VALID evidence requires a mapped bounding box")
        elif self.rejection_rationale is None:
            raise ValueError("REJECTED evidence requires a rejection_rationale")


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------

# Statuses whose definition in the design matrix requires deterministic support.
_STATUSES_REQUIRING_SUPPORT = (
    DrawingVlmReconciliationStatus.CORROBORATED,
    DrawingVlmReconciliationStatus.RECOVERY_CANDIDATE,
    DrawingVlmReconciliationStatus.CONFLICT,
)


@dataclass(frozen=True)
class DrawingVlmFinding:
    """Classification of AI evidence against deterministic evidence.

    ``deterministic_origins`` is set-like (which deterministic sources support
    the finding) and may contain only VECTOR and OCR. ID tuples keep the
    caller's order; duplicates are rejected.
    """

    finding_id: str
    status: DrawingVlmReconciliationStatus
    rationale: DrawingVlmRationale
    ai_evidence_ids: tuple[str, ...]
    deterministic_support_ids: tuple[str, ...] = ()
    deterministic_origins: tuple[DrawingEvidenceOrigin, ...] = ()
    conflict_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier(self.finding_id, "DrawingVlmFinding.finding_id")
        if not isinstance(self.status, DrawingVlmReconciliationStatus):
            raise TypeError("DrawingVlmFinding.status must be DrawingVlmReconciliationStatus")
        if not isinstance(self.rationale, DrawingVlmRationale):
            raise TypeError("DrawingVlmFinding.rationale must be DrawingVlmRationale")
        _validate_identifier_tuple(
            self.ai_evidence_ids, "DrawingVlmFinding.ai_evidence_ids", allow_empty=False
        )
        _validate_identifier_tuple(
            self.deterministic_support_ids, "DrawingVlmFinding.deterministic_support_ids"
        )
        _validate_identifier_tuple(self.conflict_ids, "DrawingVlmFinding.conflict_ids")
        _validate_typed_tuple(
            self.deterministic_origins,
            "DrawingVlmFinding.deterministic_origins",
            DrawingEvidenceOrigin,
        )
        if len(set(self.deterministic_origins)) != len(self.deterministic_origins):
            raise ValueError("DrawingVlmFinding.deterministic_origins must not contain duplicates")
        if DrawingEvidenceOrigin.AI_VLM in self.deterministic_origins:
            raise ValueError("DrawingVlmFinding.deterministic_origins must not contain AI_VLM")
        if bool(self.deterministic_support_ids) != bool(self.deterministic_origins):
            raise ValueError(
                "DrawingVlmFinding deterministic_support_ids and deterministic_origins "
                "must both be present or both be empty"
            )
        if set(self.ai_evidence_ids) & set(self.deterministic_support_ids):
            raise ValueError(
                "DrawingVlmFinding AI evidence IDs must not appear as deterministic support"
            )
        if self.status in _STATUSES_REQUIRING_SUPPORT and not self.deterministic_support_ids:
            raise ValueError(
                f"DrawingVlmFinding status {self.status.value} requires deterministic support"
            )
        if self.status is DrawingVlmReconciliationStatus.CONFLICT and not self.conflict_ids:
            raise ValueError("DrawingVlmFinding status CONFLICT requires conflict_ids")


# ---------------------------------------------------------------------------
# Advisory report and assisted result
# ---------------------------------------------------------------------------

_EMPTY_RESULT_STATUSES = (DrawingIngestionStatus.FAILED, DrawingIngestionStatus.UNSUPPORTED)


def _validate_fingerprint(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if _FINGERPRINT_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


@dataclass(frozen=True)
class DrawingAdvisoryReport:
    """Bounded, deterministic advisory output. Never part of CanonicalDrawing.

    Fingerprints are caller-supplied (computed by a later task) and only
    validated structurally here. There are no timestamps, raw payloads, image
    bytes or paths.
    """

    status: DrawingIngestionStatus
    prompt_contract_version: str
    model: VlmModelIdentity | None
    config_fingerprint: str
    base_result_fingerprint: str
    regions: tuple[DrawingVlmRegion, ...] = ()
    evidence: tuple[DrawingVlmEvidence, ...] = ()
    findings: tuple[DrawingVlmFinding, ...] = ()
    diagnostics: tuple[str, ...] = ()
    request_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.status, DrawingIngestionStatus):
            raise TypeError("DrawingAdvisoryReport.status must be DrawingIngestionStatus")
        _validate_identifier(
            self.prompt_contract_version, "DrawingAdvisoryReport.prompt_contract_version"
        )
        if self.model is not None and not isinstance(self.model, VlmModelIdentity):
            raise TypeError("DrawingAdvisoryReport.model must be VlmModelIdentity or None")
        _validate_fingerprint(self.config_fingerprint, "DrawingAdvisoryReport.config_fingerprint")
        _validate_fingerprint(
            self.base_result_fingerprint, "DrawingAdvisoryReport.base_result_fingerprint"
        )
        _validate_typed_tuple(self.regions, "DrawingAdvisoryReport.regions", DrawingVlmRegion)
        _validate_typed_tuple(self.evidence, "DrawingAdvisoryReport.evidence", DrawingVlmEvidence)
        _validate_typed_tuple(self.findings, "DrawingAdvisoryReport.findings", DrawingVlmFinding)
        self._validate_diagnostics()
        _validate_int(self.request_count, "DrawingAdvisoryReport.request_count", minimum=0)
        if self.status in _EMPTY_RESULT_STATUSES and (self.evidence or self.findings):
            raise ValueError(
                f"DrawingAdvisoryReport with status {self.status.value} must not carry "
                "evidence or findings"
            )
        self._validate_references()

    def _validate_diagnostics(self) -> None:
        if not isinstance(self.diagnostics, tuple):
            raise TypeError("DrawingAdvisoryReport.diagnostics must be a tuple")
        if len(self.diagnostics) > _MAX_DIAGNOSTICS:
            raise ValueError(f"DrawingAdvisoryReport.diagnostics exceeds {_MAX_DIAGNOSTICS}")
        for code in self.diagnostics:
            _validate_text(code, "DrawingAdvisoryReport.diagnostics item", _MAX_DIAGNOSTIC_LENGTH)

    def _validate_references(self) -> None:
        region_ids = tuple(region.region_id for region in self.regions)
        evidence_ids = tuple(item.evidence_id for item in self.evidence)
        finding_ids = tuple(finding.finding_id for finding in self.findings)
        for name, ids in (
            ("region", region_ids),
            ("evidence", evidence_ids),
            ("finding", finding_ids),
        ):
            if len(set(ids)) != len(ids):
                raise ValueError(f"DrawingAdvisoryReport {name} IDs must be unique")
        known_regions = set(region_ids)
        for item in self.evidence:
            if item.region_id not in known_regions:
                raise ValueError("DrawingAdvisoryReport evidence must reference a report region")
            if self.model is None or item.model != self.model:
                raise ValueError("DrawingAdvisoryReport evidence model must match report model")
            if item.prompt_contract_version != self.prompt_contract_version:
                raise ValueError(
                    "DrawingAdvisoryReport evidence prompt contract must match the report"
                )
        known_evidence = set(evidence_ids)
        for finding in self.findings:
            if not set(finding.ai_evidence_ids) <= known_evidence:
                raise ValueError(
                    "DrawingAdvisoryReport findings must reference report evidence"
                )


@dataclass(frozen=True)
class DrawingAssistedIngestionResult:
    """Deterministic parse result plus optional advisory report.

    ``result`` is carried unchanged; this wrapper never copies or mutates it.
    ``advisory`` is ``None`` whenever assistance is disabled or not run.
    """

    result: DrawingIngestionResult
    advisory: DrawingAdvisoryReport | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.result, DrawingIngestionResult):
            raise TypeError("DrawingAssistedIngestionResult.result must be DrawingIngestionResult")
        if self.advisory is not None and not isinstance(self.advisory, DrawingAdvisoryReport):
            raise TypeError(
                "DrawingAssistedIngestionResult.advisory must be DrawingAdvisoryReport or None"
            )


__all__ = [
    "DrawingAdvisoryReport",
    "DrawingAssistedIngestionResult",
    "DrawingEvidenceOrigin",
    "DrawingVlmAssistConfig",
    "DrawingVlmEvidence",
    "DrawingVlmEvidenceKind",
    "DrawingVlmFinding",
    "DrawingVlmLegibility",
    "DrawingVlmMode",
    "DrawingVlmRationale",
    "DrawingVlmReconciliationStatus",
    "DrawingVlmRegion",
    "DrawingVlmRegionKind",
    "DrawingVlmValidationStatus",
    "VlmLimits",
]
