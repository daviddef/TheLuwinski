#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Roots & Routes: the tree page for this archive, built from this archive's own committed data.

    python3 tools/build-tree-page.py            # rebuild data/tree-page/ (tree.json, atlas-data.json, roots.html, roots.embed.html) and site/public/roots-links.json
    python3 tools/build-tree-page.py --check    # exit 1 if the page is older than the data it was built from

WHERE THE PEOPLE COME FROM. There is no committed GEDCOM and no people.json. The people are the two published files the person pages are drawn from:
site/src/data/register.json (the register: the family proper, the surname index, the people found in a register; written by tools/build-register.py with the
living already reduced to a name) and site/src/data/english-people.json (the twenty-six hand-written people of the English line). They are turned into a small
GEDCOM (data/tree-page/people.ged, not committed) and handed to the family-tree-page skill's converter, vendored in tools/tree-page/.

WHO IS DRAWN. This archive's living standard (README, kit/tools/living_rule.py) is kept, and this page is STRICTER than it. A person is drawn only if
  - the register does not flag them living or named-only (`living`, `bare`) and they are not a placeholder (a record that stands for nobody), AND
  - their death is recorded (a death year or date in the register), OR the tree marks them deceased and they were born in 1900 or earlier.
A person with no death recorded who was born after 1900, or with no birth year at all and no death, is NOT drawn, and is not listed by name either: the
report holds a count. Nobody with `no_death_recorded` is drawn on the strength of a birth year alone. The converter then adds its own floor (no death and
born in the last 110 years: not drawn). The English line is drawn only for its twenty-six hand-written people (all born before 1900); the 79 relatives it
names without a page of their own have no sex, no place and, mostly, no death, and are not drawn. The raw register harvest is never read.

COLOUR is the archive's own family (site/src/data/families.json: the surname line a person is declared in), not a surname spelling. Which spellings are one
name is the Record Atlas catalogue's to say (surname-variants skill); this builder keeps no list of them and the catalogue's `sk` key is not used.

PLACES are never guessed. Each place string, as printed, is resolved in this order, and the first that applies wins:
  1. data/tree-page/place-additions.json "places" (a string decided by hand, with its reason);
  2. data/era/ground.tsv + data/era/towns.tsv (the archive's own decision of the town for a string, with the archive's hand point). A string whose first
     segment is not the town itself (a village in a Kreis) is placed at the village if the Atlas's GeoNames gazetteer has exactly one place of that name
     in that country within 40 km of the archive's point, and otherwise is named "<village> (near <town>)" at the town's point and says so;
  3. place-additions.json "by_ground_town": the town the archive's ground.tsv names in its reason column for a string it left without a point;
  4. the converter's own rule: a Record Atlas place that is the single match for the first segment AND whose country the string names.
