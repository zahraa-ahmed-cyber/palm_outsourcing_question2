"""Name matching for two exports that share no client ID.

Judgement lives in this file on purpose. The alternative at each fork is
named in the comment so a reviewer can disagree without reverse-engineering
the code.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# Legal / entity tokens that billing writes and project tools drop.
# Alternative: keep them and hope fuzzy ratio eats the difference. That
# fails on short brands ("Mira Skin LLC" vs a different "Mira").
_STRIP_TOKENS = {
    "inc",
    "incorporated",
    "llc",
    "ltd",
    "limited",
    "co",
    "company",
    "corp",
    "corporation",
    "plc",
    "lp",
    "pllc",
    "pc",
}

# Leading "the" is a brand-style word, not an entity type, but billing
# dumps it in all-caps legal names. Stripping it is the only way
# "THE KINDRED HOME INC." meets "Kindred Home".
_STRIP_LEADING = {"the"}

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_name(name: str) -> str:
    """Lowercase, expand '&', drop punctuation and legal suffixes."""
    if not name:
        return ""
    s = name.casefold().replace("&", " and ")
    s = _NON_ALNUM.sub(" ", s)
    tokens = [t for t in s.split() if t]
    while tokens and tokens[0] in _STRIP_LEADING:
        tokens.pop(0)
    while tokens and tokens[-1] in _STRIP_TOKENS:
        tokens.pop()
    return " ".join(tokens)


def compact(name: str) -> str:
    return normalize_name(name).replace(" ", "")


def _ratio(a: str, b: str) -> int:
    if not a or not b:
        return 0
    return round(SequenceMatcher(None, a, b).ratio() * 100)


def name_score(left: str, right: str) -> tuple[int, str]:
    """Return (0-100, why).

    Compact-equal is scored just under exact-normalized so Glow Theory /
    GlowTheory still *finds* each other, but is not treated as confirmed.
    Alternative: treat compact-equal as 100 — that hides the spelling mess.
    """
    na, nb = normalize_name(left), normalize_name(right)
    if not na or not nb:
        return 0, "empty name"
    if na == nb:
        return 100, "same after normalising case, punctuation and legal suffix"
    ca, cb = na.replace(" ", ""), nb.replace(" ", "")
    if ca == cb:
        return 96, "same letters once spaces are ignored"
    # Extra trailing words on one side ("Mira Skin" vs "Mira Skin Care").
    # Alternative: token-set ratio, which also gives 100 and false-positives
    # two brands that share a generic word like Skin.
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    if len(shorter) >= 8 and longer.startswith(shorter + " "):
        extra = longer[len(shorter) :].strip()
        if extra and extra not in _STRIP_TOKENS:
            return 90, f"one name is the other plus '{extra}'"
    seq = _ratio(na, nb)
    sorted_a = " ".join(sorted(na.split()))
    sorted_b = " ".join(sorted(nb.split()))
    token_sort = _ratio(sorted_a, sorted_b)
    compact_r = _ratio(ca, cb)
    score = max(seq, token_sort, compact_r)
    return score, "fuzzy (sequence / token-sort / compact)"


# Confirmed means the names are the same after the normaliser — not "pretty
# close". 72–99 is a possible match the lead must confirm. Alternative:
# auto-attach at 88. That is how a 90% Mira Skin / Mira Skin Care pair
# silently becomes one client.
CONFIRMED = 100
REVIEW_FLOOR = 72


def classify_score(score: int) -> str:
    if score >= CONFIRMED:
        return "matched"
    if score >= REVIEW_FLOOR:
        return "review"
    return "unmatched"
