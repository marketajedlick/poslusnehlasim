"""Generování sdílecích obrázků (Open Graph) pro vydání."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from svejk.build.seo import SITE_NAME, _edition_date_label, article_headline

_STATIC = Path(__file__).resolve().parent.parent / "static"
_BRAND_ICON = _STATIC / "ph-fav.png"
_SIGN_DEFAULT = "- Váš dobrý voják Švejk -"
_SITE_FOOTER = "www.poslusnehlasim.cz"
_CARD_RADIUS = 6
_HERO_ICON_SIZE = 56
_OG_ICON_SIZE = 80
_OG_SIGN_SIZE = 24
_SHARE_HERO_ICON_SIZE = 120
_SHARE_HERO_SIGN_SIZE = 30
_SHARE_BTN_SIZE = 28

OG_WIDTH = 1200
OG_HEIGHT = 630
# Bump při vizuální změně OG — sociální sítě cacheují obrázek podle URL.
OG_CACHE_VERSION = "hero-card-2"

# Čtverec odpovídá hero kartě na mobilu; ruční nahrání na X vypadá lépe než 1200×630.
# OG zůstává landscape pro twitter:card / og:image u odkazu na vydání.
SHARE_HERO_WIDTH = 1080
SHARE_HERO_HEIGHT = 1080

_CREAM = "#f7f2f0"
_CHAR = "#262626"
_INK = "#6b6355"
_YELLOW = "#f4c430"


def datum_unl_to_iso(datum_unl: str) -> str:
    return datetime.strptime(datum_unl, "%d.%m.%Y").strftime("%Y-%m-%d")


def og_image_filename(datum_unl: str) -> str:
    return f"{datum_unl_to_iso(datum_unl)}.png"


def og_image_href(base_path: str, datum_unl: str, *, version: str = OG_CACHE_VERSION) -> str:
    base = base_path.rstrip("/")
    rel = f"/og/{og_image_filename(datum_unl)}?v={version}"
    return f"{base}{rel}" if base else rel


def og_image_abs_url(
    site_url: str,
    base_path: str,
    datum_unl: str,
    *,
    version: str = OG_CACHE_VERSION,
) -> str:
    return f"{site_url.rstrip('/')}{og_image_href(base_path, datum_unl, version=version)}"


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
    nadpis_vydani: str = "",
    first_item_nadpis: str = "",
    datum_unl: str,
    den: str = "",
) -> str:
    return article_headline(
        dnesni_ucet=dnesni_ucet,
        nadpis_vydani=nadpis_vydani,
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
    size: int,
    *,
    bold: bool = False,
    italic: bool = False,
    sans: bool = False,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if italic:
        preferred = (
            "DejaVuSerif-Italic.ttf",
            "LiberationSerif-Italic.ttf",
            "Georgia Italic.ttf",
            "DejaVuSerif.ttf",
        )
    elif bold and sans:
        preferred = (
            "DejaVuSans-Bold.ttf",
            "LiberationSans-Bold.ttf",
            "Arial Bold.ttf",
            "DejaVuSans.ttf",
        )
    elif bold:
        preferred = (
            "DejaVuSerif-Bold.ttf",
            "LiberationSerif-Bold.ttf",
            "Georgia Bold.ttf",
            "DejaVuSerif.ttf",
        )
    elif sans:
        preferred = (
            "DejaVuSans.ttf",
            "LiberationSans-Regular.ttf",
            "Arial.ttf",
            "DejaVuSerif.ttf",
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


def _prepare_brand_icon(size: int) -> Image.Image | None:
    if not _BRAND_ICON.is_file():
        return None
    icon = Image.open(_BRAND_ICON).convert("RGBA")
    ratio = size / max(icon.width, icon.height)
    new_size = (max(1, int(icon.width * ratio)), max(1, int(icon.height * ratio)))
    return icon.resize(new_size, Image.Resampling.LANCZOS)


def _font_line_height(font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
    size = getattr(font, "size", 16)
    return max(16, int(size * 1.15))


def _compose_quote_text(
    *,
    zaver_key: str = "",
    quote_body: str = "",
    fallback: str = "",
) -> str:
    body = (quote_body or "").strip()
    if body:
        key = (zaver_key or "").strip()
        return f"{key} {body}".strip() if key else body
    return (fallback or "").strip()


def _apply_yellow_card(
    img: Image.Image,
    box: tuple[int, int, int, int],
    *,
    radius: int = _CARD_RADIUS,
) -> Image.Image:
    x0, y0, x1, y1 = box
    layered = img.convert("RGBA")
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh = ImageDraw.Draw(shadow)
    sh.rounded_rectangle((x0, y0 + 5, x1, y1 + 5), radius=radius, fill=(38, 38, 38, 38))
    layered = Image.alpha_composite(layered, shadow)
    card_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(card_layer)
    cd.rounded_rectangle(box, radius=radius, fill=_YELLOW)
    return Image.alpha_composite(layered, card_layer).convert("RGB")


def _draw_share_icon(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    *,
    size: int = _SHARE_BTN_SIZE,
) -> None:
    r = size / 2
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=_CHAR, width=2)
    scale = size / 28.0
    dots = ((18, 5), (6, 12), (18, 19))
    dot_r = 2.6 * scale
    px = [((cx + (x - 12) * scale), (cy + (y - 12) * scale)) for x, y in dots]
    for x, y in px:
        draw.ellipse((x - dot_r, y - dot_r, x + dot_r, y + dot_r), fill=_CHAR)
    draw.line((px[1][0] + dot_r, px[1][1], px[0][0] - dot_r, px[0][1]), fill=_CHAR, width=2)
    draw.line((px[1][0] + dot_r, px[1][1], px[2][0] - dot_r, px[2][1]), fill=_CHAR, width=2)


def _draw_quote_block(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    width: int,
    lines: list[str],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    mark_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    line_h: int,
) -> int:
    open_mark = "„"
    close_mark = "“"
    for i, line in enumerate(lines):
        prefix = open_mark if i == 0 else ""
        suffix = close_mark if i == len(lines) - 1 else ""
        cursor = x
        if prefix:
            draw.text((cursor, y - 6), prefix, fill=_CHAR, font=mark_font)
            cursor += int(draw.textlength(prefix, font=mark_font) * 0.55)
        draw.text((cursor, y), f"{line}{suffix}", fill=_CHAR, font=font)
        y += line_h
    return y


def _draw_card_footer(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    width: int,
    sign: str,
    fav: Image.Image | None,
    sign_size: int = 18,
    show_share: bool = True,
) -> None:
    sign_font = _load_font(sign_size, bold=True, sans=True)
    sign_text = sign.upper()
    sign_h = _font_line_height(sign_font)
    fav_h = fav.height if fav is not None else 0
    fav_gap = 18 if sign_size >= _OG_SIGN_SIZE else 14
    foot_h = max(sign_h, fav_h)
    foot_x = x
    if fav is not None:
        fav_y = y + max(0, (foot_h - fav.height) // 2)
        img.paste(fav, (foot_x, fav_y), fav)
        foot_x += fav.width + fav_gap
    sign_y = y + max(0, (foot_h - sign_h) // 2)
    draw.text((foot_x, sign_y), sign_text, fill=_CHAR, font=sign_font)
    if show_share:
        share_cx = x + width - _SHARE_BTN_SIZE // 2
        share_cy = y + foot_h // 2
        _draw_share_icon(draw, share_cx, share_cy)


def render_og_image(
    dest: Path | str,
    *,
    date_label: str,
    headline: str = "",
    zaver_key: str = "",
    quote_body: str = "",
    sign: str = _SIGN_DEFAULT,
) -> Path:
    """Vykreslí 1200×630 PNG ve stylu card-hero (krémové pozadí, žlutá karta)."""
    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (OG_WIDTH, OG_HEIGHT), _CREAM)
    probe = ImageDraw.Draw(img)

    outer_x = 80
    card_w = OG_WIDTH - outer_x * 2
    pad_x = 48
    pad_y = 40
    text_w = card_w - pad_x * 2
    footer_h = 44
    footer_gap = 28
    card_area_bottom = OG_HEIGHT - footer_h - footer_gap

    quote_text = _compose_quote_text(
        zaver_key=zaver_key,
        quote_body=quote_body,
        fallback=headline,
    )
    quote_font, quote_lines = _fit_font_size(
        probe,
        quote_text,
        text_w,
        start=34,
        min_size=22,
        max_lines=6,
    )
    mark_font = _load_font(max(44, int(getattr(quote_font, "size", 34) * 1.55)))
    line_h = max(32, int(getattr(quote_font, "size", 34) * 1.42))
    fav = _prepare_brand_icon(_OG_ICON_SIZE)
    sign_font = _load_font(_OG_SIGN_SIZE, bold=True, sans=True)
    sign_h = _font_line_height(sign_font)
    fav_h = fav.height if fav is not None else 0
    foot_h = max(sign_h, fav_h)
    quote_h = len(quote_lines) * line_h
    card_inner_h = pad_y + quote_h + 20 + foot_h + pad_y
    card_top = max(36, (card_area_bottom - card_inner_h) // 2)
    card_box = (outer_x, card_top, outer_x + card_w, card_top + card_inner_h)
    img = _apply_yellow_card(img, card_box)
    draw = ImageDraw.Draw(img)

    text_x = outer_x + pad_x
    y = card_top + pad_y
    y = _draw_quote_block(
        draw,
        x=text_x,
        y=y,
        width=text_w,
        lines=quote_lines,
        font=quote_font,
        mark_font=mark_font,
        line_h=line_h,
    )
    y += 20
    _draw_card_footer(
        img,
        draw,
        x=text_x,
        y=y,
        width=text_w,
        sign=sign,
        fav=fav,
        sign_size=_OG_SIGN_SIZE,
        show_share=False,
    )

    footer_font = _load_font(22, sans=True)
    footer_y = OG_HEIGHT - footer_h
    draw.text((outer_x, footer_y), _SITE_FOOTER, fill=_INK, font=footer_font)
    date_w = draw.textlength(date_label, font=footer_font)
    draw.text((OG_WIDTH - outer_x - date_w, footer_y), date_label, fill=_INK, font=footer_font)

    img.save(out, format="PNG", optimize=True)
    return out


def _fit_font_size(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    *,
    start: int,
    min_size: int,
    max_lines: int = 8,
    bold: bool = False,
    italic: bool = False,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str]]:
    """ponytail: jednoduché zmenšování fontu, ne přesný line-box."""
    size = start
    while size >= min_size:
        font = _load_font(size, bold=bold, italic=italic)
        lines = _wrap_text(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
        size -= 2
    font = _load_font(min_size, bold=bold, italic=italic)
    return font, _wrap_text(draw, text, font, max_width)[:max_lines]


def render_share_hero_image(
    dest: Path | str,
    *,
    zaver_key: str = "",
    quote_body: str,
    sign: str = _SIGN_DEFAULT,
) -> Path:
    """Vykreslí 1080×1080 žlutou hero kartu (card-hero na webu)."""
    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (SHARE_HERO_WIDTH, SHARE_HERO_HEIGHT), _YELLOW)
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        (0, SHARE_HERO_HEIGHT - 3, SHARE_HERO_WIDTH, SHARE_HERO_HEIGHT),
        fill="#d9b82e",
    )

    margin = 72
    text_x = margin
    text_width = SHARE_HERO_WIDTH - margin * 2
    quote_text = _compose_quote_text(zaver_key=zaver_key, quote_body=quote_body)
    quote_font, quote_lines = _fit_font_size(
        draw,
        quote_text,
        text_width,
        start=44,
        min_size=28,
    )
    mark_font = _load_font(max(56, int(getattr(quote_font, "size", 44) * 1.55)))
    line_h = max(40, int(getattr(quote_font, "size", 44) * 1.45))
    fav = _prepare_brand_icon(_SHARE_HERO_ICON_SIZE)
    sign_font = _load_font(_SHARE_HERO_SIGN_SIZE, bold=True, sans=True)
    sign_h = _font_line_height(sign_font)
    fav_h = fav.height if fav is not None else 0
    quote_h = len(quote_lines) * line_h
    foot_h = max(sign_h, fav_h)
    block_h = quote_h + 20 + foot_h
    y = max(margin, (SHARE_HERO_HEIGHT - block_h) // 2)

    y = _draw_quote_block(
        draw,
        x=text_x,
        y=y,
        width=text_width,
        lines=quote_lines,
        font=quote_font,
        mark_font=mark_font,
        line_h=line_h,
    )
    y += 20
    _draw_card_footer(
        img,
        draw,
        x=text_x,
        y=y,
        width=text_width,
        sign=sign,
        fav=fav,
        sign_size=_SHARE_HERO_SIGN_SIZE,
        show_share=False,
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
    nadpis_vydani: str = "",
    first_item_nadpis: str = "",
    zaver_key: str = "",
    zaver_body: str = "",
    zaver: str = "",
    sign: str = _SIGN_DEFAULT,
) -> Path:
    headline = edition_og_headline(
        dnesni_ucet=dnesni_ucet,
        nadpis_vydani=nadpis_vydani,
        first_item_nadpis=first_item_nadpis,
        datum_unl=datum_unl,
        den=den,
    )
    body = (zaver_body or zaver or "").strip()
    key = (zaver_key or "").strip()
    if body and not key and body.lower().startswith("poslušně hlásím"):
        from svejk.build.day_content import split_zaver

        key, body = split_zaver(body if not zaver_body else f"{zaver_key} {zaver_body}".strip())
    return render_og_image(
        Path(dest_dir) / og_image_filename(datum_unl),
        date_label=_edition_date_label(datum_unl, den),
        headline=headline if not body else "",
        zaver_key=key,
        quote_body=body,
        sign=sign,
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
        f'<meta property="og:image:secure_url" content="{og_image_url}" />',
        '<meta property="og:image:type" content="image/png" />',
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
            r'<meta property="og:image:secure_url"[^>]*>\n?',
            "",
            html,
        )
        html = re.sub(
            r'<meta property="og:image:type"[^>]*>\n?',
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
