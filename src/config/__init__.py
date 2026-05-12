"""Persistência de configurações do app no perfil do usuário."""
from .app_settings import DEFAULT_SETTINGS, get_settings_path, load_settings, save_settings

__all__ = ["load_settings", "save_settings", "get_settings_path", "DEFAULT_SETTINGS"]
