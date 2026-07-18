"""AI engine shell: converts model states to the fast core and runs the search."""

from __future__ import annotations

import threading

from PyQt6.QtCore import QThread, pyqtSignal

from jungle.engine.core import FastPosition, to_model_move
from jungle.engine.search import SearchConfig, Searcher, _TTEntry
from jungle.model.board import GameState, Move
from jungle.model.constants import Side

DEFAULT_TIME_LIMIT_S = 1.5


class AI:
    """Jungle AI: iterative-deepening PVS over the fast engine core.

    `depth` caps the search depth; `time_limit_s` sets the soft wall-clock
    budget per move (the hard abort fires at 2.5x the soft limit). A full
    `SearchConfig` can be injected instead (used by the gauntlet to replay
    previous engine generations). The transposition table persists across
    moves with generation aging unless disabled in the config. The search
    is deterministic when it reaches `max_depth` within the time budget.
    """

    def __init__(
        self,
        side: Side,
        depth: int = 3,
        time_limit_s: float | None = None,
        config: SearchConfig | None = None,
    ) -> None:
        self.side = side
        if config is None:
            soft = time_limit_s if time_limit_s is not None else DEFAULT_TIME_LIMIT_S
            config = SearchConfig(
                max_depth=max(1, depth),
                soft_limit_s=soft,
                hard_limit_s=soft * 2.5,
            )
        self.config = config
        self._tt: dict[int, _TTEntry] = {}
        self._tt_generation = 0

    def choose_move(
        self,
        state: GameState,
        on_info=None,
        abort_event: threading.Event | None = None,
    ) -> Move | None:
        """Return the best move for the side to move, or None if unavailable."""
        if state.winner is not None or state.draw:
            return None
        pos = FastPosition.from_game_state(state)
        if not pos.has_legal_move():
            return None
        self._tt_generation = (self._tt_generation + 1) & 0xFF
        searcher = Searcher(
            self.config,
            on_info=on_info,
            abort_event=abort_event,
            tt=self._tt if self.config.use_persistent_tt else None,
            generation=self._tt_generation,
        )
        result = searcher.search(pos)
        if result.best_move == 0 and result.depth == 0:
            return None
        return to_model_move(result.best_move)


class AIWorker(QThread):
    """Run the AI search in a background thread."""

    move_chosen = pyqtSignal(object)
    search_info = pyqtSignal(int, int, int)  # depth, score_cp, nodes
    error = pyqtSignal(str)

    def __init__(self, ai: AI, state: GameState, parent=None) -> None:
        super().__init__(parent)
        self.ai = ai
        self.state = state
        self._abort = threading.Event()

    def abort(self) -> None:
        """Ask the search to stop and discard the result (new game / quit)."""
        self._abort.set()

    def run(self) -> None:
        try:
            move = self.ai.choose_move(
                self.state,
                on_info=lambda d, s, n: self.search_info.emit(d, s, n),
                abort_event=self._abort,
            )
            # An aborted worker's result is stale by definition (a new game
            # or quit superseded it) — never emit it into the GUI.
            if not self._abort.is_set():
                self.move_chosen.emit(move)
        except Exception as exc:  # pragma: no cover - safety net
            if not self._abort.is_set():
                self.error.emit(str(exc))
