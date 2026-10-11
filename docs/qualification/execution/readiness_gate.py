"""
Zero-inference Ollama readiness gate for qualification execution.

Uses ONLY Ollama metadata/health endpoints (GET requests):

  GET /api/version  -> service alive check
  GET /api/tags     -> model installed check
  GET /api/ps       -> model in-memory check (Ollama >= 0.1.33, optional)

NEVER calls /api/chat or /api/generate.
NEVER consumes a scored qualification RUN_ID.

A gate that cannot confirm readiness within max_wait_seconds raises
ReadinessGateError. The caller must not start any scored run after that.
"""

from __future__ import annotations

import enum
import http.client
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 11434
DEFAULT_MODEL = "granite3.2-vision:2b"

# Frozen gate policy — changing these requires a new qualification task.
READY_GATE_MAX_WAIT_SECONDS: float = 120.0
READY_GATE_POLL_INTERVAL_SECONDS: float = 5.0
READY_GATE_REQUIRED_CONSECUTIVE_PASS_COUNT: int = 2

# Paths that prove readiness. MUST NOT include /api/chat or /api/generate.
PATH_VERSION = "/api/version"
PATH_TAGS = "/api/tags"
PATH_PS = "/api/ps"

_INFERENCE_PATHS = frozenset({"/api/chat", "/api/generate"})

# ── Transport contract ─────────────────────────────────────────────────────────
# Callable[[host, port, path], (http_status, body_bytes)]
# status=0 means connection failed (OSError / HTTPException).
GetTransport = Callable[[str, int, str], tuple[int, bytes]]


def _default_get(host: str, port: int, path: str) -> tuple[int, bytes]:
    if path in _INFERENCE_PATHS:
        raise RuntimeError(
            f"readiness_gate attempted inference path {path!r} — this is a bug"
        )
    conn = http.client.HTTPConnection(host, port, timeout=5.0)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read(65_536)
        return resp.status, body
    except (OSError, http.client.HTTPException):
        return 0, b""
    finally:
        conn.close()


# ── State ──────────────────────────────────────────────────────────────────────

class ReadinessState(enum.Enum):
    READY = "READY"
    OLLAMA_UNREACHABLE = "OLLAMA_UNREACHABLE"
    MODEL_NOT_LISTED = "MODEL_NOT_LISTED"
    UNSTABLE = "UNSTABLE"
    TIMEOUT = "TIMEOUT"


@dataclass
class ReadinessObservation:
    timestamp: float
    http_version_status: int    # 0 = connection failed
    http_tags_status: int
    http_ps_status: int         # 0 = not available or failed
    service_alive: bool
    model_listed: bool
    model_in_memory: bool | None  # None when /api/ps not available
    # inference_calls_made is always 0 — field exists for audit
    inference_calls_made: int = 0


@dataclass
class ReadinessResult:
    state: ReadinessState
    observations: list[ReadinessObservation] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    consecutive_pass_count: int = 0
    # Must always be 0; present for mandatory audit trail.
    inference_calls_made: int = 0

    def is_ready(self) -> bool:
        return self.state is ReadinessState.READY


class ReadinessGateError(Exception):
    """Raised when the readiness gate does not reach READY within the budget."""

    def __init__(self, result: ReadinessResult) -> None:
        super().__init__(
            f"Readiness gate failed: state={result.state.value} "
            f"elapsed={result.elapsed_seconds:.1f}s "
            f"observations={len(result.observations)}"
        )
        self.result = result


# ── Probe ──────────────────────────────────────────────────────────────────────

