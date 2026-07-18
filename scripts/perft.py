"""Print perft node counts from the standard start (model vs fast core)."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jungle.engine.core import FastPosition  # noqa: E402
from jungle.model.board import Board, GameState, IllegalMoveError  # noqa: E402
from jungle.model.constants import Side  # noqa: E402
from tests.engine.test_perft import perft  # noqa: E402


def model_perft(state: GameState, depth: int) -> int:
    if depth == 0 or state.winner is not None or state.draw:
        return 1
    total = 0
    for move in state.legal_moves():
        try:
            child = state.after_move(move)
        except IllegalMoveError:
            continue
        total += model_perft(child, depth - 1)
    return total


def main() -> int:
    max_depth = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    state = GameState(board=Board.starting(), current_side=Side.RED)
    fast = FastPosition.from_game_state(state)
    print(f"{'depth':>5} {'model':>12} {'fast':>12} {'model s':>8} {'fast s':>8}")
    for depth in range(1, max_depth + 1):
        t0 = time.perf_counter()
        model_count = model_perft(state, depth) if depth <= 3 else None
        t1 = time.perf_counter()
        fast_count = perft(fast, depth)
        t2 = time.perf_counter()
        model_s = f"{t1 - t0:8.2f}" if model_count is not None else "     n/a"
        print(
            f"{depth:>5} {model_count if model_count is not None else '':>12} "
            f"{fast_count:>12} {model_s} {t2 - t1:8.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
