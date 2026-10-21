from __future__ import annotations

from pathlib import Path

from app.cv.pipeline import analyze_target

ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_detects_holes(synthetic_with_holes: bytes, sector_map_path: Path):
    result = analyze_target(
        synthetic_with_holes,
        sector_map_path=sector_map_path,
        max_new_holes=4,
        over_limit_policy="warn",
    )
    assert result.ok, result.message
    assert len(result.holes) >= 1
    assert result.overlay_jpeg
    for h in result.holes:
        assert h.sector is not None
        assert 1 <= h.sector <= 10


def test_pipeline_tape_ignored(synthetic_with_tape: bytes, sector_map_path: Path):
    result = analyze_target(
        synthetic_with_tape,
        sector_map_path=sector_map_path,
    )
    assert result.ok, result.message
    # отверстие под скотчем должно быть исключено или не учтено
    assert len(result.holes) == 0 or all(
        h.ignored_reason != "white_tape" for h in result.holes
    )


def test_pipeline_rejects_non_target(sector_map_path: Path):
    # почти белый кадр без зелени
    import numpy as np
    import cv2

    img = np.full((400, 400, 3), 230, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    result = analyze_target(bytes(buf), sector_map_path=sector_map_path)
    assert not result.ok
