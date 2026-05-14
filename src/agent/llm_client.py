from __future__ import annotations

import logging
import os
from typing import Protocol, runtime_checkable

from ..errcodes import ErrCode, err_str

log = logging.getLogger(__name__)


DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"
DEFAULT_NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_NIM_MODEL = "meta/llama-3.1-70b-instruct"


@runtime_checkable
class LLMClient(Protocol):
    def is_available(self) -> bool: ...

    def generate(self, prompt: str, system: str | None = None, max_tokens: int = 2048) -> str: ...


def create_client(settings: dict) -> LLMClient:
    backend = settings.get("llm_backend", "ollama").strip().lower()

    if backend == "nim":
        from ..integrations.token_store import get_nim_api_key
        from .nim_client import NimClient

        api_key = (get_nim_api_key() or os.getenv("NVIDIA_API_KEY", "")).strip()
        base_url = (settings.get("nim_base_url") or DEFAULT_NIM_BASE_URL).strip()
        model = (settings.get("nim_model") or DEFAULT_NIM_MODEL).strip()

        client = NimClient(api_key=api_key, model=model, base_url=base_url)
        if not api_key:
            log.warning(err_str(ErrCode.NIM_AUTH_FAILED, "NVIDIA_API_KEY not set"))
        return client

    from .ollama_client import OllamaClient

    model = (settings.get("model") or DEFAULT_OLLAMA_MODEL).strip()
    return OllamaClient(model=model)
