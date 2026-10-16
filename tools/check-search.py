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
import os, re, sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# ARCHIVE_OUT beats the default, as in every kit tool (kit/tools/outdir.py). An isolated
# build lives in site/$ARCHIVE_OUT and this read site/dist whatever the variable said, so a
# session building somewhere of its own indexed and checked the shared directory instead.
# The default is still dist, which CI uploads.
DIST = ROOT / "site" / (os.environ.get("ARCHIVE_OUT") or "dist")
SRC  = ROOT / "site" / "src" / "pages"
NOINDEX = re.compile(r'<meta[^>]*name=["\']robots["\'][^>]*noindex|<meta[^>]*noindex[^>]*name=["\']robots["\']', re.I)

def main():
    if not DIST.exists():
        sys.exit("check-search: no dist/ -- run a build first")
    wanted = set()
    for page in sorted(SRC.rglob("*.astro")):
        src = page.read_text(encoding="utf-8")
        for m in re.finditer(r"fetch\(\s*base\s*\+\s*'(/[^']+\.json)'", src):
            wanted.add(m.group(1).lstrip("/"))
        # THE KIT'S SEARCH BOX DOES THE FETCHING NOW, AND THIS GATE WENT QUIET
        # THE MOMENT IT DID. On 22 September the search page stopped carrying
        # its own fetch() and started importing the shared component; `wanted`
        # came back empty, and this printed "no page fetches a JSON file" and
        # passed. Everything below — is the index published, does it parse, is
        # it empty, is it STALE — stopped running, on the build that changed
        # it and on every build after.
        #
        # A check that cannot find its subject must not report success. The
        # component fetches /searchindex.json; a page that imports it wants
        # that file exactly as a hand-written fetch did.
        if "archive-kit/components/Search.astro" in src:
            wanted.add("searchindex.json")
    if not wanted:
        # This archive has a search page; no page fetching an index means the gate cannot
        # find its subject (the 22 September failure), and that must not read as success.
        sys.exit("check-search: REFUSED — no page under site/src/pages fetches a JSON index, "
                 "so nothing was examined. That is not a pass.")
    bad = []
    for rel in sorted(wanted):
        f = DIST / rel
        if not f.exists():
            bad.append(f"{rel} — fetched by a page, NOT PUBLISHED"); continue
        try:
            rows = json.loads(f.read_text(encoding="utf-8"))
            rows = rows.get("entries", []) if isinstance(rows, dict) else rows
            n = len(rows)
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
            # The estate's schema calls it `h`; this archive's old one called it
            # `url`. Both are read so the gate keeps working across the change
            # rather than going quiet on the build that makes it.
            _r = json.loads(f.read_text(encoding="utf-8"))
            _r = _r.get("entries", []) if isinstance(_r, dict) else _r
            urls = {e.get("h") or e.get("url", "") for e in _r}
        except Exception:
            urls = set()
        built, absent, noindexed = 0, [], []
        for page in sorted(DIST.rglob("index.html")):
            slug = "/" + str(page.parent.relative_to(DIST)).replace("\\", "/").strip(".")
            slug = "/" if slug in ("/.", "/") else slug.rstrip("/") + "/"
            # A page that noindexes itself (a living person's) is deliberately NOT in the index, and
            # being in it is the fault: the index is a public file and the page asked to be left out.
            is_noindex = bool(NOINDEX.search(page.read_text(encoding="utf-8", errors="ignore")))
            in_index = any(u.rstrip("/") + "/" == slug for u in urls)
            if is_noindex:
                if in_index:
                    noindexed.append(slug)
                continue
            built += 1
            if not any(u.rstrip("/") + "/" == slug or u.rstrip("/").endswith(slug.rstrip("/")) for u in urls):
                absent.append(slug)
        skip = {"/search/", "/404/"}
        absent = [a for a in absent if a not in skip]
        if noindexed:
            bad.append(f"{rel} — {len(noindexed)} page(s) that carry noindex are IN the index, first few {noindexed[:5]}")
        if absent:
            bad.append(f"{rel} — STALE: {len(absent)} of {built} built page(s) absent from the index, "
                       f"first few {absent[:5]} — the index describes a site that is no longer there")
        else:
            print(f"  ok    check-search — {rel} published, {n} entries, "
                  f"all {built} indexable page(s) represented, no noindex page in it")
    if bad:
        for b in bad:
            print(f"  FAIL  check-search — {b}")
        sys.exit(f"check-search: {len(bad)} problem(s)")

if __name__ == "__main__":
    main()
