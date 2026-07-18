"""Differential tests: the fast engine core must mirror the model exactly."""

import random

from jungle.engine.core import FastPosition, move_from, move_to, pack_move
from jungle.model.board import Board, GameState, Move, Piece
from jungle.model.constants import COLS, Rank, Side
from jungle.model.zobrist import position_key


def _board_with(pieces):
    rows = [[None for _ in range(7)] for _ in range(9)]
    for (row, col), piece in pieces.items():
        rows[row][col] = piece
    return Board(tuple(tuple(row) for row in rows))


def _fast_move_set(fast: FastPosition) -> set[tuple[int, int]]:
    result = set()
    for m in fast.legal_moves():
        f, t = move_from(m), move_to(m)
        result.add(((f // COLS, f % COLS), (t // COLS, t % COLS)))
    return result


def _assert_in_sync(state: GameState, fast: FastPosition) -> None:
    model_moves = {(m.from_pos, m.to_pos) for m in state.legal_moves()}
    assert _fast_move_set(fast) == model_moves
    assert fast.side is state.current_side
    assert fast.key == position_key(state.board, state.current_side)
    assert fast.has_legal_move() == bool(model_moves)
    over, winner, draw = fast.is_terminal()
    assert over == (state.winner is not None or state.draw)
    assert winner == state.winner
    assert draw == state.draw


def test_directed_positions_match():
    boards = [
        # Lion/tiger jumps with rats in and around the river.
        _board_with({
            (2, 1): Piece(Side.RED, Rank.LION),
            (4, 1): Piece(Side.BLUE, Rank.RAT),
            (6, 1): Piece(Side.BLUE, Rank.DOG),
            (4, 0): Piece(Side.BLUE, Rank.TIGER),
        }),
        # Traps: defender rank 0; rat/elephant specials across media.
        _board_with({
            (7, 3): Piece(Side.BLUE, Rank.ELEPHANT),
            (8, 3): Piece(Side.RED, Rank.RAT),
            (3, 1): Piece(Side.RED, Rank.RAT),
            (3, 5): Piece(Side.BLUE, Rank.RAT),
        }),
        # Den adjacency and near-endgame race.
        _board_with({
            (1, 3): Piece(Side.RED, Rank.LEOPARD),
            (0, 2): Piece(Side.BLUE, Rank.DOG),
            (8, 3): Piece(Side.RED, Rank.LION),
        }),
        Board.starting(),
    ]
    for board in boards:
        for side in (Side.RED, Side.BLUE):
            state = GameState(board=board, current_side=side)
            fast = FastPosition.from_game_state(state)
            _assert_in_sync(state, fast)


def test_random_playouts_match_model():
    for seed in range(50):
        rng = random.Random(seed)
        state = GameState(board=Board.starting(), current_side=Side.RED)
        fast = FastPosition.from_game_state(state)
        for _ in range(120):
            _assert_in_sync(state, fast)
            model_moves = sorted(
                {(m.from_pos, m.to_pos) for m in state.legal_moves()}
            )
            if not model_moves:
                break
            from_pos, to_pos = rng.choice(model_moves)
            state = state.after_move(Move(from_pos, to_pos))
            fast.make(pack_move(from_pos[0] * COLS + from_pos[1], to_pos[0] * COLS + to_pos[1]))
            if state.winner is not None or state.draw:
                _assert_in_sync(state, fast)
                break


def test_make_undo_roundtrip():
    rng = random.Random(99)
    state = GameState(board=Board.starting(), current_side=Side.RED)
    fast = FastPosition.from_game_state(state)
    snapshot = (list(fast.cells), fast.side, fast.key, fast.move_count, list(fast.keys))
    made: list[int] = []
    for _ in range(40):
        moves = fast.legal_moves()
        if not moves or fast.is_terminal()[0]:
            break
        move = rng.choice(moves)
        fast.make(move)
        made.append(move)
    for _ in made:
        fast.undo()
    assert fast.cells == snapshot[0]
    assert fast.side == snapshot[1]
    assert fast.key == snapshot[2]
    assert fast.move_count == snapshot[3]
    assert fast.keys == snapshot[4]
