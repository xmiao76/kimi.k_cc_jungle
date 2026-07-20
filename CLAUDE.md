# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

## Project

Windows desktop **Jungle / Dou Shou Qi** (鬥獸棋) game: Python 3.12 + PySide6,
human vs built-in AI on a visual 9×7 board. Specification: `prompt.md` (repo
root — keep it tracked and untouched).

## Commands

```bash
python main.py [--strength hard] [--ai-first] [--ai-vs-ai] [--depth N] [--time-limit S] [--flip]
python -m pytest                 # fast suite (excludes @pytest.mark.slow)
python -m pytest -m slow         # gauntlet vs legacy engine + deep perft
python -m pytest --cov=jungle --cov-report=term-missing --cov-fail-under=80
python scripts/perft.py          # model vs fast-core perft conformance
python scripts/benchmark.py      # NPS benchmark
python scripts/gauntlet.py --games 20                       # vs legacy baseline
python scripts/gauntlet.py --baseline v1 --games 8 --depth 3  # vs frozen v1
python scripts/gauntlet.py --baseline self --games 8          # vs features-off
python scripts/ai_vs_ai_smoke.py 120   # full game, MUST stay a subprocess
python package.py                # -> release/Jungle.exe + release/README.md
python scripts/smoke_release.py  # packaged-exe validation
```

## Architecture (strict layering: gui → engine → model)

- `jungle/model/` — immutable rules of record. `board.py` has `Board`,
  `GameState`, and every rule (locked interpretations are in its docstring —
  e.g. tiger jumps horizontally ONLY; draws: threefold repetition or
  200 plies). `constants.py` has geometry; `zobrist.py` the keys.
- `jungle/engine/` — AI. `core.py` (`FastPosition`: flat int board, packed
  moves, make/undo, incremental keys AND incremental PST eval state) MUST
  mirror the model exactly; `tests/engine/test_core_differential.py` and
  `test_evaluation.py` enforce it via seeded playouts.
  `search.py` = ID-PVS alpha-beta with **fresh TT per search** (persistent
  TTs poison repetition scoring — measured strength loss); **no LMR, no
  aspiration, no SEE** (measured harmful/neutral on this game). Strength
  lives in `evaluation.py` terms — gauntlet-verified: `den_defense=12`
  (8/8 vs frozen v1). `rat_river` and `rat_elephant_proximity` measured
  HARMFUL (0/8) — keep at 0. `den_extension`/`ordered_advance` measured
  neutral — kept off. `v1_frozen.py` is the fixed first-generation gauntlet
  opponent; never "improve" it.
- `jungle/gui/` — PySide6. `board_view.py` flip is a PURE display transform
  (never touches state/sides/turn). `main_window.py` orchestrates the
  `AIWorker(QThread)`; the GUI never blocks.
- `main.py` — CLI entry. `package.py` — PyInstaller build with Windows
  file-lock retries.

## Windows/Qt testing hazards (hard-won — do not regress)

1. GUI tests: `QT_QPA_PLATFORM=offscreen` (set in `tests/conftest.py` before
   Qt imports). Offscreen has NO fonts — never assert on glyph shapes.
2. Full AI-vs-AI games only via subprocess (`scripts/ai_vs_ai_smoke.py`).
3. The game-over dialog is NEVER `exec()`'d — non-modal `show()` only.
4. `_maybe_start_ai` must never run two AI workers at once (an earlier
   deferred-timer design caused orphaned workers and crashes).
5. `package.py`: taskkill the running exe first; retry deletes/copies past
   antivirus file locks.
