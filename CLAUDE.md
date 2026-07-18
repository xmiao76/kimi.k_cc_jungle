# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Windows desktop implementation of **Jungle / Dou Shou Qi** (鬥獸棋) built with Python and PyQt6.
A human player competes against a built-in AI on a visual 9×7 board.

## Common Commands

All commands assume a Windows environment and a virtual environment at `.venv/`.

```bash
# Create / activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run from source
python main.py
python main.py --ai-first --strength hard
python main.py --ai-vs-ai --strength easy

# Run tests
pytest

# Run slow strength/performance tests (gauntlet vs legacy engine, depth-5 benchmark)
pytest -m slow

# Run tests with coverage (required: ≥80%)
pytest --cov=jungle --cov-report=term-missing --cov-fail-under=80

# Type check
mypy jungle main.py

# Engine tooling
python scripts\benchmark.py     # depth/nodes/nps per position
python scripts\perft.py         # fast-core vs model node-count conformance
python scripts\gauntlet.py      # self-play vs legacy baseline engine
python scripts\gauntlet.py --baseline v2 --games 20  # vs frozen previous generation
python scripts\ai_vs_ai_smoke.py  # headless full-game GUI smoke test

# Package executable
python package.py
python scripts\smoke_release.py
# Output: release/Jungle.exe + release/README.md
```

## Architecture

- `jungle/model/` — Immutable game state, rules, and move generation.
  - `board.py` contains `Board`, `Piece`, `Move`, `GameState`, and all legal-move / capture logic.
  - `constants.py` defines `Side`, `Rank`, `Terrain`, board geometry, and starting layout.
  - `zobrist.py` provides deterministic position keys shared with the engine.
- `jungle/engine/` — AI opponent.
  - `tables.py` precomputes cell geometry (neighbors, jumps, terrain) from model constants.
  - `core.py` (`FastPosition`) is the fast mutable search core: flat int board, packed int moves, make/undo, incremental Zobrist keys. It must mirror `model` rules exactly; `tests/engine/test_core_differential.py` enforces this via seeded playouts.
  - `search.py` implements iterative-deepening negamax PVS with a persistent transposition table (generation aging), aspiration windows, late move reductions, quiescence with SEE-lite pruning, killer/history/MVV-LVA ordering, mate-distance pruning, repetition-aware draw scoring, and wall-clock time management with abort. All v3 features are `SearchConfig` flag-gated so previous engine generations remain reproducible for gauntlets.
  - `evaluation.py` provides the tapered static evaluator (`evaluate_fast`) plus the legacy-compatible `evaluate(state, perspective)` wrapper. Weights are bundled in the frozen `EvalWeights` dataclass: `DEFAULT_WEIGHTS` (current generation) vs `V2_WEIGHTS` (previous generation, new terms zeroed).
  - `ai.py` is the public shell: `AI` (config: max depth, time limit) and `AIWorker` (QThread; `abort()`, `search_info` signal).
  - `legacy_ai.py` freezes the original depth-limited negamax as the gauntlet baseline (excluded from coverage).
- `jungle/gui/` — PyQt6 interface.
  - `board_view.py` is the custom-painted board widget; handles selection, legal-move hints, and display flip.
  - `main_window.py` wires menus, status bar, human input, AI turns, AI-vs-AI mode, difficulty presets, and search aborts.
  - `dialogs.py` provides the new-game (mode / first move / difficulty) and game-over dialogs.
  - `assets.py` and `styles.py` define piece rendering and application styling.
- `scripts/` — benchmark, perft, gauntlet, and smoke-test tooling.
- `tests/` — pytest unit, differential, tactical, integration, GUI, and slow gauntlet tests.

## Key Conventions

- `GameState` and `Board` are immutable; every move returns a new instance.
- `FastPosition` (engine core) is the deliberate exception: mutable, make/undo, used only inside search. Public APIs exchange immutable `GameState`/`Move`; convert with `FastPosition.from_game_state` / `to_model_move`.
- Board coordinates are `(row, col)` with `row=0` at the top (BLUE side) and `row=8` at the bottom (RED side). Engine cell indices are `row * 7 + col`; packed moves are `from_idx | (to_idx << 6)`.
- The display flip in `BoardView` is purely visual; internal coordinates and turn order never change.
- RED moves first by standard rules. The GUI's "who moves first" setting only decides whether the human or AI plays RED.
- Animal piece symbols are rendered with the system emoji font.
- The game-over dialog is shown non-blocking (`dialog.open()`); sustained in-process GUI self-play tests must run offscreen in a subprocess (see `scripts/ai_vs_ai_smoke.py`) because the Windows event loop crashes under prolonged rapid `QThread` signal delivery on some machines.

## Rules Interpretation

- Standard starting position: BLUE lion (0,0), tiger (0,6), dog (1,1), cat (1,5), rat (2,0), leopard (2,2), wolf (2,4), elephant (2,6); RED mirrored 180°.
- Ranks follow Wikipedia: rat 1 < cat 2 < dog 3 < wolf 4 < leopard 5 < tiger 6 < lion 7 < elephant 8 (some Chinese sources swap dog/wolf; Wikipedia is the primary reference).
- River: two 3×2 bodies centered on rows 3–5, columns {1,2} and {4,5}.
- Only rats may enter river squares. A rat in the river can only capture another rat in the river; land pieces cannot capture a rat in the river.
- Lion may jump across the river horizontally or vertically (2-cell and 3-cell spans); tiger may jump horizontally only (2-cell span).
- Jumps are blocked by any rat in an intervening river square.
- Rat on land can capture elephant (from a land square only); elephant cannot capture rat.
- A piece in an opponent's trap has defensive rank 0 but attacks with its normal rank.
- Win by entering the opponent's den, capturing all enemy pieces, or leaving the opponent with no legal moves.
- Draw by threefold repetition or after 200 plies (100 moves per side).

## Release

The packaged executable and the player README (from `packaging/README.release.md`, includes the required model/code-agent credit) are produced in `release/` by `python package.py`. Validate with `python scripts\smoke_release.py` after packaging.
Do not commit large build artifacts (`build/`, `dist/`, `*.spec`, `release/Jungle.exe`) to git; `.gitignore` covers them.
