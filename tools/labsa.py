"""The Landesarchiv Berlin register finder (LABSA), called directly.

WHAT IT IS. https://content.landesarchiv-berlin.de/labsa/show/index.php is a
finding aid for the Berlin registry offices' NAMENSVERZEICHNISSE -- the name
indexes to the birth, marriage and death registers -- served as PDFs. It is
not a name search: `regName` is the REGISTRY OFFICE's name, not a person's.

*** THE DEFECT THAT MATTERS, FOUND 22 SEPTEMBER 2026. ***
The three checkboxes (geburten / heirats / sterbe) DO NOT UNION. Ticking more
than one does not widen the search, it corrupts it, and the corruption is not
even consistent:

    Standesamt Schoeneberg, sterbe alone          -> 61 volumes
    Standesamt Schoeneberg, all three together    ->  0 volumes
    Standesamt Charlottenburg, sterbe alone       ->  7 volumes
    Standesamt Charlottenburg, all three together ->  8 volumes

A zero from the all-three form is therefore worth nothing, and a non-zero from
it is worth no more. ALWAYS QUERY ONE RECORD TYPE PER REQUEST; this module
will not let you do otherwise.

The office name must be exact and carry the "Standesamt " prefix -- bare
"Charlottenburg" returns nothing. Offices with umlauts are DOUBLE-ENCODED by
the far end, so send "Standesamt SchAxc3Axb6neberg" style mojibake, i.e. the
UTF-8 bytes reinterpreted as latin-1: use office_mojibake() below.
"""
import urllib.request, urllib.parse, re, html as H

URL = "https://content.landesarchiv-berlin.de/labsa/show/index.php"
KINDS = ("geburten", "heirats", "sterbe")
PDF = "https://content.landesarchiv-berlin.de/labsa/pdf/%s.pdf"


def office_mojibake(name):
    """'Standesamt Schoeneberg' with real umlauts -> the double-encoded form."""
    return name.encode("utf-8").decode("latin-1")


def volumes(office, kind, timeout=90):
    """Every index volume of ONE record type for ONE office.

    Returns a list of dicts: bestand, nr, office, title, date, size, pdf, url.
    Rows for other offices (the match is a prefix, so 'Charlottenburg' also
    catches 'Charlottenburg I') are returned too -- filter on ['office'].
    """
    if kind not in KINDS:
        raise ValueError("kind must be one of %s" % (KINDS,))
    data = urllib.parse.urlencode({"regName": office, kind: kind}).encode()
    req = urllib.request.Request(
        URL, data=data,
        headers={"User-Agent": "Mozilla/5.0",
                 "Content-Type": "application/x-www-form-urlencoded"})
    html = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [H.unescape(re.sub(r"<[^>]+>", " ", c)).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        pdf = re.search(r"\.\./pdf/(P_Rep_\d+_\d+)\.pdf", row)
        if len(cells) < 6 or not pdf or "Standesamt" not in cells[2]:
            continue
        out.append({"bestand": cells[0], "nr": cells[1], "office": cells[2],
                    "title": cells[3], "date": cells[5],
                    "size": cells[8] if len(cells) > 8 else "",
                    "pdf": pdf.group(1), "url": PDF % pdf.group(1)})
    return out


def inventory(office, timeout=90):
    """All three record types for one office, queried SEPARATELY."""
    return {k: volumes(office, k, timeout) for k in KINDS}
