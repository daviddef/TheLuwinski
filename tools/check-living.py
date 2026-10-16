#!/usr/bin/env python3
"""Fail the build if a living person is shown as anything more than a name, a relationship,
and a town and country.

THE RULE (David Defranceski, 16 October 2026; the estate-wide living-people standard).
A living person is NAMED, with their relationship to the people around them and their town
and country, AND NOTHING MORE: no date of any kind, no record, no source, no photograph, no
structured data, no cause of death, no event. Where the archive has a page for the person it
is `noindex` (so out of the sitemap and the search index) and a name page whose every bearer
is living is `noindex` too. THIS ARCHIVE HAS NO PAGE FOR ANYONE IN THE REGISTER, so no living
person has one; the gate still fails if one appears without `noindex`.
Lynn Derrick Luwinski is the one exception and goes the other way: named with his parents
only, not even a town. He is left exactly as he was and is exempt from every rule here.

Until 16 October this gate enforced the OPPOSITE rule (no living name anywhere), and a gate
that passes on a build that now contains the names it used to forbid would be asleep. So it
is inverted, not loosened. What it checks, against the RENDERED output, never the generator:

  data     the generated register (site/src/data/register.json, committed and so public):
           every record flagged living carries only the allowed fields; no date; the place
           is town and country only; every relationship edge that points at a living person
           carries the word Living and not the source's life span; the set of records
           flagged living is exactly the set the shared test (tools/livingtest.py) picks out.
  context  every place a living person's name appears in a built page or served JSON: the
           text that stands with it (its table row, list item, paragraph or chart node, or
           for embedded JSON its own object) must hold no year, no date, no «born/died».
  page     a page whose title or h1 is a living person's name must be `noindex` and must not
           be in sitemap.xml; no JSON-LD may name a living person; a search-index entry may
           not be headed by one.
  leak     (--mode harvest only) the exact dates, comments and profile links the private
           harvest holds for each living person must appear NOWHERE in the build or in any
           tracked file.

Two modes, as before:
  --harvest   the full private harvest is present (local runs). Recognises names exactly.
  --hashes    the repository checkout only (CI). Recognises names by the salted digests in
              data/guarded-hashes.json, which also lists the ids of the living records.

*** KNOWN LIMITS, STATED SO THEY ARE NOT DISCOVERED. ***
 - A person recorded under a single token, and the source's «Unknown …» placeholder records,
   cannot be recognised by name in rendered text (a bare given name would match ordinary
   prose across the site). Those are covered by the data checks and, in embedded JSON, by id.
   Run `python3 tools/make-guarded.py` to see which ids that affects.
 - --harvest builds a guard from the live tree's `first` + `last`, a CURRENT name, and so
   does not recognise a married woman's maiden-name form. --hashes holds those variants. A
   green --harvest run is therefore not permission; both are run locally, harvest first.
 - «the text that stands with a name» is a heuristic about layout. It cannot prove that no
   prose elsewhere on a page describes a living person without naming them.

A check that can only pass proves nothing, so the gate REFUSES (exit 1) rather than reports ok
when it has examined nothing: no files, no guard list, no living record in the register, or a
matcher that sees no living name in a build whose register publishes living people.
tools/selftest-living.py plants a fault for every rule below in a copy and demands the gate
catch each one.
"""
import argparse, hashlib, html as htmllib, json, os, pathlib, re, subprocess, sys, unicodedata
from html.parser import HTMLParser

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import names
import livingtest

ROOT = pathlib.Path(__file__).resolve().parent.parent


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


# ---------------------------------------------------------------- recognising the living
class Matcher:
    """Says whether a block of text names a living person. Exempts Derrick by construction:
    he is never in the guard."""

    def __init__(self, mode, living, digests=None, salt=None):
        self.mode = mode
        self.guards = []          # harvest: (label, regex)
        self.digests = digests or {}
        self.salt = salt
        self.unmatchable = []     # ids that cannot be recognised by name
        if mode == "harvest":
            for p in living:
                first = (p["first"] or "").strip().split()[0] if (p["first"] or "").strip() else ""
                last = (p["last"] or "").strip()
                if len(first) < 3 or len(last) < 3 or "unknown" in (first + last).lower():
                    self.unmatchable.append(p["id"])
                    continue
                rx = re.compile(re.escape(first) + r"[\w\s.,'\"()\-]{0,40}?" + re.escape(last), re.I)
                self.guards.append((f"living person id {p['id']}", rx))
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
        self._script = None
        self._cap = None            # ("title"|"h1", [parts])

    def _classes(self, attrs):
        return set((dict(attrs).get("class") or "").split())

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "meta" and (d.get("name") or "").lower() == "robots" and "noindex" in (d.get("content") or "").lower():
            self.noindex = True
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
        if tag == "title":
            self._cap = ("title", [])
        elif tag == "h1":
            self._cap = ("h1", [])

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
            else:
                self.h1.append(text)
            self._cap = None

    def handle_data(self, data):
        if self._script is not None:
            self._script[2].append(data)
            return
        if not data.strip():
            return
        if self._cap:
            self._cap[1].append(data)
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


