"""Deterministic Zobrist keys for position hashing (shared by model and engine)."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from jungle.model.constants import COLS, ROWS, Side

if TYPE_CHECKING:  # pragma: no cover
    from jungle.model.board import Board

# Fixed seed so keys are reproducible across runs (0x4A554E47 == "JUNG").
_rng = random.Random(0x4A554E47)

# Piece code: rank.value (1..8) for BLUE, 8 + rank.value (9..16) for RED; 0 = empty.
TABLE: tuple[tuple[int, ...], ...] = tuple(
    tuple(_rng.getrandbits(64) for _ in range(17)) for _ in range(ROWS * COLS)
)
SIDE_KEY: int = _rng.getrandbits(64)


def piece_code(side: Side, rank_value: int) -> int:
    """Return the Zobrist piece code for a side and rank value."""
    return rank_value + (8 if side is Side.RED else 0)


def position_key(board: Board, side: Side) -> int:
    """Return the Zobrist key for a board and the side to move."""
    key = SIDE_KEY if side is Side.RED else 0
    for pos in board.positions():
        piece = board.piece_at(pos)
        if piece is not None:
            code = piece_code(piece.side, piece.rank.value)
            key ^= TABLE[pos[0] * COLS + pos[1]][code]
    return key
