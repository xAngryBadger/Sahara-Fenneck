"""
SettingsController — dialogo de configuracoes, modelo recomendado, OAuth.
"""
import logging
import subprocess
import threading
import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from ..config import load_settings
from . import styles as s
from .constants import APP_VERSION, DEFAULT_MODEL

log = logging.getLogger(__name__)

NIM_MODELS = [
    "meta/llama-3.1-70b-instruct",
    "meta/llama-3.1-8b-instruct",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "nvidia/llama-3.1-nemotron-ultra-253b-v1",
    "mistralai/mixtral-8x22b-instruct-v0.1",
    "mistralai/mistral-large-3-675b-instruct-2512",
    "google/gemma-3-27b-it",
    "deepseek-ai/deepseek-v4-pro",
    "qwen/qwen3.5-397b-a17b",
]

OLLAMA_MODELS = ["qwen2.5:14b", "qwen2.5:7b", "qwen2.5:3b", "phi3:mini"]


class SettingsController:
    def __init__(
        self,
        root: ctk.CTk,
        status_var,
        model_name_var,
        include_all_sheets_var,
        max_rows_var,
        llm_backend_var,
        nim_base_url_var,
        nim_model_var,
        on_save_settings: Callable[..., None],
    ):
        self._root = root
        self._status_var = status_var
        self._model_name = model_name_var
        self._include_all_sheets = include_all_sheets_var
        self._max_rows = max_rows_var
        self._llm_backend = llm_backend_var
        self._nim_base_url = nim_base_url_var
        self._nim_model = nim_model_var
        self._on_save_settings = on_save_settings

    @staticmethod
    def recommended_model() -> tuple[str, str]:
        ram_gb = 0.0
        vram_gb = 0.0

        try:
            import psutil

            ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        except Exception:
            log.exception("Falha ao detectar RAM via psutil")

        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
            vals = [float(x.strip()) / 1024.0 for x in out.splitlines() if x.strip()]
            if vals:
                vram_gb = max(vals)
        except Exception:
            log.warning("Falha ao detectar VRAM via nvidia-smi")
            vram_gb = 0.0

        if ram_gb >= 24 and vram_gb >= 10:
            return "qwen2.5:14b", f"RAM ~{ram_gb:.1f}GB, VRAM ~{vram_gb:.1f}GB"
        if ram_gb >= 16 and vram_gb >= 6:
            return "qwen2.5:7b", f"RAM ~{ram_gb:.1f}GB, VRAM ~{vram_gb:.1f}GB"
        return "qwen2.5:3b", f"RAM ~{ram_gb:.1f}GB, VRAM ~{vram_gb:.1f}GB"

    def open_settings(self):
        from ..integrations import connect_provider, disconnect_provider, provider_status
        from ..integrations.oauth_defaults import get_default_client_id
        from ..integrations.token_store import get_nim_api_key, set_nim_api_key

        load_settings()
        win = ctk.CTkToplevel(self._root)
        win.title(f"Configurações - Sahara Fennec {APP_VERSION}")
        win.geometry("540x720")
        win.transient(self._root)
        win.configure(fg_color=s.BG_WARM)

        rec_model, rec_hint = self.recommended_model()

        body = ctk.CTkScrollableFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(
            body,
            text="Backend de IA",
            fg_color="transparent",
            text_color=s.DARK_TEXT,
            font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.SMALL_SIZE, weight="bold"),
        ).pack(anchor="w", pady=(0, 4))

        backend_var = tk.StringVar(value=self._llm_backend.get())

        def _on_backend_change(value: str):
            backend_var.set(value)
            ollama_frame.pack_forget() if value == "nim" else ollama_frame.pack(fill="x", pady=(0, 8))
            nim_frame.pack(fill="x", pady=(0, 8)) if value == "nim" else nim_frame.pack_forget()

        radio_row = ctk.CTkFrame(body, fg_color="transparent")
        radio_row.pack(fill="x", pady=(0, 8))
        ctk.CTkRadioButton(radio_row, text="Ollama (local)", variable=backend_var, value="ollama", command=lambda: _on_backend_change("ollama"), fg_color=s.ACTION_BG, text_color=s.DARK_TEXT).pack(side="left", padx=(0, 16))
        ctk.CTkRadioButton(radio_row, text="NVIDIA NIM (nuvem)", variable=backend_var, value="nim", command=lambda: _on_backend_change("nim"), fg_color=s.ACTION_BG, text_color=s.DARK_TEXT).pack(side="left")

        ollama_frame = ctk.CTkFrame(body, fg_color="transparent")

        ctk.CTkLabel(ollama_frame, text="Modelo Ollama", fg_color="transparent", text_color=s.DARK_TEXT).pack(anchor="w")
        model_var = tk.StringVar(value=self._model_name.get())
        ctk.CTkOptionMenu(
            ollama_frame,
            variable=model_var,
            values=OLLAMA_MODELS,
            fg_color=s.ACTION_BG,
            button_color=s.ACTION_HOVER,
            button_hover_color=s.SIDE_HOVER,
            text_color=s.ACTION_TEXT,
        ).pack(fill="x", pady=(4, 10))

        ctk.CTkLabel(
            ollama_frame,
            text=f"Recomendado para seu hardware: {rec_model} ({rec_hint})",
            fg_color="transparent",
            text_color=s.MUTED_TEXT,
            wraplength=490,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        ollama_frame.pack(fill="x", pady=(0, 8))

        nim_frame = ctk.CTkFrame(body, fg_color="transparent")

        ctk.CTkLabel(nim_frame, text="API Key NVIDIA", fg_color="transparent", text_color=s.DARK_TEXT).pack(anchor="w")
        stored_key = get_nim_api_key()
        nim_key_var = tk.StringVar(value=stored_key)
        ctk.CTkEntry(
            nim_frame,
            textvariable=nim_key_var,
            show="*",
            fg_color=s.INPUT_BG,
            border_color=s.INPUT_BORDER,
            text_color=s.DARK_TEXT,
        ).pack(fill="x", pady=(4, 10))
        ctk.CTkLabel(
            nim_frame,
            text="Obtenha em build.nvidia.com → Settings → API Keys",
            fg_color="transparent",
            text_color=s.MUTED_TEXT,
        ).pack(anchor="w", pady=(0, 8))

        ctk.CTkLabel(nim_frame, text="URL base", fg_color="transparent", text_color=s.DARK_TEXT).pack(anchor="w")
        nim_url_var = tk.StringVar(value=self._nim_base_url.get())
        ctk.CTkEntry(
            nim_frame,
            textvariable=nim_url_var,
            fg_color=s.INPUT_BG,
            border_color=s.INPUT_BORDER,
            text_color=s.DARK_TEXT,
        ).pack(fill="x", pady=(4, 10))

        ctk.CTkLabel(nim_frame, text="Modelo NIM", fg_color="transparent", text_color=s.DARK_TEXT).pack(anchor="w")
        nim_model_var = tk.StringVar(value=self._nim_model.get())
        ctk.CTkComboBox(
            nim_frame,
            variable=nim_model_var,
            values=NIM_MODELS,
            fg_color=s.INPUT_BG,
            border_color=s.INPUT_BORDER,
            text_color=s.DARK_TEXT,
            button_color=s.ACTION_HOVER,
            button_hover_color=s.SIDE_HOVER,
        ).pack(fill="x", pady=(4, 10))

        if backend_var.get() != "nim":
            nim_frame.pack_forget()

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
        max_rows_var = tk.StringVar(value=str(self._max_rows.get()))
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
                self._status_var.set(
                    f"Credenciais de {label} nao configuradas. "
                    "O desenvolvedor deve preencher em oauth_defaults.py"
                )
                return

            self._status_var.set(f"Abrindo tela de login do {label}...")

            def worker():
                msg = connect_provider(provider, cid)

                def finish():
                    refresh_oauth_status()
                    self._status_var.set(msg)

                self._root.after(0, finish)

            threading.Thread(target=worker, daemon=True).start()

        def disconnect_oauth(provider: str):
            msg = disconnect_provider(provider)
            refresh_oauth_status()
            self._status_var.set(msg)

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
                self._max_rows.set(0 if raw_value <= 0 else min(raw_value, 200000))
            except Exception:
                log.warning("Valor inválido para limite de linhas por aba, usando 0")
                self._max_rows.set(0)
            self._llm_backend.set(backend_var.get().strip())
            self._nim_base_url.set(nim_url_var.get().strip())
            self._nim_model.set(nim_model_var.get().strip())

            new_key = nim_key_var.get().strip()
            if new_key:
                try:
                    set_nim_api_key(new_key)
                except Exception:
                    log.exception("Falha ao salvar API key do NIM")

            self._on_save_settings({})
            self._status_var.set("Configurações salvas.")
            win.destroy()

        ctk.CTkButton(footer, text="Aplicar recomendado", command=apply_recommended, **_btn_style).pack(side="left")
        ctk.CTkButton(footer, text="Salvar", command=save_and_close, **_btn_style).pack(side="right")
