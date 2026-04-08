# -*- coding: utf-8 -*-
"""
Sahara Fennec - Janela principal (UI + backend integrado).
"""
import tkinter as tk
from pathlib import Path
import threading
import subprocess

import customtkinter as ctk

from . import styles as s
from .side_buttons import SideButtons
from .instruct_panel import InstructPanel
from .input_bar import InputBar
from .chat_bubbles import FennecBubble, UserBubble
from .gradient import draw_vertical_gradient
from .indexer_window import IndexerWindow

from ..indexing import Workspace
from ..checkpoints import CheckpointManager
from ..config import load_settings, save_settings

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ASSETS = _PROJECT_ROOT / "assets"
_BG_CANDIDATES = [
    _PROJECT_ROOT / "fundodeserto.png",  # prioridade: arquivo na raiz (pedido do usuário)
    _ASSETS / "fundodeserto.png",
    _ASSETS / "desert_bg.png",
]
DEFAULT_MODEL = "qwen2.5:7b"
APP_VERSION = "2.0"


def _ctk_img(path: Path, size: tuple[int, int]):
    try:
        from PIL import Image

        return ctk.CTkImage(
            light_image=Image.open(path).convert("RGBA"),
            dark_image=Image.open(path).convert("RGBA"),
            size=size,
        )
    except Exception:
        return None


