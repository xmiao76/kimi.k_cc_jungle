"""Post-packaging smoke test: launch release/Jungle.exe and verify it stays up."""

import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXE = REPO_ROOT / "release" / "Jungle.exe"
README = REPO_ROOT / "release" / "README.md"
HOLD_SECONDS = 8


def main() -> int:
    if not EXE.exists():
        print(f"FAIL: {EXE} not found — run python package.py first")
        return 1
    if not README.exists():
        print(f"FAIL: {README} not found — run python package.py first")
        return 1
    readme_text = README.read_text(encoding="utf-8")
    if "Claude Code" not in readme_text or "k3" not in readme_text:
        print("FAIL: release README is missing the model/code-agent credit statement")
        return 1

    print(f"Launching {EXE} ...")
    proc = subprocess.Popen([str(EXE)])
    try:
        time.sleep(HOLD_SECONDS)
        if proc.poll() is not None:
            print(f"FAIL: Jungle.exe exited early with code {proc.returncode}")
            return 1
        print(f"PASS: Jungle.exe alive after {HOLD_SECONDS}s; release README OK")
        return 0
    finally:
        if proc.poll() is None:
            # PyInstaller onefile detaches a child app process; killing by
            # image name is the only reliable teardown (tree kill misses it).
            subprocess.run(
                ["taskkill", "/F", "/IM", "Jungle.exe"],
                capture_output=True,
            )


if __name__ == "__main__":
    raise SystemExit(main())
