from pathlib import Path

from PIL import Image

from svejk.build.og_image import (
    OG_CACHE_VERSION,
    OG_HEIGHT,
    OG_WIDTH,
    SHARE_HERO_HEIGHT,
    SHARE_HERO_WIDTH,
    og_image_abs_url,
    render_og_image,
    render_share_hero_image,
)


def test_render_og_image_dimensions(tmp_path: Path) -> None:
    out = render_og_image(
        tmp_path / "og.png",
        date_label="Pátek 13. 2. 2026",
        zaver_key="Poslušně hlásím, že",
        quote_body=(
            "bojiště zůstává bojištěm, jen se v něm bude méně mluvit, "
            "a že výbory si mezi sebou poslanci umí přeskládat rychleji, "
            "než stihnete říct rezignace."
        ),
    )
    with Image.open(out) as img:
        assert img.size == (OG_WIDTH, OG_HEIGHT)
        assert img.getpixel((0, 0)) == (247, 242, 240)
        # žlutá karta uprostřed, ne celé plátno
        assert img.getpixel((OG_WIDTH // 2, OG_HEIGHT // 2)) == (244, 196, 48)


def test_og_image_abs_url_cache_bust() -> None:
    url = og_image_abs_url("https://poslusnehlasim.cz", "", "13.02.2026")
    assert url.endswith(f"2026-02-13.png?v={OG_CACHE_VERSION}")


def test_render_share_hero_dimensions(tmp_path: Path) -> None:
    out = render_share_hero_image(
        tmp_path / "share.png",
        zaver_key="Poslušně hlásím, že",
        quote_body="sněmovna dnes zase něco schválila",
    )
    with Image.open(out) as img:
        assert img.size == (SHARE_HERO_WIDTH, SHARE_HERO_HEIGHT)
        assert img.getpixel((0, 0)) == (244, 196, 48)
