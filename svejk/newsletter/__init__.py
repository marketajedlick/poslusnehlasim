"""Newsletter: odběr přes Ecomail, RSS, volitelné rozeslání po exportu."""

from svejk.newsletter.api import (
    api_request,
    add_subscriber,
    list_id_from_env,
    list_subscribers,
    send_campaign,
    subscribe_list_id_from_env,
    update_list,
)
from svejk.newsletter.config import NewsletterConfig
from svejk.newsletter.doi import export_doi_template, sync_doi_to_ecomail
from svejk.newsletter.feed import write_feed_xml
from svejk.newsletter.notify import run_newsletter_notify

__all__ = [
    "NewsletterConfig",
    "api_request",
    "add_subscriber",
    "export_doi_template",
    "list_id_from_env",
    "subscribe_list_id_from_env",
    "list_subscribers",
    "send_campaign",
    "sync_doi_to_ecomail",
    "update_list",
    "write_feed_xml",
    "run_newsletter_notify",
]
