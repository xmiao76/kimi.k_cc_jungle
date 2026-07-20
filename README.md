# Jungle / Dou Shou Qi (鬥獸棋)

A polished Windows desktop implementation of the classic Jungle board game
with a built-in AI, written in Python with PySide6. A human plays against
the computer on a visual 9×7 board; AI-vs-AI mode is also included.

![Game](https://img.shields.io/badge/game-Dou%20Shou%20Qi-red)
![Tests](https://img.shields.io/badge/tests-160%2B-green)

## Quick start

Requires Python ≥ 3.11 (developed on 3.12) and Windows.

```bash
pip install -r requirements.txt
python main.py
```

Useful flags:

```bash
python main.py --strength hard     # easy | medium | hard (default: medium)
python main.py --ai-first          # AI moves first (you play BLUE)
python main.py --ai-vs-ai          # watch the AI play itself
python main.py --depth N           # override AI max search depth
python main.py --time-limit SEC    # override AI thinking time per move
python main.py --flip              # start with the board flipped (view only)
```

## Development

```bash
python -m pytest                                        # fast suite (default)
python -m pytest -m slow                                # strength/performance tests
python -m pytest --cov=jungle --cov-report=term-missing --cov-fail-under=80

python scripts/perft.py            # model vs fast-core move-generation conformance
python scripts/benchmark.py        # search depth/nodes/NPS per position
python scripts/gauntlet.py         # self-play vs the legacy baseline engine
python scripts/ai_vs_ai_smoke.py   # headless full-game smoke (subprocess pattern)

python package.py                  # build release/Jungle.exe (+ release/README.md)
python scripts/smoke_release.py    # validate the packaged executable
```

## Architecture

Strict layering `gui → engine → model`:

- `jungle/model/` — immutable rules of record: board geometry
  (`constants.py`), Zobrist keys (`zobrist.py`), and the complete ruleset
  with immutable `Board`/`GameState` (`board.py`).
- `jungle/engine/` — the AI: precomputed tables (`tables.py`), a fast mutable
  search core with make/undo, incremental Zobrist keys, and incremental
  piece-square-table eval state (`core.py`), the static evaluation
  (`evaluation.py`), iterative-deepening PVS alpha-beta search (`search.py`),
  difficulty presets and the GUI worker thread (`ai.py`), an intentionally
  weak baseline (`legacy_ai.py`), and the frozen first-generation engine used
  as the gauntlet yardstick (`v1_frozen.py`).
- `jungle/gui/` — PySide6 presentation: piece/terrain artwork (`assets.py`),
  the interactive board widget (`board_view.py`), dialogs (`dialogs.py`),
  the main window (`main_window.py`), and the stylesheet (`styles.py`).
- `main.py` — entry point and CLI.
- `scripts/` — conformance, benchmark, gauntlet, smoke, and release tooling.
- `tests/` — ~160 automated tests (rules, perft, model↔core differential
  playouts, search behavior, offscreen GUI tests, subprocess full games).

The ruleset (including the tiger-horizontal-only river-jump variant and the
draw rules) is documented in `release/README.md` and in
`jungle/model/board.py`'s module docstring. The task specification lives in
`prompt.md` at the repository root.

## Testing notes (Windows)

- GUI tests run offscreen (`QT_QPA_PLATFORM=offscreen`, set in
  `tests/conftest.py`).
- Full AI-vs-AI games run in a **subprocess**, never in the pytest process;
  the game-over dialog is always non-modal. Long in-process Qt self-play
  sessions are unstable on Windows.

## Credits

Designed, implemented, tested, and packaged by the code agent
**Claude Code** running the model **`k3[1m]`**, from the requirements in
`prompt.md`.
