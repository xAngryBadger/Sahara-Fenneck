"""
Cliente Ollama para chamadas ao LLM local.
"""
from __future__ import annotations

import atexit
import json as _json
import logging
import os
import shutil
import subprocess
import threading
import time
import urllib.request

from .llm_client import DEFAULT_OLLAMA_MODEL as DEFAULT_MODEL

log = logging.getLogger(__name__)

OLLAMA_BASE = "http://localhost:11434"

_ollama_process: subprocess.Popen | None = None
_ollama_lock = threading.Lock()


def _cleanup_ollama() -> None:
    global _ollama_process
    with _ollama_lock:
        if _ollama_process is not None:
            try:
                _ollama_process.terminate()
                _ollama_process.wait(timeout=5)
            except Exception:
                pass
            _ollama_process = None


atexit.register(_cleanup_ollama)


def _check_ollama() -> bool:
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as r:
            return bool(r.status == 200)
    except Exception:
        log.warning("Falha ao verificar disponibilidade do Ollama")
        return False


def _find_ollama_exe() -> str | None:
    cmd = shutil.which("ollama")
    if cmd:
        return cmd
    candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Ollama", "ollama.exe"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None


def _start_ollama_if_possible(timeout_sec: int = 20) -> bool:
    global _ollama_process
    if _check_ollama():
        return True
    exe = _find_ollama_exe()
    if not exe:
        return False
    try:
        with _ollama_lock:
            _ollama_process = subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        log.warning("Falha ao iniciar processo do Ollama")
        return False

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if _check_ollama():
            return True
        time.sleep(0.8)
    return False


def _list_local_models() -> list[str]:
    """Returns names of models already downloaded in Ollama."""
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=4) as r:
            data = _json.loads(r.read().decode())
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        log.warning("Falha ao listar modelos locais do Ollama")
        return []


def _resolve_model(requested: str) -> str:
    """Returns requested model if installed, otherwise falls back to first available."""
    available = _list_local_models()
    if not available:
        return requested
    if requested in available:
        return requested
    for m in available:
        if m.startswith(requested.split(":")[0]):
            return m
    return available[0]


def _pull_model_if_missing(model: str) -> bool:
    exe = _find_ollama_exe()
    if not exe:
        return False
    try:
        ls = subprocess.run([exe, "ls"], capture_output=True, text=True, timeout=15)
        if ls.returncode == 0 and model in (ls.stdout or ""):
            return True
        pull = subprocess.run([exe, "pull", model], timeout=3600)
        return pull.returncode == 0
    except Exception:
        log.warning("Falha ao baixar modelo '%s' no Ollama", model)
        return False


class OllamaClient:
    """Chama o modelo via API HTTP do Ollama."""

    def __init__(self, model: str | None = None, base_url: str = OLLAMA_BASE):
        self.model = _resolve_model(model or DEFAULT_MODEL)
        self.base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        return _check_ollama() or _start_ollama_if_possible()

    def generate(self, prompt: str, system: str | None = None, max_tokens: int = 2048) -> str:
        """Envia prompt e retorna a resposta do modelo."""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens},
            }
            if system:
                payload["system"] = system
            data = _json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                out = _json.loads(r.read().decode())

            err = (out.get("error") or "").strip()
            if err and "not found" in err.lower() and _pull_model_if_missing(self.model):
                with urllib.request.urlopen(req, timeout=120) as r2:
                    out = _json.loads(r2.read().decode())

            return str(out.get("response", "")).strip()
        except Exception as e:
            log.exception("Erro ao gerar resposta com Ollama")
            raise RuntimeError(f"[E018] Ollama não disponível: {e!s}") from e
