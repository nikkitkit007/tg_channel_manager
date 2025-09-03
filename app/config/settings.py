import tempfile
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


file_args = {
    "env_file": (".env",),
    "env_file_encoding": "utf-8",
    "extra": "ignore",
}

NOT_SET = "NOT SET"


class AppSettings(BaseSettings):
    NAME: str = "offers-refinement"
    VERSION: str = "0.1.0"

    model_config = SettingsConfigDict(env_prefix="APP_", **file_args)


class LogSettings(BaseSettings):
    ECS_FORMAT: bool = False
    LEVEL: str = "INFO"
    ALCHEMY: str = "NOTSET"

    model_config = SettingsConfigDict(env_prefix="LOG_", **file_args)


class TGBotSettings(BaseSettings):
    BOT_TOKEN: str = None
    ADMIN_CHAT_ID: int = None
    CHANNEL_ID: str = None
    POSTS_ROOT: str = None
    SCAN_INTERVAL: int = None

    model_config = SettingsConfigDict(env_prefix="TGBOT", **file_args)


class Settings(BaseSettings):
    APP: AppSettings
    LOG: LogSettings
    TGBOT: TGBotSettings

    IN_DATA_DIR: str = str(Path(tempfile.gettempdir()) / "posts_data")


settings = Settings(APP=AppSettings(), LOG=LogSettings(), TGBOT=TGBotSettings())
