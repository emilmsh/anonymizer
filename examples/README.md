# Example: evaluation of a grant scheme

Everything in the example is fictional: people, municipalities, newspaper,
consultancy, case management system and events.

`grant-scheme/` is a project folder as it looks after the anonymization, before
the keys are deleted:

| Folder or file | What it is |
|---|---|
| `policy.json` | the rules, with goal, suitability and file rules |
| `raw/` | the originals: an interview as a text file, meeting notes in Markdown, a survey in CSV, and chat interviews in JSON Lines with an HTML overview |
| `raw/anonymize.json` | a package description, as the tool that exported the chat interviews could write it; its file rules are copied into `policy.json` |
| `changes/` | the change lists, one per document, and the link to the new IDs (`id-map.json`) |
| `out/` | the anonymized package |
| `assessment.md` | the assessment, made by `assess.py` |

The change lists are written by hand to show the format. In a real project, the
AI model makes them. Changes with `"round": 2` are the ones found in the re-read.

## What the file rules do

- `survey.csv`: the two free text columns are anonymized, the role is kept, and
  respondent ID, email, municipality and time are removed. Emails and
  municipalities are also names that the residual check searches the output for.
- `chats/interviews.jsonl`: the messages and the summary are anonymized, the
  speaker is kept, the start time is shortened to the date, and the participant's
  name is used by the residual check. The test interview is skipped. The invite
  link name and the time of each message are removed, because the rule does not
  name them.
- `chats/overview.html`: left out, because it only repeats the interviews with
  the participants' names.

## Before and after

| Original | Anonymized |
|---|---|
| I am the only lawyer in child welfare in Fjordvik municipality. There are four of us in the service, and I have been here since 1998. | I am [an employee in a municipal service] in [a small municipality in Western Norway]. There are [a few] of us in the service, and I have been here [for over 20 years]. |
| My manager Per Hansen has been supportive, also when I was on sick leave with burnout for three months last year. | My manager [PERSON_3] has been supportive, also when I was [removed: health information]. |
| We used external consultants from Fjordråd AS, and it cost us NOK 350,000. | We used external consultants from [ORGANIZATION_1], and it cost us [a six-figure sum]. |
| I am Mari, the grants coordinator in Nordvik. I have done this alone since my colleague retired. | I am [PERSON_1], [the person responsible for grants] in [a small municipality in Northern Norway]. I have done this alone [for some time]. |

What the analysis needs is left: type of role, size of municipality, region, the
year of the grant and the name of the system.

## Build the example again

From `examples/grant-scheme/`:

```bash
python ../../skills/anonymize/scripts/apply_changes.py --policy policy.json --force
python ../../skills/anonymize/scripts/check_residuals.py --target out/ --original raw/ --policy policy.json
python ../../skills/anonymize/scripts/assess.py --force
```

`tests/test_examples.py` checks that the documents in `out/` stay the same.
