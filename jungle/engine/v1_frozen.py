"""Frozen snapshot of the first-generation engine (the v1 baseline).

Self-contained copy of the original search + evaluation so gauntlets can
measure newer versions against a fixed opponent that never improves as the
real engine evolves. Shares only the rules core (move generation, Zobrist)
with the live engine. Excluded from coverage requirements.

Do NOT "improve" this file — its whole purpose is to stay frozen.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from jungle.engine.core import FastPosition, move_to, rank_of, side_of, to_model_move
from jungle.engine.tables import DEN_IDX, DIST_TO_DEN, MAX_DEN_DIST, TRAP_TABLE
from jungle.model.board import GameState, Move

MATE = 100_000
INF = 1_000_000
MAX_PLY = 64
QSEARCH_MAX_PLY = 8
TIME_CHECK_MASK = 2047
DELTA_MARGIN = 1200

EXACT, LOWER, UPPER = 0, 1, 2

_TT_SCORE = 10_000_000
_CAPTURE_BASE = 1_000_000
_KILLER_PRIMARY = 900_000
_KILLER_SECONDARY = 800_000

# -- v1 evaluation (verbatim snapshot) -----------------------------------------

V1_MATERIAL = (0, 100, 180, 260, 340, 420, 560, 700, 900)
V1_ADVANCEMENT = 8
V1_DEN_APPROACH = 50
V1_TRAP_DANGER = 40
V1_ELEPHANT_RAT_PENALTY = 120
V1_RAT_UTILITY_BONUS = 60


def v1_evaluate(pos: FastPosition) -> int:
    totals = [0, 0]
    has_rat = [False, False]
    has_elephant = [False, False]
    for idx in range(63):
        cell = pos.cells[idx]
        if cell == 0:
            continue
        side = side_of(cell)
        rank = rank_of(cell)
        if rank == 1:
            has_rat[side] = True
        elif rank == 8:
            has_elephant[side] = True
        value = V1_MATERIAL[rank]
        dist = DIST_TO_DEN[side ^ 1][idx]
        value += V1_ADVANCEMENT * (MAX_DEN_DIST - dist)
        if dist == 1:
            value += V1_DEN_APPROACH
        if TRAP_TABLE[side ^ 1][idx]:
            value -= V1_TRAP_DANGER
        totals[side] += value
    for side in (0, 1):
        if has_elephant[side] and has_rat[side ^ 1]:
            totals[side] -= V1_ELEPHANT_RAT_PENALTY
        if has_rat[side] and has_elephant[side ^ 1]:
            totals[side] += V1_RAT_UTILITY_BONUS
    side = pos.side
    return totals[side] - totals[side ^ 1]


class _AbortSearch(Exception):
    pass


class V1Searcher:
    """Verbatim snapshot of the v1 search (fresh TT per root search)."""

    def __init__(self, max_depth: int, soft_limit_s: float, hard_limit_s: float,
                 abort_event: Optional[threading.Event] = None) -> None:
        self.max_depth = max_depth
        self.soft_limit_s = soft_limit_s
        self.hard_limit_s = hard_limit_s
        self.abort_event = abort_event if abort_event is not None else threading.Event()
        self.tt: dict[int, tuple[int, int, int, int]] = {}
        self.killers = [[0, 0] for _ in range(MAX_PLY)]
        self.history = [[0] * 64 for _ in range(64)]
        self.nodes = 0
        self._start = 0.0
        self._deadline = 0.0

    def search(self, pos: FastPosition) -> tuple[int, int]:
        self._start = time.monotonic()
        self._deadline = self._start + self.hard_limit_s
        self.nodes = 0
        root_moves = pos.legal_moves()
        if not root_moves:
            return 0, -MATE
        best_move = root_moves[0]
        best_score = -INF
        completed_depth = 0
        last_iter_s = 0.0
        for depth in range(1, self.max_depth + 1):
            iter_start = time.monotonic()
            try:
                score, move = self._search_root(pos, depth, best_move)
            except _AbortSearch:
                break
            best_move, best_score = move, score
            completed_depth = depth
            last_iter_s = time.monotonic() - iter_start
            if abs(score) >= MATE - MAX_PLY:
                break
            elapsed = time.monotonic() - self._start
            if elapsed >= self.soft_limit_s:
                break
            if last_iter_s * 4 > self.soft_limit_s - elapsed:
                break
        return best_move, best_score

    def _search_root(self, pos: FastPosition, depth: int, prev_best: int) -> tuple[int, int]:
        alpha, beta = -INF, INF
        moves = pos.legal_moves()
        self._order_moves(pos, moves, prev_best, 0)
        best_move = moves[0]
        for i, move in enumerate(moves):
            pos.make(move)
            if i == 0:
                score = -self._pvs(pos, depth - 1, -beta, -alpha, 1)
            else:
                score = -self._pvs(pos, depth - 1, -alpha - 1, -alpha, 1)
                if alpha < score < beta:
                    score = -self._pvs(pos, depth - 1, -beta, -alpha, 1)
            pos.undo()
            if score > alpha:
                alpha = score
                best_move = move
        return alpha, best_move

    def _pvs(self, pos: FastPosition, depth: int, alpha: int, beta: int, ply: int) -> int:
        self.nodes += 1
        if self.nodes & TIME_CHECK_MASK == 0:
            self._check_abort()
        if pos.is_repetition_draw() or pos.is_ply_cap_draw():
            return 0
        winner = pos.winner()
        if winner is not None:
            return (MATE - ply) if winner == pos.side else -(MATE - ply)
        alpha = max(alpha, -(MATE - ply))
        beta = min(beta, MATE - ply - 1)
        if alpha >= beta:
            return alpha
        if depth <= 0:
            return self._quiescence(pos, alpha, beta, ply, QSEARCH_MAX_PLY)
        tt_move = 0
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
            return -(MATE - ply)
        self._order_moves(pos, moves, tt_move, ply)
        best_score = -INF
        best_move = 0
        flag = UPPER
        for i, move in enumerate(moves):
            is_capture = pos.cells[move_to(move)] != 0
            pos.make(move)
            if i == 0:
                score = -self._pvs(pos, depth - 1, -beta, -alpha, ply + 1)
            else:
                score = -self._pvs(pos, depth - 1, -alpha - 1, -alpha, ply + 1)
                if alpha < score < beta:
                    score = -self._pvs(pos, depth - 1, -beta, -alpha, ply + 1)
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
        if best_move:
            self.tt[pos.key] = (depth, self._score_to_tt(best_score, ply), flag, best_move)
        return best_score

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
        stand_pat = v1_evaluate(pos)
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
            move for move in all_moves
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

    def _order_moves(self, pos: FastPosition, moves: list[int], tt_move: int, ply: int) -> None:
        cells = pos.cells
        slot = self.killers[ply]
        history = self.history
        scored: list[tuple[int, int]] = []
        for move in moves:
            if move == tt_move:
                scored.append((_TT_SCORE, move))
                continue
            frm = move & 63
            to = move_to(move)
            victim = cells[to]
            if victim != 0:
                scored.append((_CAPTURE_BASE + rank_of(victim) * 32 - rank_of(cells[frm]), move))
            elif move == slot[0]:
                scored.append((_KILLER_PRIMARY, move))
            elif move == slot[1]:
                scored.append((_KILLER_SECONDARY, move))
            else:
                scored.append((history[frm][to], move))
        scored.sort(key=lambda item: item[0], reverse=True)
        moves[:] = [move for _, move in scored]

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


class V1FrozenAI:
    """The v1 engine as a gauntlet opponent (same interface as AI)."""

    def __init__(self, depth: int = 3, time_limit: float = 0.3) -> None:
        self.depth = depth
        self.soft = time_limit
        self.hard = time_limit * 2.5

    def choose_move(self, state: GameState) -> tuple[Move, None]:
        pos = FastPosition.from_game_state(state)
        searcher = V1Searcher(self.depth, self.soft, self.hard)
        best, _ = searcher.search(pos)
        if best == 0:
            legal = pos.legal_moves()
            if not legal:
                raise RuntimeError("no legal moves — the game is over")
            best = legal[0]
        return to_model_move(best), None
