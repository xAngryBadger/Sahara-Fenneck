# -*- coding: utf-8 -*-
"""
Roteador de integracoes v2.

Suporte:
- Gmail (OAuth Google API ou fallback SMTP)
- Google Calendar e Google Drive
- Outlook/Graph (email + calendario)
- OneDrive e SharePoint (Graph)
- Teams (Incoming Webhook)
- Trello (API key + token)
"""
from __future__ import annotations

import base64
import json
import os
import re
import smtplib
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any

from ..config import load_settings
from ..indexing import Workspace, get_workspace_summary
from .oauth import get_access_token, provider_status

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


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(ch for ch in value if unicodedata.category(ch) != "Mn")


def _settings_client_ids() -> tuple[str, str]:
    from .oauth_defaults import get_default_client_id

    cfg = load_settings()
    google_client_id = str(cfg.get("google_client_id", "") or "").strip() or get_default_client_id("google")
    microsoft_client_id = str(cfg.get("microsoft_client_id", "") or "").strip() or get_default_client_id("microsoft")
    return google_client_id, microsoft_client_id


def _http_json(method: str, url: str, headers: dict[str, str], payload: bytes | None = None) -> tuple[int, dict, str]:
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
            details = str(e)
        return int(getattr(e, "code", 500)), {}, details
    except Exception as e:
        return 500, {}, str(e)


def _extract_emails(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text or "")


def _safe_sheet_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name or "planilha")


def _google_token() -> tuple[str, str]:
    env_token = str(os.environ.get(GOOGLE_TOKEN_ENV, "") or "").strip()
    if env_token:
        return env_token, ""
    google_client_id, _ = _settings_client_ids()
    return get_access_token("google", google_client_id)


def _microsoft_token() -> tuple[str, str]:
    env_token = str(os.environ.get(MICROSOFT_TOKEN_ENV, "") or "").strip()
    if env_token:
        return env_token, ""
    _, ms_client_id = _settings_client_ids()
    return get_access_token("microsoft", ms_client_id)


def _integration_list_message() -> str:
    google_status = provider_status("google")
    ms_status = provider_status("microsoft")
    return (
        "Integracoes disponiveis (v2):\n"
        "- Gmail (Google API OAuth)\n"
        "- Google Agenda\n"
        "- Google Drive\n"
        "- Outlook/Graph (email e calendario)\n"
        "- OneDrive e SharePoint (Graph)\n"
        "- Microsoft Teams (webhook)\n"
        "- Trello (API key + token)\n\n"
        f"Status OAuth Google: {google_status}\n"
        f"Status OAuth Microsoft: {ms_status}\n\n"
        "Config minima:\n"
        f"- Teams: {TEAMS_WEBHOOK_ENV}\n"
        f"- Trello: {TRELLO_KEY_ENV}, {TRELLO_TOKEN_ENV}, {TRELLO_LIST_ENV}\n"
        f"- SharePoint (opcional): {SHAREPOINT_SITE_ENV}, {SHAREPOINT_DRIVE_ENV} (opcional)"
    )


def _send_teams_summary(workspace: Workspace) -> str:
    webhook = (os.environ.get(TEAMS_WEBHOOK_ENV) or "").strip()
    if not webhook:
        return f"Teams nao configurado. Defina {TEAMS_WEBHOOK_ENV}."

    text = (
        "Sahara Fennec - resumo de planilha\n\n"
        f"Arquivo: {workspace.workbook_name}\n"
        f"Aba: {workspace.sheet_name}\n\n"
        f"{get_workspace_summary(workspace)[:3500]}"
    )
    status, _, err = _http_json(
        "POST",
        webhook,
        {"Content-Type": "application/json"},
        payload=json.dumps({"text": text}).encode("utf-8"),
    )
    if 200 <= status < 300:
        return "Resumo enviado para o Microsoft Teams com sucesso."
    return f"Falha ao enviar para Teams (status={status}). {err[:300]}"


