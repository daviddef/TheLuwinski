"""The archive's own decisions about WHICH RECORDS ARE WHICH PEOPLE. Not the living test.

The living test is the estate's, one definition in the kit (kit/tools/living_rule.py, ruling of
16 October 2026), and nothing here decides who is living. This file used to be tools/livingtest.py,
which carried this archive's own copy of that test; the copy is gone and what is left is the two
facts the kit cannot know:

  NAMED_BARE   Derrick, the subject of the archive. The kit's rule would call him living (he is
               under 80 with no death recorded) and he is, but this archive has always named him
               with his parents and nothing else, not even a town (standard, point 9). The ruling
               keeps that exception.
  DUPLICATES   records the source holds twice for one person, collapsed to the copy that carries
               both dates and parents. Keyed redundant -> canonical. Each pair shares an identical
               birth AND death date.

and the helper that finds the kit's rule, so that the generator, the guard writer and the gate all
import the same file from the same place.
"""
import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
KIT_TOOLS = ROOT / "site" / "node_modules" / "@daviddef" / "archive-kit" / "kit" / "tools"

NAMED_BARE = {9500003}          # Derrick

DUPLICATES = {
    9500151: 9500026,   # Georg Leibholz, dateless-parent copy
    9500150: 9500154,   # Leopold Leibke, dateless copy
    9500145: 9500104,   # Gertrud Leibke: the copy attached to Georg; the 1939 census puts her
                        # at Oskar's address, so the Oskar copy (9500104) is canonical.
    9500148: 9500152,   # Julius Leibke
    9500149: 9500153,   # Henriette Katz
}


def load_living_rule():
    """Import the kit's living_rule from the installed, pinned kit. Refuses if it is not there:
    a stale install is the one way to end up with an older definition of who is living."""
    if not (KIT_TOOLS / "living_rule.py").exists():
        sys.exit(f"REFUSED: {KIT_TOOLS / 'living_rule.py'} is not installed. Run `npm install` in site/ "
                 "against the pinned kit; this archive keeps no living test of its own.")
    if str(KIT_TOOLS) not in sys.path:
        sys.path.insert(0, str(KIT_TOOLS))
    import living_rule
    return living_rule


# ---------------------------------------------------------------------------------------------
# WHO IS LIVING, WHO IS HELD OUT: the generator's side. (tools/check-living.py computes the same
# thing again from the harvest by its own code, so that the gate is not the generator agreeing with
# itself.) Everything below only EXTRACTS the three inputs the kit's rule takes - a birth year, whether
# a death or burial is recorded, and the citations - and hands them to living_rule.
# ---------------------------------------------------------------------------------------------
import re

# People whose privacy was promised, by id, never by name. None in this archive. D'Arcy has one.
HELD_IDS = ()

_YEAR = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")


def year(s):
    m = _YEAR.search(s or "")
    return int(m.group(1)) if m else None


def _own_death_events(p):
    """The person's OWN Death or Burial events: not a fact whose label ends in a colon or starts «Death of»
    («Death of husband:», «Death of son:»), which is another person's death filed on this person's page."""
    out = []
    for f in p.get("facts", []):
        t = (f.get("t") or "").strip()
        if f.get("ty") in ("DEAT", "BURI") and not t.endswith(":") and not t.startswith("Death of"):
            out.append(f)
    return out


def recorded_dead(p):
    """A death or burial RECORD: a death date, or a Death or Burial event of the person's OWN that carries a date
    or a place. This is the only thing the kit's living rule takes as a death for someone born 1946 or later
    (kit/docs/living.md, 25 October 2026)."""
    if (p.get("d") or "").strip():
        return True
    return any((f.get("date") or "").strip() or (f.get("place") or "").strip() for f in _own_death_events(p))


def undated_dead(p):
    """Only a FLAG that the person is dead: the tree marks them deceased (`alive` false), or carries a Death or Burial
    event with no date and no place (GEDCOM `DEAT Y`), and nothing more. The kit treats that as a belief, not
    a record: a person born 1946 or later stays living, an undated or older person is dead (undated_dead=True)."""
    if recorded_dead(p):
        return False
    return (not p.get("alive")) or bool(_own_death_events(p))


def citations(p):
    """What the record cites for the person's OWN facts: the comment and the alternate comment of each
    (a fact filed under another person's death or marriage, label ending in a colon, is theirs). The
    harvest is a private family tree and holds no source records as such; a comment that names a public
    record collection (FamilySearch, Arolsen) is the one place a public source shows."""
    out = []
    for f in p.get("facts", []):
        t = (f.get("t") or "").strip()
        if t.endswith(":") or t.startswith(("Death of", "Birth of", "Marriage of")):
            continue
        out += [x for x in (f.get("c"), f.get("ac")) if x]
    return out


_PARENT = re.compile(r"father|mother|parent", re.I)
_CHILD = re.compile(r"\b(son|daughter|child)\b", re.I)


def parent_ids(people, pid):
    """The people who are this person's parents, read from BOTH directions: the person's own
    «His father» edges and any other record's «Her son» edge that points at them."""
    out = set()
    for q in people:
        if q["id"] == pid:
            out |= {r["id"] for r in q["rel"] if _PARENT.search(r["rel"])}
        else:
            out |= {q["id"] for r in q["rel"] if r["id"] == pid and _CHILD.search(r["rel"])}
    return out


def child_index(people):
    """{parent id: {child ids}}, read from BOTH directions (the parent's own «His son» edges and any other record's
    «Her father» edge), with a redundant duplicate record folded into the copy it collapses to, so that a child
    attached to either copy counts for the one person."""
    canon = lambda i: DUPLICATES.get(i, i)
    out = {}
    for q in people:
        qid = canon(q["id"])
        for r in q["rel"]:
            rid = canon(r["id"])
            if rid == qid:
                continue
            if _CHILD.search(r["rel"]):
                out.setdefault(qid, set()).add(rid)
            elif _PARENT.search(r["rel"]):
                out.setdefault(rid, set()).add(qid)
    return out


def youngest_child_year(people, pid, index=None):
    """The latest known birth YEAR among this person's children, or None. A child whose birth year is not
    known does not count, and neither does a child who is not in the harvest. The kit's rule
    (living_rule.is_living, youngest_child_year, 17 October 2026) calls an UNDATED parent living when this
    is 60 years ago or less, because a parent is about twenty years older than a child."""
    index = index if index is not None else child_index(people)
    by = {p["id"]: p for p in people}
    ys = [year(by[c].get("b")) for c in index.get(DUPLICATES.get(pid, pid), ()) if c in by]
    ys = [y for y in ys if y]
    return max(ys) if ys else None


def classify(people, lr=None, today=None):
    """{id: 'living' | 'dead' | 'held_out' | 'duplicate' | 'bare'} for every harvest record.

    'bare' is Derrick: living by the rule, kept as he has always been. 'dead' means NOT LIVING:
    older than 80, or a recorded death, or no birth year to show them younger. 'held_out' is
    published nowhere (see living_rule.is_held_out). An UNDATED person with no recorded death and no public
    source is living when their youngest child with a known birth year was born 60 years ago or less
    (youngest_child_year above); the same child year is given to is_held_out, so that such an adult parent is
    not held out as a possible minor."""
    lr = lr or load_living_rule()
    by = {p["id"]: p for p in people}
    index = child_index(people)

    def living(p):
        return lr.is_living(year(p.get("b")), recorded_dead(p), citations(p), today,
                            youngest_child_year(people, p["id"], index), undated_dead=undated_dead(p))

    out = {}
    for p in people:
        pid = p["id"]
        if pid in DUPLICATES:
            out[pid] = "duplicate"
        elif pid in NAMED_BARE:
            out[pid] = "bare"
        else:
            plive = any(living(by[x]) for x in parent_ids(people, pid) if x in by)
            if lr.is_held_out(pid, year(p.get("b")), recorded_dead(p), citations(p), plive, HELD_IDS, today,
                              youngest_child_year(people, pid, index), undated_dead=undated_dead(p)):
                out[pid] = "held_out"
            elif living(p):
                out[pid] = "living"
            else:
                out[pid] = "dead"
    return out
