"""Comprehensive rule tests for the Jungle board model."""

import pytest

from jungle.model.board import Board, GameState, IllegalMoveError, Move, Piece
from jungle.model.constants import Rank, Side, Terrain, terrain_at


def _board_with(pieces):
    rows = [[None for _ in range(7)] for _ in range(9)]
    for (row, col), piece in pieces.items():
        rows[row][col] = piece
    return Board(tuple(tuple(row) for row in rows))


def test_standard_rank_capture():
    board = _board_with({
        (2, 0): Piece(Side.RED, Rank.LION),
        (2, 1): Piece(Side.BLUE, Rank.DOG),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((2, 0), (2, 1)))


def test_equal_rank_capture():
    board = _board_with({
        (2, 0): Piece(Side.RED, Rank.LION),
        (2, 1): Piece(Side.BLUE, Rank.LION),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((2, 0), (2, 1)))


def test_weaker_cannot_capture_stronger():
    board = _board_with({
        (2, 0): Piece(Side.RED, Rank.DOG),
        (2, 1): Piece(Side.BLUE, Rank.LION),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((2, 0), (2, 1)))


def test_cannot_capture_own_piece():
    board = _board_with({
        (4, 3): Piece(Side.RED, Rank.LION),
        (4, 4): Piece(Side.RED, Rank.DOG),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((4, 3), (4, 4)))


def test_rat_captures_elephant_only_on_land():
    board = _board_with({
        (2, 0): Piece(Side.RED, Rank.RAT),
        (2, 1): Piece(Side.BLUE, Rank.ELEPHANT),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((2, 0), (2, 1)))


def test_rat_cannot_capture_elephant_from_water():
    board = _board_with({
        (3, 1): Piece(Side.RED, Rank.RAT),
        (3, 2): Piece(Side.BLUE, Rank.ELEPHANT),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((3, 1), (3, 2)))


def test_rat_moves_in_river():
    board = _board_with({(3, 1): Piece(Side.RED, Rank.RAT)})
    state = GameState(board=board, current_side=Side.RED)
    # Can move to adjacent river squares.
    assert state.is_legal_move(Move((3, 1), (3, 2)))
    assert state.is_legal_move(Move((3, 1), (4, 1)))


def test_rat_can_leave_river():
    board = _board_with({(3, 1): Piece(Side.RED, Rank.RAT)})
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((3, 1), (2, 1)))


def test_non_rat_cannot_enter_river():
    for rank in (Rank.CAT, Rank.DOG, Rank.WOLF, Rank.LEOPARD, Rank.TIGER, Rank.LION, Rank.ELEPHANT):
        board = _board_with({(2, 1): Piece(Side.RED, rank)})
        state = GameState(board=board, current_side=Side.RED)
        assert not state.is_legal_move(Move((2, 1), (3, 1))), f"{rank} should not enter river"


def test_lion_horizontal_jump_over_left_river():
    board = _board_with({(4, 0): Piece(Side.RED, Rank.LION)})
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((4, 0), (4, 3)))


def test_lion_horizontal_jump_over_right_river():
    board = _board_with({(4, 6): Piece(Side.RED, Rank.LION)})
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((4, 6), (4, 3)))


def test_tiger_horizontal_jump():
    board = _board_with({(4, 0): Piece(Side.RED, Rank.TIGER)})
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((4, 0), (4, 3)))


def test_tiger_vertical_jump_is_illegal():
    board = _board_with({(6, 1): Piece(Side.RED, Rank.TIGER)})
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((6, 1), (2, 1)))


def test_tiger_vertical_jump_up_is_illegal():
    board = _board_with({(2, 1): Piece(Side.RED, Rank.TIGER)})
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((2, 1), (6, 1)))


