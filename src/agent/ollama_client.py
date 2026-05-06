# -*- coding: utf-8 -*-
"""
Cliente Ollama para chamadas ao LLM local.
"""
from __future__ import annotations

import json as _json
import os
import shutil
import subprocess
import time
import urllib.request
from typing import Optional

DEFAULT_MODEL = "qwen2.5:7b"
OLLAMA_BASE = "http://localhost:11434"


def _check_ollama() -> bool:
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _find_ollama_exe() -> Optional[str]:
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
    if _check_ollama():
        return True
    exe = _find_ollama_exe()
    if not exe:
        return False
    try:
        subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
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
        return []


def _resolve_model(requested: str) -> str:
    """Returns requested model if installed, otherwise falls back to first available."""
    available = _list_local_models()
    if not available:
        return requested
    # exact match
    if requested in available:
        return requested
    # prefix match (e.g. "qwen2.5:7b" vs "qwen2.5:7b-instruct-q4_0")
    for m in available:
        if m.startswith(requested.split(":")[0]):
            return m
    # last resort: first installed model
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
        return False


class OllamaClient:
    """Chama o modelo via API HTTP do Ollama."""

    def __init__(self, model: Optional[str] = None, base_url: str = OLLAMA_BASE):
        self.model = _resolve_model(model or DEFAULT_MODEL)
        self.base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        return _check_ollama() or _start_ollama_if_possible()

    def generate(self, prompt: str, system: Optional[str] = None, max_tokens: int = 2048) -> str:
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

            return out.get("response", "").strip()
        except Exception as e:
            return f"[Erro Ollama: {e!s}]"
