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


AUTO = "https://content.landesarchiv-berlin.de/labsa/show/autocomplete.php?b=1&q=%s"


def offices(timeout=60):
    """Every registry office LABSA knows -- 142 of them, newline separated.

    The search itself matches the office name EXACTLY (a bare "Standesamt",
    "Standesamt C" or "Standesamt Sch" all return nothing), so this list is
    the only way to enumerate the holdings. The endpoint is the jQuery
    autocomplete behind the form's own text box, with matchContains, so any
    substring every name shares will do.

    THE NAMES COME BACK ALREADY DOUBLE-ENCODED -- "Standesamt SchAxc3Axb6neberg"
    rather than Schoeneberg with a real umlaut -- which is precisely the form
    the search expects. Decode the response as UTF-8 and pass the strings
    straight back to volumes(); do NOT repair the mojibake first.
    """
    url = AUTO % urllib.parse.quote("Standesamt")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")
    return [l.strip() for l in raw.splitlines() if l.strip()]


def office_mojibake(name):
    """'Standesamt Schoeneberg' with real umlauts -> the double-encoded form."""
    return name.encode("utf-8").decode("latin-1")


def office_repair(name):
    """The inverse: the double-encoded form -> the real name with umlauts.

    *** YOU NEED THIS, AND LEAVING IT OUT COSTS YOU EVERY OFFICE WITH AN UMLAUT. ***
    offices() hands back DOUBLE-ENCODED names and volumes() needs them that way,
    but the RESULT TABLE prints the office correctly encoded. So a loop that
    queries with the autocomplete name and then filters rows on
    `row["office"] == that_name` throws away every row for all 29 offices whose
    name carries an umlaut or an eszett -- Schoeneberg, Neukoelln, Koepenick,
    Weissensee and the rest -- and reports a confident, quiet ZERO for each.
    Schoeneberg has 61 death-index volumes. Compare with office_repair() applied
    to the query name, or compare loosely.
    """
    try:
        return name.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


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
