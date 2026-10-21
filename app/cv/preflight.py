from __future__ import annotations

import cv2
import numpy as np


class PreflightError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def decode_image(data: bytes) -> np.ndarray:
    if not data:
        raise PreflightError("Пустой файл изображения.")
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise PreflightError("Не удалось прочитать изображение. Пришлите JPG или PNG.")
    h, w = img.shape[:2]
    if h < 200 or w < 200:
        raise PreflightError("Слишком маленькое изображение. Сфотографируйте мишень целиком.")
    if h > 6000 or w > 6000:
        scale = 4000 / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return img


def check_framing(img: np.ndarray, green_ratio: float) -> list[str]:
    """Эвристика: доля зелёной зоны и заполнение кадра."""
    warnings: list[str] = []
    if green_ratio < 0.05:
        raise PreflightError(
            "Не похоже на грудную мишень №4 с зелёной заливкой. "
            "Снимите мишень целиком при хорошем освещении."
        )
    if green_ratio < 0.12:
        warnings.append("Мишень занимает мало кадра — лучше снимать с расстояния около 1 м.")
    if green_ratio > 0.85:
        warnings.append("Кадр слишком плотный — убедитесь, что мишень видна целиком, включая белое поле.")
    return warnings
