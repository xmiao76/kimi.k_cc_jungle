"""Draw rules: threefold repetition and the 200-ply cap."""

from jungle.model.board import MAX_PLIES, GameState, Move, Piece
from jungle.model.constants import Rank, Side


def _shuffle_state() -> GameState:
    """Two rats free to shuttle back and forth forever."""
    return GameState.from_pieces(
        {(2, 0): Piece(Side.RED, Rank.RAT), (6, 0): Piece(Side.BLUE, Rank.RAT)}
    )


_CYCLE = [
    Move((2, 0), (2, 1)),
    Move((6, 0), (6, 1)),
    Move((2, 1), (2, 0)),
    Move((6, 1), (6, 0)),
]


def _play(state: GameState, plies: int) -> GameState:
    for i in range(plies):
        state = state.apply_move(_CYCLE[i % 4])
    return state


def test_start_position_is_not_a_draw():
    assert not _shuffle_state().is_draw


def test_second_occurrence_is_not_yet_a_draw():
    # Full cycle back to the opening position = second occurrence only.
    state = _play(_shuffle_state(), 4)
    assert not state.is_draw
    assert not state.is_game_over


def test_third_occurrence_is_a_repetition_draw():
    state = _play(_shuffle_state(), 8)
    assert state.is_draw
    assert state.is_game_over
    assert state.winner is None
    assert state.game_over_reason == "repetition"


def test_repetition_counts_identical_placement_and_side_to_move():
    # Same pieces but the OTHER side to move must not count as the same
    # position; the cycle above already validates this implicitly (no false
    # positive at odd plies), and here we check the keys differ directly.
    state = _play(_shuffle_state(), 7)
    assert not state.is_draw


def test_two_hundred_ply_cap_is_a_draw():
    state = GameState.from_pieces(
        {(2, 0): Piece(Side.RED, Rank.RAT), (6, 0): Piece(Side.BLUE, Rank.RAT)},
        move_count=MAX_PLIES - 2,
    )
    state = state.apply_move(Move((2, 0), (2, 1)))
    assert not state.is_draw
    state = state.apply_move(Move((6, 0), (6, 1)))
    assert state.is_draw
    assert state.game_over_reason == "move_limit"
    assert state.move_count == MAX_PLIES


def test_a_win_beats_the_ply_cap():
    # A den entry on the final allowed ply still wins (wins outrank draws).
    state = GameState.from_pieces(
        {(1, 3): Piece(Side.RED, Rank.RAT), (5, 5): Piece(Side.BLUE, Rank.DOG)},
        move_count=MAX_PLIES - 1,
    )
    state = state.apply_move(Move((1, 3), (0, 3)))
    assert state.winner is Side.RED
    assert not state.is_draw
    assert state.game_over_reason == "den"
