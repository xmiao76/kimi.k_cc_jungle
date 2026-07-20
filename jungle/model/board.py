"""Immutable game state and the complete Jungle / Dou Shou Qi ruleset.

This module is the rules of record. The engine's fast core mirrors it
exactly; the differential tests under ``tests/engine/`` enforce that.

Locked rule interpretations (documented in the release README):

* Ranks rat 1 < cat 2 < dog 3 < wolf 4 < leopard 5 < tiger 6 < lion 7 <
  elephant 8; a piece captures an enemy of equal or lower rank.
* Only the rat enters the river. A rat in the river captures only an enemy
  rat in the river; no captures happen between land and river in either
  direction. The rat captures the elephant (land squares only); the
  elephant never captures the rat.
* The lion jumps the river horizontally AND vertically; the tiger jumps
  horizontally ONLY (chosen variant). Any rat of either side standing on a
  crossed river square blocks the jump. Captures on the landing square
  follow the normal rules.
* A piece inside one of the OPPONENT's traps defends with rank 0 but still
  attacks with its normal rank. A piece in its own trap is unaffected.
* A piece may never enter its own den.
* Wins: entering the opponent's den, capturing every enemy piece, or
  leaving the side to move with no legal moves.
* Draws: the same position (placement + side to move) occurring three
  times, or 200 plies without a result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional

from jungle.model import zobrist
from jungle.model.constants import (
    COLS,
    DEN_POSITIONS,
    ROWS,
    TRAP_POSITIONS,
    Rank,
    Side,
    Terrain,
    initial_layout,
    orthogonal_neighbors,
    river_jump_paths,
    terrain_at,
)

MAX_PLIES = 200
REPETITION_LIMIT = 3

Position = tuple[int, int]


class IllegalMoveError(ValueError):
    """Raised when applying a move that is not legal in the position."""


@dataclass(frozen=True)
class Piece:
    side: Side
    rank: Rank

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        return f"{self.side.name} {self.rank.name}"


@dataclass(frozen=True)
class Move:
    from_pos: Position
    to_pos: Position

    def __str__(self) -> str:
        fr, fc = self.from_pos
        tr, tc = self.to_pos
        return f"({fr},{fc})->({tr},{tc})"


class Board:
    """Immutable piece placement: a 9x7 tuple grid of ``Piece | None``."""

    __slots__ = ("_cells",)

    def __init__(self, cells: tuple[tuple[Optional[Piece], ...], ...]) -> None:
        self._cells = cells

    @classmethod
    def empty(cls) -> "Board":
        return cls(tuple(tuple(None for _ in range(COLS)) for _ in range(ROWS)))

    @classmethod
    def starting(cls) -> "Board":
        return cls.from_pieces(
            {pos: Piece(side, rank) for pos, (side, rank) in initial_layout().items()}
        )

    @classmethod
    def from_pieces(cls, pieces: dict[Position, Piece]) -> "Board":
        """Build a board from a sparse {position: piece} mapping (test aid)."""
        grid = [[None for _ in range(COLS)] for _ in range(ROWS)]
        for (row, col), piece in pieces.items():
            grid[row][col] = piece
        return cls(tuple(tuple(row) for row in grid))

    def piece_at(self, pos: Position) -> Optional[Piece]:
        row, col = pos
        return self._cells[row][col]

    def positions(self) -> Iterator[tuple[Position, Piece]]:
        """Yield (position, piece) for every occupied square, row-major."""
        for row in range(ROWS):
            for col in range(COLS):
                piece = self._cells[row][col]
                if piece is not None:
                    yield (row, col), piece

    def count_pieces(self, side: Side) -> int:
        return sum(1 for _, piece in self.positions() if piece.side is side)

    def with_piece_moved(self, from_pos: Position, to_pos: Position) -> "Board":
        """New board with the piece moved from→to (capturing any occupant)."""
        piece = self.piece_at(from_pos)
        if piece is None:
            raise IllegalMoveError(f"no piece at {from_pos}")
        grid = [list(row) for row in self._cells]
        grid[from_pos[0]][from_pos[1]] = None
        grid[to_pos[0]][to_pos[1]] = piece
        return Board(tuple(tuple(row) for row in grid))

    def rotate_180(self) -> "Board":
        """The position from the other player's viewpoint: the board rotated
        180 degrees with every piece's side swapped. The starting position is
        invariant under this transform."""
        grid = [[None for _ in range(COLS)] for _ in range(ROWS)]
        for (row, col), piece in self.positions():
            grid[ROWS - 1 - row][COLS - 1 - col] = Piece(piece.side.opponent, piece.rank)
        return Board(tuple(tuple(row) for row in grid))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Board) and self._cells == other._cells

    def __hash__(self) -> int:
        return hash(self._cells)


# ---------------------------------------------------------------------------
# Capture and movement rules
# ---------------------------------------------------------------------------


def _defense_rank(piece: Piece, pos: Position) -> int:
    """A piece defending inside an opponent's trap counts as rank 0."""
    if pos in TRAP_POSITIONS[piece.side.opponent]:
        return 0
    return int(piece.rank)


def can_capture(attacker: Piece, from_pos: Position, defender: Piece, def_pos: Position) -> bool:
    """Whether ``attacker`` at ``from_pos`` may capture ``defender`` at ``def_pos``."""
    attacker_in_river = terrain_at(from_pos) is Terrain.RIVER
    defender_in_river = terrain_at(def_pos) is Terrain.RIVER
    if attacker_in_river != defender_in_river:
        # No captures between land and river, in either direction.
        return False
    if attacker.rank is Rank.ELEPHANT and defender.rank is Rank.RAT:
        return False  # the elephant never captures the rat
    if attacker.rank is Rank.RAT and defender.rank is Rank.ELEPHANT:
        return True  # the rat captures the elephant (both on land here)
    return int(attacker.rank) >= _defense_rank(defender, def_pos)


