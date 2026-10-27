#!/usr/bin/env python3
"""THE MINI FLAGS ON THE RIBBON CARDS (27 October 2026; kit/docs/ribbon-flags.md): the kit's generator, run over this archive's
ribbons (the story's and every family ribbon), into a file of its own.

    python3 tools/build-ribbon-flags.py               write site/src/data/ribbon-flags.json and print what each place line drew
    python3 tools/build-ribbon-flags.py --check       exit 1 if the committed ribbon-flags.json is not what the inputs make
    python3 tools/build-ribbon-flags.py --merged DIR  also write DIR/story.json and DIR/family-lines.json: the two ribbon files
                                                      with each card's `flags` put back, for the kit's gate checkribbonflags.py
    python3 tools/build-ribbon-flags.py --report F    also write the kit's report (every place line, what it drew, why not more)

WHAT DECIDES A FLAG is the kit's, not this file's: kit/tools/ribbonflags.py (imported, never copied) with this archive's era
snapshot (site/src/data/era-snapshot.json: the same table and rules as the 'at the time' notes), its alias table
(site/src/data/flag-places.json: a card's place -> the SAME town's row in the era table) and its country table
(site/src/data/flag-countries.json: the country today of a place the kit will not place by itself). Both tables are typed by
hand, each entry with its evidence. A flag of a hate-symbol or occupation regime is never drawn (the kit's table withholds every
one: for those years a card shows today's flag alone, or nothing), and a living card gets today's flag only, with no year.

WHY A FILE OF ITS OWN, AND NOT `flags` WRITTEN INTO THE CARDS AS THE KIT'S --write DOES. At kit 1fa6b54 the story's contract
(kit/data/story-schema.json, checkfamilystory.py S0) and the family ribbon's (checkfamilyribbon.py F0) refuse a card field they
do not know, and `flags` is one; story.json is typed by hand, and family-lines.json is rewritten whole by
tools/build-family-lines.py. So the flags live here, keyed by ribbon, the card's position and its name (a living card:
`living`, no name), and the pages put them on the cards as they are drawn (site/src/lib/ribbonflags.js: /story/ and the family
pages). A card whose name no longer matches gets no flags, and the kit's gate then fails it (R7: a flag missing) until this is run
again. `npm run build` runs this before astro build (flags:data) and checks it after (check:ribbonflags: --check, then the kit's
checkribbonflags.py over the --merged copies and the built pages, then its selftest); CI runs the same checks, and the box gate
(check:flagfit, tools/check-flagfit.sh: no card one pixel bigger with its flags).

Exit 0 ok, 1 (--check) the file is not what the inputs make, 2 an input cannot be read.
"""
import argparse, copy, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "site", "src", "data")
KIT_TOOLS = os.path.join(ROOT, "site", "node_modules", "@daviddef", "archive-kit", "kit", "tools")
SNAPSHOT = os.path.join(DATA, "era-snapshot.json")
STORY = os.path.join(DATA, "story.json")
FAMILIES = os.path.join(DATA, "family-lines.json")
ALIAS = os.path.join(DATA, "flag-places.json")
COUNTRIES = os.path.join(DATA, "flag-countries.json")
OUT = os.path.join(DATA, "ribbon-flags.json")

NOTE = ("Made by tools/build-ribbon-flags.py with the kit's ribbonflags.py from era-snapshot.json, flag-places.json and "
        "flag-countries.json, over story.json's ribbon and family-lines.json; do not edit by hand. Each entry: a ribbon card that "
        "draws flags (its position from 1, its name or `living`, and the kit's `flags`). The pages put them on the cards "
        "(src/lib/ribbonflags.js). Flags: Flags Atlas, by David Defranceski, drawn for this project; no licence is claimed.")


def key_of(card):
    """How the page recognises the card: its name, or `living` for a living card (whose name this file never carries)."""
    return {"living": True} if (card.get("living") or card.get("minor")) else {"name": card.get("name")}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--merged")
    ap.add_argument("--report")
    a = ap.parse_args()
    if not os.path.exists(os.path.join(KIT_TOOLS, "ribbonflags.py")):
        print("build-ribbon-flags: the kit's ribbonflags.py is not installed (npm install in site/, kit pin 1fa6b54 or later)")
        return 2
    sys.path.insert(0, KIT_TOOLS)
    import ribbonflags as RF  # noqa: E402

    def table(path):
        return {k: v for k, v in RF.load(path).items() if not k.startswith("_")}
    try:
        story, families = RF.load(STORY), RF.load(FAMILIES)
        ctx = RF.context(RF.load(SNAPSHOT), table(ALIAS), None, countries=table(COUNTRIES))
    except (OSError, ValueError) as e:
        print("build-ribbon-flags: cannot read an input: %s" % e)
        return 2
    s2, f2 = copy.deepcopy(story), copy.deepcopy(families)
    rep = RF.run(ctx, s2, f2)

    out = {"_note": NOTE, "story": [], "families": {}}
    for i, c in enumerate((s2.get("ribbon") or {}).get("cards") or []):
        if c.get("flags"):
            out["story"].append(dict(card=i + 1, **key_of(c), flags=c["flags"]))
    for fam in f2.get("families") or []:
        rows = [dict(card=i + 1, **key_of(c), flags=c["flags"]) for i, c in enumerate(fam.get("cards") or []) if c.get("flags")]
        if rows:
            out["families"][fam["id"]] = rows
    text = json.dumps(out, ensure_ascii=False, indent=1) + "\n"

    if a.merged:
        os.makedirs(a.merged, exist_ok=True)
        RF.dump(os.path.join(a.merged, "story.json"), s2)
        RF.dump(os.path.join(a.merged, "family-lines.json"), f2)
    if a.report:
        RF.dump(a.report, rep)
    n = len(rep["cards"])
    lines = ", ".join("%s %d" % kv for kv in sorted(rep["lines"].items()))
    if a.check:
        have = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else None
        if have != text:
            print("build-ribbon-flags: site/src/data/ribbon-flags.json is not what the inputs make; run python3 tools/build-ribbon-flags.py")
            return 1
        print("build-ribbon-flags: ribbon-flags.json is what the inputs make: %d flags; place lines by what they draw: %s" % (n, lines))
        return 0
    if not os.path.exists(OUT) or open(OUT, encoding="utf-8").read() != text:
        open(OUT, "w", encoding="utf-8").write(text)
    RF.print_report(rep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
