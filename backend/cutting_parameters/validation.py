"""Empirical data authority validation (Stage 3G).

Provides deterministic functions that check whether a
:class:`~backend.cutting_parameters.models.CuttingParameterRecord` meets
the provenance and evidence requirements for authoritative use.

Fail-closed contract
--------------------
``require_authoritative`` raises :class:`~backend.empirical.exceptions.EmpiricalDataError`
whenever the record does not meet the authoritative threshold.  Callers
that need a softer check can use :func:`is_usable_for_authority`.

Authority model (from the project spec)
----------------------------------------
DETERMINISTIC PHYSICS / KINEMATICS  →  AUTHORITATIVE (Stages 3A–3F)
EMPIRICAL ENGINEERING DATA          →  SOURCE-BOUNDED AUTHORITATIVE
                                       (only when provenance is valid)
AI                                  →  ADVISORY ONLY — can never override

:data:`ACCEPTABLE_AUTHORITATIVE_SOURCE_TYPES` controls which
:class:`~backend.domain.enums.ProvenanceType` values are acceptable for
an authoritative empirical record.
"""

from __future__ import annotations

from backend.cutting_parameters.models import (
    AUTHORITATIVE_STATUSES,
    CuttingParameterRecord,
)
from backend.domain.enums import ProvenanceType
from backend.empirical.exceptions import EmpiricalDataError

__all__ = [
    "ACCEPTABLE_AUTHORITATIVE_SOURCE_TYPES",
    "is_usable_for_authority",
    "require_authoritative",
]

#: ProvenanceType values that are acceptable for authoritative empirical
#: records.  AI_SUGGESTION is explicitly excluded — AI output is advisory
#: only and must never be admitted as authoritative engineering data.
ACCEPTABLE_AUTHORITATIVE_SOURCE_TYPES: frozenset[ProvenanceType] = frozenset(
    {
        ProvenanceType.MANUFACTURER_DATA,
        ProvenanceType.MATERIAL_STANDARD,
        ProvenanceType.ENGINEERING_STANDARD,
        ProvenanceType.LITERATURE,
        ProvenanceType.HISTORICAL_PROCESS_DATA,
        ProvenanceType.USER_INPUT,  # explicitly supplied by a qualified engineer
    }
)

#: ProvenanceType values that are never acceptable for authoritative use.
REJECTED_SOURCE_TYPES: frozenset[ProvenanceType] = frozenset(
    {ProvenanceType.AI_SUGGESTION, ProvenanceType.UNKNOWN}
)


def is_usable_for_authority(record: CuttingParameterRecord) -> bool:
    """Return ``True`` when *record* satisfies all authority requirements.

    Requirements:
    1. ``evidence_status`` is in :data:`AUTHORITATIVE_STATUSES`.
    2. ``provenance.source_reference`` is not ``None``.
    3. ``provenance.source_type`` is in
       :data:`ACCEPTABLE_AUTHORITATIVE_SOURCE_TYPES`.
    4. ``provenance.source_type`` is NOT in :data:`REJECTED_SOURCE_TYPES`
       (AI_SUGGESTION and UNKNOWN are explicitly blocked).
    """
    if record.evidence_status not in AUTHORITATIVE_STATUSES:
        return False
    if record.provenance.source_reference is None:
        return False
    if record.provenance.source_type in REJECTED_SOURCE_TYPES:
        return False
    if record.provenance.source_type not in ACCEPTABLE_AUTHORITATIVE_SOURCE_TYPES:
        return False
    return True


def require_authoritative(record: CuttingParameterRecord) -> CuttingParameterRecord:
    """Return *record* unchanged, or raise :class:`EmpiricalDataError`.

    Raises:
        EmpiricalDataError: when *record* does not meet authority requirements.

    Use this as a deterministic gate before passing an empirical record
    into a calculation.  Fail closed: an unsourced or AI-generated record
    never passes.
    """
    if is_usable_for_authority(record):
        return record

    # Build a specific diagnosis for the caller.
    reasons: list[str] = []
    if record.evidence_status not in AUTHORITATIVE_STATUSES:
        reasons.append(
            f"evidence_status is {record.evidence_status!r} "
            f"(required: one of {sorted(s.value for s in AUTHORITATIVE_STATUSES)})"
        )
    if record.provenance.source_reference is None:
        reasons.append("provenance.source_reference is None")
    if record.provenance.source_type in REJECTED_SOURCE_TYPES:
        reasons.append(
            f"provenance.source_type {record.provenance.source_type!r} "
            "is not acceptable for authoritative records (AI_SUGGESTION "
            "and UNKNOWN are always rejected)"
        )
    elif record.provenance.source_type not in ACCEPTABLE_AUTHORITATIVE_SOURCE_TYPES:
        reasons.append(
            f"provenance.source_type {record.provenance.source_type!r} "
            "is not in ACCEPTABLE_AUTHORITATIVE_SOURCE_TYPES"
        )

    raise EmpiricalDataError(
        f"record {record.record_id!r} is not authoritative: "
        + "; ".join(reasons)
    )
