# Assessment of the anonymization

**Project:** Evaluation of a grant scheme for municipalities (fictional example)
**Made:** 2026-09-28 with anonymize 0.5.1, rules version 1
**Goal:** Anonymous data. The anonymized data may be used by providers without a data processing agreement once the keys are deleted.

This file holds no personal data and can be kept as documentation. The method is
described in `references/method.md` in the skill.

## Suitability

**Recipients and what they know:** The analysts in the project and the AI tools they use, including providers without a data processing agreement. The analysts do not have the recruitment list. The client only gets the report, but knows the list of grant recipients.

**Can the data be responsibly anonymized?** Yes. The analysis needs size of municipality, region and type of role, not which municipality or person. With about 80 possible respondents across many municipalities, this can be generalized without losing the purpose.

**Decided by:** Project manager **Date:** 2026-09-27

## Rules

**Population:** About 80 case workers and managers in municipalities that received a grant. Many know each other from networks, and the client has the list of grant recipients.

**The analysis needs:**
- Size of municipality (small, medium, large)
- Region
- Type of role (case worker, manager, finance)
- The year the municipality received the grant

**Kept:**
- The name of the grant scheme and the directorate that runs it
- Names of case management systems and digital tools
- General descriptions of tasks

**Generalized:**
- Names of municipalities and places → Size of municipality and region, for example [small municipality in Western Norway]
- Job titles → Role category, for example [manager]
- Exact dates → Year or half-year
- Numbers of employees, inhabitants or amounts that point to one municipality → Order of magnitude

**Removed:**
- Names of people, including colleagues, managers and politicians
- Contact details and ID numbers
- Health information and other special categories about identifiable people
- Events covered by the media or known in the field that point to a municipality or person

## What was done

- 5 documents, anonymized with example, written by hand.
- 33 changes: person 7, other 6, role 6, date 4, place 4, event 3, contact details 1, health 1, organization 1. Actions: generalized 20, replaced 8, removed 5.
- First pass: 28 changes. Re-read in a fresh context: 5 changes, recorded for 5 of 5 documents.
- Assessed residual risk per document: low 5.
- Uncertain cases not decided: 0.
- Measures beyond the change lists:
  - The files have new names, so file and folder names cannot point back to the people.
  - Columns removed from CSV files: email, municipality, respondent_id, submitted.
  - Rows in CSV files are shuffled, so the order cannot be linked to the original.
  - Only the fields named in the file rules are kept in JSON Lines files. Records get new IDs and are sorted by them.
  - Dates in JSON Lines files are shortened to the date.
  - 1 record is left out by 'skip' in the file rules.
  - 1 file is left out, as the file rules say.

## Fixed check

The residual check found no known names, contact details, ID numbers or links.

## The three criteria

The criteria are from the EDPB draft guidelines on anonymisation (02/2026). Zero
risk is not required, but identification must not be reasonably likely.

- **Singling out: can one person be picked out?** The rules describe the
  population, and combinations of role, place, time and event are generalized by
  them. Each document is assessed on its own and read again in a fresh context.
- **Linkability: can the data be linked to other data about the same person?**
  Files and records have new IDs and names, and placeholders are numbered per
  document. The keys are deleted, see 'Deleting the keys'.
- **Inference: can new information about a person be deduced?** Special
  categories are removed or generalized by the rules (1 change in
  the health category). What the analysis needs is kept in generalized form.

## Deleting the keys

The anonymized data is only anonymous for you, and for providers that process it
on your behalf, once everything that can link it back is deleted. Verbatim quotes
make the originals a key. Tick each item when it is done, then check with
`assess.py --verify-deletion`.

- [ ] The originals in `raw/`
- [ ] The change lists and the link to the original IDs in `changes/`
- [ ] The review material in `review/`, the allow list and the name list
- [ ] Session logs and caches in the AI tool used for the anonymization
- [ ] Copies at the provider used for the anonymization, deleted or deleted as the agreement says
- [ ] The interviews and survey answers in the collection tools
- [ ] The recruitment list with names, municipalities and contact details
- [ ] Backups of the project folder

Status: not checked.

## Approval

The assessment should be repeated within a year, and when recipients, purpose or
available technology change substantially.

**Approved by:** ____________________ **Date:** ____________
