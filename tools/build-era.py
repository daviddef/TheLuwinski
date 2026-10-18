#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The place table behind the "at the time" notes: which Record Atlas region each place on a person's page belongs to.

THE DECISION IS data/era/ground.tsv, written by hand: one row per place string exactly as a person's page prints it (the place of each
dated fact of every register person who is not living, and the place of a born / died line in the English line), with the Atlas region it
belongs to, or '-' for "looked at, and no region covers it", the reason, and the town whose point (data/era/towns.tsv) lets the kit refuse a
place that falls in a neighbouring region's ring. This tool turns those rows into site/src/data/era-places.json and refuses to pass when
the rows and the data disagree. Run from site/ (every path the CI workflow uses is site-relative):

    python3 ../tools/build-era.py                       write src/data/era-places.json
    python3 ../tools/build-era.py --check               build gate (and CI): the file is what the rows build, every place a non-living person's
                                                        page prints beside a fact has a row, no row is stale, the born / died pattern the page
                                                        uses is the one this tool uses, and no mapped place has a dated event in an Atlas era
                                                        that describes only PART of its region (SPLIT_ERAS) unless its row says "split-ok:"
    python3 ../tools/build-era.py --snapshot <Record Atlas>/site/public/context.json --rings <Record Atlas>/data/regions.json
                                                        also rebuild src/data/era-snapshot.json from the Atlas's versioned contract (the
                                                        deliberate refresh: nothing in a build ever reads the Atlas). The contract carries no
                                                        rings; they come from the Atlas's regions.json.
    python3 ../tools/build-era.py --living-urls PATH    write the page paths the notes must never appear on (the register's living and
                                                        named-only people), from the committed register alone, for check:era (CI too)

THE POLICY ON ERAS THE ATLAS HAS NOT ASSESSED. The contract (1.7.0) carries `contested` and `approx` as null on every region era: nobody has
assessed them. The kit refuses such an era by default, which leaves no note at all, so this archive builds its snapshot with
--unassessed allow, on purpose and on the record (David approved it for now, 18 October 2026): the snapshot's policy says so, the gate prints
how many notes rest on an unassessed era, and dropping that flag below (then rebuilding) is the whole of going strict.

Only places of people who are NOT living are read: a living person's page prints a town and a country and no fact, and the notes are never
drawn there. A held-out person has no page and is in no register, so is in no row.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "..", "site")
KIT_TOOLS = os.path.join(SITE, "node_modules", "@daviddef", "archive-kit", "kit", "tools")
DATA = os.path.join(SITE, "src", "data")
GROUND = os.path.join(HERE, "..", "data", "era", "ground.tsv")
TOWNS = os.path.join(HERE, "..", "data", "era", "towns.tsv")
OUT = os.path.join(DATA, "era-places.json")
SNAP = os.path.join(DATA, "era-snapshot.json")
PLACE_JS = os.path.join(SITE, "src", "lib", "eraplace.js")

# The English line's born / died strings are free prose. Only «<plain date>, <one place>» is read as a dated place-event; anything longer
# («Q1 1890, St Olave Southwark, aged 31», «1957, registered at Hitchin as ...») is not, and gets no note. src/lib/eraplace.js holds the
# SAME pattern and --check fails if the two differ.
ENGLISH_LIFE = r"^(\d{1,2} [A-Z][a-z]+ \d{4}|\d{4}),\s+([A-Z][A-Za-z' -]+)$"

# Atlas eras that describe only PART of their region (read from the contract's polity text for the regions this archive uses). A label
# is region-wide, so a place in the other part would be given the wrong regime. A mapped place with a dated event in one of these must say
# "split-ok:" in its row, i.e. a person looked at it.
SPLIT_ERAS = ("east-prussia--era-1945", "galicia--era-1945", "silesia--era-1918", "west-prussia--era-1920")


