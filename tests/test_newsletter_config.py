"""Tests for newsletter public config."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from svejk.newsletter.config import NewsletterConfig


class NewsletterConfigCorrectionsTest(unittest.TestCase):
    def test_corrections_url_defaults_from_subscribe_api(self):
        with patch.dict(
            os.environ,
            {
                "SVEJK_SUBSCRIBE_API_URL": "https://worker.example",
                "SVEJK_CORRECTIONS_API_URL": "",
                "SVEJK_SHOW_CORRECTIONS": "",
                "SVEJK_SHOW_SUBSCRIBE": "0",
            },
            clear=False,
        ):
            cfg = NewsletterConfig.from_env()
        self.assertEqual(cfg.corrections_api_url, "https://worker.example/corrections")
        self.assertTrue(cfg.show_corrections)

    def test_corrections_can_be_disabled(self):
        with patch.dict(
            os.environ,
            {
                "SVEJK_SUBSCRIBE_API_URL": "https://worker.example",
                "SVEJK_SHOW_CORRECTIONS": "0",
            },
            clear=False,
        ):
            cfg = NewsletterConfig.from_env()
        self.assertFalse(cfg.show_corrections)


class NewsletterConfigReactionsTest(unittest.TestCase):
    def test_reactions_url_defaults_from_subscribe_api(self):
        with patch.dict(
            os.environ,
            {
                "SVEJK_SUBSCRIBE_API_URL": "https://worker.example",
                "SVEJK_REACTIONS_API_URL": "",
                "SVEJK_SHOW_REACTIONS": "",
                "SVEJK_SHOW_SUBSCRIBE": "0",
            },
            clear=False,
        ):
            cfg = NewsletterConfig.from_env()
        self.assertEqual(cfg.reactions_api_url, "https://worker.example/reactions")
        self.assertTrue(cfg.show_reactions)

    def test_reactions_can_be_disabled(self):
        with patch.dict(
            os.environ,
            {
                "SVEJK_SUBSCRIBE_API_URL": "https://worker.example",
                "SVEJK_SHOW_REACTIONS": "0",
            },
            clear=False,
        ):
            cfg = NewsletterConfig.from_env()
        self.assertFalse(cfg.show_reactions)


if __name__ == "__main__":
    unittest.main()
