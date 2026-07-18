"""Smoke tests for the core board model."""

import pytest

from jungle.model.board import Board, GameState, IllegalMoveError, Move, Piece
from jungle.model.constants import Rank, Side, Terrain, terrain_at


def _board_with(pieces: dict[tuple[int, int], Piece]) -> Board:
    rows: list[list[Piece | None]] = [[None for _ in range(7)] for _ in range(9)]
    for (row, col), piece in pieces.items():
        rows[row][col] = piece
    return Board(tuple(tuple(row) for row in rows))


def test_board_dimensions():
    board = Board.starting()
    assert board.ROWS == 9
    assert board.COLS == 7


def test_starting_piece_counts():
    board = Board.starting()
    counts: dict[Side, int] = {Side.RED: 0, Side.BLUE: 0}
    for pos in board.positions():
        piece = board.piece_at(pos)
        if piece is not None:
            counts[piece.side] += 1
    assert counts[Side.RED] == 8
    assert counts[Side.BLUE] == 8


def test_starting_layout():
    board = Board.starting()
    assert board.piece_at((0, 0)) == Piece(Side.BLUE, Rank.LION)
    assert board.piece_at((0, 6)) == Piece(Side.BLUE, Rank.TIGER)
    assert board.piece_at((1, 1)) == Piece(Side.BLUE, Rank.DOG)
    assert board.piece_at((1, 5)) == Piece(Side.BLUE, Rank.CAT)
    assert board.piece_at((2, 0)) == Piece(Side.BLUE, Rank.RAT)
    assert board.piece_at((2, 6)) == Piece(Side.BLUE, Rank.ELEPHANT)
    assert board.piece_at((8, 0)) == Piece(Side.RED, Rank.TIGER)
    assert board.piece_at((8, 6)) == Piece(Side.RED, Rank.LION)
    assert board.piece_at((6, 0)) == Piece(Side.RED, Rank.ELEPHANT)
    assert board.piece_at((6, 6)) == Piece(Side.RED, Rank.RAT)
    assert board.piece_at((7, 1)) == Piece(Side.RED, Rank.CAT)
    assert board.piece_at((7, 5)) == Piece(Side.RED, Rank.DOG)


def test_rotate_180_symmetry():
    board = Board.starting()
    rotated = board.rotate_180()
    assert rotated.piece_at((8, 6)) == Piece(Side.BLUE, Rank.LION)
    assert rotated.piece_at((0, 0)) == Piece(Side.RED, Rank.LION)
    assert rotated.piece_at((0, 6)) == Piece(Side.RED, Rank.TIGER)
    assert rotated.piece_at((8, 0)) == Piece(Side.BLUE, Rank.TIGER)


def test_terrain():
    assert terrain_at((0, 3)) is Terrain.DEN_BLUE
    assert terrain_at((8, 3)) is Terrain.DEN_RED
    assert terrain_at((3, 1)) is Terrain.RIVER
    assert terrain_at((3, 4)) is Terrain.RIVER
    assert terrain_at((0, 2)) is Terrain.TRAP_BLUE
    assert terrain_at((8, 2)) is Terrain.TRAP_RED
    assert terrain_at((4, 3)) is Terrain.LAND


def test_legal_move_basic():
    state = GameState(board=Board.starting(), current_side=Side.RED)
    # Red tiger at (8,0) can move up to (7,0).
    assert state.is_legal_move(Move((8, 0), (7, 0)))


def test_cannot_move_into_own_den():
    state = GameState(board=Board.starting(), current_side=Side.RED)
    moves = state.legal_moves()
    for move in moves:
        terrain = terrain_at(move.to_pos)
        piece = state.board.piece_at(move.from_pos)
        assert piece is not None
        if terrain is Terrain.DEN_RED:
            assert piece.side is not Side.RED
        if terrain is Terrain.DEN_BLUE:
            assert piece.side is not Side.BLUE


def test_rat_can_enter_river():
    board = _board_with({(2, 1): Piece(Side.RED, Rank.RAT)})
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((2, 1), (3, 1)))


def test_lion_cannot_enter_river():
    board = _board_with({(2, 1): Piece(Side.RED, Rank.LION)})
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((2, 1), (3, 1)))


def test_rat_captures_elephant_on_land():
    board = _board_with({
        (2, 0): Piece(Side.RED, Rank.RAT),
        (2, 1): Piece(Side.BLUE, Rank.ELEPHANT),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((2, 0), (2, 1)))


def test_elephant_cannot_capture_rat():
    board = _board_with({
        (2, 0): Piece(Side.RED, Rank.ELEPHANT),
        (2, 1): Piece(Side.BLUE, Rank.RAT),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((2, 0), (2, 1)))


def test_rat_in_river_safe_from_land():
    board = _board_with({
        (3, 1): Piece(Side.RED, Rank.RAT),
        (2, 1): Piece(Side.BLUE, Rank.LION),
    })
    state = GameState(board=board, current_side=Side.BLUE)
    assert not state.is_legal_move(Move((2, 1), (3, 1)))


def test_lion_horizontal_jump():
    board = _board_with({(4, 0): Piece(Side.RED, Rank.LION)})
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((4, 0), (4, 3)))


def test_tiger_horizontal_jump():
    board = _board_with({(4, 0): Piece(Side.RED, Rank.TIGER)})
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((4, 0), (4, 3)))


def test_lion_vertical_jump():
    board = _board_with({(2, 1): Piece(Side.RED, Rank.LION)})
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((2, 1), (6, 1)))


def test_tiger_vertical_jump_illegal():
    board = _board_with({(2, 1): Piece(Side.RED, Rank.TIGER)})
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((2, 1), (6, 1)))


def test_jump_blocked_by_rat():
    board = _board_with({
        (2, 1): Piece(Side.RED, Rank.LION),
        (4, 1): Piece(Side.BLUE, Rank.RAT),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((2, 1), (6, 1)))


def test_trap_reduces_rank():
    board = _board_with({
        (7, 3): Piece(Side.BLUE, Rank.ELEPHANT),
        (8, 3): Piece(Side.RED, Rank.RAT),
    })
    # Wait, blue elephant is in red trap at (7,3). Red rat at (8,3) adjacent.
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((8, 3), (7, 3)))


def test_win_by_den():
    board = _board_with({
        (1, 3): Piece(Side.RED, Rank.RAT),
    })
    state = GameState(board=board, current_side=Side.RED)
    new_state = state.after_move(Move((1, 3), (0, 3)))
    assert new_state.winner is Side.RED


def test_win_by_elimination():
    board = _board_with({
        (2, 0): Piece(Side.RED, Rank.LION),
        (2, 1): Piece(Side.BLUE, Rank.RAT),
    })
    state = GameState(board=board, current_side=Side.RED)
    new_state = state.after_move(Move((2, 0), (2, 1)))
    assert new_state.winner is Side.RED


def test_game_already_over_raises():
    board = _board_with({(0, 3): Piece(Side.RED, Rank.RAT)})
    state = GameState(board=board, current_side=Side.RED, winner=Side.RED)
    with pytest.raises(IllegalMoveError):
        state.after_move(Move((0, 3), (0, 2)))
