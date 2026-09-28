"""Tests for skills/anonymize/scripts/check_residuals.py. All data is fictional."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "anonymize" / "scripts"))
import check_residuals as cr  # noqa: E402

POLICY = {"files": [{"match": "*.jsonl", "id": "id", "text": ["text"], "names": ["person"]}]}


def make_fnr(prefix: str) -> str:
    """Make a valid national identity number from nine digits (date + individual number)."""
    for last in range(1000):
        base = prefix[:6] + f"{last:03d}"
        d = [int(c) for c in base]
        k1 = 11 - sum(w * v for w, v in zip([3, 7, 6, 1, 8, 9, 4, 5, 2], d)) % 11
        k1 = 0 if k1 == 11 else k1
        if k1 == 10:
            continue
        d.append(k1)
        k2 = 11 - sum(w * v for w, v in zip([5, 4, 3, 2, 7, 6, 5, 4, 3, 2], d)) % 11
        k2 = 0 if k2 == 11 else k2
        if k2 == 10:
            continue
        return base + str(k1) + str(k2)
    raise AssertionError("found no valid number")


class CheckResidualsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.original = root / "raw"
        (self.original / "round 1").mkdir(parents=True)
        (self.original / "round 1" / "Interview Kari Nordmann.txt").write_text("…", encoding="utf-8")
        (self.original / "chats.jsonl").write_text(
            json.dumps({"id": "a", "person": "Øystein Ås", "text": "x"}) + "\n", encoding="utf-8")
        self.target = root / "out"
        (self.target / "documents").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name: str, text: str) -> None:
        (self.target / name).write_text(text, encoding="utf-8")

    def kinds(self, allow: set[str] | None = None) -> list[tuple[str, str]]:
        terms = cr.known_terms(self.original, None, POLICY)
        return [(h.kind, h.text) for h in cr.scan(self.target, terms, allow or set())]

    def test_national_id_numbers_are_checked_with_check_digits(self):
        valid = make_fnr("010190")
        self.assertTrue(cr.fnr_valid(valid))
        self.assertFalse(cr.fnr_valid(valid[:-1] + str((int(valid[-1]) + 1) % 10)))
        self.assertTrue(cr.fnr_valid(make_fnr("410190")))  # D number
        self.assertFalse(cr.fnr_valid("32139012345"))

    def test_finds_names_from_file_names_and_name_fields(self):
        self.write("documents/a.md", "I talked to Kari and Nordmann again. Øystein ås said hi, and Øystein too.")
        found = self.kinds()
        self.assertIn(("file_name", "Kari"), found)
        self.assertIn(("file_name", "Nordmann"), found)
        self.assertIn(("name", "Øystein ås"), found)
        self.assertIn(("name_part", "Øystein"), found)
        self.assertNotIn(("file_name", "Interview"), found)

    def test_finds_contact_details_and_numbers(self):
        fnr = make_fnr("150385")
        self.write(
            "documents/b.md",
            f"Send to kari@example.no or call +47 912 34 567 / 91234567. ID {fnr}, account 12345678901. "
            "See https://example.no/profile.",
        )
        found = {k for k, _ in self.kinds()}
        self.assertTrue({"email", "phone", "national_id", "id_number", "link"} <= found, found)

    def test_no_false_hits_on_dates_ids_and_placeholders(self):
        self.write("documents/c.csv", "\ufeffanswer;sent\nI work with [PERSON_1] in [small municipality] since 2019.;"
                                      "2026-09-22\n")
        self.write("manifest.json", json.dumps({"sha256": "9f3a12345678901234567890abcdef",
                                                "file": "documents/document-3fa9c2e1.txt"}))
        self.assertEqual(self.kinds(), [])

    def test_the_allow_list_accepts_assessed_hits(self):
        self.write("documents/d.md", "The budget was 20000000 kroner.")
        self.assertEqual(self.kinds(), [("phone", "20000000")])
        self.assertEqual(self.kinds(allow={"20000000"}), [])

    def test_html_and_json_escapes_are_decoded(self):
        self.write("page.html", "<p>K&#97;ri was here</p>")
        self.write("documents/t.jsonl", '{"content": "Hi \\u00d8ystein \\u00c5s"}\n')
        found = self.kinds()
        self.assertIn(("file_name", "Kari"), found)
        self.assertIn(("name", "Øystein Ås"), found)

    def test_files_that_are_not_text_are_reported(self):
        (self.target / "data.xlsx").write_bytes(b"PK\x03\x04")
        self.assertIn(("unchecked_file", ".xlsx"), self.kinds())

    def test_main_gives_the_right_exit_code_and_can_mask_hits(self):
        self.write("documents/e.md", "No identifiers here.")
        policy = Path(self.tmp.name) / "policy.json"
        policy.write_text(json.dumps(POLICY), encoding="utf-8")
        args = ["--target", str(self.target), "--original", str(self.original), "--policy", str(policy)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cr.main(args), 0)
        self.write("documents/f.md", "Kari Nordmann was there.")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cr.main([*args, "--json", "--mask"])
        self.assertEqual(code, 1)
        report = json.loads(out.getvalue())
        self.assertNotIn("Kari", out.getvalue())
        self.assertNotIn("Nordmann", out.getvalue())
        self.assertEqual(report["counts"]["file_name"], 2)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cr.main(["--target", str(self.target / "missing")]), 2)


if __name__ == "__main__":
    unittest.main()
