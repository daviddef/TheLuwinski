# The Luwinski Archive

An evidence-first family archive for the family of **Lynn Derrick Luwinski** — Berlin, Schubin,
Sauerbaum, Lourenço Marques, Johannesburg, Porto.

> Four of this family's men were deported from Berlin between 1941 and 1944 and did not come back.
> One young man got out in 1933 and became a dress designer in Johannesburg. A woman born in
> Portuguese East Africa married four times in that city and was buried in Porto.

## The spine

| | |
|---|---|
| **Sally Leibholz** & **Friederike Schmul** | Hammerstein; married at Szubin, 24 Nov 1874. A Jewish family of the Posen–West Prussia borderland |
| **Joachim Luwinski** (b. Allenstein 1865, *Landwirt*) & **Johanna Thimm** (b. Sauerbaum 1871) | Catholic farming people of the Ermland |
| **Jacob Leibholz** | b. Schubin 8 Aug 1884; *Kaufmann* of Berlin-Schöneberg. **Deported to Auschwitz, 26 February 1943** |
| **Auguste "Lizzy" Luwinski** | b. Sauerbaum 1893, *Schneiderin und Modistin*; d. Kraichtal 1975. Survived |
| **Kurt Israel Luwinski** | b. Berlin 11 May 1912 — twelve years before his parents married. **Emigrated 1933**. Dress designer. d. Johannesburg 15 Dec 1969, buried Chevra Kadisha |
| **Ivone de Figueiredo** | b. Lourenço Marques 4 Mar 1924. Four marriages. Died and buried at **Porto** |
| **Lynn Derrick Luwinski** | **Living — named only**, with his parents and nothing else |

## The finding this archive cannot avoid

**Kurt Israel Luwinski is very probably not Derrick's biological father.** *Inferred, not closed.*

If he were, Derrick's DNA would carry ~25% Ashkenazi Jewish from Jacob Leibholz and ~25% East
Prussian German from Auguste. It carries **0.0%** and **1.4%**, against **60.6% Portuguese** and
**18.5% English**. Of 5,464 DNA matches the ten closest form two clusters — British and Portuguese —
with no German or Jewish cluster anywhere near the top. The paper record was already whispering it:
Ivone married de Witt, then Kurt four and a half months later, and Kurt filed for divorce within
weeks of the wedding and before the child was born.

This does not unsettle Ivone — three Portuguese matches at 108–133 cM confirm her line directly — and
it does not make the Berlin history untrue or less his. See `/dna/` for the arithmetic and the tests
that would overturn it.

## Two corrections to the family tree, on the record

1. **Jacob Leibholz did not die in 1945.** The Bundesarchiv records his deportation to Auschwitz on
   **26 February 1943** and, deliberately, no date of death.
2. **Georg Leibholz was not his brother.** Jacob was born at Schubin in Posen on 8 Aug 1884, Georg at
   Hammerstein in West Prussia on 7 Jun 1884 — two months and two hundred kilometres apart. Sally
   Leibholz was himself born at Hammerstein, so Georg is likely a cousin.

Five duplicate records in the source are collapsed and listed at `/method/`.

## Method

| | |
|---|---|
| **Documented** | A named source with a reference, and where possible the scan |
| **Inferred** | A reasoned conclusion from documented facts, with the reasoning written out so it can be overturned |
| **Disputed** | Asserted in the family record and contradicted by what can be seen |
| **Unproven** | Kept because it may matter later, carrying no weight now — the ~100 surname-index Luwinskis |

**A living person (80 or younger, with no death recorded) is named with their relationships and their town and
country, and nothing more** (the estate-wide standard, version 2, 16 October 2026; the one definition is
`kit/tools/living_rule.py` in the pinned kit, and this archive keeps no test of its own). No dates, no records,
no photograph, no structured data. Every person in the register has a page of their own at `/people/<slug>/`,
the living included: a living person's page is `noindex`, which keeps it out of the sitemap and the search
index. A possible minor (not recorded dead, no public source, no birth year, and a living parent) is **held
out**; a child with a known birth year is living, not held out,: no record, no page, not even as someone's relative. One person goes the other
way: Lynn Derrick Luwinski is *named*, with his parents, and not even a town. A removal request is honoured
within days, without argument and without requiring a reason.

`tools/check-living.py` gates the deploy on that rule by scanning the rendered pages, the served JSON and
the generated register, and it is tested against planted faults (`tools/selftest-living.py`), not merely
assumed to work. The rule is applied where the register is generated (`tools/build-register.py`), so a
living person's dates never reach a committed file. Two things follow from the repository being public:

- **The raw harvest and the working notes are not in it.** `data/myheritage-tree9.json` holds all 164
  people including the living and the held out, and `notes/` names living DNA match holders. Both are
  gitignored. The build needs only `site/src/data/register.json`, in which each living person is a name,
  a relationship and a place.
- **The check cannot be handed the names.** CI therefore recognises the living and the held out by salted
  digests (`data/guarded-hashes.json`) and by their record ids. That is obfuscation rather than secrecy, and
  is documented as such in `tools/make-guarded.py`. The exact check runs locally, where the private source is.

## Running it

```bash
cd site
npm install
npm run dev      # http://localhost:4331/
npm run build    # static output in site/dist, then the living-persons check
```

Deploys to GitHub Pages on every push to `main`.

## Layout

```
data/myheritage-tree9.json    the harvest — 164 people, 648 facts (private, gitignored)
data/leibholz-gedenkbuch.tsv  the four Memorial Book entries
data/dna-ethnicity-derrick.json
notes/                        dna-paternity.md, leibholz-holocaust.md (private, gitignored)
data/guarded-hashes.json      salted digests of the living, and their record ids, so CI can check without the harvest
tools/build-register.py       harvest -> site register, applying the kit's living rule; gives every person a page address
tools/names.py                one normaliser, shared, so generator and checker agree
tools/make-guarded.py         writes the digests; reports any name it cannot guard
tools/people_decisions.py     who the subject is and which records are one person; finds the kit's living_rule
tools/check-living.py         gates the build on the living-persons rule
tools/selftest-living.py      plants a fault for every rule of the gate in a copy and demands it is caught
site/src/pages/               the archive itself
```

## Sources

Bundesarchiv *Gedenkbuch* · MyHeritage (tree and DNA) · FamilySearch, *South Africa Civil Marriage
Records 1840–1973* · National Archives of South Africa · Stolpersteine Berlin.

Identified and not yet worked: Conservatória do Registo Civil do Porto · Arquivo Histórico de
Moçambique · Arquivo Histórico Ultramarino · Landesarchiv Berlin · Arolsen Archives · Yad Vashem ·
Master of the Supreme Court, Pretoria · the Schubin and Hammerstein Jewish registers · the Allenstein
and Kreis Rössel Catholic registers.

## Sibling archives

**The Defranceski** (Istria), **The Falco** (Arienzo), **The Lerena** (Rosario) — same method, same
author. Cheryl Anne Lerena's marriages are the hinge between those archives and this one.

Ivone's parents are unknown. That is the work.
