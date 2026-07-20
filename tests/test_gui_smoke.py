"""Basic GUI smoke: window constructs, a full human+AI exchange completes."""

from PySide6.QtTest import QTest
from PySide6.QtCore import Qt

from jungle.gui.main_window import MainWindow
from jungle.model.constants import Side


def _fast_window(qtbot, **overrides):
    kwargs = dict(ai_depth=1, time_limit=0.05, strength="easy")
    kwargs.update(overrides)
    window = MainWindow(**kwargs)
    qtbot.addWidget(window)
    window.show()
    return window


def test_window_constructs_with_starting_state(qtbot):
    window = _fast_window(qtbot)
    assert window._state.move_count == 0
    assert window._state.current_side is Side.RED
    assert window._board_view is not None
    assert window._game_over_dialog is None
    window._abort_ai()


def test_human_move_then_ai_replies(qtbot):
    window = _fast_window(qtbot)
    qtbot.waitUntil(lambda: window._worker is None, timeout=3000)  # human first: no worker

    view = window._board_view
    move = window._state.legal_moves()[0]
    # Click the piece, then the destination, via real mouse events.
    from_center = view.cell_rect(move.from_pos).center()
    to_center = view.cell_rect(move.to_pos).center()
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=from_center.toPoint())
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=to_center.toPoint())

    assert window._state.move_count == 1
    qtbot.waitUntil(lambda: window._state.move_count == 2, timeout=10000)
    assert window._state.current_side is Side.RED  # human to move again
    window._abort_ai()


def test_flip_is_display_only(qtbot):
    window = _fast_window(qtbot)
    view = window._board_view
    state_before = window._state
    key_before = state_before.position_key

    window._flip_action.setChecked(True)
    assert view.is_flipped()
    assert window._state is state_before
    assert window._state.position_key == key_before

    # The display transform inverts: RED's back rank now renders on top.
    top_left = view.cell_rect((8, 0))
    bottom_right = view.cell_rect((0, 6))
    assert top_left.y() < bottom_right.y()
    window._abort_ai()
