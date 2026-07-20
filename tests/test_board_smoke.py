"""Immutability, integrity, and consistency of Board and GameState."""

import random

import pytest

from jungle.model.board import Board, GameState, IllegalMoveError, Move, Piece
from jungle.model.constants import Rank, Side


def test_apply_move_returns_new_state_and_leaves_original_untouched(initial_state):
    move = initial_state.legal_moves()[0]
    new_state = initial_state.apply_move(move)
    assert new_state is not initial_state
    assert initial_state.move_count == 0
    assert initial_state.current_side is Side.RED
    assert new_state.move_count == 1
    assert new_state.current_side is Side.BLUE


def test_with_piece_moved_clears_origin_and_sets_destination():
    board = Board.from_pieces({(2, 3): Piece(Side.RED, Rank.WOLF), (2, 4): Piece(Side.BLUE, Rank.CAT)})
    moved = board.with_piece_moved((2, 3), (2, 4))
    assert moved.piece_at((2, 3)) is None
    assert moved.piece_at((2, 4)) == Piece(Side.RED, Rank.WOLF)
    # Original board unchanged (immutability).
    assert board.piece_at((2, 3)) == Piece(Side.RED, Rank.WOLF)
    assert board.piece_at((2, 4)) == Piece(Side.BLUE, Rank.CAT)


def test_with_piece_moved_requires_a_piece():
    with pytest.raises(IllegalMoveError):
        Board.empty().with_piece_moved((2, 3), (2, 4))


def test_rotate_180_twice_is_identity():
    board = Board.starting()
    assert board.rotate_180().rotate_180() == board


def test_is_legal_move_matches_legal_moves(initial_state):
    legal = set(initial_state.legal_moves())
    assert legal  # sanity: the start position has moves
    for move in legal:
        assert initial_state.is_legal_move(move)
    assert not initial_state.is_legal_move(Move((0, 0), (4, 4)))
    assert not initial_state.is_legal_move(Move((0, 0), (0, 1)))  # blue's piece


def test_apply_move_rejects_illegal_moves(initial_state):
    with pytest.raises(IllegalMoveError):
        initial_state.apply_move(Move((0, 0), (0, 1)))  # not RED's piece
    with pytest.raises(IllegalMoveError):
        initial_state.apply_move(Move((6, 0), (6, 0)))  # no-op move


def test_apply_move_rejects_moves_after_game_over():
    game = GameState.from_pieces({(2, 3): Piece(Side.RED, Rank.DOG), (2, 4): Piece(Side.BLUE, Rank.CAT)})
    over = game.apply_move(Move((2, 3), (2, 4)))  # captures the last blue piece
    assert over.is_game_over
    assert over.legal_moves() == ()
    with pytest.raises(IllegalMoveError):
        over.apply_move(Move((2, 4), (2, 3)))


def test_position_key_is_deterministic_and_side_dependent():
    a = GameState.starting()
    b = GameState.starting()
    assert a.position_key == b.position_key
    same_board_blue_to_move = GameState(a.board, Side.BLUE, 0, ())
    assert same_board_blue_to_move.position_key != a.position_key


def test_history_tracks_every_position(initial_state):
    state = initial_state
    moves_played = 0
    for _ in range(4):
        move = state.legal_moves()[0]
        state = state.apply_move(move)
        moves_played += 1
    assert len(state.history) == 1 + moves_played
    assert state.history[-1] == state.position_key


def test_legal_move_generation_is_deterministic(initial_state):
    assert initial_state.legal_moves() == initial_state.legal_moves()


def test_random_games_keep_invariants():
    """Seeded random playouts: piece counts never rise, history grows by one
    key per ply, and the game always terminates within the ply cap."""
    rng = random.Random(1234)
    for _ in range(10):
        state = GameState.starting()
        plies = 0
        while not state.is_game_over:
            moves = state.legal_moves()
            assert moves, "non-terminal state must have legal moves"
            before = sum(1 for _ in state.board.positions())
            state = state.apply_move(rng.choice(moves))
            after = sum(1 for _ in state.board.positions())
            assert after <= before
            assert len(state.history) == state.move_count + 1
            plies += 1
            assert plies <= 200, "game exceeded the ply cap without terminating"
