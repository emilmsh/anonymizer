"""Show the documents in raw/ with the numbered segments the change lists refer to.

    python <skill dir>/scripts/segments.py --raw raw/ --policy policy.json --list
    python <skill dir>/scripts/segments.py --raw raw/ --policy policy.json interview-01.docx
    python <skill dir>/scripts/segments.py --raw raw/ --policy policy.json --anonymized interview-01.docx

--list shows what happens to each file, the documents, the number of segments
and where each change list goes, without the content. CSV files are shown with
their column names, so the columns can be set up in policy.json. A package
description (anonymize.json) from the tool that made the export is reported.

With a document ID, the segments of that document are shown, each with position
and field as they are written in the change list. --json gives one JSON line per
segment, with the text exactly as it must be written in 'original'.

--anonymized shows the text with the change list applied, with the same
addresses as the original. This is what is read in the re-read. Findings go into
the same change list.

Output with a document ID contains personal data and must only be read by the
approved AI provider.

Exit code: 0 = ok, 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import core
import formats


def list_documents(raw: Path, changes: Path, policy: dict | None) -> list[str]:
    p = formats.plan(raw, policy)
    out = [f"{core.count(len(p.anonymize), 'file', 'files')} to anonymize, {len(p.copy)} to copy unchanged, "
           f"{len(p.exclude)} left out."]
    if p.has_description:
        out.append(f"The package has a description ({formats.PACKAGE_DESCRIPTION}) from the tool that made it. "
                   "Use its file rules as a draft for 'files' in policy.json, and show them to the user.")

    def status(doc_id: str) -> str:
        path = core.changes_path(changes, doc_id)
        return f"{path.as_posix()} ({'exists' if path.is_file() else 'missing'})"

    for path, kind, rule in p.anonymize:
        rel = path.relative_to(raw).as_posix()
        try:
            documents = formats.read_file(raw, path, kind, rule)
        except formats.FormatError as exc:
            columns = f" with the columns {', '.join(formats.csv_columns(path))}" if kind == "csv" else ""
            out.append(f"- {rel}: {formats.KIND_LABELS[kind]}{columns}. {exc}")
            continue
        if kind == "jsonl":
            out.append(f"- {rel}: JSON Lines, {core.count(len(documents), 'record', 'records')} "
                       f"({documents[0].address() if documents else 'no records'}).")
            out += [f"  - {d.id}: {core.count(len(d.segments), 'segment', 'segments')}. Change list: {status(d.id)}"
                    for d in documents]
            continue
        d = documents[0]
        out.append(f"- {rel}: {formats.KIND_LABELS[kind]}, {core.count(len(d.segments), 'segment', 'segments')} "
                   f"({d.address()}). Change list: {status(d.id)}")
        out += [f"  Note: {note}" for note in d.notes]
    out += [f"- {path.relative_to(raw).as_posix()}: copied unchanged." for path in p.copy]
    out += [f"- {path.relative_to(raw).as_posix()}: not supported. Save it as .docx, .txt, .md, .csv or .jsonl, "
            "move it out of the folder, or add a file rule for it." for path in p.unsupported]
    if p.exclude:
        out.append(f"{core.count(len(p.exclude), 'file is', 'files are')} left out by the file rules.")
    return out


def document_segments(raw: Path, doc_id: str, policy: dict | None,
                      changes: Path | None = None) -> tuple[str, list[tuple[core.Key, str]]]:
    """The address description and the segments of one document, in order.

    With ``changes``, the change list is applied, so the text is the anonymized
    one, with the same addresses as the original.
    """
    document = formats.find_document(raw, doc_id, policy)
    texts = document.segments
    if changes is not None:
        doc, problems = core.load_changelist(core.changes_path(changes, doc_id), doc_id)
        policy_version = str(policy["policy_version"]) if policy and "policy_version" in policy else None
        problems = problems or core.validate(doc, doc_id, texts, document.fields, policy_version)
        if problems:
            raise core.ChangeError(problems)
        texts = {**texts, **core.apply(texts, doc, doc_id, document.label)}
    items = [(key, texts[key]) for key in document.segments]
    if document.kind != "jsonl":
        # JSON Lines keep the order of the paths in the rule; the others go by position, then column.
        columns = document.data.get("header", [])
        items.sort(key=lambda item: (item[0][0], columns.index(item[0][1]) if item[0][1] in columns else 0))
    return document.address(), items


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show the documents and the numbered segments.")
    parser.add_argument("document", nargs="?", help="Document ID (the path under raw/, plus /<record ID> for JSON Lines).")
    parser.add_argument("--raw", type=Path, default=Path("raw"), help="The originals (default raw/).")
    parser.add_argument("--changes", type=Path, default=Path("changes"), help="The change lists (default changes/).")
    parser.add_argument("--policy", type=Path, help="policy.json with the file rules.")
    parser.add_argument("--list", action="store_true", help="Show the documents without content.")
    parser.add_argument("--json", action="store_true", help="One JSON line per segment.")
    parser.add_argument("--anonymized", action="store_true",
                        help="Show the text with the change list applied, for the re-read.")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        policy = json.loads(args.policy.read_text(encoding="utf-8")) if args.policy else None
        if args.list or not args.document:
            print("\n".join(list_documents(args.raw, args.changes, policy)))
            return 0
        address, items = document_segments(args.raw, args.document, policy,
                                           args.changes if args.anonymized else None)
    except core.ChangeError as exc:
        print("The change list cannot be applied:", file=sys.stderr)
        for problem in exc.problems:
            print(f"- {problem}", file=sys.stderr)
        return 2
    except (ValueError, OSError, KeyError) as exc:
        print(exc, file=sys.stderr)
        return 2
    if args.json:
        for (position, field), text in items:
            print(json.dumps({"position": position, "field": field, "text": text}, ensure_ascii=False))
        return 0
    print(f"Document: {args.document}{' (anonymized)' if args.anonymized else ''}")
    print(f"Change list: {core.changes_path(args.changes, args.document).as_posix()}")
    print(f"Address: {address}")
    print("Line breaks inside a segment are shown indented and written as \\n in 'original'.")
    print()
    for (position, field), text in items:
        where = "null" if position is None else str(position)
        name = "" if field == "content" else f" {field}:"
        print(f"[{where}]{name} {text}".replace("\n", "\n    "))
    return 0


if __name__ == "__main__":
    sys.exit(main())
