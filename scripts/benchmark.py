"""Engine benchmark: iterative-deepening depth, nodes, and speed per position."""

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jungle.engine.core import FastPosition  # noqa: E402
from jungle.engine.search import SearchConfig, Searcher  # noqa: E402
from jungle.model.board import Board, GameState  # noqa: E402
from jungle.model.constants import Side  # noqa: E402


def _middlegame(seed: int, plies: int) -> GameState:
    rng = random.Random(seed)
    state = GameState(board=Board.starting(), current_side=Side.RED)
    for _ in range(plies):
        moves = state.legal_moves()
        if not moves or state.winner is not None or state.draw:
            break
        state = state.after_move(rng.choice(moves))
    return state


POSITIONS = {
    "start": GameState(board=Board.starting(), current_side=Side.RED),
    "midgame-12": _middlegame(7, 12),
    "midgame-24": _middlegame(13, 24),
}


def benchmark(state: GameState, max_depth: int) -> tuple[int, int, float]:
    pos = FastPosition.from_game_state(state)
    searcher = Searcher(
        SearchConfig(max_depth=max_depth, soft_limit_s=600.0, hard_limit_s=1200.0)
    )
    start = time.perf_counter()
    result = searcher.search(pos)
    elapsed = time.perf_counter() - start
    return result.depth, result.nodes, elapsed


def main() -> int:
    max_depth = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    print(f"{'position':<12} {'depth':>5} {'nodes':>12} {'time s':>8} {'nps':>12}")
    for name, state in POSITIONS.items():
        depth, nodes, elapsed = benchmark(state, max_depth)
        nps = int(nodes / elapsed) if elapsed > 0 else 0
        print(f"{name:<12} {depth:>5} {nodes:>12} {elapsed:>8.2f} {nps:>12}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
