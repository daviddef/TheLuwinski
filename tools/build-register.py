#!/usr/bin/env python3
"""Turn the MyHeritage harvest into the site register.

Living-persons policy for this archive (David Defranceski, 14 Sep 2026; the
second bullet replaced 16 Oct 2026 by the estate-wide standard):
  - Lynn Derrick Luwinski is NAMED, BARE. Name, parents. Nothing else, not even a
    town. He is the one exception to the standard below and is left exactly as
    he was.
  - Everyone else the source flags as living is NAMED, with their relationship to
    the people around them and their town and country, AND NOTHING MORE: no date
    of any kind (no birth year, no marriage or divorce date), no event, no
    record, no source, no note, no occupation, no photograph, no profile link,
    no cause of death. That is scrubbed HERE, at the source, so that nothing of
    it can reach a committed file. Born in 1920 or earlier means presumed dead
    (106 or more now), and those are published as before with the fact that no
    death is recorded stated plainly.
  - Everyone else is dead and is narrated in full.
THE TEST FOR "MIGHT BE ALIVE" IS UNCHANGED: flagged alive in the source, not
Derrick, not a collapsed duplicate, not born in 1920 or earlier.
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "myheritage-tree9.json"
DOCUMENTED = ROOT / "data" / "register-documented.json"
OUT = ROOT / "site" / "src" / "data" / "register.json"

# Who is living, who is Derrick and which records are duplicates: one definition, shared with
# the generator of the guard digests and with the gate (tools/livingtest.py).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import livingtest
from livingtest import NAMED_BARE, DUPLICATES

# The two placeholder hubs the tree hangs its surname index from.
PLACEHOLDER_HUBS = {9500035, 9500036, 9500037, 9500039}

year = livingtest.year

def qualifier(s):
    """How much the year() of a date string is actually worth.

    THE FAULT THIS FIXES. year() takes the FIRST four-digit year it finds and
    hands back a bare integer, and bloodline.astro prints that integer and
    timeline.astro PLOTS A POINT AT IT. So "Before 1955" was published as a
    death in 1955 and plotted there, when all the source says is that Joachim
    Luwinski was dead by then; "After May 13 1942" was published as a death in
    1942 when that date is the floor, not the event; and two "Circa" births
    were printed as exact years. FOUR BOUNDED OR APPROXIMATE DATES WERE ON THE
    SITE AS FACTS, and the register could not tell you which they were because
    the qualifier was thrown away at parse time.

    Returns None for a plain date, or one of 'circa', 'before', 'after',
    'range' — the word the page has to print if the number is not to lie.
    """
    v = (s or "").strip().lower()
    if not v:
        return None
    if re.search(r"\bbefore\b", v):
        return "before"
    if re.search(r"\bafter\b", v):
        return "after"
    if re.search(r"\b(circa|abt|about)\b", v):
        return "circa"
    ys = re.findall(r"\b(?:1[5-9]\d\d|20\d\d)\b", v)
    if len(ys) > 1 and int(max(ys)) != int(min(ys)):
        return "range"
    return None

# The countries the source writes as the LAST part of a place. A place is shown for a
# living person as «town, country» or «country» only; the parts in between (a county,
# a province) and anything with a digit in it (a street address) are dropped.
COUNTRIES = {"germany", "deutschland", "south africa", "poland", "polen", "polska",
             "portugal", "mozambique", "england", "united kingdom", "uk", "scotland",
             "wales", "austria", "australia", "united states", "usa", "namibia",
             "zimbabwe", "angola", "switzerland", "france", "netherlands", "israel",
             "canada", "new zealand", "brazil", "czech republic", "ireland"}

def living_place(p):
    """(town, country) for a living person, from their OWN birth fact and nothing else.

    The harvest holds no residence for anyone, so the only place that belongs to the
    person themself is where they were born. Facts about a spouse or a child (marriage
    to, death of, birth of son) carry their places and are never used. Returns
    ("", "") when there is nothing safe to show: a place with a digit in it reads as a
    street address and is dropped whole.
    """
    for f in p.get("facts", []):
        if f.get("t") != "Birth" or f.get("ty") != "BIRT" or not f.get("place"):
            continue
        parts = [x.strip() for x in f["place"].split(",") if x.strip()]
        if not parts or any(re.search(r"\d", x) for x in parts):
            return "", ""
        country = parts[-1] if parts[-1].lower() in COUNTRIES else ""
        town = parts[0] if (len(parts) >= 2 or not country) else ""
        if town and town == country:
            town = ""
        return town, country
    return "", ""

def living_note():
    return "Living. Named with relationship, town and country; nothing more, per the archive's standard."

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

    # Who is a living person under the standard. Computed first because a relative's
    # edge to a living person has to be scrubbed wherever it appears, not only in the
    # living person's own record.
    LIVING = {p["id"] for p in people if livingtest.might_be_alive(p)}
    protected = LIVING | NAMED_BARE

    def keep_edge(r):
        """Edges to a target that is flagged alive in the source are dropped, as they always
        were, EXCEPT where the target is a living person under the standard or Derrick.
        That leaves the unchanged behaviour for the two other kinds the source flags alive
        (collapsed duplicates and the presumed-dead aged 106 or more)."""
        return not by_id.get(r["id"], {}).get("alive") or r["id"] in protected

    def edge(r):
        """A relationship edge as published. If the person it points at is living, the
        source's `ls` field (a life span, «Born: 19xx») is replaced by the word Living."""
        return dict(r, ls="Living") if r["id"] in protected else r

    out, named_living, dropped = [], [], []
    for p in people:
        pid = p["id"]
        if pid in DUPLICATES:
            dropped.append((p["name"], pid, DUPLICATES[pid])); continue
        by_ = year(p["b"])
        presumed_dead = bool(by_) and by_ <= 1920
        if pid in LIVING:
            assert pid not in by_person, "a correction targets a living person: it would publish a date"
            town, country = living_place(p)
            named_living.append(pid)
            out.append({
                "id": pid, "name": p["name"], "first": p["first"], "last": p["last"],
                "sex": p["g"], "kind": "index" if pid in index_only else "family",
                "living": True,
                # No date of any kind, spelled out so a template reading these gets a blank.
                "born": "", "died": "", "by": None, "dy": None, "byq": None, "dyq": None,
                "facts": [],
                "town": town, "country": country,
                "place": ", ".join(x for x in (town, country) if x),
                "note": living_note(),
                "rel": [edge(r) for r in p["rel"] if keep_edge(r)],
            })
            continue
        rec = {
            "id": pid, "name": p["name"], "first": p["first"], "last": p["last"],
            "sex": p["g"], "born": p["b"], "died": p["d"],
            "by": year(p["b"]), "dy": year(p["d"]),
            "byq": qualifier(p["b"]), "dyq": qualifier(p["d"]),
            "kind": "index" if pid in index_only else "family",
        }
        if pid in NAMED_BARE:
            # Name only. No birth date, no birth YEAR, no death, no facts. The year is
            # a date of birth in disguise and is stripped with everything else.
            rec.update({"bare": True, "born": "", "died": "", "by": None, "dy": None,
                        "byq": None, "dyq": None,
                        "facts": [], "note": "Living. Named only, per the archive's policy."})
            rec["rel"] = [r for r in p["rel"] if "father" in r["rel"].lower() or "mother" in r["rel"].lower()]
        else:
            rec["facts"] = [f for f in p["facts"] if f["t"] and not f["t"].startswith(
                ("Birth of", "Death of", "Marriage of"))]
            # Living relatives are now kept, as an edge carrying a name, a relationship and
            # nothing else (see edge()). Until 16 Oct 2026 they were filtered out here.
            rec["rel"] = [edge(r) for r in p["rel"] if keep_edge(r)]
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
                    rec["dyq"] = qualifier(c["now"])
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
                    rec["byq"] = qualifier(c["now"])
        out.append(rec)

    # *** THE THIRD CLASS: PEOPLE THIS ARCHIVE ESTABLISHED FROM A DOCUMENT. ***
    # The register was built from the MyHeritage harvest alone, so a person found in a
    # Berlin civil register could not enter it at all -- and on 8 October the site was
    # telling readers that three Leibholz women simply vanish while their death entries
    # sat in data/. Adding them to the harvest file would have corrupted its provenance;
    # they get their own file, their own id block and their own label instead.
    # EVERY ONE CARRIES ITS OWN `basis`, and two of the seven say plainly that they are a
    # text layer not yet confirmed at the image. NONE IS PROVED KIN.
    documented = []
    if DOCUMENTED.exists():
        for d in json.load(open(DOCUMENTED))["people"]:
            rec = dict(d)
            rec["kind"] = "document"
            rec["by"], rec["dy"] = year(d.get("born")), year(d.get("died"))
            rec["byq"], rec["dyq"] = qualifier(d.get("born")), qualifier(d.get("died"))
            documented.append(rec)
        clash = {r["id"] for r in out} & {r["id"] for r in documented}
        assert not clash, "documented id collides with the harvest: %s" % clash
        out.extend(documented)

    out.sort(key=lambda r: (r["last"] or "", r["first"] or ""))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"people": out,
               "duplicates": [{"name": n, "dropped": d, "kept": k} for n, d, k in dropped],
               "corrections": corrections,
               "counts": {"total": len(people), "published": len(out),
                          "living_named": len(named_living),
                          "living_with_town": sum(1 for r in out if r.get("town")),
                          "living_country_only": sum(1 for r in out if r.get("living") and r.get("country") and not r.get("town")),
                          "living_no_place": sum(1 for r in out if r.get("living") and not r.get("place")),
                          "duplicates_collapsed": len(dropped),
                          "family": sum(1 for r in out if r["kind"] == "family"),
                          "index": sum(1 for r in out if r["kind"] == "index"),
                          "document": sum(1 for r in out if r["kind"] == "document")}},
              open(OUT, "w"), indent=1, ensure_ascii=False)
    print(f"published {len(out)}  family {sum(1 for r in out if r['kind']=='family')}"
          f"  surname-index {sum(1 for r in out if r['kind']=='index')}"
          f"  documented-from-record {sum(1 for r in out if r['kind']=='document')}"
          f"  living named {len(named_living)}")
    # Counts only: a living person's name is not printed into a build log.
    for n, d, k in dropped: print(f"  duplicate collapsed: {n} ({d} -> {k})")

if __name__ == "__main__":
    main()
