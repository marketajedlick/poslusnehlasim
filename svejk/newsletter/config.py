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


DEFAULT_ECOMAIL_FORM_ACTION = (
    "https://poslusnehlasim.ecomailapp.cz/public/subscribe/2/2bb287d15897fe2f9d89c882af9a3a8b"
)
DEFAULT_ECOMAIL_LIST_ID = "2"


@dataclass(frozen=True)
class NewsletterConfig:
    """Veřejná konfigurace pro šablonu (bez API klíče)."""

    form_action: str
    subscribe_api_url: str
    privacy_url: str
    site_url: str
    feed_url: str
    show_subscribe: bool

    @property
    def enabled(self) -> bool:
        return bool(self.form_action or self.subscribe_api_url)

    @classmethod
    def from_env(cls) -> NewsletterConfig:
        form_action = (
            os.environ.get("ECOMAIL_FORM_ACTION") or DEFAULT_ECOMAIL_FORM_ACTION
        ).strip()
        if form_action and "source=" not in form_action:
            sep = "&" if "?" in form_action else "?"
            form_action = f"{form_action}{sep}source=poslusnehlasim"
        site = _site_url()
        feed = f"{site}/feed.xml"
        subscribe_api_url = (os.environ.get("SVEJK_SUBSCRIBE_API_URL") or "").strip()
        show_raw = os.environ.get("SVEJK_SHOW_SUBSCRIBE", "").strip().lower()
        show_subscribe = show_raw in ("1", "true", "yes")
        return cls(
            form_action=form_action,
            subscribe_api_url=subscribe_api_url,
            privacy_url="https://ecomail.cz/gdpr",
            site_url=site,
            feed_url=feed,
            show_subscribe=show_subscribe,
        )
