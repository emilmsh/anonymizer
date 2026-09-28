"""Write the assessment of the anonymization, and check that the keys are deleted.

    python <skill dir>/scripts/assess.py --policy policy.json --raw raw/ --changes changes/ --out out/
    python <skill dir>/scripts/assess.py --verify-deletion

The assessment (assessment.md) documents the anonymization: the goal, the
suitability decision, the rules, what was done, the result of the fixed check
and how the three criteria in the EDPB draft guidelines are met. It builds on
policy.json, the manifest in out/ and a new run of the residual check. It holds
numbers and decisions, no text from the documents, and can be kept after the
keys are deleted.

When the goal is anonymous data, the assessment has a checklist for deleting the
keys. A human deletes and ticks the boxes. --verify-deletion checks that every box
is ticked and that raw/, changes/, review/, allow.txt and names.txt do not exist,
and writes the result into the assessment.

Exit code: 0 = no open points, 1 = open points (listed in the output and in the
assessment), 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

import check_residuals
import core

GOALS = {
    "anonymous": "Anonymous data. The anonymized data may be used by providers without a data processing "
                 "agreement once the keys are deleted.",
    "risk_reduction": "Reduced risk. The keys are kept, and the anonymized data is still treated as personal "
                      "data at approved providers.",
}
ACTION_LABELS = {"replace": "replaced", "generalize": "generalized", "remove": "removed"}
DELETION = "## Deleting the keys"
STATUS = re.compile(r"^Status: .*$", re.MULTILINE)


class AssessError(ValueError):
    pass


def _manifest(out: Path) -> tuple[Path, dict]:
    path = out / "manifest.json"
    if path.is_file():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if "anonymization" in manifest:
            return path, manifest
    raise AssessError(f"Found no anonymized package in {out}. Run apply_changes.py first.")


def _check_policy(policy: dict) -> list[str]:
    problems = []
    if policy.get("goal") not in GOALS:
        problems.append("policy.json lacks 'goal' (anonymous or risk_reduction).")
    assessment = policy.get("assessment")
    if not isinstance(assessment, dict):
        problems.append("policy.json lacks 'assessment' with the suitability decision.")
    else:
        for key, kind in (("recipients", str), ("suitable", bool), ("rationale", str)):
            if not isinstance(assessment.get(key), kind):
                problems.append(f"policy.json lacks assessment.{key}.")
    return problems


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) or "- (none)"


def build(policy: dict, manifest: dict, hits: list, allowed: int) -> tuple[str, list[str]]:
    """The assessment as Markdown, and the points that are open before release."""
    a = manifest["anonymization"]
    assessment = policy["assessment"]
    goal = policy["goal"]
    n = a.get("documents", 0)
    docs = core.count(n, "document", "documents")
    by_round = a.get("by_round", {})
    reread_changes = sum(v for k, v in by_round.items() if k != "1")
    open_points = []
    if not assessment["suitable"]:
        open_points.append("The data is judged unsuitable for anonymization. It must not be shared as anonymous.")
    if a.get("needs_review", 0):
        open_points.append(f"{core.count(a['needs_review'], 'uncertain case is', 'uncertain cases are')} not decided.")
    if a.get("reread", 0) < n:
        open_points.append(f"A re-read is recorded for {a.get('reread', 0)} of {docs}.")
    if hits:
        open_points.append(f"The residual check found {core.count(len(hits), 'hit', 'hits')} "
                           "that are not fixed or assessed.")

    counts: dict[str, int] = {}
    for hit in hits:
        counts[hit.kind] = counts.get(hit.kind, 0) + 1
    if hits:
        found = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
        control = (f"The residual check found {core.count(len(hits), 'hit', 'hits')} ({found}). They must be fixed, "
                   "or assessed and put in the allow list.")
    else:
        control = "The residual check found no known names, contact details, ID numbers or links."
    if allowed:
        control += f" {core.count(allowed, 'hit is', 'hits are')} assessed and accepted in the allow list."

    actions = ", ".join(f"{ACTION_LABELS.get(k, k)} {v}"
                        for k, v in sorted(a.get("by_action", {}).items(), key=lambda x: -x[1])) or "none"
    risk = ", ".join(f"{k} {a['residual_risk'][k]}"
                     for k in ("low", "medium", "high") if a.get("residual_risk", {}).get(k)) or "-"
    models = ", ".join(a.get("models") or []) or "not given in the change lists"
    health = a.get("by_category", {}).get("health", 0)
    generalize = [f"{g.get('what')} → {g.get('to')}" for g in policy.get("generalize", [])]
    keys_text = ("The keys are deleted, see 'Deleting the keys'." if goal == "anonymous"
                 else "The keys are kept, so whoever holds them can link the data back.")
    measures = "\n".join(f"  - {m}" for m in a.get("measures", []))

    parts = [f"""# Assessment of the anonymization

