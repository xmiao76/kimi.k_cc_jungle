"""Precomputed board geometry for the fast engine core.

Everything here is derived from ``jungle.model.constants`` at import time —
never hand-duplicated — so the fast core cannot drift from the rules of
record. Cells are indexed ``row * COLS + col``; sides are 0 (RED) and
1 (BLUE), matching ``model.zobrist.side_index``.
"""

from __future__ import annotations

from jungle.model.constants import (
    COLS,
    DEN_POSITIONS,
    ROWS,
    TRAP_POSITIONS,
    Rank,
    Side,
    Terrain,
    orthogonal_neighbors,
    river_jump_paths,
    terrain_at,
)

CELL_COUNT = ROWS * COLS

RED = 0
BLUE = 1


def idx_of(row: int, col: int) -> int:
    return row * COLS + col


def row_of(idx: int) -> int:
    return idx // COLS


def col_of(idx: int) -> int:
    return idx % COLS


def _positions():
    for row in range(ROWS):
        for col in range(COLS):
            yield (row, col)


TERRAIN: tuple[Terrain, ...] = tuple(terrain_at(pos) for pos in _positions())
IS_RIVER: tuple[bool, ...] = tuple(t is Terrain.RIVER for t in TERRAIN)

NEIGHBORS: tuple[tuple[int, ...], ...] = tuple(
    tuple(idx_of(r, c) for r, c in orthogonal_neighbors(pos)) for pos in _positions()
)

# DEN_IDX[side] = cell index of that side's own den.
DEN_IDX: tuple[int, int] = (
    idx_of(*DEN_POSITIONS[Side.RED]),
    idx_of(*DEN_POSITIONS[Side.BLUE]),
)

# TRAPS[side] = cell indices of that side's traps (the ones guarding its den).
TRAPS: tuple[frozenset[int], frozenset[int]] = (
    frozenset(idx_of(r, c) for r, c in TRAP_POSITIONS[Side.RED]),
    frozenset(idx_of(r, c) for r, c in TRAP_POSITIONS[Side.BLUE]),
)

# TRAP_TABLE[side][idx] -> True when idx is one of `side`'s traps. A piece of
# the OTHER side standing there defends with rank 0.
TRAP_TABLE: tuple[tuple[bool, ...], tuple[bool, ...]] = (
    tuple(i in TRAPS[RED] for i in range(CELL_COUNT)),
    tuple(i in TRAPS[BLUE] for i in range(CELL_COUNT)),
)


def _build_jumps(rank: Rank) -> tuple[tuple[tuple[int, tuple[int, ...]], ...], ...]:
    table: list[tuple[tuple[int, tuple[int, ...]], ...]] = []
    for pos in _positions():
        entries = tuple(
            (idx_of(*landing), tuple(idx_of(r, c) for r, c in path))
            for landing, path in river_jump_paths(pos, rank)
        )
        table.append(entries)
    return tuple(table)


# JUMPS[rank][idx] -> ((landing_idx, (crossed river cell indices)), ...).
# Tiger geometry intentionally has no vertical entries (locked variant).
JUMPS: dict[int, tuple[tuple[tuple[int, tuple[int, ...]], ...], ...]] = {
    int(Rank.LION): _build_jumps(Rank.LION),
    int(Rank.TIGER): _build_jumps(Rank.TIGER),
}

# Manhattan distance from each cell to each side's den (for advancement eval).
DIST_TO_DEN: tuple[tuple[int, ...], tuple[int, ...]] = (
    tuple(
        abs(row_of(i) - DEN_POSITIONS[Side.RED][0]) + abs(col_of(i) - DEN_POSITIONS[Side.RED][1])
        for i in range(CELL_COUNT)
    ),
    tuple(
        abs(row_of(i) - DEN_POSITIONS[Side.BLUE][0]) + abs(col_of(i) - DEN_POSITIONS[Side.BLUE][1])
        for i in range(CELL_COUNT)
    ),
)

MAX_DEN_DIST = max(max(DIST_TO_DEN[RED]), max(DIST_TO_DEN[BLUE]))

# Full pairwise Manhattan distance between cells (for animal-proximity terms).
CELL_DIST: tuple[tuple[int, ...], ...] = tuple(
    tuple(abs(row_of(a) - row_of(b)) + abs(col_of(a) - col_of(b)) for b in range(CELL_COUNT))
    for a in range(CELL_COUNT)
)
