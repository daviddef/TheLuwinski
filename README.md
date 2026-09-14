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
| **Lynn Derrick Luwinski** | b. 24 April 1949. **Living — named only** |

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

**Living people are omitted from the build entirely.** One exception: Lynn Derrick Luwinski is
*named*, with his birth year and parents, and nothing else. A removal request is honoured within
days, without argument and without requiring a reason.

`tools/check-living.py` gates the deploy on that promise by scanning the rendered HTML — and it is
tested against planted names, not merely assumed to work. Two things follow from the repository being
public:

- **The raw harvest and the working notes are not in it.** `data/myheritage-tree9.json` holds all 164
  people including the living, and `notes/` names living DNA match holders. Both are gitignored. The
  build needs only `site/src/data/register.json`, from which living people are already gone.
- **The list of names to keep out cannot itself be in here.** CI therefore guards on salted digests
  (`data/guarded-hashes.json`), hashing candidate names out of the built HTML. That is obfuscation
  rather than secrecy, and is documented as such in `tools/make-guarded.py`. The exact check runs
  locally, where the private source is.

## Running it

```bash
cd site
npm install
npm run dev      # http://localhost:4331/TheLuwinski/
npm run build    # static output in site/dist, then the living-persons check
```

Deploys to GitHub Pages on every push to `main`.

## Layout

```
data/myheritage-tree9.json    the harvest — 164 people, 648 facts (private, gitignored)
data/leibholz-gedenkbuch.tsv  the four Memorial Book entries
data/dna-ethnicity-derrick.json
notes/                        dna-paternity.md, leibholz-holocaust.md (private, gitignored)
data/guarded-hashes.json      salted digests of the omitted, so CI can check without the names
tools/build-register.py       harvest -> site register, applying the living rule
tools/names.py                one normaliser, shared, so generator and checker agree
tools/make-guarded.py         writes the digests; reports any name it cannot guard
tools/check-living.py         gates the build on the living-persons promise
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
