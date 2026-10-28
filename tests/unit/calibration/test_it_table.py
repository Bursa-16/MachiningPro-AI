"""Tests for IT grade tolerance table — EPIC_04F.

IT_TABLE_TESTS=YES
"""

import pytest

from backend.calibration.it_table import (
    IT_GRADE_MAX,
    IT_GRADE_MIN,
    IT_SIZE_MAX_MM,
    IT_SIZE_MIN_MM,
    it_tolerance_range_um,
    it_tolerance_um,
)


class TestItTableBounds:
    def test_grade_bounds(self):
        assert IT_GRADE_MIN == 1
        assert IT_GRADE_MAX == 18

    def test_size_bounds(self):
        assert IT_SIZE_MIN_MM == 1.0
        assert IT_SIZE_MAX_MM == 500.0


class TestItToleranceUm:
    def test_it7_30mm_is_positive(self):
        val = it_tolerance_um(7, 30)
        assert val is not None
        assert val > 0

    def test_it6_is_less_than_it8_same_size(self):
        v6 = it_tolerance_um(6, 50)
        v8 = it_tolerance_um(8, 50)
        assert v6 is not None and v8 is not None
        assert v6 < v8

    def test_larger_size_gives_larger_tolerance_same_grade(self):
        v_small = it_tolerance_um(7, 10)
        v_large = it_tolerance_um(7, 100)
        assert v_small is not None and v_large is not None
        assert v_small < v_large

    def test_invalid_grade_returns_none(self):
        assert it_tolerance_um(0, 50) is None
        assert it_tolerance_um(19, 50) is None

    def test_invalid_size_returns_none(self):
        assert it_tolerance_um(7, 0) is None
        assert it_tolerance_um(7, 501) is None
        assert it_tolerance_um(7, -5) is None

    def test_it7_nominal_25mm_approx(self):
        # IT7 for ~25mm should be around 21 µm (handbook reference)
        val = it_tolerance_um(7, 25)
        assert val is not None
        assert 15 < val < 30

    def test_it6_nominal_50mm_approx(self):
        # IT6 for 50mm should be around 16 µm
        val = it_tolerance_um(6, 50)
        assert val is not None
        assert 10 < val < 25

    def test_it4_is_tighter_than_it10(self):
        v4 = it_tolerance_um(4, 30)
        v10 = it_tolerance_um(10, 30)
        assert v4 is not None and v10 is not None
        assert v4 < v10

    def test_size_boundary_1mm(self):
        val = it_tolerance_um(7, 1.0)
        assert val is not None and val > 0

    def test_size_boundary_500mm(self):
        val = it_tolerance_um(7, 500)
        assert val is not None and val > 0

    def test_it1_is_smallest_grade(self):
        v1 = it_tolerance_um(1, 30)
        v18 = it_tolerance_um(18, 30)
        assert v1 is not None and v18 is not None
        assert v1 < v18

    def test_multipliers_ratio_it7_it6(self):
        # IT7/IT6 = 16/10 = 1.6
        v7 = it_tolerance_um(7, 30)
        v6 = it_tolerance_um(6, 30)
        assert v7 is not None and v6 is not None
        ratio = v7 / v6
        assert abs(ratio - 1.6) < 0.01

    def test_multipliers_ratio_it8_it7(self):
        # IT8/IT7 = 25/16 ≈ 1.5625
        v8 = it_tolerance_um(8, 50)
        v7 = it_tolerance_um(7, 50)
        assert v8 is not None and v7 is not None
        ratio = v8 / v7
        assert abs(ratio - (25 / 16)) < 0.02


class TestItToleranceRange:
    def test_range_returns_two_values(self):
        lo, hi = it_tolerance_range_um(6, 9, 30)
        assert lo is not None and hi is not None
        assert lo < hi

    def test_range_swaps_if_min_gt_max(self):
        lo1, hi1 = it_tolerance_range_um(6, 9, 30)
        lo2, hi2 = it_tolerance_range_um(9, 6, 30)
        assert abs(lo1 - lo2) < 1e-9
        assert abs(hi1 - hi2) < 1e-9

    def test_range_single_grade(self):
        lo, hi = it_tolerance_range_um(7, 7, 50)
        assert lo is not None and hi is not None
        assert abs(lo - hi) < 1e-9

    def test_range_invalid_grade_returns_none(self):
        result = it_tolerance_range_um(0, 9, 30)
        assert result is None

    def test_range_invalid_size_returns_none(self):
        result = it_tolerance_range_um(6, 9, 0)
        assert result is None

    def test_range_it9_12_drilling(self):
        lo, hi = it_tolerance_range_um(9, 12, 25)
        assert lo is not None and hi is not None
        assert lo > 0 and hi > lo
