"""Tests for game modes, difficulty plumbing, abort, and draw handling."""

from jungle.gui.dialogs import (
    DIFFICULTY_EASY,
    DIFFICULTY_HARD,
    DIFFICULTY_MEDIUM,
    MODE_AI_VS_AI,
    MODE_HUMAN_VS_AI,
    GameOverDialog,
    NewGameDialog,
)
from jungle.gui.main_window import MainWindow
from jungle.model.board import GameState, Move
from jungle.model.constants import Side


def test_new_game_dialog_defaults(qtbot):
    dialog = NewGameDialog()
    qtbot.addWidget(dialog)
    assert dialog.mode() == MODE_HUMAN_VS_AI
    assert dialog.difficulty() == DIFFICULTY_MEDIUM
    assert dialog.human_first() is True


def test_new_game_dialog_mode_disables_first_choice(qtbot):
    dialog = NewGameDialog()
    qtbot.addWidget(dialog)
    assert dialog._first_box.isEnabled()
    dialog._mode_ai.setChecked(True)
    assert not dialog._first_box.isEnabled()
    assert dialog.mode() == MODE_AI_VS_AI
    dialog._mode_human.setChecked(True)
    assert dialog._first_box.isEnabled()


def test_new_game_dialog_difficulty_selection(qtbot):
    dialog = NewGameDialog()
    qtbot.addWidget(dialog)
    dialog._level_easy.setChecked(True)
    assert dialog.difficulty() == DIFFICULTY_EASY
    dialog._level_hard.setChecked(True)
    assert dialog.difficulty() == DIFFICULTY_HARD


def test_main_window_difficulty_preset(qtbot):
    window = MainWindow(ai_first=False, strength="easy")
    qtbot.addWidget(window)
    assert window._ai.config.max_depth == 3
    assert window._ai.config.soft_limit_s == 0.5


def test_main_window_depth_override(qtbot):
    window = MainWindow(ai_first=False, ai_depth=2, strength="hard")
    qtbot.addWidget(window)
    assert window._ai.config.max_depth == 2


def test_ai_vs_ai_game_completes():
    # Runs the full self-play game in an offscreen subprocess: the sustained
    # QThread signal storm crashes the in-process Windows event loop on this
    # machine (fatal 0x8001010d), and a headless run is CI-safe anyway.
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parent.parent / "scripts" / "ai_vs_ai_smoke.py"
    result = subprocess.run(
        [sys.executable, str(script), "110"],
        capture_output=True,
        text=True,
        timeout=150,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "GAME_OVER" in result.stdout


def test_new_game_aborts_thinking(qtbot):
    window = MainWindow(ai_first=True, ai_depth=8, time_limit=30.0)
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: window._ai_thinking, timeout=10_000)
    generation = window._generation
    window._start_new_game(difficulty="easy")
    assert window._generation == generation + 1
    state = window._board_view.state()
    assert state is not None and state.move_count == 0
    window._abort_ai()


def test_search_info_updates_status(qtbot):
    # Long search so the thinking status is observable (fast searches
    # finish before waitUntil polls and the status is overwritten).
    window = MainWindow(ai_first=True, ai_depth=16, time_limit=2.0)
    qtbot.addWidget(window)
    qtbot.waitUntil(
        lambda: "d=" in window._status_bar.currentMessage(), timeout=10_000
    )
    assert "AI (medium)" in window._status_bar.currentMessage()
    window._abort_ai()


def test_human_input_ignored_in_ai_vs_ai(qtbot):
    window = MainWindow(ai_vs_ai=True, ai_depth=1, time_limit=0.05)
    qtbot.addWidget(window)
    window._abort_ai()  # freeze the self-play so the assertion is stable
    state = window._board_view.state()
    assert state is not None
    mover = state.current_side
    window._on_human_move(Move((8, 0), (7, 0)))
    state = window._board_view.state()
    assert state is not None
    assert state.current_side is mover  # unchanged


def test_game_over_dialog_draw_text(qtbot):
    from PyQt6.QtWidgets import QLabel

    dialog = GameOverDialog("Draw")
    qtbot.addWidget(dialog)
    texts = [label.text() for label in dialog.findChildren(QLabel)]
    assert "Draw" in texts
    assert not dialog.wants_new_game()


