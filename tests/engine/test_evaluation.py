"""Parity between the incremental PST evaluation and the frozen v1 formula,
plus exact make/undo round-tripping of the incremental eval state."""

import random
from dataclasses import replace

import pytest

from jungle.engine.core import FastPosition, from_model_move, to_model_move
from jungle.engine.evaluation import DEFAULT_WEIGHTS, build_tables, evaluate_fast
from jungle.engine.v1_frozen import v1_evaluate
from jungle.model.board import GameState

# v1's formula has no den-defense term; zero it for an exact parity check.
TABLES = build_tables(replace(DEFAULT_WEIGHTS, den_defense=0))
GAMES = 12
MAX_PLIES_PER_GAME = 80


@pytest.mark.parametrize("game_no", range(GAMES))
def test_incremental_eval_matches_v1_formula(game_no):
    rng = random.Random(31337 + game_no)
    state = GameState.starting()
    pos = FastPosition.from_game_state(state)
    pos.attach_tables(TABLES)
    for ply in range(MAX_PLIES_PER_GAME):
        assert evaluate_fast(pos, TABLES) == v1_evaluate(pos), f"ply {ply}"
        if state.is_game_over:
            break
        move = rng.choice(state.legal_moves())
        state = state.apply_move(move)
        pos.make(from_model_move(move))


def test_eval_state_round_trips_under_make_undo():
    rng = random.Random(999)
    state = GameState.starting()
    pos = FastPosition.from_game_state(state)
    pos.attach_tables(TABLES)
    for _ in range(30):
        if state.is_game_over:
            break
        scores_before = list(pos.eval_scores)
        counts_before = [list(c) for c in pos.rank_counts]
        for move in pos.legal_moves():
            pos.make(move)
            # After any make, the incremental state must equal a fresh build.
            rebuilt = FastPosition.from_game_state(state.apply_move(to_model_move(move)))
            rebuilt.attach_tables(TABLES)
            assert pos.eval_scores == rebuilt.eval_scores
            assert pos.rank_counts == rebuilt.rank_counts
            pos.undo()
        assert pos.eval_scores == scores_before
        assert pos.rank_counts == counts_before
        move = rng.choice(state.legal_moves())
        state = state.apply_move(move)
        pos.make(from_model_move(move))
