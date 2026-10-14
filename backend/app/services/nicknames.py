"""Public nicknames: refuses insults and names that pretend to speak for the app.

Matching runs on a normalised form (lower case, look-alike digits turned into letters, separators removed), so
"Adm1n", "a.d.m.i.n" or "SUPP0RT" are caught too. Short words that often appear inside harmless names are matched
only as the whole nickname, never as a part of it.
"""

from __future__ import annotations

import re

_LOOKALIKES = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "$": "s", "@": "a"})

# Names that could make a user look like staff or the app itself (any part of the nickname).
_IMPERSONATION = ("admin", "moderator", "support", "podpora", "official", "oficial", "staff", "aicrypto",
                  "cryptoanalytics", "helpdesk", "spravca")
# Insults and slurs in the app's languages (any part of the nickname).
_OFFENSIVE = (
    # English
    "fuck", "shit", "bitch", "cunt", "nigg", "fagg", "whore", "slut", "retard", "hitler",
    # Slovak / Czech
    "kokot", "picus", "kurv", "jebat", "jeban", "jebem", "zmrd", "debil",
    "chuj", "hovad", "hovno", "sracka", "prdel", "cigan", "buzerant", "mrdat", "mrdka", "pojeb", "zkurv", "skurv",
    # German
    "fotze", "hurens", "wichser", "arschloch", "schlampe", "missgeburt",
    # Polish
    "kurwa", "pierdol", "jebac", "spierdal", "zajeb", "cwel",
)
# Too short or too common to match inside other words: refused only as the whole nickname.
_WHOLE_ONLY = ("ass", "fag", "sex", "pussy", "dick", "cock", "cum", "anal", "pica", "pice", "pedal", "nazi", "system",
               "root", "team", "sprava")


def normalise(nickname: str) -> str:
    text = nickname.lower().translate(_LOOKALIKES)
    text = text.replace("č", "c").replace("ť", "t").replace("ž", "z").replace("š", "s").replace("ľ", "l")
    return re.sub(r"[^a-z]", "", text)


def is_allowed(nickname: str) -> bool:
    plain = normalise(nickname)
    return plain not in _WHOLE_ONLY and not any(word in plain for word in _OFFENSIVE + _IMPERSONATION)
