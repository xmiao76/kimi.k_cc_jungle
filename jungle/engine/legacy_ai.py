"""Intentionally weak baseline engine used as the gauntlet opponent.

Plain depth-limited alpha-beta with a material-only evaluation: no
transposition table, no move ordering, no quiescence, no time management.
It exists so ``scripts/gauntlet.py`` and the slow tests can measure whether
the real engine actually beats something. Excluded from coverage gates.
"""

from __future__ import annotations

import random
from typing import Optional

from jungle.engine.core import FastPosition, to_model_move
from jungle.engine.evaluation import MATERIAL_ONLY, EvalTables, EvalWeights, build_tables, evaluate_fast
from jungle.engine.search import INF, MATE
from jungle.model.board import GameState, Move


class LegacyAI:
    def __init__(
        self,
        depth: int = 2,
        weights: EvalWeights = MATERIAL_ONLY,
        seed: Optional[int] = None,
    ) -> None:
        self.depth = depth
        self.weights = weights
        self.tables: EvalTables = build_tables(weights)
        self._rng = random.Random(seed) if seed is not None else None

    def choose_move(self, state: GameState) -> Move:
        pos = FastPosition.from_game_state(state)
        pos.attach_tables(self.tables)
        moves = pos.legal_moves()
        if not moves:
            raise RuntimeError("no legal moves — the game is over")
        best_score = -INF
        best_moves: list[int] = []
        for move in moves:
            pos.make(move)
            score = -self._negamax(pos, self.depth - 1, -INF, INF, 1)
            pos.undo()
            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)
        # Tie-breaking is optionally seeded so gauntlet games vary while
        # remaining reproducible.
        chosen = self._rng.choice(best_moves) if self._rng is not None else best_moves[0]
        return to_model_move(chosen)

    def _negamax(self, pos: FastPosition, depth: int, alpha: int, beta: int, ply: int) -> int:
        if pos.is_repetition_draw() or pos.is_ply_cap_draw():
            return 0
        winner = pos.winner()
        if winner is not None:
            return (MATE - ply) if winner == pos.side else -(MATE - ply)
        if depth <= 0:
            return evaluate_fast(pos, self.tables)
        moves = pos.legal_moves()
        if not moves:
            return -(MATE - ply)
        best = -INF
        for move in moves:
            pos.make(move)
            score = -self._negamax(pos, depth - 1, -beta, -alpha, ply + 1)
            pos.undo()
            if score > best:
                best = score
            if score > alpha:
                alpha = score
                if alpha >= beta:
                    break
        return best
