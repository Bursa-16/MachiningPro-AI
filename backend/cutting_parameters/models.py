"""Empirical cutting-parameter record models (Stage 3G).

Defines the strongly typed, provenance-mandatory data contracts for
empirical machining information entering MachineryPro AI.

Authority model
---------------
These records represent *source-bounded authoritative* engineering data.
A record is only as authoritative as its provenance.  Every field that
makes a record usable in a deterministic calculation must be present and
validated; anything missing causes a fail-closed rejection.

No production seed data lives here.  Records are constructed by callers
who supply real provenance (source document, revision, page/table).

Design principles
-----------------
* All numeric values use :class:`~backend.domain.units.Quantity` (Decimal +
  explicit Unit).  No bare floats.
* Ranges are explicit (min / max pair); no implicit midpoints.
* Provenance is mandatory for authoritative status.
* Process and material applicability are typed enums; no free-form strings
  for controlled vocabulary.
* Models are frozen dataclasses — immutable once constructed.
* Validation is in ``__post_init__``; no silent coercion.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.base import (
    Provenance,
    entity_as_dict,
    optional_non_empty_str,
    require_non_empty_str,
)
from backend.domain.enums import (
    CoolantMode,
    IsoMaterialGroup,
    OperationType,
    ToolMaterial,
    ToolType,
)
from backend.domain.exceptions import ValidationError
from backend.domain.units import Quantity, Unit

__all__ = [
    "EvidenceStatus",
    "ParameterType",
    "QuantityRange",
    "ApplicabilityScope",
    "CuttingParameterRecord",
]


# ---------------------------------------------------------------------------
# Evidence / authority status
# ---------------------------------------------------------------------------

from enum import StrEnum


class EvidenceStatus(StrEnum):
    """Engineering evidence / authority classification for empirical records.

    This is an engineering classification, not a probabilistic score.

    AUTHORITATIVE
        Sourced from a primary authority (manufacturer technical bulletin,
        ISO/DIN standard, peer-reviewed experimental measurement).  May be
        used as authoritative input to deterministic calculations.

    REFERENCE_ONLY
        Taken from a secondary source (textbook, training material, general
        handbook excerpt) without a primary experiment citation.  Useful for
        orientation but must not be used as a direct deterministic input
        without validation.

    EXPERIMENTAL
        From an internal experiment or pilot study.  May be promoted to
        AUTHORITATIVE after review and sign-off.

    UNVERIFIED
        Source is not independently confirmed.  May not be treated as
        authoritative.  Fail-closed behaviour applies.
    """

    AUTHORITATIVE = "AUTHORITATIVE"
    REFERENCE_ONLY = "REFERENCE_ONLY"
    EXPERIMENTAL = "EXPERIMENTAL"
    UNVERIFIED = "UNVERIFIED"


#: Evidence statuses that may be treated as authoritative in calculations.
AUTHORITATIVE_STATUSES: frozenset[EvidenceStatus] = frozenset(
    {EvidenceStatus.AUTHORITATIVE, EvidenceStatus.EXPERIMENTAL}
)


# ---------------------------------------------------------------------------
# Parameter type / identity
# ---------------------------------------------------------------------------

class ParameterType(StrEnum):
    """Controlled vocabulary of empirical cutting-parameter identities.

    Only parameter types whose units and semantics are unambiguous within
    the existing :class:`~backend.domain.units.Unit` model are defined.

    Stage 3G prioritises the parameters directly needed by the current
    deterministic cores (Stages 3A–3F): cutting speed, feed per tooth,
    feed per revolution.  Additional types are included only where their
    units are non-ambiguous.
    """

    CUTTING_SPEED = "CUTTING_SPEED"           # Vc — Unit.M_MIN
    FEED_PER_TOOTH = "FEED_PER_TOOTH"         # fz — Unit.MM_TOOTH
    FEED_PER_REV = "FEED_PER_REV"             # f  — Unit.MM_REV
    AXIAL_DEPTH_OF_CUT = "AXIAL_DEPTH_OF_CUT"  # ap — Unit.MM
    RADIAL_ENGAGEMENT = "RADIAL_ENGAGEMENT"   # ae — Unit.MM
    SPECIFIC_CUTTING_FORCE = "SPECIFIC_CUTTING_FORCE"  # Kc1.1 — Unit.MPA
    TOOL_LIFE_CONSTANT = "TOOL_LIFE_CONSTANT"           # Taylor C — Unit.M_MIN
    TOOL_LIFE_EXPONENT = "TOOL_LIFE_EXPONENT"           # Taylor n — Unit.DIMENSIONLESS


#: Canonical unit for each ParameterType.  Used during validation to ensure
#: record values carry the expected unit.
PARAMETER_CANONICAL_UNIT: dict[ParameterType, Unit] = {
    ParameterType.CUTTING_SPEED: Unit.M_MIN,
    ParameterType.FEED_PER_TOOTH: Unit.MM_TOOTH,
    ParameterType.FEED_PER_REV: Unit.MM_REV,
    ParameterType.AXIAL_DEPTH_OF_CUT: Unit.MM,
    ParameterType.RADIAL_ENGAGEMENT: Unit.MM,
    ParameterType.SPECIFIC_CUTTING_FORCE: Unit.MPA,
    ParameterType.TOOL_LIFE_CONSTANT: Unit.M_MIN,
    ParameterType.TOOL_LIFE_EXPONENT: Unit.DIMENSIONLESS,
}


# ---------------------------------------------------------------------------
# Quantity range
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class QuantityRange:
    """An immutable, unit-safe inclusive range [min_value, max_value].

    Both bounds must carry the same :class:`~backend.domain.units.Unit`.
    ``min_value.value <= max_value.value`` is enforced.

    A point value is represented as a range where min == max.
    """

    min_value: Quantity
    max_value: Quantity

    def __post_init__(self) -> None:
        if not isinstance(self.min_value, Quantity):
            raise ValidationError("min_value must be a Quantity")
        if not isinstance(self.max_value, Quantity):
            raise ValidationError("max_value must be a Quantity")
        if self.min_value.unit is not self.max_value.unit:
            raise ValidationError(
                f"min_value and max_value must share the same unit; "
                f"got {self.min_value.unit} and {self.max_value.unit}"
            )
        if self.min_value.value > self.max_value.value:
            raise ValidationError(
                f"min_value ({self.min_value.value}) must be <= "
                f"max_value ({self.max_value.value})"
            )

    @property
    def unit(self) -> Unit:
        """The shared unit of both bounds."""
        return self.min_value.unit

    def contains(self, value: Quantity) -> bool:
        """True when *value* lies within [min_value, max_value] (inclusive).

        Raises :class:`~backend.domain.exceptions.ValidationError` when
        *value* carries a different unit — no implicit conversion.
        """
        if not isinstance(value, Quantity):
            raise ValidationError("value must be a Quantity")
        self.min_value.require_same_unit(value, context="QuantityRange.contains")
        return self.min_value.value <= value.value <= self.max_value.value

    @property
    def is_point(self) -> bool:
        """True when both bounds are equal (point value, not a range)."""
        return self.min_value.value == self.max_value.value

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Applicability scope
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ApplicabilityScope:
    """Metadata describing the engineering context in which an empirical
    record is valid.

    All fields are optional (``None`` means "not constrained to a specific
    value").  At least :attr:`operation_type` should be provided for any
    practically useful record.

    A ``None`` field is *not* equivalent to "any value is acceptable"; it
    means "this dimension was not specified by the source".  Callers that
    require a match on a specific dimension should treat ``None`` as a
    partial match (match) or as unknown (do not use), according to their
    lookup policy.
    """

    operation_type: OperationType | None = None
    iso_material_group: IsoMaterialGroup | None = None
    tool_material: ToolMaterial | None = None
    tool_type: ToolType | None = None
    coolant_mode: CoolantMode | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.operation_type is not None and not isinstance(
            self.operation_type, OperationType
        ):
            raise ValidationError("operation_type must be an OperationType or None")
        if self.iso_material_group is not None and not isinstance(
            self.iso_material_group, IsoMaterialGroup
        ):
            raise ValidationError(
                "iso_material_group must be an IsoMaterialGroup or None"
            )
        if self.tool_material is not None and not isinstance(
            self.tool_material, ToolMaterial
        ):
            raise ValidationError("tool_material must be a ToolMaterial or None")
        if self.tool_type is not None and not isinstance(self.tool_type, ToolType):
            raise ValidationError("tool_type must be a ToolType or None")
        if self.coolant_mode is not None and not isinstance(
            self.coolant_mode, CoolantMode
        ):
            raise ValidationError("coolant_mode must be a CoolantMode or None")
        object.__setattr__(
            self, "notes", optional_non_empty_str(self.notes, "notes")
        )

    def matches(self, query: ApplicabilityScope) -> bool:
        """True when this scope is compatible with *query*.

        A ``None`` field in *self* is treated as "unspecified by source" and
        always matches the corresponding query dimension.  A non-None field
        must equal the query field exactly (or the query field must be None,
        meaning "not filtering on that dimension").

        This is a *structural* match — not a ranking or scoring function.
        """
        pairs = [
            (self.operation_type, query.operation_type),
            (self.iso_material_group, query.iso_material_group),
            (self.tool_material, query.tool_material),
            (self.tool_type, query.tool_type),
            (self.coolant_mode, query.coolant_mode),
        ]
        for self_val, query_val in pairs:
            if self_val is None:
                # Unspecified in record — matches any query value.
                continue
            if query_val is None:
                # Query does not filter on this dimension — matches.
                continue
            if self_val != query_val:
                return False
        return True

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Core empirical record
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CuttingParameterRecord:
    """One empirical cutting-parameter observation / approved data entry.

    Represents a single authoritative (or classified) engineering data
    point: a named parameter with an explicit range, scoped to a process
    context, with mandatory provenance.

    Immutability guarantee
    ----------------------
    The record is a frozen dataclass.  Once constructed it cannot be
    mutated.  Provenance is permanently bound to the value.

    Authoritative status
    --------------------
    A record is authoritative only when:

    * ``evidence_status`` is in :data:`AUTHORITATIVE_STATUSES`, AND
    * ``provenance`` carries a non-None ``source_reference``.

    Use :meth:`is_authoritative` to test this condition.

    Fields
    ------
    record_id
        Stable, unique identifier within the catalog.  Must be non-empty.
    parameter_type
        The engineering parameter identity (:class:`ParameterType`).
    value_range
        The parameter value as an inclusive range.  The unit in the range
        must match :data:`PARAMETER_CANONICAL_UNIT` for this parameter type.
    applicability
        The engineering context in which this record is valid.
    provenance
        Mandatory source traceability.  ``source_reference`` should
        identify the document (e.g. "Sandvik Coromant General Catalogue
        2023, Table 3.4, p. 187").
    evidence_status
        Engineering classification of this record's authority.
    notes
        Optional human-readable limitations or caveats.
    """

    record_id: str
    parameter_type: ParameterType
    value_range: QuantityRange
    applicability: ApplicabilityScope
    provenance: Provenance
    evidence_status: EvidenceStatus
    notes: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "record_id",
            require_non_empty_str(self.record_id, "record_id"),
        )
        if not isinstance(self.parameter_type, ParameterType):
            raise ValidationError("parameter_type must be a ParameterType")
        if not isinstance(self.value_range, QuantityRange):
            raise ValidationError("value_range must be a QuantityRange")
        # Enforce canonical unit for the parameter type.
        expected_unit = PARAMETER_CANONICAL_UNIT[self.parameter_type]
        if self.value_range.unit is not expected_unit:
            raise ValidationError(
                f"parameter_type {self.parameter_type} requires unit "
                f"{expected_unit.value}; got {self.value_range.unit.value}"
            )
        if not isinstance(self.applicability, ApplicabilityScope):
            raise ValidationError("applicability must be an ApplicabilityScope")
        if not isinstance(self.provenance, Provenance):
            raise ValidationError("provenance must be a Provenance")
        if not isinstance(self.evidence_status, EvidenceStatus):
            raise ValidationError("evidence_status must be an EvidenceStatus")
        object.__setattr__(
            self, "notes", optional_non_empty_str(self.notes, "notes")
        )
        # Fail closed: AUTHORITATIVE status requires a source_reference.
        if (
            self.evidence_status in AUTHORITATIVE_STATUSES
            and self.provenance.source_reference is None
        ):
            raise ValidationError(
                f"evidence_status {self.evidence_status} requires "
                "provenance.source_reference to be set"
            )

    @property
    def is_authoritative(self) -> bool:
        """True when this record may be used as authoritative engineering input.

        Requires AUTHORITATIVE or EXPERIMENTAL evidence status AND a
        non-None ``provenance.source_reference``.
        """
        return (
            self.evidence_status in AUTHORITATIVE_STATUSES
            and self.provenance.source_reference is not None
        )

    def matches_scope(self, query: ApplicabilityScope) -> bool:
        """True when this record's applicability is compatible with *query*."""
        return self.applicability.matches(query)

    def as_dict(self) -> dict[str, object]:
        """Deterministic serialization-friendly representation."""
        return entity_as_dict(self)
