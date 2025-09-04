from __future__ import annotations

from pathlib import Path

from schemas.enums import IMAGE_EXTS


def html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def collect_images(folder: Path) -> list[Path]:
    imgs: list[Path] = []
    for f in sorted(folder.iterdir(), key=lambda x: x.name.lower()):
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
            imgs.append(f)
    return imgs
