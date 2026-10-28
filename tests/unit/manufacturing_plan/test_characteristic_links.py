"""Tests for characteristic links."""
import pytest
from backend.manufacturing_plan.characteristic_links import (
    OperationCharacteristicRole,
    InspectionMethodSuitability,
    OperationCharacteristicLink,
    InspectionCharacteristicLink,
    build_operation_char_links,
    build_inspection_char_links,
)
from backend.manufacturing_plan.characteristic import (
    ManufacturingCharacteristic, CharacteristicType, CharacteristicCriticality,
)
from backend.manufacturing_plan.inspection_library import InspectionMethod


def _char(cid="c1", char_type=CharacteristicType.DIMENSION):
    return ManufacturingCharacteristic(
        characteristic_id=cid,
        source_requirement_id=None,
        feature_id="f1",
        char_type=char_type,
        label=f"char_{cid}",
        nominal_value=10.0,
        upper_limit=10.05,
        lower_limit=9.95,
    )


class TestOperationCharacteristicRole:
    def test_all_roles(self):
        roles = {e.value for e in OperationCharacteristicRole}
        assert {"CREATES", "CONTROLS", "CONTRIBUTES", "REFERENCES", "VERIFIES"} == roles


class TestInspectionMethodSuitability:
    def test_all_values(self):
        vals = {e.value for e in InspectionMethodSuitability}
        assert {"SUITABLE", "CONDITIONAL", "INSUFFICIENT_DATA", "NOT_SUITABLE"} == vals


class TestOperationCharacteristicLink:
    def test_frozen_dataclass(self):
        link = OperationCharacteristicLink(
            link_id="l1",
            step_id="s1",
            operation_type="DRILLING",
            char_id="c1",
            char_type=CharacteristicType.DIMENSION,
            role=OperationCharacteristicRole.CREATES,
            notes="",
        )
        with pytest.raises((AttributeError, TypeError)):
            link.role = OperationCharacteristicRole.CONTROLS  # type: ignore


class TestBuildOperationCharLinks:
    def test_empty_ops_empty_links(self):
        links = build_operation_char_links([], [_char()])
        assert links == []

    def test_empty_chars_empty_links(self):
        ops = [{"op_id": "op1", "operation_type": "DRILLING"}]
        links = build_operation_char_links(ops, [])
        assert links == []

    def test_drilling_creates_role(self):
        ops = [{"op_id": "op1", "operation_type": "DRILLING", "feature_id": "f1"}]
        chars = [_char("c1")]
        links = build_operation_char_links(ops, chars)
        drilling_links = [l for l in links if l.operation_type == "DRILLING"]
        assert all(l.role == OperationCharacteristicRole.CREATES for l in drilling_links)

    def test_reaming_controls_role(self):
        ops = [{"op_id": "op2", "operation_type": "REAMING", "feature_id": "f1"}]
        chars = [_char("c1")]
        links = build_operation_char_links(ops, chars)
        reaming_links = [l for l in links if l.operation_type == "REAMING"]
        if reaming_links:
            assert all(l.role == OperationCharacteristicRole.CONTROLS for l in reaming_links)

    def test_inspection_verifies_role(self):
        ops = [{"op_id": "op3", "operation_type": "INSPECTION", "feature_id": "f1"}]
        chars = [_char("c1")]
        links = build_operation_char_links(ops, chars)
        insp = [l for l in links if l.operation_type == "INSPECTION"]
        if insp:
            assert all(l.role == OperationCharacteristicRole.VERIFIES for l in insp)


class TestBuildInspectionCharLinks:
    def test_empty_returns_empty(self):
        result = build_inspection_char_links([], [])
        assert result == []

    def test_link_has_suitability(self):
        chars = [_char("c1")]
        insp_ops = [{"op_id": "iop1", "operation_type": "INSPECTION"}]
        links = build_inspection_char_links(insp_ops, chars)
        for link in links:
            assert isinstance(link.suitability, InspectionMethodSuitability)
