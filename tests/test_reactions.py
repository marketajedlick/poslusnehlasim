"""Tests for article reaction markup in templates."""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from svejk.build.html import _jinja_env
from svejk.newsletter.config import NewsletterConfig
from svejk.strings import load_strings


class ReactionsTemplateTest(unittest.TestCase):
    def _render(self, *, show_reactions: bool, slug: str = "rozpoctove-brzdy") -> str:
        cfg = NewsletterConfig(
            form_action="",
            subscribe_api_url="https://worker.example",
            privacy_url="https://poslusnehlasim.cz/soukromi/",
            contact_email="",
            site_url="https://poslusnehlasim.cz",
            feed_url="https://poslusnehlasim.cz/feed.xml",
            show_subscribe=False,
            embed_widget_id="",
            embed_mount_id="",
            embed_account="",
            embed_widget_js="",
            subscribe_mode="",
            corrections_api_url="https://worker.example/corrections",
            show_corrections=True,
            reactions_api_url="https://worker.example/reactions",
            show_reactions=show_reactions,
        )
        return _jinja_env().get_template("card-reactions.html").render(
            newsletter=cfg,
            edition_iso_date="2026-07-02",
            item=SimpleNamespace(slug=slug),
            t=load_strings(),
        )

    def test_reactions_markup_when_enabled(self):
        html = self._render(show_reactions=True)
        self.assertIn('class="article-actions reactions"', html)
        self.assertIn('class="article-actions-row"', html)
        self.assertIn('data-slug="rozpoctove-brzdy"', html)
        self.assertIn('class="reaction-clear"', html)
        self.assertIn('data-reaction="nojo"', html)
        self.assertIn("😅", html)

    def test_reactions_hidden_when_disabled(self):
        html = self._render(show_reactions=False)
        self.assertNotIn('class="article-actions reactions"', html)

    def test_reactions_hidden_without_slug(self):
        html = self._render(show_reactions=True, slug="")
        self.assertNotIn('class="article-actions reactions"', html)


class ReactionsScriptTemplateTest(unittest.TestCase):
    def test_reactions_config_rendered_when_enabled(self):
        with patch.dict(
            os.environ,
            {
                "SVEJK_SUBSCRIBE_API_URL": "https://worker.example",
                "SVEJK_SHOW_REACTIONS": "1",
                "SVEJK_SHOW_SUBSCRIBE": "0",
            },
            clear=False,
        ):
            cfg = NewsletterConfig.from_env()
        html = _jinja_env().get_template("reactions-script.html").render(
            newsletter=cfg,
            edition_iso_date="2026-07-02",
        )
        self.assertIn('id="reactions-config"', html)
        self.assertLess(html.index('id="reactions-config"'), html.index("<script>"))
        self.assertIn("https://worker.example/reactions", html)
        self.assertIn("__phInitReactions", html)


if __name__ == "__main__":
    unittest.main()
