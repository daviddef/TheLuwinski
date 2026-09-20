#!/usr/bin/env python3
"""Audit the family tree against itself and against its own citations.

Two checks, both mechanical, neither of which needs a network:

  CITATIONS  Most FamilySearch citation strings carry the record's own
             description — "Entry for X and Y, 19 Jun 1948". Compare that
             date with the date of the fact the citation is attached to.
             A parish register records the BAPTISM or the BURIAL, so a
             record 1-45 days after the event is correct practice and not
             an error. Anything further apart is reported.

             Arolsen citations are bare URLs with nothing in them to check
             against, so they are counted and listed, not verified. That is
             itself the finding: six of the seven were wrong and nothing in
             the citation could have caught it.

  ARITHMETIC Death before birth, age over 105, a parent under 14 or over 60
             at a child's birth, a mother dead before her child was born, a
             father dead more than a year before.

Run:  python3 tools/audit-tree.py
The harvest is gitignored, so this is a local check and not a build gate.
"""
import collections, datetime, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HARVEST = ROOT / "data" / "myheritage-tree9.json"
BAPTISM_LAG_DAYS = 45          # a record this soon after the event is the baptism or burial
MON = {m: i + 1 for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split())}


def date(s):
    if not s:
        return None
    for rx, order in ((r'([A-Za-z]{3,})\s+(\d{1,2})[, ]+(\d{4})', (1, 2, 3)),
                      (r'(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{4})', (2, 1, 3))):
        m = re.search(rx, s)
        if m and m.group(order[0])[:3].lower() in MON:
            try:
                return datetime.date(int(m.group(order[2])),
                                     MON[m.group(order[0])[:3].lower()],
                                     int(m.group(order[1])))
            except ValueError:
                return None
    return None


def year(s):
    m = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", s or "")
    return int(m.group(1)) if m else None


def record_date(raw):
    """The date the citation says the RECORD carries, not the access date."""
    m = re.search(r"Entry for [^,]*(?:and [^,]*)?,\s*([^.]+)\.?\s*$", raw)
    return date(m.group(1)) if m else None


def main():
    if not HARVEST.exists():
        sys.exit(f"audit-tree: {HARVEST} not found — the harvest is local only")
    people = json.load(open(HARVEST))
    by = {p["id"]: p for p in people}

    cites = collections.Counter()
    verdicts = collections.Counter()
    wrong, arolsen = [], []
    for p in people:
        for f in p.get("facts") or []:
            for key in ("ac", "c"):
                raw = (f.get(key) or "").strip()
                if "http" not in raw and "FamilySearch" not in raw:
                    continue
                host = re.search(r"https?://([^/\s]+)", raw)
                host = host.group(1) if host else "(prose)"
                cites[host] += 1
                if "arolsen" in host:
                    arolsen.append((p["id"], p["name"], f.get("t"), f.get("date"), raw))
                    continue
                if "familysearch" not in host:
                    continue
                fd, rd = date(f.get("date") or ""), record_date(raw)
                if fd is None:
                    verdicts["fact has no full date"] += 1
                elif rd is None:
                    verdicts["citation carries no record date"] += 1
                elif rd == fd:
                    verdicts["exact match"] += 1
                elif 0 < (rd - fd).days <= BAPTISM_LAG_DAYS:
                    verdicts["record is the baptism or burial"] += 1
                else:
                    verdicts["MISCITED"] += 1
                    wrong.append((p["id"], p["name"], f.get("t"), f.get("date"),
                                  (rd - fd).days, raw[-95:].strip()))

    bad, seen = [], set()
    def flag(kind, pid, who, detail):
        k = (kind, pid, who)
        if k not in seen:
            seen.add(k); bad.append((kind, pid, who, detail))

    for p in people:
        b, d = year(p.get("b")), year(p.get("d"))
        if b and d and d < b:
            flag("death before birth", p["id"], p["name"], f"{p.get('b')} / {p.get('d')}")
        if b and d and d - b > 105:
            flag("age over 105", p["id"], p["name"], f"{p.get('b')} / {p.get('d')}")
        for fam in p.get("fams") or []:
            if fam.get("type") != "spouse":
                continue
            for cid in fam.get("childrenIds") or []:
                c = by.get(cid)
                cb = year((c or {}).get("b"))
                if not c or not cb:
                    continue
                who = f"{p['name']} -> {c['name']}"
                if b and cb - b < 14:
                    flag("parent under 14 at the birth", p["id"], who,
                         f"parent b.{p.get('b')}, child b.{c.get('b')}")
                if b and cb - b > 60:
                    flag("parent over 60 at the birth", p["id"], who,
                         f"parent b.{p.get('b')}, child b.{c.get('b')}")
                if d and cb > d and p.get("g") == "F":
                    flag("MOTHER DEAD BEFORE THE CHILD WAS BORN", p["id"], who,
                         f"mother d.{p.get('d')}, child b.{c.get('b')}")
                if d and cb > d + 1 and p.get("g") == "M":
                    flag("father dead over a year before the birth", p["id"], who,
                         f"father d.{p.get('d')}, child b.{c.get('b')}")

    print(f"audit-tree: {len(people)} people, {sum(cites.values())} cited facts")
    for h, n in cites.most_common():
        print(f"    {n:4d}  {h}")
    print("\n  FamilySearch citations, checked against their own record date:")
    for k, n in verdicts.most_common():
        print(f"    {n:4d}  {k}")
    for w in wrong:
        print(f"      MISCITED  {w[0]} {w[1][:34]} | {w[2]} \"{w[3]}\" | {w[4]:+d} days")
        print(f"                {w[5]}")
    print(f"\n  Arolsen citations: {len(arolsen)} — bare URLs, nothing in them to check against.")
    for a in arolsen:
        print(f"      {a[0]} {a[1][:34]} | {a[2]} {a[3]}")
    print(f"\n  Internal impossibilities: {len(bad)}")
    for k, pid, who, detail in sorted(bad):
        print(f"      [{k}] {pid} {who[:58]} | {detail}")
    return 1 if (wrong or bad) else 0


if __name__ == "__main__":
    sys.exit(main())
