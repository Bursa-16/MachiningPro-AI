"""Empirical engineering data layer for MachineryPro AI.

Stage 3G establishes the authoritative DATA CONTRACTS for empirical
machining information: provenance requirements, applicability metadata,
unit-safe parameter representation, and fail-closed validation.

No production seed data is included in this package.  Every record
admitted to the empirical layer must carry explicit provenance before
it may be treated as authoritative.

Authority model
---------------
Deterministic physics/kinematics (Stages 3A–3F) are authoritative by
construction.  Empirical data is *source-bounded* authoritative: it is
only as trustworthy as its provenance.  AI output is advisory only and
can never elevate itself to authoritative status through this layer.
"""

from backend.empirical.exceptions import EmpiricalDataError
from backend.empirical.models import VP100EmpiricalRecord, VP100SourceMeta
from backend.empirical.registry import VP100EmpiricalRegistry, get_vp100_registry
from backend.empirical.seed_toollife968 import seed_toollife968_registry
from backend.empirical.seed_vp100 import seed_vp100_registry
from backend.empirical.toollife968_models import (
    ToolLife968Observation,
    ToolLife968SourceMeta,
)
from backend.empirical.toollife968_registry import (
    ToolLife968Registry,
    get_toollife968_registry,
)

__all__ = [
    "EmpiricalDataError",
    "VP100EmpiricalRecord",
    "VP100SourceMeta",
    "VP100EmpiricalRegistry",
    "get_vp100_registry",
    "seed_vp100_registry",
    "ToolLife968Observation",
    "ToolLife968SourceMeta",
    "ToolLife968Registry",
    "get_toollife968_registry",
    "seed_toollife968_registry",
]
