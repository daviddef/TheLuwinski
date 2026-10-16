#!/usr/bin/env python3
"""Plant a fault for every rule of tools/check-living.py in a COPY of the build and demand that the gate
catch it. A check that can only pass proves nothing.

For each rule there is a fault that must make the gate exit 1 with that rule's message, and for the rules
that depend on context there is a control that must NOT fail, so the gate is shown to be specific as well
as sensitive:

  - the untouched build passes (the baseline), in both modes where both can run;
  - a year planted beside a DEAD person's name, or in a dead person's page, does not fail (it is their own);
  - and a build in which no living person is recognised, an empty build, an empty guard list and a register
    that flags no one living are all REFUSED, never reported ok.

Every planted value is one that no living person can have (the year 1799, a life span «1799 - 1850», a
date of 1799) or is computed from the current year in the copy; no real person's value is a literal here.
The names it plants beside come from site/src/data/register.json, which is public, so this runs in CI as
well as locally. The harvest-only rules (the exact leak scan, the guard file against the harvest, a
held-out name) run only where the harvest is present and are reported as skipped where it is not.

Also tested, in the same copy: the search index leaves out a noindex page (tools/build-search.py), the
search gate refuses a noindex page that is IN the index (tools/check-search.py), and the kit's sitemap tool
leaves out a noindex page and takes the page back the moment the tag goes.

Usage: python3 tools/selftest-living.py --dist site/dist
Exit 0 only if every planted fault was caught and every control passed.
"""
import argparse, datetime, hashlib, json, os, pathlib, re, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import names
GATE = ROOT / "tools" / "check-living.py"
KIT_SITEMAP = ROOT / "site" / "node_modules" / "@daviddef" / "archive-kit" / "kit" / "tools" / "sitemap.py"


def run_gate(root, dist, mode):
    env = {k: v for k, v in os.environ.items() if k != "ARCHIVE_OUT"}
    r = subprocess.run([sys.executable, str(GATE), "--root", str(root), "--dist", str(dist), "--mode", mode],
                       capture_output=True, text=True, env=env)
    return r.returncode, (r.stdout + r.stderr)


