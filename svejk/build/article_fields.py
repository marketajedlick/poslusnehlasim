"""Textová pole článku (DenItem / facts/by_topic) na jednom místě.

Dřív byl seznam ručně opsaný na ~8 místech a e-mail, glosář i steno odkazy
vynechávaly pointa_end, pointa_close a citace3/4.
"""

ARTICLE_PROSE_FIELDS = (
    "lead",
    "lead_tail",
    "pointa",
    "pointa_tail",
    "pointa_end",
    "pointa_close",
    "mean",
    "kuriozita",
)
ARTICLE_CITACE_PREFIXES = ("citace", "citace2", "citace3", "citace4")
ARTICLE_CITACE_FIELDS = tuple(f"{p}_text" for p in ARTICLE_CITACE_PREFIXES)
ARTICLE_TEXT_FIELDS = ARTICLE_PROSE_FIELDS + ARTICLE_CITACE_FIELDS