**Project:** {policy.get('project', '')}
**Made:** {date.today().isoformat()} with anonymize {a.get('version', core.tool_version())}, rules version {a.get('policy_version')}
**Goal:** {GOALS[goal]}

This file holds no personal data and can be kept as documentation. The method is
described in `references/method.md` in the skill.

## Suitability

**Recipients and what they know:** {assessment['recipients']}

**Can the data be responsibly anonymized?** {'Yes' if assessment['suitable'] else 'No'}. {assessment['rationale']}

**Decided by:** {assessment.get('decided_by') or '________'} **Date:** {assessment.get('decided_on') or '________'}

## Rules

**Population:** {policy.get('population', '')}

**The analysis needs:**
{_bullets(policy.get('analysis_needs', []))}

**Kept:**
{_bullets(policy.get('keep', []))}

**Generalized:**
{_bullets(generalize)}

**Removed:**
{_bullets(policy.get('remove', []))}

## What was done

- {docs}, anonymized with {models}.
- {core.count(a.get('changes', 0), 'change', 'changes')}: {core.category_text(a.get('by_category', {}))}. Actions: {actions}.
- First pass: {core.count(by_round.get('1', 0), 'change', 'changes')}. Re-read in a fresh context: {core.count(reread_changes, 'change', 'changes')}, recorded for {a.get('reread', 0)} of {docs}.
- Assessed residual risk per document: {risk}.
- Uncertain cases not decided: {a.get('needs_review', 0)}.
- Measures beyond the change lists:
{measures}

## Fixed check

{control}

## The three criteria

The criteria are from the EDPB draft guidelines on anonymisation (02/2026). Zero
risk is not required, but identification must not be reasonably likely.

- **Singling out: can one person be picked out?** The rules describe the
  population, and combinations of role, place, time and event are generalized by
  them. Each document is assessed on its own and read again in a fresh context.
- **Linkability: can the data be linked to other data about the same person?**
  Files and records have new IDs and names, and placeholders are numbered per
  document. {keys_text}
- **Inference: can new information about a person be deduced?** Special
  categories are removed or generalized by the rules ({core.count(health, 'change', 'changes')} in
  the health category). What the analysis needs is kept in generalized form.
"""]

    if goal == "anonymous":
        extra = "".join(f"- [ ] {key}\n" for key in assessment.get("keys", []))
        parts.append(f"""{DELETION}

The anonymized data is only anonymous for you, and for providers that process it
on your behalf, once everything that can link it back is deleted. Verbatim quotes
make the originals a key. Tick each item when it is done, then check with
`assess.py --verify-deletion`.

- [ ] The originals in `raw/`
- [ ] The change lists and the link to the original IDs in `changes/`
- [ ] The review material in `review/`, the allow list and the name list
- [ ] Session logs and caches in the AI tool used for the anonymization
- [ ] Copies at the provider used for the anonymization, deleted or deleted as the agreement says
{extra}
Status: not checked.
""")
    else:
        parts.append("""## Keys

The keys are kept. The anonymized data is therefore still personal data and must
only be processed by providers approved for it. The anonymization means less
personal data is processed, and less harm is done if something goes wrong.
""")

    parts.append("""## Approval

