#!/usr/bin/env python3
"""Fail the build if the living-people standard (version 2, 16 October 2026) is broken in this archive.

THE RULE (David Defranceski; the estate's standard, kit/tools/living_rule.py).
  LIVING   born 80 years ago or less (this year minus the birth year) with no death or burial recorded
           and no public source. A person with no birth year cannot be shown to be that young, so is
           not living. A living person is shown as a NAME, their RELATIONSHIPS and their TOWN AND
           COUNTRY, and nothing more: no date, no record, no source, no photograph, no occupation or
           note, no structured data. Their page is `noindex`, so it is in neither the sitemap nor the
           search index.
  PAGES    every person in the register has a page of their own, /people/<slug>/. No name stands
           without one: not in a register row, a chart node, or a relative's family.
  HELD OUT a possible minor (not recorded dead, no public source, NO birth year, and a living parent) is
           published nowhere: no record, no page, not even as someone's relative. A child with a KNOWN
           birth year is not held out (David, 16 October 2026): they follow the standard and are living.
  EXCEPTION Derrick, the subject of the archive, is named with his parents and nothing else, not even a
           town. His page is built to the same bounds and is also `noindex`.

WHAT THIS GATE DOES, against the RENDERED output and the committed data, never the generator:

  who      (--mode harvest) it computes who is living and who is held out FROM THE PRIVATE HARVEST with
           kit/tools/living_rule.py and its OWN code for the three inputs (birth year, recorded death,
           citations), independently of tools/build-register.py and tools/people_decisions.py, and
           demands that the register's living flags, the guard file and the published set agree with it.
           (--mode hashes) it takes the living ids and held-out ids from data/guarded-hashes.json, and
           ALSO re-applies living_rule to the register's own public fields.
  data     the generated register (site/src/data/register.json, committed and so public): a living record
           carries only the allowed fields, no date, a plain town and country (no street, no
           institution), only edges that name a relative; nobody held out is in it, by id or as a
           relative; every relationship edge points at a published person; every record has a unique slug.
  pages    for every person in the register a built page exists. A LIVING person's page is `noindex`,
           carries no JSON-LD, no table, no image, no year or date in the head or the body, and no
           heading but «Family». Everyone else's page is indexable. The register, the people index and
           the blood-relatives chart each reach every person; each relative named on a page is linked
           to their own page.
  exposure the sitemap holds no living page and every non-living page; the search index holds no
           living page and every non-living page; no JSON-LD names a living person.
  context  every place a living person's name appears in a built page or served JSON: the text that
           stands with it (its table row, list item, paragraph or chart node, or for embedded JSON its
           own object) holds no year, no date, no «born/died».
  held out nobody held out appears anywhere: not in the register, the guard file excepted, not in a built
           page or served file, not in any tracked file; by id, and by name (exactly in harvest mode, by
           salted digest in hashes mode where the name has two or more tokens).
  leak     (--mode harvest only) the exact dates, comments and profile links the private harvest holds
           for each living, held-out and bare person appear NOWHERE in the build or in any tracked file.

Two modes:
  --harvest   the full private harvest is present (local runs). Recognises names exactly.
  --hashes    the repository checkout only (CI). Recognises names by the salted digests in
              data/guarded-hashes.json, which also lists the ids of the living and held-out records.

*** KNOWN LIMITS, STATED SO THEY ARE NOT DISCOVERED. ***
 - A person recorded under a single token cannot be recognised by name by digest (a bare given name
   would match ordinary prose across the site); in --hashes mode such a person is covered by id and by
   the data checks only. In --harvest mode a single-token held-out name is searched for as a whole word
   in every built file and every tracked text file, which is strict but not blind to ordinary prose.
 - --harvest builds its guard from the live tree's `first` + `last`, a CURRENT name, and so does not
   recognise a married woman's maiden-name form. --hashes holds those variants. A green --harvest run is
   therefore not permission; both are run locally, harvest first.
 - «The text that stands with a name» is a heuristic about layout. It cannot prove that no prose
   elsewhere on a page describes a living person without naming them.
 - The harvest holds no public-record citations as such; the kit's test is given the comments the tree
   attaches to a person's own facts, which is where a FamilySearch or Arolsen citation shows.

A check that can only pass proves nothing, so the gate REFUSES (exit 1) rather than reports ok when it has
examined nothing: no files, no guard list, no living record in the register, no person page, or a matcher
that sees no living name in a build whose register publishes living people.
tools/selftest-living.py plants a fault for every rule above in a copy and demands the gate catch each one.
"""
import argparse, datetime, hashlib, json, os, pathlib, re, subprocess, sys, unicodedata
from html.parser import HTMLParser

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import names
# The two ARCHIVE DECISIONS (who is the subject, which records are one person) - not a test of who is living.
from people_decisions import NAMED_BARE, DUPLICATES

KIT_TOOLS = ROOT / "site" / "node_modules" / "@daviddef" / "archive-kit" / "kit" / "tools"


def load_rule(root=None):
    kit = (pathlib.Path(root) if root else ROOT) / "site" / "node_modules" / "@daviddef" / "archive-kit" / "kit" / "tools"
    if not (kit / "living_rule.py").exists():
        kit = KIT_TOOLS
    if not (kit / "living_rule.py").exists():
        sys.exit("check-living: REFUSED: kit/tools/living_rule.py is not installed, so who is living cannot be "
                 "computed. Run `npm install` in site/. That is not a pass.")
    if str(kit) not in sys.path:
        sys.path.insert(0, str(kit))
    import living_rule
    return living_rule


