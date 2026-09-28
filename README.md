<img src="assets/icon.svg" alt="Anonymizer icon" width="96" align="right">

# Anonymizer

Anonymizer is a skill for the AI tools Claude Code, Codex and OpenCode. It
removes personal data from free text, such as interviews, meeting notes and
open-ended survey answers, before analysis, whether by people or by other AI
tools. A language model at an approved provider does the anonymization under
rules for each project. Every change can be checked.

## The problem

Qualitative data is hard to share and hard to analyse with the best tools.
Personal data may only be processed by providers with a data processing agreement
and adequate data location, and many capable tools do not meet those terms.

Removing names does not solve the problem. In interviews, combinations give
people away: "the only lawyer in child welfare in a small municipality that
switched systems last year" contains no name, but points to one person. The
smaller and better known the population, the easier it is to recognize someone.
Doing this by hand over many interviews takes time and quickly becomes uneven.

## How it works

1. **The user confirms approved processing.** The skill asks for confirmation that
   the AI provider and the project folder are approved for the data. It does not
   enforce the choice itself.
2. **A human decides goal and suitability.** Should the data become anonymous, or
   only carry lower risk? Can it be responsibly anonymized without losing its purpose?
3. **Rules for the project are written before the data is read.** They say what
   the analysis needs, what may stay, what is generalized and what is always
   removed, and what happens to each file.
4. **The model writes a change list for each document**, not rewritten text. Each
   change has the original text, the action, the replacement, a category and a
   reason. A script applies the changes and builds an anonymized package with the
   same file types, new IDs and new file names.
5. **A script searches for what is left:** known names, email, phone numbers,
   Norwegian national identity numbers, other ID numbers and links.
6. **Each document is read again in a fresh context**, and anything that can still
   identify someone is added to the change list.
7. **A human decides the uncertain cases** the model flagged.
8. **A script writes the assessment** (`assessment.md`): goal, suitability, rules,
   what was done, the check and how the legal criteria are met.
9. **When the goal is anonymous data, the keys are deleted**, and the deletion is checked.

Why the routine is set up like this, and what it cannot promise, is in the
[method description](skills/anonymize/references/method.md).

## Two uses

- **Anonymous data for tools with weaker guarantees.** Everything that can link
  the data back must be deleted before it is used: the originals, the change
  lists, the link between old and new IDs, recruitment lists and data in the
  collection tool. The reason is that your means count when a provider processes
  the data on your behalf, and verbatim quotes make the originals a key.
- **Lower risk at approved providers.** The keys are kept, and the data is still
  personal data. The anonymization means less personal data is processed, and
  less harm is done if something goes wrong.

## Provider and model

The anonymization must happen at a provider allowed to process the data:

- **a local model**, so the data does not leave the machine or the organization, or
- **a provider with adequate guarantees:** a data processing agreement, adequate
  data location and no training on the data.

Use the most capable model that is approved. Research shows that large open
models can anonymize nearly as well as the best commercial ones, but that was
measured on English text. Try it on a few documents first.

## Formats

| Files in `raw/` | What is anonymized | The anonymized file |
|---|---|---|
| `.txt`, `.md` | each line | same file type, same lines |
| `.docx` | each paragraph, also in tables and text boxes | a new Word document with the text only; formatting, comments, headers, footers, footnotes, images and metadata are not carried over |
| `.csv` | the columns the rules mark as free text | the kept columns; rows shuffled |
| `.jsonl` | the fields the rules name, for example `messages[].content` | only the named fields; new record IDs |

File rules in `policy.json` say what happens to each file: anonymized, copied
unchanged or left out. A tool that exports data can describe its own package in
`anonymize.json`, and the skill uses that as a draft for the rules. See
[files and file rules](skills/anonymize/references/formats.md). Other file types,
such as PDF and .doc, must be saved in another format first.

## Get started

You need git, Python 3.10 or newer and Claude Code, Codex or OpenCode with a
provider approved for the project data.

**1. Get the repository:**

```bash
git clone https://github.com/emilmsh/anonymizer.git
```

**2. Install once for your tool:**

```bash
python anonymizer/install.py --tool claude
```

Use `--tool codex`, `--tool opencode` or `--tool all` for the other tools. The
skill goes into your personal skills folder. Existing files are not overwritten
without `--update`; local edits are protected. Add `--mode auto` to install new
versions automatically. Start a new session to load the skill.

