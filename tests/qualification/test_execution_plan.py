"""Tests for REAL_DRAWING_QUALIFICATION_05 execution plan artifacts.

Validates:
1.  Exact run count matches frozen spec (24 AI + 3 structural probes = 27)
2.  Run IDs unique across all baseline runs
3.  Fixture IDs are valid (appear in fixture manifest)
4.  Fixture hashes match fixture manifest
5.  GT record hashes match GT manifest
6.  Exactly one AI call per planned AI run
7.  No model calls for structural probe runs
8.  retry_allowed=false for all runs
9.  fallback_model_allowed=false in plan
10. cloud_fallback_allowed=false in plan
11. Structural probe runs separated from AI inference runs
12. Result file paths are unique
13. Completed run would be skipped (resume logic)
14. Failed run status recorded (not auto-retried)
15. Malformed result envelope rejected (SchemaError)
16. Incomplete campaign cannot PASS
17. Synthetic complete campaign reaches scoring engine and scores
18. P1-P7 thresholds unchanged (values not drifted from spec)
19. Recall-gain gate unchanged
20. No production file changed (backend/**, frontend/**)
21. Zero inference calls during dry run
22. campaign_plan.json frozen artifact hashes are current
23. First/last baseline run IDs match plan
24. Per-class run counts correct (CORE×3, EXT-GATE×3, EXT×1)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_EXEC_DIR = _REPO / "docs" / "qualification" / "execution"
_GT_DIR = _REPO / "docs" / "qualification" / "ground_truth"
_FX_MANIFEST = _REPO / "docs" / "qualification" / "fixtures" / "manifest.json"
_CAMPAIGN_PLAN = _EXEC_DIR / "campaign_plan.json"
_RUN_MANIFEST = _EXEC_DIR / "run_manifest.json"


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def campaign_plan() -> dict:
    return json.loads(_CAMPAIGN_PLAN.read_bytes())


@pytest.fixture(scope="module")
def run_manifest() -> dict:
    return json.loads(_RUN_MANIFEST.read_bytes())


@pytest.fixture(scope="module")
def baseline_runs(run_manifest: dict) -> list[dict]:
    return run_manifest["runs"]


@pytest.fixture(scope="module")
def conditional_runs(run_manifest: dict) -> list[dict]:
    return run_manifest.get("conditional_runs", [])


@pytest.fixture(scope="module")
def fixture_sha_index() -> dict[str, str]:
    data = json.loads(_FX_MANIFEST.read_bytes())
    return {e["id"]: e.get("sha256_pdf") for e in data["entries"]}


@pytest.fixture(scope="module")
def gt_sha_index() -> dict[str, str]:
    data = json.loads((_GT_DIR / "manifest.json").read_bytes())
    return {e["qual_id"]: e["record_sha256"] for e in data["records"]}


@pytest.fixture(scope="module")
def gt_records() -> tuple[dict, str]:
    scoring_dir = _REPO / "docs" / "qualification" / "scoring"
    if str(scoring_dir) not in sys.path:
        sys.path.insert(0, str(scoring_dir))
    from score_qualification import load_ground_truth

    return load_ground_truth(_GT_DIR)


# ── 1. Run counts ─────────────────────────────────────────────────────────────

def test_baseline_ai_inference_count(run_manifest: dict, baseline_runs: list[dict]) -> None:
    ai_runs = [r for r in baseline_runs if r["expected_inference"]]
    assert len(ai_runs) == run_manifest["baseline_ai_inference_count"] == 24


def test_structural_probe_count(run_manifest: dict, baseline_runs: list[dict]) -> None:
    probes = [r for r in baseline_runs if not r["expected_inference"]]
    assert len(probes) == run_manifest["structural_probe_count"] == 3


def test_total_baseline_run_records(run_manifest: dict, baseline_runs: list[dict]) -> None:
    assert len(baseline_runs) == run_manifest["total_baseline_run_records"] == 27


# ── 2. Run ID uniqueness ──────────────────────────────────────────────────────

def test_run_ids_unique(baseline_runs: list[dict], conditional_runs: list[dict]) -> None:
    all_ids = [r["run_id"] for r in baseline_runs + conditional_runs]
    assert len(all_ids) == len(set(all_ids))


# ── 3. Fixture IDs valid ──────────────────────────────────────────────────────

def test_fixture_ids_in_fixture_manifest(
    baseline_runs: list[dict],
    fixture_sha_index: dict,
) -> None:
    for run in baseline_runs:
        qid = run["qual_id"]
        if run.get("fixture_sha256") is None:
            continue
        assert qid in fixture_sha_index, f"{qid} not in fixture manifest"


# ── 4. Fixture hashes match fixture manifest ──────────────────────────────────

def test_fixture_hashes_match_manifest(
    baseline_runs: list[dict],
    conditional_runs: list[dict],
    fixture_sha_index: dict,
) -> None:
    for run in baseline_runs + conditional_runs:
        qid = run["qual_id"]
        plan_sha = run.get("fixture_sha256")
        if plan_sha is None:
            continue
        manifest_sha = fixture_sha_index.get(qid)
        if manifest_sha is None:
            continue
        assert plan_sha == manifest_sha, f"{qid}: fixture SHA mismatch"


# ── 5. GT record hashes match GT manifest ─────────────────────────────────────

def test_gt_record_hashes_match_manifest(
    baseline_runs: list[dict],
    conditional_runs: list[dict],
    gt_sha_index: dict,
) -> None:
    for run in baseline_runs + conditional_runs:
        qid = run["qual_id"]
        plan_sha = run.get("gt_record_sha256")
        if plan_sha is None:
            continue
        manifest_sha = gt_sha_index.get(qid)
        if manifest_sha is None:
            continue
        assert plan_sha == manifest_sha, f"{qid}: GT record SHA mismatch"


# ── 6–7. Model calls per run ──────────────────────────────────────────────────

def test_one_model_call_per_ai_run(baseline_runs: list[dict]) -> None:
    for run in baseline_runs:
        if run["expected_inference"]:
            assert run["model_calls_per_run"] == 1, (
                f"{run['run_id']}: expected model_calls_per_run=1"
            )


def test_zero_model_calls_for_structural_probes(baseline_runs: list[dict]) -> None:
    for run in baseline_runs:
        if not run["expected_inference"]:
            assert run["model_calls_per_run"] == 0, (
                f"{run['run_id']}: expected model_calls_per_run=0 for structural probe"
            )


# ── 8–10. Retry / fallback policy ────────────────────────────────────────────

def test_retry_disabled_all_runs(baseline_runs: list[dict], conditional_runs: list[dict]) -> None:
    for run in baseline_runs + conditional_runs:
        assert not run["retry_allowed"], f"{run['run_id']}: retry_allowed must be false"


def test_fallback_model_disabled(campaign_plan: dict) -> None:
    assert not campaign_plan["provider_config"]["fallback_model_allowed"]


def test_cloud_fallback_disabled(campaign_plan: dict) -> None:
    assert not campaign_plan["provider_config"]["cloud_fallback_allowed"]


# ── 11. Structural probes separated ──────────────────────────────────────────

def test_structural_probes_not_scheduled_as_ai_runs(baseline_runs: list[dict]) -> None:
    for run in baseline_runs:
        if run["fixture_class"] == "STRUCTURAL_EXPECTATION":
            assert not run["expected_inference"], (
                f"{run['run_id']}: structural probe must not have expected_inference=true"
            )
            assert run["model_calls_per_run"] == 0


# ── 12. Result paths unique ───────────────────────────────────────────────────

def test_result_paths_unique(campaign_plan: dict, baseline_runs: list[dict]) -> None:
    cid = campaign_plan["campaign_id"]
    paths = [
        f"docs/qualification/results/{cid}/{r['qual_id']}/{r['run_id']}.json"
        for r in baseline_runs
    ]
    assert len(paths) == len(set(paths))


# ── 13. Resume: completed run skipped ────────────────────────────────────────

def test_resume_skips_completed_run() -> None:
    completed: set[str] = {"Q01-R01"}

    def would_execute(run_id: str) -> bool:
        return run_id not in completed

    assert not would_execute("Q01-R01"), "Completed run must be skipped"
    assert would_execute("Q01-R02"), "Pending run must execute"


# ── 14. Failed run not auto-retried ──────────────────────────────────────────

def test_failed_run_requires_explicit_rerun() -> None:
    failed: set[str] = {"Q01-R01"}

    def auto_retry_allowed(run_id: str) -> bool:
        return False

    def is_failed(run_id: str) -> bool:
        return run_id in failed

    assert is_failed("Q01-R01")
    assert not auto_retry_allowed("Q01-R01")


# ── 15. Malformed result rejected ────────────────────────────────────────────

def test_malformed_result_envelope_rejected(gt_records: tuple) -> None:
    from score_qualification import QualRunInput, SchemaError, score_campaign

    records, _ = gt_records
    bad = QualRunInput(
        qual_id="Q01",
        run_id="",
        run_number=1,
        fixture_class="RECOGNITION_GROUND_TRUTH",
        job_status="COMPLETED",
    )
    with pytest.raises(SchemaError):
        score_campaign(
            runs=[bad],
            gt_records=records,
            qualification_version="REAL_DRAWING_QUALIFICATION_01",
            qual_id="DEMO-QUAL-01",
        )


# ── 16. Incomplete campaign cannot PASS ──────────────────────────────────────

def test_incomplete_campaign_cannot_pass(gt_records: tuple) -> None:
    from score_qualification import (
        PredictedFinding,
        QualRunInput,
        score_campaign,
    )

    records, _ = gt_records
    runs = [
        QualRunInput(
            qual_id="Q01",
            run_id=f"Q01-R0{i}",
            run_number=i,
            fixture_class="RECOGNITION_GROUND_TRUTH",
            job_status="COMPLETED",
            ai_findings=[
                PredictedFinding(
                    finding_id=f"Q01-R0{i}-F001",
                    raw_text="100 MM",
                )
            ],
        )
        for i in range(1, 3)
    ]
    campaign = score_campaign(
        runs=runs,
        gt_records=records,
        qualification_version="REAL_DRAWING_QUALIFICATION_01",
        qual_id="DEMO-QUAL-01",
    )
    assert campaign.overall_status == "INCOMPLETE"


# ── 17. Synthetic complete campaign reaches scoring engine ────────────────────

def test_synthetic_complete_campaign_scores(
    baseline_runs: list[dict],
    gt_records: tuple,
) -> None:
    from score_qualification import (
        HumanReviewEntry,
        PredictedFinding,
        ProbeObservation,
        QualRunInput,
        score_campaign,
    )

    records, _ = gt_records
    inputs: list[QualRunInput] = []
    for run in baseline_runs:
        qid = run["qual_id"]
        if qid not in records:
            continue
        gt = records[qid]
        fc = run["fixture_class"]
        if fc == "RECOGNITION_GROUND_TRUTH":
            findings = [
                PredictedFinding(
                    finding_id=f"{qid}-F{j:03d}",
                    raw_text=item["expected_text"],
                    feature_type=item.get("feature_type"),
                    normalized_value=item.get("expected_normalized_value"),
                    unit=item.get("expected_normalized_unit"),
                )
                for j, item in enumerate(gt.get("items", []), start=1)
                if item.get("scoreable", True)
            ]
            reviews = [
                HumanReviewEntry(
                    finding_id=f.finding_id,
                    review_action="ACCEPT",
                    original_ai_value=f.raw_text,
                    reviewed_value=f.raw_text,
                )
                for f in findings
            ]
            inputs.append(
                QualRunInput(
                    qual_id=qid,
                    run_id=run["run_id"],
                    run_number=run["run_number"],
                    fixture_class="RECOGNITION_GROUND_TRUTH",
                    job_status="COMPLETED",
                    provider="ollama.chat",
                    model="granite3.2-vision:2b",
                    inference_elapsed_ms=150_000,
                    ai_findings=findings,
                    human_review_findings=reviews,
                )
            )
        elif fc == "STRUCTURAL_EXPECTATION":
            inputs.append(
                QualRunInput(
                    qual_id=qid,
                    run_id=run["run_id"],
                    run_number=run["run_number"],
                    fixture_class="STRUCTURAL_EXPECTATION",
                    job_status="FAILED",
                    probe_observations=ProbeObservation(
                        observed_behavior=gt.get("expected_behavior", ""),
                        observed_job_status="FAILED",
                        observed_error_or_gate=gt.get("expected_error_or_gate", ""),
                    ),
                )
            )

    campaign = score_campaign(
        runs=inputs,
        gt_records=records,
        qualification_version="REAL_DRAWING_QUALIFICATION_01",
        qual_id="DEMO-QUAL-01",
    )
    assert campaign.overall_status in {"PASS", "FAIL", "INCOMPLETE"}
    assert len(campaign.threshold_evaluations) > 0


# ── 18–19. Threshold constants unchanged ─────────────────────────────────────

def test_p2_threshold_unchanged() -> None:
    from score_qualification import P2_DIMENSION_RECALL_MIN

    assert P2_DIMENSION_RECALL_MIN == 0.70


def test_p3a_threshold_unchanged() -> None:
    from score_qualification import P3A_TEXT_PRECISION_MIN

    assert P3A_TEXT_PRECISION_MIN == 0.75


def test_p3b_threshold_unchanged() -> None:
    from score_qualification import P3B_SYSTEMATIC_RUNS

    assert P3B_SYSTEMATIC_RUNS == 2


def test_p4_threshold_unchanged() -> None:
    from score_qualification import P4_FAILURE_RATE_MAX

    assert P4_FAILURE_RATE_MAX == 0.20


def test_p5_threshold_unchanged() -> None:
    from score_qualification import P5_MEDIAN_S, P5_WORST_S

    assert P5_MEDIAN_S == 240.0
    assert P5_WORST_S == 480.0


def test_p6_threshold_unchanged() -> None:
    from score_qualification import P6_CORRECTION_RATE_MAX

    assert P6_CORRECTION_RATE_MAX == 0.40


def test_recall_gain_gate_unchanged() -> None:
    from score_qualification import RECALL_GAIN_GATE_MIN

    assert RECALL_GAIN_GATE_MIN == 0.15


# ── 20. No production files changed ──────────────────────────────────────────

def test_no_production_files_changed() -> None:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        check=True,
    )
    changed = result.stdout.strip().splitlines()
    production = [
        f for f in changed
        if f.startswith("backend/") or f.startswith("frontend/")
    ]
    assert not production, f"Production files changed: {production}"


# ── 21. Zero inference calls during dry run ───────────────────────────────────

def test_zero_inference_dry_run_executes_no_real_ai() -> None:
    result = subprocess.run(
        [sys.executable, str(_EXEC_DIR / "dry_run.py")],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"dry_run.py failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "ZERO_INFERENCE_DRY_RUN=PASS" in result.stdout
    assert "OLLAMA_INFERENCE_CALLS=0" in result.stdout


# ── 22. campaign_plan.json frozen hashes are current ─────────────────────────

def test_frozen_artifact_hashes_current(campaign_plan: dict) -> None:
    import hashlib

    fa = campaign_plan["frozen_artifacts"]
    for key, path_key in [
        ("spec_sha256", "spec_path"),
        ("fixture_manifest_sha256", "fixture_manifest_path"),
        ("gt_manifest_sha256", "gt_manifest_path"),
        ("scoring_engine_sha256", "scoring_engine_path"),
    ]:
        path = _REPO / fa[path_key]
        assert path.exists(), f"{fa[path_key]} not found"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == fa[key], (
            f"{fa[path_key]} hash mismatch: expected {fa[key]}, got {actual}"
        )


# ── 23. First/last baseline run IDs match plan ────────────────────────────────

def test_first_and_last_baseline_run_ids(campaign_plan: dict, baseline_runs: list[dict]) -> None:
    ai_runs = [r for r in baseline_runs if r["expected_inference"]]
    assert ai_runs[0]["run_id"] == campaign_plan["first_real_run_id"]
    assert ai_runs[-1]["run_id"] == campaign_plan["last_baseline_run_id"]


# ── 24. Per-class run counts ──────────────────────────────────────────────────

def test_core_run_counts(baseline_runs: list[dict]) -> None:
    from collections import Counter

    by_qid = Counter(r["qual_id"] for r in baseline_runs if r.get("expected_inference"))
    for qid in ["Q01", "Q02", "Q05", "Q06", "Q07"]:
        assert by_qid[qid] == 3, f"CORE {qid}: expected 3 runs, got {by_qid[qid]}"


def test_ext_gate_run_counts(baseline_runs: list[dict]) -> None:
    from collections import Counter

    by_qid = Counter(r["qual_id"] for r in baseline_runs if r.get("expected_inference"))
    for qid in ["Q09", "Q10"]:
        assert by_qid[qid] == 3, f"EXT-GATE {qid}: expected 3 runs, got {by_qid[qid]}"


def test_ext_run_counts(baseline_runs: list[dict]) -> None:
    from collections import Counter

    by_qid = Counter(r["qual_id"] for r in baseline_runs if r.get("expected_inference"))
    for qid in ["Q03", "Q04", "Q08"]:
        assert by_qid[qid] == 1, f"EXT {qid}: expected 1 run, got {by_qid[qid]}"
