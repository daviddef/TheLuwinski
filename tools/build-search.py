#!/usr/bin/env python3
"""Build the search index from the rendered site.

Runs AFTER astro build, over site/dist, and writes searchindex.json next to the
pages. Indexing the rendered HTML rather than the .astro sources means what is
searched is exactly what a reader can see — including anything a component
generated, and nothing that was stripped by the living-persons rule.
"""
import html, json, pathlib, re, sys, unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "site" / "dist"

def text_of(fragment):
    fragment = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", fragment)
    fragment = re.sub(r"(?s)<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(fragment)).strip()

def fold(s):
    """Lowercase and strip accents, so a reader typing `Schoneberg` finds
       Schöneberg. The shared box folds the query the same way."""
    return unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode()


def main():
    if not DIST.exists():
        sys.exit("build-search: no dist; run astro build first")
    entries = []
    for f in sorted(DIST.rglob("index.html")):
        raw = f.read_text(encoding="utf-8", errors="ignore")
        url = "/" + str(f.parent.relative_to(DIST)).replace(".", "").strip("/")
        url = (url.rstrip("/") + "/") if url != "/" else "/"
        title = text_of((re.search(r"(?is)<title>(.*?)</title>", raw) or [None, ""])[1])
        title = title.split(" — ")[0].strip() or url
        body = raw.split("<main", 1)[-1]
        # one entry per section, so a hit lands on the right part of a long page
        sections = re.split(r"(?i)(?=<h2\b)", body)
        for sec in sections:
            heading = text_of((re.search(r"(?is)<h2[^>]*>(.*?)</h2>", sec) or [None, ""])[1])
            content = text_of(sec)
            if heading:
                content = content[len(heading):].strip()
            if len(content) < 40:
                continue
            # THE ESTATE'S SCHEMA, ADOPTED 22 SEPTEMBER 2026. Seven archives
            # already emit k/t/s/h/q and share one search box; this archive
            # emitted page/url/heading/text and carried 85 lines of its own
            # box to read it. The fields map one-for-one — only `q`, the
            # folded haystack the shared box ranks on, is new.
            entries.append({
                "k": "Page",
                "t": heading or title,
                "s": title if heading else "",
                "h": url,
                "q": fold(" ".join([title, heading or "", content[:1500]])),
            })
    payload = json.dumps(entries, ensure_ascii=False)
    # Written to BOTH, deliberately, and the reason is the ordering of the build chain.
    # astro build empties dist before it refills it, and build-search runs AFTER astro,
    # so a copy in dist alone exists only between the end of one build and the start of
    # the next: any bare `astro build`, or any build interrupted before this step, and
    # the search page fetches a file that is not there. A copy in public alone is worse
    # in a quieter way -- astro copies public into dist DURING the build, before this
    # script has run, so dist would carry the PREVIOUS build's index and be permanently
    # one build stale. Writing both gives dist a fresh index now and leaves a durable
    # copy that the next astro build will lay down before this script overwrites it.
    out = DIST / "searchindex.json"
    out.write_text(payload, encoding="utf-8")
    keep = ROOT / "site" / "public" / "searchindex.json"
    keep.write_text(payload, encoding="utf-8")
    print(f"build-search: {len(entries)} sections across "
          f"{len(set(e['h'] for e in entries))} pages -> {out.relative_to(ROOT)} "
          f"and {keep.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
