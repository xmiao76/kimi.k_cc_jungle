"""The complete Jungle ruleset, tested rule family by rule family."""

import pytest

from jungle.model.board import GameState, Move, Piece
from jungle.model.constants import Rank, Side

R = Side.RED
B = Side.BLUE

_DUMMY_SQUARES = [(0, 0), (0, 6), (8, 0), (8, 6), (2, 3), (6, 3)]


def state(pieces: dict, side: Side = R) -> GameState:
    """Custom-position state. A lone army would already have lost by
    elimination, so a harmless dummy enemy cat is added on a free square
    whenever one side is missing."""
    pieces = dict(pieces)
    for missing in (B, R):
        if not any(p.side is missing for p in pieces.values()):
            for square in _DUMMY_SQUARES:
                if square not in pieces:
                    pieces[square] = Piece(missing, Rank.CAT)
                    break
    return GameState.from_pieces(pieces, current_side=side)


def destinations(game: GameState, pos) -> set:
    return {m.to_pos for m in game.legal_moves() if m.from_pos == pos}


# -- basic movement ---------------------------------------------------------


def test_pieces_move_one_step_orthogonally():
    game = state({(2, 3): Piece(R, Rank.WOLF)})
    assert destinations(game, (2, 3)) == {(1, 3), (3, 3), (2, 2), (2, 4)}


def test_pieces_do_not_move_diagonally():
    game = state({(2, 3): Piece(R, Rank.WOLF)})
    for diagonal in ((1, 2), (1, 4), (3, 2), (3, 4)):
        assert diagonal not in destinations(game, (2, 3))


def test_board_edges_limit_movement():
    game = state({(0, 0): Piece(R, Rank.CAT)})
    assert destinations(game, (0, 0)) == {(1, 0), (0, 1)}


def test_own_pieces_block_movement():
    game = state({(2, 3): Piece(R, Rank.WOLF), (2, 4): Piece(R, Rank.DOG)})
    assert (2, 4) not in destinations(game, (2, 3))


# -- ordinary captures -------------------------------------------------------


def test_capture_equal_or_lower_rank():
    game = state({
        (2, 3): Piece(R, Rank.LION),
        (2, 4): Piece(B, Rank.TIGER),
        (2, 2): Piece(B, Rank.LION),
    })
    dests = destinations(game, (2, 3))
    assert (2, 4) in dests  # lion takes tiger
    assert (2, 2) in dests  # lion takes lion (equal rank)


def test_cannot_capture_higher_rank():
    game = state({(2, 3): Piece(R, Rank.TIGER), (2, 4): Piece(B, Rank.LION)})
    assert (2, 4) not in destinations(game, (2, 3))


# -- river -------------------------------------------------------------------


def test_only_rat_enters_river():
    game = state({(3, 0): Piece(R, Rank.DOG), (6, 0): Piece(R, Rank.RAT)})
    assert (3, 1) not in destinations(game, (3, 0))  # dog barred from river
    assert (6, 1) in destinations(game, (6, 0))  # rat enters from land


def test_rat_swims_within_river_and_exits_to_land():
    game = state({(4, 2): Piece(R, Rank.RAT)})
    dests = destinations(game, (4, 2))
    assert (4, 1) in dests and (5, 2) in dests  # river-to-river
    assert (4, 3) in dests  # exit to land


def test_river_rat_cannot_capture_land_piece():
    game = state({(3, 1): Piece(B, Rank.RAT), (3, 0): Piece(R, Rank.ELEPHANT)}, side=B)
    assert (3, 0) not in destinations(game, (3, 1))


def test_land_piece_cannot_capture_river_rat():
    # A land rat may not take a swimming rat either (no land<->river capture).
    game = state({(3, 0): Piece(R, Rank.RAT), (3, 1): Piece(B, Rank.RAT)})
    assert (3, 1) not in destinations(game, (3, 0))


def test_river_rat_captures_river_rat():
    game = state({(4, 1): Piece(R, Rank.RAT), (4, 2): Piece(B, Rank.RAT)})
    assert (4, 2) in destinations(game, (4, 1))


# -- rat <-> elephant ---------------------------------------------------------


def test_rat_captures_elephant_from_land():
    game = state({(2, 3): Piece(R, Rank.RAT), (2, 4): Piece(B, Rank.ELEPHANT)})
    assert (2, 4) in destinations(game, (2, 3))


def test_elephant_cannot_capture_rat():
    game = state({(2, 3): Piece(R, Rank.ELEPHANT), (2, 4): Piece(B, Rank.RAT)})
    assert (2, 4) not in destinations(game, (2, 3))


def test_elephant_cannot_capture_rat_even_in_trap():
    # The elephant/rat restriction overrides the trap's rank-0 defense.
    game = state({(7, 2): Piece(R, Rank.ELEPHANT), (7, 3): Piece(B, Rank.RAT)})
    assert (7, 3) not in destinations(game, (7, 2))


# -- lion and tiger river jumps ----------------------------------------------


def test_lion_jumps_horizontally_both_ways():
    game = state({(3, 3): Piece(R, Rank.LION)})
    dests = destinations(game, (3, 3))
    assert (3, 0) in dests and (3, 6) in dests
    # Steps into the river itself are still forbidden.
    assert (3, 2) not in dests and (3, 4) not in dests