def resolve_dist(dist):
    """ARCHIVE_OUT beats --dist, deliberately.

    package.json passes `--dist dist` on the command line, which is the repository default --
    what to read when nobody has said otherwise. ARCHIVE_OUT is an operator saying «read THIS
    build, the one I just made». If the flag won, honouring the operator would mean editing
    package.json. Sessions share this working tree and `dist` is routinely half-written or
    somebody else's. THE LIVING GATE IS THE ONE THAT MUST NEVER BE WRONG, so it must not read a
    build it was not pointed at. Only the last component is replaced.
    """
    out = os.environ.get("ARCHIVE_OUT")
    if not out:
        return dist
    d = (dist or "").rstrip("/\\")
    parent = os.path.dirname(d)
    return os.path.join(parent, out) if parent else out


# ---------------------------------------------------------------- what counts as «more than a name»
YEAR = re.compile(r"(?<![\d])(1[5-9]\d\d|20[0-4]\d)(?![\d])")
MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
DATEISH = re.compile(
    r"(?<!\d)\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*(?:\d{2}|\d{4})(?!\d)"
    r"|\b" + MONTH + r"\s+\d{1,2}\b|\b\d{1,2}(?:st|nd|rd|th)?\s+" + MONTH + r"\b", re.I)
EVENTWORD = re.compile(r"\b(?:born|died|aged?)\b|(?<![\w])[bd]\.(?=\s*\d)", re.I)
# A place that is not a town or a country: an institution, a street, anything with a digit.
NOT_A_PLACE = re.compile(
    r"hospital|hospice|clinic|infirmary|maternity|nursing|care\s*home|retirement|sanatorium|asylum|"
    r"medical|\bhome\b|\bcentre\b|\bcenter\b|\bprison\b|\bstreet\b|\bstr\b|\bstr\.|stra(ss|ß)e|"
    r"\broad\b|\bavenue\b|\bave\b|\blane\b|\bdrive\b|\brua\b|\bavenida\b|\bp\.?\s?o\.?\s?box\b", re.I)


def more_than_a_name(text):
    """The first thing in `text` that a living person's neighbourhood may not hold, or None."""
    if YEAR.search(text):
        return "a year"
    if DATEISH.search(text):
        return "a date"
    if EVENTWORD.search(text):
        return "a born/died/aged word"
    return None


def fold(s):
    return unicodedata.normalize("NFD", (s or "").lower()).encode("ascii", "ignore").decode()


# ---------------------------------------------------------------- who is living, computed independently
# DELIBERATELY NOT SHARED with tools/people_decisions.py (the generator's side). If the generator's idea of
# a birth year, a recorded death or a citation drifted, this must not drift with it. The kit's rule is the
# one thing both call.
_YEAR_RX = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")


def g_year(p):
    m = _YEAR_RX.search(p.get("b") or "")
    return int(m.group(1)) if m else None


def g_dead(p):
    if (p.get("d") or "").strip() or not p.get("alive"):
        return True
    for f in p.get("facts", []):
        t = (f.get("t") or "").strip()
        if f.get("ty") in ("DEAT", "BURI") and not t.endswith(":") and not t.startswith("Death of"):
            return True
    return False


def g_cites(p):
    out = []
    for f in p.get("facts", []):
        t = (f.get("t") or "").strip()
        if t.endswith(":") or t.startswith(("Death of", "Birth of", "Marriage of")):
            continue
        out += [x for x in (f.get("c"), f.get("ac")) if x]
    return out


def g_classify(people, lr, today=None):
    """{id: 'living' | 'held_out' | 'bare' | 'duplicate' | 'dead'} from the harvest, by the kit's rule."""
    by = {p["id"]: p for p in people}

    def living(p):
        return lr.is_living(g_year(p), g_dead(p), g_cites(p), today)

    def parents_of(pid):
        out = set()
        me = by[pid]
        out |= {r["id"] for r in me["rel"] if re.search(r"father|mother|parent", r["rel"], re.I)}
        for q in people:
            if q["id"] != pid and any(r["id"] == pid and re.search(r"\b(son|daughter|child)\b", r["rel"], re.I)
                                      for r in q["rel"]):
                out.add(q["id"])
        return out

    out = {}
    for p in people:
        pid = p["id"]
        if pid in DUPLICATES:
            out[pid] = "duplicate"
        elif pid in NAMED_BARE:
            out[pid] = "bare"
        else:
            plive = any(living(by[x]) for x in parents_of(pid) if x in by)
            if lr.is_held_out(pid, g_year(p), g_dead(p), g_cites(p), plive, (), today):
                out[pid] = "held_out"
            elif living(p):
                out[pid] = "living"
            else:
                out[pid] = "dead"
    return out


# ---------------------------------------------------------------- recognising names
class Matcher:
    """Says whether a block of text names one of a group of people (the living, or the held out).
    Derrick is never in the living guard, so he is exempt by construction."""

    def __init__(self, mode, group, digests=None, salt=None):
        self.mode = mode
        self.guards = []          # harvest: (label, regex, whole_word_only)
        self.digests = digests or {}
        self.salt = salt
        self.unmatchable = []     # ids that cannot be recognised by name
        if mode == "harvest":
            for p in group:
                nm = (p["name"] or "").strip()
                first = (p["first"] or "").strip().split()[0] if (p["first"] or "").strip() else ""
                last = (p["last"] or "").strip()
                if "unknown" in (first + last).lower():
                    self.unmatchable.append(p["id"])
                elif len(first) >= 3 and len(last) >= 3:
                    rx = re.compile(re.escape(first) + r"[\w\s.,'\"()\-]{0,40}?" + re.escape(last), re.I)
                    self.guards.append((f"person id {p['id']}", rx))
                elif len(nm) >= 3 and " " not in nm:
                    # a single-token name: a whole word, exactly as written
                    self.guards.append((f"person id {p['id']}", re.compile(r"(?<![\w])" + re.escape(nm) + r"(?![\w])")))
                else:
                    self.unmatchable.append(p["id"])
        self.n = len(self.guards) if mode == "harvest" else len(self.digests)
        self.seen = set()         # which guards have been recognised at least once

    def refs_slug(self, path):
        """The same test on an address: /people/first-last/ names a person as surely as a heading."""
        words = re.sub(r"[-_/]+", " ", path).strip()
        if not words:
            return []
        if self.mode == "harvest":
            f = fold(words)
            return [label for label, rx in self.guards if rx.search(f)]
        return self.refs(words.title())

    def refs(self, text):
        if not text:
            return []
        out = []
        if self.mode == "harvest":
            f = fold(text)
            for label, rx in self.guards:
                if rx.search(text) or rx.search(f):
                    out.append(label)
        else:
            for k in names.candidates(re.sub(r"\s+", " ", text)):
                d = hashlib.sha256((self.salt + "|" + k).encode()).hexdigest()[:32]
                if d in self.digests:
                    out.append(f"guarded name {d[:6]}")
        self.seen.update(out)
        return out


