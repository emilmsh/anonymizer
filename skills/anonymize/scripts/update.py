"""Update an installed anonymize skill from the repository.

    python <skill dir>/scripts/update.py              check (at most once a day)
    python <skill dir>/scripts/update.py --check      check now
    python <skill dir>/scripts/update.py --install    install the newest version now

Only version tags in the repository (vX.Y.Z) count as releases. A commit on main
gives no update. The setting applies to this installation and is kept in
.install.json next to the skill, with version, source and fingerprint.

- notify: reports a newer version. Nothing is changed.
- auto: installs a newer version, but only when the installed files are not
  edited locally. The previous version goes to anonymize-backups/ next to the
  skills folder.
- off: no check at start. --check and --install still work.

The script only fetches code from the repository with git. It sends no data. The
clone is placed briefly in the system's temp folder; only the skill files are
copied into the skills folder.

Exit code: 0 = nothing to do or only a notice, 3 = the skill was updated (start a
new session), 2 = usage or installation error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
RECORD_NAME = ".install.json"
DEFAULT_SOURCE = "https://github.com/emilmsh/anonymizer.git"
MODES = ("notify", "auto", "off")
CHECK_INTERVAL = timedelta(hours=24)
UPDATED = 3
TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def parse_version(text: str | None) -> tuple[int, int, int] | None:
    if not text:
        return None
    text = text.strip()
    m = TAG.match(text if text.startswith("v") else "v" + text)
    return tuple(int(x) for x in m.groups()) if m else None


def _newer(candidate: str | None, installed: str | None) -> bool:
    new, old = parse_version(candidate), parse_version(installed)
    return new is not None and (old is None or new > old)


def read_version(skill_dir: Path) -> str:
    return (skill_dir / "VERSION").read_text(encoding="utf-8").strip()


def fingerprint(skill_dir: Path) -> str:
    """SHA-256 over all files in the skill, without the install record and caches."""
    digest = hashlib.sha256()
    for path in sorted(p for p in skill_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(skill_dir).as_posix()
        if rel == RECORD_NAME or "__pycache__" in rel or rel.endswith(".pyc"):
            continue
        digest.update(rel.encode("utf-8") + b"\0")
        # Line endings are normalized, so git's autocrlf does not look like a local edit.
        digest.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()


def load_record(skill_dir: Path) -> dict | None:
    path = skill_dir / RECORD_NAME
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_record(skill_dir: Path, record: dict) -> None:
    (skill_dir / RECORD_NAME).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def new_record(skill_dir: Path, source: str, commit: str | None, mode: str = "notify", previous: dict | None = None) -> dict:
    previous = previous or {}
    return {
        "version": read_version(skill_dir),
        "source": source,
        "commit": commit,
        "installed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "installed_sha256": fingerprint(skill_dir),
        "mode": previous.get("mode", mode),
        "last_check": previous.get("last_check"),
        "latest": previous.get("latest"),
    }


def _remove_tree(path: Path) -> None:
    """Delete a folder we made ourselves. Git makes read-only files on Windows."""
    def make_writable(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    try:
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=make_writable)
        else:
            shutil.rmtree(path, onerror=make_writable)
    except OSError:
        pass


def _git(*args: str, cwd: Path | None = None) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    result = subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or f"git {args[0]} failed")
    return result.stdout


def latest_release(source: str) -> str | None:
    """The newest version tag in the source, for example '0.2.0', or None."""
    versions = []
    for line in _git("ls-remote", "--tags", "--refs", source).splitlines():
        ref = line.split("\t")[-1].rsplit("/", 1)[-1]
        version = parse_version(ref)
        if version:
            versions.append(version)
    return ".".join(map(str, max(versions))) if versions else None


def install_release(skill_dir: Path, record: dict, version: str) -> dict:
    """Fetch the version from the source and replace the skill. The previous version is kept.

    The repository is cloned into the system's temp folder, which has a short path.
    Only the skill files are copied into the skills folder before the swap.
    """
    work = skill_dir.parent.parent  # the root folder for the tool's skills
    clone_root = Path(tempfile.mkdtemp(prefix="anonymize-"))
    staged = work / f".anonymize-new-{uuid.uuid4().hex[:6]}"
    try:
        clone = clone_root / "repo"
        _git("-c", "core.longpaths=true", "clone", "--quiet", "--depth", "1", "--branch", f"v{version}",
             record["source"], str(clone))
        fetched = clone / "skills" / "anonymize"
        if read_version(fetched) != version:
            raise RuntimeError(f"VERSION in v{version} is {read_version(fetched)}, not {version}.")
        commit = _git("rev-parse", "HEAD", cwd=clone).strip()
        shutil.copytree(fetched, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

        backups = work / "anonymize-backups"
        backups.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = backups / f"{record.get('version', 'unknown')}-{stamp}"
        os.replace(skill_dir, backup)
        try:
            os.replace(staged, skill_dir)
        except OSError:
            os.replace(backup, skill_dir)
            raise
        updated = new_record(skill_dir, record["source"], commit, previous=record)
        updated["latest"] = version
        save_record(skill_dir, updated)
        return updated
    finally:
        _remove_tree(clone_root)
        if staged.exists():
            _remove_tree(staged)


def _due(record: dict) -> bool:
    last = record.get("last_check")
    if not last:
        return True
    return datetime.now(timezone.utc) - datetime.fromisoformat(last) >= CHECK_INTERVAL


def run(skill_dir: Path, *, check: bool = False, install: bool = False, mode: str | None = None) -> tuple[int, str]:
    record = load_record(skill_dir)
    if record is None:
        return 0, "Development or manual copy without an install record. It is not updated automatically."

    if mode:
        record["mode"] = mode
        save_record(skill_dir, record)
        if not (check or install):
            return 0, f"Updates are set to '{mode}' for this installation."

    installed = record.get("version", "unknown")
    current_mode = record.get("mode", "notify")
    if not (check or install):
        if current_mode == "off":
            return 0, f"anonymize {installed}. Automatic checks are turned off."
        if not _due(record):
            latest = record.get("latest")
            if _newer(latest, installed):
                return 0, f"anonymize {installed} is installed. Version {latest} exists (checked in the last day)."
            return 0, f"anonymize {installed} is installed and up to date (checked in the last day)."

    try:
        latest = latest_release(record["source"])
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        return 0, f"anonymize {installed}. Could not check for updates: {exc}"
    record["last_check"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record["latest"] = latest
    save_record(skill_dir, record)

    if not _newer(latest, installed):
        return 0, f"anonymize {installed} is the newest version."
    if not (install or current_mode == "auto"):
        return 0, (
            f"anonymize {installed} is installed. Version {latest} exists. Install it with "
            "'python <skill dir>/scripts/update.py --install'."
        )
    if fingerprint(skill_dir) != record.get("installed_sha256"):
        return 0, (
            f"Version {latest} exists, but the installed files are edited locally. The automatic update is "
            "stopped. Keep your edits and run install.py --update from the repository."
        )
    try:
        install_release(skill_dir, record, latest)
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        return 2, f"The update to {latest} failed, and {installed} is kept: {exc}"
    return UPDATED, (
        f"anonymize is updated from {installed} to {latest}. Start a new session in the AI tool, "
        "so the new skill is loaded, before you continue."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check for and install updates of the anonymize skill.")
    parser.add_argument("--check", action="store_true", help="Check now, however recently it was checked.")
    parser.add_argument("--install", action="store_true", help="Install the newest version now.")
    parser.add_argument("--mode", choices=MODES, help="Set updates for this installation.")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    code, message = run(SKILL_DIR, check=args.check, install=args.install, mode=args.mode)
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
