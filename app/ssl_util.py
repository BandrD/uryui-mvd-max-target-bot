from __future__ import annotations

import ssl
from pathlib import Path


def build_ssl_context(extra_ca_path: Path | None) -> ssl.SSLContext:
    """Системные CA + корневой CA Минцифры (нужен для platform-api2.max.ru)."""
    ctx = ssl.create_default_context()
    if extra_ca_path and extra_ca_path.is_file():
        ctx.load_verify_locations(cafile=str(extra_ca_path))
    return ctx
