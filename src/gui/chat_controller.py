"""
ChatController — dispatch do agente, bubbles, dialogo de confirmacao.
"""
import logging
import threading
from collections.abc import Callable

import customtkinter as ctk

from ..agent.llm_client import create_client
from ..agent.runner import run_agent
from ..config import load_settings
from . import styles as s
from .chat_bubbles import FennecBubble, UserBubble
from .constants import APP_VERSION, DEFAULT_MODEL

log = logging.getLogger(__name__)


class ChatController:
    def __init__(
        self,
        root: ctk.CTk,
        chat_scroll: ctk.CTkScrollableFrame,
        status_var,
        input_bar,
        images: dict[str, object],
        on_workspace_status: Callable[[], str],
    ):
        self._root = root
        self._chat_scroll = chat_scroll
        self._status_var = status_var
        self._input_bar = input_bar
        self._imgs = images
        self._ws_status = on_workspace_status
        self._last_fennec_message = ""

    def add_user_bubble(self, text: str):
        UserBubble(self._chat_scroll, text).pack(anchor="e", fill="x", pady=(0, 6), padx=(0, 10))
        self._scroll_bottom()

    def add_fennec_bubble(self, text: str):
        clean = (text or "").strip()
        if not clean:
            return
        self._last_fennec_message = clean
        FennecBubble(self._chat_scroll, clean, avatar_image=self._imgs.get("head_avatar")).pack(
            anchor="w", fill="x", pady=(0, 6), padx=(0, 10)
        )
        self._scroll_bottom()

    def reset_last_message(self):
        self._last_fennec_message = ""

    def send(self, text: str, ws, model_name: str, llm_backend: str, nim_base_url: str, nim_model: str, on_confirm_change=None):
        text = text.strip()
        if not text:
            return
        if ws is None or ws.error:
            self.add_fennec_bubble("Indexe ao menos uma planilha antes de enviar consultas.")
            return

        self.add_user_bubble(text)
        self._status_var.set("Processando...")
        self._input_bar.entry.configure(state="disabled")

        settings = load_settings()
        settings["llm_backend"] = llm_backend.strip()
        settings["nim_base_url"] = nim_base_url.strip()
        settings["nim_model"] = nim_model.strip()
        settings["model"] = model_name.strip() or DEFAULT_MODEL

        def run():
            try:
                client = create_client(settings)

                def _safe_after(fn):
                    if self._root.winfo_exists():
                        self._root.after(0, fn)

                def on_msg(msg: str):
                    _safe_after(lambda m=msg: self.add_fennec_bubble(m))

                def on_cp(label: str):
                    _safe_after(lambda: self._status_var.set(f"Checkpoint salvo: {label}"))

                def on_prog(status: str):
                    _safe_after(lambda s=status: self._status_var.set(s))

                kwargs = dict(
                    query=text,
                    workspace=ws,
                    client=client,
                    settings=settings,
                    on_message=on_msg,
                    on_checkpoint=on_cp,
                    on_progress=on_prog,
                )
                if on_confirm_change:
                    kwargs["on_confirm_change"] = on_confirm_change

                run_agent(**kwargs)
                _safe_after(self._agent_done)
            except Exception as e:
                log.exception("Erro durante execução do agente")
                try:
                    _safe_after(lambda exc=e: self._agent_done(error=f"Erro: {exc!s}"))
                except Exception:
                    pass

        threading.Thread(target=run, daemon=True).start()

    def _agent_done(self, error: str | None = None):
        self._input_bar.entry.configure(state="normal")
        if error:
            self.add_fennec_bubble(error)
        self._status_var.set(self._ws_status())

    def confirm_change_blocking(self, preview_text: str) -> bool:
        decision = threading.Event()
        result = {"approved": False}
        _win_ref: list[object] = [None]
        _reject_ref = [lambda: None]

        def show_dialog():
            self._status_var.set("Aguardando confirmacao para alterar a planilha...")

            win = ctk.CTkToplevel(self._root)
            _win_ref[0] = win
            win.title(f"Confirmar alteracao - Sahara Fennec {APP_VERSION}")
            win.geometry("760x520")
            win.transient(self._root)
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

            _reject_ref[0] = reject

            ctk.CTkButton(footer, text="Cancelar", width=110, command=reject, **btn_style).pack(side="right")
            ctk.CTkButton(footer, text="Confirmar", width=110, command=approve, **btn_style).pack(side="right", padx=(0, 8))

        win.protocol("WM_DELETE_WINDOW", _reject_ref[0])  # noqa: F821
        try:
            win.after(50, win.grab_set)  # noqa: F821
            win.focus()  # noqa: F821
        except Exception:
            log.exception("Falha ao capturar foco da janela de confirmação")

        self._root.after(0, show_dialog)
        timed_out = not decision.wait(timeout=300)

        def _safe_after(fn):
            if self._root.winfo_exists():
                self._root.after(0, fn)

        if timed_out:
            result["approved"] = False
            _safe_after(lambda: self._status_var.set("Confirmação expirada (5 min). Alteração cancelada."))

        if result["approved"]:
            _safe_after(lambda: self._status_var.set("Confirmado. Aplicando alteracoes..."))
        else:
            _safe_after(lambda: self._status_var.set("Alteracao cancelada pelo usuario."))
        return bool(result["approved"])

    def _scroll_bottom(self):
        try:
            self._root.after(10, lambda: self._chat_scroll._parent_canvas.yview_moveto(1.0))
        except Exception:
            log.exception("Falha ao rolar chat para o final")
