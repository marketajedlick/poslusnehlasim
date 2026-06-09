"""Export a synchronizace šablony potvrzovacího e-mailu (double opt-in) pro Ecomail."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from svejk.newsletter.api import (
    api_key_from_env,
    create_template,
    list_id_from_env,
    list_templates,
    show_list,
    update_list,
    update_template,
)
from svejk.newsletter.config import NewsletterConfig

DOI_TEMPLATE_NAME = "Poslušně hlásím · DOI"


def _doi_sender() -> tuple[str, str, str]:
    from_name = (os.environ.get("ECOMAIL_FROM_NAME") or "Poslušně hlásím").strip()
    from_email = (os.environ.get("ECOMAIL_FROM_EMAIL") or "").strip()
    reply_to = (os.environ.get("ECOMAIL_REPLY_TO") or from_email).strip()
    return from_name, from_email, reply_to


def _doi_content(*, base_path: str = "") -> tuple[str, str, str]:
    from svejk.build.html import render_doi_email_html

    cfg = NewsletterConfig.from_env()
    return render_doi_email_html(site_url=cfg.site_url, base_path=base_path)


def export_doi_template(
    out_dir: Path | str,
    *,
    base_path: str = "",
) -> dict[str, Any]:
    """Zapíše HTML a plain text šablony DOI do složky (pro vložení do Ecomailu)."""
    cfg = NewsletterConfig.from_env()
    subject, plain, html = _doi_content(base_path=base_path)
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
                "Automaticky:",
                "  ./run-svejk.sh newsletter-doi-sync --apply",
                "",
                "Ručně:",
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


def _find_template_id(templates: list[dict[str, Any]], name: str) -> int | None:
    for tpl in templates:
        if (tpl.get("name") or "").strip() == name:
            raw_id = tpl.get("id")
            if isinstance(raw_id, int):
                return raw_id
            if isinstance(raw_id, str) and raw_id.isdigit():
                return int(raw_id)
    return None


def sync_doi_to_ecomail(
    *,
    base_path: str = "",
    apply: bool = False,
    enable_double_optin: bool = False,
    sync_template: bool = True,
) -> dict[str, Any]:
    """
    Nahraje DOI šablonu do Ecomailu:
    - nastaví conf_message/conf_subject u seznamu (skutečný potvrzovací mail)
    - volitelně vytvoří/aktualizuje šablonu v Knihovně šablon
    """
    api_key = api_key_from_env()
    list_id = list_id_from_env()
    if not api_key:
        return {"skipped": True, "reason": "chybí ECOMAIL_API_KEY"}
    if not list_id:
        return {"skipped": True, "reason": "chybí ECOMAIL_LIST_ID"}

    cfg = NewsletterConfig.from_env()
    from_name, from_email, reply_to = _doi_sender()
    if apply and not from_email:
        return {"skipped": True, "reason": "chybí ECOMAIL_FROM_EMAIL"}

    subject, plain, html = _doi_content(base_path=base_path)
    if "*|SUBCONFIRM|*" not in html:
        return {"skipped": True, "reason": "HTML neobsahuje *|SUBCONFIRM|*"}

    current = show_list(api_key, list_id)
    list_info = current.get("list") if isinstance(current.get("list"), dict) else current

    list_payload: dict[str, Any] = {
        "conf_subject": subject,
        "conf_message": html,
        "sub_confirmed_page": cfg.confirm_redirect_url,
    }
    if from_name:
        list_payload["from_name"] = from_name
    if from_email:
        list_payload["from_email"] = from_email
    if reply_to:
        list_payload["reply_to"] = reply_to
    if enable_double_optin:
        list_payload["double_optin"] = True

    preview_payload = {**list_payload, "conf_message": f"<html … {len(html)} znaků>"}
    result: dict[str, Any] = {
        "dry_run": not apply,
        "list_id": list_id,
        "subject": subject,
        "confirm_redirect_url": cfg.confirm_redirect_url,
        "html_bytes": len(html.encode("utf-8")),
        "has_subconfirm": True,
        "current_double_optin": list_info.get("double_optin"),
        "list_update": preview_payload if not apply else {
            k: v for k, v in list_payload.items() if k != "conf_message"
        },
    }

    if sync_template:
        templates = list_templates(api_key)
        template_id = _find_template_id(templates, DOI_TEMPLATE_NAME)
        result["template_name"] = DOI_TEMPLATE_NAME
        result["template_id"] = template_id
        result["template_action"] = "update" if template_id else "create"

    if not apply:
        result["skipped_send"] = True
        result["hint"] = "Spusť znovu s --apply pro zápis do Ecomailu."
        return result

    updated_list = update_list(api_key, list_id, list_payload)
    result["ecomail_list"] = updated_list

    if sync_template:
        if template_id:
            updated_tpl = update_template(
                api_key,
                template_id,
                name=DOI_TEMPLATE_NAME,
                html=html,
            )
            result["ecomail_template"] = updated_tpl
        else:
            created_tpl = create_template(
                api_key,
                name=DOI_TEMPLATE_NAME,
                html=html,
            )
            result["ecomail_template"] = created_tpl

    result["synced"] = True
    result["plain_preview"] = plain
    return result
