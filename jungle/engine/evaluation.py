"""Static evaluation for Jungle / Dou Shou Qi positions.

Tapered evaluation (middlegame/endgame) over material, development,
rat-elephant dynamics, traps, lion/tiger jump threats, den pressure,
mobility, and an endgame den-race term. Weights live in the frozen
`EvalWeights` dataclass so engine generations can be compared: `V2_WEIGHTS`
freezes the previous generation (new terms disabled), `DEFAULT_WEIGHTS` is
the current tuned set.

`evaluate_fast` works on the engine's FastPosition and returns a score from
the side to move's perspective (negamax convention). It is the hottest
function in the engine — keep enum attribute access and division out of the
per-piece loop. `evaluate` keeps the original public signature.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from jungle.engine import tables
from jungle.engine.core import EMPTY, FastPosition, rank_of, side_of
from jungle.model.board import GameState
from jungle.model.constants import Rank, Side, Terrain

# Integer rank constants for the hot loop (enum .value access is slow).
_RAT = 1
_LION = 7
_ELEPHANT = 8


@dataclass(frozen=True)
class EvalWeights:
    """All evaluation weights in one frozen, comparable bundle."""

    # Material by rank value (index 0 unused), middlegame / endgame.
    mg_values: tuple[int, ...] = (0, 100, 160, 200, 240, 300, 450, 520, 600)
    eg_values: tuple[int, ...] = (0, 120, 160, 200, 240, 310, 470, 560, 620)
    # Rat-elephant interplay: the elephant is fragile while the enemy rat lives.
    elephant_vs_rat_penalty: int = 150
    rat_vs_elephant_bonus: int = 50
    # Positional terms.
    trapped_penalty: int = 40            # own piece sitting in an enemy trap
    trap_capture_threat_bonus: int = 30  # our piece adjacent to an enemy trapped in OUR trap
    jump_threat_bonus: int = 25          # lion/tiger with an unblocked river jump
    rat_river_bonus: int = 30            # rat in the river
    advanced_rat_bonus: int = 4          # per row a rat has advanced into the enemy half
    den_guard_bonus: int = 35            # piece adjacent to its own den
    den_pressure: int = 12               # per step of proximity of our closest piece to the enemy den
    mobility_bonus: int = 2              # per pseudo-legal step move (own minus opponent)
    # Advancement bonus per row of progress toward the enemy den, by rank.
    advance_bonus: tuple[int, ...] = (0, 5, 2, 2, 2, 3, 2, 2, 3)
    # Endgame race term.
    endgame_pieces: int = 6
    eg_race_bonus: int = 15


DEFAULT_WEIGHTS = EvalWeights()
# Previous engine generation: identical except the new v3 terms are disabled.
V2_WEIGHTS = replace(DEFAULT_WEIGHTS, advanced_rat_bonus=0, trap_capture_threat_bonus=0)

# Backward-compatible aliases (ordering tables, external imports).
MG_VALUES = dict(enumerate(DEFAULT_WEIGHTS.mg_values))
EG_VALUES = dict(enumerate(DEFAULT_WEIGHTS.eg_values))

# Terminal score kept for the compatibility wrapper.
WIN_SCORE = 10_000


def evaluate_fast(pos: FastPosition, weights: EvalWeights = DEFAULT_WEIGHTS) -> int:
    """Return the static score of `pos` from the side to move's perspective."""
    cells = pos.cells
    mg_values = weights.mg_values
    eg_values = weights.eg_values
    advance_bonus = weights.advance_bonus
    terrain_t = tables.TERRAIN
    is_river = tables.IS_RIVER
    neighbors_t = tables.NEIGHBORS
    dist_red_den = tables.DIST_FROM_DEN[Side.RED]
    dist_blue_den = tables.DIST_FROM_DEN[Side.BLUE]
    own_den_red = tables.DEN_IDX[Side.RED]
    own_den_blue = tables.DEN_IDX[Side.BLUE]

    # Accumulators indexed 0=RED, 1=BLUE.
    mg = [0, 0]
    eg = [0, 0]
    mobility = [0, 0]
    min_den_dist = [16, 16]
    rats = [0, 0]
    elephants = [0, 0]
    phase = 0

    for i, code in enumerate(cells):
        if code == EMPTY:
            continue
        is_red = code > 8
        sv = 0 if is_red else 1
        rank = code if code <= 8 else code - 8

        mg_v = mg_values[rank]
        mg[sv] += mg_v
        eg[sv] += eg_values[rank]
        phase += mg_v

        # Development: progress toward the enemy den (row 0 for RED, row 8 for BLUE).
        row = tables.ROW[i]
        advancement = (8 - row) if is_red else row
        positional = advance_bonus[rank] * advancement

        if rank == _RAT:
            rats[sv] += 1
            if is_river[i]:
                positional += weights.rat_river_bonus
            if advancement > 3:
                positional += weights.advanced_rat_bonus * (advancement - 3)
        elif rank == _ELEPHANT:
            elephants[sv] += 1
        elif rank >= 6:
            jumps = tables.JUMPS_LION[i] if rank == _LION else tables.JUMPS_TIGER[i]
            for _landing, crossed in jumps:
                if not any(
                    (sq := cells[c]) != EMPTY and (sq if sq <= 8 else sq - 8) == _RAT
                    for c in crossed
                ):
                    positional += weights.jump_threat_bonus
                    break

        # Traps: a piece in an enemy trap defends at 0 — penalize it, and
        # reward the other side when a piece sits adjacent to claim it.
        terrain = terrain_t[i]
        if (terrain is Terrain.TRAP_RED and not is_red) or (
            terrain is Terrain.TRAP_BLUE and is_red
        ):
            positional -= weights.trapped_penalty
            enemy_sv = 1 - sv
            for nb in neighbors_t[i]:
                nb_code = cells[nb]
                if nb_code != EMPTY and (0 if nb_code > 8 else 1) == enemy_sv:
                    mg[enemy_sv] += weights.trap_capture_threat_bonus
                    eg[enemy_sv] += weights.trap_capture_threat_bonus
                    break

        # Guard of the own den.
        if (dist_red_den[i] if is_red else dist_blue_den[i]) == 1:
            positional += weights.den_guard_bonus

        mg[sv] += positional
        eg[sv] += positional

        # Closest approach to the den this piece attacks.
        dist = dist_blue_den[i] if is_red else dist_red_den[i]
        if dist < min_den_dist[sv]:
            min_den_dist[sv] = dist

        # Pseudo-mobility: step targets that are not obviously illegal.
        own_den = own_den_red if is_red else own_den_blue
        for nb in neighbors_t[i]:
            if is_river[nb] and rank != _RAT:
                continue
            if nb == own_den:
                continue
            target = cells[nb]
            if target != EMPTY and (target > 8) == is_red:
                continue
            mobility[sv] += 1

    # Rat-elephant dynamics.
    for sv in (0, 1):
        enemy = 1 - sv
        if elephants[sv] and rats[enemy]:
            mg[sv] -= weights.elephant_vs_rat_penalty
            eg[sv] -= weights.elephant_vs_rat_penalty
        if rats[sv] and elephants[enemy]:
            mg[sv] += weights.rat_vs_elephant_bonus * rats[sv]
            eg[sv] += weights.rat_vs_elephant_bonus * rats[sv]

    us = 0 if pos.side is Side.RED else 1
    them = 1 - us

    mg_score = (mg[us] - mg[them]) + weights.mobility_bonus * (mobility[us] - mobility[them])
    eg_score = eg[us] - eg[them]

    # Den pressure: reward our closest approach to the enemy den, and punish
    # the opponent's closest approach to ours.
    if min_den_dist[us] < 8:
        pressure = (8 - min_den_dist[us]) * weights.den_pressure
        mg_score += pressure
        eg_score += pressure
    if min_den_dist[them] < 8:
        pressure = (8 - min_den_dist[them]) * weights.den_pressure
        mg_score -= pressure
        eg_score -= pressure

    # Endgame race term.
    total_pieces = pos.piece_counts[0] + pos.piece_counts[1]
    if 0 < total_pieces <= weights.endgame_pieces:
        eg_score += weights.eg_race_bonus * (min_den_dist[them] - min_den_dist[us])

    # Taper between middlegame and endgame by remaining material.
    phase_max = 2 * sum(mg_values)
    phase = min(phase, phase_max)
    return (mg_score * phase + eg_score * (phase_max - phase)) // phase_max


def evaluate(state: GameState, perspective: Side) -> int:
    """Return a heuristic score from `perspective`'s point of view.

    Positive is good for `perspective`; negative is good for the opponent.
    Kept for backward compatibility; the engine uses `evaluate_fast`.
    """
    if state.winner is not None:
        return WIN_SCORE if state.winner is perspective else -WIN_SCORE

    pos = FastPosition.from_game_state(state)
    score = evaluate_fast(pos)
    return score if perspective is state.current_side else -score
