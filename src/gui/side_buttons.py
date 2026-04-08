# -*- coding: utf-8 -*-
"""
Botões laterais de navegação principal.
"""
import customtkinter as ctk
from . import styles as s


class SideButtons(ctk.CTkFrame):
    def __init__(self, parent, on_index, on_multi, on_config, on_help, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        items = [
            ("Indexar Agora", on_index),
            ("MultiPlanilhas", on_multi),
            ("Configurações", on_config),
            ("Ajuda / Exemplos", on_help),
        ]
        for label, cmd in items:
            ctk.CTkButton(
                self,
                text=label,
                font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.TINY_SIZE),
                text_color=s.SIDE_TEXT,
                fg_color=s.SIDE_BG,
                hover_color=s.SIDE_HOVER,
                border_width=1,
                border_color=s.SIDE_BORDER,
                corner_radius=14,
                width=s.SIDE_BTN_W,
                height=s.SIDE_BTN_H,
                command=cmd,
            ).pack(pady=4)
