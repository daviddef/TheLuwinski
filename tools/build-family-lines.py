#!/usr/bin/env python3
"""THE FAMILY RIBBONS AND 'HOW OUR LINE CONNECTS', MADE FROM DATA THIS ARCHIVE ALREADY HOLDS. Added 27 October 2026.

Every family page (/families/<slug>/, declared in site/src/data/families.json) gets, at the top, the kit's FamilyRibbon:
that family's own line of generations as the story's ribbon draws ours, smaller, and under it one block for each place
OUR DIRECT LINE touches the family (kit/docs/family-ribbon.md). Nothing here is typed. This script reads:

  site/src/data/story.json          the story's ribbon (our line, verbatim cards) and its chapter trees (the grades)
  site/src/data/direct-line.json    who is on our direct line (made from the story by the kit's directline.py)
  site/src/data/register.json       the register's people and their parent and spouse edges
  site/src/data/english-people.json the English line's people, their grades and their kin
  site/src/data/families.json       which surnames make which family page
  site/src/data/lines.json          the lanes marked ours: their status, note and span

and writes two files:

  site/src/data/family-lines.json   the families with a LINE OF AT LEAST TWO GENERATIONS: cards and connections (kit contract)
  site/src/data/family-blocks.json  the families with no such line (one person of the name has a page here, or none):
                                    the connection blocks only, drawn without a ribbon

THE CARDS. A family's line is the longest chain parent -> child through people of the name who have a page and whom the
archive draws (on the story's ribbon or in a chapter's tree, on the tree page, or on the English line). Where both
parents carry the name the chain follows the father. A story ribbon card with no person page that stands immediately
before the chain's first person on the ribbon, and carries the name, heads the chain as the story wrote it. A person on
the story's ribbon is the story's card, verbatim. Anyone else: the name as the story or the English line writes it (the
register's otherwise, without the married name in brackets); the years the data holds; 'from' the birthplace the data
holds, graded by the story's own outline for that person (the best one, since a person drawn twice is drawn once as a
child of a household and once in a marriage that documents them), by the English line's grade, or else as the family's
tree (lore); the spouse is the other parent of the next card's person (on the last card: the story's spouse, or the
only spouse the data holds). A living person is never a card: a family page names none (THE LIVING STANDARD, version 2).

THE CONNECTIONS. For every person on our direct line (people and partners) and every person X of the family: a marriage,
or our person a son or daughter of X, is a connection, unless our person is of the family too and X is on our line as well
(that is the line itself, which the tinted cards already show). Every connection must be drawn by one of the story's
chapter trees (the couple, or the parent above the child), and takes that drawing's grade (the weaker of the two
outlines) and that chapter's link; an edge the data holds and no chapter draws stops this script, so that a connection
is never graded by guesswork. A family that touches none says why, in the archive's own words; a family this script
cannot account for stops it.

    python3 tools/build-family-lines.py            write both files
    python3 tools/build-family-lines.py --check    exit 1 if either file is not what the data makes (CI and the build)
"""
import argparse, json, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "site", "src", "data")
OUT_LINES = os.path.join(DATA, "family-lines.json")
OUT_BLOCKS = os.path.join(DATA, "family-blocks.json")
GRANK = {"lore": 0, "inf": 1, "doc": 2}
EN_GRADE = {"documented": "doc", "probable": "inf", "inferred": "inf", "family": "lore", "disputed": "lore"}
PARENT_REL = {"His father", "Her father", "His mother", "Her mother", "Her parent"}
SPOUSE_REL = {"His wife", "Her husband", "His ex-wife", "Her ex-husband", "Partner", "Her partner", "His partner"}
ENGLISH_WHY = ("This family is on the English line the DNA points to, through the Wears of Hertfordshire. No document yet "
               "joins that line to the family of record that the story follows, so nothing on it is drawn as ours; "
               "it has pages of its own.")


def load(name):
    return json.load(open(os.path.join(DATA, name), encoding="utf-8"))


