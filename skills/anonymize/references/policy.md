# Rules for a project (`policy.json`)

The rules say what the goal is, whether the data is suitable, what happens to
each file, and what to keep, generalize and remove in one project. They are
written before the anonymization starts, approved by whoever owns the project,
and apply equally to every document. The format is in
`schemas/policy.schema.json`, and `templates/policy.example.json` is a filled-in
example. The file must not hold personal data about the people interviewed or
mentioned.

## First: goal and suitability

These are the user's decisions. Ask the questions and write the answers in.

1. **Goal** (`goal`).
   - `anonymous`: the anonymized data may be used by providers without a data
     processing agreement. That requires deleting all the keys at the end, because
     the data is otherwise personal data for the user and for providers that
     process it on the user's behalf. Verbatim quotes make the originals a key.
   - `risk_reduction`: the keys are kept, and the data is still only used by
     approved providers. The anonymization means less personal data is processed.
2. **Recipients** (`assessment.recipients`). Who will use the anonymized data, and
   what do they know? Do they have the list of respondents? Do they know the field?
3. **Suitability** (`assessment.suitable` and `rationale`). Can the data be
   responsibly anonymized without losing its purpose? It works poorly when:
   - the population is so small or well known that almost any detail points to someone,
   - the analysis needs exactly the identifying details, for example a case study
     of one named organization,
   - the material is about events known in the field or covered by the media,
   - the keys cannot be deleted, and the goal is anonymous data.
   If the answer is no, the anonymization stops. The alternative is to do the
   analysis at an approved provider.
4. **Keys outside the project folder** (`assessment.keys`). Everything that can
   link the data back: the interviews in the collection tool, recruitment lists,
   recordings, backups and emails with attachments. `raw/`, `changes/` and
   `review/` come in addition.
5. Who decided, and when (`decided_by`, `decided_on`). A role is enough.

## Then: the files

**File rules** (`files`) say what happens to each file in `raw/`: anonymized,
copied unchanged or left out, and for CSV and JSON Lines which columns and fields
are free text. See `references/formats.md`. If `raw/anonymize.json` exists, the
tool that made the export has described its package; use its file rules as the
draft, and show them to the user.

## Then: the rules

1. **Describe the population** (`population`). Who are the respondents, how many
   are they, and how well do they and the readers know each other? This decides
   how strictly combinations must be assessed.
2. **Write what the analysis needs** (`analysis_needs`). This is what must
   survive the anonymization, often in generalized form. Ask whoever does the
   analysis.
3. **Write what may stay** (`keep`). For example the name of the scheme being
   evaluated, case management systems or tools that the study is about.
4. **Write what is generalized, and to what** (`generalize`). Names of
   municipalities can become size and region, job titles can become role
   categories, and dates can become years.
5. **Write what is always removed** (`remove`). Names of people, contact details,
   ID numbers, health information and events known in the field.
6. **Choose placeholders** (`placeholders`). `n` is numbered per document (per
   row in CSV files, per record in JSON Lines files). Write placeholders in the
   language of the documents.

The user knows the field; the model knows the text. So put what the user knows
about the field into the rules: which roles are rare, which events are known,
which places are small.

## Assessments

- Indirect identifiers identify more often than names in small populations.
  Assess role, place, time and event together, not one by one.
- What cannot be anonymized without losing the meaning is removed with a marker,
  for example "[removed: identifying detail]".
- If the rules change along the way, increase `policy_version` and make the
  change lists again for the documents handled under the old version.
