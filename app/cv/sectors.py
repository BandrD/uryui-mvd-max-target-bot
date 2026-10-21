from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Hole


class SectorMapper:
    """
    Карта 10 секторов.

    Режим provisional: сетка 2 колонки × 5 рядов поверх канонического кадра.
    До согласования с заказчиком (п. 0.6 плана).
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.mode = config.get("mode", "grid_2x5")
        size = config.get("canonical_size", [600, 800])
        self.width = int(size[0])
        self.height = int(size[1])
        self.rows = int(config.get("rows", 5))
        self.cols = int(config.get("cols", 2))
        # Нумерация: слева направо, сверху вниз → 1..10
        self.sector_ids = config.get("sector_ids") or list(range(1, self.rows * self.cols + 1))

    @classmethod
    def from_file(cls, path: Path) -> SectorMapper:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data)

    def sector_for(self, x: float, y: float) -> int:
        if self.mode == "grid_2x5":
            col = min(self.cols - 1, max(0, int(x / self.width * self.cols)))
            row = min(self.rows - 1, max(0, int(y / self.height * self.rows)))
            idx = row * self.cols + col
            return int(self.sector_ids[idx])
        raise ValueError(f"Неизвестный mode карты секторов: {self.mode}")

    def assign(self, holes: list[Hole]) -> list[Hole]:
        for hole in holes:
            hole.sector = self.sector_for(hole.x, hole.y)
        return holes

    def cell_rects(self) -> list[tuple[int, int, int, int, int]]:
        """(sector_id, x0, y0, x1, y1) для отладочной отрисовки."""
        out: list[tuple[int, int, int, int, int]] = []
        cw = self.width / self.cols
        rh = self.height / self.rows
        for row in range(self.rows):
            for col in range(self.cols):
                idx = row * self.cols + col
                sid = int(self.sector_ids[idx])
                x0 = int(col * cw)
                y0 = int(row * rh)
                x1 = int((col + 1) * cw)
                y1 = int((row + 1) * rh)
                out.append((sid, x0, y0, x1, y1))
        return out