def probe_once(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    model: str = DEFAULT_MODEL,
    *,
    transport: GetTransport = _default_get,
) -> ReadinessObservation:
    """
    One non-inference health probe.

    1. GET /api/version  -> service alive
    2. GET /api/tags     -> model listed (installed on disk)
    3. GET /api/ps       -> model in memory (optional, graceful on 404/error)

    No call to /api/chat or /api/generate.
    """
    ts = time.monotonic()

    # 1. Service alive
    ver_status, ver_body = transport(host, port, PATH_VERSION)
    service_alive = ver_status == 200

    # 2. Model listed
    tags_status, tags_body = transport(host, port, PATH_TAGS)
    model_listed = False
    if tags_status == 200:
        try:
            data: Any = json.loads(tags_body)
            models = data.get("models", [])
            model_listed = any(
                _model_name_matches(m.get("name", ""), model)
                for m in models
                if isinstance(m, dict)
            )
        except (ValueError, AttributeError):
            pass

    # 3. Model in memory via /api/ps (optional; 404 means endpoint not available)
    ps_status, ps_body = transport(host, port, PATH_PS)
    model_in_memory: bool | None = None
    if ps_status == 200:
        try:
            data = json.loads(ps_body)
            loaded = data.get("models", [])
            model_in_memory = any(
                _model_name_matches(m.get("name", ""), model)
                for m in loaded
                if isinstance(m, dict)
            )
        except (ValueError, AttributeError):
            model_in_memory = None
    # ps_status=404 means the endpoint doesn't exist in this Ollama version — not an error.

    return ReadinessObservation(
        timestamp=ts,
        http_version_status=ver_status,
        http_tags_status=tags_status,
        http_ps_status=ps_status,
        service_alive=service_alive,
        model_listed=model_listed,
        model_in_memory=model_in_memory,
        inference_calls_made=0,
    )


def _model_name_matches(listed: str, wanted: str) -> bool:
    """
    True when the listed model name matches the wanted model name.

    Normalises tag suffixes: "granite3.2-vision:2b" and "granite3.2-vision" both
    match "granite3.2-vision:2b" and "granite3.2-vision:latest".
    """
    listed = listed.strip().lower()
    wanted = wanted.strip().lower()
    if listed == wanted:
        return True
    # Strip :tag for a loose match (wanted is the authoritative id)
    listed_base = listed.split(":")[0]
    wanted_base = wanted.split(":")[0]
    return listed_base == wanted_base


def _observation_passes(obs: ReadinessObservation) -> bool:
    """
    True when this probe indicates the service is ready to accept a request.

    A passing probe requires:
    - service alive (HTTP 200 on /api/version)
    - model listed (shows up in /api/tags)

    model_in_memory=True is a bonus signal but its absence is not a failure
    because /api/ps may be unavailable in older Ollama versions.
    """
    return obs.service_alive and obs.model_listed


# ── Gate ───────────────────────────────────────────────────────────────────────

def wait_for_readiness(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    model: str = DEFAULT_MODEL,
    *,
    max_wait_s: float = READY_GATE_MAX_WAIT_SECONDS,
    poll_interval_s: float = READY_GATE_POLL_INTERVAL_SECONDS,
    required_consecutive: int = READY_GATE_REQUIRED_CONSECUTIVE_PASS_COUNT,
    transport: GetTransport = _default_get,
) -> ReadinessResult:
    """
    Poll Ollama readiness until stable or budget exhausted. Zero inference calls.

    Returns ReadinessResult with state=READY if `required_consecutive` consecutive
    passing probes are observed within `max_wait_s` seconds.

    Returns a non-READY state if the budget is exhausted. The caller must
    call assert_ready() (or check result.is_ready()) before starting any
    scored qualification run.
    """
    t_start = time.monotonic()
    observations: list[ReadinessObservation] = []
    consecutive = 0

    while True:
        elapsed = time.monotonic() - t_start
        if elapsed > max_wait_s:
            # Final probe to capture current state before giving up
            if not observations or (time.monotonic() - observations[-1].timestamp) > 1.0:
                obs = probe_once(host, port, model, transport=transport)
                observations.append(obs)
            state = _terminal_state(observations)
            return ReadinessResult(
                state=ReadinessState.TIMEOUT if state is ReadinessState.READY
                else state,
                observations=observations,
                elapsed_seconds=time.monotonic() - t_start,
                consecutive_pass_count=consecutive,
                inference_calls_made=0,
            )

        obs = probe_once(host, port, model, transport=transport)
        observations.append(obs)

        if _observation_passes(obs):
            consecutive += 1
            if consecutive >= required_consecutive:
                return ReadinessResult(
                    state=ReadinessState.READY,
                    observations=observations,
                    elapsed_seconds=time.monotonic() - t_start,
                    consecutive_pass_count=consecutive,
                    inference_calls_made=0,
                )
        else:
            consecutive = 0

        remaining = max_wait_s - (time.monotonic() - t_start)
        if remaining <= 0:
            continue
        time.sleep(min(poll_interval_s, remaining))


