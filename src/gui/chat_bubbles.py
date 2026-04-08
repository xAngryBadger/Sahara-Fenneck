# -*- coding: utf-8 -*-
"""
Bolha de chat do Fennec -- avatar circular (cabecinha) + bolha macia.
"""
import customtkinter as ctk
from . import styles as s


class FennecBubble(ctk.CTkFrame):
    """Avatar do chatbot + bolha de fala arredondada."""

    def __init__(self, parent, text: str, avatar_image=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._avatar = avatar_image
        self._label = None
        self._build(text)
        self.bind("<Configure>", self._update_wrap)

    def _build(self, text: str):
        # Avatar (cabecinha do Fennec)
        if self._avatar:
            ctk.CTkLabel(
                self, text="", image=self._avatar, fg_color="transparent",
            ).pack(side="left", padx=(0, 10), anchor="n", pady=(4, 0))

        # Bolha de fala (macia, cantos grandes)
        bubble = ctk.CTkFrame(
            self,
            fg_color=s.BUBBLE_BG,
            corner_radius=20,
            border_width=1,
            border_color=s.BUBBLE_BORDER,
        )
        bubble.pack(side="left", fill="x", expand=True)
        self._label = ctk.CTkLabel(
            bubble,
            text=text,
            font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.BODY_SIZE),
            text_color=s.DARK_TEXT,
            fg_color="transparent",
            wraplength=320,
            justify="left",
            anchor="w",
        )
        self._label.pack(padx=16, pady=14, anchor="w")
        bubble.bind("<Configure>", self._update_wrap)

    def _update_wrap(self, _event=None):
        if not self._label:
            return
        # Ajusta wrap dinamicamente para evitar cortar palavras em janela pequena.
        base = int(self.winfo_width() or 0)
        if base <= 0:
            return
        avatar_space = 68 if self._avatar else 16
        wrap = max(140, base - avatar_space - 52)
        self._label.configure(wraplength=wrap)


class UserBubble(ctk.CTkFrame):
    """Bolha do usuário (direita, sem avatar)."""

    def __init__(self, parent, text: str, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._label = None
        bubble = ctk.CTkFrame(
            self,
            fg_color=s.BUBBLE_BG,
            corner_radius=20,
            border_width=1,
            border_color=s.BUBBLE_BORDER,
        )
        bubble.pack(side="right", fill="x", expand=True)
        self._label = ctk.CTkLabel(
            bubble,
            text=text,
            font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.BODY_SIZE),
            text_color=s.DARK_TEXT,
            fg_color="transparent",
            wraplength=320,
            justify="right",
            anchor="e",
        )
        self._label.pack(padx=16, pady=14, anchor="e")
        self.bind("<Configure>", self._update_wrap)
        bubble.bind("<Configure>", self._update_wrap)

    def _update_wrap(self, _event=None):
        if not self._label:
            return
        base = int(self.winfo_width() or 0)
        if base <= 0:
            return
        wrap = max(140, base - 48)
        self._label.configure(wraplength=wrap)
