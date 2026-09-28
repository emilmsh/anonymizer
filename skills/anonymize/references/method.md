# Method

This is the rationale for the routine: what the law requires, why the steps are
as they are, and what the routine cannot promise. It is not legal advice. Assess
the method with your data protection officer before using it on a new kind of
data.

## What is anonymous data?

The General Data Protection Regulation (GDPR) does not apply to anonymous
information (recital 26). Information is anonymous when nobody can identify the
person by means reasonably likely to be used. All objective factors count, such
as the cost and time of identification, and the technology available now and
coming.

- **Not zero risk.** The Court of Justice of the EU has held that the risk is
  insignificant when identification needs a disproportionate effort, or is
  prohibited by law (Breyer, C-582/14, 2016). The UK Information Commissioner's
  Office (ICO) says so explicitly: the risk does not have to be zero.
- **A relative assessment.** The same data can be anonymous for one recipient and
  personal data for another, depending on the means each has (EDPS v SRB,
  C-413/23 P, 2025). The EDPB draft guidelines on anonymisation (02/2026, open for
  consultation until 30 October 2026) build on this.
- **Processors.** When a provider processes the data on your behalf, your means
  count, according to the draft. As long as you hold the originals, the anonymized
  data is personal data for you, and for the provider.
- **Three criteria.** The draft says data is anonymous when
  1. no person can be picked out (singling out),
  2. the data cannot be linked to other data about the same person (linkability), and
  3. no new information about a person can be deduced (inference).
  If not all three are met, the risk must be assessed further and shown to be
  insignificant.
- **Contracts are not enough on their own.** A ban on re-identification in a
  contract can come in addition to technical measures, not instead of them.
- **Documentation and new assessments.** The anonymization and the checks must be
  documented. The assessment must be made again when recipients, purpose or
  technology change, because the risk of re-identification grows over time.

### What it means for the routine

- **Two goals.** With the goal *anonymous data*, everything that can link the data
  back must be deleted before it is used by providers without a data processing
  agreement: the originals, the change lists, the link between old and new IDs,
  the review material, recruitment lists, data in the collection tool and copies
  in the AI tool's sessions. Verbatim quotes make the originals a key, because
  anyone with the originals can find the quote again. With the goal *reduced
  risk*, the keys are kept, and the data is still processed as personal data at
  approved providers. That has value too: less personal data is processed, and
  less harm is done if something goes wrong.
- **The anonymization itself is processing of personal data.** It needs a legal
  basis, a provider approved for the data, and information to the participants.
  The information letter should say that the interviews are anonymized with AI at
  the approved provider, that the originals are deleted by a given date, and that
  the anonymized data may be analysed, also with AI tools.

## The principles of the routine

1. **A human first decides whether the data is suitable.** Some data cannot be
   anonymized without losing its purpose, for example when the population is very
   small or the analysis needs exactly the identifying details. This is an
   assessment of purpose and population, not of the text, and it is made before
   the data is read.
2. **Local knowledge goes into the rules.** Whoever knows the field knows which
   roles are rare, which events are known and which places are small. It is
   written in `policy.json` before the anonymization starts, and applies equally
   to all documents.
3. **AI does the review, with the best possible conditions.** People are not
   necessarily better than a good language model at finding identifiers in a lot
   of text, and they tire and become uneven. The model gets the rules, the
   population and the recipients, one document at a time and every segment,
   including the interviewer's. Use the most capable model approved for the data.
4. **Change list, not rewriting.** The model says which verbatim excerpts to
   replace, with a reason. A script makes the changes, the same way every time.
   Everything can be checked, and the quotes are verbatim except for what was changed.
5. **Re-read in a fresh context.** The document is read again, anonymized, without
   the first attempt in memory. Research on AI anonymization shows that another
   round catches much of what the first one missed (Staab et al., 2025).
6. **A fixed check of direct identifiers.** A script searches for names from the
   originals, file names and name fields, contact details, Norwegian national
   identity numbers, other ID numbers and links.
7. **Technical measures against linking.** Files and records get new IDs and
   names. Placeholders are numbered per document, so the same person cannot be
   followed across documents. Rows in CSV files are shuffled, and records in JSON
   Lines files are sorted by their new ID. Only the fields named in the file rules
   are kept. Word documents are rebuilt without metadata, comments and hidden
   parts. Dates can be shortened to the day.
8. **A human decides the uncertain cases and approves the assessment.** The model
   flags what it is unsure about. It never declares the data anonymous itself.
9. **The keys are deleted when the goal is anonymous data**, and the deletion is
   checked and recorded in the assessment.

How the steps meet the three criteria:

| Criterion | What the routine does |
|---|---|
| Singling out | Rules for the population, generalization of combinations, the re-read, the suitability decision |
| Linkability | New IDs and names, placeholders per document, shuffled rows and sorted records, only named fields kept, new Word files, deleting the keys |
| Inference | Special categories such as health removed or generalized, publicly known events removed |

## What the routine cannot promise

- **No method gives zero risk.** Even the best AI anonymizers in Staab et al.
  left a good share of personal attributes inferable after five rounds.
- **Verbatim quotes keep ways of speaking, stories and details** that someone who
  knows the person well may recognize.
- **The quality depends on the model.** Staab et al. found that an open model
  (Llama 3.1 70B) was nearly as good as GPT-4, and that smaller local models also
  beat common commercial anonymization tools. Kim et al. (2025) show that small
  models can be trained to nearly the same level. This was measured on English
  online comments, not interviews in other languages. Try the routine on a few
  documents before a large project.
- **The residual check only finds what it knows about**, such as known names and
  fixed patterns.
- **AI agents with web search can link weak clues** (Li et al., 2026). So keep
  publicly known details out: events covered by the media, figures from public
  accounts, rare combinations of place and role.

## Choice of provider and model

- **A local model.** The data does not leave the machine or the organization. Use
  the largest model that runs.
- **A provider with adequate guarantees.** A data processing agreement, adequate
  data location and no training on the data. Which providers are approved is for
  the organization to decide.
- When the goal is anonymous data and the keys are deleted, the anonymized
  material may be used in tools with weaker guarantees. Until then, it is personal
  data.

## Sources

- General Data Protection Regulation (EU) 2016/679, Article 4(1) and recital 26.
- Court of Justice of the EU, C-582/14 Breyer, 19 October 2016.
- Court of Justice of the EU, C-413/23 P EDPS v SRB, 4 September 2025.
- EDPB, Guidelines 02/2026 on Anonymisation, version 1.0 for public consultation,
  adopted 7 July 2026.
- ICO, Anonymisation guidance, 2025.
- Staab, R. et al. (2025). Language Models are Advanced Anonymizers. ICLR 2025.
  arXiv:2402.13846.
- Kim, K., Jeon, H. and Shin, J. (2025). Self-Refining Language Model Anonymizers
  via Adversarial Distillation. NeurIPS 2025. arXiv:2506.01420.
- Li et al. (2026). LLM Anonymization Against Agentic Re-Identification.
  arXiv:2605.30848.
