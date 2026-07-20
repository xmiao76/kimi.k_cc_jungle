"""Search behavior: tactics, time management, determinism, TT discipline."""

import threading
import time

from jungle.engine.ai import AI
from jungle.engine.core import FastPosition, from_model_move, to_model_move
from jungle.engine.search import MATE, MAX_PLY, SearchConfig, Searcher
from jungle.model.board import GameState, Move, Piece
from jungle.model.constants import Rank, Side

R, B = Side.RED, Side.BLUE


def _config(depth: int = 3) -> SearchConfig:
    # Generous limits: every iteration completes, so results are deterministic.
    return SearchConfig(max_depth=depth, soft_limit_s=120.0, hard_limit_s=240.0)


def _search(state: GameState, depth: int = 3):
    return Searcher(_config(depth)).search(FastPosition.from_game_state(state))


def test_finds_den_entry_mate_in_one():
    # Red rat steps into the blue den next move; blue cannot prevent it.
    state = GameState.from_pieces(
        {
            (1, 3): Piece(R, Rank.RAT),
            (6, 0): Piece(R, Rank.LION),
            (2, 6): Piece(B, Rank.ELEPHANT),
            (7, 6): Piece(B, Rank.DOG),
        }
    )
    result = _search(state, depth=2)
    assert to_model_move(result.best_move) == Move((1, 3), (0, 3))
    assert result.score >= MATE - MAX_PLY


def test_prefers_winning_capture_over_quiet_moves():
    # The lion's jump capture of the undefended dog is clearly the best move.
    state = GameState.from_pieces(
        {
            (3, 3): Piece(R, Rank.LION),
            (3, 6): Piece(B, Rank.DOG),
            (6, 0): Piece(R, Rank.RAT),
            (0, 6): Piece(B, Rank.ELEPHANT),
        }
    )
    result = _search(state, depth=2)
    assert to_model_move(result.best_move) == Move((3, 3), (3, 6))


def test_search_is_deterministic_at_completed_depth():
    state = GameState.starting()
    first = _search(state, depth=3)
    second = _search(state, depth=3)
    assert first.depth == second.depth == 3
    assert first.best_move == second.best_move
    assert first.score == second.score


def test_hard_time_limit_is_respected():
    state = GameState.starting()
    pos = FastPosition.from_game_state(state)
    config = SearchConfig(max_depth=99, soft_limit_s=600.0, hard_limit_s=0.3)
    start = time.monotonic()
    result = Searcher(config).search(pos)
    elapsed = time.monotonic() - start
    assert elapsed < 2.0, f"search overran the hard limit ({elapsed:.2f}s)"
    assert result.depth >= 1
    assert result.best_move != 0


def test_abort_event_stops_search_promptly():
    state = GameState.starting()
    pos = FastPosition.from_game_state(state)
    abort = threading.Event()
    config = SearchConfig(max_depth=99, soft_limit_s=600.0, hard_limit_s=600.0)
    searcher = Searcher(config, abort_event=abort)
    outcome = {}

    def run():
        outcome["result"] = searcher.search(pos)

    thread = threading.Thread(target=run)
    start = time.monotonic()
    thread.start()
    time.sleep(0.1)
    abort.set()
    thread.join(timeout=5.0)
    elapsed = time.monotonic() - start
    assert not thread.is_alive(), "search ignored the abort event"
    assert elapsed < 3.0


def test_no_legal_moves_returns_mate_score():
    # Blue is cornered: any search sees the position as a loss for blue.
    state = GameState.from_pieces(
        {
            (0, 0): Piece(B, Rank.RAT),
            (1, 0): Piece(R, Rank.LION),
            (0, 1): Piece(R, Rank.TIGER),
        },
        current_side=B,
    )
    result = _search(state, depth=2)
    assert result.best_move == 0
    assert result.score == -MATE


def test_quiescence_stays_bounded_on_tactical_position():
    state = GameState.from_pieces(
        {
            (3, 3): Piece(R, Rank.LION),
            (3, 6): Piece(B, Rank.DOG),
            (2, 4): Piece(B, Rank.WOLF),
            (6, 3): Piece(R, Rank.TIGER),
            (6, 0): Piece(R, Rank.RAT),
            (0, 6): Piece(B, Rank.ELEPHANT),
            (1, 1): Piece(B, Rank.CAT),
        }
    )
    result = _search(state, depth=3)
    assert result.nodes < 500_000, f"quiescence exploded: {result.nodes} nodes"


# -- repetition awareness and TT discipline -----------------------------------


def _repetition_scenario():
    """RED is hopelessly behind but can shuttle the lion for an immediate
    threefold draw; alternatively it can capture a hanging dog (still lost).
    Returns (state_with_history, fresh_state, draw_move, capture_move)."""
    pieces = {
        (6, 3): Piece(R, Rank.LION),
        (6, 2): Piece(B, Rank.DOG),
        (6, 0): Piece(B, Rank.RAT),
        (0, 0): Piece(B, Rank.LION),
        (2, 6): Piece(B, Rank.ELEPHANT),
    }
    base = GameState.from_pieces(pieces, current_side=R)
    draw_move = Move((6, 3), (5, 3))
    capture_move = Move((6, 3), (6, 2))
    k0 = base.position_key
    k1 = base.apply_move(draw_move).position_key
    with_history = GameState(base.board, R, 0, (k1, k1, k0))
    return with_history, base, draw_move, capture_move


