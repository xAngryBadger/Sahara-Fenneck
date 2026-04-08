# -*- coding: utf-8 -*-
"""Leitura/escrita de settings do Sahara Fennec."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_SETTINGS = {
    "model": "qwen2.5:7b",
    "index_all_sheets": False,
    "max_rows_per_sheet": 0,
    "google_client_id": "",
    "microsoft_client_id": "",
}


def get_settings_path() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home() / ".sahara_fennec")
    root = Path(appdata) / "SaharaFennec"
    root.mkdir(parents=True, exist_ok=True)
    return root / "settings.json"


def load_settings() -> dict[str, Any]:
    path = get_settings_path()
    if not path.exists():
        return DEFAULT_SETTINGS.copy()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        cfg = DEFAULT_SETTINGS.copy()
        cfg.update(raw if isinstance(raw, dict) else {})
        return cfg
    except Exception:
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict[str, Any]) -> None:
    path = get_settings_path()
    cfg = DEFAULT_SETTINGS.copy()
    cfg.update(settings)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