The country is always the Atlas's own geo.country_of on the point. Anything unresolved is listed in tree.report.json; a person with no resolved birth place
is drawn at a relative's birth place (said on the page) or, with no relative placed, not drawn. The Record Atlas is only ever read.
"""
import argparse, collections, datetime, gzip, hashlib, io, json, math, os, re, subprocess, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "site", "src", "data")
OUT = os.path.join(ROOT, "data", "tree-page")
ERA = os.path.join(ROOT, "data", "era")
TP = os.path.join(ROOT, "tools", "tree-page")
EXT = os.path.join(TP, "painted-lines.ext.html")
HOST = "luwinski.defranceski.com"
ATLAS_CANDIDATES = [os.environ.get("RECORD_ATLAS", ""), os.path.expanduser("~/Projects/Family Projects/Record Atlas"),
                    os.path.join(os.path.dirname(ROOT), "Record Atlas")]
INPUTS = ["register.json", "english-people.json", "families.json"]
LONG_DEAD = 1900     # born in or before this year, marked deceased by the tree, no death date: still drawn
NOW = datetime.date.today().year

def jl(path): return json.load(io.open(path, encoding="utf-8"))
def run(args):
    print("$", " ".join(os.path.relpath(a, ROOT) if os.path.isabs(a) and a.startswith(ROOT) else a for a in args)); r = subprocess.run(args)
    if r.returncode: sys.exit(r.returncode)
def inputs_hash():
    h = hashlib.sha1()
    for n in INPUTS: h.update(io.open(os.path.join(DATA, n), "rb").read())
    for n in ("tree-views.template.html", "painted-lines.ext.html", "gedcom_to_tree.py"): h.update(io.open(os.path.join(TP, n), "rb").read())
    h.update(io.open(os.path.abspath(__file__), "rb").read())
    for f in (os.path.join(ERA, "ground.tsv"), os.path.join(ERA, "towns.tsv"), os.path.join(OUT, "place-additions.json")):
        if os.path.exists(f): h.update(io.open(f, "rb").read())
    return h.hexdigest()[:16]
def atlas_path():
    for c in ATLAS_CANDIDATES:
        if c and os.path.exists(os.path.join(c, "data", "places.json")): return c
    sys.exit("Record Atlas checkout not found (set RECORD_ATLAS)")

def fold(s):
    s = str(s or "").replace("ł", "l").replace("Ł", "L").replace("đ", "d").replace("Đ", "D").replace("ø", "o")
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()).strip()
def km(a, b, c, d):
    p = math.pi / 180; x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))

# ---------------------------------------------------------------- who is drawn
RELBAND = {"His father": "p", "Her father": "p", "His mother": "p", "Her mother": "p", "Her parent": "p",
           "His wife": "s", "Her husband": "s", "His ex-wife": "s", "Her ex-husband": "s", "Partner": "s", "Her partner": "s", "His partner": "s",
           "His son": "c", "Her son": "c", "His daughter": "c", "Her daughter": "c", "Daughter": "c"}
def rels_of(p):
    v = p.get("rel")
    if isinstance(v, list): return v
    if isinstance(v, str) and v.strip():
        try: return json.loads(v.replace("'", '"'))
        except Exception: return []
    return []
def surname_of(p):
    if p.get("last"): return p["last"]
    bare = re.sub(r"\([^)]*\)", " ", p.get("name") or "").split()
    return bare[-1] if bare else ""
def clean_given(s): return re.sub(r"\s+", " ", re.sub(r"\s*,\s*", " ", str(s or ""))).strip(" ,")
def gedname(s): return re.sub(r"\s+", " ", str(s or "").replace("/", " ")).strip()
def has_death(p):
    return p.get("dy") is not None or any(f.get("ty") == "DEAT" and f.get("date") for f in p.get("facts") or [])
def violent_no_year(p):
    """Murdered or deported and the register gives no year of death: the converter's +75 years would carry them decades past it, so they are not drawn."""
    return p.get("dy") is None and bool(re.search(r"murder|deport|camp|auschwitz|theresienstadt|kulmhof", (p.get("died") or "") + " " + " ".join(f.get("place") or "" for f in p.get("facts") or []), re.I))

def not_a_place():
    """Strings data/era/ground.tsv marks «not a place: a sentence or a description the source tree put in the place field»: never offered as a place."""
    out = set()
    for line in io.open(os.path.join(ERA, "ground.tsv"), encoding="utf-8"):
        c = line.rstrip("\n").split("\t")
        if len(c) > 2 and c[2].startswith("not a place"): out.add(c[0])
    return out
NOT_A_PLACE = not_a_place()
okplace = lambda s: s if s and s not in NOT_A_PLACE else None

def register_selection(reg):
    """Returns (drawn dict id -> person, counts). Nobody living, named-only, placeholder, or not clearly dead is drawn."""
    drawn, c, pending = {}, collections.Counter(), set()
    for p in reg["people"]:
        if p.get("living") or p.get("bare"): c["living or named-only (omitted)"] += 1; continue
        if p.get("placeholder"): c["placeholder (a record that stands for nobody)"] += 1; continue
        by = p.get("by")
        documented = p.get("dy") is not None
        long_dead = (not p.get("no_death_recorded")) and by is not None and by <= LONG_DEAD
        if not (documented or long_dead):
            c["no death recorded and not long dead (omitted, not named)"] += 1; continue
        if by is None and p.get("dy") is None: c["no birth year and no death year"] += 1; continue
        if violent_no_year(p): c["murdered or deported, no year of death recorded (not drawn: a year would be invented)"] += 1; continue
        drawn[str(p["id"])] = p
        if not documented: pending.add(str(p["id"]))
    # A person with no death date, held only by "the tree marks them deceased and they were born in 1900 or earlier", is drawn only if they are
    # related to someone else who is drawn. A surname-index entry with no relation and no death date (the archive's own "unproven" Luwinskis) is not.
    keep = set(drawn) - pending
    changed = True
    while changed:
        changed = False
        for i in sorted(pending - keep):
            if any(str(r.get("id")) in keep and RELBAND.get(str(r.get("rel"))) for r in rels_of(drawn[i])): keep.add(i); changed = True
        for i in sorted(pending - keep):   # the relation may be written only on the other person's side
            if any(i in {str(r.get("id")) for r in rels_of(drawn[k]) if RELBAND.get(str(r.get("rel")))} for k in keep if k in drawn): keep.add(i); changed = True
    for i in sorted(pending - keep):
        c["no death date, no relative drawn (surname-index entry, not drawn)"] += 1; del drawn[i]
    return drawn, c