def _send_gmail_summary(query: str, workspace: Workspace) -> str:
    recipients = _extract_emails(query)
    if not recipients:
        env_to = (os.environ.get(GMAIL_TO_ENV) or "").strip()
        if env_to:
            recipients = [x.strip() for x in env_to.split(",") if x.strip()]
    if not recipients:
        return "Informe destinatario no texto (ex: para nome@empresa.com) ou configure FENNEC_GMAIL_TO."

    subject = f"Resumo de planilha - {workspace.workbook_name} / {workspace.sheet_name}"
    body = (
        "Resumo gerado pelo Sahara Fennec\n\n"
        f"Arquivo: {workspace.workbook_name}\n"
        f"Aba: {workspace.sheet_name}\n\n"
        f"{get_workspace_summary(workspace)}"
    )

    # OAuth Google API (preferencial)
    token, err = _google_token()
    if token:
        msg = EmailMessage()
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg.set_content(body)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii").rstrip("=")
        status, _, details = _http_json(
            "POST",
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            payload=json.dumps({"raw": raw}).encode("utf-8"),
        )
        if 200 <= status < 300:
            return f"E-mail enviado via Gmail API para: {', '.join(recipients)}."
        # continua para fallback SMTP

    # Fallback SMTP com app password
    user = (os.environ.get(GMAIL_USER_ENV) or "").strip()
    password = (os.environ.get(GMAIL_PASS_ENV) or "").strip()
    if not user or not password:
        oauth_hint = f" OAuth: {err}" if err else ""
        return (
            "Gmail indisponivel no momento. Para fallback SMTP, defina "
            f"{GMAIL_USER_ENV} e {GMAIL_PASS_ENV}.{oauth_hint}"
        )
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
        return f"E-mail enviado via SMTP para: {', '.join(recipients)}."
    except Exception as e:
        return f"Falha ao enviar Gmail: {e!s}"


