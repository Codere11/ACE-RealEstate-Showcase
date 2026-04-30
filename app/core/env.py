from __future__ import annotations

import os
from pathlib import Path

_LOADED = False


def load_local_env() -> None:
    global _LOADED
    if _LOADED:
        return

    root = Path(__file__).resolve().parents[2]
    env_path = root / '.env'
    if not env_path.exists():
        _LOADED = True
        return

    try:
        for raw in env_path.read_text(encoding='utf-8').splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
    finally:
        _LOADED = True