# ---------------------------------------------------------------- HTML reading
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param",
        "source", "track", "wbr"}
INLINE = {"a", "abbr", "b", "bdi", "bdo", "cite", "code", "data", "dfn", "em", "i", "kbd", "mark",
          "q", "s", "samp", "small", "span", "strong", "sub", "sup", "time", "u", "var", "label"}
UNIT_TAGS = {"tr", "li", "p", "dd", "dt", "figcaption", "blockquote", "caption", "summary",
             "h1", "h2", "h3", "h4", "h5", "h6", "button", "option"}
UNIT_CLASS = {"node", "card", "item", "entry", "person", "row"}
ATTRS = {"title", "alt", "aria-label", "content", "placeholder", "value"}


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.units = {}             # unit element index -> [text, ...]
        self.elems = []             # (tag, classes)
        self.stack = []
        self.scripts = []           # (type, text)
        self.attrs = []             # attribute values to test
        self.title, self.h1, self.noindex = "", [], False
        self.heads = {2: [], 3: []}   # h2 / h3 text
        self.hrefs = []
        self.count = {"table": 0, "img": 0, "svgimage": 0, "picture": 0, "video": 0}
        self.main = []              # visible text inside <main>
        self.head_attrs = []        # content of the <meta> tags in the head
        self._script = None
        self._cap = None            # ("title"|"h1"|"h2"|"h3", [parts])

    def _classes(self, attrs):
        return set((dict(attrs).get("class") or "").split())

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "meta" and (d.get("name") or "").lower() == "robots" and "noindex" in (d.get("content") or "").lower():
            self.noindex = True
        if tag == "meta" and d.get("content") and (d.get("name") or "").lower() != "robots":
            self.head_attrs.append(d["content"])
        if tag == "a" and d.get("href"):
            self.hrefs.append(d["href"])
        if tag in self.count:
            self.count[tag] += 1
        for k, v in attrs:
            if v and (k in ATTRS or k.startswith("data-")) and k != "data-astro-cid":
                if not (tag == "meta" and (d.get("name") or "").lower() == "robots"):
                    self.attrs.append(v)
        if tag in VOID:
            return
        if tag == "script":
            self._script = [d.get("type") or "", d.get("src"), []]
            return
        self.elems.append((tag, self._classes(attrs)))
        self.stack.append(len(self.elems) - 1)
        if tag in ("title", "h1", "h2", "h3"):
            self._cap = (tag, [])

    def handle_endtag(self, tag):
        if tag == "script" and self._script is not None:
            if not self._script[1]:
                self.scripts.append((self._script[0], "".join(self._script[2])))
            self._script = None
            return
        if tag in VOID:
            return
        # pop to the matching open element (tolerates omitted end tags)
        for i in range(len(self.stack) - 1, -1, -1):
            if self.elems[self.stack[i]][0] == tag:
                del self.stack[i:]
                break
        if self._cap and self._cap[0] == tag:
            text = " ".join("".join(self._cap[1]).split())
            if tag == "title":
                self.title = text
            elif tag == "h1":
                self.h1.append(text)
            else:
                self.heads[int(tag[1])].append(text)
            self._cap = None

    def handle_data(self, data):
        if self._script is not None:
            self._script[2].append(data)
            return
        if not data.strip():
            return
        if self._cap:
            self._cap[1].append(data)
        if any(self.elems[i][0] == "main" for i in self.stack):
            self.main.append(data.strip())
        unit = None
        for idx in reversed(self.stack):
            tag, cls = self.elems[idx]
            if tag in UNIT_TAGS or (cls & UNIT_CLASS):
                unit = idx
                break
        if unit is None:
            for idx in reversed(self.stack):
                if self.elems[idx][0] not in INLINE:
                    unit = idx
                    break
        if unit is None:
            unit = -1
        self.units.setdefault(unit, []).append(data.strip())


def parse_html(text):
    p = Page()
    p.feed(text)
    p.close()
    return p


# ---------------------------------------------------------------- JSON reading
NAME_KEYS = {"name", "n", "title"}
IDENT_KEYS = {"slug", "id", "sid", "pid", "rid"}      # a value here says WHICH person the object is
ID_KEYS = IDENT_KEYS | {"spouseSlug"}                  # scalars an audited chart node may carry
HEAD_KEYS = {"t", "s", "h", "heading", "url", "page", "href"}
LONG_KEYS = {"q", "text", "body", "content", "desc", "description"}


def json_objects(script_text):
    """Every JSON object or array assigned in a script, decoded."""
    dec = json.JSONDecoder()
    out = []
    for m in re.finditer(r"=\s*([\[{])", script_text):
        try:
            obj, _ = dec.raw_decode(script_text, m.start(1))
            out.append(obj)
        except ValueError:
            continue
    return out


