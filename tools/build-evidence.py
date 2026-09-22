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
 "register-date-audit.tsv":    ([], "Every date in the register audited — a bound is not a date", "The register itself, all 149 people and 215 distinct date strings, 22 September 2026", "ref"),
 "negatives-classified.tsv":   ([], "Every published negative classified, and three re-run", "The archive's own /negatives/ page, all 33 rows read one at a time 22 September 2026; re-runs at FreeBMD, probatesearch.service.gov.uk and gazettes.africa", "ref"),
 "gedenkbuch-leibholz-findings.tsv": ([], "The fifty opened — deportation, death, and two more under LAIBHOLZ", "Bundesarchiv, Gedenkbuch — Opfer der Verfolgung der Juden unter der nationalsozialistischen Gewaltherrschaft", "ref"),
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
 "yadvashem-leibholz.tsv":       (["who"], "Yad Vashem, Central Database of Shoah Victims' Names", "collections.yadvashem.org — records 13520936 and 13449776, item IDs 11572198, 4113817, 11572206", "person"),
 "arolsen-leibholz-luwinski.tsv": (["who"], "The Arolsen Archives index", "collections.arolsen-archives.org — index entries only; the documents need a consent declaration that was not ticked", "person"),
 "berlin-adressbuch.tsv":        ([], "The Berliner Adressbücher", "Zentral- und Landesbibliothek Berlin, digital.zlb.de — annual volumes 1799-1970, full-text", "ref"),
 "berlin-postwar-luwinski.tsv": ([], "Post-war West Berlin \u2014 the Luwinskis, Auguste under her last surname, and who was still called Leibholz", "Zentral- und Landesbibliothek Berlin, digital.zlb.de \u2014 Namenteil series 34117222 (1949-1970) and telephone books 15849358 (1969-1980), searched through the Goobi Solr API and the per-page OCR endpoint, 20 September 2026", "ref"),
 "berlin-adressbuch-names.tsv": ([], "The Berliner Adressbuch, alphabetical name section", "Zentral- und Landesbibliothek Berlin, digital.zlb.de — Teil I (Einwohner / Haushaltungsvorstände), annual volumes 1920-1943, read 20 September 2026", "ref"),
 "mappingthelives-leibholz.tsv": (["who"], "The Berlin directory against the 1939 census, household by household", "Mapping the Lives (Tracing the Past e.V.), surname LEIBHOLZ, 114 persons, matched to the Berliner Adressbuch by street and house number, 20 September 2026", "person"),
 "ermland-sauerbaum.tsv":       ([], "Sauerbaum, Kreis Rössel — the parish, the films, and what is not online", "FamilySearch catalogue koha:15497 (Katholische Kirche Groß Bössau, Kr. Rössel, Kirchenbuch 1690-1897) with its nine film notes; film 102682510 image 591; record index and full-text search, 20 September 2026", "ref"),
 "westpark-films.tsv":          ([], "The Johannesburg cemetery films, mapped", "FamilySearch catalogue olib:4148464, South Africa, Johannesburg City Cemetery records, 210 films; film 107638608 read at images 151, 187 and 401, 20 September 2026", "ref"),
 "luwinski-emigration-1965.tsv": ([], "A branch of the family flew from Berlin to Australia in 1965", "Arolsen Archives DocID 81709354 — ICEM nominal roll, 3.1.3 Emigrations, BGO 65/135, stamped September 1965; read with consent 20 September 2026", "ref"),
 "alfred-luwinski-sachsenhausen.tsv": ([], "Alfred Luwinski born 9 September 1917 — who he actually was", "Arolsen Archives DocID 130648701 — Amt für die Erfassung der Kriegsopfer (Berlin), reference 23120001 275; read with consent 20 September 2026", "ref"),
 "tree-audit.tsv":              ([], "Every citation in the family tree, checked against what it cites", "data/myheritage-tree9.json audited 20 September 2026 against Arolsen DocID 130648701 and the FamilySearch citation strings", "ref"),
 "findmypast-newspapers.tsv":   ([], "The newspaper half of the subscription, and why the surname defeats it", "Findmypast, search-newspapers results, four queries run 20 September 2026", "ref"),
 "jacob-leibholz-deportation.tsv": ([], "Jacob Leibholz, 26 February 1943 \u2014 the line on the list", "Arolsen Archives DocID 127212355 (Wave 44, 30th Osttransport to Auschwitz, reference 15510037, page 153 line 1039) and DocID 11243224 (AJDC/ITS card, reference 01020102 047); read with consent 20 September 2026", "ref"),
 "leibholz-shanghai.tsv":       ([], "A Berlin Leibholz family got out to Shanghai", "Arolsen Archives DocID 131698324 (Central Location Index card L 337909, reference 71410001) and DocID 78827389 (H.I.A.S. lists of Jewish nationals who died and were buried in Shanghai 1939-1948, reference 8808060); Yad Vashem submitter search; Mapping the Lives emigration field; 20 September 2026", "ref"),
 "dewitt-confirmed.tsv":        ([], "Ivone's first husband \u2014 the death date confirmed, and a second marriage", "FamilySearch \u2014 South Africa, Civil Death Registration 1953-1967 (ark 1:1:DD9Y-PLT2); South Africa, Civil Marriage Records 1801-1974 (ark 1:1:6ZHR-NVYN); searched 20 September 2026", "ref"),
 "oskar-leibholz-theresienstadt.tsv": ([], "Oskar Leibholz, from Schubin to a transport number leaving Theresienstadt", "Arolsen Archives DocIDs 127212723, 11243228, 11214364 and 5055941 \u2014 Gestapo transport list 15510042, AJDC/ITS card 01020102 047, Berlin registration card 10000375 24, Theresienstadt central card file 11422001 183; and DocID 12663551, the Kultusvereinigung Berlin Z\u00e4hlkarte for Gertrud, 01020401 034; read with consent 20 September 2026", "ref"),
 "leibholz-registration-card.tsv": ([], "DocID 11214358 read \u2014 the Berlin registration card, and the guess it withdraws", "Arolsen Archives DocID 11214358, both images \u2014 1.2.1.5 Berlin: Registration Cards from Jewish Residents, reference 10000375 24; read with consent 20 September 2026", "ref"),
 "arolsen-tracing-files.tsv":   ([], "The tracing files — what the consent opens and what it does not", "Arolsen Archives: T/D 52.971 (metadata only, restricted) and 6.3.1.1 reference 06030101 121.145, the 1946 Jewish Agency search for Willi Leibholz; read 20 September 2026", "ref"),
 "surname-lines.tsv":          ([], "The lines of the name \u2014 every family of Leibholz and Luwinski, kept apart", "Drawn from the archive's own files, 20 September 2026 \u2014 a structure, not new evidence", "ref"),
 "naa-recordsearch.tsv":       ([], "The National Archives of Australia has the family — it just has not scanned them", "recordsearch.naa.gov.au, item-level index, eight surname wildcards, searched 20 September 2026", "ref"),
 "gazettes-africa-sweep.tsv":  ([], "Gazettes.Africa swept across every spelling — and a find this archive already had", "gazettes.africa, thirteen queries, 20 September 2026 — written up wrong, caught against this site's own Kurt page, rewritten", "ref"),
 "australia-indexes.tsv":     ([], "The other Australian instruments — what each one can and cannot hold", "Queensland BDM historical index, the Ryerson Index and Trove, all tried 20 September 2026", "ref"),
 "entschaedigung-berlin.tsv":  ([], "The compensation files moved four months ago, and nobody has asked for them", "Landesarchiv Berlin and LABO, their own pages, read 20 September 2026", "ref"),
 "berlin-namensverzeichnisse.tsv": ([], "The Berlin registry offices put their name indexes online, and one of them holds Kurt's birth number", "Landesarchiv Berlin Standesamtsabfrage, 142 offices swept 20 September 2026", "ref"),
 "chodowieckistrasse-1913.tsv": ([], "A Luwinski and a Leibholz in adjacent houses in 1913", "Berliner Adressbuch 1913 Teil III p.139, ZLB digital copy, read at the image 20 September 2026", "ref"),
 "kurt-birth-entry.tsv":      ([], "Kurt's birth entry number, found — Standesamt Berlin VIII, 1912, Nr. 963", "Landesarchiv Berlin P Rep. 523 Nr. 1395, read at the image 20 September 2026", "ref"),
 "leibholz-luwinski-marriage.tsv": ([], "The marriage entry, found — Schöneberg II, 1924, Nr. 6, and the index records the Mischehe", "Landesarchiv Berlin P Rep. 161 Nr. 271 p.221, read at the image 20 September 2026", "ref"),
 "leipholz-sweep.tsv":        ([], "The eighth spelling, and the directory printed it itself — LEIPHOLZ", "Berliner Adressbuch cross-reference 1913 to 1940, swept 20 September 2026", "ref"),
 "gedenkbuch-fifty.tsv":      ([], "Fifty Leibholz in the Gedenkbuch, and only three of them were born at Schubin", "Bundesarchiv Gedenkbuch, all five result pages read 20 September 2026", "ref"),
 "weinstrasse-pages-of-testimony.tsv": ([], "The Weinstraße household was at Yad Vashem all along, under the eighth spelling", "Yad Vashem Pages of Testimony 5369884 and 1122806, read 21 September 2026", "ref"),
 "atlas-pin-audit.tsv":        ([], "Every atlas pin checked against a gazetteer", "OpenStreetMap Nominatim, 16 pins queried 21 September 2026; haversine distances", "ref"),
 "kreuzberg-ocr-control.tsv":  ([], "An OCR label is not a searchable index — measured", "Landesarchiv Berlin LABSA, P Rep. 510 Nr. 743 and P Rep. 163 Nr. 602/0628, 22 September 2026", "ref"),
 "melbourne-leibholz-death.tsv": ([], "Joachim Peter Leibholz died at Toorak in 1971, and the index names his parents", "Victorian BDM historical index reg. 26252/1971, searched 21 September 2026", "ref"),
 "spandau-1982-leibholz-schoenfeld.tsv": ([], "A Jewish woman born Leibholz, married Schönfeld, who survived and died in 1982", "Standesamt Spandau, Sterberegister 1982 Nr. 1486, read through pdf.js 21 September 2026 — forename withheld, see the file", "ref"),
 "kreuzberg-reinickendorf-deaths.tsv": ([], "Eleven more death volumes, no hits, and two ways the method almost lied", "Landesarchiv Berlin P Rep. 510 and P Rep. 130, read through pdf.js 21 September 2026", "ref"),
 "leipholz-postwar-berlin.tsv":  ([], "The eighth spelling in post-war Berlin — seven volumes the sweep had never seen", "ZLB Berliner Adressbuch Namenteil 1957-1970, Solr sweep and per-page OCR 21 September 2026", "ref"),
 "schoeneberg-progress.tsv":     ([], "The resume pointer for the Schöneberg death-index read", "Maintained by hand as each year closes — the control that makes a long read survive short sessions", "ref"),
 "schoeneberg-1939-guenther-leibholz.tsv": ([], "Günther Leibholz, Schöneberg 1939 Nr. 780 — the first hit in eleven years of reading", "Landesarchiv Berlin P Rep. 163 Nr. 608 p.86, read at the image at scale 6, 21 September 2026", "ref"),
 "schoeneberg-1938-1968-instrument.tsv": ([], "The other thirty-one years cannot be read the way the last twenty-five were", "Landesarchiv Berlin P Rep. 163, probed 21 September 2026 — no text layer before 1969, and no alphabet inside a letter", "ref"),
 "schoeneberg-death-indexes.tsv": ([], "The Schöneberg death indexes, and the eighth spelling in one of them", "Landesarchiv Berlin P Rep. 163, sixty-one volumes listed and eight read through pdf.js 21 September 2026", "ref"),
 "twenty-alone.tsv":          ([], "Twenty things this archive can do without David", "Written 21 September 2026 at his request — a plan, not a finding", "ref"),
 "twenty-next.tsv":            ([], "Twenty ways to open the Luwinskis abroad", "Written 20 September 2026 at David's request \u2014 a prioritised plan, not a finding", "ref"),
 "szubin-civil-registers.tsv":  ([], "The Szubin civil registers of 1874 \u2014 found, filmed and online", "szukajwarchiwach.gov.pl (AP Bydgoszcz fonds 6/1792/0, 6/1795/0, 6/1796/0) and FamilySearch catalogue koha:402152 and koha:402191, digital films 007998644 and 008016003; 20 September 2026", "ref"),
 "schmul-and-thimm.tsv":        ([], "The two great-grandmothers' surnames — what can be reached and what cannot", "FamilySearch collection metadata and Posen collection 4116415 (33 exact SCHMUL records read); Geneteka control run and failed; 20 September 2026", "ref"),
 "castle-giddings-1862.tsv":     ([], "Martha Giddings, George Castle and a marriage of one year", "GRO indexes via Findmypast — marriage Q3 1862 Hitchin; birth Q4 1862 Hitchin; death Q3 1863 Hitchin 3A/188", "ref"),
 "wear-bloom-1842.tsv":         ([], "The William Weare x Sarah Bloom marriage, Stepney 1842", "GRO marriage index via Findmypast — Stepney Q3 1842, volume 2 page 430; Marriage Finder names four grooms on the page", "ref"),
 "tna-discovery.tsv":            ([], "The National Archives Discovery catalogue", "discovery.nationalarchives.gov.uk — citations verified and references found, 17 September 2026", "ref"),
 "castle-frederick-soldier.tsv":  ([], "Frederick James Castle, soldier — 1901 to the 1920s", "1901 and 1911 censuses; TNA WO 329/1120 and WO 372/4", "ref"),
 "castle-1911-meeanee-barracks.tsv": ([], "Frederick Castle in barracks, 1911", "1911 census RG14 piece 10304 schedule 9999, Meeanee Barracks, Colchester — read from the original image", "ref"),
 "castle-nine-children.tsv":     (["name"], "The nine children of George William Castle and Caroline Wallis", "1911 census fertility question RG14/7572 sch 173; GRO birth and death indexes; 1901 census RG13/1298 f.49 p.26 sch 192", "person"),
 "castle-baptisms-weston.tsv":   ([], "The Hertfordshire baptism register, worked to its coverage bound", "Findmypast, Hertfordshire Baptisms — 823 Castle rows sorted by mother's name; Baldock coverage ends 1879", "ref"),
 "gazette-wear-sweep.tsv":       ([], "The gazette sweep for the Wears and for Phyllis", "gazettes.africa, 54,313 South African issues", "ref"),
 "familysearch-south-africa.tsv": ([], "What FamilySearch actually holds for South Africa", "FamilySearch collection metadata, all 3,502 collections enumerated 17 September 2026; index spans measured by exact-year counts", "ref"),
 "familysearch-sa-family.tsv":   (["who"], "This family in FamilySearch's South African collections", "FamilySearch, South Africa: Civil Marriage Records 1801-1974, Church of the Province of South Africa Parish Registers 1801-2004, Johannesburg Cemetery Records 1840-2019 — searched 17 September 2026", "person"),
}

