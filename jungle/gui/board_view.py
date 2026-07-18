"""Custom widget that renders the Jungle board and handles input."""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from jungle.gui.assets import (
    DEN_BLUE_COLOR,
    DEN_RED_COLOR,
    GRID_COLOR,
    LAND_COLOR,
    LAND_DARK_COLOR,
    LAST_MOVE_COLOR,
    LEGAL_MOVE_COLOR,
    RIVER_COLOR,
    RIVER_RIPPLE_COLOR,
    TRAP_BLUE_COLOR,
    TRAP_BLUE_MARK_COLOR,
    TRAP_RED_COLOR,
    TRAP_RED_MARK_COLOR,
    draw_piece,
)
from jungle.model.board import Board, GameState, Move, Piece
from jungle.model.constants import DEN_POSITIONS, RIVER_SQUARES, Rank, Side, Terrain, terrain_at


class BoardView(QWidget):
    """A widget that draws the Jungle board and emits move requests."""

    move_requested = pyqtSignal(object)  # Emits Move
    status_message = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._state: GameState | None = None
        self._selected_pos: tuple[int, int] | None = None
        self._legal_moves: list[Move] = []
        self._flipped = False
        self._last_move: Move | None = None
        self._minimum_cell = 48
        self.setMinimumSize(self._minimum_cell * 7, self._minimum_cell * 9)
        self.setSizePolicy(
            self.sizePolicy().Policy.Expanding,
            self.sizePolicy().Policy.Expanding,
        )

    def set_state(self, state: GameState) -> None:
        self._state = state
        self._selected_pos = None
        self._legal_moves = []
        self.update()

    def set_flipped(self, flipped: bool) -> None:
        self._flipped = flipped
        self.update()

    def set_last_move(self, move: Move | None) -> None:
        self._last_move = move
        self.update()

    def state(self) -> GameState | None:
        return self._state

    def flip_display_position(self, pos: tuple[int, int]) -> tuple[int, int]:
        """Convert internal board coords to display coords based on flip state."""
        if not self._flipped:
            return pos
        return (Board.ROWS - 1 - pos[0], Board.COLS - 1 - pos[1])

    def cell_rect(self, pos: tuple[int, int]) -> QRectF:
        """Return the QRectF for the board cell at `pos` in widget coordinates."""
        display_pos = self.flip_display_position(pos)
        cell_size = self._cell_size()
        x = display_pos[1] * cell_size + self._margin()
        y = display_pos[0] * cell_size + self._margin()
        return QRectF(x, y, cell_size, cell_size)

    def pos_from_point(self, point: QPointF) -> tuple[int, int] | None:
        """Map a widget coordinate to a board position, or None if outside."""
        margin = self._margin()
        cell_size = self._cell_size()
        x = point.x() - margin
        y = point.y() - margin
        if x < 0 or y < 0:
            return None
        col = int(x // cell_size)
        row = int(y // cell_size)
        if not (0 <= row < Board.ROWS and 0 <= col < Board.COLS):
            return None
        display_pos = (row, col)
        if self._flipped:
            internal = (
                Board.ROWS - 1 - display_pos[0],
                Board.COLS - 1 - display_pos[1],
            )
        else:
            internal = display_pos
        return internal

    def _cell_size(self) -> float:
        width = self.width() - 2 * self._margin()
        height = self.height() - 2 * self._margin()
        return min(width / Board.COLS, height / Board.ROWS)

    def _margin(self) -> float:
        return 8.0

    def paintEvent(self, event) -> None:  # noqa: ARG002
        if self._state is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw_board(painter)
        self._draw_last_move(painter)
        self._draw_legal_move_hints(painter)
        self._draw_pieces(painter)

    def _draw_board(self, painter: QPainter) -> None:
        if self._state is None:
            return
        # Background.
        rect = self.rect().adjusted(
            int(self._margin()),
            int(self._margin()),
            int(-self._margin()),
            int(-self._margin()),
        )
        painter.fillRect(rect, LAND_COLOR)

        # Individual squares: checkerboard land, terrain details on top.
        for pos in self._state.board.positions():
            cell = self.cell_rect(pos)
            terrain = terrain_at(pos)
            if (pos[0] + pos[1]) % 2 == 1:
                painter.fillRect(cell, LAND_DARK_COLOR)
            if terrain is Terrain.RIVER:
                painter.fillRect(cell, RIVER_COLOR)
                self._draw_river_ripples(painter, cell)
            elif terrain is Terrain.TRAP_RED:
                painter.fillRect(cell, TRAP_RED_COLOR)
                self._draw_trap_marker(painter, cell, TRAP_RED_MARK_COLOR)
            elif terrain is Terrain.TRAP_BLUE:
                painter.fillRect(cell, TRAP_BLUE_COLOR)
                self._draw_trap_marker(painter, cell, TRAP_BLUE_MARK_COLOR)
            elif terrain is Terrain.DEN_RED:
                painter.fillRect(cell, DEN_RED_COLOR)
            elif terrain is Terrain.DEN_BLUE:
                painter.fillRect(cell, DEN_BLUE_COLOR)

        # Grid lines.
        pen = QPen(GRID_COLOR)
        pen.setWidthF(2)
        painter.setPen(pen)
        cell_size = self._cell_size()
        left = self._margin()
        top = self._margin()
        right = left + cell_size * Board.COLS
        bottom = top + cell_size * Board.ROWS
        for i in range(Board.ROWS + 1):
            y = top + i * cell_size
            painter.drawLine(QPointF(left, y), QPointF(right, y))
        for j in range(Board.COLS + 1):
            x = left + j * cell_size
            painter.drawLine(QPointF(x, top), QPointF(x, bottom))

        # Den markers (stars).
        for side, den_pos in DEN_POSITIONS.items():
            cell = self.cell_rect(den_pos)
            self._draw_star(painter, cell, QColor("#f1c40f"))

    def _draw_river_ripples(self, painter: QPainter, cell: QRectF) -> None:
        pen = QPen(RIVER_RIPPLE_COLOR)
        pen.setWidthF(max(1.0, cell.width() * 0.03))
        painter.setPen(pen)
        inset = cell.width() * 0.18
        for fraction in (1 / 3, 2 / 3):
            y = cell.top() + cell.height() * fraction
            painter.drawLine(
                QPointF(cell.left() + inset, y),
                QPointF(cell.right() - inset, y),
            )

    def _draw_trap_marker(self, painter: QPainter, cell: QRectF, color: QColor) -> None:
        # Small warning triangle centered in the trap square.
        w = cell.width()
        cx = cell.center().x()
        top = cell.top() + w * 0.22
        bottom = cell.top() + w * 0.72
        triangle = QPolygonF(
            [
                QPointF(cx, top),
                QPointF(cx - w * 0.26, bottom),
                QPointF(cx + w * 0.26, bottom),
            ]
        )
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(triangle)

    def _draw_star(self, painter: QPainter, rect: QRectF, color: QColor) -> None:
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        outer_radius = min(rect.width(), rect.height()) * 0.34
        inner_radius = outer_radius * 0.45
        points = []
        for i in range(10):
            angle = -math.pi / 2 + i * math.pi / 5
            radius = outer_radius if i % 2 == 0 else inner_radius
            points.append(
                QPointF(
                    rect.center().x() + radius * math.cos(angle),
                    rect.center().y() + radius * math.sin(angle),
                )
            )
        painter.drawPolygon(QPolygonF(points))

    def _draw_last_move(self, painter: QPainter) -> None:
        if self._last_move is None:
            return
        pen = QPen(LAST_MOVE_COLOR)
        pen.setWidthF(self._cell_size() * 0.08)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.cell_rect(self._last_move.from_pos).adjusted(2, 2, -2, -2))
        painter.drawRect(self.cell_rect(self._last_move.to_pos).adjusted(2, 2, -2, -2))

    def _draw_legal_move_hints(self, painter: QPainter) -> None:
        if self._selected_pos is None or not self._legal_moves:
            return
        painter.setBrush(QBrush(LEGAL_MOVE_COLOR))
        painter.setPen(Qt.PenStyle.NoPen)
        radius = self._cell_size() * 0.12
        for move in self._legal_moves:
            cell = self.cell_rect(move.to_pos)
            painter.drawEllipse(cell.center(), radius, radius)

    def _draw_pieces(self, painter: QPainter) -> None:
        if self._state is None:
            return
        for pos in self._state.board.positions():
            piece = self._state.board.piece_at(pos)
            if piece is None:
                continue
            cell = self.cell_rect(pos)
            selected = self._selected_pos == pos
            draw_piece(painter, cell, piece.side, piece.rank, selected=selected)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if (
            event is None
            or self._state is None
            or self._state.winner is not None
            or self._state.draw
        ):
            return

        pos = self.pos_from_point(event.position())
        if pos is None:
            return

        piece = self._state.board.piece_at(pos)

        if self._selected_pos is None:
            if piece is not None and piece.side is self._state.current_side:
                self._selected_pos = pos
                self._legal_moves = [
                    m for m in self._state.legal_moves() if m.from_pos == pos
                ]
                self.status_message.emit(f"Selected {piece.rank.name} at {pos}")
                self.update()
            return

        # If a piece is already selected.
        selected_piece = self._state.board.piece_at(self._selected_pos)
        if selected_piece is None:
            self._selected_pos = None
            self._legal_moves = []
            self.update()
            return

        # Try to move to clicked square.
        move = Move(self._selected_pos, pos)
        if self._state.is_legal_move(move):
            self.move_requested.emit(move)
            self._selected_pos = None
            self._legal_moves = []
            return

        # If clicked another own piece, select it instead.
        if piece is not None and piece.side is self._state.current_side:
            self._selected_pos = pos
            self._legal_moves = [
                m for m in self._state.legal_moves() if m.from_pos == pos
            ]
            self.status_message.emit(f"Selected {piece.rank.name} at {pos}")
            self.update()
            return

        # Illegal destination: deselect.
        self._selected_pos = None
        self._legal_moves = []
        self.status_message.emit("Illegal move")
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(self._minimum_cell * 7 + 16, self._minimum_cell * 9 + 16)
