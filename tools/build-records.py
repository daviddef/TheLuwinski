#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The records table for the linking standard (kit/components/Rec.astro, L3 and L4): every record a passage may link to.

    python3 ../tools/build-records.py            # from site/: writes site/src/data/records.json
    python3 ../tools/build-records.py --check    # fails if the committed table is not what the data gives (or not safe)
    python3 ../tools/build-records.py --counts   # prints counts only, writes nothing

WHERE IT COMES FROM. Only data the archive already holds and commits:
  * site/src/data/evidence.json, which tools/build-evidence.py writes from the 144 ledger files in data/: one row per file,
    `url` the file's own entry on /searched/ (every file has an anchor there: /searched/#<file-stem>), `label` its title;
  * data/record-plates.json, the archive's word on (a) which published scans belong to which ledger entry and whether its
    rules let it show them, (b) the records it holds a PUBLIC ADDRESS for (two FamilySearch arks, link only), and (c) the
    ledger entries it will not link to (`hold`) and the scans it withholds.
No address is invented. A row's `url` is the ledger entry's anchor, or an ark that the ledger file itself prints (the build
refuses an external row whose needle is not in the file it names).

THE LIVING GATE. A ledger entry is never given a row (it is held: Rec draws nothing for a held row, so none is written) when
  * the data/record-plates.json `hold` list names it (a file that concerns people who are flagged living but are not named
    in it: the 1965 roll names two children only as "aged 10 and 3"), or
  * the file's text holds any living or held-out person's spelling from the private feed (private/checkprose-feed.json,
    when this machine has it). Without the feed it says so and the hold list is the only gate; --check in CI is therefore the
    weaker, public half of the same test, as for the names index.
A scan row (`kind: plate`) is `show: true` only where data/record-plates.json says so, and never for a held record.
Counts only are printed.
"""
import io, json, os, re, sys, argparse, pathlib, unicodedata

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SITE = ROOT / "site"
EVIDENCE = SITE / "src" / "data" / "evidence.json"
PLATES = ROOT / "data" / "record-plates.json"
OUT = SITE / "src" / "data" / "records.json"
FEED = pathlib.Path(os.environ.get("CHECKPROSE_FEED") or ROOT / "private" / "checkprose-feed.json")


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c)).casefold()).strip()


def living_spellings():
    if not FEED.exists():
        return set(), False
    feed = json.load(io.open(FEED, encoding="utf-8"))
    out = set()
    for x in feed.get("living", []):
        for n in x.get("names", []):
            f = fold(n)
            if len(f.split()) >= 2:
                out.add(f)
    return out, True


def build():
    ev = json.load(io.open(EVIDENCE, encoding="utf-8"))
    pl = json.load(io.open(PLATES, encoding="utf-8"))
    living, have_feed = living_spellings()
    held_stems = {h["record"] for h in pl.get("hold", [])}
    for h in pl.get("hold", []):
        if len(str(h.get("reason", "")).strip()) < 20:
            raise SystemExit("build-records: a hold entry needs a reason (%s)" % h.get("record"))
    stems = {}
    rows, stats = [], {"ledger entries": 0, "held (hold list)": 0, "held (a living spelling in the file)": 0,
                       "scan rows": 0, "scan rows that may be shown": 0, "external rows (link only)": 0}
    for f in ev["files"]:
        stem = f["file"].rsplit(".", 1)[0]
        stems[stem] = f
        text = ""
        p = ROOT / "data" / f["file"]
        if p.exists():
            text = fold(io.open(p, encoding="utf-8").read() + " " + f["title"] + " " + f["source"])
        if stem in held_stems:
            stats["held (hold list)"] += 1
            continue
        if have_feed and any(n in text for n in living):
            stats["held (a living spelling in the file)"] += 1
            held_stems.add(stem)
            continue
        rows.append({"id": stem, "url": "/searched/#" + stem, "label": f["title"], "kind": "ledger"})
        stats["ledger entries"] += 1
    for h in held_stems:
        if h not in stems:
            raise SystemExit("build-records: the hold list names a file that is not a ledger entry (%s)" % h)
    for q in pl.get("plates", []):
        rec = q["record"]
        if rec not in stems:
            raise SystemExit("build-records: a scan names a record that is not a ledger entry (%s)" % rec)
        if not (SITE / "public" / q["file"]).exists():
            raise SystemExit("build-records: a scan is not in site/public (%s)" % q["file"])
        if rec in held_stems:
            continue
        stats["scan rows"] += 1
        row = {"id": q["id"], "url": "/searched/#" + rec, "label": q["label"], "kind": "plate", "plate": q["file"], "w": q["w"], "h": q["h"]}
        if q.get("show") is True and len(str(q.get("basis", "")).strip()) >= 20:
            row["show"] = True
            stats["scan rows that may be shown"] += 1
        rows.append(row)
    for x in pl.get("external", []):
        src = ROOT / "data" / (x["from"] + ".tsv")
        if not src.exists() or x["needle"] not in io.open(src, encoding="utf-8").read():
            raise SystemExit("build-records: an external address is not printed in the file it names (%s)" % x["id"])
        if not re.match(r"^https://(www\.familysearch\.org/ark:/61903/|antenati\.cultura\.gov\.it/ark:/)", x["url"]):
            raise SystemExit("build-records: an external address is not on a host this table accepts (%s)" % x["id"])
        rows.append({"id": x["id"], "url": x["url"], "label": x["label"], "kind": x["kind"]})
        stats["external rows (link only)"] += 1
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise SystemExit("build-records: an id is used twice")
    return {"records": rows}, stats, have_feed


def render(table):
    return json.dumps(table, ensure_ascii=False, indent=1) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--counts", action="store_true")
    a = ap.parse_args(argv)
    table, stats, have_feed = build()
    for k, v in stats.items():
        print("  %-62s %d" % (k, v))
    print("  %-62s %s" % ("private feed (living spellings) read", "yes" if have_feed else "NO (the hold list is the only living gate)"))
    text = render(table)
    if a.counts:
        return 0
    if a.check:
        if not OUT.exists():
            print("build-records: FAIL, %s is missing; run tools/build-records.py" % OUT.relative_to(ROOT))
            return 1
        cur = io.open(OUT, encoding="utf-8").read()
        if have_feed:
            ok = cur == text
        else:
            # public half (CI): the committed table may hold no row the public data does not give, and may hold fewer
            # (the machine with the private feed held more files back)
            have = {r["id"]: r for r in json.loads(cur)["records"]}
            give = {r["id"]: r for r in table["records"]}
            ok = all(i in give and give[i] == r for i, r in have.items())
            # a held-out stem must never be in the committed table
            hold = {h["record"] for h in json.load(io.open(PLATES, encoding="utf-8")).get("hold", [])}
            ok = ok and not (hold & set(have))
        if not ok:
            print("build-records: FAIL, %s is not what the data gives; run tools/build-records.py and commit it" % OUT.relative_to(ROOT))
            return 1
        print("build-records: ok (%s)" % ("equal to the data, private feed read" if have_feed else "every committed row is one the public data gives"))
        return 0
    io.open(OUT, "w", encoding="utf-8").write(text)
    print("build-records: wrote %s" % OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
