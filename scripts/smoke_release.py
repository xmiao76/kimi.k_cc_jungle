"""Post-packaging smoke test for release/Jungle.exe.

Verifies the release folder contents, launches the packaged executable,
checks it survives a few seconds (no startup crash), then terminates it by
image name (PyInstaller onefile spawns a detached child, so image-name kill
is the reliable teardown).

Usage: python scripts/smoke_release.py
Exit code 0 = PASS.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
RELEASE_DIR = REPO_ROOT / "release"
EXE = RELEASE_DIR / "Jungle.exe"
README = RELEASE_DIR / "README.md"
HOLD_SECONDS = 8.0


def _fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def main() -> int:
    if not EXE.exists():
        return _fail(f"{EXE} is missing — run python package.py first")
    if not README.exists():
        return _fail(f"{README} is missing — the release README is required")

    readme_text = README.read_text(encoding="utf-8")
    for needle in ("Claude Code", "k3[1m]"):
        if needle not in readme_text:
            return _fail(f"release README must identify the agent and model ({needle!r} missing)")

    print("Launching Jungle.exe…")
    process = subprocess.Popen([str(EXE)], cwd=str(RELEASE_DIR))
    try:
        deadline = time.monotonic() + HOLD_SECONDS
        while time.monotonic() < deadline:
            code = process.poll()
            if code is not None:
                return _fail(f"Jungle.exe exited early with code {code}")
            time.sleep(0.25)
    finally:
        # Teardown even on failure; onefile spawns a detached child process.
        subprocess.run(["taskkill", "/F", "/IM", "Jungle.exe"], capture_output=True)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass

    crash_log = RELEASE_DIR / "jungle-crash.log"
    if crash_log.exists() and crash_log.stat().st_size > 0:
        return _fail("jungle-crash.log was written during startup")

    print(f"PASS: Jungle.exe survived {HOLD_SECONDS:.0f}s, README checks OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
