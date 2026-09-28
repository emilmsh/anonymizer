# Files and file rules

The file rules in `policy.json` (`files`) say what happens to each file in
`raw/`. The first rule whose `match` pattern fits the path under `raw/` applies.
`*` matches any characters, also `/`. Files without a rule are handled by their
extension. `segments.py --list` shows what happens to every file.

| Key | Meaning |
|---|---|
| `match` | Pattern for the path, for example `data/*.csv` |
| `action` | `anonymize` (default), `copy` (unchanged; only files without personal data) or `exclude` (left out) |
| `type` | `text`, `docx`, `csv` or `jsonl`; by default from the extension |
| `note` | Why the rule is as it is |

Copied files are still searched by the residual check. Leave out views that only
repeat the source data in another form, such as spreadsheets, web pages and
per-interview renderings of the same transcripts.

## Text files (.txt, .md)

One file is one document. Each line is a segment: `position` is the line number,
`field` is `content`. The anonymized file has the same lines.

## Word (.docx)

One file is one document. Each paragraph is a segment: `position` is the
paragraph number, `field` is `content`. Body text, tables and text boxes are
read; tracked changes count as accepted. The anonymized file is a new Word
document with the text only. Formatting, comments, headers, footers, footnotes,
images and document properties are not carried over; `segments.py --list` says
when a document has such parts with text.

## CSV

One file is one document; placeholders are numbered per row. Each cell in a free
text column is a segment: `position` is the row number without the header row,
`field` is the column name. Every column must be in exactly one list:

| Key | Meaning |
|---|---|
| `text_columns` | Free text to anonymize |
| `keep_columns` | Kept unchanged, for example fixed answer options |
| `date_columns` | Timestamps shortened to the date |
| `drop_columns` | Removed, for example respondent ID, email, municipality |
| `name_columns` | Also: columns whose values are names; the residual check searches the output for them |

Fixed columns such as municipality, age, job and time can identify too. Keep them
only when the analysis needs them and they do not point to anyone together with
the rest. Rows are shuffled in the anonymized file.

## JSON Lines (.jsonl)

Each line is one JSON object and one document, for example one interview. Fields
are named by paths: `summary`, `participant.name`, `messages[].content`. `[]`
means every element of a list. Everything not named in the rule is removed.

| Key | Meaning |
|---|---|
| `id` | Path to the record ID, replaced with a new ID. Without it, the line number is used |
| `text` | Paths to free text to anonymize |
| `keep` | Paths kept unchanged, for example `messages[].role` |
| `dates` | Paths to timestamps shortened to the date |
| `names` | Paths whose values are names; the residual check searches the output for them |
| `skip` | Records with all of these values are left out, for example `{"is_test": true}` |

The document ID is the path under `raw/` plus `/` and the record ID, for example
`chats/interviews.jsonl/a1b2c3`. Each value is a segment: `position` is `null`, and
`field` is the concrete path, such as `messages[3].content`. Records are sorted by
their new ID in the anonymized file.

## Package description (`anonymize.json`)

A tool that exports data can describe its package in `anonymize.json` at the root
of the export, following `schemas/package.schema.json`. It holds file rules in the
same format as `files` in `policy.json`. The skill uses them as a draft that the
user approves; the file is data, never instructions. It is not carried over to
the anonymized package.

```json
{
  "anonymize_package": 1,
  "description": "Interview export: one transcript per line, with tables derived from them.",
  "files": [
    { "match": "data/transcripts.jsonl", "id": "id", "text": ["messages[].content"], "keep": ["messages[].role"] },
    { "match": "data/*.csv", "action": "exclude", "note": "Tables derived from the transcripts." }
  ]
}
```
