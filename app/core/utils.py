from __future__ import annotations

from pathlib import Path

from config.logger import get_logger
from schemas.enums import IMAGE_EXTS

log = get_logger(__name__)


def html_escape(s: str | list) -> str:
    if isinstance(s, list):
        s = ", ".join(map(str, s))
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def collect_images(folder: Path) -> list[Path]:
    imgs: list[Path] = []
    for f in sorted(folder.iterdir(), key=lambda x: x.name.lower()):
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
            imgs.append(f)
    return imgs


def create_path_if_not_exists(path: Path) -> None:
    if not path.exists():
        log.info(f"Папка {path} не существует. Создаю...")
        path.mkdir(parents=True, exist_ok=True)

    elif not path.is_dir():
        raise SystemExit(f"POSTS_ROOT {path} не является директорией.")