class Findings:
    def __init__(self):
        self.hits = []
        self.seen_units = 0      # units (or JSON strings) in which a living name was recognised
        self.seen_pages = set()
        self.audited_objects = 0
        self.stats = {}

    def add(self, where, rule, ref):
        self.hits.append((str(where), rule, ref))


def audit_living_object(obj, where, rule_ref, F):
    """A JSON object that IS a living person (matched by id or by name): its own scalar
    fields may hold a name, an id and a relationship, and nothing with a digit in it."""
    F.audited_objects += 1
    for k, v in obj.items():
        if isinstance(v, (dict, list)):
            continue      # nested objects are other people, audited on their own
        if k in NAME_KEYS or k in ID_KEYS:
            continue
        if v in ("", None, False):
            continue
        if isinstance(v, str) and not re.search(r"\d", v):
            continue      # a relationship word, a tag
        F.add(where, f"a living person's chart node holds more than a name (field {k!r})", rule_ref)


def walk_json(obj, where, matcher, living_ids, F, key=None, owner=None):
    if isinstance(obj, dict):
        ident = None
        for k in IDENT_KEYS:
            if k in obj and str(obj[k]) in living_ids:
                ident = f"living person id {obj[k]}"
        named = None
        for k in NAME_KEYS:
            if isinstance(obj.get(k), str):
                r = matcher.refs(obj[k])
                if r:
                    named = r[0]
        if ident or named:
            F.seen_units += 1
            F.seen_pages.add(str(where))
            audit_living_object(obj, where, ident or named, F)
        for k, v in obj.items():
            walk_json(v, where, matcher, living_ids, F, key=k, owner=obj)
    elif isinstance(obj, list):
        for v in obj:
            walk_json(v, where, matcher, living_ids, F, key=key, owner=owner)
    elif isinstance(obj, str):
        refs = matcher.refs(obj)
        if not refs:
            return
        F.seen_units += 1
        F.seen_pages.add(str(where))
        if key in HEAD_KEYS:
            F.add(where, "a living person heads or addresses a search-index or data entry", refs[0])
        elif key in NAME_KEYS and owner is not None:
            pass              # the owner object was audited above
        elif key in LONG_KEYS or len(obj) > 160:
            # running text (the folded search haystack): a digit hard against the name
            f = fold(obj)
            for label, rx in getattr(matcher, "guards", []):
                for m in rx.finditer(f):
                    if re.search(r"\d", f[m.end(): m.end() + 10]):
                        F.add(where, "a digit stands hard against a living person's name in indexed text", label)
        else:
            why = more_than_a_name(obj)
            if why:
                F.add(where, f"{why} stands in the same field as a living person's name", refs[0])


# ---------------------------------------------------------------- the passes over dist
def pages(dist):
    p = pathlib.Path(dist)
    if not p.is_absolute():
        p = pathlib.Path.cwd() / p
    f = sorted(p.rglob("*.html")) + sorted(p.rglob("*.json"))
    if not f:
        sys.exit(f"check-living: REFUSED: no HTML or JSON found under {p}, so nothing was checked. That is not a pass.")
    return p, f


def page_path(slug):
    return f"people/{slug}/index.html"


def sitemap_paths(root):
    sm = root / "sitemap.xml"
    if not sm.exists():
        return None
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm.read_text(encoding="utf-8", errors="ignore"))
    return {re.sub(r"^https?://[^/]+", "", loc).strip("/") for loc in locs}


def check_dist(dist, matcher, living_ids, F):
    """The context pass over every built file: what stands with a living person's name."""
    root, files = pages(dist)
    about_living = set()           # relative paths of pages headed by a living person
    for f in files:
        rel = f.relative_to(root)
        raw = f.read_text(encoding="utf-8", errors="ignore")
        if f.suffix == ".json":
            try:
                walk_json(json.loads(raw), rel, matcher, living_ids, F)
            except ValueError:
                pass
            continue
        pg = parse_html(raw)
        for idx, parts in pg.units.items():
            text = " ".join(parts)
            refs = matcher.refs(text)
            if not refs:
                continue
            F.seen_units += 1
            F.seen_pages.add(str(rel))
            why = more_than_a_name(text)
            if why:
                F.add(rel, f"{why} stands with a living person's name", refs[0])
        for v in pg.attrs:
            refs = matcher.refs(v)
            if refs:
                F.seen_units += 1
                F.seen_pages.add(str(rel))
                why = more_than_a_name(v)
                if why:
                    F.add(rel, f"{why} in an attribute with a living person's name", refs[0])
        # scripts: JSON-LD is forbidden outright for the living, other embedded JSON is walked
        for typ, body in pg.scripts:
            if "ld+json" in typ:
                r = matcher.refs(body)
                if r:
                    F.add(rel, "structured data (JSON-LD) names a living person", r[0])
                continue
            for obj in json_objects(body):
                walk_json(obj, rel, matcher, living_ids, F)
        head = [pg.title] + pg.h1
        hit = next((r for h in head for r in matcher.refs(h)), None)
        if hit:
            about_living.add(str(rel))
            if not pg.noindex:
                F.add(rel, "a page about a living person lacks noindex", hit)
    return root, files, about_living


