"""Integration: click-driven moves through the full window stack, the
non-modal game-over dialog, and AI-think lifecycle."""

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from jungle.gui.dialogs import NewGameDialog
from jungle.gui.main_window import MainWindow
from jungle.model.board import GameState, Move, Piece
from jungle.model.constants import Rank, Side


def _fast_window(qtbot, **overrides):
    kwargs = dict(ai_depth=1, time_limit=0.05, strength="easy")
    kwargs.update(overrides)
    window = MainWindow(**kwargs)
    qtbot.addWidget(window)
    window.show()
    return window


def test_click_driven_move_flows_through_the_window(qtbot):
    window = _fast_window(qtbot)
    qtbot.waitUntil(lambda: window._worker is None, timeout=3000)
    move = Move((6, 0), (5, 0))
    view = window._board_view
    QTest.mouseClick(view, Qt.MouseButton.LeftButton,
                     pos=view.cell_rect(move.from_pos).center().toPoint())
    QTest.mouseClick(view, Qt.MouseButton.LeftButton,
                     pos=view.cell_rect(move.to_pos).center().toPoint())
    assert window._state.move_count == 1
    assert window._state.current_side is Side.BLUE
    # AI answers; input is re-enabled for the human afterwards.
    qtbot.waitUntil(lambda: window._state.move_count == 2, timeout=10000)
    qtbot.waitUntil(lambda: window._worker is None, timeout=3000)
    assert window._board_view._input_enabled
    window._abort_ai()


def test_input_is_disabled_while_the_ai_thinks(qtbot):
    # A slower AI makes the thinking window observable.
    window = _fast_window(qtbot, ai_depth=3, time_limit=0.5)
    move = Move((6, 0), (5, 0))
    window._on_move_requested(move)
    assert window._state.move_count == 1
    qtbot.waitUntil(lambda: window._worker is not None, timeout=3000)
    assert not window._board_view._input_enabled
    qtbot.waitUntil(lambda: window._state.move_count == 2, timeout=15000)
    window._abort_ai()


def test_game_over_dialog_is_non_modal_and_reports_the_winner(qtbot):
    from PySide6.QtWidgets import QLabel

    window = _fast_window(qtbot)
    # RED rat one step from the blue den.
    window._state = GameState.from_pieces(
        {(1, 3): Piece(Side.RED, Rank.RAT), (5, 5): Piece(Side.BLUE, Rank.DOG)}
    )
    window._apply_move(Move((1, 3), (0, 3)))
    dialog = window._game_over_dialog
    assert dialog is not None
    assert not dialog.isModal()
    assert dialog.isVisible()
    # The human plays RED by default, so the message is a human win.
    labels = [label.text() for label in dialog.findChildren(QLabel)]
    assert any("you win" in text.lower() for text in labels)
    window._abort_ai()


def test_game_over_new_game_button_emits(qtbot, monkeypatch):
    # The button opens the modal NewGameDialog; reject it instantly so the
    # test does not block inside exec().
    monkeypatch.setattr(NewGameDialog, "exec",
                        lambda self: NewGameDialog.DialogCode.Rejected)
    window = _fast_window(qtbot)
    window._state = GameState.from_pieces(
        {(1, 3): Piece(Side.RED, Rank.RAT), (5, 5): Piece(Side.BLUE, Rank.DOG)}
    )
    window._apply_move(Move((1, 3), (0, 3)))
    dialog = window._game_over_dialog
    fired = []
    dialog.new_game_requested.connect(lambda: fired.append(True))
    QTest.mouseClick(dialog.new_game_button, Qt.MouseButton.LeftButton)
    assert fired == [True]
    window._abort_ai()


def test_abort_ai_stops_the_worker_without_applying(qtbot):
    # Deep enough that the abort lands mid-search, not after a fast finish.
    window = _fast_window(qtbot, ai_depth=4, time_limit=5.0)
    window._on_move_requested(Move((6, 0), (5, 0)))
    qtbot.waitUntil(lambda: window._worker is not None, timeout=3000)
    window._abort_ai()
    assert window._worker is None
    qtbot.wait(200)
    assert window._state.move_count == 1  # aborted AI never applied a move


def test_close_event_aborts_the_ai(qtbot, monkeypatch):
    # Full close-mid-think is validated end-to-end by the release smoke and
    # manual checklist; in-process we verify the wiring (see project notes on
    # Windows in-process Qt threading instability).
    window = _fast_window(qtbot, ai_depth=3, time_limit=0.5)
    window._on_move_requested(Move((6, 0), (5, 0)))
    qtbot.waitUntil(lambda: window._worker is not None, timeout=3000)
    calls = []
    monkeypatch.setattr(window, "_abort_ai", lambda: calls.append(True))
    window.close()
    assert calls == [True]
    # Clean up the real worker ourselves since the patched abort skipped it.
    monkeypatch.undo()
    window._abort_ai()
