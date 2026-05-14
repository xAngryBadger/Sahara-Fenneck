"""
Utilidades compartilhadas entre backends de integracao.
"""
from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
import urllib.error
import urllib.request

from ...config.app_settings import settings_client_ids

log = logging.getLogger(__name__)

GMAIL_USER_ENV = "FENNEC_GMAIL_USER"
GMAIL_PASS_ENV = "FENNEC_GMAIL_APP_PASSWORD"
GMAIL_TO_ENV = "FENNEC_GMAIL_TO"
TEAMS_WEBHOOK_ENV = "FENNEC_TEAMS_WEBHOOK_URL"
GOOGLE_TOKEN_ENV = "FENNEC_GOOGLE_ACCESS_TOKEN"
MICROSOFT_TOKEN_ENV = "FENNEC_MICROSOFT_ACCESS_TOKEN"
TRELLO_KEY_ENV = "FENNEC_TRELLO_KEY"
TRELLO_TOKEN_ENV = "FENNEC_TRELLO_TOKEN"
TRELLO_LIST_ENV = "FENNEC_TRELLO_LIST_ID"
SHAREPOINT_SITE_ENV = "FENNEC_SHAREPOINT_SITE_ID"
SHAREPOINT_DRIVE_ENV = "FENNEC_SHAREPOINT_DRIVE_ID"
OUTLOOK_TO_ENV = "FENNEC_OUTLOOK_TO"

_ERR_PREFIX = "\u26a0 "


def _err_msg(service: str, detail: str) -> str:
    return f"{_ERR_PREFIX}{service}: {detail}"


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(ch for ch in value if unicodedata.category(ch) != "Mn")


def has_word(text: str, word: str) -> bool:
    return bool(re.search(rf"\b{re.escape(word)}\b", text))


def http_json(method: str, url: str, headers: dict[str, str], payload: bytes | None = None, *, redact_url: bool = False) -> tuple[int, dict, str]:
    safe_url = re.sub(r"([?&])(key|token)=[^&]+", r"\1\2=***", url) if redact_url else url
    req = urllib.request.Request(url, method=method, data=payload)
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(body) if body.strip() else {}
            return int(resp.status), parsed if isinstance(parsed, dict) else {"raw": parsed}, ""
    except urllib.error.HTTPError as e:
        try:
            details = e.read().decode("utf-8", errors="replace")
        except Exception:
            log.warning("Falha ao ler corpo do erro HTTP: usando representacao string")
            details = str(e)
        log.debug("HTTP %s %s => %s", method, safe_url, e.code)
        return int(getattr(e, "code", 500)), {}, details
    except Exception as e:
        log.warning("Erro inesperado na requisicao HTTP %s %s: %s", method, safe_url, e)
        return 500, {}, str(e)


def extract_emails(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text or "")


def safe_sheet_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name or "planilha")


def google_token() -> tuple[str, str]:
    from ..oauth import get_access_token

    env_token = str(os.environ.get(GOOGLE_TOKEN_ENV, "") or "").strip()
    if env_token:
        return env_token, ""
    google_client_id, _ = settings_client_ids()
    return get_access_token("google", google_client_id)


def microsoft_token() -> tuple[str, str]:
    from ..oauth import get_access_token

    env_token = str(os.environ.get(MICROSOFT_TOKEN_ENV, "") or "").strip()
    if env_token:
        return env_token, ""
    _, ms_client_id = settings_client_ids()
    return get_access_token("microsoft", ms_client_id)


def trello_auth() -> tuple[str, str, str]:
    key = (os.environ.get(TRELLO_KEY_ENV) or "").strip()
    token = (os.environ.get(TRELLO_TOKEN_ENV) or "").strip()
    if not key or not token:
        return "", "", f"Trello nao configurado. Defina {TRELLO_KEY_ENV} e {TRELLO_TOKEN_ENV}."
    return key, token, ""
