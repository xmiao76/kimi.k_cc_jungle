"""Slow strength/performance tests (run with: pytest -m slow)."""

import time

import pytest

from jungle.engine.ai import AI
from jungle.engine.core import FastPosition
from jungle.engine.legacy_ai import LegacyAI
from jungle.engine.search import SearchConfig, Searcher
from jungle.model.board import Board, GameState
from jungle.model.constants import Side
from scripts.gauntlet import make_v2, run_gauntlet

pytestmark = pytest.mark.slow


def test_candidate_dominates_legacy():
    candidate = lambda side: AI(side, depth=3, time_limit_s=0.2)  # noqa: E731
    baseline = lambda side: LegacyAI(side, depth=2)  # noqa: E731
    score = run_gauntlet(10, candidate, baseline, seed=777, verbose=False)
    assert score >= 0.7, f"candidate scored only {score:.0%} vs legacy"


def test_v3_beats_v2():
    # Fixed depth = deterministic, contention-proof, and the proven
    # configuration (69-75% in measurement runs).
    candidate = lambda side: AI(  # noqa: E731
        side,
        config=SearchConfig(max_depth=5, soft_limit_s=600.0, hard_limit_s=1200.0),
    )
    baseline = lambda side: make_v2(side, depth=5, time_s=600.0)  # noqa: E731
    score = run_gauntlet(8, candidate, baseline, seed=999, verbose=False)
    assert score >= 0.6, f"v3 scored only {score:.0%} vs v2"


def test_depth_five_from_start_under_ten_seconds():
    pos = FastPosition.from_game_state(
        GameState(board=Board.starting(), current_side=Side.RED)
    )
    searcher = Searcher(SearchConfig(max_depth=5, soft_limit_s=60.0, hard_limit_s=120.0))
    start = time.perf_counter()
    result = searcher.search(pos)
    elapsed = time.perf_counter() - start
    assert result.depth == 5
    assert elapsed < 10.0, f"depth 5 took {elapsed:.1f}s"