# ---------------------------------------------------------------- the person pages
def check_person_pages(root, files, reg, F, sm, index_hs, held_ids_in_reg):
    """One page per person, and what each kind of page may carry. Returns counts for the report."""
    people = reg["people"]
    by_id = {p["id"]: p for p in people}
    slug_of = {p["id"]: p["slug"] for p in people}
    n = {"living_pages": 0, "living_noindex": 0, "living_in_sitemap": 0, "living_in_index": 0,
         "living_jsonld": 0, "living_tables": 0, "living_images": 0, "living_years": 0,
         "dead_pages": 0, "dead_noindex": 0, "dead_in_sitemap": 0, "dead_in_index": 0, "dead_personld": 0,
         "bare_pages": 0}      # living_* counts the living AND the named-only subject; bare_pages is the subject alone
    idx_h = {re.sub(r"/+$", "", h) + "/" for h in index_hs} if index_hs is not None else None
    for r in people:
        rel = page_path(r["slug"])
        f = root / rel
        ref = f"person id {r['id']}"
        if not f.exists():
            F.add(rel, "a named person has no page", ref)
            continue
        raw = f.read_text(encoding="utf-8", errors="ignore")
        pg = parse_html(raw)
        url = f"/people/{r['slug']}/"
        in_sm = (sm is not None) and (f"people/{r['slug']}" in sm)
        in_ix = (idx_h is not None) and (url in idx_h)
        live = bool(r.get("living")) or bool(r.get("bare"))
        # every relative named on the page leads to their own page
        for e in r.get("rel", []):
            tgt = slug_of.get(e["id"])
            if tgt and f"/people/{tgt}/" not in pg.hrefs:
                F.add(rel, "a relative named here is not linked to their own page", f"{ref} -> id {e['id']}")
        if live:
            n["living_pages"] += 1
            n["bare_pages"] += 1 if r.get("bare") else 0
            if not pg.noindex:
                F.add(rel, "a living person's page lacks noindex", ref)
            else:
                n["living_noindex"] += 1
            if in_sm:
                n["living_in_sitemap"] += 1
                F.add(rel, "a living person's page is in the sitemap", ref)
            if in_ix:
                n["living_in_index"] += 1
                F.add(rel, "a living person's page is in the search index", ref)
            if any("ld+json" in t for t, _ in pg.scripts):
                n["living_jsonld"] += 1
                F.add(rel, "structured data (JSON-LD) on a living person's page", ref)
            if pg.count["table"]:
                n["living_tables"] += 1
                F.add(rel, "a table on a living person's page", ref)
            if pg.count["img"] or pg.count["picture"] or pg.count["video"]:
                n["living_images"] += 1
                F.add(rel, "an image on a living person's page", ref)
            main = " ".join(pg.main)
            head = " ".join([pg.title] + pg.head_attrs)
            bad = more_than_a_name(main) or more_than_a_name(head)
            if bad:
                n["living_years"] += 1
                F.add(rel, f"{bad} on a living person's page", ref)
            extra = [h for lvl in (2, 3) for h in pg.heads[lvl] if h != "Family"]
            if extra:
                F.add(rel, "a living person's page has a section beyond «Family» (a record, a source, a note)", ref)
            if r.get("bare") and r.get("place"):
                F.add(rel, "the subject of the archive carries a place; he is named with his parents and nothing else", ref)
        else:
            n["dead_pages"] += 1
            if pg.noindex:
                n["dead_noindex"] += 1
                F.add(rel, "a page for a person who is not living is noindex, hiding them for no reason", ref)
            if sm is not None:
                if in_sm:
                    n["dead_in_sitemap"] += 1
                else:
                    F.add(rel, "a page for a person who is not living is missing from the sitemap", ref)
            if idx_h is not None:
                if in_ix:
                    n["dead_in_index"] += 1
                else:
                    F.add(rel, "a page for a person who is not living is missing from the search index", ref)
            if any("ld+json" in t and '"Person"' in b for t, b in pg.scripts):
                n["dead_personld"] += 1
    return n


def check_listings(root, reg, F):
    """The register, the people index and the blood-relatives chart reach every person."""
    people = reg["people"]
    want = {f"/people/{p['slug']}/" for p in people}
    for name in ("register", "people"):
        f = root / name / "index.html"
        if not f.exists():
            F.add(f"{name}/index.html", "the page that should list every person is not built", "listing")
            continue
        pg = parse_html(f.read_text(encoding="utf-8", errors="ignore"))
        missing = want - set(pg.hrefs)
        if missing:
            F.add(f"{name}/index.html", f"{len(missing)} person(s) in the register are named or listed without a link to their page",
                  sorted(missing)[0])
    f = root / "bloodline" / "index.html"
    if f.exists():
        ids = {str(p["id"]) for p in people}
        pg = parse_html(f.read_text(encoding="utf-8", errors="ignore"))
        for typ, body in pg.scripts:
            for obj in json_objects(body):
                if isinstance(obj, dict) and obj and all(isinstance(v, dict) for v in obj.values()):
                    for k in obj:
                        if k not in ids:
                            F.add("bloodline/index.html", "a chart node names someone with no person page", f"node {k}")
    # every internal person link resolves
    for h in sorted(root.rglob("*.html")):
        t = h.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'href="(/people/([^"/#?]+)/)', t):
            if not (root / "people" / m.group(2) / "index.html").exists():
                F.add(h.relative_to(root), "a link to a person page that does not exist", m.group(1))


# ---------------------------------------------------------------- the generated register
ALLOWED_LIVING_KEYS = {"id", "name", "first", "last", "sex", "kind", "living", "born", "died",
                       "by", "dy", "byq", "dyq", "facts", "town", "country", "place", "note", "rel", "slug"}
ALLOWED_BARE_KEYS = ALLOWED_LIVING_KEYS | {"bare"}
EDGE_KEYS = {"id", "n", "rel", "ls"}
PARENT_WORDS = re.compile(r"father|mother|parent", re.I)