def test_lion_jumps_vertically():
    game = state({(6, 1): Piece(R, Rank.LION)})
    assert (2, 1) in destinations(game, (6, 1))
    game_blue = state({(2, 5): Piece(B, Rank.LION)}, side=B)
    assert (6, 5) in destinations(game_blue, (2, 5))


def test_tiger_jumps_horizontally_only():
    game = state({(3, 3): Piece(R, Rank.TIGER)})
    dests = destinations(game, (3, 3))
    assert (3, 0) in dests and (3, 6) in dests


def test_tiger_must_not_jump_vertically():
    # Locked variant: the tiger is barred from the 3-cell vertical jump.
    game = state({(6, 1): Piece(R, Rank.TIGER)})
    assert (2, 1) not in destinations(game, (6, 1))
    game_blue = state({(2, 4): Piece(B, Rank.TIGER)}, side=B)
    assert (6, 4) not in destinations(game_blue, (2, 4))


def test_any_rat_blocks_jumps_either_side():
    # Enemy rat in the river blocks the lion's vertical jump.
    game = state({(6, 1): Piece(R, Rank.LION), (4, 1): Piece(B, Rank.RAT)})
    assert (2, 1) not in destinations(game, (6, 1))
    # Friendly rat blocks it too.
    game = state({(6, 1): Piece(R, Rank.LION), (5, 1): Piece(R, Rank.RAT)})
    assert (2, 1) not in destinations(game, (6, 1))
    # And a river rat blocks the horizontal jump.
    game = state({(3, 0): Piece(R, Rank.LION), (3, 2): Piece(B, Rank.RAT)})
    assert (3, 3) not in destinations(game, (3, 0))


def test_jump_may_capture_on_landing():
    game = state({(3, 3): Piece(R, Rank.LION), (3, 6): Piece(B, Rank.DOG)})
    assert (3, 6) in destinations(game, (3, 3))


def test_jump_cannot_capture_higher_rank_on_landing():
    game = state({(3, 3): Piece(R, Rank.LION), (3, 0): Piece(B, Rank.ELEPHANT)})
    assert (3, 0) not in destinations(game, (3, 3))


def test_jump_landing_on_own_piece_is_blocked():
    game = state({(3, 3): Piece(R, Rank.TIGER), (3, 0): Piece(R, Rank.CAT)})
    assert (3, 0) not in destinations(game, (3, 3))


# -- traps -------------------------------------------------------------------


def test_piece_in_opponent_trap_defends_with_rank_zero():
    # A blue lion standing in a red trap can be taken even by the rat.
    game = state({(7, 3): Piece(B, Rank.LION), (7, 2): Piece(R, Rank.RAT)})
    assert (7, 3) in destinations(game, (7, 2))


def test_piece_in_opponent_trap_still_attacks_with_normal_rank():
    game = state({(7, 3): Piece(B, Rank.LION), (7, 2): Piece(R, Rank.TIGER)}, side=B)
    assert (7, 2) in destinations(game, (7, 3))


def test_piece_in_own_trap_defends_normally():
    # Red lion in red's own trap is NOT weakened; the blue rat cannot take it.
    game = state({(7, 3): Piece(R, Rank.LION), (7, 2): Piece(B, Rank.RAT)}, side=B)
    assert (7, 3) not in destinations(game, (7, 2))


# -- dens and winning ----------------------------------------------------------


def test_cannot_enter_own_den():
    game = state({(8, 2): Piece(R, Rank.RAT), (7, 3): Piece(R, Rank.DOG)})
    assert (8, 3) not in destinations(game, (8, 2))
    assert (8, 3) not in destinations(game, (7, 3))


def test_entering_opponent_den_wins():
    game = state({(1, 3): Piece(R, Rank.RAT), (5, 5): Piece(B, Rank.DOG)})
    assert (0, 3) in destinations(game, (1, 3))
    new_game = game.apply_move(Move((1, 3), (0, 3)))
    assert new_game.winner is R
    assert new_game.game_over_reason == "den"
    assert new_game.is_game_over


def test_capturing_all_enemy_pieces_wins():
    game = state({(2, 3): Piece(R, Rank.DOG), (2, 4): Piece(B, Rank.CAT)})
    new_game = game.apply_move(Move((2, 3), (2, 4)))
    assert new_game.winner is R
    assert new_game.game_over_reason == "elimination"


def test_side_with_no_legal_moves_loses():
    # Blue rat is cornered by the red lion and tiger and has no moves.
    game = state(
        {
            (0, 0): Piece(B, Rank.RAT),
            (1, 0): Piece(R, Rank.LION),
            (0, 1): Piece(R, Rank.TIGER),
        },
        side=B,
    )
    assert game.winner is R
    assert game.game_over_reason == "no_moves"
    assert game.legal_moves() == ()


def test_no_moves_loss_after_applied_move():
    game = state(
        {
            (0, 0): Piece(B, Rank.RAT),
            (1, 0): Piece(R, Rank.LION),
            (0, 1): Piece(R, Rank.TIGER),
            (5, 5): Piece(R, Rank.DOG),
        }
    )
    new_game = game.apply_move(Move((5, 5), (5, 6)))
    assert new_game.winner is R
    assert new_game.game_over_reason == "no_moves"


def test_game_not_over_at_start(initial_state):
    assert initial_state.winner is None
    assert not initial_state.is_draw
    assert not initial_state.is_game_over
    assert initial_state.game_over_reason is None
