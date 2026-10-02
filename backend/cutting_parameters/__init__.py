"""Cutting-parameter empirical data foundation (Stage 3G).

Provides the typed, provenance-mandatory data contracts for empirical
machining parameter records entering MachineryPro AI.

Recommendations are generated deterministically from registered rules and
data; every recommendation carries its rule ID and citations (Stage 3-4).

Stage 3G establishes the DATA LAYER:

* :class:`~backend.cutting_parameters.models.CuttingParameterRecord` —
  the core empirical record (parameter identity, unit-safe range,
  applicability scope, provenance, evidence status).
* :class:`~backend.cutting_parameters.models.QuantityRange` —
  explicit min/max range with unit validation.
* :class:`~backend.cutting_parameters.models.ApplicabilityScope` —
  typed engineering context (process, material group, tool material, …).
* :class:`~backend.cutting_parameters.models.ParameterType` —
  controlled vocabulary of parameter identities.
* :class:`~backend.cutting_parameters.models.EvidenceStatus` —
  engineering authority classification.
* :class:`~backend.cutting_parameters.registry.CuttingParameterRegistry` —
  deterministic in-memory catalog with fail-closed exact-ID lookup and
  scope-filtered collection queries.
* :mod:`~backend.cutting_parameters.validation` — authority gate
  functions (``require_authoritative``, ``is_usable_for_authority``).

No production seed data is included.  All numeric values must be
supplied with explicit, verifiable provenance.
"""

from backend.cutting_parameters.models import (
    AUTHORITATIVE_STATUSES,
    PARAMETER_CANONICAL_UNIT,
    ApplicabilityScope,
    CuttingParameterRecord,
    EvidenceStatus,
    ParameterType,
    QuantityRange,
)
from backend.cutting_parameters.registry import CuttingParameterRegistry
from backend.cutting_parameters.validation import (
    ACCEPTABLE_AUTHORITATIVE_SOURCE_TYPES,
    REJECTED_SOURCE_TYPES,
    is_usable_for_authority,
    require_authoritative,
)

__all__ = [
    "ACCEPTABLE_AUTHORITATIVE_SOURCE_TYPES",
    "AUTHORITATIVE_STATUSES",
    "PARAMETER_CANONICAL_UNIT",
    "REJECTED_SOURCE_TYPES",
    "ApplicabilityScope",
    "CuttingParameterRecord",
    "CuttingParameterRegistry",
    "EvidenceStatus",
    "ParameterType",
    "QuantityRange",
    "is_usable_for_authority",
    "require_authoritative",
]