def check_register(reg_path, expected, held_ids, digest_set, salt, F, lr):
    """The data rules. `expected` = {'living': set, 'held': set, 'bare': set, 'source': str}."""
    if not reg_path.exists():
        sys.exit(f"check-living: REFUSED: {reg_path} not found, so the data rules were not checked. That is not a pass.")
    reg = json.load(open(reg_path))
    people = reg["people"]
    ids = {p["id"] for p in people}
    flagged = {p["id"] for p in people if p.get("living")}
    if not flagged:
        sys.exit("check-living: REFUSED: the register flags no one as living, so the data rules checked nothing. "
                 "That is not a pass.")
    where = "register.json"
    if expected["living"] is not None and flagged != expected["living"]:
        F.add(where, "the records flagged living differ from the people the kit's rule picks out "
              f"(flagged {len(flagged)}, expected {len(expected['living'])}; from {expected['source']})", "set mismatch")
    for hid in held_ids:
        if hid in ids:
            F.add(where, "a held-out person is published in the register", f"id {hid}")
    blob = json.dumps(people)
    for hid in held_ids:
        if re.search(r"(?<!\d)%d(?!\d)" % hid, blob.replace('"id": %d' % hid, "")) or \
           any(e["id"] == hid for p in people for e in p.get("rel", [])):
            F.add(where, "a held-out person is named as somebody's relative", f"id {hid}")
    slugs = [p.get("slug") for p in people]
    if any(not s for s in slugs) or len(set(slugs)) != len(slugs):
        F.add(where, "a record has no slug, or two records share one (a person page cannot be addressed)", "slug")
    for p in people:
        pid = p["id"]
        ref = f"person id {pid}"
        for e in p.get("rel", []):
            if e.get("id") not in ids:
                F.add(where, "a relationship edge points at someone who is not published (no page)", f"{ref} -> id {e.get('id')}")
        if pid in flagged or p.get("bare"):
            allowed = ALLOWED_BARE_KEYS if p.get("bare") else ALLOWED_LIVING_KEYS
            extra = set(p) - allowed
            if extra:
                F.add(where, f"a living record carries fields beyond the allowed ones ({', '.join(sorted(extra))})", ref)
            for k in ("born", "died"):
                if p.get(k):
                    F.add(where, f"a living record carries a {k} date", ref)
            for k in ("by", "dy", "byq", "dyq"):
                if p.get(k) not in (None, ""):
                    F.add(where, f"a living record carries a {k} year", ref)
            if p.get("facts"):
                F.add(where, "a living record carries events or facts", ref)
            for k in ("town", "country", "place"):
                v = p.get(k) or ""
                if re.search(r"\d", v) or len(v) > 60 or "|" in v or "/" in v or NOT_A_PLACE.search(v):
                    F.add(where, f"a living record's {k} is not a plain town or country", ref)
            if p.get("place") != ", ".join(x for x in (p.get("town"), p.get("country")) if x) and not p.get("bare"):
                F.add(where, "a living record's place is not its town and country", ref)
            if p.get("bare"):
                if p.get("place") or p.get("town") or p.get("country"):
                    F.add(where, "the subject of the archive carries a place", ref)
                if any(not PARENT_WORDS.search(e["rel"]) for e in p.get("rel", [])):
                    F.add(where, "the subject of the archive is drawn with more than his parents", ref)
            for e in p.get("rel", []):
                if set(e) - EDGE_KEYS:
                    F.add(where, "a relationship edge carries fields beyond name, relationship and id", ref)
                if e.get("ls") not in (None, "Living"):
                    F.add(where, "a relationship edge on a living record carries a life span", ref)
            if p.get("note") and re.search(r"\d", p["note"]):
                F.add(where, "a living record's note carries a digit", ref)
        else:
            if digest_set and salt:
                d = names.digest(salt, p.get("name"))
                d2 = names.digest(salt, (p.get("first") or "") + " " + (p.get("last") or ""))
                if (d in digest_set or d2 in digest_set) and pid not in NAMED_BARE:
                    F.add(where, "a person whose name is guarded as living is published without the living flag", ref)
        # every edge, anywhere, that points at a living person
        for e in p.get("rel", []):
            if (e.get("id") in flagged or e.get("id") in NAMED_BARE) and e.get("ls") != "Living":
                F.add(where, "a relationship edge to a living person carries the source's life span", f"edge to id {e.get('id')}")
    # THE KIT'S RULE RE-APPLIED TO THE REGISTER'S OWN PUBLIC FIELDS, so that CI, which has no harvest, still
    # tests the generator. Nobody the register publishes as not living may be, by the kit's rule, living
    # (a birth year inside the window and no sign of a death) or a possible minor. The register knows
    # nothing of the tree's «deceased» marker, so a person it publishes with a recent birth year and no death
    # would be a loud failure here even if the tree called them dead: that is the safe direction, and it
    # is a person for a human to look at.
    year_now = datetime.date.today().year
    flagged_or_bare = flagged | {p["id"] for p in people if p.get("bare")}
    for p in people:
        if p["id"] in flagged_or_bare or p.get("kind") == "document":
            continue
        by = p.get("by")
        dead = bool(p.get("dy") or p.get("died") or any(
            f.get("ty") in ("DEAT", "BURI") and not str(f.get("t") or "").endswith(":") for f in p.get("facts", [])))
        cites = [x for f in p.get("facts", []) for x in (f.get("c"), f.get("ac")) if x]
        plive = any(e["id"] in flagged_or_bare and PARENT_WORDS.search(e["rel"]) for e in p.get("rel", [])) or \
            any(p["id"] == e["id"] and re.search(r"\b(son|daughter|child)\b", e["rel"], re.I)
                for q in people if q["id"] in flagged_or_bare for e in q.get("rel", []))
        if lr.is_living(by, dead, cites, year_now):
            F.add(where, "a record the kit's rule calls living is published as if not living", f"person id {p['id']}")
        if lr.possible_minor(by, dead, cites, plive, year_now):
            F.add(where, "a possible minor is published", f"person id {p['id']}")
    return reg, flagged


# ---------------------------------------------------------------- the held out
SERVED = {".html", ".json", ".xml", ".txt", ".js", ".css", ".svg", ".tsv", ".csv", ".webmanifest", ".map"}


