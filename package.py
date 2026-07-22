"""Build a Windows executable with PyInstaller."""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def _remove_tree(path: Path, attempts: int = 5, delay_s: float = 0.5) -> None:
    """Remove a directory tree, retrying past transient Windows file locks
    (antivirus/indexer handles on freshly written executables)."""
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
    release_dir = repo_root / "release"

    # A previous Jungle.exe still running locks the release folder on Windows.
    subprocess.run(
        ["taskkill", "/F", "/IM", "Jungle.exe"],
        capture_output=True,
    )

    # Clean previous build artifacts.
    _remove_tree(dist_dir)
    _remove_tree(release_dir)

    pyinstaller = shutil.which("pyinstaller") or str(repo_root / ".venv" / "Scripts" / "pyinstaller.exe")

    cmd = [
        pyinstaller,
        "--onefile",
        "--windowed",
        "--name", "Jungle",
        "--distpath", str(dist_dir),
        "--workpath", str(repo_root / "build"),
        "--specpath", str(repo_root),
        str(repo_root / "main.py"),
    ]

    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print("PyInstaller failed")
        return result.returncode

    release_dir.mkdir(parents=True, exist_ok=True)
    exe_source = dist_dir / "Jungle.exe"
    exe_dest = release_dir / "Jungle.exe"
    _copy_with_retry(exe_source, exe_dest)

    # Copy the release README (player-facing, with credits) to the release folder.
    readme_source = repo_root / "packaging" / "README.release.md"
    if readme_source.exists():
        _copy_with_retry(readme_source, release_dir / "README.md")
    else:
        print("WARNING: packaging/README.release.md not found; release has no README")

    print(f"Release executable: {exe_dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