def test_tiger_horizontal_jump_blocked_by_rat():
    board = _board_with({
        (4, 0): Piece(Side.RED, Rank.TIGER),
        (4, 2): Piece(Side.BLUE, Rank.RAT),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((4, 0), (4, 3)))


def test_tiger_horizontal_jump_capture():
    board = _board_with({
        (4, 6): Piece(Side.RED, Rank.TIGER),
        (4, 3): Piece(Side.BLUE, Rank.WOLF),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((4, 6), (4, 3)))


def test_lion_vertical_jump():
    board = _board_with({(2, 1): Piece(Side.RED, Rank.LION)})
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((2, 1), (6, 1)))


def test_jump_blocked_by_friendly_rat():
    board = _board_with({
        (2, 1): Piece(Side.RED, Rank.LION),
        (4, 1): Piece(Side.RED, Rank.RAT),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((2, 1), (6, 1)))


def test_jump_blocked_by_enemy_rat():
    board = _board_with({
        (2, 1): Piece(Side.RED, Rank.LION),
        (4, 1): Piece(Side.BLUE, Rank.RAT),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((2, 1), (6, 1)))


def test_jump_captures_on_landing():
    board = _board_with({
        (2, 1): Piece(Side.RED, Rank.LION),
        (6, 1): Piece(Side.BLUE, Rank.DOG),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((2, 1), (6, 1)))


def test_jump_cannot_land_on_stronger_piece():
    board = _board_with({
        (2, 1): Piece(Side.RED, Rank.LION),
        (6, 1): Piece(Side.BLUE, Rank.ELEPHANT),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((2, 1), (6, 1)))


def test_trap_reduces_defender_rank():
    board = _board_with({
        (7, 3): Piece(Side.BLUE, Rank.ELEPHANT),
        (8, 3): Piece(Side.RED, Rank.RAT),
    })
    # Blue elephant is in red trap at (7,3). Red rat at (8,3) adjacent.
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((8, 3), (7, 3)))


def test_trapped_piece_can_attack_out():
    board = _board_with({
        (7, 3): Piece(Side.BLUE, Rank.RAT),
        (7, 2): Piece(Side.RED, Rank.ELEPHANT),
    })
    # Blue rat is in red trap at (7,3); the red elephant is also in a red trap
    # at (7,2), so its defensive rank is 0 and the rat can capture it.
    state = GameState(board=board, current_side=Side.BLUE)
    assert state.is_legal_move(Move((7, 3), (7, 2)))


def test_own_trap_does_not_reduce_rank():
    board = _board_with({
        (0, 2): Piece(Side.BLUE, Rank.ELEPHANT),
        (0, 1): Piece(Side.RED, Rank.LION),
    })
    # Blue elephant is in own trap; red lion (7) still cannot capture it (8).
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((0, 1), (0, 2)))


def test_rat_captures_elephant_in_own_trap():
    # The rat's special capture of the elephant ignores rank; an own-trap
    # square gives the elephant no extra protection.
    board = _board_with({
        (0, 2): Piece(Side.BLUE, Rank.ELEPHANT),
        (0, 1): Piece(Side.RED, Rank.RAT),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((0, 1), (0, 2)))


def test_cannot_move_into_own_den():
    board = _board_with({(8, 3): Piece(Side.RED, Rank.RAT)})
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((8, 3), (8, 3)))


def test_moving_into_opponent_den_wins():
    board = _board_with({(1, 3): Piece(Side.RED, Rank.RAT)})
    state = GameState(board=board, current_side=Side.RED)
    new_state = state.after_move(Move((1, 3), (0, 3)))
    assert new_state.winner is Side.RED


def test_win_by_eliminating_all_enemy_pieces():
    board = _board_with({
        (2, 0): Piece(Side.RED, Rank.LION),
        (2, 1): Piece(Side.BLUE, Rank.RAT),
    })
    state = GameState(board=board, current_side=Side.RED)
    new_state = state.after_move(Move((2, 0), (2, 1)))
    assert new_state.winner is Side.RED


def test_stalemate_no_legal_moves():
    # Red rat is boxed in by stronger enemy pieces; no other red pieces exist.
    board = _board_with({
        (0, 0): Piece(Side.RED, Rank.RAT),
        (0, 1): Piece(Side.BLUE, Rank.CAT),
        (1, 0): Piece(Side.BLUE, Rank.DOG),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert state.legal_moves() == []


def test_after_move_switches_side():
    state = GameState(board=Board.starting(), current_side=Side.RED)
    move = Move((8, 0), (7, 0))
    new_state = state.after_move(move)
    assert new_state.current_side is Side.BLUE


def test_illegal_move_raises():
    state = GameState(board=Board.starting(), current_side=Side.RED)
    with pytest.raises(IllegalMoveError):
        state.after_move(Move((8, 0), (8, 0)))


def test_moving_after_game_over_raises():
    board = _board_with({(0, 3): Piece(Side.RED, Rank.RAT)})
    state = GameState(board=board, current_side=Side.RED, winner=Side.RED)
    with pytest.raises(IllegalMoveError):
        state.after_move(Move((0, 3), (0, 2)))


def test_board_empty_has_no_pieces():
    board = Board.empty()
    for pos in board.positions():
        assert board.piece_at(pos) is None


def test_board_invalid_dimensions_raise():
    with pytest.raises(ValueError):
        Board(((None, None), (None, None)))


def test_rat_in_water_cannot_capture_elephant_on_land():
    board = _board_with({
        (3, 1): Piece(Side.RED, Rank.RAT),
        (2, 1): Piece(Side.BLUE, Rank.ELEPHANT),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((3, 1), (2, 1)))


def test_rat_in_water_cannot_capture_rat_on_land():
    board = _board_with({
        (3, 1): Piece(Side.RED, Rank.RAT),
        (2, 1): Piece(Side.BLUE, Rank.RAT),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((3, 1), (2, 1)))


def test_rat_on_land_cannot_capture_rat_in_water():
    board = _board_with({
        (2, 1): Piece(Side.RED, Rank.RAT),
        (3, 1): Piece(Side.BLUE, Rank.RAT),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((2, 1), (3, 1)))


def test_rat_in_water_captures_rat_in_water():
    board = _board_with({
        (3, 1): Piece(Side.RED, Rank.RAT),
        (3, 2): Piece(Side.BLUE, Rank.RAT),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((3, 1), (3, 2)))


def test_rat_on_land_captures_rat_on_land():
    board = _board_with({
        (2, 1): Piece(Side.RED, Rank.RAT),
        (2, 2): Piece(Side.BLUE, Rank.RAT),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((2, 1), (2, 2)))


def test_wolf_outranks_dog():
    # Wikipedia ranking: dog 3, wolf 4.
    board = _board_with({
        (2, 0): Piece(Side.RED, Rank.WOLF),
        (2, 1): Piece(Side.BLUE, Rank.DOG),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert state.is_legal_move(Move((2, 0), (2, 1)))


def test_dog_cannot_capture_wolf():
    board = _board_with({
        (2, 0): Piece(Side.RED, Rank.DOG),
        (2, 1): Piece(Side.BLUE, Rank.WOLF),
    })
    state = GameState(board=board, current_side=Side.RED)
    assert not state.is_legal_move(Move((2, 0), (2, 1)))
