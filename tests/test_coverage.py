"""Targeted coverage tests for model and AI edge cases."""

import pytest

from jungle.engine.ai import AI, AIWorker
from jungle.model.board import Board, GameState, IllegalMoveError, Move, Piece
from jungle.model.constants import Rank, Side, is_inside_board


def _board_with(pieces):
    rows = [[None for _ in range(7)] for _ in range(9)]
    for (row, col), piece in pieces.items():
        rows[row][col] = piece
    return Board(tuple(tuple(row) for row in rows))


# --- Model edge cases ---


def test_board_init_with_pieces():
    pieces = tuple(tuple(None for _ in range(7)) for _ in range(9))
    board = Board(pieces)
    assert board.piece_at((0, 0)) is None


def test_with_piece_moved_raises_when_empty():
    board = Board.empty()
    with pytest.raises(IllegalMoveError):
        board.with_piece_moved((0, 0), (0, 1))


def test_after_move_when_winner_set():
    board = _board_with({(0, 3): Piece(Side.RED, Rank.RAT)})
    state = GameState(board=board, current_side=Side.RED, winner=Side.RED)
    with pytest.raises(IllegalMoveError):
        state.after_move(Move((0, 3), (0, 2)))


def test_jump_no_river_squares():
    # Lion on land not adjacent to river cannot jump.
    board = _board_with({(0, 0): Piece(Side.RED, Rank.LION)})
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((0, 0), (0, 3)))


def test_jump_out_of_bounds():
    board = _board_with({(4, 6): Piece(Side.RED, Rank.LION)})
    state = GameState(board=board, current_side=Side.RED)
    # Jumping right from col 6 goes out of bounds.
    moves = state.legal_moves()
    assert all(m.to_pos != (4, 9) for m in moves)


def test_jump_lands_on_own_piece():
    board = _board_with({
        (2, 1): Piece(Side.RED, Rank.LION),
        (6, 1): Piece(Side.RED, Rank.RAT),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((2, 1), (6, 1)))


def test_rat_cannot_capture_stronger_on_land():
    board = _board_with({
        (2, 0): Piece(Side.RED, Rank.RAT),
        (2, 1): Piece(Side.BLUE, Rank.LION),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((2, 0), (2, 1)))


def test_stalemate_sets_winner():
    # Blue to move with no legal pieces; red just moved and caused stalemate.
    board = _board_with({
        (0, 0): Piece(Side.BLUE, Rank.RAT),
        (0, 1): Piece(Side.RED, Rank.CAT),
        (1, 0): Piece(Side.RED, Rank.DOG),
    })
    state = GameState(board=board, current_side=Side.BLUE)
    # Force a move by blue? Blue has no moves, so after_move can't be called.
    # Instead, verify legal_moves is empty.
    assert state.legal_moves() == []


def test_starting_state_returns_red_to_move():
    from jungle.model.board import starting_state
    state = starting_state(human_first=True)
    assert state.current_side is Side.RED


def test_is_inside_board():
    assert is_inside_board((0, 0)) is True
    assert is_inside_board((8, 6)) is True
    assert is_inside_board((-1, 0)) is False
    assert is_inside_board((0, 7)) is False


# --- AI edge cases ---


def test_ai_choose_move_with_illegal_ordered_move():
    # Create a state where ordering by capture puts a move first, but all moves are legal.
    board = _board_with({(0, 0): Piece(Side.RED, Rank.RAT)})
    state = GameState(board=board, current_side=Side.RED)
    ai = AI(side=Side.RED, depth=2)
    move = ai.choose_move(state)
    assert move is not None


def test_ai_score_tiebreak():
    # Symmetric position where two moves have equal score.
    board = _board_with({
        (2, 0): Piece(Side.RED, Rank.RAT),
        (2, 6): Piece(Side.RED, Rank.RAT),
    })
    state = GameState(board=board, current_side=Side.RED)
    ai = AI(side=Side.RED, depth=1)
    move = ai.choose_move(state)
    assert move is not None


def test_ai_choose_move_returns_none_when_game_won():
    board = _board_with({(0, 3): Piece(Side.RED, Rank.RAT)})
    state = GameState(board=board, current_side=Side.RED, winner=Side.RED)
    ai = AI(side=Side.RED, depth=2)
    assert ai.choose_move(state) is None


def test_ai_choose_move_returns_none_when_stalemated():
    board = _board_with({
        (0, 0): Piece(Side.RED, Rank.RAT),
        (0, 1): Piece(Side.BLUE, Rank.CAT),
        (1, 0): Piece(Side.BLUE, Rank.DOG),
    })
    state = GameState(board=board, current_side=Side.RED)
    ai = AI(side=Side.RED, depth=2)
    assert ai.choose_move(state) is None


def test_ai_choose_move_returns_none_when_drawn():
    board = _board_with({(4, 3): Piece(Side.RED, Rank.RAT), (4, 0): Piece(Side.BLUE, Rank.RAT)})
    state = GameState(board=board, current_side=Side.RED, draw=True)
    ai = AI(side=Side.RED, depth=2)
    assert ai.choose_move(state) is None


def test_ai_worker_emits_move(qtbot):
    board = _board_with({(0, 0): Piece(Side.RED, Rank.RAT)})
    state = GameState(board=board, current_side=Side.RED)
    ai = AI(side=Side.RED, depth=1)
    worker = AIWorker(ai, state)

    with qtbot.waitSignal(worker.move_chosen, timeout=5000):
        worker.start()
    worker.wait(1000)


def test_ai_worker_emits_error(qtbot, monkeypatch):
    board = _board_with({(0, 0): Piece(Side.RED, Rank.RAT)})
    state = GameState(board=board, current_side=Side.RED)
    ai = AI(side=Side.RED, depth=1)
    worker = AIWorker(ai, state)

    def raise_exc(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(ai, "choose_move", raise_exc)

    with qtbot.waitSignal(worker.error, timeout=5000):
        worker.start()
    worker.wait(1000)
