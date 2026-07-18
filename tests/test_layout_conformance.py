"""Conformance tests pinning the standard Jungle starting position."""

from jungle.model.board import Board, GameState, Piece
from jungle.model.constants import Rank, Side

# Standard starting position per Wikipedia / AncientChess.com.
EXPECTED_LAYOUT: dict[tuple[int, int], Piece] = {
    (0, 0): Piece(Side.BLUE, Rank.LION),
    (0, 6): Piece(Side.BLUE, Rank.TIGER),
    (1, 1): Piece(Side.BLUE, Rank.DOG),
    (1, 5): Piece(Side.BLUE, Rank.CAT),
    (2, 0): Piece(Side.BLUE, Rank.RAT),
    (2, 2): Piece(Side.BLUE, Rank.LEOPARD),
    (2, 4): Piece(Side.BLUE, Rank.WOLF),
    (2, 6): Piece(Side.BLUE, Rank.ELEPHANT),
    (8, 6): Piece(Side.RED, Rank.LION),
    (8, 0): Piece(Side.RED, Rank.TIGER),
    (7, 5): Piece(Side.RED, Rank.DOG),
    (7, 1): Piece(Side.RED, Rank.CAT),
    (6, 6): Piece(Side.RED, Rank.RAT),
    (6, 4): Piece(Side.RED, Rank.LEOPARD),
    (6, 2): Piece(Side.RED, Rank.WOLF),
    (6, 0): Piece(Side.RED, Rank.ELEPHANT),
}


def test_exact_starting_layout():
    board = Board.starting()
    for pos in board.positions():
        assert board.piece_at(pos) == EXPECTED_LAYOUT.get(pos), f"mismatch at {pos}"


def test_starting_layout_is_180_symmetric():
    board = Board.starting()
    rotated = board.rotate_180()
    for pos, piece in EXPECTED_LAYOUT.items():
        expected = Piece(piece.side.opponent(), piece.rank)
        assert rotated.piece_at(pos) == expected, f"asymmetry at {pos}"


def test_starting_move_count():
    state = GameState(board=Board.starting(), current_side=Side.RED)
    assert len(state.legal_moves()) == 24
