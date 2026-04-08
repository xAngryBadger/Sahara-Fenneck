# -*- coding: utf-8 -*-
"""
Persona configurável para o agente (Fennec padrão; depois outros temas).
"""
from pathlib import Path

# Caminho base para assets (relativo a raiz do projeto)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ASSETS = PROJECT_ROOT / "assets"

FENNEC_DEFAULT = {
    "name": "Sahara Fennec",
    "welcome_message": "Olá! Eu sou Fennec Excel, seu agente pessoal de planilhas!\n\nIndexe sua planilha e me diga o que otimizar.",
    "avatar_path": str(ASSETS / "fennec_icon.png"),
    "head_icon_path": str(ASSETS / "fennec_head_icon.png"),  # cabecinha para ícone do app / intro
    "watermark_path": str(ASSETS / "fennec_mascot_transparent.png"),
    "sound_greeting_path": None,
    "animation_enabled": False,
    "show_intro_on_start": False,  # animação de intro com a cabecinha (placeholder)
}


def get_persona(name: str = "fennec") -> dict:
    """Retorna config da persona. Por enquanto só 'fennec'."""
    if name == "fennec":
        return FENNEC_DEFAULT.copy()
    return FENNEC_DEFAULT.copy()
