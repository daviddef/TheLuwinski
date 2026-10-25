#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail the build if the lines page (/lines/) says something its own data does not, or links where nothing is.

    python3 ../tools/check-lines.py [--dist dist]      # from site/ (what `npm run check:lines` and the build run)
    python3 ../tools/check-lines.py --selftest         # plant a fault for every rule and demand it is caught

Added 18 October 2026, after the lines audit found that nothing at all read site/src/data/lines.json: the
marriage date the archive had corrected three weeks earlier was still on the page in two places, the
dek was printed twice, the figure's accessible title said "Six families" over lanes numbering eight and seven,
a pen entry sent the reader to "L3" (lanes are not numbered on the page), and two lanes had their dots out of
date order, so the drawn timeline read backwards. Each of those is a rule below. The withdrawn VALUES are
check-superseded.py's business (data/superseded.json); this gate checks the SHAPE of the lanes.

  links     every lane, end and pen link reaches a built page; a link with a #fragment reaches an id that is on
            that page; a link with no fragment ends in a slash (a slash-less link is a 301 first). A label such
            as "Row 206" that promises a place has to land on it, so a fragment is never allowed to dangle.
  order     the dots along a lane are in date order: no dot begins after the next one ends (a range such as
            1874-1884 may overlap its neighbours; 1938, 1941, 1913 may not).
  text      no unbalanced *** (it prints), no lane numbered "L3" or "U2" (the page does not number its lanes),
            no lane key used twice.
  page      each set's dek appears once on the built page, not twice; the figure's accessible title carries no
            count that is not the number of lanes of every figure on the page, and each figure's aria-labelledby
            points at its own <title> (the kit gives every figure a unique id; a title shared by both figures
            must still be true of both, so it carries no count and no surname);
            no literal \\uXXXX escape and no raw *** is visible in the text of any built page.

EXIT CODES. 0 passed. 1 failed. 2 could not run (no build to read): "I could not look" is not a pass.
--selftest exits 1 unless every planted fault was caught and the unmodified data passed.
"""
import os, re, sys, json, html, copy, pathlib, argparse

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
NUMWORDS = "one two three four five six seven eight nine ten eleven twelve".split()


def resolve_dist(root, dist):
    out = os.environ.get("ARCHIVE_OUT")
    d = (dist or "dist").rstrip("/\\")
    base = pathlib.Path(root) / "site"
    if out:
        return base / out
    p = pathlib.Path(d)
    return p if p.is_absolute() else base / p


def nod(n):
    """(place, year, why) of a node, whether it is the old [place, year, why] or the kit's {place, year, why, person}."""
    if isinstance(n, dict):
        return n.get("place", ""), n.get("year", ""), n.get("why", "")
    return n[0], n[1], n[2]


def pens_of(s):
    """The set's pens as [(id, [items])]: `pens` when present (the kit's contract), else the two older lists."""
    if isinstance(s.get("pens"), list):
        return [(p.get("id", "?"), p.get("items", [])) for p in s["pens"]]
    return [(k, s.get(k, [])) for k in ("unplaced", "loose")]


def years_of(s):
    return [int(y) for y in re.findall(r"\b(1[5-9]\d\d|20\d\d)\b", str(s))]


def hrefs(data):
    """(where, href) for every link in lines.json."""
    for s in data["sets"]:
        for l in s["lanes"]:
            yield "%s/%s read link" % (s["name"], l["key"]), l["href"]
            for e in l["ends"]:
                yield "%s/%s end %s" % (s["name"], l["key"], e[0]), e[1]
        for k, items in pens_of(s):
            for x in items:
                yield "%s %s %s" % (s["name"], k, x[0]), x[1]


def strings(data):
    for s in data["sets"]:
        yield s["name"] + " dek", s["dek"]
        for l in s["lanes"]:
            for k in ("label", "statusNote", "read"):
                yield "%s/%s %s" % (s["name"], l["key"], k), l.get(k, "")
            for n in l["nodes"]:
                yield "%s/%s node %s" % (s["name"], l["key"], nod(n)[1]), " ".join(nod(n))
            for e in l["ends"]:
                yield "%s/%s end %s" % (s["name"], l["key"], e[0]), " ".join([e[0], e[2]])
        for p in s.get("pens", []):
            yield "%s pen %s note" % (s["name"], p.get("id", "?")), p.get("note", "")
        for k, items in pens_of(s):
            for x in items:
                yield "%s %s %s" % (s["name"], k, x[0]), " ".join([x[0], x[2]])


def visible(page):
    page = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", page)
    return html.unescape(re.sub(r"(?s)<[^>]+>", " ", page))


