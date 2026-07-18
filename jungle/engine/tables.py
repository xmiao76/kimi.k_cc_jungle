"""Precomputed geometry tables for the fast engine core.

All tables are generated from jungle.model.constants at import time so the
engine can never silently fork the model's terrain definitions.
"""

from __future__ import annotations

from jungle.model.constants import (
    COLS,
    DEN_POSITIONS,
    ROWS,
    TRAP_POSITIONS,
    Side,
    Terrain,
    terrain_at,
)

CELLS = ROWS * COLS

_DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def idx_of(row: int, col: int) -> int:
    return row * COLS + col


def row_of(idx: int) -> int:
    return idx // COLS


def col_of(idx: int) -> int:
    return idx % COLS


TERRAIN: tuple[Terrain, ...] = tuple(terrain_at((i // COLS, i % COLS)) for i in range(CELLS))
IS_RIVER: tuple[bool, ...] = tuple(t is Terrain.RIVER for t in TERRAIN)

DEN_IDX: dict[Side, int] = {side: idx_of(*pos) for side, pos in DEN_POSITIONS.items()}
TRAP_IDX: dict[Side, frozenset[int]] = {
    side: frozenset(idx_of(*pos) for pos in positions)
    for side, positions in TRAP_POSITIONS.items()
}

# Row/column per cell, and Manhattan distance to each side's own den —
# precomputed so the evaluator never needs division or enum access per piece.
ROW: tuple[int, ...] = tuple(i // COLS for i in range(CELLS))
COL: tuple[int, ...] = tuple(i % COLS for i in range(CELLS))
DIST_FROM_DEN: dict[Side, tuple[int, ...]] = {
    side: tuple(
        abs(ROW[i] - row_of(den)) + abs(COL[i] - col_of(den)) for i in range(CELLS)
    )
    for side, den in DEN_IDX.items()
}


def _build_neighbors() -> tuple[tuple[int, ...], ...]:
    neighbors: list[tuple[int, ...]] = []
    for i in range(CELLS):
        row, col = row_of(i), col_of(i)
        cells: list[int] = []
        for dr, dc in _DIRECTIONS:
            r, c = row + dr, col + dc
            if 0 <= r < ROWS and 0 <= c < COLS:
                cells.append(idx_of(r, c))
        neighbors.append(tuple(cells))
    return tuple(neighbors)


NEIGHBORS: tuple[tuple[int, ...], ...] = _build_neighbors()


def _build_jumps(horizontal_only: bool) -> tuple[tuple[tuple[int, tuple[int, ...]], ...], ...]:
    """Precompute river jumps, mirroring Board._jump_moves geometry.

    Each entry maps a cell to ((landing_idx, (crossed_idx, ...)), ...).
    A jump exists when the cells immediately along a direction are river and
    the first non-river cell beyond them is on the board.
    """
    table: list[tuple[tuple[int, tuple[int, ...]], ...]] = []
    for i in range(CELLS):
        row, col = row_of(i), col_of(i)
        jumps: list[tuple[int, tuple[int, ...]]] = []
        for dr, dc in _DIRECTIONS:
            if horizontal_only and dr != 0:
                continue
            r, c = row, col
            crossed: list[int] = []
            while True:
                r += dr
                c += dc
                if not (0 <= r < ROWS and 0 <= c < COLS):
                    break
                landing = idx_of(r, c)
                if TERRAIN[landing] is Terrain.RIVER:
                    crossed.append(landing)
                    continue
                if crossed:
                    jumps.append((landing, tuple(crossed)))
                break
        table.append(tuple(jumps))
    return tuple(table)


# Lions jump horizontally and vertically; tigers jump horizontally only.
JUMPS_LION: tuple[tuple[tuple[int, tuple[int, ...]], ...], ...] = _build_jumps(horizontal_only=False)
JUMPS_TIGER: tuple[tuple[tuple[int, tuple[int, ...]], ...], ...] = _build_jumps(horizontal_only=True)
