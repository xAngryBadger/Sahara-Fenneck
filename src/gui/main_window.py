"""
Sahara Fennec - Janela principal (UI + backend integrado).
"""
import logging
import sys
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from ..checkpoints import CheckpointManager
from ..config import load_settings, save_settings
from ..indexing import Workspace
from . import styles as s
from .chat_controller import ChatController
from .constants import APP_VERSION, DEFAULT_MODEL
from .gradient import draw_vertical_gradient
from .indexer_window import IndexerWindow
from .input_bar import InputBar
from .instruct_panel import InstructPanel
from .settings_controller import SettingsController
from .side_buttons import SideButtons
from .workspace_manager import WorkspaceManager

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ASSETS = _PROJECT_ROOT / "assets"
_BG_CANDIDATES = [
    _PROJECT_ROOT / "fundodeserto.png",
    _ASSETS / "fundodeserto.png",
    _ASSETS / "desert_bg.png",
]


def _ctk_img(path: Path, size: tuple[int, int]):
    try:
        from PIL import Image

        return ctk.CTkImage(
            light_image=Image.open(path).convert("RGBA"),
            dark_image=Image.open(path).convert("RGBA"),
            size=size,
        )
    except Exception:
        log.exception("Falha ao carregar imagem: %s", path)
        return None


