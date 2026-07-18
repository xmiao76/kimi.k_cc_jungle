# Jungle / Dou Shou Qi

A polished Windows desktop board game with a built-in AI opponent.

## Requirements

- Python 3.11+
- Windows (the packaged `.exe` is Windows-only)

## Development Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run from Source

```bash
python main.py
```

Optional flags:
- `--strength easy|medium|hard` — AI difficulty preset (default: medium)
- `--ai-first` — let the AI move first (default: human first)
- `--ai-vs-ai` — watch the AI play against itself
- `--depth N` — override the AI max search depth for the chosen preset
- `--time-limit SECONDS` — override the AI soft thinking time per move
- `--flip` — start with the board flipped

Difficulty presets: Easy = depth 3 / 0.5 s, Medium = depth 6 / 1.5 s,
Hard = depth 12 / 2.5 s (iterative deepening; the time limit governs,
and iterations that cannot finish in the remaining budget are skipped).

## Run Tests

```bash
pytest
```

Slow strength/performance tests (self-play gauntlet, depth-5 benchmark):

```bash
pytest -m slow
```

With coverage (required ≥ 80%):

```bash
pytest --cov=jungle --cov-report=term-missing --cov-fail-under=80
```

## Type Check

```bash
mypy jungle main.py
```

## Engine Tools

```bash
python scripts\benchmark.py [max_depth]   # depth / nodes / nps per position
python scripts\perft.py [max_depth]       # move-count conformance vs the model
python scripts\gauntlet.py --games 4                          # vs original legacy engine
python scripts\gauntlet.py --games 20 --baseline v2           # vs frozen previous engine generation
python scripts\ai_vs_ai_smoke.py          # headless full-game GUI smoke test
```

## Package

```bash
python package.py
```

The packaged executable and the player README are placed in `release/`.
Validate the packaged app afterwards:

```bash
python scripts\smoke_release.py
```

## Project Structure

- `jungle/model/` — authoritative game rules, immutable board state, Zobrist keys
- `jungle/engine/` — AI engine
  - `tables.py` / `core.py` — fast incremental position (make/undo, packed moves)
  - `search.py` — iterative-deepening PVS with persistent transposition table
    (generation aging), aspiration windows, late move reductions, and
    quiescence with SEE-lite pruning; features are flag-gated so previous
    engine generations stay reproducible
  - `evaluation.py` — tapered static evaluation; weights bundled in
    `EvalWeights` (`DEFAULT_WEIGHTS` current, `V2_WEIGHTS` previous generation)
  - `ai.py` — public `AI` shell and `AIWorker` (QThread, abortable)
  - `legacy_ai.py` — frozen original engine, kept as the gauntlet baseline
- `jungle/gui/` — PyQt6 GUI (board view, dialogs, main window)
- `tests/` — automated tests (unit, differential, tactical, GUI, slow gauntlet)
- `scripts/` — benchmark / perft / gauntlet / smoke tooling
- `packaging/` — release README source

## Rules

The game follows the standard Jungle / Dou Shou Qi rules (Wikipedia is the
primary reference) with these documented interpretations:

- Board: 9 rows × 7 columns; standard starting position (lion (0,0),
  tiger (0,6), dog (1,1), cat (1,5), rat (2,0), leopard (2,2), wolf (2,4),
  elephant (2,6) for BLUE; RED mirrored).
- Ranks: rat 1 < cat 2 < dog 3 < wolf 4 < leopard 5 < tiger 6 < lion 7 <
  elephant 8 (Wikipedia ordering; some Chinese sources swap dog and wolf).
- Only rats may enter river squares. A rat in the river can only capture
  another rat in the river; land pieces cannot capture a rat in the river.
  A rat captures an elephant only from a land square.
- Lion jumps the river horizontally or vertically (both the 2-cell and
  3-cell spans); tiger jumps horizontally only (the 2-cell span).
  A jump is blocked by any rat in an intervening river square.
- Elephant cannot capture rat.
- A piece in an opponent's trap defends with rank 0 but attacks normally.
- Win by entering the opponent's den, capturing all enemy pieces, or when
  the opponent has no legal moves.
- Draws: threefold repetition, or 200 plies (100 moves per side) played.