def _terminal_state(observations: list[ReadinessObservation]) -> ReadinessState:
    """Classify the final state from the last observation."""
    if not observations:
        return ReadinessState.OLLAMA_UNREACHABLE
    last = observations[-1]
    if not last.service_alive:
        return ReadinessState.OLLAMA_UNREACHABLE
    if not last.model_listed:
        return ReadinessState.MODEL_NOT_LISTED
    # Alive and model listed but not enough consecutive passes
    return ReadinessState.UNSTABLE


def assert_ready(result: ReadinessResult) -> None:
    """
    Raise ReadinessGateError if the gate did not reach READY.

    Must be called before any scored qualification RUN_ID is started.
    """
    if not result.is_ready():
        raise ReadinessGateError(result)


# ── Run-state semantics ────────────────────────────────────────────────────────

class RunState(enum.Enum):
    """
    Explicit states for a qualification run attempt.

    PRECHECK_FAILED     : readiness gate did not pass; no RUN_ID consumed.
    REQUEST_NOT_ACCEPTED: RUN_ID reserved but Ollama rejected before inference.
    INFERENCE_STARTED   : Ollama accepted the request; outcome unknown until done.
    COMPLETED           : Inference finished with findings.
    FAILED              : Inference finished with error (no findings).
    """

    PRECHECK_FAILED = "PRECHECK_FAILED"
    REQUEST_NOT_ACCEPTED = "REQUEST_NOT_ACCEPTED"
    INFERENCE_STARTED = "INFERENCE_STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ── Artifact immutability ──────────────────────────────────────────────────────

class ArtifactExistsError(Exception):
    """Raised when an attempt is made to write over an existing run artifact."""

    def __init__(self, path: str) -> None:
        super().__init__(
            f"Artifact already exists and must not be overwritten: {path}. "
            "Use a recovery run ID if this run needs to be re-attempted."
        )
        self.path = path


def assert_artifact_absent(artifact_path: str) -> None:
    """Raise ArtifactExistsError if the artifact file already exists."""
    from pathlib import Path

    if Path(artifact_path).exists():
        raise ArtifactExistsError(artifact_path)


# ── Recovery run ID ────────────────────────────────────────────────────────────

class RecoveryNotAuthorizedError(Exception):
    """Raised when a recovery run is attempted without explicit authorization."""


@dataclass
class RecoveryAuthorization:
    """
    Explicit human authorization to re-attempt a failed qualification run.

    Must be created with authorize() to produce a usable token. The original
    artifact is never deleted or overwritten; the recovery run gets a new ID.
    """

    original_run_id: str
    recovery_run_id: str
    reason: str
    authorized_at: float
    authorized_by: str

    @classmethod
    def create(
        cls,
        original_run_id: str,
        *,
        reason: str,
        authorized_by: str,
        attempt: int = 1,
    ) -> RecoveryAuthorization:
        if not original_run_id.strip():
            raise ValueError("original_run_id must not be empty")
        if not reason.strip():
            raise ValueError("reason must not be empty")
        recovery_id = f"{original_run_id}-RERUN-{attempt:02d}"
        return cls(
            original_run_id=original_run_id,
            recovery_run_id=recovery_id,
            reason=reason,
            authorized_at=time.time(),
            authorized_by=authorized_by,
        )


def authorize_recovery(
    original_run_id: str,
    *,
    reason: str,
    authorized_by: str,
    attempt: int = 1,
) -> RecoveryAuthorization:
    """
    Explicitly authorize a recovery run after a readiness/transport failure.

    The original artifact is preserved. The recovery attempt uses a new run ID
    (e.g. Q01-R01-RERUN-01) so history is never lost.
    """
    return RecoveryAuthorization.create(
        original_run_id,
        reason=reason,
        authorized_by=authorized_by,
        attempt=attempt,
    )


__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "DEFAULT_MODEL",
    "READY_GATE_MAX_WAIT_SECONDS",
    "READY_GATE_POLL_INTERVAL_SECONDS",
    "READY_GATE_REQUIRED_CONSECUTIVE_PASS_COUNT",
    "PATH_VERSION",
    "PATH_TAGS",
    "PATH_PS",
    "ArtifactExistsError",
    "ReadinessGateError",
    "ReadinessObservation",
    "ReadinessResult",
    "ReadinessState",
    "RecoveryAuthorization",
    "RecoveryNotAuthorizedError",
    "RunState",
    "assert_artifact_absent",
    "assert_ready",
    "authorize_recovery",
    "probe_once",
    "wait_for_readiness",
]
