#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The prose gate for living people: run the kit's checkprose.py over what this archive's authors type.

    python3 ../tools/check-prose.py                  # from site/ (what `npm run check:prose` and the build run)
    python3 ../tools/check-prose.py --require-tree   # a run without the harvest is a FAILURE, even in CI

checkprose.py (kit/tools) fails when a hand-written page, a hand-edited data file or a note puts a year, a date or
a life-event word (or a DNA result) beside a living person's name, or when a JSON record naming a living person
carries a field beyond the standard (name, relationships, full town and country). tools/check-living.py guards the
BUILT pages and the generated register; this guards what somebody typed.

THE FEED. Who is living is the kit's question (living_rule.py), answered here by tools/build-checkprose-feed.py
over the private harvest. The feed holds names, so it lives in private/ (gitignored) or at $CHECKPROSE_FEED, and is
rebuilt on every run so it is never stale.

THE SUBJECT. The subject of the archive is shown as he is now, by David's design (a stated exception). He is in the
feed like any living person; checkprose-allow.json, by id and with the reason, is the only thing that exempts him.

EXIT CODES. 0 passed. 1 failed. 2 NOT RUN: the harvest is not on this machine, so nobody can say who is living,
and "cannot say" is not "nobody is". On David's machine that stops the build. In CI (the environment variable CI
is set; GitHub Actions sets it) the step goes on and the log says, in capitals, that this gate did not run; the
CI workflow cannot hold the harvest, so the prose gate runs wherever the harvest is. --require-tree turns the
CI case into a failure too, as check-living.py's harvest mode does.