def test_game_over_stay_keeps_window_open(qtbot):
    window = MainWindow(ai_first=False, ai_depth=2)
    qtbot.addWidget(window)
    close_events = []
    window.closeEvent = lambda event: close_events.append(event)

    state = window._board_view.state()
    assert state is not None
    final_state = GameState(board=state.board, current_side=Side.BLUE, winner=Side.RED)
    window._board_view.set_state(final_state)

    window._show_game_over(final_state)
    assert window._game_over_dialog is not None
    window._game_over_dialog.reject()  # "Stay"

    assert window._game_over_dialog is None
    assert close_events == []  # the app must NOT close after game over
    assert window._board_view.state() is final_state  # final position kept


def test_game_over_new_game_opens_prompt(qtbot, monkeypatch):
    window = MainWindow(ai_first=False, ai_depth=2)
    qtbot.addWidget(window)
    prompted = []
    monkeypatch.setattr(window, "_prompt_new_game", lambda: prompted.append(True))

    state = window._board_view.state()
    final_state = GameState(board=state.board, current_side=Side.BLUE, winner=Side.RED)
    window._show_game_over(final_state)
    window._game_over_dialog.accept()  # "New Game"
    assert prompted == [True]


def test_board_view_ignores_clicks_on_draw(qtbot):
    from PyQt6.QtCore import Qt

    window = MainWindow(ai_first=False, ai_depth=2)
    qtbot.addWidget(window)
    state = window._board_view.state()
    drawn = GameState(board=state.board, current_side=Side.RED, draw=True)
    window._board_view.set_state(drawn)
    view = window._board_view
    view.resize(view.sizeHint())
    cell = view.cell_rect((8, 0))
    qtbot.mouseClick(view, Qt.MouseButton.LeftButton, pos=cell.center().toPoint())
    qtbot.wait(30)
    assert view._selected_pos is None


def test_parse_args_new_flags():
    from main import parse_args

    args = parse_args(["--strength", "hard", "--ai-vs-ai", "--time-limit", "2.5"])
    assert args.strength == "hard"
    assert args.ai_vs_ai is True
    assert args.time_limit == 2.5
    assert args.depth is None


def test_new_game_after_ai_move_does_not_crash(qtbot):
    """Regression: starting a new game after the AI's worker finished and Qt
    deleted it must not raise 'wrapped C/C++ object has been deleted'."""
    window = MainWindow(ai_first=True, ai_depth=1, time_limit=0.05)
    qtbot.addWidget(window)
    # AI (RED) moves first; wait until its move is applied.
    qtbot.waitUntil(
        lambda: (window._board_view.state() is not None)
        and window._board_view.state().move_count >= 1,
        timeout=10_000,
    )
    # Let finished/deleteLater be delivered; the window must drop its
    # reference to the completed worker.
    qtbot.waitUntil(lambda: window._ai_worker is None, timeout=5_000)
    # The user's scenario: New Game with a different difficulty, mid-game.
    window._start_new_game(difficulty="easy")
    state = window._board_view.state()
    assert state is not None and state.move_count == 0
    assert window._strength == "easy"
    window._abort_ai()


def test_new_game_while_ai_thinking_does_not_crash(qtbot):
    """Regression: aborting a running worker then switching difficulty."""
    window = MainWindow(ai_first=True, ai_depth=16, time_limit=30.0)
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: window._ai_thinking, timeout=10_000)
    window._start_new_game(difficulty="hard")
    assert window._strength == "hard"
    window._abort_ai()


def test_aborted_worker_emits_nothing(qtbot):
    import threading
    import time

    from jungle.engine.ai import AI, AIWorker
    from jungle.model.board import Board

    state = GameState(board=Board.starting(), current_side=Side.RED)
    ai = AI(side=Side.RED, depth=16, time_limit_s=30.0)
    worker = AIWorker(ai, state)
    emissions = []
    worker.move_chosen.connect(lambda move: emissions.append(move))
    worker.start()
    time.sleep(0.05)
    worker.abort()
    assert worker.wait(3000)
    assert emissions == []
