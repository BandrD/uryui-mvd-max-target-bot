from __future__ import annotations

import asyncio
import logging

from app.max_bot.client import MaxClient
from app.max_bot.handlers import BotApp

logger = logging.getLogger(__name__)


async def run_polling(app: BotApp, client: MaxClient) -> None:
    me = await client.get_me()
    logger.info("MAX bot online: %s", me.get("username") or me.get("user_id") or me)
    marker: int | None = None
    while True:
        try:
            updates, marker = await client.get_updates(marker, timeout=30)
            for update in updates:
                await app.handle_update(update)
            await asyncio.sleep(0.35)  # min interval ~300ms
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("polling loop error")
            await asyncio.sleep(2.0)
