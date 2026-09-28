"""Fixed check after anonymization: are known identifiers left?

The script is a check, not the anonymization method. It searches all text files
and Word documents in the anonymized package for:

- known names from the originals (--original raw/): words with a capital letter in
  the names of the files and folders in raw/, which often hold the name of the
  person interviewed, and, with --policy, the values of the fields and columns the
  file rules mark as names,
- names from a list of your own (--names), one per line,
- email addresses, Norwegian phone numbers, Norwegian national identity numbers,
  other 11-digit numbers and links.

Hits can be false. A hit you have assessed goes into an allow list (--allow), one
text per line, with the reason as a comment after #. The report shows the hits
and is therefore personal data when it has hits; --mask hides them.

Other files (for example .xlsx) are reported as unchecked, because the script
cannot see into them.

Exit code: 0 = no hits, 1 = hits, 2 = usage error.

Example:
    python check_residuals.py --target out/ --original raw/ --policy policy.json --allow allow.txt
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.etree import ElementTree

import formats

TEXT_SUFFIXES = {".md", ".csv", ".jsonl", ".json", ".txt", ".html", ".htm", ".tsv"}
SKIP_DIRS = {".opencode", ".git", "__pycache__"}

# Words that often stand in file names or labels without being names.
STOPWORDS = {
    "Respondent", "Interview", "Intervju", "Intervjuer", "Test", "Kommune", "Fylkeskommune", "Leder", "Rådgiver",
    "Saksbehandler", "Transcript", "Transkripsjon", "Transkript", "Referat", "Notes", "Notat", "Svar", "Answers",
    "Survey", "Undersøkelse", "Undersokelse", "Spørreundersøkelse", "Runde", "Round", "Del", "Part", "Versjon",
    "Version", "Utkast", "Draft", "Endelig", "Final", "Kopi", "Copy", "Informant", "Deltaker", "Participant",
    "Fokusgruppe", "Focus", "Group", "Gruppe", "Møte", "Meeting", "Data", "Rådata", "Eksport", "Export",
}

EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
# Norwegian numbers start with 2–9. Only spaces as separators, so dates
# (2026-09-22) and IDs do not match. Numbers inside words or hex strings do not count.
PHONE = re.compile(
    r"(?<![\w+])(?:\+47 ?)?(?:[2-9]\d{7}|[2-9]\d{2} \d{2} \d{3}|[2-9]\d \d{2} \d{2} \d{2})(?!\w)"
)
ELEVEN = re.compile(r"(?<![\w.,])(\d{6}) ?(\d{5})(?![\w])")
UNICODE_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")


@dataclass
class Hit:
    file: str
    line: int
    kind: str
    text: str
    context: str


def fnr_valid(digits: str) -> bool:
    """A valid Norwegian national identity number, D number or H number (date and check digits)."""
    if len(digits) != 11 or not digits.isdigit():
        return False
    d = [int(c) for c in digits]
    day, month = int(digits[0:2]), int(digits[2:4])
    if day > 40:  # D number
        day -= 40
    if month > 80:  # synthetic test numbers
        month -= 80
    elif month > 40:  # H number
        month -= 40
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return False

    def control(weights: list[int], values: list[int]) -> int | None:
        k = 11 - sum(w * v for w, v in zip(weights, values)) % 11
        return 0 if k == 11 else (None if k == 10 else k)

    k1 = control([3, 7, 6, 1, 8, 9, 4, 5, 2], d[:9])
    k2 = control([5, 4, 3, 2, 7, 6, 5, 4, 3, 2], d[:10])
    return k1 == d[9] and k2 == d[10]


def _name_terms(name: str) -> list[tuple[str, str]]:
    """The full name (any case) and the parts of the name (exact)."""
    name = name.strip()
    if len(name) < 3:
        return []
    terms = [("name", name)]
    tokens = re.findall(r"[^\W\d_]+", name)
    if len(tokens) > 1:
        for token in tokens:
            if len(token) >= 3 and token[0].isupper() and token not in STOPWORDS:
                terms.append(("name_part", token))
    return terms


def known_terms(original: Path | None, names_file: Path | None, policy: dict | None = None) -> list[tuple[str, str]]:
    terms: list[tuple[str, str]] = []
    if original is not None:
        if not original.is_dir():
            raise FileNotFoundError(f"Cannot find the folder {original}")
        for path in sorted(p for p in original.rglob("*") if p.is_file()):
            for part in path.relative_to(original).with_suffix("").parts:
                terms += [("file_name", token) for token in re.findall(r"[^\W\d_]+", part)
                          if len(token) >= 3 and token[0].isupper() and token not in STOPWORDS]
        if policy is not None:
            for value in formats.names_in(original, policy):
                terms += _name_terms(value)
    if names_file is not None:
        for line in names_file.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                terms += _name_terms(line) or [("name", line)]
    return list(dict.fromkeys(terms))


def load_allow(path: Path | None) -> set[str]:
    if path is None:
        return set()
    allowed = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.split("#", 1)[0].strip()
        if value:
            allowed.add(value)
    return allowed


def _term_pattern(kind: str, term: str) -> re.Pattern:
    flags = re.IGNORECASE if kind == "name" else 0
    return re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", flags)


def _normalize(line: str, suffix: str) -> str:
    if suffix in {".html", ".htm"}:
        return html.unescape(line)
    if suffix in {".json", ".jsonl"}:
        return UNICODE_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), line)
    return line


def _context(line: str, start: int, end: int, width: int = 40) -> str:
    left = max(0, start - width)
    right = min(len(line), end + width)
    return ("…" if left else "") + line[left:right].strip() + ("…" if right < len(line) else "")


def scan_line(line: str, patterns: list[tuple[str, re.Pattern]]) -> list[tuple[str, int, int]]:
    found = []
    for kind, pattern in patterns:
        for m in pattern.finditer(line):
            found.append((kind, m.start(), m.end()))
    for m in ELEVEN.finditer(line):
        digits = m.group(1) + m.group(2)
        found.append(("national_id" if fnr_valid(digits) else "id_number", m.start(), m.end()))
    return found


def scan(target: Path, terms: list[tuple[str, str]], allowed: set[str]) -> list[Hit]:
    patterns = [(kind, _term_pattern(kind, term)) for kind, term in terms]
    patterns += [("email", EMAIL), ("phone", PHONE), ("link", URL)]
    hits: list[Hit] = []
    files = [target] if target.is_file() else sorted(
        p for p in target.rglob("*") if p.is_file() and not (SKIP_DIRS & set(p.relative_to(target).parts))
    )
    for path in files:
        rel = path.name if target.is_file() else path.relative_to(target).as_posix()
        suffix = path.suffix.lower()
        if suffix == ".docx":
            try:
                lines = formats.docx_paragraphs(path)
            except (zipfile.BadZipFile, KeyError, ElementTree.ParseError):
                hits.append(Hit(rel, 0, "unchecked_file", path.suffix, "Cannot be read as a Word document."))
                continue
        elif suffix not in TEXT_SUFFIXES:
            hits.append(Hit(rel, 0, "unchecked_file", path.suffix,
                            "This file type cannot be checked. Remove the file or check it by hand."))
            continue
        else:
            try:
                lines = path.read_text(encoding="utf-8-sig").splitlines()
            except UnicodeDecodeError:
                hits.append(Hit(rel, 0, "unchecked_file", path.suffix, "The file is not UTF-8."))
                continue
        # Line number in text files, paragraph number in Word documents.
        for number, raw in enumerate(lines, start=1):
            line = _normalize(raw, suffix)
            for kind, start, end in scan_line(line, patterns):
                value = line[start:end]
                if value in allowed or value.strip() in allowed:
                    continue
                hits.append(Hit(rel, number, kind, value, _context(line, start, end)))
    return hits


def _mask(value: str) -> str:
    return value[:1] + "*" * max(0, len(value) - 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search for identifiers left after anonymization.")
    parser.add_argument("--target", required=True, type=Path, help="The anonymized package (folder or file).")
    parser.add_argument("--original", type=Path, help="The originals in raw/, for known names.")
    parser.add_argument("--policy", type=Path, help="policy.json, for the fields and columns that hold names.")
    parser.add_argument("--names", type=Path, help="A file with more names to search for, one per line.")
    parser.add_argument("--allow", type=Path, help="A file with assessed hits to accept, one per line.")
    parser.add_argument("--json", action="store_true", help="Write the report as JSON.")
    parser.add_argument("--mask", action="store_true", help="Hide the hits in the report.")
    args = parser.parse_args(argv)
    # Windows consoles often use another encoding; æøå and quotes must show correctly.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not args.target.exists():
        print(f"Cannot find {args.target}", file=sys.stderr)
        return 2
    try:
        policy = json.loads(args.policy.read_text(encoding="utf-8")) if args.policy else None
        terms = known_terms(args.original, args.names, policy)
        allowed = load_allow(args.allow)
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2

    hits = scan(args.target, terms, allowed)
    if args.mask:
        # Hide every hit on the same line in each context, not only the hit's own.
        by_line: dict[tuple[str, int], set[str]] = {}
        for hit in hits:
            by_line.setdefault((hit.file, hit.line), set()).add(hit.text)
        for hit in hits:
            for text in sorted(by_line[(hit.file, hit.line)], key=len, reverse=True):
                hit.context = re.sub(re.escape(text), _mask(text), hit.context, flags=re.IGNORECASE)
            hit.text = _mask(hit.text)

    if args.json:
        counts: dict[str, int] = {}
        for hit in hits:
            counts[hit.kind] = counts.get(hit.kind, 0) + 1
        print(json.dumps({"hits": [asdict(h) for h in hits], "counts": counts, "known_terms": len(terms)},
                         ensure_ascii=False, indent=2))
    else:
        for hit in hits:
            where = f"{hit.file}:{hit.line}" if hit.line else hit.file
            print(f"{where}: {hit.kind}: '{hit.text}'  {hit.context}")
        print(f"{len(hits)} hits. {len(terms)} known names were checked.")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
