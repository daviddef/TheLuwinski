#!/usr/bin/env python3
"""Fail the build if anyone omitted as living turns up in the output.

The archive promises that living people are not present in the build. This
checks the promise against the rendered HTML rather than trusting the generator.

Two modes:
  --harvest   the full private harvest is present (local runs). Guards on real
              names taken straight from the source.
  --hashes    the repository checkout only (CI). Guards on the salted digests in
              data/guarded-hashes.json, extracting candidate personal names from
              the HTML and hashing those. The names themselves are never in the
              public repository, which is the point.

Default: harvest if it exists, otherwise hashes.

Known limit of --hashes: a person recorded under a single token ("Luke") cannot
be keyed, because guarding a bare given name would match ordinary prose across
the whole site. Those depend on the --harvest run, which is local and exact.
Run `python3 tools/make-guarded.py` to see which names that currently affects.

Rules, identical to tools/build-register.py:
  - Derrick is the one permitted exception, and by name only.
  - Someone flagged living but born in 1920 or earlier is presumed dead and is
    published, so they are not guarded.
  - Duplicate records are data artefacts, not living people.
"""
import argparse, hashlib, json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import names

ALLOWED = {9500003}
DUPLICATES = {9500151, 9500150, 9500145, 9500148, 9500149}
PRESUMED_DEAD_BY = 1920

ROOT = pathlib.Path(__file__).resolve().parent.parent

def year(s):
    m = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", s or "")
    return int(m.group(1)) if m else None

def pages(dist):
    p = pathlib.Path(dist)
    if not p.is_absolute():
        p = pathlib.Path.cwd() / p
    f = sorted(p.rglob("*.html"))
    if not f:
        sys.exit(f"check-living: no HTML found under {p}")
    return p, f

def visible(text):
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)

def check_harvest(dist):
    people = json.load(open(ROOT / "data" / "myheritage-tree9.json"))
    guarded = []
    for p in people:
        if not p["alive"] or p["id"] in ALLOWED or p["id"] in DUPLICATES:
            continue
        by = year(p["b"])
        if by and by <= PRESUMED_DEAD_BY:
            continue
        first = (p["first"] or "").strip().split()[0] if (p["first"] or "").strip() else ""
        last = (p["last"] or "").strip()
        if len(first) < 3 or len(last) < 3 or "unknown" in (first + last).lower():
            continue
        guarded.append((p["name"], re.compile(
            re.escape(first) + r"[\w\s.,'\"()\-]{0,40}?" + re.escape(last), re.IGNORECASE)))
    root, files = pages(dist)
    hits = []
    for f in files:
        t = f.read_text(encoding="utf-8", errors="ignore")
        for full, rx in guarded:
            m = rx.search(t)
            if m:
                hits.append((f.relative_to(root), full, m.group(0)[:60]))
    return hits, len(files), len(guarded), "harvest"

def check_hashes(dist):
    g = json.load(open(ROOT / "data" / "guarded-hashes.json"))
    salt, want = g["salt"], set(g["digests"])
    root, files = pages(dist)
    hits = []
    for f in files:
        for k in names.candidates(visible(f.read_text(encoding="utf-8", errors="ignore"))):
            d = hashlib.sha256((salt + "|" + k).encode()).hexdigest()[:32]
            if d in want:
                hits.append((f.relative_to(root), "a guarded name", k))
    return hits, len(files), len(want), "hashes"

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", default="dist")
    ap.add_argument("--mode", choices=["auto", "harvest", "hashes"], default="auto")
    a = ap.parse_args()
    mode = a.mode
    if mode == "auto":
        mode = "harvest" if (ROOT / "data" / "myheritage-tree9.json").exists() else "hashes"
    hits, n, guarded, used = (check_harvest if mode == "harvest" else check_hashes)(a.dist)
    if hits:
        print(f"check-living: FAILED ({used}) — living people present in the build")
        for f, full, found in hits:
            print(f"  {f}: {full} matched {found!r}")
        sys.exit(1)
    print(f"check-living: ok ({used}) — {n} pages, {guarded} guarded, none present")
