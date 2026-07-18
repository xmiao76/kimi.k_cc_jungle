"""Fast incremental position for search.

Mirrors the rules of jungle.model.board exactly, but with a flat integer
board, make/undo, and incremental Zobrist keys. Correctness is enforced by
differential tests against the model (tests/engine/test_core_differential.py).

Piece encoding: 0 = empty; 1..8 = BLUE ranks; 9..16 = RED ranks (rank + 8).
Move encoding: from_idx | (to_idx << 6); the capture is implicit in the board.
"""

from __future__ import annotations

from jungle.engine import tables
from jungle.model.board import MAX_PLIES, REPETITION_LIMIT, Board, GameState, Move
from jungle.model.constants import COLS, ROWS, Rank, Side, Terrain
from jungle.model.zobrist import SIDE_KEY, TABLE, piece_code

EMPTY = 0
_RANK_RAT = Rank.RAT.value
_RANK_ELEPHANT = Rank.ELEPHANT.value
_RANK_LION = Rank.LION.value
_RANK_TIGER = Rank.TIGER.value


def code_of(side: Side, rank: Rank) -> int:
    """Return the cell piece code for a side and rank."""
    return piece_code(side, rank.value)


def rank_of(code: int) -> int:
    """Return the rank value (1..8) of a nonzero piece code."""
    return code if code <= 8 else code - 8


def side_of(code: int) -> Side:
    """Return the side of a nonzero piece code."""
    return Side.RED if code > 8 else Side.BLUE


def pack_move(from_idx: int, to_idx: int) -> int:
    return from_idx | (to_idx << 6)


def move_from(move: int) -> int:
    return move & 63


def move_to(move: int) -> int:
    return (move >> 6) & 63


