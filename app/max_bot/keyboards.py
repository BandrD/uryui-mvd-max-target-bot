from __future__ import annotations

from typing import Any


def main_menu() -> dict[str, Any]:
    return {
        "type": "inline_keyboard",
        "payload": {
            "buttons": [
                [
                    {"type": "callback", "text": "Анализ мишени", "payload": "analyze"},
                    {"type": "callback", "text": "Задать вопрос", "payload": "ask"},
                ],
                [
                    {"type": "callback", "text": "Помощь / правила", "payload": "help"},
                ],
            ]
        },
    }


def cancel_menu() -> dict[str, Any]:
    return {
        "type": "inline_keyboard",
        "payload": {
            "buttons": [
                [{"type": "callback", "text": "Отмена", "payload": "cancel"}],
            ]
        },
    }
