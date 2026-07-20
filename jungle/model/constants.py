"""Board geometry, terrain, piece ranks, and the standard starting layout.

Coordinate system: positions are ``(row, col)`` tuples. Row 0 is the top of
the board (BLUE's home edge), row 8 is the bottom (RED's home edge). Columns
run 0..6 left to right from RED's point of view.

Standard Jungle / Dou Shou Qi layout (per Wikipedia):

    row 0:  LIO ... TRP DEN TRP ... TIG
    row 1:  ... DOG ... ... ... CAT ...
    row 2:  RAT ... LEO ... WLF ... ELE
    rows 3-5: river in columns {1,2} and {4,5}
    rows 6-8: RED mirrors BLUE exactly (180-degree rotation).
"""

from __future__ import annotations

from enum import Enum, IntEnum


class Side(Enum):
    """The two players. RED moves first."""

    RED = 0
    BLUE = 1

    @property
    def opponent(self) -> "Side":
        return Side.BLUE if self is Side.RED else Side.RED


class Rank(IntEnum):
    """Animal ranks; a higher value captures an equal or lower value."""

    RAT = 1
    CAT = 2
    DOG = 3
    WOLF = 4
    LEOPARD = 5
    TIGER = 6
    LION = 7
    ELEPHANT = 8


class Terrain(Enum):
    LAND = 0
    RIVER = 1
    TRAP_RED = 2
    TRAP_BLUE = 3
    DEN_RED = 4
    DEN_BLUE = 5


ROWS = 9
COLS = 7

# A position is a (row, col) tuple of ints.
DEN_POSITIONS: dict[Side, tuple[int, int]] = {
    Side.BLUE: (0, 3),
    Side.RED: (8, 3),
}

TRAP_POSITIONS: dict[Side, frozenset[tuple[int, int]]] = {
    Side.BLUE: frozenset({(0, 2), (0, 4), (1, 3)}),
    Side.RED: frozenset({(8, 2), (8, 4), (7, 3)}),
}

RIVER_SQUARES: frozenset[tuple[int, int]] = frozenset(
    (row, col)
    for row in (3, 4, 5)
    for col in (1, 2, 4, 5)
)

# Standard starting layout for BLUE (top side). RED is the 180-degree
# rotation of this arrangement.
BLUE_LAYOUT: dict[tuple[int, int], Rank] = {
    (0, 0): Rank.LION,
    (0, 6): Rank.TIGER,
    (1, 1): Rank.DOG,
    (1, 5): Rank.CAT,
    (2, 0): Rank.RAT,
    (2, 2): Rank.LEOPARD,
    (2, 4): Rank.WOLF,
    (2, 6): Rank.ELEPHANT,
}


def initial_layout() -> dict[tuple[int, int], tuple[Side, Rank]]:
    """Full starting layout: position -> (side, rank) for both armies."""
    layout: dict[tuple[int, int], tuple[Side, Rank]] = {}
    for (row, col), rank in BLUE_LAYOUT.items():
        layout[(row, col)] = (Side.BLUE, rank)
        layout[(ROWS - 1 - row, COLS - 1 - col)] = (Side.RED, rank)
    return layout


def is_inside_board(pos: tuple[int, int]) -> bool:
    row, col = pos
    return 0 <= row < ROWS and 0 <= col < COLS


def terrain_at(pos: tuple[int, int]) -> Terrain:
    """The terrain at a board position (must be inside the board)."""
    for side in (Side.RED, Side.BLUE):
        if pos == DEN_POSITIONS[side]:
            return Terrain.DEN_RED if side is Side.RED else Terrain.DEN_BLUE
        if pos in TRAP_POSITIONS[side]:
            return Terrain.TRAP_RED if side is Side.RED else Terrain.TRAP_BLUE
    if pos in RIVER_SQUARES:
        return Terrain.RIVER
    return Terrain.LAND


# River jump geometry. A jump is described as (landing, path) where `path`
# holds the crossed river squares. The river forms two 3x2 regions:
# rows 3..5 x cols {1,2} and rows 3..5 x cols {4,5}.
#
#   horizontal (both lion and tiger): 3-cell leap across a region's 2-cell
#       width, e.g. (r,0) <-> (r,3) over (r,1),(r,2).
#   vertical (lion only, per this project's locked ruleset): 4-cell leap
#       across a region's 3-cell height, e.g. (2,c) <-> (6,c).
#
# The tiger must NOT jump vertically — this is the documented variant chosen
# for this application (see prompt.md and release README).

_HORIZONTAL_JUMPS: dict[tuple[int, int], tuple[tuple[tuple[int, int], tuple[tuple[int, int], ...]], ...]] = {}
_VERTICAL_JUMPS: dict[tuple[int, int], tuple[tuple[tuple[int, int], tuple[tuple[int, int], ...]], ...]] = {}


def _build_jump_tables() -> None:
    for row in (3, 4, 5):
        left = ((row, 1), (row, 2))
        right = ((row, 4), (row, 5))
        _HORIZONTAL_JUMPS.setdefault((row, 0), ())
        _HORIZONTAL_JUMPS[(row, 0)] += (((row, 3), left),)
        _HORIZONTAL_JUMPS.setdefault((row, 3), ())
        _HORIZONTAL_JUMPS[(row, 3)] += (((row, 0), left), ((row, 6), right))
        _HORIZONTAL_JUMPS.setdefault((row, 6), ())
        _HORIZONTAL_JUMPS[(row, 6)] += (((row, 3), right),)
    for col in (1, 2, 4, 5):
        path = ((3, col), (4, col), (5, col))
        _VERTICAL_JUMPS.setdefault((2, col), ())
        _VERTICAL_JUMPS[(2, col)] += (((6, col), path),)
        _VERTICAL_JUMPS.setdefault((6, col), ())
        _VERTICAL_JUMPS[(6, col)] += (((2, col), path),)


_build_jump_tables()


def river_jump_paths(
    pos: tuple[int, int], rank: Rank
) -> tuple[tuple[tuple[int, int], tuple[tuple[int, int], ...]], ...]:
    """Candidate river jumps for a piece at ``pos``: ((landing, path), ...).

    Pure geometry — occupancy and rat blocks are checked by the caller.
    The tiger only ever receives horizontal candidates.
    """
    if rank is Rank.LION:
        return _HORIZONTAL_JUMPS.get(pos, ()) + _VERTICAL_JUMPS.get(pos, ())
    if rank is Rank.TIGER:
        return _HORIZONTAL_JUMPS.get(pos, ())
    return ()


def orthogonal_neighbors(pos: tuple[int, int]) -> tuple[tuple[int, int], ...]:
    """In-board orthogonal neighbors of a position."""
    row, col = pos
    candidates = ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1))
    return tuple(p for p in candidates if is_inside_board(p))
