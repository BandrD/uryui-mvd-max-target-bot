from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Hole:
    id: int
    x: float
    y: float
    radius: float
    sector: int | None = None
    ignored_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "x": round(self.x, 1),
            "y": round(self.y, 1),
            "radius": round(self.radius, 1),
            "sector": self.sector,
            "ignored_reason": self.ignored_reason,
        }


@dataclass
class AnalysisResult:
    ok: bool
    message: str
    holes: list[Hole] = field(default_factory=list)
    ignored_holes: list[Hole] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    overlay_jpeg: bytes | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "message": self.message,
            "holes": [h.to_dict() for h in self.holes],
            "ignored_holes": [h.to_dict() for h in self.ignored_holes],
            "warnings": self.warnings,
            "meta": self.meta,
        }

    def report_markdown(self) -> str:
        lines = [f"**Результат анализа мишени №4**", ""]
        if not self.ok:
            lines.append(self.message)
            if self.warnings:
                lines.append("")
                lines.extend(f"⚠ {w}" for w in self.warnings)
            return "\n".join(lines)

        lines.append(f"Учтено пробитий: **{len(self.holes)}**")
        if self.ignored_holes:
            lines.append(f"Исключено (скотч/крепёж): **{len(self.ignored_holes)}**")
        lines.append("")
        if self.holes:
            lines.append("Пробития:")
            for h in self.holes:
                sec = h.sector if h.sector is not None else "?"
                lines.append(f"{h.id}. сектор **{sec}** (x={h.x:.0f}, y={h.y:.0f})")
        else:
            lines.append("Новых пробитий не обнаружено.")
        if self.warnings:
            lines.append("")
            lines.extend(f"⚠ {w}" for w in self.warnings)
        return "\n".join(lines)
