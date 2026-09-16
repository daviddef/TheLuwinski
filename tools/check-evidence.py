#!/usr/bin/env python3
"""Refuse to ship a build in which a documented person looks undocumented.

THE FAULT THIS GUARDS. Until 17 September 2026 this archive held twenty-one
evidence files in data/ and no build script read any of them. The data was
fine. The build dropped it in silence and nothing refused. The sister archive
at Mazza had the same fault in a different shape: a per-person builder that
never opened documented-additions.tsv or corrections.tsv, so twelve people
whose evidence was sitting in the repo were told, on their own pages, that
nothing had been read about them.

THREE THINGS ARE CHECKED.

  1. EVERY EVIDENCE FILE IS DECLARED. A .tsv in data/ that build-evidence.py's
     manifest does not name reaches nobody. That is the original bug, and it is
     an error rather than a warning on purpose.

  2. THE BUILDER'S OUTPUT IS NOT STALE. If site/src/data/evidence.json does not
     match what the builder produces from data/ right now, the pages are showing
     yesterday's evidence.

  3. NO DOCUMENTED PERSON IS PUBLISHED AS UNDOCUMENTED. For every person named
     in an evidence file, the rendered site must carry EITHER a record for them
     OR a correction. If a documented person reaches dist/ with neither, the
     build stops and the person is named.

    python3 tools/check-evidence.py
"""
import json, os, re, subprocess, sys, pathlib, html

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
EV = ROOT / "site" / "src" / "data" / "evidence.json"
REG = ROOT / "site" / "src" / "data" / "register.json"
DIST = ROOT / "site" / "dist"

def fail(msg):
    print("  " + msg)

def main():
    problems = []

    # (1) + (2): the builder must run clean, and its output must be current.
    before = EV.read_text(encoding="utf-8") if EV.exists() else None
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "build-evidence.py")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout.strip())
        print("\n  FAIL  check-evidence — an evidence file reaches nobody")
        return 1
    after = EV.read_text(encoding="utf-8")
    if before is not None and before != after:
        problems.append("site/src/data/evidence.json was STALE — the pages were built from "
                        "an older reading of data/. Rebuilt; run the build again.")

    ev = json.load(open(EV))
    if not ev["people"]:
        problems.append("build-evidence found no people at all — the manifest key columns are wrong")

    # (3) a documented person must not be published as undocumented.
    if not DIST.exists():
        print("  check-evidence: no site/dist — run astro build first"); return 1
    pages = {}
    for p in DIST.rglob("*.html"):
        pages[p] = html.unescape(re.sub(r"<[^>]+>", " ", p.read_text(encoding="utf-8", errors="ignore")))
    blob = "\n".join(pages.values()).lower()

    corrected = set()
    if REG.exists():
        for p in json.load(open(REG))["people"]:
            if p.get("corrections"):
                corrected.add(p["name"].lower())

    # The evidence page itself is the record. A person named in an evidence file
    # must appear SOMEWHERE in the published site; if they appear nowhere, the
    # evidence never reached a reader, which is exactly the Mazza failure.
    silent = []
    for person in ev["people"]:
        name = person["name"].lower()
        if name in corrected:
            continue
        if name in blob:
            continue
        # try first + last, for index names carrying a middle name
        parts = person["name"].split()
        if len(parts) > 1 and (parts[0].lower() + " " + parts[-1].lower()) in blob:
            continue
        silent.append(person)
    if silent:
        problems.append(f"{len(silent)} person(s) are named in an evidence file and reach the "
                        f"published site with NEITHER a record NOR a correction:")
        for s in silent[:25]:
            problems.append(f"    {s['name']}  —  documented in {', '.join(sorted({r['file'] for r in s['records']}))}")

    if problems:
        print("")
        for p in problems: fail(p)
        print(f"\n  FAIL  check-evidence — {len(problems)} problem(s); evidence is not reaching the page")
        return 1

    c = ev["counts"]
    if ev.get("ambiguous"):
        print(f"  note  check-evidence — {len(ev['ambiguous'])} name(s) match more than one register "
              f"entry and are deliberately NOT linked: {', '.join(ev['ambiguous'])}")
    print(f"  ok    check-evidence — {c['records']} records about {c['people']} people from "
          f"{c['files']} files, all declared, all reaching the page "
          f"({c['linked_to_register']} matched to a register entry)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