The assessment should be repeated within a year, and when recipients, purpose or
available technology change substantially.

**Approved by:** ____________________ **Date:** ____________
""")
    if open_points:
        parts.append("## Open points\n\n" + _bullets(open_points) + "\n")
    return "\n".join(parts), open_points


def verify_deletion(assessment: Path, paths: list[Path]) -> tuple[bool, list[str]]:
    text = assessment.read_text(encoding="utf-8")
    start = text.find(DELETION)
    if start < 0:
        return False, ["The assessment has no deletion checklist. The goal is reduced risk, and the keys are kept."]
    end = text.find("\n## ", start + len(DELETION))
    section = text[start:end if end >= 0 else len(text)]
    problems = [f"Not ticked: {line[6:]}" for line in section.splitlines() if line.startswith("- [ ]")]
    problems += [f"Still exists: {p.as_posix()}" for p in paths if p.exists()]
    if problems:
        return False, problems
    names = ", ".join(p.as_posix() for p in paths)
    status = f"Status: checked {date.today().isoformat()}. {names} do not exist, and every item is ticked."
    new_section = STATUS.sub(status, section) if STATUS.search(section) else section.rstrip("\n") + f"\n\n{status}\n"
    assessment.write_text(text.replace(section, new_section), encoding="utf-8")
    return True, [status]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the assessment, or check that the keys are deleted.")
    parser.add_argument("--policy", type=Path, default=Path("policy.json"))
    parser.add_argument("--raw", type=Path, default=Path("raw"))
    parser.add_argument("--changes", type=Path, default=Path("changes"))
    parser.add_argument("--out", type=Path, default=Path("out"))
    parser.add_argument("--review", type=Path, default=Path("review"))
    parser.add_argument("--allow", type=Path, help="The allow list for the residual check.")
    parser.add_argument("--names", type=Path, help="The name list for the residual check.")
    parser.add_argument("--output", type=Path, default=Path("assessment.md"))
    parser.add_argument("--force", action="store_true", help="Replace an existing assessment.")
    parser.add_argument("--verify-deletion", action="store_true", help="Check that the keys are deleted.")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.verify_deletion:
        if not args.output.is_file():
            print(f"Cannot find {args.output}.", file=sys.stderr)
            return 2
        paths = [args.raw, args.changes, args.review, args.allow or Path("allow.txt"), args.names or Path("names.txt")]
        ok, lines = verify_deletion(args.output, paths)
        print("\n".join(lines))
        return 0 if ok else 1

    try:
        if args.output.exists() and not args.force:
            raise AssessError(f"{args.output} exists. Use --force to make it again; ticked boxes are lost.")
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        problems = _check_policy(policy)
        if problems:
            raise AssessError(" ".join(problems) + " See references/policy.md.")
        manifest_path, manifest = _manifest(args.out)
        if args.changes.is_dir():
            lists = [p for p in args.changes.rglob("*.json") if p.name != core.ID_MAP]
            if any(p.stat().st_mtime > manifest_path.stat().st_mtime for p in lists):
                raise AssessError("Some change lists are newer than the package in out/. "
                                  "Run apply_changes.py --force first.")
        raw = args.raw if args.raw.is_dir() else None
        terms = check_residuals.known_terms(raw, args.names, policy if raw else None)
        allowed = check_residuals.load_allow(args.allow)
        hits = check_residuals.scan(args.out, terms, allowed)
    except (AssessError, OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2
    text, open_points = build(policy, manifest, hits, len(allowed))
    args.output.write_text(text, encoding="utf-8")
    print(f"The assessment is written to {args.output}.")
    if open_points:
        print("Open points before release:")
        print(_bullets(open_points))
        return 1
    if policy["goal"] == "anonymous":
        print("Next step: a human approves the assessment, deletes the keys and ticks the boxes. "
              "Then run assess.py --verify-deletion.")
    else:
        print("Next step: a human approves the assessment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
