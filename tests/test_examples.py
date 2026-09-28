"""The example in examples/grant-scheme must build again into the same files.

The example is fictional. The change lists and id-map.json are in the repository,
so the new file names, IDs and order are the same every time.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "skills" / "anonymize" / "scripts"))
import apply_changes as ac  # noqa: E402
import check_residuals as cr  # noqa: E402
import formats  # noqa: E402

EXAMPLE = REPO / "examples" / "grant-scheme"


class ExampleTest(unittest.TestCase):
    def test_the_example_gives_the_same_anonymized_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            for name in ("raw", "changes"):
                shutil.copytree(EXAMPLE / name, work / name)
            shutil.copy(EXAMPLE / "policy.json", work / "policy.json")
            result = ac.run(work / "raw", work / "changes", work / "out", policy=work / "policy.json")
            self.assertEqual(result["documents"], 5)
            built = {p.name: p.read_bytes() for p in (work / "out" / "documents").iterdir()}
            committed = {p.name: p.read_bytes() for p in (EXAMPLE / "out" / "documents").iterdir()}
            self.assertEqual(built, committed)
            self.assertEqual((work / "changes" / "id-map.json").read_bytes(),
                             (EXAMPLE / "changes" / "id-map.json").read_bytes())

    def test_the_check_finds_nothing_in_the_example(self):
        policy = json.loads((EXAMPLE / "policy.json").read_text(encoding="utf-8"))
        self.assertEqual(cr.scan(EXAMPLE / "out", cr.known_terms(EXAMPLE / "raw", None, policy), set()), [])

    def test_the_policy_uses_the_file_rules_from_the_package_description(self):
        policy = json.loads((EXAMPLE / "policy.json").read_text(encoding="utf-8"))
        package = json.loads((EXAMPLE / "raw" / formats.PACKAGE_DESCRIPTION).read_text(encoding="utf-8"))
        self.assertEqual(formats.check_rules(package["files"]), [])
        for rule in package["files"]:
            self.assertIn(rule, policy["files"])


if __name__ == "__main__":
    unittest.main()
