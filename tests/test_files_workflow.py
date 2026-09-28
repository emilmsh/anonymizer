"""The workflow: apply_changes, segments, check_residuals and assess on text, Word, CSV and JSON Lines.

All data is fictional.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "skills" / "anonymize" / "scripts"))
import apply_changes as ac  # noqa: E402
import assess  # noqa: E402
import check_residuals as cr  # noqa: E402
import core  # noqa: E402
import formats  # noqa: E402
import segments  # noqa: E402

TEXT = "I: Where do you work?\nR: I am the only lawyer in Fjordvik municipality.\n"
RECORDS = [
    {"id": "r1", "participant": "Mari Olsen", "test": False, "started": "2026-03-10T09:00:00+01:00",
     "messages": [{"role": "assistant", "content": "Welcome."}, {"role": "user", "content": "I am Mari from Nordvik."}]},
    {"id": "r2", "participant": "Test User", "test": True, "messages": [{"role": "user", "content": "Test"}]},
]
POLICY = {
    "policy_version": "1",
    "project": "Fictional test",
    "goal": "anonymous",
    "assessment": {"recipients": "Analysts without the recruitment list.", "suitable": True,
                   "rationale": "The analysis only needs the role.", "keys": ["The recruitment list"]},
    "population": "About 50 municipal employees.",
    "analysis_needs": ["Type of role"], "keep": [], "generalize": [], "remove": ["Names"],
    "files": [
        {"match": "answers.csv", "text_columns": ["answer"], "keep_columns": ["role"], "drop_columns": ["id"]},
        {"match": "chats/*.jsonl", "id": "id", "text": ["messages[].content"], "keep": ["messages[].role"],
         "dates": ["started"], "names": ["participant"], "skip": {"test": True}},
        {"match": "guide.md", "action": "copy"},
        {"match": "*.html", "action": "exclude"},
    ],
}


def change(position, original, replacement, category="person", field="content", **extra):
    return {"position": position, "field": field, "original": original, "occurrence": 1, "action": "replace",
            "replacement": replacement, "category": category, "reason": "Test.", **extra}


def changelist(doc_id, changes, **extra):
    return {"document_id": doc_id, "policy_version": "1", "passes": 2, "changes": changes,
            "residual_risk": "low", "needs_review": [], **extra}


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)
        self.raw = self.work / "raw"
        (self.raw / "round 2").mkdir(parents=True)
        (self.raw / "chats").mkdir()
        (self.raw / "Kari Nordmann.txt").write_bytes(TEXT.encode("utf-8"))
        (self.raw / "round 2" / "interview.docx").write_bytes(
            formats.docx_bytes(["Notes from a talk with Kari", "", "She works in Fjordvik."]))
        (self.raw / "answers.csv").write_bytes(b"id;role;answer\n7;Manager;Kari here. I like the scheme.\n8;Manager;Good.\n")
        (self.raw / "chats" / "export.jsonl").write_text("".join(json.dumps(r) + "\n" for r in RECORDS), encoding="utf-8")
        (self.raw / "guide.md").write_text("# Interview guide\n", encoding="utf-8")
        (self.raw / "overview.html").write_text("<p>Kari Nordmann, Mari Olsen</p>", encoding="utf-8")
        self.changes = self.work / "changes"
        self.out = self.work / "out"
        self.policy = self.work / "policy.json"
        self.write_policy(POLICY)
        self.write(changelist("Kari Nordmann.txt", [
            change(2, "the only lawyer in Fjordvik municipality", "[an employee] in [a small municipality]",
                   category="role", round=2)]))
        self.write(changelist("round 2/interview.docx", [
            change(1, "Kari", "[PERSON_1]"), change(3, "Fjordvik", "[a small municipality]", category="place")]))
        self.write(changelist("answers.csv", [change(1, "Kari", "[PERSON_1]", field="answer")]))
        self.write(changelist("chats/export.jsonl/r1", [
            change(None, "Mari", "[PERSON_1]", field="messages[1].content"),
            change(None, "Nordvik", "[a municipality]", category="place", field="messages[1].content")]))

    def tearDown(self):
        self.tmp.cleanup()

    def write_policy(self, policy):
        self.policy.write_text(json.dumps(policy, ensure_ascii=False), encoding="utf-8")

    def write(self, doc):
        path = core.changes_path(self.changes, doc["document_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def run_apply(self, **kwargs):
        return ac.run(self.raw, self.changes, self.out, policy=self.policy, **kwargs)

    def documents(self) -> dict[str, bytes]:
        return {p.name: p.read_bytes() for p in sorted((self.out / "documents").iterdir())}

    def test_the_package_has_new_names_and_only_the_changed_texts_differ(self):
        result = self.run_apply()
        self.assertEqual((result["documents"], result["changes"], result["reread"]), (4, 6, 4))
        docs = self.documents()
        self.assertEqual(sorted(Path(n).suffix for n in docs), [".csv", ".docx", ".jsonl", ".txt"])
        self.assertFalse(any("Kari" in name or "interview" in name or "export" in name for name in docs))
        by_suffix = {Path(n).suffix: data for n, data in docs.items()}
        self.assertEqual(by_suffix[".txt"].decode("utf-8"),
                         "I: Where do you work?\nR: I am [an employee] in [a small municipality].\n")
        word = self.out / "documents" / next(n for n in docs if n.endswith(".docx"))
        self.assertEqual(formats.docx_paragraphs(word),
                         ["Notes from a talk with [PERSON_1]", "", "She works in [a small municipality]."])
        csv_text = by_suffix[".csv"].decode("utf-8")
        self.assertIn("role;answer", csv_text)
        self.assertIn("Manager;[PERSON_1] here. I like the scheme.", csv_text)
        records = [json.loads(line) for line in by_suffix[".jsonl"].decode("utf-8").splitlines()]
        self.assertEqual(len(records), 1)
        self.assertEqual(set(records[0]), {"id", "messages", "started"})
        self.assertEqual(records[0]["messages"][1], {"role": "user", "content": "I am [PERSON_1] from [a municipality]."})
        self.assertEqual(records[0]["started"], "2026-03-10")
        self.assertNotEqual(records[0]["id"], "r1")
        self.assertEqual((self.out / "guide.md").read_text(encoding="utf-8"), "# Interview guide\n")
        self.assertFalse((self.out / "overview.html").exists())
        manifest = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        a = manifest["anonymization"]
        self.assertEqual((a["documents"], a["by_round"], a["reread"]), (4, {"1": 5, "2": 1}, 4))
        self.assertIn("Columns removed from CSV files: id.", a["measures"])
        self.assertIn("1 record is left out by 'skip' in the file rules.", a["measures"])
        self.assertEqual([d["file"] for d in manifest["documents"]], sorted(d["file"] for d in manifest["documents"]))
        self.assertNotIn("Kari", json.dumps(manifest, ensure_ascii=False))
        terms = cr.known_terms(self.raw, None, POLICY)
        self.assertIn(("name", "Mari Olsen"), terms)
        self.assertEqual(cr.scan(self.out, terms, set()), [])
        self.assertEqual(set(core.load_id_map(self.changes / core.ID_MAP)),
                         {"Kari Nordmann.txt", "round 2/interview.docx", "answers.csv", "chats/export.jsonl",
                          "chats/export.jsonl/r1"})
        # The same change lists and IDs give the same files.
        self.run_apply(force=True)
        self.assertEqual(self.documents(), docs)

    def test_the_check_finds_names_from_file_names_and_name_fields(self):
        self.write(changelist("round 2/interview.docx", [change(3, "Fjordvik", "[a small municipality]", category="place")]))
        self.write(changelist("chats/export.jsonl/r1", [
            change(None, "Nordvik", "[a municipality]", category="place", field="messages[1].content")]))
        self.run_apply()
        hits = cr.scan(self.out, cr.known_terms(self.raw, None, POLICY), set())
        self.assertEqual(sorted((h.kind, h.text) for h in hits), [("file_name", "Kari"), ("name_part", "Mari")])

    def test_errors_in_the_change_lists_stop_everything(self):
        self.write(changelist("answers.csv", [
            change(1, "Kari", "[PERSON_1]", field="role"),
            change(9, "Kari", "[PERSON_1]", field="answer"),
            change(1, "Kari", "[PERSON_1]", field="answer", round=0, extra=True),
            change(1, "Kari here", "[X]", field="answer"),
        ]))
        self.write(changelist("round 2/interview.docx", [change(1, "Pål", "[PERSON_1]")]))
        (self.changes / "Kari Nordmann.txt.json").unlink()
        with self.assertRaises(core.ChangeError) as raised:
            self.run_apply()
        problems = "\n".join(raised.exception.problems)
        self.assertIn("Kari Nordmann.txt: change list is missing", problems)
        self.assertIn("unknown field 'role'. Valid here: 'answer'", problems)
        self.assertIn("no text at position 9", problems)
        self.assertIn("unknown keys extra", problems)
        self.assertIn("round must be an integer", problems)
        self.assertFalse(self.out.exists())
        self.write(changelist("Kari Nordmann.txt", []))
        self.write(changelist("answers.csv", [change(1, "Kari", "[P]", field="answer"),
                                              change(1, "Kari here", "[X]", field="answer")]))
        with self.assertRaises(core.ChangeError) as raised:
            self.run_apply()
        problems = "\n".join(raised.exception.problems)
        self.assertIn("cannot find occurrence 1 of 'Pål' verbatim", problems)
        self.assertIn("overlap", problems)

    def test_the_policy_version_must_match(self):
        self.write_policy({**POLICY, "policy_version": "2"})
        with self.assertRaises(core.ChangeError) as raised:
            self.run_apply()
        self.assertIn("current is 2", raised.exception.problems[0])

    def test_occurrence_picks_the_right_match(self):
        text, errors = core.apply_to_text("Vik and Vik and Vik", [(1, change(0, "Vik", "[X]", "place", occurrence=2))], "t")
        self.assertEqual((text, errors), ("Vik and [X] and Vik", []))

    def test_only_replaces_its_own_earlier_package(self):
        self.run_apply()
        with self.assertRaises(ValueError):
            self.run_apply()
        self.run_apply(force=True)
        other = self.work / "other"
        other.mkdir()
        (other / "important.txt").write_text("do not delete", encoding="utf-8")
        with self.assertRaises(ValueError):
            ac.run(self.raw, self.changes, other, policy=self.policy, force=True)
        self.assertTrue((other / "important.txt").is_file())

    def test_new_ids_never_look_like_phone_numbers(self):
        numbers = [uuid.UUID("23456789-0000-4000-8000-000000000001"), uuid.UUID("a3456789-0000-4000-8000-000000000001")]
        with mock.patch.object(core.uuid, "uuid4", side_effect=numbers):
            ids = core.assign_ids(["a.txt"], {}, keep=False)
        self.assertEqual(ids, {"a.txt": "a3456789-0000-4000-8000-000000000001"})

    def test_can_keep_file_names_and_ids(self):
        result = self.run_apply(keep_ids=True)
        self.assertIsNone(result["id_map"])
        self.assertTrue((self.out / "round 2" / "interview.docx").is_file())
        record = json.loads((self.out / "chats" / "export.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(record["id"], "r1")

    def test_main_gives_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = ac.main(["--raw", str(self.raw), "--changes", str(self.changes), "--out", str(self.out),
                            "--policy", str(self.policy)])
        self.assertEqual(code, 0)
        self.assertIn("4 documents anonymized with 6 changes", out.getvalue())
        (self.changes / "answers.csv.json").unlink()
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code = ac.main(["--raw", str(self.raw), "--changes", str(self.changes), "--out", str(self.out),
                            "--policy", str(self.policy), "--force"])
        self.assertEqual(code, 1)
        self.assertIn("Nothing was written", err.getvalue())

    def test_segments_lists_documents_and_shows_segments(self):
        (self.raw / formats.PACKAGE_DESCRIPTION).write_text('{"anonymize_package": 1, "files": []}', encoding="utf-8")
        listing = "\n".join(segments.list_documents(self.raw, self.changes, POLICY))
        self.assertIn("4 files to anonymize, 1 to copy unchanged, 1 left out.", listing)
        self.assertIn("anonymize.json", listing)
        self.assertIn("changes/round 2/interview.docx.json (exists)", listing)
        self.assertIn("chats/export.jsonl/r1: 2 segments", listing)
        without_rules = "\n".join(segments.list_documents(self.raw, self.changes, None))
        self.assertIn("answers.csv: CSV with the columns id, role, answer", without_rules)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = segments.main(["--raw", str(self.raw), "--policy", str(self.policy), "--json", "answers.csv"])
        self.assertEqual(code, 0)
        lines = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(lines[0], {"position": 1, "field": "answer", "text": "Kari here. I like the scheme."})

    def test_segments_shows_the_anonymized_text_with_the_same_addresses(self):
        _, items = segments.document_segments(self.raw, "round 2/interview.docx", POLICY, self.changes)
        self.assertEqual(items, [((1, "content"), "Notes from a talk with [PERSON_1]"),
                                 ((3, "content"), "She works in [a small municipality].")])
        _, items = segments.document_segments(self.raw, "chats/export.jsonl/r1", POLICY, self.changes)
        self.assertIn(((None, "messages[1].content"), "I am [PERSON_1] from [a municipality]."), items)
        self.write(changelist("answers.csv", [change(1, "Pål", "[PERSON_1]", field="answer")]))
        with self.assertRaises(core.ChangeError):
            segments.document_segments(self.raw, "answers.csv", POLICY, self.changes)

    def assess_main(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = assess.main(["--policy", str(self.policy), "--raw", str(self.raw), "--changes", str(self.changes),
                                "--out", str(self.out), "--review", str(self.work / "review"),
                                "--output", str(self.work / "assessment.md"), *args])
        return code, out.getvalue()

    def test_assessment_and_deletion_check(self):
        self.run_apply()
        code, text = self.assess_main()
        self.assertEqual(code, 0, text)
        assessment = (self.work / "assessment.md").read_text(encoding="utf-8")
        self.assertIn("## Deleting the keys", assessment)
        self.assertIn("- [ ] The recruitment list", assessment)
        self.assertIn("recorded for 4 of 4 documents", assessment)
        self.assertNotIn("Kari", assessment)
        self.assertEqual(self.assess_main()[0], 2)  # already exists

        code, text = self.assess_main("--verify-deletion")
        self.assertEqual(code, 1)
        self.assertIn("Not ticked: The recruitment list", text)
        self.assertIn("Still exists", text)
        (self.work / "assessment.md").write_text(assessment.replace("- [ ]", "- [x]"), encoding="utf-8")
        shutil.rmtree(self.raw)
        shutil.rmtree(self.changes)
        code, text = self.assess_main("--verify-deletion")
        self.assertEqual(code, 0, text)
        self.assertIn("Status: checked", (self.work / "assessment.md").read_text(encoding="utf-8"))

    def test_the_assessment_shows_open_points(self):
        doc = changelist("answers.csv", [change(1, "Kari", "[PERSON_1]", field="answer")],
                         needs_review=[{"position": 2, "field": "answer", "note": "Unclear."}])
        del doc["passes"]
        self.write(doc)
        self.run_apply()
        code, text = self.assess_main()
        self.assertEqual(code, 1)
        self.assertIn("1 uncertain case is not decided", text)
        self.assertIn("recorded for 3 of 4 documents", text)
        self.assertIn("## Open points", (self.work / "assessment.md").read_text(encoding="utf-8"))

    def test_the_assessment_needs_goal_suitability_and_a_fresh_package(self):
        self.run_apply()
        self.write_policy({k: v for k, v in POLICY.items() if k != "goal"})
        code, text = self.assess_main()
        self.assertEqual(code, 2)
        self.assertIn("goal", text)
        self.write_policy(POLICY)
        later = time.time() + 60
        os.utime(self.changes / "answers.csv.json", (later, later))
        code, text = self.assess_main()
        self.assertEqual(code, 2)
        self.assertIn("newer than the package", text)

    def test_reduced_risk_has_no_deletion_checklist(self):
        self.write_policy({**POLICY, "goal": "risk_reduction"})
        self.run_apply()
        self.assertEqual(self.assess_main()[0], 0)
        assessment = (self.work / "assessment.md").read_text(encoding="utf-8")
        self.assertNotIn("Deleting the keys", assessment)
        self.assertIn("The keys are kept", assessment)
        self.assertEqual(self.assess_main("--verify-deletion")[0], 1)


if __name__ == "__main__":
    unittest.main()
