from __future__ import annotations

import logging
from dataclasses import dataclass

from app.llm.faq import match_faq
from app.llm.gigachat_client import GigaChatClient
from app.storage.store import Storage

logger = logging.getLogger(__name__)


@dataclass
class TextAnswer:
    text: str
    source: str  # faq | gigachat | fallback


async def answer_text(
    user_text: str,
    *,
    gigachat: GigaChatClient | None,
    storage: Storage | None = None,
) -> TextAnswer:
    hit = match_faq(user_text)
    if hit:
        return TextAnswer(text=hit.answer, source="faq")

    if gigachat is not None and gigachat.ready:
        try:
            reply = await gigachat.ask(user_text)
            if storage is not None:
                storage.log_token_usage(
                    prompt_tokens=reply.prompt_tokens,
                    completion_tokens=reply.completion_tokens,
                    total_tokens=reply.total_tokens,
                    note="gigachat",
                )
            return TextAnswer(text=reply.text, source="gigachat")
        except Exception:
            logger.exception("GigaChat error")
            return TextAnswer(
                text=(
                    "Не удалось получить ответ GigaChat (ключ/токены/сеть). "
                    "Попробуйте вопрос из раздела «Помощь» или повторите позже."
                ),
                source="fallback",
            )

    return TextAnswer(
        text=(
            "Я не нашёл готовый ответ в FAQ, а **GigaChat сейчас выключен** "
            "(нет ключа или `GIGACHAT_ENABLED=false`).\n\n"
            "Нажмите «Помощь / правила» или задайте вопрос про съёмку/скотч/сектора."
        ),
        source="fallback",
    )
