"""Tests for Slack share-card payload (no network)."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from svejk.newsletter.slack import (
    _image_reachable,
    post_share_card,
    webhook_url_from_env,
)


class SlackWebhookTest(unittest.TestCase):
    def test_webhook_url_from_env(self):
        with patch.dict(os.environ, {"SLACK_WEBHOOK_URL": " https://hooks.slack.com/x "}, clear=False):
            self.assertEqual(webhook_url_from_env(), "https://hooks.slack.com/x")

    def test_post_share_card_payload(self):
        captured: dict = {}

        def fake_urlopen(req, timeout=30):
            captured["url"] = req.full_url
            captured["body"] = json.loads(req.data.decode("utf-8"))
            resp = MagicMock()
            resp.status = 200
            resp.read.return_value = b"ok"
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch("svejk.newsletter.slack.urllib.request.urlopen", side_effect=fake_urlopen):
            out = post_share_card(
                webhook_url="https://hooks.slack.com/services/T/B/x",
                subject="Senát nestačil",
                edition_url="https://poslusnehlasim.cz/vydani/2026-09-09/",
                image_url="https://poslusnehlasim.cz/share/2026-09-09.png?v=abc",
            )
        self.assertTrue(out["ok"])
        blocks = captured["body"]["blocks"]
        self.assertEqual(blocks[0]["type"], "section")
        self.assertIn("Senát nestačil", blocks[0]["text"]["text"])
        self.assertIn("vydani/2026-09-09", blocks[0]["text"]["text"])
        self.assertEqual(blocks[1]["type"], "image")
        self.assertEqual(
            blocks[1]["image_url"],
            "https://poslusnehlasim.cz/share/2026-09-09.png?v=abc",
        )

    def test_image_reachable_rejects_bad_url(self):
        self.assertFalse(_image_reachable(""))
        self.assertFalse(_image_reachable("ftp://x"))

    def test_image_reachable_ok_on_head_200(self):
        def fake_urlopen(req, timeout=15):
            resp = MagicMock()
            resp.status = 200
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch("svejk.newsletter.slack.urllib.request.urlopen", side_effect=fake_urlopen):
            self.assertTrue(_image_reachable("https://poslusnehlasim.cz/share/x.png"))


if __name__ == "__main__":
    unittest.main()
