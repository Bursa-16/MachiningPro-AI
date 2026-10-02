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

__all__ = ["EmpiricalDataError"]
