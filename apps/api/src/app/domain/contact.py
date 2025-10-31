"""Light checks for how a visitor can be reached: Telegram, phone or email."""

import re

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_TELEGRAM = re.compile(r"^@([A-Za-z][A-Za-z0-9_]{4,31})$")
_TELEGRAM_LINK = re.compile(r"^(?:https?://)?t\.me/([A-Za-z][A-Za-z0-9_]{4,31})/?$", re.IGNORECASE)
_PHONE_NOISE = re.compile(r"[\s\-().]")
_PHONE = re.compile(r"^\+?\d{7,15}$")


def normalize_contact(raw: str) -> str | None:
    """The contact in a tidy form, or None when it looks like none of the three."""
    text = raw.strip()
    if _EMAIL.match(text):
        return text
    if match := _TELEGRAM.match(text) or _TELEGRAM_LINK.match(text):
        return f"@{match.group(1)}"
    phone = _PHONE_NOISE.sub("", text)
    if _PHONE.match(phone):
        return phone
    return None


def check_contact(raw: str) -> str:
    """Pydantic validator: rejects anything a manager couldn't use to write back."""
    contact = normalize_contact(raw)
    if contact is None:
        raise ValueError("Enter a Telegram @username, a phone number or an email")
    return contact
