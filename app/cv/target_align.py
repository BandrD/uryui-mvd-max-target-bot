from __future__ import annotations

import cv2
import numpy as np

from .preflight import PreflightError


def green_mask(bgr: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    # Два диапазона зелёного (разный свет)
    lower1 = np.array([35, 40, 40], dtype=np.uint8)
    upper1 = np.array([95, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower1, upper1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    return mask


def locate_target_bbox(bgr: np.ndarray) -> tuple[tuple[int, int, int, int], float, np.ndarray]:
    mask = green_mask(bgr)
    green_ratio = float(np.count_nonzero(mask)) / float(mask.size)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise PreflightError("Зелёная зона мишени №4 не найдена.")
    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    if area < 0.02 * bgr.shape[0] * bgr.shape[1]:
        raise PreflightError("Зелёная зона слишком маленькая — подойдите ближе (~1 м) и снимите мишень целиком.")
    x, y, w, h = cv2.boundingRect(largest)
    # Расширяем на белое поле вокруг
    pad_x = int(0.08 * w)
    pad_y = int(0.08 * h)
    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(bgr.shape[1], x + w + pad_x)
    y1 = min(bgr.shape[0], y + h + pad_y)
    return (x0, y0, x1 - x0, y1 - y0), green_ratio, mask


def align_to_canonical(
    bgr: np.ndarray,
    bbox: tuple[int, int, int, int],
    canonical_size: tuple[int, int] = (600, 800),
) -> tuple[np.ndarray, np.ndarray]:
    """Вырезаем bbox и масштабируем в канон. Homography-упрощение для MVP."""
    x, y, w, h = bbox
    crop = bgr[y : y + h, x : x + w]
    if crop.size == 0:
        raise PreflightError("Не удалось вырезать область мишени.")
    cw, ch = canonical_size
    aligned = cv2.resize(crop, (cw, ch), interpolation=cv2.INTER_AREA)
    # Матрица для обратного маппинга точек (canonical -> original crop coords scaled)
    # Здесь aligned уже в каноне; исходные координаты в crop: sx = x_canon * w/cw
    meta_affine = np.array(
        [
            [w / cw, 0, x],
            [0, h / ch, y],
        ],
        dtype=np.float64,
    )
    return aligned, meta_affine