def check_data(data, page_of):
    """page_of(path) -> built html of that page, or None. Returns a list of problems."""
    probs = []
    for where, h in hrefs(data):
        if not h.startswith("/"):
            probs.append("links: %s: %r is not a site path" % (where, h)); continue
        path, _, frag = h.partition("#")
        if not path.endswith("/"):
            probs.append("links: %s: %r has no trailing slash (a 301 first)" % (where, h))
        page = page_of(path if path.endswith("/") else path + "/")
        if page is None:
            probs.append("links: %s: %r reaches no built page" % (where, h)); continue
        if frag and not re.search(r"""\sid=["']%s["']""" % re.escape(frag), page):
            probs.append("links: %s: %r - there is no id=%r on that page" % (where, h, frag))
    for s in data["sets"]:
        keys = [l["key"] for l in s["lanes"]]
        if len(keys) != len(set(keys)):
            probs.append("text: %s: a lane key is used twice" % s["name"])
        for l in s["lanes"]:
            ns = l["nodes"]
            for a, b in zip(ns, ns[1:]):
                (pa, ya_), (pb, yb_) = nod(a)[:2], nod(b)[:2]
                ya, yb = years_of(ya_), years_of(yb_)
                if ya and yb and min(ya) > max(yb):
                    probs.append("order: %s/%s: %r (%s) comes before %r (%s), which is earlier"
                                 % (s["name"], l["key"], pa, ya_, pb, yb_))
    for where, t in strings(data):
        if t.count("***") % 2:
            probs.append("text: %s: an unbalanced *** (it prints as asterisks)" % where)
        if re.search(r"\b[LU]\d\b", t):
            probs.append("text: %s: a numbered lane reference (the page does not number its lanes)" % where)
    return probs


def _rt_ids(page):
    return re.findall(r"""<title id="(rt-[^"]+)">""", page)


def _share_id(page):
    """Planted fault: the second figure's title and aria-labelledby take the first figure's id."""
    ids = _rt_ids(page)
    return page.replace(ids[1], ids[0]) if len(ids) > 1 else page


def _point_away(page):
    """Planted fault: the second figure's aria-labelledby names the first figure's title."""
    ids = _rt_ids(page)
    return page.replace('aria-labelledby="%s"' % ids[1], 'aria-labelledby="%s"' % ids[0]) if len(ids) > 1 else page


def check_built(data, dist):
    probs = []
    lp = dist / "lines" / "index.html"
    if not lp.exists():
        return ["not run: %s is missing" % lp]
    page = lp.read_text(encoding="utf-8")
    text = re.sub(r"\s+", " ", visible(page)).replace("*", "")
    for s in data["sets"]:
        head = re.sub(r"\s+", " ", re.sub(r"\*+", "", s["dek"])).strip()[:70]
        n = text.count(head)
        if n != 1:
            probs.append("page: the %s dek appears %d times on /lines/ (it should be once)" % (s["name"], n))
    titled = re.findall(r"""<title id="(rt-[^"]+)">(.*?)</title>""", page, re.S)
    titles = [t for _, t in titled]
    if len(titles) != len(data["sets"]):
        probs.append("page: %d figure title(s) for %d set(s)" % (len(titles), len(data["sets"])))
    ids = [i for i, _ in titled]
    if len(set(ids)) != len(ids):
        probs.append("page: two figures share a title id (%s), so one of them reads the other's title" % ", ".join(ids))
    # each figure's own svg must point at its own title, not at the first one in the document
    for m in re.finditer(r"""<svg\b[^>]*aria-labelledby="(rt-[^"]+)"[^>]*>\s*<title id="([^"]+)">""", page):
        if m.group(1) != m.group(2):
            probs.append("page: a figure's aria-labelledby %s points away from its own title %s" % (m.group(1), m.group(2)))
    if len(re.findall(r"""aria-labelledby="rt-""", page)) != len(titles):
        probs.append("page: the figures' aria-labelledby and their titles do not pair up")
    counts = {len(s["lanes"]) for s in data["sets"]}
    for t in titles:
        t = html.unescape(t)
        said = {int(x) for x in re.findall(r"\b\d+\b", t)}
        # a number word counts only where it counts something ("six families"); "one surname" is not a count
        said |= {NUMWORDS.index(w) + 1 for w in re.findall(r"\b(%s)\s+(?:lanes?|famil(?:y|ies)|households?|rivers?|strands?|roads?)\b"
                                                           % "|".join(NUMWORDS), t.lower())}
        for n in said:
            if counts != {n}:
                probs.append("page: the figure title %r says %d, and the figures draw %s lanes" % (t, n, sorted(counts)))
        for s in data["sets"]:
            if s["name"].lower() in t.lower() and len(data["sets"]) > 1:
                probs.append("page: the figure title %r names %s, but the same title is read over every figure" % (t, s["name"]))
    for p in sorted(dist.rglob("index.html")):
        v = visible(p.read_text(encoding="utf-8"))
        m = re.search(r"\\u[0-9a-fA-F]{4}", v)
        if m:
            probs.append("page: %s shows a literal %s in its text" % (p.relative_to(dist), m.group(0)))
        if "***" in v and p.parent.name == "lines":
            probs.append("page: /lines/ shows a raw ***")
    return probs