def served_files(droot):
    """Every text file the build serves, not only the pages: a held-out person in a sitemap, a data file or a
    script is as published as one in a page."""
    return [f for f in sorted(pathlib.Path(droot).rglob("*")) if f.is_file() and f.suffix.lower() in SERVED]


def scan_held_out(served, droot, tracked, held, held_ids, guard_digests, salt, mode, F, root):
    """Nobody held out appears anywhere: by id in any served or tracked file but the guard file; by name
    (exactly in harvest mode; by digest where the name has two or more tokens, in hashes mode)."""
    hm = Matcher(mode, held if mode == "harvest" else [], digests=guard_digests, salt=salt)
    idrx = [(i, re.compile(r"(?<!\d)%d(?!\d)" % i)) for i in held_ids]
    n_files = 0
    for f in list(served) + list(tracked):
        if f.name == "guarded-hashes.json":
            continue
        try:
            t = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        n_files += 1
        try:
            shown = f.relative_to(droot)
        except ValueError:
            try:
                shown = f.relative_to(root)
            except ValueError:
                shown = f.name
        for i, rx in idrx:
            if rx.search(t):
                F.add(shown, "a held-out person's id appears", f"id {i}")
        text = re.sub(r"<[^>]+>", " ", t) if f.suffix in (".html", ".xml", ".svg") else t
        if mode == "harvest":
            r = hm.refs(text)
        elif guard_digests and len(text) < 600000:
            r = hm.refs(text)
        else:
            r = []
        if r:
            F.add(shown, "a held-out person is named", r[0])
    return n_files


# ---------------------------------------------------------------- the exact leak scan (harvest only)
def fragments_for(p, edge_ls):
    """Strings the private harvest holds for a person that must appear nowhere."""
    out = []
    for k in ("b", "d"):
        v = (p.get(k) or "").strip()
        if len(v) >= 6:
            out.append((f"{k} date", v))
    for f in p.get("facts", []):
        # Facts whose label ends in a colon («Death of husband:», «Birth of son:», «Marriage to:»)
        # are about somebody else, or shared with them, and carry THAT person's published dates.
        # Only the person's own events are exact fragments.
        if (f.get("t") or "").strip().endswith(":"):
            continue
        v = (f.get("date") or "").strip()
        if len(v) >= 6:
            out.append(("fact date", v))
        for kk in ("c", "ac"):
            v = (f.get(kk) or "").strip()
            if len(v) >= 14:
                out.append(("fact comment", v))
    prof = (p.get("profile") or "").strip()
    if len(prof) >= 10:
        out.append(("profile link", prof))
    for ls in edge_ls.get(p["id"], set()):
        if len(ls) >= 8:
            out.append(("relationship life span", ls))
    return out


def tracked_text_files(root):
    try:
        raw = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True).stdout
    except Exception:
        return []
    out = []
    for rel in raw.decode("utf-8", "ignore").split("\0"):
        if not rel or rel.startswith("node_modules/") or rel.endswith(".lock"):
            continue
        if pathlib.Path(rel).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".ico", ".woff", ".woff2", ".zip"}:
            continue
        p = root / rel
        if p.is_file() and p.stat().st_size < 8_000_000:
            out.append(p)
    return out


def leak_scan(root, dist_files, people, group, tracked, F):
    ids = {p["id"] for p in group}
    edge_ls = {}
    for p in people:
        for r in p["rel"]:
            if r["id"] in ids and r.get("ls"):
                edge_ls.setdefault(r["id"], set()).add(r["ls"])
    frags = []
    for p in group:
        for kind, s in fragments_for(p, edge_ls):
            frags.append((p["id"], kind, s))
    seen = set()
    for f in list(dist_files) + tracked:
        if f in seen:
            continue
        seen.add(f)
        if f.name == "guarded-hashes.json":
            continue
        try:
            t = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pid, kind, s in frags:
            if s in t:
                try:
                    shown = f.relative_to(root)
                except ValueError:
                    shown = f.name
                F.add(shown, f"the harvest's {kind} for a living, held-out or named-only person is present", f"person id {pid}")
    return len(frags), len(seen)


