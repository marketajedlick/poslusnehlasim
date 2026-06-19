from datetime import datetime, timezone
from pathlib import Path

from svejk.build.seo import write_security_txt


def test_write_security_txt(tmp_path: Path) -> None:
    path = write_security_txt(
        tmp_path,
        site_url="https://poslusnehlasim.cz",
        expires=datetime(2027, 6, 19, tzinfo=timezone.utc),
    )
    assert path == tmp_path / ".well-known" / "security.txt"
    text = path.read_text(encoding="utf-8")
    assert "Contact: mailto:svejk@poslusnehlasim.cz" in text
    assert "Canonical: https://poslusnehlasim.cz/.well-known/security.txt" in text
    assert "Expires: 2027-06-19T00:00:00Z" in text