def english_years(p):
    """(birth year, birth estimated, death year, death estimated) from the line's own `dates` and `born` / `died` strings."""
    d, born, died = (p.get("dates") or "").strip(), p.get("born") or "", p.get("died") or ""
    by = bye = dy = dye = None
    m = re.match(r"^(?:b\. )?(c\.? ?)?(\d{4})(?:\s*[–-]\s*(c\.? ?)?(\d{4}))?(.*)$", d)
    if m:
        by, bye = int(m.group(2)), bool(m.group(1))
        if m.group(4): dy, dye = int(m.group(4)), bool(m.group(3)) or "probably" in (m.group(5) or "")
    if by is not None and re.search(r"baptis|bapt", born, re.I): bye = True
    if dy is None and not re.match(r"(not |after|between)", died, re.I):
        m = re.match(r"^(?:\d{1,2} \w+ |Q\d )?(\d{4})\b", died)
        if m: dy, dye = int(m.group(1)), False
    return by, bool(bye), dy, bool(dye)

# the English line's places, as the line's own born / died text gives them (the strings the place rules below resolve); None = the line names no single place
EN_PLACES = {
 "henry-robert-wear": ("Bermondsey", "Johannesburg"), "martha-maud-castle": ("Baldock", "Johannesburg"),
 "robert-wear": ("Bermondsey", "Southwark"), "emma-hawkins-1859": ("Aldenham", "Hitchin"),
 "george-william-castle-1862": ("Hitchin", "Hitchin"), "caroline-wallis": ("Weston, Hertfordshire", "Hitchin"),
 "joseph-wallis-1827": ("Weston, Hertfordshire", "Hitchin"), "sarah-field-1829": ("Weston, Hertfordshire", "Hitchin"),
 "william-wallis-1807": ("Weston, Hertfordshire", None), "mary-foster-1806": ("Wallington, Hertfordshire", None),
 "william-field-1802": ("Weston, Hertfordshire", "Weston, Hertfordshire"), "elizabeth-phillips-1798": ("Weston, Hertfordshire", None),
 "william-wear": (None, None), "sarah-bloom": (None, None), "john-hawkins-1819": ("Aldenham", None), "emma-larkin-1822": ("Aldenham", None),
 "george-castle-1840": ("Baldock", "Hitchin"), "martha-giddings": ("Baldock", "Hitchin"), "james-giddins": ("Baldock", None),
 "elizabeth-giddins": (None, None), "john-wear": (None, None), "elizabeth-wear": (None, None),
 "william-hawkins": (None, "Aldenham"), "mary-appleyard": (None, "Aldenham"), "robert-larkin": (None, "Aldenham"), "mary-burch": (None, "Aldenham"),
}
EN_SEX = lambda rel: "F" if re.search(r"mother", rel or "") else "M"

