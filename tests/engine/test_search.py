"""Tactical and behavioral tests for the search and evaluation."""

import threading
import time

from jungle.engine.ai import AI
from jungle.engine.core import FastPosition, pack_move
from jungle.engine.evaluation import evaluate, evaluate_fast
from jungle.engine.search import INF, SearchConfig, Searcher
from jungle.model.board import Board, GameState, Move, Piece
from jungle.model.constants import COLS, Rank, Side


def _board_with(pieces):
    rows = [[None for _ in range(7)] for _ in range(9)]
    for (row, col), piece in pieces.items():
        rows[row][col] = piece
    return Board(tuple(tuple(row) for row in rows))


def _state(pieces, side=Side.RED):
    return GameState(board=_board_with(pieces), current_side=side)


def _fast_search(state: GameState, depth: int, time_s: float = 30.0):
    ai = AI(side=state.current_side, depth=depth, time_limit_s=time_s)
    return ai.choose_move(state)


def test_mate_in_one_den_entry():
    state = _state({
        (1, 3): Piece(Side.RED, Rank.RAT),
        (2, 6): Piece(Side.BLUE, Rank.ELEPHANT),
    })
    move = _fast_search(state, depth=3)
    assert move == Move((1, 3), (0, 3))


def test_mate_in_two_forced_den_push():
    # Lion pushes to the trap square in front of the den; the cat cannot
    # stop the den entry on the following move.
    state = _state({
        (2, 3): Piece(Side.RED, Rank.LION),
        (0, 2): Piece(Side.BLUE, Rank.CAT),
    })
    move = _fast_search(state, depth=5)
    assert move == Move((2, 3), (1, 3))


def test_engine_exploits_trapped_elephant():
    state = _state({
        (7, 2): Piece(Side.RED, Rank.RAT),
        (7, 3): Piece(Side.BLUE, Rank.ELEPHANT),  # sitting in RED's trap
        (0, 0): Piece(Side.BLUE, Rank.LION),
    })
    move = _fast_search(state, depth=3)
    assert move == Move((7, 2), (7, 3))


def test_engine_respects_rat_jump_block():
    # The lion's jump capture of the dog is blocked by the rat in the river;
    # the engine must take the adjacent cat instead.
    state = _state({
        (2, 1): Piece(Side.RED, Rank.LION),
        (6, 1): Piece(Side.BLUE, Rank.DOG),
        (4, 1): Piece(Side.BLUE, Rank.RAT),
        (2, 2): Piece(Side.BLUE, Rank.CAT),
    })
    move = _fast_search(state, depth=3)
    assert move == Move((2, 1), (2, 2))


def test_search_aborts_promptly():
    state = GameState(board=Board.starting(), current_side=Side.RED)
    pos = FastPosition.from_game_state(state)
    abort = threading.Event()
    searcher = Searcher(
        SearchConfig(max_depth=64, soft_limit_s=60.0, hard_limit_s=120.0),
        abort_event=abort,
    )
    timer = threading.Timer(0.05, abort.set)
    timer.start()
    start = time.perf_counter()
    result = searcher.search(pos)
    elapsed = time.perf_counter() - start
    timer.cancel()
    assert elapsed < 1.0
    legal = {(m.from_pos, m.to_pos) for m in state.legal_moves()}
    from jungle.engine.core import to_model_move
    move = to_model_move(result.best_move)
    assert (move.from_pos, move.to_pos) in legal


def test_search_deterministic_at_fixed_depth():
    state = GameState(board=Board.starting(), current_side=Side.RED)
    first = _fast_search(state, depth=5, time_s=60.0)
    second = _fast_search(state, depth=5, time_s=60.0)
    assert first == second


def test_repetition_scores_as_draw():
    # A position already seen on the path must score 0 (draw) in the tree.
    state = GameState(board=Board.starting(), current_side=Side.RED)
    pos = FastPosition.from_game_state(state)
    pos.keys.append(pos.key)  # pretend the root position occurred before
    searcher = Searcher(SearchConfig(max_depth=4, soft_limit_s=10, hard_limit_s=20))
    assert searcher._pvs(pos, 2, -INF, INF, 1) == 0


def test_tt_consistency():
    state = GameState(board=Board.starting(), current_side=Side.RED)
    pos = FastPosition.from_game_state(state)
    with_tt = Searcher(SearchConfig(max_depth=3, soft_limit_s=30, hard_limit_s=60)).search(pos)
    pos2 = FastPosition.from_game_state(state)
    without_tt = Searcher(
        SearchConfig(max_depth=3, soft_limit_s=30, hard_limit_s=60, use_tt=False)
    ).search(pos2)
    assert with_tt.score == without_tt.score
    assert with_tt.best_move == without_tt.best_move


