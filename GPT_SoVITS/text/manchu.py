# GPT_SoVITS/text/manchu.py
# Manchu Latin romanization → CMUdict-style ARPAbet phoneme converter.
#
# Two input modes are supported:
#   1. Manchu Latin text  (e.g. "ere be age de bumbi")
#      → each token is looked up in the bundled word dictionary
#      → returns the corresponding CMUdict phoneme list
#   2. Pre-converted CMUdict phoneme string (e.g. "AH1 R AH1 P AH1")
#      → split by whitespace and returned directly
#
# Mode is detected by whether the first token is lower-case (Manchu text)
# or upper-case / digit-suffixed (already ARPAbet).

import os
import re
import warnings

# ---------------------------------------------------------------------------
# Dictionary path – relative to this file so the package is self-contained
# ---------------------------------------------------------------------------
_DICT_PATH = os.path.join(os.path.dirname(__file__), "manchu_dict", "manchu_cmudict.txt")

_WORD_DICT = None   # type: dict | None  # lazy-loaded


def _load_dict() -> dict:
    global _WORD_DICT
    if _WORD_DICT is not None:
        return _WORD_DICT
    _WORD_DICT = {}
    if not os.path.isfile(_DICT_PATH):
        raise FileNotFoundError(
            f"Manchu CMUdict not found at {_DICT_PATH}. "
            "Run GPT_SoVITS/text/manchu_dict/gen_manchu_dict.py to generate it."
        )
    with open(_DICT_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                _WORD_DICT[parts[0]] = parts[1]
    return _WORD_DICT


# ---------------------------------------------------------------------------
# Helper: detect whether the text is already ARPAbet phonemes
# ---------------------------------------------------------------------------
_ARPA_TOKEN = re.compile(r'^[A-Z]+[0-9]?$')
_WORD_TOKEN = re.compile(r"[a-z']+|[.!?,…-]")

_CJK_PUNCT_MAP = {
    "。": ".",
    "，": ",",
    "、": ",",
    "！": "!",
    "？": "?",
    "：": ",",
    "；": ",",
}

_PUNCT_TOKENS = {".", ",", "!", "?", "…", "-"}

# Fallback rule mapping for unknown words.
# Priority:
#   1) multi-char clusters (longest match)
#   2) single-char letters
_FALLBACK_MULTI = {
    "ng": ["NG"],
    "sh": ["SH"],
    "ch": ["CH"],
    "zh": ["JH"],
    "ai": ["AW1", "JH"],
    "oi": ["OW1", "JH"],
    "ui": ["UW1", "JH"],
}

_FALLBACK_SINGLE = {
    "a": ["AW1"],
    "e": ["AH1"],
    "i": ["IY1"],
    "o": ["OW1"],
    "u": ["UW1"],
    "v": ["AO1"],
    "b": ["P"],
    "p": ["P"],
    "d": ["T"],
    "t": ["T"],
    "g": ["K"],
    "k": ["K"],
    "h": ["HH"],
    "f": ["F"],
    "s": ["S"],
    "x": ["S"],
    "z": ["JH"],
    "j": ["JH"],
    "y": ["JH"],
    "w": ["W"],
    "r": ["R"],
    "l": ["L"],
    "m": ["M"],
    "n": ["N"],
    "q": ["K"],
    "c": ["CH"],
}


def _is_arpa_sequence(text: str) -> bool:
    """Return True if every whitespace-separated token looks like an ARPAbet symbol."""
    tokens = text.split()
    if not tokens:
        return False
    return all(_ARPA_TOKEN.match(t) or t in _PUNCT_TOKENS for t in tokens)


def _normalize_punctuation(text: str) -> str:
    for src, dst in _CJK_PUNCT_MAP.items():
        text = text.replace(src, dst)
    return text


def _split_oov_by_known_subwords(word: str, word_dict: dict) -> list:
    """Try to decompose OOV word into known dictionary subwords using DP."""
    n = len(word)
    dp = [None] * (n + 1)
    dp[n] = []

    for i in range(n - 1, -1, -1):
        for j in range(n, i, -1):
            seg = word[i:j]
            if seg in word_dict and dp[j] is not None:
                dp[i] = word_dict[seg].split() + dp[j]
                break

    if dp[0] is None:
        return None

    # If decomposition ended up as a single exact word, caller should have matched it already.
    return dp[0]


def _fallback_roman_to_cmu(word: str) -> list:
    """Rule-based romanized fallback for OOV words."""
    i = 0
    out = []
    n = len(word)

    while i < n:
        if i + 1 < n:
            dig = word[i:i + 2]
            if dig in _FALLBACK_MULTI:
                out.extend(_FALLBACK_MULTI[dig])
                i += 2
                continue

        ch = word[i]
        if ch in _FALLBACK_SINGLE:
            out.extend(_FALLBACK_SINGLE[ch])
        else:
            out.append("SP")
        i += 1

    return out


# ---------------------------------------------------------------------------
# Public API expected by cleaner.py
# ---------------------------------------------------------------------------

def text_normalize(text: str) -> str:
    """Lower-case and strip Manchu Latin input; leave ARPAbet strings untouched."""
    stripped = _normalize_punctuation(text.strip())
    if _is_arpa_sequence(stripped):
        return stripped          # already phoneme sequence – nothing to do
    return stripped.lower()      # normalise Manchu Latin text


def g2p(text: str) -> list:
    """
    Convert Manchu text or pre-converted ARPAbet string to a phoneme list.

    - ARPAbet input  → split by whitespace, return list
        - Manchu Latin   → dictionary-first with two fallback layers:
            1) decompose OOV token by known subwords in dictionary
            2) rule-based romanized fallback mapping to ARPAbet
    """
    text = _normalize_punctuation(text.strip())
    if not text:
        return []

    # --- Mode 1: already ARPAbet ---
    if _is_arpa_sequence(text):
        return text.split()

    # --- Mode 2: Manchu Latin text ---
    word_dict = _load_dict()
    phones = []
    # Split words and punctuation so "tokso." becomes ["tokso", "."]
    for word in _WORD_TOKEN.findall(text.lower()):
        if word in _PUNCT_TOKENS:
            phones.append(word)
            continue
        word_lower = word.lower()
        if word_lower in word_dict:
            phones.extend(word_dict[word_lower].split())
        else:
            # Fallback 1: known subword decomposition
            subword_phones = _split_oov_by_known_subwords(word_lower, word_dict)
            if subword_phones:
                warnings.warn(
                    f"[manchu g2p] OOV word '{word}' decomposed by dictionary subwords.",
                    UserWarning,
                    stacklevel=2,
                )
                phones.extend(subword_phones)
                continue

            # Fallback 2: rule-based romanized mapping
            fallback_phones = _fallback_roman_to_cmu(word_lower)
            warnings.warn(
                f"[manchu g2p] OOV word '{word}' using rule fallback: "
                + " ".join(fallback_phones),
                UserWarning,
                stacklevel=2,
            )
            phones.extend(fallback_phones)

    return phones