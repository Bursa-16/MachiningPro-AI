"""Tests for hole finishing engineering rules (Stage 3F)."""

from __future__ import annotations

from decimal import Decimal

from backend.domain.enums import ResultStatus
from backend.domain.units import Quantity, Unit
from backend.machining.hole_finishing_rules import (
    AnnularVolumeRule,
    DiametralRadialConsistencyRule,
    DiametralStockRule,
    EffectiveTravelNotLessThanLengthRule,
    FinalDiameterNotLessThanInitialRule,
    HoleFinishingMachiningTimeRule,
    HoleFinishingMRRRule,
    MRRConsistencyRule,
    RadialStockRule,
    ZeroStockRemovalRule,
    foundational_hole_finishing_rules,
)

Q = Quantity.of


class TestRuleIDUniqueness:
    def test_all_ids_unique(self):
        rules = foundational_hole_finishing_rules()
        ids = [r.rule_id for r in rules]
        assert len(ids) == len(set(ids))

    def test_no_overlap_with_3a(self):
        from backend.machining.rules import foundational_machining_rules
        assert {r.rule_id for r in foundational_machining_rules()}.isdisjoint(
            {r.rule_id for r in foundational_hole_finishing_rules()}
        )

    def test_no_overlap_with_3b(self):
        from backend.machining.turning_rules import foundational_turning_rules
        assert {r.rule_id for r in foundational_turning_rules()}.isdisjoint(
            {r.rule_id for r in foundational_hole_finishing_rules()}
        )

    def test_no_overlap_with_3c(self):
        from backend.machining.milling_rules import foundational_milling_rules
        assert {r.rule_id for r in foundational_milling_rules()}.isdisjoint(
            {r.rule_id for r in foundational_hole_finishing_rules()}
        )

    def test_no_overlap_with_3d(self):
        from backend.machining.drilling_rules import foundational_drilling_rules
        assert {r.rule_id for r in foundational_drilling_rules()}.isdisjoint(
            {r.rule_id for r in foundational_hole_finishing_rules()}
        )

    def test_no_overlap_with_3e(self):
        from backend.machining.threading_rules import foundational_threading_rules
        assert {r.rule_id for r in foundational_threading_rules()}.isdisjoint(
            {r.rule_id for r in foundational_hole_finishing_rules()}
        )


