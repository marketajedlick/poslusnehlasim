"""Export a synchronizace šablony potvrzovacího e-mailu (double opt-in) pro Ecomail."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from svejk.locale import localized_path, normalize_locale
from svejk.newsletter.api import (
    api_key_from_env,
    create_template,
    list_templates,
    show_list,
    subscribe_list_id_en_from_env,
    subscribe_list_id_from_env,
    update_list,
    update_template,
)
from svejk.newsletter.config import NewsletterConfig

DOI_TEMPLATE_NAMES = {
    "cs": "Poslušně hlásím · DOI",
    "en": "Poslušně hlásím · DOI (EN)",
}
DOI_EXPORT_FILES = {
    "cs": ("doi.html", "doi.txt"),
    "en": ("doi-en.html", "doi-en.txt"),
}


def _doi_sender() -> tuple[str, str, str]:
    from_name = (os.environ.get("ECOMAIL_FROM_NAME") or "Poslušně hlásím").strip()
    from_email = (os.environ.get("ECOMAIL_FROM_EMAIL") or "").strip()
    reply_to = (os.environ.get("ECOMAIL_REPLY_TO") or from_email).strip()
    return from_name, from_email, reply_to


def _doi_content(*, base_path: str = "", locale: str = "cs") -> tuple[str, str, str]:
    from svejk.build.html import render_doi_email_html

    cfg = NewsletterConfig.from_env()
    return render_doi_email_html(
        site_url=cfg.site_url,
        base_path=base_path,
        locale=locale,
    )


def _doi_list_id(locale: str) -> int | None:
    loc = normalize_locale(locale)
    if loc == "en":
        return subscribe_list_id_en_from_env()
    return subscribe_list_id_from_env()


def export_doi_template(
    out_dir: Path | str,
    *,
    base_path: str = "",
    locale: str | None = None,
) -> dict[str, Any]:
    """Zapíše HTML a plain text šablony DOI do složky (pro vložení do Ecomailu)."""
    cfg = NewsletterConfig.from_env()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    locales = ["cs", "en"] if locale is None else [normalize_locale(locale)]
    exports: dict[str, Any] = {"locales": {}}

    for loc in locales:
        subject, plain, html = _doi_content(base_path=base_path, locale=loc)
        html_name, plain_name = DOI_EXPORT_FILES[loc]
        html_path = out / html_name
        plain_path = out / plain_name
        html_path.write_text(html, encoding="utf-8")
        plain_path.write_text(plain, encoding="utf-8")
        list_id = _doi_list_id(loc)
        exports["locales"][loc] = {
            "subject": subject,
            "html": str(html_path),
            "plain": str(plain_path),
            "list_id": list_id,
            "template_name": DOI_TEMPLATE_NAMES[loc],
        }

    readme_lines = [
        "Šablony double opt-in pro Ecomail",
        "=================================",
        "",
    ]
    for loc in locales:
        info = exports["locales"][loc]
        readme_lines.extend(
            [
                f"[{loc}] předmět: {info['subject']}",
                f"  seznam: {info['list_id']}",
                f"  HTML: {Path(info['html']).name}",
                f"  plain: {Path(info['plain']).name}",
                "",
            ]
        )
    readme_lines.extend(
        [
            "Automaticky (oba seznamy):",
            "  ./run-svejk.sh newsletter-doi-sync --apply --all-locales",
            "",
            "Jen angličtina:",
            "  ./run-svejk.sh newsletter-doi-sync --apply --locale en",
            "",
            f"URL po potvrzení (cs): {cfg.site_url.rstrip('/')}/potvrzeno/",
            f"URL po potvrzení (en): {cfg.site_url.rstrip('/')}/en/potvrzeno/",
        ]
    )
    readme_path = out / "README.txt"
    readme_path.write_text("\n".join(readme_lines) + "\n", encoding="utf-8")
    exports["readme"] = str(readme_path)
    exports["subject"] = exports["locales"]["cs"]["subject"]
    exports["html"] = exports["locales"]["cs"]["html"]
    exports["plain"] = exports["locales"]["cs"]["plain"]
    exports["confirm_redirect_url"] = cfg.confirm_redirect_url
    return exports


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
    locale: str = "cs",
    all_locales: bool = False,
) -> dict[str, Any]:
    """
    Nahraje DOI šablonu do Ecomailu:
    - nastaví conf_message/conf_subject u seznamu (skutečný potvrzovací mail)
    - volitelně vytvoří/aktualizuje šablonu v Knihovně šablon
    """
    if all_locales:
        results: dict[str, Any] = {"all_locales": True, "locales": {}}
        for loc in ("cs", "en"):
            results["locales"][loc] = sync_doi_to_ecomail(
                base_path=base_path,
                apply=apply,
                enable_double_optin=enable_double_optin,
                sync_template=sync_template,
                locale=loc,
                all_locales=False,
            )
        return results

    loc = normalize_locale(locale)
    api_key = api_key_from_env()
    list_id = _doi_list_id(loc)
    if not api_key:
        return {"skipped": True, "reason": "chybí ECOMAIL_API_KEY", "locale": loc}
    if not list_id:
        key = "ECOMAIL_SUBSCRIBE_LIST_ID_EN" if loc == "en" else "ECOMAIL_SUBSCRIBE_LIST_ID"
        return {"skipped": True, "reason": f"chybí {key}", "locale": loc}

    cfg = NewsletterConfig.from_env()
    from_name, from_email, reply_to = _doi_sender()
    if apply and not from_email:
        return {"skipped": True, "reason": "chybí ECOMAIL_FROM_EMAIL", "locale": loc}

    subject, plain, html = _doi_content(base_path=base_path, locale=loc)
    if "*|SUBCONFIRM|*" not in html:
        return {"skipped": True, "reason": "HTML neobsahuje *|SUBCONFIRM|*", "locale": loc}

    confirm_redirect_url = f"{cfg.site_url.rstrip('/')}{localized_path('/potvrzeno/', loc)}"
    template_name = DOI_TEMPLATE_NAMES[loc]

    current = show_list(api_key, list_id)
    list_info = current.get("list") if isinstance(current.get("list"), dict) else current

    list_payload: dict[str, Any] = {
        "conf_subject": subject,
        "conf_message": html,
        "sub_confirmed_page": confirm_redirect_url,
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
        "locale": loc,
        "list_id": list_id,
        "subject": subject,
        "confirm_redirect_url": confirm_redirect_url,
        "html_bytes": len(html.encode("utf-8")),
        "has_subconfirm": True,
        "current_double_optin": list_info.get("double_optin"),
        "list_update": preview_payload if not apply else {
            k: v for k, v in list_payload.items() if k != "conf_message"
        },
    }

    if sync_template:
        templates = list_templates(api_key)
        template_id = _find_template_id(templates, template_name)
        result["template_name"] = template_name
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
                name=template_name,
                html=html,
            )
            result["ecomail_template"] = updated_tpl
        else:
            created_tpl = create_template(
                api_key,
                name=template_name,
                html=html,
            )
            result["ecomail_template"] = created_tpl

    result["synced"] = True
    result["plain_preview"] = plain
    return result
