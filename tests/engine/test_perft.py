"""Perft node-count conformance between the two independent move generators.

The start-position counts (24 / 576 / 12240 / 260099) are pinned regression
anchors: both generators were validated against each other and against the
known 24-move root width of Jungle. The custom position exercises jumps,
a rat block, and a river rat.
"""

import pytest

from jungle.engine.core import FastPosition
from jungle.model.board import GameState, Piece
from jungle.model.constants import Rank, Side

START_COUNTS = {1: 24, 2: 576, 3: 12240, 4: 260099}
CUSTOM_COUNTS = {1: 7, 2: 64, 3: 442}


def _perft_model(state: GameState, depth: int) -> int:
    if depth == 0:
        return 1
    return sum(_perft_model(state.apply_move(move), depth - 1) for move in state.legal_moves())


def _perft_core(pos: FastPosition, depth: int) -> int:
    if depth == 0:
        return 1
    total = 0
    for move in pos.legal_moves():
        pos.make(move)
        total += _perft_core(pos, depth - 1)
        pos.undo()
    return total


def _custom_state() -> GameState:
    return GameState.from_pieces(
        {
            (3, 3): Piece(Side.RED, Rank.LION),
            (3, 2): Piece(Side.BLUE, Rank.RAT),  # blocks the lion's left jump
            (3, 6): Piece(Side.BLUE, Rank.DOG),  # capturable via the right jump
            (6, 1): Piece(Side.RED, Rank.RAT),
            (7, 2): Piece(Side.BLUE, Rank.CAT),
        },
        current_side=Side.RED,
    )


@pytest.mark.parametrize(
    "depth,expected",
    [
        (1, START_COUNTS[1]),
        (2, START_COUNTS[2]),
        (3, START_COUNTS[3]),
        pytest.param(4, START_COUNTS[4], marks=pytest.mark.slow),
    ],
)
def test_start_position_perft_model(depth, expected):
    assert _perft_model(GameState.starting(), depth) == expected


@pytest.mark.parametrize("depth,expected", sorted(START_COUNTS.items()))
def test_start_position_perft_core(depth, expected):
    pos = FastPosition.from_game_state(GameState.starting())
    assert _perft_core(pos, depth) == expected


@pytest.mark.parametrize("depth,expected", sorted(CUSTOM_COUNTS.items()))
def test_custom_position_perft_agrees(depth, expected):
    state = _custom_state()
    assert _perft_model(state, depth) == expected
    assert _perft_core(FastPosition.from_game_state(state), depth) == expected
