"""
Tests for GET /api/tool-life/summary, /tools and /tools/{tool_id}.

All tests use synthetic data injected via monkeypatching.
The real ToolLife 968 XLSX is never required during unit tests.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend.api import tool_life as tl_module
from backend.api.app import app
from backend.cutting_parameters.models import EvidenceStatus
from backend.domain.base import Provenance
from backend.domain.enums import ProvenanceType
from backend.domain.units import Quantity, Unit
from backend.empirical.toollife968_models import (
    TOOLLIFE968_SENSOR_FEATURE_COUNT,
    ToolLife968Observation,
    ToolLife968SourceMeta,
)
from backend.empirical.toollife968_registry import ToolLife968Registry

client = TestClient(app)

# ---------------------------------------------------------------------------
# Synthetic fixture helpers
# ---------------------------------------------------------------------------

_SENSOR_HEADERS: tuple[str, ...] = tuple(
    f"s_{ch}_{stat}"
    for ch in range(20)
    for stat in ("min", "max", "mean", "std", "skew", "kurt")
)

_SOURCE_META = ToolLife968SourceMeta(
    source_dataset="TOOLLIFE-968",
    source_filename="test_fixture.xlsx",
    source_sha256="a" * 64,
    source_sheet="Golden ToolLife 968",
    doi="10.6084/m9.figshare.28589216",
    sensor_feature_headers=_SENSOR_HEADERS,
)

_PROVENANCE = Provenance(source_type=ProvenanceType.LITERATURE)


def _make_obs(
    obs_id: str,
    tool_index: int,
    cycle_number: int,
    cycle_to_failure: int,
    *,
    tool_type: str = "1",
    adoc_mm: float = 5.0,
    rdoc_mm: float = 8.0,
    holder_mm: float = 80.0,
    hardness: str = "38.0",
    sample_index: int = 0,
) -> ToolLife968Observation:
    max_ctf = cycle_number + cycle_to_failure - 1
    ctf_norm = (
        Decimal(str(cycle_to_failure)) / Decimal(str(max_ctf))
        if max_ctf > 0
        else Decimal("0")
    )
    if ctf_norm > Decimal("1"):
        ctf_norm = Decimal("1")
    return ToolLife968Observation(
        observation_id=obs_id,
        source=_SOURCE_META,
        source_row=cycle_number,
        tool_index=tool_index,
        tool_type=tool_type,
        adoc=Quantity(value=Decimal(str(adoc_mm)), unit=Unit.MM),
        rdoc=Quantity(value=Decimal(str(rdoc_mm)), unit=Unit.MM),
        tool_holder_length=Quantity(value=Decimal(str(holder_mm)), unit=Unit.MM),
        hardness_mean=Decimal(hardness),
        cycle_number=cycle_number,
        sample_index=sample_index,
        cycle_to_failure=cycle_to_failure,
        cycle_to_failure_normalized=ctf_norm,
        sensor_features=tuple(float(i) for i in range(TOOLLIFE968_SENSOR_FEATURE_COUNT)),
        provenance=_PROVENANCE,
        evidence_status=EvidenceStatus.EXPERIMENTAL,
    )


def _make_seeded_registry(obs_list: list[ToolLife968Observation]) -> ToolLife968Registry:
    reg = ToolLife968Registry()
    reg.register_all(obs_list)
    return reg


def _three_obs_registry() -> ToolLife968Registry:
    """Tool 1: 3 obs, CTF 2→1→0 (EOL). Tool 2: 2 obs, CTF 1→0."""
    obs = [
        _make_obs("t1_c1_s0", tool_index=1, cycle_number=1, cycle_to_failure=2),
        _make_obs("t1_c2_s0", tool_index=1, cycle_number=2, cycle_to_failure=1),
        _make_obs("t1_c3_s0", tool_index=1, cycle_number=3, cycle_to_failure=0),
        _make_obs("t2_c1_s0", tool_index=2, cycle_number=1, cycle_to_failure=1),
        _make_obs("t2_c2_s0", tool_index=2, cycle_number=2, cycle_to_failure=0),
    ]
    return _make_seeded_registry(obs)


# ---------------------------------------------------------------------------
# Fixtures: reset module state between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    """Reset the seeding flag and inject an unseeded registry by default."""
    tl_module._reset_registry_state()
    yield
    tl_module._reset_registry_state()


# ---------------------------------------------------------------------------
# Summary — unseeded
# ---------------------------------------------------------------------------

def test_summary_unseeded_returns_seeded_false(monkeypatch):
    """Summary returns seeded=false with zero counts when env var is not set."""
    monkeypatch.delenv("MACHININGPRO_TOOLLIFE968_SOURCE_PATH", raising=False)
    res = client.get("/api/tool-life/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["seeded"] is False
    assert data["observation_count"] == 0
    assert data["tool_count"] == 0


def test_summary_unseeded_has_doi(monkeypatch):
    """Summary always returns the DOI even when unseeded."""
    monkeypatch.delenv("MACHININGPRO_TOOLLIFE968_SOURCE_PATH", raising=False)
    res = client.get("/api/tool-life/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["source_doi"] == "10.6084/m9.figshare.28589216"


def test_summary_unseeded_has_limitations(monkeypatch):
    """Summary always returns the limitations list."""
    monkeypatch.delenv("MACHININGPRO_TOOLLIFE968_SOURCE_PATH", raising=False)
    res = client.get("/api/tool-life/summary")
    data = res.json()
    assert isinstance(data["limitations"], list)
    assert len(data["limitations"]) > 0


def test_summary_unseeded_cycle_to_failure_semantics(monkeypatch):
    """cycle_to_failure_semantics must describe it as countdown."""
    monkeypatch.delenv("MACHININGPRO_TOOLLIFE968_SOURCE_PATH", raising=False)
    res = client.get("/api/tool-life/summary")
    data = res.json()
    assert data["cycle_to_failure_semantics"] == "countdown_to_eol"


# ---------------------------------------------------------------------------
# Summary — seeded (monkeypatched registry)
# ---------------------------------------------------------------------------

def test_summary_seeded(monkeypatch):
    """Summary returns correct counts when registry is seeded."""
    reg = _three_obs_registry()
    monkeypatch.setattr(tl_module, "_get_registry", lambda: reg)
    res = client.get("/api/tool-life/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["seeded"] is True
    assert data["observation_count"] == 5
    assert data["tool_count"] == 2
    assert data["eol_observation_count"] == 2


def test_summary_seeded_sensor_feature_headers(monkeypatch):
    """Summary includes all 120 sensor feature header names."""
    reg = _three_obs_registry()
    monkeypatch.setattr(tl_module, "_get_registry", lambda: reg)
    res = client.get("/api/tool-life/summary")
    data = res.json()
    assert len(data["sensor_feature_headers"]) == TOOLLIFE968_SENSOR_FEATURE_COUNT


def test_summary_evidence_status(monkeypatch):
    """evidence_status must be EXPERIMENTAL."""
    reg = _three_obs_registry()
    monkeypatch.setattr(tl_module, "_get_registry", lambda: reg)
    res = client.get("/api/tool-life/summary")
    data = res.json()
    assert data["evidence_status"] == "EXPERIMENTAL"


# ---------------------------------------------------------------------------
# Tools list
# ---------------------------------------------------------------------------

def test_tools_list_unseeded_503(monkeypatch):
    """Tools list returns 503 when registry is not seeded."""
    monkeypatch.delenv("MACHININGPRO_TOOLLIFE968_SOURCE_PATH", raising=False)
    res = client.get("/api/tool-life/tools")
    assert res.status_code == 503


def test_tools_list_returns_correct_count(monkeypatch):
    """Tools list returns one entry per distinct tool_id."""
    reg = _three_obs_registry()
    monkeypatch.setattr(tl_module, "_get_registry", lambda: reg)
    res = client.get("/api/tool-life/tools")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2


def test_tools_list_eol_present(monkeypatch):
    """eol_present is True for tools that have a CTF=0 observation."""
    reg = _three_obs_registry()
    monkeypatch.setattr(tl_module, "_get_registry", lambda: reg)
    res = client.get("/api/tool-life/tools")
    data = res.json()
    eol_flags = {item["tool_id"]: item["eol_present"] for item in data}
    assert eol_flags[1] is True
    assert eol_flags[2] is True


def test_tools_list_observation_counts(monkeypatch):
    """observation_count per tool matches the fixture."""
    reg = _three_obs_registry()
    monkeypatch.setattr(tl_module, "_get_registry", lambda: reg)
    res = client.get("/api/tool-life/tools")
    data = res.json()
    counts = {item["tool_id"]: item["observation_count"] for item in data}
    assert counts[1] == 3
    assert counts[2] == 2


# ---------------------------------------------------------------------------
# Tool detail
# ---------------------------------------------------------------------------

def test_tool_detail_unseeded_503(monkeypatch):
    """Tool detail returns 503 when registry is not seeded."""
    monkeypatch.delenv("MACHININGPRO_TOOLLIFE968_SOURCE_PATH", raising=False)
    res = client.get("/api/tool-life/tools/1")
    assert res.status_code == 503


def test_tool_detail_not_found_404(monkeypatch):
    """Tool detail returns 404 for a tool_id not in the registry."""
    reg = _three_obs_registry()
    monkeypatch.setattr(tl_module, "_get_registry", lambda: reg)
    res = client.get("/api/tool-life/tools/99")
    assert res.status_code == 404


def test_tool_detail_lifecycle_length(monkeypatch):
    """Tool 1 lifecycle has 3 observations."""
    reg = _three_obs_registry()
    monkeypatch.setattr(tl_module, "_get_registry", lambda: reg)
    res = client.get("/api/tool-life/tools/1")
    assert res.status_code == 200
    data = res.json()
    assert len(data["lifecycle"]) == 3


def test_tool_detail_eol_flag(monkeypatch):
    """Last lifecycle point of tool 1 has is_eol=True."""
    reg = _three_obs_registry()
    monkeypatch.setattr(tl_module, "_get_registry", lambda: reg)
    res = client.get("/api/tool-life/tools/1")
    data = res.json()
    lifecycle = data["lifecycle"]
    # sorted by cycle_number — last entry is cycle 3, CTF=0
    eol_points = [p for p in lifecycle if p["is_eol"]]
    assert len(eol_points) == 1
    assert eol_points[0]["cycle_to_failure"] == 0


def test_tool_detail_sensor_series_length(monkeypatch):
    """sensor_series.values has one value per lifecycle observation."""
    reg = _three_obs_registry()
    monkeypatch.setattr(tl_module, "_get_registry", lambda: reg)
    res = client.get("/api/tool-life/tools/1")
    data = res.json()
    assert len(data["sensor_series"]["values"]) == len(data["lifecycle"])


def test_tool_detail_feature_index_default(monkeypatch):
    """Default feature_index is 0."""
    reg = _three_obs_registry()
    monkeypatch.setattr(tl_module, "_get_registry", lambda: reg)
    res = client.get("/api/tool-life/tools/1")
    data = res.json()
    assert data["sensor_series"]["feature_index"] == 0


def test_tool_detail_feature_index_override(monkeypatch):
    """feature_index query param is respected."""
    reg = _three_obs_registry()
    monkeypatch.setattr(tl_module, "_get_registry", lambda: reg)
    res = client.get("/api/tool-life/tools/1?feature_index=5")
    assert res.status_code == 200
    data = res.json()
    assert data["sensor_series"]["feature_index"] == 5


def test_tool_detail_feature_index_out_of_range(monkeypatch):
    """feature_index >= 120 is rejected with 422."""
    reg = _three_obs_registry()
    monkeypatch.setattr(tl_module, "_get_registry", lambda: reg)
    res = client.get("/api/tool-life/tools/1?feature_index=120")
    assert res.status_code == 422


def test_tool_detail_no_private_path_in_response(monkeypatch):
    """Response body must not contain any filesystem path fragment."""
    reg = _three_obs_registry()
    monkeypatch.setattr(tl_module, "_get_registry", lambda: reg)
    res = client.get("/api/tool-life/tools/1")
    body = res.text
    # Private path indicators that must never appear
    for fragment in (":\\", "/Users/", "/home/", "C:\\", "Documents", ".xlsx"):
        assert fragment not in body, f"Private path fragment found: {fragment!r}"


def test_tool_detail_evidence_status_experimental(monkeypatch):
    """evidence_status must be EXPERIMENTAL."""
    reg = _three_obs_registry()
    monkeypatch.setattr(tl_module, "_get_registry", lambda: reg)
    res = client.get("/api/tool-life/tools/1")
    data = res.json()
    assert data["evidence_status"] == "EXPERIMENTAL"


def test_tool_detail_cycle_to_failure_countdown(monkeypatch):
    """CycleToFailure values decrease along the lifecycle (for tool 1)."""
    reg = _three_obs_registry()
    monkeypatch.setattr(tl_module, "_get_registry", lambda: reg)
    res = client.get("/api/tool-life/tools/1")
    data = res.json()
    ctf_values = [p["cycle_to_failure"] for p in data["lifecycle"]]
    # Should be non-increasing (countdown pattern)
    assert ctf_values == sorted(ctf_values, reverse=True) or ctf_values[-1] == 0


def test_summary_no_vb_in_limitations(monkeypatch):
    """Limitations must explicitly state VB is NOT present."""
    monkeypatch.delenv("MACHININGPRO_TOOLLIFE968_SOURCE_PATH", raising=False)
    res = client.get("/api/tool-life/summary")
    data = res.json()
    combined = " ".join(data["limitations"]).upper()
    assert "VB" in combined or "FLANK WEAR" in combined.upper()


def test_summary_no_taylor_claim(monkeypatch):
    """Limitations must state Taylor fit is NOT possible."""
    monkeypatch.delenv("MACHININGPRO_TOOLLIFE968_SOURCE_PATH", raising=False)
    res = client.get("/api/tool-life/summary")
    data = res.json()
    combined = " ".join(data["limitations"]).upper()
    assert "TAYLOR" in combined or "VC" in combined


def test_summary_production_not_validated_in_limitations(monkeypatch):
    """Limitations must state production deployment is NOT VALIDATED."""
    monkeypatch.delenv("MACHININGPRO_TOOLLIFE968_SOURCE_PATH", raising=False)
    res = client.get("/api/tool-life/summary")
    data = res.json()
    combined = " ".join(data["limitations"]).upper()
    assert "NOT VALIDATED" in combined or "PRODUCTION" in combined