# ---------------------------------------------------------------- people -> a small GEDCOM
def build_people(reg, eng):
    """-> list of dict(id, name, given, sur, sex, by, dy, bp, dp, resi[], slug, fam_hint, kind) and relations (parents, spouses)."""
    drawn, counts = register_selection(reg)
    pe = []
    for rid, p in drawn.items():
        facts = p.get("facts") or []
        def place(ty):
            f = next((f for f in facts if f.get("ty") == ty and okplace(f.get("place"))), None); return f["place"] if f else None
        resi = []
        for f in facts:
            if okplace(f.get("place")) and (f.get("ty") in ("RESI", "CENS", "IMMI", "EMIG") or re.match(r"(Residence|Immigration|Emigration|Census)", f.get("t") or "")):
                yy = re.search(r"(1[5-9]\d\d|20[0-2]\d)", f.get("date") or ""); resi.append((yy.group(1) if yy else "", f["place"]))
        dplace = place("DEAT") or place("BURI")
        if re.search(r"not documented", p.get("died") or "", re.I): dplace = resi[-1][1] if resi else None   # the archive says the death is not documented: no death place is claimed
        given = clean_given(p.get("first")) or clean_given(re.sub(r"\([^)]*\)", " ", p["name"]).rsplit(" ", 1)[0])
        pe.append(dict(id=rid, name=p["name"], given=given, sur=surname_of(p), sex=p.get("sex") if p.get("sex") in ("M", "F") else "U",
                       by=p.get("by"), dy=p.get("dy"), byq=p.get("byq"), dyq=p.get("dyq"), died=p.get("died") or "",
                       bp=place("BIRT"), dp=dplace, resi=resi, slug=p["slug"], src="register", p=p))
    eng_ids = {}
    for p in eng["people"]:
        by, bye, dy, dye = english_years(p)
        bpl, dpl = EN_PLACES.get(p["slug"], (None, None))
        parts = p["name"].split()
        pe.append(dict(id="E-" + p["slug"], name=p["name"], given=" ".join(parts[:-1]), sur=parts[-1], sex=EN_SEX(p.get("rel")), by=by, dy=dy,
                       byq="circa" if bye else None, dyq="circa" if dye else None, died=p.get("died") or "", bp=bpl, dp=dpl, resi=[], slug=p["slug"], src="english", p=p))
        eng_ids[p["slug"]] = "E-" + p["slug"]
    by_id = {x["id"]: x for x in pe}
    slug_id = {x["slug"]: x["id"] for x in pe}
    parents = collections.defaultdict(dict)   # child -> {"F": id, "M": id}
    spouses = set()
    notes = collections.Counter()
    def add_parent(child, par):
        sx = by_id[par]["sex"]
        if sx not in ("M", "F"): notes["parent of unrecorded sex (left out of the family link)"] += 1; return
        k = "F" if sx == "M" else "M"
        if k in parents[child] and parents[child][k] != par: notes["second %s for one child (first kept)" % ("father" if k == "F" else "mother")] += 1; return
        parents[child][k] = par
    for x in pe:
        if x["src"] == "register":
            for r in rels_of(x["p"]):
                oid, band = str(r.get("id")), RELBAND.get(str(r.get("rel")))
                if oid not in by_id or not band: continue
                if band == "p": add_parent(x["id"], oid)
                elif band == "c": add_parent(oid, x["id"])
                else: spouses.add(tuple(sorted((x["id"], oid))))
        else:
            kin = x["p"]["kin"]
            for k in kin.get("parents", []):
                oid = slug_id.get(k.get("s"));
                if oid: add_parent(x["id"], oid)
            for k in kin.get("children", []):
                oid = slug_id.get(k.get("s"))
                if oid: add_parent(oid, x["id"])
            for k in kin.get("spouses", []):
                oid = slug_id.get(k.get("s"))
                if oid: spouses.add(tuple(sorted((x["id"], oid))))
    # the English line names Agnes Kate Castle by her register slug: she is one person (slug_id covers both sources), drawn once
    return pe, parents, spouses, counts, notes

