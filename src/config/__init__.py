# -*- coding: utf-8 -*-
"""Persistência de configurações do app no perfil do usuário."""
from .app_settings import load_settings, save_settings, get_settings_path, DEFAULT_SETTINGS

__all__ = ["load_settings", "save_settings", "get_settings_path", "DEFAULT_SETTINGS"]
