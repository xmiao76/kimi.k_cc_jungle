"""Fast mutable search core mirroring ``jungle.model.board`` exactly.

Pieces are small ints (``rank | side << 4``), moves are packed ints
(``from | to << 6``), and the Zobrist key is maintained incrementally under
make/undo, so search never allocates board copies. Differential tests
(``tests/engine/test_core_differential.py``) prove the move sets, position
keys, and terminal outcomes match the immutable model on every position of
seeded random playouts.
"""

from __future__ import annotations

from typing import Optional

from jungle.engine.tables import (
    DEN_IDX,
    IS_RIVER,
    JUMPS,
    NEIGHBORS,
    TERRAIN,
    TRAP_TABLE,
)
from jungle.model import zobrist
from jungle.model.board import MAX_PLIES, REPETITION_LIMIT, GameState, Move
from jungle.model.constants import COLS, Rank, Side, Terrain

EMPTY = 0
_SIDE_SHIFT = 4

RED = 0
BLUE = 1

RANK_RAT = int(Rank.RAT)
RANK_TIGER = int(Rank.TIGER)
RANK_LION = int(Rank.LION)
RANK_ELEPHANT = int(Rank.ELEPHANT)


def make_cell(side: int, rank: int) -> int:
    return rank | (side << _SIDE_SHIFT)


def rank_of(cell: int) -> int:
    return cell & 15


def side_of(cell: int) -> int:
    return (cell >> _SIDE_SHIFT) & 1


def pack_move(frm: int, to: int) -> int:
    return frm | (to << 6)


def move_from(move: int) -> int:
    return move & 63


def move_to(move: int) -> int:
    return (move >> 6) & 63