class Sandbox:
    """A scratch repository root and a scratch copy of the build, rebuilt for every fault."""

    def __init__(self, dist, have_harvest):
        self.dist_src = pathlib.Path(dist)
        self.have_harvest = have_harvest
        self.base = pathlib.Path(tempfile.mkdtemp(prefix="selftest-living-"))

    def fresh(self):
        shutil.rmtree(self.base, ignore_errors=True)
        (self.base / "data").mkdir(parents=True)
        (self.base / "site" / "src" / "data").mkdir(parents=True)
        shutil.copy(ROOT / "data" / "guarded-hashes.json", self.base / "data")
        shutil.copy(ROOT / "site" / "src" / "data" / "register.json", self.base / "site" / "src" / "data")
        if self.have_harvest:
            shutil.copy(ROOT / "data" / "myheritage-tree9.json", self.base / "data")
        shutil.copytree(self.dist_src, self.base / "dist")
        return self.base, self.base / "dist"

    def done(self):
        shutil.rmtree(self.base, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", default="site/dist")
    a = ap.parse_args()
    dist = pathlib.Path(a.dist)
    if os.environ.get("ARCHIVE_OUT"):
        dist = dist.parent / os.environ["ARCHIVE_OUT"]
    if not dist.is_absolute():
        dist = pathlib.Path.cwd() / dist
    if not (dist / "register" / "index.html").exists():
        sys.exit(f"selftest-living: REFUSED: {dist} has no register page, so there is nothing to plant a fault in")
    harvest = (ROOT / "data" / "myheritage-tree9.json").exists()
    modes = ["hashes"] + (["harvest"] if harvest else [])
    reg = json.load(open(ROOT / "site" / "src" / "data" / "register.json"))
    people = reg["people"]
    guard = json.load(open(ROOT / "data" / "guarded-hashes.json"))
    living = [p for p in people if p.get("living")]
    bare = [p for p in people if p.get("bare")]
    ids = {p["id"] for p in people}
    # a living person recognisable by name (two or more tokens), who is a node of the blood-relatives chart
    blood = (dist / "bloodline" / "index.html").read_text(encoding="utf-8")
    named = [p for p in living if len((p["name"] or "").split()) >= 2 and re.search(r"[A-Za-z]{3}", p["first"] or "")
             and re.search(r"[A-Za-z]{3}", p["last"] or "")
             and re.search(r'"slug":"%s","name":"[^"]*","dt":""' % p["id"], blood)]
    dead = [p for p in people if not p.get("living") and not p.get("bare") and p.get("kind") == "family"
            and p.get("born") and p.get("rel") and not p.get("placeholder")]
    if not named or not dead or not bare:
        sys.exit("selftest-living: REFUSED: no living person with a recognisable name in the register, or no dead person, or no named-only subject")
    L = named[0]
    LID = str(L["id"])
    D = dead[0]
    B = bare[0]
    held_ids = [int(i) for i in guard.get("held_out_ids", [])]
    HID = held_ids[0] if held_ids else 9599999
    # a relative of D who has a page, to unlink
    rel_of_L = next(e for e in L["rel"] if e["id"] in ids)
    rel_slug = next(p["slug"] for p in people if p["id"] == rel_of_L["id"])
    sb = Sandbox(dist, harvest)
    results = []          # (label, expected, ok, detail)
    year_now = datetime.date.today().year

    def case(label, mode, expect_fail, setup, needle=None):
        base, d = sb.fresh()
        setup(base, d)
        code, out = run_gate(base, d, mode)
        failed = code != 0
        ok = failed == expect_fail and (needle is None or not expect_fail or needle.lower() in out.lower())
        results.append((f"[{mode}] {label}", "fails" if expect_fail else "passes", ok,
                        "" if ok else out.strip().splitlines()[-1][:160] if out.strip() else f"exit {code}"))

    def sub_in(path, old_rx, new, count=1):
        t = path.read_text(encoding="utf-8")
        t2, n = re.subn(old_rx, new, t, count=count)
        if n == 0:
            raise SystemExit(f"selftest-living: could not plant (pattern not found in {path.name}): {old_rx[:60]}")
        path.write_text(t2, encoding="utf-8")

    def reg_edit(fn, who):
        def f(b, d):
            p = b / "site" / "src" / "data" / "register.json"
            data = json.load(open(p))
            for r in data["people"]:
                if r["id"] == who:
                    fn(r, data)
            json.dump(data, open(p, "w"))
        return f

    def link(p):
        return re.escape(f'<a href="/people/{p["slug"]}/">')

    def after_name(p, inject):
        """Append `inject` after the register row's link to person p (a family-table row or an index-table row)."""
        return lambda b, d: sub_in(d / "register" / "index.html",
                                   r"(" + link(p) + r"(?:<strong>)?" + re.escape(p["name"]) + r"(?:</strong>)?</a>)", r"\1" + inject)

    def living_page(b, d):
        return d / "people" / L["slug"] / "index.html"

    def dead_page(b, d):
        return d / "people" / D["slug"] / "index.html"

    def sitemap_add(url):
        def f(b, d):
            sm = d / "sitemap.xml"
            t = sm.read_text(encoding="utf-8") if sm.exists() else \
                '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
            sm.write_text(t.replace("</urlset>", f"<url><loc>https://example.test{url}</loc></url></urlset>"), encoding="utf-8")
        return f

    def idx_edit(fn):
        def f(b, d):
            p = d / "searchindex.json"
            data = json.loads(p.read_text(encoding="utf-8"))
            fn(data)
            p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return f

    for mode in modes:
        # --- baseline
        case("the untouched build", mode, False, lambda b, d: None)

        # --- context: the text that stands with a living name
        case("a birth year planted in a living person's register row", mode, True,
             after_name(L, " (b. 1799)"), "stands with a living person")
        case("a full date planted in a living person's register row", mode, True,
             after_name(L, " 12 March 1799"), "stands with a living person")
        case("the word «died» planted in a living person's register row", mode, True,
             after_name(L, " died"), "stands with a living person")
        case("CONTROL: a year planted beside a DEAD person's name in the register", mode, False,
             after_name(D, " (b. 1799)"))
        case("a year in an attribute that carries a living person's name", mode, True,
             lambda b, d: sub_in(d / "register" / "index.html", r"<table", f'<table title="{L["name"]} born 1799"'), "attribute")
        case("a living person named in a meta description with a date", mode, True,
             lambda b, d: sub_in(d / "index.html", r"<head>", f'<head><meta name="description" content="{L["name"]}, 3 May 1799">'),
             "attribute")
        case("JSON-LD naming a living person, on another page", mode, True,
             lambda b, d: sub_in(d / "index.html", r"</head>",
                                 '<script type="application/ld+json">{"@type":"Person","name":"' + L["name"] + '"}</script></head>'),
             "json-ld")

        # --- the embedded chart data
        case("a date on a living person's node in the blood-relatives chart data", mode, True,
             lambda b, d: sub_in(d / "bloodline" / "index.html",
                                 r'("slug":"' + LID + r'","name":"[^"]*","dt":)""', r'\1"1799 – "'), "chart node")
        case("a field beyond name on a living person's chart node", mode, True,
             lambda b, d: sub_in(d / "bloodline" / "index.html", r'("slug":"' + LID + r'",)', r'\1"occupation":"engineer 2",'),
             "chart node")

        # --- the page of a living person
        case("a living person's page without noindex", mode, True,
             lambda b, d: sub_in(living_page(b, d), r'<meta name="robots" content="noindex">', ""), "lacks noindex")
        case("JSON-LD on a living person's page", mode, True,
             lambda b, d: sub_in(living_page(b, d), r"</head>", '<script type="application/ld+json">{"@type":"Article"}</script></head>'),
             "structured data")
        case("a table on a living person's page", mode, True,
             lambda b, d: sub_in(living_page(b, d), r"</main>", "<table><tr><td>x</td></tr></table></main>"), "a table")
        case("an image on a living person's page", mode, True,
             lambda b, d: sub_in(living_page(b, d), r"</main>", '<img src="/x.jpg" alt="x"></main>'), "an image")
        case("a year in the body of a living person's page", mode, True,
             lambda b, d: sub_in(living_page(b, d), r"</main>", "<p>1799</p></main>"), "a year")
        case("a full date in the body of a living person's page", mode, True,
             lambda b, d: sub_in(living_page(b, d), r"</main>", "<p>3 May 1799</p></main>"), "year")
        case("a year in the head of a living person's page", mode, True,
             lambda b, d: sub_in(living_page(b, d), r"</head>", '<meta name="description" content="1799"></head>'), "a year")
        case("a section beyond «Family» on a living person's page (a record, a source)", mode, True,
             lambda b, d: sub_in(living_page(b, d), r"</main>", "<h2>Where this comes from</h2></main>"), "section beyond")
        case("a living person's page in the sitemap", mode, True, sitemap_add(f"/people/{L['slug']}/"), "sitemap")
        case("a living person's page in the search index", mode, True,
             idx_edit(lambda data: data.append({"k": "Page", "t": "x", "s": "", "h": f"/people/{L['slug']}/", "q": "x"})), "search index")
        case("a search-index entry headed by a living person", mode, True,
             idx_edit(lambda data: data.append({"k": "Page", "t": L["name"], "s": "", "h": "/x/", "q": "x"})), "search-index")
        case("a relative named on a living person's page but not linked", mode, True,
             lambda b, d: sub_in(living_page(b, d), r'href="/people/' + re.escape(rel_slug) + r'/"', 'href="#"'), "not linked")
        case("a living person with no page", mode, True,
             lambda b, d: shutil.rmtree(d / "people" / L["slug"]), "no page")
        case("the named-only subject's page carries a place", mode, True,
             reg_edit(lambda r, data: r.update(place="Leeds", town="Leeds"), B["id"]), "subject")
        case("the named-only subject's record drawn with a child", mode, True,
             reg_edit(lambda r, data: r["rel"].append({"id": L["id"], "n": L["name"], "rel": "His son", "ls": "Living"}), B["id"]),
             "more than his parents")
        case("the named-only subject's page without noindex", mode, True,
             lambda b, d: sub_in(d / "people" / B["slug"] / "index.html", r'<meta name="robots" content="noindex">', ""), "lacks noindex")

        # --- the page of someone who is not living
        case("CONTROL: a year planted in a dead person's page", mode, False,
             lambda b, d: sub_in(dead_page(b, d), r"</main>", "<p>b. 1799</p></main>"))
        case("a non-living person's page that is noindex", mode, True,
             lambda b, d: sub_in(dead_page(b, d), r"<head>", '<head><meta name="robots" content="noindex">'), "noindex")
        case("a non-living person's page missing from the sitemap", mode, True,
             lambda b, d: sub_in(d / "sitemap.xml", r"<url><loc>[^<]*/people/" + re.escape(D["slug"]) + r"/</loc>.*?</url>", ""),
             "missing from the sitemap")
        case("a non-living person's page missing from the search index", mode, True,
             idx_edit(lambda data: data.__setitem__(slice(None), [e for e in data if e.get("h") != f"/people/{D['slug']}/"])),
             "missing from the search index")
        case("a person with no page (a dead person's page deleted)", mode, True,
             lambda b, d: shutil.rmtree(d / "people" / D["slug"]), "no page")
        case("a person left out of the register page's links", mode, True,
             lambda b, d: sub_in(d / "register" / "index.html", r'<a href="/people/' + re.escape(D["slug"]) + r'/">', '<a href="#">'),
             "without a link")
        case("a person left out of the people index's links", mode, True,
             lambda b, d: sub_in(d / "people" / "index.html", r'<a href="/people/' + re.escape(D["slug"]) + r'/">', '<a href="#">'),
             "without a link")
        case("a link to a person page that does not exist", mode, True,
             lambda b, d: sub_in(d / "index.html", r"</main>", '<a href="/people/nobody-at-all/">x</a></main>'), "does not exist")
        case("a chart node naming someone with no person page", mode, True,
             lambda b, d: sub_in(d / "bloodline" / "index.html", r'([{,])"' + LID + r'":\{', r'\1"9599998":{'), "no person page")

        # --- the sitemap and the search index by name
        def sitemap_only(b, d):
            sitemap_add(f"/who/{re.sub(r'[^a-z]+', '-', L['name'].lower()).strip('-')}/")(b, d)
        case("a sitemap address that is a living person's name", mode, True, sitemap_only, "address in the sitemap")
        if mode == "harvest":
            fq = (L["name"] + " 1799 born").lower()
            case("a digit hard against a living name in indexed text", mode, True,
                 idx_edit(lambda data: data.append({"k": "Page", "t": "Register", "s": "", "h": "/register/", "q": fq})), "indexed text")

        # --- the generated register
        case("a birth date on a living record in the register", mode, True,
             reg_edit(lambda r, data: r.update(born="Mar 3 1799"), L["id"]), "born date")
        case("a birth year on a living record in the register", mode, True,
             reg_edit(lambda r, data: r.update(by=1799), L["id"]), "by year")
        case("a fact on a living record in the register", mode, True,
             reg_edit(lambda r, data: r.update(facts=[{"t": "Marriage to:", "date": "1799"}]), L["id"]), "events or facts")
        case("a field beyond the allowed ones on a living record (a profile link)", mode, True,
             reg_edit(lambda r, data: r.update(profile="https://example.test/x"), L["id"]), "beyond the allowed")
        case("a street address as a living record's place", mode, True,
             reg_edit(lambda r, data: r.update(town="12 High Street", place="12 High Street"), L["id"]), "plain town or country")
        case("an institution as a living record's town", mode, True,
             reg_edit(lambda r, data: r.update(town="St Mary's Hospital", place="St Mary's Hospital"), L["id"]), "plain town or country")
        case("a living record whose flag is removed (published as if not living)", mode, True,
             reg_edit(lambda r, data: r.pop("living"), L["id"]), "differ from the people")

        def edge_ls(r, data):
            for q in data["people"]:
                for e in q.get("rel", []):
                    if e["id"] == L["id"]:
                        e["ls"] = "Born: 1799"
                        return
        case("the source's life span on a relationship edge to a living person", mode, True,
             reg_edit(lambda r, data: edge_ls(r, data), D["id"]), "life span")
        case("a life span on an edge inside a living record", mode, True,
             reg_edit(lambda r, data: r["rel"][0].update(ls="1799 - 1850"), L["id"]), "life span")
        case("a record with no slug", mode, True, reg_edit(lambda r, data: r.pop("slug"), D["id"]), "slug")
        case("a relationship edge to somebody who is not published", mode, True,
             reg_edit(lambda r, data: r["rel"].append({"id": 9599997, "n": "Nobody", "rel": "His son"}), D["id"]), "not published")

        # --- the people held out
        case("a held-out id in a built page", mode, True,
             lambda b, d: sub_in(d / "index.html", r"</main>", f"<p>record {HID}</p></main>"), "held-out")
        case("a held-out id in a served data file", mode, True,
             lambda b, d: (d / "extra.json").write_text(json.dumps({"id": HID}), encoding="utf-8"), "held-out")
        case("a held-out person published in the register", mode, True,
             lambda b, d: _publish_held(b, HID, D), "held-out")
        case("a held-out person named as somebody's relative", mode, True,
             reg_edit(lambda r, data: r["rel"].append({"id": HID, "n": "x", "rel": "His son"}), D["id"]), "held-out")

        def minor(b, d):
            # an UNDATED person with a living parent: still held out, so still caught if published
            p = b / "site" / "src" / "data" / "register.json"
            data = json.load(open(p))
            for r in data["people"]:
                if r["id"] == D["id"]:
                    r.update(by=None, dy=None, died="", born="", facts=[], no_death_recorded=None)
                    r["rel"] = [{"id": L["id"], "n": L["name"], "rel": "His mother", "ls": "Living"}]
            json.dump(data, open(p, "w"))
        case("a possible minor published (undated, a living parent, no death recorded)", mode, True, minor, "possible minor")

        def young(b, d):
            p = b / "site" / "src" / "data" / "register.json"
            data = json.load(open(p))
            for r in data["people"]:
                if r["id"] == D["id"]:
                    r.update(by=year_now - 30, dy=None, died="", facts=[], no_death_recorded=None)
            json.dump(data, open(p, "w"))
        case("a person the rule calls living (30, no death) published as not living", mode, True, young, "calls living")

        def old_alive(b, d):
            p = b / "site" / "src" / "data" / "register.json"
            data = json.load(open(p))
            for r in data["people"]:
                if r["id"] == D["id"]:
                    r.update(by=year_now - 95, dy=None, died="", facts=[])
            json.dump(data, open(p, "w"))
        case("CONTROL: a person over eighty with no death recorded is NOT living and passes", mode, False, old_alive)

    # --- a child with a KNOWN birth year is not held out (David, 16 October 2026)
    sys.path.insert(0, str(ROOT / "site" / "node_modules" / "@daviddef" / "archive-kit" / "kit" / "tools"))
    import living_rule as _lr
    ok_rule = (not _lr.is_held_out(1, year_now - 10, False, (), True, ()) and _lr.is_living(year_now - 10, False, ())
               and _lr.is_held_out(1, None, False, (), True, ()) and not _lr.is_held_out(1, None, False, (), False, ()))
    results.append(("[rule] CONTROL: the kit holds out an undated person with a living parent, and not a dated child (who is living)",
                    "passes", ok_rule, "" if ok_rule else "the kit's rule is not the one this gate assumes"))
    if harvest:
        def dated_child(b, d):
            p = b / "data" / "myheritage-tree9.json"
            hv_ = json.load(open(p))
            for q in hv_:
                if q["id"] == L["id"]:
                    q["b"] = f"Jan 1 {year_now - 10}"
            json.dump(hv_, open(p, "w"))
        case("CONTROL: a living person with a known birth year under 18 is published, not held out, and the gate passes",
             "harvest", False, dated_child)

    # --- hashes mode: a held-out NAME, by digest. The held-out person here has a single-token name, which a digest cannot
    # key, so the digest path is proved with a name that cannot belong to anyone.
    planted = "Zzyzx Plantedwho"

    def with_held_digest(b, d):
        g = json.load(open(b / "data" / "guarded-hashes.json"))
        g["held_out_digests"] = [names.digest(g["salt"], planted)]
        json.dump(g, open(b / "data" / "guarded-hashes.json", "w"))
    case("CONTROL: a held-out digest on file, the name absent", "hashes", False, with_held_digest)

    def with_held_digest_and_name(b, d):
        with_held_digest(b, d)
        sub_in(d / "index.html", r"</main>", f"<p>{planted} lived here.</p></main>")
    case("a held-out person's name (by digest) in a built page", "hashes", True, with_held_digest_and_name, "held-out person is named")

    # --- harvest-only rules
    if harvest:
        hv = json.load(open(ROOT / "data" / "myheritage-tree9.json"))
        by_id = {p["id"]: p for p in hv}
        prof = by_id[L["id"]].get("profile")
        if prof and len(prof) >= 10:
            case("the harvest's profile link for a living person present in a built page", "harvest", True,
                 lambda b, d: sub_in(d / "index.html", r"</body>", f'<a href="{prof}">x</a></body>'), "profile link")
        else:
            results.append(("[harvest] profile-link leak (no profile for this person)", "fails", False, "cannot plant"))
        bstr = (by_id[L["id"]].get("b") or "").strip()
        if len(bstr) >= 6:
            case("the harvest's birth date for a living person present in a built page", "harvest", True,
                 lambda b, d: sub_in(d / "index.html", r"</body>", f"<p>{bstr}</p></body>"), "b date")
        dstr = (by_id[B["id"]].get("b") or "").strip()
        if len(dstr) >= 6:
            case("the harvest's birth date for the named-only subject present in a built page", "harvest", True,
                 lambda b, d: sub_in(d / "index.html", r"</body>", f"<p>{dstr}</p></body>"), "b date")
        if held_ids:
            tok = by_id[held_ids[0]]["name"].strip()
            case("a held-out person's name in a built page", "harvest", True,
                 lambda b, d: sub_in(d / "index.html", r"</main>", f"<p>{tok}</p></main>"), "held-out person is named")
        case("a guard file whose living ids differ from the harvest", "harvest", True,
             lambda b, d: _edit_guard(b, lambda g: g.update(living_ids=g["living_ids"][1:])), "guard file")
        case("a guard file whose held-out ids differ from the harvest", "harvest", True,
             lambda b, d: _edit_guard(b, lambda g: g.update(held_out_ids=[])), "guard file")

    # --- refusals: nothing examined is never ok
    for mode in modes:
        def empty_guard(b, d):
            _edit_guard(b, lambda g: g.update(digests=[]))
        if mode == "hashes":
            case("an empty guard list", mode, True, empty_guard, "refused")

        def empty_dist(b, d):
            shutil.rmtree(d)
            d.mkdir()
        case("an empty build directory", mode, True, empty_dist, "refused")

        def blind(b, d):
            for f in list(d.rglob("*.html")) + list(d.rglob("*.json")):
                t = f.read_text(encoding="utf-8", errors="ignore")
                for p in living:
                    for part in {p["name"], p["first"] or "", p["last"] or ""}:
                        if len(part) >= 3:
                            t = re.sub(re.escape(part), "REDACTED", t, flags=re.I)
                f.write_text(t, encoding="utf-8")
        case("a build in which no living person can be recognised", mode, True, blind, "refused")

        def nobody_living(b, d):
            p = b / "site" / "src" / "data" / "register.json"
            data = json.load(open(p))
            for r in data["people"]:
                r.pop("living", None)
            json.dump(data, open(p, "w"))
        case("a register that flags nobody as living", mode, True, nobody_living, "refused")

        def no_pages(b, d):
            shutil.rmtree(d / "people")
        case("a build with no person pages at all", mode, True, no_pages)

    # --- the search index and the sitemap tool, in a copy
    search_cases(sb, results, people, L, D, dist)

    sb.done()
    width = max(len(r[0]) for r in results)
    bad = 0
    for label, expect, ok, detail in results:
        print(f"  {'ok  ' if ok else 'FAIL'}  {label.ljust(width)}  expected to {expect}" + ("" if ok else f"  -> {detail}"))
        bad += not ok
    print(f"selftest-living: {len(results) - bad} of {len(results)} planted faults and controls behaved as required"
          + ("" if harvest else "; harvest-only rules skipped (no private harvest here)"))
    sys.exit(1 if bad else 0)


def _edit_guard(base, fn):
    p = base / "data" / "guarded-hashes.json"
    g = json.load(open(p))
    fn(g)
    json.dump(g, open(p, "w"))


def _publish_held(base, hid, template):
    p = base / "site" / "src" / "data" / "register.json"
    data = json.load(open(p))
    clone = dict(template)
    clone.update(id=hid, slug="held-planted", name="Held Planted", first="Held", last="Planted", rel=[])
    data["people"].append(clone)
    json.dump(data, open(p, "w"))


def search_cases(sb, results, people, L, D, dist):
    """build-search.py leaves a noindex page out; check-search.py refuses one that is in the index; the kit's
    sitemap tool leaves a noindex page out and takes it back when the tag goes."""
    def check(label, ok, detail=""):
        results.append((f"[search] {label}", "passes", ok, detail))

    base, d = sb.fresh()
    site = base / "site"
    shutil.move(str(base / "dist"), str(site / "dist"))
    (base / "tools").mkdir()
    for n in ("check-search.py", "build-search.py"):
        shutil.copy(ROOT / "tools" / n, base / "tools" / n)
    (site / "src" / "pages").mkdir(parents=True)
    shutil.copy(ROOT / "site" / "src" / "pages" / "search.astro", site / "src" / "pages" / "search.astro")
    (site / "public").mkdir()
    shutil.copy(ROOT / "site" / "astro.config.mjs", site / "astro.config.mjs")
    env = {k: v for k, v in os.environ.items() if k != "ARCHIVE_OUT"}
    dd = site / "dist"
    # the build-search tool, run over a copy whose index is first removed
    (dd / "searchindex.json").unlink()
    r = subprocess.run([sys.executable, str(base / "tools" / "build-search.py")], capture_output=True, text=True, env=env)
    rows = json.load(open(dd / "searchindex.json"))
    hs = {e["h"] for e in rows}
    check("build-search leaves every noindex page out of the index", f"/people/{L['slug']}/" not in hs and r.returncode == 0,
          r.stdout.strip()[-120:])
    check("build-search puts every other person's page in the index", f"/people/{D['slug']}/" in hs)
    r = subprocess.run([sys.executable, str(base / "tools" / "check-search.py")], capture_output=True, text=True, env=env)
    check("check-search passes the honest index", r.returncode == 0, (r.stdout + r.stderr).strip()[-160:])
    # plant a noindex page into the index
    rows.append({"k": "Page", "t": "x", "s": "", "h": f"/people/{L['slug']}/", "q": "x"})
    json.dump(rows, open(dd / "searchindex.json", "w"))
    r = subprocess.run([sys.executable, str(base / "tools" / "check-search.py")], capture_output=True, text=True, env=env)
    results.append(("[search] check-search fails a noindex page that is in the index", "fails",
                    r.returncode != 0 and "noindex" in (r.stdout + r.stderr), (r.stdout + r.stderr).strip()[-160:]))
    rows.pop()
    rows = [e for e in rows if e["h"] != f"/people/{D['slug']}/"]
    json.dump(rows, open(dd / "searchindex.json", "w"))
    r = subprocess.run([sys.executable, str(base / "tools" / "check-search.py")], capture_output=True, text=True, env=env)
    results.append(("[search] check-search fails an indexable person page that is absent from the index", "fails",
                    r.returncode != 0 and "STALE" in (r.stdout + r.stderr), (r.stdout + r.stderr).strip()[-160:]))
    # the kit's sitemap tool
    if KIT_SITEMAP.exists():
        for f in dd.glob("sitemap.xml"):
            f.unlink()
        env2 = dict(env, ARCHIVE_OUT="dist")
        r = subprocess.run([sys.executable, str(KIT_SITEMAP)], capture_output=True, text=True, env=env2, cwd=str(site))
        sm = (dd / "sitemap.xml").read_text(encoding="utf-8") if (dd / "sitemap.xml").exists() else ""
        if not sm:
            check("the kit's sitemap tool wrote a sitemap", False, (r.stdout + r.stderr).strip()[-160:])
        check("the kit's sitemap tool leaves a noindex person page out and writes the others",
              f"/people/{L['slug']}/" not in sm and f"/people/{D['slug']}/" in sm)
        pg = dd / "people" / L["slug"] / "index.html"
        pg.write_text(pg.read_text(encoding="utf-8").replace('<meta name="robots" content="noindex">', ""), encoding="utf-8")
        if (dd / "sitemap.xml").exists():
            (dd / "sitemap.xml").unlink()
        subprocess.run([sys.executable, str(KIT_SITEMAP)], capture_output=True, text=True, env=env2, cwd=str(site))
        sm = (dd / "sitemap.xml").read_text(encoding="utf-8") if (dd / "sitemap.xml").exists() else ""
        check("CONTROL: take the noindex tag off a living page and the sitemap tool lists it (so the gate has something to catch)",
              f"/people/{L['slug']}/" in sm)


if __name__ == "__main__":
    main()
