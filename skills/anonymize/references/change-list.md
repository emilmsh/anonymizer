# The change list (`changes/<document ID>.json`)

One file per document with every change to make. The format is in
`schemas/changes.schema.json`. The list holds the original excerpts and is
therefore personal data. It stays in the project folder.

## Document ID and file name

The document ID is the path under `raw/`, for example `interview-01.docx` or
`round-2/interview-07.txt`. For JSON Lines, every record is a document, and the
ID is the path plus `/` and the record ID, for example
`chats/interviews.jsonl/a1b2c3`. The change list has the same name with `.json`
added: `changes/interview-01.docx.json`, `changes/chats/interviews.jsonl/a1b2c3.json`.

`segments.py --list` shows the document IDs and where the lists go.

## Address

Each change applies to one segment, given by `position` and `field`.
`segments.py <document ID>` shows the segments with the address in front.

| Format | `position` | `field` |
|---|---|---|
| .txt and .md | the line number, from 1 | `content` |
| .docx | the paragraph number, from 1 | `content` |
| .csv | the row number, from 1, without the header row | the column name |
| .jsonl | `null` | the path to the value, such as `messages[3].content` |

A change cannot span two segments. If a detail runs over two lines, make one
change for each.

## Rules

- **Verbatim:** `original` must be found exactly like this in the segment, with
  the same upper and lower case and punctuation. With several occurrences in the
  same segment, make one change per occurrence, with `occurrence` 1, 2, 3 and so on.
- **Action:**
  - `replace`: swap for a placeholder, for example `[PERSON_1]`.
  - `generalize`: swap for a more general description, for example
    `[small municipality in Western Norway]`.
  - `remove`: remove and mark, for example `[removed: identifying detail]`.
- **Placeholders** are numbered per document (per row in CSV files, per record in
  JSON Lines files). The same person in the same document gets the same
  placeholder, also in the interviewer's questions and in summaries. Write them in
  the language of the document.
- **Reason:** `reason` says briefly why the text identifies someone. Do not put
  more personal data in the reason than is in `original`.
- **Passes:** `passes` is how many times the document has been gone through: 1
  after the first pass, 2 after the re-read. Changes found in the re-read get
  `round: 2`. Without `round`, a change counts to the first pass.
- **The whole document:** `residual_risk` is the risk after the changes, given the
  population and recipients in `policy.json`. `needs_review` holds uncertain cases
  for a human to decide. They are taken out of the list once decided.

## Example

```json
{
  "document_id": "interview-01.txt",
  "policy_version": "1",
  "model": "the approved model",
  "passes": 2,
  "changes": [
    {
      "position": 7,
      "field": "content",
      "original": "the only lawyer in child welfare in Fjordvik",
      "occurrence": 1,
      "action": "generalize",
      "replacement": "[employee in a municipal service] in [small municipality in Western Norway]",
      "category": "role",
      "reason": "Role and municipality together point to one person."
    },
    {
      "position": 8,
      "field": "content",
      "original": "Fjordvik",
      "occurrence": 1,
      "action": "generalize",
      "replacement": "[small municipality in Western Norway]",
      "category": "place",
      "reason": "The interviewer repeats the municipality."
    },
    {
      "position": 7,
      "field": "content",
      "original": "since 1998",
      "occurrence": 1,
      "action": "generalize",
      "replacement": "[for over 20 years]",
      "category": "date",
      "reason": "Length of service together with the role can point to the person.",
      "round": 2
    }
  ],
  "residual_risk": "low",
  "needs_review": []
}
```

More examples, with text, Markdown, CSV and JSON Lines, are in `examples/` in the
repository.
