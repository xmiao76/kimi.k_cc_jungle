"""Fixed-depth feature ablation gauntlets (deterministic, contention-proof)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.gauntlet import run_gauntlet
from jungle.engine.ai import AI
from jungle.engine.evaluation import DEFAULT_WEIGHTS
from jungle.engine.search import SearchConfig
from scripts.gauntlet import make_v2

DEPTH = 5
GAMES = 8
T = 600.0  # effectively untimed: results depend on move quality only

def factory(**flags):
    def make(side):
        return AI(side, config=SearchConfig(
            max_depth=DEPTH, soft_limit_s=T, hard_limit_s=T,
            use_aspiration=False, use_persistent_tt=False, **flags))
    return make

def v2(side):
    return make_v2(side, DEPTH, T)

RUNS = [
    ("A: v3-eval only", factory(use_lmr=False, use_see_pruning=False)),
    ("B: v3-eval + LMR", factory(use_lmr=True, use_see_pruning=False)),
    ("C: v3-eval + SEE", factory(use_lmr=False, use_see_pruning=True)),
]

for name, cand in RUNS:
    score = run_gauntlet(GAMES, cand, v2, seed=999, verbose=False)
    print(f"{name} vs v2 @fixed-depth-{DEPTH}: {score:.2f} ({GAMES} games)", flush=True)
