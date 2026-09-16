#!/usr/bin/env python3
"""Refuse to ship a build that names a living DNA match holder.

check-living guards the people in the family register. It does NOT guard the
people on the DNA match list, who are living, who never consented to anything,
and whose names reached this archive only because they share chromosomes with
Derrick. On 16 September 2026 four of them were found published in full on the
work-list page and five more by surname on the DNA page. Nothing caught it,
because nothing was looking.

The authority is the AutoClusters export, which is gitignored precisely because
it names them. So this check DEGRADES GRACEFULLY: with no export present it
says so and passes, rather than giving a false all-clear on a machine that
simply does not hold the list.

    python3 tools/check-matches.py [--strict]

--strict makes a missing export an error instead of a skip.
"""
import csv, glob, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS = sorted(glob.glob(os.path.join(ROOT, "data", "autoclusters-*.csv")))
DIST = os.path.join(ROOT, "site", "dist")

# Surnames that are also legitimately the names of DEAD people in this archive,
# or ordinary English words. A surname alone here is not evidence; a full name is.
AMBIGUOUS = {
    "halsey",    # Mervin Richard Halsey m. Cynthia Wear 1952 — both dead
    "morris",    # Morris Isaac Salkow — dead
    "brown", "browne",  # Walter George Brown m. Agnes Kate Castle — dead
    # Giddins/Giddings is NOT a coincidence, and that is exactly why it is here.
    # James Giddins of Norton End, Baldock, b.1815, is Derrick's 3x-great-grandfather,
    # proved from the 1861 and 1871 censuses on 16 September 2026. TWO LIVING MATCH
    # HOLDERS CARRY THE SURNAME, at 43.36 and 62.89 cM, both in cluster 12 — which is
    # consistent with fourth cousins descending from James through Martha's brothers.
    # THE RULE PROTECTS LIVING PEOPLE, NOT DEAD ONES. Publishing a man born in 1815
    # does not identify anybody alive; the two match holders remain unnamed on the site
    # and appear only as cM and cluster. Recorded rather than silently widened.
    "giddins", "giddings",
    "mary", "thomas", "roberts", "hunter", "cross", "wood", "hall", "ward",
    "johnson", "gray", "collins", "marshall", "cox", "ball", "lord", "carter",
    "payne", "gordon", "graham", "gibson", "scully", "bury", "irons",
    # Portuguese surnames that occur throughout the Ivone research as ancestors
    "dias", "gaspar", "conde", "fernandes", "machado", "rodrigues", "ferreira",
    "costa", "veloso", "soares", "pombo", "neves", "brinca",
}

def load_names():
    names = set()
    for p in EXPORTS:
        for row in csv.DictReader(open(p, encoding="utf-8-sig")):
            nm = (row.get("Name") or "").strip()
            if nm and not nm.startswith("<"):
                names.add(nm)
    return names

def main():
    strict = "--strict" in sys.argv
    if not EXPORTS:
        msg = "check-matches: NO AutoClusters export on this machine — cannot verify"
        print(("  FAIL  " if strict else "  skip  ") + msg)
        return 1 if strict else 0
    names = load_names()
    pages = [(p, open(p, encoding="utf-8", errors="ignore").read())
             for p in glob.glob(os.path.join(DIST, "**", "*.html"), recursive=True)]
    if not pages:
        print("  skip  check-matches: no build in site/dist — run astro build first")
        return 0

    bad = []
    for nm in sorted(names):
        for path, text in pages:
            if re.search(r"\b" + re.escape(nm) + r"\b", text, re.I):
                bad.append(("FULL NAME", nm, rel(path)))
                break

    # surnames, minus the ambiguous list
    for nm in sorted(names):
        parts = [x for x in re.split(r"[\s()]+", nm)
                 if len(x) > 3 and x.lower() not in ("born", "private")]
        if not parts:
            continue
        sur = parts[-1]
        if sur.lower() in AMBIGUOUS:
            continue
        for path, text in pages:
            if re.search(r"\b" + re.escape(sur) + r"\b", text):
                bad.append(("surname", sur, rel(path)))
                break

    if bad:
        print("  FAIL  check-matches: %d living DNA match holder(s) named in the build" % len(bad))
        for kind, nm, where in bad:
            print("          %-10s %-32s %s" % (kind, nm, where))
        print("\n        Living match holders are published as ROLE, COUNTRY and cM only.")
        print("        If one of these is a coincidence, add the surname to AMBIGUOUS in this file")
        print("        WITH A REASON — do not widen the list silently.")
        return 1

    print("  ok    check-matches — %d match holders checked against %d pages, none named"
          % (len(names), len(pages)))
    return 0

def rel(p):
    return p.replace(DIST + os.sep, "").replace(os.sep + "index.html", "") or "/"

if __name__ == "__main__":
    sys.exit(main())
