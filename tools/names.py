"""Shared name normalisation, so the digest generator and the HTML scanner agree.

The two sides must derive the same key from the same person or the check is
vacuous — which it silently was for 'Jacinto Da Oliveira', caught only because
the negative test planted a real guarded name and the hash mode shrugged.
"""
import hashlib, re

PARTICLES = {"da", "de", "del", "della", "di", "do", "dos", "du", "la", "le",
             "van", "von", "der", "den", "ten", "ter", "el", "al", "bin", "mc", "st"}

def tokens(name):
    """Alphabetic tokens, lowercased, particles dropped, initials dropped."""
    raw = re.split(r"[^A-Za-zÀ-ÿ']+", name or "")
    out = [t.lower() for t in raw if len(t) > 1]
    out = [t for t in out if t not in PARTICLES]
    return out

def key(name):
    """Canonical key for a personal name: first token and last token."""
    t = tokens(name)
    if len(t) < 2:
        return None
    return t[0] + " " + t[-1]

def digest(salt, name):
    k = key(name)
    return None if not k else hashlib.sha256((salt + "|" + k).encode()).hexdigest()[:32]

# A run of name-like words in prose: capitalised words and lowercase particles.
WORD = r"(?:[A-ZÀ-Þ][a-zA-ZÀ-ÿ'\-]+|" + "|".join(sorted(PARTICLES)) + r")"
RUN = re.compile(r"\b(" + WORD + r"(?:\s+" + WORD + r"){1,4})\b")

def candidates(text):
    """Every plausible personal name in a block of prose, as canonical keys."""
    seen = set()
    for m in RUN.finditer(text):
        parts = m.group(1).split()
        for i in range(len(parts)):
            for j in range(i + 2, min(i + 5, len(parts)) + 1):
                k = key(" ".join(parts[i:j]))
                if k:
                    seen.add(k)
    return seen
