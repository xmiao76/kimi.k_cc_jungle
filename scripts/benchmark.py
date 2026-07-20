"""Fixed-depth search benchmark: nodes, time, and NPS per position."""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jungle.engine.core import FastPosition, to_model_move
from jungle.engine.search import SearchConfig, Searcher
from jungle.model.board import GameState, Move, Piece
from jungle.model.constants import Rank, Side

DEPTH = 5

POSITIONS: list[tuple[str, GameState]] = []


def _build_positions() -> None:
    start = GameState.starting()
    mid = start
    for move in (Move((6, 0), (5, 0)), Move((2, 6), (2, 5)),
                 Move((8, 0), (7, 0)), Move((0, 0), (1, 0)),
                 Move((6, 4), (6, 3)), Move((2, 2), (2, 3)),
                 Move((7, 1), (6, 1)), Move((1, 5), (1, 4))):
        mid = mid.apply_move(move)
    tactical = GameState.from_pieces(
        {
            (3, 3): Piece(Side.RED, Rank.LION),
            (3, 2): Piece(Side.BLUE, Rank.RAT),
            (3, 6): Piece(Side.BLUE, Rank.DOG),
            (6, 1): Piece(Side.RED, Rank.RAT),
            (7, 2): Piece(Side.BLUE, Rank.CAT),
        },
        current_side=Side.RED,
    )
    POSITIONS.extend([("start", start), ("midgame", mid), ("tactical", tactical)])


def main() -> int:
    _build_positions()
    config = SearchConfig(max_depth=DEPTH, soft_limit_s=600.0, hard_limit_s=1200.0)
    total_nodes = 0
    total_time = 0.0
    for name, state in POSITIONS:
        searcher = Searcher(config)
        pos = FastPosition.from_game_state(state)
        start = time.monotonic()
        result = searcher.search(pos)
        elapsed = time.monotonic() - start
        nps = result.nodes / elapsed if elapsed > 0 else 0.0
        total_nodes += result.nodes
        total_time += elapsed
        print(f"{name:9s} depth {result.depth}: {result.nodes:>9,} nodes in {elapsed:6.2f}s "
              f"= {nps:>9,.0f} nps  best={to_model_move(result.best_move)} score={result.score:+}")
    if total_time > 0:
        print(f"overall  : {total_nodes:>9,} nodes in {total_time:6.2f}s "
              f"= {total_nodes / total_time:>9,.0f} nps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
