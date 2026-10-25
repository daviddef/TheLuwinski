#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the feed the kit's prose gate (kit/tools/checkprose.py) reads: who is living, and who is dead.

    python3 tools/build-checkprose-feed.py                # writes private/checkprose-feed.json
    python3 tools/build-checkprose-feed.py --out PATH     # or $CHECKPROSE_FEED
    python3 tools/build-checkprose-feed.py --counts       # counts only, writes nothing

The feed holds living people's NAMES, so it is never committed: it is written under private/ (gitignored),
or wherever $CHECKPROSE_FEED / --out says, and the file is created readable by its owner only. This script
prints COUNTS only, never a name.

    {"living":    [{"id": "<harvest id>", "names": ["Given Family", ...]}, ...],
     "deadNames": ["Given Family", ...]}

WHO IS LIVING is not decided here. It is the kit's one definition (kit/tools/living_rule.py), reached the way
this archive's generator and its living gate reach it: tools/people_decisions.py classify(), over the private
MyHeritage harvest (data/myheritage-tree9.json, the only place a living person's birth year exists). The feed
holds three groups, all of whom a hand-written page must not describe beyond a name:

  * 'living'   everyone the rule calls living;
  * 'bare'     the SUBJECT of the archive. The rule calls him living, and he is. This archive shows him as he is
               now, by David's design (a stated exception), and that is recorded in checkprose-allow.json, by id,
               with the reason. NOTHING HERE exempts him: he is in the feed like any living person, so the
               allow file is the only thing that does, and it can be read and removed;
  * 'held_out' a possible minor. Published nowhere, so any date or detail beside such a name in a hand-written
               page is as wrong as for a living one. (Placeholder and single-word names cannot make a
               two-word phrase; the kit skips them and the counts say how many.)

Every recorded spelling goes in: the full name, the first and last name, each given name with the last name,
and a name written with a parenthesis (the married name beside the maiden name) in each of its readings.

WHO IS DEAD is decided by IDENTITY, never by "every name that is not a living name" (a living person and an
ancestor who share a name would then cancel each other out of the corpus; the kit skips and counts a name both
have, it does not guess). Dead names come from rows this archive records as dead:

  * every harvest record the rule does not call living or held out ('dead', and the 'duplicate' copies of a
    dead person that the register collapses);
  * the people the archive documented from a record (data/register-documented.json) that the rule does not
    call living;
  * the twenty ancestors of the English line (site/src/data/english-people.json), published as long dead.

Without the harvest this writes nothing and exits 2: "cannot say who is living" is not "nobody is".
"""
import os, sys, re, io, json, argparse, pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import people_decisions as pd                    # the archive's adapter to the kit's living_rule.py

HARVEST = ROOT / "data" / "myheritage-tree9.json"
DOCUMENTED = ROOT / "data" / "register-documented.json"
ENGLISH = ROOT / "site" / "src" / "data" / "english-people.json"
DEFAULT_FEED = ROOT / "private" / "checkprose-feed.json"
PARTICLES = {"da", "de", "del", "della", "di", "do", "dos", "du", "la", "le", "van", "von", "der", "den", "ten", "ter"}


def feed_path(explicit=None):
    return pathlib.Path(explicit or os.environ.get("CHECKPROSE_FEED") or DEFAULT_FEED)


def _clean(n):
    return re.sub(r"\s+", " ", str(n or "").replace("/", " ")).strip()


def spellings(p):
    """Every recorded spelling of one person, as plain 'Given Family' strings (two words at least)."""
    name, first, last = _clean(p.get("name")), _clean(p.get("first")), _clean(p.get("last"))
    out = {name, (first + " " + last).strip()}
    paren = re.findall(r"\(([^)]*)\)", name)
    bare = _clean(re.sub(r"\([^)]*\)", " ", name))
    out.add(bare)
    for x in paren:
        x = _clean(x)
        if not x:
            continue
        out.add((first + " " + x).strip())
        toks = bare.split()
        if toks:
            out.add(" ".join(toks[:-1] + [x]))          # the given names with the parenthesised surname
    # each given name beside the last name, and beside a parenthesised surname
    surnames = [last] + [_clean(x).split()[-1] for x in paren if _clean(x)]
    for g in first.split():
        if len(g) > 1 and g.lower() not in PARTICLES:
            for s in surnames:
                if s:
                    out.add(g + " " + s)
    return sorted(n for n in out if " " in n)


def build(harvest=None):
    """Return (feed, stats), or (None, reason) when the harvest is not on this machine."""
    path = pathlib.Path(harvest) if harvest else HARVEST
    if not path.exists():
        return None, "the private harvest (data/myheritage-tree9.json) is not on this machine"
    with io.open(path, encoding="utf-8") as f:
        people = json.load(f)
    if len(people) < 100:
        return None, "the harvest has %d people; refusing to decide who is living from that" % len(people)
    lr = pd.load_living_rule()
    status = pd.classify(people, lr)

    living, dead = {}, set()
    unsearchable = 0                                  # living / held out, but written with one word only
    stats = {"harvest people": len(people), "living": 0, "bare (the subject, in the feed like anyone living)": 0,
             "held out (possible minors)": 0, "dead rows": 0, "duplicate copies of dead rows": 0,
             "documented people": 0, "documented people the rule calls living": 0, "English-line ancestors": 0}
    for p in people:
        s = status[p["id"]]
        if s in ("living", "bare", "held_out"):
            key = {"living": "living", "bare": "bare (the subject, in the feed like anyone living)",
                   "held_out": "held out (possible minors)"}[s]
            stats[key] += 1
            living[str(p["id"])] = spellings(p)
            unsearchable += 0 if living[str(p["id"])] else 1
        else:
            stats["dead rows" if s == "dead" else "duplicate copies of dead rows"] += 1
            dead.update(spellings(p))
    if DOCUMENTED.exists():
        for d in json.load(io.open(DOCUMENTED, encoding="utf-8"))["people"]:
            stats["documented people"] += 1
            by = pd.year(d.get("born"))
            has_record = bool((d.get("died") or "").strip())          # a death date or place written out
            flag_only = (not has_record) and not d.get("no_death_recorded", False)   # the source says deceased, no more
            if lr.is_living(by, has_record, [], undated_dead=flag_only):
                stats["documented people the rule calls living"] += 1
                living[str(d["id"])] = spellings(d)
            else:
                dead.update(spellings(d))
    if ENGLISH.exists():
        for d in json.load(io.open(ENGLISH, encoding="utf-8"))["people"]:
            stats["English-line ancestors"] += 1
            dead.add(_clean(d.get("name")))
    dead = sorted(n for n in dead if n and " " in n)
    feed = {"living": [{"id": k, "names": v} for k, v in sorted(living.items()) if v], "deadNames": dead}

    sys.path.insert(0, str(ROOT / "site" / "node_modules" / "@daviddef" / "archive-kit" / "kit" / "tools"))
    try:
        import checkprose as cp
        lp, dp = set(), set()
        for x in feed["living"]:
            lp |= cp.phrases(x["names"])
        for n in dead:
            dp |= cp.phrases([n])
        stats["living phrases (two words or more)"] = len(lp)
        stats["living phrases shared with a dead person (skipped by the gate)"] = len(lp & dp)
        stats["living people with no two-word phrase (cannot be searched by name)"] = sum(
            1 for x in feed["living"] if not cp.phrases(x["names"])) + unsearchable
    except ImportError:
        pass
    stats["living people in the feed"] = len(feed["living"])
    stats["living names"] = sum(len(x["names"]) for x in feed["living"])
    stats["dead names"] = len(dead)
    return feed, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write the living / dead name feed for checkprose.py (counts only are printed).")
    ap.add_argument("--out")
    ap.add_argument("--harvest")
    ap.add_argument("--counts", action="store_true", help="print counts, write nothing")
    a = ap.parse_args(argv)
    feed, stats = build(a.harvest)
    if feed is None:
        print("build-checkprose-feed: not run: %s" % stats)
        return 2
    if not feed["living"] or not feed["deadNames"]:
        print("build-checkprose-feed: FAIL, %d living, %d dead names; refusing to write a feed that could pass on nothing" % (
            len(feed["living"]), len(feed["deadNames"])))
        return 1
    for k, v in stats.items():
        print("  %-66s %d" % (k, v))
    if a.counts:
        return 0
    out = feed_path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(out), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False)
    try:
        rel = out.resolve().relative_to(ROOT)
        print("build-checkprose-feed: wrote %s (names inside; gitignored, not for commit)" % rel)
    except ValueError:
        print("build-checkprose-feed: wrote the feed outside the repo (names inside)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
