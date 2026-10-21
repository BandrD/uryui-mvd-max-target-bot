from __future__ import annotations

from pathlib import Path

from app.cv.sectors import SectorMapper

ROOT = Path(__file__).resolve().parents[1]


def test_sector_map_loads():
    mapper = SectorMapper.from_file(ROOT / "assets" / "sector_map.json")
    assert mapper.rows * mapper.cols == 10
    assert mapper.sector_for(10, 10) == 1
    assert mapper.sector_for(500, 10) == 2
    assert mapper.sector_for(10, 750) == 9
    assert mapper.sector_for(500, 750) == 10


def test_cell_rects_count():
    mapper = SectorMapper.from_file(ROOT / "assets" / "sector_map.json")
    assert len(mapper.cell_rects()) == 10
