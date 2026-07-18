"""Tests for GUI helper functions and dialogs."""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QPushButton,
)

from jungle.gui.assets import draw_piece
from jungle.gui.board_view import BoardView
from jungle.gui.dialogs import GameOverDialog, NewGameDialog
from jungle.model.board import Board, GameState
from jungle.model.constants import Rank, Side


def test_draw_piece_does_not_crash(qtbot):
    pixmap = QPixmap(100, 100)
    pixmap.fill(Qt.GlobalColor.white)
    painter = QPainter(pixmap)
    draw_piece(painter, pixmap.rect().toRectF(), Side.RED, Rank.LION, selected=True)
    painter.end()
    assert not pixmap.isNull()


def test_new_game_dialog_human_first(qtbot):
    dialog = NewGameDialog()
    qtbot.addWidget(dialog)
    assert dialog.human_first() is True
    dialog._ai_first.setChecked(True)
    assert dialog.human_first() is False


def test_new_game_dialog_accept(qtbot):
    from PyQt6.QtWidgets import QDialog
    dialog = NewGameDialog()
    qtbot.addWidget(dialog)
    ok = dialog._button_box.button(QDialogButtonBox.StandardButton.Ok)
    qtbot.mouseClick(ok, Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_game_over_dialog_wants_new_game(qtbot):
    dialog = GameOverDialog("Human")
    qtbot.addWidget(dialog)
    for child in dialog.findChildren(QPushButton):
        if child.text() == "New Game":
            qtbot.mouseClick(child, Qt.MouseButton.LeftButton)
            break
    assert dialog.wants_new_game() is True


def test_board_view_state_setter(qtbot):
    view = BoardView()
    qtbot.addWidget(view)
    state = GameState(board=Board.starting(), current_side=Side.RED)
    view.set_state(state)
    assert view.state() is state
    assert view._selected_pos is None


def test_board_view_flip(qtbot):
    view = BoardView()
    qtbot.addWidget(view)
    state = GameState(board=Board.starting(), current_side=Side.RED)
    view.set_state(state)
    view.set_flipped(True)
    assert view._flipped is True
    rect = view.cell_rect((8, 0))
    # When flipped, bottom-left internal (8,0) displays near top-right.
    assert rect.x() >= view.width() / 2 - 10


def test_board_view_pos_from_point(qtbot):
    view = BoardView()
    qtbot.addWidget(view)
    state = GameState(board=Board.starting(), current_side=Side.RED)
    view.set_state(state)
    view.resize(view.sizeHint())
    rect = view.cell_rect((8, 0))
    pos = view.pos_from_point(rect.center())
    assert pos == (8, 0)
