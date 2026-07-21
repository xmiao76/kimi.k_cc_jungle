"""Main window: wires the board view, game state, AI worker, and menus."""

from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QLabel, QMainWindow, QWidget

from jungle.engine.ai import AI, AIWorker
from jungle.gui.board_view import BoardView
from jungle.gui.dialogs import (
    MODE_AI_VS_AI,
    MODE_HUMAN_VS_AI,
    GameOverDialog,
    NewGameDialog,
)
from jungle.model.board import MAX_PLIES, GameState, Move
from jungle.model.constants import Side

_WIN_REASONS = {
    "den": "entered the enemy den ★",
    "elimination": "captured all enemy pieces",
    "no_moves": "the opponent has no legal moves",
}
_DRAW_REASONS = {
    "repetition": "threefold repetition",
    "move_limit": f"{MAX_PLIES} plies without a result",
}


class MainWindow(QMainWindow):
    def __init__(
        self,
        ai_first: bool = False,
        ai_depth: Optional[int] = None,
        flipped: bool = False,
        strength: str = "medium",
        time_limit: Optional[float] = None,
        ai_vs_ai: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Jungle — Dou Shou Qi 鬥獸棋")

        self._strength = strength
        self._ai_depth = ai_depth
        self._time_limit = time_limit
        self._ai = AI(strength=strength, depth=ai_depth, time_limit=time_limit)

        self._state = GameState.starting()
        self._human_side: Optional[Side] = None if ai_vs_ai else (Side.BLUE if ai_first else Side.RED)
        self._worker: Optional[AIWorker] = None
        self._game_over_dialog: Optional[GameOverDialog] = None

        self._board_view = BoardView(self)
        self._board_view.set_flipped(flipped)
        self.setCentralWidget(self._board_view)

        self._turn_label = QLabel()
        self._ai_info_label = QLabel()
        self.statusBar().addWidget(self._turn_label, 1)
        self.statusBar().addPermanentWidget(self._ai_info_label)

        self._build_menus()
        self._board_view.move_requested.connect(self._on_move_requested)
        self._board_view.status_message.connect(self._on_status_message)
        self._board_view.set_state(self._state)
        self.resize(640, 780)

        # Covers AI-first / AI-vs-AI: the AI may already be on move.
        self._maybe_start_ai()

    # -- menus ----------------------------------------------------------------

    def _build_menus(self) -> None:
        game_menu = self.menuBar().addMenu("&Game")
        new_action = QAction("&New Game…", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._prompt_new_game)
        game_menu.addAction(new_action)
        game_menu.addSeparator()
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        game_menu.addAction(quit_action)

        view_menu = self.menuBar().addMenu("&View")
        self._flip_action = QAction("&Flip Board", self, checkable=True)
        self._flip_action.setShortcut("Ctrl+F")
        self._flip_action.setChecked(self._board_view.is_flipped())
        self._flip_action.toggled.connect(self._on_flip_toggled)
        view_menu.addAction(self._flip_action)

        ai_menu = self.menuBar().addMenu("&AI")
        group = QActionGroup(self)
        self._strength_actions: dict[str, QAction] = {}
        for name in ("easy", "medium", "hard"):
            action = QAction(name.capitalize(), self, checkable=True)
            action.triggered.connect(lambda checked, n=name: self._on_strength_changed(n))
            group.addAction(action)
            ai_menu.addAction(action)
            self._strength_actions[name] = action
        self._sync_strength_actions()

    def _sync_strength_actions(self) -> None:
        """Check the AI-menu entry matching ``self._strength``.

        Needed when the strength changes outside the menu itself (New Game
        dialog, CLI start): the menu is the only difficulty indicator in the
        game UI, so it must never contradict the AI actually in play.
        ``setChecked`` emits ``toggled`` (not ``triggered``), and the group is
        exclusive, so this neither recurses nor leaves two entries checked.
        """
        for name, action in self._strength_actions.items():
            action.setChecked(name == self._strength)

    # -- game flow --------------------------------------------------------------

    def _maybe_start_ai(self) -> None:
        if self._worker is not None:
            return  # an AI worker is already thinking; never run two at once
        if self._state.is_game_over:
            self._show_game_over()
            return
        human_turn = self._human_side is not None and self._state.current_side is self._human_side
        self._board_view.set_input_enabled(human_turn)
        self._update_turn_label(ai_thinking=not human_turn)
        if human_turn:
            return
        worker = AIWorker(self._ai, self._state, parent=self)
        worker.result_ready.connect(self._on_ai_result)
        worker.search_info.connect(self._on_search_info)
        self._worker = worker
        self._ai_info_label.setText("")
        worker.start()

    def _on_move_requested(self, move: Move) -> None:
        if self._worker is not None:
            return  # AI is thinking; input should already be disabled
        if self._human_side is None or self._state.current_side is not self._human_side:
            return
        self._apply_move(move)

    def _on_ai_result(self, move: Move) -> None:
        worker = self.sender()
        if worker is not self._worker:
            return  # stale result from an aborted game
        self._worker = None
        worker.deleteLater()
        self._apply_move(move)

    def _apply_move(self, move: Move) -> None:
        captured = self._state.board.piece_at(move.to_pos) is not None
        self._state = self._state.apply_move(move)
        self._board_view.set_state(self._state, last_move=move, last_capture=captured)
        if self._state.is_game_over:
            self._board_view.set_input_enabled(False)
            self._show_game_over()
        else:
            self._maybe_start_ai()

    def _abort_ai(self) -> None:
        """Stop any running AI worker and wait for it to finish."""
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.abort()
            worker.wait(3000)
            worker.deleteLater()

    # -- game over --------------------------------------------------------------

    def _game_over_message(self) -> str:
        winner = self._state.winner
        reason = self._state.game_over_reason
        if winner is not None:
            detail = _WIN_REASONS.get(reason, reason or "")
            if self._human_side is None:
                return f"{winner.name} wins — {detail}!"
            if winner is self._human_side:
                return f"You win! 🎉 ({detail})"
            return f"The AI wins — {detail}."
        detail = _DRAW_REASONS.get(reason, reason or "")
        return f"Draw — {detail}."

    def _show_game_over(self) -> None:
        self._abort_ai()
        self._board_view.set_input_enabled(False)
        self._turn_label.setText("Game over")
        self._ai_info_label.setText("")
        dialog = GameOverDialog(self._game_over_message(), parent=self)
        dialog.new_game_requested.connect(self._prompt_new_game)
        dialog.quit_requested.connect(self.close)
        self._game_over_dialog = dialog
        dialog.show()  # non-modal by design — never exec()

    # -- slots ------------------------------------------------------------------

    def _prompt_new_game(self) -> None:
        dialog = NewGameDialog(
            self,
            mode=MODE_AI_VS_AI if self._human_side is None else MODE_HUMAN_VS_AI,
            ai_first=self._human_side is Side.BLUE,
            strength=self._strength,
        )
        if dialog.exec() != NewGameDialog.DialogCode.Accepted:
            return
        self.start_new_game(mode=dialog.mode, ai_first=dialog.ai_first, strength=dialog.strength)

    def start_new_game(self, mode: str, ai_first: bool, strength: str) -> None:
        """Reset everything and start a fresh game (test-friendly entry)."""
        self._abort_ai()
        self._strength = strength
        self._ai = AI(strength=strength, depth=self._ai_depth, time_limit=self._time_limit)
        self._sync_strength_actions()
        self._state = GameState.starting()
        self._human_side = None if mode == MODE_AI_VS_AI else (Side.BLUE if ai_first else Side.RED)
        if self._game_over_dialog is not None:
            self._game_over_dialog.close()
            self._game_over_dialog = None
        self._board_view.set_state(self._state)
        self._board_view.clear_selection()
        self._update_turn_label()
        self._maybe_start_ai()

    def _on_flip_toggled(self, checked: bool) -> None:
        # Purely a display option: game state, sides, and turn are untouched.
        self._board_view.set_flipped(checked)

    def _on_strength_changed(self, name: str) -> None:
        self._strength = name
        self._ai = AI(strength=name, depth=self._ai_depth, time_limit=self._time_limit)
        # No-op when the menu itself initiated the change; keeps the menu
        # truthful for any other caller (tests, future shortcuts).
        self._sync_strength_actions()

    def _on_search_info(self, depth: int, score: int, nodes: int) -> None:
        self._ai_info_label.setText(f"d={depth}  {score / 100:+.2f}  {nodes / 1000:.1f}kN")

    def _on_status_message(self, text: str) -> None:
        self.statusBar().showMessage(text, 3000)

    def _update_turn_label(self, ai_thinking: bool = False) -> None:
        side = self._state.current_side
        who = "RED" if side is Side.RED else "BLUE"
        if self._human_side is None:
            self._turn_label.setText(f"AI vs AI — {who} to move" + (" 🤖" if ai_thinking else ""))
        elif side is self._human_side:
            self._turn_label.setText(f"Your turn ({who})")
        else:
            self._turn_label.setText(f"AI thinking… ({who})")

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._abort_ai()
        super().closeEvent(event)
