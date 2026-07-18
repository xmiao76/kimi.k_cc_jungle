"""Self-play gauntlet: candidate engine vs a baseline (legacy AI or frozen v2)."""

import argparse
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jungle.engine.ai import AI  # noqa: E402
from jungle.engine.evaluation import V2_WEIGHTS  # noqa: E402
from jungle.engine.legacy_ai import LegacyAI  # noqa: E402
from jungle.engine.search import SearchConfig  # noqa: E402
from jungle.model.board import Board, GameState  # noqa: E402
from jungle.model.constants import Side  # noqa: E402


def make_v2(side: Side, depth: int, time_s: float) -> AI:
    """The frozen previous engine generation (all v3 features disabled)."""
    return AI(
        side,
        config=SearchConfig(
            max_depth=depth,
            soft_limit_s=time_s,
            hard_limit_s=time_s * 2.5,
            use_aspiration=False,
            use_lmr=False,
            use_see_pruning=False,
            use_persistent_tt=False,
            weights=V2_WEIGHTS,
        ),
    )


def opening_state(rng: random.Random, plies: int = 6) -> GameState:
    """A randomized midgame-start position so deterministic engines vary."""
    state = GameState(board=Board.starting(), current_side=Side.RED)
    for _ in range(plies):
        moves = state.legal_moves()
        if not moves or state.winner is not None or state.draw:
            break
        state = state.after_move(rng.choice(moves))
    return state


def play_game(
    engine_red,
    engine_blue,
    start_state: GameState | None = None,
    max_plies: int = 200,
) -> tuple[str, int]:
    """Play one game; return ("red" | "blue" | "draw", plies)."""
    state = start_state or GameState(board=Board.starting(), current_side=Side.RED)
    while state.winner is None and not state.draw and state.move_count < max_plies:
        engine = engine_red if state.current_side is Side.RED else engine_blue
        move = engine.choose_move(state)
        if move is None:
            break
        state = state.after_move(move)
    if state.winner is Side.RED:
        return "red", state.move_count
    if state.winner is Side.BLUE:
        return "blue", state.move_count
    return "draw", state.move_count


def run_gauntlet(
    games: int,
    candidate_factory,
    baseline_factory,
    seed: int = 12345,
    verbose: bool = True,
) -> float:
    """Return the candidate's score fraction (win=1, draw=0.5, loss=0)."""
    score = 0.0
    started = time.perf_counter()
    for g in range(games):
        random.seed(seed + g)  # deterministic tie-breaking inside LegacyAI
        opening_rng = random.Random(seed * 1000 + g)
        start = opening_state(opening_rng)
        if g % 2 == 0:
            red = candidate_factory(Side.RED)
            blue = baseline_factory(Side.BLUE)
            candidate_color = "red"
        else:
            red = baseline_factory(Side.RED)
            blue = candidate_factory(Side.BLUE)
            candidate_color = "blue"
        result, plies = play_game(red, blue, start_state=start)
        if result == candidate_color:
            points = 1.0
        elif result == "draw":
            points = 0.5
        else:
            points = 0.0
        score += points
        if verbose:
            print(
                f"game {g + 1:>2}/{games}: candidate={candidate_color:<4} "
                f"result={result:<4} plies={plies:>3} points={points:.1f}"
            )
    fraction = score / games if games else 0.0
    if verbose:
        elapsed = time.perf_counter() - started
        print(f"candidate score: {score:.1f}/{games} = {fraction:.0%} ({elapsed:.1f}s)")
    return fraction


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--candidate-depth", type=int, default=6)
    parser.add_argument("--candidate-time", type=float, default=0.5)
    parser.add_argument("--baseline", choices=("legacy", "v2"), default="legacy")
    parser.add_argument("--baseline-depth", type=int, default=3)
    parser.add_argument("--seed", type=int, default=12345)
    args = parser.parse_args()

    def candidate(side: Side) -> AI:
        return AI(side, depth=args.candidate_depth, time_limit_s=args.candidate_time)

    if args.baseline == "v2":
        def baseline(side: Side) -> AI:
            # Same budget as the candidate; only the feature set differs.
            return make_v2(side, args.candidate_depth, args.candidate_time)
    else:
        def baseline(side: Side) -> LegacyAI:
            return LegacyAI(side, depth=args.baseline_depth)

    run_gauntlet(args.games, candidate, baseline, seed=args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
