"""Newsletter: odběr přes Ecomail, RSS, volitelné rozeslání po exportu."""

from svejk.newsletter.api import api_request, list_id_from_env, list_subscribers, send_campaign
from svejk.newsletter.config import NewsletterConfig
from svejk.newsletter.feed import write_feed_xml
from svejk.newsletter.notify import run_newsletter_notify

__all__ = [
    "NewsletterConfig",
    "api_request",
    "list_id_from_env",
    "list_subscribers",
    "send_campaign",
    "write_feed_xml",
    "run_newsletter_notify",
]