WHICH FILES (HAND_EDITED and GENERATED below). The kit reads, by default, site/src/pages, site/src/content, notes/,
docs/ and the top-level markdown; this adds the hand-EDITED data files, the research logs in data/, the letters in
requests/, exports/ and the layout (a sentence can be typed there). A data file that is in neither list FAILS the
gate, so that a new file has to be classified by someone who knows whether a person edits it or a script writes it.
notes/ is gitignored in this archive (it holds private working notes), so the kit, which reads only tracked files,
never sees it: those notes are outside this gate.
"""
import os, sys, json, argparse, subprocess, importlib.util, pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SITE = ROOT / "site"
CHECKPROSE = SITE / "node_modules" / "@daviddef" / "archive-kit" / "kit" / "tools" / "checkprose.py"
ALLOW = ROOT / "checkprose-allow.json"

# Data files a person edits (or a session appends to). A name here means the gate reads the file.
HAND_EDITED = {
    # site/src/data: the narrative pages' own content
    "site/src/data/book.json",               # the book's order, part titles, one-line blurbs and part introductions (17 Oct 2026)
    "site/src/data/autoclusters.json",       # a typed summary of a private export (match holders unnamed)
    "site/src/data/dna.json", "site/src/data/emigration.json", "site/src/data/english-people.json",
    "site/src/data/families.json",           # declarations for the family pages: tree-entry names, verbatim fragments, page lists
    "site/src/data/gedenkbuch.json", "site/src/data/letters.json", "site/src/data/lines.json",
    "site/src/data/litigation.json", "site/src/data/names.json", "site/src/data/negatives.json",
    "site/src/data/open-questions.json", "site/src/data/page-subjects.json", "site/src/data/searched.json",
    "site/src/data/segments.json", "site/src/data/sources.json", "site/src/data/tree.json",
    "site/src/data/wear-signature.json", "site/src/data/wear-emigration-bt27.tsv", "site/src/data/worklist.json",
    # data/: the archive's own records and corrections
    "data/corrections.json", "data/dna-ethnicity-derrick.json", "data/dna-segments.json",
    "data/register-documented.json", "data/superseded.json", "data/wear-signature.json",
    "data/names-aliases.json",               # forms of a name the data states for a person who has a page (18 Oct 2026)
    "data/living-year-allow.json",           # reviewed exceptions to the kit's printed-year gate, each with its reason (25 Oct 2026)
    "data/record-plates.json",               # which scans belong to which ledger entry, and whether the archive may show them
}

# Data files a script writes. Their generator's own scrub gate is the guard; scanning them here would only meet
# the homonyms of a family that reuses its names, and a fix would be undone by the next run of the generator.
GENERATED = {
    "site/src/data/register.json",           # tools/build-register.py, guarded by tools/check-living.py
    "site/src/data/evidence.json",           # tools/build-evidence.py, guarded by tools/check-evidence.py
    "site/src/data/names-index.json",        # tools/build-names-index.py (dead people with a page; checked against the register by check:names)
    "data/guarded-hashes.json",              # tools/make-guarded.py: salted digests, no names
    "data/labsa-catalogue.json",             # tools/labsa.py: the Landesarchiv's own catalogue of index volumes
    "site/src/data/records.json",            # tools/build-records.py: one row per ledger entry, scan or public address
    "site/src/data/era-places.json",         # tools/build-era.py, from data/era/ground.tsv and era/towns.tsv: place strings and a region id, no names
    "site/src/data/era-snapshot.json",       # tools/build-era.py --snapshot, from the Record Atlas's context contract: region eras and regime labels, no names
}

# Prose typed outside src/pages and notes/*.md: the layout (a sentence can be typed there), the research logs
# (hand-written tables of what was searched), the letters and requests the archive writes to record offices and
# researchers, and the exported scripts.
EXTRA_INCLUDE = ["site/src/layouts/**/*.astro", "data/**/*.tsv", "requests/**/*.md", "requests/**/*.txt",
                 "exports/**/*.md", "exports/**/*.txt"]
DATA_DIRS = ("site/src/data", "data")


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def tracked(*dirs):
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"] + list(dirs), capture_output=True, text=True)
    return sorted(f for f in r.stdout.split("\0") if f)


def classify():
    """Return (include list, problems). A tracked data file (json, or a tsv in site/src/data) in neither list fails.
    The tsv research logs in data/ are read by glob, so a new one is read without being listed."""
    problems = []
    names = [f for f in tracked(*DATA_DIRS)
             if os.path.dirname(f) in DATA_DIRS and not (os.path.dirname(f) == "data" and f.endswith(".tsv"))]
    for f in names:
        if f not in HAND_EDITED and f not in GENERATED:
            problems.append("%s is in neither HAND_EDITED nor GENERATED in tools/check-prose.py: say whether "
                            "a person edits it or a script writes it" % f)
    on_disk = set(tracked())
    for f in sorted((HAND_EDITED | GENERATED) - on_disk):
        problems.append("tools/check-prose.py lists %s, which is not a tracked file" % f)
    for f in sorted(HAND_EDITED & GENERATED):
        problems.append("%s is listed as both hand-edited and generated" % f)
    return sorted(HAND_EDITED), problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--require-tree", action="store_true",
                    help="a run without the harvest (nobody can say who is living) fails even in CI")
    ap.add_argument("--feed", help="where to write the feed (default: $CHECKPROSE_FEED or private/checkprose-feed.json)")
    ap.add_argument("--harvest")
    a = ap.parse_args(argv)

    if not CHECKPROSE.exists():
        print("checkprose: FAIL, the kit has no checkprose.py at %s (pin the kit at 26a4cba or later)" % CHECKPROSE)
        return 1
    include, problems = classify()
    if problems:
        print("checkprose: FAIL (%d)" % len(problems))
        for p in problems:
            print("  - " + p)
        return 1

    fb = load_module(HERE / "build-checkprose-feed.py", "build_checkprose_feed")
    feed, stats = fb.build(a.harvest)
    if feed is None:
        print("checkprose: NOT RUN (%s). The prose gate could not say who is living, so it checked nothing; "
              "this is NOT A PASS." % stats)
        if os.environ.get("CI") and not a.require_tree:
            print("checkprose: NOT RUN in CI, as check-living.py's harvest mode does not run there; it runs "
                  "wherever the private harvest is (David's machine)")
            return 0
        return 2

    out = fb.feed_path(a.feed)
    out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(out), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False)
    print("checkprose: feed has %d living people (%d names) and %d dead names" % (
        len(feed["living"]), sum(len(x["names"]) for x in feed["living"]), len(feed["deadNames"])))
    cmd = [sys.executable, str(CHECKPROSE), "--root", str(ROOT), "--feed", str(out)]
    for inc in include + EXTRA_INCLUDE:
        cmd += ["--include", inc]
    if ALLOW.exists():
        cmd += ["--allow", str(ALLOW)]
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    sys.exit(main())
