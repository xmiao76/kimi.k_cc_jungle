# Jungle / Dou Shou Qi (鬥獸棋)

A polished Windows desktop board game with a built-in AI opponent.
Play the classic Chinese animal chess against the computer on a visual 9×7 board.

## Launch

Double-click `Jungle.exe`. No installation or Python required.

Optional command-line flags (run from a terminal):

```
Jungle.exe --strength hard     # easy | medium | hard (default: medium)
Jungle.exe --ai-first          # AI moves first (default: human moves first)
Jungle.exe --ai-vs-ai          # watch the AI play itself
Jungle.exe --depth N           # override the AI max search depth
Jungle.exe --time-limit SEC    # override the AI thinking time per move
Jungle.exe --flip              # start with the board flipped (view only)
```

## Gameplay

- **Goal**: win by moving any piece into the opponent's den (★), or by
  capturing all enemy pieces. A side with no legal moves loses.
- **Your move**: click one of your pieces — legal destinations light up as
  green dots (captures show a red ring) — then click a destination.
  Click elsewhere to deselect.
- **Menu → Game**: New Game (mode, who moves first, difficulty), Quit.
- **Menu → View**: Flip Board — rotates the display only. It never changes
  the game state, swaps sides, or changes whose turn it is.
- **Menu → AI**: switch difficulty at any time.
- **Status bar**: shows whose turn it is; while the AI thinks it also shows
  live search depth, score, and speed (e.g. `d=5 +0.42 38.1kN`).
- **Difficulty**: Easy (fast), Medium, Hard (stronger, up to ~2 s/move).
- **AI vs AI**: pick it in the New Game dialog (or `--ai-vs-ai`) to watch a
  full game played automatically.
- **Who moves first**: chosen in the New Game dialog (or `--ai-first`).
  This only affects the starting order and works together with the flip
  option, which stays purely visual.

## Rules summary

Standard Jungle / Dou Shou Qi rules (per Wikipedia), 8 animals per side:

- Ranks: rat 1 < cat 2 < dog 3 < wolf 4 < leopard 5 < tiger 6 < lion 7 <
  elephant 8. A piece captures any enemy piece of equal or lower rank.
- Only the **rat** may enter the river (blue squares). A rat in the river can
  only capture another rat in the river; it cannot capture (or be captured
  by) pieces on land. The rat captures the elephant only from a land square.
- The **elephant** cannot capture the rat.
- The **lion** may jump across the river horizontally or vertically (both
  the 2-cell-wide and 3-cell-tall spans); the **tiger** may jump only
  horizontally, across the 2-cell-wide span. A jump is blocked by any rat
  (either side) standing in the river along the path. Captures on the
  landing square follow the normal rules.
- A piece inside one of the **opponent's traps** defends with rank 0 — any
  enemy piece can capture it — but it still attacks with its normal rank.
- You may not enter your **own den**.
- **Draws**: a game is drawn if the same position occurs three times, or
  after 200 plies (100 moves per side) without a result.

## Notes

- RED moves first. With the default options you play RED against the AI.
- If the app ever crashes, details are appended to `jungle-crash.log`
  next to the executable.

## Credits

This application — game rules, AI engine, GUI, automated tests, and
packaging — was designed, implemented, tested, and packaged by the code
agent **Claude Code** running the model **`k3[1m]`**, from the requirements
in `prompt.md`.
