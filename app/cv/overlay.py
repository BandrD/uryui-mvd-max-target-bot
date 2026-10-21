from __future__ import annotations

import cv2
import numpy as np

from .models import Hole
from .sectors import SectorMapper


def encode_jpeg(bgr: np.ndarray, quality: int = 90) -> bytes:
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("Не удалось закодировать JPEG")
    return bytes(buf)


def draw_result(
    aligned_bgr: np.ndarray,
    holes: list[Hole],
    ignored: list[Hole],
    mapper: SectorMapper | None = None,
    *,
    draw_sectors: bool = True,
) -> bytes:
    canvas = aligned_bgr.copy()
    if mapper is not None and draw_sectors:
        for sid, x0, y0, x1, y1 in mapper.cell_rects():
            cv2.rectangle(canvas, (x0, y0), (x1 - 1, y1 - 1), (80, 80, 80), 1)
            cv2.putText(
                canvas,
                str(sid),
                (x0 + 8, y0 + 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (60, 60, 60),
                1,
                cv2.LINE_AA,
            )

    for hole in ignored:
        color = (180, 180, 180)
        cv2.circle(canvas, (int(hole.x), int(hole.y)), int(hole.radius) + 2, color, 2)

    for hole in holes:
        cv2.circle(canvas, (int(hole.x), int(hole.y)), int(hole.radius) + 3, (0, 0, 255), 2)
        label = f"{hole.id}"
        if hole.sector is not None:
            label += f"→{hole.sector}"
        cv2.putText(
            canvas,
            label,
            (int(hole.x) + 8, int(hole.y) - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )
    return encode_jpeg(canvas)