class TestDiametralStockRule:
    def test_pass(self):
        r = DiametralStockRule()
        result = r.evaluate({
            "initial_diameter": Q("9.8", Unit.MM),
            "final_diameter": Q("10", Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["diametral_stock"].value == Decimal("0.2")

    def test_missing(self):
        r = DiametralStockRule()
        assert r.evaluate({}).status is ResultStatus.INSUFFICIENT_DATA


class TestRadialStockRule:
    def test_pass(self):
        r = RadialStockRule()
        result = r.evaluate({
            "initial_diameter": Q("9.8", Unit.MM),
            "final_diameter": Q("10", Unit.MM),
        })
        assert result.outputs["radial_stock"].value == Decimal("0.1")


class TestAnnularVolumeRule:
    def test_pass(self):
        r = AnnularVolumeRule()
        result = r.evaluate({
            "initial_diameter": Q("9.8", Unit.MM),
            "final_diameter": Q("10", Unit.MM),
            "length": Q("30", Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["volume"].unit is Unit.MM3


class TestHoleFinishingMRRRule:
    def test_pass(self):
        r = HoleFinishingMRRRule()
        result = r.evaluate({
            "initial_diameter": Q("9.8", Unit.MM),
            "final_diameter": Q("10", Unit.MM),
            "feed_rate": Q("200", Unit.MM_MIN),
        })
        assert result.status is ResultStatus.PASS

    def test_missing(self):
        r = HoleFinishingMRRRule()
        assert r.evaluate({"initial_diameter": Q("9.8", Unit.MM)}).status is (
            ResultStatus.INSUFFICIENT_DATA
        )


class TestMachiningTimeRule:
    def test_pass(self):
        r = HoleFinishingMachiningTimeRule()
        result = r.evaluate({
            "spindle_speed": Q("500", Unit.RPM),
            "feed_per_rev": Q("0.4", Unit.MM_REV),
            "operation_length": Q("30", Unit.MM),
        })
        assert result.status is ResultStatus.PASS
        assert result.outputs["time"].value == Decimal("0.15")


class TestFinalDiameterNotLessThanInitialRule:
    def test_valid(self):
        r = FinalDiameterNotLessThanInitialRule()
        result = r.evaluate({
            "initial_diameter": Q("9.8", Unit.MM),
            "final_diameter": Q("10", Unit.MM),
        })
        assert result.status is ResultStatus.PASS

    def test_equal(self):
        r = FinalDiameterNotLessThanInitialRule()
        result = r.evaluate({
            "initial_diameter": Q("10", Unit.MM),
            "final_diameter": Q("10", Unit.MM),
        })
        assert result.status is ResultStatus.PASS

    def test_reversed(self):
        r = FinalDiameterNotLessThanInitialRule()
        result = r.evaluate({
            "initial_diameter": Q("10", Unit.MM),
            "final_diameter": Q("9", Unit.MM),
        })
        assert result.status is ResultStatus.FAIL


class TestDiametralRadialConsistencyRule:
    def test_consistent(self):
        r = DiametralRadialConsistencyRule()
        result = r.evaluate({
            "diametral_stock": Q("0.4", Unit.MM),
            "radial_stock": Q("0.2", Unit.MM),
        })
        assert result.status is ResultStatus.PASS

    def test_inconsistent(self):
        r = DiametralRadialConsistencyRule()
        result = r.evaluate({
            "diametral_stock": Q("0.5", Unit.MM),
            "radial_stock": Q("0.2", Unit.MM),
        })
        assert result.status is ResultStatus.FAIL


class TestEffectiveTravelRule:
    def test_travel_ge_length(self):
        r = EffectiveTravelNotLessThanLengthRule()
        result = r.evaluate({
            "operation_length": Q("30", Unit.MM),
            "effective_travel": Q("33", Unit.MM),
        })
        assert result.status is ResultStatus.PASS

    def test_travel_lt_length(self):
        r = EffectiveTravelNotLessThanLengthRule()
        result = r.evaluate({
            "operation_length": Q("30", Unit.MM),
            "effective_travel": Q("25", Unit.MM),
        })
        assert result.status is ResultStatus.FAIL


class TestZeroStockRemovalRule:
    def test_nonzero_pass(self):
        r = ZeroStockRemovalRule()
        result = r.evaluate({
            "initial_diameter": Q("9.8", Unit.MM),
            "final_diameter": Q("10", Unit.MM),
        })
        assert result.status is ResultStatus.PASS

    def test_zero_warning(self):
        r = ZeroStockRemovalRule()
        result = r.evaluate({
            "initial_diameter": Q("10", Unit.MM),
            "final_diameter": Q("10", Unit.MM),
        })
        assert result.status is ResultStatus.WARNING


class TestMRRConsistencyRule:
    def test_consistent(self):
        from backend.machining.hole_finishing import hole_finishing_mrr
        d_i, d_f = Q("9.8", Unit.MM), Q("10", Unit.MM)
        vf = Q("200", Unit.MM_MIN)
        expected_mrr = hole_finishing_mrr(d_i, d_f, vf)

        r = MRRConsistencyRule()
        result = r.evaluate({
            "initial_diameter": d_i,
            "final_diameter": d_f,
            "feed_rate": vf,
            "mrr": expected_mrr,
        })
        assert result.status is ResultStatus.PASS

    def test_inconsistent(self):
        r = MRRConsistencyRule()
        result = r.evaluate({
            "initial_diameter": Q("9.8", Unit.MM),
            "final_diameter": Q("10", Unit.MM),
            "feed_rate": Q("200", Unit.MM_MIN),
            "mrr": Q("99999", Unit.MM3_MIN),
        })
        assert result.status is ResultStatus.FAIL


class TestDeterminism:
    def test_repeat(self):
        r = DiametralStockRule()
        inputs = {
            "initial_diameter": Q("9.8", Unit.MM),
            "final_diameter": Q("10", Unit.MM),
        }
        a = r.evaluate(inputs)
        b = r.evaluate(inputs)
        assert a.outputs["diametral_stock"].value == b.outputs["diametral_stock"].value


class TestNoMutation:
    def test_inputs_unchanged(self):
        r = HoleFinishingMRRRule()
        inputs = {
            "initial_diameter": Q("9.8", Unit.MM),
            "final_diameter": Q("10", Unit.MM),
            "feed_rate": Q("200", Unit.MM_MIN),
        }
        orig = {k: v.value for k, v in inputs.items()}
        r.evaluate(inputs)
        for k, v in inputs.items():
            assert v.value == orig[k]
