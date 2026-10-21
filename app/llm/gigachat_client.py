from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты помощник чат-бота УрЮИ МВД по анализу грудной мишени №4. "
    "Отвечай кратко по-русски. Помогай только с правилами съёмки, работой бота, "
    "пробитиями и секторами. Не выдумывай координаты попаданий и не анализируй фото. "
    "Если вопрос не по теме — вежливо откажись."
)


@dataclass
class GigaReply:
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class GigaChatClient:
    """Минимальный клиент GigaChat. Без credentials считается выключенным."""

    def __init__(
        self,
        credentials: str,
        scope: str = "GIGACHAT_API_PERS",
        *,
        enabled: bool = True,
    ) -> None:
        self.credentials = credentials.strip()
        self.scope = scope
        self.enabled = enabled and bool(self.credentials)
        self._token: str | None = None
        self._client = httpx.AsyncClient(timeout=60.0)

    @property
    def ready(self) -> bool:
        return self.enabled

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _ensure_token(self) -> str:
        if self._token:
            return self._token
        # Официальный OAuth GigaChat
        resp = await self._client.post(
            "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
            headers={
                "Authorization": f"Basic {self.credentials}",
                "RqUID": str(uuid4()),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"scope": self.scope},
            # Контур Сбера: в проде лучше системные CA; verify оставляем True
        )
        if resp.status_code >= 400:
            logger.error("GigaChat oauth failed: %s %s", resp.status_code, resp.text[:300])
            resp.raise_for_status()
        self._token = resp.json()["access_token"]
        return self._token

    async def ask(self, user_text: str) -> GigaReply:
        if not self.ready:
            raise RuntimeError("GigaChat выключен")
        token = await self._ensure_token()
        payload: dict[str, Any] = {
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            "temperature": 0.2,
        }
        resp = await self._client.post(
            "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        if resp.status_code == 401:
            self._token = None
            token = await self._ensure_token()
            resp = await self._client.post(
                "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
        if resp.status_code >= 400:
            logger.error("GigaChat chat failed: %s %s", resp.status_code, resp.text[:300])
            resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        return GigaReply(
            text=text,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )
