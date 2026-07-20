"""Rule interactions and awkward corners of the ruleset."""

from jungle.model.board import Board, GameState, Move, Piece, piece_moves
from jungle.model.constants import Rank, Side

R = Side.RED
B = Side.BLUE

_DUMMY_SQUARES = [(0, 0), (0, 6), (8, 0), (8, 6), (2, 3), (6, 3)]


def state(pieces: dict, side: Side = R) -> GameState:
    """Custom-position state with a dummy enemy cat added when one side is
    absent (a lone army would already have lost by elimination)."""
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


def test_rat_in_opponent_trap_can_still_take_elephant():
    # The rat/elephant rule outranks the trap penalty on the attacker.
    game = state({(7, 3): Piece(B, Rank.RAT), (7, 2): Piece(R, Rank.ELEPHANT)}, side=B)
    assert (7, 2) in destinations(game, (7, 3))


def test_rat_swims_full_river_crossing():
    # Board-level checks so the alternating-turn machinery stays out of it.
    path = [(3, 1), (3, 2), (4, 2), (4, 1), (5, 1), (5, 2)]
    for current, nxt in zip(path, path[1:]):
        board = Board.from_pieces({current: Piece(R, Rank.RAT)})
        dests = {m.to_pos for m in piece_moves(board, current)}
        assert nxt in dests, f"rat at {current} should swim to {nxt}"


def test_lion_has_no_diagonal_jump():
    game = state({(3, 3): Piece(R, Rank.LION)})
    for bad in ((2, 1), (2, 5), (4, 1), (4, 5), (1, 3), (5, 3)):
        assert bad not in destinations(game, (3, 3))


def test_jump_over_empty_river_is_always_available():
    # With no rats on the board, every geometric jump must be present.
    for rank in (Rank.LION, Rank.TIGER):
        game = state({(5, 6): Piece(R, rank)})
        assert (5, 3) in destinations(game, (5, 6))
    lion = state({(2, 2): Piece(B, Rank.LION)}, side=B)
    assert (6, 2) in destinations(lion, (2, 2))


def test_trapped_piece_can_move_out_and_recover():
    game = GameState.from_pieces(
        {(7, 3): Piece(B, Rank.LION), (2, 6): Piece(R, Rank.RAT)}, current_side=B
    )
    state = game.apply_move(Move((7, 3), (6, 3)))
    assert state.board.piece_at((6, 3)) == Piece(B, Rank.LION)


def test_capture_removes_exactly_one_piece(initial_state):
    dog_game = GameState.from_pieces(
        {(2, 3): Piece(R, Rank.DOG), (2, 4): Piece(B, Rank.CAT), (8, 0): Piece(B, Rank.LION)}
    )
    before = sum(1 for _ in dog_game.board.positions())
    state = dog_game.apply_move(Move((2, 3), (2, 4)))
    after = sum(1 for _ in state.board.positions())
    assert before - after == 1


def test_lone_army_loses_by_elimination_not_crash():
    # Degenerate but must not raise; with no red pieces the game is over.
    game = GameState.from_pieces({(2, 2): Piece(B, Rank.CAT)}, current_side=R)
    assert game.winner is B
    assert game.game_over_reason == "elimination"
