#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail the build if a family page says something the archive's data does not, or leaves out something it must.

    python3 ../tools/check-families.py [--dist dist]      # from site/ (what `npm run check:families` and the build run)
    python3 ../tools/check-families.py --selftest        # plant a fault for every rule and demand it is caught

The family pages (/families/, /families/<surname>/, added 17 October 2026) are DRAWN from data the archive
already holds (src/lib/families.js); src/data/families.json only DECLARES which people, tree entries and pages
belong to which name. This gate reads the declarations AND the built pages and checks what a template cannot:

  verbatim   every quoted fragment (families.json `say`) is, whole and unchanged, in the tree entry it is
             attributed to; every `notes` sentence is, whole and unchanged, in the file it is attributed to.
             A quotation that has drifted from its source is a paraphrase wearing quotation marks.
  declared   every `tree_links` target exists, and is the person the tree entry names: its name must share the
             entry's given name and surname, and a register person with a birth year must have that year in the
             entry's dates (two Joachim Luwinski, one born 1865 and one born 1940, share a name and nothing
             else). `say` and `tree_links` keys must each be a real tree entry.
  pages      every family has a built page, a canonical, the nav entry, an entry on the index, a place in the
             sitemap and in the search index; every page it lists as telling the family's story exists and
             actually mentions the family; every internal link on a family page reaches a built page.
  counts     the number of people who have died that a family page states is recomputed here from the register
             and the English line with code of its own, and must agree.
  living     no living person's name appears on a family page, and no family page links to a living person's page
             (standard v2: a family page counts the living and names none of them).

