"""
Client IDs OAuth - VOCÊ configura UMA VEZ aqui. Os usuários só clicam e fazem login.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

# =============================================================================
# PREENCHA AQUI (uma vez) após criar OAuth apps no Google Cloud e Azure.
# Depois disso, os usuários só clicam "Entrar com Google/Microsoft" e fazem
# login com email/senha normalmente. Ninguém vê ou configura Client ID.
# Guia: docs/OAUTH-SETUP.md
# =============================================================================
EMBEDDED_GOOGLE_CLIENT_ID = ""
EMBEDDED_MICROSOFT_CLIENT_ID = ""


def _load_json_defaults() -> tuple[str, str]:
    """Carrega de oauth_defaults.json (appdata ou raiz do projeto)."""
    g, m = "", ""
    candidates: list[Path] = []
    appdata = os.environ.get("APPDATA") or str(Path.home() / ".sahara_fennec")
    candidates.append(Path(appdata) / "SaharaFennec" / "oauth_defaults.json")
    try:
        root = Path(__file__).resolve().parent.parent.parent
        candidates.append(root / "oauth_defaults.json")
    except Exception:
        log.warning("Falha ao resolver caminho raiz do projeto para oauth_defaults.json")

    for p in candidates:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    g = str(data.get("google_client_id", "") or "").strip()
                    m = str(data.get("microsoft_client_id", "") or "").strip()
                    if g or m:
                        return g, m
            except Exception:
                log.warning("Falha ao carregar oauth_defaults.json de %s", p)
    return "", ""


def get_default_client_id(provider: str) -> str:
    """Client ID para o provider. Ordem: embutido > env > oauth_defaults.json."""
    provider = provider.strip().lower()
    json_g, json_m = _load_json_defaults()
    if provider == "google":
        return (
            (EMBEDDED_GOOGLE_CLIENT_ID or "").strip()
            or os.environ.get("FENNEC_GOOGLE_CLIENT_ID", "").strip()
            or json_g
        )
    if provider == "microsoft":
        return (
            (EMBEDDED_MICROSOFT_CLIENT_ID or "").strip()
            or os.environ.get("FENNEC_MICROSOFT_CLIENT_ID", "").strip()
            or json_m
        )
    return ""
