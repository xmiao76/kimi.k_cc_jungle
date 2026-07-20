"""Full-game regression driven as a subprocess (see scripts/ai_vs_ai_smoke.py
for why the game must not run inside the pytest process)."""

import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_full_ai_vs_ai_game_completes_in_subprocess():
    result = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "scripts", "ai_vs_ai_smoke.py"), "120"],
        capture_output=True,
        text=True,
        timeout=150,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "GAME_OVER" in result.stdout
