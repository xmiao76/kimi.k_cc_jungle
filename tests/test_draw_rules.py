"""Tests for draw rules (threefold repetition, ply cap) and move helpers."""

import random

from jungle.model.board import MAX_PLIES, Board, GameState, Move, Piece
from jungle.model.constants import Rank, Side


def _board_with(pieces):
    rows = [[None for _ in range(7)] for _ in range(9)]
    for (row, col), piece in pieces.items():
        rows[row][col] = piece
    return Board(tuple(tuple(row) for row in rows))


def _shuttle_state():
    # Two rats shuttling on land; a 4-ply cycle returns to the start position.
    board = _board_with({
        (4, 3): Piece(Side.RED, Rank.RAT),
        (4, 0): Piece(Side.BLUE, Rank.RAT),
    })
    return GameState(board=board, current_side=Side.RED)


_CYCLE = [
    Move((4, 3), (3, 3)),
    Move((4, 0), (5, 0)),
    Move((3, 3), (4, 3)),
    Move((5, 0), (4, 0)),
]


def test_threefold_repetition_is_draw():
    state = _shuttle_state()
    # First full cycle: position occurs twice — no draw yet.
    for move in _CYCLE:
        state = state.after_move(move)
    assert not state.draw
    assert state.winner is None
    # Second cycle: position occurs a third time — draw.
    for move in _CYCLE:
        state = state.after_move(move)
    assert state.draw
    assert state.winner is None


def test_ply_cap_is_draw():
    state = _shuttle_state()
    state = GameState(
        board=state.board,
        current_side=state.current_side,
        move_count=MAX_PLIES - 1,
    )
    state = state.after_move(Move((4, 3), (3, 3)))
    assert state.draw
    assert state.winner is None


def test_win_outranks_draw():
    board = _board_with({(1, 3): Piece(Side.RED, Rank.RAT)})
    state = GameState(board=board, current_side=Side.RED, move_count=MAX_PLIES - 1)
    new_state = state.after_move(Move((1, 3), (0, 3)))
    assert new_state.winner is Side.RED
    assert not new_state.draw


def test_has_legal_move_matches_legal_moves():
    rng = random.Random(20260716)
    checked = 0
    for _ in range(30):
        state = GameState(board=Board.starting(), current_side=Side.RED)
        for _ in range(30):
            assert state.has_legal_move() == bool(state.legal_moves())
            checked += 1
            moves = state.legal_moves()
            if not moves:
                break
            state = state.after_move(rng.choice(moves))
            if state.winner is not None or state.draw:
                break
    assert checked > 100
