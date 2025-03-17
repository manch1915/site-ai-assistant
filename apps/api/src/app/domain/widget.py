from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, StringConstraints

HexColor = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]
QuickQuestion = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=60)
]


class WidgetSettings(BaseModel):
    title: str = Field(default="Assistant", max_length=40)
    subtitle: str = Field(default="Answers from our help pages", max_length=60)
    greeting: str = Field(default="Hi! Ask me anything about our services.", max_length=300)
    accent: HexColor = "#0E7C66"
    theme: Literal["light", "dark", "auto"] = "auto"
    position: Literal["right", "left"] = "right"
    radius: int = Field(default=16, ge=0, le=28)
    quick_questions: list[QuickQuestion] = Field(default_factory=list, max_length=4)
    language: Literal["auto", "en", "ru"] = "auto"
    show_sources: bool = True
    collect_leads: bool = True
    handoff_enabled: bool = True


def host_of(origin: str) -> str | None:
    return urlparse(origin).hostname


def origin_allowed(origin: str | None, allowed_domains: list[str], always: list[str]) -> bool:
    """`example.com` also covers `www.example.com`; `*.example.com` covers any subdomain.

    A request without Origin is not from a browser page, so domain locking doesn't apply;
    rate limits and budgets still do.
    """
    if not origin:
        return True
    host = host_of(origin)
    if host is None:
        return False
    if host in {host_of(a) for a in always}:
        return True
    for raw_rule in allowed_domains:
        rule = raw_rule.strip().lower()
        if rule.startswith("*.") and (host == rule[2:] or host.endswith(rule[1:])):
            return True
        if host in {rule, f"www.{rule}"}:
            return True
    return False
