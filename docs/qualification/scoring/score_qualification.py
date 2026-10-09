"""
Deterministic qualification scoring engine – MachiningPro AI.

OFFLINE. DETERMINISTIC. READ-ONLY ground truth.
No AI calls, no OCR calls, no network calls.

Entry points
------------
score_run(gt_record, run)           -> RunScore
score_probe(probe_record, probe_run) -> ProbeResult
score_campaign(runs, gt_records, ...) -> CampaignScore
load_ground_truth(gt_dir)           -> (records_dict, manifest_hash)
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────────────────────────
# Sentinels for undefined / inapplicable metrics
# ──────────────────────────────────────────────────────────────────────────────
NOT_APPLICABLE = "NOT_APPLICABLE"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
NOT_SCORABLE = "NOT_SCORABLE"

MetricValue = float | int | str  # str when sentinel

# ──────────────────────────────────────────────────────────────────────────────
# Frozen thresholds (REAL_DRAWING_QUALIFICATION_01B)
# CHANGING ANY VALUE REQUIRES A NEW RECORDED DECISION.
# ──────────────────────────────────────────────────────────────────────────────
P2_DIMENSION_RECALL_MIN: float = 0.70
P3A_TEXT_PRECISION_MIN: float = 0.75
P3B_SYSTEMATIC_RUNS: int = 2
P4_FAILURE_RATE_MAX: float = 0.20
P5_MEDIAN_S: float = 240.0
P5_WORST_S: float = 480.0
P6_CORRECTION_RATE_MAX: float = 0.40
RECALL_GAIN_GATE_MIN: float = 0.15
CORE_RUNS_PER_DRAWING: int = 3
ESCALATION_RUNS_PER_DRAWING: int = 5

CORE_QUAL_IDS: frozenset[str] = frozenset({"Q01", "Q02", "Q05", "Q06", "Q07"})
EXT_GATE_QUAL_IDS: frozenset[str] = frozenset({"Q09", "Q10"})
EXT_QUAL_IDS: frozenset[str] = frozenset({"Q03", "Q04", "Q08"})

DIMENSION_FEATURE_TYPES: frozenset[str] = frozenset({
    "LINEAR_DIMENSION",
    "DIAMETER",
    "RADIUS",
    "ANGLE",
    "TOLERANCE",
    "HOLE_CALLOUT",
})

SCHEMA_VERSION = "1.0"

# ──────────────────────────────────────────────────────────────────────────────
# Exceptions
# ──────────────────────────────────────────────────────────────────────────────


class SchemaError(ValueError):
    """Malformed scoring input. Scoring fails closed."""


# ──────────────────────────────────────────────────────────────────────────────
# Normalisation helpers
# ──────────────────────────────────────────────────────────────────────────────
_UNIT_CANON: dict[str, str] = {
    "mm": "mm",
    "MM": "mm",
    "Mm": "mm",
    "inch": "inch",
    "in": "inch",
    "IN": "inch",
    "deg": "degree",
    "degree": "degree",
    "DEGREE": "degree",
    "°": "degree",
}


def _unit(u: str | None) -> str | None:
    if u is None:
        return None
    stripped = u.strip()
    return _UNIT_CANON.get(stripped, stripped.lower())


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip()


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", _nfc(s)).lower()


# ──────────────────────────────────────────────────────────────────────────────
# Input data classes
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class PredictedFinding:
    finding_id: str
    raw_text: str
    candidate_type: str | None = None
    feature_type: str | None = None
    normalized_value: str | None = None
    unit: str | None = None
    validation_status: str | None = None
    evidence_reference: str | None = None
    box_basis: str | None = None
    source_region: str | None = None


@dataclass
class DeterministicFinding:
    finding_id: str
    raw_text: str
    feature_type: str
    normalized_value: str | None = None
    unit: str | None = None
    validation_status: str | None = None


@dataclass
class HumanReviewEntry:
    finding_id: str
    review_action: str  # ACCEPT | EDIT | REJECT
    original_ai_value: str | None = None
    reviewed_value: str | None = None
    review_status: str = "FINAL"


@dataclass
class ProbeObservation:
    observed_behavior: str
    observed_job_status: str | None = None
    observed_error_or_gate: str | None = None
    additional_notes: str | None = None


@dataclass
class QualRunInput:
    qual_id: str
    run_id: str
    run_number: int
    fixture_class: str  # RECOGNITION_GROUND_TRUTH | PROBE_EXPECTATION | STRUCTURAL_EXPECTATION
    job_status: str     # COMPLETED | FAILED | R3B_VALIDATION_FAILURE | …
    provider: str | None = None
    model: str | None = None
    inference_elapsed_ms: int | None = None
    ai_findings: list[PredictedFinding] = field(default_factory=list)
    deterministic_findings: list[DeterministicFinding] = field(default_factory=list)
    human_review_findings: list[HumanReviewEntry] = field(default_factory=list)
    probe_observations: ProbeObservation | None = None
    r3b_rejection_code: str | None = None


# ──────────────────────────────────────────────────────────────────────────────
# Validation (fail closed)
# ──────────────────────────────────────────────────────────────────────────────
_VALID_FIXTURE_CLASSES = frozenset({
    "RECOGNITION_GROUND_TRUTH",
    "PROBE_EXPECTATION",
    "STRUCTURAL_EXPECTATION",
})
_VALID_REVIEW_ACTIONS = frozenset({"ACCEPT", "EDIT", "REJECT"})


def _validate(run: QualRunInput) -> None:
    if not isinstance(run, QualRunInput):
        raise SchemaError("run must be a QualRunInput instance")
    if not run.qual_id:
        raise SchemaError("qual_id is required")
    if not run.run_id:
        raise SchemaError("run_id is required")
    if not isinstance(run.run_number, int) or run.run_number < 1:
        raise SchemaError(f"run_number must be a positive int, got {run.run_number!r}")
    if run.fixture_class not in _VALID_FIXTURE_CLASSES:
        raise SchemaError(f"Unknown fixture_class: {run.fixture_class!r}")
    if not run.job_status:
        raise SchemaError("job_status is required")
    seen: set[str] = set()
    for f in run.ai_findings:
        if not isinstance(f, PredictedFinding):
            raise SchemaError("ai_findings entries must be PredictedFinding instances")
        if not f.finding_id:
            raise SchemaError("PredictedFinding.finding_id is required")
        if not f.raw_text:
            raise SchemaError("PredictedFinding.raw_text is required")
        if f.finding_id in seen:
            raise SchemaError(f"Duplicate finding_id: {f.finding_id!r}")
        seen.add(f.finding_id)
    for h in run.human_review_findings:
        if not isinstance(h, HumanReviewEntry):
            raise SchemaError("human_review_findings must be HumanReviewEntry instances")
        if h.review_action not in _VALID_REVIEW_ACTIONS:
            raise SchemaError(f"Invalid review_action: {h.review_action!r}")
    if run.inference_elapsed_ms is not None and not isinstance(run.inference_elapsed_ms, int):
        raise SchemaError("inference_elapsed_ms must be an int or None")


# ──────────────────────────────────────────────────────────────────────────────
# Matching
# ──────────────────────────────────────────────────────────────────────────────
# Ordered from best to worst (used for index comparison).
MATCH_LEVELS = ("EXACT", "NORMALISED", "SEMANTIC", "NO_MATCH")


def _match_level(
    pred_raw: str,
    pred_norm_value: str | None,
    pred_unit: str | None,
    gt_item: dict[str, Any],
) -> str:
    gt_text = gt_item.get("expected_text", "")
    # Level 1: EXACT (NFC + trim)
    if _nfc(pred_raw) == _nfc(gt_text):
        return "EXACT"
    # Level 2: NORMALISED (case-fold + collapse whitespace)
    if _norm(pred_raw) == _norm(gt_text):
        return "NORMALISED"
    # Level 3: SEMANTIC (same normalised numeric value + canonical unit)
    gt_val = gt_item.get("expected_normalized_value")
    gt_unit_raw = gt_item.get("expected_normalized_unit")
    ft = gt_item.get("feature_type", "")
    if (
        ft in DIMENSION_FEATURE_TYPES
        and gt_val is not None
        and pred_norm_value is not None
        and str(pred_norm_value).strip() == str(gt_val).strip()
        and _unit(pred_unit) == _unit(gt_unit_raw)
    ):
        return "SEMANTIC"
    return "NO_MATCH"


def _looks_like_dim(pred: PredictedFinding) -> bool:
    """True when finding looks like a dimension by value pattern (has value + unit)."""
    return pred.normalized_value is not None and pred.unit is not None


# ──────────────────────────────────────────────────────────────────────────────
# Result data classes
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class MatchResult:
    item_id: str
    expected_text: str
    feature_type: str
    required_for_demo: bool
    match_level: str
    matched_finding_id: str | None = None


@dataclass
class RunScore:
    qual_id: str
    run_id: str
    run_number: int
    job_status: str
    job_success: bool

    gt_item_count: int = 0

    # Recognition (all types)
    true_positive_count: int = 0
    false_positive_count: int = 0
    false_negative_count: int = 0

    # Dimension subset
    dim_tp: int = 0
    dim_fp: int = 0
    dim_fn: int = 0
    dim_looking_count: int = 0       # predictions that look like dimensions

    # Critical misses
    critical_miss_count: int = 0     # required_for_demo items missed
    r3b_rejection_count: int = 0
    no_findings: bool = False

    # Human review
    human_accept_count: int = 0
    human_edit_count: int = 0
    human_reject_count: int = 0
    accepted_wrong_count: int = 0    # accepted but not matching GT (P7)

    inference_elapsed_ms: int | None = None

    # Deterministic metrics
    det_dim_tp: int = 0
    det_dim_fn: int = 0
    det_dim_fp: int = 0              # false frame / unsupported reported
    det_dim_scoreable: bool = False  # False when RQ06 not yet scoreable
    det_title_tp: int = 0
    det_title_fn: int = 0
    det_gdt_tp: int = 0
    det_gdt_fp: int = 0              # unsupported characteristic reported
    det_status_distribution: dict[str, int] = field(default_factory=dict)

    # Detail
    match_detail: list[MatchResult] = field(default_factory=list)
    unmatched_finding_ids: list[str] = field(default_factory=list)
    matched_finding_ids: set[str] = field(default_factory=set)

    # RQ06 items
    rq06_items: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ProbeResult:
    probe_id: str
    fixture_class: str
    expected_behavior: str
    expected_error_or_gate: str
    actual_behavior: str | None
    actual_job_status: str | None
    actual_error: str | None
    pass_fail: str  # PASS | FAIL | NOT_EVALUATED
    recognition_score: dict[str, Any] | None = None  # for P-CROP scored_as_recognition
    notes: str = ""


@dataclass
class FixtureAggregate:
    qual_id: str
    demo_class: str  # CORE | EXT-GATE | EXT
    run_count: int

    # Pooled recognition
    text_recall: MetricValue = NOT_APPLICABLE
    text_precision: MetricValue = NOT_APPLICABLE
    dim_recall: MetricValue = NOT_APPLICABLE
    dim_precision: MetricValue = NOT_APPLICABLE
    false_positive_count: int = 0
    critical_miss_count: int = 0
    r3b_rejection_count: int = 0
    no_findings_count: int = 0
    job_failure_count: int = 0

    # Human review
    human_accept_count: int = 0
    human_edit_count: int = 0
    human_reject_count: int = 0
    human_correction_rate: MetricValue = NOT_APPLICABLE
    accepted_wrong_count: int = 0

    # Performance
    inference_times_s: list[float] = field(default_factory=list)
    median_inference_s: MetricValue = NOT_APPLICABLE
    p90_inference_s: MetricValue = NOT_APPLICABLE
    worst_inference_s: MetricValue = NOT_APPLICABLE

    # Deterministic
    det_dim_recall: MetricValue = NOT_SCORABLE
    det_title_recall: MetricValue = NOT_APPLICABLE
    det_gdt_recall: MetricValue = NOT_APPLICABLE
    det_gdt_false_frames: int = 0

    # Item stability: items found in every run / items found in any run
    item_stability: MetricValue = NOT_APPLICABLE

    # P1 per-drawing: any required_for_demo item missed in >=2/3 runs?
    p1_drawing_failing: bool = False
    p1_detail: list[str] = field(default_factory=list)  # item_ids that failed


@dataclass
class ClassAggregate:
    demo_class: str  # CORE | EXT_GATE | EXT
    drawing_count: int
    run_count: int
    text_recall: MetricValue = NOT_APPLICABLE
    text_precision: MetricValue = NOT_APPLICABLE
    dim_recall: MetricValue = NOT_APPLICABLE
    dim_precision: MetricValue = NOT_APPLICABLE
    human_correction_rate: MetricValue = NOT_APPLICABLE
    false_positive_count: int = 0
    r3b_rejection_count: int = 0
    no_findings_count: int = 0
    job_failure_rate: MetricValue = NOT_APPLICABLE
    median_inference_s: MetricValue = NOT_APPLICABLE
    worst_inference_s: MetricValue = NOT_APPLICABLE
    accepted_wrong_count: int = 0


@dataclass
class ThresholdEvaluation:
    threshold_id: str
    metric_value: MetricValue
    threshold_value: MetricValue
    pass_fail: str  # PASS | FAIL | NOT_APPLICABLE | INSUFFICIENT_DATA
    rationale: str


@dataclass
class RQ06Result:
    rq06_fixture_id: str
    expected_token: str
    observed: str | None
    match: bool
    scoreable: bool


@dataclass
class CampaignScore:
    schema_version: str
    qualification_version: str
    ground_truth_manifest_hash: str
    run_metadata: dict[str, Any]
    per_run_results: list[dict[str, Any]]
    per_fixture_aggregates: list[dict[str, Any]]
    class_aggregates: dict[str, Any]
    campaign_aggregate: dict[str, Any]
    threshold_evaluations: list[dict[str, Any]]
    probe_results: list[dict[str, Any]]
    rq06_results: list[dict[str, Any]]
    warnings: list[str]
    overall_status: str  # PASS | FAIL | INCOMPLETE


# ──────────────────────────────────────────────────────────────────────────────
# Per-run scoring
# ──────────────────────────────────────────────────────────────────────────────


def score_run(
    gt_record: dict[str, Any],
    run: QualRunInput,
) -> RunScore:
    """
    Score one qualification run against a frozen ground truth record.

    gt_record is never modified.
    Raises SchemaError for malformed input.
    """
    _validate(run)

    if run.fixture_class in ("PROBE_EXPECTATION", "STRUCTURAL_EXPECTATION"):
        # Recognition metrics do not apply to probe runs.
        return RunScore(
            qual_id=run.qual_id,
            run_id=run.run_id,
            run_number=run.run_number,
            job_status=run.job_status,
            job_success=run.job_status == "COMPLETED",
            inference_elapsed_ms=run.inference_elapsed_ms,
        )

    result = RunScore(
        qual_id=run.qual_id,
        run_id=run.run_id,
        run_number=run.run_number,
        job_status=run.job_status,
        job_success=run.job_status == "COMPLETED",
        inference_elapsed_ms=run.inference_elapsed_ms,
    )

    if run.job_status == "R3B_VALIDATION_FAILURE":
        result.r3b_rejection_count = 1

    if run.job_status == "COMPLETED" and len(run.ai_findings) == 0:
        result.no_findings = True

    # --- Collect scoreable GT items ----------------------------------------
    items: list[dict[str, Any]] = [
        it for it in gt_record.get("items", []) if it.get("scoreable", True)
    ]
    result.gt_item_count = len(items)

    # --- Match AI findings to GT items (greedy, best level first) ----------
    matched_gt: dict[str, str] = {}   # gt_item_id -> finding_id
    matched_pred: dict[str, str] = {} # finding_id -> gt_item_id

    for pred in run.ai_findings:
        best_level = "NO_MATCH"
        best_gt_id: str | None = None
        for gt_item in items:
            gid = gt_item["item_id"]
            if gid in matched_gt:
                continue
            lvl = _match_level(
                pred.raw_text,
                pred.normalized_value,
                pred.unit,
                gt_item,
            )
            if lvl == "NO_MATCH":
                continue
            if (
                best_level == "NO_MATCH"
                or MATCH_LEVELS.index(lvl) < MATCH_LEVELS.index(best_level)
            ):
                best_level = lvl
                best_gt_id = gid
        if best_gt_id is not None:
            matched_gt[best_gt_id] = pred.finding_id
            matched_pred[pred.finding_id] = best_gt_id

    result.matched_finding_ids = set(matched_pred.keys())

    # --- Per-GT-item classification ----------------------------------------
    for gt_item in items:
        gid = gt_item["item_id"]
        ft = gt_item.get("feature_type", "")
        rfd = bool(gt_item.get("required_for_demo", False))
        is_dim = ft in DIMENSION_FEATURE_TYPES

        if gid in matched_gt:
            finding_id = matched_gt[gid]
            pred = next(p for p in run.ai_findings if p.finding_id == finding_id)
            lvl = _match_level(pred.raw_text, pred.normalized_value, pred.unit, gt_item)
            result.match_detail.append(MatchResult(
                item_id=gid,
                expected_text=gt_item.get("expected_text", ""),
                feature_type=ft,
                required_for_demo=rfd,
                match_level=lvl,
                matched_finding_id=finding_id,
            ))
            result.true_positive_count += 1
            if is_dim:
                result.dim_tp += 1
        else:
            result.match_detail.append(MatchResult(
                item_id=gid,
                expected_text=gt_item.get("expected_text", ""),
                feature_type=ft,
                required_for_demo=rfd,
                match_level="NO_MATCH",
            ))
            result.false_negative_count += 1
            if is_dim:
                result.dim_fn += 1
                if rfd:
                    result.critical_miss_count += 1

    # --- Per-prediction classification ------------------------------------
    for pred in run.ai_findings:
        if _looks_like_dim(pred):
            result.dim_looking_count += 1
        if pred.finding_id not in matched_pred:
            result.false_positive_count += 1
            result.unmatched_finding_ids.append(pred.finding_id)
            if _looks_like_dim(pred):
                result.dim_fp += 1

    # --- Human review -------------------------------------------------------
    for h in run.human_review_findings:
        if h.review_action == "ACCEPT":
            result.human_accept_count += 1
            # accepted_wrong: accepted but did not match any GT item
            if h.finding_id not in result.matched_finding_ids:
                result.accepted_wrong_count += 1
        elif h.review_action == "EDIT":
            result.human_edit_count += 1
        elif h.review_action == "REJECT":
            result.human_reject_count += 1

    # --- Deterministic scoring ---------------------------------------------
    _score_deterministic(gt_record, run, result)

    return result


def _score_deterministic(
    gt_record: dict[str, Any],
    run: QualRunInput,
    result: RunScore,
) -> None:
    items = gt_record.get("items", [])
    det_dim_gt = [
        it for it in items
        if it.get("deterministic_scoreable")
        and it.get("feature_type") in DIMENSION_FEATURE_TYPES
    ]
    det_title_gt = [
        it for it in items
        if it.get("deterministic_scoreable")
        and it.get("feature_type") == "TITLE_BLOCK_TEXT"
    ]
    det_gdt_allowlisted = [
        it for it in items
        if it.get("deterministic_scoreable")
        and it.get("feature_type") == "GDT_TRANSCRIPTION"
        and it.get("gdt_role") == "FEATURE_CONTROL_FRAME"
        and it.get("characteristic_allowlisted") is True
    ]
    det_gdt_negative = [
        it for it in items
        if it.get("feature_type") == "GDT_TRANSCRIPTION"
        and it.get("gdt_role") == "FEATURE_CONTROL_FRAME"
        and it.get("negative_case") is True
    ]

    result.det_dim_scoreable = len(det_dim_gt) > 0

    # Match deterministic findings against GT items (same algorithm)
    det_findings = run.deterministic_findings
    matched_det_gt: dict[str, str] = {}
    matched_det_pred: dict[str, str] = {}

    for df in det_findings:
        best_level = "NO_MATCH"
        best_gid: str | None = None
        candidates = (
            det_dim_gt
            + det_title_gt
            + det_gdt_allowlisted
        )
        for gt_item in candidates:
            gid = gt_item["item_id"]
            if gid in matched_det_gt:
                continue
            lvl = _match_level(
                df.raw_text,
                df.normalized_value,
                df.unit,
                gt_item,
            )
            if lvl == "NO_MATCH":
                continue
            if (
                best_level == "NO_MATCH"
                or MATCH_LEVELS.index(lvl) < MATCH_LEVELS.index(best_level)
            ):
                best_level = lvl
                best_gid = gid
        if best_gid is not None:
            matched_det_gt[best_gid] = df.finding_id
            matched_det_pred[df.finding_id] = best_gid

    for it in det_dim_gt:
        if it["item_id"] in matched_det_gt:
            result.det_dim_tp += 1
        else:
            result.det_dim_fn += 1

    for it in det_title_gt:
        if it["item_id"] in matched_det_gt:
            result.det_title_tp += 1
        else:
            result.det_title_fn += 1

    for it in det_gdt_allowlisted:
        if it["item_id"] in matched_det_gt:
            result.det_gdt_tp += 1

    # False GDT frames: negative_case GT items that were reported by deterministic path
    neg_characteristics = {
        it.get("characteristic") for it in det_gdt_negative if it.get("characteristic")
    }
    for df in det_findings:
        raw_lower = _norm(df.raw_text)
        for ch in neg_characteristics:
            if ch and ch.lower() in raw_lower:
                result.det_gdt_fp += 1
                break

    # det_status_distribution
    for df in det_findings:
        if df.validation_status:
            result.det_status_distribution[df.validation_status] = (
                result.det_status_distribution.get(df.validation_status, 0) + 1
            )

    # RQ06: dimension grammar items
    for it in det_dim_gt:
        if it.get("deterministic_expectation") == "DIMENSION_GRAMMAR_ACCEPTED":
            observed: str | None = None
            matched = it["item_id"] in matched_det_gt
            if matched:
                fid = matched_det_gt[it["item_id"]]
                obs_f = next((d for d in det_findings if d.finding_id == fid), None)
                observed = obs_f.raw_text if obs_f else None
            result.rq06_items.append({
                "rq06_fixture_id": run.qual_id,
                "expected_token": it.get("expected_text", ""),
                "observed": observed,
                "match": matched,
                "scoreable": True,
            })


# ──────────────────────────────────────────────────────────────────────────────
# Probe scoring
# ──────────────────────────────────────────────────────────────────────────────


def score_probe(
    probe_record: dict[str, Any],
    probe_run: QualRunInput,
    parent_gt_record: dict[str, Any] | None = None,
) -> ProbeResult:
    """
    Score a probe run against its frozen probe expectation record.

    For P-CROP probes (scored_as_recognition=True), parent_gt_record
    provides the Q09 GT items referenced by contained_item_ids.
    """
    _validate(probe_run)

    expected_behavior = probe_record.get("expected_behavior", "")
    expected_gate = probe_record.get("expected_error_or_gate", "")
    obs = probe_run.probe_observations

    actual_behavior = obs.observed_behavior if obs else None
    actual_status = obs.observed_job_status if obs else probe_run.job_status
    actual_error = obs.observed_error_or_gate if obs else probe_run.r3b_rejection_code

    # Determine pass/fail
    if obs is None:
        pf = "NOT_EVALUATED"
        notes = "No probe_observations provided."
    else:
        # Check expected gate/status
        gate_ok = False
        if expected_gate:
            gate_ok = (
                actual_error is not None
                and _norm(expected_gate) in _norm(actual_error)
            ) or (
                actual_status is not None
                and _norm(expected_gate) in _norm(actual_status)
            )
        else:
            gate_ok = True

        pf = "PASS" if gate_ok else "FAIL"
        notes = ""

    recognition_score: dict[str, Any] | None = None

    # P-CROP: also score recognition against contained items
    if probe_record.get("scored_as_recognition") and parent_gt_record is not None:
        contained_ids = set(probe_record.get("contained_item_ids", []))
        # Build a synthetic GT record with only the contained items
        synthetic_gt = dict(parent_gt_record)
        synthetic_gt["items"] = [
            it for it in parent_gt_record.get("items", [])
            if it["item_id"] in contained_ids
        ]
        run_score = score_run(synthetic_gt, probe_run)
        recognition_score = _run_score_to_dict(run_score)

    return ProbeResult(
        probe_id=probe_run.qual_id,
        fixture_class=probe_record.get("fixture_class", ""),
        expected_behavior=expected_behavior,
        expected_error_or_gate=expected_gate,
        actual_behavior=actual_behavior,
        actual_job_status=actual_status,
        actual_error=actual_error,
        pass_fail=pf,
        recognition_score=recognition_score,
        notes=notes,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Aggregation helpers
# ──────────────────────────────────────────────────────────────────────────────


def _safe_rate(numerator: int, denominator: int) -> MetricValue:
    """Division with explicit NOT_APPLICABLE for zero denominator."""
    if denominator == 0:
        return NOT_APPLICABLE
    return round(numerator / denominator, 6)


def _median(values: list[float]) -> MetricValue:
    if not values:
        return NOT_APPLICABLE
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 == 1 else round((s[mid - 1] + s[mid]) / 2, 3)


def _p90(values: list[float]) -> MetricValue:
    if not values:
        return NOT_APPLICABLE
    s = sorted(values)
    idx = int(len(s) * 0.9)
    return s[min(idx, len(s) - 1)]


# ──────────────────────────────────────────────────────────────────────────────
# Per-fixture aggregation
# ──────────────────────────────────────────────────────────────────────────────


def aggregate_fixture(
    qual_id: str,
    demo_class: str,
    runs: list[RunScore],
    gt_record: dict[str, Any],
) -> FixtureAggregate:
    agg = FixtureAggregate(
        qual_id=qual_id,
        demo_class=demo_class,
        run_count=len(runs),
    )
    if not runs:
        return agg

    total_tp = sum(r.true_positive_count for r in runs)
    total_fp = sum(r.false_positive_count for r in runs)
    total_gt = sum(r.gt_item_count for r in runs)
    total_dim_tp = sum(r.dim_tp for r in runs)
    total_dim_fn = sum(r.dim_fn for r in runs)
    total_dim_looking = sum(r.dim_looking_count for r in runs)

    agg.text_recall = _safe_rate(total_tp, total_gt)
    agg.text_precision = _safe_rate(total_tp, total_tp + total_fp)
    agg.dim_recall = _safe_rate(total_dim_tp, total_dim_tp + total_dim_fn)
    agg.dim_precision = _safe_rate(total_dim_tp, total_dim_looking)
    agg.false_positive_count = total_fp
    agg.critical_miss_count = sum(r.critical_miss_count for r in runs)
    agg.r3b_rejection_count = sum(r.r3b_rejection_count for r in runs)
    agg.no_findings_count = sum(1 for r in runs if r.no_findings)
    agg.job_failure_count = sum(1 for r in runs if not r.job_success)
    agg.accepted_wrong_count = sum(r.accepted_wrong_count for r in runs)

    # Human review
    total_reviewed = (
        sum(r.human_accept_count for r in runs)
        + sum(r.human_edit_count for r in runs)
        + sum(r.human_reject_count for r in runs)
    )
    agg.human_accept_count = sum(r.human_accept_count for r in runs)
    agg.human_edit_count = sum(r.human_edit_count for r in runs)
    agg.human_reject_count = sum(r.human_reject_count for r in runs)
    total_corrected = agg.human_edit_count + agg.human_reject_count
    agg.human_correction_rate = _safe_rate(total_corrected, total_reviewed)

    # Performance
    times_s = [
        r.inference_elapsed_ms / 1000.0
        for r in runs
        if r.inference_elapsed_ms is not None and r.job_success
    ]
    agg.inference_times_s = times_s
    agg.median_inference_s = _median(times_s)
    agg.p90_inference_s = _p90(times_s)
    agg.worst_inference_s = max(times_s) if times_s else NOT_APPLICABLE

    # Deterministic
    det_dim_scoreable = any(r.det_dim_scoreable for r in runs)
    if det_dim_scoreable:
        det_dim_tp = sum(r.det_dim_tp for r in runs)
        det_dim_fn = sum(r.det_dim_fn for r in runs)
        agg.det_dim_recall = _safe_rate(det_dim_tp, det_dim_tp + det_dim_fn)
    # else stays NOT_SCORABLE

    det_title_expected = sum(r.det_title_tp + r.det_title_fn for r in runs)
    det_title_tp = sum(r.det_title_tp for r in runs)
    agg.det_title_recall = _safe_rate(det_title_tp, det_title_expected)

    det_gdt_tp = sum(r.det_gdt_tp for r in runs)
    det_gdt_fp = sum(r.det_gdt_fp for r in runs)
    # gdt expected = items from GT with allowlisted frames
    gdt_expected_items = [
        it for it in gt_record.get("items", [])
        if it.get("deterministic_scoreable")
        and it.get("gdt_role") == "FEATURE_CONTROL_FRAME"
        and it.get("characteristic_allowlisted") is True
    ]
    gdt_expected_per_run = len(gdt_expected_items) * len(runs)
    agg.det_gdt_recall = _safe_rate(det_gdt_tp, gdt_expected_per_run)
    agg.det_gdt_false_frames = det_gdt_fp

    # Item stability: items found in every run / items found in any run
    items = [it for it in gt_record.get("items", []) if it.get("scoreable", True)]
    if items and len(runs) >= 2:
        found_in_run: dict[str, int] = {}
        for r in runs:
            for m in r.match_detail:
                if m.match_level != "NO_MATCH":
                    found_in_run[m.item_id] = found_in_run.get(m.item_id, 0) + 1
        found_any = len(found_in_run)
        found_all = sum(1 for cnt in found_in_run.values() if cnt == len(runs))
        agg.item_stability = _safe_rate(found_all, found_any) if found_any > 0 else NOT_APPLICABLE
    else:
        agg.item_stability = NOT_APPLICABLE

    # P1 per-drawing check (CORE only, first 3 runs)
    if demo_class == "CORE":
        first3 = runs[:3]
        required_items = [
            it for it in items if it.get("required_for_demo") and it.get("scoreable", True)
        ]
        for gt_item in required_items:
            gid = gt_item["item_id"]
            miss_count = sum(
                1 for r in first3
                if all(
                    m.item_id != gid or m.match_level == "NO_MATCH"
                    for m in r.match_detail
                )
            )
            if miss_count >= 2 and len(first3) >= 2:
                agg.p1_drawing_failing = True
                agg.p1_detail.append(gid)

    return agg


# ──────────────────────────────────────────────────────────────────────────────
# Threshold evaluation
# ──────────────────────────────────────────────────────────────────────────────


def evaluate_thresholds(
    fixture_aggs: dict[str, FixtureAggregate],
    all_runs: list[RunScore],
    probe_results: list[ProbeResult],
    total_non_probe_jobs: int,
) -> list[ThresholdEvaluation]:
    evals: list[ThresholdEvaluation] = []

    # ── P1 ──────────────────────────────────────────────────────────────────
    core_failing = [
        qid for qid in CORE_QUAL_IDS
        if qid in fixture_aggs and fixture_aggs[qid].p1_drawing_failing
    ]
    p1_metric = len(core_failing)
    p1_pf = "FAIL" if p1_metric >= 2 else "PASS"
    if not any(qid in fixture_aggs for qid in CORE_QUAL_IDS):
        p1_pf = INSUFFICIENT_DATA

    evals.append(ThresholdEvaluation(
        threshold_id="P1",
        metric_value=p1_metric,
        threshold_value="<2 CORE drawings",
        pass_fail=p1_pf,
        rationale=(
            f"{p1_metric} CORE drawing(s) have a required_for_demo item"
            f" missed in >=2 of 3 runs: {core_failing or 'none'}"
        ),
    ))

    # ── P2 ──────────────────────────────────────────────────────────────────
    core_runs = [r for r in all_runs if r.qual_id in CORE_QUAL_IDS]
    dim_tp_c = sum(r.dim_tp for r in core_runs)
    dim_fn_c = sum(r.dim_fn for r in core_runs)
    p2_denom = dim_tp_c + dim_fn_c
    if p2_denom == 0:
        p2_metric: MetricValue = INSUFFICIENT_DATA
        p2_pf = INSUFFICIENT_DATA
    else:
        p2_v = round(dim_tp_c / p2_denom, 6)
        p2_metric = p2_v
        p2_pf = "PASS" if p2_v >= P2_DIMENSION_RECALL_MIN else "FAIL"

    evals.append(ThresholdEvaluation(
        threshold_id="P2",
        metric_value=p2_metric,
        threshold_value=P2_DIMENSION_RECALL_MIN,
        pass_fail=p2_pf,
        rationale=f"Overall DIMENSION_RECALL (CORE pooled) = {p2_metric}",
    ))

    # ── P3a ─────────────────────────────────────────────────────────────────
    tp_c = sum(r.true_positive_count for r in core_runs)
    fp_c = sum(r.false_positive_count for r in core_runs)
    p3a_denom = tp_c + fp_c
    if p3a_denom == 0:
        p3a_metric: MetricValue = INSUFFICIENT_DATA
        p3a_pf = INSUFFICIENT_DATA
    else:
        p3a_v = round(tp_c / p3a_denom, 6)
        p3a_metric = p3a_v
        p3a_pf = "PASS" if p3a_v >= P3A_TEXT_PRECISION_MIN else "FAIL"

    # ── P3b ─────────────────────────────────────────────────────────────────
    p3b_systematic = _check_p3b(all_runs)
    p3b_pf = "FAIL" if p3b_systematic else "PASS"

    # P3 overall FAIL if either part fails
    p3_pf = "FAIL" if (p3a_pf == "FAIL" or p3b_pf == "FAIL") else "PASS"
    if p3a_pf == INSUFFICIENT_DATA and p3b_pf == "PASS":
        p3_pf = INSUFFICIENT_DATA

    evals.append(ThresholdEvaluation(
        threshold_id="P3",
        metric_value=p3a_metric,
        threshold_value=P3A_TEXT_PRECISION_MIN,
        pass_fail=p3_pf,
        rationale=(
            f"P3a TEXT_PRECISION (CORE pooled) = {p3a_metric} "
            f"(threshold {P3A_TEXT_PRECISION_MIN}); "
            f"P3b systematic wrong value = {p3b_systematic}"
        ),
    ))

    # ── P4 ──────────────────────────────────────────────────────────────────
    if total_non_probe_jobs == 0:
        p4_metric: MetricValue = INSUFFICIENT_DATA
        p4_pf = INSUFFICIENT_DATA
    else:
        r3b_total = sum(r.r3b_rejection_count for r in all_runs)
        fail_total = sum(1 for r in all_runs if not r.job_success and r.r3b_rejection_count == 0)
        p4_v = round((r3b_total + fail_total) / total_non_probe_jobs, 6)
        p4_metric = p4_v
        p4_pf = "PASS" if p4_v <= P4_FAILURE_RATE_MAX else "FAIL"

    evals.append(ThresholdEvaluation(
        threshold_id="P4",
        metric_value=p4_metric,
        threshold_value=P4_FAILURE_RATE_MAX,
        pass_fail=p4_pf,
        rationale=f"(R3B rejections + failed jobs) / non-probe jobs = {p4_metric}",
    ))

    # ── P5 ──────────────────────────────────────────────────────────────────
    non_probe_times_s = [
        r.inference_elapsed_ms / 1000.0
        for r in all_runs
        if r.inference_elapsed_ms is not None
        and r.job_success
        and r.qual_id not in {  # exclude P-CROP
            q for q in [] # probes already excluded by fixture_class
        }
    ]
    p5_median: MetricValue = _median(non_probe_times_s)
    p5_worst: MetricValue = max(non_probe_times_s) if non_probe_times_s else NOT_APPLICABLE

    if not non_probe_times_s:
        p5_pf = INSUFFICIENT_DATA
    else:
        median_fail = isinstance(p5_median, float) and p5_median > P5_MEDIAN_S
        worst_fail = isinstance(p5_worst, float) and p5_worst > P5_WORST_S
        p5_pf = "FAIL" if (median_fail or worst_fail) else "PASS"

    evals.append(ThresholdEvaluation(
        threshold_id="P5",
        metric_value=f"median={p5_median} worst={p5_worst}",
        threshold_value=f"median<={P5_MEDIAN_S}s worst<={P5_WORST_S}s",
        pass_fail=p5_pf,
        rationale=f"Median inference = {p5_median}s; worst = {p5_worst}s",
    ))

    # ── P6 ──────────────────────────────────────────────────────────────────
    core_accept = sum(
        r.human_accept_count for r in all_runs if r.qual_id in CORE_QUAL_IDS
    )
    core_edit = sum(
        r.human_edit_count for r in all_runs if r.qual_id in CORE_QUAL_IDS
    )
    core_reject = sum(
        r.human_reject_count for r in all_runs if r.qual_id in CORE_QUAL_IDS
    )
    core_reviewed = core_accept + core_edit + core_reject
    p6_metric: MetricValue = _safe_rate(core_edit + core_reject, core_reviewed)

    if isinstance(p6_metric, str):
        p6_pf = INSUFFICIENT_DATA
    else:
        p6_pf = "FAIL" if p6_metric > P6_CORRECTION_RATE_MAX else "PASS"

    evals.append(ThresholdEvaluation(
        threshold_id="P6",
        metric_value=p6_metric,
        threshold_value=P6_CORRECTION_RATE_MAX,
        pass_fail=p6_pf,
        rationale=f"HUMAN_CORRECTION_RATE (CORE) = {p6_metric}",
    ))

    # ── P7 ──────────────────────────────────────────────────────────────────
    total_accepted_wrong = sum(r.accepted_wrong_count for r in all_runs)
    p7_pf = "FAIL" if total_accepted_wrong > 0 else "PASS"

    evals.append(ThresholdEvaluation(
        threshold_id="P7",
        metric_value=total_accepted_wrong,
        threshold_value=0,
        pass_fail=p7_pf,
        rationale=(
            f"ACCEPTED_WRONG_COUNT = {total_accepted_wrong} "
            "(any value > 0 indicates a misleading presentation)"
        ),
    ))

    # ── Recall-gain gate ────────────────────────────────────────────────────
    evals.append(_evaluate_recall_gain_gate(all_runs))

    return evals


def _check_p3b(all_runs: list[RunScore]) -> bool:
    """Check for same wrong value (unmatched prediction text) in >=2 runs per drawing."""
    # Group by qual_id
    by_drawing: dict[str, list[RunScore]] = {}
    for r in all_runs:
        by_drawing.setdefault(r.qual_id, []).append(r)

    for _qual_id, runs in by_drawing.items():
        if len(runs) < P3B_SYSTEMATIC_RUNS:
            continue
    # P3b check happens at campaign level where we have access to run inputs
    return False  # base; overridden in _check_p3b_from_inputs


def _check_p3b_from_inputs(
    runs_by_drawing: dict[str, list[tuple[QualRunInput, RunScore]]],
) -> bool:
    """P3b: same wrong value text in >=2 runs for any drawing with >=2 runs."""
    for _qual_id, run_pairs in runs_by_drawing.items():
        if len(run_pairs) < P3B_SYSTEMATIC_RUNS:
            continue
        texts_per_run: list[set[str]] = []
        for inp, score in run_pairs:
            unmatched_texts: set[str] = set()
            for pred in inp.ai_findings:
                if pred.finding_id in score.unmatched_finding_ids:
                    unmatched_texts.add(_norm(pred.raw_text))
            texts_per_run.append(unmatched_texts)
        all_texts = set().union(*texts_per_run)
        for text in all_texts:
            count = sum(1 for ts in texts_per_run if text in ts)
            if count >= P3B_SYSTEMATIC_RUNS:
                return True
    return False


def _evaluate_recall_gain_gate(all_runs: list[RunScore]) -> ThresholdEvaluation:
    """
    G2 / RECALL_GAIN_GATE: for Q05, Q09, Q10 where whole-image recall < P2
    and crop recall exists, check if gain >= 0.15.

    Returns INSUFFICIENT_DATA when crop runs are not present.
    """
    # Separate whole-image and crop runs
    whole_image_runs = [r for r in all_runs if not r.qual_id.startswith("P-CROP")]
    crop_runs = [r for r in all_runs if r.qual_id.startswith("P-CROP")]

    if not crop_runs:
        return ThresholdEvaluation(
            threshold_id="RECALL_GAIN_GATE",
            metric_value=INSUFFICIENT_DATA,
            threshold_value=RECALL_GAIN_GATE_MIN,
            pass_fail=INSUFFICIENT_DATA,
            rationale="No P-CROP runs present; cannot evaluate G2.",
        )

    # Extract parent qual_id from P-CROP qual_ids (e.g. P-CROP_Q09_c1 -> Q09)
    g2_candidates = {"Q05", "Q09", "Q10"}
    for qid in g2_candidates:
        wi_runs = [r for r in whole_image_runs if r.qual_id == qid]
        cr_runs = [r for r in crop_runs if r.qual_id.startswith(f"P-CROP_{qid}")]
        if not wi_runs or not cr_runs:
            continue
        wi_dim_tp = sum(r.dim_tp for r in wi_runs)
        wi_dim_denom = wi_dim_tp + sum(r.dim_fn for r in wi_runs)
        cr_dim_tp = sum(r.dim_tp for r in cr_runs)
        cr_dim_denom = cr_dim_tp + sum(r.dim_fn for r in cr_runs)

        if wi_dim_denom == 0 or cr_dim_denom == 0:
            continue

        wi_recall = wi_dim_tp / wi_dim_denom
        cr_recall = cr_dim_tp / cr_dim_denom
        gain = cr_recall - wi_recall

        if wi_recall < P2_DIMENSION_RECALL_MIN:
            pf = "PASS" if gain >= RECALL_GAIN_GATE_MIN else "FAIL"
            return ThresholdEvaluation(
                threshold_id="RECALL_GAIN_GATE",
                metric_value=round(gain, 6),
                threshold_value=RECALL_GAIN_GATE_MIN,
                pass_fail=pf,
                rationale=(
                    f"{qid}: whole-image recall={wi_recall:.4f} "
                    f"crop recall={cr_recall:.4f} gain={gain:.4f}"
                ),
            )

    return ThresholdEvaluation(
        threshold_id="RECALL_GAIN_GATE",
        metric_value=INSUFFICIENT_DATA,
        threshold_value=RECALL_GAIN_GATE_MIN,
        pass_fail=INSUFFICIENT_DATA,
        rationale="G2 precondition not met (no candidate drawing below P2) or crop data absent.",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Campaign completeness
# ──────────────────────────────────────────────────────────────────────────────


def _is_campaign_complete(
    runs_by_drawing: dict[str, list[RunScore]],
    warnings: list[str],
) -> bool:
    complete = True
    for qid in CORE_QUAL_IDS:
        n = len(runs_by_drawing.get(qid, []))
        if n < CORE_RUNS_PER_DRAWING:
            warnings.append(
                f"CORE {qid}: {n}/{CORE_RUNS_PER_DRAWING} runs – INCOMPLETE"
            )
            complete = False
    for qid in EXT_GATE_QUAL_IDS:
        n = len(runs_by_drawing.get(qid, []))
        if n < CORE_RUNS_PER_DRAWING:
            warnings.append(
                f"EXT-GATE {qid}: {n}/{CORE_RUNS_PER_DRAWING} runs – INCOMPLETE"
            )
            complete = False
    for qid in EXT_QUAL_IDS:
        n = len(runs_by_drawing.get(qid, []))
        if n < 1:
            warnings.append(f"EXT {qid}: 0/1 runs – INCOMPLETE")
            complete = False
    return complete


# ──────────────────────────────────────────────────────────────────────────────
# Serialisation helpers
# ──────────────────────────────────────────────────────────────────────────────


def _run_score_to_dict(r: RunScore) -> dict[str, Any]:
    return {
        "qual_id": r.qual_id,
        "run_id": r.run_id,
        "run_number": r.run_number,
        "job_status": r.job_status,
        "job_success": r.job_success,
        "gt_item_count": r.gt_item_count,
        "true_positive_count": r.true_positive_count,
        "false_positive_count": r.false_positive_count,
        "false_negative_count": r.false_negative_count,
        "dim_tp": r.dim_tp,
        "dim_fp": r.dim_fp,
        "dim_fn": r.dim_fn,
        "dim_looking_count": r.dim_looking_count,
        "critical_miss_count": r.critical_miss_count,
        "r3b_rejection_count": r.r3b_rejection_count,
        "no_findings": r.no_findings,
        "human_accept_count": r.human_accept_count,
        "human_edit_count": r.human_edit_count,
        "human_reject_count": r.human_reject_count,
        "accepted_wrong_count": r.accepted_wrong_count,
        "inference_elapsed_ms": r.inference_elapsed_ms,
        "det_dim_tp": r.det_dim_tp,
        "det_dim_fn": r.det_dim_fn,
        "det_dim_scoreable": r.det_dim_scoreable,
        "det_gdt_fp": r.det_gdt_fp,
        "det_status_distribution": r.det_status_distribution,
        "match_detail": [
            {
                "item_id": m.item_id,
                "expected_text": m.expected_text,
                "feature_type": m.feature_type,
                "required_for_demo": m.required_for_demo,
                "match_level": m.match_level,
                "matched_finding_id": m.matched_finding_id,
            }
            for m in r.match_detail
        ],
        "unmatched_finding_ids": r.unmatched_finding_ids,
        "rq06_items": r.rq06_items,
    }


def _fixture_agg_to_dict(a: FixtureAggregate) -> dict[str, Any]:
    return {
        "qual_id": a.qual_id,
        "demo_class": a.demo_class,
        "run_count": a.run_count,
        "text_recall": a.text_recall,
        "text_precision": a.text_precision,
        "dim_recall": a.dim_recall,
        "dim_precision": a.dim_precision,
        "false_positive_count": a.false_positive_count,
        "critical_miss_count": a.critical_miss_count,
        "r3b_rejection_count": a.r3b_rejection_count,
        "no_findings_count": a.no_findings_count,
        "job_failure_count": a.job_failure_count,
        "human_accept_count": a.human_accept_count,
        "human_edit_count": a.human_edit_count,
        "human_reject_count": a.human_reject_count,
        "human_correction_rate": a.human_correction_rate,
        "accepted_wrong_count": a.accepted_wrong_count,
        "median_inference_s": a.median_inference_s,
        "p90_inference_s": a.p90_inference_s,
        "worst_inference_s": a.worst_inference_s,
        "det_dim_recall": a.det_dim_recall,
        "det_title_recall": a.det_title_recall,
        "det_gdt_recall": a.det_gdt_recall,
        "det_gdt_false_frames": a.det_gdt_false_frames,
        "item_stability": a.item_stability,
        "p1_drawing_failing": a.p1_drawing_failing,
        "p1_detail": a.p1_detail,
    }


def _probe_result_to_dict(p: ProbeResult) -> dict[str, Any]:
    return {
        "probe_id": p.probe_id,
        "fixture_class": p.fixture_class,
        "expected_behavior": p.expected_behavior,
        "expected_error_or_gate": p.expected_error_or_gate,
        "actual_behavior": p.actual_behavior,
        "actual_job_status": p.actual_job_status,
        "actual_error": p.actual_error,
        "pass_fail": p.pass_fail,
        "recognition_score": p.recognition_score,
        "notes": p.notes,
    }


def _threshold_to_dict(t: ThresholdEvaluation) -> dict[str, Any]:
    return {
        "threshold_id": t.threshold_id,
        "metric_value": t.metric_value,
        "threshold_value": t.threshold_value,
        "pass_fail": t.pass_fail,
        "rationale": t.rationale,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Ground truth loader (read-only)
# ──────────────────────────────────────────────────────────────────────────────


def load_ground_truth(
    gt_dir: Path,
) -> tuple[dict[str, Any], str]:
    """
    Load all frozen GT records from gt_dir. Never modifies any file.

    Returns (records_dict, manifest_hash) where records_dict maps
    qual_id -> record dict.
    """
    manifest_path = gt_dir / "manifest.json"
    if not manifest_path.exists():
        raise SchemaError(f"Ground truth manifest not found: {manifest_path}")

    raw = manifest_path.read_bytes()
    manifest_hash = hashlib.sha256(raw).hexdigest()

    manifest: dict[str, Any] = json.loads(raw)
    records: dict[str, Any] = {}

    for entry in manifest.get("records", []):
        record_file = gt_dir / entry["record_file"]
        with record_file.open("r", encoding="utf-8") as fh:
            record = json.load(fh)
        records[entry["qual_id"]] = record

    return records, manifest_hash


# ──────────────────────────────────────────────────────────────────────────────
# Campaign scoring (main entry point)
# ──────────────────────────────────────────────────────────────────────────────


def score_campaign(
    runs: list[QualRunInput],
    gt_records: dict[str, Any],
    manifest_hash: str = "",
    qualification_version: str = "REAL_DRAWING_QUALIFICATION_01",
    qual_id: str = "DEMO_QUAL_01",
) -> CampaignScore:
    """
    Score a complete (or partial) qualification campaign.

    gt_records: mapping of qual_id -> frozen GT record (never modified).
    Incomplete campaigns receive OVERALL_STATUS = INCOMPLETE.
    Raises SchemaError for malformed run inputs.
    """
    warnings: list[str] = []
    per_run_results: list[dict[str, Any]] = []
    probe_results: list[ProbeResult] = []
    all_run_scores: list[RunScore] = []
    all_rq06: list[dict[str, Any]] = []

    # Pair inputs with their GT records and score
    runs_by_drawing: dict[str, list[RunScore]] = {}
    run_input_by_drawing: dict[str, list[tuple[QualRunInput, RunScore]]] = {}

    for inp in runs:
        if inp.qual_id not in gt_records:
            raise SchemaError(
                f"No ground truth record for qual_id: {inp.qual_id!r}. "
                "Provide a matching record in gt_records."
            )
        gt = gt_records[inp.qual_id]
        is_probe = inp.fixture_class in ("PROBE_EXPECTATION", "STRUCTURAL_EXPECTATION")

        if is_probe:
            parent_gt = None
            probe_record = gt
            # For P-CROP probes, look up parent GT
            if gt.get("scored_as_recognition"):
                parent_qid = gt.get("parent_qual_id") or gt.get("derived_from")
                if parent_qid and parent_qid in gt_records:
                    parent_gt = gt_records[parent_qid]
            p_result = score_probe(probe_record, inp, parent_gt)
            probe_results.append(p_result)
            per_run_results.append(_probe_result_to_dict(p_result))
        else:
            run_score = score_run(gt, inp)
            all_run_scores.append(run_score)
            per_run_results.append(_run_score_to_dict(run_score))
            runs_by_drawing.setdefault(inp.qual_id, []).append(run_score)
            run_input_by_drawing.setdefault(inp.qual_id, []).append((inp, run_score))
            all_rq06.extend(run_score.rq06_items)

    # P3b check with access to raw predictions
    p3b_systematic = _check_p3b_from_inputs(run_input_by_drawing)
    # (We inject this into the threshold evaluation later)

    # Per-fixture aggregation
    fixture_aggs: dict[str, FixtureAggregate] = {}
    for qid, run_scores in runs_by_drawing.items():
        gt = gt_records.get(qid, {})
        demo_class = gt.get("demo_class", "EXT")
        agg = aggregate_fixture(qid, demo_class, run_scores, gt)
        fixture_aggs[qid] = agg

    # Class aggregation
    class_aggs = _aggregate_by_class(fixture_aggs, all_run_scores)

    # Campaign aggregate
    total_non_probe = len(all_run_scores)
    campaign_agg = _aggregate_campaign(all_run_scores, total_non_probe)

    # Threshold evaluation
    threshold_evals = evaluate_thresholds(
        fixture_aggs, all_run_scores, probe_results, total_non_probe
    )
    # Override P3b with accurate value
    _patch_p3b(threshold_evals, p3b_systematic)

    # Campaign completeness
    is_complete = _is_campaign_complete(runs_by_drawing, warnings)

    # RQ06 results
    rq06_results = all_rq06

    # Overall status
    if not is_complete:
        overall_status = "INCOMPLETE"
    else:
        any_fail = any(
            t.pass_fail == "FAIL" for t in threshold_evals
        )
        overall_status = "FAIL" if any_fail else "PASS"

    return CampaignScore(
        schema_version=SCHEMA_VERSION,
        qualification_version=qualification_version,
        ground_truth_manifest_hash=manifest_hash,
        run_metadata={
            "qual_id": qual_id,
            "run_count": len(all_run_scores),
            "probe_count": len(probe_results),
        },
        per_run_results=per_run_results,
        per_fixture_aggregates=[_fixture_agg_to_dict(a) for a in fixture_aggs.values()],
        class_aggregates=class_aggs,
        campaign_aggregate=campaign_agg,
        threshold_evaluations=[_threshold_to_dict(t) for t in threshold_evals],
        probe_results=[_probe_result_to_dict(p) for p in probe_results],
        rq06_results=rq06_results,
        warnings=warnings,
        overall_status=overall_status,
    )


def _patch_p3b(
    threshold_evals: list[ThresholdEvaluation],
    systematic: bool,
) -> None:
    for t in threshold_evals:
        if t.threshold_id == "P3":
            if systematic:
                t.pass_fail = "FAIL"
                t.rationale = t.rationale + " [P3b: systematic wrong value DETECTED]"
            break


def _aggregate_by_class(
    fixture_aggs: dict[str, FixtureAggregate],
    all_runs: list[RunScore],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for demo_class, qual_ids in [
        ("CORE", CORE_QUAL_IDS),
        ("EXT_GATE", EXT_GATE_QUAL_IDS),
        ("EXT", EXT_QUAL_IDS),
    ]:
        class_runs = [r for r in all_runs if r.qual_id in qual_ids]
        drawing_count = len({r.qual_id for r in class_runs})
        tp = sum(r.true_positive_count for r in class_runs)
        fp = sum(r.false_positive_count for r in class_runs)
        fn = sum(r.false_negative_count for r in class_runs)
        gt = tp + fn
        dim_tp = sum(r.dim_tp for r in class_runs)
        dim_fn = sum(r.dim_fn for r in class_runs)
        dim_looking = sum(r.dim_looking_count for r in class_runs)
        accept = sum(r.human_accept_count for r in class_runs)
        edit = sum(r.human_edit_count for r in class_runs)
        reject = sum(r.human_reject_count for r in class_runs)
        reviewed = accept + edit + reject
        r3b = sum(r.r3b_rejection_count for r in class_runs)
        no_f = sum(1 for r in class_runs if r.no_findings)
        failed = sum(1 for r in class_runs if not r.job_success)
        times_s = [
            r.inference_elapsed_ms / 1000.0
            for r in class_runs
            if r.inference_elapsed_ms is not None and r.job_success
        ]
        result[demo_class] = {
            "drawing_count": drawing_count,
            "run_count": len(class_runs),
            "text_recall": _safe_rate(tp, gt),
            "text_precision": _safe_rate(tp, tp + fp),
            "dim_recall": _safe_rate(dim_tp, dim_tp + dim_fn),
            "dim_precision": _safe_rate(dim_tp, dim_looking),
            "human_correction_rate": _safe_rate(edit + reject, reviewed),
            "false_positive_count": fp,
            "r3b_rejection_count": r3b,
            "no_findings_count": no_f,
            "job_failure_rate": _safe_rate(failed, len(class_runs)),
            "median_inference_s": _median(times_s),
            "worst_inference_s": max(times_s) if times_s else NOT_APPLICABLE,
            "accepted_wrong_count": sum(r.accepted_wrong_count for r in class_runs),
        }
    return result


def _aggregate_campaign(
    all_runs: list[RunScore],
    total_non_probe: int,
) -> dict[str, Any]:
    if not all_runs:
        return {"run_count": 0, "overall_status": NOT_APPLICABLE}
    tp = sum(r.true_positive_count for r in all_runs)
    fp = sum(r.false_positive_count for r in all_runs)
    fn = sum(r.false_negative_count for r in all_runs)
    gt_total = tp + fn
    dim_tp = sum(r.dim_tp for r in all_runs)
    dim_fn = sum(r.dim_fn for r in all_runs)
    dim_looking = sum(r.dim_looking_count for r in all_runs)
    accept = sum(r.human_accept_count for r in all_runs)
    edit = sum(r.human_edit_count for r in all_runs)
    reject = sum(r.human_reject_count for r in all_runs)
    reviewed = accept + edit + reject
    r3b = sum(r.r3b_rejection_count for r in all_runs)
    no_f = sum(1 for r in all_runs if r.no_findings)
    failed = sum(1 for r in all_runs if not r.job_success and r.r3b_rejection_count == 0)
    times_s = [
        r.inference_elapsed_ms / 1000.0
        for r in all_runs
        if r.inference_elapsed_ms is not None and r.job_success
    ]
    return {
        "run_count": total_non_probe,
        "text_recall": _safe_rate(tp, gt_total),
        "text_precision": _safe_rate(tp, tp + fp),
        "dim_recall": _safe_rate(dim_tp, dim_tp + dim_fn),
        "dim_precision": _safe_rate(dim_tp, dim_looking),
        "false_positive_count": fp,
        "r3b_rejection_count": r3b,
        "no_findings_count": no_f,
        "job_failure_rate": _safe_rate(failed, total_non_probe),
        "human_accept_count": accept,
        "human_edit_count": edit,
        "human_reject_count": reject,
        "human_correction_rate": _safe_rate(edit + reject, reviewed),
        "accepted_wrong_count": sum(r.accepted_wrong_count for r in all_runs),
        "median_inference_s": _median(times_s),
        "p90_inference_s": _p90(times_s),
        "worst_inference_s": max(times_s) if times_s else NOT_APPLICABLE,
    }
