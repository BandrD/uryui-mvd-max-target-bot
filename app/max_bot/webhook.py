from __future__ import annotations

import hmac
import logging
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.max_bot.handlers import BotApp

logger = logging.getLogger(__name__)


def create_webhook_app(bot: BotApp, secret: str) -> FastAPI:
    api = FastAPI(title="УрЮИ МВД MAX Target Bot", version="0.1.0")

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/max/webhook")
    async def max_webhook(
        request: Request,
        x_max_bot_api_secret: str | None = Header(default=None, alias="X-Max-Bot-Api-Secret"),
    ) -> PlainTextResponse:
        if secret:
            if not x_max_bot_api_secret or not hmac.compare_digest(x_max_bot_api_secret, secret):
                raise HTTPException(status_code=401, detail="invalid secret")
        try:
            payload: dict[str, Any] = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="invalid json") from exc

        # Быстрый ack: обработка в фоне
        update = payload if "update_type" in payload else payload.get("update") or payload
        bot._spawn(bot.handle_update(update))
        return PlainTextResponse("ok", status_code=200)

    @api.exception_handler(Exception)
    async def on_error(_req: Request, exc: Exception) -> JSONResponse:
        logger.exception("webhook error: %s", exc)
        return JSONResponse({"error": "internal"}, status_code=500)

    return api
