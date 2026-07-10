from pathlib import Path

from PIL import Image

from svejk.build.og_image import (
    OG_HEIGHT,
    OG_WIDTH,
    SHARE_HERO_HEIGHT,
    SHARE_HERO_WIDTH,
    render_og_image,
    render_share_hero_image,
)


def test_render_og_image_dimensions(tmp_path: Path) -> None:
    out = render_og_image(
        tmp_path / "og.png",
        date_label="Úterý 8. 7. 2026",
        headline="Sněmovna zase něco schválila",
        score="3:1",
    )
    with Image.open(out) as img:
        assert img.size == (OG_WIDTH, OG_HEIGHT)
        assert img.getpixel((0, 0)) == (247, 242, 240)


def test_render_share_hero_dimensions(tmp_path: Path) -> None:
    out = render_share_hero_image(
        tmp_path / "share.png",
        zaver_key="Poslušně hlásím, že",
        quote_body="sněmovna dnes zase něco schválila",
    )
    with Image.open(out) as img:
        assert img.size == (SHARE_HERO_WIDTH, SHARE_HERO_HEIGHT)
        assert img.getpixel((0, 0)) == (244, 196, 48)