NOT_A_PERSON = re.compile(r"^(married|marriage|#|-|—|\s*)$", re.I)

# Words that occur in a sentence and not inside a person's name. Used only to
# tell a NAME from a ROW LABEL in the narrative files; see person_name below.
_PROSE = re.compile(
    r"\b(who|this|that|and|the|with|from|which|because|not|are|was|were|her|his|"
    r"their|its|has|have|been|why|how|when|where|all|every|same|own|named|read|"
    r"found|corrected|archive|street|strasse|straße)\b", re.I)


def person_name(raw):
    """The person named in a 'who' cell, or None if the cell is a row label.

    THE FAULT THIS FIXES. The narrative files write their key column as
    "NAME — what the row is about", and some rows are pure commentary with no
    name in them at all. Until 21 September the whole cell was taken as a
    person, so the archive counted "*** AND A CHILD THIS ARCHIVE DID NOT HAVE
    ***" and "AFRIKANISCHE STRASSE 37 — and a namesake to keep apart" among its
    people. Two costs: the published count overstated, and check-evidence's
    promise degraded from "this PERSON reaches a reader" to "this STRING is
    somewhere on the site" — which it trivially was, because the sentence is
    printed on the page, so those rows passed for the wrong reason.

    So: cut at the em dash to recover the name, then require what is left to
    look like one. Nothing is dropped silently — build-evidence prints every
    rejected cell, because a filter you cannot see is the fault this archive
    keeps having.
    """
    v = raw.split(" — ")[0].split(" -- ")[0]
    v = v.split(" (")[0]                      # "IVONE LUWENSKI (formerly de Witt...)"
    if "," in v:                              # "ARTHUR, THE SANITÄTSRAT" -> "ARTHUR",
        head, tail = v.split(",", 1)          # but NOT "Leibholz, Samuel" -> "Leibholz"
        if _PROSE.search(tail):
            v = head
    v = v.strip().rstrip(",;:")
    if not v or NOT_A_PERSON.match(v):
        return None
    if v[0] in "*(\"'" or v[0].islower():
        return None
    if any(ch.isdigit() for ch in v):
        return None
    if len(v.split()) > 6:
        return None
    if _PROSE.search(v):
        return None
    return v

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
    rejected = []
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
                if not raw:
                    continue
                if keys == ["first", "last"]:
                    continue
                nm = person_name(raw)
                if nm is None:
                    rejected.append((fname, raw))
                    continue
                named.append((nm, r))
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
    if rejected:
        print(f"  {len(rejected)} key cell(s) read as a ROW LABEL rather than a person and NOT "
              f"counted — if a real name is in this list, the data or the rule is wrong:")
        for fn, raw in rejected:
            print(f"      {fn}: {raw[:100]}")
    if strict_missing:
        print("  declared but absent:", ", ".join(strict_missing))
    return 0

if __name__ == "__main__":
    sys.exit(main())
