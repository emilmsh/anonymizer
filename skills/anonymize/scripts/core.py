"""Shared by all formats: change lists, new IDs and version.

A document is a set of text segments, each with an address (position, field).
A change list belongs to one document and says which verbatim excerpts to
replace. formats.py says what the addresses mean for each file type.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
ACTIONS = {"replace", "generalize", "remove"}
CATEGORIES = {"person", "organization", "place", "role", "event", "date", "contact", "id", "health", "other"}
CATEGORY_LABELS = {"id": "ID number", "contact": "contact details"}
RISKS = {"low", "medium", "high"}
CHANGE_KEYS = ("position", "field", "original", "occurrence", "action", "replacement", "category", "reason")
OPTIONAL_CHANGE_KEYS = ("round",)
DOCUMENT_KEYS = ("document_id", "policy_version", "model", "passes", "changes", "residual_risk", "needs_review")
ID_MAP = "id-map.json"

Key = tuple[int | None, str]


class ChangeError(Exception):
    """Errors in change lists. ``problems`` holds readable lines."""

    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


def count(n: int, one: str, many: str) -> str:
    """'1 document', '2 documents'."""
    return f"{n} {one if n == 1 else many}"


def tool_version() -> str:
    path = SKILL_DIR / "VERSION"
    return path.read_text(encoding="utf-8").strip() if path.is_file() else "unknown"


# ---------------------------------------------------------------------------
# Reading and checking change lists
# ---------------------------------------------------------------------------


def changes_path(changes_dir: Path, doc_id: str) -> Path:
    """changes/<document ID>.json. Folders in raw/ are mirrored in changes/."""
    return changes_dir / f"{doc_id}.json"


def load_changelist(path: Path, doc_id: str) -> tuple[dict | None, list[str]]:
    if not path.is_file():
        return None, [f"{doc_id}: change list is missing ({path.as_posix()})."]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [f"{doc_id}: change list is not valid JSON ({exc})."]


def _is_int(value, minimum: int = 1) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def validate(doc: dict, doc_id: str, segments: Iterable[Key], fields: Iterable[str],
             policy_version: str | None) -> list[str]:
    """Check a change list against the schema and against the document.

    ``segments`` are the addresses that exist in the document, ``fields`` the
    fields that can be changed in this document.
    """
    if not isinstance(doc, dict):
        return [f"{doc_id}: the change list must be a JSON object."]
    problems = [f"{doc_id}: missing '{key}'." for key in ("document_id", "policy_version", "changes",
                                                           "residual_risk", "needs_review") if key not in doc]
    if problems:
        return problems
    if not isinstance(doc["changes"], list) or not isinstance(doc["needs_review"], list):
        return [f"{doc_id}: changes and needs_review must be lists."]
    if doc["document_id"] != doc_id:
        problems.append(f"{doc_id}: document_id in the file is {doc['document_id']}.")
    unknown = sorted(set(doc) - set(DOCUMENT_KEYS))
    if unknown:
        problems.append(f"{doc_id}: unknown keys {', '.join(unknown)}.")
    if policy_version is not None and str(doc["policy_version"]) != str(policy_version):
        problems.append(f"{doc_id}: made under policy {doc['policy_version']}, current is {policy_version}.")
    if doc["residual_risk"] not in RISKS:
        problems.append(f"{doc_id}: residual_risk must be one of {sorted(RISKS)}.")
    if "passes" in doc and not _is_int(doc["passes"]):
        problems.append(f"{doc_id}: passes must be an integer from 1.")

    segments, fields = set(segments), sorted(set(fields))
    for i, change in enumerate(doc["changes"], start=1):
        where = f"{doc_id}, change {i}"
        if not isinstance(change, dict):
            problems.append(f"{where}: must be a JSON object.")
            continue
        missing = [k for k in CHANGE_KEYS if k not in change]
        if missing:
            problems.append(f"{where}: missing {', '.join(missing)}.")
            continue
        extra = sorted(set(change) - set(CHANGE_KEYS) - set(OPTIONAL_CHANGE_KEYS))
        if extra:
            problems.append(f"{where}: unknown keys {', '.join(extra)}.")
        field, position = change["field"], change["position"]
        if field not in fields:
            valid = ", ".join(f"'{f}'" for f in fields[:10]) or "none"
            problems.append(f"{where}: unknown field '{field}'. Valid here: {valid}.")
        elif (position, field) not in segments:
            problems.append(f"{where}: no text at position {position} in field '{field}'.")
        if change["action"] not in ACTIONS:
            problems.append(f"{where}: unknown action '{change['action']}'.")
        if change["category"] not in CATEGORIES:
            problems.append(f"{where}: unknown category '{change['category']}'.")
        if not isinstance(change["original"], str) or not change["original"]:
            problems.append(f"{where}: original must be non-empty text.")
        if not _is_int(change["occurrence"]):
            problems.append(f"{where}: occurrence must be an integer from 1.")
        if not isinstance(change["replacement"], str):
            problems.append(f"{where}: replacement must be text.")
        if "round" in change and not _is_int(change["round"]):
            problems.append(f"{where}: round must be an integer from 1.")
    for i, item in enumerate(doc["needs_review"], start=1):
        if not isinstance(item, dict) or not isinstance(item.get("note"), str):
            problems.append(f"{doc_id}, needs_review {i}: must have a note.")
    return problems


# ---------------------------------------------------------------------------
# Applying the changes
# ---------------------------------------------------------------------------


def apply_to_text(text: str, changes: list[tuple[int, dict]], where: str) -> tuple[str, list[str]]:
    """Apply the changes to one text. Returns the new text and any errors."""
    spans: list[tuple[int, int, str, int]] = []
    problems: list[str] = []
    for number, change in changes:
        original, occurrence = change["original"], change["occurrence"]
        start, search_from = -1, 0
        for _ in range(occurrence):
            start = text.find(original, search_from)
            if start < 0:
                break
            search_from = start + len(original)
        if start < 0:
            problems.append(f"{where}, change {number}: cannot find occurrence {occurrence} of '{original}' verbatim.")
            continue
        replacement = change["replacement"] or "[removed]"
        spans.append((start, start + len(original), replacement, number))
    spans.sort()
    for (s1, e1, _, n1), (s2, e2, _, n2) in zip(spans, spans[1:]):
        if s2 < e1:
            problems.append(f"{where}: changes {n1} and {n2} overlap.")
    if problems:
        return text, problems
    for start, end, replacement, _ in reversed(spans):
        text = text[:start] + replacement + text[end:]
    return text, []


def apply(segments: dict[Key, str], doc: dict, doc_id: str, label: Callable[[Key], str]) -> dict[Key, str]:
    """New texts for the segments the changes apply to. Raises ChangeError on errors."""
    grouped: dict[Key, list[tuple[int, dict]]] = {}
    for number, change in enumerate(doc["changes"], start=1):
        grouped.setdefault((change["position"], change["field"]), []).append((number, change))
    result: dict[Key, str] = {}
    problems: list[str] = []
    for key, changes in grouped.items():
        result[key], errors = apply_to_text(segments[key], changes, f"{doc_id}, {label(key)}")
        problems += errors
    if problems:
        raise ChangeError(problems)
    return result


def stats(docs: Iterable[dict], *, new_ids: bool) -> dict:
    """Numbers for the manifest and the assessment. No text from the documents."""
    out = {"documents": 0, "changes": 0, "by_category": {}, "by_action": {}, "by_round": {}, "residual_risk": {},
           "needs_review": 0, "reread": 0, "models": [], "new_ids": new_ids}
    models = set()
    for doc in docs:
        out["documents"] += 1
        out["changes"] += len(doc["changes"])
        out["needs_review"] += len(doc["needs_review"])
        out["reread"] += 1 if doc.get("passes", 1) >= 2 else 0
        out["residual_risk"][doc["residual_risk"]] = out["residual_risk"].get(doc["residual_risk"], 0) + 1
        if doc.get("model"):
            models.add(str(doc["model"]))
        for change in doc["changes"]:
            for key, value in (("by_category", change["category"]), ("by_action", change["action"]),
                               ("by_round", str(change.get("round", 1)))):
                out[key][value] = out[key].get(value, 0) + 1
    out["models"] = sorted(models)
    return out


def anonymization_record(stats: dict, policy_version: str | None, measures: list[str], **extra) -> dict:
    """The 'anonymization' block in the manifest of the anonymized package."""
    keys = ("documents", "changes", "by_category", "by_action", "by_round", "residual_risk", "needs_review",
            "reread", "models")
    return {
        "tool": "anonymizer", "version": tool_version(), "at": datetime.now(timezone.utc).date().isoformat(),
        "policy_version": policy_version, "new_ids": stats["new_ids"], **extra,
        **{key: stats[key] for key in keys}, "measures": measures,
    }


def category_text(by_category: dict[str, int]) -> str:
    """For example 'person 5, place 3', most frequent first."""
    labelled = sorted(((CATEGORY_LABELS.get(k, k), v) for k, v in by_category.items()), key=lambda x: (-x[1], x[0]))
    return ", ".join(f"{label} {v}" for label, v in labelled) or "none"


# ---------------------------------------------------------------------------
# New IDs
# ---------------------------------------------------------------------------


def short_id(new_id: str) -> str:
    return new_id.replace("-", "")[:8]


def load_id_map(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def save_id_map(path: Path, ids: dict[str, str]) -> None:
    merged = {**load_id_map(path), **ids}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def assign_ids(ids: list[str], existing: dict[str, str], keep: bool) -> dict[str, str]:
    """The same old ID gets the same new ID on a new run. Short IDs are unique.

    A short ID made only of digits could look like a phone number to the
    residual check, so none is made.
    """
    if keep:
        return {old: old for old in ids}
    mapping = {old: existing[old] for old in ids if old in existing}
    shorts = {short_id(new) for new in mapping.values()} | {short_id(old) for old in ids}
    for old in ids:
        if old in mapping:
            continue
        while True:
            new = str(uuid.uuid4())
            if short_id(new) not in shorts and not short_id(new).isdigit():
                break
        shorts.add(short_id(new))
        mapping[old] = new
    return mapping
