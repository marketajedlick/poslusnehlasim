"""Newsletter: odběr přes Buttondown, RSS, volitelné rozeslání po exportu."""

from svejk.newsletter.config import NewsletterConfig
from svejk.newsletter.feed import write_feed_xml
from svejk.newsletter.notify import run_newsletter_notify

__all__ = ["NewsletterConfig", "write_feed_xml", "run_newsletter_notify"]
