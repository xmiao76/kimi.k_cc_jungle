"""Dialogs: new-game options and the (always non-modal) game-over notice.

The game-over dialog must never be exec()'d: long modal Qt sessions inside
tests triggered intermittent 0x8001010d crashes on Windows, so it is shown
with ``show()`` and reports through signals instead.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from jungle.engine.ai import STRENGTH_NAMES

MODE_HUMAN_VS_AI = "human_vs_ai"
MODE_AI_VS_AI = "ai_vs_ai"


class NewGameDialog(QDialog):
    """Collects game mode, who moves first, and difficulty."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        mode: str = MODE_HUMAN_VS_AI,
        ai_first: bool = False,
        strength: str = "medium",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Game")
        self.setModal(True)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Human vs AI", MODE_HUMAN_VS_AI)
        self.mode_combo.addItem("AI vs AI", MODE_AI_VS_AI)
        self.mode_combo.setCurrentIndex(0 if mode == MODE_HUMAN_VS_AI else 1)
        form.addRow("Mode", self.mode_combo)

        self.first_combo = QComboBox()
        self.first_combo.addItem("Human moves first", False)
        self.first_combo.addItem("AI moves first", True)
        self.first_combo.setCurrentIndex(1 if ai_first else 0)
        form.addRow("First move", self.first_combo)

        self.strength_combo = QComboBox()
        for name in STRENGTH_NAMES:
            self.strength_combo.addItem(name.capitalize(), name)
        self.strength_combo.setCurrentIndex(STRENGTH_NAMES.index(strength))
        form.addRow("Difficulty", self.strength_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.mode_combo.currentIndexChanged.connect(self._sync_first_enabled)
        self._sync_first_enabled()

    def _sync_first_enabled(self) -> None:
        self.first_combo.setEnabled(self.mode_combo.currentData() == MODE_HUMAN_VS_AI)

    @property
    def mode(self) -> str:
        return self.mode_combo.currentData()

    @property
    def ai_first(self) -> bool:
        return bool(self.first_combo.currentData())

    @property
    def strength(self) -> str:
        return self.strength_combo.currentData()


class GameOverDialog(QDialog):
    """Non-modal result notice with New Game / Quit actions.

    Shown via ``show()``; never ``exec()``.
    """

    new_game_requested = Signal()
    quit_requested = Signal()

    def __init__(self, message: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Game Over")
        self.setModal(False)

        layout = QVBoxLayout(self)
        label = QLabel(message)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        layout.addWidget(label)

        row = QHBoxLayout()
        self.new_game_button = QPushButton("New Game")
        self.quit_button = QPushButton("Quit")
        row.addWidget(self.new_game_button)
        row.addWidget(self.quit_button)
        layout.addLayout(row)

        self.new_game_button.clicked.connect(self._on_new_game)
        self.quit_button.clicked.connect(self._on_quit)

    def _on_new_game(self) -> None:
        self.new_game_requested.emit()
        self.close()

    def _on_quit(self) -> None:
        self.quit_requested.emit()
        self.close()
