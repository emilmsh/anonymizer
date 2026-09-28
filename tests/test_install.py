"""Tests for install.py, and that the templates and schemas in the skill are valid."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "skills" / "anonymize" / "scripts"))
import formats  # noqa: E402
import install  # noqa: E402

SKILL = REPO / "skills" / "anonymize"


class InstallTest(unittest.TestCase):
    def test_installs_project_locally_without_changing_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            install.install(target)
            self.assertTrue((target / ".opencode/skills/anonymize/SKILL.md").is_file())
            self.assertTrue((target / ".opencode/skills/anonymize/scripts/check_residuals.py").is_file())
            self.assertFalse((target / "opencode.jsonc").exists())
            for name in install.FOLDERS:
                self.assertTrue((target / name).is_dir())
            (target / "opencode.jsonc").write_text("{}", encoding="utf-8")
            log = install.install(target)
            self.assertEqual((target / "opencode.jsonc").read_text(encoding="utf-8"), "{}")
            self.assertTrue(any("already exists" in line for line in log))

    def test_global_installation_for_every_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            log = install.install_global("all", home=home, source="https://example.invalid/repo.git")
            paths = (home / ".config/opencode/skills/anonymize",
                     home / ".agents/skills/anonymize", home / ".claude/skills/anonymize")
            self.assertEqual(len(log), 3)
            for skill in paths:
                self.assertTrue((skill / "SKILL.md").is_file())
                self.assertTrue((skill / "scripts/apply_changes.py").is_file())
                self.assertEqual(json.loads((skill / ".install.json").read_text(encoding="utf-8"))["source"],
                                 "https://example.invalid/repo.git")
            self.assertFalse((home / "raw").exists())

    def test_global_update_does_not_overwrite_local_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            install.install_global("all", home=home)
            changed = home / ".agents/skills/anonymize/SKILL.md"
            changed.write_text("local edit", encoding="utf-8")
            with self.assertRaises(ValueError):
                install.install_global("all", home=home, update=True)
            self.assertEqual(changed.read_text(encoding="utf-8"), "local edit")

    def test_a_manual_skill_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            skill = home / ".claude/skills/anonymize"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("my skill", encoding="utf-8")
            install.install_global("claude", home=home)
            self.assertEqual((skill / "SKILL.md").read_text(encoding="utf-8"), "my skill")
            with self.assertRaises(ValueError):
                install.install_global("claude", home=home, update=True)

    def test_refuses_a_project_folder_inside_the_repository(self):
        with self.assertRaises(ValueError):
            install.install(REPO / "examples")

    def test_the_example_policy_has_every_required_key_and_valid_file_rules(self):
        schema = json.loads((SKILL / "schemas" / "policy.schema.json").read_text(encoding="utf-8"))
        example = json.loads((SKILL / "templates" / "policy.example.json").read_text(encoding="utf-8"))
        self.assertTrue(set(schema["required"]) <= set(example))
        self.assertTrue(set(example) <= set(schema["properties"]))
        self.assertEqual(formats.check_rules(example["files"]), [])
        rule_keys = set(schema["$defs"]["fileRule"]["properties"])
        self.assertEqual(rule_keys, set().union(*formats.RULE_KEYS.values()))
        for name in ("changes.schema.json", "package.schema.json"):
            json.loads((SKILL / "schemas" / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
