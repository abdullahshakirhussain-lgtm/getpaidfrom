# Translations

English is the source and the reference. Other languages live under `/<lang>/` (es, fr, pt, ar so far;
ur, bn, id, vi are planned and skipped by the build until their files exist and are complete).

## What is translated

- **Interface text**: `data/i18n/ui.<lang>.json`, same keys as `ui.en.json`, `{placeholders}` unchanged.
- **Our own wording** (short answers, warnings, service reasons, verdicts, legal ways): `data/i18n/strings.<lang>.tsv`,
  one `<id>\t<translation>` per line. The id is a hash of the English line, so when the English changes the old
  translation stops matching and the line shows as missing. A stale translation can never be shown.
- **Country names**: Unicode CLDR 49 (`data/i18n/cldr_<lang>_territories.json`), never hand-written.
- **Search words**: `data/i18n/search.<lang>.json` (extra stop words and topic words in that language).

The long research text ("Details and sources") and the source titles stay in English on every page, marked
`lang="en"` and labelled "(in English)".

## A language only ships when it is complete

`scripts/build_site.py` leaves a language out if any line is untranslated (it prints `skipped <lang>`).
If an English edit leaves a live language incomplete, that language's pages disappear on the next deploy
until the missing lines are translated, so translate before or with the English change.

    python scripts/i18n_todo.py es                 # writes data/i18n/todo.es.tsv: what's missing
    python scripts/i18n_put.py es batch.txt        # add "N: translation" lines (N = line in source.tsv)
    python scripts/i18n_check.py es                # must say 0 problems
    python scripts/build_site.py --langs en,es --draft   # local preview of an incomplete language

## What the checker verifies (scripts/i18n_check.py, run in CI by tests/test_i18n.py)

- every number survives, read with the language's own separators (24,000 → 24.000 / 24 000), billions compared in millions
- every currency code, acronym and service name survives (a short glossary allows accepted local forms: VAT → IVA/TVA, EU → UE…)
- if the English says no / not / without, the translation contains a negation
- interface placeholders match exactly
- findings a reviewer has accepted go in `data/i18n/allow.<lang>.txt` as `<id> <check>`

It cannot judge grammar, tone or legal nuance. Translations were written by Claude (machine-assisted) on
2026-10-28/29; a native-speaker review of each language is recommended before promoting them.

## Choices made

- Spanish: neutral Latin American / Spanish, informal "tú". Portuguese: Brazilian, "você".
- French: "vous"; country names after a colon ("Sénégal : se faire payer") to avoid article rules.
- Arabic: Modern Standard Arabic, Western digits, service names in Latin script; dates are wrapped in
  left-to-right isolates so they don't flip.
