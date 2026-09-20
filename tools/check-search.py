#!/usr/bin/env python3
"""Fail the build if the search page fetches a file that was not published.

WHY THIS GATE EXISTS. On 21 September 2026 a peer session found that this
archive's search index was missing from dist, and it was missing because
build-search.py wrote it into dist while astro build empties dist on the way
past. The live site was never affected -- CI runs the chain in order and
deploys what the last step produced -- but locally the index vanished every
time a build was interrupted, and NOTHING NOTICED. The page fetched, the fetch
404'd, the search box returned nothing, and every gate in the chain said ok.

That is the same shape as the living-name gate that walked *.html and never
looked at the JSON the browser fetches: a file that is served but not rendered
is invisible to anything that only reads pages. This gate reads the page to
find out what it fetches, and then checks that the fetch would succeed.
"""
import re, sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "site" / "dist"
SRC  = ROOT / "site" / "src" / "pages"

def main():
    if not DIST.exists():
        sys.exit("check-search: no dist/ -- run a build first")
    wanted = set()
    for page in sorted(SRC.rglob("*.astro")):
        for m in re.finditer(r"fetch\(\s*base\s*\+\s*'(/[^']+\.json)'", page.read_text(encoding="utf-8")):
            wanted.add(m.group(1).lstrip("/"))
    if not wanted:
        print("  ok    check-search — no page fetches a JSON file")
        return
    bad = []
    for rel in sorted(wanted):
        f = DIST / rel
        if not f.exists():
            bad.append(f"{rel} — fetched by a page, NOT PUBLISHED"); continue
        try:
            n = len(json.loads(f.read_text(encoding="utf-8")).get("entries", []))
        except Exception as e:
            bad.append(f"{rel} — published but not readable JSON: {e}"); continue
        if n == 0:
            bad.append(f"{rel} — published but empty")
            continue
        # FRESHNESS, WHICH IS THE FAILURE EXISTENCE DOES NOT CATCH.
        # A peer session pointed out on 21 September that a stale index passes
        # every test above: it exists, it parses, it has twelve thousand rows,
        # and it is quietly describing a site that no longer exists. Two of the
        # sibling archives are in exactly that state because their generator is
        # not in the build chain at all. The cheap test is not to look at the
        # index but to COMPARE IT AGAINST dist: every page that was built should
        # be represented, and a page built after the index was written will not
        # be. That is one number, and it is zero or it is not.
        try:
            urls = {e.get("url", "") for e in json.loads(f.read_text(encoding="utf-8"))["entries"]}
        except Exception:
            urls = set()
        built, absent = 0, []
        for page in sorted(DIST.rglob("index.html")):
            slug = "/" + str(page.parent.relative_to(DIST)).replace("\\", "/").strip(".")
            slug = "/" if slug in ("/.", "/") else slug.rstrip("/") + "/"
            built += 1
            if not any(u.rstrip("/") + "/" == slug or u.rstrip("/").endswith(slug.rstrip("/")) for u in urls):
                absent.append(slug)
        skip = {"/search/", "/404/"}
        absent = [a for a in absent if a not in skip]
        if absent:
            bad.append(f"{rel} — STALE: {len(absent)} of {built} built page(s) absent from the index, "
                       f"first few {absent[:5]} — the index describes a site that is no longer there")
        else:
            print(f"  ok    check-search — {rel} published, {n} entries, "
                  f"all {built} built page(s) represented")
    if bad:
        for b in bad:
            print(f"  FAIL  check-search — {b}")
        sys.exit(f"check-search: {len(bad)} problem(s)")

if __name__ == "__main__":
    main()
