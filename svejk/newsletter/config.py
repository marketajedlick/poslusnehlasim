"""Konfigurace newsletteru z proměnných prostředí (bez e-mailů v repu)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _site_url() -> str:
    base = os.environ.get("SVEJK_SITE_URL", "https://poslusnehlasim.cz").rstrip("/")
    path = os.environ.get("SVEJK_BASE_PATH", "").rstrip("/")
    if path and not path.startswith("/"):
        path = "/" + path
    return (base + path).rstrip("/") or base


DEFAULT_BUTTONDOWN_USERNAME = "marketa"


@dataclass(frozen=True)
class NewsletterConfig:
    """Veřejná konfigurace pro šablonu (bez API klíče)."""

    username: str
    form_action: str
    privacy_url: str
    site_url: str
    feed_url: str

    @property
    def enabled(self) -> bool:
        return bool(self.username)

    @classmethod
    def from_env(cls) -> NewsletterConfig:
        username = (
            os.environ.get("BUTTONDOWN_USERNAME") or DEFAULT_BUTTONDOWN_USERNAME
        ).strip()
        site = _site_url()
        feed = f"{site}/feed.xml"
        return cls(
            username=username,
            form_action=f"https://buttondown.email/api/emails/embed-subscribe/{username}",
            privacy_url="https://buttondown.com/legal/privacy",
            site_url=site,
            feed_url=feed,
        )
