"""Stažení a aktualizace UNL hlasování z open dat PSP (hl-{obdobi}ps.zip)."""

from __future__ import annotations

import io
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def unl_zip_url(obdobi: int) -> str:
    return f"https://www.psp.cz/eknih/cdrom/opendata/hl-{obdobi}ps.zip"


def unl_dir(data_dir: Path, obdobi: int) -> Path:
    return data_dir / f"hl-{obdobi}ps"


def hl_soubor(data_dir: Path, obdobi: int) -> Path:
    return unl_dir(data_dir, obdobi) / f"hl{obdobi}s.unl"


def head_unl_zip(obdobi: int, *, timeout: float = 60.0) -> dict[str, Any]:
    """Metadata ZIPu bez stažení těla (Last-Modified, ETag, Content-Length)."""
    url = unl_zip_url(obdobi)
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {
                "url": url,
                "status": resp.status,
                "etag": resp.headers.get("ETag", "").strip('"'),
                "last_modified": resp.headers.get("Last-Modified", ""),
                "content_length": int(resp.headers.get("Content-Length") or 0),
            }
    except urllib.error.HTTPError as e:
        raise OSError(f"HEAD {url} → HTTP {e.code}") from e


def _unl_changed(
    remote: dict[str, Any],
    local_meta: dict[str, Any] | None,
    hl_path: Path,
    *,
    force: bool,
) -> bool:
    if force:
        return True
    if not hl_path.is_file():
        return True
    if not local_meta:
        return True
    if remote.get("etag") and local_meta.get("etag") == remote.get("etag"):
        return False
    if (
        remote.get("last_modified")
        and local_meta.get("last_modified") == remote.get("last_modified")
        and remote.get("content_length") == local_meta.get("content_length")
    ):
        return False
    return True


def _count_unl_lines(path: Path) -> int:
    if not path.is_file():
        return 0
    count = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            count += chunk.count(b"\n")
    return count


def unl_needs_refresh(
    obdobi: int,
    data_dir: Path,
    local_meta: dict[str, Any] | None = None,
    *,
    force: bool = False,
) -> tuple[dict[str, Any], bool]:
    remote = head_unl_zip(obdobi)
    hl_path = hl_soubor(data_dir, obdobi)
    return remote, _unl_changed(remote, local_meta, hl_path, force=force)


def refresh_unl(
    obdobi: int,
    data_dir: Path,
    *,
    local_meta: dict[str, Any] | None = None,
    force: bool = False,
    timeout: float = 120.0,
    verbose: bool = True,
) -> dict[str, Any]:
    """
    Stáhne hl-{obdobi}ps.zip a rozbalí jen hl{obdobi}s.unl (souhrnné hlasování schůzí).
    Vrací metadata včetně changed=True/False.
    """
    remote_head = head_unl_zip(obdobi, timeout=timeout)
    out_dir = unl_dir(data_dir, obdobi)
    hl_path = hl_soubor(data_dir, obdobi)
    changed = _unl_changed(remote_head, local_meta, hl_path, force=force)

    if not changed:
        if verbose:
            print(f"UNL {hl_path.name} beze změny ({remote_head.get('last_modified')})", flush=True)
        return {
            "changed": False,
            "path": str(hl_path),
            "lines": _count_unl_lines(hl_path),
            **remote_head,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    url = remote_head["url"]
    if verbose:
        print(f"Stahuji {url} …", flush=True)
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        raise OSError(f"GET {url} → HTTP {e.code}") from e

    member = f"hl{obdobi}s.unl"
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        if member not in names:
            raise OSError(f"V ZIPu chybí {member}, obsah: {names[:8]}")
        out_dir.mkdir(parents=True, exist_ok=True)
        hl_path.write_bytes(zf.read(member))

    lines = _count_unl_lines(hl_path)
    if verbose:
        print(f"UNL aktualizováno: {hl_path} ({lines} řádků)", flush=True)

    return {
        "changed": True,
        "path": str(hl_path),
        "lines": lines,
        **remote_head,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
