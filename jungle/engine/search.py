"""Iterative-deepening PVS alpha-beta search over the fast core.

Design constraints are deliberate and measured on this game (see project
notes): the transposition table is created fresh for every root search —
persistent cross-move TT entries poison repetition-aware draw scoring and
measurably cost strength — and LMR, SEE pruning, and aspiration windows are
omitted because gauntlets showed them harmful-to-neutral here. Strength
comes from evaluation, move ordering, and clean time management.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from jungle.engine.core import FastPosition, move_to, rank_of
from jungle.engine.evaluation import (
    DEFAULT_WEIGHTS,
    EvalTables,
    EvalWeights,
    build_tables,
    evaluate_fast,
)
from jungle.engine.tables import DEN_IDX, DIST_TO_DEN
from jungle.model.board import MAX_PLIES  # noqa: F401  (re-exported for callers)

MATE = 100_000
INF = 1_000_000
MAX_PLY = 64
QSEARCH_MAX_PLY = 8
TIME_CHECK_MASK = 2047  # poll the clock every 2048 nodes
# Delta-pruning margin: safely above the largest plausible single-move swing
# (elephant material 900 + full advancement 112 + den approach 50).
DELTA_MARGIN = 1200

EXACT, LOWER, UPPER = 0, 1, 2

_TT_SCORE = 10_000_000
_CAPTURE_BASE = 1_000_000
_KILLER_PRIMARY = 900_000
_KILLER_SECONDARY = 800_000

# Max den-threat extensions per search path (prevents extension chains).
EXTENSION_BUDGET = 4


@dataclass(frozen=True)
class SearchConfig:
    max_depth: int = 4
    soft_limit_s: float = 1.0
    hard_limit_s: float = 2.5
    use_tt: bool = True
    weights: EvalWeights = DEFAULT_WEIGHTS
    # Den-threat extension: search one ply deeper when the side to move can
    # enter the enemy den next move (bounded per path). Measured NEUTRAL in
    # fixed-depth gauntlets vs the features-off engine (4/8 at d3 and d2) —
    # defaulted OFF per project discipline (same fate as LMR/aspiration).
    den_extension: bool = False
    # Static quiet-move ordering: prefer moves approaching the enemy den.
    # Also measured neutral — kept off by default.
    ordered_advance: bool = False


@dataclass(frozen=True)
class SearchResult:
    best_move: int  # packed engine move; 0 means "none" (terminal position)
    score: int
    depth: int  # deepest fully completed iteration
    nodes: int


class _AbortSearch(Exception):
    """Internal unwind used when the hard time limit or abort fires."""


class Searcher:
    """Runs one root search per instance so the TT is never shared across
    moves. Reuse is prevented by design, not just convention."""

    def __init__(
        self,
        config: SearchConfig,
        abort_event: Optional[threading.Event] = None,
        info_callback: Optional[Callable[[int, int, int], None]] = None,
    ) -> None:
        self.config = config
        self.abort_event = abort_event if abort_event is not None else threading.Event()
        self.info_callback = info_callback
        self.tables: EvalTables = build_tables(config.weights)
        self.tt: dict[int, tuple[int, int, int, int]] = {}
        self.killers = [[0, 0] for _ in range(MAX_PLY)]
        self.history = [[0] * 64 for _ in range(64)]
        self.nodes = 0
        self._start = 0.0
        self._deadline = 0.0

    # -- root search ------------------------------------------------------

    def search(self, pos: FastPosition) -> SearchResult:
        self._start = time.monotonic()
        self._deadline = self._start + self.config.hard_limit_s
        self.nodes = 0
        if pos.tables is not self.tables:
            pos.attach_tables(self.tables)

        root_moves = pos.legal_moves()
        if not root_moves:
            return SearchResult(0, -MATE, 0, 0)
        if len(root_moves) == 1:
            # Forced move: skip the whole iterative-deepening machinery.
            only = root_moves[0]
            pos.make(only)
            winner = pos.winner()
            if winner is not None:
                score = (MATE - 1) if winner == pos.side ^ 1 else -(MATE - 1)
            elif pos.is_repetition_draw() or pos.is_ply_cap_draw():
                score = 0
            else:
                score = -evaluate_fast(pos, self.tables)
            pos.undo()
            return SearchResult(only, score, 0, self.nodes)

        best_move = root_moves[0]
        best_score = -INF
        completed_depth = 0
        last_iter_s = 0.0
        for depth in range(1, self.config.max_depth + 1):
            iter_start = time.monotonic()
            try:
                score, move = self._search_root(pos, depth, best_move)
            except _AbortSearch:
                break
            best_move, best_score = move, score
            completed_depth = depth
            last_iter_s = time.monotonic() - iter_start
            if self.info_callback is not None:
                self.info_callback(depth, score, self.nodes)
            if abs(score) >= MATE - MAX_PLY:
                break  # forced mate found — deeper search adds nothing
            elapsed = time.monotonic() - self._start
            if elapsed >= self.config.soft_limit_s:
                break
            if last_iter_s * 4 > self.config.soft_limit_s - elapsed:
                break  # the next iteration would likely overrun the budget
        return SearchResult(best_move, best_score, completed_depth, self.nodes)

    def _search_root(self, pos: FastPosition, depth: int, prev_best: int) -> tuple[int, int]:
        alpha, beta = -INF, INF
        moves = pos.legal_moves()
        self._order_moves(pos, moves, prev_best, 0)
        best_move = moves[0]
        for i, move in enumerate(moves):
            pos.make(move)
            if i == 0:
                score = -self._pvs(pos, depth - 1, -beta, -alpha, 1, EXTENSION_BUDGET)
            else:
                score = -self._pvs(pos, depth - 1, -alpha - 1, -alpha, 1, EXTENSION_BUDGET)
                if alpha < score < beta:
                    score = -self._pvs(pos, depth - 1, -beta, -alpha, 1, EXTENSION_BUDGET)
            pos.undo()
            if score > alpha:
                alpha = score
                best_move = move
        return alpha, best_move

    # -- negamax with PVS ---------------------------------------------------

    def _pvs(self, pos: FastPosition, depth: int, alpha: int, beta: int, ply: int,
             ext_left: int) -> int:
        self.nodes += 1
        if self.nodes & TIME_CHECK_MASK == 0:
            self._check_abort()

        if pos.is_repetition_draw() or pos.is_ply_cap_draw():
            return 0
        winner = pos.winner()
        if winner is not None:
            return (MATE - ply) if winner == pos.side else -(MATE - ply)

        # Mate-distance pruning.
        alpha = max(alpha, -(MATE - ply))
        beta = min(beta, MATE - ply - 1)
        if alpha >= beta:
            return alpha

        if depth <= 0:
            # Den-threat extension: a side one step from the enemy den makes
            # this position sharp — search one ply deeper (bounded per path).
            if ext_left > 0 and self.config.den_extension and self._has_den_threat(pos):
                depth = 1
                ext_left -= 1
            else:
                return self._quiescence(pos, alpha, beta, ply, QSEARCH_MAX_PLY)

        tt_move = 0
        if self.config.use_tt:
            entry = self.tt.get(pos.key)
            if entry is not None:
                tt_depth, tt_score, tt_flag, tt_move = entry
                if ply > 0 and tt_depth >= depth:
                    adjusted = self._score_from_tt(tt_score, ply)
                    if tt_flag == EXACT:
                        return adjusted
                    if tt_flag == LOWER:
                        alpha = max(alpha, adjusted)
                    else:
                        beta = min(beta, adjusted)
                    if alpha >= beta:
                        return adjusted

        moves = pos.legal_moves()
        if not moves:
            return -(MATE - ply)  # side to move has no legal moves: loss

        self._order_moves(pos, moves, tt_move, ply)
        best_score = -INF
        best_move = 0
        flag = UPPER
        for i, move in enumerate(moves):
            is_capture = pos.cells[move_to(move)] != 0
            pos.make(move)
            if i == 0:
                score = -self._pvs(pos, depth - 1, -beta, -alpha, ply + 1, ext_left)
            else:
                score = -self._pvs(pos, depth - 1, -alpha - 1, -alpha, ply + 1, ext_left)
                if alpha < score < beta:
                    score = -self._pvs(pos, depth - 1, -beta, -alpha, ply + 1, ext_left)
            pos.undo()
            if score > best_score:
                best_score, best_move = score, move
            if score > alpha:
                alpha = score
                if alpha >= beta:
                    if not is_capture:
                        slot = self.killers[ply]
                        if move != slot[0]:
                            slot[0], slot[1] = move, slot[0]
                        self.history[move & 63][move_to(move)] += depth * depth
                    flag = LOWER
                    break
                flag = EXACT

        if self.config.use_tt and best_move:
            self.tt[pos.key] = (depth, self._score_to_tt(best_score, ply), flag, best_move)
        return best_score

    # -- quiescence ---------------------------------------------------------

    def _quiescence(self, pos: FastPosition, alpha: int, beta: int, ply: int, qply: int) -> int:
        self.nodes += 1
        if self.nodes & TIME_CHECK_MASK == 0:
            self._check_abort()

        if pos.is_repetition_draw() or pos.is_ply_cap_draw():
            return 0
        winner = pos.winner()
        if winner is not None:
            return (MATE - ply) if winner == pos.side else -(MATE - ply)

        all_moves = pos.legal_moves()
        if not all_moves:
            return -(MATE - ply)

        stand_pat = evaluate_fast(pos, self.tables)
        if stand_pat >= beta:
            return stand_pat
        if stand_pat + DELTA_MARGIN < alpha:
            return alpha
        if stand_pat > alpha:
            alpha = stand_pat
        if qply <= 0:
            return alpha

        enemy_den = DEN_IDX[pos.side ^ 1]
        tactical = [
            move
            for move in all_moves
            if pos.cells[move_to(move)] != 0 or move_to(move) == enemy_den
        ]
        scored = []
        for move in tactical:
            to = move_to(move)
            if to == enemy_den:
                scored.append((_TT_SCORE, move))
            else:
                scored.append(
                    (_CAPTURE_BASE + rank_of(pos.cells[to]) * 32 - rank_of(pos.cells[move & 63]), move)
                )
        scored.sort(key=lambda item: item[0], reverse=True)

        for _, move in scored:
            pos.make(move)
            score = -self._quiescence(pos, -beta, -alpha, ply + 1, qply - 1)
            pos.undo()
            if score >= beta:
                return score
            if score > alpha:
                alpha = score
        return alpha

    # -- move ordering --------------------------------------------------------

    def _order_moves(self, pos: FastPosition, moves: list[int], tt_move: int, ply: int) -> None:
        cells = pos.cells
        slot = self.killers[ply]
        history = self.history
        enemy_den_dist = DIST_TO_DEN[pos.side ^ 1] if self.config.ordered_advance else None
        scored: list[tuple[int, int]] = []
        for move in moves:
            if move == tt_move:
                scored.append((_TT_SCORE, move))
                continue
            frm = move & 63
            to = move_to(move)
            victim = cells[to]
            if victim != 0:
                # MVV-LVA: most valuable victim, least valuable attacker.
                scored.append((_CAPTURE_BASE + rank_of(victim) * 32 - rank_of(cells[frm]), move))
            elif move == slot[0]:
                scored.append((_KILLER_PRIMARY, move))
            elif move == slot[1]:
                scored.append((_KILLER_SECONDARY, move))
            else:
                score = history[frm][to]
                if enemy_den_dist is not None:
                    # Static bias: quiet moves approaching the enemy den first.
                    score += 2 * (enemy_den_dist[frm] - enemy_den_dist[to])
                scored.append((score, move))
        scored.sort(key=lambda item: item[0], reverse=True)
        moves[:] = [move for _, move in scored]

    # -- misc ----------------------------------------------------------------

    def _has_den_threat(self, pos: FastPosition) -> bool:
        """True when the side to move has a piece one step from the enemy den
        (den entry next move). Uses the incrementally tracked animal indices."""
        dist = DIST_TO_DEN[pos.side ^ 1]
        for idx in pos.animal_idx[pos.side]:
            if idx >= 0 and dist[idx] == 1:
                return True
        return False

    def _check_abort(self) -> None:
        if self.abort_event.is_set() or time.monotonic() >= self._deadline:
            raise _AbortSearch

    @staticmethod
    def _score_to_tt(score: int, ply: int) -> int:
        if score > MATE - MAX_PLY:
            return score + ply
        if score < -(MATE - MAX_PLY):
            return score - ply
        return score

    @staticmethod
    def _score_from_tt(score: int, ply: int) -> int:
        if score > MATE - MAX_PLY:
            return score - ply
        if score < -(MATE - MAX_PLY):
            return score + ply
        return score
