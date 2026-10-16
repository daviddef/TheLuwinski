#!/usr/bin/env python3
"""Write the guard digests the CI living-people check runs against.

Under the estate's standard, version 2 (16 October 2026) a living person is NAMED in this archive, with
their relationship and their town and country and nothing more, and has a page of their own that is
`noindex`. A possible minor is HELD OUT and appears nowhere at all. The gate therefore has to RECOGNISE
two groups of names in the built pages and served files, and CI does not hold the private harvest, so it
recognises them by salted SHA-256 digest:

  digests / living_ids         the living (kit living_rule.is_living), so that what stands with their
                               name can be tested;
  held_out_digests / held_out_ids   the held out (living_rule.is_held_out), so that their name and their
                               id can be shown to be absent.

The ids are local sequence numbers (9500xxx), not identifiers of anyone. A held-out id is recorded by id,
never by name.

This is obfuscation, not secrecy: the salt sits beside the digests, so anyone determined could test a
guess against them. That is accepted for the living, whose names are published in any case. For the
held out it means the digests prove nothing about WHO is held out beyond what a guess would confirm;
the names themselves are never in the repository.
"""
import json, pathlib, secrets, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import names
import people_decisions as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
HARVEST = ROOT / "data" / "myheritage-tree9.json"
OUT = ROOT / "data" / "guarded-hashes.json"


def digests_for(salt, p):
    out = []
    for variant in {p["name"], (p["first"] or "") + " " + (p["last"] or "")}:
        d = names.digest(salt, variant)
        if d:
            out.append(d)
    return out


def main():
    prev = json.load(open(OUT)) if OUT.exists() else {}
    salt = prev.get("salt") or secrets.token_hex(16)
    people = json.load(open(HARVEST))
    status = pd.classify(people)
    out, held_out, ids, held_ids, unguardable = [], [], [], [], []
    for p in people:
        s = status[p["id"]]
        if s == "living":
            ids.append(p["id"])
            got = digests_for(salt, p)
            out += got
            if not got:
                unguardable.append("id %s" % p["id"])
        elif s == "held_out":
            held_ids.append(p["id"])
            held_out += digests_for(salt, p)
    json.dump({"salt": salt, "algorithm": "sha256(salt|<first token> <last token>), particles dropped, first 32 hex",
               "rule": "kit living_rule: living = 80 or younger by year with no death or burial recorded and no public source; "
                       "held out = possible minor (not recorded dead, no public source, under 18 by year, or no birth year and a living parent)",
               "count": len(out), "digests": sorted(set(out)),
               "living_ids": sorted(ids),
               "held_out_ids": sorted(held_ids), "held_out_digests": sorted(set(held_out))},
              open(OUT, "w"), indent=1)
    print(f"guarded digests written: {len(set(out))}; living ids written: {len(ids)}; "
          f"held-out ids written: {len(held_ids)} with {len(set(held_out))} digests")
    if unguardable:
        print("NOT GUARDABLE by digest -- single-token names, which cannot be keyed")
        print("without matching ordinary words all over the site. These rely on the")
        print("full-harvest check run locally before every commit:")
        for n in unguardable:
            print("   ", n)

if __name__ == "__main__":
    main()
