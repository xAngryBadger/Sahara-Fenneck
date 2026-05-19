"""
Input arredondado macio + botao enviar circular com patinha.
"""
import customtkinter as ctk

from . import styles as s

PLACEHOLDER = "Digite sua solicitacao (ex: Otimize com funil de vendas, filtros e graficos...)"


class InputBar(ctk.CTkFrame):
    def __init__(self, parent, on_send, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.on_send = on_send
        self._build()

    def _build(self):
        self.entry = ctk.CTkEntry(
            self,
            placeholder_text=PLACEHOLDER,
            placeholder_text_color=s.MUTED_TEXT,
            font=ctk.CTkFont(family=s.FONT_FAMILY, size=s.SMALL_SIZE),
            text_color=s.DARK_TEXT,
            fg_color=s.INPUT_BG,
            border_color=s.INPUT_BORDER,
            border_width=1,
            corner_radius=s.INPUT_CORNER,
            height=s.INPUT_HEIGHT,
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry.bind("<Return>", lambda e: self._do_send())

        # Botao circular azul com patinha
        send = ctk.CTkButton(
            self,
            text="\U0001F43E",  # paw prints unicode
            font=ctk.CTkFont(size=20),
            fg_color=s.SEND_BG,
            hover_color=s.SEND_HOVER,
            text_color=s.WHITE,
            corner_radius=s.SEND_CORNER,
            width=s.SEND_SIZE,
            height=s.SEND_SIZE,
            command=self._do_send,
        )
        send.pack(side="right")

    def _do_send(self):
        text = self.entry.get().strip()
        if text:
            self.entry.delete(0, "end")
            self.on_send(text)