def to_model_move(move: int) -> Move:
    """Convert a packed move to the model's Move type."""
    return Move(
        (move_from(move) // COLS, move_from(move) % COLS),
        (move_to(move) // COLS, move_to(move) % COLS),
    )


class FastPosition:
    """Mutable search position with make/undo and incremental hashing."""

    __slots__ = ("cells", "side", "key", "move_count", "piece_counts", "keys", "undo_stack")

    def __init__(
        self,
        cells: list[int],
        side: Side,
        move_count: int = 0,
        history: tuple[int, ...] = (),
    ) -> None:
        if len(cells) != tables.CELLS:
            raise ValueError("Invalid cell count")
        self.cells = cells
        self.side = side
        self.move_count = move_count
        key = SIDE_KEY if side is Side.RED else 0
        counts = [0, 0]
        for i, code in enumerate(cells):
            if code:
                key ^= TABLE[i][code]
                counts[0 if side_of(code) is Side.RED else 1] += 1
        self.key = key
        self.piece_counts = counts  # [RED, BLUE]
        self.keys = list(history)
        self.undo_stack: list[tuple[int, int, int, int]] = []

    @classmethod
    def from_game_state(cls, state: GameState) -> FastPosition:
        """Build a fast position from an immutable model state."""
        cells = [EMPTY] * tables.CELLS
        for pos in state.board.positions():
            piece = state.board.piece_at(pos)
            if piece is not None:
                cells[pos[0] * COLS + pos[1]] = code_of(piece.side, piece.rank)
        return cls(cells, state.current_side, state.move_count, state.history)

    def to_board(self) -> Board:
        """Rebuild the immutable model board (for tests and debugging)."""
        from jungle.model.board import Piece

        rows: list[list[Piece | None]] = []
        for r in range(ROWS):
            row: list[Piece | None] = []
            for c in range(COLS):
                code = self.cells[r * COLS + c]
                row.append(
                    None if code == EMPTY else Piece(side_of(code), Rank(rank_of(code)))
                )
            rows.append(row)
        return Board(tuple(tuple(row) for row in rows))

    # ------------------------------------------------------------------
    # Move generation (mirrors GameState._moves_for_piece order of checks)
    # ------------------------------------------------------------------

    def legal_moves(self) -> list[int]:
        """Return all legal packed moves for the side to move."""
        cells = self.cells
        side = self.side
        own_den = tables.DEN_IDX[side]
        moves: list[int] = []
        for i, code in enumerate(cells):
            if code == EMPTY or side_of(code) is not side:
                continue
            rank = rank_of(code)
            for nb in tables.NEIGHBORS[i]:
                if tables.IS_RIVER[nb] and rank != _RANK_RAT:
                    continue
                if nb == own_den:
                    continue
                target = cells[nb]
                if target != EMPTY and not self._can_capture(code, i, nb, target):
                    continue
                moves.append(i | (nb << 6))
            if rank == _RANK_LION:
                jumps = tables.JUMPS_LION[i]
            elif rank == _RANK_TIGER:
                jumps = tables.JUMPS_TIGER[i]
            else:
                continue
            for landing, crossed in jumps:
                blocked = False
                for sq in crossed:
                    sq_code = cells[sq]
                    if sq_code != EMPTY and rank_of(sq_code) == _RANK_RAT:
                        blocked = True
                        break
                if blocked:
                    continue
                target = cells[landing]
                if target != EMPTY and not self._can_capture(code, i, landing, target):
                    continue
                moves.append(i | (landing << 6))
        return moves

    def has_legal_move(self) -> bool:
        """Return True if the side to move has at least one legal move."""
        cells = self.cells
        side = self.side
        own_den = tables.DEN_IDX[side]
        for i, code in enumerate(cells):
            if code == EMPTY or side_of(code) is not side:
                continue
            rank = rank_of(code)
            for nb in tables.NEIGHBORS[i]:
                if tables.IS_RIVER[nb] and rank != _RANK_RAT:
                    continue
                if nb == own_den:
                    continue
                target = cells[nb]
                if target == EMPTY or self._can_capture(code, i, nb, target):
                    return True
            if rank == _RANK_LION:
                jumps = tables.JUMPS_LION[i]
            elif rank == _RANK_TIGER:
                jumps = tables.JUMPS_TIGER[i]
            else:
                continue
            for landing, crossed in jumps:
                if any(
                    (sq_code := cells[sq]) != EMPTY and rank_of(sq_code) == _RANK_RAT
                    for sq in crossed
                ):
                    continue
                target = cells[landing]
                if target == EMPTY or self._can_capture(code, i, landing, target):
                    return True
        return False

    def _can_capture(self, attacker: int, from_idx: int, to_idx: int, target: int) -> bool:
        """Mirror GameState._can_capture (see model for rule references)."""
        if side_of(attacker) is side_of(target):
            return False
        attacker_rank = rank_of(attacker)
        target_rank = rank_of(target)
        # Defender in a trap belonging to the attacker's side has rank 0.
        terrain = tables.TERRAIN[to_idx]
        if side_of(attacker) is Side.RED:
            defender_rank = 0 if terrain is Terrain.TRAP_RED else target_rank
        else:
            defender_rank = 0 if terrain is Terrain.TRAP_BLUE else target_rank

        if attacker_rank == _RANK_RAT:
            attacker_in_water = tables.IS_RIVER[from_idx]
            target_in_water = tables.IS_RIVER[to_idx]
            if attacker_in_water:
                return target_in_water and target_rank == _RANK_RAT
            if target_in_water:
                return False
            if target_rank == _RANK_ELEPHANT:
                return True
            return attacker_rank >= defender_rank

        if target_rank == _RANK_RAT:
            if attacker_rank == _RANK_ELEPHANT:
                return False
            if tables.IS_RIVER[to_idx]:
                return False

        return attacker_rank >= defender_rank

    # ------------------------------------------------------------------
    # Make / undo
    # ------------------------------------------------------------------

    def make(self, move: int) -> None:
        """Apply a packed move, pushing an undo record."""
        cells = self.cells
        from_idx = move & 63
        to_idx = move >> 6
        piece = cells[from_idx]
        captured = cells[to_idx]
        self.undo_stack.append((move, captured, self.key, self.move_count))
        self.keys.append(self.key)

        new_key = self.key ^ TABLE[from_idx][piece] ^ TABLE[to_idx][piece] ^ SIDE_KEY
        if captured != EMPTY:
            new_key ^= TABLE[to_idx][captured]
            self.piece_counts[0 if side_of(captured) is Side.RED else 1] -= 1
        cells[from_idx] = EMPTY
        cells[to_idx] = piece
        self.key = new_key
        self.side = Side.BLUE if self.side is Side.RED else Side.RED
        self.move_count += 1

    def undo(self) -> None:
        """Revert the most recent make()."""
        move, captured, old_key, old_count = self.undo_stack.pop()
        cells = self.cells
        from_idx = move & 63
        to_idx = move >> 6
        piece = cells[to_idx]
        cells[from_idx] = piece
        cells[to_idx] = captured
        if captured != EMPTY:
            self.piece_counts[0 if side_of(captured) is Side.RED else 1] += 1
        self.side = Side.BLUE if self.side is Side.RED else Side.RED
        self.key = old_key
        self.move_count = old_count
        self.keys.pop()

    # ------------------------------------------------------------------
    # Terminal / draw queries
    # ------------------------------------------------------------------

    def winner(self) -> Side | None:
        """Return the winner by den entry or elimination (cheap checks)."""
        red_den = self.cells[tables.DEN_IDX[Side.RED]]
        if red_den != EMPTY and side_of(red_den) is Side.BLUE:
            return Side.BLUE
        blue_den = self.cells[tables.DEN_IDX[Side.BLUE]]
        if blue_den != EMPTY and side_of(blue_den) is Side.RED:
            return Side.RED
        if self.piece_counts[0] == 0:
            return Side.BLUE
        if self.piece_counts[1] == 0:
            return Side.RED
        return None

    def is_repetition(self) -> bool:
        """Return True if the current position occurred before on the path."""
        return self.key in self.keys

    def is_draw(self) -> bool:
        """Return True by threefold repetition or the ply cap (model rules)."""
        return (
            self.keys.count(self.key) >= REPETITION_LIMIT - 1
            or self.move_count >= MAX_PLIES
        )

    def is_terminal(self) -> tuple[bool, Side | None, bool]:
        """Mirror GameState terminal semantics: (over, winner, draw).

        Order matches the model: den/elimination, then stalemate, then draw.
        """
        w = self.winner()
        if w is not None:
            return True, w, False
        if not self.has_legal_move():
            return True, Side.BLUE if self.side is Side.RED else Side.RED, False
        if self.is_draw():
            return True, None, True
        return False, None, False
