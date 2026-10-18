#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The living list for the build-time name linker: every living or held-out person, as names and page addresses.

    python3 tools/build-living-list.py                      # private/living.json, from the private feed AND the register
    python3 tools/build-living-list.py --public --out PATH  # CI: from the committed register only
    python3 tools/build-living-list.py --counts             # counts only, writes nothing

kit/tools/autolink.py and checklinks.py take it as --living. They refuse to run (exit 2) if the names index holds a name or
an address that this list also holds, they will not link a dead name that overlaps a living one, and the gate fails any
autolink anchor to a living address. It is a safety net behind tools/build-names-index.py, which already leaves every
living person out of the index.

WHO IS ON IT is not decided here. Two sources, both the archive's own:
  * the register (site/src/data/register.json), where tools/build-register.py wrote `living` (four people) and `bare` (the
    named-only subject) from the kit's one definition (kit/tools/living_rule.py): each one's name, every form of it, and the
    address of their page (/people/<slug>/);
  * the private feed (private/checkprose-feed.json, written by tools/build-checkprose-feed.py over the private harvest):
    every living, named-only and HELD-OUT person by every recorded spelling. The held-out have no page and are in no
    register, so this is the only place they are. A bare given name is never a name here (one word is skipped).

WHERE IT GOES. It holds living people's names, so it is never committed: the default is private/ (gitignored), mode 0600.
--out may name another place; refuse anywhere inside the tracked tree that is not gitignored.

TWO MODES, and the second is the weaker:
  default   needs the private feed. Without it the script exits 2 ("cannot say who is living" is not "nobody is"), so a run on
            David's machine is never quietly the weaker one.
  --public  the register alone. This is what CI runs: the deploy runner does not hold the harvest. It covers every living
            person the site names (all five flagged in the committed register) and not a held-out person, who is published
            nowhere and so cannot be in the committed index in the first place (the index is built from the register).
It prints counts only, never a name.
"""
import os, sys, io, json, argparse, pathlib, subprocess, importlib.util

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
REGISTER = ROOT / "site" / "src" / "data" / "register.json"
FEED = pathlib.Path(os.environ.get("CHECKPROSE_FEED") or ROOT / "private" / "checkprose-feed.json")
DEFAULT_OUT = ROOT / "private" / "living.json"


def _bni():
    spec = importlib.util.spec_from_file_location("bni", str(HERE / "build-names-index.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def safe_out(path):
    """Refuse a path inside the repository that git would track."""
    p = pathlib.Path(path).resolve()
    try:
        rel = p.relative_to(ROOT)
    except ValueError:
        return True
    r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", str(rel)], capture_output=True)
    return r.returncode == 0


def build(public):
    bni = _bni()
    reg = json.load(io.open(REGISTER, encoding="utf-8"))
    names, urls = set(), set()
    n_reg = 0
    for p in reg["people"]:
        if p.get("living") or p.get("bare"):
            n_reg += 1
            urls.add("/people/%s/" % p["slug"])
            for f in bni.register_forms(p):
                names.add(f)
            if p.get("name"):
                names.add(bni.clean(p["name"]))
    n_feed = 0
    if not public:
        if not FEED.exists():
            return None, "the private feed (%s) is not on this machine, so nobody can say who is held out; use --public only in CI" % FEED.name
        feed = json.load(io.open(FEED, encoding="utf-8"))
        if not feed.get("living"):
            return None, "the private feed lists nobody living; refusing a living list that could pass on nothing"
        for x in feed["living"]:
            n_feed += 1
            for n in x.get("names", []):
                if len(bni.clean(n).split()) >= 2:
                    names.add(bni.clean(n))
    if not urls:
        return None, "the register flags nobody living; refusing a living list that could pass on nothing"
    out = {"names": sorted(names, key=lambda s: s.casefold()), "urls": sorted(urls)}
    return out, {"register people flagged living or named-only": n_reg, "private-feed people (living, named-only, held out)": n_feed,
                 "living names and spellings (two words or more)": len(out["names"]), "living page addresses": len(out["urls"])}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--public", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--counts", action="store_true")
    a = ap.parse_args(argv)
    out, stats = build(a.public)
    if out is None:
        print("build-living-list: NOT WRITTEN: %s" % stats)
        return 2
    for k, v in stats.items():
        print("  %-62s %d" % (k, v))
    print("  %-62s %s" % ("mode", "public (register only)" if a.public else "full (register and private feed)"))
    if a.counts:
        return 0
    dest = pathlib.Path(a.out) if a.out else DEFAULT_OUT
    if not safe_out(dest):
        print("build-living-list: REFUSED: %s is inside the repository and not gitignored; this file holds living people's names" % dest)
        return 2
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(dest), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print("build-living-list: wrote the living list (names inside; not for commit)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