def fold(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def rels(p):
    v = p.get("rel")
    if isinstance(v, list):
        return v
    if isinstance(v, str) and v.strip():
        try:
            return json.loads(v.replace("'", '"'))
        except ValueError:
            return []
    return []


def surname_of(p):
    if p.get("last"):
        return p["last"]
    bare = re.sub(r"\([^)]*\)", " ", p.get("name", "")).split()
    return bare[-1] if bare else ""


def clean_reg_name(n):
    n = re.sub(r"\([^)]*\)", " ", n)
    n = n.replace(",", " ")
    return re.sub(r"\s+", " ", n).strip()


def town(place):
    t = str(place or "").split(",")[0]
    t = re.sub(r"\([^)]*\)", "", t)
    t = re.sub(r"\s+Germany$", "", t.strip(), flags=re.I).strip()
    return "" if (not t or re.search(r"\d", t) or len(t) > 40) else t


def build():
    story = load("story.json")
    dl = load("direct-line.json")
    reg = load("register.json")
    eng = load("english-people.json")
    fams = load("families.json")
    lines = load("lines.json")

    ours = {}
    for p in dl.get("people", []):
        ours[p["slug"]] = p["generation"]
    for p in dl.get("partners", []):
        ours[p["slug"]] = p["generation"]

    ribbon = story["ribbon"]["cards"]
    rib_person = {c["person"]: c for c in ribbon if c.get("person")}
    rib_spouse = {c["spousePerson"]: c for c in ribbon if c.get("spousePerson")}

    # the story's chapter trees: every node of a person, with its row and chapter; the drawn couples and parent -> child
    tree_nodes = {}          # slug -> [grade]
    tree_names = {}          # slug -> name as a chapter draws it
    drawn_couple = {}        # frozenset(a, b) -> (grade, chapter)
    drawn_child = {}         # (child, parent) -> (grade, chapter)
    for ch in story.get("chapters", []):
        t = ch.get("tree")
        if not t:
            continue
        rows = {r["kind"]: r["nodes"] for r in t.get("rows", [])}
        for r in t.get("rows", []):
            for n in r["nodes"]:
                if n.get("person"):
                    tree_nodes.setdefault(n["person"], []).append(n.get("grade", "lore"))
                    nm = n.get("name", "")
                    if len(nm.split()) >= 2 and " née " not in nm and " and " not in nm:
                        tree_names.setdefault(n["person"], nm)
        couple = [n for n in rows.get("couple", []) if n.get("person")]
        if len(couple) == 2:
            a, b = couple
            g = min(a.get("grade", "lore"), b.get("grade", "lore"), key=GRANK.get)
            drawn_couple.setdefault(frozenset((a["person"], b["person"])), (g, ch["id"]))
        for parent in couple:
            for kid in [n for n in rows.get("children", []) if n.get("person")]:
                g = min(parent.get("grade", "lore"), kid.get("grade", "lore"), key=GRANK.get)
                drawn_child.setdefault((kid["person"], parent["person"]), (g, ch["id"]))
        for parent in [n for n in rows.get("above", []) if n.get("person")]:
            for kid in couple:
                g = min(parent.get("grade", "lore"), kid.get("grade", "lore"), key=GRANK.get)
                drawn_child.setdefault((kid["person"], parent["person"]), (g, ch["id"]))

    # the tree page's declared links (families.json tree_links) for register people
    tree_ids = {v.split(":", 1)[1] for vs in fams.get("tree_links", {}).values() for v in vs if v.startswith("id:")}

    # one person table: register (no placeholders) and the English line
    P = {}
    by_id = {str(p["id"]): p for p in reg["people"]}
    for p in reg["people"]:
        if p.get("placeholder"):
            continue
        birth = next((f for f in p.get("facts", []) if f.get("ty") == "BIRT"), {})
        parents, spouses = [], []
        for r in rels(p):
            o = by_id.get(str(r.get("id")))
            if not o or o.get("placeholder"):
                continue
            if r.get("rel") in PARENT_REL:
                parents.append((o["slug"], "father" in r["rel"]))
            elif r.get("rel") in SPOUSE_REL:
                spouses.append(o["slug"])
        P[p["slug"]] = {
            "slug": p["slug"], "src": "register", "surname": surname_of(p), "sex": p.get("sex"),
            "living": bool(p.get("living") or p.get("bare")),
            "name": clean_reg_name(p["name"]), "by": p.get("by"), "dy": p.get("dy"), "dyq": p.get("dyq"), "byq": p.get("byq"),
            "origin": town(birth.get("place")), "parents": parents, "spouses": spouses,
            "drawn": p["slug"] in rib_person or p["slug"] in rib_spouse or p["slug"] in tree_nodes or str(p["id"]) in tree_ids,
        }
    for p in eng["people"]:
        # the birthplace as the English line writes it: the parts of `born` that are not a date or a qualifier
        parts = [x.strip() for x in re.sub(r"\([^)]*\)", "", str(p.get("born", ""))).split(",")]
        origin = ", ".join(x for x in parts if x and not re.search(r"\d", x)
                           and not re.match(r"^(not established|about|baptised|before|after|between)\b", x, re.I))
        if not origin and re.match(r"^of [A-Z]", p.get("dates", "")):
            origin = p["dates"][3:]
        kin = p.get("kin", {})
        P[p["slug"]] = {
            "slug": p["slug"], "src": "english", "surname": p["name"].split()[-1], "sex": None, "living": False,
            "name": p["name"], "dates": p.get("dates", ""), "grade": EN_GRADE.get(p.get("grade"), "lore"),
            "origin": origin,
            "parents": [(k["s"], i == 0) for i, k in enumerate(kin.get("parents", [])) if k.get("s")],
            "spouses": [k["s"] for k in kin.get("spouses", []) if k.get("s")],
            "drawn": True,
        }

    def name_of(s):
        if s in rib_person:
            return rib_person[s]["name"]
        if s in rib_spouse:
            return rib_spouse[s]["spouse"]
        if s in tree_names:
            return tree_names[s]
        return P[s]["name"]

    def years_of(s):
        if s in rib_person:
            return rib_person[s]["years"]
        p = P[s]
        if p["src"] == "english":
            return p["dates"] if re.search(r"\d", p["dates"]) else "dates not known"
        b = ("%s " % p["byq"].lower() if p.get("byq") else "") + str(p["by"]) if p.get("by") else ""
        d = ("%s " % p["dyq"].lower() if p.get("dyq") else "") + str(p["dy"]) if p.get("dy") else ""
        if b and d:
            return "%s–%s" % (b, d)
        return "b. %s" % b if b else ("d. %s" % d if d else "dates not known")

    def grade_of(s):
        if s in rib_person:
            return rib_person[s]["originGrade"]
        if P[s]["src"] == "english":
            return P[s]["grade"]
        gs = tree_nodes.get(s)
        return max(gs, key=GRANK.get) if gs else "lore"

    def origin_phrase(s):
        """'of X' for a spouse or a connection's other side."""
        if s in rib_spouse:
            return rib_spouse[s]["spouseOrigin"]
        if s in rib_person:
            return "of %s" % rib_person[s]["origin"] if rib_person[s].get("origin") else "place not known"
        return "of %s" % P[s]["origin"] if P[s].get("origin") else "place not known"

    def published_spouses(s):
        return [x for x in P[s]["spouses"] if x in P and not P[x]["living"]]

    def card(s, nxt):
        if s in rib_person:
            c = rib_person[s]
            out = {k: c.get(k, "") for k in ("name", "years", "origin", "originGrade", "spouse", "spouseOrigin", "atPlace", "atYear")}
            out.update({"living": bool(c.get("living")), "person": s})
            if c.get("spousePerson"):
                out["spousePerson"] = c["spousePerson"]
            if c.get("title"):
                out["title"] = c["title"]
            return out
        sp = ""
        if nxt:
            others = [x for x, _ in P[nxt]["parents"] if x != s]
            sp = others[0] if len(others) == 1 and others[0] in P and not P[others[0]]["living"] else ""
        else:
            ps = published_spouses(s)
            sp = ps[0] if len(ps) == 1 else ""
        out = {"name": name_of(s), "years": years_of(s), "origin": P[s]["origin"], "originGrade": grade_of(s),
               "spouse": name_of(sp) if sp else "", "spouseOrigin": origin_phrase(sp) if sp else "",
               "atPlace": "", "atYear": "", "living": False, "person": s}
        if sp:
            out["spousePerson"] = sp
        return out

    lanes_ours = {}
    for st in lines["sets"]:
        for ln in st["lanes"]:
            if ln.get("ours"):
                lanes_ours[fold(st["name"])] = ln

    fam_lines, fam_blocks, report = [], [], []
    for f in fams["families"]:
        reg_keys = {fold(x) for x in f.get("register", [])}
        ids = {str(x) for x in f.get("register_ids", [])}
        eng_keys = {fold(x) for x in f.get("english", [])}
        members = set()
        for s, p in P.items():
            if p["src"] == "register" and (fold(p["surname"]) in reg_keys or s in {by_id[i]["slug"] for i in ids if i in by_id}):
                members.add(s)
            if p["src"] == "english" and fold(p["surname"]) in eng_keys:
                members.add(s)
        cand = {s for s in members if P[s]["drawn"] and not P[s]["living"]}

        # the longest chain, parent -> child, following the father where both parents carry the name
        def up(s):
            ps = [(x, fa) for x, fa in P[s]["parents"] if x in cand]
            if not ps:
                return None
            fathers = [x for x, fa in ps if fa]
            return fathers[0] if fathers else ps[0][0]

        best = []
        for s in sorted(cand):
            chain = [s]
            while True:
                u = up(chain[0])
                if not u or u in chain:
                    break
                chain.insert(0, u)
            key = (len(chain), sum(1 for x in chain if x in ours))
            if key > (len(best), sum(1 for x in best if x in ours)):
                best = chain
        chain = best
        cards = [card(s, chain[i + 1] if i + 1 < len(chain) else None) for i, s in enumerate(chain)]
        head = None
        if chain and chain[0] in rib_person:
            i = ribbon.index(rib_person[chain[0]])
            prev = ribbon[i - 1] if i > 0 else None
            if prev and not prev.get("person") and fold(prev["name"]).split()[-1:] and fold(prev["name"]).split()[-1] in reg_keys:
                head = {k: prev.get(k, "") for k in ("name", "years", "origin", "originGrade", "spouse", "spouseOrigin", "atPlace", "atYear")}
                head["living"] = bool(prev.get("living"))
                if prev.get("title"):
                    head["title"] = prev["title"]
                cards.insert(0, head)

        # the connections
        conns = []
        for o, gen in sorted(ours.items(), key=lambda kv: (kv[1], kv[0])):
            if o not in P:
                continue
            o_in = o in members
            edges = [(x, "married") for x in P[o]["spouses"]] + \
                    [(x, ("son of" if P[o]["sex"] == "M" else "daughter of" if P[o]["sex"] == "F" else "child of")) for x, _ in P[o]["parents"]]
            for x, rel in edges:
                if x not in members or x not in P or P[x]["living"]:
                    continue
                if o_in and x in ours:
                    continue
                drawn = drawn_couple.get(frozenset((o, x))) if rel == "married" else drawn_child.get((o, x))
                if not drawn:
                    if rel == "married" and not P[x]["drawn"]:
                        continue          # a later marriage of our person to someone the archive draws nowhere (a second wife)
                    raise SystemExit("build-family-lines: %s %s %s (%s) is in the data and no chapter of the story draws it; "
                                     "grade it in the story before it can be a connection" % (o, rel, x, f["slug"]))
                grade, chapter = drawn
                conns.append({"ourSlug": o, "ourGeneration": gen, "ourName": name_of(o), "theirSlug": x, "theirName": name_of(x),
                              "theirOrigin": origin_phrase(x), "relation": rel, "grade": grade, "storyHref": "/story/#%s" % chapter})

        entry = {"id": f["slug"], "title": f["name"], "page": "/families/%s/" % f["slug"]}
        if len(cards) >= 2:
            lane = lanes_ours.get(fold(f.get("lanes") or ""))
            if lane:
                entry["status"] = lane["status"]
                if lane.get("statusNote"):
                    entry["statusNote"] = lane["statusNote"]
                if lane.get("span"):
                    entry["span"] = lane["span"]
            else:
                g0 = cards[0]["originGrade"]
                entry["status"] = {"doc": "documented", "inf": "inferred"}.get(g0) or (
                    "inferred" if any(c["originGrade"] == "doc" for c in cards) else "family-lore")
            entry["cards"] = cards
        else:
            entry["ribbon"] = "none"
            entry["ribbonWhy"] = ("One person of the name has a page in this archive, so there is no line of generations to draw."
                                  if len(cands_with_page(members, P)) == 1 else
                                  "No two people of the name with a page here are parent and child, so there is no line of generations to draw.")
        if conns:
            entry["connections"] = conns
        else:
            if members and all(P[s]["src"] == "english" for s in members):
                entry["notConnected"] = {"why": ENGLISH_WHY}
            else:
                raise SystemExit("build-family-lines: %s touches no one on our line and the archive gives no reason; say why "
                                 "in the data before the page can" % f["slug"])
        (fam_lines if "cards" in entry else fam_blocks).append(entry)
    return fam_lines, fam_blocks


def cands_with_page(members, P):
    return [s for s in members if not P[s]["living"]]


def render(fl, fb):
    a = {"_note": "Made by tools/build-family-lines.py from story.json, direct-line.json, register.json, english-people.json, "
                  "families.json and lines.json; do not edit by hand. The kit's contract: kit/docs/family-ribbon.md.",
         "families": fl}
    b = {"_note": "Made by tools/build-family-lines.py with family-lines.json: the family pages with no line of two or more "
                  "generations to draw. Their connection blocks (or the not-connected block) are drawn without a ribbon.",
         "families": fb}
    return (json.dumps(a, ensure_ascii=False, indent=1) + "\n", json.dumps(b, ensure_ascii=False, indent=1) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    fl, fb = build()
    ta, tb = render(fl, fb)
    if a.check:
        bad = []
        for path, text in ((OUT_LINES, ta), (OUT_BLOCKS, tb)):
            have = open(path, encoding="utf-8").read() if os.path.exists(path) else None
            if have != text:
                bad.append(os.path.relpath(path, ROOT))
        if bad:
            print("build-family-lines: %s not what the data makes; run python3 tools/build-family-lines.py" % ", ".join(bad))
            return 1
        print("build-family-lines: family-lines.json (%d families with a line) and family-blocks.json (%d without) are what "
              "the data makes" % (len(fl), len(fb)))
        return 0
    open(OUT_LINES, "w", encoding="utf-8").write(ta)
    open(OUT_BLOCKS, "w", encoding="utf-8").write(tb)
    nc = sum(len(f.get("connections", [])) for f in fl + fb)
    print("build-family-lines: wrote %d families with a line, %d without; %d connections" % (len(fl), len(fb), nc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
