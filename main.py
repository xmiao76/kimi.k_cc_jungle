"""Entry point for the Jungle / Dou Shou Qi desktop application."""

import argparse
import sys
import traceback
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox

from jungle.gui.main_window import DIFFICULTY_PRESETS, MainWindow


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="Jungle",
        description="Jungle / Dou Shou Qi board game with AI",
    )
    parser.add_argument(
        "--ai-first",
        action="store_true",
        help="Let the AI move first (default: human first).",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=None,
        help="Override the AI max search depth for the chosen strength.",
    )
    parser.add_argument(
        "--strength",
        choices=sorted(DIFFICULTY_PRESETS),
        default="medium",
        help="AI difficulty preset (default: medium).",
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Override the AI soft time limit per move.",
    )
    parser.add_argument(
        "--ai-vs-ai",
        action="store_true",
        help="Watch the AI play against itself.",
    )
    parser.add_argument(
        "--flip",
        action="store_true",
        help="Start with the board flipped visually.",
    )
    return parser.parse_args(argv)


def _install_excepthook() -> None:
    """Show (and log) unexpected errors instead of vanishing silently."""

    def _hook(exc_type, exc_value, exc_tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            base = (
                Path(sys.executable).parent
                if getattr(sys, "frozen", False)
                else Path.cwd()
            )
            with open(base / "jungle-crash.log", "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError:
            pass
        QMessageBox.critical(
            None,
            "Unexpected error",
            "Jungle hit an unexpected error but will try to keep running.\n\n"
            f"{exc_type.__name__}: {exc_value}",
        )

    sys.excepthook = _hook


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    app = QApplication(sys.argv)
    app.setApplicationName("Jungle")
    app.setApplicationVersion("2.0.0")
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
    raise SystemExit(main())
