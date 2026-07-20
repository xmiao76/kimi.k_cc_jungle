"""Perft conformance: model vs fast core, from the start and a tactical spot."""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jungle.engine.core import FastPosition
from jungle.model.board import GameState, Piece
from jungle.model.constants import Rank, Side


def perft_model(state: GameState, depth: int) -> int:
    if depth == 0:
        return 1
    return sum(perft_model(state.apply_move(move), depth - 1) for move in state.legal_moves())


def perft_core(pos: FastPosition, depth: int) -> int:
    if depth == 0:
        return 1
    total = 0
    for move in pos.legal_moves():
        pos.make(move)
        total += perft_core(pos, depth - 1)
        pos.undo()
    return total


def _tactical_state() -> GameState:
    return GameState.from_pieces(
        {
            (3, 3): Piece(Side.RED, Rank.LION),
            (3, 2): Piece(Side.BLUE, Rank.RAT),
            (3, 6): Piece(Side.BLUE, Rank.DOG),
            (6, 1): Piece(Side.RED, Rank.RAT),
            (7, 2): Piece(Side.BLUE, Rank.CAT),
        },
        current_side=Side.RED,
    )


def main() -> int:
    failures = 0
    for label, state, max_depth in (
        ("start", GameState.starting(), 4),
        ("tactical", _tactical_state(), 3),
    ):
        for depth in range(1, max_depth + 1):
            start = time.monotonic()
            model_count = perft_model(state, depth)
            core_count = perft_core(FastPosition.from_game_state(state), depth)
            elapsed = time.monotonic() - start
            ok = model_count == core_count
            failures += 0 if ok else 1
            status = "OK " if ok else "MISMATCH"
            print(f"{status} {label:9s} depth {depth}: model={model_count} core={core_count} "
                  f"({elapsed:.2f}s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
