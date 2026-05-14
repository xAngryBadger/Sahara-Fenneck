"""Unit tests for token_store — Fernet encryption, DPAPI fallback, migration."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from src.integrations.token_store import (
    _fernet_key,
    _migrate_if_plain,
    _protect,
    _tokens_path,
    _unprotect,
    clear_provider_token,
    get_provider_token,
    set_provider_token,
)


class TestFernetKey:
    def test_deterministic(self):
        k1 = _fernet_key()
        k2 = _fernet_key()
        assert k1 == k2

    def test_is_32_bytes_b64(self):
        key = _fernet_key()
        raw = base64.urlsafe_b64decode(key)
        assert len(raw) == 32

    @patch.dict(os.environ, {"USERNAME": "testuser", "COMPUTERNAME": "testhost"})
    def test_raises_when_key_file_unwritable(self, tmp_path):
        from unittest.mock import patch

        import pytest
        settings_path = tmp_path / "readonly" / "settings.json"
        with patch("src.integrations.token_store.get_settings_path", return_value=settings_path), \
             patch("pathlib.Path.write_bytes", side_effect=PermissionError("read-only")):
            with pytest.raises(RuntimeError, match=r"\[E020\]"):
                _fernet_key()

    def test_uses_key_file_when_present(self, tmp_path):
        import os as _os
        from unittest.mock import patch
        stored = base64.urlsafe_b64encode(_os.urandom(32))
        key_path = tmp_path / "sf" / ".enc_key"
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(stored)
        with patch("src.integrations.token_store.get_settings_path", return_value=tmp_path / "sf" / "settings.json"):
            key = _fernet_key()
        assert key == stored


class TestProtect:
    def test_fernet_on_linux(self):
        raw = b'{"google": {"token": "abc"}}'
        protected, mode = _protect(raw)
        assert mode == "fernet"
        assert protected != raw
        assert len(protected) > 0

    @patch("src.integrations.token_store._fernet_key", side_effect=RuntimeError("no fernet"))
    def test_raises_when_both_fail(self, _mock):
        with pytest.raises(RuntimeError, match=r"\[E020\]"):
            _protect(b"test")


class TestUnprotect:
    def test_fernet_roundtrip(self):
        raw = b'{"google": {"token": "xyz123"}}'
        protected, mode = _protect(raw)
        result = _unprotect(protected, mode)
        assert result == raw

    def test_plain_mode_passes_through(self):
        data = b"plaintext data"
        result = _unprotect(data, "plain")
        assert result == data

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match=r"\[E020\]"):
            _unprotect(b"test", "aes256")


class TestMigrateIfPlain:
    def test_no_migration_needed(self):
        wrapper = {"mode": "fernet", "payload_b64": "abc"}
        result = _migrate_if_plain(wrapper)
        assert result == wrapper

    def test_plain_wrapper_triggers_migration(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.integrations.token_store._tokens_path", lambda: tmp_path / "tokens.json")
        plain_data = {"google": {"access_token": "test123"}}
        payload = base64.b64encode(json.dumps(plain_data).encode("utf-8")).decode("ascii")
        wrapper = {"mode": "plain", "payload_b64": payload}
        result = _migrate_if_plain(wrapper)
        assert result.get("mode") == "fernet"


class TestTokensPath:
    def test_returns_path_object(self):
        p = _tokens_path()
        assert isinstance(p, Path)
        assert p.name == "oauth_tokens.json"


class TestGetSetClearProviderToken:
    def test_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.integrations.token_store._tokens_path", lambda: tmp_path / "tokens.json")
        set_provider_token("google", {"access_token": "abc", "refresh_token": "def"})
        result = get_provider_token("google")
        assert result is not None
        assert result["access_token"] == "abc"

    def test_nonexistent_provider(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.integrations.token_store._tokens_path", lambda: tmp_path / "tokens.json")
        assert get_provider_token("nonexistent") is None

    def test_clear_provider(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.integrations.token_store._tokens_path", lambda: tmp_path / "tokens.json")
        set_provider_token("microsoft", {"access_token": "ms123"})
        clear_provider_token("microsoft")
        assert get_provider_token("microsoft") is None

    def test_multiple_providers(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.integrations.token_store._tokens_path", lambda: tmp_path / "tokens.json")
        set_provider_token("google", {"access_token": "g"})
        set_provider_token("microsoft", {"access_token": "m"})
        assert get_provider_token("google")["access_token"] == "g"
        assert get_provider_token("microsoft")["access_token"] == "m"

    def test_no_file_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.integrations.token_store._tokens_path", lambda: tmp_path / "nonexistent.json")
        assert get_provider_token("google") is None

    def test_persistence_across_calls(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.integrations.token_store._tokens_path", lambda: tmp_path / "tokens.json")
        set_provider_token("google", {"access_token": "persist_test"})
        # Re-read from disk (not caching)
        result = get_provider_token("google")
        assert result["access_token"] == "persist_test"
        # Verify file exists
        assert (tmp_path / "tokens.json").exists()

    def test_stored_as_fernet_not_plain(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.integrations.token_store._tokens_path", lambda: tmp_path / "tokens.json")
        set_provider_token("google", {"access_token": "check_mode"})
        raw = json.loads((tmp_path / "tokens.json").read_text(encoding="utf-8"))
        assert raw.get("mode") == "fernet"
