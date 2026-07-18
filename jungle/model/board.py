"""Core game model: pieces, board, moves, and game state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from jungle.model.constants import (
    COLS,
    DEN_POSITIONS,
    INITIAL_LAYOUT,
    RIVER_SQUARES,
    ROWS,
    Rank,
    Side,
    Terrain,
    terrain_at,
)
from jungle.model.zobrist import position_key


class IllegalMoveError(Exception):
    """Raised when an illegal move is attempted."""


# A game is drawn once this many plies (half-moves) have been played.
MAX_PLIES = 200

# A game is drawn when the same position occurs this many times.
REPETITION_LIMIT = 3


@dataclass(frozen=True)
class Piece:
    """A game piece with a side and rank."""

    side: Side
    rank: Rank

    def __repr__(self) -> str:
        return f"{self.side.name[0]}{self.rank.name[0]}"


@dataclass(frozen=True)
class Move:
    """A move from one board square to another."""

    from_pos: tuple[int, int]
    to_pos: tuple[int, int]


class Board:
    """Immutable representation of the 9×7 Jungle board."""

    ROWS = ROWS
    COLS = COLS

    def __init__(self, pieces: tuple[tuple[Piece | None, ...], ...] | None = None) -> None:
        if pieces is None:
            pieces = self._starting_pieces()
        if len(pieces) != self.ROWS or any(len(row) != self.COLS for row in pieces):
            raise ValueError("Invalid board dimensions")
        self._pieces = pieces

    @classmethod
    def starting(cls) -> Board:
        """Return the standard starting board."""
        return cls()

    @classmethod
    def empty(cls) -> Board:
        """Return an empty board."""
        pieces = tuple(tuple(None for _ in range(cls.COLS)) for _ in range(cls.ROWS))
        return cls(pieces)

    @staticmethod
    def _starting_pieces() -> tuple[tuple[Piece | None, ...], ...]:
        return tuple(
            tuple(
                Piece(entry[0], entry[1]) if (entry := INITIAL_LAYOUT[row][col]) is not None else None
                for col in range(COLS)
            )
            for row in range(ROWS)
        )

    def piece_at(self, pos: tuple[int, int]) -> Piece | None:
        row, col = pos
        return self._pieces[row][col]

    def positions(self) -> Iterable[tuple[int, int]]:
        """Yield every board position in row-major order."""
        for row in range(self.ROWS):
            for col in range(self.COLS):
                yield (row, col)

    def with_piece_moved(self, from_pos: tuple[int, int], to_pos: tuple[int, int]) -> Board:
        """Return a new board with the piece at `from_pos` moved to `to_pos`."""
        piece = self.piece_at(from_pos)
        if piece is None:
            raise IllegalMoveError(f"No piece at {from_pos}")

        new_rows: list[list[Piece | None]] = [list(row) for row in self._pieces]
        new_rows[from_pos[0]][from_pos[1]] = None
        new_rows[to_pos[0]][to_pos[1]] = piece
        return Board(tuple(tuple(row) for row in new_rows))

    def rotate_180(self) -> Board:
        """Return a board rotated 180°. Useful for symmetry tests."""
        new_rows = tuple(
            tuple(
                self.piece_at((self.ROWS - 1 - row, self.COLS - 1 - col))
                for col in range(self.COLS)
            )
            for row in range(self.ROWS)
        )
        return Board(new_rows)


@dataclass(frozen=True)
class GameState:
    """Immutable snapshot of a game in progress.

    `history` holds the Zobrist keys of all ancestor positions (excluding
    this state); it drives the threefold-repetition draw rule.
    """

    board: Board
    current_side: Side
    winner: Side | None = None
    move_count: int = 0
    draw: bool = False
    history: tuple[int, ...] = ()

    def legal_moves(self) -> list[Move]:
        """Return all legal moves for the current side."""
        moves: list[Move] = []
        for pos in self.board.positions():
            piece = self.board.piece_at(pos)
            if piece is None or piece.side != self.current_side:
                continue
            moves.extend(self._moves_for_piece(pos, piece))
        return moves

    def is_legal_move(self, move: Move) -> bool:
        """Return True if `move` is legal in the current state."""
        piece = self.board.piece_at(move.from_pos)
        if piece is None or piece.side != self.current_side:
            return False
        return move in self._moves_for_piece(move.from_pos, piece)

    def has_legal_move(self) -> bool:
        """Return True if the current side has at least one legal move."""
        for pos in self.board.positions():
            piece = self.board.piece_at(pos)
            if piece is None or piece.side != self.current_side:
                continue
            if self._moves_for_piece(pos, piece):
                return True
        return False

    def after_move(self, move: Move) -> GameState:
        """Return the game state after applying `move`."""
        if self.winner is not None or self.draw:
            raise IllegalMoveError("Game is already over")
        if not self.is_legal_move(move):
            raise IllegalMoveError(f"Illegal move: {move}")

        new_board = self.board.with_piece_moved(move.from_pos, move.to_pos)
        new_side = self.current_side.opponent()
        new_count = self.move_count + 1

        winner = self._determine_winner(new_board, new_side, self.current_side)

        new_key = position_key(new_board, new_side)
        new_history = self.history + (position_key(self.board, self.current_side),)
        draw = (
            winner is None
            and (
                new_history.count(new_key) >= REPETITION_LIMIT - 1
                or new_count >= MAX_PLIES
            )
        )
        return GameState(
            board=new_board,
            current_side=new_side,
            winner=winner,
            move_count=new_count,
            draw=draw,
            history=new_history,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _moves_for_piece(self, pos: tuple[int, int], piece: Piece) -> list[Move]:
        moves: list[Move] = []
        for direction in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            moves.extend(self._step_moves(pos, piece, direction))
            moves.extend(self._jump_moves(pos, piece, direction))
        return moves

    def _step_moves(
        self,
        pos: tuple[int, int],
        piece: Piece,
        direction: tuple[int, int],
    ) -> list[Move]:
        new_row = pos[0] + direction[0]
        new_col = pos[1] + direction[1]
        new_pos = (new_row, new_col)

        if not self._is_inside(new_pos):
            return []

        target_terrain = terrain_at(new_pos)
        if target_terrain is Terrain.RIVER and piece.rank is not Rank.RAT:
            return []

        if target_terrain is Terrain.DEN_RED and piece.side is Side.RED:
            return []
        if target_terrain is Terrain.DEN_BLUE and piece.side is Side.BLUE:
            return []

        target = self.board.piece_at(new_pos)
        if target is not None and not self._can_capture(piece, pos, new_pos, target):
            return []

        return [Move(pos, new_pos)]

    def _jump_moves(
        self,
        pos: tuple[int, int],
        piece: Piece,
        direction: tuple[int, int],
    ) -> list[Move]:
        """Generate lion/tiger river jumps for `piece` along `direction`."""
        if piece.rank not in (Rank.LION, Rank.TIGER):
            return []

        # Tigers may only jump horizontally (the 2-cell river span); lions
        # jump horizontally and vertically (2- or 3-cell spans).
        if piece.rank is Rank.TIGER and direction[0] != 0:
            return []

        # Jumps are only horizontal or vertical by more than one square.
        dr, dc = direction
        if (dr == 0) == (dc == 0):
            return []

        row, col = pos
        landing_row, landing_col = row, col
        river_squares: list[tuple[int, int]] = []

        # Walk in the direction until we leave the board or land on non-river.
        while True:
            landing_row += dr
            landing_col += dc
            if not self._is_inside((landing_row, landing_col)):
                return []
            current_terrain = terrain_at((landing_row, landing_col))
            if current_terrain is not Terrain.RIVER:
                break
            river_squares.append((landing_row, landing_col))

        # Must have crossed at least one river square and landed on land.
        if not river_squares:
            return []

        landing_pos = (landing_row, landing_col)
        if terrain_at(landing_pos) in (Terrain.RIVER,):
            return []

        # Blocked if any rat occupies an intervening river square.
        for river_pos in river_squares:
            blocker = self.board.piece_at(river_pos)
            if blocker is not None and blocker.rank is Rank.RAT:
                return []

        # Landing square must be empty or capturable.
        target = self.board.piece_at(landing_pos)
        if target is not None and not self._can_capture(piece, pos, landing_pos, target):
            return []

        return [Move(pos, landing_pos)]

    def _can_capture(
        self,
        attacker: Piece,
        attacker_pos: tuple[int, int],
        target_pos: tuple[int, int],
        target: Piece,
    ) -> bool:
        if attacker.side is target.side:
            return False

        # Attacker uses its normal rank even when standing in an opponent trap;
        # defender's rank is reduced to 0 while in an opponent trap.
        attacker_rank = attacker.rank.value
        defender_rank = self._effective_rank(target, target_pos)

        # Special rat rules (Wikipedia: the rat captures the elephant "only
        # from a land square, not from a water square"; a rat in the water
        # "can only be killed by another rat in the water"). Interpretation:
        # rats capture each other only within the same medium.
        if attacker.rank is Rank.RAT:
            attacker_in_water = terrain_at(attacker_pos) is Terrain.RIVER
            target_in_water = terrain_at(target_pos) is Terrain.RIVER
            if attacker_in_water:
                # Rat in water can only capture an enemy rat in water.
                return target_in_water and target.rank is Rank.RAT
            if target_in_water:
                # A rat on land cannot capture a rat in the water.
                return False
            # Rat on land can capture elephant on land.
            if target.rank is Rank.ELEPHANT:
                return True
            return attacker_rank >= defender_rank

        if target.rank is Rank.RAT:
            # Elephant cannot capture rat.
            if attacker.rank is Rank.ELEPHANT:
                return False
            # Land pieces cannot capture rat in river.
            if terrain_at(target_pos) is Terrain.RIVER:
                return False

        return attacker_rank >= defender_rank

    def _effective_rank(self, piece: Piece, pos: tuple[int, int]) -> int:
        terrain = terrain_at(pos)
        if (terrain is Terrain.TRAP_RED and piece.side is Side.RED) or (
            terrain is Terrain.TRAP_BLUE and piece.side is Side.BLUE
        ):
            return piece.rank.value
        if terrain in (Terrain.TRAP_RED, Terrain.TRAP_BLUE):
            # Piece is in an opponent trap: rank reduced to 0.
            return 0
        return piece.rank.value

    def _determine_winner(
        self,
        board: Board,
        next_side: Side,
        moving_side: Side,
    ) -> Side | None:
        # Win by entering the opponent's den.
        for side, den_pos in DEN_POSITIONS.items():
            piece = board.piece_at(den_pos)
            if piece is not None and piece.side != side:
                return piece.side

        # Win by capturing all enemy pieces.
        sides_with_pieces: set[Side] = set()
        for pos in board.positions():
            piece = board.piece_at(pos)
            if piece is not None:
                sides_with_pieces.add(piece.side)
        if len(sides_with_pieces) == 1:
            return sides_with_pieces.pop()

        # Stalemate: side to move has no legal moves loses.
        state = GameState(board=board, current_side=next_side, move_count=self.move_count + 1)
        if not state.has_legal_move():
            return moving_side

        return None

    @staticmethod
    def _is_inside(pos: tuple[int, int]) -> bool:
        row, col = pos
        return 0 <= row < Board.ROWS and 0 <= col < Board.COLS


def starting_state(human_first: bool = True) -> GameState:
    """Return a fresh game state.

    RED always moves first by standard rules. `human_first` is retained for
    API compatibility; the human/AI side assignment is a GUI concern.
    """
    return GameState(board=Board.starting(), current_side=Side.RED)
