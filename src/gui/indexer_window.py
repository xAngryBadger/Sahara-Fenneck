"""
Tela secundária de indexação:
- planilhas abertas no Excel
- seleção múltipla de arquivos
- opcionalmente todas as abas
- limite de linhas por aba
- tentativa de drag-and-drop (se tkinterdnd2 estiver disponível)
"""
from __future__ import annotations

import logging
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path

import customtkinter as ctk

from ..indexing import (
    Workspace,
    index_file_multi,
    index_open_excel_workbooks,
    is_excel_file,
)
from . import styles as s

log = logging.getLogger(__name__)


class IndexerWindow(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        on_indexed: Callable[[list[Workspace], bool, int], None],
        default_include_all_sheets: bool = False,
        default_max_rows: int = 5000,
    ):
        super().__init__(parent)
        self.title("Indexar Planilhas")
        self.geometry("620x520")
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=s.BG_WARM)

        self._on_indexed = on_indexed
        self._selected_files: list[str] = []

        self._include_all_sheets = tk.BooleanVar(value=bool(default_include_all_sheets))
        self._max_rows_var = tk.StringVar(value=str(int(default_max_rows)))
        self._status_var = tk.StringVar(value="Selecione como deseja indexar.")

        self._build()

    def _build(self):
        root = ctk.CTkFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=14, pady=12)

        ctk.CTkLabel(
            root,
            text="Indexação de Planilhas",
            font=ctk.CTkFont(family=s.FONT_FAMILY, size=16, weight="bold"),
            text_color=s.DARK_TEXT,
            fg_color="transparent",
        ).pack(anchor="w")

        ctk.CTkLabel(
            root,
            text=(
                "Você pode indexar planilhas abertas no Excel ou escolher múltiplos arquivos.\n"
                "Para máquinas mais fracas, reduza o limite de linhas por aba (use 0 para carregar tudo)."
            ),
            font=ctk.CTkFont(family=s.FONT_FAMILY, size=12),
            text_color=s.MUTED_TEXT,
            justify="left",
            anchor="w",
            fg_color="transparent",
        ).pack(anchor="w", pady=(4, 10))

        opts = ctk.CTkFrame(root, fg_color="transparent")
        opts.pack(fill="x", pady=(0, 8))

        ctk.CTkCheckBox(
            opts,
            text="Indexar todas as abas",
            variable=self._include_all_sheets,
            text_color=s.DARK_TEXT,
            fg_color=s.ACTION_BG,
            border_color=s.ACTION_BORDER,
            checkmark_color=s.ACTION_TEXT,
        ).pack(side="left")

        ctk.CTkLabel(
            opts,
            text="Limite de linhas/aba:",
            text_color=s.DARK_TEXT,
            fg_color="transparent",
        ).pack(side="left", padx=(16, 6))

        ctk.CTkEntry(
            opts,
            width=100,
            textvariable=self._max_rows_var,
            fg_color=s.INPUT_BG,
            border_color=s.INPUT_BORDER,
            text_color=s.DARK_TEXT,
        ).pack(side="left")

        actions = ctk.CTkFrame(root, fg_color="transparent")
        actions.pack(fill="x", pady=(0, 8))

        ctk.CTkButton(
            actions,
            text="Indexar planilhas abertas no Excel",
            command=self._index_open_excel,
            fg_color=s.ACTION_BG,
            text_color=s.ACTION_TEXT,
            border_width=1,
            border_color=s.ACTION_BORDER,
            hover_color=s.ACTION_HOVER,
        ).pack(side="left")

        ctk.CTkButton(
            actions,
            text="Selecionar arquivos",
            command=self._pick_files,
            fg_color=s.ACTION_BG,
            text_color=s.ACTION_TEXT,
            border_width=1,
            border_color=s.ACTION_BORDER,
            hover_color=s.ACTION_HOVER,
        ).pack(side="left", padx=8)

        # Drop zone (tentativa opcional)
        self._drop_label = ctk.CTkLabel(
            root,
            text="Arraste e solte planilhas aqui (opcional)",
            text_color=s.MUTED_TEXT,
            fg_color=s.BUBBLE_BG,
            corner_radius=10,
            height=36,
        )
        self._drop_label.pack(fill="x", pady=(0, 8))
        self._enable_drop_if_available()

        self._files_box = ctk.CTkTextbox(
            root,
            height=220,
            fg_color=s.INPUT_BG,
            border_color=s.INPUT_BORDER,
            text_color=s.DARK_TEXT,
        )
        self._files_box.pack(fill="both", expand=True)
        self._files_box.insert("end", "Nenhum arquivo selecionado.\n")
        self._files_box.configure(state="disabled")

        bottom = ctk.CTkFrame(root, fg_color="transparent")
        bottom.pack(fill="x", pady=(8, 0))

        ctk.CTkButton(
            bottom,
            text="Indexar arquivos selecionados",
            command=self._index_selected_files,
            fg_color=s.ACTION_BG,
            text_color=s.ACTION_TEXT,
            border_width=1,
            border_color=s.ACTION_BORDER,
            hover_color=s.ACTION_HOVER,
        ).pack(side="left")

        ctk.CTkButton(
            bottom,
            text="Fechar",
            command=self.destroy,
            fg_color=s.ACTION_BG,
            text_color=s.ACTION_TEXT,
            border_width=1,
            border_color=s.ACTION_BORDER,
            hover_color=s.ACTION_HOVER,
        ).pack(side="right")

        ctk.CTkLabel(root, textvariable=self._status_var, text_color=s.MUTED_TEXT, fg_color="transparent").pack(
            anchor="w", pady=(8, 0)
        )

    def _enable_drop_if_available(self):
        """Ativa drag-and-drop se tkinterdnd2 estiver disponível no ambiente."""
        try:
            from tkinterdnd2 import DND_FILES  # type: ignore

            self._drop_label.drop_target_register(DND_FILES)
            self._drop_label.dnd_bind("<<Drop>>", self._on_drop)
            self._drop_label.configure(text="Arraste e solte planilhas aqui")
        except Exception:
            log.warning("tkinterdnd2 indisponível, drag-and-drop desativado")
            self._drop_label.configure(text="Arrastar arquivos indisponível (use Selecionar arquivos)")

    def _on_drop(self, event):
        try:
            dropped = [str(Path(p).resolve()) for p in self.tk.splitlist(event.data)]
            self._append_files(dropped)
        except Exception:
            log.exception("Falha ao processar arquivos arrastados")
            self._status_var.set("Falha ao processar arquivos arrastados.")

    def _get_max_rows(self) -> int:
        try:
            value = int(self._max_rows_var.get().strip())
            if value <= 0:
                return 0
            return max(100, min(value, 200000))
        except Exception:
            log.warning("Valor inválido para limite de linhas, usando padrão 5000")
            return 5000

    def _pick_files(self):
        from tkinter import filedialog

        paths = filedialog.askopenfilenames(
            title="Selecionar planilhas",
            filetypes=[("Planilhas", "*.xlsx *.xlsm *.xls *.ods"), ("Todos", "*.*")],
        )
        self._append_files(list(paths))

    def _append_files(self, files: list[str]):
        valid = []
        for f in files:
            if is_excel_file(f):
                valid.append(str(Path(f).resolve()))
        if not valid:
            self._status_var.set("Nenhum arquivo de planilha válido encontrado.")
            return

        current = set(self._selected_files)
        for f in valid:
            if f not in current:
                self._selected_files.append(f)

        self._refresh_files_box()
        self._status_var.set(f"{len(self._selected_files)} arquivo(s) selecionado(s).")

    def _refresh_files_box(self):
        self._files_box.configure(state="normal")
        self._files_box.delete("1.0", "end")
        if not self._selected_files:
            self._files_box.insert("end", "Nenhum arquivo selecionado.\n")
        else:
            for i, p in enumerate(self._selected_files, 1):
                self._files_box.insert("end", f"{i}. {p}\n")
        self._files_box.configure(state="disabled")

    def _index_open_excel(self):
        include_all = self._include_all_sheets.get()
        max_rows = self._get_max_rows()
        self._status_var.set("Indexando Excel aberto...")

        def worker():
            workspaces = index_open_excel_workbooks(include_all_sheets=include_all, max_rows=max_rows)
            self.after(0, lambda: self._finish_index(workspaces, include_all, max_rows))

        threading.Thread(target=worker, daemon=True).start()

    def _index_selected_files(self):
        if not self._selected_files:
            self._status_var.set("Selecione ao menos um arquivo.")
            return

        include_all = self._include_all_sheets.get()
        max_rows = self._get_max_rows()
        self._status_var.set("Indexando arquivos selecionados...")

        def worker():
            all_ws: list[Workspace] = []
            for p in self._selected_files:
                all_ws.extend(index_file_multi(p, include_all_sheets=include_all, max_rows=max_rows))
            self.after(0, lambda: self._finish_index(all_ws, include_all, max_rows))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_index(self, workspaces: list[Workspace], include_all: bool, max_rows: int):
        self._on_indexed(workspaces, include_all, max_rows)
        ok_count = sum(1 for w in workspaces if not w.error)
        err_count = len(workspaces) - ok_count
        self._status_var.set(f"Indexação concluída: {ok_count} ok, {err_count} erro(s).")
