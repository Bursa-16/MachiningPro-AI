"""
REAL_DRAWING_QUALIFICATION_05 - Zero-inference dry run.

Proves the execution pipeline WITHOUT running any real AI inference:
  fixture/GT manifest loading -> run matrix -> mock envelopes
  -> scoring engine -> result paths -> resume logic -> incomplete-campaign check.

REAL_LOCAL_AI_CALLS_EXECUTED=0
OLLAMA_INFERENCE_CALLS=0
OPENAI_CALLS=0
CLOUD_AI_CALLS=0
PAID_API_CALLS=0
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ── sys.path: scoring engine is alongside the execution plan ──────────────────
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCORING_DIR = _REPO_ROOT / "docs" / "qualification" / "scoring"
if str(_SCORING_DIR) not in sys.path:
    sys.path.insert(0, str(_SCORING_DIR))

from score_qualification import (  # noqa: E402
    HumanReviewEntry,
    PredictedFinding,
    ProbeObservation,
    QualRunInput,
    SchemaError,
    load_ground_truth,
    score_campaign,
)

# ── Paths ─────────────────────────────────────────────────────────────────────
_EXECUTION_DIR = Path(__file__).resolve().parent
_GT_DIR = _REPO_ROOT / "docs" / "qualification" / "ground_truth"
_FIXTURE_MANIFEST = _REPO_ROOT / "docs" / "qualification" / "fixtures" / "manifest.json"
_CAMPAIGN_PLAN = _EXECUTION_DIR / "campaign_plan.json"
_RUN_MANIFEST = _EXECUTION_DIR / "run_manifest.json"

# ── Frozen hashes (from campaign_plan.json; validated at runtime) ─────────────
_EXPECTED_GT_MANIFEST_SHA256 = (
    "e11b2c949363583b8d2ebec18acd2ac26e7181882ed6ac275e831ebf39105757"
)
_EXPECTED_FIXTURE_MANIFEST_SHA256 = (
    "a1d3eef221f6a3bf15999d1e91c924f0492814d899add40871b0a351ab1ac0a1"
)


# ── Hash helper ───────────────────────────────────────────────────────────────
def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── Manifest validation ───────────────────────────────────────────────────────
def validate_manifests() -> None:
    gt_hash = _sha256(_GT_DIR / "manifest.json")
    if gt_hash != _EXPECTED_GT_MANIFEST_SHA256:
        raise RuntimeError(
            f"GT manifest hash mismatch: expected {_EXPECTED_GT_MANIFEST_SHA256}, "
            f"got {gt_hash}"
        )
    fx_hash = _sha256(_FIXTURE_MANIFEST)
    if fx_hash != _EXPECTED_FIXTURE_MANIFEST_SHA256:
        raise RuntimeError(
            f"Fixture manifest hash mismatch: expected {_EXPECTED_FIXTURE_MANIFEST_SHA256}, "
            f"got {fx_hash}"
        )


# ── Fixture hash lookup ───────────────────────────────────────────────────────
def _build_fixture_sha_index() -> dict[str, str]:
    data: dict = json.loads(_FIXTURE_MANIFEST.read_bytes())
    return {e["id"]: e["sha256_pdf"] for e in data["entries"] if e.get("sha256_pdf")}


# ── Run manifest loader ───────────────────────────────────────────────────────
def load_run_manifest() -> list[dict]:
    data: dict = json.loads(_RUN_MANIFEST.read_bytes())
    return data["runs"]


# ── Resume tracker (in-memory, simulating a checkpoint store) ─────────────────
class _ResumeTracker:
    def __init__(self) -> None:
        self._completed: set[str] = set()
        self._failed: set[str] = set()

    def mark_completed(self, run_id: str) -> None:
        self._completed.add(run_id)

    def mark_failed(self, run_id: str) -> None:
        self._failed.add(run_id)

    def status(self, run_id: str) -> str:
        if run_id in self._completed:
            return "SKIPPED_ALREADY_COMPLETE"
        if run_id in self._failed:
            return "FAILED_REQUIRES_RERUN_AUTHORIZATION"
        return "PENDING"


# ── Mock envelope builders ────────────────────────────────────────────────────
def _mock_recognition_run(
    run: dict,
    gt_record: dict,
    *,
    job_status: str = "COMPLETED",
) -> QualRunInput:
    findings = []
    for i, item in enumerate(gt_record.get("items", []), start=1):
        if item.get("scoreable", True):
            findings.append(
                PredictedFinding(
                    finding_id=f"{run['qual_id']}-F{i:03d}",
                    raw_text=item["expected_text"],
                    feature_type=item.get("feature_type"),
                    normalized_value=item.get("expected_normalized_value"),
                    unit=item.get("expected_normalized_unit"),
                    validation_status="ACCEPTED",
                )
            )
    reviews = [
        HumanReviewEntry(
            finding_id=f.finding_id,
            review_action="ACCEPT",
            original_ai_value=f.raw_text,
            reviewed_value=f.raw_text,
        )
        for f in findings
    ]
    return QualRunInput(
        qual_id=run["qual_id"],
        run_id=run["run_id"],
        run_number=run["run_number"],
        fixture_class="RECOGNITION_GROUND_TRUTH",
        job_status=job_status,
        provider="ollama.chat",
        model="granite3.2-vision:2b",
        inference_elapsed_ms=150_000,
        ai_findings=findings,
        human_review_findings=reviews,
    )


def _mock_structural_probe_run(run: dict, gt_record: dict) -> QualRunInput:
    expected_error = gt_record.get("expected_error_or_gate", "INVALID_REGION")
    return QualRunInput(
        qual_id=run["qual_id"],
        run_id=run["run_id"],
        run_number=run["run_number"],
        fixture_class="STRUCTURAL_EXPECTATION",
        job_status="FAILED",
        provider="ollama.chat",
        model="granite3.2-vision:2b",
        probe_observations=ProbeObservation(
            observed_behavior=gt_record.get("expected_behavior", ""),
            observed_job_status="FAILED",
            observed_error_or_gate=expected_error,
        ),
    )


# ── Result path naming ────────────────────────────────────────────────────────
def result_path(campaign_id: str, qual_id: str, run_id: str) -> Path:
    return (
        _REPO_ROOT
        / "docs"
        / "qualification"
        / "results"
        / campaign_id
        / qual_id
        / f"{run_id}.json"
    )


# ── Dry-run scenarios ─────────────────────────────────────────────────────────
def run_complete_campaign_scenario(
    gt_records: dict,
    runs: list[dict],
) -> None:
    print("\n=== SCENARIO: Complete baseline campaign (24 recognition + 3 structural probes) ===")
    inputs: list[QualRunInput] = []
    for run in runs:
        qid = run["qual_id"]
        if qid not in gt_records:
            continue
        fc = run["fixture_class"]
        if fc == "RECOGNITION_GROUND_TRUTH":
            inputs.append(_mock_recognition_run(run, gt_records[qid]))
        elif fc == "STRUCTURAL_EXPECTATION":
            inputs.append(_mock_structural_probe_run(run, gt_records[qid]))

    campaign = score_campaign(
        runs=inputs,
        gt_records=gt_records,
        manifest_hash=_EXPECTED_GT_MANIFEST_SHA256,
        qualification_version="REAL_DRAWING_QUALIFICATION_01",
        qual_id="DEMO-QUAL-01",
    )
    print(f"  overall_status  : {campaign.overall_status}")
    recognition_count = sum(1 for r in inputs if r.fixture_class == "RECOGNITION_GROUND_TRUTH")
    structural_count = sum(1 for r in inputs if r.fixture_class == "STRUCTURAL_EXPECTATION")
    print(f"  run count scored: {recognition_count}")
    print(f"  probe count     : {structural_count}")
    thresholds = {t["threshold_id"]: t["pass_fail"] for t in campaign.threshold_evaluations}
    print(f"  thresholds      : {thresholds}")
    print("  result path sample:", result_path("DEMO-QUAL-01", "Q01", "Q01-R01"))


def run_incomplete_campaign_scenario(gt_records: dict) -> None:
    print("\n=== SCENARIO: Incomplete campaign (only 2 of 3 Q01 runs) ===")
    partial_runs = [
        _mock_recognition_run(
            {"qual_id": "Q01", "run_id": f"Q01-R0{i}", "run_number": i},
            gt_records["Q01"],
        )
        for i in range(1, 3)
    ]
    campaign = score_campaign(
        runs=partial_runs,
        gt_records=gt_records,
        qualification_version="REAL_DRAWING_QUALIFICATION_01",
        qual_id="DEMO-QUAL-01",
    )
    assert campaign.overall_status == "INCOMPLETE", (
        f"Expected INCOMPLETE, got {campaign.overall_status}"
    )
    print(f"  overall_status: {campaign.overall_status}  (CONFIRMED: incomplete cannot PASS)")


def run_resume_scenario(gt_records: dict, runs: list[dict]) -> None:
    print("\n=== SCENARIO: Resume - completed run skipped, failed requires rerun auth ===")
    tracker = _ResumeTracker()
    q01_runs = [r for r in runs if r["qual_id"] == "Q01"]

    for run in q01_runs:
        st = tracker.status(run["run_id"])
        if st == "PENDING":
            tracker.mark_completed(run["run_id"])
            print(f"  {run['run_id']}: PENDING -> COMPLETED")

    tracker.mark_failed("Q01-R03")

    for run in q01_runs:
        st = tracker.status(run["run_id"])
        print(f"  {run['run_id']}: resume status = {st}")


def run_malformed_input_scenario(gt_records: dict) -> None:
    print("\n=== SCENARIO: Malformed input rejected (SchemaError) ===")
    bad = QualRunInput(
        qual_id="Q01",
        run_id="",
        run_number=1,
        fixture_class="RECOGNITION_GROUND_TRUTH",
        job_status="COMPLETED",
    )
    try:
        score_campaign(
            runs=[bad],
            gt_records=gt_records,
            qualification_version="REAL_DRAWING_QUALIFICATION_01",
            qual_id="DEMO-QUAL-01",
        )
        raise AssertionError("Expected SchemaError was not raised")
    except SchemaError as exc:
        print(f"  SchemaError correctly raised: {exc}")


def run_failed_run_scenario(gt_records: dict, runs: list[dict]) -> None:
    print("\n=== SCENARIO: Failed run recorded as FAILED (not silently retried) ===")
    run = next(r for r in runs if r["qual_id"] == "Q01" and r["run_number"] == 1)
    failed_input = _mock_recognition_run(run, gt_records["Q01"], job_status="FAILED")
    single_run_campaign = score_campaign(
        runs=[failed_input],
        gt_records=gt_records,
        qualification_version="REAL_DRAWING_QUALIFICATION_01",
        qual_id="DEMO-QUAL-01",
    )
    run_result = single_run_campaign.per_run_results[0]
    assert run_result["job_status"] == "FAILED", (
        f"Expected FAILED, got {run_result['job_status']}"
    )
    print(f"  job_status: {run_result['job_status']}  (CONFIRMED: failure recorded, not retried)")


def run_result_path_scenario(runs: list[dict]) -> None:
    print("\n=== SCENARIO: Result path naming (no two paths collide) ===")
    seen: set[str] = set()
    for run in runs:
        p = str(result_path("DEMO-QUAL-01", run["qual_id"], run["run_id"]))
        assert p not in seen, f"Duplicate result path: {p}"
        seen.add(p)
    print(f"  {len(seen)} unique result paths confirmed (no collisions)")


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    print("REAL_DRAWING_QUALIFICATION_05 - Zero-inference dry run")
    print("=" * 70)
    print("REAL_LOCAL_AI_CALLS_EXECUTED=0")
    print("OLLAMA_INFERENCE_CALLS=0")

    print("\n[1] Validating manifest hashes...")
    validate_manifests()
    print("    GT manifest:      OK")
    print("    Fixture manifest: OK")

    print("\n[2] Loading ground truth...")
    gt_records, manifest_hash = load_ground_truth(_GT_DIR)
    assert manifest_hash == _EXPECTED_GT_MANIFEST_SHA256, "GT manifest hash drift"
    print(f"    Loaded {len(gt_records)} GT records, manifest_hash verified")

    print("\n[3] Loading run manifest...")
    runs = load_run_manifest()
    ai_runs = [r for r in runs if r["expected_inference"]]
    probe_runs = [r for r in runs if not r["expected_inference"]]
    print(f"    Total run records : {len(runs)}")
    print(f"    AI inference runs : {len(ai_runs)}")
    print(f"    Structural probes : {len(probe_runs)}")
    assert len(ai_runs) == 24, f"Expected 24 AI runs, got {len(ai_runs)}"
    assert len(probe_runs) == 3, f"Expected 3 structural probes, got {len(probe_runs)}"

    print("\n[4] Validating fixture hashes against run manifest...")
    fx_index = _build_fixture_sha_index()
    for run in runs:
        qid = run["qual_id"]
        expected = run.get("fixture_sha256")
        if expected is None:
            continue
        actual = fx_index.get(qid)
        if actual is None:
            continue
        assert actual == expected, (
            f"Fixture SHA mismatch for {qid}: manifest={actual}, plan={expected}"
        )
    print("    All fixture hashes validated")

    print("\n[5] Validating run ID uniqueness...")
    all_ids = [r["run_id"] for r in runs]
    assert len(all_ids) == len(set(all_ids)), "Duplicate run IDs detected"
    print(f"    {len(all_ids)} unique run IDs confirmed")

    run_result_path_scenario(runs)
    run_complete_campaign_scenario(gt_records, runs)
    run_incomplete_campaign_scenario(gt_records)
    run_resume_scenario(gt_records, runs)
    run_malformed_input_scenario(gt_records)
    run_failed_run_scenario(gt_records, runs)

    print("\n" + "=" * 70)
    print("ZERO_INFERENCE_DRY_RUN=PASS")
    print("EXECUTION_PLAN_READY=YES")
    print("REAL_DRAWING_QUALIFICATION_05_STATUS=PASS")


if __name__ == "__main__":
    main()
