"""Rendering conformance: terrain colors and piece discs at expected pixels.

Runs offscreen, where no font glyphs exist — so assertions target filled
geometry (cell backgrounds, discs, dots), never glyph shapes.
"""

import pytest
from PySide6.QtGui import QImage

from jungle.gui import assets
from jungle.gui.board_view import BoardView
from jungle.model.board import GameState, Move
from jungle.model.constants import Side


@pytest.fixture()
def view(qtbot, initial_state):
    widget = BoardView()
    qtbot.addWidget(widget)
    widget.resize(560, 700)
    widget.set_state(initial_state)
    widget.show()
    return widget


def _pixel(view: BoardView, pos, fx: float = 0.5, fy: float = 0.5):
    """Pixel color at a fractional point inside a cell."""
    rect = view.cell_rect(pos)
    x = int(rect.x() + rect.width() * fx)
    y = int(rect.y() + rect.height() * fy)
    image: QImage = view.grab().toImage()
    return image.pixelColor(x, y)


def _close(c1, c2, tol: int = 12) -> bool:
    return all(abs(a - b) <= tol for a, b in zip((c1.red(), c1.green(), c1.blue()),
                                                 (c2.red(), c2.green(), c2.blue())))


def test_land_is_checkerboarded(view):
    # Empty cells only — occupied cells show the piece disc at center.
    assert _close(_pixel(view, (0, 1)), assets.LAND_DARK)   # (0+1) odd -> dark
    assert _close(_pixel(view, (3, 3)), assets.LAND_LIGHT)  # even -> light
    assert _close(_pixel(view, (1, 0)), assets.LAND_DARK)
    assert _close(_pixel(view, (4, 0)), assets.LAND_LIGHT)


def test_river_cells_are_blue(view):
    for pos in ((3, 1), (4, 2), (5, 4)):
        color = _pixel(view, pos)
        assert _close(color, assets.RIVER_FILL), f"{pos}: {color.name()}"


def test_trap_cells_are_amber(view):
    for pos in ((0, 2), (1, 3), (8, 4)):
        # sample near a corner to avoid the triangle outline stroke
        assert _close(_pixel(view, pos, 0.15, 0.15), assets.TRAP_FILL), pos


def test_dens_show_star_on_side_color(view):
    # Center of the star is gold; a corner keeps the den's side color.
    assert _close(_pixel(view, (0, 3)), assets.DEN_STAR)
    assert _close(_pixel(view, (0, 3), 0.08, 0.08), assets.DEN_FILL_BLUE)
    assert _close(_pixel(view, (8, 3)), assets.DEN_STAR)
    assert _close(_pixel(view, (8, 3), 0.08, 0.08), assets.DEN_FILL_RED)


def test_pieces_render_as_side_colored_discs(view):
    # Sample off-center inside the disc, away from the glyph area.
    red = _pixel(view, (8, 0), 0.5, 0.82)   # RED lion disc lower-left area
    blue = _pixel(view, (0, 0), 0.5, 0.82)  # BLUE lion
    assert _close(red, assets.PIECE_FILL[Side.RED], tol=30)
    assert _close(blue, assets.PIECE_FILL[Side.BLUE], tol=30)


def test_legal_move_dot_is_green(view):
    view._select((6, 0))  # RED elephant; (5,0) is a legal empty destination
    color = _pixel(view, (5, 0))
    assert color.green() > color.red() + 40
    assert color.green() > color.blue() + 20


def test_last_move_highlight_outlines_both_squares(view, initial_state):
    move = Move((6, 0), (5, 0))
    state = initial_state.apply_move(move)
    view.set_state(state, last_move=move, last_capture=False)
    for pos in (move.from_pos, move.to_pos):
        # The outline hugs the cell's inner edge (2px inset, 3px pen);
        # sample the middle of the top edge.
        color = _pixel(view, pos, 0.5, 0.03)
        assert color.red() > 150 and color.green() < 190, f"{pos}: {color.name()}"


def test_flipped_view_moves_piece_rendering(view):
    view.set_flipped(True)
    # RED lion at board (8,0) renders at display (0,6): its disc pixels now
    # sit in the top-right cell region.
    color = _pixel(view, (8, 0), 0.5, 0.82)
    assert _close(color, assets.PIECE_FILL[Side.RED], tol=30)
    # ...and the cell that used to show it (top-left unflipped region) shows
    # the blue tiger at board (0,6), now displayed bottom-left.
    color = _pixel(view, (0, 6), 0.5, 0.82)
    assert _close(color, assets.PIECE_FILL[Side.BLUE], tol=30)
