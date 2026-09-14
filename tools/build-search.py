#!/usr/bin/env python3
"""Build the search index from the rendered site.

Runs AFTER astro build, over site/dist, and writes searchindex.json next to the
pages. Indexing the rendered HTML rather than the .astro sources means what is
searched is exactly what a reader can see — including anything a component
generated, and nothing that was stripped by the living-persons rule.
"""
import html, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "site" / "dist"

def text_of(fragment):
    fragment = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", fragment)
    fragment = re.sub(r"(?s)<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(fragment)).strip()

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
            entries.append({
                "page": title,
                "url": url,
                "heading": heading or None,
                "text": content[:1500],
            })
    out = DIST / "searchindex.json"
    out.write_text(json.dumps({"entries": entries}, ensure_ascii=False), encoding="utf-8")
    print(f"build-search: {len(entries)} sections across "
          f"{len(set(e['url'] for e in entries))} pages -> {out.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
