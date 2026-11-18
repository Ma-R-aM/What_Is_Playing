"""Track metadata cleanup.

This is a Python port of the Android app's ``TrackInfoParser`` so the desktop
build behaves the same way when it receives noisy artist strings.
"""

from __future__ import annotations

import random
import re

MAX_STATUS_LENGTH = 128

KAOMOJIS: tuple[str, ...] = (
    "(=^•ω•^=)",
    "(=^･ω･^=)",
    "(=ↀωↀ=)",
    "(=^ ◡ ^=)",
    "(^・ω・^ )",
    "(｡•̀ᴗ-)✧",
    "(๑>ᴗ<๑)",
    "(≧◡≦)",
    "(づ｡◕‿‿◕｡)づ",
    "(´｡• ᵕ •｡`)",
    "(˶ᵔ ᵕ ᵔ˶)",
    "(｡･ω･｡)",
    "(„• ᴗ •„)",
    "(✿◠‿◠)",
    "(⁄ ⁄•⁄ω⁄•⁄ ⁄)",
    "(๑•́ ₃ •̀๑)",
    "(≧ω≦)",
    "(＾▽＾)",
    "(⌒‿⌒)",
    "(๑˃ᴗ˂)ﻭ",
    "(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧",
    "(｡>﹏<｡)",
    "(´･ω･`)",
    "(・∀・)",
    "(◕ᴗ◕✿)",
    "(ᵔᴥᵔ)",
    "(ฅ^•ﻌ•^ฅ)",
    "(｡•ω•｡)",
    "(っ˘ω˘ς)",
    "(๑´ω`๑)",
    "(o^▽^o)",
    "(✧ω✧)",
    "(ﾉ´ヮ`)ﾉ*: ･ﾟ",
    "( ˘ ³˘)♥",
    "(๑•᎑•๑)",
)

_WITH_SLOVAK = re.compile(r"\(spolu s[^)]*\)", re.IGNORECASE)
_WITH_ENGLISH = re.compile(r"\(with[^)]*\)", re.IGNORECASE)

# Matches a trailing play-count/views suffix such as:
#
#   IamOutlandish a 1,3 tis. prehraní
#   IamOutlandish, 1,3 tis. prehraní
#   Artist • 1.3K plays
#   Artist, 1 234 zobrazení
#
# It intentionally requires a play-count/views word at the end, so artist
# names that merely contain a number are left alone.
_PLAY_COUNT = re.compile(
    r"""(?i)\s*(?:[,•·|&–—-]\s*|\ba\s+)?"""
    r"""(?:\d{1,3}(?:[ \u00A0\u202F]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"""
    r"""\s*(?:tis\.?|mil\.?|mld\.?|k|m|b|tisíc|tisic|milión\w*|milion\w*|miliárd\w*|miliard\w*)?"""
    r"""\s*(?:prehraní|prehratí|prehrání|přehrání|prehrania|zhliadnutí|zhliadnutia|zhliadnuťia|zhlédnutí|zhlédnutia|plays?|zobrazení|zobrazení|views?|listens?)\s*$"""
)

_TRAILING_SEPARATORS = ",•·|&–—-"


def normalize(text: str) -> str:
    """Collapse the non-breaking spaces players like to put in metadata."""
    return text.replace("\u00a0", " ").replace("\u202f", " ").strip()


def clean_title(raw: str) -> str:
    title = normalize(raw)
    title = _WITH_SLOVAK.sub("", title)
    title = _WITH_ENGLISH.sub("", title)
    return title.strip()


def clean_artist(raw: str) -> str:
    artist = normalize(raw)
    artist = _PLAY_COUNT.sub("", artist)
    return artist.strip().rstrip(_TRAILING_SEPARATORS).strip()


def is_player_notification(title: str) -> bool:
    normalized = normalize(title)
    return (
        normalized.casefold() in {"prehrávač hudby", "music player"}
        or "metrolist" in normalized.casefold()
    )


def build_status(
    title: str,
    artist: str,
    *,
    append_kaomoji: bool = True,
    kaomoji: str | None = None,
    max_length: int = MAX_STATUS_LENGTH,
) -> str:
    """Build the Discord custom-status text (Discord allows 128 characters)."""
    body = f"{title} | {artist}" if artist else title
    suffix = ""
    if append_kaomoji:
        chosen = kaomoji or random.choice(KAOMOJIS)
        suffix = f" {chosen}"

    max_body_length = max_length - len(suffix)
    if len(body) > max_body_length:
        body = body[: max(max_body_length - 3, 0)] + "..."

    return body + suffix
