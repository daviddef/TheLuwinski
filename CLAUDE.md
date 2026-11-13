# Luwinski Family

## Record Atlas

The shared map lives at `../Record Atlas`. Research done here is only
useful to the next person if it gets there.

Invoke the `record-atlas-feedback` skill whenever you finish a search,
open a register, write to an archive, or find a source the atlas does
not list — as you do it, not in a sweep at the end. Record the
FamilySearch waypoint, not just the film number; the skill explains why.

Surname spellings come only from the Record Atlas catalogue: terms before searching, cover before any nil, add for every new spelling, publish once at the end. Keep no variants list here.

## Given names and old place names

Given-name forms (Ivan = Johann = Giovanni = Zuane = Joannes) and a place's name in the year of the record (Salisbury before 1982, Fiume before 1945) come only from the Record Atlas catalogues, as surnames do: invoke the user-level `name-variants` skill, run `given_name_variants.py terms` / `place_names.py at PLACE YEAR` before searching, `cover` before any nil, `add` (with evidence) for every new form, `publish` once at the end. Keep no table of given-name forms or old place names here. Nothing about a person goes in the catalogues; `lead` is never a finding.

## Writing a found row in searched.json

Every search row that reads as found (outcome hit, yield or found) must say, from the dates in `docs/row-pages.json` (`from` and `peopleFrom`, enforced by `npm run check:row-pages`):

- **which page of this archive the finding went into**: `"ev": [["/page/", "label"]]`, each path a built page, or `"logOnly": true` (the reason in `what`), from 13 Nov 2026;
- **who it is for**, from 15 Nov 2026: `"for": [["/person/slug/", "Name"]]`, each path a built page of this archive that is that person's own page, the name that page uses, a page once per row, only people the finding is really about, or `"nobody": true` when the pages were read and no new person came out (the reason may go in `what`). Never both. A living person has no page to list and none is ever added to satisfy the check.

Old rows are not backfilled and an existing row is never edited: editing a row changes its key in the Record Atlas and it reads "Not sent yet" again. Nothing about the people goes to the Atlas; its receipts hold only the row key.
