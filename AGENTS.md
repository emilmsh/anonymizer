# Rules for AI agents in this repository

- **No real data in the repository.** Raw data, change lists, anonymized packages,
  test sets and reports from runs belong in a project folder outside the
  repository. `.gitignore` stops the most common folder names, but is no guarantee.
- Test data in `tests/` and the example in `examples/` must be fictional.
- The skill in `skills/anonymize/` is the unit that `install.py` installs. Keep
  everything the skill needs (scripts, schemas, templates, references) inside it.
- The skill is general. Do not name or describe particular products or export
  formats; a tool can describe its own package in `anonymize.json`.
- The scripts use the Python standard library only (3.10+). Run the tests with
  `python -m unittest discover -s tests` after changes.
- English in code, comments, documentation and messages. The skill talks to users
  in their own language.
- If you change the format of change lists, policies or package descriptions,
  update both the schema in `skills/anonymize/schemas/` and the description in
  `skills/anonymize/references/`.
- If you change how documents are built, build the example again (see
  `examples/README.md`), so `tests/test_examples.py` still holds.
- New version: update `skills/anonymize/VERSION` and `CITATION.cff`, run the
  tests, commit and make a version tag `vX.Y.Z` with the same version. Installed
  copies only update from tags.
