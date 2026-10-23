# Alfa Pulse — bank knowledge search (first module)

Python >= 3.10, standard library only. This module searches only records in `human_checked_excerpts` from the team's `bank_evidence_index.json`. A document title/topic match is never treated as proof of a bank opinion.

## Run a search

```bash
python bank_knowledge.py "ключевая ставка" --category monetary_policy --company-id U_1595 --source-id NEWS_001
```

The program prints one JSON handoff record using the team's `P1.1` structure. If no reviewed excerpt matches, it returns an empty `retrieved_bank_excerpts`, a candidate query, and `igor_handoff_status: requires_bank_document_review`.

## Run tests

From this directory:

```bash
python -m unittest discover -s tests -v
```

## Current limitations

- This is deterministic lexical search, not semantic/vector search.
- Only the curated, human-reviewed excerpts are searchable (currently two in the supplied index).
- It does not OCR PDFs, fetch external documents, or generate interpretations.
- Confirm schema compatibility with the current Alfa Pulse repository before integration.
