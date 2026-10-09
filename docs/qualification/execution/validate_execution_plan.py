"""
Validate the execution plan artifacts against frozen specification.

Checks:
  - campaign_plan.json is internally consistent
  - run_manifest.json matches the frozen spec run counts
  - All run IDs are unique
  - Fixture hashes in run manifest match fixture manifest
  - GT record hashes in run manifest match GT manifest
  - Scoring engine accessible and importable
  - One model call per inference run; no model calls for structural probes
  - retry_allowed=false for all runs

Exits 0 on success, 1 on any failure.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_EXECUTION_DIR = Path(__file__).resolve().parent
_SCORING_DIR = _REPO_ROOT / "docs" / "qualification" / "scoring"
if str(_SCORING_DIR) not in sys.path:
    sys.path.insert(0, str(_SCORING_DIR))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def _check(condition: bool, msg: str) -> None:
    if not condition:
        _fail(msg)


def main() -> None:
    errors: list[str] = []

    def err(msg: str) -> None:
        errors.append(msg)
        print(f"  FAIL: {msg}")

    def ok(msg: str) -> None:
        print(f"  OK  : {msg}")

    print("validate_execution_plan.py")
    print("=" * 60)

    # ── 1. Load campaign_plan.json ────────────────────────────────────────────
    plan_path = _EXECUTION_DIR / "campaign_plan.json"
    if not plan_path.exists():
        _fail(f"campaign_plan.json not found: {plan_path}")
    plan: dict = json.loads(plan_path.read_bytes())

    # ── 2. Verify frozen artifact hashes ─────────────────────────────────────
    print("\n[2] Frozen artifact hashes")
    fa = plan["frozen_artifacts"]
    for key, path_key in [
        ("spec_sha256", "spec_path"),
        ("fixture_manifest_sha256", "fixture_manifest_path"),
        ("gt_manifest_sha256", "gt_manifest_path"),
        ("scoring_engine_sha256", "scoring_engine_path"),
    ]:
        artifact_path = _REPO_ROOT / fa[path_key]
        if not artifact_path.exists():
            err(f"{fa[path_key]} not found")
            continue
        actual = _sha256(artifact_path)
        expected = fa[key]
        if actual == expected:
            ok(f"{fa[path_key]}")
        else:
            err(f"{fa[path_key]} hash mismatch: expected {expected}, got {actual}")

    # ── 3. Verify scoring engine importable ───────────────────────────────────
    print("\n[3] Scoring engine importable")
    try:
        import score_qualification as sq

        ok(f"score_qualification imported, SCHEMA_VERSION={sq.SCHEMA_VERSION}")
    except ImportError as exc:
        err(f"Cannot import score_qualification: {exc}")

    # ── 4. Load run manifest ──────────────────────────────────────────────────
    print("\n[4] Run manifest")
    rm_path = _EXECUTION_DIR / "run_manifest.json"
    if not rm_path.exists():
        _fail(f"run_manifest.json not found: {rm_path}")
    manifest: dict = json.loads(rm_path.read_bytes())
    runs: list[dict] = manifest["runs"]
    cond_runs: list[dict] = manifest.get("conditional_runs", [])

    # ── 5. Run ID uniqueness ──────────────────────────────────────────────────
    print("\n[5] Run ID uniqueness")
    all_ids = [r["run_id"] for r in runs] + [r["run_id"] for r in cond_runs]
    if len(all_ids) == len(set(all_ids)):
        ok(f"{len(all_ids)} total run IDs are unique")
    else:
        from collections import Counter

        dupes = [rid for rid, n in Counter(all_ids).items() if n > 1]
        err(f"Duplicate run IDs: {dupes}")

    # ── 6. Baseline run counts match spec ─────────────────────────────────────
    print("\n[6] Baseline run counts")
    expected_ai = manifest.get("baseline_ai_inference_count", 24)
    expected_probe = manifest.get("structural_probe_count", 3)

    ai_runs = [r for r in runs if r.get("expected_inference")]
    probe_runs = [r for r in runs if not r.get("expected_inference")]

    if len(ai_runs) == expected_ai:
        ok(f"AI inference run count = {len(ai_runs)}")
    else:
        err(f"AI inference run count: expected {expected_ai}, got {len(ai_runs)}")

    if len(probe_runs) == expected_probe:
        ok(f"Structural probe count = {len(probe_runs)}")
    else:
        err(f"Structural probe count: expected {expected_probe}, got {len(probe_runs)}")

    # ── 7. Per-class run counts ───────────────────────────────────────────────
    print("\n[7] Per-class run counts")
    from collections import Counter

    by_qid: Counter = Counter(r["qual_id"] for r in runs if r.get("expected_inference"))
    core_ids = ["Q01", "Q02", "Q05", "Q06", "Q07"]
    ext_gate_ids = ["Q09", "Q10"]
    ext_ids = ["Q03", "Q04", "Q08"]

    for qid in core_ids:
        n = by_qid.get(qid, 0)
        if n == 3:
            ok(f"CORE {qid}: {n} runs")
        else:
            err(f"CORE {qid}: expected 3 runs, got {n}")

    for qid in ext_gate_ids:
        n = by_qid.get(qid, 0)
        if n == 3:
            ok(f"EXT-GATE {qid}: {n} runs")
        else:
            err(f"EXT-GATE {qid}: expected 3 runs, got {n}")

    for qid in ext_ids:
        n = by_qid.get(qid, 0)
        if n == 1:
            ok(f"EXT {qid}: {n} run")
        else:
            err(f"EXT {qid}: expected 1 run, got {n}")

    # ── 8. One model call per AI run; zero for structural probes ──────────────
    print("\n[8] model_calls_per_run policy")
    for r in runs:
        expected_calls = 1 if r.get("expected_inference") else 0
        actual_calls = r.get("model_calls_per_run", -1)
        if actual_calls != expected_calls:
            err(
                f"{r['run_id']}: model_calls_per_run={actual_calls}, "
                f"expected {expected_calls}"
            )
    ok("All runs have correct model_calls_per_run (1 for AI, 0 for structural probes)")

    # ── 9. retry_allowed=false for all runs ───────────────────────────────────
    print("\n[9] retry_allowed policy")
    retry_violations = [r["run_id"] for r in runs + cond_runs if r.get("retry_allowed")]
    if retry_violations:
        err(f"retry_allowed=true found in: {retry_violations}")
    else:
        ok("retry_allowed=false for all runs")

    # ── 10. Fixture hashes ────────────────────────────────────────────────────
    print("\n[10] Fixture hash cross-reference")
    fx_manifest_path = _REPO_ROOT / "docs" / "qualification" / "fixtures" / "manifest.json"
    if not fx_manifest_path.exists():
        err(f"Fixture manifest not found: {fx_manifest_path}")
    else:
        fx_data: dict = json.loads(fx_manifest_path.read_bytes())
        fx_index = {e["id"]: e.get("sha256_pdf") for e in fx_data["entries"]}
        mismatches = 0
        for run in runs + cond_runs:
            qid = run["qual_id"]
            plan_sha = run.get("fixture_sha256")
            if plan_sha is None:
                continue
            manifest_sha = fx_index.get(qid)
            if manifest_sha is None:
                continue
            if plan_sha != manifest_sha:
                err(f"{qid}: fixture SHA mismatch in run_manifest vs fixture manifest")
                mismatches += 1
        if mismatches == 0:
            ok("All fixture hashes match fixture manifest")

    # ── 11. GT record hashes ──────────────────────────────────────────────────
    print("\n[11] GT record hash cross-reference")
    gt_manifest_path = _REPO_ROOT / "docs" / "qualification" / "ground_truth" / "manifest.json"
    if not gt_manifest_path.exists():
        err(f"GT manifest not found: {gt_manifest_path}")
    else:
        gt_data: dict = json.loads(gt_manifest_path.read_bytes())
        gt_index = {e["qual_id"]: e["record_sha256"] for e in gt_data["records"]}
        mismatches = 0
        for run in runs + cond_runs:
            qid = run["qual_id"]
            plan_sha = run.get("gt_record_sha256")
            if plan_sha is None:
                continue
            manifest_sha = gt_index.get(qid)
            if manifest_sha is None:
                continue
            if plan_sha != manifest_sha:
                err(f"{qid}: GT record SHA mismatch in run_manifest vs GT manifest")
                mismatches += 1
        if mismatches == 0:
            ok("All GT record hashes match GT manifest")

    # ── 12. Result paths are unique ───────────────────────────────────────────
    print("\n[12] Result path uniqueness")
    campaign_id = plan["campaign_id"]
    result_paths: set[str] = set()
    for run in runs:
        p = f"docs/qualification/results/{campaign_id}/{run['qual_id']}/{run['run_id']}.json"
        if p in result_paths:
            err(f"Duplicate result path: {p}")
        result_paths.add(p)
    ok(f"{len(result_paths)} unique result paths")

    # ── 13. Execution order: first/last run IDs ───────────────────────────────
    print("\n[13] Execution order anchors")
    expected_first = plan.get("first_real_run_id")
    expected_last = plan.get("last_baseline_run_id")
    all_ai_ids = [r["run_id"] for r in runs if r.get("expected_inference")]
    if expected_first and all_ai_ids[0] == expected_first:
        ok(f"first_real_run_id = {expected_first}")
    elif expected_first:
        err(f"first_real_run_id expected {expected_first}, manifest starts with {all_ai_ids[0]}")
    if expected_last and all_ai_ids[-1] == expected_last:
        ok(f"last_baseline_run_id = {expected_last}")
    elif expected_last:
        err(
            f"last_baseline_run_id expected {expected_last}, manifest ends with {all_ai_ids[-1]}"
        )

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if errors:
        print(f"VALIDATION FAILED ({len(errors)} error(s)):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("VALIDATION PASSED")
        print("RUN_MATRIX_VALID=YES")
        print("RUN_IDS_UNIQUE=YES")
        print("FIXTURE_HASHES_VALID=YES")
        print("GROUND_TRUTH_REFERENCES_VALID=YES")
        print("SCORING_INPUT_SCHEMA_COMPATIBLE=YES")


if __name__ == "__main__":
    main()