def test_repetition_draw_is_scored_zero():
    with_history, _, draw_move, _ = _repetition_scenario()
    # The model agrees the shuttle move draws...
    assert with_history.apply_move(draw_move).is_draw
    # ...and the engine prefers the draw over a losing capture.
    result = _search(with_history, depth=3)
    assert to_model_move(result.best_move) == draw_move
    assert result.score == 0


def test_same_board_with_fresh_history_ignores_phantom_draw():
    _, fresh, draw_move, capture_move = _repetition_scenario()
    result = _search(fresh, depth=3)
    assert to_model_move(result.best_move) == capture_move
    assert result.score != 0


def test_every_search_starts_with_an_empty_tt():
    # The repetition-poisoning regression guard: TT entries computed under one
    # repetition history must never leak into another search. Each Searcher
    # owns exactly one root search.
    with_history, fresh, _, capture_move = _repetition_scenario()
    searcher = Searcher(_config(3))
    assert searcher.tt == {}
    searcher.search(FastPosition.from_game_state(with_history))
    poisoned = Searcher(_config(3))
    assert poisoned.tt == {}  # fresh instance, fresh table
    result = poisoned.search(FastPosition.from_game_state(fresh))
    assert to_model_move(result.best_move) == capture_move


def test_ai_choose_move_is_consistent_across_calls():
    # AI builds a fresh Searcher per call: repeated calls must not drift.
    with_history, _, draw_move, _ = _repetition_scenario()
    ai = AI(strength="medium", depth=3, time_limit=5.0)
    first, _ = ai.choose_move(with_history)
    second, _ = ai.choose_move(with_history)
    assert first == second == draw_move


def test_mate_scores_prefer_faster_mates():
    # Mate in 1 must outscore mate in 3 for the side to move.
    mate_in_one = GameState.from_pieces(
        {(1, 3): Piece(R, Rank.RAT), (6, 0): Piece(R, Rank.LION), (2, 6): Piece(B, Rank.ELEPHANT)}
    )
    result = _search(mate_in_one, depth=3)
    assert result.score >= MATE - 4  # mate at the first or second ply


# -- E3 refinements: shortcut, den extension, advance ordering ------------------


def test_single_legal_move_returns_immediately():
    # The rat has exactly one legal move; no need to deepen.
    state = GameState.from_pieces(
        {(0, 0): Piece(R, Rank.RAT), (1, 0): Piece(B, Rank.LION), (0, 2): Piece(B, Rank.CAT)}
    )
    assert len(state.legal_moves()) == 1
    result = _search(state, depth=4)
    assert to_model_move(result.best_move) == Move((0, 0), (0, 1))
    assert result.depth == 0
    assert result.nodes < 10


def test_den_threat_detection():
    from jungle.engine.evaluation import build_tables
    from jungle.engine.search import Searcher

    searcher = Searcher(_config(2))
    threatened = GameState.from_pieces(
        {(1, 3): Piece(R, Rank.RAT), (6, 0): Piece(R, Rank.LION), (2, 6): Piece(B, Rank.ELEPHANT)}
    )
    pos = FastPosition.from_game_state(threatened)
    pos.attach_tables(build_tables())
    assert searcher._has_den_threat(pos)

    quiet = GameState.starting()
    pos2 = FastPosition.from_game_state(quiet)
    pos2.attach_tables(build_tables())
    assert not searcher._has_den_threat(pos2)


def test_den_extension_finds_the_win_and_stays_bounded():
    # RED rat one step from the den; the win must be seen even at depth 1.
    state = GameState.from_pieces(
        {(1, 3): Piece(R, Rank.RAT), (6, 0): Piece(R, Rank.LION), (2, 6): Piece(B, Rank.ELEPHANT)}
    )
    result = _search(state, depth=1)
    assert to_model_move(result.best_move) == Move((1, 3), (0, 3))
    assert result.score >= MATE - MAX_PLY
    assert result.nodes < 500_000


def test_advance_ordering_prefers_forward_quiets():
    from jungle.engine.search import SearchConfig, Searcher

    state = GameState.from_pieces(
        {(5, 3): Piece(R, Rank.WOLF), (0, 0): Piece(B, Rank.CAT)}
    )
    pos = FastPosition.from_game_state(state)
    searcher = Searcher(SearchConfig(max_depth=2, soft_limit_s=60.0, hard_limit_s=120.0,
                                   ordered_advance=True))
    moves = pos.legal_moves()
    searcher._order_moves(pos, moves, 0, 0)
    # Forward (4,3) approaches the blue den; (6,3) retreats. Forward first.
    first = to_model_move(moves[0])
    assert first == Move((5, 3), (4, 3))


def test_search_features_can_be_disabled():
    from jungle.engine.search import SearchConfig, Searcher

    config = SearchConfig(max_depth=3, soft_limit_s=60.0, hard_limit_s=120.0,
                          den_extension=False, ordered_advance=False)
    state = GameState.starting()
    result = Searcher(config).search(FastPosition.from_game_state(state))
    assert result.best_move != 0