def _can_enter(board: Board, piece: Piece, from_pos: Position, target: Position) -> bool:
    terrain = terrain_at(target)
    if terrain is Terrain.RIVER and piece.rank is not Rank.RAT:
        return False
    if target == DEN_POSITIONS[piece.side]:
        return False  # never enter your own den
    occupant = board.piece_at(target)
    if occupant is None:
        return True
    if occupant.side is piece.side:
        return False
    return can_capture(piece, from_pos, occupant, target)


def _jump_is_blocked(board: Board, path: tuple[Position, ...]) -> bool:
    # Only rats can occupy river squares, so any occupant on the crossed
    # river squares is a rat (of either side) blocking the jump.
    return any(board.piece_at(square) is not None for square in path)


def piece_moves(board: Board, pos: Position) -> tuple[Move, ...]:
    """All legal destinations for the piece at ``pos`` (pseudo-game context)."""
    piece = board.piece_at(pos)
    if piece is None:
        return ()
    moves: list[Move] = []
    for target in orthogonal_neighbors(pos):
        if _can_enter(board, piece, pos, target):
            moves.append(Move(pos, target))
    for landing, path in river_jump_paths(pos, piece.rank):
        if not _jump_is_blocked(board, path) and _can_enter(board, piece, pos, landing):
            moves.append(Move(pos, landing))
    return tuple(moves)


# ---------------------------------------------------------------------------
# Game state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GameState:
    """A full game position: board, side to move, ply count, key history."""

    board: Board
    current_side: Side
    move_count: int
    history: tuple[int, ...]

    @classmethod
    def starting(cls) -> "GameState":
        state = cls(board=Board.starting(), current_side=Side.RED, move_count=0, history=())
        return cls(
            board=state.board,
            current_side=state.current_side,
            move_count=0,
            history=(state.position_key,),
        )

    @classmethod
    def from_pieces(
        cls,
        pieces: dict[Position, Piece],
        current_side: Side = Side.RED,
        move_count: int = 0,
    ) -> "GameState":
        """Custom-position state (test aid); history holds just this key."""
        state = cls(board=Board.from_pieces(pieces), current_side=current_side,
                    move_count=move_count, history=())
        return cls(state.board, current_side, move_count, (state.position_key,))

    @property
    def position_key(self) -> int:
        key = 0
        for pos, piece in self.board.positions():
            key ^= zobrist.piece_key_at(piece.side, piece.rank, pos)
        if self.current_side is Side.BLUE:
            key ^= zobrist.SIDE_TO_MOVE_KEY
        return key

    # -- move access ------------------------------------------------------

    def _generate_moves(self) -> tuple[Move, ...]:
        moves: list[Move] = []
        for pos, piece in self.board.positions():
            if piece.side is self.current_side:
                moves.extend(piece_moves(self.board, pos))
        return tuple(moves)

    def _has_legal_move(self) -> bool:
        return any(
            piece.side is self.current_side and piece_moves(self.board, pos)
            for pos, piece in self.board.positions()
        )

    def legal_moves(self) -> tuple[Move, ...]:
        """Legal moves for the side to move; empty once the game is over."""
        if self.is_game_over:
            return ()
        return self._generate_moves()

    def is_legal_move(self, move: Move) -> bool:
        return move in set(self.legal_moves())

    def apply_move(self, move: Move) -> "GameState":
        """Play a legal move, returning the resulting state."""
        if self.is_game_over:
            raise IllegalMoveError("the game is already over")
        if move not in set(self._generate_moves()):
            raise IllegalMoveError(f"illegal move {move}")
        new_board = self.board.with_piece_moved(move.from_pos, move.to_pos)
        new_state = GameState(
            board=new_board,
            current_side=self.current_side.opponent,
            move_count=self.move_count + 1,
            history=(),
        )
        return GameState(
            board=new_board,
            current_side=new_state.current_side,
            move_count=new_state.move_count,
            history=self.history + (new_state.position_key,),
        )

    # -- outcome ----------------------------------------------------------

    def _outcome(self) -> tuple[Optional[Side], bool, Optional[str]]:
        """(winner, is_draw, reason); reason in {den, elimination, no_moves,
        move_limit, repetition}."""
        for side, den in DEN_POSITIONS.items():
            occupant = self.board.piece_at(den)
            if occupant is not None and occupant.side is not side:
                return occupant.side, False, "den"
        for side in (Side.RED, Side.BLUE):
            if self.board.count_pieces(side) == 0:
                return side.opponent, False, "elimination"
        if not self._has_legal_move():
            return self.current_side.opponent, False, "no_moves"
        if self.move_count >= MAX_PLIES:
            return None, True, "move_limit"
        if self.history.count(self.position_key) >= REPETITION_LIMIT:
            return None, True, "repetition"
        return None, False, None

    @property
    def winner(self) -> Optional[Side]:
        return self._outcome()[0]

    @property
    def is_draw(self) -> bool:
        return self._outcome()[1]

    @property
    def is_game_over(self) -> bool:
        winner, is_draw, _ = self._outcome()
        return winner is not None or is_draw

    @property
    def game_over_reason(self) -> Optional[str]:
        return self._outcome()[2]
