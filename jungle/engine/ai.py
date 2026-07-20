"""Public AI interface: difficulty presets, synchronous chooser, QThread worker."""

from __future__ import annotations

import threading
from typing import Optional

from PySide6.QtCore import QThread, Signal

from jungle.engine.core import FastPosition, to_model_move
from jungle.engine.evaluation import DEFAULT_WEIGHTS, EvalWeights
from jungle.engine.search import SearchConfig, Searcher, SearchResult
from jungle.model.board import GameState, Move

DIFFICULTY_PRESETS: dict[str, SearchConfig] = {
    "easy": SearchConfig(max_depth=2, soft_limit_s=0.3, hard_limit_s=0.8),
    "medium": SearchConfig(max_depth=4, soft_limit_s=1.0, hard_limit_s=2.5),
    "hard": SearchConfig(max_depth=6, soft_limit_s=2.0, hard_limit_s=5.0),
}

STRENGTH_NAMES = tuple(DIFFICULTY_PRESETS)


class NoLegalMoveError(RuntimeError):
    """Raised when the AI is asked to move in a terminal position."""


class AI:
    """Synchronous move chooser. A fresh ``Searcher`` (and therefore a fresh
    transposition table) is built for every move — see ``engine.search`` for
    why persistent TTs are banned on this game."""

    def __init__(
        self,
        strength: str = "medium",
        depth: Optional[int] = None,
        time_limit: Optional[float] = None,
        weights: Optional[EvalWeights] = None,
    ) -> None:
        if strength not in DIFFICULTY_PRESETS:
            raise ValueError(f"unknown strength {strength!r}; expected one of {STRENGTH_NAMES}")
        base = DIFFICULTY_PRESETS[strength]
        max_depth = depth if depth is not None else base.max_depth
        soft = time_limit if time_limit is not None else base.soft_limit_s
        hard = time_limit * 2.5 if time_limit is not None else base.hard_limit_s
        self.config = SearchConfig(
            max_depth=max_depth,
            soft_limit_s=soft,
            hard_limit_s=hard,
            weights=weights if weights is not None else DEFAULT_WEIGHTS,
        )

    def choose_move(self, state: GameState) -> tuple[Move, SearchResult]:
        pos = FastPosition.from_game_state(state)
        result = Searcher(self.config).search(pos)
        best = result.best_move
        if best == 0:
            legal = pos.legal_moves()
            if not legal:
                raise NoLegalMoveError("no legal moves — the game is over")
            best = legal[0]
        return to_model_move(best), result


class AIWorker(QThread):
    """Runs the AI off the GUI thread so the board stays responsive.

    Emits ``result_ready(Move)`` with the chosen move (unless aborted) and
    ``search_info(depth, score, nodes)`` after each completed iteration for
    the status bar. All search state lives inside ``run()``; the worker only
    reads the immutable ``GameState`` snapshot it was given.
    """

    result_ready = Signal(object)
    search_info = Signal(int, int, int)

    def __init__(self, ai: AI, state: GameState, parent=None) -> None:
        super().__init__(parent)
        self._ai = ai
        self._state = state
        self._abort = threading.Event()
        self.result: Optional[Move] = None

    def run(self) -> None:
        pos = FastPosition.from_game_state(self._state)
        searcher = Searcher(
            self._ai.config,
            abort_event=self._abort,
            info_callback=self._on_info,
        )
        result = searcher.search(pos)
        if self._abort.is_set():
            return
        best = result.best_move
        if best == 0:
            legal = pos.legal_moves()
            if not legal:
                return  # terminal position; the GUI's game-over check handles it
            best = legal[0]
        self.result = to_model_move(best)
        self.result_ready.emit(self.result)

    def abort(self) -> None:
        """Ask the search to stop promptly; ``run`` then returns nothing."""
        self._abort.set()

    def _on_info(self, depth: int, score: int, nodes: int) -> None:
        if not self._abort.is_set():
            self.search_info.emit(depth, score, nodes)
