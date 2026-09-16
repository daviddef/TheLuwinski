#!/usr/bin/env python3
"""Query The National Archives' Discovery catalogue.

WHY THIS EXISTS. This archive published its two hundred and nineteenth commit
citing RG10, RG11, RG12, RG13, RG14, RG15, BT 27, WO 329, WO 372 and WO 392 -
hundreds of references to records held at Kew - AND HAD NEVER ONCE OPENED THE
CATALOGUE THOSE REFERENCES BELONG TO. Every one came second-hand through a
commercial index's transcript. Discovery is free, needs no account, answers
JSON, and describes 2,500+ other archives besides Kew's own.

    python3 tools/tna.py "Castle 10061 Scottish Rifles"
    python3 tools/tna.py --verify "WO 392/15" "WO 329/1120"

TWO THINGS IT IS GOOD FOR AND ONE IT IS NOT.
  VERIFYING A CITATION. Paste a reference and read back what the catalogue says
  the thing is. This found that WO 392/15 is specifically "Section 5: South
  Africa (Union Defence Forces)", which is a better citation than the one this
  archive had published.
  FINDING WHERE A RECORD LIVES. Discovery indexes county record offices, so it
  answers "which register would hold this baptism" with an orderable reference.
  IT IS NOT A NAME INDEX. Most series are described at piece level, not person
  level. A person returning nothing here has usually not been searched for.
"""
import json, sys, urllib.request, urllib.parse

API = "https://discovery.nationalarchives.gov.uk/API/search/records"
UA = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}


def search(q, n=20, **extra):
    p = {"sps.searchQuery": q, "sps.resultsPageSize": str(n)}
    p.update(extra)
    url = API + "?" + urllib.parse.urlencode(p)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as fh:
        return json.load(fh)


def held(rec):
    h = rec.get("heldBy")
    return (h[0] if isinstance(h, list) and h else h) or ""


def line(rec):
    return (rec.get("reference") or "?", rec.get("coveringDates") or "",
            (rec.get("description") or rec.get("title") or "").replace("\n", " ")[:150],
            held(rec), rec.get("id") or "")


def verify(ref):
    """Read back what the catalogue says a reference actually is."""
    r = search('"%s"' % ref, 5)
    recs = r.get("records") or []
    exact = [x for x in recs if (x.get("reference") or "") == ref]
    if not recs:
        return ref, None
    return ref, line(exact[0] if exact else recs[0])


def main(argv):
    if not argv:
        print(__doc__); return 2
    if argv[0] == "--verify":
        for ref in argv[1:]:
            r, got = verify(ref)
            if not got:
                print(f"  {r:<16} NOT FOUND IN THE CATALOGUE")
            else:
                print(f"  {r:<16} {got[1]:<24} {got[2]}")
        return 0
    q = argv[0]
    n = int(argv[1]) if len(argv) > 1 else 15
    r = search(q, n)
    print("COUNT", r.get("count"))
    for rec in (r.get("records") or []):
        ref, dates, desc, h, i = line(rec)
        print(f"  {ref:<22} {dates:<24} {desc}  [{h}] {i}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
