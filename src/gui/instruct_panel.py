"""
Painel do Instruct Mode — ações rápidas + busca de funções Excel.
Substitui os SideButtons quando o modo Instruct está ativo.
"""
from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from . import styles as s

# Ações rápidas: (rótulo do botão, prefixo enviado ao agente)
QUICK_ACTIONS: list[tuple[str, str]] = [
    ("Ordenar", "Ordene a planilha por"),
    ("Filtrar", "Filtre a planilha onde"),
    ("Preencher vazios", "Preencha os valores vazios em"),
    ("Renomear coluna", "Renomeie a coluna"),
    ("Remover colunas", "Remova as colunas"),
    ("Criar coluna", "Crie uma nova coluna calculada,"),
    ("Duplicar aba", "Duplique a aba atual com o nome"),
    ("Nova aba", "Crie uma nova aba com o nome"),
    ("Substituir valor", "Substitua na planilha"),
]


class InstructPanel(ctk.CTkFrame):
    """
    Painel lateral do Instruct Mode.
    - Ações rápidas: botão → popup com campo de texto → manda pro agente
    - Buscar Funções: campo de busca → resultados locais + possibilidade de pedir ao agente
    """

    def __init__(
        self,
        parent,
        on_send: Callable[[str], None],
        on_function_ask: Callable[[str], None],
        on_close: Callable[[], None] | None = None,
        **kwargs,
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._on_send = on_send
        self._on_function_ask = on_function_ask
        self._on_close = on_close
        self._build()

    def _build(self):
        # Título
        ctk.CTkLabel(
            self,
            text="Ações Rápidas",
            font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.SMALL_SIZE, weight="bold"),
            text_color=s.DARK_TEXT,
            fg_color="transparent",
        ).pack(anchor="w", pady=(0, 4))

        # Botões de ação rápida
        for label, prefix in QUICK_ACTIONS:
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
                height=30,
                command=lambda p=prefix: self._open_quick_input(p),
            ).pack(pady=2)

        # Separador visual
        ctk.CTkFrame(self, height=1, fg_color=s.SIDE_BORDER).pack(fill="x", pady=8)

        # Buscar Funções
        ctk.CTkLabel(
            self,
            text="Buscar Funções",
            font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.SMALL_SIZE, weight="bold"),
            text_color=s.DARK_TEXT,
            fg_color="transparent",
        ).pack(anchor="w", pady=(0, 4))

        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.pack(fill="x")

        self._search_entry = ctk.CTkEntry(
            search_row,
            placeholder_text="ex: achar valor, filtrar...",
            placeholder_text_color=s.MUTED_TEXT,
            font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.TINY_SIZE),
            text_color=s.DARK_TEXT,
            fg_color=s.INPUT_BG,
            border_color=s.INPUT_BORDER,
            border_width=1,
            corner_radius=10,
            height=30,
            width=s.SIDE_BTN_W,
        )
        self._search_entry.pack(fill="x", pady=(0, 4))
        self._search_entry.bind("<Return>", lambda _e: self._do_function_search())

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x")

        ctk.CTkButton(
            btn_row,
            text="Buscar",
            font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.TINY_SIZE),
            text_color=s.ACTION_TEXT,
            fg_color=s.ACTION_BG,
            hover_color=s.ACTION_HOVER,
            border_width=1,
            border_color=s.ACTION_BORDER,
            corner_radius=10,
            width=60,
            height=26,
            command=self._do_function_search,
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            btn_row,
            text="Perguntar ao Fennec",
            font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.TINY_SIZE),
            text_color=s.SEND_BG,
            fg_color=s.ACTION_BG,
            hover_color=s.ACTION_HOVER,
            border_width=1,
            border_color=s.ACTION_BORDER,
            corner_radius=10,
            width=60,
            height=26,
            command=self._ask_agent_functions,
        ).pack(side="left")

        # Área de resultados
        self._results_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._results_frame.pack(fill="x", pady=(4, 0))

        # Botão voltar ao modo Chat
        if self._on_close:
            ctk.CTkFrame(self, height=1, fg_color=s.SIDE_BORDER).pack(fill="x", pady=8)
            ctk.CTkButton(
                self,
                text="← Voltar ao Chat",
                font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.TINY_SIZE),
                text_color=s.SIDE_TEXT,
                fg_color=s.SIDE_BG,
                hover_color=s.SIDE_HOVER,
                border_width=1,
                border_color=s.SIDE_BORDER,
                corner_radius=14,
                width=s.SIDE_BTN_W,
                height=30,
                command=self._on_close,
            ).pack(pady=2)

    def _open_quick_input(self, prefix: str):
        """Popup minimalista: o usuário digita em linguagem natural, concatena com o prefixo."""
        win = ctk.CTkToplevel(self.winfo_toplevel())
        win.title("Instrução")
        win.geometry("380x140")
        win.transient(self.winfo_toplevel())
        win.grab_set()
        win.configure(fg_color=s.BG_WARM)

        ctk.CTkLabel(
            win,
            text=prefix + "...",
            font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.SMALL_SIZE),
            text_color=s.DARK_TEXT,
            fg_color="transparent",
        ).pack(anchor="w", padx=12, pady=(10, 4))

        entry = ctk.CTkEntry(
            win,
            placeholder_text="descreva naturalmente (ex: coluna B, de Z a A)",
            placeholder_text_color=s.MUTED_TEXT,
            font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.SMALL_SIZE),
            text_color=s.DARK_TEXT,
            fg_color=s.INPUT_BG,
            border_color=s.INPUT_BORDER,
            border_width=1,
            corner_radius=12,
            height=34,
        )
        entry.pack(fill="x", padx=12, pady=(0, 8))
        entry.focus_set()

        def send(_event=None):
            txt = entry.get().strip()
            if txt:
                full = f"{prefix} {txt}"
                win.destroy()
                self._on_send(full)

        entry.bind("<Return>", send)

        ctk.CTkButton(
            win,
            text="Enviar",
            command=send,
            fg_color=s.SEND_BG,
            hover_color=s.SEND_HOVER,
            text_color=s.WHITE,
            corner_radius=12,
            height=30,
        ).pack(pady=(0, 10))

    def _do_function_search(self):
        """Busca local no catálogo e mostra resultados inline."""
        query = self._search_entry.get().strip()
        if not query:
            return

        from .excel_functions_catalog import search_functions

        results = search_functions(query, limit=5)

        # Limpar resultados anteriores
        for child in self._results_frame.winfo_children():
            child.destroy()

        if not results:
            ctk.CTkLabel(
                self._results_frame,
                text="Nenhuma função encontrada.",
                font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.TINY_SIZE),
                text_color=s.MUTED_TEXT,
                fg_color="transparent",
            ).pack(anchor="w")
            return

        for name, cat, desc in results:
            row = ctk.CTkFrame(self._results_frame, fg_color=s.BUBBLE_BG, corner_radius=8)
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(
                row,
                text=f"{name}",
                font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.TINY_SIZE, weight="bold"),
                text_color=s.DARK_TEXT,
                fg_color="transparent",
            ).pack(anchor="w", padx=6, pady=(2, 0))
            ctk.CTkLabel(
                row,
                text=desc,
                font=ctk.CTkFont(family=s.FONT_FAMILY, size=9),
                text_color=s.MUTED_TEXT,
                fg_color="transparent",
                wraplength=s.SIDE_BTN_W - 12,
                justify="left",
            ).pack(anchor="w", padx=6, pady=(0, 2))

    def _ask_agent_functions(self):
        """Manda a busca pro agente com contexto de 'sugerir funções'."""
        query = self._search_entry.get().strip()
        if not query:
            return
        self._search_entry.delete(0, "end")
        self._on_function_ask(query)
