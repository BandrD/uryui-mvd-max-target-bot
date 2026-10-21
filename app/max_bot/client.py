from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from app.ssl_util import build_ssl_context

logger = logging.getLogger(__name__)

MAX_TEXT_LIMIT = 4000


class RateLimiter:
    """Простой token-bucket (~30 rps глобально)."""

    def __init__(self, rps: float = 25.0) -> None:
        self.rate = rps
        self.tokens = rps
        self.last = time.monotonic()
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                self.tokens = min(self.rate, self.tokens + (now - self.last) * self.rate)
                self.last = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                await asyncio.sleep((1 - self.tokens) / self.rate)


class MaxClient:
    def __init__(
        self,
        token: str,
        base_url: str = "https://platform-api2.max.ru",
        ca_path: Path | None = None,
        timeout: float = 60.0,
    ) -> None:
        if not token:
            raise ValueError("MAX_BOT_TOKEN пуст")
        self.token = token
        self.base_url = base_url.rstrip("/")
        self._limiter = RateLimiter()
        ssl_ctx = build_ssl_context(ca_path)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": token},
            timeout=timeout,
            verify=ssl_ctx,
        )
        # Загрузки файлов с CDN (Let's Encrypt / HARICA) — отдельный клиент
        self._plain = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()
        await self._plain.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        await self._limiter.wait()
        resp = await self._client.request(method, path, params=params, json=json)
        if resp.status_code >= 400:
            logger.error("MAX API %s %s -> %s %s", method, path, resp.status_code, resp.text[:500])
            resp.raise_for_status()
        if not resp.content:
            return {}
        return resp.json()

    async def get_me(self) -> dict[str, Any]:
        return await self._request("GET", "/me")

    async def get_updates(
        self,
        marker: int | None = None,
        *,
        limit: int = 100,
        timeout: int = 30,
        types: str | None = None,
    ) -> tuple[list[dict[str, Any]], int | None]:
        params: dict[str, Any] = {"limit": limit, "timeout": timeout}
        if marker is not None:
            params["marker"] = marker
        if types:
            params["types"] = types
        data = await self._request("GET", "/updates", params=params)
        updates = data.get("updates") or []
        return updates, data.get("marker")

    async def send_message(
        self,
        *,
        chat_id: int | None = None,
        user_id: int | None = None,
        text: str | None = None,
        format: str | None = "markdown",
        attachments: list[dict[str, Any]] | None = None,
        notify: bool = True,
        disable_link_preview: bool = True,
    ) -> dict[str, Any]:
        if chat_id is None and user_id is None:
            raise ValueError("нужен chat_id или user_id")
        params: dict[str, Any] = {"disable_link_preview": str(disable_link_preview).lower()}
        if chat_id is not None:
            params["chat_id"] = chat_id
        if user_id is not None:
            params["user_id"] = user_id
        body: dict[str, Any] = {"notify": notify}
        if text is not None:
            body["text"] = text[:MAX_TEXT_LIMIT]
        if format:
            body["format"] = format
        if attachments is not None:
            body["attachments"] = attachments
        return await self._request("POST", "/messages", params=params, json=body)

    async def answer_callback(
        self,
        callback_id: str,
        *,
        notification: str | None = None,
        message: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if notification is not None:
            body["notification"] = notification
        if message is not None:
            body["message"] = message
        return await self._request(
            "POST",
            "/answers",
            params={"callback_id": callback_id},
            json=body or {"notification": "OK"},
        )

    async def upload_image(self, data: bytes, filename: str = "image.jpg") -> dict[str, Any]:
        """POST /uploads?type=image → upload binary → attachment payload."""
        meta = await self._request("POST", "/uploads", params={"type": "image"})
        url = meta["url"]
        token = meta.get("token")

        await self._limiter.wait()
        # multipart на upload-host
        files = {"data": (filename, data, "image/jpeg")}
        up = await self._plain.post(url, files=files)
        up.raise_for_status()
        try:
            up_json = up.json()
        except Exception:
            up_json = {}

        # Разные ответы upload-host; собираем token
        photo_token = token
        if isinstance(up_json, dict):
            if "token" in up_json:
                photo_token = up_json["token"]
            photos = up_json.get("photos")
            if isinstance(photos, dict) and photos:
                first = next(iter(photos.values()))
                if isinstance(first, dict) and first.get("token"):
                    photo_token = first["token"]

        if not photo_token:
            raise RuntimeError(f"upload image: нет token в ответе: {up_json!r}")

        return await self._send_image_with_retry(photo_token)

    async def _send_image_with_retry(self, token: str) -> dict[str, Any]:
        """Возвращает attachment-объект; готовность проверяется при send."""
        return {"type": "image", "payload": {"token": token}}

    async def send_text_and_image(
        self,
        chat_id: int,
        text: str,
        image_bytes: bytes,
        *,
        format: str = "markdown",
    ) -> None:
        """MAX не умеет inline media — сначала картинка, затем текст."""
        attachment = None
        last_err: Exception | None = None
        for attempt in range(4):
            try:
                if attachment is None:
                    attachment = await self.upload_image(image_bytes, "result.jpg")
                await self.send_message(
                    chat_id=chat_id,
                    text=None,
                    attachments=[attachment],
                    format=None,
                )
                last_err = None
                break
            except httpx.HTTPStatusError as exc:
                last_err = exc
                body = exc.response.text.lower() if exc.response is not None else ""
                if "attachment.not.ready" in body or exc.response.status_code in (400, 409):
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                raise
        if last_err:
            raise last_err

        # Текст отдельным сообщением (с нарезкой снаружи)
        if text:
            await self.send_message(chat_id=chat_id, text=text, format=format)

    async def download_url(self, url: str) -> bytes:
        resp = await self._plain.get(url)
        resp.raise_for_status()
        return resp.content
