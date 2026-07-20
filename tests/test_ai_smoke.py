"""Smoke tests for the public AI interface and difficulty presets."""

import pytest

from jungle.engine.ai import AI, STRENGTH_NAMES, NoLegalMoveError
from jungle.model.board import GameState, Piece
from jungle.model.constants import Rank, Side


@pytest.mark.parametrize("strength", STRENGTH_NAMES)
def test_ai_returns_a_legal_move_at_every_strength(strength, initial_state):
    ai = AI(strength=strength)
    move, result = ai.choose_move(initial_state)
    assert move in initial_state.legal_moves()
    assert result.depth >= 1
    assert result.nodes > 0


def test_ai_rejects_unknown_strength():
    with pytest.raises(ValueError):
        AI(strength="grandmaster")


def test_ai_raises_on_terminal_position():
    state = GameState.from_pieces({(2, 2): Piece(Side.BLUE, Rank.CAT)}, current_side=Side.RED)
    assert state.is_game_over
    with pytest.raises(NoLegalMoveError):
        AI(strength="easy").choose_move(state)


def test_depth_and_time_overrides_apply():
    ai = AI(strength="easy", depth=5, time_limit=2.0)
    assert ai.config.max_depth == 5
    assert ai.config.soft_limit_s == 2.0
    assert ai.config.hard_limit_s == 5.0


def test_ai_plays_convincingly_for_both_sides(initial_state):
    ai = AI(strength="medium", depth=2, time_limit=1.0)
    red_move, _ = ai.choose_move(initial_state)
    blue_state = initial_state.apply_move(red_move)
    blue_move, _ = ai.choose_move(blue_state)
    assert blue_move in blue_state.legal_moves()
