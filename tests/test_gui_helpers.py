"""BoardView geometry and selection mechanics (offscreen)."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from jungle.gui.board_view import BoardView
from jungle.model.board import GameState, Move, Piece
from jungle.model.constants import COLS, ROWS, Rank, Side


@pytest.fixture()
def view(qtbot, initial_state):
    widget = BoardView()
    qtbot.addWidget(widget)
    widget.resize(560, 700)
    widget.set_state(initial_state)
    widget.show()
    return widget


def test_cell_rect_and_pos_from_point_round_trip(view):
    for row in range(ROWS):
        for col in range(COLS):
            center = view.cell_rect((row, col)).center()
            assert view.pos_from_point(center.x(), center.y()) == (row, col)


def test_pos_from_point_outside_grid_returns_none(view):
    assert view.pos_from_point(-50, -50) is None
    assert view.pos_from_point(view.width() + 50, view.height() + 50) is None


def test_flip_transform_is_an_involution(view):
    view.set_flipped(True)
    for pos in ((0, 0), (3, 3), (8, 6), (2, 4)):
        display = view._display_pos(pos)
        assert display == (ROWS - 1 - pos[0], COLS - 1 - pos[1])
        assert view._board_pos(display) == pos
    # And clicks still map to the underlying board position when flipped.
    center = view.cell_rect((8, 0)).center()
    assert view.pos_from_point(center.x(), center.y()) == (8, 0)


def test_select_own_piece_populates_targets(view, initial_state):
    view._select((6, 0))  # RED elephant... verify it is RED's piece first
    piece = initial_state.board.piece_at((6, 0))
    assert piece.side is Side.RED
    expected = {m.to_pos for m in initial_state.legal_moves() if m.from_pos == (6, 0)}
    assert set(view._targets) == expected
    assert expected, "the elephant should have moves at the start"


def test_clicking_enemy_piece_does_not_select(view):
    view._select((6, 0))
    QTest.mouseClick(view, Qt.MouseButton.LeftButton,
                     pos=view.cell_rect((0, 0)).center().toPoint())
    assert view._selected is None  # deselected, not re-selected to blue's lion


def test_click_sequence_emits_move(qtbot, view):
    emitted = []
    view.move_requested.connect(emitted.append)
    move = Move((6, 0), (5, 0))  # RED elephant steps forward
    QTest.mouseClick(view, Qt.MouseButton.LeftButton,
                     pos=view.cell_rect(move.from_pos).center().toPoint())
    assert view._selected == (6, 0)
    QTest.mouseClick(view, Qt.MouseButton.LeftButton,
                     pos=view.cell_rect(move.to_pos).center().toPoint())
    assert emitted == [move]
    assert view._selected is None


def test_click_illegal_destination_clears_without_emitting(view):
    emitted = []
    view.move_requested.connect(emitted.append)
    QTest.mouseClick(view, Qt.MouseButton.LeftButton,
                     pos=view.cell_rect((6, 0)).center().toPoint())
    QTest.mouseClick(view, Qt.MouseButton.LeftButton,
                     pos=view.cell_rect((4, 0)).center().toPoint())  # two steps: illegal
    assert emitted == []
    assert view._selected is None


def test_input_disabled_blocks_interaction(view):
    emitted = []
    view.move_requested.connect(emitted.append)
    view.set_input_enabled(False)
    QTest.mouseClick(view, Qt.MouseButton.LeftButton,
                     pos=view.cell_rect((6, 0)).center().toPoint())
    assert view._selected is None
    assert emitted == []


def test_game_over_state_blocks_interaction(view):
    over = GameState.from_pieces(
        {(2, 3): Piece(Side.RED, Rank.DOG), (2, 4): Piece(Side.BLUE, Rank.CAT)}
    )
    over = over.apply_move(Move((2, 3), (2, 4)))  # red captures the last blue piece
    assert over.is_game_over
    view.set_state(over)
    emitted = []
    view.move_requested.connect(emitted.append)
    QTest.mouseClick(view, Qt.MouseButton.LeftButton,
                     pos=view.cell_rect((2, 4)).center().toPoint())
    assert emitted == []
