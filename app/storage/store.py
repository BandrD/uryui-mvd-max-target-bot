from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Storage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.images = root / "images"
        self.overlays = root / "overlays"
        self.results = root / "results"
        for p in (self.root, self.images, self.overlays, self.results):
            p.mkdir(parents=True, exist_ok=True)
        self.db_path = root / "sessions.db"
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    total_tokens INTEGER,
                    note TEXT
                )
                """
            )
            conn.commit()

    def save_image(self, chat_id: int, data: bytes, suffix: str = "src.jpg") -> Path:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        path = self.images / f"{chat_id}_{ts}_{suffix}"
        path.write_bytes(data)
        return path

    def save_overlay(self, chat_id: int, data: bytes) -> Path:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        path = self.overlays / f"{chat_id}_{ts}_overlay.jpg"
        path.write_bytes(data)
        return path

    def save_result(self, chat_id: int, payload: dict[str, Any], status: str = "ok") -> Path:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        path = self.results / f"{chat_id}_{ts}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO jobs (chat_id, created_at, status, result_json) VALUES (?, ?, ?, ?)",
                (chat_id, datetime.now(timezone.utc).isoformat(), status, path.read_text(encoding="utf-8")),
            )
            conn.commit()
        return path

    def log_token_usage(
        self,
        *,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        note: str = "",
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO token_usage (created_at, prompt_tokens, completion_tokens, total_tokens, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    note,
                ),
            )
            conn.commit()
        logger.info("token_usage total=%s note=%s", total_tokens, note)
