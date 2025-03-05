import re

_CYRILLIC = re.compile(r"[а-яё]", re.IGNORECASE)
_LATIN = re.compile(r"[a-z]", re.IGNORECASE)

LANGUAGE_NAMES = {"ru": "Russian", "en": "English"}


def detect_language(text: str, fallback: str = "en") -> str:
    cyrillic = len(_CYRILLIC.findall(text))
    latin = len(_LATIN.findall(text))
    if cyrillic == 0 and latin == 0:
        return fallback
    # Brand names are often typed in Latin inside a Russian sentence.
    return "ru" if cyrillic * 2 >= latin else "en"
