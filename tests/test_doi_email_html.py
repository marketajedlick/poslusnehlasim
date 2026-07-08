"""E-mailové šablony: bez color !important (SpamAssassin T_KAM_HTML_FONT_INVALID)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from svejk.build.html import _inline_email_body_link_styles, render_doi_email_html

_COLOR_IMPORTANT = re.compile(r"color\s*:[^;{]*!important", re.IGNORECASE)
_REPO = Path(__file__).resolve().parent.parent


class EmailHtmlTest(unittest.TestCase):
    def test_doi_html_has_no_color_important(self) -> None:
        _, _, html = render_doi_email_html(site_url="https://poslusnehlasim.cz")
        self.assertIn("*|SUBCONFIRM|*", html)
        self.assertIsNone(_COLOR_IMPORTANT.search(html))

    def test_nwl_css_has_no_color_important(self) -> None:
        css = (_REPO / "svejk/static/noviny-email.css").read_text(encoding="utf-8")
        self.assertIsNone(_COLOR_IMPORTANT.search(css))

    def test_inline_link_styles_have_no_color_important(self) -> None:
        html = '<a class="steno-link" href="https://example.com">odkaz</a>'
        styled = _inline_email_body_link_styles(html, field="lead")
        self.assertIn('style="color:#211c14;', styled)
        self.assertIsNone(_COLOR_IMPORTANT.search(styled))


if __name__ == "__main__":
    unittest.main()