EXIT CODES. 0 passed. 1 failed. 2 could not run (no build to read, no families): "I could not look" is not a
pass. --selftest exits 1 unless every planted fault was caught and the unmodified copy passed.
"""
import os, re, sys, json, html, shutil, tempfile, pathlib, argparse, unicodedata

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent


def fold(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def norm_text(s):
    """Comparison form for a quotation: tags and entities gone, curly quotes straight, whitespace and case folded,
    asterisk emphasis dropped. Nothing else is forgiven: a changed word is a changed quotation."""
    s = html.unescape(re.sub(r"<[^>]+>", "", str(s)))
    s = (s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
          .replace("–", "-").replace("—", "-").replace("*", ""))
    return re.sub(r"\s+", " ", s).strip().lower()


def flatten(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from flatten(v)
    elif isinstance(o, list):
        for v in o:
            yield from flatten(v)


def page_text(path):
    t = pathlib.Path(path).read_text(encoding="utf-8")
    m = re.search(r"<main.*?</main>", t, re.S)
    t = m.group(0) if m else t
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def years(s):
    return [int(y) for y in re.findall(r"\b(1[5-9]\d\d|20[0-4]\d)\b", str(s or ""))]


def resolve_dist(root, dist):
    out = os.environ.get("ARCHIVE_OUT")
    d = (dist or "dist").rstrip("/\\")
    base = pathlib.Path(root) / "site"
    if out:
        return base / out
    p = pathlib.Path(d)
    return p if p.is_absolute() else base / p


def surname_of(p):
    if p.get("last"):
        return p["last"]
    bare = re.sub(r"\([^)]*\)", " ", p.get("name", "")).split()
    return bare[-1] if bare else ""


# ----------------------------------------------------------------------------------------------- the checks
def run(root, dist):
    root = pathlib.Path(root)
    data = root / "site" / "src" / "data"
    probs = []
    P = probs.append

    def load(n):
        return json.load(open(data / n, encoding="utf-8"))

    cfg, tree, reg, eng, names = load("families.json"), load("tree.json"), load("register.json"), load("english-people.json"), load("names.json")
    fams = cfg.get("families", [])
    if not fams:
        return ["no families declared in families.json: nothing was examined"], 2
    people = reg["people"]
    by_id = {str(p["id"]): p for p in people}
    by_slug = {p["slug"]: p for p in eng["people"]}
    entries = {e["name"]: e for g in tree["generations"] for e in g["people"]}
    slugs = [f["slug"] for f in fams]
    if len(set(slugs)) != len(slugs):
        P("families.json: a slug is used twice")

    # ---- verbatim
    for name, frags in cfg.get("say", {}).items():
        e = entries.get(name)
        if not e:
            P("families.json say: %r is not a tree entry" % name); continue
        hay = norm_text(e.get("how", ""))
        for fr in frags:
            if norm_text(fr) not in hay:
                P("families.json say: not verbatim in the tree entry %r: %r" % (name, fr[:70]))
    for name in cfg.get("tree_links", {}):
        if name not in entries:
            P("families.json tree_links: %r is not a tree entry" % name)
    cache = {}
    for f in fams:
        for n in f.get("notes", []):
            fp = root / "site" / n["file"]
            if not fp.exists():
                P("%s: note file %s does not exist" % (f["slug"], n["file"])); continue
            if fp not in cache:
                raw = fp.read_text(encoding="utf-8")
                if fp.suffix == ".json":
                    raw = " ".join(flatten(json.loads(raw)))
                cache[fp] = norm_text(raw)
            if norm_text(n["text"]) not in cache[fp]:
                P("%s: a note is not verbatim in %s: %r" % (f["slug"], n["file"], n["text"][:70]))

    # ---- declared
    for ename, specs in cfg.get("tree_links", {}).items():
        e = entries.get(ename)
        if not e:
            continue
        efold = " " + fold(ename) + " "
        eyears = set(years(e.get("dates", "")))
        for spec in specs:
            kind, _, val = spec.partition(":")
            if kind == "href":
                continue
            if kind == "id":
                p = by_id.get(val)
            elif kind == "slug":
                p = by_slug.get(val)
            else:
                P("tree_links %r: unknown link kind %r" % (ename, spec)); continue
            if not p:
                P("tree_links %r: %s does not exist" % (ename, spec)); continue
            toks = fold(re.sub(r"\([^)]*\)", " ", p["name"])).split()
            if not toks or (" " + toks[0] + " ") not in efold:
                P("tree_links %r: %s is %r, whose given name is not in the entry" % (ename, spec, p["name"])); continue
            surn = fold(surname_of(p)).split()
            others = fold(re.sub(r"\([^)]*\)", " ", p["name"])).split()
            if not any((" " + t + " ") in efold for t in set(surn + others[-1:])):
                P("tree_links %r: %s is %r, whose surname is not in the entry" % (ename, spec, p["name"]))
            if kind == "id" and eyears:
                mine = [int(y) for y in (p.get("by"), p.get("dy")) if y]
                for y in mine:
                    if y not in eyears:
                        P("tree_links %r: %s is %r, whose recorded year %s is not among the entry's years %s" % (ename, spec, p["name"], y, sorted(eyears)))
                if not mine and len(specs) == 1:
                    P("tree_links %r: %s is %r, who has no recorded year, so a namesake cannot be told from the person the entry dates" % (ename, spec, p["name"]))
    for f in fams:
        toks = [fold(t) for t in f.get("tree", [])]
        used = [n for n in entries if any((" " + t + " ") in (" " + fold(n) + " ") for t in toks) and entries[n].get("dates") != "Living"]
        if not used:
            P("%s: no tree entry carries the name, but the page promises one" % f["slug"])

    # ---- built pages
    if not dist.exists():
        return ["no build at %s: nothing was examined" % dist], 2
    base_ok = {}

    def built(href):
        h = href.split("#")[0].split("?")[0]
        if not h.startswith("/"):
            return True
        key = h
        if key in base_ok:
            return base_ok[key]
        rel = h.strip("/")
        cands = [dist / rel / "index.html", dist / rel] if rel else [dist / "index.html"]
        ok = any(c.exists() and c.is_file() for c in cands)
        base_ok[key] = ok
        return ok

    sitemap = (dist / "sitemap.xml").read_text(encoding="utf-8") if (dist / "sitemap.xml").exists() else ""
    searchtxt = (dist / "searchindex.json").read_text(encoding="utf-8") if (dist / "searchindex.json").exists() else ""
    if not sitemap:
        P("no sitemap.xml in the build (the sitemap step has not run)")
    if not searchtxt:
        P("no searchindex.json in the build")

    # who is living, from the register's own flags (the generator took them from the kit's living rule)
    living = [p for p in people if p.get("living") is True or p.get("bare") is True]
    living_names = set()
    for p in living:
        nm = re.sub(r"\s+", " ", p["name"]).strip()
        living_names.add(fold(nm))
        living_names.add(fold(re.sub(r"\([^)]*\)", " ", nm)))
        if p.get("first") and p.get("last"):
            living_names.add(fold(p["first"] + " " + p["last"]))
    living_names = {n for n in living_names if len(n.split()) >= 2}
    living_slugs = {p["slug"] for p in living}
    if not living_names:
        P("the register holds no living person to test against: the living check examined nothing")

    idx = dist / "families" / "index.html"
    if not idx.exists():
        P("/families/ is not built")
        idx_html = ""
    else:
        idx_html = idx.read_text(encoding="utf-8")

    for f in fams:
        slug = f["slug"]
        pg = dist / "families" / slug / "index.html"
        if not pg.exists():
            P("/families/%s/ is not built" % slug); continue
        raw = pg.read_text(encoding="utf-8")
        txt = page_text(pg)
        ftxt = fold(txt)
        if '<link rel="canonical" href="https://luwinski.defranceski.com/families/%s/"' % slug not in raw:
            P("/families/%s/: canonical is not its own address" % slug)
        if "noindex" in raw:
            P("/families/%s/: is noindex" % slug)
        if 'href="/families/%s/"' % slug not in raw.split("</nav>")[0]:
            P("/families/%s/: the nav does not link to the page" % slug)
        if 'href="/families/%s/"' % slug not in idx_html:
            P("/families/ does not link to /families/%s/" % slug)
        if "/families/%s/" % slug not in sitemap:
            P("/families/%s/ is not in the sitemap" % slug)
        if '"/families/%s/"' % slug not in searchtxt:
            P("/families/%s/ is not in the search index" % slug)

        # counts, recomputed
        regk = {fold(x) for x in f.get("register", [])}
        ids = {str(x) for x in f.get("register_ids", [])}
        engk = {fold(x) for x in f.get("english", [])}
        dead = [p for p in people if not p.get("placeholder") and (str(p["id"]) in ids or fold(surname_of(p)) in regk)
                and not (p.get("living") is True or p.get("bare") is True)]
        nd = len(dead) + len([p for p in eng["people"] if fold(p["name"].split()[-1]) in engk])
        m = re.search(r"<strong[^>]*>\s*(\d+) (?:person who has|people who have) died\s*</strong>", raw)
        if not m:
            P("/families/%s/: the count of people who have died is not on the page" % slug)
        elif int(m.group(1)) != nd:
            P("/families/%s/: the page says %s people who have died, the data says %d" % (slug, m.group(1), nd))

        # living
        for nm in living_names:
            if (" " + nm + " ") in (" " + ftxt + " "):
                P("/families/%s/: names a living person" % slug); break
        for s in living_slugs:
            if "/people/%s/" % s in raw:
                P("/families/%s/: links to a living person's page (%s)" % (slug, s)); break

        # links
        for href in set(re.findall(r'href="(/[^"#]*)', raw)):
            if not built(href):
                P("/families/%s/: link to %s reaches no built page" % (slug, href))

        # pages that tell the story
        forms = {fold(f["name"])}
        forms |= {fold(x) for x in f.get("forms", [])}
        for lbl, href in f.get("pages", []):
            if not built(href):
                P("%s: listed page %s is not built" % (slug, href)); continue
            fp = dist / href.strip("/") / "index.html"
            body = fold(page_text(fp)) if fp.exists() else ""
            if not any((" " + x + " ") in (" " + body + " ") for x in forms | {fold(f["name"]) + "s"}):
                P("%s: the listed page %s never mentions the family" % (slug, href))

    # the index counts what the pages say
    for f in fams:
        if idx_html and ("The %s family" % f["name"]) not in html.unescape(idx_html):
            P("/families/: no card for %s" % f["name"])
    return probs, (1 if probs else 0)


def report(label, probs, code):
    if code == 2:
        print("check-families: NOT RUN: " + "; ".join(probs)); return 2
    if probs:
        print("check-families: FAIL (%d)" % len(probs))
        for p in probs:
            print("  - " + p)
        return 1
    print(label)
    return 0


# ----------------------------------------------------------------------------------------------- the self-test
def selftest(real_root, real_dist):
    """Plant one fault per rule in a COPY and demand the gate catches it; the unmodified copy must pass."""
    real_root, real_dist = pathlib.Path(real_root), pathlib.Path(real_dist)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="selftest-families-"))
    try:
        def fresh(tag):
            r = tmp / tag
            (r / "site" / "src" / "data").mkdir(parents=True)
            for n in ["families.json", "tree.json", "register.json", "english-people.json", "names.json"]:
                shutil.copy(real_root / "site" / "src" / "data" / n, r / "site" / "src" / "data" / n)
            (r / "site" / "src" / "pages").mkdir(parents=True)
            shutil.copy(real_root / "site" / "src" / "pages" / "register.astro", r / "site" / "src" / "pages" / "register.astro")
            shutil.copy(real_root / "site" / "src" / "data" / "lines.json", r / "site" / "src" / "data" / "lines.json")
            d = r / "site" / "dist"
            shutil.copytree(real_dist, d, ignore=shutil.ignore_patterns("*.png", "*.jpg", "*.jpeg", "*.woff*"))
            return r, d

        def jedit(r, name, fn):
            p = r / "site" / "src" / "data" / name
            o = json.load(open(p, encoding="utf-8")); fn(o)
            json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False)

        def hedit(d, rel, fn):
            p = d / rel
            p.write_text(fn(p.read_text(encoding="utf-8")), encoding="utf-8")

        reg_living = [p for p in json.load(open(real_root / "site/src/data/register.json"))["people"] if p.get("living") is True][0]

        faults = []

        def f_say(r, d):
            def fn(o): o["say"]["Kurt Israel Luwinski"][0] = "NOT HIS BIOLOGICAL FATHER, PERHAPS"
            jedit(r, "families.json", fn)
        faults.append(("a quotation that is not verbatim in the tree entry", f_say))

        def f_note(r, d):
            def fn(o): o["families"][0]["notes"][0]["text"] += " It is, however, entirely certain."
            jedit(r, "families.json", fn)
        faults.append(("a note that is not verbatim in its source file", f_note))

        def f_link(r, d):
            def fn(o): o["tree_links"]["Kurt Israel Luwinski"] = ["id:9500040"]
            jedit(r, "families.json", fn)
        faults.append(("a tree entry declared to be about the wrong Kurt", f_link))

        def f_year(r, d):
            def fn(o): o["tree_links"]["Joachim Luwinski × Johanna Thimm"] = ["id:9500141", "id:9500029"]
            jedit(r, "families.json", fn)
        faults.append(("a tree entry declared to be about the wrong Joachim (same name, born 1940)", f_year))

        def f_living(r, d):
            nm = reg_living["name"]
            hedit(d, "families/luwinski/index.html", lambda t: t.replace("<main", "<main data-x><p>%s</p>" % nm, 1) if "<main" in t else t)
        faults.append(("a living person's name on a family page", f_living))

        def f_livelink(r, d):
            hedit(d, "families/luwinski/index.html", lambda t: t.replace("</main>", '<a href="/people/%s/">x</a></main>' % reg_living["slug"], 1))
        faults.append(("a link from a family page to a living person's page", f_livelink))

        def f_sitemap(r, d):
            hedit(d, "sitemap.xml", lambda t: t.replace("/families/wear/", "/families/wear-gone/"))
        faults.append(("a family page missing from the sitemap", f_sitemap))

        def f_search(r, d):
            hedit(d, "searchindex.json", lambda t: t.replace('"/families/castle/"', '"/families/castle-gone/"'))
        faults.append(("a family page missing from the search index", f_search))

        def f_count(r, d):
            hedit(d, "families/leibholz/index.html", lambda t: re.sub(r"(<strong[^>]*>\s*)(\d+)( people who have died\s*</strong>)", lambda m: "%s%d%s" % (m.group(1), int(m.group(2)) + 1, m.group(3)), t, count=1))
        faults.append(("a count on a page that disagrees with the data", f_count))

        def f_pages(r, d):
            def fn(o): o["families"][2]["pages"].append(["Search", "/search/"])
            jedit(r, "families.json", fn)
        faults.append(("a listed page that never mentions the family", f_pages))

        def f_missing(r, d):
            shutil.rmtree(d / "families" / "bloom")
        faults.append(("a family page that is not built", f_missing))

        def f_nav(r, d):
            def fn(t):
                head, sep, rest = t.partition("</nav>")
                return head.replace('href="/families/larkin/"', 'href="/families/larkin-x/"') + sep + rest
            hedit(d, "families/larkin/index.html", fn)
        faults.append(("a family page the nav does not link to", f_nav))

        def f_dead(r, d):
            hedit(d, "families/wallis/index.html", lambda t: t.replace("</main>", '<a href="/nowhere-at-all/">x</a></main>', 1))
        faults.append(("a link on a family page that reaches no built page", f_dead))

        # the control: an unmodified copy must PASS, or a pass proves nothing about the faults
        r, d = fresh("control")
        probs, code = run(r, d)
        if code != 0:
            print("selftest: the UNMODIFIED copy fails (%d problem(s)); the self-test cannot be trusted:" % len(probs))
            for p in probs[:8]:
                print("  - " + p)
            return 1
        missed = []
        for i, (label, plant) in enumerate(faults):
            r, d = fresh("f%d" % i)
            plant(r, d)
            probs, code = run(r, d)
            if code == 1 and probs:
                print("selftest: caught   %s" % label)
            else:
                print("selftest: MISSED   %s" % label)
                missed.append(label)
        if missed:
            print("selftest: FAIL, %d planted fault(s) not caught" % len(missed))
            return 1
        print("selftest: ok, the unmodified copy passes and all %d planted faults are caught" % len(faults))
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dist", default="dist")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    dist = resolve_dist(a.root, a.dist)
    if a.selftest:
        return selftest(a.root, dist)
    probs, code = run(a.root, dist)
    n = len(json.load(open(pathlib.Path(a.root) / "site/src/data/families.json", encoding="utf-8"))["families"]) if code != 2 else 0
    return report("check-families: ok - %d family pages and the index, quotations verbatim, declarations match the tree, counts recomputed, "
                  "no living person named or linked, every link and every listed page reaches a built page" % n, probs, code)


if __name__ == "__main__":
    sys.exit(main())
