from __future__ import annotations

import cv2
import numpy as np


def white_tape_mask(bgr: np.ndarray) -> np.ndarray:
    """Маска белого малярного скотча: высокая яркость, низкая насыщенность."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    # Белый / почти белый
    lower = np.array([0, 0, 180], dtype=np.uint8)
    upper = np.array([180, 55, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)
    # Убираем мелкий шум, оставляем ленты
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    kernel2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel2, iterations=1)
    return mask


def point_on_tape(tape: np.ndarray, x: float, y: float, radius: float) -> bool:
    h, w = tape.shape[:2]
    cx, cy = int(round(x)), int(round(y))
    if not (0 <= cx < w and 0 <= cy < h):
        return False
    r = max(2, int(radius * 0.8))
    y0, y1 = max(0, cy - r), min(h, cy + r + 1)
    x0, x1 = max(0, cx - r), min(w, cx + r + 1)
    patch = tape[y0:y1, x0:x1]
    if patch.size == 0:
        return False
    return float(np.count_nonzero(patch)) / float(patch.size) > 0.35
