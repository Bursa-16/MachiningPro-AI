"""
REAL_DRAWING_QUALIFICATION_06B - Readiness gate deterministic tests.

All tests are zero-inference: no real network calls, no Ollama process required.
HTTP interactions are provided via injected mock transports.

Covers:
  1.  Ollama unavailable -> precheck fails before scored run
  2.  model missing -> precheck fails
  3.  HTTP health unstable -> waits, then fails closed
  4.  consecutive stable health -> READY
  5.  readiness check performs zero inference
  6.  /api/chat is never called by readiness gate
  7.  /api/generate is never called by readiness gate
  8.  existing result artifact cannot be overwritten
  9.  failed original run requires explicit recovery authorization
  10. recovery gets a new traceable run ID
  11. completed run cannot be rerun accidentally (ArtifactExistsError)
  12. no retry/fallback introduced by recovery mechanism
  13. existing Q01 result artifacts remain readable and structurally valid
  14. R02/R03 scoring remains unchanged against frozen GT

REAL_LOCAL_AI_CALLS_EXECUTED=0
OLLAMA_INFERENCE_CALLS=0
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# ── path setup ────────────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[2]
_EXEC_DIR = _REPO / "docs" / "qualification" / "execution"
_SCORING_DIR = _REPO / "docs" / "qualification" / "scoring"
_GT_DIR = _REPO / "docs" / "qualification" / "ground_truth"
_RESULTS_DIR = _REPO / "docs" / "qualification" / "results" / "DEMO-QUAL-01" / "Q01"

for _p in [str(_EXEC_DIR), str(_SCORING_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from readiness_gate import (  # noqa: E402
    PATH_PS,
    PATH_TAGS,
    PATH_VERSION,
    ArtifactExistsError,
    ReadinessGateError,
    ReadinessState,
    RecoveryAuthorization,
    RunState,
    assert_artifact_absent,
    assert_ready,
    authorize_recovery,
    probe_once,
    wait_for_readiness,
)

# ── Mock transport helpers ────────────────────────────────────────────────────

def _transport_ok(model: str = "granite3.2-vision:2b"):
    """All probes succeed; model listed and in memory."""
    tags_body = json.dumps({"models": [{"name": model}]}).encode()
    ps_body = json.dumps({"models": [{"name": model}]}).encode()
    ver_body = json.dumps({"version": "0.6.0"}).encode()

    def _transport(host, port, path):
        if path == PATH_VERSION:
            return 200, ver_body
        if path == PATH_TAGS:
            return 200, tags_body
        if path == PATH_PS:
            return 200, ps_body
        return 404, b""

    return _transport


def _transport_down():
    """Service is completely unreachable."""
    def _transport(host, port, path):
        return 0, b""
    return _transport


def _transport_model_missing():
    """Service alive, but model not in /api/tags."""
    ver_body = json.dumps({"version": "0.6.0"}).encode()

    def _transport(host, port, path):
        if path == PATH_VERSION:
            return 200, ver_body
        if path == PATH_TAGS:
            return 200, json.dumps({"models": []}).encode()
        if path == PATH_PS:
            return 200, json.dumps({"models": []}).encode()
        return 404, b""

    return _transport


def _transport_unstable(fail_first_n: int, model: str = "granite3.2-vision:2b"):
    """Fails for first n calls to /api/version, then recovers."""
    count = [0]
    tags_body = json.dumps({"models": [{"name": model}]}).encode()
    ps_body = json.dumps({"models": [{"name": model}]}).encode()

    def _transport(host, port, path):
        if path == PATH_VERSION:
            count[0] += 1
            if count[0] <= fail_first_n:
                return 0, b""
            return 200, json.dumps({"version": "0.6.0"}).encode()
        if path == PATH_TAGS:
            if count[0] <= fail_first_n:
                return 0, b""
            return 200, tags_body
        if path == PATH_PS:
            return 200, ps_body
        return 404, b""

    return _transport


def _tracking_transport(inner, calls: list):
    """Wraps another transport to record every path called."""
    def _transport(host, port, path):
        calls.append(path)
        return inner(host, port, path)
    return _transport


# ── Test 1: Ollama unavailable -> precheck fails before scored run ────────────

def test_ollama_unavailable_precheck_fails():
    result = wait_for_readiness(
        transport=_transport_down(),
        max_wait_s=0.1,
        poll_interval_s=0.05,
        required_consecutive=2,
    )
    assert result.state is not ReadinessState.READY
    assert result.state in (ReadinessState.OLLAMA_UNREACHABLE, ReadinessState.TIMEOUT)
    with pytest.raises(ReadinessGateError) as exc_info:
        assert_ready(result)
    assert exc_info.value.result is result


def test_ollama_unavailable_no_run_id_consumed():
    """Verify that gate failure prevents any inference start."""
    result = wait_for_readiness(
        transport=_transport_down(),
        max_wait_s=0.1,
        poll_interval_s=0.05,
        required_consecutive=2,
    )
    # The only way to "consume" a run is to call assert_ready() first.
    # A caller that checks result.is_ready() before proceeding is safe.
    assert not result.is_ready(), "Gate must not pass when Ollama is down"


# ── Test 2: model missing -> precheck fails ───────────────────────────────────

def test_model_missing_precheck_fails():
    result = wait_for_readiness(
        transport=_transport_model_missing(),
        max_wait_s=0.1,
        poll_interval_s=0.05,
        required_consecutive=2,
    )
    assert result.state is not ReadinessState.READY
    assert result.state in (ReadinessState.MODEL_NOT_LISTED, ReadinessState.TIMEOUT)


def test_model_missing_observation_detail():
    obs = probe_once(transport=_transport_model_missing())
    assert obs.service_alive
    assert not obs.model_listed


# ── Test 3: HTTP health unstable -> waits/fails closed ───────────────────────

def test_unstable_health_fails_closed_within_budget():
    """Fails for all probes within the budget -> TIMEOUT (not READY)."""
    result = wait_for_readiness(
        transport=_transport_unstable(fail_first_n=999),
        max_wait_s=0.12,
        poll_interval_s=0.04,
        required_consecutive=2,
    )
    assert result.state is not ReadinessState.READY


def test_unstable_health_eventually_stabilises():
    """Fails first 1 probe, then succeeds -> should reach READY with required=2."""
    result = wait_for_readiness(
        transport=_transport_unstable(fail_first_n=1),
        max_wait_s=5.0,
        poll_interval_s=0.01,
        required_consecutive=2,
    )
    assert result.state is ReadinessState.READY
    assert result.consecutive_pass_count >= 2


# ── Test 4: consecutive stable health -> READY ────────────────────────────────

def test_consecutive_stable_health_ready():
    result = wait_for_readiness(
        transport=_transport_ok(),
        max_wait_s=5.0,
        poll_interval_s=0.01,
        required_consecutive=2,
    )
    assert result.state is ReadinessState.READY
    assert result.consecutive_pass_count >= 2


def test_single_pass_not_enough_for_required_two():
    """With required_consecutive=2, a single pass is not sufficient."""
    call_count = [0]

    def _one_pass_transport(host, port, path):
        call_count[0] += 1
        # First set of calls: pass; after that fail version
        probe_num = (call_count[0] - 1) // 3
        if probe_num == 0:
            if path == PATH_VERSION:
                return 200, json.dumps({"version": "0.1.0"}).encode()
            if path == PATH_TAGS:
                return 200, json.dumps({"models": [{"name": "granite3.2-vision:2b"}]}).encode()
            return 404, b""
        # All subsequent probes fail
        return 0, b""

    result = wait_for_readiness(
        transport=_one_pass_transport,
        max_wait_s=0.2,
        poll_interval_s=0.02,
        required_consecutive=2,
    )
    assert result.state is not ReadinessState.READY


# ── Test 5: readiness check performs zero inference ───────────────────────────

def test_readiness_zero_inference_calls():
    calls: list[str] = []
    tracked = _tracking_transport(_transport_ok(), calls)
    result = wait_for_readiness(
        transport=tracked,
        max_wait_s=1.0,
        poll_interval_s=0.01,
        required_consecutive=2,
    )
    assert result.inference_calls_made == 0
    for path in calls:
        assert path not in ("/api/chat", "/api/generate"), (
            f"Readiness gate called inference path: {path}"
        )


# ── Test 6: /api/chat never called by readiness gate ─────────────────────────

def test_chat_never_called_by_readiness_gate():
    calls: list[str] = []
    tracked = _tracking_transport(_transport_down(), calls)
    wait_for_readiness(
        transport=tracked,
        max_wait_s=0.1,
        poll_interval_s=0.05,
        required_consecutive=2,
    )
    assert "/api/chat" not in calls, "/api/chat must never be called by readiness gate"


# ── Test 7: /api/generate never called by readiness gate ─────────────────────

def test_generate_never_called_by_readiness_gate():
    calls: list[str] = []
    tracked = _tracking_transport(_transport_ok(), calls)
    wait_for_readiness(
        transport=tracked,
        max_wait_s=0.5,
        poll_interval_s=0.01,
        required_consecutive=2,
    )
    assert "/api/generate" not in calls, (
        "/api/generate must never be called by readiness gate"
    )


# ── Test 8: existing result artifact cannot be overwritten ───────────────────

def test_artifact_immutability_existing_file(tmp_path):
    artifact = tmp_path / "Q01-R01.json"
    artifact.write_text('{"run_id": "Q01-R01"}')
    with pytest.raises(ArtifactExistsError) as exc_info:
        assert_artifact_absent(str(artifact))
    assert "Q01-R01.json" in exc_info.value.path


def test_artifact_absent_no_error(tmp_path):
    artifact = tmp_path / "Q01-R99.json"
    # Must not raise when file does not exist
    assert_artifact_absent(str(artifact))


# ── Test 9: failed original run requires explicit recovery authorization ──────

def test_failed_run_requires_recovery_authorization():
    """Cannot re-attempt a failed run via assert_artifact_absent alone."""
    # If the artifact for Q01-R01 exists (it does from the pilot),
    # assert_artifact_absent must raise.
    r01_artifact = _RESULTS_DIR / "Q01-R01.json"
    if r01_artifact.exists():
        with pytest.raises(ArtifactExistsError):
            assert_artifact_absent(str(r01_artifact))
    else:
        pytest.skip("Q01-R01.json not present (pilot not yet run)")


def test_recovery_authorization_requires_reason():
    with pytest.raises(ValueError, match="reason"):
        RecoveryAuthorization.create(
            "Q01-R01",
            reason="",
            authorized_by="test",
        )


def test_recovery_authorization_requires_run_id():
    with pytest.raises(ValueError, match="original_run_id"):
        RecoveryAuthorization.create(
            "",
            reason="transient failure",
            authorized_by="test",
        )


# ── Test 10: recovery gets a new traceable run ID ─────────────────────────────

def test_recovery_gets_new_run_id():
    auth = authorize_recovery(
        "Q01-R01",
        reason="OLLAMA_UNAVAILABLE transient failure during cold start",
        authorized_by="QUAL_OPERATOR",
        attempt=1,
    )
    assert auth.original_run_id == "Q01-R01"
    assert auth.recovery_run_id == "Q01-R01-RERUN-01"
    assert auth.recovery_run_id != auth.original_run_id


def test_recovery_run_id_format():
    auth = authorize_recovery(
        "Q01-R01",
        reason="approved",
        authorized_by="operator",
        attempt=2,
    )
    assert auth.recovery_run_id == "Q01-R01-RERUN-02"


def test_recovery_preserves_original_id():
    auth = authorize_recovery(
        "Q01-R01",
        reason="pilot failure",
        authorized_by="QUAL_RUNNER_06A",
    )
    assert auth.original_run_id == "Q01-R01"
    # The recovery ID must start with the original
    assert auth.recovery_run_id.startswith("Q01-R01-")


# ── Test 11: completed run cannot be rerun accidentally ───────────────────────

def test_completed_run_cannot_be_rerun(tmp_path):
    """A completed artifact blocks a second attempt regardless of outcome."""
    artifact = tmp_path / "Q01-R02.json"
    artifact.write_text('{"run_id": "Q01-R02", "job_status": "COMPLETED"}')
    with pytest.raises(ArtifactExistsError):
        assert_artifact_absent(str(artifact))


def test_completed_run_immutable_on_real_pilot():
    """R02 pilot artifact (if present) cannot be overwritten."""
    r02 = _RESULTS_DIR / "Q01-R02.json"
    if r02.exists():
        with pytest.raises(ArtifactExistsError):
            assert_artifact_absent(str(r02))
    else:
        pytest.skip("Q01-R02.json not present")


# ── Test 12: no retry/fallback introduced ────────────────────────────────────

def test_recovery_is_not_automatic_retry():
    """Recovery requires explicit authorization — it is not an automatic retry."""
    # authorize_recovery is a deliberate call; it cannot be invoked silently.
    auth = authorize_recovery(
        "Q01-R01",
        reason="explicit authorization test",
        authorized_by="test_operator",
    )
    # Recovery run ID is distinct → proves it's not the same run retried
    assert auth.recovery_run_id != auth.original_run_id
    # Must carry a reason and authorizer — anonymous/automatic recovery is impossible
    assert auth.reason
    assert auth.authorized_by


def test_run_state_enum_has_precheck_failed():
    """PRECHECK_FAILED state exists to distinguish gate failure from inference failure."""
    assert RunState.PRECHECK_FAILED.value == "PRECHECK_FAILED"
    assert RunState.FAILED.value == "FAILED"
    assert RunState.PRECHECK_FAILED is not RunState.FAILED


# ── Test 13: existing Q01 artifacts remain readable ──────────────────────────

@pytest.mark.parametrize("run_id", ["Q01-R01", "Q01-R02", "Q01-R03"])
def test_existing_q01_result_artifacts_readable(run_id):
    path = _RESULTS_DIR / f"{run_id}.json"
    if not path.exists():
        pytest.skip(f"{run_id}.json not present (pilot not yet run)")
    data = json.loads(path.read_text())
    assert data["run_id"] == run_id
    assert data["qual_id"] == "Q01"
    assert data["campaign_id"] == "DEMO-QUAL-01"
    assert data["model_call_count"] == 1
    assert data["automatic_retry_used"] is False
    assert data["fallback_used"] is False
    assert "run_score" in data


@pytest.mark.parametrize("run_id", ["Q01-R01", "Q01-R02", "Q01-R03"])
def test_existing_q01_log_artifacts_readable(run_id):
    logs_dir = _REPO / "docs/qualification/run_logs/DEMO-QUAL-01/Q01"
    path = logs_dir / f"{run_id}.json"
    if not path.exists():
        pytest.skip(f"Log {run_id}.json not present")
    data = json.loads(path.read_text())
    assert data["run_id"] == run_id
    assert data["model_call_count"] == 1
    assert data["automatic_retry_used"] is False


# ── Test 14: R02/R03 scoring unchanged ───────────────────────────────────────

def test_r02_scoring_unchanged():
    """Re-score R02 from frozen GT and confirm TP=3, FP=1, FN=0."""
    r02_path = _RESULTS_DIR / "Q01-R02.json"
    if not r02_path.exists():
        pytest.skip("Q01-R02.json not present")

    from score_qualification import (
        PredictedFinding,
        QualRunInput,
        load_ground_truth,
        score_run,
    )

    gt_records, _ = load_ground_truth(_GT_DIR)
    data = json.loads(r02_path.read_text())

    ai_findings = [
        PredictedFinding(
            finding_id=f["finding_id"],
            raw_text=f["raw_text"],
            candidate_type=f.get("candidate_type"),
            validation_status=f.get("reconciliation") or "ACCEPTED",
        )
        for f in data["ai_findings"]
    ]
    run = QualRunInput(
        qual_id="Q01",
        run_id="Q01-R02",
        run_number=2,
        fixture_class="RECOGNITION_GROUND_TRUTH",
        job_status="COMPLETED",
        provider="ollama.chat",
        model="granite3.2-vision:2b",
        ai_findings=ai_findings,
    )
    rs = score_run(gt_records["Q01"], run)
    assert rs.true_positive_count == 3
    assert rs.false_positive_count == 1
    assert rs.false_negative_count == 0
    assert rs.gt_item_count == 3


def test_r03_scoring_unchanged():
    """Re-score R03 from frozen GT and confirm TP=3, FP=1, FN=0."""
    r03_path = _RESULTS_DIR / "Q01-R03.json"
    if not r03_path.exists():
        pytest.skip("Q01-R03.json not present")

    from score_qualification import (
        PredictedFinding,
        QualRunInput,
        load_ground_truth,
        score_run,
    )

    gt_records, _ = load_ground_truth(_GT_DIR)
    data = json.loads(r03_path.read_text())

    ai_findings = [
        PredictedFinding(
            finding_id=f["finding_id"],
            raw_text=f["raw_text"],
            candidate_type=f.get("candidate_type"),
            validation_status=f.get("reconciliation") or "ACCEPTED",
        )
        for f in data["ai_findings"]
    ]
    run = QualRunInput(
        qual_id="Q01",
        run_id="Q01-R03",
        run_number=3,
        fixture_class="RECOGNITION_GROUND_TRUTH",
        job_status="COMPLETED",
        provider="ollama.chat",
        model="granite3.2-vision:2b",
        ai_findings=ai_findings,
    )
    rs = score_run(gt_records["Q01"], run)
    assert rs.true_positive_count == 3
    assert rs.false_positive_count == 1
    assert rs.false_negative_count == 0
    assert rs.gt_item_count == 3


def test_r02_r03_item_sets_identical():
    """R02 and R03 returned the same set of raw text values."""
    r02_path = _RESULTS_DIR / "Q01-R02.json"
    r03_path = _RESULTS_DIR / "Q01-R03.json"
    if not r02_path.exists() or not r03_path.exists():
        pytest.skip("Pilot artifacts not present")

    r02 = json.loads(r02_path.read_text())
    r03 = json.loads(r03_path.read_text())

    r02_texts = sorted(f["raw_text"] for f in r02["ai_findings"])
    r03_texts = sorted(f["raw_text"] for f in r03["ai_findings"])
    assert r02_texts == r03_texts, (
        f"R02 texts {r02_texts} differ from R03 texts {r03_texts}"
    )


def test_duplicate_60mm_is_sole_fp():
    """The only false positive in R02/R03 is the duplicate '60 MM' finding."""
    for run_id in ("Q01-R02", "Q01-R03"):
        path = _RESULTS_DIR / f"{run_id}.json"
        if not path.exists():
            pytest.skip(f"{run_id}.json not present")
        data = json.loads(path.read_text())
        rs = data["run_score"]
        assert rs["false_positive_count"] == 1
        unmatched = rs["unmatched_finding_ids"]
        assert len(unmatched) == 1
        # Confirm the unmatched finding is a "60 MM" finding
        fp_finding_id = unmatched[0]
        fp_raw = next(
            f["raw_text"] for f in data["ai_findings"] if f["finding_id"] == fp_finding_id
        )
        assert fp_raw == "60 MM", f"Expected FP to be '60 MM', got {fp_raw!r}"


# ── Probe detail tests ────────────────────────────────────────────────────────

def test_probe_service_alive_field():
    obs = probe_once(transport=_transport_ok())
    assert obs.service_alive is True
    assert obs.model_listed is True
    assert obs.inference_calls_made == 0


def test_probe_model_in_memory_field():
    obs = probe_once(transport=_transport_ok())
    assert obs.model_in_memory is True


def test_probe_ps_unavailable_graceful():
    """If /api/ps returns 404, model_in_memory is None, not an error."""
    def _transport_no_ps(host, port, path):
        if path == PATH_VERSION:
            return 200, json.dumps({"version": "0.1.0"}).encode()
        if path == PATH_TAGS:
            return 200, json.dumps({"models": [{"name": "granite3.2-vision:2b"}]}).encode()
        if path == PATH_PS:
            return 404, b"Not found"
        return 404, b""

    obs = probe_once(transport=_transport_no_ps)
    assert obs.service_alive is True
    assert obs.model_listed is True
    assert obs.model_in_memory is None  # 404 -> gracefully unknown, not False


def test_model_name_matching_case_insensitive():
    """Model name matching is case-insensitive and strips :tag suffixes."""
    def _transport_mixed_case(host, port, path):
        if path == PATH_VERSION:
            return 200, json.dumps({"version": "0.6.0"}).encode()
        if path == PATH_TAGS:
            return 200, json.dumps({
                "models": [{"name": "Granite3.2-Vision:2B"}]
            }).encode()
        return 404, b""

    obs = probe_once(model="granite3.2-vision:2b", transport=_transport_mixed_case)
    assert obs.model_listed is True
