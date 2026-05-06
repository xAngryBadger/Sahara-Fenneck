# -*- coding: utf-8 -*-
"""
Botao com estilo gradiente 3D transparente (claro no topo, sombra suave embaixo).
Simulado com faixas CTkFrame para compatibilidade com CustomTkinter.
"""
import customtkinter as ctk
from . import styles as s


class GradientButton(ctk.CTkFrame):
    """Botao com fundo em gradiente vertical (estilo 3D transparente)."""

    def __init__(self, parent, text: str, command=None, width=None, height=None,
                 corner_radius=None, font=None, fg_top=None, fg_bottom=None,
                 fg_top_hover=None, fg_bottom_hover=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._command = command
        self._w = width or 280
        self._h = height or s.BUTTON_HEIGHT
        self._r = corner_radius or s.BUTTON_CORNER
        self._top = fg_top or "#FAF6F0"
        self._bottom = fg_bottom or "#EDE4D8"
        self._top_hover = fg_top_hover or "#F5EDE2"
        self._bottom_hover = fg_bottom_hover or "#E8DCC8"
        self._font = font or ctk.CTkFont(family=s.FONT_FAMILY, size=s.SMALL_SIZE, weight="bold")
        self._text = text
        self._build()

    def _build(self):
        # Faixas de gradiente (3 faixas para efeito suave)
        self._bands = []
        colors = [self._top, self._mid_color(self._top, self._bottom), self._bottom]
        for color in colors:
            band = ctk.CTkFrame(
                self, fg_color=color, corner_radius=0, height=max(1, self._h // 3),
                border_width=0,
            )
            band.pack(fill="x")
            band.pack_propagate(False)
            self._bands.append((band, color))
        # Label por cima (centralizado)
        self._label = ctk.CTkLabel(
            self, text=self._text, font=self._font, text_color=s.ACTION_TEXT,
            fg_color="transparent",
        )
        self._label.place(relx=0.5, rely=0.5, anchor="center")
        # Borda suave
        self.configure(border_width=1, border_color=s.ACTION_BORDER, corner_radius=self._r)
        # Clique e hover
        for band, _ in self._bands:
            band.bind("<Button-1>", self._on_click)
            band.bind("<Enter>", self._on_enter)
            band.bind("<Leave>", self._on_leave)
        self._label.bind("<Button-1>", self._on_click)
        self._label.bind("<Enter>", self._on_enter)
        self._label.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    @staticmethod
    def _mid_color(hex1: str, hex2: str) -> str:
        h1, h2 = hex1.lstrip("#"), hex2.lstrip("#")
        r = (int(h1[0:2], 16) + int(h2[0:2], 16)) // 2
        g = (int(h1[2:4], 16) + int(h2[2:4], 16)) // 2
        b = (int(h1[4:6], 16) + int(h2[4:6], 16)) // 2
        return f"#{r:02x}{g:02x}{b:02x}"

    def _set_band_colors(self, top: str, bottom: str):
        mid = self._mid_color(top, bottom)
        colors = [top, mid, bottom]
        for (band, _), color in zip(self._bands, colors):
            band.configure(fg_color=color)

    def _on_enter(self, _e):
        self._set_band_colors(self._top_hover, self._bottom_hover)

    def _on_leave(self, _e):
        self._set_band_colors(self._top, self._bottom)

    def _on_click(self, _e):
        if self._command:
            self._command()