# ---------------------------------------------------------------- main
def run(dist, mode, root, with_leak_scan=True, quiet=False):
    root = pathlib.Path(root)
    lr = load_rule(root)
    F = Findings()
    harvest_path = root / "data" / "myheritage-tree9.json"
    gpath = root / "data" / "guarded-hashes.json"
    if not gpath.exists():
        print(f"check-living: REFUSED ({mode}): data/guarded-hashes.json is missing, so there is no guard list. That is not a pass.")
        sys.exit(1)
    guarded = json.load(open(gpath))
    digest_set, salt = set(guarded.get("digests", [])), guarded.get("salt")
    g_living = [int(i) for i in guarded.get("living_ids", [])]
    g_held = [int(i) for i in guarded.get("held_out_ids", [])]
    held_digests = set(guarded.get("held_out_digests", []))
    people, living_p, held_p, bare_p = [], [], [], []
    if mode == "harvest":
        people = json.load(open(harvest_path))
        status = g_classify(people, lr)
        living_p = [p for p in people if status[p["id"]] == "living"]
        held_p = [p for p in people if status[p["id"]] == "held_out"]
        bare_p = [p for p in people if status[p["id"]] == "bare"]
        living_ids = {str(p["id"]) for p in living_p}
        expected = {"living": {p["id"] for p in living_p}, "source": "the harvest"}
        held_ids = [p["id"] for p in held_p]
        matcher = Matcher("harvest", living_p)
        n_guard = len(living_p)
        # the guard file must agree with the harvest, or CI is guarding the wrong people
        if sorted(g_living) != sorted(expected["living"]):
            F.add("data/guarded-hashes.json", "the guard file's living ids differ from the people the kit's rule picks out "
                  "(run tools/make-guarded.py)", "guard file")
        if sorted(g_held) != sorted(held_ids):
            F.add("data/guarded-hashes.json", "the guard file's held-out ids differ from the people the kit's rule holds out "
                  "(run tools/make-guarded.py)", "guard file")
    else:
        living_ids = {str(i) for i in g_living}
        expected = {"living": set(g_living) if "living_ids" in guarded else None, "source": "the guard file"}
        held_ids = g_held
        matcher = Matcher("hashes", [], digests=digest_set, salt=salt)
        n_guard = len(digest_set)
    if not n_guard:
        # A guard list of zero guards nothing and used to print "ok". An empty digests list or a
        # harvest with nobody living is a broken input, not a clean build.
        print(f"check-living: REFUSED ({mode}): 0 guarded people loaded, so nothing was checked. That is not a pass.")
        sys.exit(1)
    if not living_ids:
        print(f"check-living: REFUSED ({mode}): no living ids loaded, so the data rules cannot tell who is living. "
              "That is not a pass.")
        sys.exit(1)
    reg, flagged = check_register(root / "site" / "src" / "data" / "register.json", expected, held_ids,
                                  digest_set, salt, F, lr)
    nflag = len(flagged)
    droot, dfiles, about = check_dist(dist, matcher, living_ids, F)
    sm = sitemap_paths(droot)
    ix = None
    ixf = droot / "searchindex.json"
    if ixf.exists():
        try:
            rows = json.loads(ixf.read_text(encoding="utf-8"))
            rows = rows.get("entries", []) if isinstance(rows, dict) else rows
            ix = {e.get("h") or e.get("url", "") for e in rows}
        except ValueError:
            F.add("searchindex.json", "the search index is not readable JSON", "index")
    if not [p for p in reg["people"] if not p.get("living") and not p.get("bare")]:
        print(f"check-living: REFUSED ({mode}): the register publishes no person who is not living, so the "
              "positive controls (indexed, in the sitemap) had nothing to test. That is not a pass.")
        sys.exit(1)
    counts = check_person_pages(droot, dfiles, reg, F, sm, ix, held_ids)
    if counts["living_pages"] + counts["dead_pages"] == 0:
        print(f"check-living: REFUSED ({mode}): no person page was found under {droot}, so nothing was checked. "
              "That is not a pass.")
        sys.exit(1)
    check_listings(droot, reg, F)
    # the sitemap: no address that is a living person's name, whatever the page says
    if sm is not None:
        for path in sorted(sm):
            r = matcher.refs_slug(path)
            if r:
                F.add("sitemap.xml", "an address in the sitemap is a living person's name", r[0])
    tracked = tracked_text_files(root)
    nheld_files = 0
    if held_ids or held_digests:
        if mode == "harvest":
            nheld_files = scan_held_out(served_files(droot), droot, tracked, held_p, held_ids, set(), salt, "harvest", F, root)
        else:
            nheld_files = scan_held_out(served_files(droot), droot, tracked, [], held_ids, held_digests, salt, "hashes", F, root)
    nfrag = nscan = 0
    if mode == "harvest" and with_leak_scan:
        nfrag, nscan = leak_scan(root, dfiles, people, living_p + held_p + bare_p, tracked, F)
    if F.seen_units == 0 or not matcher.seen:
        print(f"check-living: REFUSED ({mode}): the register publishes {nflag} living people but this check "
              f"recognised none of them by name in {len(dfiles)} built files. A matcher that sees nobody is blind, "
              "not satisfied. That is not a pass.")
        sys.exit(1)
    if F.hits:
        print(f"check-living: FAILED ({mode}): the living-people standard is broken")
        seen = set()
        for where, rule, ref in F.hits:
            line = f"  {where}: {rule} [{ref}]"
            if line not in seen:
                seen.add(line)
                print(line)
        sys.exit(1)
    recog = f"; {len(matcher.seen)} of {matcher.n} guards recognised in the build"
    extra = f"; {nfrag} exact fragments searched for in {nscan} files" if mode == "harvest" else ""
    unm = f"; {len(matcher.unmatchable)} not recognisable by name (data and id checks only)" if mode == "harvest" else ""
    c = counts
    print(f"check-living: ok ({mode}) - {len(dfiles)} built files (html and served json); "
          f"{nflag} living records and {len(held_ids)} held out, {n_guard} guards{unm}{recog}; "
          f"{c['living_pages']} living pages (of which {c['bare_pages']} named-only): "
          f"noindex {c['living_noindex']}, in sitemap {c['living_in_sitemap']}, in search index {c['living_in_index']}, "
          f"JSON-LD {c['living_jsonld']}, tables {c['living_tables']}, images {c['living_images']}, years {c['living_years']}; "
          f"{c['dead_pages']} other person pages: noindex {c['dead_noindex']}, in sitemap {c['dead_in_sitemap']}, "
          f"in search index {c['dead_in_index']}, Person JSON-LD {c['dead_personld']}; "
          f"held-out scanned in {nheld_files} files{extra}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", default="dist")
    ap.add_argument("--mode", choices=["auto", "harvest", "hashes"], default="auto")
    ap.add_argument("--root", default=str(ROOT), help="repository root (default: this checkout)")
    ap.add_argument("--no-leak-scan", action="store_true")
    a = ap.parse_args()
    dist = resolve_dist(a.dist)
    if dist != a.dist:
        print(f"  ..    reading {dist} (ARCHIVE_OUT)")
    mode = a.mode
    if mode == "auto":
        mode = "harvest" if (pathlib.Path(a.root) / "data" / "myheritage-tree9.json").exists() else "hashes"
    sys.exit(run(dist, mode, a.root, with_leak_scan=not a.no_leak_scan))