def _pos_of(idx: int) -> tuple[int, int]:
    return (idx // COLS, idx % COLS)


def to_model_move(move: int) -> Move:
    return Move(_pos_of(move_from(move)), _pos_of(move_to(move)))


def from_model_move(move: Move) -> int:
    return pack_move(move.from_pos[0] * COLS + move.from_pos[1],
                     move.to_pos[0] * COLS + move.to_pos[1])


class FastPosition:
    """Mutable position with make/undo and an incremental Zobrist key.

    Optionally carries incrementally maintained evaluation state (piece-square
    table scores, per-rank piece counts, and per-rank piece indices — each
    side has exactly one animal per rank) once ``attach_tables`` is called,
    so leaf evaluation is O(1) instead of a full board scan.
    """

    __slots__ = ("cells", "side", "move_count", "key", "piece_counts",
                 "key_history", "key_counts", "_undo",
                 "tables", "eval_scores", "rank_counts", "animal_idx")

    def __init__(self) -> None:
        self.cells: list[int] = [EMPTY] * 63
        self.side: int = RED
        self.move_count: int = 0
        self.key: int = 0
        self.piece_counts: list[int] = [0, 0]
        self.key_history: list[int] = []
        self.key_counts: dict[int, int] = {}
        self._undo: list[tuple[int, int]] = []
        self.tables = None
        self.eval_scores: list[int] = [0, 0]
        self.rank_counts: list[list[int]] = [[0] * 9, [0] * 9]
        self.animal_idx: list[list[int]] = [[-1] * 9, [-1] * 9]

    # -- construction -----------------------------------------------------

    @classmethod
    def from_game_state(cls, state: GameState) -> "FastPosition":
        pos = cls()
        for (row, col), piece in state.board.positions():
            side = zobrist.side_index(piece.side)
            pos.cells[row * COLS + col] = make_cell(side, int(piece.rank))
            pos.piece_counts[side] += 1
        pos.side = zobrist.side_index(state.current_side)
        pos.move_count = state.move_count
        pos.key = state.position_key
        pos.key_history = list(state.history)
        for key in pos.key_history:
            pos.key_counts[key] = pos.key_counts.get(key, 0) + 1
        return pos

    def attach_tables(self, tables) -> None:
        """Bind evaluation tables and compute incremental eval state once."""
        self.tables = tables
        scores = [0, 0]
        counts = [[0] * 9, [0] * 9]
        indices = [[-1] * 9, [-1] * 9]
        for idx in range(63):
            cell = self.cells[idx]
            if cell == EMPTY:
                continue
            side = side_of(cell)
            rank = rank_of(cell)
            scores[side] += tables.pst[side][rank][idx]
            counts[side][rank] += 1
            indices[side][rank] = idx
        self.eval_scores = scores
        self.rank_counts = counts
        self.animal_idx = indices

    # -- move generation ----------------------------------------------------

    def legal_moves(self) -> list[int]:
        """Packed legal moves for the side to move (mirrors the model)."""
        cells = self.cells
        side = self.side
        own_den = DEN_IDX[side]
        enemy_trap = TRAP_TABLE[side]  # enemy pieces there defend with rank 0
        moves: list[int] = []
        append = moves.append
        for idx in range(63):
            cell = cells[idx]
            if cell == EMPTY or side_of(cell) != side:
                continue
            rank = rank_of(cell)
            from_river = IS_RIVER[idx]
            for to in NEIGHBORS[idx]:
                terrain = TERRAIN[to]
                if terrain is Terrain.RIVER and rank != RANK_RAT:
                    continue
                if to == own_den:
                    continue
                occ = cells[to]
                if occ == EMPTY:
                    append(pack_move(idx, to))
                    continue
                if side_of(occ) == side:
                    continue
                if from_river != IS_RIVER[to]:
                    continue  # no land<->river captures
                defence = rank_of(occ)
                if rank == RANK_ELEPHANT and defence == RANK_RAT:
                    continue  # elephant never captures rat
                if rank == RANK_RAT and defence == RANK_ELEPHANT:
                    append(pack_move(idx, to))
                    continue
                if enemy_trap[to]:
                    defence = 0
                if rank >= defence:
                    append(pack_move(idx, to))
            if rank == RANK_TIGER or rank == RANK_LION:
                for landing, path in JUMPS[rank][idx]:
                    blocked = False
                    for square in path:
                        if cells[square] != EMPTY:
                            blocked = True  # a rat (either side) blocks the jump
                            break
                    if blocked:
                        continue
                    occ = cells[landing]
                    if occ == EMPTY:
                        append(pack_move(idx, landing))
                        continue
                    if side_of(occ) == side:
                        continue
                    defence = rank_of(occ)
                    if enemy_trap[landing]:
                        defence = 0
                    if rank >= defence:
                        append(pack_move(idx, landing))
        return moves

    # -- make / undo ----------------------------------------------------------

    def make(self, move: int) -> None:
        cells = self.cells
        frm = move & 63
        to = (move >> 6) & 63
        cell = cells[frm]
        captured = cells[to]
        self._undo.append((move, captured))

        key = self.key ^ zobrist.PIECE_KEYS[side_of(cell)][rank_of(cell)][frm]
        key ^= zobrist.PIECE_KEYS[side_of(cell)][rank_of(cell)][to]
        if captured != EMPTY:
            key ^= zobrist.PIECE_KEYS[side_of(captured)][rank_of(captured)][to]
            self.piece_counts[side_of(captured)] -= 1
        key ^= zobrist.SIDE_TO_MOVE_KEY

        tables = self.tables
        if tables is not None:
            side = side_of(cell)
            rank = rank_of(cell)
            self.eval_scores[side] += tables.pst[side][rank][to] - tables.pst[side][rank][frm]
            self.animal_idx[side][rank] = to
            if captured != EMPTY:
                cap_side = side_of(captured)
                cap_rank = rank_of(captured)
                self.eval_scores[cap_side] -= tables.pst[cap_side][cap_rank][to]
                self.rank_counts[cap_side][cap_rank] -= 1
                self.animal_idx[cap_side][cap_rank] = -1

        cells[to] = cell
        cells[frm] = EMPTY
        self.side ^= 1
        self.move_count += 1
        self.key = key
        self.key_history.append(key)
        self.key_counts[key] = self.key_counts.get(key, 0) + 1

    def undo(self) -> None:
        move, captured = self._undo.pop()
        frm = move & 63
        to = (move >> 6) & 63
        cells = self.cells
        cell = cells[to]

        tables = self.tables
        if tables is not None:
            side = side_of(cell)
            rank = rank_of(cell)
            self.eval_scores[side] -= tables.pst[side][rank][to] - tables.pst[side][rank][frm]
            self.animal_idx[side][rank] = frm
            if captured != EMPTY:
                cap_side = side_of(captured)
                cap_rank = rank_of(captured)
                self.eval_scores[cap_side] += tables.pst[cap_side][cap_rank][to]
                self.rank_counts[cap_side][cap_rank] += 1
                self.animal_idx[cap_side][cap_rank] = to

        remaining = self.key_counts[self.key] - 1
        if remaining:
            self.key_counts[self.key] = remaining
        else:
            # Keep the counter map exact — dead zero entries would accumulate
            # over a long search (game-history keys never reach zero).
            del self.key_counts[self.key]
        self.key_history.pop()
        self.side ^= 1
        self.move_count -= 1
        cells[frm] = cell
        cells[to] = captured
        if captured != EMPTY:
            self.piece_counts[side_of(captured)] += 1
        self.key = self.key_history[-1]

    # -- outcomes ---------------------------------------------------------------

    def winner(self) -> Optional[int]:
        """Winning side index, or None. (The no-legal-moves loss is detected
        by an empty move list, matching how search consumes it.)"""
        occupant = self.cells[DEN_IDX[RED]]
        if occupant != EMPTY and side_of(occupant) == BLUE:
            return BLUE
        occupant = self.cells[DEN_IDX[BLUE]]
        if occupant != EMPTY and side_of(occupant) == RED:
            return RED
        if self.piece_counts[RED] == 0:
            return BLUE
        if self.piece_counts[BLUE] == 0:
            return RED
        return None

    def is_repetition_draw(self) -> bool:
        return self.key_counts.get(self.key, 0) >= REPETITION_LIMIT

    def is_ply_cap_draw(self) -> bool:
        return self.move_count >= MAX_PLIES

    def model_side(self) -> Side:
        return Side.RED if self.side == RED else Side.BLUE

    def to_debug_grid(self) -> str:  # pragma: no cover - debugging aid
        rows = []
        for row in range(9):
            rows.append(" ".join(f"{self.cells[row * COLS + col]:2d}" for col in range(COLS)))
        return "\n".join(rows)
