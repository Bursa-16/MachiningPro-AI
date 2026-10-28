"""Tests for manufacturing characteristic extraction and domain model."""
import pytest
from backend.manufacturing_plan.characteristic import (
    CharacteristicType,
    CharacteristicCriticality,
    ManufacturingCharacteristic,
    CharacteristicReviewStatus,
    extract_characteristics_from_requirement_set,
)


def _char(
    char_type=CharacteristicType.DIMENSION,
    criticality=CharacteristicCriticality.STANDARD,
    label="test",
):
    return ManufacturingCharacteristic(
        characteristic_id="c1",
        source_requirement_id=None,
        feature_id=None,
        char_type=char_type,
        label=label,
        criticality=criticality,
    )


class TestCharacteristicType:
    def test_all_enum_values(self):
        types = [e.value for e in CharacteristicType]
        assert "DIMENSION" in types
        assert "GDT" in types
        assert "SURFACE_FINISH" in types
        assert "THREAD" in types
        assert "MATERIAL" in types

    def test_str_enum_usage(self):
        assert CharacteristicType.DIMENSION == "DIMENSION"


class TestCharacteristicCriticality:
    def test_standard_is_default(self):
        c = _char()
        assert c.criticality == CharacteristicCriticality.STANDARD

    def test_key_char_value(self):
        assert CharacteristicCriticality.KEY_CHARACTERISTIC == "KEY_CHARACTERISTIC"

    def test_all_values(self):
        vals = {e.value for e in CharacteristicCriticality}
        assert {"STANDARD", "IMPORTANT", "CRITICAL", "KEY_CHARACTERISTIC", "UNKNOWN"} <= vals


class TestManufacturingCharacteristic:
    def test_frozen_dataclass(self):
        c = _char()
        with pytest.raises((AttributeError, TypeError)):
            c.label = "mutated"  # type: ignore

    def test_nominal_and_limits(self):
        c = ManufacturingCharacteristic(
            characteristic_id="c2",
            source_requirement_id=None,
            feature_id="f1",
            char_type=CharacteristicType.DIMENSION,
            label="bore_dia",
            nominal_value=25.0,
            upper_limit=25.021,
            lower_limit=25.0,
            unit="mm",
        )
        assert c.nominal_value == 25.0
        assert c.upper_limit - c.lower_limit == pytest.approx(0.021)

    def test_review_status_default(self):
        c = _char()
        assert c.review_status == CharacteristicReviewStatus.PENDING

    def test_source_confidence(self):
        c = _char()
        assert c.source_confidence == "EXTRACTED"


class TestExtractCharacteristicsFromRequirementSet:
    def test_none_returns_empty(self):
        result = extract_characteristics_from_requirement_set(None)
        assert result == []

    def test_empty_dict_returns_empty(self):
        result = extract_characteristics_from_requirement_set({})
        assert isinstance(result, list)

    def test_dict_with_dimensional_reqs(self):
        req_set = {
            "dimensional_requirements": [
                {
                    "requirement_id": "r1",
                    "feature_id": "f1",
                    "dimension_type": "DIAMETER",
                    "nominal_value": 25.0,
                    "upper_deviation": 0.021,
                    "lower_deviation": 0.0,
                    "unit": "mm",
                }
            ]
        }
        result = extract_characteristics_from_requirement_set(req_set)
        assert len(result) >= 1
        assert result[0].char_type == CharacteristicType.DIMENSION

    def test_dict_with_surface_finish(self):
        req_set = {
            "surface_finish_requirements": [
                {
                    "requirement_id": "sf1",
                    "feature_id": "f2",
                    "ra_max": 0.8,
                    "unit": "µm",
                }
            ]
        }
        result = extract_characteristics_from_requirement_set(req_set)
        sf = [r for r in result if r.char_type == CharacteristicType.SURFACE_FINISH]
        assert len(sf) >= 1

    def test_dict_with_threads(self):
        req_set = {
            "thread_requirements": [
                {"requirement_id": "t1", "feature_id": "f3", "thread_standard": "M10x1.5"}
            ]
        }
        result = extract_characteristics_from_requirement_set(req_set)
        threads = [r for r in result if r.char_type == CharacteristicType.THREAD]
        assert len(threads) >= 1

    def test_unsupported_type_does_not_raise(self):
        result = extract_characteristics_from_requirement_set(
            {"unknown_key": [{"id": "x"}]}
        )
        assert isinstance(result, list)

    def test_object_with_getattr(self):
        class FakeReqSet:
            dimensional_requirements = [
                {
                    "requirement_id": "robj",
                    "feature_id": "fobj",
                    "dimension_type": "LENGTH",
                    "nominal_value": 100.0,
                    "upper_deviation": 0.1,
                    "lower_deviation": -0.1,
                    "unit": "mm",
                }
            ]
        result = extract_characteristics_from_requirement_set(FakeReqSet())
        dim = [r for r in result if r.char_type == CharacteristicType.DIMENSION]
        assert len(dim) >= 1
