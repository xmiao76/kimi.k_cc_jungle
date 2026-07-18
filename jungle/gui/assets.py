"""Visual assets and piece rendering helpers."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen

from jungle.model.constants import Rank, Side

# Animal symbols used for pieces. These render as animals in most modern fonts.
PIECE_SYMBOLS: dict[Rank, str] = {
    Rank.RAT: "🐀",
    Rank.CAT: "🐈",
    Rank.WOLF: "🐺",
    Rank.DOG: "🐕",
    Rank.LEOPARD: "🐆",
    Rank.TIGER: "🐅",
    Rank.LION: "🦁",
    Rank.ELEPHANT: "🐘",
}

# Short English names shown on pieces in a small font below the emoji.
PIECE_NAMES: dict[Rank, str] = {
    Rank.RAT: "RAT",
    Rank.CAT: "CAT",
    Rank.WOLF: "WLF",
    Rank.DOG: "DOG",
    Rank.LEOPARD: "LEO",
    Rank.TIGER: "TGR",
    Rank.LION: "LIO",
    Rank.ELEPHANT: "ELE",
}

# Piece base colors by side.
SIDE_COLORS: dict[Side, QColor] = {
    Side.RED: QColor("#d9534f"),
    Side.BLUE: QColor("#5bc0de"),
}

SIDE_DARK_COLORS: dict[Side, QColor] = {
    Side.RED: QColor("#c9302c"),
    Side.BLUE: QColor("#31b0d5"),
}

# Terrain colors.
LAND_COLOR = QColor("#82cf5a")
LAND_DARK_COLOR = QColor("#54a03c")
RIVER_COLOR = QColor("#4facfe")
RIVER_RIPPLE_COLOR = QColor("#a8d8ff")
TRAP_RED_COLOR = QColor("#ff9999")
TRAP_BLUE_COLOR = QColor("#99ccff")
TRAP_RED_MARK_COLOR = QColor("#d64545")
TRAP_BLUE_MARK_COLOR = QColor("#4585d6")
DEN_RED_COLOR = QColor("#ff6666")
DEN_BLUE_COLOR = QColor("#66b3ff")
GRID_COLOR = QColor("#3e5f35")
SELECTED_HIGHLIGHT = QColor("#ffeb3b")
LEGAL_MOVE_COLOR = QColor("#ffffff")
LAST_MOVE_COLOR = QColor("#ffd700")


def draw_piece(
    painter: QPainter,
    rect: QRectF,
    side: Side,
    rank: Rank,
    selected: bool = False,
) -> None:
    """Draw a single piece inside `rect`: disc, emoji, and short name label."""
    base_color = SIDE_COLORS[side]
    dark_color = SIDE_DARK_COLORS[side]

    # Outer circle with gradient-like effect via concentric circles.
    margin = rect.width() * 0.05
    outer = rect.adjusted(margin, margin, -margin, -margin)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(dark_color))
    painter.drawEllipse(outer)

    inner = outer.adjusted(outer.width() * 0.08, outer.width() * 0.08, -outer.width() * 0.08, -outer.width() * 0.08)
    painter.setBrush(QBrush(base_color))
    painter.drawEllipse(inner)

    # Animal emoji, centered in the upper part of the cell.
    font = QFont("Segoe UI Emoji")
    if not font.exactMatch():
        font = QFont("Noto Color Emoji")
    if not font.exactMatch():
        font = QFont()
    font.setPointSizeF(rect.width() * 0.42)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QPen(QColor("#222222")))
    emoji_rect = QRectF(
        rect.x(), rect.y() + rect.height() * 0.02, rect.width(), rect.height() * 0.62
    )
    painter.drawText(emoji_rect, Qt.AlignmentFlag.AlignCenter, PIECE_SYMBOLS[rank])

    # Short name label near the bottom of the disc, with a dark halo so it
    # stays readable on both side colors.
    name_font = QFont()
    name_font.setPointSizeF(max(5.0, rect.width() * 0.17))
    name_font.setBold(True)
    painter.setFont(name_font)
    label_rect = QRectF(
        rect.x(), rect.y() + rect.height() * 0.58, rect.width(), rect.height() * 0.32
    )
    painter.setPen(QPen(QColor(0, 0, 0, 170)))
    painter.drawText(
        label_rect.translated(1.0, 1.0), Qt.AlignmentFlag.AlignCenter, PIECE_NAMES[rank]
    )
    painter.setPen(QPen(QColor("#ffffff")))
    painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, PIECE_NAMES[rank])

    if selected:
        pen = QPen(SELECTED_HIGHLIGHT)
        pen.setWidthF(rect.width() * 0.08)
        pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(outer)
