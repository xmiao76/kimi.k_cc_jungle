"""Application entry point.

Usage:
    python main.py [--strength easy|medium|hard] [--ai-first] [--ai-vs-ai]
                   [--depth N] [--time-limit SECONDS] [--flip]
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback

from jungle.engine.ai import STRENGTH_NAMES


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="Jungle",
        description="Jungle / Dou Shou Qi — play against the built-in AI.",
    )
    parser.add_argument("--strength", choices=STRENGTH_NAMES, default="medium",
                        help="AI difficulty (default: medium)")
    parser.add_argument("--ai-first", action="store_true",
                        help="the AI moves first (you play BLUE)")
    parser.add_argument("--ai-vs-ai", action="store_true",
                        help="watch the AI play itself")
    parser.add_argument("--depth", type=int, default=None,
                        help="override the AI max search depth")
    parser.add_argument("--time-limit", type=float, default=None,
                        help="override the AI thinking time per move (seconds)")
    parser.add_argument("--flip", action="store_true",
                        help="start with the board flipped (view only)")
    return parser.parse_args(argv)


def _crash_log_path() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "jungle-crash.log")
    return os.path.join(os.getcwd(), "jungle-crash.log")


def _install_excepthook() -> None:
    def hook(exc_type, exc_value, exc_tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        sys.stderr.write(text)
        try:
            with open(_crash_log_path(), "a", encoding="utf-8") as handle:
                handle.write(text + "\n")
        except OSError:
            pass
        try:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(None, "Jungle crashed",
                                 f"An unexpected error occurred.\n\n{exc_value}\n\n"
                                 f"Details were written to jungle-crash.log.")
        except Exception:
            pass

    sys.excepthook = hook


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    from PySide6.QtWidgets import QApplication

    from jungle.gui.main_window import MainWindow
    from jungle.gui.styles import APP_QSS

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Jungle")
    app.setOrganizationName("JungleGame")
    app.setStyleSheet(APP_QSS)
    _install_excepthook()

    window = MainWindow(
        ai_first=args.ai_first,
        ai_depth=args.depth,
        flipped=args.flip,
        strength=args.strength,
        time_limit=args.time_limit,
        ai_vs_ai=args.ai_vs_ai,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
