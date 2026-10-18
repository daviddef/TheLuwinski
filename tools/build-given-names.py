#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The given-name vocabulary for the linking standard (kit/tools/checkstandard.py, names.given_names_file).

    python3 ../tools/build-given-names.py            # from site/: writes site/given.json (gitignored, rebuilt every run)
    python3 ../tools/build-given-names.py --counts   # counts only

checkstandard reads a name-like phrase only if it holds a word the archive uses as a GIVEN name. The names index gives it the
given names of the people it lists; this adds the rest of the register's, so that a person read from a record whose given name
is in the register is seen.

WHERE IT COMES FROM. site/src/data/register.json and site/src/data/english-people.json, both committed, so CI builds the same
file as the machine that holds the harvest. A person the register flags `living` or `bare` (the named-only subject), and a
record that stands for nobody (`placeholder`), contributes NOTHING: a living person's given name is not written into a file
because they bear it. The words are the register's `first` field and the English line's given names, split into words. Counts
only are printed.
"""
import io, json, pathlib, re, sys, unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
OUT = SITE / "given.json"


def clean(s):
    return re.sub(r"\s+", " ", str(s or "").replace(" ", " ")).strip()


def words(s):
    out = []
    for w in clean(re.sub(r"\([^)]*\)", " ", s)).split():
        w = w.strip(".,;:'’\"“”")
        if len(w) >= 2 and w[0].isalpha() and w[0].isupper() and not re.search(r"\d", w):
            out.append(w)
    return out


def build():
    reg = json.load(io.open(SITE / "src" / "data" / "register.json", encoding="utf-8"))
    eng = json.load(io.open(SITE / "src" / "data" / "english-people.json", encoding="utf-8"))
    got, skipped = set(), 0
    for p in reg["people"]:
        if p.get("living") or p.get("bare") or p.get("placeholder") or "unknown" in (p.get("name") or "").lower():
            skipped += 1
            continue
        got.update(words(p.get("first") or ""))
    for p in eng["people"]:
        toks = words(p.get("name") or "")
        got.update(toks[:-1])
    return sorted(got, key=lambda s: unicodedata.normalize("NFKD", s).casefold()), skipped


def main(argv):
    words_, skipped = build()
    print("build-given-names: %d given-name words from the register and the English line (%d register records contribute nothing: "
          "living, named-only or a placeholder)" % (len(words_), skipped))
    if "--counts" in argv:
        return 0
    io.open(OUT, "w", encoding="utf-8").write(json.dumps(words_, ensure_ascii=False, indent=0) + "\n")
    print("build-given-names: wrote %s" % OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
