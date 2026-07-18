"""Smoke tests for the GUI."""

import pytest

from jungle.gui.main_window import MainWindow


@pytest.mark.skipif(
    pytest.importorskip("PyQt6") is None,
    reason="PyQt6 not available",
)
def test_main_window_creation(qtbot):
    window = MainWindow(ai_first=False, ai_depth=2)
    qtbot.addWidget(window)
    assert window.windowTitle() == "Jungle / Dou Shou Qi"
    assert window._board_view.state() is not None