def run(root, dist):
    data = json.load(open(pathlib.Path(root) / "site/src/data/lines.json", encoding="utf-8"))
    if not dist.is_dir():
        return ["no build at %s" % dist], 2
    cache = {}

    def page_of(path):
        if path not in cache:
            f = dist / path.strip("/") / "index.html" if path.strip("/") else dist / "index.html"
            cache[path] = f.read_text(encoding="utf-8") if f.exists() else None
        return cache[path]

    probs = check_data(data, page_of) + check_built(data, dist)
    return probs, (2 if any(p.startswith("not run") for p in probs) else (1 if probs else 0))


def selftest(root, dist):
    data = json.load(open(pathlib.Path(root) / "site/src/data/lines.json", encoding="utf-8"))
    cache = {}

    def page_of(path):
        if path not in cache:
            f = dist / path.strip("/") / "index.html" if path.strip("/") else dist / "index.html"
            cache[path] = f.read_text(encoding="utf-8") if f.exists() else None
        return cache[path]

    base = check_data(data, page_of)
    if base:
        print("selftest: the UNMODIFIED data fails (%d problem(s)); the self-test cannot be trusted:" % len(base))
        for p in base[:8]:
            print("  - " + p)
        return 1

    def lz():
        return copy.deepcopy(data)

    faults = []

    def plant(label, fn, expect):
        d = lz(); fn(d); faults.append((label, d, expect))

    def swap_nodes(d):
        n = d["sets"][0]["lanes"][1]["nodes"]; n[0], n[3] = n[3], n[0]
    plant("two dots out of date order", swap_nodes, "order:")
    plant("a dangling #fragment", lambda d: d["sets"][0]["lanes"][0].__setitem__("href", "/leibholz/#no-such-anchor"), "no id=")
    plant("a link with no trailing slash", lambda d: d["sets"][0]["lanes"][0].__setitem__("href", "/leibholz"), "trailing slash")
    plant("a link to no page", lambda d: d["sets"][0]["lanes"][0].__setitem__("href", "/nowhere/"), "reaches no built page")
    plant("an unbalanced ***", lambda d: d["sets"][0].__setitem__("dek", "*** UPDATED: " + d["sets"][0]["dek"]), "unbalanced")
    plant("a numbered lane reference (L3)", lambda d: d["sets"][0]["pens"][1]["items"][0].__setitem__(2, "married into L3 or near it"), "numbered lane")
    plant("a link in a pen to no page", lambda d: d["sets"][0]["pens"][0]["items"][0].__setitem__(1, "/nowhere/"), "reaches no built page")
    plant("a lane key used twice", lambda d: d["sets"][1]["lanes"][1].__setitem__("key", d["sets"][1]["lanes"][0]["key"]), "used twice")
    missed = []
    for label, d, expect in faults:
        probs = check_data(d, page_of)
        if any(expect in p for p in probs):
            print("selftest: caught   %s" % label)
        else:
            print("selftest: MISSED   %s" % label); missed.append(label)
    # the built-page rules, planted in a copy of the lines page
    lp = (dist / "lines" / "index.html")
    if lp.exists():
        import tempfile, shutil
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            (tmp / "lines").mkdir()
            good = lp.read_text(encoding="utf-8")
            dek = html.escape(re.sub(r"\*+", "", data["sets"][1]["dek"])[:70], quote=False)
            planted = {
                "the dek printed twice": good.replace("</main>", "<p>" + dek + "</p></main>", 1),
                "a figure title that says Six": re.sub(r"(<title id=\"rt-[^\"]+\">).*?(</title>)", r"\1Six families of one surname\2", good),
                "both figures sharing one title id": _share_id(good),
                "the second figure pointing at the first's title": _point_away(good),
                "a raw *** on the page": good.replace("</main>", "<p>*** UPDATED</p></main>", 1),
            }
            for label, page in planted.items():
                (tmp / "lines" / "index.html").write_text(page, encoding="utf-8")
                probs = check_built(data, tmp)
                if probs:
                    print("selftest: caught   %s" % label)
                else:
                    print("selftest: MISSED   %s" % label); missed.append(label)
            (tmp / "lines" / "index.html").write_text(good, encoding="utf-8")
            if check_built(data, tmp):
                print("selftest: the UNMODIFIED lines page fails; the self-test cannot be trusted:")
                for p in check_built(data, tmp)[:8]:
                    print("  - " + p)
                return 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if missed:
        print("selftest: FAIL, %d planted fault(s) not caught" % len(missed))
        return 1
    print("selftest: ok, the unmodified data passes and all %d planted faults are caught" % (len(faults) + 5))
    return 0


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
    if code == 2:
        print("check-lines: NOT RUN: " + "; ".join(probs)); return 2
    if probs:
        print("check-lines: FAIL (%d)" % len(probs))
        for p in probs:
            print("  - " + p)
        return 1
    data = json.load(open(pathlib.Path(a.root) / "site/src/data/lines.json", encoding="utf-8"))
    n = sum(len(s["lanes"]) for s in data["sets"])
    print("check-lines: ok - %d lanes in %d sets, every link reaches a built page and every #fragment an id on it, dots in date order, "
          "each dek printed once, the figure title carries no wrong count, no raw *** or \\u escape on any page" % (n, len(data["sets"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
