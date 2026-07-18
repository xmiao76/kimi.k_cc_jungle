"""Additional edge-case tests to push coverage above 80%."""

import pytest
from PyQt6.QtCore import Qt

from jungle.engine.ai import AI
from jungle.gui.board_view import BoardView
from jungle.model.board import Board, GameState, Move, Piece
from jungle.model.constants import Rank, Side


def _board_with(pieces):
    rows = [[None for _ in range(7)] for _ in range(9)]
    for (row, col), piece in pieces.items():
        rows[row][col] = piece
    return Board(tuple(tuple(row) for row in rows))


def test_stalemate_after_move_sets_winner():
    # Red moves a lion away, leaving blue rat boxed in by lions.
    board = _board_with({
        (0, 0): Piece(Side.BLUE, Rank.RAT),
        (0, 1): Piece(Side.RED, Rank.LION),
        (1, 0): Piece(Side.RED, Rank.LION),
        (1, 1): Piece(Side.RED, Rank.LION),
    })
    state = GameState(board=board, current_side=Side.RED)
    new_state = state.after_move(Move((1, 1), (2, 1)))
    assert new_state.winner is Side.RED


def test_ai_score_tie_with_random_choice():
    # Empty board with a single rat; all moves score equally.
    board = _board_with({(4, 3): Piece(Side.RED, Rank.RAT)})
    state = GameState(board=board, current_side=Side.RED)
    ai = AI(side=Side.RED, depth=1)
    move = ai.choose_move(state)
    assert move is not None
    assert state.is_legal_move(move)


def test_board_view_reselect_own_piece(qtbot):
    view = BoardView()
    qtbot.addWidget(view)
    state = GameState(board=Board.starting(), current_side=Side.RED)
    view.set_state(state)
    view.resize(view.sizeHint())

    first = view.cell_rect((8, 0))
    qtbot.mouseClick(view, Qt.MouseButton.LeftButton, pos=first.center().toPoint())
    qtbot.wait(30)
    assert view._selected_pos == (8, 0)

    second = view.cell_rect((8, 6))
    qtbot.mouseClick(view, Qt.MouseButton.LeftButton, pos=second.center().toPoint())
    qtbot.wait(30)
    assert view._selected_pos == (8, 6)