class MainWindow:
    def __init__(self, persona: dict):
        self.persona = persona
        self._imgs: dict[str, object] = {}
        self._ws = WorkspaceManager()
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
        self._llm_backend = tk.StringVar(master=self.root, value=str(cfg.get("llm_backend", "ollama")))
        self._nim_base_url = tk.StringVar(master=self.root, value=str(cfg.get("nim_base_url", "https://integrate.api.nvidia.com/v1")))
        self._nim_model = tk.StringVar(master=self.root, value=str(cfg.get("nim_model", "meta/llama-3.1-70b-instruct")))
        self._nim_api_key = tk.StringVar(master=self.root)
        self.root.minsize(s.WINDOW_MIN_WIDTH, s.WINDOW_MIN_HEIGHT)
        self.root.geometry(f"{s.WINDOW_DEFAULT_WIDTH}x{s.WINDOW_DEFAULT_HEIGHT}")
        self.root.configure(fg_color=s.BG_WARM)

        self._load_assets()
        self._set_icon()
        self._build()
        self._chat = ChatController(
            root=self.root,
            chat_scroll=self._chat_scroll,
            status_var=self.status_var,
            input_bar=self.input_bar,
            images=self._imgs,
            on_workspace_status=self._workspace_status,
        )
        self._settings = SettingsController(
            root=self.root,
            status_var=self.status_var,
            model_name_var=self._model_name,
            include_all_sheets_var=self._include_all_sheets,
            max_rows_var=self._max_rows_per_sheet,
            llm_backend_var=self._llm_backend,
            nim_base_url_var=self._nim_base_url,
            nim_model_var=self._nim_model,
            on_save_settings=self._save_current_settings,
        )
        self._reset_chat()
        self.root.after(800, self._check_pending_models)

    def _load_assets(self):
        head = _ASSETS / "fennec_head_icon.png"
        if head.exists():
            self._imgs["head_avatar"] = _ctk_img(head, s.AVATAR_SIZE)

    def _check_pending_models(self):
        import os
        pending = Path(os.environ.get("APPDATA") or str(Path.home() / ".sahara_fennec")) / "pending_models.txt"
        if pending.exists():
            try:
                models = [m.strip() for m in pending.read_text(encoding="utf-8").splitlines() if m.strip()]
                if models:
                    self._chat.add_fennec_bubble(
                        f"⏳ O modelo de IA ({', '.join(models)}) ainda está sendo baixado em segundo plano. "
                        "Isso pode levar alguns minutos dependendo da sua conexão. "
                        "Você poderá usar o app normalmente assim que o download for concluído."
                    )
            except Exception:
                log.exception("Falha ao verificar modelos pendentes")

    def _set_icon(self):
        ico = _ASSETS / "fennec_head_icon.ico"
        png = _ASSETS / "fennec_head_icon.png"
        if png.exists():
            try:
                from PIL import Image, ImageTk
                img = Image.open(png)
                self._icon_photo = ImageTk.PhotoImage(img)
                self.root.iconphoto(True, self._icon_photo)
                return
            except Exception:
                log.exception("Falha ao definir ícone da janela via iconphoto")
        if ico.exists() and sys.platform == "win32":
            try:
                self.root.iconbitmap(str(ico))
            except Exception:
                log.exception("Falha ao definir ícone da janela via iconbitmap")

    def _draw_bg(self, _ev=None):
        if hasattr(self, "_bg_draw_after_id"):
            self.root.after_cancel(self._bg_draw_after_id)
        self._bg_draw_after_id = self.root.after(80, self._do_draw_bg)

    def _do_draw_bg(self):
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
        try:
            sb = scrollable._scrollbar
            sb.grid_remove()
        except Exception:
            pass

    def _reset_chat(self):
        for child in self._chat_scroll.winfo_children():
            child.destroy()

        welcome = self.persona.get(
            "welcome_message",
            "Olá! Eu sou Fennec Excel, seu agente pessoal de planilhas!",
        )
        self._chat.reset_last_message()
        self._chat.add_fennec_bubble(welcome)
        self._chat.add_fennec_bubble(
            "Use 'Indexar Agora' na lateral para abrir a tela de indexação e escolher uma ou múltiplas planilhas/abas."
        )

    def _active_workspace(self) -> Workspace | None:
        return self._ws.active()

    def _workspace_status(self) -> str:
        return self._ws.status_text()

    def _save_current_settings(self, extra: dict | None = None):
        payload = load_settings()
        payload.update(
            {
                "model": self._model_name.get().strip() or DEFAULT_MODEL,
                "index_all_sheets": bool(self._include_all_sheets.get()),
                "max_rows_per_sheet": int(self._max_rows_per_sheet.get()),
                "llm_backend": self._llm_backend.get().strip(),
                "nim_base_url": self._nim_base_url.get().strip(),
                "nim_model": self._nim_model.get().strip(),
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
                log.exception("Falha ao verificar existência da janela do indexador")

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
            key, has_err = self._ws.add(ws)
            if has_err:
                errs.append(f"{ws.workbook_name or ws.path}: {ws.error}")
            else:
                ok += 1

        if ok > 0:
            self._chat.add_fennec_bubble(f"Indexação concluída: {ok} aba(s) carregada(s). Planilha ativa: {self._ws.active_key}.")
        if errs:
            self._chat.add_fennec_bubble("Algumas indexações falharam:\n- " + "\n- ".join(errs[:4]))

        self.status_var.set(self._workspace_status())

    # Chat / agente

    def _on_send(self, text: str):
        self._chat.send(
            text=text,
            ws=self._active_workspace(),
            model_name=self._model_name.get(),
            llm_backend=self._llm_backend.get(),
            nim_base_url=self._nim_base_url.get(),
            nim_model=self._nim_model.get(),
            on_confirm_change=self._chat.confirm_change_blocking,
        )

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

        ws_items = self._ws.items()
        if not ws_items:
            ctk.CTkLabel(box, text="Nenhuma planilha indexada.", fg_color="transparent", text_color=s.MUTED_TEXT).pack(
                anchor="w"
            )

        for key, ws in ws_items:
            row = ctk.CTkFrame(box, fg_color="transparent")
            row.pack(fill="x", pady=3)

            tag = " (ativa)" if key == self._ws.active_key else ""
            ctk.CTkLabel(row, text=f"{key}{tag}", fg_color="transparent", text_color=s.DARK_TEXT).pack(side="left")

            def do_activate(k=key, w=win):
                self._ws.set_active(k)
                self.status_var.set(self._workspace_status())
                self._chat.add_fennec_bubble(f"Planilha ativa alterada para: {k}")
                w.destroy()

            def do_remove(k=key, w=win):
                self._ws.remove(k)
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
        self._ws.clear()
        self._chat.reset_last_message()
        self._reset_chat()
        self.status_var.set("Pronto | Sessão reiniciada")

    # Top controls

    def _toggle_pin(self):
        self._pinned = not self._pinned
        try:
            self.root.attributes("-topmost", self._pinned)
        except Exception:
            log.exception("Falha ao alternar atributo topmost (pin)")
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
        ws = self._active_workspace()
        if ws is None or ws.error:
            self._chat.add_fennec_bubble("Indexe ao menos uma planilha antes de perguntar sobre funções.")
            return

        full = (
            f"O usuário quer saber quais funções do Excel podem ajudá-lo com: {query}\n"
            "Liste de 2 a 5 funções relevantes do Excel (nome em português e inglês), "
            "com uma explicação curta de cada. Não aplique nenhuma mudança na planilha."
        )
        self._chat.send(
            text=full,
            ws=ws,
            model_name=self._model_name.get(),
            llm_backend=self._llm_backend.get(),
            nim_base_url=self._nim_base_url.get(),
            nim_model=self._nim_model.get(),
        )

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

    def _on_settings(self):
        self._settings.open_settings()

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