def write_ged(pe, parents, spouses, path):
    by_id = {x["id"]: x for x in pe}
    fams, fam_of_child, fam_of_spouse = {}, {}, collections.defaultdict(list)
    def fam(h, w):
        k = (h, w)
        if k not in fams: fams[k] = "@F%d@" % (len(fams) + 1)
        return fams[k]
    for c, d in sorted(parents.items()):
        fam_of_child[c] = fam(d.get("F"), d.get("M"))
    for a, b in sorted(spouses):
        if by_id[a]["sex"] == "F" and by_id[b]["sex"] != "F": a, b = b, a
        k = fam(a, b)
        for q in (a, b):
            if k not in fam_of_spouse[q]: fam_of_spouse[q].append(k)
    out = ["0 HEAD", "1 CHAR UTF-8"]
    for x in pe:
        out += ["0 @%s@ INDI" % x["id"], "1 NAME %s /%s/" % (gedname(x["given"]), gedname(x["sur"])), "1 SEX %s" % ("F" if x["sex"] == "F" else "M")]
        if x["by"] is not None or x["bp"]:
            out.append("1 BIRT")
            if x["by"] is not None: out.append("2 DATE %d" % x["by"])
            if x["bp"]: out.append("2 PLAC %s" % x["bp"])
        if x["dy"] is not None or x["dp"] or x["src"] == "english":
            out.append("1 DEAT")
            if x["dy"] is not None: out.append("2 DATE %d" % x["dy"])
            if x["dp"]: out.append("2 PLAC %s" % x["dp"])
        elif x["src"] == "register" and x["by"] is not None and x["by"] <= LONG_DEAD and not x["p"].get("no_death_recorded"):
            out.append("1 DEAT")           # the tree marks them deceased and they were born long ago; no date is invented here
        for yy, pl in x["resi"]:
            out += ["1 RESI"] + (["2 DATE %s" % yy] if yy else []) + ["2 PLAC %s" % pl]
        if x["id"] in fam_of_child: out.append("1 FAMC %s" % fam_of_child[x["id"]])
        for fx in fam_of_spouse.get(x["id"], []): out.append("1 FAMS %s" % fx)
    for (h, w), fx in fams.items():
        out.append("0 %s FAM" % fx)
        if h: out.append("1 HUSB @%s@" % h)
        if w: out.append("1 WIFE @%s@" % w)
        for cid, f in sorted(fam_of_child.items()):
            if f == fx: out.append("1 CHIL @%s@" % cid)
    out.append("0 TRLR")
    io.open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")

# ---------------------------------------------------------------- places
class Atlas:
    def __init__(self, path):
        sys.path.insert(0, os.path.join(path, "scripts")); import geo
        self.geo = geo
        self.countries = jl(os.path.join(path, "data", "countries.json"))["countries"]
        self.places = jl(os.path.join(path, "data", "places.json"))["places"]
        self.by_id = {x["id"]: x for x in self.places}
        self.byname = collections.defaultdict(list)
        for x in self.places:
            for nm in [x["name"]] + [n["n"].split(",")[0] for n in x.get("names", [])]: self.byname[fold(nm)].append(x)
        self.gz_path = os.path.join(path, "data", "gazetteer.json.gz"); self._gz = None
    @property
    def gaz(self):
        if self._gz is None:
            self._gz = collections.defaultdict(list)
            for x in json.load(gzip.open(self.gz_path))["places"]:
                self._gz[fold(x["n"])].append(x)
        return self._gz
    def entry(self, name, lat, lon, how, shown=None):
        iso = self.geo.country_of(lat, lon)
        if not iso: return None
        hit = next((x for x in self.byname.get(fold(name), []) if x.get("country") == iso and km(lat, lon, x["lat"], x["lon"]) <= 15), None)
        return {"name": shown or name, "lat": lat, "lon": lon, "country": self.countries.get(iso, {}).get("name", iso), "iso": iso,
                "atlas_id": hit["id"] if hit else None, "how": how}
    def gazetteer(self, name, iso, near=None, pop_min=None, ):
        c = [x for x in self.gaz.get(fold(name), []) if x["k"] == iso]
        if near: c = [x for x in c if km(near[0], near[1], x["y"], x["x"]) <= near[2]]
        if pop_min is not None: c = [x for x in c if (x.get("p") or 0) >= pop_min]
        return c

def read_tsv(path):
    rows = []
    for line in io.open(path, encoding="utf-8"):
        if line.startswith("#") or not line.strip(): continue
        rows.append(line.rstrip("\n").split("\t"))
    return rows

def same_place(first, town):
    f, t = fold(first), fold(town)
    return f == t or f.startswith(t + " ") or t.startswith(f + " ")
ALIAS_TOWN = {"posen": "poznan", "schubin": "szubin", "frankfurt am main": "frankfurt", "brisbane": "brisbane", "porto": "porto"}
INTOWN = re.compile(r"cemetery|friedhof|kadisha|westpark|west park|\bst\.? ", re.I)

