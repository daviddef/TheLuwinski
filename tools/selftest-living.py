#!/usr/bin/env python3
"""Plant a fault for every rule of tools/check-living.py in a COPY of the build and demand that
the gate catch it. A check that can only pass proves nothing.

For each rule there is a fault that must make the gate exit 1 with that rule's message, and for
the rules that depend on context there is a control that must NOT fail, so the gate is shown to
be specific as well as sensitive:

  - the untouched build passes (the baseline), in both modes where both can run;
  - a year planted beside a DEAD person's name does not fail (it is that person's own date);
  - a page about a living person passes once it is `noindex` and out of the sitemap;
  - and a build in which no living person is recognised, an empty build, an empty guard list
    and a register that flags no one living are all REFUSED, never reported ok.

The names it plants beside come from site/src/data/register.json, which is public, so this runs
in CI as well as locally. The harvest-only rule (an exact date from the private harvest) runs only
where the harvest is present and is reported as skipped where it is not.

Usage: python3 tools/selftest-living.py --dist site/dist
Exit 0 only if every planted fault was caught and every control passed.
"""
import argparse, json, os, pathlib, re, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
GATE = ROOT / "tools" / "check-living.py"


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


def living_records():
    reg = json.load(open(ROOT / "site" / "src" / "data" / "register.json"))["people"]
    return [p for p in reg if p.get("living")], reg


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
    living, reg = living_records()
    # a living person recognisable by name (two or more tokens, not a placeholder)
    named = [p for p in living if len((p["name"] or "").split()) >= 2 and "unknown" not in p["name"].lower()
             and re.search(r"[A-Za-z]{3}", p["first"] or "") and re.search(r"[A-Za-z]{3}", p["last"] or "")]
    dead = [p for p in reg if not p.get("living") and not p.get("bare") and p.get("kind") == "family"
            and p.get("born") and "unknown" not in p["name"].lower()]
    if not named or not dead:
        sys.exit("selftest-living: REFUSED: no living person with a recognisable name in the register")
    # the register's family table prints a name in <strong>; the surname-index table does not
    # and the planting needs a person who is a node of the blood-relatives chart and a row of the table
    blood = (dist / "bloodline" / "index.html").read_text(encoding="utf-8")
    regpage = (dist / "register" / "index.html").read_text(encoding="utf-8")
    ok_for_planting = [p for p in named if p.get("kind") == "family"
                       and re.search(r'"slug":"%s","name":"[^"]*","dt":""' % p["id"], blood)
                       and ("<strong>%s</strong>" % p["name"]) in regpage]
    if not ok_for_planting:
        sys.exit("selftest-living: REFUSED: no living person is both a table row and a chart node in this build")
    L = ok_for_planting[0]
    LID = str(L["id"])
    D = dead[0]
    sb = Sandbox(dist, harvest)
    results = []          # (label, expected, ok, detail)

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
            raise SystemExit(f"selftest-living: could not plant (pattern not found in {path.name}): {old_rx[:50]}")
        path.write_text(t2, encoding="utf-8")

    nm = re.escape(L["name"])
    for mode in modes:
        # --- baseline
        case("the untouched build", mode, False, lambda b, d: None)

        # --- context: the text that stands with a living name
        case("a birth year planted in a living person's register row", mode, True,
             lambda b, d: sub_in(d / "register" / "index.html", r"(<strong>" + nm + r"</strong>)", r"\1 (b. 1961)"),
             "stands with a living person")
        case("a full date planted in a living person's register row", mode, True,
             lambda b, d: sub_in(d / "register" / "index.html", r"(<strong>" + nm + r"</strong>)", r"\1 12 March 1961"),
             "stands with a living person")
        case("the word «died» planted in a living person's register row", mode, True,
             lambda b, d: sub_in(d / "register" / "index.html", r"(<strong>" + nm + r"</strong>)", r"\1 died"),
             "stands with a living person")
        case("CONTROL: a year planted beside a DEAD person's name", mode, False,
             lambda b, d: sub_in(d / "register" / "index.html", r"(<strong>" + re.escape(D["name"]) + r"</strong>)", r"\1 (b. 1961)"))
        case("a year in an attribute that carries a living person's name", mode, True,
             lambda b, d: sub_in(d / "register" / "index.html", r"<table", f'<table title="{L["name"]} born 1961"'),
             "attribute")
        case("a living person named in the meta description with a date", mode, True,
             lambda b, d: sub_in(d / "index.html", r"<head>", f'<head><meta name="description" content="{L["name"]}, 3 May 1961">'),
             "attribute")

        # --- structured data
        case("JSON-LD Person naming a living person", mode, True,
             lambda b, d: sub_in(d / "index.html", r"</head>",
                                 '<script type="application/ld+json">{"@type":"Person","name":"' + L["name"] + '"}</script></head>'),
             "json-ld")

        # --- the embedded chart data
        case("a date on a living person's node in the blood-relatives chart data", mode, True,
             lambda b, d: sub_in(d / "bloodline" / "index.html",
                                 r'("slug":"' + LID + r'","name":"[^"]*","dt":)""', r'\1"1961 – "'),
             "chart node")
        case("a field beyond name on a living person's chart node", mode, True,
             lambda b, d: sub_in(d / "bloodline" / "index.html",
                                 r'("slug":"' + LID + r'",)', r'\1"occupation":"engineer 2",'),
             "chart node")

        # --- a page about a living person
        slug = re.sub(r"[^a-z]+", "-", L["name"].lower()).strip("-")

        def living_page(noindex, in_sitemap):
            def f(b, d):
                p = d / "people" / slug
                p.mkdir(parents=True, exist_ok=True)
                robots = '<meta name="robots" content="noindex">' if noindex else ""
                (p / "index.html").write_text(
                    f"<!doctype html><html><head><title>{L['name']}</title>{robots}</head><body><main>"
                    f"<h1>{L['name']}</h1><p>Living.</p></main></body></html>", encoding="utf-8")
                if in_sitemap:
                    sm = d / "sitemap.xml"
                    t = sm.read_text(encoding="utf-8") if sm.exists() else \
                        '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
                    t = t.replace("</urlset>", f"<url><loc>https://example.test/people/{slug}/</loc></url></urlset>")
                    sm.write_text(t, encoding="utf-8")
            return f
        case("a page about a living person without noindex", mode, True, living_page(False, False), "lacks noindex")
        case("a noindex page about a living person that is in the sitemap", mode, True, living_page(True, True), "sitemap")
        case("CONTROL: a noindex page about a living person, out of the sitemap", mode, False, living_page(True, False))

        def sitemap_only(b, d):
            sm = d / "sitemap.xml"
            t = sm.read_text(encoding="utf-8") if sm.exists() else \
                '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
            sm.write_text(t.replace("</urlset>", f"<url><loc>https://example.test/who/{slug}/</loc></url></urlset>"),
                          encoding="utf-8")
        case("a sitemap address that is a living person's name", mode, True, sitemap_only, "address in the sitemap")

        # --- the search index
        def idx(entry):
            def f(b, d):
                p = d / "searchindex.json"
                data = json.loads(p.read_text(encoding="utf-8"))
                data.append(entry)
                p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return f
        case("a search-index entry headed by a living person", mode, True,
             idx({"k": "Page", "t": L["name"], "s": "", "h": "/x/", "q": "x"}), "search-index")
        if mode == "harvest":
            fq = (L["name"] + " 1961 born").lower()
            case("a digit hard against a living name in indexed text", mode, True,
                 idx({"k": "Page", "t": "Register", "s": "", "h": "/register/", "q": fq}), "indexed text")

        # --- the generated register
        def reg_edit(fn):
            def f(b, d):
                p = b / "site" / "src" / "data" / "register.json"
                data = json.load(open(p))
                for r in data["people"]:
                    if str(r["id"]) == LID:
                        fn(r, data)
                json.dump(data, open(p, "w"))
            return f
        case("a birth date on a living record in the register", mode, True,
             reg_edit(lambda r, data: r.update(born="Mar 3 1961")), "born date")
        case("a birth year on a living record in the register", mode, True,
             reg_edit(lambda r, data: r.update(by=1961)), "by year")
        case("a fact on a living record in the register", mode, True,
             reg_edit(lambda r, data: r.update(facts=[{"t": "Marriage to:", "date": "1990"}])), "events or facts")
        case("a field beyond the allowed ones on a living record (a profile link)", mode, True,
             reg_edit(lambda r, data: r.update(profile="https://example.test/x")), "beyond the allowed")
        case("a street address as a living record's place", mode, True,
             reg_edit(lambda r, data: r.update(town="12 High Street", place="12 High Street")), "plain town or country")
        case("a living record whose flag is removed (published as if dead)", mode, True,
             reg_edit(lambda r, data: r.pop("living")), "differ from the people")

        def edge_ls(r, data):
            for q in data["people"]:
                for e in q.get("rel", []):
                    if str(e["id"]) == LID:
                        e["ls"] = "Born: 1799"
                        return
        case("the source's life span on a relationship edge to a living person", mode, True,
             reg_edit(lambda r, data: edge_ls(r, data)), "life span")

    # --- harvest-only: the exact leak scan
    if harvest:
        people = json.load(open(ROOT / "data" / "myheritage-tree9.json"))
        by_id = {p["id"]: p for p in people}
        prof = by_id[int(LID)].get("profile")
        if prof and len(prof) >= 10:
            case("the harvest's profile link for a living person present in a built page", "harvest", True,
                 lambda b, d: sub_in(d / "index.html", r"</body>", f'<a href="{prof}">x</a></body>'),
                 "profile link")
        else:
            results.append(("[harvest] profile-link leak (no profile for this person)", "fails", False, "cannot plant"))
        # the tree's own birth date for a living person who has one
        bd = [p for p in people if livingtest_alive(p) and (p.get("b") or "").strip()]
        if bd:
            bstr = bd[0]["b"].strip()
            case("the harvest's birth date for a living person present in a built page", "harvest", True,
                 lambda b, d: sub_in(d / "index.html", r"</body>", f"<p>{bstr}</p></body>"), "b date")

    # --- refusals: nothing examined is never ok
    for mode in modes:
        def empty_guard(b, d):
            g = json.load(open(b / "data" / "guarded-hashes.json"))
            g["digests"] = []
            json.dump(g, open(b / "data" / "guarded-hashes.json", "w"))
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

    sb.done()
    width = max(len(r[0]) for r in results)
    bad = 0
    for label, expect, ok, detail in results:
        print(f"  {'ok  ' if ok else 'FAIL'}  {label.ljust(width)}  expected to {expect}" + ("" if ok else f"  -> {detail}"))
        bad += not ok
    print(f"selftest-living: {len(results) - bad} of {len(results)} planted faults and controls behaved as required"
          + ("" if harvest else "; harvest-only rules skipped (no private harvest here)"))
    sys.exit(1 if bad else 0)


def livingtest_alive(p):
    sys.path.insert(0, str(ROOT / "tools"))
    import livingtest
    return livingtest.might_be_alive(p)


if __name__ == "__main__":
    main()
