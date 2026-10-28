"""Tests for batch model — EPIC_04F."""

import pytest

from backend.calibration.cycle_components import compute_batch_model
from backend.calibration.models import CycleTimeCompleteness


class TestComputeBatchModel:
    def test_fully_known_computes_per_part(self):
        b = compute_batch_model(10, 1800.0, 60.0, 65.0)
        assert b.completeness == CycleTimeCompleteness.FULLY_CALCULATED
        assert b.per_part_setup_sec == pytest.approx(180.0)
        assert b.per_part_total_sec_min == pytest.approx(60.0 + 180.0)
        assert b.per_part_total_sec_max == pytest.approx(65.0 + 180.0)

    def test_no_setup_partial(self):
        b = compute_batch_model(10, None, 60.0, 60.0)
        assert b.completeness == CycleTimeCompleteness.PARTIALLY_CALCULATED
        assert b.per_part_setup_sec is None

    def test_no_cutting_partial(self):
        b = compute_batch_model(10, 1800.0, None, None)
        assert b.completeness == CycleTimeCompleteness.PARTIALLY_CALCULATED
        assert b.per_part_total_sec_min is None

    def test_nothing_known_insufficient_data(self):
        b = compute_batch_model(10, None, None, None)
        assert b.completeness == CycleTimeCompleteness.INSUFFICIENT_DATA

    def test_zero_batch_insufficient_data(self):
        b = compute_batch_model(0, 1800.0, 60.0, 60.0)
        assert b.completeness == CycleTimeCompleteness.INSUFFICIENT_DATA

    def test_batch_1_amortizes_fully(self):
        b = compute_batch_model(1, 3600.0, 120.0, 120.0)
        assert b.per_part_setup_sec == pytest.approx(3600.0)
        assert b.per_part_total_sec_min == pytest.approx(3720.0)

    def test_batch_100_amortizes_setup_small(self):
        b = compute_batch_model(100, 3600.0, 60.0, 60.0)
        assert b.per_part_setup_sec == pytest.approx(36.0)

    def test_min_max_symmetry_when_equal(self):
        b = compute_batch_model(10, 1800.0, 60.0, 60.0)
        assert b.per_part_total_sec_min == b.per_part_total_sec_max

    def test_min_lt_max_when_different(self):
        b = compute_batch_model(5, 600.0, 50.0, 60.0)
        assert b.per_part_total_sec_min < b.per_part_total_sec_max

    def test_batch_qty_preserved(self):
        b = compute_batch_model(25, None, 45.0, 50.0)
        assert b.batch_quantity == 25

    def test_other_per_part_added(self):
        b = compute_batch_model(10, 600.0, 60.0, 60.0, other_per_part_sec=30.0)
        # per_part_setup = 60, cutting = 60, other = 30 → 150
        assert b.per_part_total_sec_min == pytest.approx(60.0 + 60.0 + 30.0)
