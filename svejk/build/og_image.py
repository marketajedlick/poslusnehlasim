"""Generování sdílecích obrázků (Open Graph) pro vydání."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from svejk.build.seo import _edition_date_label, article_headline
from svejk.locale import localized_path, normalize_locale

_STATIC = Path(__file__).resolve().parent.parent / "static"
_SVEJK_ICON = _STATIC / "svejk-terra.png"

OG_WIDTH = 1200
OG_HEIGHT = 630

_PAPER = "#f0e6cf"
_INK = "#211c14"
_INK_SOFT = "#5a503e"
_TERRA = "#cf5a31"
_BORDER = "#ded0ad"


def datum_unl_to_iso(datum_unl: str) -> str:
    return datetime.strptime(datum_unl, "%d.%m.%Y").strftime("%Y-%m-%d")


def og_image_filename(datum_unl: str) -> str:
    return f"{datum_unl_to_iso(datum_unl)}.png"


def og_image_href(base_path: str, datum_unl: str, *, locale: str = "cs") -> str:
    base = base_path.rstrip("/")
    rel = localized_path(f"/og/{og_image_filename(datum_unl)}", locale)
    return f"{base}{rel}" if base else rel


def og_image_abs_url(site_url: str, base_path: str, datum_unl: str, *, locale: str = "cs") -> str:
    return f"{site_url.rstrip('/')}{og_image_href(base_path, datum_unl, locale=locale)}"


def edition_og_title(datum_unl: str, den: str = "", *, locale: str = "cs") -> str:
    return f"Poslušně hlásím · {_edition_date_label(datum_unl, den, locale=locale)}"


def edition_og_headline(
    *,
    dnesni_ucet: str,
    first_item_nadpis: str = "",
    datum_unl: str,
    den: str = "",
    locale: str = "cs",
) -> str:
    return article_headline(
        dnesni_ucet=dnesni_ucet,
        first_item_nadpis=first_item_nadpis,
        edition_title=edition_og_title(datum_unl, den, locale=locale),
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


def _load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    preferred = (
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSerif.ttf",
        "LiberationSans-Bold.ttf" if bold else "LiberationSerif-Regular.ttf",
        "Arial Bold.ttf" if bold else "Georgia.ttf",
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
    locale: str = "cs",
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
        score_prefix = "Match score" if normalize_locale(locale) == "en" else "Skóre dne"
        score_text = f"{score_prefix} {score}"
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


def render_edition_og_image(
    dest_dir: Path | str,
    *,
    datum_unl: str,
    den: str = "",
    dnesni_ucet: str = "",
    first_item_nadpis: str = "",
    proslo: int = 0,
    zamitnuto: int = 0,
    locale: str = "cs",
) -> Path:
    loc = normalize_locale(locale)
    headline = edition_og_headline(
        dnesni_ucet=dnesni_ucet,
        first_item_nadpis=first_item_nadpis,
        datum_unl=datum_unl,
        den=den,
        locale=loc,
    )
    score = f"{proslo}:{zamitnuto}" if proslo or zamitnuto else ""
    return render_og_image(
        Path(dest_dir) / og_image_filename(datum_unl),
        date_label=_edition_date_label(datum_unl, den, locale=loc),
        headline=headline,
        score=score,
        locale=loc,
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
