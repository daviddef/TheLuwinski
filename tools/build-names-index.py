#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The names index for the build-time name linker (kit/tools/autolink.py): which written names are one dead person with a page.

    python3 tools/build-names-index.py            # writes site/src/data/names-index.json
    python3 tools/build-names-index.py --check    # fails if the committed file is not what the data gives (or not safe)
    python3 tools/build-names-index.py --counts   # prints counts only, writes nothing

WHERE IT COMES FROM. Only site/src/data/register.json and site/src/data/english-people.json, the two files that already
draw every /people/<slug>/ page, and both committed. The index holds nobody who has no public page and nobody who is
living, so it is safe to commit (it is committed, so the deploy links exactly what was checked here).

WHO IS IN IT ("people"). A form of a name that is borne by exactly ONE person in the whole archive's data, where that
person
  * has an indexable /people/<slug>/ page (a register person who is not living, not the named-only subject, not a
    placeholder; or an English-line ancestor),
  * has a death recorded (a register person with `no_death_recorded` is not known to be dead, so is never linked). ONE
    EXCEPTION, for a person the archive read from a document (kind `document`): a birth year of 1900 or earlier that the
    document states (a person of 126 or more) is shown dead by the date alone, so that person may be linked although no
    death was found. Nobody else gets that: a tree person with no death recorded and an old birth year stays unlinked,
  * and shares that form with nobody else: not a living person, not a held-out person (the private feed, when this
    machine has it), not a person with no death recorded, not a second dead person.
A form borne by two or more DEAD people who all have pages is "ambiguous": it goes to /search/?q=<name>, the archive's own
search page, which reads ?q= and ranks the people pages on the name. A form that any living, held-out or not-known-dead
person also bears is left out altogether (the kit: "link such a name to the disambiguation address or not at all").

