"""Export šablony potvrzovacího e-mailu (double opt-in) pro Ecomail."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from svejk.build.html import render_doi_email_html
from svejk.newsletter.config import NewsletterConfig


def export_doi_template(
    out_dir: Path | str,
    *,
    base_path: str = "",
) -> dict[str, Any]:
    """Zapíše HTML a plain text šablony DOI do složky (pro vložení do Ecomailu)."""
    cfg = NewsletterConfig.from_env()
    subject, plain, html = render_doi_email_html(
        site_url=cfg.site_url,
        base_path=base_path,
    )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    html_path = out / "doi.html"
    plain_path = out / "doi.txt"
    readme_path = out / "README.txt"

    html_path.write_text(html, encoding="utf-8")
    plain_path.write_text(plain, encoding="utf-8")
    readme_path.write_text(
        "\n".join(
            [
                "Šablona double opt-in pro Ecomail",
                "================================",
                "",
                f"Předmět: {subject}",
                "",
                "1. Ecomail → Šablony → nová šablona",
                "2. Vlož obsah souboru doi.html (HTML editor)",
                "3. Ověř, že v šabloně zůstal merge tag *|SUBCONFIRM|*",
                "4. Seznam kontaktů → Nastavení → double opt-in → vyber tuto šablonu",
                f"5. URL po potvrzení: {cfg.confirm_redirect_url}",
                "",
                "doi.txt = záložní plain text verze",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "subject": subject,
        "html": str(html_path),
        "plain": str(plain_path),
        "readme": str(readme_path),
        "confirm_redirect_url": cfg.confirm_redirect_url,
    }
