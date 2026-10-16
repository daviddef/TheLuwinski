#!/usr/bin/env python3
"""Turn the MyHeritage harvest into the site register.

Living-persons policy for this archive: the estate's standard, version 2 (David Defranceski,
16 October 2026).
  - WHO IS LIVING is decided by the kit's one definition (kit/tools/living_rule.py), not by a test of
    this archive's own: born 80 years ago or less (by year) with no death or burial recorded and no
    public source. A person with no birth year cannot be shown to be that young, so is not living.
  - A living person is NAMED, with their relationship to the people around them and their town and
    country, AND NOTHING MORE: no date of any kind (no birth year, no marriage or divorce date), no
    event, no record, no source, no note, no occupation, no photograph, no profile link, no cause of
    death. That is scrubbed HERE, at the source, so that nothing of it can reach a committed file.
    Every person in the register has a page; a living person's is noindex.
  - Lynn Derrick Luwinski is NAMED, BARE. Name, parents. Nothing else, not even a town. He is the one
    exception (standard, point 9) and is left exactly as he was.
  - HELD OUT, published nowhere (no record, no page, no name as anyone's relative): a possible minor
    (not recorded dead, no public source, no birth year, and a living parent; a child with a known birth
    year is NOT held out and is living under the standard) and
    anyone promised privacy by id (none here). Computed, not hand-listed.
  - Everyone else is not living and is narrated in full.
THE OLD TEST (flagged alive in the source, not born in 1920 or earlier) IS GONE. It called ten people
living; the kit's rule calls four, because five have no birth year and one is over 80.
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "myheritage-tree9.json"
DOCUMENTED = ROOT / "data" / "register-documented.json"
OUT = ROOT / "site" / "src" / "data" / "register.json"

# Who is living and who is held out: the kit's rule, through tools/people_decisions.py, which also holds
# the two facts the kit cannot know (Derrick, and the records the source holds twice).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import people_decisions as pd
from people_decisions import NAMED_BARE, DUPLICATES

# The two placeholder hubs the tree hangs its surname index from.
PLACEHOLDER_HUBS = {9500035, 9500036, 9500037, 9500039}

year = pd.year

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

# A part of a birth place that is NOT a town or a country: an institution (a hospital, a care home,
# a clinic) or a street. «Full town» means the town or city (standard, point 5), never a street, an
# address-like string or an institution, so such a part is dropped and what is left is read as before.
NOT_A_TOWN = re.compile(
    r"hospital|hospice|clinic|infirmary|maternity|nursing|care\s*home|retirement|sanatorium|asylum|"
    r"medical|\bhome\b|\bcentre\b|\bcenter\b|\bprison\b|\bstreet\b|\bstr\b|\bstr\.|stra(ss|ß)e|"
    r"\broad\b|\bavenue\b|\bave\b|\blane\b|\bdrive\b|\brua\b|\bavenida\b|\bp\.?\s?o\.?\s?box\b", re.I)

def living_place(p):
    """(town, country) for a living person, from their OWN birth fact and nothing else.

    The harvest holds no residence for anyone, so the only place that belongs to the
    person themself is where they were born. Facts about a spouse or a child (marriage
    to, death of, birth of son) carry their places and are never used. Parts with a digit
    in them (a street number), and parts that are an institution or a street, are dropped;
    what remains is the town and the country. Returns ("", "") when nothing safe remains.
    """
    for f in p.get("facts", []):
        if f.get("t") != "Birth" or f.get("ty") != "BIRT" or not f.get("place"):
            continue
        parts = [x.strip() for x in f["place"].split(",") if x.strip()]
        parts = [x for x in parts if not re.search(r"\d", x) and not NOT_A_TOWN.search(x)]
        if not parts:
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

    # Who is living, who is held out, who is neither: the kit's rule (tools/people_decisions.py ->
    # kit/tools/living_rule.py). Computed first because a relative's edge to a living person has to be
    # scrubbed wherever it appears, not only in the living person's own record, and an edge to a held-out
    # person has to go from every record that names them.
    lr = pd.load_living_rule()
    status = pd.classify(people, lr)
    LIVING = {i for i, v in status.items() if v == "living"}
    HELD = {i for i, v in status.items() if v == "held_out"}
    protected = LIVING | NAMED_BARE

    def edges_of(p):
        """The relationship edges of one record as published.
          - an edge to a HELD-OUT person is dropped: they are published nowhere, not even as a name;
          - an edge to a record the source holds twice is pointed at the copy that is kept (and an
            edge that would then point at the person themself, or repeat one already there, goes);
          - an edge to a living person (or Derrick) carries the word Living where the source gave a
            life span («Born: 19xx») that would be a date of birth;
          - on the record of a LIVING person (or Derrick) the source's life span for a DEAD relative is
            dropped too: it is the relative's date, but it would stand inside the living person's own
            record, and no page reads it;
          - every other edge is kept, as it was, to a person who now has a page of their own."""
        seen, out_ = set(), []
        owner_protected = p["id"] in protected
        for r in p["rel"]:
            tid = DUPLICATES.get(r["id"], r["id"])
            if tid in HELD or tid == p["id"] or tid not in by_id:
                continue
            e = dict(r, id=tid)
            if tid != r["id"]:
                e["n"] = by_id[tid]["name"]
                e.pop("ls", None)
            if tid in protected:
                e["ls"] = "Living"
            elif owner_protected:
                e.pop("ls", None)
            if (tid, e["rel"]) in seen:
                continue
            seen.add((tid, e["rel"]))
            out_.append(e)
        return out_

    out, named_living, dropped, held = [], [], [], []
    for p in people:
        pid = p["id"]
        if pid in DUPLICATES:
            dropped.append((p["name"], pid, DUPLICATES[pid])); continue
        if pid in HELD:
            held.append(pid); continue
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
                "rel": edges_of(p),
            })
            continue
        rec = {
            "id": pid, "name": p["name"], "first": p["first"], "last": p["last"],
            "sex": p["g"], "born": p["b"], "died": p["d"],
            "by": year(p["b"]), "dy": year(p["d"]),
            "byq": qualifier(p["b"]), "dyq": qualifier(p["d"]),
            "kind": "index" if pid in index_only else "family",
        }
        if pid in PLACEHOLDER_HUBS or "unknown" in (p["name"] or "").lower():
            # A record that stands for nobody: the hub the surname index hangs from, or a parent the
            # source could only call «Unknown». It keeps its page (David, 16 Oct 2026) and the page says so.
            rec["placeholder"] = True
        if pid in NAMED_BARE:
            # Name only. No birth date, no birth YEAR, no death, no facts. The year is
            # a date of birth in disguise and is stripped with everything else.
            rec.update({"bare": True, "born": "", "died": "", "by": None, "dy": None,
                        "byq": None, "dyq": None,
                        "facts": [], "note": "Living. Named only, per the archive's policy."})
            rec["rel"] = [r for r in edges_of(p) if "father" in r["rel"].lower() or "mother" in r["rel"].lower()]
        else:
            rec["facts"] = [f for f in p["facts"] if f["t"] and not f["t"].startswith(
                ("Birth of", "Death of", "Marriage of"))]
            # Living relatives are kept, as an edge carrying a name, a relationship and
            # nothing else (see edges_of()).
            rec["rel"] = edges_of(p)
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
    assign_slugs(out)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"people": out,
               "duplicates": [{"name": n, "dropped": d, "kept": k} for n, d, k in dropped],
               "corrections": corrections,
               # `total` is the people the source tree holds that are PUBLISHED or collapsed as a duplicate.
               # A held-out person (a possible minor, or promised privacy) is not counted anywhere that is
               # published, so that nobody can be derived from a gap between two numbers.
               "counts": {"total": len(people) - len(held), "published": len(out),
                          "living_named": len(named_living),
                          "living_with_town": sum(1 for r in out if r.get("living") and r.get("town")),
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
          f"  living named {len(named_living)}  held out {len(held)} (not published)")
    # Counts only: a living person's name is not printed into a build log.
    for n, d, k in dropped: print(f"  duplicate collapsed: {n} ({d} -> {k})")

def fold_slug(name):
    """A page address from a name: ASCII, lower case, hyphens, at most 80 characters."""
    import unicodedata
    t = unicodedata.normalize("NFD", name or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:80].strip("-")
    return t or "person"

def assign_slugs(records):
    """Every record gets the address of its own page, /people/<slug>/. Unique across the register AND the
    twenty hand-written pages of the English line that share the route. A name shared by two people gets
    the id appended to both, so neither is the other's address."""
    taken = set()
    eng = ROOT / "site" / "src" / "data" / "english-people.json"
    if eng.exists():
        taken |= {x["slug"] for x in json.load(open(eng))["people"]}
    taken.add("index")
    base = {}
    for r in records:
        base.setdefault(fold_slug(r["name"]), []).append(r)
    for slug, group in base.items():
        if len(group) == 1 and slug not in taken:
            group[0]["slug"] = slug
        else:
            for r in group:
                r["slug"] = f"{slug}-{r['id']}"
    assert len({r["slug"] for r in records}) == len(records), "slug collision"
    assert not ({r["slug"] for r in records} & taken), "a slug collides with the English line"

if __name__ == "__main__":
    main()
