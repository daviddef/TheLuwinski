#!/usr/bin/env python3
"""Write the guarded-name digests the CI living-persons check runs against.

The repository is public, so the list of people to keep OUT of it cannot itself
be in it in plaintext. This writes salted SHA-256 digests of the omitted living
people's names instead.

This is obfuscation, not secrecy: the salt sits beside the digests, so anyone
determined could test a guess against them. That is accepted. The purpose is
that the names are not *published* here, and that CI can still verify the build
without being handed them.
"""
import json, pathlib, re, secrets, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import names

ROOT = pathlib.Path(__file__).resolve().parent.parent
HARVEST = ROOT / "data" / "myheritage-tree9.json"
OUT = ROOT / "data" / "guarded-hashes.json"

ALLOWED = {9500003}
DUPLICATES = {9500151, 9500150, 9500104, 9500148, 9500149}
PRESUMED_DEAD_BY = 1920

def year(s):
    m = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", s or "")
    return int(m.group(1)) if m else None

def main():
    prev = json.load(open(OUT)) if OUT.exists() else {}
    salt = prev.get("salt") or secrets.token_hex(16)
    people = json.load(open(HARVEST))
    out, unguardable = [], []
    for p in people:
        if not p["alive"] or p["id"] in ALLOWED or p["id"] in DUPLICATES:
            continue
        by = year(p["b"])
        if by and by <= PRESUMED_DEAD_BY:
            continue
        if "unknown" in (p["name"] or "").lower():
            continue
        got = False
        for variant in {p["name"], (p["first"] or "") + " " + (p["last"] or "")}:
            d = names.digest(salt, variant)
            if d:
                out.append(d); got = True
        if not got:
            unguardable.append(p["name"])
    json.dump({"salt": salt, "algorithm": "sha256(salt|<first token> <last token>), particles dropped, first 32 hex",
               "count": len(out), "digests": sorted(set(out))},
              open(OUT, "w"), indent=1)
    print(f"guarded digests written: {len(set(out))}")
    if unguardable:
        print("NOT GUARDABLE by digest — single-token names, which cannot be keyed")
        print("without matching ordinary words all over the site. These rely on the")
        print("full-harvest check run locally before every commit:")
        for n in unguardable:
            print("   ", n)

if __name__ == "__main__":
    main()
