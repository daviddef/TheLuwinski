#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One page per person: does every person's page list exactly the other people of their name?

    python3 ../tools/check-namesakes.py --dist dist             # from site/; `npm run check:namesakes`
    python3 ../tools/check-namesakes.py --dist dist --selftest  # plants one fault per rule

WHAT THIS IS (23 November 2026). David's rule is one page per person, and each person's page links to the other people who carry
the same name. This archive never had name pages (/who/), so only that half applies: a person page whose name another page also
carries has a section "Others of the same name" (#others-of-this-name) listing each of those other people, one link to THEIR page.
The gate checks the BUILD and nothing the page generator used (src/lib/namesakes.js is not read):

  sets      derived here from the h1 of every built person page (/people/<slug>/, the pages that carry data-person-page): the name
            is the h1, accents and case folded, every run of other characters one space. Left out, as the generator leaves them
            out: a placeholder page (the tag "Placeholder": it stands for someone the source tree could not name, so there is no
            name to share) and a living person's page (noindex). The others of a page are the rest of its set.
  missing   a page's list lacks a person of its name.
  extra     it lists a page that does not carry the name, itself, a placeholder or a living person.
  absent    a name is shared and the page has no section, or the page has a section and nobody shares its name.
  living    a living person's page has the section, or any page links to a living person's page from a namesake list.

A living person is never named in a message (their slug can carry a year): their page is reported as "a living person's page".
Exit 0 clean, 1 findings, 2 it could not see what it checks (no build, no person page, no shared name to check against).
"""
import argparse
import html
import os
import re
import sys
import unicodedata

SECTION = "others-of-this-name"


def fold(s):
    s = unicodedata.normalize("NFD", html.unescape(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def text_of(x):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()


def read_pages(dist):
    pages = {}
    for root, _dirs, files in os.walk(dist):
        if "index.html" in files:
            rel = os.path.relpath(root, dist).replace(os.sep, "/")
            route = "/" if rel == "." else "/" + rel + "/"
            with open(os.path.join(root, "index.html"), encoding="utf-8", errors="replace") as f:
                pages[route] = f.read()
    return pages


def h1_of(raw):
    m = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.S)
    return text_of(m.group(1)) if m else ""


def is_living(raw):
    return bool(re.search(r'<meta name="robots" content="[^"]*noindex', raw[:6000]))


def is_placeholder(raw):
    return 'tag open">Placeholder' in raw


def listed(raw):
    """(has the section, the person pages its list links to, in order)"""
    m = re.search(r'id="%s"' % SECTION, raw)
    if not m:
        return False, []
    tail = raw[m.end():]
    ul = re.search(r'<ul class="oth-list[^"]*"[^>]*>(.*?)</ul>', tail, re.S)
    hrefs = re.findall(r'href="(/people/[^"#?]+/)"', ul.group(1)) if ul else []
    return True, hrefs


def check(pages):
    """(findings, counts, setof) over an in-memory build: route -> html. findings is None when there is nothing to check."""
    findings = []
    persons = {}
    for route, raw in pages.items():
        if route.startswith("/people/") and route != "/people/" and "data-person-page" in raw:
            persons[route] = {"h1": h1_of(raw), "living": is_living(raw), "placeholder": is_placeholder(raw)}
    if not persons:
        return None, {}, {}
    label = lambda r: "a living person's page" if persons.get(r, {}).get("living") else r
    eligible = {r: p for r, p in persons.items() if not p["living"] and not p["placeholder"]}

    group = {}
    for r, p in eligible.items():
        group.setdefault(fold(p["h1"]), []).append(r)
    setof = {}
    for members in group.values():
        for r in members:
            setof[r] = set(members) - {r}
    shared_sets = {b for b, m in group.items() if len(m) > 1}

    with_section = 0
    for r in sorted(persons):
        has, got = listed(pages[r])
        if has:
            with_section += 1
        if r not in eligible:
            if has:
                findings.append("living: %s is a %s page and has a #%s section" % (label(r), "living person's" if persons[r]["living"] else "placeholder", SECTION))
            continue
        others = setof[r]
        if others and not has:
            findings.append("absent: %s shares its name with %d other page(s) and has no #%s section" % (label(r), len(others), SECTION))
            continue
        if has and not others:
            findings.append("absent: %s has a #%s section and nobody shares its name" % (label(r), SECTION))
        miss = sorted(others - set(got))
        extra = sorted(set(got) - others)
        if miss:
            findings.append("missing: %s does not list %d of its name: %s" % (label(r), len(miss), ", ".join(label(x) for x in miss)))
        if extra:
            findings.append("extra: %s lists %d that do not carry its name: %s" % (label(r), len(extra), ", ".join(label(x) for x in extra)))
    counts = {"person pages": len(persons), "placeholders left out": sum(1 for p in persons.values() if p["placeholder"]),
              "living left out": sum(1 for p in persons.values() if p["living"]),
              "shared names": len(shared_sets), "pages with the section": with_section}
    return findings, counts, setof


def selftest(pages):
    f0, _c, setof = check(pages)
    ok = True
    print("  control: the untouched build -> %d finding(s)%s" % (len(f0 or []), "" if not f0 else "  <-- SHOULD BE 0"))
    if f0:
        ok = False
    shared = sorted(r for r, o in setof.items() if o)
    solo = sorted(r for r, o in setof.items() if not o)
    living = sorted(r for r, raw in pages.items() if r.startswith("/people/") and r != "/people/" and "data-person-page" in raw and is_living(raw))
    holders = sorted(r for r, raw in pages.items() if r.startswith("/people/") and "data-person-page" in raw and is_placeholder(raw))
    if not shared or not solo or not living or not holders:
        print("  no shared name, unshared person, living person or placeholder to plant against: refusing")
        return False
    a = shared[0]

    def planted(name, mutate, want):
        nonlocal ok
        v = dict(pages)
        mutate(v)
        got, _c, _s = check(v)
        hit = any(g.startswith(want) for g in (got or []))
        print("  %-52s %s" % (name, "caught" if hit else "MISSED  <-- the gate cannot see this"))
        ok = ok and hit

    other = sorted(setof[a])[0]
    planted("a person of the name left off a list",
            lambda v: v.__setitem__(a, re.sub(r'<li[^>]*>(?:(?!</li>).)*?href="%s".*?</li>' % re.escape(other), "", v[a], count=1, flags=re.S)), "missing")

    def add_to_list(href):
        def mutate(v):
            i = v[a].index('<ul class="oth-list')
            j = v[a].index("</ul>", i)
            v[a] = v[a][:j] + '<li><a href="%s">x</a></li>' % href + v[a][j:]
        return mutate
    planted("a stranger added to a list", add_to_list(solo[0]), "extra")
    planted("a list on a name nobody shares",
            lambda v: v.__setitem__(solo[0], v[solo[0]].replace("</main>", '<section id="%s"><ul class="oth-list"><li><a href="%s">x</a></li></ul></section></main>' % (SECTION, a), 1)), "absent")
    planted("a shared name with no section", lambda v: v.__setitem__(a, v[a].replace('id="%s"' % SECTION, 'id="nothing"')), "absent")
    planted("a list that names a living person's page", add_to_list(living[0]), "extra")
    planted("a section on a living person's page",
            lambda v: v.__setitem__(living[0], v[living[0]].replace("</main>", '<section id="%s"></section></main>' % SECTION, 1)), "living")
    planted("a section on a placeholder",
            lambda v: v.__setitem__(holders[0], v[holders[0]].replace("</main>", '<section id="%s"></section></main>' % SECTION, 1)), "living")
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dist", default="dist")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.dist):
        print("check-namesakes: %s is not a directory; nothing was checked" % a.dist)
        return 2
    pages = read_pages(a.dist)
    if a.selftest:
        return 0 if selftest(pages) else 1
    findings, counts, _setof = check(pages)
    if findings is None:
        print("check-namesakes: no person page in %s; nothing was checked" % a.dist)
        return 2
    if not counts["shared names"]:
        print("check-namesakes: no name is shared in %s; nothing was checked" % a.dist)
        return 2
    for f in findings:
        print("  FAIL  " + f)
    print("check-namesakes: " + ", ".join("%d %s" % (v, k) for k, v in counts.items()) + "; %d finding%s" % (len(findings), "" if len(findings) == 1 else "s"))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
