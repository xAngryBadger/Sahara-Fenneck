# -*- coding: utf-8 -*-
"""
Armazenamento seguro de tokens OAuth.

No Windows, usa DPAPI via win32crypt para proteger os dados em repouso.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from ..config.app_settings import get_settings_path


def _tokens_path() -> Path:
    return get_settings_path().parent / "oauth_tokens.json"


def _protect(raw: bytes) -> tuple[bytes, str]:
    try:
        import win32crypt  # type: ignore

        protected = win32crypt.CryptProtectData(raw, None, None, None, None, 0)
        return protected[1], "dpapi"
    except Exception:
        return raw, "plain"


def _unprotect(data: bytes, mode: str) -> bytes:
    if mode == "dpapi":
        try:
            import win32crypt  # type: ignore

            unprotected = win32crypt.CryptUnprotectData(data, None, None, None, 0)
            return unprotected[1]
        except Exception:
            return b""
    return data


def _load_all() -> dict[str, Any]:
    path = _tokens_path()
    if not path.exists():
        return {}
    try:
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        payload_b64 = wrapper.get("payload_b64", "")
        mode = str(wrapper.get("mode", "plain"))
        if not payload_b64:
            return {}
        protected = base64.b64decode(payload_b64.encode("ascii"))
        raw = _unprotect(protected, mode)
        if not raw:
            return {}
        parsed = json.loads(raw.decode("utf-8"))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _save_all(data: dict[str, Any]) -> None:
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    protected, mode = _protect(raw)
    wrapper = {
        "mode": mode,
        "payload_b64": base64.b64encode(protected).decode("ascii"),
    }
    _tokens_path().write_text(json.dumps(wrapper, ensure_ascii=False, indent=2), encoding="utf-8")


def get_provider_token(provider: str) -> dict[str, Any] | None:
    all_data = _load_all()
    token = all_data.get(provider)
    return token if isinstance(token, dict) else None


def set_provider_token(provider: str, token_data: dict[str, Any]) -> None:
    all_data = _load_all()
    all_data[provider] = token_data
    _save_all(all_data)


def clear_provider_token(provider: str) -> None:
    all_data = _load_all()
    if provider in all_data:
        del all_data[provider]
        _save_all(all_data)