def test_eval_sign_convention():
    with_lion = _state({
        (4, 0): Piece(Side.RED, Rank.LION),
        (2, 6): Piece(Side.BLUE, Rank.ELEPHANT),
    })
    without_lion = _state({(2, 6): Piece(Side.BLUE, Rank.ELEPHANT)})
    assert evaluate(without_lion, Side.BLUE) > evaluate(with_lion, Side.BLUE)


def test_eval_symmetry_under_rotation():
    state = GameState(board=Board.starting(), current_side=Side.RED)
    rotated = GameState(
        board=state.board.rotate_180(), current_side=Side.BLUE
    )
    score_red = evaluate_fast(FastPosition.from_game_state(state))
    score_blue = evaluate_fast(FastPosition.from_game_state(rotated))
    assert score_red == -score_blue


def test_capture_rich_position_completes():
    # Both armies colliding in the center; quiescence must not blow up.
    state = _state({
        (4, 3): Piece(Side.RED, Rank.LION),
        (3, 3): Piece(Side.BLUE, Rank.TIGER),
        (5, 3): Piece(Side.BLUE, Rank.LEOPARD),
        (4, 0): Piece(Side.RED, Rank.ELEPHANT),
        (3, 1): Piece(Side.BLUE, Rank.RAT),
        (4, 6): Piece(Side.RED, Rank.WOLF),
        (5, 4): Piece(Side.BLUE, Rank.DOG),
        (6, 6): Piece(Side.RED, Rank.RAT),
    })
    move = _fast_search(state, depth=4)
    assert move is not None
    assert state.is_legal_move(move)


def test_mate_score_prefers_fast_win():
    # Mate-in-1 available; the returned score must be a mate score.
    state = _state({
        (1, 3): Piece(Side.RED, Rank.RAT),
        (2, 6): Piece(Side.BLUE, Rank.ELEPHANT),
    })
    pos = FastPosition.from_game_state(state)
    searcher = Searcher(SearchConfig(max_depth=3, soft_limit_s=30, hard_limit_s=60))
    result = searcher.search(pos)
    from jungle.engine.search import MATE_BOUND
    assert result.score >= MATE_BOUND


def test_persistent_tt_reused_across_moves():
    from jungle.engine.search import SearchConfig

    config = SearchConfig(max_depth=3, soft_limit_s=30.0, use_persistent_tt=True)
    ai = AI(side=Side.RED, config=config)
    state = GameState(board=Board.starting(), current_side=Side.RED)
    move = ai.choose_move(state)
    assert move is not None
    assert len(ai._tt) > 0
    generation = ai._tt_generation
    reply = state.after_move(move).legal_moves()[0]
    state3 = state.after_move(move).after_move(reply)
    assert ai.choose_move(state3) is not None
    assert ai._tt_generation == generation + 1


def test_aspiration_consistency():
    state = GameState(board=Board.starting(), current_side=Side.RED)
    base = dict(
        max_depth=5,
        soft_limit_s=60.0,
        hard_limit_s=120.0,
        use_lmr=False,
        use_see_pruning=False,
        use_persistent_tt=False,
    )
    with_asp = Searcher(SearchConfig(**base, use_aspiration=True)).search(
        FastPosition.from_game_state(state)
    )
    without = Searcher(SearchConfig(**base, use_aspiration=False)).search(
        FastPosition.from_game_state(state)
    )
    assert with_asp.best_move == without.best_move
    assert with_asp.score == without.score


def test_eval_trap_capture_threat():
    from jungle.engine.evaluation import DEFAULT_WEIGHTS, V2_WEIGHTS

    # Blue elephant trapped in RED's trap; red rat adjacent to claim it.
    state = _state({
        (7, 3): Piece(Side.BLUE, Rank.ELEPHANT),
        (7, 2): Piece(Side.RED, Rank.RAT),
        (0, 0): Piece(Side.BLUE, Rank.CAT),
    })
    pos = FastPosition.from_game_state(state)
    assert evaluate_fast(pos, DEFAULT_WEIGHTS) > evaluate_fast(pos, V2_WEIGHTS)


def test_eval_advanced_rat_bonus():
    from jungle.engine.evaluation import DEFAULT_WEIGHTS, V2_WEIGHTS

    state = _state({
        (2, 0): Piece(Side.RED, Rank.RAT),  # deep in the enemy half
        (0, 6): Piece(Side.BLUE, Rank.RAT),
    })
    pos = FastPosition.from_game_state(state)
    assert evaluate_fast(pos, DEFAULT_WEIGHTS) > evaluate_fast(pos, V2_WEIGHTS)
