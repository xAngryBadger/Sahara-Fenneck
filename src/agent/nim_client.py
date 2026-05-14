"""Cliente NVIDIA NIM (OpenAI-compatible) para chamadas ao LLM na nuvem."""
from __future__ import annotations

import logging

from ..errcodes import ErrCode, err_str
from .llm_client import DEFAULT_NIM_BASE_URL, DEFAULT_NIM_MODEL

log = logging.getLogger(__name__)


class NimClient:
    def __init__(
        self,
        api_key: str = "",
        model: str = DEFAULT_NIM_MODEL,
        base_url: str = DEFAULT_NIM_BASE_URL,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError(
                err_str(ErrCode.NIM_UNAVAILABLE, "Pacote 'openai' não instalado. Execute: pip install openai")
            )
        if not self.api_key:
            raise RuntimeError(err_str(ErrCode.NIM_AUTH_FAILED, "API key não configurada"))
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            self._get_client()
            return True
        except Exception as e:
            log.debug("NIM availability check failed: %s", e)
            return False

    def generate(self, prompt: str, system: str | None = None, max_tokens: int = 2048) -> str:
        client = self._get_client()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.3,
            )
            content = response.choices[0].message.content
            return (content or "").strip()
        except Exception as e:
            err_msg = str(e).lower()
            if "auth" in err_msg or "401" in err_msg or "api_key" in err_msg or "invalid" in err_msg:
                raise RuntimeError(err_str(ErrCode.NIM_AUTH_FAILED, str(e))) from e
            raise RuntimeError(err_str(ErrCode.NIM_REQUEST_FAILED, str(e))) from e
