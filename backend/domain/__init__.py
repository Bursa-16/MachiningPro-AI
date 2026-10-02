"""Machinery AI engineering domain model (Stage 2).

Strongly typed, deterministic, fail-closed domain entities shared by every
later module. Deterministic engineering rules are authoritative; AI is
advisory only and may never silently override engineering constraints.
"""

from backend.domain.base import (
    Provenance,
    entity_as_dict,
    json_safe,
)
from backend.domain.enums import (
    CoolantMode,
    FeatureType,
    MachineType,
    MaterialFamily,
    OperationStatus,
    OperationType,
    ProvenanceType,
    ResultStatus,
    ToolType,
)
from backend.domain.exceptions import (
    DomainError,
    DuplicateRuleError,
    RuleError,
    RuleNotFoundError,
    UnitError,
    UnknownUnitError,
    ValidationError,
)
from backend.domain.feature import Feature
from backend.domain.machine import Machine
from backend.domain.material import Material
from backend.domain.operation import Operation
from backend.domain.parameters import MachiningParameters
from backend.domain.part import Part
from backend.domain.result import EngineeringResult
from backend.domain.tool import Tool
from backend.domain.units import Quantity, Unit

__all__ = [
    "CoolantMode",
    "DomainError",
    "DuplicateRuleError",
    "EngineeringResult",
    "Feature",
    "FeatureType",
    "Machine",
    "MachineType",
    "MachiningParameters",
    "Material",
    "MaterialFamily",
    "Operation",
    "OperationStatus",
    "OperationType",
    "Part",
    "Provenance",
    "ProvenanceType",
    "Quantity",
    "ResultStatus",
    "RuleError",
    "RuleNotFoundError",
    "Tool",
    "ToolType",
    "Unit",
    "UnitError",
    "UnknownUnitError",
    "ValidationError",
    "entity_as_dict",
    "json_safe",
]
