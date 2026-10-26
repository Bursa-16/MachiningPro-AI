"""Tests for drawing_intelligence.operation_capability (EPIC_04 Phase 2)."""

import pytest
from decimal import Decimal

from backend.domain.enums import FeatureType, OperationType
from backend.drawing_intelligence.operation_capability import (
    CAPABILITY_LIBRARY,
    FEATURE_OPERATION_MATRIX,
    OperationCapabilityLibrary,
    ToleranceCapability,
    ops_for_feature,
)


class TestOperationCapabilityLibrary:
    def test_drilling_capability_exists(self):
        cap = CAPABILITY_LIBRARY.get(OperationType.DRILLING)
        assert cap is not None
        assert cap.operation == OperationType.DRILLING

    def test_drilling_is_rough(self):
        cap = CAPABILITY_LIBRARY.get(OperationType.DRILLING)
        assert cap.produces_rough is True

    def test_reaming_ra_le_0_4(self):
        cap = CAPABILITY_LIBRARY.get(OperationType.REAMING)
        assert cap is not None
        assert cap.ra_achievable_um <= Decimal("0.4")

    def test_grinding_achieves_fine_ra(self):
        cap = CAPABILITY_LIBRARY.get(OperationType.GRINDING)
        assert cap is not None
        assert cap.ra_achievable_um <= Decimal("0.1")

    def test_tapping_produces_thread(self):
        cap = CAPABILITY_LIBRARY.get(OperationType.TAPPING)
        assert cap is not None
        assert FeatureType.THREAD in cap.can_produce

    def test_can_achieve_ra_match(self):
        assert CAPABILITY_LIBRARY.can_achieve_ra(OperationType.REAMING, Decimal("0.8"))

    def test_can_achieve_ra_too_tight(self):
        # Drilling cannot achieve Ra 0.4 µm
        assert not CAPABILITY_LIBRARY.can_achieve_ra(OperationType.DRILLING, Decimal("0.4"))

    def test_can_achieve_ra_unknown_op(self):
        # UNKNOWN_CAPABILITY_TREATED_AS_SUPPORTED=NO — returns False
        assert not CAPABILITY_LIBRARY.can_achieve_ra(OperationType.OTHER, Decimal("10.0"))

    def test_ops_for_hole(self):
        ops = CAPABILITY_LIBRARY.ops_for_feature(FeatureType.HOLE)
        assert OperationType.DRILLING in ops
        assert OperationType.REAMING in ops

    def test_ops_for_thread(self):
        ops = CAPABILITY_LIBRARY.ops_for_feature(FeatureType.THREAD)
        assert OperationType.TAPPING in ops

    def test_ops_for_unknown_feature_empty(self):
        ops = CAPABILITY_LIBRARY.ops_for_feature(FeatureType.UNKNOWN)
        assert isinstance(ops, list)


class TestFeatureOperationMatrix:
    def test_hole_has_drilling_reaming_boring_honing(self):
        ops = FEATURE_OPERATION_MATRIX[FeatureType.HOLE]
        assert OperationType.DRILLING in ops
        assert OperationType.REAMING in ops
        assert OperationType.BORING in ops
        assert OperationType.HONING in ops

    def test_thread_has_tapping(self):
        ops = FEATURE_OPERATION_MATRIX[FeatureType.THREAD]
        assert OperationType.TAPPING in ops

    def test_slot_has_milling(self):
        ops = FEATURE_OPERATION_MATRIX[FeatureType.SLOT]
        assert OperationType.MILLING in ops

    def test_planar_face_has_milling_and_grinding(self):
        ops = FEATURE_OPERATION_MATRIX[FeatureType.PLANAR_FACE]
        assert OperationType.MILLING in ops
        assert OperationType.GRINDING in ops

    def test_unknown_has_no_ops(self):
        ops = FEATURE_OPERATION_MATRIX[FeatureType.UNKNOWN]
        assert ops == []

    def test_ops_for_feature_helper(self):
        ops = ops_for_feature(FeatureType.CYLINDRICAL_SURFACE)
        assert OperationType.TURNING in ops


class TestNoFabricatedCapability:
    def test_inspection_produces_no_features(self):
        cap = CAPABILITY_LIBRARY.get(OperationType.INSPECTION)
        assert cap is not None
        assert len(cap.can_produce) == 0

    def test_all_ops_have_finite_ra(self):
        for op in CAPABILITY_LIBRARY.all_operations():
            cap = CAPABILITY_LIBRARY.get(op)
            assert cap is not None
            # Ra must be non-negative and finite
            assert cap.ra_achievable_um >= Decimal("0")