THE FORMS (the archive's own data and nothing invented):
  * the name as the register writes it, with a parenthesised surname taken out ("Given Maiden (Married)" gives "Given Maiden");
  * the same with the parenthesised surname in place of the last name ("Given Married");
  * the first given name beside the register's `last` field, where the name carries more given names;
  * for the English line the name as written in english-people.json;
  * the forms in data/names-aliases.json, each with the record that says the two names are one person (a person who
    already has a page; the generator refuses a slug that is not one, and every form goes through the same filters).
A form is dropped if it is one word, begins "Unknown", or carries a character that no name has (a slash, a comma, a
quotation mark, a digit, the word "or": the register keeps some of the harvest's own muddle in a name). Never a bare given name.

THE LIVING SAFETY NET is a second file, tools/build-living-list.py, written outside the tree. This script never reads
a living person's name into the committed index: it reads the register, where the four living people and the named-only
subject are flagged, and the private feed (private/checkprose-feed.json) when it is on the machine, where the living and
the held-out are listed by every spelling. Without the feed it still excludes every register person flagged living; it
says so, and --check in CI is therefore the weaker, public half of the same test.
"""
import os, sys, re, io, json, argparse, pathlib, unicodedata

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SITE = ROOT / "site"
REGISTER = SITE / "src" / "data" / "register.json"
ENGLISH = SITE / "src" / "data" / "english-people.json"
OUT = SITE / "src" / "data" / "names-index.json"
FEED = pathlib.Path(os.environ.get("CHECKPROSE_FEED") or ROOT / "private" / "checkprose-feed.json")
BLOCKERS = HERE / "autolink-blockers.json"
ALIASES = ROOT / "data" / "names-aliases.json"
DOC_DEAD_BY = 1900          # a document person born in or before this year is shown dead by the date alone
PARTICLES = {"da", "de", "del", "della", "di", "do", "dos", "du", "la", "le", "van", "von", "der", "den", "ten", "ter"}
BAD = re.compile(r"[/,\"“”()\d]|\bor\b|\band\b|\?", re.I)


def clean(s):
    return re.sub(r"\s+", " ", str(s or "").replace(" ", " ")).strip()


def fold(s):
    s = unicodedata.normalize("NFKD", clean(s))
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


def ok_form(f):
    f = clean(f)
    if len(f.split()) < 2 or f.lower().startswith("unknown") or BAD.search(f):
        return False
    return all(len(t.strip(".'’-")) >= 1 for t in f.split())


def register_forms(p):
    """Every form of one register person, as plain strings (before the safety filters)."""
    name = clean(p.get("name"))
    paren = [clean(x) for x in re.findall(r"\(([^)]*)\)", name) if clean(x)]
    bare = clean(re.sub(r"\([^)]*\)", " ", name))
    out = [bare]
    toks = bare.split()
    for x in paren:
        out.append(" ".join(toks[:-1] + [x]))
    first, last = clean(p.get("first")), clean(p.get("last"))
    if first and last:
        g = first.split()[0]
        out.append(g + " " + last)
        for x in paren:
            out.append(g + " " + x)
    return [f for f in dict.fromkeys(out) if ok_form(f)]


def load():
    reg = json.load(io.open(REGISTER, encoding="utf-8"))
    eng = json.load(io.open(ENGLISH, encoding="utf-8"))
    return reg, eng


def feed_names():
    """(living spellings, available) from the private feed, folded. Names only ever compared, never written."""
    if not FEED.exists():
        return set(), False
    f = json.load(io.open(FEED, encoding="utf-8"))
    s = set()
    for x in f.get("living", []):
        for n in x.get("names", []):
            s.add(fold(n))
    return s, True


SPLIT = re.compile(r"[×·;,()\[\]]| nee | née | geb\. | and | the elder| the younger|\bnot\b")


def segments(text):
    """The written names inside one string of the data: «A × B» is two, «Given Maiden (Married)» is two, «A née B» is two."""
    out = set()
    for part in SPLIT.split(clean(text)):
        part = fold(part)
        if len(part.split()) >= 2:
            out.add(part)
    return out


def data_json(name):
    return json.load(io.open(SITE / "src" / "data" / name, encoding="utf-8"))


def other_people(reg, eng, page_forms, page_surnames):
    """People the archive's data names who have NO /people/ page, and longer written names that cut a shorter one.

    returns (nopage, longer):
      nopage  folded names of people with no page: an English-line relative listed without a slug (213 of them: siblings,
              children, in-laws read from a census) or with a page of another kind (Leonard has /leonard/). A name one
              of them bears is not one person's, so it is never linked.
      longer  folded written names, from the data the pages are written from, that are not themselves linked and are not
              a recorded form of a page person. A shorter name inside one of them ("Robert Wear" in "Leonard Aubrey
              Robert Wear") must not be linked there. «Charlotte Leibholz née Tworoger» (a Gedenkbuch entry, not the
              Charlotte who has a page) is one: the form «Charlotte Leibholz» must not link there.
    A name of the data that IS a recorded form of a page person (the tree and the evidence files name the people who have
    pages) is that person and is skipped; so is «A née B» when B is a surname the page person with form A is recorded under.
    """
    nopage, longer = set(), set()
    raw = []
    for p in eng["people"]:
        for band in ("parents", "spouses", "children", "siblings"):
            for k in p["kin"].get(band, []):
                if not k.get("s"):
                    nopage.add(fold(k["n"]))
                    raw.append(k["n"])
    for g in data_json("tree.json")["generations"]:
        for q in g["people"]:
            raw.append(q["name"])
    for q in data_json("gedenkbuch.json"):
        raw.append(q.get("name", ""))
    nm = data_json("names.json")
    for q in nm.get("people", []):
        raw.append(q.get("canonical", ""))
    for q in nm.get("others", []):
        raw.append(q.get("name", ""))
    for q in data_json("litigation.json"):
        for k in ("plaintiff", "defendant"):
            if isinstance(q.get(k), str):
                raw.append(q[k])
    for q in data_json("evidence.json")["people"]:
        raw.append(q.get("name", ""))
    if BLOCKERS.exists():
        bl = json.load(io.open(BLOCKERS, encoding="utf-8"))
        for n in bl["names"]:
            raw.append(n)
        for x in bl.get("namesakes", []):          # a second person bears the form: it is never linked
            nopage.add(fold(x["name"]))
    NEE = re.compile(r"^(.+?)\s+(?:n\u00e9e|nee|geb\.)\s+(.+)$", re.I)
    for r0 in raw:
        for r in re.split(r"[×·]", clean(r0)):         # «A × B» names a couple
            r = clean(r)
            m = NEE.match(r)
            if m:                                    # «A née B»: the same woman as a page person only if B is one of her surnames
                a, b = fold(m.group(1)), fold(m.group(2)).split()[-1:] or [""]
                if a in page_forms and b[0] in page_surnames.get(a, set()):
                    continue
                longer.add(fold(r))
                continue
            for seg in segments(r):
                if seg not in page_forms:
                    longer.add(seg)
    longer.discard("")
    return nopage, longer


def surname_of(name):
    """The last word of a name, parenthesised parts and a trailing «Jr» left out."""
    toks = clean(re.sub(r"\([^)]*\)", " ", name)).split()
    return toks[-1] if toks else ""


def married_forms(reg, eng):
    """[(form, person id or None)]: the name a wife is written under in a census or an index, her given name beside her
    husband's surname («Emma Larkin» married to a Hawkins is «Emma Hawkins» in the 1871 census). The archive's data
    holds the marriage but not always the name, so a form here is never LINKED; it only counts as one more bearer, so that
    a name which is also a married name is ambiguous («Emma Hawkins» is the woman born 1859 and the wife of John Hawkins)."""
    out = []
    by_id = {p["id"]: p for p in reg["people"]}
    for p in reg["people"]:
        if p.get("sex") != "F" or p.get("placeholder"):
            continue
        given = clean(p.get("first")).split()[:1] or clean(p.get("name")).split()[:1]
        for x in p.get("rel", []):
            if re.match(r"^Her (ex-)?husband", x.get("rel", "")) and given:
                sn = surname_of(x.get("n", ""))
                if sn and sn[:1].isalpha():
                    out.append((given[0] + " " + sn, "r%s" % p["id"]))
    FEM = re.compile(r"mother|sister|daughter|aunt|wife", re.I)
    for p in eng["people"]:
        fem = bool(FEM.search(p.get("rel", "")))
        for k in p["kin"].get("spouses", []):
            if fem:
                out.append((p["name"].split()[0] + " " + surname_of(k["n"]), "e:%s" % p["slug"]))
            else:
                out.append((k["n"].split()[0] + " " + surname_of(p["name"]), ("e:%s" % k["s"]) if k.get("s") else None))
    return [(f, i) for (f, i) in out if ok_form(f)]


def add_aliases(persons):
    """Add the forms of data/names-aliases.json to the person each names. Refuses (SystemExit) a slug that is not a page, a
    living or placeholder person, a form that is not a name, and an entry with no basis. Returns the number of forms added."""
    if not ALIASES.exists():
        return 0
    data = json.load(io.open(ALIASES, encoding="utf-8"))
    by_url = {q["url"]: q for q in persons}
    n = 0
    for a in data.get("aliases", []):
        q = by_url.get("/people/%s/" % a.get("slug"))
        if q is None:
            raise SystemExit("build-names-index: names-aliases.json names a page that does not exist: %s" % a.get("slug"))
        if not q["linkable"]:
            raise SystemExit("build-names-index: names-aliases.json gives a form to a person who is living, a placeholder or not known to be dead (%s)" % a.get("slug"))
        if len(clean(a.get("basis"))) < 20:
            raise SystemExit("build-names-index: an alias entry has no basis (%s)" % a.get("slug"))
        for f in a.get("forms", []):
            if not ok_form(f):
                raise SystemExit("build-names-index: an alias form is not a name (%s)" % f)
            if fold(f) not in {fold(x) for x in q["forms"]}:
                q["forms"].append(clean(f))
                n += 1
    return n


def build():
    reg, eng = load()
    living_fold, have_feed = feed_names()
    persons = []          # dicts: id, url, forms, linkable (dead with a page), kind
    for p in reg["people"]:
        slug = p["slug"]
        living = bool(p.get("living") or p.get("bare"))
        placeholder = bool(p.get("placeholder"))
        known_dead = not p.get("no_death_recorded")
        if p.get("kind") == "document" and not known_dead and isinstance(p.get("by"), int) and p["by"] <= DOC_DEAD_BY:
            known_dead = True
        persons.append({"id": "r%s" % p["id"], "url": "/people/%s/" % slug, "forms": register_forms(p),
                        "linkable": (not living) and (not placeholder) and known_dead})
    for p in eng["people"]:
        n = clean(p["name"])
        persons.append({"id": "e:%s" % p["slug"], "url": "/people/%s/" % p["slug"], "forms": [n] if ok_form(n) else [],
                        "linkable": True})
    n_alias = add_aliases(persons)
    bearers = {}
    page_surnames = {}
    for q in persons:
        sn = {fold(f).split()[-1] for f in q["forms"]}
        for f in q["forms"]:
            bearers.setdefault(fold(f), []).append(q)
            page_surnames.setdefault(fold(f), set()).update(sn)
    nopage, longer = other_people(reg, eng, set(bearers), page_surnames)
    by_pid = {q["id"]: q for q in persons}
    n_married = 0
    for form, pid in married_forms(reg, eng):
        key = fold(form)
        if pid is None:
            nopage.add(key)
        elif pid in by_pid and not any(q["id"] == pid for q in bearers.get(key, [])):
            n_married += 1
            bearers.setdefault(key, []).append(dict(by_pid[pid], implicit=True))
    stats = {"register people": len(reg["people"]), "English-line people": len(eng["people"]),
             "forms added from data/names-aliases.json": n_alias,
             "forms with a bearer": len(bearers), "married names counted as extra bearers (never linked)": n_married,
             "dropped: a living, held-out, placeholder or not-known-dead person also bears it": 0,
             "dropped: a living or held-out name from the private feed": 0,
             "dropped: a relative with no page of their own also bears it": 0,
             "dropped: sits inside a longer name that is not linked": 0}
    keep = {}
    for key, qs in sorted(bearers.items()):
        if key in living_fold:
            stats["dropped: a living or held-out name from the private feed"] += 1
        elif not all(q["linkable"] for q in qs):
            stats["dropped: a living, held-out, placeholder or not-known-dead person also bears it"] += 1
        elif key in nopage:
            stats["dropped: a relative with no page of their own also bears it"] += 1
        else:
            keep[key] = qs
    # A form that sits inside a longer written name which is not itself linked is dropped, until nothing changes.
    # (Linked names win by the linker's own longest-first rule; an unlinked longer name would be cut.)
    def inside(short, long_):
        a, b = short.split(), long_.split()
        return len(a) < len(b) and any(b[i:i + len(a)] == a for i in range(len(b) - len(a) + 1))
    changed = True
    while changed:
        changed = False
        for key in list(keep):
            if any(inside(key, n) and n not in keep for n in longer):
                del keep[key]
                stats["dropped: sits inside a longer name that is not linked"] += 1
                changed = True
    people, ambiguous = [], []
    by_person = {}
    for key, qs in sorted(keep.items()):
        ids = {q["id"] for q in qs}
        written = next((f for q in qs if not q.get("implicit") for f in q["forms"] if fold(f) == key), None)
        if written is None:                  # only a married name that nobody is recorded under: never linked
            continue
        if len(ids) == 1:
            by_person.setdefault(qs[0]["id"], (qs[0]["url"], []))[1].append(written)
        else:
            ambiguous.append({"name": written, "url": "/search/?q=" + urlq(written)})
    # Group the one-bearer forms by person: the longest form is the name, the rest its aliases.
    for pid, (url, forms) in sorted(by_person.items()):
        forms = sorted(set(forms), key=lambda s: (-len(s.split()), -len(s), s))
        people.append({"name": forms[0], "aliases": forms[1:], "url": url})
    people.sort(key=lambda e: (fold(e["name"]), e["url"]))
    ambiguous.sort(key=lambda e: fold(e["name"]))
    return {"people": people, "ambiguous": ambiguous}, stats, have_feed


def urlq(s):
    from urllib.parse import quote
    return quote(s, safe="")


def counts(idx):
    return {"people (one dead bearer, with a page)": len(idx["people"]),
            "aliases": sum(len(e["aliases"]) for e in idx["people"]),
            "ambiguous (several dead bearers, sent to /search/?q=)": len(idx["ambiguous"])}


def render(idx):
    return json.dumps(idx, ensure_ascii=False, indent=1) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--counts", action="store_true")
    a = ap.parse_args(argv)
    idx, stats, have_feed = build()
    text = render(idx)
    for k, v in {**stats, **counts(idx)}.items():
        print("  %-82s %d" % (k, v))
    print("  %-82s %s" % ("private feed (living / held-out spellings) read", "yes" if have_feed else "NO (public half only: the register's own living flags)"))
    if not idx["people"]:
        print("build-names-index: FAIL, no person in the index; refusing to write an empty one")
        return 1
    if a.counts:
        return 0
    if a.check:
        if not OUT.exists():
            print("build-names-index: FAIL, %s is missing; run tools/build-names-index.py" % OUT.relative_to(ROOT))
            return 1
        cur = io.open(OUT, encoding="utf-8").read()
        if have_feed:
            if cur != text:
                print("build-names-index: FAIL, %s is not what the data gives; run tools/build-names-index.py and commit it" % OUT.relative_to(ROOT))
                return 1
        else:
            # Public half (CI): the committed index may hold no form the register's own data does not give
            # (it may hold fewer: the machine with the private feed dropped more).
            have = json.loads(cur)
            ok = {fold(e["name"]) for e in idx["people"]} | {fold(x) for e in idx["people"] for x in e["aliases"]}
            by_url = {e["url"]: e for e in idx["people"]}
            bad = 0
            for e in have["people"]:
                names = [e["name"]] + e["aliases"]
                if e["url"] not in by_url or any(fold(n) not in ok for n in names):
                    bad += 1
            amb = {fold(e["name"]) for e in idx["ambiguous"]}
            bad += sum(1 for e in have["ambiguous"] if fold(e["name"]) not in amb)
            if bad:
                print("build-names-index: FAIL, %d committed entries are not in what the register gives (a stale or hand-edited index)" % bad)
                return 1
        print("build-names-index: ok (%s)" % ("equal to the data, private feed read" if have_feed else "every committed entry is one the public data gives"))
        return 0
    io.open(OUT, "w", encoding="utf-8").write(text)
    print("build-names-index: wrote %s" % OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
