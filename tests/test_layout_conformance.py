"""The starting layout and terrain map must match the standard spec."""

from jungle.model.board import Board, GameState, Piece
from jungle.model.constants import (
    BLUE_LAYOUT,
    COLS,
    DEN_POSITIONS,
    RIVER_SQUARES,
    ROWS,
    TRAP_POSITIONS,
    Rank,
    Side,
    Terrain,
    terrain_at,
)


def test_starting_board_matches_spec_for_blue():
    expected = {
        (0, 0): Rank.LION,
        (0, 6): Rank.TIGER,
        (1, 1): Rank.DOG,
        (1, 5): Rank.CAT,
        (2, 0): Rank.RAT,
        (2, 2): Rank.LEOPARD,
        (2, 4): Rank.WOLF,
        (2, 6): Rank.ELEPHANT,
    }
    assert BLUE_LAYOUT == expected
    board = Board.starting()
    for pos, rank in expected.items():
        assert board.piece_at(pos) == Piece(Side.BLUE, rank)


def test_red_layout_is_180_degree_rotation_of_blue():
    board = Board.starting()
    for pos, rank in BLUE_LAYOUT.items():
        row, col = pos
        rotated = (ROWS - 1 - row, COLS - 1 - col)
        assert board.piece_at(rotated) == Piece(Side.RED, rank)


def test_starting_board_has_eight_pieces_per_side_one_of_each_rank():
    board = Board.starting()
    for side in (Side.RED, Side.BLUE):
        ranks = sorted(piece.rank for _, piece in board.positions() if piece.side is side)
        assert ranks == [
            Rank.RAT, Rank.CAT, Rank.DOG, Rank.WOLF,
            Rank.LEOPARD, Rank.TIGER, Rank.LION, Rank.ELEPHANT,
        ]


def test_red_moves_first():
    assert GameState.starting().current_side is Side.RED
    assert GameState.starting().move_count == 0


def test_terrain_map_matches_spec():
    dens = {(0, 3): Terrain.DEN_BLUE, (8, 3): Terrain.DEN_RED}
    traps_blue = {(0, 2), (0, 4), (1, 3)}
    traps_red = {(8, 2), (8, 4), (7, 3)}
    for row in range(ROWS):
        for col in range(COLS):
            pos = (row, col)
            terrain = terrain_at(pos)
            if pos in dens:
                assert terrain == dens[pos]
            elif pos in traps_blue:
                assert terrain is Terrain.TRAP_BLUE
            elif pos in traps_red:
                assert terrain is Terrain.TRAP_RED
            elif row in (3, 4, 5) and col in (1, 2, 4, 5):
                assert terrain is Terrain.RIVER
            else:
                assert terrain is Terrain.LAND


def test_river_trap_den_constants_are_consistent():
    assert len(RIVER_SQUARES) == 12
    assert TRAP_POSITIONS[Side.BLUE] == frozenset({(0, 2), (0, 4), (1, 3)})
    assert TRAP_POSITIONS[Side.RED] == frozenset({(8, 2), (8, 4), (7, 3)})
    assert DEN_POSITIONS[Side.BLUE] == (0, 3)
    assert DEN_POSITIONS[Side.RED] == (8, 3)


def test_starting_board_rotated_180_is_identical():
    board = Board.starting()
    assert board.rotate_180() == board


def test_no_piece_starts_on_river_trap_or_den_of_opponent():
    board = Board.starting()
    for pos, _ in board.positions():
        assert terrain_at(pos) is not Terrain.RIVER