def seed_place_map(atlas, used, report):
    """Fill place_map.json for every place string in `used` that rules 1-3 settle; the converter takes the rest (rule 4)."""
    adds = jl(os.path.join(OUT, "place-additions.json"))
    towns = {r[0]: (float(r[1]), float(r[2]), r[3] if len(r) > 3 else "") for r in read_tsv(os.path.join(ERA, "towns.tsv")) if r[0] != "town"}
    ground = {r[0]: r for r in read_tsv(os.path.join(ERA, "ground.tsv")) if r[0] != "place"}
    pm, how = {}, collections.Counter()
    def directive(d, raw):
        if "atlas_id" in d:
            x = atlas.by_id[d["atlas_id"]]; e = atlas.entry(x["name"], x["lat"], x["lon"], "Record Atlas place %s; %s" % (x["id"], d["why"]))
            if e: e["atlas_id"] = x["id"]
            return e
        if "gazetteer" in d:
            nm, iso = d["gazetteer"][:2]
            c = atlas.gazetteer(nm, iso, near=d.get("near"), pop_min=d.get("pop_min"))
            if len(c) != 1: sys.exit("place-additions: %r gives %d gazetteer matches for %r (need exactly one): %s" % (nm, len(c), raw, [(x['y'], x['x'], x.get('p')) for x in c][:5]))
            x = c[0]; return atlas.entry(d.get("shown") or nm, x["y"], x["x"], "Record Atlas GeoNames gazetteer, the one %s in %s%s; %s" % (nm, iso, " within %s" % d["near"][2:] if d.get("near") else (" of %d+ people" % d["pop_min"] if d.get("pop_min") else ""), d["why"]))
        return atlas.entry(d["name"], d["lat"], d["lon"], d["why"])
    for raw in sorted(used):
        if raw in adds["places"]:
            e = directive(adds["places"][raw], raw)
            if e: pm[raw] = e; how["place-additions.json (this string)"] += 1
            continue
        g = ground.get(raw)
        if g and len(g) > 3 and g[3] and g[3] in towns:
            lat, lon, th = towns[g[3]]; tname = g[3]
            first = re.split(r"[,/|(]", raw)[0].strip()
            direct = same_place(first, tname) or ALIAS_TOWN.get(fold(first)) == fold(tname) or bool(INTOWN.search(first)) or fold(first) == fold(tname)
            how_ = "data/era/ground.tsv names the town %s; point from data/era/towns.tsv (%s); country by the Atlas's geo.country_of" % (tname, th)
            if direct:
                e = atlas.entry(tname, lat, lon, how_)
                how["ground.tsv + towns.tsv (the town itself)"] += 1
            else:
                c = atlas.gazetteer(first, atlas.geo.country_of(lat, lon) or "", near=(lat, lon, 40)) if first else []
                if len(c) == 1:
                    e = atlas.entry(first, c[0]["y"], c[0]["x"], "the Atlas GeoNames gazetteer has one %s in the country within 40 km of %s, the archive's point (data/era/ground.tsv names the district)" % (first, tname))
                    how["ground.tsv district + the one GeoNames village within 40 km"] += 1
                else:
                    e = atlas.entry(tname, lat, lon, how_ + "; the village %s is not found once in the gazetteer within 40 km, so it is drawn at the town and named 'near'" % first, shown="%s (near %s)" % (first, tname))
                    report["district_level"].append(raw); how["ground.tsv + towns.tsv, drawn 'near' the town"] += 1
            if e: pm[raw] = e
            continue
        if g and len(g) > 2:
            tn = g[2].split(":")[0].strip()
            d = adds["by_ground_town"].get(tn)
            if d and raw not in adds.get("exclude", {}):
                e = directive(d, raw)
                if e: pm[raw] = e; how["place-additions.json (by the town ground.tsv names)"] += 1
    return pm, how

def collect_places(ged):
    out = collections.Counter()
    for line in io.open(ged, encoding="utf-8"):
        m = re.match(r"^\d PLAC (.*)$", line.rstrip("\n"))
        if m: out[m.group(1).strip()] += 1
    return out

