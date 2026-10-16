#!/usr/bin/env python3
"""Write the guarded-name digests the CI living-persons check runs against.

Since 16 October 2026 a living person is NAMED in this archive, with their relationship and
their town and country and nothing more (tools/build-register.py). The gate therefore no longer
asks «is this name absent?» but «is this name only ever shown as a name?». It still needs to
RECOGNISE the names in the built pages, and CI does not hold the private harvest, so it
recognises them by salted SHA-256 digest, exactly as before. It also needs to know WHICH
register records are the living ones, so their ids are written too: an id is a local sequence
number (9500xxx), not an identifier of anyone, and the register already carries it.

This is obfuscation, not secrecy: the salt sits beside the digests, so anyone determined could
test a guess against them. That is accepted: the names are now published in any case, but the
digests are what lets CI find them in the rendered pages and test what stands beside them.
"""
import json, pathlib, re, secrets, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import names

ROOT = pathlib.Path(__file__).resolve().parent.parent
HARVEST = ROOT / "data" / "myheritage-tree9.json"
OUT = ROOT / "data" / "guarded-hashes.json"

import livingtest

def main():
    prev = json.load(open(OUT)) if OUT.exists() else {}
    salt = prev.get("salt") or secrets.token_hex(16)
    people = json.load(open(HARVEST))
    out, unguardable, ids = [], [], []
    for p in people:
        if not livingtest.might_be_alive(p):
            continue
        ids.append(p["id"])
        if "unknown" in (p["name"] or "").lower():
            continue
        got = False
        for variant in {p["name"], (p["first"] or "") + " " + (p["last"] or "")}:
            d = names.digest(salt, variant)
            if d:
                out.append(d); got = True
        if not got:
            unguardable.append("id %s" % p["id"])
    json.dump({"salt": salt, "algorithm": "sha256(salt|<first token> <last token>), particles dropped, first 32 hex",
               "count": len(out), "digests": sorted(set(out)),
               "living_ids": sorted(ids)},
              open(OUT, "w"), indent=1)
    print(f"guarded digests written: {len(set(out))}; living ids written: {len(ids)}")
    if unguardable:
        print("NOT GUARDABLE by digest — single-token names, which cannot be keyed")
        print("without matching ordinary words all over the site. These rely on the")
        print("full-harvest check run locally before every commit:")
        for n in unguardable:
            print("   ", n)

if __name__ == "__main__":
    main()
