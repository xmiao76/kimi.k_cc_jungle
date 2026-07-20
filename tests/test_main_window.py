"""Main window structure: menus, flip action, new-game dialog plumbing."""

from jungle.gui.dialogs import NewGameDialog
from jungle.gui.main_window import MainWindow


def _fast_window(qtbot, **overrides):
    kwargs = dict(ai_depth=1, time_limit=0.05, strength="easy")
    kwargs.update(overrides)
    window = MainWindow(**kwargs)
    qtbot.addWidget(window)
    window.show()
    return window


def test_menus_and_actions_exist(qtbot):
    window = _fast_window(qtbot)
    titles = [action.text() for action in window.menuBar().actions()]
    assert any("Game" in t for t in titles)
    assert any("View" in t for t in titles)
    assert any("AI" in t for t in titles)
    assert window._flip_action is not None
    window._abort_ai()


def test_flip_action_drives_the_view(qtbot):
    window = _fast_window(qtbot)
    assert not window._board_view.is_flipped()
    window._flip_action.setChecked(True)
    assert window._board_view.is_flipped()
    window._flip_action.setChecked(False)
    assert not window._board_view.is_flipped()
    window._abort_ai()


def test_cancelled_new_game_dialog_keeps_state(qtbot, monkeypatch):
    window = _fast_window(qtbot)
    monkeypatch.setattr(NewGameDialog, "exec",
                        lambda self: NewGameDialog.DialogCode.Rejected)
    state_before = window._state
    window._prompt_new_game()
    assert window._state is state_before
    window._abort_ai()


def test_accepted_new_game_dialog_starts_fresh(qtbot, monkeypatch):
    window = _fast_window(qtbot)
    monkeypatch.setattr(NewGameDialog, "exec",
                        lambda self: NewGameDialog.DialogCode.Accepted)
    monkeypatch.setattr(NewGameDialog, "mode", property(lambda self: "human_vs_ai"))
    monkeypatch.setattr(NewGameDialog, "ai_first", property(lambda self: True))
    monkeypatch.setattr(NewGameDialog, "strength", property(lambda self: "hard"))
    window._prompt_new_game()
    assert window._state.move_count == 0
    assert window._human_side.name == "BLUE"  # AI moves first
    assert window._strength == "hard"
    window._abort_ai()


def test_status_message_slot_updates_statusbar(qtbot):
    window = _fast_window(qtbot)
    window._on_status_message("hello jungle")
    assert window.statusBar().currentMessage() == "hello jungle"
    window._abort_ai()


def test_search_info_updates_the_ai_readout(qtbot):
    window = _fast_window(qtbot)
    window._on_search_info(4, 125, 42300)
    assert "d=4" in window._ai_info_label.text()
    assert "+1.25" in window._ai_info_label.text()
    assert "42.3kN" in window._ai_info_label.text()
    window._abort_ai()
