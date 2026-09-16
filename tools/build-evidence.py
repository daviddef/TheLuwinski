#!/usr/bin/env python3
"""Attach the read records in data/ to the people they are about.

WHY THIS EXISTS. Until 17 September 2026 this archive had twenty-one evidence
files in data/ and NOT ONE BUILD SCRIPT READ ANY OF THEM. build-register.py
read the MyHeritage export and corrections.json and nothing else. Everything a
census or a register actually said reached the site only because a human
retyped it into narrative prose, and nothing anywhere would have noticed if a
file had been added and never surfaced, or if the prose and the file disagreed.

THE MANIFEST IS DELIBERATELY EXPLICIT. Every file is declared here with the
column that names a person. A file in data/ that is not declared is an ERROR,
not a skip — that is the whole point. Silence is what went wrong.

THIS DOES NOT REWRITE THE TREE. The register and the charts draw the export as
given; corrections are shown as was/now and nowhere else. This adds a second,
parallel statement — "here is a record that was read about this person, and
here is what it says" — and changes no date anybody inherited.
"""
import csv, json, os, re, sys, pathlib, unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "site" / "src" / "data" / "evidence.json"
REG = ROOT / "site" / "src" / "data" / "register.json"

# file -> (key columns, title, source citation, kind)
# "kind": person = rows are people; ref = rows are references, not people.
MANIFEST = {
 "leibholz-gedenkbuch.tsv":      (["name"], "The Bundesarchiv Gedenkbuch", "Bundesarchiv, Gedenkbuch — Opfer der Verfolgung der Juden unter der nationalsozialistischen Gewaltherrschaft", "person"),
 "wear-1851-bermondsey.tsv":     (["first","last"], "1851 census, Salisbury Street, Bermondsey", "HO107 piece 1560 folio 212", "person"),
 "wear-1871-bermondsey.tsv":     (["first","last"], "1871 census, Jamaica Road, Bermondsey", "RG10 piece 641 folio 40 schedule 40", "person"),
 "wear-brothers-1881.tsv":       (["first","last"], "1881 census, two Bermondsey households", "RG11 piece 574 folio 56 page 8 sch 501; RG11 piece 567 folio 128 page 60 sch 1238", "person"),
 "wear-1891-watford.tsv":        (["first","last"], "1891 census, Watford", "RG12, Watford", "person"),
 "hull-1901-st-albans.tsv":      (["first","last"], "1901 census, 22 Mount Pleasant, St Albans", "RG13 piece 1312", "person"),
 "wear-1911-letchworth.tsv":     (["first","last"], "1911 census, Letchworth", "RG14, Letchworth", "person"),
 "wear-1939-register.tsv":       (["first","last"], "1939 Register, 72 Pix Road, Letchworth", "TNA R39", "person"),
 "shenton-1939-pix-road.tsv":    (["first","last"], "1939 Register, 63 Pix Road, Letchworth", "TNA R39/1620/1620G/011/28, schedule 305", "person"),
 "shenton-line-closed.tsv":      (["who"], "The 63 Pix Road household, traced end to end", "GRO birth, marriage and death indexes; 1939 Register", "person"),
 "hawkins-1871-aldenham.tsv":    (["first","last"], "1871 census, The Red Lion Cottages, Aldenham", "RG10 piece 1365", "person"),
 "giddins-norton-end.tsv":       (["first","last"], "1861 and 1871 censuses, Norton End, Baldock", "RG9/816 f.69; RG10/1365 f.27", "person"),
 "bloom-1861-yarmouth.tsv":      (["first","last"], "1861 census, 80 Howard Street, Great Yarmouth", "RG9, Great Yarmouth", "person"),
 "castle-1911-1921.tsv":         (["name"], "1911 and 1921 censuses, Baldock and Letchworth", "RG14/7572 sch 173; RG15/07079 sch 125", "person"),
 "castle-from-match-tree.tsv":   (["person"], "A match holder's Ancestry tree", "Brown Family Tree, tree 113587011, read as guest 16 September 2026 — A USER TREE, NOT A RECORD SET", "person"),
 "wear-emigration-bt27.tsv":     (["first","last"], "BT 27 outbound passenger lists", "TNA BT 27", "person"),
 "wear-pow-1943-45.tsv":         ([], "War Office prisoner-of-war lists", "TNA WO 392/15 and WO 392/21", "ref"),
 "caroline-james-1920-1957.tsv": ([], "Caroline Castle, later James, 1920 to 1957", "GRO indexes; 1939 Register RG101/1598B/017/25", "ref"),
 "litigation.tsv":               (["plaintiff","defendant"], "Transvaal court files", "National Archives of South Africa, WLD and TPD series", "person"),
 "naairs-figueiredo.tsv":        ([], "The NAAIRS index under FIGUEIREDO", "National Archives of South Africa", "ref"),
 "tna-discovery.tsv":            ([], "The National Archives Discovery catalogue", "discovery.nationalarchives.gov.uk — citations verified and references found, 17 September 2026", "ref"),
 "castle-frederick-soldier.tsv":  ([], "Frederick James Castle, soldier — 1901 to the 1920s", "1901 and 1911 censuses; TNA WO 329/1120 and WO 372/4", "ref"),
 "castle-1911-meeanee-barracks.tsv": ([], "Frederick Castle in barracks, 1911", "1911 census RG14 piece 10304 schedule 9999, Meeanee Barracks, Colchester — read from the original image", "ref"),
 "castle-nine-children.tsv":     (["name"], "The nine children of George William Castle and Caroline Wallis", "1911 census fertility question RG14/7572 sch 173; GRO birth and death indexes; 1901 census RG13/1298 f.49 p.26 sch 192", "person"),
 "castle-baptisms-weston.tsv":   ([], "The Hertfordshire baptism register, worked to its coverage bound", "Findmypast, Hertfordshire Baptisms — 823 Castle rows sorted by mother's name; Baldock coverage ends 1879", "ref"),
 "gazette-wear-sweep.tsv":       ([], "The gazette sweep for the Wears and for Phyllis", "gazettes.africa, 54,313 South African issues", "ref"),
}

