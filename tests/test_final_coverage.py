"""Final coverage tests for GUI and engine."""

import pytest
from PyQt6.QtCore import Qt

from jungle.gui.board_view import BoardView
from jungle.gui.main_window import MainWindow
from jungle.model.board import Board, GameState, Move
from jungle.model.constants import Side


def test_board_view_last_move(qtbot):
    view = BoardView()
    qtbot.addWidget(view)
    state = GameState(board=Board.starting(), current_side=Side.RED)
    view.set_state(state)
    view.set_last_move(Move((8, 0), (7, 0)))
    assert view._last_move == Move((8, 0), (7, 0))


def test_board_view_click_empty_does_nothing(qtbot):
    view = BoardView()
    qtbot.addWidget(view)
    state = GameState(board=Board.starting(), current_side=Side.RED)
    view.set_state(state)
    view.resize(view.sizeHint())
    empty = view.cell_rect((4, 3))
    qtbot.mouseClick(view, Qt.MouseButton.LeftButton, pos=empty.center().toPoint())
    qtbot.wait(30)
    assert view._selected_pos is None


def test_board_view_click_enemy_does_nothing(qtbot):
    view = BoardView()
    qtbot.addWidget(view)
    state = GameState(board=Board.starting(), current_side=Side.RED)
    view.set_state(state)
    view.resize(view.sizeHint())
    enemy = view.cell_rect((0, 0))  # Blue dog
    qtbot.mouseClick(view, Qt.MouseButton.LeftButton, pos=enemy.center().toPoint())
    qtbot.wait(30)
    assert view._selected_pos is None


def test_main_window_apply_illegal_move(qtbot):
    window = MainWindow(ai_first=False, ai_depth=2)
    qtbot.addWidget(window)
    illegal = Move((8, 0), (8, 0))
    window._apply_move(illegal)
    # State unchanged; status may show error.
    assert window._board_view.state().board.piece_at((8, 0)) is not None


def test_main_window_ai_error(qtbot):
    window = MainWindow(ai_first=False, ai_depth=2)
    qtbot.addWidget(window)
    window._on_ai_error("test error")
    assert not window._ai_thinking
    assert "test error" in window._status_bar.currentMessage()
