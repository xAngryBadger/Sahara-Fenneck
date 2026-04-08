# -*- coding: utf-8 -*-
"""
Painel de dicas (tips) -- sempre visivel, abaixo dos botoes de acao.
Label + grade de botoes em 2 colunas para nao estourar a largura.
"""
import customtkinter as ctk
from . import styles as s

DEFAULT_TIPS = [
    ("Crie um funil de vendas", "Crie um funil de vendas por regiao nesta planilha"),
    ("Analise o churn rate", "Analise o churn rate dos dados nesta planilha"),
    ("Graficos por regiao", "Crie graficos de pizza por regiao com os dados desta planilha"),
    ("Consultar Agenda", "Traga os compromissos da minha agenda para esta planilha"),
    ("Enviar por Email", "Envie um resumo desta planilha por e-mail"),
    ("Resumo no Teams", "Envie um resumo desta planilha no Teams"),
]


class TipsPanel(ctk.CTkFrame):
    """Painel de sugestoes em grid 2 colunas, com titulo."""

    def __init__(self, parent, on_tip_click, tips=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._on_tip = on_tip_click
        self._tips = tips or DEFAULT_TIPS
        self._build()

    def _build(self):
        # Titulo
        ctk.CTkLabel(
            self,
            text="Sugestoes",
            font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.SMALL_SIZE, weight="bold"),
            text_color=s.MUTED_TEXT,
            fg_color="transparent",
        ).pack(anchor="w", pady=(0, 6))

        # Grid de tips (2 colunas)
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x")
        for i, (label, query) in enumerate(self._tips):
            row, col = divmod(i, 2)
            btn = ctk.CTkButton(
                grid,
                text=label,
                font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.TINY_SIZE),
                text_color=s.DARK_TEXT,
                fg_color=s.TIP_BG,
                hover_color=s.TIP_HOVER,
                corner_radius=10,
                height=28,
                border_width=0,
                command=lambda q=query: self._on_tip(q),
            )
            btn.grid(row=row, column=col, padx=(0, 6), pady=2, sticky="ew")
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
