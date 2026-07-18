"""Constants for the Jungle / Dou Shou Qi game model."""

from __future__ import annotations

from enum import Enum, IntEnum


class Side(Enum):
    """A player side. RED starts at the bottom row; BLUE starts at the top row."""

    RED = 0
    BLUE = 1

    def opponent(self) -> Side:
        return Side.BLUE if self is Side.RED else Side.RED


class Rank(IntEnum):
    """Piece rank, from weakest to strongest.

    Follows the Wikipedia ordering (dog 3, wolf 4). Some Chinese sources
    swap dog and wolf; Wikipedia is the primary reference per prompt.md.
    """

    RAT = 1
    CAT = 2
    DOG = 3
    WOLF = 4
    LEOPARD = 5
    TIGER = 6
    LION = 7
    ELEPHANT = 8


class Terrain(Enum):
    """Terrain type of a board square."""

    LAND = 0
    RIVER = 1
    TRAP_RED = 2
    TRAP_BLUE = 3
    DEN_RED = 4
    DEN_BLUE = 5


# Board dimensions.
ROWS = 9
COLS = 7

# Den positions by side.
DEN_POSITIONS: dict[Side, tuple[int, int]] = {
    Side.RED: (8, 3),
    Side.BLUE: (0, 3),
}

# Trap positions by side.
TRAP_POSITIONS: dict[Side, frozenset[tuple[int, int]]] = {
    Side.RED: frozenset([(8, 2), (7, 3), (8, 4)]),
    Side.BLUE: frozenset([(0, 2), (1, 3), (0, 4)]),
}

# River squares (two 3x2 bodies separated by a land column at col 3).
RIVER_SQUARES: frozenset[tuple[int, int]] = frozenset(
    (row, col)
    for row in range(3, 6)
    for col in (1, 2, 4, 5)
)

# Initial piece layout. Row 0 is the top (BLUE side); row 8 is the bottom (RED side).
# Columns run left-to-right from the viewer's perspective.
# Standard position per Wikipedia / AncientChess.com:
#   BLUE: lion (0,0), tiger (0,6), dog (1,1), cat (1,5),
#         rat (2,0), leopard (2,2), wolf (2,4), elephant (2,6)
#   RED is the 180-degree rotation of BLUE.
INITIAL_LAYOUT: tuple[tuple[tuple[Side, Rank] | None, ...], ...] = (
    ((Side.BLUE, Rank.LION), None, None, None, None, None, (Side.BLUE, Rank.TIGER)),
    (None, (Side.BLUE, Rank.DOG), None, None, None, (Side.BLUE, Rank.CAT), None),
    ((Side.BLUE, Rank.RAT), None, (Side.BLUE, Rank.LEOPARD), None, (Side.BLUE, Rank.WOLF), None, (Side.BLUE, Rank.ELEPHANT)),
    (None, None, None, None, None, None, None),
    (None, None, None, None, None, None, None),
    (None, None, None, None, None, None, None),
    ((Side.RED, Rank.ELEPHANT), None, (Side.RED, Rank.WOLF), None, (Side.RED, Rank.LEOPARD), None, (Side.RED, Rank.RAT)),
    (None, (Side.RED, Rank.CAT), None, None, None, (Side.RED, Rank.DOG), None),
    ((Side.RED, Rank.TIGER), None, None, None, None, None, (Side.RED, Rank.LION)),
)


def terrain_at(pos: tuple[int, int]) -> Terrain:
    """Return the terrain type of a board square."""
    row, col = pos
    if pos in RIVER_SQUARES:
        return Terrain.RIVER
    if pos == DEN_POSITIONS[Side.RED]:
        return Terrain.DEN_RED
    if pos == DEN_POSITIONS[Side.BLUE]:
        return Terrain.DEN_BLUE
    if pos in TRAP_POSITIONS[Side.RED]:
        return Terrain.TRAP_RED
    if pos in TRAP_POSITIONS[Side.BLUE]:
        return Terrain.TRAP_BLUE
    return Terrain.LAND


def is_inside_board(pos: tuple[int, int]) -> bool:
    row, col = pos
    return 0 <= row < ROWS and 0 <= col < COLS
