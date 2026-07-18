"""Integration tests for the GUI."""

import pytest
from PyQt6.QtCore import Qt

from jungle.gui.main_window import MainWindow
from jungle.model.constants import Side


def test_board_flip_preserves_state(qtbot):
    window = MainWindow(ai_first=False, ai_depth=2)
    qtbot.addWidget(window)

    assert window._board_view.state().current_side is Side.RED
    window._toggle_flip()
    assert window._board_view._flipped is True
    assert window._board_view.state().current_side is Side.RED


def test_click_selects_piece(qtbot):
    window = MainWindow(ai_first=False, ai_depth=2)
    qtbot.addWidget(window)

    board_view = window._board_view
    cell = board_view.cell_rect((8, 0))
    qtbot.mouseClick(board_view, Qt.MouseButton.LeftButton, pos=cell.center().toPoint())
    qtbot.wait(50)

    assert board_view._selected_pos == (8, 0)
    assert len(board_view._legal_moves) > 0
