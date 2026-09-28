"""Tests for skills/anonymize/scripts/formats.py: file rules, text, Word, CSV and JSON Lines. All data is fictional."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "anonymize" / "scripts"))
import formats  # noqa: E402

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
MC = 'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"'
BODY = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document {W} {MC}><w:body>
<w:p><w:pPr><w:tabs><w:tab w:val="left" w:pos="720"/></w:tabs></w:pPr>
  <w:r><w:t>Interview with </w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>Kari</w:t></w:r>
  <w:r><w:t xml:space="preserve"> Nordmann</w:t></w:r><w:r><w:tab/><w:t>Fjordvik</w:t></w:r></w:p>
<w:p/>
<w:p><w:r><w:t>Line one</w:t><w:br/><w:t>line two</w:t></w:r></w:p>
<w:p><w:del w:id="1" w:author="Kari Nordmann"><w:r><w:delText>deleted </w:delText></w:r></w:del>
  <w:ins w:id="2" w:author="Kari Nordmann"><w:r><w:t>inserted</w:t></w:r></w:ins></w:p>
<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
<w:p><w:r><mc:AlternateContent><mc:Choice Requires="wps"><w:drawing><w:txbxContent>
  <w:p><w:r><w:t>Text box</w:t></w:r></w:p></w:txbxContent></w:drawing></mc:Choice>
  <mc:Fallback><w:pict><w:txbxContent><w:p><w:r><w:t>Text box</w:t></w:r></w:p></w:txbxContent></w:pict></mc:Fallback>
  </mc:AlternateContent></w:r><w:r><w:t>After the box</w:t></w:r></w:p>
<w:sectPr/></w:body></w:document>"""
PARTS = {
    "word/header1.xml": f'<w:hdr {W}><w:p><w:r><w:t>Kari Nordmann</w:t></w:r></w:p></w:hdr>',
    "word/comments.xml": f'<w:comments {W}><w:comment w:id="0" w:author="Ola"><w:p><w:r><w:t>Check Fjordvik</w:t></w:r></w:p></w:comment></w:comments>',
    "word/footnotes.xml": f'<w:footnotes {W}><w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote></w:footnotes>',
    "docProps/core.xml": '<cp:coreProperties xmlns:cp="x" xmlns:dc="y"><dc:creator>Kari Nordmann</dc:creator></cp:coreProperties>',
    "word/media/image1.png": "PNG",
}
PARAGRAPHS = ["Interview with Kari Nordmann\tFjordvik", "", "Line one\nline two", "inserted", "Cell", "After the box", "Text box"]
CSV_RULE = {"match": "*.csv", "text_columns": ["answer"], "keep_columns": ["role"], "date_columns": ["sent"],
            "drop_columns": ["id", "municipality"], "name_columns": ["municipality"]}
JSONL_RULE = {"match": "*.jsonl", "id": "id", "text": ["messages[].content", "summary"], "keep": ["messages[].role"],
              "dates": ["started"], "names": ["person.name"], "skip": {"test": True}}
RECORDS = [
    {"id": "a1", "person": {"name": "Kari Nordmann"}, "started": "2026-03-10T23:30:00-02:00", "secret": "x",
     "messages": [{"role": "assistant", "content": "Hi!"}, {"role": "user", "content": "I am Kari from Fjordvik.", "at": "t"}],
     "summary": "Kari from Fjordvik."},
    {"id": "t1", "test": True, "messages": [{"role": "user", "content": "Test"}]},
    {"id": "b2", "person": {"name": "Ola Hansen"}, "messages": [{"role": "user", "content": ""}], "summary": "Nothing."},
]


def make_docx(path: Path, body: str = BODY, parts: dict | None = None) -> None:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", body)
        for name, text in (PARTS if parts is None else parts).items():
            z.writestr(name, text)


def one(raw: Path, name: str, policy: dict | None = None) -> formats.Document:
    documents, _ = formats.load_documents(raw, policy)
    return next(d for d in documents if d.file == name)


class FormatsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raw = Path(self.tmp.name) / "raw"
        self.raw.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_text_file_has_line_numbers_and_keeps_line_endings(self):
        (self.raw / "a.txt").write_bytes("I: Hello\r\n\r\nR: I live in Fjordvik.\r\n".encode("utf-8"))
        doc = one(self.raw, "a.txt")
        self.assertEqual(doc.segments, {(1, "content"): "I: Hello", (3, "content"): "R: I live in Fjordvik."})
        out = formats._render_text(doc, {**doc.segments, (3, "content"): "R: I live in [PLACE_1]."})
        self.assertEqual(out, "I: Hello\r\n\r\nR: I live in [PLACE_1].\r\n".encode("utf-8"))

    def test_text_file_that_is_not_utf8_is_read_as_windows_1252(self):
        (self.raw / "b.md").write_bytes("Kari lives in Ås".encode("cp1252"))
        doc = one(self.raw, "b.md")
        self.assertEqual(doc.segments[(1, "content")], "Kari lives in Ås")
        self.assertIn("Windows-1252", doc.notes[0])

    def test_word_reads_paragraphs_in_order_without_hidden_parts(self):
        make_docx(self.raw / "c.docx")
        self.assertEqual(formats.docx_paragraphs(self.raw / "c.docx"), PARAGRAPHS)
        doc = one(self.raw, "c.docx")
        self.assertNotIn((2, "content"), doc.segments)
        notes = " ".join(doc.notes)
        for word in ("header", "comments", "images", "tracked changes"):
            self.assertIn(word, notes)
        self.assertNotIn("footnotes", notes)

    def test_word_is_rebuilt_without_metadata(self):
        paragraphs = ["Interview with [PERSON_1]\t[PLACE_1]", *PARAGRAPHS[1:]]
        out = Path(self.tmp.name) / "out.docx"
        out.write_bytes(formats.docx_bytes(paragraphs))
        self.assertEqual(formats.docx_paragraphs(out), paragraphs)
        with zipfile.ZipFile(out) as z:
            self.assertEqual({i.date_time for i in z.infolist()}, {(1980, 1, 1, 0, 0, 0)})
            self.assertFalse(any(n.startswith("docProps") for n in z.namelist()))
            everything = b"".join(z.read(n) for n in z.namelist())
        self.assertNotIn(b"Kari", everything)

    def test_word_that_cannot_be_read_gives_an_error(self):
        (self.raw / "d.docx").write_bytes(b"not a zip")
        with self.assertRaises(formats.FormatError):
            formats.load_documents(self.raw, None)

    def test_csv_needs_every_column_in_a_rule(self):
        (self.raw / "e.csv").write_text("id;municipality;role;sent;answer;age\n1;Fjordvik;Manager;x;I am Kari.;44\n",
                                        encoding="utf-8")
        with self.assertRaises(formats.FormatError) as raised:
            formats.load_documents(self.raw, None)
        self.assertIn("text_columns", str(raised.exception))
        with self.assertRaises(formats.FormatError) as raised:
            formats.load_documents(self.raw, {"files": [CSV_RULE]})
        self.assertIn("age", str(raised.exception))
        double = {**CSV_RULE, "keep_columns": ["role", "age"], "drop_columns": ["id", "municipality", "age"]}
        with self.assertRaises(formats.FormatError):
            formats.load_documents(self.raw, {"files": [double]})

    def test_csv_drops_columns_shortens_dates_and_shuffles_rows_the_same_way(self):
        rows = "".join(f"{i},Fjordvik,Manager,2026-03-0{i % 9 + 1} 10:00,Answer {i}\n" for i in range(1, 21))
        (self.raw / "f.csv").write_text("id,municipality,role,sent,answer\n" + rows, encoding="utf-8")
        doc = one(self.raw, "f.csv", {"files": [CSV_RULE]})
        self.assertEqual(doc.segments[(3, "answer")], "Answer 3")
        self.assertEqual(doc.fields, {"answer"})

        def lines(**kwargs) -> list[str]:
            data = formats._render_csv(doc, {**doc.segments, (3, "answer"): "[changed]"}, "new-id", **kwargs)
            return data.decode("utf-8").lstrip("﻿").splitlines()

        shuffled, ordered = lines(keep_order=False), lines(keep_order=True)
        self.assertEqual(shuffled, lines(keep_order=False))
        self.assertEqual(shuffled[0], "role,sent,answer")
        self.assertEqual(ordered[1:4], ["Manager,2026-03-02,Answer 1", "Manager,2026-03-03,Answer 2",
                                        "Manager,2026-03-04,[changed]"])
        self.assertNotIn("Fjordvik", "\n".join(shuffled))
        self.assertNotEqual(shuffled[1:], ordered[1:])
        self.assertEqual(sorted(shuffled[1:]), sorted(ordered[1:]))
        self.assertEqual(formats.names_in(self.raw, {"files": [CSV_RULE]}), ["Fjordvik"] * 20)

    def test_csv_with_too_many_cells_gives_an_error(self):
        (self.raw / "g.csv").write_text("id;municipality;role;sent;answer\n1;F;M;x;A;extra\n", encoding="utf-8")
        with self.assertRaises(formats.FormatError):
            formats.load_documents(self.raw, {"files": [CSV_RULE]})

    def test_jsonl_makes_one_document_per_record_with_paths(self):
        (self.raw / "chats.jsonl").write_text("".join(json.dumps(r) + "\n" for r in RECORDS), encoding="utf-8")
        documents, _ = formats.load_documents(self.raw, {"files": [JSONL_RULE]})
        self.assertEqual([d.id for d in documents], ["chats.jsonl/a1", "chats.jsonl/b2"])
        first = documents[0]
        self.assertEqual(first.segments, {(None, "messages[0].content"): "Hi!",
                                          (None, "messages[1].content"): "I am Kari from Fjordvik.",
                                          (None, "summary"): "Kari from Fjordvik."})
        record = formats._render_record(first, {**first.segments, (None, "summary"): "[PERSON_1] from [PLACE_1]."}, "new")
        self.assertEqual(record, {"id": "new", "messages": [{"role": "assistant", "content": "Hi!"},
                                                            {"role": "user", "content": "I am Kari from Fjordvik."}],
                                  "started": "2026-03-11", "summary": "[PERSON_1] from [PLACE_1]."})
        second = formats._render_record(documents[1], documents[1].segments, "new2")
        self.assertEqual(second["messages"], [{"role": "user", "content": ""}])
        self.assertEqual(documents[0].data["skipped"], 1)
        self.assertEqual(formats.names_in(self.raw, {"files": [JSONL_RULE]}), ["Kari Nordmann", "Ola Hansen"])

    def test_jsonl_needs_a_rule_with_text_and_safe_unique_ids(self):
        rule = {"files": [{"match": "*.jsonl", "id": "id", "text": ["text"]}]}
        (self.raw / "h.jsonl").write_text('{"id": "a/b", "text": "x"}\n', encoding="utf-8")
        with self.assertRaises(formats.FormatError):
            formats.load_documents(self.raw, None)
        with self.assertRaises(formats.FormatError):
            formats.load_documents(self.raw, rule)
        (self.raw / "h.jsonl").write_text('{"id": "a", "text": "x"}\n{"id": "a", "text": "y"}\n', encoding="utf-8")
        with self.assertRaises(formats.FormatError):
            formats.load_documents(self.raw, rule)

    def test_paths_are_parsed_expanded_and_set(self):
        self.assertEqual(formats.parse_path("a.b[].c[2]"), ["a", "b", None, "c", 2])
        with self.assertRaises(formats.FormatError):
            formats.parse_path("a..b")
        value = {"a": [{"b": 1}, {"b": 2}, {"c": 3}]}
        self.assertEqual(formats.expand(value, formats.parse_path("a[].b")), [("a[0].b", 1), ("a[1].b", 2)])
        target: dict = {}
        formats.set_path(target, "a[1].b", "x")
        self.assertEqual(target, {"a": [None, {"b": "x"}]})

    def test_file_rules_copy_exclude_and_are_checked(self):
        (self.raw / "a.txt").write_text("Hello", encoding="utf-8")
        (self.raw / "guide.md").write_text("Interview guide", encoding="utf-8")
        (self.raw / "view.html").write_text("<p>Kari</p>", encoding="utf-8")
        (self.raw / formats.PACKAGE_DESCRIPTION).write_text("{}", encoding="utf-8")
        (self.raw / "~$a.docx").write_bytes(b"Kari Nordmann")
        rules = [{"match": "guide.md", "action": "copy"}, {"match": "*.html", "action": "exclude"}]
        p = formats.plan(self.raw, {"files": rules})
        self.assertEqual([path.name for path, _, _ in p.anonymize], ["a.txt"])
        self.assertEqual(([x.name for x in p.copy], [x.name for x in p.exclude]), (["guide.md"], ["view.html"]))
        self.assertTrue(p.has_description)
        with self.assertRaises(formats.FormatError) as raised:
            formats.load_documents(self.raw, None)
        self.assertIn("view.html", str(raised.exception))
        problems = formats.check_rules([{"match": "*.csv", "text_column": ["a"]}, {"match": "x", "action": "move"},
                                        {"match": "*.jsonl", "text": ["a..b"]}, {"type": "csv"}])
        self.assertEqual(len(problems), 4)
        self.assertIn("unknown keys text_column", problems[0])


if __name__ == "__main__":
    unittest.main()
