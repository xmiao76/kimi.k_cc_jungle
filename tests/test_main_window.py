"""Safe GUI coverage tests for main window actions."""

from jungle.gui.main_window import MainWindow


def test_main_window_flip_action(qtbot):
    window = MainWindow(ai_first=False, ai_depth=2)
    qtbot.addWidget(window)
    assert not window._board_view._flipped
    window._toggle_flip()
    assert window._board_view._flipped


def test_main_window_status_updates(qtbot):
    window = MainWindow(ai_first=False, ai_depth=2)
    qtbot.addWidget(window)
    window._update_status()
    assert "Turn: Human" in window._status_bar.currentMessage()
