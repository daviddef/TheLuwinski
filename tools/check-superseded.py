#!/usr/bin/env python3
"""Refuse to ship a build that still asserts a fact this archive has withdrawn.

On 27 September 2026 the 1874 Schubin marriage was re-read at the image and
two published facts fell: the date was December and not November, and the
mother's given name was neither of the two names anybody had read. The date
alone was asserted in TWELVE FILES.

They were corrected by hand, by grep, carefully, and the sweep was declared
complete. IT HAD MISSED THREE — data/corrections.json, site/src/data/negatives.json
and the register generated from the first of them — because the grep output was
read at a glance and those three matched deep inside long strings. A correction
that reaches the page a reader lands on and not the file underneath it is the
failure this archive keeps cataloguing, and doing it by eye is how it happens.

So the withdrawn values are DECLARED, in data/superseded.json, and every place
they may still legitimately appear is declared with them. Legitimate means one
of three things: the file is the correction itself, or it quotes the withdrawn
claim in order to withdraw it, or it is a dated record of what was believed or
sent at the time and is superseded in place rather than rewritten.

Anything else is a withdrawn fact still standing as a live assertion.

    python3 tools/check-superseded.py [--strict]

Without --strict a file that matches nothing at all is reported and passes:
a declaration whose 'was' string has vanished everywhere is stale, not fatal.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECL = os.path.join(ROOT, "data", "superseded.json")

# Where a live assertion can hide. Generated output (site/dist) is not scanned:
# it is rebuilt from these, so a hit there is a duplicate of a hit here.
SEARCH = ["data", "site/src", "requests", "tools"]
SKIP_DIRS = {"node_modules", ".git", "dist", "__pycache__"}
SKIP_EXT = {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".webp", ".ico", ".woff", ".woff2"}


def files():
    for base in SEARCH:
        root = os.path.join(ROOT, base)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith("dist")]
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() in SKIP_EXT:
                    continue
                yield os.path.join(dirpath, fn)


def rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, "/")


def main():
    strict = "--strict" in sys.argv
    if not os.path.exists(DECL):
        print("  ok    check-superseded — no data/superseded.json, nothing declared")
        return 0

    decl = json.load(open(DECL, encoding="utf-8"))
    facts = decl.get("facts", [])

    paths = sorted(files())
    texts = {}
    for p in paths:
        try:
            texts[p] = open(p, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue

    bad, stale, checked = [], [], 0
    for f in facts:
        allow = f.get("allow", {})
        hits_anywhere = 0
        for was in f.get("was", []):
            checked += 1
            for p, t in texts.items():
                if was not in t:
                    continue
                hits_anywhere += 1
                r = rel(p)
                if any(r == a or r.startswith(a) for a in allow):
                    continue
                n = t.count(was)
                bad.append((f["id"], was, r, n))
        if not hits_anywhere:
            stale.append(f["id"])

    if bad:
        print("  FAIL  check-superseded: %d withdrawn value(s) still asserted" % len(bad))
        for fid, was, where, n in bad:
            print("          %-28s %-24s %s (x%d)" % (fid, '"%s"' % was, where, n))
        print()
        print("        Either correct the file, or — if it quotes the withdrawn claim in order")
        print("        to withdraw it, or is a dated record superseded in place — add the path")
        print("        to that fact's 'allow' in data/superseded.json WITH A REASON.")
        return 1

    for fid in stale:
        print('  note  check-superseded — "%s" no longer appears anywhere; its declaration is stale' % fid)
    if stale and strict:
        return 1

    print("  ok    check-superseded — %d withdrawn value(s) across %d fact(s), none asserted in %d files"
          % (checked, len(facts), len(texts)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
