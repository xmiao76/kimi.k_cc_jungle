"""Differential testing: the fast core must mirror the immutable model.

Seeded random playouts compare, on every single ply:
* the exact set of legal moves each generator produces,
* the Zobrist position key (incremental vs recomputed),
* the terminal status (winner / draw / ongoing).

Make/undo round-trips and ``from_game_state`` re-derivation are checked too.
"""

import random

import pytest

from jungle.engine.core import FastPosition, from_model_move
from jungle.model import zobrist
from jungle.model.board import GameState

GAMES = 24
MAX_PLIES_PER_GAME = 120
SEED_BASE = 20240


def _core_terminal(pos: FastPosition) -> tuple[bool, int | None]:
    """(is_terminal, winner_side_index_or_None) from the fast core."""
    winner = pos.winner()
    if winner is not None:
        return True, winner
    if pos.is_repetition_draw() or pos.is_ply_cap_draw():
        return True, None
    if not pos.legal_moves():
        return True, pos.side ^ 1  # no legal moves: side to move loses
    return False, None


def _model_terminal(state: GameState) -> tuple[bool, int | None]:
    if not state.is_game_over:
        return False, None
    winner = state.winner
    return True, None if winner is None else zobrist.side_index(winner)


def _assert_in_sync(state: GameState, pos: FastPosition) -> None:
    model_moves = sorted(from_model_move(m) for m in state.legal_moves())
    core_moves = sorted(pos.legal_moves())
    assert model_moves == core_moves
    assert pos.key == state.position_key
    assert pos.move_count == state.move_count
    assert _core_terminal(pos) == _model_terminal(state)


def _check_make_undo_round_trip(pos: FastPosition) -> None:
    cells_before = list(pos.cells)
    key_before = pos.key
    counts_before = dict(pos.key_counts)
    pieces_before = list(pos.piece_counts)
    for move in pos.legal_moves():
        pos.make(move)
        pos.undo()
        assert pos.cells == cells_before
        assert pos.key == key_before
        assert pos.key_counts == counts_before
        assert pos.piece_counts == pieces_before


def _check_rederivation(state: GameState, pos: FastPosition) -> None:
    rebuilt = FastPosition.from_game_state(state)
    assert rebuilt.cells == pos.cells
    assert rebuilt.key == pos.key
    assert rebuilt.key_history == pos.key_history
    assert rebuilt.key_counts == pos.key_counts
    assert rebuilt.piece_counts == pos.piece_counts


@pytest.mark.parametrize("game_no", range(GAMES))
def test_seeded_playouts_stay_in_sync(game_no):
    rng = random.Random(SEED_BASE + game_no)
    state = GameState.starting()
    pos = FastPosition.from_game_state(state)
    for ply in range(MAX_PLIES_PER_GAME):
        _assert_in_sync(state, pos)
        if state.is_game_over:
            break
        if ply % 5 == 0:
            _check_make_undo_round_trip(pos)
        if ply % 10 == 0:
            _check_rederivation(state, pos)
        move = rng.choice(state.legal_moves())
        state = state.apply_move(move)
        pos.make(from_model_move(move))
    # Final position must agree on the outcome.
    _assert_in_sync(state, pos)
