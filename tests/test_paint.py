"""Paint smoke tests: the board and pieces must render without crashing."""

from PyQt6.QtGui import QColor, QPainter, QPixmap

from jungle.gui.assets import (
    LAND_COLOR,
    LAND_DARK_COLOR,
    PIECE_NAMES,
    RIVER_COLOR,
    draw_piece,
)
from jungle.gui.board_view import BoardView
from jungle.model.board import Board, GameState, Move
from jungle.model.constants import Rank, Side


def test_draw_piece_all_ranks_with_labels(qtbot):
    assert len(PIECE_NAMES) == 8
    pixmap = QPixmap(640, 80)
    pixmap.fill(QColor("#7ec850"))
    painter = QPainter(pixmap)
    for i, rank in enumerate(Rank):
        draw_piece(
            painter,
            pixmap.rect().toRectF().adjusted(i * 80.0, 0, -(7 - i) * 80.0, 0),
            Side.RED if i % 2 == 0 else Side.BLUE,
            rank,
            selected=i == 0,
        )
    painter.end()
    assert not pixmap.isNull()


def test_board_renders_to_pixmap(qtbot):
    view = BoardView()
    qtbot.addWidget(view)
    state = GameState(board=Board.starting(), current_side=Side.RED)
    view.set_state(state)
    view.set_last_move(Move((8, 0), (7, 0)))
    view.resize(7 * 64 + 16, 9 * 64 + 16)
    pixmap = view.grab()
    assert not pixmap.isNull()

    image = pixmap.toImage()

    def cell_color(pos):
        return image.pixelColor(view.cell_rect(pos).center().toPoint()).name()

    # River cell center keeps the river color (ripples are off-center).
    assert cell_color((4, 1)) == RIVER_COLOR.name()
    # Checkerboard land alternates.
    assert cell_color((4, 0)) == LAND_COLOR.name()
    assert cell_color((4, 3)) == LAND_DARK_COLOR.name()
    # Checkerboard is consistent under flip as well (visual-only rotation).
    view.set_flipped(True)
    flipped = view.grab().toImage()
    assert flipped.pixelColor(view.cell_rect((4, 1)).center().toPoint()).name() == RIVER_COLOR.name()


def test_board_renders_selection_and_hints(qtbot):
    view = BoardView()
    qtbot.addWidget(view)
    state = GameState(board=Board.starting(), current_side=Side.RED)
    view.set_state(state)
    view.resize(7 * 64 + 16, 9 * 64 + 16)
    # Simulate a selection with legal-move hints visible.
    view._selected_pos = (8, 0)
    view._legal_moves = [m for m in state.legal_moves() if m.from_pos == (8, 0)]
    pixmap = view.grab()
    assert not pixmap.isNull()
