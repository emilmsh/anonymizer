"""Install one shared skill for OpenCode, Codex and Claude Code.

    python install.py --tool all
    python install.py --tool opencode --update

An optional project folder as a positional argument is still supported for older
setups, but is not needed for a global installation. No project data is copied
or read during installation.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
SKILL = REPO / "skills" / "anonymize"
FOLDERS = ("raw", "changes", "out", "review")
TOOLS = ("opencode", "codex", "claude")

sys.path.insert(0, str(SKILL / "scripts"))
import update as updater  # noqa: E402


def _repo_git(*args: str) -> str | None:
    try:
        result = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


def _copy_skill(dest: Path, update: bool, source: str | None, mode: str) -> list[str]:
    log: list[str] = []
    if dest.exists() and not update:
        log.append(f"The skill already exists in {dest}. Use --update to replace it.")
    else:
        if dest.exists() and not (dest / ".install.json").is_file():
            raise ValueError(f"{dest} was not installed by this script. Keep it and choose another location.")
        if dest.exists() and updater.fingerprint(dest) != updater.load_record(dest).get("installed_sha256"):
            raise ValueError(f"{dest} is edited locally. Keep your edits before --update.")
        previous = updater.load_record(dest) if dest.exists() else None
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SKILL, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", updater.RECORD_NAME))
        source = source or _repo_git("remote", "get-url", "origin") or updater.DEFAULT_SOURCE
        record = updater.new_record(dest, source, _repo_git("rev-parse", "HEAD"), mode=mode, previous=previous)
        updater.save_record(dest, record)
        log.append(f"The skill {record['version']} is installed in {dest} (updates: {record['mode']}).")
    return log


def install_global(tool: str, *, home: Path | None = None, update: bool = False,
                   source: str | None = None, mode: str = "notify") -> list[str]:
    """Install in the user's skills folder(s), not in the data folder."""
    if tool not in (*TOOLS, "all"):
        raise ValueError(f"Unknown tool: {tool}")
    home = home or Path.home()
    paths = {
        "opencode": home / ".config" / "opencode" / "skills" / "anonymize",
        "codex": home / ".agents" / "skills" / "anonymize",
        "claude": home / ".claude" / "skills" / "anonymize",
    }
    if os.environ.get("XDG_CONFIG_HOME") and home == Path.home():
        paths["opencode"] = Path(os.environ["XDG_CONFIG_HOME"]) / "opencode" / "skills" / "anonymize"
    selected = TOOLS if tool == "all" else (tool,)
    # Check every destination before any of them is changed.
    for name in selected:
        dest = paths[name]
        if dest.exists() and not (dest / ".install.json").is_file() and update:
            raise ValueError(f"{dest} was not installed by this script. No files were changed.")
        if dest.exists() and update and updater.fingerprint(dest) != updater.load_record(dest).get("installed_sha256"):
            raise ValueError(f"{dest} is edited locally. No files were changed.")
    log = []
    for name in selected:
        log.extend(_copy_skill(paths[name], update, source, mode))
    return log


def install(target: Path, update: bool = False, source: str | None = None, mode: str = "notify") -> list[str]:
    """Older project-local installation; no lock or data is copied."""
    target = target.resolve()
    if not target.is_dir():
        raise ValueError(f"The project folder does not exist: {target}")
    if target == REPO or REPO in target.parents:
        raise ValueError("The project folder must be outside the repository, so real data never ends up in git.")
    log = _copy_skill(target / ".opencode" / "skills" / "anonymize", update, source, mode)
    for name in FOLDERS:
        folder = target / name
        if not folder.exists():
            folder.mkdir()
            log.append(f"Made {folder}.")
    return log


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install the anonymize skill.")
    parser.add_argument("target", type=Path, nargs="?", help="Optional older project-local installation.")
    parser.add_argument("--tool", choices=(*TOOLS, "all"), default="all", help="Global installation for one or all tools.")
    parser.add_argument("--update", action="store_true", help="Replace an installed skill with the version in the repository.")
    parser.add_argument("--mode", choices=updater.MODES, default="notify",
                        help="Updates from the repository: notify (default), auto or off.")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        log = (install(args.target, update=args.update, mode=args.mode) if args.target
               else install_global(args.tool, update=args.update, mode=args.mode))
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    print("\n".join(log))
    print("\nNext step: start the AI tool from an approved project folder and ask for anonymization. "
          "Confirm the provider for the project before any data is read.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
