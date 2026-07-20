"""Deterministic Zobrist keys shared by the model and the fast engine core.

A position key identifies the full piece placement plus the side to move; it
drives threefold-repetition detection and the engine's transposition table.
The table is generated from a fixed seed so keys are stable across runs,
which the model<->engine differential tests rely on.
"""

from __future__ import annotations

import random

from jungle.model.constants import COLS, ROWS, Rank, Side

SEED = 0x5EED_D05E_0CAB_2024

NUM_CELLS = ROWS * COLS
MAX_RANK = 8

_rng = random.Random(SEED)


def _next_key() -> int:
    return _rng.getrandbits(64)


# [side][rank][cell] — rank 0 slot is unused so keys can be indexed directly.
PIECE_KEYS: list[list[list[int]]] = [
    [[_next_key() for _ in range(NUM_CELLS)] for _ in range(MAX_RANK + 1)]
    for _ in range(2)
]

SIDE_TO_MOVE_KEY = _next_key()


def side_index(side: Side) -> int:
    return 0 if side is Side.RED else 1


def piece_key(side: Side, rank: Rank, cell: int) -> int:
    """Zobrist key component for one piece on one cell (row-major index)."""
    return PIECE_KEYS[side_index(side)][int(rank)][cell]


def piece_key_at(side: Side, rank: Rank, pos: tuple[int, int]) -> int:
    row, col = pos
    return piece_key(side, rank, row * COLS + col)