def build(a):
    os.makedirs(OUT, exist_ok=True)
    reg, eng, fams = jl(os.path.join(DATA, "register.json")), jl(os.path.join(DATA, "english-people.json")), jl(os.path.join(DATA, "families.json"))
    pe, parents, spouses, counts, notes = build_people(reg, eng)
    ged = os.path.join(OUT, "people.ged"); write_ged(pe, parents, spouses, ged)
    slugs = {x["id"]: x["slug"] for x in pe}
    io.open(os.path.join(OUT, "slugs.json"), "w", encoding="utf-8").write(json.dumps(slugs, ensure_ascii=False))
    atlas_dir = atlas_path(); atlas = Atlas(atlas_dir)
    report = {"district_level": []}
    used = collect_places(ged)
    pm, how = seed_place_map(atlas, used, report)
    pm_path = os.path.join(OUT, "place_map.json")
    io.open(pm_path, "w", encoding="utf-8").write(json.dumps(pm, indent=1, ensure_ascii=False))
    print("place_map: %d of %d place strings settled before the converter (%s)" % (len(pm), len(used), dict(how)))
    # colour: the archive's own declared family
    famlist = fams["families"]
    fam_of_surname = {}
    for f in famlist:
        for s in list(f.get("register") or []) + list(f.get("english") or []): fam_of_surname[fold(s)] = f
    fam_of_id = {str(i): f for f in famlist for i in (f.get("register_ids") or [])}
    def family(x):
        f = fam_of_id.get(x["id"]) or fam_of_surname.get(fold(x["sur"]))
        return f["slug"] if f else None
    fam_label = {f["slug"]: f["name"] for f in famlist}
    cnt = collections.Counter(family(x) for x in pe if family(x))
    top = [s for s, _ in cnt.most_common(7)]
    tree = os.path.join(OUT, "tree.json")
    cmd = [sys.executable, os.path.join(TP, "gedcom_to_tree.py"), ged, "--out", tree, "--place-map", pm_path, "--atlas", atlas_dir, "--living", "omit",
           "--lines", "8", "--focus", "9500001", "--slugs", os.path.join(OUT, "slugs.json"), "--title", "Roots & Routes",
           "--subtitle", "Explore the family tree ten ways: by generation, place, era and relationship. Click anyone and every view follows."]
    if a.accept_unique: cmd.append("--accept-unique")
    run(cmd)
    t = jl(tree)
    fam_by_pid = {x["id"]: family(x) for x in pe}
    names = {x["id"]: (x["given"], x["sur"]) for x in pe}
    for p in t["people"]: p["given"], p["sur"] = names[p["id"]]
    key_i = {s: i for i, s in enumerate(top)}
    for p in t["people"]:
        p["line"] = key_i.get(fam_by_pid.get(p["id"]), 7)
        p["page"] = "/people/%s/" % slugs[p["id"]] if p["id"] in slugs else None
        if p["page"] is None: p.pop("page")
    t["lines"] = [{"sur": fam_label[s], "host": HOST} for s in top] + [{"sur": "Other", "host": HOST}]
    t["meta"].update({"rowLabel": "Family line", "lineLabel": "Family line"})
    drop_conflicts(t, tree)
    keep_death_place(t, pe)
    flag_estimates(t, pe)
    io.open(tree, "w", encoding="utf-8").write(json.dumps(t, ensure_ascii=False, separators=(",", ":")))
    rep_path = os.path.splitext(tree)[0] + ".report.json"; rep = jl(rep_path)
    drawn_reg = sum(1 for p in t["people"] if not p["id"].startswith("E-")); drawn_en = len(t["people"]) - drawn_reg
    unresolved = rep.get("unresolved_places") or {}
    rep["adapter"] = {
        "register_people_published": len(reg["people"]), "register_not_offered_to_the_converter": dict(counts),
        "english_line_people_offered": len(eng["people"]), "english_line_relatives_not_drawn": "79 relatives named without a page of their own (no sex, no place, mostly no death)",
        "offered_to_the_converter": len(pe), "drawn": len(t["people"]), "drawn_register": drawn_reg, "drawn_english_line": drawn_en,
        "family_link_notes": dict(notes), "place_strings_used": len(used), "place_strings_settled_before_converter": len(pm), "how_placed": dict(how),
        "district_level_place_strings": report["district_level"], "unresolved_place_strings": unresolved,
    }
    io.open(rep_path, "w", encoding="utf-8").write(json.dumps(rep, indent=1, ensure_ascii=False))

