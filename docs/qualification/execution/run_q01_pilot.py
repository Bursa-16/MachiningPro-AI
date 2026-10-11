"""
REAL_DRAWING_QUALIFICATION_06A - Q01 three-run real local pilot.

Executes exactly 3 sequential inference runs on Q01 fixture using local Ollama
(granite3.2-vision:2b at loopback only). Scores each run against frozen GT.
Writes result and run-log artifacts. STOPS after Q01-R03.

Hardened by REAL_DRAWING_QUALIFICATION_06B:
  - Zero-inference readiness gate (see readiness_gate.py) runs before any
    scored RUN_ID is started. Gate failure aborts with PRECHECK_FAILED.
  - Existing result artifacts are immutable: re-running without a recovery ID
    raises ArtifactExistsError.
  - Recovery runs use authorised, traceable IDs (e.g. Q01-R01-RERUN-01).

Constraints (hard):
  REAL_LOCAL_AI_CALLS_EXECUTED=3  (Q01-R01, Q01-R02, Q01-R03)
  INFERENCE_SCOPE=Q01_ONLY
  OPENAI_CALLS=0
  CLOUD_AI_CALLS=0
  PAID_API_CALLS=0
  AUTOMATIC_RETRY_USED=NO
  FALLBACK_USED=NO
  COMMIT_PERFORMED=NO
  PUSH_PERFORMED=NO
  PRODUCTION_CODE_CHANGED=NO
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Must be set BEFORE any backend imports
os.environ["MACHININGPRO_AI_PROVIDER"] = "ollama"

_REPO = Path(__file__).resolve().parents[3]
_SCORING_DIR = _REPO / "docs" / "qualification" / "scoring"
_EXEC_DIR = Path(__file__).resolve().parent

if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_SCORING_DIR) not in sys.path:
    sys.path.insert(0, str(_SCORING_DIR))
if str(_EXEC_DIR) not in sys.path:
    sys.path.insert(0, str(_EXEC_DIR))

from readiness_gate import (  # noqa: E402
    ArtifactExistsError,
    ReadinessGateError,
    assert_artifact_absent,
    assert_ready,
    wait_for_readiness,
)

# ── Frozen constants ───────────────────────────────────────────────────────────
CAMPAIGN_ID = "DEMO-QUAL-01"
QUAL_ID = "Q01"
RUN_IDS = ["Q01-R01", "Q01-R02", "Q01-R03"]
PROVIDER = "ollama.chat"
MODEL = "granite3.2-vision:2b"

FIXTURE_PDF = _REPO / "docs/qualification/fixtures/pdf/Q01.pdf"
EXPECTED_FIXTURE_SHA = "690ec7c721c8a0425264aebef965c12297ff2d2aa0f05c8bc69674afc421fda7"
GT_DIR = _REPO / "docs/qualification/ground_truth"
EXPECTED_GT_MANIFEST_SHA = "e11b2c949363583b8d2ebec18acd2ac26e7181882ed6ac275e831ebf39105757"

RESULTS_DIR = _REPO / "docs/qualification/results" / CAMPAIGN_ID / QUAL_ID
LOGS_DIR = _REPO / "docs/qualification/run_logs" / CAMPAIGN_ID / QUAL_ID

# ── Helpers ────────────────────────────────────────────────────────────────────

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _preconditions() -> None:
    branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=_REPO, text=True,
    ).strip()
    if branch != "work/next-stage":
        raise RuntimeError(f"WRONG BRANCH: {branch}  (expected work/next-stage)")

    actual = _sha256(FIXTURE_PDF)
    if actual != EXPECTED_FIXTURE_SHA:
        raise RuntimeError(f"Q01 fixture hash mismatch: {actual}")

    actual_gt = _sha256(GT_DIR / "manifest.json")
    if actual_gt != EXPECTED_GT_MANIFEST_SHA:
        raise RuntimeError(f"GT manifest hash mismatch: {actual_gt}")


def _sync_runner(task) -> None:
    """Run the inference task synchronously (no thread)."""
    task()


_DIM_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(MM|mm|INCH|inch|IN|in|DEG|deg|DEGREE|degree)",
    re.IGNORECASE,
)


def _extract_dim(text: str) -> tuple[str | None, str | None]:
    m = _DIM_RE.search(text)
    if not m:
        return None, None
    val = m.group(1).replace(",", ".")
    raw_unit = m.group(2).upper()
    if raw_unit in ("IN", "INCH"):
        unit = "INCH"
    elif raw_unit in ("DEG", "DEGREE"):
        unit = "DEG"
    else:
        unit = raw_unit  # MM
    return val, unit


def _map_job_status(view: dict) -> str:
    """Map backend job view status to scoring-engine job_status token."""
    status = view.get("status", "FAILED")
    error_code = view.get("error_code")
    if status == "FAILED" and error_code == "R3B_VALIDATION_FAILURE":
        return "R3B_VALIDATION_FAILURE"
    return status


def _map_findings(raw_findings: list[dict]) -> list:
    from score_qualification import PredictedFinding

    out = []
    for f in raw_findings:
        raw_text = f.get("original_value") or ""
        norm_val, unit = _extract_dim(raw_text)
        out.append(
            PredictedFinding(
                finding_id=f["evidence_id"],
                raw_text=raw_text,
                candidate_type=f.get("candidate_type"),
                feature_type=None,
                normalized_value=norm_val,
                unit=unit,
                validation_status=f.get("reconciliation") or "ACCEPTED",
                box_basis=f.get("box_basis"),
                source_region=f.get("region_id"),
            )
        )
    return out


def _run_score_to_dict(rs) -> dict:
    d: dict = {}
    for fld in dataclasses.fields(rs):
        v = getattr(rs, fld.name)
        if isinstance(v, set):
            v = sorted(v)
        elif (
            isinstance(v, list)
            and v
            and dataclasses.is_dataclass(v[0])
        ):
            v = [dataclasses.asdict(item) for item in v]
        d[fld.name] = v
    return d


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("REAL_DRAWING_QUALIFICATION_06A - Q01 three-run real local pilot")
    print("=" * 70)
    print(f"timestamp_utc: {datetime.now(UTC).isoformat()}")

    # ── [1] Preconditions ──────────────────────────────────────────────────────
    print("\n[1] Precondition checks")
    _preconditions()
    print("    BRANCH=work/next-stage              OK")
    print("    Q01 fixture SHA256                  OK")
    print("    GT manifest SHA256                  OK")

    # ── [2] Imports (after env var set) ───────────────────────────────────────
    from score_qualification import QualRunInput, load_ground_truth, score_run

    from backend.api.drawing_analysis import AnalysisService

    # ── [2b] Ollama readiness gate (zero inference) ───────────────────────────
    print("\n[2b] Ollama readiness gate (zero inference calls)")
    gate_result = wait_for_readiness()
    print(f"    state              : {gate_result.state.value}")
    print(f"    elapsed_s          : {gate_result.elapsed_seconds:.1f}")
    print(f"    consecutive_pass   : {gate_result.consecutive_pass_count}")
    print(f"    observations       : {len(gate_result.observations)}")
    print(f"    inference_calls    : {gate_result.inference_calls_made}  (must be 0)")
    assert gate_result.inference_calls_made == 0, "Gate made inference calls — abort"
    try:
        assert_ready(gate_result)
    except ReadinessGateError as exc:
        print(f"\n    PRECHECK_FAILED: {exc}")
        print("    No RUN_ID consumed. Exiting without scoring any run.")
        sys.exit(2)
    print("    READINESS_GATE=PASS")

    # ── [3] Ground truth ──────────────────────────────────────────────────────
    print("\n[2] Loading ground truth")
    gt_records, gt_manifest_hash = load_ground_truth(GT_DIR)
    assert gt_manifest_hash == EXPECTED_GT_MANIFEST_SHA, "GT manifest hash drift"
    q01_gt = gt_records[QUAL_ID]
    items = q01_gt.get("items", [])
    print(f"    Q01 GT items: {len(items)}")
    for it in items:
        print(f"      {it['item_id']}: {it['expected_text']!r}  ({it.get('feature_type')})")

    # ── [4] Upload fixture ────────────────────────────────────────────────────
    print("\n[3] Uploading Q01 fixture to AnalysisService (sync runner)")
    service = AnalysisService(runner=_sync_runner)
    pdf_bytes = FIXTURE_PDF.read_bytes()
    upload_result = service.upload(pdf_bytes)
    drawing_id = upload_result["drawing_id"]
    print(f"    drawing_id: {drawing_id}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # ── [5] Three runs ────────────────────────────────────────────────────────
    run_scores = []
    print()

    for i, run_id in enumerate(RUN_IDS, start=1):
        print(f"[4.{i}] {run_id} {'-' * 50}")

        # Guard: never overwrite an existing scored artifact
        result_path_check = str(RESULTS_DIR / f"{run_id}.json")
        log_path_check = str(LOGS_DIR / f"{run_id}.json")
        try:
            assert_artifact_absent(result_path_check)
            assert_artifact_absent(log_path_check)
        except ArtifactExistsError as exc:
            print(f"      SKIPPED: {exc}")
            print("      Use authorize_recovery() + a new recovery run ID to re-attempt.")
            continue

        print(f"      started_at_utc: {datetime.now(UTC).isoformat()}")

        t_wall = time.monotonic()

        # start_analysis: with sync_runner, _run() completes before this returns
        initial_view, _ = service.start_analysis(
            drawing_id,
            ai_enabled=True,
            page_number=1,
            image_index=1,
            crop_px=None,
            requested_by="QUAL_RUNNER_06A",
        )
        job_id = initial_view["job_id"]

        # Get post-run view (initial_view is pre-run snapshot)
        view = service.job_view(drawing_id, job_id)
        wall_elapsed_ms = int((time.monotonic() - t_wall) * 1000)

        # Parse API timestamps for inference elapsed
        started_at = view.get("started_at")
        completed_at = view.get("completed_at")
        if started_at and completed_at:
            t_s = datetime.fromisoformat(started_at)
            t_e = datetime.fromisoformat(completed_at)
            inference_elapsed_ms = int((t_e - t_s).total_seconds() * 1000)
        else:
            inference_elapsed_ms = wall_elapsed_ms

        job_status_raw = view.get("status", "FAILED")
        scoring_job_status = _map_job_status(view)
        raw_findings = view.get("findings") or []
        error_code = view.get("error_code")

        print(f"      job_status        : {job_status_raw}")
        if error_code:
            print(f"      error_code        : {error_code}")
        print(f"      findings          : {len(raw_findings)}")
        print(f"      inference_elapsed : {inference_elapsed_ms} ms")

        ai_findings = _map_findings(raw_findings)
        for f in ai_findings:
            suffix = (
                f"  norm={f.normalized_value!r} unit={f.unit!r}"
                if f.normalized_value
                else ""
            )
            print(f"      finding: {f.raw_text!r}{suffix}")

        qual_run = QualRunInput(
            qual_id=QUAL_ID,
            run_id=run_id,
            run_number=i,
            fixture_class="RECOGNITION_GROUND_TRUTH",
            job_status=scoring_job_status,
            provider=PROVIDER,
            model=MODEL,
            inference_elapsed_ms=inference_elapsed_ms,
            ai_findings=ai_findings,
        )

        rs = score_run(q01_gt, qual_run)
        run_scores.append(rs)

        recall = rs.true_positive_count / rs.gt_item_count if rs.gt_item_count else 0.0
        print(
            f"      TP={rs.true_positive_count}  FP={rs.false_positive_count}"
            f"  FN={rs.false_negative_count}  recall={recall:.2f}"
        )
        for md in rs.match_detail:
            hit = md.match_level if md.matched_finding_id else "NO_MATCH"
            print(f"        {md.item_id}: {md.expected_text!r}  →  {hit}")

        # ── Write result file ─────────────────────────────────────────────────
        result_doc = {
            "schema_version": "1.0",
            "run_id": run_id,
            "qual_id": QUAL_ID,
            "run_number": i,
            "campaign_id": CAMPAIGN_ID,
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "fixture_sha256": EXPECTED_FIXTURE_SHA,
            "gt_manifest_hash": gt_manifest_hash,
            "provider": PROVIDER,
            "model": MODEL,
            "job_status": job_status_raw,
            "scoring_job_status": scoring_job_status,
            "job_id": job_id,
            "r3b_status": error_code if job_status_raw == "FAILED" else "PASSED",
            "inference_elapsed_ms": inference_elapsed_ms,
            "wall_elapsed_ms": wall_elapsed_ms,
            "model_call_count": 1,
            "automatic_retry_used": False,
            "fallback_used": False,
            "ai_findings_count": len(raw_findings),
            "ai_findings": [
                {
                    "finding_id": f["evidence_id"],
                    "raw_text": f.get("original_value"),
                    "candidate_type": f.get("candidate_type"),
                    "box_basis": f.get("box_basis"),
                    "region_id": f.get("region_id"),
                    "reconciliation": f.get("reconciliation"),
                    "legibility": f.get("legibility"),
                    "confidence": f.get("confidence"),
                }
                for f in raw_findings
            ],
            "run_score": _run_score_to_dict(rs),
        }
        result_path = RESULTS_DIR / f"{run_id}.json"
        result_path.write_text(json.dumps(result_doc, indent=2, default=str))
        print(f"      result → {result_path.relative_to(_REPO)}")

        # ── Write run log ─────────────────────────────────────────────────────
        log_doc = {
            "run_id": run_id,
            "qual_id": QUAL_ID,
            "campaign_id": CAMPAIGN_ID,
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "job_id": job_id,
            "drawing_id": drawing_id,
            "job_status": job_status_raw,
            "scoring_job_status": scoring_job_status,
            "started_at": started_at,
            "completed_at": completed_at,
            "inference_elapsed_ms": inference_elapsed_ms,
            "wall_elapsed_ms": wall_elapsed_ms,
            "error_code": error_code,
            "error_message": view.get("error_message"),
            "finding_count": len(raw_findings),
            "region": view.get("region"),
            "provider": PROVIDER,
            "model": MODEL,
            "requested_by": "QUAL_RUNNER_06A",
            "model_call_count": 1,
            "automatic_retry_used": False,
            "fallback_used": False,
            # raw findings — box omitted (pixel coordinates, not needed for audit)
            "raw_findings": [
                {k: v for k, v in f.items() if k != "box"}
                for f in raw_findings
            ],
        }
        log_path = LOGS_DIR / f"{run_id}.json"
        log_path.write_text(json.dumps(log_doc, indent=2, default=str))
        print(f"      log   → {log_path.relative_to(_REPO)}")
        print()

    # ── [6] Summary ───────────────────────────────────────────────────────────
    print("=" * 70)
    print("INFERENCE_COMPLETE=YES  (Q01-R01 through Q01-R03)")
    print("FURTHER_INFERENCE_HALTED=YES")
    print()
    print(f"{'Run':<12} {'Status':<12} {'TP':>3} {'FP':>3} {'FN':>3}  {'Recall':>7}  {'ms':>8}")
    print("-" * 56)
    for run_id, rs in zip(RUN_IDS, run_scores, strict=False):
        recall = rs.true_positive_count / rs.gt_item_count if rs.gt_item_count else 0.0
        elapsed = rs.inference_elapsed_ms or 0
        print(
            f"{run_id:<12} {rs.job_status:<12} {rs.true_positive_count:>3}"
            f" {rs.false_positive_count:>3} {rs.false_negative_count:>3}"
            f"  {recall:>6.2f}  {elapsed:>8}"
        )

    if run_scores:
        completed = [rs for rs in run_scores if rs.job_status == "COMPLETED"]
        total_tp = sum(rs.true_positive_count for rs in completed)
        total_gt = sum(rs.gt_item_count for rs in completed)
        if total_gt:
            overall_recall = total_tp / total_gt
            gate = "PASS" if overall_recall >= 0.70 else "FAIL"
            print()
            print(f"P2_DIMENSION_RECALL (Q01, {len(completed)}-run aggregate): "
                  f"{overall_recall:.3f}  [{gate}]")

    print()
    print("REAL_DRAWING_QUALIFICATION_06A_STATUS=COMPLETE")
    print("STOP_INFERENCE=YES")


if __name__ == "__main__":
    main()
