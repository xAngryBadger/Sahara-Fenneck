# -*- coding: utf-8 -*-
"""
Gradiente vertical otimizado (usa faixas em vez de pixel-a-pixel para performance).
"""
import tkinter as tk
from . import styles as s

BANDS = 120  # mais faixas = mais suave, mas razoável para performance


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _lerp_color(c1: tuple, c2: tuple, t: float) -> str:
    r = int(c1[0] + (c2[0] - c1[0]) * t)
    g = int(c1[1] + (c2[1] - c1[1]) * t)
    b = int(c1[2] + (c2[2] - c1[2]) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def draw_vertical_gradient(canvas: tk.Canvas, top_hex: str = None, bottom_hex: str = None):
    top_hex = top_hex or s.GRADIENT_TOP
    bottom_hex = bottom_hex or s.GRADIENT_BOTTOM
    canvas.delete("gradient")
    canvas.update_idletasks()
    w = canvas.winfo_width() or 500
    h = canvas.winfo_height() or 600
    c1 = _hex_to_rgb(top_hex)
    c2 = _hex_to_rgb(bottom_hex)
    band_h = max(1, h / BANDS)
    for i in range(BANDS):
        t = i / (BANDS - 1) if BANDS > 1 else 1
        color = _lerp_color(c1, c2, t)
        y0 = int(i * band_h)
        y1 = int((i + 1) * band_h) + 1
        canvas.create_rectangle(0, y0, w + 2, y1, fill=color, outline=color, tags="gradient")
