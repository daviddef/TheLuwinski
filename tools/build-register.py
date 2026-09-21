#!/usr/bin/env python3
"""Turn the MyHeritage harvest into the site register.

Living-persons policy for this archive (set by David Defranceski, 14 Sep 2026):
  - Lynn Derrick Luwinski is NAMED, BARE. Name, birth year, parents. Nothing else.
  - Everyone else the source flags as living is OMITTED FROM THE BUILD ENTIRELY,
    unless they were born in 1920 or earlier and so would now be 106 or more, in
    which case they are presumed dead and published with the fact that no death
    is recorded stated plainly. Several of those are Holocaust-era people whose
    fate is unrecorded; saying so is the point of the entry.
  - Everyone else is dead and is narrated in full.
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "myheritage-tree9.json"
OUT = ROOT / "site" / "src" / "data" / "register.json"

NAMED_BARE = {9500003}          # Derrick

# Records the source holds twice for one person. Collapsed to the copy that
# carries both dates and parents. Keyed redundant -> canonical. These are not
# guesses: each pair shares an identical birth AND death date.
DUPLICATES = {
    9500151: 9500026,   # Georg Leibholz, dateless-parent copy
    9500150: 9500154,   # Leopold Leibke, dateless copy (and the only one flagged living)
    9500145: 9500104,   # Gertrud Leibke — the copy attached to Georg. The 1939 census
                        # puts her at Oskar's address, so the Oskar copy (9500104) is canonical.
    9500148: 9500152,   # Julius Leibke
    9500149: 9500153,   # Henriette Katz
}
# The two placeholder hubs the tree hangs its surname index from.
PLACEHOLDER_HUBS = {9500035, 9500036, 9500037, 9500039}

def year(s):
    m = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", s or "")
    return int(m.group(1)) if m else None

def main():
    people = json.load(open(SRC))
    by_id = {p["id"]: p for p in people}

    # Corrections: where a named source overrides the family record. The original
    # value is carried through as `was`, so nothing is silently rewritten.
    corr_path = ROOT / "data" / "corrections.json"
    corrections = json.load(open(corr_path))["corrections"] if corr_path.exists() else []
    by_person = {}
    for c in corrections:
        by_person.setdefault(c["id"], []).append(c)

    # Anyone descending from the placeholder hubs is a surname-index entry,
    # not a proven relative. Walk down from the hubs and mark them.
    index_only = set()
    frontier = set(PLACEHOLDER_HUBS)
    while frontier:
        nxt = set()
        for p in people:
            pid = p["id"]
            if pid in index_only or pid in PLACEHOLDER_HUBS:
                continue
            parents = {r["id"] for r in p["rel"] if "father" in r["rel"].lower() or "mother" in r["rel"].lower()}
            if parents & (frontier | PLACEHOLDER_HUBS | index_only):
                index_only.add(pid); nxt.add(pid)
        frontier = nxt
    # spouses of index-only people are index-only too
    for p in people:
        if p["id"] in index_only:
            for r in p["rel"]:
                if "wife" in r["rel"].lower() or "husband" in r["rel"].lower():
                    index_only.add(r["id"])
    index_only |= PLACEHOLDER_HUBS

    out, omitted, dropped = [], [], []
    for p in people:
        pid = p["id"]
        if pid in DUPLICATES:
            dropped.append((p["name"], pid, DUPLICATES[pid])); continue
        by_ = year(p["b"])
        presumed_dead = bool(by_) and by_ <= 1920
        if p["alive"] and pid not in NAMED_BARE and not presumed_dead:
            omitted.append(p["name"]); continue
        rec = {
            "id": pid, "name": p["name"], "first": p["first"], "last": p["last"],
            "sex": p["g"], "born": p["b"], "died": p["d"],
            "by": year(p["b"]), "dy": year(p["d"]),
            "kind": "index" if pid in index_only else "family",
        }
        if pid in NAMED_BARE:
            # Name only. No birth date, no birth YEAR, no death, no facts. The year is
            # a date of birth in disguise and is stripped with everything else.
            rec.update({"bare": True, "born": "", "died": "", "by": None, "dy": None,
                        "facts": [], "note": "Living. Named only, per the archive's policy."})
            rec["rel"] = [r for r in p["rel"] if "father" in r["rel"].lower() or "mother" in r["rel"].lower()]
        else:
            rec["facts"] = [f for f in p["facts"] if f["t"] and not f["t"].startswith(
                ("Birth of", "Death of", "Marriage of"))]
            rec["rel"] = [dict(r, ls="Living") if r["id"] in NAMED_BARE else r
                          for r in p["rel"]
                          if not by_id.get(r["id"], {}).get("alive") or r["id"] in NAMED_BARE]
            if p["alive"]:
                rec["no_death_recorded"] = True
        if pid in by_person:
            rec["corrections"] = by_person[pid]
            for c in by_person[pid]:
                if c["field"] == "died" and not rec.get("bare"):
                    rec["died"] = c["now"]
                    # AND THE DERIVED YEAR WITH IT. Until 22 September this line
                    # corrected the date and left `dy` holding the superseded year,
                    # so Kurt Israel Luwinski read "died 15 December 1968" on the
                    # register page and "1912 - 1969" on the bloodline, and the
                    # timeline placed him in the wrong year. A correction that does
                    # not reach the value the pages actually plot is not a correction.
                    rec["dy"] = year(c["now"])
                    # A correction that supplies a death CANCELS "no death recorded".
                    # Without this the register would print the absence and throw the
                    # corrected date away - the source flags the person alive, the
                    # template tests no_death_recorded first, and the correction loses.
                    # Not currently triggered by the data. Fixed before it is.
                    rec.pop("no_death_recorded", None)
                if c["field"] == "born" and not rec.get("bare"):
                    # Symmetrical, and not currently triggered by the data either.
                    # The `died` case was not triggered when it was written and it
                    # still shipped a wrong year onto two pages.
                    rec["born"] = c["now"]
                    rec["by"] = year(c["now"])
        out.append(rec)

    out.sort(key=lambda r: (r["last"] or "", r["first"] or ""))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"people": out,
               "duplicates": [{"name": n, "dropped": d, "kept": k} for n, d, k in dropped],
               "corrections": corrections,
               "counts": {"total": len(people), "published": len(out),
                          "omitted_living": len(omitted),
                          "duplicates_collapsed": len(dropped),
                          "family": sum(1 for r in out if r["kind"] == "family"),
                          "index": sum(1 for r in out if r["kind"] == "index")}},
              open(OUT, "w"), indent=1, ensure_ascii=False)
    print(f"published {len(out)}  family {sum(1 for r in out if r['kind']=='family')}"
          f"  surname-index {sum(1 for r in out if r['kind']=='index')}"
          f"  omitted living {len(omitted)}")
    for n in omitted: print("  omitted living:", n)
    for n, d, k in dropped: print(f"  duplicate collapsed: {n} ({d} -> {k})")

if __name__ == "__main__":
    main()
