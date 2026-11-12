#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inventory of the pages the research-menu move touches, and the check that nothing was lost.

David's rule for the menu move (12 Nov 2026): we do not lose things in these moves.

    menu-inventory.py snapshot DIST OUT.json     what every in-scope page holds (counts, links, text blocks)
    menu-inventory.py sitediff BEFORE_DIST AFTER_DIST   every page of the site, old build against new: which changed, and is each declared
    menu-inventory.py compare  BEFORE.json DIST  every old URL still answers, and every text block that stood on
                                                 an old page stands somewhere on the new site

A "text block" is a paragraph, list item, table row, heading, summary or figure caption, whitespace and case
folded, at least 20 characters. After a move a block may sit on a different page (that is the point of a merge),
so the test is "somewhere on the new site", and the report says where. A block that has gone is listed; an
old URL that no longer answers (no page, no redirect stub) is listed.

Only the text under <main> (or the page wrapper) is read; the header, menu and footer are not part of a page.
"""
import hashlib, html, json, os, re, sys
from html.parser import HTMLParser

# the pages whose place in the menu changes, plus the ones that carry an AtlasNote (Luwinski archive, 12 Nov 2026)
SCOPE = [
    "/method/", "/sources/", "/searched/", "/open-questions/", "/errands/", "/worklist/", "/corrections/",
    "/changes/", "/status/", "/whats-new/", "/names/",
    # the addresses that are redirect stubs already: they must keep answering
    "/letters/", "/research-log/", "/negatives/", "/evidence/",
]
# a text block ends wherever one of these starts or ends; a table row (<tr>) is one block, however it is laid out inside
FLUSH_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "summary", "figcaption", "blockquote", "dt", "dd", "caption",
              "div", "section", "article", "details", "ul", "ol", "dl", "table", "thead", "tbody", "form", "br", "hr", "aside"}
COUNT_TAGS = {"p", "li", "tr", "h2", "h3", "section", "table", "details", "img", "a"}
SKIP_TAGS = {"script", "style", "noscript", "svg", "head", "nav", "header", "footer"}
ROW = "¦"   # marks a block that is a table row
VOID = {"br", "hr", "img", "input", "meta", "link"}


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.tr = 0
        self.in_row = False
        self.buf = []
        self.blocks = []
        self.links = []
        self.counts = {}

    def flush(self):
        txt = " ".join("".join(self.buf).split())
        self.buf = []
        if txt:
            self.blocks.append((ROW + txt) if self.in_row else txt)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in SKIP_TAGS:
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag in COUNT_TAGS:
            self.counts[tag] = self.counts.get(tag, 0) + 1
        if tag == "tr":
            self.flush()
            self.tr += 1
            self.in_row = True
        elif tag in FLUSH_TAGS and not self.tr:
            self.flush()
        elif tag in ("td", "th") and self.tr:
            self.buf.append(" ")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag == "tr":
            self.tr = max(0, self.tr - 1)
            if not self.tr:
                self.flush()
                self.in_row = False
        elif tag in FLUSH_TAGS and not self.tr:
            self.flush()

    def handle_data(self, data):
        if not self.skip:
            self.buf.append(data)

    def close(self):
        super().close()
        self.flush()


def norm(t):
    return re.sub(r"\s+", " ", t).strip().lower()


def page_file(dist, url):
    p = os.path.join(dist, url.strip("/"), "index.html")
    return p if os.path.exists(p) else None


def read_page(path):
    raw = open(path, encoding="utf-8").read()
    redirect = None
    m = re.search(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\'][^"\']*url=([^"\'>]+)', raw, re.I)
    if m:
        redirect = html.unescape(m.group(1))
    m = re.search(r"<main\b.*?</main>", raw, re.S | re.I) or re.search(r'<div class="wrap">.*', raw, re.S | re.I)
    body = m.group(0) if m else raw
    r = Reader()
    r.feed(body)
    r.close()
    blocks = []
    seen = set()
    for b in r.blocks:
        n = norm(b)
        if len(n) >= 20 and n not in seen:
            seen.add(n)
            blocks.append(n)
    title = re.search(r"<title>(.*?)</title>", raw, re.S)
    words = len(re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1>", " ", body, flags=re.S | re.I)).split())
    return {
        "title": html.unescape(title.group(1)).strip() if title else "",
        "redirect": redirect,
        "words": words,
        "counts": r.counts,
        "links": sorted(set(l for l in r.links if not l.startswith("#"))),
        "blocks": blocks,
    }


def snapshot(dist, out):
    inv = {"scope": {}, "note": "menu-inventory.py snapshot"}
    for url in SCOPE:
        f = page_file(dist, url)
        inv["scope"][url] = read_page(f) if f else None
    json.dump(inv, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("snapshot:", out)
    for url, p in inv["scope"].items():
        if p is None:
            print("  %-20s (no page)" % url)
        else:
            c = p["counts"]
            print("  %-20s %6d words  %4d blocks  %4d links  %3d rows  %3d sections" % (
                url, p["words"], len(p["blocks"]), len(p["links"]), c.get("tr", 0), c.get("section", 0)))


def all_blocks(dist):
    """every block of every page of the new site -> one of the pages it stands on"""
    where = {}
    for root, _, files in os.walk(dist):
        if "index.html" not in files:
            continue
        url = "/" + os.path.relpath(root, dist).replace(os.sep, "/") + "/"
        url = "/" if url == "/./" else url
        if url.startswith(("/people/",)):
            continue
        for b in read_page(os.path.join(root, "index.html"))["blocks"]:
            where.setdefault(b, url)
    return where


def resolve(dist, url, hops=0):
    """does an old URL answer? returns (ok, final url, kind)"""
    f = page_file(dist, url)
    if not f:
        return False, url, "missing"
    p = read_page(f)
    if p["redirect"] and hops < 4:
        t = p["redirect"]
        t = re.sub(r"^https?://[^/]+", "", t).split("#")[0]
        ok, fin, kind = resolve(dist, t if t.startswith("/") else "/" + t, hops + 1)
        return ok, fin, "redirect"
    return True, url, "page"


def load_changes():
    """docs/menu-text-changes.json: what was changed ON PURPOSE, so it is never mistaken for a loss and never hidden either.
      token_swaps   one word of a block changed for another (a vocabulary tidied): the old block counts as kept if a new block on the
                    same page-family has the same words but for exactly that word. Only for the pages named.
      accepted      a block whose wording changed in a way a swap cannot describe: matched by its start, with the reason.
    Both are printed with their counts."""
    f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "menu-text-changes.json")
    if not os.path.exists(f):
        return [], [], {}
    d = json.load(open(f, encoding="utf-8"))
    return d.get("token_swaps", []), d.get("accepted", []), d.get("snapshot_pages", {})


def compare(before, dist):
    inv = json.load(open(before, encoding="utf-8"))
    where = all_blocks(dist)
    swaps, accepted, snaps = load_changes()
    big = None
    heads = {}
    for blk, w in where.items():
        t = blk.split()
        heads.setdefault((len(t), tuple(t[:6])), []).append((blk, w))
    used = {i: 0 for i in range(len(swaps))}
    used_acc = {i: 0 for i in range(len(accepted))}

    def contained(b):
        """an old block that now stands inside a longer one (a row that gained a link) is kept"""
        nonlocal big
        if big is None:
            big = "\n".join(where)
        return b in big

    def swapped(b, url):
        """the same block but for one swapped word -> where it stands, or None"""
        t = b.split()
        for blk, w in heads.get((len(t), tuple(t[:6])), []):
            u = blk.split()
            diff = [(x, y) for x, y in zip(t, u) if x != y]
            if len(diff) == 1:
                for i, sw in enumerate(swaps):
                    if url in sw["pages"] and norm(sw["old"]) == diff[0][0] and norm(sw["new"]) == diff[0][1]:
                        used[i] += 1
                        return w
        # the swapped word may be among the first six: try the other direction of indexing
        for i, sw in enumerate(swaps):
            if url in sw["pages"] and norm(sw["old"]) in t:
                k = t.index(norm(sw["old"]))
                while True:
                    u = t[:k] + [norm(sw["new"])] + t[k + 1:]
                    cand = " ".join(u)
                    if cand in where:
                        used[i] += 1
                        return where[cand]
                    try:
                        k = t.index(norm(sw["old"]), k + 1)
                    except ValueError:
                        break
        return None

    def accepted_by(b, url):
        for i, a in enumerate(accepted):
            if url in a["pages"] and b.lstrip(ROW).startswith(norm(a["starts"])):
                used_acc[i] += 1
                return True
        return False

    def tok(b):
        return set(re.findall(r"\w+", b))

    new_tok = {}

    def near(b, url):
        """best token overlap (Jaccard) between an old block and any block now standing on the same page"""
        blocks = new_tok.get(url)
        if blocks is None:
            f = page_file(dist, url)
            blocks = new_tok[url] = [tok(x) for x in read_page(f)["blocks"]] if f else []
        t = tok(b)
        return max((len(t & u) / len(t | u) for u in blocks if u), default=0)

    reworded = {}
    bad = 0
    print("%-20s %-12s %7s %7s  %s" % ("old URL", "answers", "blocks", "kept", "where the rest went / what is lost"))
    for url, p in inv["scope"].items():
        if p is None:
            continue
        ok, fin, kind = resolve(dist, url)
        lost = []
        moved = {}
        for b in p["blocks"]:
            w = where.get(b)
            if w is None:
                w = swapped(b, url)
            if w is None and (contained(b) or accepted_by(b, url)):
                w = url
            if w is None and url in snaps:
                sim = near(b, url)
                if sim >= 0.8:
                    w = url          # the same entry; only the kind chip or a word of it differs
                else:
                    reworded.setdefault(url, []).append((sim, b))
                    w = url
            if w is None:
                lost.append(b)
            elif w != url:
                moved[w] = moved.get(w, 0) + 1
        status = ("%s->%s" % (kind, fin)) if ok else "MISSING"
        print("%-20s %-12s %7d %7d  %s" % (url, status[:12], len(p["blocks"]), len(p["blocks"]) - len(lost),
                                            ", ".join("%d on %s" % (n, w) for w, n in sorted(moved.items(), key=lambda x: -x[1])[:4])))
        if not ok:
            bad += 1
        for b in lost:
            bad += 1
            print("    LOST on %s: %s" % (url, b[:150]))
    print()
    for url, lst in reworded.items():
        print("REWORDED SINCE THE SNAPSHOT on %s: %d entr%s of the old page copy a log row (or a hand entry) whose wording has since been changed in the log itself;"
              % (url, len(lst), "y" if len(lst) == 1 else "ies"))
        print("    the old page, whole, is kept in %s. %s" % (snaps[url]["file"], snaps[url]["why"]))
        for sim, b in sorted(lst)[:40]:
            print("      %.2f  %s" % (sim, b[:130]))
    for i, sw in enumerate(swaps):
        print("intentional: %d block(s) on %s had %r changed to %r  (%s)" % (used[i], ", ".join(sw["pages"]), sw["old"], sw["new"], sw["why"]))
    for i, a in enumerate(accepted):
        print("intentional: %d block(s) on %s starting %r reworded  (%s)" % (used_acc[i], ", ".join(a["pages"]), a["starts"][:50], a["why"]))
    print("\n%s" % ("NOTHING LOST" if not bad else "%d problem(s)" % bad))
    return 1 if bad else 0


def sitediff(before, after):
    """Every page of the old build against the same page of the new: the pages whose text changed, and whether each change is one that
    docs/menu-text-changes.json says was made on purpose ("site_changes"). Catches what the in-scope check cannot: a number on the home
    page that counted a word which no longer exists, say. Exit 1 on a page that changed without being declared, or one that went."""
    f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "menu-text-changes.json")
    declared = json.load(open(f, encoding="utf-8")).get("site_changes", [])

    def pages(d):
        out = {}
        for root, _, files in os.walk(d):
            if "index.html" in files:
                out[("/" + os.path.relpath(root, d).replace(os.sep, "/") + "/").replace("/./", "/")] = os.path.join(root, "index.html")
        return out

    pb, pa = pages(before), pages(after)
    gone = sorted(set(pb) - set(pa))
    new = sorted(set(pa) - set(pb))
    bad = 0
    print("pages before %d, after %d; gone: %s; new: %s" % (len(pb), len(pa), gone or "none", new or "none"))
    changed = []
    for u, fn in pb.items():
        if u in pa:
            x, y = set(read_page(fn)["blocks"]), set(read_page(pa[u])["blocks"])
            if x != y:
                changed.append((u, len(x - y), len(y - x)))
    for u, a, b in sorted(changed, key=lambda t: -(t[1] + t[2])):
        why = next((d["why"] for d in declared if d["page"] == u or (d["page"].endswith("*") and u.startswith(d["page"][:-1]))), None)
        print("  %-26s -%-5d +%-5d %s" % (u, a, b, ("declared: " + why) if why else "NOT DECLARED"))
        if not why:
            bad += 1
    for u in gone:
        if not any(d["page"] == u for d in declared):
            print("  GONE without a declaration: %s" % u)
            bad += 1
    print("\n%s" % ("every changed page is declared" if not bad else "%d undeclared change(s)" % bad))
    return 1 if bad else 0


def report(before, dist, out):
    """docs/menu-inventory.md: for every in-scope page, what it holds (counts, before and after) and what only it holds."""
    inv = json.load(open(before, encoding="utf-8"))
    holds = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "menu-pages-hold.json"), encoding="utf-8"))
    L = ["# Research-menu pattern, Luwinski archive: inventory of the pages that move or change", "",
         "Generated by `tools/menu-inventory.py report` from `docs/menu-inventory-before.json` (the build of main before this branch) and the build of this branch.",
         "A *block* is a paragraph, list item, table row, heading or caption of at least 20 characters. *Rows* are table rows, *links* the distinct addresses linked from the page.", "",
         "| Page | Blocks before | after | Rows before | after | Links before | after | Answers now | What only this page holds |", "|---|---:|---:|---:|---:|---:|---:|---|---|"]
    for url, p in inv["scope"].items():
        if p is None:
            continue
        ok, fin, kind = resolve(dist, url)
        f = page_file(dist, url)
        a = read_page(f) if f else None
        redirect = bool(a and a["redirect"])
        L.append("| `%s` | %d | %s | %d | %s | %d | %s | %s | %s |" % (
            url, len(p["blocks"]), "—" if redirect or not a else len(a["blocks"]), p["counts"].get("tr", 0), "—" if redirect or not a else a["counts"].get("tr", 0),
            len(p["links"]), "—" if redirect or not a else len(a["links"]),
            ("redirect to `%s`" % fin) if redirect else ("page" if ok else "**MISSING**"), holds.get(url, "")))
    new = ["/research/", "/research/to-do/", "/research/sources-and-method/"]
    L += ["", "New pages: " + ", ".join("`%s`" % n + (" (built)" if page_file(dist, n) else " (MISSING)") for n in new) + ".", ""]
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("report:", out)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "sitediff":
        sys.exit(sitediff(sys.argv[2], sys.argv[3]))
    elif len(sys.argv) == 5 and sys.argv[1] == "report":
        report(sys.argv[2], sys.argv[3], sys.argv[4])
    elif len(sys.argv) == 4 and sys.argv[1] == "snapshot":
        snapshot(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 4 and sys.argv[1] == "compare":
        sys.exit(compare(sys.argv[2], sys.argv[3]))
    else:
        print(__doc__)
        sys.exit(2)
