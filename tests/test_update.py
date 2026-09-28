"""Tests for skills/anonymize/scripts/update.py with a local git repository as the source."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "skills" / "anonymize" / "scripts"))
import install  # noqa: E402
import update  # noqa: E402

GIT_USER = ["-c", "user.name=Test", "-c", "user.email=test@example.invalid"]


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *GIT_USER, *args], cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return result.stdout


class UpdateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        # The source: a git repository with the same layout as anonymizer, tagged v0.1.0.
        self.source = root / "source"
        shutil.copytree(REPO / "skills", self.source / "skills", ignore=shutil.ignore_patterns("__pycache__"))
        (self.source / "skills" / "anonymize" / "VERSION").write_text("0.1.0\n", encoding="utf-8")
        git(root, "init", "-q", "-b", "main", str(self.source))
        git(self.source, "add", "-A")
        git(self.source, "commit", "-q", "-m", "v0.1.0")
        git(self.source, "tag", "v0.1.0")
        # The installation: a project folder with the skill from the repository and the source above.
        self.work = root / "work"
        self.work.mkdir()
        install.install(self.work, source=str(self.source))
        self.skill = self.work / ".opencode" / "skills" / "anonymize"
        (self.skill / "VERSION").write_text("0.1.0\n", encoding="utf-8")
        record = update.load_record(self.skill)
        record["version"] = "0.1.0"
        record["installed_sha256"] = update.fingerprint(self.skill)
        update.save_record(self.skill, record)

    def tearDown(self):
        self.tmp.cleanup()

    def release(self, version: str, *, version_file: str | None = None) -> None:
        (self.source / "skills" / "anonymize" / "VERSION").write_text((version_file or version) + "\n", encoding="utf-8")
        (self.source / "skills" / "anonymize" / "NEW.md").write_text(f"New in {version}\n", encoding="utf-8")
        git(self.source, "add", "-A")
        git(self.source, "commit", "-q", "-m", f"v{version}")
        git(self.source, "tag", f"v{version}")

    def installed_version(self) -> str:
        return (self.skill / "VERSION").read_text(encoding="utf-8").strip()

    def test_reports_a_new_version_without_changing_anything(self):
        self.release("0.2.0")
        code, message = update.run(self.skill)
        self.assertEqual(code, 0)
        self.assertIn("Version 0.2.0 exists", message)
        self.assertEqual(self.installed_version(), "0.1.0")
        self.assertEqual(update.load_record(self.skill)["latest"], "0.2.0")

    def test_checks_at_most_once_a_day(self):
        self.release("0.2.0")
        update.run(self.skill)
        record = update.load_record(self.skill)
        record["source"] = str(self.source.parent / "missing")
        update.save_record(self.skill, record)
        code, message = update.run(self.skill)
        self.assertEqual(code, 0)
        self.assertIn("checked in the last day", message)

    def test_auto_installs_and_keeps_the_previous_version(self):
        update.run(self.skill, mode="auto")
        self.release("0.2.0")
        code, message = update.run(self.skill, check=True)
        self.assertEqual(code, update.UPDATED, message)
        self.assertEqual(self.installed_version(), "0.2.0")
        self.assertTrue((self.skill / "NEW.md").is_file())
        record = update.load_record(self.skill)
        self.assertEqual((record["version"], record["mode"]), ("0.2.0", "auto"))
        self.assertEqual(record["installed_sha256"], update.fingerprint(self.skill))
        backups = list((self.work / ".opencode" / "anonymize-backups").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "VERSION").read_text(encoding="utf-8").strip(), "0.1.0")
        self.assertEqual([p.name for p in (self.work / ".opencode").iterdir()], ["anonymize-backups", "skills"])

    def test_local_edits_stop_the_automatic_update(self):
        update.run(self.skill, mode="auto")
        self.release("0.2.0")
        (self.skill / "SKILL.md").write_text("edited locally\n", encoding="utf-8")
        code, message = update.run(self.skill, check=True)
        self.assertEqual(code, 0)
        self.assertIn("edited locally", message)
        self.assertEqual(self.installed_version(), "0.1.0")

    def test_rejects_a_release_whose_version_file_differs(self):
        self.release("0.3.0", version_file="0.2.0")
        code, message = update.run(self.skill, install=True)
        self.assertEqual(code, 2)
        self.assertIn("is kept", message)
        self.assertEqual(self.installed_version(), "0.1.0")

    def test_off_means_no_check_at_start(self):
        update.run(self.skill, mode="off")
        self.release("0.2.0")
        code, message = update.run(self.skill)
        self.assertEqual(code, 0)
        self.assertIn("turned off", message)
        self.assertIsNone(update.load_record(self.skill)["latest"])

    def test_a_development_copy_is_not_updated(self):
        code, message = update.run(REPO / "skills" / "anonymize")
        self.assertEqual(code, 0)
        self.assertIn("Development or manual copy", message)

    def test_the_installed_script_can_replace_its_own_folder(self):
        self.release("0.2.0")
        script = self.skill / "scripts" / "update.py"
        result = subprocess.run(
            [sys.executable, str(script), "--install"], cwd=self.work, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, update.UPDATED, result.stdout + result.stderr)
        self.assertEqual(self.installed_version(), "0.2.0")
        self.assertIn("Start a new session", result.stdout)
        record = json.loads((self.skill / update.RECORD_NAME).read_text(encoding="utf-8"))
        self.assertEqual(record["version"], "0.2.0")

    def test_a_global_skill_is_updated_without_a_project_folder(self):
        home = self.work / "user"
        install.install_global("opencode", home=home, source=str(self.source))
        skill = home / ".config/opencode/skills/anonymize"
        (skill / "VERSION").write_text("0.1.0\n", encoding="utf-8")
        record = update.load_record(skill)
        record["version"] = "0.1.0"
        record["installed_sha256"] = update.fingerprint(skill)
        update.save_record(skill, record)
        self.release("0.2.0")
        code, message = update.run(skill, install=True)
        self.assertEqual(code, update.UPDATED, message)
        self.assertEqual(update.read_version(skill), "0.2.0")
        backups = home / ".config/opencode/anonymize-backups"
        self.assertEqual(len(list(backups.iterdir())), 1)
        self.assertFalse((home / "raw").exists())


if __name__ == "__main__":
    unittest.main()