NOT_A_PERSON = re.compile(r"^(married|marriage|#|-|—|\s*)$", re.I)

# Columns that must never be published, per file. The free-text notes on the
# match-derived file name the LIVING match holder who supplied the tree, and
# living DNA match holders are published as role, country and cM and in no other
# way. check-matches.py caught this the first time this builder ran, which is the
# second guard doing its job on the first guard's output.
REDACT = {"castle-from-match-tree.tsv": {"note"}}

def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")

def rows(path):
    with open(path, encoding="utf-8") as fh:
        lines = [l for l in fh if not l.startswith("#")]
    return list(csv.DictReader(lines, delimiter="\t"))

def main():
    strict_missing = []
    present = {p.name for p in DATA.glob("*.tsv")}
    undeclared = sorted(present - set(MANIFEST))
    if undeclared:
        print("REFUSED: evidence files in data/ that build-evidence.py does not declare:")
        for u in undeclared:
            print("   ", u, "— add it to MANIFEST with its key column, or it reaches nobody")
        return 1
    missing = sorted(set(MANIFEST) - present)

    people = {}
    files_out = []
    for fname, (keys, title, source, kind) in sorted(MANIFEST.items()):
        path = DATA / fname
        if not path.exists():
            strict_missing.append(fname); continue
        rs = rows(path)
        named = []
        for r in rs:
            if not keys:
                continue
            for k in keys:
                raw = (r.get(k) or "").strip()
                if not raw or NOT_A_PERSON.match(raw):
                    continue
                if keys == ["first", "last"]:
                    continue
                named.append((raw, r))
            if keys == ["first", "last"]:
                nm = ((r.get("first") or "").strip() + " " + (r.get("last") or "").strip()).strip()
                if nm and not NOT_A_PERSON.match(nm):
                    named.append((nm, r))
        for nm, r in named:
            drop = REDACT.get(fname, set())
            detail = " · ".join(f"{k}: {v}" for k, v in r.items()
                                if v and v.strip() and k not in ("first", "last", "name", "who", "person")
                                and k not in drop and len(v) < 220)
            e = people.setdefault(slug(nm), {"name": nm, "slug": slug(nm), "records": []})
            e["records"].append({"file": fname, "title": title, "source": source, "detail": detail[:600]})
        files_out.append({"file": fname, "title": title, "source": source, "kind": kind,
                          "rows": len(rs), "people": len(named)})

    # Cross-link to the register where the name matches.
    #
    # A NAME MATCH IS NOT A PERSON MATCH, and the first version of this function
    # proved it on its own data. The register holds KURT LUWINSKI, died 1995, a
    # surname-index entry, and KURT ISRAEL LUWINSKI, 1912-1968, who is the man
    # this archive is about. Matching "Kurt LUWINSKI" from the court files on a
    # first-plus-last alias, with setdefault picking whoever sorted first, hung
    # three divorce actions on the wrong man. So:
    #
    #   EXACT full-name match, one candidate  -> linked
    #   first-plus-last alias, one candidate  -> linked, and flagged as an alias
    #   more than one candidate               -> NOT LINKED, recorded as ambiguous
    #
    # Refusing to choose is the correct behaviour. An ambiguous name is reported
    # on the page and by the gate so that a human resolves it by hand.
    linked, ambiguous = 0, []
    if REG.exists():
        reg = json.load(open(REG))
        exact, alias = {}, {}
        for rp in reg["people"]:
            exact.setdefault(slug(rp["name"]), []).append(rp)
            parts = rp["name"].replace("(", " ").replace(")", " ").split()
            if len(parts) > 2:
                alias.setdefault(slug(parts[0] + " " + parts[-1]), []).append(rp)
        for sg, e in people.items():
            # The exact and alias candidates are pooled BEFORE deciding. Testing
            # exact first and only falling back to alias is what mislinked Kurt:
            # "Kurt Luwinski" (the surname-index man who died in 1995) matched
            # exactly and won, while "Kurt Israel Luwinski" (1912-1968) was sitting
            # in the alias map and never got a vote. Two people answer to that name
            # and the honest answer is to link neither.
            pool, seen_ids = [], set()
            for c in (exact.get(sg) or []) + (alias.get(sg) or []):
                if c["id"] not in seen_ids:
                    seen_ids.add(c["id"]); pool.append(c)
            cands = pool
            how = "exact" if (exact.get(sg) or []) else "alias"
            if len(cands) == 1:
                e["register_id"] = cands[0]["id"]
                e["register_name"] = cands[0]["name"]
                e["register_match"] = how
                linked += 1
            elif len(cands) > 1:
                e["ambiguous"] = [{"id": c["id"], "name": c["name"],
                                   "born": c.get("born", ""), "died": c.get("died", "")}
                                  for c in cands]
                ambiguous.append(e["name"])

    out = {"files": files_out,
           "people": sorted(people.values(), key=lambda e: e["name"]),
           "ambiguous": sorted(ambiguous),
           "counts": {"ambiguous": len(ambiguous),
                      "files": len(files_out),
                      "person_files": sum(1 for f in files_out if f["kind"] == "person"),
                      "people": len(people),
                      "records": sum(len(e["records"]) for e in people.values()),
                      "linked_to_register": linked}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
    print(f"build-evidence: {len(files_out)} files, {len(people)} people, "
          f"{out['counts']['records']} records, {linked} linked to the register"
          + (f", {len(ambiguous)} NOT linked because the name is ambiguous" if ambiguous else ""))
    for a in ambiguous:
        print("  ambiguous, left unlinked:", a)
    if strict_missing:
        print("  declared but absent:", ", ".join(strict_missing))
    return 0

if __name__ == "__main__":
    sys.exit(main())
