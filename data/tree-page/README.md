# Roots & Routes (the tree page)

Ten views of the people in the archive who have died and whose death the archive can stand behind: hourglass, fan, whole-tree and close-family maps, Atlas map,
movements, kinship, place lanes, eras, lifespans, an Orphans tab, and the five animated views (Night sky, Ink ledger, Household, Generations, Where they
lived). It is served at `/roots/`, and bare at `/roots/view.html` for frames (the kit's `PersonRootsViews`, which this archive's person page does not use yet:
see "The person page" below).

| File | What it is | Edit by hand? |
|---|---|---|
| `tree.json` | people, parent links, years, places | no, generated |
| `place_map.json` | each place string with coordinates, country and Record Atlas id | no, generated (see below) |
| `place-additions.json` | place strings decided by hand, each with its reason | yes, with a reason |
| `atlas-data.json` | the Record Atlas slice: outlines, regimes, flags, events, collections | no, generated |
| `roots.html`, `roots.embed.html` | the page, whole and as a fragment for the site layout | no, generated |
| `tree.report.json` | counts, the place strings still unresolved, the district-level places | read it |
| `people.ged`, `slugs.json` | intermediates, not committed (`*.ged` is ignored) | no |

## Rebuild

```bash
python3 tools/build-tree-page.py --accept-unique   # rebuild everything and run the page's own checks
python3 tools/build-tree-page.py --check           # exit 1 if the page is older than the data it was built from
```

Needs the Record Atlas checkout (`RECORD_ATLAS`, default `~/Projects/Family Projects/Record Atlas`), read only, including its GeoNames gazetteer. The skill's
scripts are vendored in `tools/tree-page/` (the family-tree-page skill, template 1.6.0), so CI and other sessions do not depend on `~/.claude`.

## Who is on the page, and who is not

The people are `site/src/data/register.json` (the register the person pages are drawn from, already reduced to a name for the living) and the twenty-six
hand-written people of the English line (`english-people.json`). The raw MyHeritage harvest is never read.

- **Never drawn:** anyone the register flags `living` or `bare` (the subject, named with his parents only); placeholders (a record that stands for nobody).
- **Drawn only with a death on record:** a person is drawn if the register has a year of death for them, or if the tree marks them deceased, they were born in
  1900 or earlier and they are related to someone who is drawn. A person with no death recorded who was born after 1900 is not drawn and is **not named
  anywhere**: `tree.report.json` holds a count. A surname-index entry with no relation and no death date is not drawn either.
- **No invented death.** Someone murdered or deported with no year of death recorded is not drawn (a year would have to be made up). Someone whose death the
  register calls "not documented" (deported, no date) is drawn with a death year taken from the deportation and marked as an estimate (`1884–?`), and no
  place of death is claimed: they are placed at their last residence.
- **Estimated years are flagged**: "c. 1809" is a birth estimated from a relative or given as approximate by the source; "1809–?" is a death not recorded
  (the converter adds 75 years, the page says so).
- **The English line's 79 relatives with no page of their own are not drawn**: they have no sex, no place and, mostly, no death on record.
- **Colour is the archive's own family** (`families.json`: the surname line a person is declared in), not a surname spelling. Which spellings are one name is the
  Record Atlas catalogue's to say; nothing here lists them.

## Places

Never guessed. In order: `place-additions.json` (a string decided by hand, with its reason); `data/era/ground.tsv` + `data/era/towns.tsv` (the archive's own
decision of the town for a string, and its hand point); the town `ground.tsv` names in its reason column; then the converter's rule (one Atlas place, and the
string names its country). A string whose first segment is a village in a Kreis is placed at the village only if the Atlas's GeoNames gazetteer has exactly one
place of that name within 40 km of the archive's point, and otherwise is drawn at the town and **named "village (near town)"**. The country is always the Atlas's
own `geo.country_of`. A person with no resolved birth place is drawn at a relative's birth place (the page says so) or not drawn.

## The person page

`site/src/pages/people/[slug].astro` uses the kit's `PersonPage`, but in **chart mode**; `PersonRootsViews` (slot `where`) is drawn only in story mode, which needs
a written life (`story` slot). This archive has none for register people, so no "Where they lived" frame is added to a person page. `roots-links.json` is
written already (the people the page draws), so adding the slot to a story-mode person later is one line.