class MainWindow:
    def __init__(self, persona: dict):
        self.persona = persona
        self._imgs = {}
        self._workspaces: dict[str, Workspace] = {}
        self._active_key: str | None = None
        self._last_fennec_message = ""
        self._pinned = False
        self._instruct_mode = False
        self._indexer_window = None

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title(f"Sahara Fennec {APP_VERSION}")

        # Config persistida (agora com root j? criado)
        cfg = load_settings()
        self._model_name = tk.StringVar(master=self.root, value=str(cfg.get("model", DEFAULT_MODEL)))
        self._include_all_sheets = tk.BooleanVar(master=self.root, value=bool(cfg.get("index_all_sheets", False)))
        self._max_rows_per_sheet = tk.IntVar(master=self.root, value=int(cfg.get("max_rows_per_sheet", 0)))
        self.root.minsize(s.WINDOW_MIN_WIDTH, s.WINDOW_MIN_HEIGHT)
        self.root.geometry(f"{s.WINDOW_DEFAULT_WIDTH}x{s.WINDOW_DEFAULT_HEIGHT}")
        self.root.configure(fg_color=s.BG_WARM)

        self._load_assets()
        self._set_icon()
        self._build()
        self.root.after(800, self._check_pending_models)

    def _load_assets(self):
        head = _ASSETS / "fennec_head_icon.png"
        if head.exists():
            self._imgs["head_avatar"] = _ctk_img(head, s.AVATAR_SIZE)

    def _check_pending_models(self):
        import os
        pending = Path(os.environ.get("APPDATA", "")) / "SaharaFennec" / "pending_models.txt"
        if pending.exists():
            try:
                models = [m.strip() for m in pending.read_text(encoding="utf-8").splitlines() if m.strip()]
                if models:
                    self._add_fennec_bubble(
                        f"⏳ O modelo de IA ({', '.join(models)}) ainda está sendo baixado em segundo plano. "
                        "Isso pode levar alguns minutos dependendo da sua conexão. "
                        "Você poderá usar o app normalmente assim que o download for concluído."
                    )
            except Exception:
                pass

    def _set_icon(self):
        ico = _ASSETS / "fennec_head_icon.ico"
        if ico.exists():
            try:
                self.root.iconbitmap(str(ico))
            except Exception:
                pass

    def _draw_bg(self, _ev=None):
        self._bg.delete("all")
        self._bg.update_idletasks()
        w = max(1, self._bg.winfo_width() or 500)
        h = max(1, self._bg.winfo_height() or 600)
        path = next((p for p in _BG_CANDIDATES if p.exists()), _ASSETS / "desert_bg.png")
        if path.exists():
            try:
                from PIL import Image
                from PIL.ImageTk import PhotoImage

                img = Image.open(path).convert("RGB")
                img = img.resize((w, h), Image.Resampling.LANCZOS)
                self._bg_photo = PhotoImage(img)
                self._bg.create_image(0, 0, anchor="nw", image=self._bg_photo, tags="bg")
            except Exception:
                self._bg_photo = None
                draw_vertical_gradient(self._bg)
        else:
            self._bg_photo = None
            draw_vertical_gradient(self._bg)

    def _build(self):
        self._bg_photo = None
        self._bg = tk.Canvas(self.root, highlightthickness=0, bd=0)
        self._bg.place(x=0, y=0, relwidth=1, relheight=1)
        self._bg.bind("<Configure>", self._draw_bg)

        main = ctk.CTkFrame(self.root, fg_color="transparent", corner_radius=0)
        main.place(x=0, y=0, relwidth=1, relheight=1)

        # Topo limpo
        top = ctk.CTkFrame(main, height=s.TITLE_BAR_HEIGHT, fg_color=s.TOP_BAR_BG, corner_radius=0)
        top.pack(fill="x")
        top.pack_propagate(False)

        bar_r = ctk.CTkFrame(top, fg_color="transparent")
        bar_r.pack(side="right", padx=8)
        self._pin_btn = self._top_btn(bar_r, "Pin", self._toggle_pin)
        self._mode_btn = self._top_btn(bar_r, "Instruct", self._toggle_instruct_mode)
        self._top_btn(bar_r, "Check", self._on_checkpoints)
        self._top_btn(bar_r, "Nova", self._on_new_session)

        body = ctk.CTkFrame(main, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=(12, 6))

        cols = ctk.CTkFrame(body, fg_color="transparent")
        cols.pack(fill="both", expand=True)

        left = ctk.CTkFrame(cols, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True)

        self._right_frame = ctk.CTkFrame(cols, fg_color="transparent")
        self._right_frame.pack(side="right", anchor="n", padx=(14, 0))

        # Chat
        self._chat_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent", height=180)
        self._chat_scroll.pack(fill="both", expand=True, pady=(0, 8))
        self._hide_scrollbar(self._chat_scroll)
        self._reset_chat()

        # Botões laterais (modo Chat — padrão)
        self._side_buttons = SideButtons(
            self._right_frame,
            on_index=self._open_indexer,
            on_multi=self._on_multiplanilhas,
            on_config=self._on_settings,
            on_help=self._on_help,
        )
        self._side_buttons.pack(anchor="n")

        # Painel Instruct (criado mas escondido)
        self._instruct_panel = InstructPanel(
            self._right_frame,
            on_send=self._on_send,
            on_function_ask=self._on_function_ask,
            on_close=self._toggle_instruct_mode,
        )

        # Status
        self.status_var = tk.StringVar(value="Pronto  |  Nenhuma planilha indexada")
        ctk.CTkLabel(
            main,
            textvariable=self.status_var,
            font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.TINY_SIZE),
            text_color=s.MUTED_TEXT,
            fg_color="transparent",
        ).pack(side="bottom", pady=(0, 2))

        # Input
        self.input_bar = InputBar(main, self._on_send)
        self.input_bar.pack(side="bottom", fill="x", padx=18, pady=(0, 12))

    # Helpers de UI

    def _top_btn(self, parent, text, cmd):
        b = ctk.CTkButton(
            parent,
            text=text,
            font=ctk.CTkFont(family=s.FONT_FAMILY, size=10),
            text_color=s.TOP_BAR_TEXT,
            fg_color="transparent",
            hover_color=s.TOP_BAR_HOVER,
            width=42,
            height=24,
            corner_radius=6,
            command=cmd,
        )
        b.pack(side="left", padx=1)
        return b

    def _hide_scrollbar(self, scrollable: ctk.CTkScrollableFrame):
        """Deixa scrollbar visualmente invisível (scroll por mouse/trackpad continua)."""
        try:
            sb = scrollable._scrollbar  # acesso interno do CTkScrollableFrame
            sb.configure(width=0, fg_color="transparent", button_color="transparent", button_hover_color="transparent")
            try:
                sb.grid_remove()
            except Exception:
                pass
        except Exception:
            pass

    def _scroll_chat_bottom(self):
        try:
            self.root.after(10, lambda: self._chat_scroll._parent_canvas.yview_moveto(1.0))
        except Exception:
            pass

    def _reset_chat(self):
        for child in self._chat_scroll.winfo_children():
            child.destroy()

        welcome = self.persona.get(
            "welcome_message",
            "Olá! Eu sou Fennec Excel, seu agente pessoal de planilhas!",
        )
        self._last_fennec_message = ""
        self._add_fennec_bubble(welcome)
        self._add_fennec_bubble(
            "Use 'Indexar Agora' na lateral para abrir a tela de indexação e escolher uma ou múltiplas planilhas/abas."
        )

    def _workspace_key(self, ws: Workspace) -> str:
        book = ws.workbook_name or Path(ws.path).name or "Planilha"
        return f"{book} :: {ws.sheet_name}"

    def _active_workspace(self) -> Workspace | None:
        if not self._workspaces:
            return None
        if self._active_key and self._active_key in self._workspaces:
            return self._workspaces[self._active_key]
        self._active_key = next(iter(self._workspaces.keys()))
        return self._workspaces[self._active_key]

    def _workspace_status(self) -> str:
        active = self._active_workspace()
        if not active:
            return "Pronto  |  Nenhuma planilha indexada"
        return f"{active.summary_one_line()} | sessão: {len(self._workspaces)} item(ns)"

    def _save_current_settings(self, extra: dict | None = None):
        payload = load_settings()
        payload.update(
            {
            "model": self._model_name.get().strip() or DEFAULT_MODEL,
            "index_all_sheets": bool(self._include_all_sheets.get()),
            "max_rows_per_sheet": int(self._max_rows_per_sheet.get()),
            }
        )
        if extra:
            payload.update(extra)
        save_settings(payload)

    # Fluxos de indexação

    def _open_indexer(self):
        if self._indexer_window is not None:
            try:
                if self._indexer_window.winfo_exists():
                    self._indexer_window.focus()
                    return
            except Exception:
                pass

        self._indexer_window = IndexerWindow(
            self.root,
            on_indexed=self._on_workspaces_indexed,
            default_include_all_sheets=self._include_all_sheets.get(),
            default_max_rows=self._max_rows_per_sheet.get(),
        )

    def _on_workspaces_indexed(self, workspaces: list[Workspace], include_all_sheets: bool, max_rows: int):
        self._include_all_sheets.set(bool(include_all_sheets))
        self._max_rows_per_sheet.set(int(max_rows))
        self._save_current_settings()

        ok = 0
        errs = []
        for ws in workspaces:
            if ws.error:
                errs.append(f"{ws.workbook_name or ws.path}: {ws.error}")
                continue
            key = self._workspace_key(ws)
            self._workspaces[key] = ws
            self._active_key = key
            ok += 1

        if ok > 0:
            self._add_fennec_bubble(f"Indexação concluída: {ok} aba(s) carregada(s). Planilha ativa: {self._active_key}.")
        if errs:
            self._add_fennec_bubble("Algumas indexações falharam:\n- " + "\n- ".join(errs[:4]))

        self.status_var.set(self._workspace_status())

    # Chat / agente

    def _on_send(self, text: str):
        text = text.strip()
        if not text:
            return

        ws = self._active_workspace()
        if ws is None or ws.error:
            self._add_fennec_bubble("Indexe ao menos uma planilha antes de enviar consultas.")
            return

        self._add_user_bubble(text)
        self.status_var.set("Processando...")
        self.input_bar.entry.configure(state="disabled")

        model_name = self._model_name.get().strip() or DEFAULT_MODEL

        def run():
            try:
                from src.agent.runner import run_agent
                from src.agent.ollama_client import OllamaClient

                client = OllamaClient(model=model_name)

                def on_msg(msg: str):
                    self.root.after(0, lambda m=msg: self._add_fennec_bubble(m))

                def on_cp(label: str):
                    self.root.after(0, lambda: self.status_var.set(f"Checkpoint salvo: {label}"))

                def on_confirm(preview: str) -> bool:
                    return self._confirm_change_blocking(preview)

                run_agent(
                    text,
                    ws,
                    ollama=client,
                    on_message=on_msg,
                    on_checkpoint=on_cp,
                    on_confirm_change=on_confirm,
                )
                self.root.after(0, self._agent_done)
            except Exception as e:
                self.root.after(0, lambda: self._agent_done(error=f"Erro: {e!s}"))

        threading.Thread(target=run, daemon=True).start()

    def _agent_done(self, error: str | None = None):
        self.input_bar.entry.configure(state="normal")
        if error:
            self._add_fennec_bubble(error)
        self.status_var.set(self._workspace_status())

    def _add_user_bubble(self, text: str):
        UserBubble(self._chat_scroll, text).pack(anchor="e", fill="x", pady=(0, 6), padx=(0, 10))
        self._scroll_chat_bottom()

    def _add_fennec_bubble(self, text: str):
        clean = (text or "").strip()
        if not clean:
            return
        # Evita mensagens duplicadas consecutivas
        if clean == self._last_fennec_message:
            return
        self._last_fennec_message = clean

        FennecBubble(self._chat_scroll, clean, avatar_image=self._imgs.get("head_avatar")).pack(
            anchor="w", fill="x", pady=(0, 6), padx=(0, 10)
        )
        self._scroll_chat_bottom()

    def _confirm_change_blocking(self, preview_text: str) -> bool:
        """Exibe uma modal de preview/confirmacao no thread da UI e aguarda a decisao."""
        decision = threading.Event()
        result = {"approved": False}

        def show_dialog():
            self.status_var.set("Aguardando confirmacao para alterar a planilha...")

            win = ctk.CTkToplevel(self.root)
            win.title(f"Confirmar alteracao - Sahara Fennec {APP_VERSION}")
            win.geometry("760x520")
            win.transient(self.root)
            win.configure(fg_color=s.BG_WARM)

            ctk.CTkLabel(
                win,
                text="Revise a previa antes de alterar a planilha",
                font=ctk.CTkFont(family=s.FONT_FAMILY, size=16, weight="bold"),
                text_color=s.DARK_TEXT,
                fg_color="transparent",
            ).pack(anchor="w", padx=14, pady=(14, 6))

            ctk.CTkLabel(
                win,
                text="Se confirmar, o Fennec aplica a ordem e salva checkpoint automatico antes da primeira alteracao.",
                text_color=s.MUTED_TEXT,
                fg_color="transparent",
                wraplength=720,
                justify="left",
            ).pack(anchor="w", padx=14, pady=(0, 10))

            box = ctk.CTkTextbox(
                win,
                wrap="word",
                fg_color=s.INPUT_BG,
                border_color=s.INPUT_BORDER,
                text_color=s.DARK_TEXT,
            )
            box.pack(fill="both", expand=True, padx=14, pady=(0, 12))
            box.insert("1.0", preview_text)
            box.configure(state="disabled")

            footer = ctk.CTkFrame(win, fg_color="transparent")
            footer.pack(fill="x", padx=14, pady=(0, 14))

            btn_style = dict(
                fg_color=s.ACTION_BG,
                text_color=s.ACTION_TEXT,
                border_width=1,
                border_color=s.ACTION_BORDER,
                hover_color=s.ACTION_HOVER,
            )

            def approve():
                result["approved"] = True
                decision.set()
                win.destroy()

            def reject():
                result["approved"] = False
                decision.set()
                win.destroy()

            ctk.CTkButton(footer, text="Cancelar", width=110, command=reject, **btn_style).pack(side="right")
            ctk.CTkButton(footer, text="Confirmar", width=110, command=approve, **btn_style).pack(side="right", padx=(0, 8))

            win.protocol("WM_DELETE_WINDOW", reject)
            try:
                win.grab_set()
                win.focus()
            except Exception:
                pass

        self.root.after(0, show_dialog)
        decision.wait()

        if result["approved"]:
            self.root.after(0, lambda: self.status_var.set("Confirmado. Aplicando alteracoes..."))
        else:
            self.root.after(0, lambda: self.status_var.set("Alteracao cancelada pelo usuario."))
        return bool(result["approved"])

    # Sessão / workspaces

    def _on_multiplanilhas(self):
        win = ctk.CTkToplevel(self.root)
        win.title("MultiPlanilhas")
        win.geometry("520x360")
        win.transient(self.root)
        win.configure(fg_color=s.BG_WARM)

        _btn_style = dict(
            fg_color=s.ACTION_BG,
            text_color=s.ACTION_TEXT,
            border_width=1,
            border_color=s.ACTION_BORDER,
            hover_color=s.ACTION_HOVER,
        )
        ctk.CTkLabel(
            win,
            text="Planilhas e abas indexadas na sessão",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="transparent",
            text_color=s.DARK_TEXT,
        ).pack(anchor="w", padx=10, pady=(10, 6))

        box = ctk.CTkScrollableFrame(win, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=10, pady=6)

        if not self._workspaces:
            ctk.CTkLabel(box, text="Nenhuma planilha indexada.", fg_color="transparent", text_color=s.MUTED_TEXT).pack(
                anchor="w"
            )

        for key, ws in self._workspaces.items():
            row = ctk.CTkFrame(box, fg_color="transparent")
            row.pack(fill="x", pady=3)

            tag = " (ativa)" if key == self._active_key else ""
            ctk.CTkLabel(row, text=f"{key}{tag}", fg_color="transparent", text_color=s.DARK_TEXT).pack(side="left")

            def do_activate(k=key, w=win):
                self._active_key = k
                self.status_var.set(self._workspace_status())
                self._add_fennec_bubble(f"Planilha ativa alterada para: {k}")
                w.destroy()

            def do_remove(k=key, w=win):
                if k in self._workspaces:
                    del self._workspaces[k]
                if self._active_key == k:
                    self._active_key = None
                self.status_var.set(self._workspace_status())
                w.destroy()
                self._on_multiplanilhas()

            ctk.CTkButton(row, text="Ativar", width=70, command=do_activate, **_btn_style).pack(side="right", padx=(4, 0))
            ctk.CTkButton(row, text="Remover", width=70, command=do_remove, **_btn_style).pack(side="right")

        footer = ctk.CTkFrame(win, fg_color="transparent")
        footer.pack(fill="x", padx=10, pady=8)
        ctk.CTkButton(footer, text="Indexar mais", command=lambda: (win.destroy(), self._open_indexer()), **_btn_style).pack(side="left")
        ctk.CTkButton(footer, text="Nova sessão", command=lambda: (self._on_new_session(), win.destroy()), **_btn_style).pack(
            side="left", padx=6
        )
        ctk.CTkButton(footer, text="Fechar", command=win.destroy, **_btn_style).pack(side="right")

    def _on_new_session(self):
        self._workspaces.clear()
        self._active_key = None
        self._last_fennec_message = ""
        self._reset_chat()
        self.status_var.set("Pronto  |  Sessão reiniciada")

    # Top controls

    def _toggle_pin(self):
        self._pinned = not self._pinned
        try:
            self.root.attributes("-topmost", self._pinned)
        except Exception:
            pass
        self._pin_btn.configure(text="Unpin" if self._pinned else "Pin")

    def _toggle_instruct_mode(self):
        self._instruct_mode = not self._instruct_mode
        if self._instruct_mode:
            self._side_buttons.pack_forget()
            self._instruct_panel.pack(anchor="n")
            self._mode_btn.configure(text="Chat")
        else:
            self._instruct_panel.pack_forget()
            self._side_buttons.pack(anchor="n")
            self._mode_btn.configure(text="Instruct")

    def _on_function_ask(self, query: str):
        """Usuário pediu ao agente para sugerir funções Excel."""
        ws = self._active_workspace()
        if ws is None or ws.error:
            self._add_fennec_bubble("Indexe ao menos uma planilha antes de perguntar sobre funções.")
            return

        # Show only the user's query in chat, not the system prefix
        self._add_user_bubble(query)
        self.status_var.set("Processando...")
        self.input_bar.entry.configure(state="disabled")

        model_name = self._model_name.get().strip() or DEFAULT_MODEL
        full = (
            f"O usuário quer saber quais funções do Excel podem ajudá-lo com: {query}\n"
            "Liste de 2 a 5 funções relevantes do Excel (nome em português e inglês), "
            "com uma explicação curta de cada. Não aplique nenhuma mudança na planilha."
        )

        def run():
            try:
                from src.agent.runner import run_agent
                from src.agent.ollama_client import OllamaClient

                client = OllamaClient(model=model_name)

                def on_msg(msg: str):
                    self.root.after(0, lambda m=msg: self._add_fennec_bubble(m))

                run_agent(
                    full,
                    ws,
                    ollama=client,
                    on_message=on_msg,
                )
                self.root.after(0, self._agent_done)
            except Exception as e:
                self.root.after(0, lambda: self._agent_done(error=f"Erro: {e!s}"))

        threading.Thread(target=run, daemon=True).start()

    def _on_checkpoints(self):
        ws = self._active_workspace()
        if not ws or ws.error or not ws.path:
            self.status_var.set("Selecione/ative uma planilha para ver checkpoints.")
            return

        cp = CheckpointManager(ws.path)
        checkpoints = cp.list_checkpoints()
        if not checkpoints:
            self.status_var.set("Nenhum checkpoint ainda (cada otimização cria um).")
            return

        win = ctk.CTkToplevel(self.root)
        win.title("Checkpoints")
        win.geometry("420x260")
        win.transient(self.root)
        win.configure(fg_color=s.BG_WARM)

        f = ctk.CTkScrollableFrame(win, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=10)

        _btn_style = dict(
            fg_color=s.ACTION_BG,
            text_color=s.ACTION_TEXT,
            border_width=1,
            border_color=s.ACTION_BORDER,
            hover_color=s.ACTION_HOVER,
        )
        for info in reversed(checkpoints):
            row = ctk.CTkFrame(f, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=info.label, font=ctk.CTkFont(size=12), text_color=s.DARK_TEXT, fg_color="transparent").pack(side="left")

            def do_restore(path=info.path, w=win):
                if cp.restore(path):
                    self.status_var.set("Checkpoint restaurado. Reindexe para sincronizar contexto.")
                    w.destroy()

            ctk.CTkButton(row, text="Restaurar", width=82, command=do_restore, **_btn_style).pack(side="right")

        ctk.CTkButton(win, text="Fechar", command=win.destroy, **_btn_style).pack(pady=6)

    def _recommended_model(self) -> tuple[str, str]:
        """Sugestão simples por RAM/VRAM disponível."""
        ram_gb = 0.0
        vram_gb = 0.0

        try:
            import psutil

            ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        except Exception:
            pass

        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            vals = [float(x.strip()) / 1024.0 for x in out.splitlines() if x.strip()]
            if vals:
                vram_gb = max(vals)
        except Exception:
            vram_gb = 0.0

        if ram_gb >= 24 and vram_gb >= 10:
            return "qwen2.5:14b", f"RAM ~{ram_gb:.1f}GB, VRAM ~{vram_gb:.1f}GB"
        if ram_gb >= 16 and vram_gb >= 6:
            return "qwen2.5:7b", f"RAM ~{ram_gb:.1f}GB, VRAM ~{vram_gb:.1f}GB"
        return "qwen2.5:3b", f"RAM ~{ram_gb:.1f}GB, VRAM ~{vram_gb:.1f}GB"

    def _on_settings(self):
        from ..integrations import connect_provider, disconnect_provider, provider_status
        from ..integrations.oauth_defaults import get_default_client_id

        cfg = load_settings()
        win = ctk.CTkToplevel(self.root)
        win.title(f"Configurações - Sahara Fennec {APP_VERSION}")
        win.geometry("540x620")
        win.transient(self.root)
        win.configure(fg_color=s.BG_WARM)

        rec_model, rec_hint = self._recommended_model()

        body = ctk.CTkScrollableFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(body, text="Modelo Ollama", fg_color="transparent", text_color=s.DARK_TEXT).pack(anchor="w")

        model_var = tk.StringVar(value=self._model_name.get())
        model_opt = ctk.CTkOptionMenu(
            body,
            variable=model_var,
            values=["qwen2.5:14b", "qwen2.5:7b", "qwen2.5:3b", "phi3:mini"],
            fg_color=s.ACTION_BG,
            button_color=s.ACTION_HOVER,
            button_hover_color=s.SIDE_HOVER,
            text_color=s.ACTION_TEXT,
        )
        model_opt.pack(fill="x", pady=(4, 10))

        include_var = tk.BooleanVar(value=self._include_all_sheets.get())
        ctk.CTkCheckBox(
            body,
            text="Indexar todas as abas por padrão",
            variable=include_var,
            fg_color=s.ACTION_BG,
            border_color=s.ACTION_BORDER,
            text_color=s.DARK_TEXT,
            checkmark_color=s.ACTION_TEXT,
        ).pack(anchor="w")

        ctk.CTkLabel(body, text="Limite de linhas por aba", fg_color="transparent", text_color=s.DARK_TEXT).pack(
            anchor="w", pady=(10, 0)
        )
        max_rows_var = tk.StringVar(value=str(self._max_rows_per_sheet.get()))
        ctk.CTkEntry(
            body,
            textvariable=max_rows_var,
            fg_color=s.INPUT_BG,
            border_color=s.INPUT_BORDER,
            text_color=s.DARK_TEXT,
        ).pack(fill="x", pady=(4, 10))
        ctk.CTkLabel(
            body,
            text="Use 0 para ilimitado. Para planilhas muito grandes, prefira 1000 a 5000.",
            fg_color="transparent",
            text_color=s.MUTED_TEXT,
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(
            body,
            text=f"Recomendado para seu hardware: {rec_model} ({rec_hint})",
            fg_color="transparent",
            text_color=s.MUTED_TEXT,
            wraplength=490,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        # Integracoes / OAuth - LOGIN SOCIAL em destaque
        ctk.CTkLabel(
            body,
            text="Login social",
            fg_color="transparent",
            text_color=s.DARK_TEXT,
            font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.SMALL_SIZE, weight="bold"),
        ).pack(anchor="w", pady=(8, 2))
        ctk.CTkLabel(
            body,
            text=(
                "Clique para abrir a tela de login do Google ou Microsoft. "
                "Depois de autorizar, Gmail, Agenda, Drive, Outlook e OneDrive funcionam no chat."
            ),
            fg_color="transparent",
            text_color=s.MUTED_TEXT,
            wraplength=490,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        google_status_var = tk.StringVar(value=provider_status("google"))
        microsoft_status_var = tk.StringVar(value=provider_status("microsoft"))

        _btn_style = dict(
            fg_color=s.ACTION_BG,
            text_color=s.ACTION_TEXT,
            border_width=1,
            border_color=s.ACTION_BORDER,
            hover_color=s.ACTION_HOVER,
        )
        _btn_large = dict(**_btn_style, width=180, height=36)

        def refresh_oauth_status():
            google_status_var.set(provider_status("google"))
            microsoft_status_var.set(provider_status("microsoft"))

        def connect_oauth(provider: str):
            label = "Google" if provider == "google" else "Microsoft"
            cid = get_default_client_id(provider)

            if not cid:
                self.status_var.set(
                    f"Credenciais de {label} nao configuradas. "
                    "O desenvolvedor deve preencher em oauth_defaults.py"
                )
                return

            self.status_var.set(f"Abrindo tela de login do {label}...")

            def worker():
                msg = connect_provider(provider, cid)

                def finish():
                    refresh_oauth_status()
                    self.status_var.set(msg)

                self.root.after(0, finish)

            threading.Thread(target=worker, daemon=True).start()

        def disconnect_oauth(provider: str):
            msg = disconnect_provider(provider)
            refresh_oauth_status()
            self.status_var.set(msg)

        # Botões de login em destaque
        oauth_btns = ctk.CTkFrame(body, fg_color="transparent")
        oauth_btns.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(
            oauth_btns,
            text="Entrar com Google",
            command=lambda: connect_oauth("google"),
            **_btn_large,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            oauth_btns,
            text="Entrar com Microsoft",
            command=lambda: connect_oauth("microsoft"),
            **_btn_large,
        ).pack(side="left")

        g_row = ctk.CTkFrame(body, fg_color="transparent")
        g_row.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(g_row, textvariable=google_status_var, fg_color="transparent", text_color=s.MUTED_TEXT).pack(
            side="left"
        )
        ctk.CTkButton(g_row, text="Desconectar", command=lambda: disconnect_oauth("google"), width=90, height=24, **_btn_style).pack(
            side="left", padx=(8, 0)
        )
        m_row = ctk.CTkFrame(body, fg_color="transparent")
        m_row.pack(fill="x", pady=(2, 8))
        ctk.CTkLabel(m_row, textvariable=microsoft_status_var, fg_color="transparent", text_color=s.MUTED_TEXT).pack(
            side="left"
        )
        ctk.CTkButton(m_row, text="Desconectar", command=lambda: disconnect_oauth("microsoft"), width=90, height=24, **_btn_style).pack(
            side="left", padx=(8, 0)
        )

        footer = ctk.CTkFrame(body, fg_color="transparent")
        footer.pack(fill="x", pady=(8, 0))

        def apply_recommended():
            model_var.set(rec_model)

        def save_and_close():
            self._model_name.set(model_var.get().strip() or DEFAULT_MODEL)
            self._include_all_sheets.set(bool(include_var.get()))
            try:
                raw_value = int(max_rows_var.get().strip())
                self._max_rows_per_sheet.set(0 if raw_value <= 0 else min(raw_value, 200000))
            except Exception:
                self._max_rows_per_sheet.set(0)
            self._save_current_settings({})
            self.status_var.set("Configurações salvas.")
            win.destroy()

        ctk.CTkButton(footer, text="Aplicar recomendado", command=apply_recommended, **_btn_style).pack(side="left")
        ctk.CTkButton(footer, text="Salvar", command=save_and_close, **_btn_style).pack(side="right")

    def _on_help(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Ajuda rápida")
        win.geometry("560x390")
        win.transient(self.root)
        win.configure(fg_color=s.BG_WARM)

        msg = (
            "Como usar o Fennec:\n\n"
            "Indexação — Use o botão \"Indexar Agora\" na lateral para incluir suas planilhas. "
            "Você pode indexar vários arquivos e várias abas. O \"MultiPlanilhas\" permite trocar "
            "qual planilha ou aba está ativa na sessão.\n\n"
            "Planilhas grandes — Em PCs com menos recursos ou planilhas muito grandes, tudo pode "
            "ficar um pouco mais lento. Se quiser, reduza o limite de linhas por aba (por exemplo "
            "1000 ou 2000) nas configurações e evite indexar todas as abas de uma vez.\n\n"
            "Onde ficam os dados — O que você indexa fica na memória da sessão atual. Os checkpoints "
            "são salvos em disco (pasta _fennec_checkpoints). Cada ordem sua cria um checkpoint único "
            "antes da primeira alteração, para você conseguir desfazer a ordem inteira. "
            "O botão \"Nova\" limpa a sessão e ajuda a não acumular memória entre um uso e outro.\n\n"
            "Passos simples:\n"
            "1. Clique em \"Indexar Agora\" e escolha suas planilhas.\n"
            "2. Envie sua pergunta em linguagem natural na caixa de texto.\n"
            "3. Se precisar voltar atrás, use \"Check\" para restaurar um checkpoint."
        )

        box = ctk.CTkTextbox(
            win,
            wrap="word",
            fg_color=s.INPUT_BG,
            border_color=s.INPUT_BORDER,
            text_color=s.DARK_TEXT,
        )
        box.pack(fill="both", expand=True, padx=12, pady=12)
        box.insert("1.0", msg)
        box.configure(state="disabled")

        ctk.CTkButton(
            win,
            text="Fechar",
            command=win.destroy,
            fg_color=s.ACTION_BG,
            text_color=s.ACTION_TEXT,
            border_width=1,
            border_color=s.ACTION_BORDER,
            hover_color=s.ACTION_HOVER,
        ).pack(pady=(0, 10))

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from src.persona.persona_config import get_persona

    MainWindow(get_persona()).run()
