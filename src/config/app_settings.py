"""Leitura/escrita de settings do Sahara Fennec."""
from __future__ import annotations

import json
import logging
import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "model": "qwen2.5:7b",
    "index_all_sheets": False,
    "max_rows_per_sheet": 0,
    "google_client_id": "",
    "microsoft_client_id": "",
    "llm_backend": "ollama",
    "nim_base_url": "https://integrate.api.nvidia.com/v1",
    "nim_model": "meta/llama-3.1-70b-instruct",
}

_SETTINGS_MTIME: float | None = None
_SETTINGS_LOCK = threading.Lock()


def get_settings_path() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home() / ".sahara_fennec")
    root = Path(appdata) / "SaharaFennec"
    root.mkdir(parents=True, exist_ok=True)
    return root / "settings.json"


@lru_cache(maxsize=1)
def _read_settings_from_disk() -> dict[str, Any]:
    path = get_settings_path()
    if not path.exists():
        return DEFAULT_SETTINGS.copy()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        cfg = DEFAULT_SETTINGS.copy()
        cfg.update(raw if isinstance(raw, dict) else {})
        return cfg
    except Exception:
        log.warning("Falha ao carregar settings de %s", path)
        return DEFAULT_SETTINGS.copy()


def load_settings() -> dict[str, Any]:
    global _SETTINGS_MTIME
    with _SETTINGS_LOCK:
        path = get_settings_path()
        try:
            mtime = path.stat().st_mtime if path.exists() else 0.0
        except OSError:
            mtime = 0.0
        if _SETTINGS_MTIME is not None and mtime != _SETTINGS_MTIME:
            _read_settings_from_disk.cache_clear()
            _SETTINGS_MTIME = mtime
        return _read_settings_from_disk()


@lru_cache(maxsize=1)
def settings_client_ids() -> tuple[str, str]:
    from ..integrations.oauth_defaults import get_default_client_id

    cfg = load_settings()
    google_client_id = str(cfg.get("google_client_id", "") or "").strip() or get_default_client_id("google")
    microsoft_client_id = str(cfg.get("microsoft_client_id", "") or "").strip() or get_default_client_id("microsoft")
    return google_client_id, microsoft_client_id


def save_settings(settings: dict[str, Any]) -> None:
    global _SETTINGS_MTIME
    with _SETTINGS_LOCK:
        path = get_settings_path()
        cfg = DEFAULT_SETTINGS.copy()
        cfg.update(settings)
        path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        _SETTINGS_MTIME = None
        _read_settings_from_disk.cache_clear()
        settings_client_ids.cache_clear()
