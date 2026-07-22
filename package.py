"""Build the Windows executable with PyInstaller into release/.

Handles Windows quirks: a still-running Jungle.exe locks the release folder
(killed first), and antivirus/indexer handles can briefly lock freshly
written files (all deletes/copies retry past PermissionError).

Usage: python package.py
Output: release/Jungle.exe + release/README.md
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def _remove_tree(path: Path, attempts: int = 5, delay_s: float = 0.5) -> None:
    """Remove a directory tree, retrying past transient Windows file locks."""
    for attempt in range(attempts):
        try:
            if path.exists():
                shutil.rmtree(path)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay_s)


def _copy_with_retry(source: Path, dest: Path, attempts: int = 5, delay_s: float = 0.5) -> None:
    for attempt in range(attempts):
        try:
            shutil.copy2(source, dest)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay_s)


def _current_git_ref(repo_root: Path) -> str:
    """Return 'branch (commit)' for the current checkout, for build traceability.

    The script always packages whatever is checked out in its own directory;
    this just makes the source of each build visible in the output."""
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=repo_root,
        ).stdout.strip()
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=repo_root,
        ).stdout.strip()
    except OSError:
        return "unknown (git not available)"
    if not branch or branch == "HEAD":
        branch = "detached HEAD"
    return f"{branch} ({commit or 'unknown commit'})"


def main() -> int:
    repo_root = Path(__file__).parent.resolve()
    os.chdir(repo_root)

    print(f"Building from current checkout: {_current_git_ref(repo_root)}")

    dist_dir = repo_root / "dist"
    build_dir = repo_root / "build"
    release_dir = repo_root / "release"

    # A previous Jungle.exe still running locks the release folder on Windows.
    subprocess.run(["taskkill", "/F", "/IM", "Jungle.exe"], capture_output=True)

    print("Cleaning previous build artifacts…")
    _remove_tree(dist_dir)
    _remove_tree(build_dir)
    _remove_tree(release_dir)
    release_dir.mkdir(parents=True, exist_ok=True)

    pyinstaller = shutil.which("pyinstaller")
    command = (
        [pyinstaller] if pyinstaller else [sys.executable, "-m", "PyInstaller"]
    ) + [
        "--onefile",
        "--windowed",
        "--name", "Jungle",
        "--distpath", str(dist_dir),
        "--workpath", str(build_dir),
        "--specpath", str(repo_root),
        "main.py",
    ]
    print("Running:", " ".join(str(c) for c in command))
    result = subprocess.run([str(c) for c in command])
    if result.returncode != 0:
        print("PyInstaller failed.")
        return 1

    exe = dist_dir / "Jungle.exe"
    if not exe.exists():
        print(f"Expected executable not found at {exe}")
        return 1

    readme_source = repo_root / "packaging" / "README.release.md"
    if not readme_source.exists():
        print(f"WARNING: {readme_source} is missing; the release README is required!")

    _copy_with_retry(exe, release_dir / "Jungle.exe")
    if readme_source.exists():
        _copy_with_retry(readme_source, release_dir / "README.md")

    size_mb = (release_dir / "Jungle.exe").stat().st_size / (1024 * 1024)
    print(f"\nRelease written to {release_dir}")
    print(f"  Jungle.exe  ({size_mb:.1f} MB)")
    print(f"  README.md   {'OK' if (release_dir / 'README.md').exists() else 'MISSING!'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
