import json
import os
from pathlib import Path

from app.config.settings import settings
from schemas.schema import ScheduledPost

SCHEDULE_FILE = settings.TGBOT.POSTS_ROOT / Path(".scheduled_posts.json")


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def load_all() -> dict[str, ScheduledPost]:
    """Вернёт {job_id: ScheduledPost}."""
    if not SCHEDULE_FILE.exists():
        return {}
    try:
        raw = json.loads(SCHEDULE_FILE.read_text("utf-8"))
    except Exception:
        return {}

    out: dict[str, ScheduledPost] = {}
    for job_id, payload in raw.items():
        try:
            out[job_id] = ScheduledPost.model_validate(payload)
        except Exception:
            continue
    return out


def save_all(data: dict[str, ScheduledPost]) -> None:
    raw = {k: v.model_dump() for k, v in data.items()}
    _atomic_write_text(SCHEDULE_FILE, json.dumps(raw, ensure_ascii=False, indent=2))


def add(job_id: str, item: ScheduledPost) -> None:
    store = load_all()
    store[job_id] = item
    save_all(store)


def pop(job_id: str) -> ScheduledPost | None:
    store = load_all()
    item = store.pop(job_id, None)
    save_all(store)
    return item


def get(job_id: str) -> ScheduledPost | None:
    return load_all().get(job_id)


def prune_missing_folders() -> tuple[int, int]:
    """Удаляет записи, чьи папки отсутствуют. Возвращает (удалено, осталось)."""
    store = load_all()
    removed = 0
    for job_id, item in list(store.items()):
        if not item.folder.exists():
            store.pop(job_id, None)
            removed += 1
    save_all(store)
    return removed, len(store)
