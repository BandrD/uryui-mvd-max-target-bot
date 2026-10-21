from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    max_bot_token: str = Field(default="", alias="MAX_BOT_TOKEN")
    max_mode: Literal["polling", "webhook"] = Field(default="polling", alias="MAX_MODE")
    max_webhook_secret: str = Field(default="", alias="MAX_WEBHOOK_SECRET")
    max_webhook_host: str = Field(default="0.0.0.0", alias="MAX_WEBHOOK_HOST")
    max_webhook_port: int = Field(default=8080, alias="MAX_WEBHOOK_PORT")
    max_root_ca_path: Path = Field(
        default=ROOT_DIR / "deploy" / "russian_trusted_root_ca.pem",
        alias="MAX_ROOT_CA_PATH",
    )
    max_api_base: str = Field(
        default="https://platform-api2.max.ru",
        alias="MAX_API_BASE",
    )

    gigachat_enabled: bool = Field(default=False, alias="GIGACHAT_ENABLED")
    gigachat_credentials: str = Field(default="", alias="GIGACHAT_CREDENTIALS")
    gigachat_scope: str = Field(default="GIGACHAT_API_PERS", alias="GIGACHAT_SCOPE")

    storage_path: Path = Field(default=ROOT_DIR / "data", alias="STORAGE_PATH")
    assets_path: Path = Field(default=ROOT_DIR / "assets")
    sector_map_path: Path = Field(default=ROOT_DIR / "assets" / "sector_map.json")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Изменение к п. 0.8 плана: до согласования с заказчиком — warn (отчёт + предупреждение)
    over_limit_policy: Literal["warn", "reject"] = Field(
        default="warn",
        alias="OVER_LIMIT_POLICY",
    )
    max_new_holes: int = 4

    @property
    def gigachat_ready(self) -> bool:
        return bool(self.gigachat_enabled and self.gigachat_credentials.strip())

    @property
    def max_ready(self) -> bool:
        return bool(self.max_bot_token.strip())


def get_settings() -> Settings:
    return Settings()
