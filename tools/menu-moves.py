#!/usr/bin/env python3
"""Every entry of the header menu, old build against new: where each address stood and where it stands now, and the REACH PROOF
for every address that left a menu (12 November 2026, the menu regroup, PR A; written after the Defranceski menu-moves.py).

    python3 tools/menu-moves.py BEFORE_DIST AFTER_DIST [OUT.md]

Reads the <nav class="topnav"> of the home page of each build. An address that was in the menu and is in no menu now must be reachable from
a page that is still in a menu (an index or a hub): the script reads the built HTML of every page that is in the new menu, looks for a link
to the address in its <main>, and lists the pages that carry one. An address with no such page is a failure (exit 1): it must stay in the
menu. Also fails if an address in the new menu is not a built page.
"""
import html, os, re, sys


def menu(dist):
    t = open(dist + "/index.html", encoding="utf-8").read()
    nav = t[t.index('<nav class="topnav"'):]
    nav = nav[:nav.index("</nav>")]
    out = []   # (menu, group-or-sub, href, label)
    for m in re.finditer(r'<details class="menu">(.*?)</details>', nav, re.S):
        body = m.group(1)
        label = html.unescape(re.search(r"<summary>(.*?)</summary>", body, re.S).group(1))
        grp = ""
        for tok in re.finditer(r'<div class="pg">|<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>|<span class="ps[^"]*">(.*?)</span>', body, re.S):
            whole = tok.group(0)
            if whole.startswith('<div class="pg"'):
                grp = ""
            elif tok.group(3) is not None:
                grp = html.unescape(tok.group(3))
                if "ph0" in whole[:30]:
                    out.append((label, grp, None, grp + "  (group heading, no page)"))
            else:
                href, txt = tok.group(1), html.unescape(re.sub(r"<[^>]+>", "", tok.group(2)))
                if re.match(r'<a [^>]*class="ph[ "]', whole):
                    grp = txt
                    out.append((label, grp, href, txt + "  (group heading)"))
                else:
                    out.append((label, grp, href, txt))
    return out


def page_path(dist, href):
    p = dist + href.split("#")[0]
    if p.endswith("/"):
        p += "index.html"
    return p


def main_html(path):
    t = open(path, encoding="utf-8", errors="replace").read()
    i = t.find("<main")
    return t[i:] if i >= 0 else t


def links_of(path):
    return set(re.sub(r"#.*$", "", h) for h in re.findall(r'href="([^"]+)"', main_html(path)))


def main():
    bd, ad = sys.argv[1], sys.argv[2]
    b, a = menu(bd), menu(ad)
    bh, ah = {}, {}
    for m, g, h, l in b:
        if h:
            bh.setdefault(h, []).append((m, g, l))
    for m, g, h, l in a:
        if h:
            ah.setdefault(h, []).append((m, g, l))
    fmt = lambda xs: "; ".join("%s%s: %s" % (m, " / " + g if g else "", l) for m, g, l in xs) or "—"
    L = ["# The menu, before and after", "",
         "Read from the header menu of the home page of the build of main (before) and of this branch (after). A *group heading* is the label at the top of a column (a link where it has a page).", "",
         "| address | was | now |", "|---|---|---|"]
    for h in list(dict.fromkeys([x[2] for x in b if x[2]] + [x[2] for x in a if x[2]])):
        if fmt(bh.get(h, [])) != fmt(ah.get(h, [])):
            L.append("| `%s` | %s | %s |" % (h, fmt(bh.get(h, [])), fmt(ah.get(h, []))))

    def counts(entries):
        c = {}
        for m, g, h, l in entries:
            if h:
                c[m] = c.get(m, 0) + 1
        return c
    cb, ca = counts(b), counts(a)
    L += ["", "## Entry counts (every linked entry, group headings that are links included)", "",
          "| menu | before | after |", "|---|---:|---:|"]
    for m in list(dict.fromkeys(list(cb) + list(ca))):
        L.append("| %s | %s | %s |" % (m, cb.get(m, "—"), ca.get(m, "—")))
    nb = sum(v for k, v in cb.items() if k != "Research")
    na = sum(v for k, v in ca.items() if k != "Research")
    L.append("| **outside Research** | **%d** | **%d** |" % (nb, na))
    L.append("| **all** | **%d** | **%d** |" % (sum(cb.values()), sum(ca.values())))
    L.append("| menus | %d | %d |" % (len(cb), len(ca)))

    after_menu_pages = list(dict.fromkeys(h for _, _, h, _ in a if h))
    bad = 0
    L += ["", "## Reach proof: every address that left a menu, and the pages that stay in a menu and link to it", "",
          "| address that left | was in | reached from (pages still in a menu) |", "|---|---|---|"]
    graph = {}
    for h in after_menu_pages:
        pth = page_path(ad, h)
        if os.path.exists(pth):
            graph[h] = links_of(pth)
    left = [h for h in dict.fromkeys(x[2] for x in b if x[2]) if h not in ah]
    for h in left:
        want = h.split("#")[0]
        src = sorted(s for s, ls in graph.items() if want in ls and s.split("#")[0] != want)
        if not src:
            bad += 1
        L.append("| `%s` | %s | %s |" % (h, fmt(bh[h]), ", ".join("`%s`" % s for s in src[:6]) or "**NOTHING: keep it in the menu**"))
    if not left:
        L.append("| (none) | | |")
    L += ["", "## Every address in the new menu is a built page", ""]
    missing = [h for h in after_menu_pages if not os.path.exists(page_path(ad, h))]
    L.append(("All %d addresses answer." % len(after_menu_pages)) if not missing else "MISSING: " + ", ".join(missing))
    bad += len(missing)
    L += ["", "%d address(es) left a menu with no page that stays in a menu linking to them, or are not built." % bad]
    out = "\n".join(L) + "\n"
    if len(sys.argv) > 3:
        open(sys.argv[3], "w", encoding="utf-8").write(out)
    print(out)
    sys.exit(1 if bad else 0)


main()
