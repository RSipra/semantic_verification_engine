"""Unit tests for scripts/corpus/sampling.py.

iqr_outliers: each test pins one behaviour of the outlier rule. The fence test uses
numbers worked out by hand (inclusive quartiles, multiplier 1.5).
"""
# pylint: disable=missing-function-docstring   # test names describe the check
import pytest

from scripts.corpus.sampling import iqr_outliers

# Ten typical chapters around 5,000 words, plus one short and one long outlier.
TYPICAL = dict(enumerate([4800, 4900, 5000, 5100, 5200, 4950, 5050, 4850, 5150, 5000], start=1))


def test_planted_outliers_both_tails_flagged():
    chapters = {**TYPICAL, 11: 1500, 12: 9000}
    assert iqr_outliers(chapters) == {11, 12}


def test_typical_book_has_no_outliers():
    assert iqr_outliers(TYPICAL) == set()


def test_all_chapters_same_length_returns_empty_set():
    # IQR = 0: no spread, so no basis for outliers (not "every different chapter")
    assert iqr_outliers({n: 5000 for n in range(1, 11)}) == set()


@pytest.mark.parametrize("chapters", [{}, {1: 100}, {1: 100, 2: 5000, 3: 9000}])
def test_fewer_than_four_chapters_returns_empty_set(chapters):
    assert iqr_outliers(chapters) == set()


def test_chapter_exactly_on_fence_is_not_flagged():
    # sorted 10, 20, 30, 40, 70 → Q1 = 20, Q3 = 40, IQR = 20, upper fence = 40 + 1.5*20 = 70
    on_fence = {1: 10, 2: 20, 3: 30, 4: 40, 5: 70}
    assert iqr_outliers(on_fence) == set()


def test_chapter_just_past_fence_is_flagged():
    # same quartiles (Q3 is still the 4th value), upper fence 70 → 71 is strictly above it
    past_fence = {1: 10, 2: 20, 3: 30, 4: 40, 5: 71}
    assert iqr_outliers(past_fence) == {5}


def test_larger_multiplier_flags_fewer_chapters():
    past_fence = {1: 10, 2: 20, 3: 30, 4: 40, 5: 71}
    assert iqr_outliers(past_fence, multiplier=3.0) == set()


def test_does_not_modify_input():
    chapters = {**TYPICAL, 11: 1500}
    before = dict(chapters)
    iqr_outliers(chapters)
    assert chapters == before