def check_dist(dist, matcher, living_ids, F):
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
        # units of text
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
        # scripts: JSON-LD is forbidden outright, other embedded JSON is walked
        for typ, body in pg.scripts:
            if "ld+json" in typ:
                r = matcher.refs(body)
                if r:
                    F.add(rel, "structured data (JSON-LD) names a living person", r[0])
                continue
            for obj in json_objects(body):
                walk_json(obj, rel, matcher, living_ids, F)
        # a page headed by a living person
        head = [pg.title] + pg.h1
        hit = next((r for h in head for r in matcher.refs(h)), None)
        if hit:
            about_living.add(str(rel))
            if not pg.noindex:
                F.add(rel, "a page about a living person lacks noindex", hit)
    # sitemap: no page headed by a living person, and no address that is a living person's name
    sm = root / "sitemap.xml"
    if sm.exists():
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm.read_text(encoding="utf-8", errors="ignore"))
        for loc in locs:
            path = re.sub(r"^https?://[^/]+", "", loc).strip("/")
            if (path + "/index.html" if path else "index.html") in about_living or path + ".html" in about_living:
                F.add("sitemap.xml", "a page about a living person is in the sitemap", "a living person's page")
            r = matcher.refs_slug(path)
            if r:
                F.add("sitemap.xml", "an address in the sitemap is a living person's name", r[0])
    return root, files, about_living


# ---------------------------------------------------------------- the generated register
ALLOWED_LIVING_KEYS = {"id", "name", "first", "last", "sex", "kind", "living", "born", "died",
                       "by", "dy", "byq", "dyq", "facts", "town", "country", "place", "note", "rel"}
EDGE_KEYS = {"id", "n", "rel", "ls"}


def check_register(reg_path, living_ids, expected_ids, digest_set, salt, F):
    if not reg_path.exists():
        sys.exit(f"check-living: REFUSED: {reg_path} not found, so the data rules were not checked. That is not a pass.")
    people = json.load(open(reg_path))["people"]
    flagged = {p["id"] for p in people if p.get("living")}
    if not flagged:
        sys.exit("check-living: REFUSED: the register flags no one as living, so the data rules checked nothing. "
                 "That is not a pass.")
    where = "register.json"
    if expected_ids is not None and flagged != expected_ids:
        F.add(where, "the records flagged living differ from the people the shared test picks out "
              f"(flagged {len(flagged)}, expected {len(expected_ids)})", "set mismatch")
    for p in people:
        if p["id"] in flagged:
            ref = f"living person id {p['id']}"
            extra = set(p) - ALLOWED_LIVING_KEYS
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
                if re.search(r"\d", v) or len(v) > 60 or "|" in v or "/" in v:
                    F.add(where, f"a living record's {k} is not a plain town or country", ref)
            if p.get("place") != ", ".join(x for x in (p.get("town"), p.get("country")) if x):
                F.add(where, "a living record's place is not its town and country", ref)
            for e in p.get("rel", []):
                if set(e) - EDGE_KEYS:
                    F.add(where, "a relationship edge carries fields beyond name, relationship and id", ref)
            if p.get("note") and re.search(r"\d", p["note"]):
                F.add(where, "a living record's note carries a digit", ref)
        else:
            if digest_set and salt:
                d = names.digest(salt, p.get("name"))
                d2 = names.digest(salt, (p.get("first") or "") + " " + (p.get("last") or ""))
                if (d in digest_set or d2 in digest_set) and p["id"] not in livingtest.NAMED_BARE:
                    F.add(where, "a person whose name is guarded as living is published without the living flag",
                          f"id {p['id']}")
        # every edge, anywhere, that points at a living person
        for e in p.get("rel", []):
            if e.get("id") in flagged and e.get("ls") != "Living":
                F.add(where, "a relationship edge to a living person carries the source's life span", f"edge to id {e.get('id')}")
    return len(flagged)


