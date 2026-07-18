"""Frozen copy of the original depth-limited negamax AI.

Kept as the baseline opponent for gauntlet testing (scripts/gauntlet.py) so
engine improvements are measured against the historical strength. Not used
by the application; excluded from coverage requirements.
"""

from __future__ import annotations

import random
from typing import Iterable

from jungle.model.board import GameState, IllegalMoveError, Move
from jungle.model.constants import DEN_POSITIONS, RIVER_SQUARES, Rank, Side

# Material values loosely based on rank (original evaluation).
PIECE_VALUES: dict[Rank, int] = {
    Rank.RAT: 30,
    Rank.CAT: 15,
    Rank.WOLF: 20,
    Rank.DOG: 20,
    Rank.LEOPARD: 25,
    Rank.TIGER: 40,
    Rank.LION: 45,
    Rank.ELEPHANT: 50,
}

_DEN_BONUS_MAX = 8


def evaluate(state: GameState, perspective: Side) -> int:
    """Original static evaluation (material + den proximity + rat river)."""
    if state.winner is not None:
        return 10_000 if state.winner is perspective else -10_000

    score = 0
    target_den = DEN_POSITIONS[perspective.opponent()]

    for pos in state.board.positions():
        piece = state.board.piece_at(pos)
        if piece is None:
            continue

        value = PIECE_VALUES[piece.rank]
        distance_to_den = abs(pos[0] - target_den[0]) + abs(pos[1] - target_den[1])
        den_bonus = max(0, _DEN_BONUS_MAX - distance_to_den)
        river_bonus = 3 if piece.rank is Rank.RAT and pos in RIVER_SQUARES else 0

        piece_score = value + den_bonus + river_bonus
        if piece.side is perspective:
            score += piece_score
        else:
            score -= piece_score

    return score


class LegacyAI:
    """Original Jungle AI: fixed-depth negamax alpha-beta, captures first."""

    def __init__(self, side: Side, depth: int = 3) -> None:
        self.side = side
        self.depth = depth

    def choose_move(self, state: GameState) -> Move | None:
        """Return the best move for `self.side` from `state`, or None if no moves."""
        legal = state.legal_moves()
        if not legal:
            return None

        ordered = self._order_moves(state, legal)

        best_score = -float("inf")
        best_moves: list[Move] = []
        alpha = -float("inf")
        beta = float("inf")

        for move in ordered:
            try:
                child = state.after_move(move)
            except IllegalMoveError:
                continue
            score = -self._negamax(child, self.depth - 1, -beta, -alpha, self.side.opponent())
            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)
            alpha = max(alpha, score)

        if not best_moves:
            return random.choice(legal)

        return random.choice(best_moves)

    def _negamax(
        self,
        state: GameState,
        depth: int,
        alpha: float,
        beta: float,
        perspective: Side,
    ) -> float:
        if state.winner is not None:
            return 10_000 if state.winner is perspective else -10_000

        if depth == 0:
            return evaluate(state, perspective)

        legal = state.legal_moves()
        if not legal:
            return -10_000

        ordered = self._order_moves(state, legal)
        for move in ordered:
            try:
                child = state.after_move(move)
            except IllegalMoveError:
                continue
            score = -self._negamax(child, depth - 1, -beta, -alpha, perspective.opponent())
            if score >= beta:
                return beta
            alpha = max(alpha, score)

        return alpha

    @staticmethod
    def _order_moves(state: GameState, moves: Iterable[Move]) -> list[Move]:
        """Order moves so captures are searched first."""
        return sorted(
            moves,
            key=lambda m: state.board.piece_at(m.to_pos) is not None,
            reverse=True,
        )
