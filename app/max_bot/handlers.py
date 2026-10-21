from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import Settings
from app.cv.pipeline import analyze_target
from app.llm.faq import HELP_TEXT
from app.llm.router import answer_text
from app.llm.text_split import split_text
from app.llm.gigachat_client import GigaChatClient
from app.max_bot.client import MaxClient
from app.max_bot.fsm import DialogState, SessionStore
from app.max_bot.keyboards import cancel_menu, main_menu
from app.storage.store import Storage

logger = logging.getLogger(__name__)


def _chat_id_from_message(message: dict[str, Any]) -> int | None:
    recipient = message.get("recipient") or {}
    chat_id = recipient.get("chat_id")
    if chat_id is not None:
        return int(chat_id)
    # dialog fallback
    sender = message.get("sender") or {}
    if sender.get("user_id") is not None:
        return int(sender["user_id"])
    return None


def _extract_image_url(message: dict[str, Any]) -> str | None:
    body = message.get("body") or {}
    for att in body.get("attachments") or []:
        if att.get("type") == "image":
            payload = att.get("payload") or {}
            url = payload.get("url")
            if url:
                return str(url)
    return None


class BotApp:
    def __init__(
        self,
        settings: Settings,
        client: MaxClient,
        storage: Storage,
        gigachat: GigaChatClient | None,
    ) -> None:
        self.settings = settings
        self.client = client
        self.storage = storage
        self.gigachat = gigachat
        self.sessions = SessionStore()
        self._bg: set[asyncio.Task[Any]] = set()

    def _spawn(self, coro: Any) -> None:
        task = asyncio.create_task(coro)
        self._bg.add(task)
        task.add_done_callback(self._bg.discard)

    async def send_chunks(self, chat_id: int, text: str, *, attachments: list | None = None) -> None:
        chunks = split_text(text)
        for i, chunk in enumerate(chunks):
            atts = attachments if i == 0 else None
            await self.client.send_message(
                chat_id=chat_id,
                text=chunk,
                format="markdown",
                attachments=atts,
            )

    async def send_welcome(self, chat_id: int) -> None:
        text = (
            "**Бот анализа мишени №4 (УрЮИ МВД)**\n\n"
            "Пришлите фото мишени или выберите действие:"
        )
        await self.client.send_message(
            chat_id=chat_id,
            text=text,
            format="markdown",
            attachments=[main_menu()],
        )
        self.sessions.set_state(chat_id, DialogState.IDLE)

    async def handle_update(self, update: dict[str, Any]) -> None:
        utype = update.get("update_type")
        try:
            if utype == "bot_started":
                chat_id = int(update["chat_id"])
                await self.send_welcome(chat_id)
            elif utype == "message_created":
                await self._on_message(update.get("message") or {})
            elif utype == "message_callback":
                await self._on_callback(update)
        except Exception:
            logger.exception("handle_update failed type=%s", utype)

    async def _on_callback(self, update: dict[str, Any]) -> None:
        callback = update.get("callback") or {}
        callback_id = callback.get("callback_id")
        payload = (callback.get("payload") or "").strip()
        message = update.get("message") or {}
        chat_id = _chat_id_from_message(message)
        if chat_id is None and update.get("chat_id") is not None:
            chat_id = int(update["chat_id"])
        if callback_id:
            try:
                await self.client.answer_callback(callback_id, notification="OK")
            except Exception:
                logger.exception("answer_callback failed")
        if chat_id is None:
            return

        if payload == "analyze":
            self.sessions.set_state(chat_id, DialogState.WAIT_PHOTO)
            await self.client.send_message(
                chat_id=chat_id,
                text=(
                    "Пришлите **одно фото** грудной мишени №4 целиком "
                    "(зелёная заливка, до ~1 м, ≤4 новых пробитий)."
                ),
                format="markdown",
                attachments=[cancel_menu()],
            )
        elif payload == "ask":
            self.sessions.set_state(chat_id, DialogState.CHAT)
            await self.client.send_message(
                chat_id=chat_id,
                text="Напишите вопрос по работе бота / правилам съёмки.",
                format="markdown",
                attachments=[cancel_menu()],
            )
        elif payload == "help":
            await self.send_chunks(chat_id, HELP_TEXT, attachments=[main_menu()])
            self.sessions.set_state(chat_id, DialogState.IDLE)
        elif payload == "cancel":
            self.sessions.reset(chat_id)
            await self.send_welcome(chat_id)

    async def _on_message(self, message: dict[str, Any]) -> None:
        chat_id = _chat_id_from_message(message)
        if chat_id is None:
            return
        sender = message.get("sender") or {}
        if sender.get("is_bot"):
            return

        body = message.get("body") or {}
        text = (body.get("text") or "").strip()
        image_url = _extract_image_url(message)
        session = self.sessions.get(chat_id)

        if text in {"/start", "start", "меню", "Меню"}:
            await self.send_welcome(chat_id)
            return

        if image_url:
            self.sessions.set_state(chat_id, DialogState.PROCESSING)
            await self.client.send_message(
                chat_id=chat_id,
                text="Обрабатываю фото…",
                format="markdown",
            )
            self._spawn(self._process_photo(chat_id, image_url))
            return

        if session.state == DialogState.WAIT_PHOTO:
            await self.client.send_message(
                chat_id=chat_id,
                text="Жду **фото** мишени. Или нажмите «Отмена».",
                format="markdown",
                attachments=[cancel_menu()],
            )
            return

        # Текст → FAQ / GigaChat
        self.sessions.set_state(chat_id, DialogState.CHAT)
        ans = await answer_text(text, gigachat=self.gigachat, storage=self.storage)
        await self.send_chunks(chat_id, ans.text, attachments=[main_menu()])
        self.sessions.set_state(chat_id, DialogState.IDLE)

    async def _process_photo(self, chat_id: int, image_url: str) -> None:
        try:
            raw = await self.client.download_url(image_url)
            self.storage.save_image(chat_id, raw, suffix="src.jpg")
            result = await asyncio.to_thread(
                analyze_target,
                raw,
                sector_map_path=self.settings.sector_map_path,
                max_new_holes=self.settings.max_new_holes,
                over_limit_policy=self.settings.over_limit_policy,
            )
            payload = result.to_dict()
            self.storage.save_result(chat_id, payload, status="ok" if result.ok else "reject")

            report = result.report_markdown()
            if result.ok and result.overlay_jpeg:
                from datetime import datetime, timezone

                ov_path = self.storage.overlays / (
                    f"{chat_id}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}_overlay.jpg"
                )
                ov_path.write_bytes(result.overlay_jpeg)
                await self.client.send_text_and_image(chat_id, report, result.overlay_jpeg)
            else:
                await self.send_chunks(chat_id, report)

            await self.client.send_message(
                chat_id=chat_id,
                text="Выберите следующее действие:",
                format="markdown",
                attachments=[main_menu()],
            )
        except Exception:
            logger.exception("photo processing failed chat=%s", chat_id)
            await self.client.send_message(
                chat_id=chat_id,
                text="Не удалось обработать фото. Попробуйте ещё раз или другое изображение.",
                format="markdown",
                attachments=[main_menu()],
            )
        finally:
            self.sessions.set_state(chat_id, DialogState.IDLE)
