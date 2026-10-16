"""The ONE definition of who counts as a living person in this archive.

Three tools used to carry their own copy of this test (build-register.py, make-guarded.py,
check-living.py), and the copies had already drifted: make-guarded.py named 9500104 in its
duplicates where the other two named 9500145. A gate that disagrees with the generator about
who is living is not a gate. They all import this now.

THE TEST IS UNCHANGED from the one that decided who was omitted before the 16 October 2026
standard, and it is deliberately NOT widened or narrowed by the standard: a person is living
here if the source flags them alive, they are not Derrick, they are not a duplicate record
collapsed into another person, and they were not born in 1920 or earlier (106 or more now,
presumed dead and published with the absence of a death record stated plainly).

Derrick (NAMED_BARE) is flagged alive in the source too. He is the one exception to the
standard: named with his parents and nothing else, not even a town, and left exactly as he was.
"""
import re

NAMED_BARE = {9500003}          # Derrick

# Records the source holds twice for one person, collapsed to the copy that carries both dates
# and parents. Keyed redundant -> canonical. Each pair shares an identical birth AND death date.
DUPLICATES = {
    9500151: 9500026,   # Georg Leibholz, dateless-parent copy
    9500150: 9500154,   # Leopold Leibke, dateless copy (and the only one flagged living)
    9500145: 9500104,   # Gertrud Leibke: the copy attached to Georg; the 1939 census puts her
                        # at Oskar's address, so the Oskar copy (9500104) is canonical.
    9500148: 9500152,   # Julius Leibke
    9500149: 9500153,   # Henriette Katz
}

PRESUMED_DEAD_BY = 1920


def year(s):
    m = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", s or "")
    return int(m.group(1)) if m else None


def might_be_alive(p):
    """True for a person who is published as a living person under the standard."""
    if not p.get("alive"):
        return False
    if p["id"] in NAMED_BARE or p["id"] in DUPLICATES:
        return False
    by = year(p.get("b"))
    return not (by and by <= PRESUMED_DEAD_BY)
