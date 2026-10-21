from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Позволяет запускать `python -m app.main` из корня проекта
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.llm.gigachat_client import GigaChatClient
from app.logging_setup import setup_logging
from app.max_bot.client import MaxClient
from app.max_bot.handlers import BotApp
from app.max_bot.polling import run_polling
from app.storage.store import Storage

logger = logging.getLogger(__name__)


def build_app() -> tuple[BotApp, MaxClient, GigaChatClient | None]:
    settings = get_settings()
    setup_logging(settings.log_level)
    storage = Storage(settings.storage_path)

    if not settings.max_ready:
        raise SystemExit(
            "MAX_BOT_TOKEN не задан. Скопируйте .env.example → .env и укажите токен "
            "(business.max.ru → Чат-боты)."
        )

    client = MaxClient(
        token=settings.max_bot_token,
        base_url=settings.max_api_base,
        ca_path=settings.max_root_ca_path,
    )
    gigachat = GigaChatClient(
        credentials=settings.gigachat_credentials,
        scope=settings.gigachat_scope,
        enabled=settings.gigachat_enabled,
    )
    if not gigachat.ready:
        logger.warning("GigaChat выключен — текстовые ответы только из FAQ")

    bot = BotApp(settings, client, storage, gigachat if gigachat.ready else None)
    return bot, client, gigachat


async def run_polling_mode() -> None:
    bot, client, gigachat = build_app()
    try:
        await run_polling(bot, client)
    finally:
        await client.aclose()
        if gigachat is not None:
            await gigachat.aclose()


def run_webhook_mode() -> None:
    import uvicorn

    from app.max_bot.webhook import create_webhook_app

    settings = get_settings()
    bot, client, gigachat = build_app()
    api = create_webhook_app(bot, settings.max_webhook_secret)

    @api.on_event("shutdown")
    async def _shutdown() -> None:
        await client.aclose()
        if gigachat is not None:
            await gigachat.aclose()

    uvicorn.run(
        api,
        host=settings.max_webhook_host,
        port=settings.max_webhook_port,
        log_level=settings.log_level.lower(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="УрЮИ МВД MAX target bot")
    parser.add_argument(
        "--mode",
        choices=["polling", "webhook"],
        default=None,
        help="Переопределить MAX_MODE из .env",
    )
    args = parser.parse_args()
    settings = get_settings()
    mode = args.mode or settings.max_mode
    if mode == "webhook":
        run_webhook_mode()
    else:
        asyncio.run(run_polling_mode())


if __name__ == "__main__":
    main()
