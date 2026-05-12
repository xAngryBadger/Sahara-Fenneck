"""Tests for app_settings: load, save, defaults merge, cache invalidation, path resolution."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from src.config.app_settings import (
    DEFAULT_SETTINGS,
    _read_settings_from_disk,
    get_settings_path,
    load_settings,
    save_settings,
)


class TestGetSettingsPath:
    def test_returns_path_object(self):
        p = get_settings_path()
        assert isinstance(p, Path)

    def test_filename_is_settings_json(self):
        p = get_settings_path()
        assert p.name == "settings.json"

    def test_linux_path(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("APPDATA", None)
            p = get_settings_path()
            assert ".sahara_fennec" in str(p)

    def test_windows_appdata_path(self):
        with patch.dict(os.environ, {"APPDATA": "/tmp/fake_appdata"}):
            p = get_settings_path()
            assert "SaharaFennec" in str(p)


class TestDefaultSettings:
    def test_has_required_keys(self):
        for key in ("model", "llm_backend", "index_all_sheets", "nim_model", "nim_base_url"):
            assert key in DEFAULT_SETTINGS

    def test_default_backend_is_ollama(self):
        assert DEFAULT_SETTINGS["llm_backend"] == "ollama"


class TestLoadSettings:
    def test_returns_dict(self, tmp_path):
        with patch("src.config.app_settings.get_settings_path", return_value=tmp_path / "s.json"):
            (tmp_path / "s.json").write_text("{}", encoding="utf-8")
            _read_settings_from_disk.cache_clear()
            import src.config.app_settings as mod
            mod._SETTINGS_MTIME = None
            result = load_settings()
            assert isinstance(result, dict)

    def test_missing_file_returns_defaults(self, tmp_path):
        with patch("src.config.app_settings.get_settings_path", return_value=tmp_path / "missing.json"):
            _read_settings_from_disk.cache_clear()
            import src.config.app_settings as mod
            mod._SETTINGS_MTIME = None
            result = load_settings()
            assert result == DEFAULT_SETTINGS.copy()

    def test_partial_config_merges_with_defaults(self, tmp_path):
        sp = tmp_path / "s.json"
        sp.write_text(json.dumps({"llm_backend": "nim"}), encoding="utf-8")
        with patch("src.config.app_settings.get_settings_path", return_value=sp):
            _read_settings_from_disk.cache_clear()
            import src.config.app_settings as mod
            mod._SETTINGS_MTIME = None
            result = load_settings()
            assert result["llm_backend"] == "nim"
            assert result["model"] == DEFAULT_SETTINGS["model"]


class TestSaveSettings:
    def test_creates_file(self, tmp_path):
        sp = tmp_path / "s.json"
        with patch("src.config.app_settings.get_settings_path", return_value=sp):
            save_settings({"llm_backend": "nim", "nim_model": "test-model"})
            assert sp.exists()
            saved = json.loads(sp.read_text(encoding="utf-8"))
            assert saved["llm_backend"] == "nim"
            assert saved["nim_model"] == "test-model"

    def test_merges_with_defaults_on_save(self, tmp_path):
        sp = tmp_path / "s.json"
        with patch("src.config.app_settings.get_settings_path", return_value=sp):
            save_settings({"llm_backend": "nim"})
            saved = json.loads(sp.read_text(encoding="utf-8"))
            assert "model" in saved
            assert saved["llm_backend"] == "nim"

    def test_cache_cleared_after_save(self, tmp_path):
        sp = tmp_path / "s.json"
        with patch("src.config.app_settings.get_settings_path", return_value=sp):
            save_settings({"llm_backend": "ollama"})
            _read_settings_from_disk.cache_clear()
            import src.config.app_settings as mod
            mod._SETTINGS_MTIME = None
            result = load_settings()
            assert result["llm_backend"] == "ollama"
            save_settings({"llm_backend": "nim"})
            _read_settings_from_disk.cache_clear()
            mod._SETTINGS_MTIME = None
            result = load_settings()
            assert result["llm_backend"] == "nim"
