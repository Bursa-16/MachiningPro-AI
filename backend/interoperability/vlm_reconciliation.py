"""Deterministic comparison of advisory VLM evidence with deterministic dimensions (R3C).

``reconcile_advisory_evidence`` is a pure, explicitly invoked function. It reports
how each validated AI evidence item relates to the deterministic dimensions of an
already-produced ``DrawingIngestionResult``. It never edits, replaces, merges or
promotes anything: results are evidence ABOUT a comparison, AI evidence stays
ADVISORY, a conflict is only reported, and the deterministic result is neither
read for mutation nor copied.

Matching uses explicit structured identity only. An AI item names the
deterministic source object it was cut from (its ``evidence_reference``, which
R3B already validated against the region's trigger IDs); a deterministic
dimension names the source objects it was extracted from. They match when they
are on the same page and share such an object ID. Geometry, proximity and text
similarity are never used. If one-to-one identity cannot be established the
result is ``AMBIGUOUS`` or ``NOT_COMPARABLE``, never first-match.

Comparison rules are the repository's own and nothing new is invented:

* If the AI evidence carries a ``normalized_dimension``, the canonical
  ``DrawingDimension`` fields are compared exactly (unit, type, nominal value,
  tolerance).
* Otherwise the AI ``raw_candidate`` is compared with the deterministic
  ``original_text`` after the same NFC + strip normalization the OCR stage
  applies. Equal text agrees; different text is reported as a transcription
  conflict. No numeric epsilon, alias table or unit conversion exists here.

Only ``DIMENSION`` evidence is comparable in R3C; other kinds are reported
``NOT_COMPARABLE``. No I/O, clock, randomness, environment or network.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from enum import StrEnum, unique

from backend.interoperability.drawing import (
    DrawingDimension,
    DrawingIngestionResult,
)
from backend.interoperability.vlm_drawing import (
    DrawingAdvisoryReport,
    DrawingEvidenceOrigin,
    DrawingVlmEvidence,
    DrawingVlmEvidenceKind,
    DrawingVlmFinding,
    DrawingVlmRationale,
    DrawingVlmReconciliationStatus,
    DrawingVlmValidationStatus,
)

# Adapter identities written by the deterministic Phase 1B / 1C stages. They are
# literals here so this module never imports the parsers; a test pins them.
_VECTOR_ADAPTER_ID = "machiningpro.vector-pdf"
_OCR_ADAPTER_ID = "tesseract-ocr"

AGREEMENT_AUTO_PROMOTION_ALLOWED = False
CONFLICT_AUTO_RESOLUTION_ALLOWED = False
AI_ONLY_AUTO_PROMOTION_ALLOWED = False


@unique
class DrawingVlmComparison(StrEnum):
    AGREES = "AGREES"
    CONFLICTS = "CONFLICTS"
    AI_ONLY = "AI_ONLY"
    DETERMINISTIC_ONLY = "DETERMINISTIC_ONLY"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    AMBIGUOUS = "AMBIGUOUS"


@unique
class DrawingVlmComparisonReason(StrEnum):
    TEXT_EQUAL = "TEXT_EQUAL"
    TEXT_MISMATCH = "TEXT_MISMATCH"
    NORMALIZED_EQUAL = "NORMALIZED_EQUAL"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    VALUE_MISMATCH = "VALUE_MISMATCH"
    TOLERANCE_MISMATCH = "TOLERANCE_MISMATCH"
    NO_DETERMINISTIC_COUNTERPART = "NO_DETERMINISTIC_COUNTERPART"
    NO_AI_COUNTERPART = "NO_AI_COUNTERPART"
    UNSUPPORTED_KIND = "UNSUPPORTED_KIND"
    NO_STRUCTURED_IDENTITY = "NO_STRUCTURED_IDENTITY"
    NO_DETERMINISTIC_TEXT = "NO_DETERMINISTIC_TEXT"
    UNKNOWN_DETERMINISTIC_ORIGIN = "UNKNOWN_DETERMINISTIC_ORIGIN"
    MULTIPLE_AI_CANDIDATES = "MULTIPLE_AI_CANDIDATES"
    MULTIPLE_DETERMINISTIC_MATCHES = "MULTIPLE_DETERMINISTIC_MATCHES"


_C = DrawingVlmComparison
_R = DrawingVlmComparisonReason
_MISMATCH_RATIONALE = {
    _R.TEXT_MISMATCH: DrawingVlmRationale.VALUE_MISMATCH,
    _R.UNIT_MISMATCH: DrawingVlmRationale.UNIT_MISMATCH,
    _R.TYPE_MISMATCH: DrawingVlmRationale.TYPE_MISMATCH,
    _R.VALUE_MISMATCH: DrawingVlmRationale.VALUE_MISMATCH,
    _R.TOLERANCE_MISMATCH: DrawingVlmRationale.TOLERANCE_MISMATCH,
}


@dataclass(frozen=True)
class DrawingVlmReconciliation:
    """Relationship between AI evidence and deterministic dimensions.

    It holds identifiers and provenance references only, never engineering
    values, and carries no authority. ``finding`` is the existing advisory
    ``DrawingVlmFinding`` where that contract can express the relationship.
    """

    reconciliation_id: str
    status: DrawingVlmComparison
    reason: DrawingVlmComparisonReason
    ai_evidence_ids: tuple[str, ...]
    deterministic_ids: tuple[str, ...]
    provenance_ids: tuple[str, ...]
    finding: DrawingVlmFinding | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, DrawingVlmComparison):
            raise TypeError("DrawingVlmReconciliation.status must be DrawingVlmComparison")
        if not isinstance(self.reason, DrawingVlmComparisonReason):
            raise TypeError("DrawingVlmReconciliation.reason must be DrawingVlmComparisonReason")
        for name in ("ai_evidence_ids", "deterministic_ids", "provenance_ids"):
            value = getattr(self, name)
            if not isinstance(value, tuple) or any(
                not isinstance(item, str) or not item for item in value
            ):
                raise TypeError(f"DrawingVlmReconciliation.{name} must be a tuple of str")
            if len(set(value)) != len(value):
                raise ValueError(f"DrawingVlmReconciliation.{name} must not contain duplicates")
        if not self.reconciliation_id:
            raise ValueError("DrawingVlmReconciliation.reconciliation_id must not be blank")
        ai, det = len(self.ai_evidence_ids), len(self.deterministic_ids)
        shapes = {
            _C.AGREES: ai == 1 and det == 1,
            _C.CONFLICTS: ai == 1 and det == 1,
            _C.AI_ONLY: ai == 1 and det == 0,
            _C.DETERMINISTIC_ONLY: ai == 0 and det == 1,
            _C.NOT_COMPARABLE: ai == 1 and det <= 1,
            _C.AMBIGUOUS: ai >= 1 and det >= 1 and ai + det >= 3,
        }
        if not shapes[self.status]:
            raise ValueError("DrawingVlmReconciliation identifiers do not fit its status")
        if self.finding is not None:
            if not isinstance(self.finding, DrawingVlmFinding):
                raise TypeError("DrawingVlmReconciliation.finding must be DrawingVlmFinding")
            if self.finding.ai_evidence_ids != self.ai_evidence_ids:
                raise ValueError(
                    "DrawingVlmReconciliation.finding must reference the same AI evidence"
                )


def _digest(*parts: object) -> str:
    return hashlib.sha256("\x1f".join(str(part) for part in parts).encode("utf-8")).hexdigest()[
        :24
    ]


def _text(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip()


def _origin(dimension: DrawingDimension) -> DrawingEvidenceOrigin | None:
    location = dimension.source_location
    adapter = location.adapter_id if location is not None else None
    if adapter == _VECTOR_ADAPTER_ID:
        return DrawingEvidenceOrigin.VECTOR
    if adapter == _OCR_ADAPTER_ID:
        return DrawingEvidenceOrigin.OCR
    return None


def _structured_mismatch(
    ai: DrawingDimension, det: DrawingDimension
) -> DrawingVlmComparisonReason | None:
    if ai.unit != det.unit:
        return _R.UNIT_MISMATCH
    if ai.dimension_type != det.dimension_type:
        return _R.TYPE_MISMATCH
    if ai.nominal_value != det.nominal_value:
        return _R.VALUE_MISMATCH
    ai_tol, det_tol = ai.tolerance, det.tolerance
    if (ai_tol is None) != (det_tol is None):
        return _R.TOLERANCE_MISMATCH
    if ai_tol is not None and det_tol is not None:
        if (
            ai_tol.tolerance_type != det_tol.tolerance_type
            or ai_tol.unit != det_tol.unit
            or ai_tol.upper_value != det_tol.upper_value
            or ai_tol.lower_value != det_tol.lower_value
        ):
            return _R.TOLERANCE_MISMATCH
    return None


def _compare(
    evidence: DrawingVlmEvidence, dimension: DrawingDimension
) -> tuple[DrawingVlmComparison, DrawingVlmComparisonReason]:
    if _origin(dimension) is None:
        return _C.NOT_COMPARABLE, _R.UNKNOWN_DETERMINISTIC_ORIGIN
    if evidence.normalized_dimension is not None:
        mismatch = _structured_mismatch(evidence.normalized_dimension, dimension)
        if mismatch is None:
            return _C.AGREES, _R.NORMALIZED_EQUAL
        return _C.CONFLICTS, mismatch
    original = dimension.source_location.original_text if dimension.source_location else None
    if original is None or not original.strip():
        return _C.NOT_COMPARABLE, _R.NO_DETERMINISTIC_TEXT
    if _text(evidence.raw_candidate) == _text(original):
        return _C.AGREES, _R.TEXT_EQUAL
    return _C.CONFLICTS, _R.TEXT_MISMATCH


def _build(
    status: DrawingVlmComparison,
    reason: DrawingVlmComparisonReason,
    evidence: tuple[DrawingVlmEvidence, ...],
    dimensions: tuple[DrawingDimension, ...],
) -> DrawingVlmReconciliation:
    ai_ids = tuple(sorted(item.evidence_id for item in evidence))
    det_ids = tuple(sorted(item.dimension_id for item in dimensions))
    provenance: set[str] = set()
    for item in evidence:
        provenance.update(item.source_location.source_object_ids)
    for dim in dimensions:
        if dim.source_location is not None:
            provenance.update(dim.source_location.source_object_ids)
    finding = _finding(status, reason, ai_ids, dimensions)
    return DrawingVlmReconciliation(
        reconciliation_id="vlm-rec-" + _digest(status.value, reason.value, *ai_ids, "|", *det_ids),
        status=status,
        reason=reason,
        ai_evidence_ids=ai_ids,
        deterministic_ids=det_ids,
        provenance_ids=tuple(sorted(provenance)),
        finding=finding,
    )


def _finding(
    status: DrawingVlmComparison,
    reason: DrawingVlmComparisonReason,
    ai_ids: tuple[str, ...],
    dimensions: tuple[DrawingDimension, ...],
) -> DrawingVlmFinding | None:
    """Express the relationship with the existing finding contract where exact."""
    base = "vlm-finding-" + _digest(
        status.value, reason.value, *ai_ids, *(d.dimension_id for d in dimensions)
    )
    if status is _C.AGREES or status is _C.CONFLICTS:
        origin = _origin(dimensions[0])
        if origin is None:
            return None
        support = (dimensions[0].dimension_id,)
        if status is _C.AGREES:
            return DrawingVlmFinding(
                finding_id=base,
                status=DrawingVlmReconciliationStatus.CORROBORATED,
                rationale=DrawingVlmRationale.EXACT_MATCH,
                ai_evidence_ids=ai_ids,
                deterministic_support_ids=support,
                deterministic_origins=(origin,),
            )
        return DrawingVlmFinding(
            finding_id=base,
            status=DrawingVlmReconciliationStatus.CONFLICT,
            rationale=_MISMATCH_RATIONALE[reason],
            ai_evidence_ids=ai_ids,
            deterministic_support_ids=support,
            deterministic_origins=(origin,),
            conflict_ids=support,
        )
    if status is _C.AI_ONLY:
        return DrawingVlmFinding(
            finding_id=base,
            status=DrawingVlmReconciliationStatus.ADVISORY_ONLY,
            rationale=DrawingVlmRationale.NO_DETERMINISTIC_EVIDENCE,
            ai_evidence_ids=ai_ids,
        )
    if status is _C.NOT_COMPARABLE and reason is _R.UNSUPPORTED_KIND:
        return DrawingVlmFinding(
            finding_id=base,
            status=DrawingVlmReconciliationStatus.ADVISORY_ONLY,
            rationale=DrawingVlmRationale.UNSUPPORTED_KIND,
            ai_evidence_ids=ai_ids,
        )
    return None


def reconcile_advisory_evidence(
    base_result: DrawingIngestionResult, report: DrawingAdvisoryReport
) -> tuple[DrawingVlmReconciliation, ...]:
    """Compare ``report`` evidence with ``base_result`` dimensions, report-only.

    Results are sorted by ``reconciliation_id`` so the output does not depend on
    input order. Raises ``ValueError`` for duplicate identifiers.
    """
    if not isinstance(base_result, DrawingIngestionResult):
        raise TypeError("base_result must be DrawingIngestionResult")
    if not isinstance(report, DrawingAdvisoryReport):
        raise TypeError("report must be DrawingAdvisoryReport")

    evidence = tuple(
        sorted(
            (e for e in report.evidence if e.validation_status is DrawingVlmValidationStatus.VALID),
            key=lambda item: item.evidence_id,
        )
    )
    document = base_result.document
    known = document.all_dimensions if document is not None else ()
    dimensions = tuple(sorted(known, key=lambda d: d.dimension_id))
    if len({e.evidence_id for e in evidence}) != len(evidence):
        raise ValueError("duplicate AI evidence identifiers")
    if len({d.dimension_id for d in dimensions}) != len(dimensions):
        raise ValueError("duplicate deterministic dimension identifiers")
    triggers = {region.region_id: set(region.trigger_evidence_ids) for region in report.regions}

    results: list[DrawingVlmReconciliation] = []
    edges: dict[str, set[str]] = {}
    ai_by_id = {e.evidence_id: e for e in evidence}
    dim_by_id = {d.dimension_id: d for d in dimensions}
    for item in evidence:
        if item.evidence_kind is not DrawingVlmEvidenceKind.DIMENSION:
            results.append(_build(_C.NOT_COMPARABLE, _R.UNSUPPORTED_KIND, (item,), ()))
            continue
        if item.region_id not in triggers:
            raise ValueError("AI evidence must reference a report region")
        keys = set(item.source_location.source_object_ids) & triggers[item.region_id]
        if not keys:
            results.append(_build(_C.NOT_COMPARABLE, _R.NO_STRUCTURED_IDENTITY, (item,), ()))
            continue
        page = item.source_location.page_number
        edges[item.evidence_id] = {
            dim.dimension_id
            for dim in dimensions
            if dim.source_location is not None
            and dim.source_location.page_number == page
            and keys & set(dim.source_location.source_object_ids)
        }

    # Connected components of the identity graph decide one-to-one safety.
    dim_edges: dict[str, set[str]] = {}
    for ai_id, dim_ids in edges.items():
        for dim_id in dim_ids:
            dim_edges.setdefault(dim_id, set()).add(ai_id)
    seen_ai: set[str] = set()
    seen_dim: set[str] = set()
    for start in sorted(edges):
        if start in seen_ai:
            continue
        component_ai: set[str] = set()
        component_dim: set[str] = set()
        stack = [("ai", start)]
        while stack:
            kind, node = stack.pop()
            if kind == "ai":
                if node in component_ai:
                    continue
                component_ai.add(node)
                stack.extend(("dim", d) for d in edges[node])
            else:
                if node in component_dim:
                    continue
                component_dim.add(node)
                stack.extend(("ai", a) for a in dim_edges.get(node, ()))
        seen_ai |= component_ai
        seen_dim |= component_dim
        ai_items = tuple(ai_by_id[a] for a in sorted(component_ai))
        dim_items = tuple(dim_by_id[d] for d in sorted(component_dim))
        if not dim_items:
            results.append(_build(_C.AI_ONLY, _R.NO_DETERMINISTIC_COUNTERPART, ai_items, ()))
        elif len(ai_items) == 1 and len(dim_items) == 1:
            status, reason = _compare(ai_items[0], dim_items[0])
            results.append(_build(status, reason, ai_items, dim_items))
        else:
            reason = (
                _R.MULTIPLE_AI_CANDIDATES
                if len(ai_items) > 1
                else _R.MULTIPLE_DETERMINISTIC_MATCHES
            )
            results.append(_build(_C.AMBIGUOUS, reason, ai_items, dim_items))
    for dim in dimensions:
        if dim.dimension_id not in seen_dim:
            results.append(_build(_C.DETERMINISTIC_ONLY, _R.NO_AI_COUNTERPART, (), (dim,)))
    return tuple(sorted(results, key=lambda item: item.reconciliation_id))


__all__ = [
    "AGREEMENT_AUTO_PROMOTION_ALLOWED",
    "AI_ONLY_AUTO_PROMOTION_ALLOWED",
    "CONFLICT_AUTO_RESOLUTION_ALLOWED",
    "DrawingVlmComparison",
    "DrawingVlmComparisonReason",
    "DrawingVlmReconciliation",
    "reconcile_advisory_evidence",
]
