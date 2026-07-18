"""Alpha-beta search with iterative deepening for the Jungle engine.

Stack: negamax PVS + Zobrist transposition table + quiescence search +
TT/killer/history/MVV-LVA move ordering + mate-distance pruning +
repetition-aware draw scoring + wall-clock time management with abort.
Optional (flag-gated, default off after gauntlet measurement): persistent
TT with aging, aspiration windows, late move reductions, SEE-lite pruning.

Every v3 feature can be disabled via SearchConfig so the previous engine
generation (v2) remains reproducible for gauntlet comparisons. The search
is deterministic when it completes `max_depth` within the time budget.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Event
from typing import Callable

from jungle.engine import tables
from jungle.engine.core import EMPTY, FastPosition, move_from, move_to, rank_of
from jungle.engine.evaluation import DEFAULT_WEIGHTS, EvalWeights, evaluate_fast
from jungle.model.board import MAX_PLIES
from jungle.model.constants import Side, Terrain

MATE = 100_000
INF = 1_000_000
MAX_PLY = 64
MATE_BOUND = MATE - 1000  # scores above this are mate scores

_TT_EXACT = 0
_TT_LOWER = 1
_TT_UPPER = 2

_QUIESCENCE_PLIES = 8
_DELTA_MARGIN = 200
_SEE_MARGIN = 150          # max attacker-victim deficit allowed in quiescence
_ASPIRATION_START_DEPTH = 4
_ASPIRATION_WINDOW = 150   # wide enough for this game's eval volatility
_LMR_MIN_DEPTH = 3
_LMR_MIN_MOVE_INDEX = 3
_NODE_MASK = 2047  # time/abort check granularity
_ITERATION_GROWTH = 4.0  # est. cost factor of the next ID iteration

InfoCallback = Callable[[int, int, int], None]  # (depth, score_cp, nodes)


class _Abort(Exception):
    """Raised internally to unwind the search on time-out or abort."""


@dataclass(frozen=True)
class SearchConfig:
    """Knobs for one search.

    Defaults reflect the gauntlet-proven v3 configuration: the v3 eval
    terms (75% at fixed depth 4, 69% at depth 5 vs v2) with v2's search
    shape. Disabled by default after measurement: persistent TT (scores
    stored from one repetition history poison probes under another —
    position repetitions are frequent in this game — 54% → 38%), LMR
    (−7 at fixed depth), SEE-lite (−19), aspiration (≈neutral, adds
    re-search time under volatile evals).
    """

    max_depth: int = 64
    soft_limit_s: float = 1.5   # stop starting new iterations past this
    hard_limit_s: float = 4.0   # abort mid-iteration past this
    use_tt: bool = True
    use_persistent_tt: bool = False  # off: repetition-history poisoning (see above)
    use_aspiration: bool = False
    use_lmr: bool = False
    use_see_pruning: bool = False
    weights: EvalWeights = field(default=DEFAULT_WEIGHTS)


@dataclass(frozen=True)
class SearchResult:
    """Outcome of a completed (or aborted) search."""

    best_move: int
    score: int
    depth: int
    nodes: int


@dataclass
class _TTEntry:
    depth: int
    flag: int
    score: int
    best_move: int
    generation: int = 0


class Searcher:
    """Runs iterative-deepening PVS over a FastPosition."""

    def __init__(
        self,
        config: SearchConfig | None = None,
        on_info: InfoCallback | None = None,
        abort_event: Event | None = None,
        tt: dict[int, _TTEntry] | None = None,
        generation: int = 0,
    ) -> None:
        self.config = config or SearchConfig()
        self.on_info = on_info
        self.abort_event = abort_event
        self.tt: dict[int, _TTEntry] = tt if tt is not None else {}
        self.generation = generation
        self.killers: list[list[int]] = [[0, 0] for _ in range(MAX_PLY)]
        self.history: list[list[list[int]]] = [
            [[0] * 64 for _ in range(64)] for _ in range(2)
        ]
        self.nodes = 0
        self._deadline_soft = 0.0
        self._deadline_hard = 0.0
        self._prev_best = 0

    # ------------------------------------------------------------------
    # Root / iterative deepening
    # ------------------------------------------------------------------

    def search(self, pos: FastPosition) -> SearchResult:
        """Return the best packed move for `pos` within the configured budget."""
        start = time.monotonic()
        self._deadline_soft = start + self.config.soft_limit_s
        self._deadline_hard = start + self.config.hard_limit_s

        root_moves = pos.legal_moves()
        if not root_moves:
            return SearchResult(0, -MATE, 0, 0)

        best_move = root_moves[0]
        best_score = -INF
        completed_depth = 0
        last_iter_s = 0.0
        try:
            for depth in range(1, self.config.max_depth + 1):
                iter_start = time.monotonic()
                if (
                    self.config.use_aspiration
                    and depth >= _ASPIRATION_START_DEPTH
                    and -MATE_BOUND < best_score < MATE_BOUND
                ):
                    alpha = best_score - _ASPIRATION_WINDOW
                    beta = best_score + _ASPIRATION_WINDOW
                    score, move = self._root_search(pos, root_moves, depth, alpha, beta)
                    if score <= alpha or score >= beta:
                        # Fell outside the window: re-search full width.
                        score, move = self._root_search(pos, root_moves, depth, -INF, INF)
                else:
                    score, move = self._root_search(pos, root_moves, depth, -INF, INF)
                completed_depth = depth
                best_move, best_score = move, score
                last_iter_s = time.monotonic() - iter_start
                if self.on_info is not None:
                    self.on_info(depth, score, self.nodes)
                if score >= MATE_BOUND or score <= -MATE_BOUND:
                    break  # forced result found; deeper search adds nothing
                remaining = self._deadline_soft - time.monotonic()
                if remaining <= 0:
                    break
                if depth >= 2 and last_iter_s * _ITERATION_GROWTH > remaining:
                    break  # the next iteration almost certainly won't finish
        except _Abort:
            pass
        return SearchResult(best_move, best_score, completed_depth, self.nodes)

    def _root_search(
        self, pos: FastPosition, moves: list[int], depth: int, alpha: int, beta: int
    ) -> tuple[int, int]:
        best_move = moves[0]
        best_score = -INF
        for i, move in enumerate(self._order(pos, moves, self._prev_best, 0)):
            pos.make(move)
            if i == 0:
                score = -self._pvs(pos, depth - 1, -beta, -alpha, 1)
            else:
                score = -self._pvs(pos, depth - 1, -alpha - 1, -alpha, 1)
                if alpha < score:
                    score = -self._pvs(pos, depth - 1, -beta, -alpha, 1)
            pos.undo()
            if score > best_score:
                best_score = score
                best_move = move
            if score > alpha:
                alpha = score
        self._prev_best = best_move
        self._store(pos.key, depth, _TT_EXACT, best_score, best_move)
        return best_score, best_move

    # ------------------------------------------------------------------
    # PVS / quiescence
    # ------------------------------------------------------------------

    def _pvs(self, pos: FastPosition, depth: int, alpha: int, beta: int, ply: int) -> int:
        self.nodes += 1
        if self.nodes & _NODE_MASK == 0:
            self._check_time()
        if ply >= MAX_PLY - 1:
            return evaluate_fast(pos, self.config.weights)

        if ply > 0:
            if pos.winner() is not None:
                # The side to move has lost (the previous move won the game).
                return -MATE + ply
            if pos.is_repetition() or pos.move_count >= MAX_PLIES:
                return 0
            # Mate-distance pruning.
            alpha = max(alpha, -MATE + ply)
            beta = min(beta, MATE - ply - 1)
            if alpha >= beta:
                return alpha

        tt_move = 0
        if self.config.use_tt:
            entry = self.tt.get(pos.key)
            if entry is not None:
                tt_move = entry.best_move
                if ply > 0 and entry.depth >= depth:
                    score = self._from_tt(entry.score, ply)
                    if entry.flag == _TT_EXACT:
                        return score
                    if entry.flag == _TT_LOWER:
                        alpha = max(alpha, score)
                    else:
                        beta = min(beta, score)
                    if alpha >= beta:
                        return score

        if depth <= 0:
            return self._quiescence(pos, alpha, beta, ply, _QUIESCENCE_PLIES)

        moves = pos.legal_moves()
        if not moves:
            return -MATE + ply  # stalemate is a loss (model semantics)

        original_alpha = alpha
        best_move = 0
        best_score = -INF
        enemy_den = tables.DEN_IDX[pos.side.opponent()]
        for i, move in enumerate(self._order(pos, moves, tt_move, ply)):
            to_idx = move_to(move)
            is_capture = pos.cells[to_idx] != EMPTY
            pos.make(move)
            if i == 0:
                score = -self._pvs(pos, depth - 1, -beta, -alpha, ply + 1)
            else:
                reduction = 0
                if (
                    self.config.use_lmr
                    and depth >= _LMR_MIN_DEPTH
                    and i >= _LMR_MIN_MOVE_INDEX
                    and not is_capture
                    and to_idx != enemy_den
                ):
                    reduction = 1 if i < 6 else 2
                    reduction = min(reduction, depth - 2)
                if reduction > 0:
                    score = -self._pvs(pos, depth - 1 - reduction, -alpha - 1, -alpha, ply + 1)
                    if score > alpha:
                        score = -self._pvs(pos, depth - 1, -beta, -alpha, ply + 1)
                else:
                    score = -self._pvs(pos, depth - 1, -alpha - 1, -alpha, ply + 1)
                    if alpha < score < beta:
                        score = -self._pvs(pos, depth - 1, -beta, -alpha, ply + 1)
            pos.undo()

            if score > best_score:
                best_score = score
                best_move = move
            if score > alpha:
                alpha = score
            if alpha >= beta:
                if not is_capture and ply < MAX_PLY:
                    killers = self.killers[ply]
                    if killers[0] != move:
                        killers[1] = killers[0]
                        killers[0] = move
                    self.history[pos.side.value][move_from(move)][move_to(move)] += depth * depth
                self._store(pos.key, depth, _TT_LOWER, self._to_tt(best_score, ply), move)
                return best_score

        flag = _TT_EXACT if best_score > original_alpha else _TT_UPPER
        self._store(pos.key, depth, flag, self._to_tt(best_score, ply), best_move)
        return best_score

    def _quiescence(self, pos: FastPosition, alpha: int, beta: int, ply: int, qleft: int) -> int:
        self.nodes += 1
        if self.nodes & _NODE_MASK == 0:
            self._check_time()
        if ply >= MAX_PLY - 1:
            return evaluate_fast(pos, self.config.weights)
        if pos.winner() is not None:
            return -MATE + ply
        if pos.is_repetition() or pos.move_count >= MAX_PLIES:
            return 0

        mg_values = self.config.weights.mg_values
        stand_pat = evaluate_fast(pos, self.config.weights)
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat
        if qleft <= 0:
            return alpha

        enemy_den = tables.DEN_IDX[pos.side.opponent()]
        own_trap = Terrain.TRAP_RED if pos.side is Side.RED else Terrain.TRAP_BLUE
        captures = [
            m
            for m in pos.legal_moves()
            if pos.cells[move_to(m)] != EMPTY or move_to(m) == enemy_den
        ]
        if not captures:
            if not pos.has_legal_move():
                return -MATE + ply
            return alpha

        cells = pos.cells

        def _capture_score(move: int) -> int:
            victim = cells[move_to(move)]
            if victim != EMPTY:
                return mg_values[rank_of(victim)] * 16 - rank_of(cells[move_from(move)])
            return 10_000  # den-entry move wins immediately; search it first

        captures.sort(key=_capture_score, reverse=True)
        for move in captures:
            to_idx = move_to(move)
            captured = cells[to_idx]
            victim = mg_values[rank_of(captured)] if captured != EMPTY else 0
            if stand_pat + victim + _DELTA_MARGIN < alpha:
                continue  # delta pruning: capture cannot raise alpha
            if (
                self.config.use_see_pruning
                and captured != EMPTY
                and tables.TERRAIN[to_idx] is not own_trap
                and mg_values[rank_of(cells[move_from(move)])] > victim + _SEE_MARGIN
            ):
                continue  # SEE-lite: do not search hopeless captures
            pos.make(move)
            score = -self._quiescence(pos, -beta, -alpha, ply + 1, qleft - 1)
            pos.undo()
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        return alpha

    # ------------------------------------------------------------------
    # Move ordering / TT helpers / time
    # ------------------------------------------------------------------

    def _order(self, pos: FastPosition, moves: list[int], tt_move: int, ply: int) -> list[int]:
        cells = pos.cells
        killers = self.killers[ply]
        history = self.history[pos.side.value]
        mg_values = self.config.weights.mg_values

        def score(move: int) -> int:
            if move == tt_move:
                return 10_000_000
            f = move & 63
            t = move >> 6
            victim = cells[t]
            if victim != EMPTY:
                return 1_000_000 + mg_values[rank_of(victim)] * 16 - rank_of(cells[f])
            if killers[0] == move:
                return 500_000
            if killers[1] == move:
                return 490_000
            return history[f][t]

        return sorted(moves, key=score, reverse=True)

    def _store(self, key: int, depth: int, flag: int, score: int, move: int) -> None:
        if not self.config.use_tt:
            return
        old = self.tt.get(key)
        if old is None or old.generation != self.generation or depth >= old.depth:
            self.tt[key] = _TTEntry(depth, flag, score, move, self.generation)

    @staticmethod
    def _to_tt(score: int, ply: int) -> int:
        if score > MATE_BOUND:
            return score + ply
        if score < -MATE_BOUND:
            return score - ply
        return score

    @staticmethod
    def _from_tt(score: int, ply: int) -> int:
        if score > MATE_BOUND:
            return score - ply
        if score < -MATE_BOUND:
            return score + ply
        return score

    def _check_time(self) -> None:
        if self.abort_event is not None and self.abort_event.is_set():
            raise _Abort
        if time.monotonic() >= self._deadline_hard:
            raise _Abort
