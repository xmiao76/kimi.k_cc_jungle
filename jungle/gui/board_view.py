"""The interactive board widget.

Rendering only — game state lives in the model. The ``flipped`` flag is a
pure display transform: it maps board coordinates to screen coordinates and
back, and never touches the ``GameState``, sides, or turn.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from jungle.gui import assets
from jungle.model.board import GameState, Move
from jungle.model.constants import COLS, ROWS, Side, Terrain, terrain_at


class BoardView(QWidget):
    move_requested = Signal(object)  # jungle.model.board.Move
    status_message = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._state: Optional[GameState] = None
        self._flipped = False
        self._selected: Optional[tuple[int, int]] = None
        self._targets: dict[tuple[int, int], Move] = {}
        self._last_move: Optional[Move] = None
        self._last_capture = False
        self._input_enabled = True
        self.setMinimumSize(420, 540)

    # -- public API -------------------------------------------------------

    def set_state(
        self,
        state: GameState,
        last_move: Optional[Move] = None,
        last_capture: bool = False,
    ) -> None:
        self._state = state
        self._last_move = last_move
        self._last_capture = last_capture
        self.clear_selection()
        self.update()

    def set_flipped(self, flipped: bool) -> None:
        """View-only rotation. Does not alter state, sides, or turn."""
        self._flipped = flipped
        self.update()

    def is_flipped(self) -> bool:
        return self._flipped

    def set_input_enabled(self, enabled: bool) -> None:
        self._input_enabled = enabled
        if not enabled:
            self.clear_selection()

    def clear_selection(self) -> None:
        self._selected = None
        self._targets = {}
        self.update()

    # -- coordinate mapping -------------------------------------------------

    def _display_pos(self, pos: tuple[int, int]) -> tuple[int, int]:
        """Board position -> displayed (row, col) after the flip transform."""
        if self._flipped:
            return (ROWS - 1 - pos[0], COLS - 1 - pos[1])
        return pos

    def _board_pos(self, display_pos: tuple[int, int]) -> tuple[int, int]:
        """Displayed (row, col) -> board position (inverse of _display_pos)."""
        return self._display_pos(display_pos)  # the transform is an involution

    def _grid_geometry(self) -> tuple[float, float, float]:
        """(cell_size, origin_x, origin_y) centering the grid in the widget."""
        margin = 12.0
        cell = min((self.width() - 2 * margin) / COLS, (self.height() - 2 * margin) / ROWS)
        origin_x = (self.width() - cell * COLS) / 2
        origin_y = (self.height() - cell * ROWS) / 2
        return cell, origin_x, origin_y

    def cell_rect(self, pos: tuple[int, int]) -> QRectF:
        """Widget rectangle of a BOARD position (flip-aware)."""
        cell, origin_x, origin_y = self._grid_geometry()
        drow, dcol = self._display_pos(pos)
        return QRectF(origin_x + dcol * cell, origin_y + drow * cell, cell, cell)

    def pos_from_point(self, x: float, y: float) -> Optional[tuple[int, int]]:
        """BOARD position at widget coordinates, or None off the grid."""
        cell, origin_x, origin_y = self._grid_geometry()
        dcol = int((x - origin_x) // cell)
        drow = int((y - origin_y) // cell)
        if 0 <= drow < ROWS and 0 <= dcol < COLS:
            return self._board_pos((drow, dcol))
        return None

    # -- painting -----------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_cells(painter)
        self._paint_grid(painter)
        self._paint_last_move(painter)
        self._paint_targets(painter)
        self._paint_pieces(painter)
        painter.end()

    def _paint_cells(self, painter: QPainter) -> None:
        for row in range(ROWS):
            for col in range(COLS):
                rect = self.cell_rect((row, col))
                terrain = terrain_at((row, col))
                if terrain is Terrain.RIVER:
                    painter.fillRect(rect, assets.RIVER_FILL)
                    assets.draw_ripple_accents(painter, rect)
                elif terrain in (Terrain.TRAP_RED, Terrain.TRAP_BLUE):
                    painter.fillRect(rect, self._land_color(row, col))
                    painter.fillRect(rect, assets.TRAP_FILL)
                    assets.draw_trap_marker(painter, rect)
                elif terrain in (Terrain.DEN_RED, Terrain.DEN_BLUE):
                    fill = assets.DEN_FILL_RED if terrain is Terrain.DEN_RED else assets.DEN_FILL_BLUE
                    painter.fillRect(rect, fill)
                    assets.draw_den_star(painter, rect)
                else:
                    painter.fillRect(rect, self._land_color(row, col))

    @staticmethod
    def _land_color(row: int, col: int) -> QColor:
        return assets.LAND_LIGHT if (row + col) % 2 == 0 else assets.LAND_DARK

    def _paint_grid(self, painter: QPainter) -> None:
        cell, origin_x, origin_y = self._grid_geometry()
        painter.setPen(QPen(assets.GRID_LINE, 1.5))
        for col in range(COLS + 1):
            x = origin_x + col * cell
            painter.drawLine(int(x), int(origin_y), int(x), int(origin_y + ROWS * cell))
        for row in range(ROWS + 1):
            y = origin_y + row * cell
            painter.drawLine(int(origin_x), int(y), int(origin_x + COLS * cell), int(y))

    def _paint_last_move(self, painter: QPainter) -> None:
        if self._last_move is None:
            return
        color = assets.CAPTURE_FLASH if self._last_capture else assets.LAST_MOVE
        pen = QPen(color, 3)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for pos in (self._last_move.from_pos, self._last_move.to_pos):
            painter.drawRect(self.cell_rect(pos).adjusted(2, 2, -2, -2))

    def _paint_targets(self, painter: QPainter) -> None:
        if self._state is None:
            return
        for to_pos in self._targets:
            rect = self.cell_rect(to_pos)
            occupant = self._state.board.piece_at(to_pos)
            if occupant is not None:
                # Capture target: red ring.
                painter.setPen(QPen(assets.LEGAL_CAPTURE, max(3.0, rect.width() * 0.05)))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(rect.adjusted(4, 4, -4, -4))
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(assets.LEGAL_DOT)
                radius = rect.width() * 0.14
                painter.drawEllipse(rect.center(), radius, radius)

    def _paint_pieces(self, painter: QPainter) -> None:
        if self._state is None:
            return
        for pos, piece in self._state.board.positions():
            rect = self.cell_rect(pos)
            assets.draw_piece(painter, rect, piece.side, piece.rank, selected=(pos == self._selected))

    # -- interaction ---------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if not self._input_enabled or self._state is None or self._state.is_game_over:
            return
        pos = self.pos_from_point(event.position().x(), event.position().y())
        if pos is None:
            return
        if self._selected is not None and pos in self._targets:
            move = self._targets[pos]
            self.clear_selection()
            self.move_requested.emit(move)
            return
        piece = self._state.board.piece_at(pos)
        if piece is not None and piece.side is self._state.current_side:
            self._select(pos)
        else:
            if self._selected is not None:
                self.status_message.emit("Selection cleared")
            self.clear_selection()

    def _select(self, pos: tuple[int, int]) -> None:
        self._selected = pos
        self._targets = {m.to_pos: m for m in self._state.legal_moves() if m.from_pos == pos}
        self.update()
