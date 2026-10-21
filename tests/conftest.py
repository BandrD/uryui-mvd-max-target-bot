from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "assets" / "target_no4_template.jpg"


def _imread_unicode(path: Path) -> np.ndarray:
    """OpenCV imread ломается на путях с кириллицей в Windows — читаем через imdecode."""
    data = path.read_bytes()
    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Не удалось прочитать изображение: {path}")
    return img


@pytest.fixture(scope="session")
def sector_map_path() -> Path:
    return ROOT / "assets" / "sector_map.json"


def make_synthetic_target(
    *,
    holes: list[tuple[int, int, int]] | None = None,
    tape_rects: list[tuple[int, int, int, int]] | None = None,
    paper_pad: float = 0.18,
) -> bytes:
    """Фото на основе реальной мишени №4 (Т-силуэт) + белое поле."""
    template = _imread_unicode(TEMPLATE)
    th, tw = template.shape[:2]
    pad_x = int(tw * paper_pad)
    pad_y = int(th * paper_pad)
    canvas = np.full((th + 2 * pad_y, tw + 2 * pad_x, 3), 238, dtype=np.uint8)
    canvas[pad_y : pad_y + th, pad_x : pad_x + tw] = template

    if holes:
        for x, y, r in holes:
            cv2.circle(canvas, (pad_x + x, pad_y + y), r, (15, 15, 15), -1)

    if tape_rects:
        for x0, y0, x1, y1 in tape_rects:
            cv2.rectangle(
                canvas,
                (pad_x + x0, pad_y + y0),
                (pad_x + x1, pad_y + y1),
                (252, 252, 248),
                -1,
            )

    ok, buf = cv2.imencode(".jpg", canvas)
    assert ok
    return bytes(buf)


@pytest.fixture
def synthetic_with_holes() -> bytes:
    tpl = _imread_unicode(TEMPLATE)
    th, tw = tpl.shape[:2]
    hw, hh = tw // 2, th // 2
    return make_synthetic_target(
        holes=[(hw - 35, hh - 10, 8), (hw + 40, hh + 25, 7), (hw - 5, hh + 55, 8)],
    )


@pytest.fixture
def synthetic_with_tape() -> bytes:
    tpl = _imread_unicode(TEMPLATE)
    th, tw = tpl.shape[:2]
    hw, hh = tw // 2, th // 2
    return make_synthetic_target(
        holes=[(hw, hh + 10, 8)],
        tape_rects=[(hw - 45, hh - 25, hw + 45, hh + 45)],
    )
