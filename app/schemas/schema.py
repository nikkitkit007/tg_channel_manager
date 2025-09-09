from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, field_validator, field_serializer, ConfigDict

from config.settings import TZ


class ScheduledPost(BaseModel):
    """Запись о запланированной публикации."""

    token: str  # токен поста (связывается с папкой)
    folder: Path  # путь к папке поста
    channel: int | str  # канал (@name или -100...)
    run_at: datetime  # UTC!

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="ignore",
    )

    @field_validator("run_at")
    @classmethod
    def _ensure_aware_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            # считаем, что пришло UTC-наивное; делаем UTC-aware
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @field_serializer("folder")
    def _ser_folder(self, v: Path, _info):
        return str(v)

    @field_serializer("run_at")
    def _ser_run_at(self, v: datetime, _info):
        # компактный ISO (UTC)
        return v.astimezone(timezone.utc).isoformat()

    def format_run_at(self) -> str:
        local = self.run_at.astimezone(TZ)
        return f"{local:%Y-%m-%d %H:%M} ({TZ.key}), UTC: {self.run_at:%Y-%m-%d %H:%M}"
