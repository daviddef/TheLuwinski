#!/usr/bin/env python3
"""Trove, the National Library of Australia, as an instrument this archive can control.

David's API key runs to December 2026. IT IS NOT IN THIS FILE AND MUST NEVER BE:
the key lives in notes/trove-key.txt, and notes/ is gitignored for the same reason
the DNA export is. Set TROVE_API_KEY to override.

WHY IT MATTERS HERE, AND IT IS ONE FACT: most Australian newspapers in Trove stop at
1954 for copyright, BUT THE CANBERRA TIMES IS DIGITISED TO 1995. The family was
forwarded c/o Mr H. MARQUARDT at HACKETT, ACT in 1965, and row 215 says what decides
that question is an address. A Canberra paper covering 1965 is the only free instrument
this archive has ever had that reaches it.

    python3 tools/trove.py "query" [--cat newspaper] [--n 20] [--decade 196]

Every search prints the TOTAL as well as the rows, because a total is what a control
is run against, and this archive does not read a zero it has not controlled.
"""
import json, os, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://api.trove.nla.gov.au/v3/result"


def key():
    k = os.environ.get("TROVE_API_KEY")
    if k:
        return k.strip()
    p = os.path.join(ROOT, "notes", "trove-key.txt")
    if os.path.exists(p):
        return open(p, encoding="utf-8").read().strip()
    sys.exit("no Trove key: set TROVE_API_KEY or write notes/trove-key.txt")


def search(q, category="newspaper", n=20, **extra):
    params = {"q": q, "category": category, "n": n, "encoding": "json"}
    params.update({k: v for k, v in extra.items() if v})
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"X-API-KEY": key(), "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def rows(d):
    """Flatten the v3 shape to (total, [records])."""
    out, total = [], 0
    for cat in d.get("category", []):
        recs = cat.get("records", {})
        total += int(recs.get("total", 0) or 0)
        for a in recs.get("article", []) or []:
            out.append(a)
        for a in recs.get("work", []) or []:
            out.append(a)
    return total, out


def line(a):
    t = a.get("heading") or a.get("title") or ""
    if isinstance(t, dict):
        t = t.get("value", "")
    return "%s | %s | %s | %s" % (
        (a.get("date") or "")[:10],
        (a.get("title", {}).get("title") if isinstance(a.get("title"), dict) else "")[:38],
        str(t)[:60],
        a.get("id", ""),
    )


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    q = args[0]
    kw = {}
    for i, a in enumerate(args):
        if a == "--cat":
            kw["category"] = args[i + 1]
        if a == "--n":
            kw["n"] = args[i + 1]
        if a == "--decade":
            kw["l-decade"] = args[i + 1]
    d = search(q, **kw)
    total, recs = rows(d)
    print("TOTAL %d for %r" % (total, q))
    for a in recs:
        print("  " + line(a))


def article(aid, kind="newspaper"):
    """Full text of one article. Trove NORMALISES spelling in search — Luwinski and
    Luwinsky return the identical result set — so the only way to know which spelling
    is on the page is to read the page."""
    url = "https://api.trove.nla.gov.au/v3/%s/%s?encoding=json&include=articletext" % (kind, aid)
    req = urllib.request.Request(url, headers={"X-API-KEY": key(), "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)
