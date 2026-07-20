"""Self-play gauntlet: the real engine vs the weak legacy baseline.

Alternates colors every game and reports the score. Used by the slow tests
to guard engine strength. Example:

    python scripts/gauntlet.py --games 20 --depth 3 --time-limit 0.3
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import replace
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import replace

from jungle.engine.ai import AI
from jungle.engine.evaluation import DEFAULT_WEIGHTS, EvalWeights
from jungle.engine.legacy_ai import LegacyAI
from jungle.engine.v1_frozen import V1FrozenAI
from jungle.model.board import GameState, Move
from jungle.model.constants import Side


def _choose(player, state: GameState) -> Move:
    choice = player.choose_move(state)
    return choice[0] if isinstance(choice, tuple) else choice


def parse_weights(spec: str) -> EvalWeights:
    """Parse 'den_defense=12,rat_river=25' into an EvalWeights override.
    Semicolon-separated values build tuples (advancement_per_rank=0;16;8;8)."""
    overrides: dict = {}
    for item in spec.split(","):
        key, _, value = item.partition("=")
        key = key.strip()
        if not hasattr(DEFAULT_WEIGHTS, key):
            raise ValueError(f"unknown EvalWeights field {key!r}")
        overrides[key] = tuple(int(v) for v in value.split(";")) if ";" in value else int(value)
    return replace(DEFAULT_WEIGHTS, **overrides)


def play_game(red_player, blue_player) -> float:
    """One full game. Returns 1.0 (RED wins), 0.5 (draw), or 0.0 (BLUE wins)."""
    state = GameState.starting()
    while not state.is_game_over:
        player = red_player if state.current_side is Side.RED else blue_player
        state = state.apply_move(_choose(player, state))
    winner = state.winner
    if winner is None:
        return 0.5
    return 1.0 if winner is Side.RED else 0.0


def _make_baseline(name: str, depth: int, seed: int, time_limit: float):
    if name == "legacy":
        return LegacyAI(depth=2, seed=seed)
    if name == "v1":
        return V1FrozenAI(depth=depth, time_limit=0.3)
    if name == "self":
        # The current engine with the new search features switched off, for
        # gating search refinements (den extension / advance ordering).
        ai = AI(strength="medium", depth=depth, time_limit=time_limit)
        ai.config = replace(ai.config, den_extension=False, ordered_advance=False)
        return ai
    raise ValueError(f"unknown baseline {name!r}")


def run_gauntlet(games: int, depth: int, time_limit: float, legacy_depth: int,
                 seed: int, baseline: str = "legacy",
                 weights: Optional[EvalWeights] = None) -> tuple[float, list[str]]:
    engine = AI(strength="medium", depth=depth, time_limit=time_limit, weights=weights)
    results: list[float] = []
    lines: list[str] = []
    for game_no in range(games):
        opponent = _make_baseline(baseline, depth, seed + game_no, time_limit)
        engine_is_red = game_no % 2 == 0
        red = engine if engine_is_red else opponent
        blue = opponent if engine_is_red else engine
        outcome = play_game(red, blue)
        # Convert to the engine's perspective.
        score = outcome if engine_is_red else 1.0 - outcome
        results.append(score)
        lines.append(
            f"game {game_no + 1:2d}: engine plays {'RED ' if engine_is_red else 'BLUE'} "
            f"-> {'win ' if score == 1.0 else 'draw' if score == 0.5 else 'loss'}"
        )
    total = sum(results)
    lines.append(f"score: {total:.1f}/{games} ({100.0 * total / games:.0f}%) vs {baseline}")
    return total / games, lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--depth", type=int, default=3, help="engine search depth")
    parser.add_argument("--time-limit", type=float, default=0.3,
                        help="engine soft thinking time per move (seconds)")
    parser.add_argument("--legacy-depth", type=int, default=2)
    parser.add_argument("--baseline", choices=["legacy", "v1", "self"], default="legacy")
    parser.add_argument("--weights", default=None,
                        help="eval overrides, e.g. 'den_defense=12,rat_river=25'")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    weights = parse_weights(args.weights) if args.weights else None
    _, lines = run_gauntlet(args.games, args.depth, args.time_limit,
                            args.legacy_depth, args.seed, args.baseline, weights)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
