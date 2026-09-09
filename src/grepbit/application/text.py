"""Script-aware phrase matching shared by language packs and overlays."""

from __future__ import annotations

import re

_ASCII_WORD = re.compile(r"[a-z0-9_]")


def phrase_in(question: str, phrase: str) -> bool:
    """Phrase containment with word boundaries only where the script has words.

    Latin phrases must not match inside longer words. Scripts without spaces
    (CJK) have no word boundary, and a Chinese phrase may legitimately touch a
    digit or another character, so boundaries apply per edge only when the
    phrase itself starts or ends with an ASCII word character.
    """

    if not phrase:
        return False
    before = r"(?<![a-z0-9_])" if _ASCII_WORD.match(phrase[0]) else ""
    after = r"(?![a-z0-9_])" if _ASCII_WORD.match(phrase[-1]) else ""
    return re.search(f"{before}{re.escape(phrase)}{after}", question) is not None