def rows_of(path):
    for line in open(path, encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        yield line.rstrip("\n").split("\t")


def ground():
    rows = {}
    for cols in rows_of(GROUND):
        if cols[0] == "place":
            continue
        place, region, why, town = (cols + ["", "", "", ""])[:4]
        if not place or not region or not why:
            raise SystemExit("era/ground.tsv: a row needs a place, a region (or '-') and a reason: %r" % cols[0][:60])
        if place in rows:
            raise SystemExit("era/ground.tsv: a place appears twice (a row must say one thing)")
        rows[place] = (region, why, town)
    return rows


def towns():
    out = {}
    for cols in rows_of(TOWNS):
        if cols[0] == "town":
            continue
        out[cols[0]] = (float(cols[1]), float(cols[2]))
    return out


def load(name):
    return json.load(open(os.path.join(DATA, name), encoding="utf-8"))


def is_living(r):
    return r.get("living") is True or r.get("bare") is True


def has_name(s):
    """A place with no letter or digit in it prints as nothing."""
    return any(c.isalnum() for c in str(s))


def events():
    """Every (place, date text) a non-living person's page prints beside a fact, and every born / died place the English line prints."""
    out = []
    for r in load("register.json")["people"]:
        if is_living(r):
            continue
        for f in r.get("facts") or []:
            if f.get("place") and has_name(f["place"]):
                out.append((f["place"], f.get("date") or ""))
    pat = re.compile(ENGLISH_LIFE)
    for p in load("english-people.json")["people"]:
        for k in ("born", "died"):
            m = pat.match(p.get(k) or "")
            if m:
                out.append((m.group(2), m.group(1)))
    return out


def event_places():
    out = {}
    for place, _ in events():
        out[place] = out.get(place, 0) + 1
    return out


def build():
    rows = ground()
    used = event_places()
    pts = towns()
    table = {}
    for place in sorted(rows):
        region, _, town = rows[place]
        if region == "-":
            table[place] = None
            continue
        table[place] = {"region": region}
        if town:
            if town not in pts:
                raise SystemExit("era/ground.tsv: town %r has no row in era/towns.tsv" % town)
            table[place].update(lat=pts[town][0], lon=pts[town][1])
    return rows, used, table


def living_urls():
    return sorted("/people/%s/" % r["slug"] for r in load("register.json")["people"] if is_living(r))


def split_findings(rows):
    """Mapped places with a dated event in a SPLIT era, and no 'split-ok:' on their row. Needs the snapshot (the eras' years)."""
    try:
        snap = json.load(open(SNAP, encoding="utf-8"))
    except (OSError, ValueError):
        return None
    spans = {}
    for region, eras in snap.get("regions", {}).items():
        for e in eras:
            if e["id"] in SPLIT_ERAS:
                spans[e["id"]] = (region, e["from"], e["to"])
    bad = set()
    for place, date in events():
        region = rows.get(place, ("-", "", ""))
        if region[0] == "-" or "split-ok:" in region[1]:
            continue
        years = [int(y) for y in re.findall(r"(?<!\d)(\d{4})(?!\d)", date)]
        for eid, (reg, a, b) in spans.items():
            if reg == region[0] and any(a <= y and (b is None or y < b) for y in years):
                bad.add(place)
    return sorted(bad)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--snapshot", default=None, help="a local copy of the Record Atlas's context.json (the versioned contract): also rebuild era-snapshot.json")
    ap.add_argument("--rings", default=None, help="the Atlas's regions.json (data/regions.json in the Atlas repository), for the ring-edge rule")
    ap.add_argument("--report", default=None, help="with --snapshot: also write the per-region drops (counts) here, for the Atlas session")
    ap.add_argument("--living-urls", default=None, help="write the living / named-only page paths here (JSON list) and stop")
    a = ap.parse_args()
    if a.living_urls:
        urls = living_urls()
        if not urls:
            raise SystemExit("build-era: no living page found; a list of none would make the living gate a verdict on nothing")
        os.makedirs(os.path.dirname(os.path.abspath(a.living_urls)), exist_ok=True)
        open(a.living_urls, "w", encoding="utf-8").write(json.dumps(urls, indent=0) + "\n")
        print("era living list: %d page path(s)" % len(urls))
        return 0
    rows, used, table = build()
    missing = sorted(set(used) - set(rows))
    stale = sorted(set(rows) - set(used))
    out = {"_about": "Built by tools/build-era.py from data/era/ground.tsv and data/era/towns.tsv. Place as printed -> {region, lat, lon}, or null where no Atlas "
                     "region covers it. Read by kit erasnap.py.", "places": table}
    text = json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if a.check:
        bad = False
        if missing:
            print("  FAIL  era-ground  %d place string(s) a non-living person's page prints beside a fact have no row in data/era/ground.tsv "
                  "(decide a region, or '-', for each)" % len(missing))
            bad = True
        if stale:
            print("  FAIL  era-ground  %d row(s) in data/era/ground.tsv match no place (stale)" % len(stale))
            bad = True
        try:
            have = open(OUT, encoding="utf-8").read()
        except OSError:
            have = None
        if have != text:
            print("  FAIL  era-ground  site/src/data/era-places.json is not what the rows build (run tools/build-era.py)")
            bad = True
        try:
            js = open(PLACE_JS, encoding="utf-8").read()
        except OSError:
            js = ""
        if ENGLISH_LIFE not in js:
            print("  FAIL  era-ground  site/src/lib/eraplace.js does not hold the born / died pattern tools/build-era.py uses (they must be the same)")
            bad = True
        sp = split_findings(rows)
        if sp is None:
            print("  FAIL  era-ground  site/src/data/era-snapshot.json is missing or unreadable")
            bad = True
        elif sp:
            print("  FAIL  era-ground  %d mapped place(s) have a dated event in an Atlas era that describes only part of its region (%s): look at each and "
                  "write 'split-ok: <why>' in its row, or map it to '-'" % (len(sp), ", ".join(SPLIT_ERAS)))
            bad = True
        if not bad:
            mapped = sum(1 for v in table.values() if v)
            print("  ok    era-ground  %d place strings decided (%d mapped to a region, %d to none); the table matches; no mapped place sits in a split era"
                  % (len(table), mapped, len(table) - mapped))
        return 1 if bad else 0
    open(OUT, "w", encoding="utf-8").write(text)
    print("era-places.json: %d place strings (%d mapped)" % (len(table), sum(1 for v in table.values() if v)))
    if missing:
        print("  WARNING %d place string(s) have no row in data/era/ground.tsv" % len(missing))
        return 1
    if a.snapshot:
        if not a.rings:
            print("  FAIL  era-ground  --snapshot needs --rings <the Atlas's regions.json>: the contract carries no rings")
            return 2
        cmd = [sys.executable, os.path.join(KIT_TOOLS, "erasnap.py"), "--contract", a.snapshot, "--rings", a.rings,
               "--places", OUT, "--out", SNAP, "--unassessed", "allow"]
        if a.report:
            cmd += ["--report", a.report]
        r = subprocess.run(cmd)
        return r.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
