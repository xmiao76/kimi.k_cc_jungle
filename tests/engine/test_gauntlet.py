"""Slow strength guard: the real engine must beat the legacy baseline."""

import pytest

from scripts.gauntlet import run_gauntlet

pytestmark = pytest.mark.slow


def test_engine_beats_legacy_baseline():
    score, lines = run_gauntlet(games=4, depth=3, time_limit=0.3, legacy_depth=2, seed=7)
    print("\n" + "\n".join(lines))
    assert score >= 0.6, f"engine scored only {score:.0%} vs legacy baseline"
