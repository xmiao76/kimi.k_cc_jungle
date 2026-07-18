"""Dialogs for game setup and game-over notifications."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

MODE_HUMAN_VS_AI = "human_vs_ai"
MODE_AI_VS_AI = "ai_vs_ai"

DIFFICULTY_EASY = "easy"
DIFFICULTY_MEDIUM = "medium"
DIFFICULTY_HARD = "hard"


class NewGameDialog(QDialog):
    """Dialog to choose game mode, first player, and difficulty."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Game")
        self.setModal(True)

        self._layout = QVBoxLayout(self)

        mode_box = QGroupBox("Mode", self)
        mode_layout = QVBoxLayout(mode_box)
        self._mode_human = QRadioButton("Human vs AI")
        self._mode_human.setChecked(True)
        self._mode_ai = QRadioButton("AI vs AI")
        mode_layout.addWidget(self._mode_human)
        mode_layout.addWidget(self._mode_ai)
        self._layout.addWidget(mode_box)

        first_box = QGroupBox("Who moves first?", self)
        first_layout = QVBoxLayout(first_box)
        self._human_first = QRadioButton("Human first")
        self._human_first.setChecked(True)
        self._ai_first = QRadioButton("AI first")
        first_layout.addWidget(self._human_first)
        first_layout.addWidget(self._ai_first)
        self._first_box = first_box
        self._layout.addWidget(first_box)

        level_box = QGroupBox("Difficulty", self)
        level_layout = QVBoxLayout(level_box)
        self._level_easy = QRadioButton("Easy (fast)")
        self._level_medium = QRadioButton("Medium")
        self._level_medium.setChecked(True)
        self._level_hard = QRadioButton("Hard (slow)")
        level_layout.addWidget(self._level_easy)
        level_layout.addWidget(self._level_medium)
        level_layout.addWidget(self._level_hard)
        self._layout.addWidget(level_box)

        self._mode_ai.toggled.connect(self._on_mode_toggled)
        self._on_mode_toggled(False)

        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)
        self._layout.addWidget(self._button_box)

    def _on_mode_toggled(self, ai_vs_ai: bool) -> None:
        # Side choice is meaningless when the AI plays both sides.
        self._first_box.setEnabled(not ai_vs_ai)

    def human_first(self) -> bool:
        return self._human_first.isChecked()

    def mode(self) -> str:
        return MODE_AI_VS_AI if self._mode_ai.isChecked() else MODE_HUMAN_VS_AI

    def difficulty(self) -> str:
        if self._level_easy.isChecked():
            return DIFFICULTY_EASY
        if self._level_hard.isChecked():
            return DIFFICULTY_HARD
        return DIFFICULTY_MEDIUM


class GameOverDialog(QDialog):
    """Dialog shown when the game ends.

    "New Game" accepts (start over); "Stay" rejects (dismiss only — the
    application must never quit just because a game ended).
    """

    def __init__(self, result_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Game Over")
        self.setModal(True)

        layout = QVBoxLayout(self)
        label = QLabel(result_text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        button_layout = QHBoxLayout()
        new_game_btn = QPushButton("New Game")
        stay_btn = QPushButton("Stay")
        new_game_btn.clicked.connect(self.accept)
        stay_btn.clicked.connect(self.reject)
        button_layout.addWidget(new_game_btn)
        button_layout.addWidget(stay_btn)
        layout.addLayout(button_layout)

    def wants_new_game(self) -> bool:
        return self.result() == QDialog.DialogCode.Accepted
