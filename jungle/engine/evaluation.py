"""Static evaluation for the fast core.

Strength lives here by design: gauntlet measurements on this game showed
fancy search pruning (LMR, SEE, aspiration) gains nothing, while evaluation
terms win games.

Structure: every per-(side, rank, square) term is folded into a
piece-square table (PST) built once from ``EvalWeights`` and then maintained
incrementally by ``FastPosition.make/undo``, so a leaf evaluation is a
couple of array reads instead of a full board scan. Only the conditional
elephant/rat interaction terms are computed at the leaf (from the
incrementally maintained per-rank counts).

Term families (deliberately few and orthogonal):

* material            — per-rank piece values
* advancement         — pieces earn more the closer they are to the enemy den
* den approach        — extra bonus one step away from the enemy den
* trap danger         — own piece standing in an enemy trap is at risk
* elephant/rat        — elephant devalued while the enemy rat lives; the rat
                        is more valuable while the enemy elephant lives
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jungle.engine.core import FastPosition
from jungle.engine.tables import CELL_DIST, DIST_TO_DEN, IS_RIVER, MAX_DEN_DIST, TRAP_TABLE
from jungle.model.board import GameState

RANK_RAT = 1
RANK_ELEPHANT = 8

# rank 0 slot unused; ranks are 1..8
_DEFAULT_MATERIAL = (0, 100, 180, 260, 340, 420, 560, 700, 900)


@dataclass(frozen=True)
class EvalWeights:
    material: tuple[int, ...] = field(default=_DEFAULT_MATERIAL)
    advancement: int = 8
    den_approach: int = 50
    trap_danger: int = 40
    elephant_rat_penalty: int = 120
    rat_utility_bonus: int = 60
    # Optional per-rank advancement override (index by rank; 0 unused).
    advancement_per_rank: Optional[tuple[int, ...]] = None
    # Bonus for a piece guarding its own den (distance <= 2). Gauntlet-verified
    # vs the v1 baseline: 8/8 wins at fixed depth (see project notes).
    den_defense: int = 12
    # Bonus for the rat standing on a river square — measured HARMFUL (0/8),
    # kept at 0; do not enable without a winning gauntlet.
    rat_river: int = 0
    # Proximity-scaled rat/elephant bonus — measured HARMFUL as a replacement
    # for the flat utility (0/8), kept at 0.
    rat_elephant_proximity: int = 0


DEFAULT_WEIGHTS = EvalWeights()

# Material-only profile used by the legacy baseline engine.
MATERIAL_ONLY = EvalWeights(
    advancement=0,
    den_approach=0,
    trap_danger=0,
    elephant_rat_penalty=0,
    rat_utility_bonus=0,
)


@dataclass(frozen=True)
class EvalTables:
    """Precomputed evaluation tables. ``pst[side][rank][idx]`` folds every
    per-(side, rank, square) term into one lookup; the conditional terms are
    kept as scalars for the leaf formula."""

    pst: tuple[tuple[tuple[int, ...], ...], ...]
    elephant_rat_penalty: int
    rat_utility_bonus: int
    rat_elephant_proximity: int


def build_tables(weights: EvalWeights = DEFAULT_WEIGHTS) -> EvalTables:
    advancement = (
        weights.advancement_per_rank
        if weights.advancement_per_rank is not None
        else tuple([weights.advancement] * 9)
    )
    pst = []
    for side in (0, 1):
        side_tables = [tuple([0] * 63)]  # rank 0 unused
        for rank in range(1, 9):
            row = []
            for idx in range(63):
                dist = DIST_TO_DEN[side ^ 1][idx]
                value = weights.material[rank] + advancement[rank] * (MAX_DEN_DIST - dist)
                if dist == 1:
                    value += weights.den_approach
                if TRAP_TABLE[side ^ 1][idx]:
                    value -= weights.trap_danger
                if weights.den_defense and DIST_TO_DEN[side][idx] <= 2:
                    value += weights.den_defense
                if rank == RANK_RAT and weights.rat_river and IS_RIVER[idx]:
                    value += weights.rat_river
                row.append(value)
            side_tables.append(tuple(row))
        pst.append(tuple(side_tables))
    return EvalTables(
        pst=tuple(pst),
        elephant_rat_penalty=weights.elephant_rat_penalty,
        rat_utility_bonus=weights.rat_utility_bonus,
        rat_elephant_proximity=weights.rat_elephant_proximity,
    )


def evaluate_fast(pos: FastPosition, tables: EvalTables) -> int:
    """Static score from the side-to-move's perspective (O(1) amortized)."""
    side = pos.side
    enemy = side ^ 1
    counts = pos.rank_counts
    score = pos.eval_scores[side] - pos.eval_scores[enemy]
    if counts[side][RANK_ELEPHANT] and counts[enemy][RANK_RAT]:
        score -= tables.elephant_rat_penalty
    if counts[side][RANK_RAT] and counts[enemy][RANK_ELEPHANT]:
        score += tables.rat_utility_bonus
    if counts[enemy][RANK_ELEPHANT] and counts[side][RANK_RAT]:
        score += tables.elephant_rat_penalty
    if counts[enemy][RANK_RAT] and counts[side][RANK_ELEPHANT]:
        score -= tables.rat_utility_bonus
    if tables.rat_elephant_proximity:
        indices = pos.animal_idx
        for owner, rival in ((side, enemy), (enemy, side)):
            rat = indices[owner][RANK_RAT]
            elephant = indices[rival][RANK_ELEPHANT]
            if rat >= 0 and elephant >= 0:
                bonus = tables.rat_elephant_proximity * max(0, 8 - CELL_DIST[rat][elephant])
                score += bonus if owner == side else -bonus
    return score


def evaluate_state(state: GameState, weights: EvalWeights = DEFAULT_WEIGHTS) -> int:
    """Convenience wrapper for tooling: evaluate an immutable state."""
    tables = build_tables(weights)
    pos = FastPosition.from_game_state(state)
    pos.attach_tables(tables)
    return evaluate_fast(pos, tables)
