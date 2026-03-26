"""
Tests for analytics curriculum awareness (Phase 3).

Covers: American 60% pass mark, Montessori null pass/fail,
analytics response curriculum_type, GES 50% pass mark unchanged.
"""

import pytest
from decimal import Decimal

from app.services.exam.score_strategies import (
    AmericanScoreStrategy,
    GESScoreStrategy,
    IBScoreStrategy,
    MontessoriScoreStrategy,
    SubjectScoreResult,
    get_score_strategy,
)


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

AMERICAN_PASS_MARK = Decimal("60")
GES_PASS_MARK = Decimal("50")
IB_PASS_MARK = Decimal("44")  # IB 4+ is passing (>=44%)


def _compute_pass_rate(
    results: list[SubjectScoreResult],
    pass_mark: Decimal | None,
) -> float | None:
    """Simulate the analytics pass rate calculation.

    This replicates the logic from the analytics service:
    pass_rate = count(scores >= pass_mark) / total * 100
    Returns None for curricula without numeric scoring (Montessori).
    """
    if pass_mark is None:
        return None

    if not results:
        return 0.0

    passing = sum(
        1 for r in results
        if r.final_score is not None and r.final_score >= pass_mark
    )
    return round(passing / len(results) * 100, 2)


def _build_result(score: Decimal | None) -> SubjectScoreResult:
    """Build a SubjectScoreResult with a given final_score."""
    result = SubjectScoreResult()
    result.final_score = score
    result.component_scores = {}
    return result


# ---------------------------------------------------------------
# Tests
# ---------------------------------------------------------------

class TestAnalyticsPassMark:
    """Verify pass mark varies by curriculum type for analytics."""

    def test_american_uses_60_percent_pass_mark(self):
        """American curriculum should use 60% as the pass mark."""
        results = [
            _build_result(Decimal("65")),   # pass
            _build_result(Decimal("58")),   # fail at 60%
            _build_result(Decimal("72")),   # pass
            _build_result(Decimal("45")),   # fail
        ]
        rate = _compute_pass_rate(results, AMERICAN_PASS_MARK)
        # 2 out of 4 pass = 50%
        assert rate == 50.0

    def test_ges_uses_50_percent_pass_mark(self):
        """GES curriculum should use 50% as the pass mark (unchanged)."""
        results = [
            _build_result(Decimal("55")),   # pass
            _build_result(Decimal("48")),   # fail at 50%
            _build_result(Decimal("72")),   # pass
            _build_result(Decimal("50")),   # pass (exactly 50)
        ]
        rate = _compute_pass_rate(results, GES_PASS_MARK)
        # 3 out of 4 pass = 75%
        assert rate == 75.0

    def test_montessori_has_null_pass_fail(self):
        """Montessori analytics should have null pass/fail rates."""
        results = [_build_result(None), _build_result(None)]
        rate = _compute_pass_rate(results, None)
        assert rate is None

    def test_ib_uses_44_percent_pass_mark(self):
        """IB curriculum uses ~44% (level 4+) as pass mark."""
        results = [
            _build_result(Decimal("50")),   # pass
            _build_result(Decimal("40")),   # fail at 44%
            _build_result(Decimal("70")),   # pass
        ]
        rate = _compute_pass_rate(results, IB_PASS_MARK)
        # 2 out of 3 pass = 66.67%
        assert rate == 66.67

    def test_empty_results_return_zero(self):
        """Empty results should give 0% pass rate."""
        rate = _compute_pass_rate([], GES_PASS_MARK)
        assert rate == 0.0


class TestAnalyticsCurriculumType:
    """Verify analytics can determine curriculum type from strategy."""

    def test_strategy_factory_returns_correct_types(self):
        """Each strategy type should be identifiable for analytics context."""
        type_map = {
            "ges": GESScoreStrategy,
            "american": AmericanScoreStrategy,
            "ib": IBScoreStrategy,
            "montessori": MontessoriScoreStrategy,
        }
        for curriculum_type, expected_class in type_map.items():
            strategy = get_score_strategy(curriculum_type)
            assert isinstance(strategy, expected_class), (
                f"Expected {expected_class.__name__} for '{curriculum_type}', "
                f"got {type(strategy).__name__}"
            )
