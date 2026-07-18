"""Main application window."""

from __future__ import annotations

from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QDialog,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QWidget,
)

from jungle.engine.ai import AI, AIWorker
from jungle.gui.board_view import BoardView
from jungle.gui.dialogs import (
    DIFFICULTY_MEDIUM,
    MODE_AI_VS_AI,
    MODE_HUMAN_VS_AI,
    GameOverDialog,
    NewGameDialog,
)
from jungle.gui.styles import MAIN_WINDOW_QSS
from jungle.model.board import Board, GameState, IllegalMoveError, Move
from jungle.model.constants import Side

# Difficulty presets: name -> (max search depth, soft time limit per move).
DIFFICULTY_PRESETS: dict[str, tuple[int, float]] = {
    "easy": (3, 0.5),
    "medium": (6, 1.5),
    "hard": (12, 2.5),
}

_SIDE_NAMES = {Side.RED: "RED", Side.BLUE: "BLUE"}


class MainWindow(QMainWindow):
    """The main Jungle game window."""

    def __init__(
        self,
        ai_first: bool = False,
        ai_depth: int | None = None,
        flipped: bool = False,
        strength: str = DIFFICULTY_MEDIUM,
        time_limit: float | None = None,
        ai_vs_ai: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Jungle / Dou Shou Qi")
        self.setStyleSheet(MAIN_WINDOW_QSS)
        self.resize(640, 800)

        self._strength = strength if strength in DIFFICULTY_PRESETS else DIFFICULTY_MEDIUM
        self._ai_depth = ai_depth
        self._time_limit = time_limit
        self._mode = MODE_AI_VS_AI if ai_vs_ai else MODE_HUMAN_VS_AI
        self._human_side = Side.BLUE if ai_first else Side.RED
        self._ai_side = Side.RED if ai_first else Side.BLUE
        self._ai = self._make_ai()
        self._ai_worker: AIWorker | None = None
        self._ai_thinking = False
        self._generation = 0
        self._game_over_dialog: GameOverDialog | None = None

        self._board_view = BoardView(self)
        self._board_view.move_requested.connect(self._on_human_move)
        self._board_view.status_message.connect(self._show_status)
        self.setCentralWidget(self._board_view)

        self._status_bar = QStatusBar(self)
        self.setStatusBar(self._status_bar)

        self._setup_menu()
        self._start_new_game(flipped=flipped)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _make_ai(self) -> AI:
        depth, limit = DIFFICULTY_PRESETS[self._strength]
        if self._ai_depth is not None:
            depth = self._ai_depth
        if self._time_limit is not None:
            limit = self._time_limit
        return AI(self._ai_side, depth=depth, time_limit_s=limit)

    def _setup_menu(self) -> None:
        menu_bar = self.menuBar()
        if menu_bar is None:
            return

        game_menu = menu_bar.addMenu("Game")
        if game_menu is None:
            return

        new_action = QAction("New Game...", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._prompt_new_game)
        game_menu.addAction(new_action)

        flip_action = QAction("Flip Board", self)
        flip_action.setShortcut("Ctrl+F")
        flip_action.triggered.connect(self._toggle_flip)
        game_menu.addAction(flip_action)

        game_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        game_menu.addAction(quit_action)

        help_menu = menu_bar.addMenu("Help")
        if help_menu is None:
            return
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _start_new_game(
        self,
        ai_first: bool | None = None,
        flipped: bool | None = None,
        mode: str | None = None,
        difficulty: str | None = None,
    ) -> None:
        self._abort_ai()
        self._generation += 1

        if ai_first is not None:
            self._human_side = Side.BLUE if ai_first else Side.RED
            self._ai_side = Side.RED if ai_first else Side.BLUE
        if mode is not None:
            self._mode = mode
        if difficulty is not None and difficulty in DIFFICULTY_PRESETS:
            self._strength = difficulty
        self._ai = self._make_ai()

        if flipped is not None:
            self._board_view.set_flipped(flipped)

        state = GameState(board=Board.starting(), current_side=Side.RED)
        self._board_view.set_state(state)
        self._board_view.set_last_move(None)
        if self._game_over_dialog is not None:
            self._game_over_dialog.close()
            self._game_over_dialog = None
        self._update_status()

        if self._ai_turn(state):
            self._request_ai_move(state)

    def _prompt_new_game(self) -> None:
        dialog = NewGameDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        ai_vs_ai = dialog.mode() == MODE_AI_VS_AI
        self._start_new_game(
            ai_first=not dialog.human_first(),
            mode=dialog.mode(),
            difficulty=dialog.difficulty(),
        )

    def _toggle_flip(self) -> None:
        self._board_view.set_flipped(not self._board_view._flipped)
        self._update_status()

    # ------------------------------------------------------------------
    # Move flow
    # ------------------------------------------------------------------

    def _ai_turn(self, state: GameState) -> bool:
        if self._mode == MODE_AI_VS_AI:
            return True
        return state.current_side is self._ai_side

    def _on_human_move(self, move: Move) -> None:
        if self._mode == MODE_AI_VS_AI or self._ai_thinking:
            return
        state = self._board_view.state()
        if state is None or state.current_side is not self._human_side:
            return
        self._apply_move(move)

    def _apply_move(self, move: Move) -> None:
        state = self._board_view.state()
        if state is None:
            return
        try:
            new_state = state.after_move(move)
        except IllegalMoveError as exc:
            self._show_status(str(exc))
            return

        self._board_view.set_state(new_state)
        self._board_view.set_last_move(move)
        self._update_status()

        if new_state.winner is not None or new_state.draw:
            self._show_game_over(new_state)
            return

        if self._ai_turn(new_state):
            self._request_ai_move(new_state)

    def _request_ai_move(self, state: GameState) -> None:
        if self._ai_thinking:
            return
        self._ai_thinking = True
        self._show_status(f"AI ({self._strength}) thinking...")

        worker = AIWorker(self._ai, state)
        worker.setProperty("generation", self._generation)
        worker.move_chosen.connect(self._on_ai_move_chosen)
        worker.search_info.connect(self._on_search_info)
        worker.error.connect(self._on_ai_error)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(lambda: self._on_worker_finished(worker))
        self._ai_worker = worker
        worker.start()

    def _on_worker_finished(self, worker: AIWorker) -> None:
        # Drop our reference when the current worker is done so we never
        # touch it after Qt deletes its C++ object (deleteLater above).
        if self._ai_worker is worker:
            self._ai_worker = None
            self._ai_thinking = False

    def _on_ai_move_chosen(self, move: Move | None) -> None:
        worker = self.sender()
        self._ai_thinking = False
        # Identity check first: `is` never touches the C++ object, so this is
        # safe even if the sender was already deleted by Qt.
        if worker is not self._ai_worker:
            return  # stale result from a superseded worker
        if move is None:
            self._show_status("AI has no legal moves")
            return
        self._apply_move(move)

    def _on_search_info(self, depth: int, score_cp: int, nodes: int) -> None:
        if self.sender() is not self._ai_worker:
            return  # stale progress from a superseded worker
        self._show_status(
            f"AI ({self._strength}) thinking... d={depth} "
            f"{score_cp / 100:+.2f} {nodes // 1000}kN"
        )

    def _on_ai_error(self, message: str) -> None:
        self._ai_thinking = False
        self._show_status(f"AI error: {message}")

    def _abort_ai(self) -> None:
        worker = self._ai_worker
        # Clear first: any queued signals from the old worker are then
        # discarded by the identity checks in the slots.
        self._ai_worker = None
        self._ai_thinking = False
        if worker is not None:
            try:
                if worker.isRunning():
                    worker.abort()
                    worker.wait(2000)
            except RuntimeError:
                pass  # Qt already deleted the C++ object (deleteLater)

    # ------------------------------------------------------------------
    # Status / dialogs
    # ------------------------------------------------------------------

    def _update_status(self) -> None:
        state = self._board_view.state()
        if state is None:
            self._show_status("Welcome to Jungle")
            return
        if state.winner is not None:
            self._show_status(f"{self._side_label(state.winner)} wins!")
            return
        if state.draw:
            self._show_status("Draw")
            return
        flip = " (flipped)" if self._board_view._flipped else ""
        if self._mode == MODE_AI_VS_AI:
            self._show_status(f"AI vs AI — {_SIDE_NAMES[state.current_side]} to move{flip}")
            return
        turn = "Human" if state.current_side is self._human_side else "AI"
        self._show_status(f"Turn: {turn}{flip}")

    def _side_label(self, side: Side) -> str:
        if self._mode == MODE_AI_VS_AI:
            return f"AI ({_SIDE_NAMES[side]})"
        return "Human" if side is self._human_side else "AI"

    def _show_game_over(self, state: GameState) -> None:
        self._abort_ai()
        if state.winner is not None:
            text = f"{self._side_label(state.winner)} wins!"
        else:
            text = "Draw"
        dialog = GameOverDialog(text, self)
        dialog.accepted.connect(self._prompt_new_game)
        # Rejecting ("Stay" or the dialog's close button) only dismisses the
        # dialog — the window and the final position stay open.
        dialog.finished.connect(self._on_game_over_dialog_finished)
        self._game_over_dialog = dialog
        dialog.open()  # window-modal but non-blocking: the event loop stays alive

    def _on_game_over_dialog_finished(self, _result: int) -> None:
        self._game_over_dialog = None

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Jungle",
            "Jungle / Dou Shou Qi\n\nA Windows desktop board game with AI.\n",
        )

    def _show_status(self, message: str) -> None:
        self._status_bar.showMessage(message)

    def closeEvent(self, event) -> None:
        self._abort_ai()
        event.accept()
