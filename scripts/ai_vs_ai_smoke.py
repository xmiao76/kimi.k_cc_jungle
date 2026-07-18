"""Headless AI-vs-AI full-game smoke test (offscreen Qt platform).

Runs a complete self-play game through the real MainWindow/AIWorker stack
and prints GAME_OVER on success. Used by tests and as a manual sanity check.
"""

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QEventLoop  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from jungle.gui.main_window import MainWindow  # noqa: E402


def main() -> int:
    timeout_s = int(sys.argv[1]) if len(sys.argv) > 1 else 110
    app = QApplication(sys.argv)
    window = MainWindow(ai_vs_ai=True, ai_depth=2, time_limit=0.05)
    deadline = time.monotonic() + timeout_s
    while window._game_over_dialog is None and time.monotonic() < deadline:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 100)
    if window._game_over_dialog is None:
        print("TIMEOUT: AI-vs-AI game did not complete")
        return 1
    state = window._board_view.state()
    assert state is not None
    if state.winner is not None:
        result = f"{state.winner.name} wins"
    elif state.draw:
        result = "draw"
    else:
        result = "unknown"
    print(f"GAME_OVER: {result} plies={state.move_count}")
    window._game_over_dialog.reject()
    window._abort_ai()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
