"""Accessibility guardrails for design tokens."""

from __future__ import annotations


def _relative_luminance(hex_color: str) -> float:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))

    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = channel(r), channel(g), channel(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(foreground: str, background: str) -> float:
    l1 = _relative_luminance(foreground)
    l2 = _relative_luminance(background)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def test_muted_text_meets_wcag_aa_on_cream() -> None:
    # --muted on --cream must pass WCAG AA for normal text (4.5:1).
    assert contrast_ratio("#706a62", "#f7f2f0") >= 4.5


def test_edition_spa_updates_head_meta() -> None:
    from pathlib import Path

    scripts = Path("svejk/templates/edition-scripts.html").read_text(encoding="utf-8")
    assert "applyHeadMeta" in scripts
    assert "headMetaFromDoc" in scripts
