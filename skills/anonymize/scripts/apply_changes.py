"""Apply the change lists and build the anonymized package.

    python <skill dir>/scripts/apply_changes.py --raw raw/ --changes changes/ --out out/ --policy policy.json

raw/ holds the originals: .txt, .md, .docx, .csv and .jsonl files, handled as the
file rules in policy.json say. Every document has one change list in changes/.
The anonymized package keeps the file types. formats.py describes what the
addresses in the change lists mean for each file type.

Beyond the change lists, files and records get new IDs and names, because they
can point back to the people. The link is saved in changes/id-map.json, which is
personal data and stays in the project folder. --keep-ids keeps the original
IDs. Rows in CSV files are shuffled and records in JSON Lines files are sorted by
their new ID; --keep-order keeps the order.

The script writes nothing if something is wrong: a change list is missing, a
text is not found verbatim, two changes overlap or the policy version differs.

Exit code: 0 = the package is written, 1 = errors in the change lists, 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import uuid
from pathlib import Path

import core
import formats


def run(raw: Path, changes_dir: Path, out: Path, *, policy: Path | None = None, keep_ids: bool = False,
        keep_order: bool = False, force: bool = False, id_map_path: Path | None = None) -> dict:
    policy_doc = json.loads(policy.read_text(encoding="utf-8")) if policy is not None else None
    policy_version = str(policy_doc["policy_version"]) if policy_doc is not None else None
    id_map_path = id_map_path or changes_dir / core.ID_MAP
    files, stats, ids = formats.build(raw, changes_dir, policy=policy_doc, policy_version=policy_version,
                                      keep_ids=keep_ids, keep_order=keep_order, id_map_path=id_map_path)
    _write(out, files, force)
    if not keep_ids:
        core.save_id_map(id_map_path, ids)
    return stats | {"out": str(out), "id_map": None if keep_ids else str(id_map_path)}


def _is_our_output(folder: Path) -> bool:
    try:
        return "anonymization" in json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False


def _write(out: Path, files: dict[str, bytes], force: bool) -> None:
    """Write the package to a temporary folder next to it, and swap it in at the end."""
    if out.exists() and any(out.iterdir()):
        if not force:
            raise ValueError(f"{out} is not empty. Use --force to replace an earlier anonymized package.")
        if not _is_our_output(out):
            raise ValueError(f"{out} holds something other than an anonymized package and is not replaced.")
    staging = out.parent / f".{out.name}.tmp-{uuid.uuid4().hex[:8]}"
    staging.mkdir(parents=True)
    for path, data in files.items():
        target = staging / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    if out.exists():
        old = out.parent / f".{out.name}.old-{uuid.uuid4().hex[:8]}"
        os.replace(out, old)
        os.replace(staging, out)
        shutil.rmtree(old)
    else:
        os.replace(staging, out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply the change lists and build the anonymized package.")
    parser.add_argument("--raw", type=Path, default=Path("raw"), help="The originals (default raw/).")
    parser.add_argument("--changes", type=Path, default=Path("changes"), help="The change lists (default changes/).")
    parser.add_argument("--out", type=Path, default=Path("out"), help="The anonymized package (default out/).")
    parser.add_argument("--policy", type=Path, help="policy.json. The change lists must use the same version.")
    parser.add_argument("--keep-ids", action="store_true", help="Keep the original IDs and file names.")
    parser.add_argument("--keep-order", action="store_true", help="Keep the order of CSV rows and JSON Lines records.")
    parser.add_argument("--force", action="store_true", help="Replace an earlier anonymized package in --out.")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        result = run(args.raw, args.changes, args.out, policy=args.policy, keep_ids=args.keep_ids,
                     keep_order=args.keep_order, force=args.force)
    except core.ChangeError as exc:
        print("Nothing was written. Errors in the change lists:", file=sys.stderr)
        for problem in exc.problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    except (ValueError, OSError, KeyError) as exc:
        print(f"Nothing was written: {exc}", file=sys.stderr)
        return 2
    documents = core.count(result["documents"], "document", "documents")
    risk = ", ".join(f"{k} {v}" for k, v in sorted(result["residual_risk"].items()))
    print(f"{documents} anonymized with {core.count(result['changes'], 'change', 'changes')}. "
          f"Residual risk: {risk or '-'}.")
    print(f"{core.count(result['needs_review'], 'place is', 'places are')} flagged for a human to decide.")
    print(f"A re-read is recorded for {result['reread']} of {documents}.")
    for note in result.get("notes", []):
        print(f"Note: {note}")
    print(f"The package is written to {result['out']}.")
    if result["id_map"]:
        print(f"The link to the original IDs is saved in {result['id_map']}. It is personal data.")
    print("Next step: run check_residuals.py on the package.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
