from __future__ import annotations

import cv2
import numpy as np

from .models import Hole
from .tape_filter import point_on_tape, white_tape_mask
from .target_align import green_mask


def _circularity(contour: np.ndarray) -> float:
    area = cv2.contourArea(contour)
    peri = cv2.arcLength(contour, True)
    if peri <= 1e-6:
        return 0.0
    return float(4 * np.pi * area / (peri * peri))


def _target_interior_mask(bgr: np.ndarray) -> np.ndarray:
    """Залитая область мишени (зелень + отверстия внутри контура)."""
    g = green_mask(bgr)
    # Крупное закрытие, чтобы «дыры» внутри зелени попали в interior
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
    filled = cv2.morphologyEx(g, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(filled, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = np.zeros_like(g)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        cv2.drawContours(out, [largest], -1, 255, thickness=-1)
    return out


def detect_hole_candidates(aligned_bgr: np.ndarray) -> list[Hole]:
    """Детекция тёмных круглых пробоин внутри силуэта мишени."""
    interior = _target_interior_mask(aligned_bgr)
    gray = cv2.cvtColor(aligned_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # Абсолютный порог тьмы (не Otsu — на зелёном фоне он «заливает» кадр)
    dark = (blur < 70).astype(np.uint8) * 255
    mask = cv2.bitwise_and(dark, interior)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    h, w = mask.shape
    border = int(0.015 * min(h, w))
    mask[:border, :] = 0
    mask[-border:, :] = 0
    mask[:, :border] = 0
    mask[:, -border:] = 0

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    img_area = float(h * w)
    holes: list[Hole] = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 15 or area > 0.015 * img_area:
            continue
        circ = _circularity(cnt)
        if circ < 0.25:
            continue
        (cx, cy), radius = cv2.minEnclosingCircle(cnt)
        if radius < 3 or radius > min(h, w) * 0.1:
            continue
        # Центр должен быть внутри силуэта
        if interior[int(cy), int(cx)] == 0:
            continue
        holes.append(Hole(id=0, x=float(cx), y=float(cy), radius=float(radius)))

    # Дополнение: HoughCircles, если контуров мало
    if len(holes) < 1:
        circles = cv2.HoughCircles(
            blur,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=18,
            param1=80,
            param2=18,
            minRadius=4,
            maxRadius=int(min(h, w) * 0.08),
        )
        if circles is not None:
            for x, y, r in circles[0]:
                ix, iy = int(round(x)), int(round(y))
                if not (0 <= ix < w and 0 <= iy < h):
                    continue
                if interior[iy, ix] == 0:
                    continue
                if blur[iy, ix] > 90:
                    continue
                holes.append(Hole(id=0, x=float(x), y=float(y), radius=float(r)))

    return holes


def is_corner_hardware(x: float, y: float, w: int, h: int, margin_ratio: float = 0.12) -> bool:
    """Крепёж допускается только в углах белого поля (по ТЗ)."""
    mx, my = w * margin_ratio, h * margin_ratio
    in_left = x <= mx
    in_right = x >= w - mx
    in_top = y <= my
    in_bottom = y >= h - my
    return (in_left or in_right) and (in_top or in_bottom)


def merge_overlapping(holes: list[Hole], iou_dist_factor: float = 1.2) -> list[Hole]:
    """Наложения → одно пробитие (по ТЗ)."""
    if not holes:
        return []
    remaining = sorted(holes, key=lambda hole: hole.radius, reverse=True)
    merged: list[Hole] = []
    while remaining:
        base = remaining.pop(0)
        kept: list[Hole] = []
        for other in remaining:
            dist = ((base.x - other.x) ** 2 + (base.y - other.y) ** 2) ** 0.5
            if dist <= (base.radius + other.radius) * iou_dist_factor:
                nx = (base.x * base.radius + other.x * other.radius) / (base.radius + other.radius)
                ny = (base.y * base.radius + other.y * other.radius) / (base.radius + other.radius)
                nr = max(base.radius, other.radius, dist / 2 + min(base.radius, other.radius))
                base = Hole(id=0, x=nx, y=ny, radius=nr)
            else:
                kept.append(other)
        merged.append(base)
        remaining = kept
    return merged


def filter_holes(aligned_bgr: np.ndarray, candidates: list[Hole]) -> tuple[list[Hole], list[Hole]]:
    tape = white_tape_mask(aligned_bgr)
    h, w = aligned_bgr.shape[:2]
    kept: list[Hole] = []
    ignored: list[Hole] = []
    for hole in candidates:
        if point_on_tape(tape, hole.x, hole.y, hole.radius):
            hole.ignored_reason = "white_tape"
            ignored.append(hole)
            continue
        if is_corner_hardware(hole.x, hole.y, w, h):
            hole.ignored_reason = "corner_hardware"
            ignored.append(hole)
            continue
        kept.append(hole)
    kept = merge_overlapping(kept)
    for i, hole in enumerate(kept, start=1):
        hole.id = i
    for i, hole in enumerate(ignored, start=1):
        hole.id = i
    return kept, ignored
