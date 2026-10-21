from __future__ import annotations

import logging
from pathlib import Path

from .holes import detect_hole_candidates, filter_holes
from .models import AnalysisResult
from .overlay import draw_result
from .preflight import PreflightError, check_framing, decode_image
from .sectors import SectorMapper
from .target_align import align_to_canonical, locate_target_bbox

logger = logging.getLogger(__name__)


def analyze_target(
    image_bytes: bytes,
    *,
    sector_map_path: Path,
    max_new_holes: int = 4,
    over_limit_policy: str = "warn",
) -> AnalysisResult:
    try:
        bgr = decode_image(image_bytes)
        bbox, green_ratio, _mask = locate_target_bbox(bgr)
        warnings = check_framing(bgr, green_ratio)
        mapper = SectorMapper.from_file(sector_map_path)
        aligned, _affine = align_to_canonical(
            bgr, bbox, canonical_size=(mapper.width, mapper.height)
        )
        candidates = detect_hole_candidates(aligned)
        holes, ignored = filter_holes(aligned, candidates)
        mapper.assign(holes)

        if len(holes) > max_new_holes:
            msg = (
                f"Обнаружено {len(holes)} новых пробитий (по ТЗ допускается не более {max_new_holes})."
            )
            if over_limit_policy == "reject":
                return AnalysisResult(
                    ok=False,
                    message=msg + " Анализ отклонён (OVER_LIMIT_POLICY=reject).",
                    holes=holes,
                    ignored_holes=ignored,
                    warnings=warnings,
                    meta={"green_ratio": green_ratio, "bbox": bbox},
                )
            warnings.append(msg + " Результат всё равно показан (политика warn).")

        overlay = draw_result(aligned, holes, ignored, mapper, draw_sectors=True)
        return AnalysisResult(
            ok=True,
            message="ok",
            holes=holes,
            ignored_holes=ignored,
            warnings=warnings,
            overlay_jpeg=overlay,
            meta={
                "green_ratio": round(green_ratio, 4),
                "bbox": bbox,
                "sector_map": mapper.config.get("version", "unknown"),
                "candidates_raw": len(candidates),
            },
        )
    except PreflightError as exc:
        logger.info("preflight reject: %s", exc.message)
        return AnalysisResult(ok=False, message=exc.message)
    except Exception:
        logger.exception("analyze_target failed")
        return AnalysisResult(
            ok=False,
            message="Внутренняя ошибка обработки изображения. Попробуйте другое фото.",
        )
