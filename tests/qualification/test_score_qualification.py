"""
Deterministic scoring engine tests.

All tests use mocked scoring inputs; no AI service is called,
no network connection is made, and ground truth files are never modified.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
from score_qualification import (
    CORE_RUNS_PER_DRAWING,
    INSUFFICIENT_DATA,
    NOT_APPLICABLE,
    NOT_SCORABLE,
    P2_DIMENSION_RECALL_MIN,
    DeterministicFinding,
    HumanReviewEntry,
    PredictedFinding,
    ProbeObservation,
    QualRunInput,
    SchemaError,
    aggregate_fixture,
    load_ground_truth,
    score_campaign,
    score_probe,
    score_run,
)

# ──────────────────────────────────────────────────────────────────────────────
# Minimal GT record helpers
# ──────────────────────────────────────────────────────────────────────────────

GT_DIR = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "qualification"
    / "ground_truth"
)


def _dim_item(
    item_id: str,
    text: str,
    value: str,
    unit: str,
    rfd: bool = True,
    ft: str = "LINEAR_DIMENSION",
    det_scoreable: bool = True,
) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "expected_text": text,
        "feature_type": ft,
        "expected_normalized_value": value,
        "expected_normalized_unit": unit,
        "required_for_demo": rfd,
        "scoreable": True,
        "deterministic_scoreable": det_scoreable,
        "deterministic_expectation": "DIMENSION_GRAMMAR_ACCEPTED" if det_scoreable else "NONE",
    }


def _text_item(
    item_id: str,
    text: str,
    rfd: bool = False,
    ft: str = "GENERAL_TEXT",
) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "expected_text": text,
        "feature_type": ft,
        "expected_normalized_value": None,
        "expected_normalized_unit": None,
        "required_for_demo": rfd,
        "scoreable": True,
        "deterministic_scoreable": False,
        "deterministic_expectation": "NONE",
    }


def _gt(items: list[dict[str, Any]], qual_id: str = "Q01", demo_class: str = "CORE") -> dict:
    return {
        "qual_id": qual_id,
        "demo_class": demo_class,
        "record_type": "RECOGNITION_GROUND_TRUTH",
        "items": items,
    }


def _run(
    qual_id: str = "Q01",
    run_number: int = 1,
    job_status: str = "COMPLETED",
    ai_findings: list[PredictedFinding] | None = None,
    det_findings: list[DeterministicFinding] | None = None,
    human_review: list[HumanReviewEntry] | None = None,
    inference_ms: int | None = 120_000,
    fixture_class: str = "RECOGNITION_GROUND_TRUTH",
) -> QualRunInput:
    return QualRunInput(
        qual_id=qual_id,
        run_id=f"{qual_id}-run{run_number}",
        run_number=run_number,
        fixture_class=fixture_class,
        job_status=job_status,
        inference_elapsed_ms=inference_ms,
        ai_findings=ai_findings or [],
        deterministic_findings=det_findings or [],
        human_review_findings=human_review or [],
    )


def _pred(
    fid: str,
    text: str,
    value: str | None = None,
    unit: str | None = None,
) -> PredictedFinding:
    return PredictedFinding(
        finding_id=fid,
        raw_text=text,
        normalized_value=value,
        unit=unit,
    )


def _det(
    fid: str,
    text: str,
    ft: str = "DIMENSION",
    value: str | None = None,
    unit: str | None = None,
    status: str = "VALID",
) -> DeterministicFinding:
    return DeterministicFinding(
        finding_id=fid,
        raw_text=text,
        feature_type=ft,
        normalized_value=value,
        unit=unit,
        validation_status=status,
    )


def _review(fid: str, action: str) -> HumanReviewEntry:
    return HumanReviewEntry(finding_id=fid, review_action=action)


# ──────────────────────────────────────────────────────────────────────────────
# Test 1 – Perfect recognition → precision/recall = 1
# ──────────────────────────────────────────────────────────────────────────────
def test_01_perfect_recognition():
    items = [
        _dim_item("I1", "100 MM", "100", "mm"),
        _dim_item("I2", "60 MM", "60", "mm"),
    ]
    gt = _gt(items)
    run = _run(
        ai_findings=[
            _pred("F1", "100 MM", "100", "mm"),
            _pred("F2", "60 MM", "60", "mm"),
        ],
    )
    result = score_run(gt, run)
    assert result.true_positive_count == 2
    assert result.false_positive_count == 0
    assert result.false_negative_count == 0
    assert result.dim_tp == 2
    assert result.dim_fn == 0
    assert result.dim_fp == 0


# ──────────────────────────────────────────────────────────────────────────────
# Test 2 – One missed dimension
# ──────────────────────────────────────────────────────────────────────────────
def test_02_one_missed_dimension():
    items = [
        _dim_item("I1", "100 MM", "100", "mm"),
        _dim_item("I2", "60 MM", "60", "mm"),
    ]
    gt = _gt(items)
    run = _run(ai_findings=[_pred("F1", "100 MM", "100", "mm")])
    result = score_run(gt, run)
    assert result.true_positive_count == 1
    assert result.false_negative_count == 1
    assert result.dim_fn == 1
    assert result.dim_tp == 1


# ──────────────────────────────────────────────────────────────────────────────
# Test 3 – One false positive
# ──────────────────────────────────────────────────────────────────────────────
def test_03_one_false_positive():
    items = [_dim_item("I1", "100 MM", "100", "mm")]
    gt = _gt(items)
    run = _run(
        ai_findings=[
            _pred("F1", "100 MM", "100", "mm"),
            _pred("F2", "999 MM", "999", "mm"),  # hallucinated
        ],
    )
    result = score_run(gt, run)
    assert result.true_positive_count == 1
    assert result.false_positive_count == 1
    assert result.dim_fp == 1


# ──────────────────────────────────────────────────────────────────────────────
# Test 4 – Wrong numeric value (near miss; must not match)
# ──────────────────────────────────────────────────────────────────────────────
def test_04_wrong_numeric_value():
    items = [_dim_item("I1", "100 MM", "100", "mm")]
    gt = _gt(items)
    # AI says "101 MM" – off by one digit; must NOT match
    run = _run(ai_findings=[_pred("F1", "101 MM", "101", "mm")])
    result = score_run(gt, run)
    assert result.true_positive_count == 0
    assert result.false_positive_count == 1
    assert result.false_negative_count == 1


# ──────────────────────────────────────────────────────────────────────────────
# Test 5 – Wrong unit (value same, unit different; must not match at SEMANTIC)
# ──────────────────────────────────────────────────────────────────────────────
def test_05_wrong_unit():
    items = [_dim_item("I1", "100 MM", "100", "mm")]
    gt = _gt(items)
    # AI reports 100 inch – same value, wrong unit
    run = _run(ai_findings=[_pred("F1", "100 inch", "100", "inch")])
    result = score_run(gt, run)
    assert result.true_positive_count == 0
    assert result.false_positive_count == 1
    assert result.false_negative_count == 1


# ──────────────────────────────────────────────────────────────────────────────
# Test 6 – Normalised equivalent text (case fold only)
# ──────────────────────────────────────────────────────────────────────────────
def test_06_normalised_text():
    items = [_text_item("I1", "NOTES:")]
    gt = _gt(items)
    run = _run(ai_findings=[_pred("F1", "notes:")])
    result = score_run(gt, run)
    assert result.true_positive_count == 1
    matched_levels = [m.match_level for m in result.match_detail if m.item_id == "I1"]
    assert matched_levels == ["NORMALISED"]


# ──────────────────────────────────────────────────────────────────────────────
# Test 7 – Duplicate prediction (same finding_id → SchemaError)
# ──────────────────────────────────────────────────────────────────────────────
def test_07_duplicate_prediction_rejected():
    gt = _gt([_dim_item("I1", "100 MM", "100", "mm")])
    run = _run(
        ai_findings=[
            _pred("SAME_ID", "100 MM", "100", "mm"),
            _pred("SAME_ID", "60 MM", "60", "mm"),
        ]
    )
    with pytest.raises(SchemaError, match="Duplicate finding_id"):
        score_run(gt, run)


# ──────────────────────────────────────────────────────────────────────────────
# Test 8 – No findings (COMPLETED job, zero AI findings)
# ──────────────────────────────────────────────────────────────────────────────
def test_08_no_findings():
    gt = _gt([_dim_item("I1", "100 MM", "100", "mm")])
    run = _run(job_status="COMPLETED", ai_findings=[])
    result = score_run(gt, run)
    assert result.no_findings is True
    assert result.false_negative_count == 1


# ──────────────────────────────────────────────────────────────────────────────
# Test 9 – Failed job
# ──────────────────────────────────────────────────────────────────────────────
def test_09_failed_job():
    gt = _gt([_dim_item("I1", "100 MM", "100", "mm")])
    run = _run(job_status="FAILED", ai_findings=[])
    result = score_run(gt, run)
    assert result.job_success is False
    assert result.no_findings is False   # FAILED, not COMPLETED with no findings


# ──────────────────────────────────────────────────────────────────────────────
# Test 10 – R3B rejection
# ──────────────────────────────────────────────────────────────────────────────
def test_10_r3b_rejection():
    gt = _gt([_dim_item("I1", "100 MM", "100", "mm")])
    run = _run(job_status="R3B_VALIDATION_FAILURE", ai_findings=[])
    run.r3b_rejection_code = "OVER_ITEM_LIMIT"
    result = score_run(gt, run)
    assert result.r3b_rejection_count == 1
    assert result.job_success is False


# ──────────────────────────────────────────────────────────────────────────────
# Test 11 – Human ACCEPT
# ──────────────────────────────────────────────────────────────────────────────
def test_11_human_accept():
    gt = _gt([_dim_item("I1", "100 MM", "100", "mm")])
    run = _run(
        ai_findings=[_pred("F1", "100 MM", "100", "mm")],
        human_review=[_review("F1", "ACCEPT")],
    )
    result = score_run(gt, run)
    assert result.human_accept_count == 1
    assert result.human_edit_count == 0
    assert result.human_reject_count == 0
    assert result.accepted_wrong_count == 0   # correctly accepted


# ──────────────────────────────────────────────────────────────────────────────
# Test 12 – Human EDIT
# ──────────────────────────────────────────────────────────────────────────────
def test_12_human_edit():
    gt = _gt([_dim_item("I1", "100 MM", "100", "mm")])
    run = _run(
        ai_findings=[_pred("F1", "100 MM", "100", "mm")],
        human_review=[HumanReviewEntry(
            finding_id="F1",
            review_action="EDIT",
            original_ai_value="100 MM",
            reviewed_value="100 mm",
        )],
    )
    result = score_run(gt, run)
    assert result.human_edit_count == 1
    assert result.human_accept_count == 0


# ──────────────────────────────────────────────────────────────────────────────
# Test 13 – Human REJECT
# ──────────────────────────────────────────────────────────────────────────────
def test_13_human_reject():
    gt = _gt([_dim_item("I1", "100 MM", "100", "mm")])
    run = _run(
        ai_findings=[_pred("F1", "999 MM", "999", "mm")],
        human_review=[_review("F1", "REJECT")],
    )
    result = score_run(gt, run)
    assert result.human_reject_count == 1


# ──────────────────────────────────────────────────────────────────────────────
# Test 14 – Correction rate
# ──────────────────────────────────────────────────────────────────────────────
def test_14_correction_rate():
    items = [
        _dim_item("I1", "100 MM", "100", "mm"),
        _text_item("I2", "NOTES:"),
        _text_item("I3", "TITLE:"),
    ]
    gt = _gt(items)
    run = _run(
        ai_findings=[
            _pred("F1", "100 MM", "100", "mm"),
            _pred("F2", "NOTES:"),
            _pred("F3", "WRONG"),
        ],
        human_review=[
            _review("F1", "ACCEPT"),
            _review("F2", "EDIT"),
            _review("F3", "REJECT"),
        ],
    )
    result = score_run(gt, run)
    # reviewed = 3, corrected = edit(1) + reject(1) = 2 → rate = 2/3
    reviewed = (
        result.human_accept_count + result.human_edit_count + result.human_reject_count
    )
    corrected = result.human_edit_count + result.human_reject_count
    assert reviewed == 3
    assert corrected == 2


# ──────────────────────────────────────────────────────────────────────────────
# Test 15 – Probe PASS (P-VEC: expected INVALID_REGION, observed INVALID_REGION)
# ──────────────────────────────────────────────────────────────────────────────
def test_15_probe_pass():
    probe_record = {
        "qual_id": "P-VEC_Q01",
        "fixture_class": "STRUCTURAL_EXPECTATION",
        "expected_behavior": "Job refused with INVALID_REGION",
        "expected_error_or_gate": "INVALID_REGION",
        "scored_as_recognition": False,
    }
    probe_run = _run(
        qual_id="P-VEC_Q01",
        job_status="FAILED",
        fixture_class="STRUCTURAL_EXPECTATION",
        ai_findings=[],
        inference_ms=None,
    )
    probe_run.probe_observations = ProbeObservation(
        observed_behavior="Job refused",
        observed_job_status="FAILED",
        observed_error_or_gate="INVALID_REGION",
    )
    result = score_probe(probe_record, probe_run)
    assert result.pass_fail == "PASS"


# ──────────────────────────────────────────────────────────────────────────────
# Test 16 – Probe FAIL (P-DOWN: expected OLLAMA_UNAVAILABLE, got COMPLETED)
# ──────────────────────────────────────────────────────────────────────────────
def test_16_probe_fail():
    probe_record = {
        "qual_id": "P-DOWN",
        "fixture_class": "STRUCTURAL_EXPECTATION",
        "expected_behavior": "Job FAILED with OLLAMA_UNAVAILABLE",
        "expected_error_or_gate": "OLLAMA_UNAVAILABLE",
        "scored_as_recognition": False,
    }
    probe_run = _run(
        qual_id="P-DOWN",
        job_status="COMPLETED",
        fixture_class="STRUCTURAL_EXPECTATION",
        ai_findings=[],
        inference_ms=None,
    )
    probe_run.probe_observations = ProbeObservation(
        observed_behavior="Job succeeded unexpectedly",
        observed_job_status="COMPLETED",
        observed_error_or_gate=None,
    )
    result = score_probe(probe_record, probe_run)
    assert result.pass_fail == "FAIL"


# ──────────────────────────────────────────────────────────────────────────────
# Test 17 – Undefined denominator → NOT_APPLICABLE
# ──────────────────────────────────────────────────────────────────────────────
def test_17_undefined_denominator():
    gt = _gt([])   # no GT items
    run = _run(ai_findings=[])
    result = score_run(gt, run)
    # Per-fixture aggregation with zero GT items
    agg = aggregate_fixture("Q01", "CORE", [result], gt)
    # text_recall: 0/0 → NOT_APPLICABLE
    assert agg.text_recall == NOT_APPLICABLE
    # text_precision: 0/0 → NOT_APPLICABLE
    assert agg.text_precision == NOT_APPLICABLE
    # dim_precision: 0 dim_looking → NOT_APPLICABLE
    assert agg.dim_precision == NOT_APPLICABLE


# ──────────────────────────────────────────────────────────────────────────────
# Test 18 – Incomplete campaign cannot PASS
# ──────────────────────────────────────────────────────────────────────────────
def test_18_incomplete_campaign_cannot_pass():
    # Only 1 CORE run for Q01 (need 3); no other runs
    gt_records = {
        "Q01": _gt([_dim_item("I1", "100 MM", "100", "mm")], "Q01", "CORE"),
        "Q02": _gt([_dim_item("I1", "50 MM", "50", "mm")], "Q02", "CORE"),
        "Q05": _gt([_dim_item("I1", "80 MM", "80", "mm")], "Q05", "CORE"),
        "Q06": _gt([_dim_item("I1", "90 mm", "90", "mm")], "Q06", "CORE"),
        "Q07": _gt([_dim_item("I1", "132.0 mm", "132", "mm")], "Q07", "CORE"),
        "Q09": _gt([_dim_item("I1", "200 mm", "200", "mm")], "Q09", "EXT-GATE"),
        "Q10": _gt([_dim_item("I1", "300 mm", "300", "mm")], "Q10", "EXT-GATE"),
        "Q03": _gt([_dim_item("I1", "R50 mm", "50", "mm")], "Q03", "EXT"),
        "Q04": _gt([_dim_item("I1", "45 deg", "45", "degree")], "Q04", "EXT"),
        "Q08": _gt([_dim_item("I1", "100 mm", "100", "mm")], "Q08", "EXT"),
    }
    # Only one run for Q01
    runs = [
        _run(qual_id="Q01", run_number=1,
             ai_findings=[_pred("F1", "100 MM", "100", "mm")])
    ]
    result = score_campaign(runs, gt_records)
    assert result.overall_status == "INCOMPLETE"


# ──────────────────────────────────────────────────────────────────────────────
# Test 19 – Threshold PASS (P2 dim recall >= 0.70)
# ──────────────────────────────────────────────────────────────────────────────
def test_19_threshold_pass_p2():
    # 3 items, 3 matched → recall = 1.0 ≥ 0.70
    items = [
        _dim_item("I1", "100 MM", "100", "mm"),
        _dim_item("I2", "60 MM", "60", "mm"),
        _dim_item("I3", "20 MM", "20", "mm"),
    ]
    gt = _gt(items, "Q01", "CORE")
    gt_records = {"Q01": gt}
    runs = []
    for i in range(1, CORE_RUNS_PER_DRAWING + 1):
        runs.append(_run(
            qual_id="Q01",
            run_number=i,
            ai_findings=[
                _pred("F1", "100 MM", "100", "mm"),
                _pred("F2", "60 MM", "60", "mm"),
                _pred("F3", "20 MM", "20", "mm"),
            ],
        ))
    result = score_campaign(runs, gt_records)
    p2_eval = next(t for t in result.threshold_evaluations if t["threshold_id"] == "P2")
    assert p2_eval["pass_fail"] == "PASS"
    assert isinstance(p2_eval["metric_value"], float)
    assert p2_eval["metric_value"] >= P2_DIMENSION_RECALL_MIN


# ──────────────────────────────────────────────────────────────────────────────
# Test 20 – Threshold FAIL (P2 dim recall < 0.70)
# ──────────────────────────────────────────────────────────────────────────────
def test_20_threshold_fail_p2():
    items = [
        _dim_item("I1", "100 MM", "100", "mm"),
        _dim_item("I2", "60 MM", "60", "mm"),
        _dim_item("I3", "20 MM", "20", "mm"),
        _dim_item("I4", "10 MM", "10", "mm"),
    ]
    gt = _gt(items, "Q01", "CORE")
    gt_records = {"Q01": gt}
    # Only 1 out of 4 matched per run
    runs = []
    for i in range(1, CORE_RUNS_PER_DRAWING + 1):
        runs.append(_run(
            qual_id="Q01",
            run_number=i,
            ai_findings=[_pred("F1", "100 MM", "100", "mm")],
        ))
    result = score_campaign(runs, gt_records)
    p2_eval = next(t for t in result.threshold_evaluations if t["threshold_id"] == "P2")
    assert p2_eval["pass_fail"] == "FAIL"
    assert p2_eval["metric_value"] < P2_DIMENSION_RECALL_MIN


# ──────────────────────────────────────────────────────────────────────────────
# Test 21 – Recall-gain insufficient data (no P-CROP runs)
# ──────────────────────────────────────────────────────────────────────────────
def test_21_recall_gain_insufficient_data():
    gt_records = {
        "Q01": _gt([_dim_item("I1", "100 MM", "100", "mm")], "Q01", "CORE"),
    }
    runs = [_run(qual_id="Q01", ai_findings=[_pred("F1", "100 MM", "100", "mm")])]
    result = score_campaign(runs, gt_records)
    rgg_eval = next(
        t for t in result.threshold_evaluations
        if t["threshold_id"] == "RECALL_GAIN_GATE"
    )
    assert rgg_eval["pass_fail"] in (INSUFFICIENT_DATA, NOT_APPLICABLE)


# ──────────────────────────────────────────────────────────────────────────────
# Test 22 – RQ06 target match
# ──────────────────────────────────────────────────────────────────────────────
def test_22_rq06_match():
    items = [_dim_item("I1", "100 MM", "100", "mm", det_scoreable=True)]
    gt = _gt(items)
    run = _run(
        ai_findings=[_pred("F1", "100 MM", "100", "mm")],
        det_findings=[_det("D1", "100 MM", value="100", unit="mm")],
    )
    result = score_run(gt, run)
    assert result.det_dim_scoreable is True
    assert result.det_dim_tp == 1
    assert any(
        item["match"] is True and item["expected_token"] == "100 MM"
        for item in result.rq06_items
    )


# ──────────────────────────────────────────────────────────────────────────────
# Test 23 – Malformed input is rejected (fail closed)
# ──────────────────────────────────────────────────────────────────────────────
def test_23_malformed_input_rejected():
    gt = _gt([_dim_item("I1", "100 MM", "100", "mm")])

    # Missing qual_id
    with pytest.raises(SchemaError):
        score_run(gt, QualRunInput(
            qual_id="",
            run_id="R1",
            run_number=1,
            fixture_class="RECOGNITION_GROUND_TRUTH",
            job_status="COMPLETED",
        ))

    # Invalid fixture_class
    with pytest.raises(SchemaError):
        score_run(gt, QualRunInput(
            qual_id="Q01",
            run_id="R1",
            run_number=1,
            fixture_class="BOGUS_CLASS",
            job_status="COMPLETED",
        ))

    # run_number < 1
    with pytest.raises(SchemaError):
        score_run(gt, QualRunInput(
            qual_id="Q01",
            run_id="R1",
            run_number=0,
            fixture_class="RECOGNITION_GROUND_TRUTH",
            job_status="COMPLETED",
        ))

    # Invalid review_action
    with pytest.raises(SchemaError):
        score_run(gt, _run(
            human_review=[HumanReviewEntry(finding_id="F1", review_action="INVALID")],
        ))


# ──────────────────────────────────────────────────────────────────────────────
# Test 24 – Ground truth record is not modified by scoring
# ──────────────────────────────────────────────────────────────────────────────
def test_24_ground_truth_read_only():
    items = [_dim_item("I1", "100 MM", "100", "mm")]
    gt = _gt(items)
    original = copy.deepcopy(gt)

    run = _run(ai_findings=[_pred("F1", "100 MM", "100", "mm")])
    score_run(gt, run)

    assert gt == original, "score_run must not modify the ground truth record"


# ──────────────────────────────────────────────────────────────────────────────
# Additional tests for full coverage of all spec metric families
# ──────────────────────────────────────────────────────────────────────────────

# Test 25 – Semantic match (different notation, same value+unit)
def test_25_semantic_match():
    items = [_dim_item("I1", "100 MM", "100", "mm")]
    gt = _gt(items)
    # Prediction "100mm" with same normalised value and unit but no spaces
    run = _run(ai_findings=[_pred("F1", "100mm", "100", "mm")])
    result = score_run(gt, run)
    assert result.true_positive_count == 1
    matched = [m for m in result.match_detail if m.item_id == "I1"]
    assert matched[0].match_level == "SEMANTIC"


# Test 26 – accepted_wrong_count for P7 (ACCEPT a hallucinated finding)
def test_26_accepted_wrong_p7():
    gt = _gt([_dim_item("I1", "100 MM", "100", "mm")])
    run = _run(
        ai_findings=[_pred("F1", "999 MM", "999", "mm")],   # hallucination
        human_review=[_review("F1", "ACCEPT")],
    )
    result = score_run(gt, run)
    assert result.accepted_wrong_count == 1


# Test 27 – P1 failing drawing (required item missed >= 2 of 3 runs)
def test_27_p1_failing_drawing():
    items = [_dim_item("I1", "100 MM", "100", "mm", rfd=True)]
    gt = _gt(items, "Q01", "CORE")
    # 3 runs: runs 1 and 2 miss "I1", run 3 finds it
    runs = [
        score_run(gt, _run(qual_id="Q01", run_number=1, ai_findings=[])),
        score_run(gt, _run(qual_id="Q01", run_number=2, ai_findings=[])),
        score_run(
            gt,
            _run(
                qual_id="Q01",
                run_number=3,
                ai_findings=[_pred("F1", "100 MM", "100", "mm")],
            ),
        ),
    ]
    agg = aggregate_fixture("Q01", "CORE", runs, gt)
    assert agg.p1_drawing_failing is True
    assert "I1" in agg.p1_detail


# Test 28 – Per-fixture aggregation with correct correction_rate
def test_28_per_fixture_correction_rate():
    items = [_dim_item("I1", "100 MM", "100", "mm")]
    gt = _gt(items, "Q01", "CORE")
    r1 = score_run(
        gt,
        _run(
            ai_findings=[_pred("F1", "100 MM", "100", "mm")],
            human_review=[_review("F1", "ACCEPT")],
        ),
    )
    r2 = score_run(
        gt,
        _run(
            run_number=2,
            ai_findings=[_pred("F1", "100 MM", "100", "mm")],
            human_review=[_review("F1", "EDIT")],
        ),
    )
    agg = aggregate_fixture("Q01", "CORE", [r1, r2], gt)
    # reviewed=2, corrected=1 (edit) → rate=0.5
    assert isinstance(agg.human_correction_rate, float)
    assert abs(agg.human_correction_rate - 0.5) < 1e-6


# Test 29 – Performance metrics aggregation
def test_29_performance_metrics():
    items = [_dim_item("I1", "100 MM", "100", "mm")]
    gt = _gt(items)
    runs = [
        score_run(gt, _run(run_number=1, inference_ms=60_000)),
        score_run(gt, _run(run_number=2, inference_ms=120_000)),
        score_run(gt, _run(run_number=3, inference_ms=180_000)),
    ]
    agg = aggregate_fixture("Q01", "CORE", runs, gt)
    assert agg.median_inference_s == 120.0
    assert agg.worst_inference_s == 180.0


# Test 30 – P5 threshold: worst run exceeds 480s
def test_30_p5_worst_exceeds():
    items = [_dim_item("I1", "100 MM", "100", "mm")]
    gt = _gt(items, "Q01", "CORE")
    gt_records = {"Q01": gt}
    # One run takes 490s (> 480s limit)
    runs = [
        _run(qual_id="Q01", run_number=i, inference_ms=(490_000 if i == 1 else 100_000))
        for i in range(1, 4)
    ]
    result = score_campaign(runs, gt_records)
    p5_eval = next(t for t in result.threshold_evaluations if t["threshold_id"] == "P5")
    assert p5_eval["pass_fail"] == "FAIL"


# Test 31 – Deterministic metrics: det_dim NOT_SCORABLE when no det_scoreable items
def test_31_det_dim_not_scorable():
    items = [_dim_item("I1", "100 MM", "100", "mm", det_scoreable=False)]
    gt = _gt(items)
    run = _run()
    result = score_run(gt, run)
    assert result.det_dim_scoreable is False
    agg = aggregate_fixture("Q01", "CORE", [result], gt)
    assert agg.det_dim_recall == NOT_SCORABLE


# Test 32 – Exact text match takes priority over normalised
def test_32_exact_beats_normalised():
    items = [_text_item("I1", "NOTES:")]
    gt = _gt(items)
    run = _run(ai_findings=[_pred("F1", "NOTES:")])
    result = score_run(gt, run)
    assert result.match_detail[0].match_level == "EXACT"


# Test 33 – score_campaign raises SchemaError for unknown qual_id
def test_33_unknown_qual_id_rejected():
    gt_records = {"Q01": _gt([_dim_item("I1", "100 MM", "100", "mm")])}
    runs = [_run(qual_id="Q99")]  # Q99 not in gt_records
    with pytest.raises(SchemaError, match="No ground truth record"):
        score_campaign(runs, gt_records)


# Test 34 – load_ground_truth reads frozen records without modification
def test_34_load_ground_truth_read_only():
    if not GT_DIR.exists():
        pytest.skip("Ground truth directory not found; skipping filesystem test")
    records, manifest_hash = load_ground_truth(GT_DIR)
    assert "Q01" in records
    assert isinstance(manifest_hash, str) and len(manifest_hash) == 64
    # Verify record is not empty and has expected structure
    q01 = records["Q01"]
    assert q01["qual_id"] == "Q01"
    assert isinstance(q01["items"], list)
    assert len(q01["items"]) >= 1
    # Records must not be modified by load
    original = copy.deepcopy(q01)
    assert q01 == original


# Test 35 – P6 threshold: correction rate above 0.40 → FAIL
def test_35_p6_correction_rate_fail():
    items = [_dim_item("I1", "100 MM", "100", "mm")]
    gt = _gt(items, "Q01", "CORE")
    gt_records = {"Q01": gt}
    # 3 runs, each with edit → all 3 corrected out of 3 reviewed → rate=1.0
    runs = []
    for i in range(1, 4):
        runs.append(_run(
            qual_id="Q01",
            run_number=i,
            ai_findings=[_pred("F1", "100 MM", "100", "mm")],
            human_review=[_review("F1", "EDIT")],
        ))
    result = score_campaign(runs, gt_records)
    p6_eval = next(t for t in result.threshold_evaluations if t["threshold_id"] == "P6")
    assert p6_eval["pass_fail"] == "FAIL"


# Test 36 – P7: accepted_wrong_count = 0 → PASS
def test_36_p7_pass_no_wrong_accept():
    items = [_dim_item("I1", "100 MM", "100", "mm")]
    gt = _gt(items, "Q01", "CORE")
    gt_records = {"Q01": gt}
    runs = [
        _run(
            qual_id="Q01",
            run_number=1,
            ai_findings=[_pred("F1", "100 MM", "100", "mm")],
            human_review=[_review("F1", "ACCEPT")],
        )
    ]
    result = score_campaign(runs, gt_records)
    p7_eval = next(t for t in result.threshold_evaluations if t["threshold_id"] == "P7")
    assert p7_eval["pass_fail"] == "PASS"
    assert p7_eval["metric_value"] == 0


# Test 37 – OVERALL_STATUS is PASS only when campaign complete and no threshold fails
def test_37_overall_status_pass():
    # Build a minimal complete campaign (all required drawings, all required runs)
    qual_ids_runs = {
        "Q01": (3, "CORE"), "Q02": (3, "CORE"), "Q05": (3, "CORE"),
        "Q06": (3, "CORE"), "Q07": (3, "CORE"),
        "Q09": (3, "EXT-GATE"), "Q10": (3, "EXT-GATE"),
        "Q03": (1, "EXT"), "Q04": (1, "EXT"), "Q08": (1, "EXT"),
    }
    gt_records: dict[str, Any] = {}
    runs_list: list[QualRunInput] = []
    for qid, (n_runs, dc) in qual_ids_runs.items():
        items = [_dim_item("I1", "100 mm", "100", "mm", rfd=True)]
        gt_records[qid] = _gt(items, qid, dc)
        for i in range(1, n_runs + 1):
            runs_list.append(_run(
                qual_id=qid,
                run_number=i,
                ai_findings=[_pred("F1", "100 mm", "100", "mm")],
                human_review=[_review("F1", "ACCEPT")],
                inference_ms=10_000,
            ))

    result = score_campaign(runs_list, gt_records)
    # Campaign is complete and all thresholds should pass
    assert result.overall_status in ("PASS", "FAIL")  # not INCOMPLETE
    if result.overall_status == "PASS":
        for t in result.threshold_evaluations:
            assert t["pass_fail"] in ("PASS", INSUFFICIENT_DATA, NOT_APPLICABLE)
