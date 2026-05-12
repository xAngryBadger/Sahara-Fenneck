"""
Armazenamento seguro de tokens OAuth.

No Windows, usa DPAPI via win32crypt para proteger os dados em repouso.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

from ..config.app_settings import get_settings_path
from ..errcodes import ErrCode

log = logging.getLogger(__name__)


def _tokens_path() -> Path:
    return get_settings_path().parent / "oauth_tokens.json"


def _fernet_key() -> bytes:
    """Derive a Fernet key from machine-specific data (hostname + username)."""

    identity = f"{os.getenv('USERNAME', 'user')}@{os.getenv('COMPUTERNAME', os.getenv('HOSTNAME', 'localhost'))}"
    raw = hashlib.sha256(identity.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(raw)


def _protect(raw: bytes) -> tuple[bytes, str]:
    try:
        import win32crypt  # type: ignore

        protected = win32crypt.CryptProtectData(raw, None, None, None, None, 0)
        return protected[1], "dpapi"
    except Exception:
        log.debug("DPAPI not available, falling back to Fernet")

    try:
        from cryptography.fernet import Fernet

        key = _fernet_key()
        f = Fernet(key)
        return f.encrypt(raw), "fernet"
    except Exception as e:
        log.warning("Fernet encryption failed: %s", e)
        raise RuntimeError(f"[{ErrCode.ENCRYPTION_FAILED.value}] {ErrCode.ENCRYPTION_FAILED.name}: both DPAPI and Fernet failed. Cannot store tokens safely.") from e


def _unprotect(data: bytes, mode: str) -> bytes:
    if mode == "dpapi":
        try:
            import win32crypt  # type: ignore

            unprotected = win32crypt.CryptUnprotectData(data, None, None, None, 0)
            return bytes(unprotected[1])
        except Exception as e:
            log.warning("DPAPI decryption failed: %s", e)
            raise

    if mode == "fernet":
        try:
            from cryptography.fernet import Fernet

            key = _fernet_key()
            f = Fernet(key)
            return bytes(f.decrypt(data))
        except Exception as e:
            log.warning("Fernet decryption failed: %s", e)
            raise

    if mode == "plain":
        log.warning("Migrating plaintext tokens to Fernet encryption")
        return data

    raise ValueError(f"[{ErrCode.ENCRYPTION_FAILED.value}] Unknown encryption mode: {mode}")


def _migrate_if_plain(wrapper: dict) -> dict:
    """If tokens are stored as plaintext, re-encrypt with Fernet and save."""
    if wrapper.get("mode") != "plain":
        return wrapper
    payload_b64 = wrapper.get("payload_b64", "")
    if not payload_b64:
        return wrapper
    try:
        raw = base64.b64decode(payload_b64.encode("ascii"))
        parsed = json.loads(raw.decode("utf-8"))
        if isinstance(parsed, dict) and parsed:
            _save_all(parsed)
            log.info("Migrated plaintext tokens to Fernet encryption")
            with open(_tokens_path(), encoding="utf-8") as f:
                return dict(json.loads(f.read()))
    except Exception as e:
        log.error("Plaintext token migration failed: %s", e)
    return wrapper


def _load_all() -> dict[str, Any]:
    path = _tokens_path()
    if not path.exists():
        return {}
    try:
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        wrapper = _migrate_if_plain(wrapper)
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
    except Exception as e:
        log.error("Failed to load tokens: %s", e)
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


def get_nim_api_key() -> str:
    data = get_provider_token("nvidia")
    if isinstance(data, dict):
        return str(data.get("api_key", ""))
    return ""


def set_nim_api_key(api_key: str) -> None:
    set_provider_token("nvidia", {"api_key": api_key})

