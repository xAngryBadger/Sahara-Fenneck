"""
OAuth guiado (PKCE + loopback local) para Google e Microsoft.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from .oauth_defaults import get_default_client_id
from .token_store import clear_provider_token, get_provider_token, set_provider_token

log = logging.getLogger(__name__)

PROVIDERS: dict[str, dict[str, Any]] = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": [
            "openid",
            "email",
            "profile",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/drive.file",
        ],
        "extra_auth": {
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        },
    },
    "microsoft": {
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "scopes": [
            "openid",
            "profile",
            "offline_access",
            "User.Read",
            "Mail.Send",
            "Calendars.Read",
            "Files.ReadWrite",
            "Sites.ReadWrite.All",
        ],
        "extra_auth": {},
    },
}


def _http_form_post(url: str, data: dict[str, str]) -> tuple[int, dict[str, Any], str]:
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=encoded, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(body) if body.strip() else {}
            parsed_dict = parsed if isinstance(parsed, dict) else {"raw": parsed}
            return int(resp.status), parsed_dict, ""
    except Exception as e:
        try:
            details = getattr(e, "read")().decode("utf-8", errors="replace")
        except Exception:
            log.exception("Falha ao ler detalhes do erro HTTP")
            details = str(e)
        code = int(getattr(e, "code", 500))
        return code, {}, details
        code = int(getattr(e, "code", 500))
        return code, {}, details


def _new_pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).decode("ascii").rstrip("=")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def _open_auth_url(url: str) -> tuple[bool, str]:
    """Abre o navegador com a URL de login social (Google/Microsoft)."""
    last_err = ""
    # 1) webbrowser (usa BROWSER ou default do SO)
    try:
        if webbrowser.open(url, new=2, autoraise=True):
            return True, ""
    except Exception as e:
        last_err = str(e)

    # 2) Windows: startfile (abre com app padrão do .url)
    if os.name == "nt":
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            return True, ""
        except Exception as e:
            last_err = str(e)

    # 3) PowerShell Start-Process (URL passed as argument, not interpolated)
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", "Start-Process", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return True, ""
    except Exception as e:
        last_err = str(e)

    # 4) cmd /c start (fallback)
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return True, ""
    except Exception as e:
        last_err = str(e)

    return False, last_err


class _OAuthResult:
    def __init__(self) -> None:
        self.code = ""
        self.state = ""
        self.error = ""
        self.event = threading.Event()


def _start_callback_server(expected_state: str) -> tuple[HTTPServer, threading.Thread, _OAuthResult, int]:
    result = _OAuthResult()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (API do BaseHTTPRequestHandler)
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            state = (query.get("state") or [""])[0]
            code = (query.get("code") or [""])[0]
            error = (query.get("error") or [""])[0]

            if state != expected_state:
                result.error = "state mismatch"
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"OAuth state invalido. Pode fechar esta janela.")
                result.event.set()
                return

            if error:
                result.error = error
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"Falha no OAuth: {error}".encode("utf-8", errors="replace"))
                result.event.set()
                return

            result.code = code
            result.state = state
            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                b"Conexao concluida com sucesso. Pode fechar esta janela e voltar ao Sahara Fennec."
            )
            result.event.set()

        def log_message(self, _format, *args):  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 1
    port = int(server.server_port)

    def worker():
        while not result.event.is_set():
            server.handle_request()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return server, thread, result, port


def connect_provider(provider: str, client_id: str) -> str:
    provider = provider.strip().lower()
    cfg = PROVIDERS.get(provider)
    if not cfg:
        return f"Provider OAuth invalido: {provider}"
    cid = (client_id or "").strip() or get_default_client_id(provider)
    if not cid:
        return (
            f"Nenhum Client ID configurado para {provider}. "
            "Crie credenciais OAuth no Google Cloud / Azure e adicione em Configurações > Avançado."
        )

    code_verifier, code_challenge = _new_pkce()
    state = secrets.token_urlsafe(24)

    server, _t, result, port = _start_callback_server(state)
    if port <= 0:
        return "Falha ao iniciar servidor local para callback OAuth."

    redirect_uri = f"http://127.0.0.1:{port}/callback"
    query = {
        "response_type": "code",
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "scope": " ".join(cfg["scopes"]),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    query.update(cfg.get("extra_auth", {}))
    auth_url = f"{cfg['auth_url']}?{urllib.parse.urlencode(query)}"

    opened, open_err = _open_auth_url(auth_url)
    if not opened:
        result.error = "falha ao abrir navegador"
        result.event.set()
        try:
            server.server_close()
        except Exception:
            pass
        tail = f"\nDetalhes: {open_err}" if open_err else ""
        return f"Falha ao abrir navegador automaticamente. Abra manualmente:\n{auth_url}{tail}"

    done = result.event.wait(180)
    if not done and not result.error:
        result.error = "timeout no callback OAuth"
    try:
        server.server_close()
    except Exception:
        pass

    code = str(result.code or "")
    err = str(result.error or "")
    if not code:
        return f"Falha no OAuth {provider}: {err or 'codigo nao recebido'}"

    token_payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": cid,
        "code_verifier": code_verifier,
    }
    if provider == "microsoft":
        token_payload["scope"] = " ".join(cfg["scopes"])

    status, token_data, details = _http_form_post(cfg["token_url"], token_payload)
    if not (200 <= status < 300):
        return f"Falha ao obter token de {provider} (status={status}). {details[:300]}"

    access_token = str(token_data.get("access_token") or "")
    refresh_token = str(token_data.get("refresh_token") or "")
    expires_in = int(token_data.get("expires_in") or 0)
    if not access_token:
        return f"OAuth {provider} nao retornou access_token."

    now = int(time.time())
    set_provider_token(
        provider,
        {
            "provider": provider,
            "client_id": cid,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": now + max(60, expires_in - 30),
            "scopes": cfg["scopes"],
            "token_url": cfg["token_url"],
            "updated_at": now,
        },
    )
    return f"Conexao OAuth de {provider} concluida com sucesso."


def _refresh_provider_token(provider: str, token_data: dict[str, Any], client_id: str) -> tuple[bool, str]:
    cfg = PROVIDERS.get(provider)
    if not cfg:
        return False, "provider invalido"
    refresh_token = str(token_data.get("refresh_token") or "")
    if not refresh_token:
        return False, "refresh token ausente; reconecte o OAuth."

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id.strip(),
    }
    if provider == "microsoft":
        payload["scope"] = " ".join(cfg["scopes"])

    status, refreshed, details = _http_form_post(cfg["token_url"], payload)
    if not (200 <= status < 300):
        return False, f"falha refresh ({status}): {details[:300]}"

    access_token = str(refreshed.get("access_token") or "")
    if not access_token:
        return False, "refresh sem access token"

    new_refresh = str(refreshed.get("refresh_token") or refresh_token)
    expires_in = int(refreshed.get("expires_in") or 0)
    now = int(time.time())
    token_data.update(
        {
            "access_token": access_token,
            "refresh_token": new_refresh,
            "expires_at": now + max(60, expires_in - 30),
            "updated_at": now,
        }
    )
    set_provider_token(provider, token_data)
    return True, ""


def get_access_token(provider: str, client_id: str) -> tuple[str, str]:
    """Retorna (token, erro)."""
    provider = provider.strip().lower()
    token_data = get_provider_token(provider)
    if not token_data:
        return "", f"{provider} nao conectado. Use Configuracoes > Conectar {provider.capitalize()}."

    stored_client = str(token_data.get("client_id") or "")
    if (client_id or "").strip() and stored_client and stored_client != client_id.strip():
        return "", f"Client ID de {provider} mudou. Reconecte o OAuth."

    access_token = str(token_data.get("access_token") or "")
    expires_at = int(token_data.get("expires_at") or 0)
    now = int(time.time())
    if access_token and expires_at > (now + 10):
        return access_token, ""

    ok, err = _refresh_provider_token(provider, token_data, client_id=stored_client or client_id)
    if not ok:
        return "", f"Falha ao renovar token de {provider}: {err}"
    refreshed = get_provider_token(provider) or {}
    return str(refreshed.get("access_token") or ""), ""


def disconnect_provider(provider: str) -> str:
    clear_provider_token(provider.strip().lower())
    return f"Conexao {provider} removida."


def provider_status(provider: str) -> str:
    token_data = get_provider_token(provider.strip().lower())
    if not token_data:
        return "Nao conectado"
    expires_at = int(token_data.get("expires_at") or 0)
    now = int(time.time())
    if expires_at <= now:
        return "Conectado (token expirado, sera renovado automaticamente)"
    mins = max(1, int((expires_at - now) / 60))
    return f"Conectado (token valido por ~{mins} min)"

