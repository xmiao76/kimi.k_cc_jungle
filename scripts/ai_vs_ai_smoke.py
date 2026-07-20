"""Headless full-game smoke test: plays a complete AI-vs-AI game offscreen.

Run as a SUBPROCESS (never inside pytest's process): long in-process Qt
self-play sessions crash intermittently on Windows (0x8001010d). This script
drives the real MainWindow/AIWorker machinery at high speed and prints the
result.

Usage: python scripts/ai_vs_ai_smoke.py [timeout_seconds] [--ai-first-equivalent]
Exit code 0 = a game completed; 1 = timeout / no result.
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QElapsedTimer
from PySide6.QtWidgets import QApplication


def main() -> int:
    timeout_s = float(sys.argv[1]) if len(sys.argv) > 1 else 110.0
    app = QApplication(sys.argv[:1])

    from jungle.gui.main_window import MainWindow

    window = MainWindow(ai_vs_ai=True, ai_depth=2, time_limit=0.05, strength="easy")
    window.show()

    timer = QElapsedTimer()
    timer.start()
    while window._game_over_dialog is None and timer.elapsed() < timeout_s * 1000:
        app.processEvents()
        time.sleep(0.005)

    if window._game_over_dialog is None:
        print(f"TIMEOUT after {timeout_s:.0f}s: plies={window._state.move_count}")
        window._abort_ai()
        return 1

    state = window._state
    winner = state.winner
    outcome = winner.name if winner is not None else "DRAW"
    print(f"GAME_OVER: {outcome} reason={state.game_over_reason} plies={state.move_count}")
    window._abort_ai()
    return 0


if __name__ == "__main__":
    sys.exit(main())