def _list_google_calendar_events() -> str:
    token, err = _google_token()
    if not token:
        return f"Google Agenda nao disponivel. {err}"

    params = urllib.parse.urlencode(
        {
            "maxResults": 10,
            "singleEvents": "true",
            "orderBy": "startTime",
            "timeMin": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    )
    status, data, details = _http_json(
        "GET",
        f"https://www.googleapis.com/calendar/v3/calendars/primary/events?{params}",
        {"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if not (200 <= status < 300):
        return f"Falha ao consultar Google Agenda (status={status}). {details[:300]}"

    items = data.get("items", []) if isinstance(data, dict) else []
    if not items:
        return "Nenhum compromisso encontrado na Google Agenda."
    lines = ["Proximos compromissos da Google Agenda:"]
    for item in items[:10]:
        start = item.get("start", {}) if isinstance(item, dict) else {}
        when = start.get("dateTime") or start.get("date") or "sem data"
        title = item.get("summary") or "(sem titulo)"
        lines.append(f"- {when}: {title}")
    return "\n".join(lines)


def _upload_google_drive_csv(workspace: Workspace) -> str:
    token, err = _google_token()
    if not token:
        return f"Google Drive nao disponivel. {err}"
    if workspace.df is None:
        return "Nao ha DataFrame carregado para enviar ao Google Drive."

    try:
        csv_content = workspace.df.to_csv(index=False)
    except Exception as e:
        return f"Falha ao gerar CSV: {e!s}"

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{_safe_sheet_name(workspace.workbook_name)}-{_safe_sheet_name(workspace.sheet_name)}-{ts}.csv"
    metadata = {"name": filename, "mimeType": "text/csv"}
    boundary = "FENNECBOUNDARY123456789"
    payload = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\nContent-Type: text/csv; charset=UTF-8\r\n\r\n{csv_content}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    status, data, details = _http_json(
        "POST",
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,webViewLink",
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
            "Accept": "application/json",
        },
        payload=payload,
    )
    if not (200 <= status < 300):
        return f"Falha ao enviar para Google Drive (status={status}). {details[:300]}"
    name = data.get("name", filename)
    link = data.get("webViewLink", "")
    return f"Arquivo enviado ao Google Drive: {name}\nLink: {link}" if link else f"Arquivo enviado: {name}"


def _list_outlook_calendar() -> str:
    token, err = _microsoft_token()
    if not token:
        return f"Outlook/Graph nao disponivel. {err}"
    start = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    end = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat().replace("+00:00", "Z")
    params = urllib.parse.urlencode({"startDateTime": start, "endDateTime": end, "$top": 10, "$orderby": "start/dateTime"})
    status, data, details = _http_json(
        "GET",
        f"https://graph.microsoft.com/v1.0/me/calendarView?{params}",
        {"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if not (200 <= status < 300):
        return f"Falha ao consultar Outlook Calendar (status={status}). {details[:300]}"
    items = data.get("value", []) if isinstance(data, dict) else []
    if not items:
        return "Nenhum compromisso encontrado no Outlook Calendar."
    lines = ["Proximos compromissos (Outlook):"]
    for item in items[:10]:
        start_obj = item.get("start", {}) if isinstance(item, dict) else {}
        when = start_obj.get("dateTime") or "sem data"
        title = item.get("subject") or "(sem titulo)"
        lines.append(f"- {when}: {title}")
    return "\n".join(lines)


def _send_outlook_mail(query: str, workspace: Workspace) -> str:
    token, err = _microsoft_token()
    if not token:
        return f"Outlook/Graph nao disponivel. {err}"
    recipients = _extract_emails(query)
    if not recipients:
        env_to = (os.environ.get(OUTLOOK_TO_ENV) or "").strip()
        if env_to:
            recipients = [x.strip() for x in env_to.split(",") if x.strip()]
    if not recipients:
        return "Informe destinatario no texto (ex: para pessoa@empresa.com) ou configure FENNEC_OUTLOOK_TO."

    payload = {
        "message": {
            "subject": f"Resumo de planilha - {workspace.workbook_name} / {workspace.sheet_name}",
            "body": {
                "contentType": "Text",
                "content": (
                    "Resumo gerado pelo Sahara Fennec\n\n"
                    f"Arquivo: {workspace.workbook_name}\n"
                    f"Aba: {workspace.sheet_name}\n\n"
                    f"{get_workspace_summary(workspace)}"
                ),
            },
            "toRecipients": [{"emailAddress": {"address": e}} for e in recipients],
        },
        "saveToSentItems": True,
    }
    status, _, details = _http_json(
        "POST",
        "https://graph.microsoft.com/v1.0/me/sendMail",
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        payload=json.dumps(payload).encode("utf-8"),
    )
    if 200 <= status < 300:
        return f"E-mail enviado via Outlook para: {', '.join(recipients)}."
    return f"Falha ao enviar Outlook e-mail (status={status}). {details[:300]}"


def _upload_onedrive_csv(workspace: Workspace) -> str:
    token, err = _microsoft_token()
    if not token:
        return f"OneDrive nao disponivel. {err}"
    if workspace.df is None:
        return "Nao ha DataFrame carregado para enviar ao OneDrive."

    csv_data = workspace.df.to_csv(index=False).encode("utf-8")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{_safe_sheet_name(workspace.workbook_name)}-{_safe_sheet_name(workspace.sheet_name)}-{ts}.csv"
    encoded_name = urllib.parse.quote(f"SaharaFennec/{filename}")
    url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{encoded_name}:/content"
    status, data, details = _http_json(
        "PUT",
        url,
        {"Authorization": f"Bearer {token}", "Content-Type": "text/csv", "Accept": "application/json"},
        payload=csv_data,
    )
    if not (200 <= status < 300):
        return f"Falha ao enviar arquivo ao OneDrive (status={status}). {details[:300]}"
    link = (data.get("webUrl") or "") if isinstance(data, dict) else ""
    return f"Arquivo enviado ao OneDrive com sucesso.\nLink: {link}" if link else "Arquivo enviado ao OneDrive."


def _upload_sharepoint_csv(workspace: Workspace) -> str:
    token, err = _microsoft_token()
    if not token:
        return f"SharePoint nao disponivel. {err}"
    site_id = (os.environ.get(SHAREPOINT_SITE_ENV) or "").strip()
    drive_id = (os.environ.get(SHAREPOINT_DRIVE_ENV) or "").strip()
    if not site_id:
        return (
            "SharePoint precisa de configuracao de site.\n"
            f"Defina {SHAREPOINT_SITE_ENV} (e opcionalmente {SHAREPOINT_DRIVE_ENV})."
        )
    if workspace.df is None:
        return "Nao ha DataFrame carregado para enviar ao SharePoint."

    csv_data = workspace.df.to_csv(index=False).encode("utf-8")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{_safe_sheet_name(workspace.workbook_name)}-{_safe_sheet_name(workspace.sheet_name)}-{ts}.csv"
    encoded_name = urllib.parse.quote(f"SaharaFennec/{filename}")
    if drive_id:
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root:/{encoded_name}:/content"
    else:
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:/{encoded_name}:/content"
    status, data, details = _http_json(
        "PUT",
        url,
        {"Authorization": f"Bearer {token}", "Content-Type": "text/csv", "Accept": "application/json"},
        payload=csv_data,
    )
    if not (200 <= status < 300):
        return f"Falha ao enviar arquivo ao SharePoint (status={status}). {details[:300]}"
    link = (data.get("webUrl") or "") if isinstance(data, dict) else ""
    return f"Arquivo enviado ao SharePoint com sucesso.\nLink: {link}" if link else "Arquivo enviado ao SharePoint."


def _trello_auth() -> tuple[str, str, str]:
    key = (os.environ.get(TRELLO_KEY_ENV) or "").strip()
    token = (os.environ.get(TRELLO_TOKEN_ENV) or "").strip()
    if not key or not token:
        return "", "", f"Trello nao configurado. Defina {TRELLO_KEY_ENV} e {TRELLO_TOKEN_ENV}."
    return key, token, ""


def _trello_list_boards() -> str:
    key, token, err = _trello_auth()
    if err:
        return err
    url = f"https://api.trello.com/1/members/me/boards?fields=name,url&key={urllib.parse.quote(key)}&token={urllib.parse.quote(token)}"
    status, data, details = _http_json("GET", url, {"Accept": "application/json"})
    if not (200 <= status < 300):
        return f"Falha ao listar quadros Trello (status={status}). {details[:300]}"
    if not isinstance(data, list):
        # _http_json retorna dict para JSON object; Trello retorna array
        # se vier object, tenta campo raw
        raw = data.get("raw")
        if isinstance(raw, list):
            boards = raw
        else:
            boards = []
    else:
        boards = data
    if not boards:
        return "Nenhum quadro Trello encontrado."
    lines = ["Quadros Trello:"]
    for b in boards[:10]:
        lines.append(f"- {b.get('name', '(sem nome)')} | {b.get('url', '')}")
    return "\n".join(lines)


def _trello_create_card(query: str, workspace: Workspace) -> str:
    key, token, err = _trello_auth()
    if err:
        return err
    list_id = (os.environ.get(TRELLO_LIST_ENV) or "").strip()
    m = re.search(r"lista[:\s]+([A-Za-z0-9]+)", query or "", re.IGNORECASE)
    if m:
        list_id = m.group(1)
    if not list_id:
        return f"Informe a lista Trello (FENNEC_TRELLO_LIST_ID) ou use 'lista <id>' no comando."

    title = ""
    m2 = re.search(r"titulo[:\s]+(.+)$", query or "", re.IGNORECASE)
    if m2:
        title = m2.group(1).strip()
    if not title:
        title = f"Resumo {workspace.workbook_name} - {workspace.sheet_name}"

    desc = (
        "Criado pelo Sahara Fennec\n\n"
        f"Arquivo: {workspace.workbook_name}\n"
        f"Aba: {workspace.sheet_name}\n\n"
        f"{get_workspace_summary(workspace)[:3000]}"
    )
    params = {
        "key": key,
        "token": token,
        "idList": list_id,
        "name": title,
        "desc": desc,
    }
    status, data, details = _http_json(
        "POST",
        "https://api.trello.com/1/cards",
        {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        payload=urllib.parse.urlencode(params).encode("utf-8"),
    )
    if not (200 <= status < 300):
        return f"Falha ao criar card no Trello (status={status}). {details[:300]}"
    card_url = data.get("url", "")
    return f"Card criado no Trello com sucesso.\nLink: {card_url}" if card_url else "Card criado no Trello."


def handle_integration_query(query: str, workspace: Workspace) -> str | None:
    """Retorna mensagem tratada por integracao ou None para seguir fluxo normal do LLM."""
    raw = query or ""
    normalized = _normalize(raw)

    if "integrac" in normalized and any(x in normalized for x in ("lista", "quais", "mostrar", "mostre")):
        return _integration_list_message()

    if "teams" in normalized:
        return _send_teams_summary(workspace)

    if "trello" in normalized:
        if any(x in normalized for x in ("card", "cartao", "tarefa", "criar")):
            return _trello_create_card(raw, workspace)
        return _trello_list_boards()

    is_ms_ctx = any(x in normalized for x in ("outlook", "graph", "corporativ", "office 365", "microsoft"))
    is_mail = any(x in normalized for x in ("e-mail", "email", "gmail", "correio"))
    is_calendar = any(x in normalized for x in ("agenda", "calendario", "calendar", "compromisso"))

    if is_ms_ctx and is_mail:
        return _send_outlook_mail(raw, workspace)
    if is_ms_ctx and is_calendar:
        return _list_outlook_calendar()

    if "onedrive" in normalized:
        return _upload_onedrive_csv(workspace)
    if "sharepoint" in normalized:
        return _upload_sharepoint_csv(workspace)

    if is_calendar:
        return _list_google_calendar_events()

    if "drive" in normalized:
        return _upload_google_drive_csv(workspace)

    if is_mail:
        return _send_gmail_summary(raw, workspace)

    return None

