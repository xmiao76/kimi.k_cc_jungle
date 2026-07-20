"""Game modes: who-moves-first, AI-vs-AI, difficulty, and their composition
with the view-only board flip."""

from jungle.gui.dialogs import MODE_AI_VS_AI, MODE_HUMAN_VS_AI
from jungle.gui.main_window import MainWindow
from jungle.model.constants import Side


def _fast_window(qtbot, **overrides):
    kwargs = dict(ai_depth=1, time_limit=0.05, strength="easy")
    kwargs.update(overrides)
    window = MainWindow(**kwargs)
    qtbot.addWidget(window)
    window.show()
    return window


def test_human_first_mode_waits_for_the_human(qtbot):
    window = _fast_window(qtbot, ai_first=False)
    assert window._human_side is Side.RED
    qtbot.waitUntil(lambda: window._worker is None, timeout=3000)
    assert window._state.move_count == 0  # nothing moves until the human does
    assert window._board_view._input_enabled
    window._abort_ai()


def test_ai_first_mode_makes_the_opening_move(qtbot):
    window = _fast_window(qtbot, ai_first=True)
    assert window._human_side is Side.BLUE
    qtbot.waitUntil(lambda: window._state.move_count == 1, timeout=10000)
    assert window._state.current_side is Side.BLUE  # human to move
    qtbot.waitUntil(lambda: window._worker is None, timeout=3000)
    assert window._board_view._input_enabled
    window._abort_ai()


def test_ai_vs_ai_mode_runs_without_a_human(qtbot):
    window = _fast_window(qtbot, ai_vs_ai=True)
    assert window._human_side is None
    qtbot.waitUntil(lambda: window._state.move_count >= 3, timeout=15000)
    assert not window._board_view._input_enabled
    window._abort_ai()


def test_ai_first_composes_with_flip(qtbot):
    window = _fast_window(qtbot, ai_first=True, flipped=True)
    view = window._board_view
    assert view.is_flipped()
    qtbot.waitUntil(lambda: window._state.move_count == 1, timeout=10000)
    # Flip changed nothing but the display mapping.
    assert window._human_side is Side.BLUE
    assert window._state.current_side is Side.BLUE
    assert view._display_pos((8, 0)) == (0, 6)
    window._abort_ai()


def test_difficulty_switch_reconfigures_ai(qtbot):
    # Without a CLI depth override, the difficulty drives the search depth.
    window = _fast_window(qtbot, ai_depth=None)
    window._on_strength_changed("hard")
    assert window._strength == "hard"
    assert window._ai.config.max_depth == 6
    window._abort_ai()


def test_cli_depth_override_survives_difficulty_switch(qtbot):
    window = _fast_window(qtbot, ai_depth=2)
    window._on_strength_changed("hard")
    assert window._ai.config.max_depth == 2
    window._abort_ai()


def test_start_new_game_resets_everything(qtbot):
    window = _fast_window(qtbot, ai_first=True)
    qtbot.waitUntil(lambda: window._state.move_count >= 1, timeout=10000)
    window.start_new_game(mode=MODE_HUMAN_VS_AI, ai_first=False, strength="medium")
    assert window._state.move_count == 0
    assert window._state.current_side is Side.RED
    assert window._human_side is Side.RED
    assert window._strength == "medium"
    assert window._worker is None
    window._abort_ai()


def test_start_new_game_ai_vs_ai_switches_mode(qtbot):
    window = _fast_window(qtbot)
    window.start_new_game(mode=MODE_AI_VS_AI, ai_first=False, strength="easy")
    assert window._human_side is None
    qtbot.waitUntil(lambda: window._state.move_count >= 2, timeout=15000)
    window._abort_ai()