def drop_conflicts(t, tree):
    """A person whose recorded death comes before their birth, or more than 110 years after it, is not one life: not drawn, counted in tree.report.json,
    every relation to them removed."""
    bad = {p["id"] for p in t["people"] if p.get("dy") is not None and not 0 <= p["dy"] - p["by"] <= 110}
    rep_path = os.path.splitext(tree)[0] + ".report.json"; rep = jl(rep_path)
    rep["conflicts"] = [{"id": p["id"], "slug": p.get("slug"), "born": p["by"], "died": p["dy"]} for p in t["people"] if p["id"] in bad]
    io.open(rep_path, "w", encoding="utf-8").write(json.dumps(rep, indent=1, ensure_ascii=False))
    if not bad: return
    t["people"] = [p for p in t["people"] if p["id"] not in bad]
    for p in t["people"]:
        for k in ("father", "mother"):
            if p.get(k) in bad: p[k] = None
        p["spouse"] = [x for x in p["spouse"] if x not in bad]; p["kids"] = [x for x in p["kids"] if x not in bad]
    if t.get("focus") in bad: t["focus"] = t["people"][0]["id"]
    print("conflicts: %d people whose death is before their birth, or over 110 years later, are not drawn" % len(bad))

def keep_death_place(t, pe):
    """The converter takes a later residence as the place of death (a move). A death place the record states and the place map resolves is the place of death."""
    by = {x["id"]: x for x in pe}; pm = jl(os.path.join(OUT, "place_map.json")); n = 0
    for p in t["people"]:
        src = by.get(p["id"]); r = pm.get((src or {}).get("dp") or "")
        if r and r.get("lat") is not None and r.get("name") and r["name"] != p["dp"]: p["dp"] = r["name"]; n += 1
    print("death places: %d put back to the recorded place of death" % n)

def flag_estimates(t, pe):
    """Mark as estimated what the source says is approximate, and do not let the converter's +75 years carry a deported person past the deportation."""
    by = {x["id"]: x for x in pe}; n = 0
    for p in t["people"]:
        x = by.get(p["id"])
        if not x: continue
        if x.get("byq") == "circa" and x["by"] is not None: p["bye"] = True; n += 1
        if x.get("dyq") in ("circa", "before") and x["dy"] is not None: p["dye"] = True; n += 1
        if x["src"] == "register" and x["dy"] is not None and re.search(r"not documented|deport", x["died"], re.I): p["dye"] = True; n += 1
    print("estimates: %d years flagged as approximate" % n)

def write_roots_links(tree):
    ids = sorted(p["id"] for p in jl(tree)["people"])
    out = {"note": "The people Roots & Routes draws, by person id. Made by tools/build-tree-page.py; do not edit by hand.", "people": ids}
    io.open(os.path.join(ROOT, "site", "public", "roots-links.json"), "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print("roots-links: %d people" % len(ids))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true"); ap.add_argument("--accept-unique", action="store_true")
    a = ap.parse_args()
    if a.check:
        try: have = jl(os.path.join(OUT, "tree.json"))["meta"]["inputs"]
        except Exception: print("tree page: not built yet. python3 tools/build-tree-page.py"); sys.exit(1)
        if have != inputs_hash(): print("tree page is STALE: the register, the English line, the families, the place files or the builder changed since it was built.\n  python3 tools/build-tree-page.py --accept-unique"); sys.exit(1)
        print("tree page is current"); return
    build(a)
    tree = os.path.join(OUT, "tree.json"); pm = os.path.join(OUT, "place_map.json"); ad = os.path.join(OUT, "atlas-data.json"); page = os.path.join(OUT, "roots.html")
    run([sys.executable, os.path.join(TP, "build_atlas_data.py"), "--atlas", atlas_path(), "--tree", tree, "--place-map", pm, "--out", ad])
    t = jl(tree); t["meta"]["inputs"] = inputs_hash()
    io.open(tree, "w", encoding="utf-8").write(json.dumps(t, ensure_ascii=False, separators=(",", ":")))
    write_roots_links(tree)
    tpl = os.path.join(TP, "tree-views.template.html")
    run([sys.executable, os.path.join(TP, "build_page.py"), "--template", tpl, "--tree", tree, "--atlas-data", ad, "--out", page, "--ext", EXT])
    embed = os.path.join(OUT, "roots.embed.html")
    run([sys.executable, os.path.join(TP, "build_page.py"), "--template", tpl, "--tree", tree, "--atlas-data", ad, "--out", embed, "--embed", "--ext", EXT])
    run([sys.executable, os.path.join(TP, "check_tree_page.py"), "--tree", tree, "--atlas-data", ad, "--page", page])
    run([sys.executable, os.path.join(TP, "check_tree_page.py"), "--tree", tree, "--atlas-data", ad, "--page", embed])

if __name__ == "__main__": main()
