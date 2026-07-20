"""Visual assets: palette, piece artwork, and terrain accents.

All artwork is drawn in code with ``QPainter`` — there are no image files to
bundle, and the animal glyphs come from the OS emoji font (Segoe UI Emoji is
present on every supported Windows install).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen

from jungle.model.constants import Rank, Side

# -- palette -------------------------------------------------------------------

LAND_LIGHT = QColor("#EBDDB4")
LAND_DARK = QColor("#DCC893")
RIVER_FILL = QColor("#3D7AB8")
RIVER_RIPPLE = QColor("#8FC3EE")
TRAP_FILL = QColor("#E3B54C")
TRAP_MARKER = QColor("#7A5B12")
DEN_FILL_RED = QColor("#7E2A1E")
DEN_FILL_BLUE = QColor("#1F4E79")
DEN_STAR = QColor("#F4D03F")
GRID_LINE = QColor("#6E5B34")
SELECTION_RING = QColor("#F8C471")
LEGAL_DOT = QColor(39, 174, 96, 190)
LEGAL_CAPTURE = QColor(231, 76, 60, 220)
LAST_MOVE = QColor("#E67E22")
CAPTURE_FLASH = QColor("#C0392B")

PIECE_FILL = {Side.RED: QColor("#C0392B"), Side.BLUE: QColor("#2471A3")}
PIECE_RIM = {Side.RED: QColor("#6E1B12"), Side.BLUE: QColor("#123F5E")}
PIECE_TEXT = QColor("#FDFEFE")
PIECE_TEXT_OUTLINE = QColor(0, 0, 0, 170)

EMOJI_FONT_FAMILY = "Segoe UI Emoji"
LABEL_FONT_FAMILY = "Segoe UI"

RANK_EMOJI = {
    Rank.RAT: "🐭",
    Rank.CAT: "🐱",
    Rank.DOG: "🐶",
    Rank.WOLF: "🐺",
    Rank.LEOPARD: "🐆",
    Rank.TIGER: "🐯",
    Rank.LION: "🦁",
    Rank.ELEPHANT: "🐘",
}

RANK_LABEL = {
    Rank.RAT: "RAT",
    Rank.CAT: "CAT",
    Rank.DOG: "DOG",
    Rank.WOLF: "WLF",
    Rank.LEOPARD: "LEO",
    Rank.TIGER: "TIG",
    Rank.LION: "LIO",
    Rank.ELEPHANT: "ELE",
}


def draw_piece(
    painter: QPainter,
    rect: QRectF,
    side: Side,
    rank: Rank,
    selected: bool = False,
) -> None:
    """Draw one animal piece: a colored disc with its emoji and short label."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    margin = rect.width() * 0.07
    disc = rect.adjusted(margin, margin, -margin, -margin)

    painter.setPen(QPen(PIECE_RIM[side], max(2.0, rect.width() * 0.03)))
    painter.setBrush(PIECE_FILL[side])
    painter.drawEllipse(disc)

    # Animal emoji, centered in the upper ~2/3 of the disc.
    emoji_font = QFont(EMOJI_FONT_FAMILY)
    emoji_font.setPixelSize(int(rect.height() * 0.42))
    painter.setFont(emoji_font)
    emoji_rect = QRectF(disc.x(), disc.y() + disc.height() * 0.04,
                        disc.width(), disc.height() * 0.62)
    painter.drawText(emoji_rect, Qt.AlignmentFlag.AlignCenter, RANK_EMOJI[rank])

    # Short name with a dark outline so it stays readable on any disc color.
    label = RANK_LABEL[rank]
    label_font = QFont(LABEL_FONT_FAMILY)
    label_font.setPixelSize(max(8, int(rect.height() * 0.17)))
    label_font.setBold(True)
    painter.setFont(label_font)
    path = QPainterPath()
    baseline = disc.y() + disc.height() * 0.88
    fm_width = painter.fontMetrics().horizontalAdvance(label)
    path.addText(QPointF(disc.center().x() - fm_width / 2, baseline), label_font, label)
    painter.strokePath(path, QPen(PIECE_TEXT_OUTLINE, max(2.0, rect.width() * 0.025)))
    painter.fillPath(path, PIECE_TEXT)

    if selected:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(SELECTION_RING, max(3.0, rect.width() * 0.05)))
        ring = disc.adjusted(-2, -2, 2, 2)
        painter.drawEllipse(ring)


def draw_ripple_accents(painter: QPainter, rect: QRectF) -> None:
    """Two wave strokes across a river cell."""
    painter.setPen(QPen(RIVER_RIPPLE, max(1.5, rect.width() * 0.03)))
    for frac in (0.35, 0.65):
        y = rect.y() + rect.height() * frac
        path = QPainterPath(QPointF(rect.x() + rect.width() * 0.15, y))
        path.quadTo(rect.center().x(), y - rect.height() * 0.18,
                    rect.x() + rect.width() * 0.85, y)
        painter.drawPath(path)


def draw_trap_marker(painter: QPainter, rect: QRectF) -> None:
    """Warning-triangle glyph centered in a trap cell."""
    w, h = rect.width(), rect.height()
    path = QPainterPath()
    path.moveTo(rect.center().x(), rect.y() + h * 0.22)
    path.lineTo(rect.x() + w * 0.22, rect.y() + h * 0.74)
    path.lineTo(rect.x() + w * 0.78, rect.y() + h * 0.74)
    path.closeSubpath()
    painter.setPen(QPen(TRAP_MARKER, max(2.0, w * 0.035)))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)


def draw_den_star(painter: QPainter, rect: QRectF) -> None:
    """Five-pointed star centered in a den cell."""
    import math

    cx, cy = rect.center().x(), rect.center().y()
    outer = rect.width() * 0.30
    inner = outer * 0.45
    path = QPainterPath()
    for i in range(10):
        radius = outer if i % 2 == 0 else inner
        angle = -math.pi / 2 + i * math.pi / 5
        point = QPointF(cx + radius * math.cos(angle), cy + radius * math.sin(angle))
        if i == 0:
            path.moveTo(point)
        else:
            path.lineTo(point)
    path.closeSubpath()
    painter.setPen(QPen(DEN_STAR, max(1.5, rect.width() * 0.02)))
    painter.setBrush(DEN_STAR)
    painter.drawPath(path)
