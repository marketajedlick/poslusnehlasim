"""Konfigurace newsletteru z proměnných prostředí (bez e-mailů v repu)."""

from __future__ import annotations

import os
import re
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
DEFAULT_ECOMAIL_WIDGET_JS = "https://d70shl7vidtft.cloudfront.net/widget.js"


def _parse_subscribe_form(form_action: str) -> tuple[str, str, str]:
    """Vrátí (widget_id, mount_id, account) z URL /public/subscribe/LIST/HASH."""
    base_url = form_action.split("?", 1)[0]
    m = re.match(
        r"https?://([^.]+)\.ecomailapp\.cz/public/subscribe/(\d+)/([a-f0-9]+)",
        base_url,
    )
    if not m:
        return "", "", ""
    account, list_id, form_hash = m.group(1), m.group(2), m.group(3)
    widget_id = f"{list_id}-{form_hash}"
    return widget_id, f"f-{widget_id}", account


@dataclass(frozen=True)
class NewsletterConfig:
    """Veřejná konfigurace pro šablonu (bez API klíče)."""

    form_action: str
    subscribe_api_url: str
    privacy_url: str
    site_url: str
    feed_url: str
    show_subscribe: bool
    embed_widget_id: str
    embed_mount_id: str
    embed_account: str
    embed_widget_js: str

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
        if not show_raw:
            show_subscribe = bool(form_action or subscribe_api_url)
        else:
            show_subscribe = show_raw in ("1", "true", "yes")
        widget_id, mount_id, account = _parse_subscribe_form(form_action)
        embed_widget_js = (
            os.environ.get("ECOMAIL_WIDGET_JS") or DEFAULT_ECOMAIL_WIDGET_JS
        ).strip()
        return cls(
            form_action=form_action,
            subscribe_api_url=subscribe_api_url,
            privacy_url="https://ecomail.cz/gdpr",
            site_url=site,
            feed_url=feed,
            show_subscribe=show_subscribe,
            embed_widget_id=widget_id,
            embed_mount_id=mount_id,
            embed_account=account,
            embed_widget_js=embed_widget_js,
        )
