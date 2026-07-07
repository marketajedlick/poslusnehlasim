"""Generování sdílecích obrázků (Open Graph) pro vydání."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from svejk.build.seo import SITE_NAME, _edition_date_label, article_headline

_STATIC = Path(__file__).resolve().parent.parent / "static"
_SVEJK_ICON = _STATIC / "svejk-terra.png"

OG_WIDTH = 1200
OG_HEIGHT = 630

# Čtverec odpovídá hero kartě na mobilu; ruční nahrání na X vypadá lépe než 1200×630.
# OG zůstává landscape pro twitter:card / og:image u odkazu na vydání.
SHARE_HERO_WIDTH = 1080
SHARE_HERO_HEIGHT = 1080

_PAPER = "#f7f2f0"
_INK = "#262626"
_INK_SOFT = "#6b6355"
_TERRA = "#ff4411"
_BORDER = "#c9c2ba"
_YELLOW = "#f4c430"


def datum_unl_to_iso(datum_unl: str) -> str:
    return datetime.strptime(datum_unl, "%d.%m.%Y").strftime("%Y-%m-%d")


def og_image_filename(datum_unl: str) -> str:
    return f"{datum_unl_to_iso(datum_unl)}.png"


def og_image_href(base_path: str, datum_unl: str) -> str:
    base = base_path.rstrip("/")
    rel = f"/og/{og_image_filename(datum_unl)}"
    return f"{base}{rel}" if base else rel


def og_image_abs_url(site_url: str, base_path: str, datum_unl: str) -> str:
    return f"{site_url.rstrip('/')}{og_image_href(base_path, datum_unl)}"


def share_hero_filename(datum_unl: str) -> str:
    return f"{datum_unl_to_iso(datum_unl)}.png"


def share_hero_href(base_path: str, datum_unl: str) -> str:
    base = base_path.rstrip("/")
    rel = f"/share/{share_hero_filename(datum_unl)}"
    return f"{base}{rel}" if base else rel


def share_hero_abs_url(site_url: str, base_path: str, datum_unl: str) -> str:
    return f"{site_url.rstrip('/')}{share_hero_href(base_path, datum_unl)}"


def edition_og_title(datum_unl: str, den: str = "") -> str:
    return f"{SITE_NAME} · {_edition_date_label(datum_unl, den)}"


def edition_og_headline(
    *,
    dnesni_ucet: str,
    first_item_nadpis: str = "",
    datum_unl: str,
    den: str = "",
) -> str:
    return article_headline(
        dnesni_ucet=dnesni_ucet,
        first_item_nadpis=first_item_nadpis,
        edition_title=edition_og_title(datum_unl, den),
        max_len=140,
    )


def _font_candidates() -> tuple[tuple[str, int], ...]:
    roots = (
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts/truetype/liberation",
        "/System/Library/Fonts/Supplemental",
        "/Library/Fonts",
    )
    names = (
        ("DejaVuSans-Bold.ttf", 72),
        ("DejaVuSans.ttf", 36),
        ("DejaVuSerif.ttf", 52),
        ("LiberationSans-Bold.ttf", 72),
        ("LiberationSans-Regular.ttf", 36),
        ("LiberationSerif-Regular.ttf", 52),
        ("Arial Bold.ttf", 72),
        ("Arial.ttf", 36),
        ("Georgia.ttf", 52),
        ("Helvetica.ttc", 72),
    )
    out: list[tuple[str, int]] = []
    for root in roots:
        for name, size in names:
            path = Path(root) / name
            if path.is_file():
                out.append((str(path), size))
    return tuple(out)


def _load_font(
    size: int, *, bold: bool = False, italic: bool = False
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if italic:
        preferred = (
            "DejaVuSerif-Italic.ttf",
            "LiberationSerif-Italic.ttf",
            "Georgia Italic.ttf",
            "DejaVuSerif.ttf",
        )
    elif bold:
        preferred = (
            "DejaVuSans-Bold.ttf",
            "LiberationSans-Bold.ttf",
            "Arial Bold.ttf",
            "DejaVuSans.ttf",
        )
    else:
        preferred = (
            "DejaVuSerif.ttf",
            "LiberationSerif-Regular.ttf",
            "Georgia.ttf",
            "DejaVuSans.ttf",
            "Arial.ttf",
        )
    for root in (
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts/truetype/liberation",
        "/System/Library/Fonts/Supplemental",
        "/Library/Fonts",
    ):
        for name in preferred:
            path = Path(root) / name
            if path.is_file():
                try:
                    return ImageFont.truetype(str(path), size)
                except OSError:
                    continue
    for path, _ in _font_candidates():
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _prepare_svejk_icon(size: int) -> Image.Image | None:
    if not _SVEJK_ICON.is_file():
        return None
    icon = Image.open(_SVEJK_ICON).convert("RGBA")
    pixels = icon.load()
    for y in range(icon.height):
        for x in range(icon.width):
            r, g, b, a = pixels[x, y]
            if r < 40 and g < 40 and b < 40:
                pixels[x, y] = (r, g, b, 0)
    ratio = size / max(icon.width, icon.height)
    new_size = (max(1, int(icon.width * ratio)), max(1, int(icon.height * ratio)))
    return icon.resize(new_size, Image.Resampling.LANCZOS)


def render_og_image(
    dest: Path | str,
    *,
    date_label: str,
    headline: str,
    score: str = "",
) -> Path:
    """Vykreslí 1200×630 PNG pro sdílení vydání."""
    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (OG_WIDTH, OG_HEIGHT), _PAPER)
    draw = ImageDraw.Draw(img)

    margin = 72
    draw.rectangle((24, 24, OG_WIDTH - 24, OG_HEIGHT - 24), outline=_BORDER, width=3)
    draw.rectangle((margin, margin + 118, margin + 220, margin + 122), fill=_TERRA)

    title_font = _load_font(58, bold=True)
    date_font = _load_font(34)
    headline_font = _load_font(46)
    score_font = _load_font(30, bold=True)
    site_font = _load_font(24)

    draw.text((margin, margin), "POSLUŠNĚ HLÁSÍM", fill=_TERRA, font=title_font)
    draw.text((margin, margin + 78), date_label, fill=_INK_SOFT, font=date_font)

    text_width = OG_WIDTH - margin * 2 - 220
    lines = _wrap_text(draw, headline, headline_font, text_width)[:3]
    y = margin + 170
    for line in lines:
        draw.text((margin, y), line, fill=_INK, font=headline_font)
        y += 58

    if score:
        score_text = f"Skóre dne {score}"
        score_w = draw.textlength(score_text, font=score_font)
        draw.text(
            (OG_WIDTH - margin - score_w, OG_HEIGHT - margin - 34),
            score_text,
            fill=_TERRA,
            font=score_font,
        )

    draw.text(
        (margin, OG_HEIGHT - margin - 34),
        "poslusnehlasim.cz",
        fill=_INK_SOFT,
        font=site_font,
    )

    icon = _prepare_svejk_icon(300)
    if icon is not None:
        x = OG_WIDTH - margin - icon.width
        y = margin + 10
        img.paste(icon, (x, y), icon)

    img.save(out, format="PNG", optimize=True)
    return out


def _fit_font_size(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    *,
    start: int,
    min_size: int,
    bold: bool = False,
    italic: bool = False,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str]]:
    """ponytail: jednoduché zmenšování fontu, ne přesný line-box."""
    size = start
    while size >= min_size:
        font = _load_font(size, bold=bold, italic=italic)
        lines = _wrap_text(draw, text, font, max_width)
        if len(lines) <= 8:
            return font, lines
        size -= 2
    font = _load_font(min_size, bold=bold, italic=italic)
    return font, _wrap_text(draw, text, font, max_width)[:8]


def render_share_hero_image(
    dest: Path | str,
    *,
    zaver_key: str = "",
    quote_body: str,
    sign: str = "- Váš dobrý voják Švejk -",
) -> Path:
    """Vykreslí 1080×1080 žlutou kartu s citací (v7 hero)."""
    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (SHARE_HERO_WIDTH, SHARE_HERO_HEIGHT), _YELLOW)
    draw = ImageDraw.Draw(img)

    margin = 72
    inner = 28
    draw.rectangle(
        (inner, inner, SHARE_HERO_WIDTH - inner, SHARE_HERO_HEIGHT - inner),
        outline=_BORDER,
        width=3,
    )

    text_width = SHARE_HERO_WIDTH - margin * 2
    key_font = _load_font(40, italic=True) if zaver_key else None
    quote_font, quote_lines = _fit_font_size(
        draw,
        f"„{quote_body}“",
        text_width,
        start=46,
        min_size=30,
    )

    sign_font = _load_font(24, bold=True)
    sign_text = sign.upper()
    sign_w = draw.textlength(sign_text, font=sign_font)
    sign_y = SHARE_HERO_HEIGHT - margin - 36

    key_h = 0
    if key_font and zaver_key:
        key_h = 52
    quote_h = len(quote_lines) * 58
    block_h = key_h + quote_h
    y = (sign_y - margin - block_h) // 2
    if y < margin:
        y = margin

    if key_font and zaver_key:
        draw.text((margin, y), zaver_key, fill=_INK, font=key_font)
        y += key_h

    line_h = max(44, int(quote_font.size * 1.35) if hasattr(quote_font, "size") else 58)
    for line in quote_lines:
        draw.text((margin, y), line, fill=_INK, font=quote_font)
        y += line_h

    draw.text(
        ((SHARE_HERO_WIDTH - sign_w) / 2, sign_y),
        sign_text,
        fill=_INK,
        font=sign_font,
    )

    img.save(out, format="PNG", optimize=True)
    return out


def render_edition_share_hero_image(
    dest_dir: Path | str,
    *,
    datum_unl: str,
    zaver_key: str = "",
    zaver_body: str = "",
    zaver: str = "",
    sign: str = "- Váš dobrý voják Švejk -",
) -> Path | None:
    body = (zaver_body or zaver or "").strip()
    if not body:
        return None
    key = (zaver_key or "").strip()
    if not key and body.lower().startswith("poslušně hlásím"):
        from svejk.build.day_content import split_zaver

        key, body = split_zaver(body if not zaver_body else f"{zaver_key} {zaver_body}".strip())
    return render_share_hero_image(
        Path(dest_dir) / share_hero_filename(datum_unl),
        zaver_key=key,
        quote_body=body,
        sign=sign,
    )


def render_edition_og_image(
    dest_dir: Path | str,
    *,
    datum_unl: str,
    den: str = "",
    dnesni_ucet: str = "",
    first_item_nadpis: str = "",
    proslo: int = 0,
    zamitnuto: int = 0,
) -> Path:
    headline = edition_og_headline(
        dnesni_ucet=dnesni_ucet,
        first_item_nadpis=first_item_nadpis,
        datum_unl=datum_unl,
        den=den,
    )
    score = f"{proslo}:{zamitnuto}" if proslo or zamitnuto else ""
    return render_og_image(
        Path(dest_dir) / og_image_filename(datum_unl),
        date_label=_edition_date_label(datum_unl, den),
        headline=headline,
        score=score,
    )


def og_meta_block(
    *,
    og_image_url: str,
    og_image_width: int = OG_WIDTH,
    og_image_height: int = OG_HEIGHT,
    og_image_alt: str,
    og_title: str | None = None,
) -> str:
    from html import escape

    alt = escape(og_image_alt, quote=True)
    title = escape(og_title, quote=True) if og_title else ""
    lines = [
        f'<meta property="og:image" content="{og_image_url}" />',
        f'<meta property="og:image:width" content="{og_image_width}" />',
        f'<meta property="og:image:height" content="{og_image_height}" />',
        f'<meta property="og:image:alt" content="{alt}" />',
        '<meta name="twitter:card" content="summary_large_image" />',
        f'<meta name="twitter:image" content="{og_image_url}" />',
        f'<meta name="twitter:image:alt" content="{alt}" />',
    ]
    if og_title:
        lines.extend(
            [
                f'<meta property="og:title" content="{title}" />',
                f'<meta name="twitter:title" content="{title}" />',
            ]
        )
    return "\n".join(lines) + "\n"


def inject_og_image(
    html: str,
    *,
    og_image_url: str,
    og_image_width: int = OG_WIDTH,
    og_image_height: int = OG_HEIGHT,
    og_image_alt: str,
    og_title: str | None = None,
) -> str:
    """Doplní nebo přepíše og:image v HTML (včetně snapshotů)."""
    import re

    block = og_meta_block(
        og_image_url=og_image_url,
        og_image_width=og_image_width,
        og_image_height=og_image_height,
        og_image_alt=og_image_alt,
        og_title=og_title,
    )

    if 'property="og:image"' in html:
        html = re.sub(
            r'<meta property="og:image"[^>]*>\n?',
            "",
            html,
        )
        html = re.sub(
            r'<meta property="og:image:width"[^>]*>\n?',
            "",
            html,
        )
        html = re.sub(
            r'<meta property="og:image:height"[^>]*>\n?',
            "",
            html,
        )
        html = re.sub(
            r'<meta property="og:image:alt"[^>]*>\n?',
            "",
            html,
        )
        html = re.sub(
            r'<meta name="twitter:card"[^>]*>\n?',
            "",
            html,
        )
        html = re.sub(
            r'<meta name="twitter:image"[^>]*>\n?',
            "",
            html,
        )
        html = re.sub(
            r'<meta name="twitter:image:alt"[^>]*>\n?',
            "",
            html,
        )
        if og_title:
            html = re.sub(
                r'<meta property="og:title"[^>]*>\n?',
                "",
                html,
            )
            html = re.sub(
                r'<meta name="twitter:title"[^>]*>\n?',
                "",
                html,
            )

    marker = '<meta property="og:url"'
    if marker in html:
        return html.replace(marker, block + marker, 1)

    marker = '<meta name="twitter:description"'
    if marker in html:
        return html.replace(marker, block + marker, 1)

    return html.replace("</head>", block + "</head>", 1)