| Tool | Installed skill folder (default) |
| --- | --- |
| Claude Code | `~/.claude/skills/anonymize/` |
| Codex | `~/.agents/skills/anonymize/` |
| OpenCode | `~/.config/opencode/skills/anonymize/` |

**3. Make a project folder outside the repository**, and put the documents in `raw/`.

**4. Start the AI tool from the project folder** and write, for example:

> Anonymize the interviews in raw/.

The skill checks for updates, asks you to confirm an approved provider and
project folder, and makes the rules for the project with you before it reads any
data. It talks to you in your language.

**5. Clean up afterwards.** AI tools can store sessions and tool output outside
the project folder. Such copies are keys too, and are on the checklist in the
assessment.

## When is the data anonymous?

The skill makes and checks the proposals. Whether the result is anonymous is
decided by whoever is responsible for the processing. Before the data is used by a
provider without a data processing agreement, this should be in place:

- The goal is anonymous data, and the data is judged suitable.
- Every document has been read again in a fresh context.
- The residual check gives no hits, or every hit is assessed and justified in an
  allow list.
- No uncertain cases are open.
- The assessment is approved with name and date.
- The keys are deleted, and the deletion is checked with `assess.py --verify-deletion`.
- The method is assessed by the data protection officer for this kind of data.

The anonymization itself is processing of personal data. The information to the
participants should say that the data is anonymized with AI, when the originals
are deleted, and that the anonymized data may be analysed, also with AI tools.

## Example

[`examples/grant-scheme/`](examples/grant-scheme/) is a fictional project with an
interview as a text file, meeting notes in Markdown, a survey in CSV and chat
interviews in JSON Lines with a package description, together with the rules, the
change lists, the anonymized package and the assessment.

## Updates

The skill checks for new versions every time it starts, at most once a day. Only
published versions (`vX.Y.Z`) count.

| Setting | What happens |
|---|---|
| `notify` (default) | The skill reports a newer version. Nothing changes. |
| `auto` | A newer version is installed, as long as the installed files are not edited locally. The previous version goes to `anonymize-backups/` next to the skills folder. |
| `off` | No check at start. |

Run these with the path to the installed skill (Claude Code example):

```bash
python ~/.claude/skills/anonymize/scripts/update.py --check
python ~/.claude/skills/anonymize/scripts/update.py --install
python ~/.claude/skills/anonymize/scripts/update.py --mode auto
```

The update only fetches code from the repository with git and sends no data.
Without a network, the skill carries on as before. Start a new session in the AI
tool after an update.

## Contents

```text
install.py                        installs the skill for the chosen tools
skills/anonymize/                 the skill
  SKILL.md                        the workflow for the agent
  references/method.md            the rationale for the routine and the law
  references/policy.md            how goal, suitability and rules are written
  references/formats.md           file types, file rules and package descriptions
  references/change-list.md       how change lists are written
  schemas/                        JSON schemas for rules, change lists and package descriptions
  scripts/segments.py             shows the documents with numbered segments
  scripts/apply_changes.py        applies the change lists and builds the anonymized package
  scripts/check_residuals.py      fixed check after anonymization
  scripts/assess.py               writes the assessment and checks the deletion
  scripts/update.py               checks for and installs new versions
  scripts/core.py, formats.py     shared code, and the file types
  templates/policy.example.json   example rules
examples/grant-scheme/            fictional example, before and after
assets/                           the app icon as SVG and PNG
tests/                            tests for the scripts
```

The scripts use the Python standard library only. Run the tests with
`python -m unittest discover -s tests`.

## License and citation

Anonymizer is developed by [Emil Mathias Strøm Halseth](https://emilmsh.github.io)
and licensed under [Apache-2.0](LICENSE). Anyone who redistributes the code, also
in modified form, must include [NOTICE](NOTICE).

If you use Anonymizer in research, reports or analysis, please cite it. GitHub
shows a ready-made reference under "Cite this repository", taken from
[CITATION.cff](CITATION.cff):

> Halseth, E. M. S. (2026). *Anonymizer: AI-assisted anonymization of free text
> with personal data* (version 0.5.0) [Software]. https://github.com/emilmsh/anonymizer
