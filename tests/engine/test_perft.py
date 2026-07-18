"""Perft conformance: fast core node counts must match the trusted model."""

from jungle.engine.core import FastPosition
from jungle.model.board import Board, GameState
from jungle.model.constants import Side


def perft(pos: FastPosition, depth: int) -> int:
    """Count game-tree leaves, stopping at terminal positions."""
    if depth == 0:
        return 1
    total = 0
    for move in pos.legal_moves():
        pos.make(move)
        if pos.is_terminal()[0]:
            total += 1
        else:
            total += perft(pos, depth - 1)
        pos.undo()
    return total


# Reference counts produced by the immutable model (scripts/perft.py).
MODEL_PERFT_FROM_START = {
    1: 24,
    2: 576,
    3: 12240,
}


def _start() -> FastPosition:
    return FastPosition.from_game_state(
        GameState(board=Board.starting(), current_side=Side.RED)
    )


def test_perft_matches_model():
    pos = _start()
    for depth, expected in MODEL_PERFT_FROM_START.items():
        assert perft(pos, depth) == expected, f"perft({depth}) mismatch"


def test_perft_deterministic():
    assert perft(_start(), 3) == perft(_start(), 3)