# ---------------------------------------------------------------- the exact leak scan (harvest only)
def fragments_for(p, edge_ls):
    """Strings the private harvest holds for a living person that must appear nowhere."""
    out = []
    for k in ("b", "d"):
        v = (p.get(k) or "").strip()
        if len(v) >= 6:
            out.append((f"{k} date", v))
    for f in p.get("facts", []):
        # Facts whose label ends in a colon («Death of husband:», «Birth of son:», «Marriage to:»)
        # are about somebody else, or shared with them, and carry THAT person's published dates.
        # Only the living person's own events are exact fragments.
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


def leak_scan(root, dist_files, people, living, F):
    by_id = {p["id"]: p for p in people}
    ids = {p["id"] for p in living}
    edge_ls = {}
    for p in people:
        for r in p["rel"]:
            if r["id"] in ids and r.get("ls"):
                edge_ls.setdefault(r["id"], set()).add(r["ls"])
    frags = []
    for p in living:
        for kind, s in fragments_for(p, edge_ls):
            frags.append((p["id"], kind, s))
    targets = list(dist_files) + tracked_text_files(root)
    seen = set()
    for f in targets:
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
                F.add(shown, f"the harvest's {kind} for a living person is present", f"living person id {pid}")
    return len(frags), len(seen)


# ---------------------------------------------------------------- main
def run(dist, mode, root, with_leak_scan=True):
    root = pathlib.Path(root)
    F = Findings()
    harvest_path = root / "data" / "myheritage-tree9.json"
    guarded = json.load(open(root / "data" / "guarded-hashes.json")) if (root / "data" / "guarded-hashes.json").exists() else {}
    people, living = [], []
    if mode == "harvest":
        people = json.load(open(harvest_path))
        living = [p for p in people if livingtest.might_be_alive(p)]
        living_ids = {str(p["id"]) for p in living}
        expected = {p["id"] for p in living}
        matcher = Matcher("harvest", living)
        digest_set, salt = set(guarded.get("digests", [])), guarded.get("salt")
        n_guard = len(living)
    else:
        digest_set = set(guarded.get("digests", []))
        salt = guarded.get("salt")
        ids = guarded.get("living_ids")
        living_ids = {str(i) for i in (ids or [])}
        expected = set(ids) if ids is not None else None
        matcher = Matcher("hashes", [], digests=digest_set, salt=salt)
        n_guard = len(digest_set)
    if not n_guard:
        # A guard list of zero guards nothing and used to print "ok". An empty digests list or a
        # harvest with nobody flagged living is a broken input, not a clean build.
        print(f"check-living: REFUSED ({mode}): 0 guarded people loaded, so nothing was checked. That is not a pass.")
        sys.exit(1)
    if not living_ids:
        print(f"check-living: REFUSED ({mode}): no living ids loaded, so the data rules cannot tell who is living. "
              "That is not a pass.")
        sys.exit(1)
    nflag = check_register(root / "site" / "src" / "data" / "register.json", living_ids, expected,
                           digest_set, salt, F)
    droot, dfiles, about = check_dist(dist, matcher, living_ids, F)
    nfrag = nscan = 0
    if mode == "harvest" and with_leak_scan:
        nfrag, nscan = leak_scan(root, dfiles, people, living, F)
    if F.seen_units == 0 or not matcher.seen:
        print(f"check-living: REFUSED ({mode}): the register publishes {nflag} living people but this check "
              f"recognised none of them by name in {len(dfiles)} built files. A matcher that sees nobody is blind, "
              "not satisfied. That is not a pass.")
        sys.exit(1)
    if F.hits:
        print(f"check-living: FAILED ({mode}): a living person is shown as more than a name, a relationship, "
              "and a town and country")
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
    print(f"check-living: ok ({mode}) — {len(dfiles)} built files (html and served json); "
          f"{nflag} living records in the register, {n_guard} guards{unm}{recog}; the living are named in "
          f"{len(F.seen_pages)} files and nothing more stands with any of them{extra}")
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
