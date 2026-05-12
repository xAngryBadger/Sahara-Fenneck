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

from ..indexing import Workspace
from .backends import (
    list_google_calendar_events,
    list_outlook_calendar,
    send_gmail_summary,
    send_outlook_mail,
    send_teams_summary,
    trello_create_card,
    trello_list_boards,
    upload_google_drive_csv,
    upload_onedrive_csv,
    upload_sharepoint_csv,
)
from .backends._utils import (
    SHAREPOINT_DRIVE_ENV,
    SHAREPOINT_SITE_ENV,
    TEAMS_WEBHOOK_ENV,
    TRELLO_KEY_ENV,
    TRELLO_LIST_ENV,
    TRELLO_TOKEN_ENV,
    has_word,
    normalize,
)
from .oauth import provider_status


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


_INTEGRATION_LIST_WORDS = ("lista", "quais", "mostrar", "mostre")

_MS_BRAND_WORDS = ("outlook", "microsoft", "office 365")

_MAIL_WORDS = ("e-mail", "email", "gmail")

_CALENDAR_WORDS = ("calendario", "calendar")

_MAIL_ACTION_WORDS = ("enviar", "envie", "mandar", "mande", "mensagem", "resumo", "sumario")

_CALENDAR_ACTION_WORDS = ("evento", "reuniao", "horario", "compromisso")


def handle_integration_query(query: str, workspace: Workspace) -> str | None:
    """Retorna mensagem tratada por integracao ou None para seguir fluxo normal do LLM."""
    raw = query or ""
    normalized = normalize(raw)

    if "integrac" in normalized and any(has_word(normalized, x) for x in _INTEGRATION_LIST_WORDS):
        return _integration_list_message()

    if has_word(normalized, "teams"):
        return send_teams_summary(workspace)

    if has_word(normalized, "trello"):
        if any(has_word(normalized, x) for x in ("card", "cartao", "tarefa", "criar")):
            return trello_create_card(raw, workspace)
        return trello_list_boards()

    is_ms_ctx = any(has_word(normalized, x) for x in _MS_BRAND_WORDS) or "microsoft graph" in normalized
    is_mail = any(has_word(normalized, x) for x in _MAIL_WORDS) and any(
        has_word(normalized, v) for v in _MAIL_ACTION_WORDS
    )
    is_calendar = any(has_word(normalized, x) for x in _CALENDAR_WORDS) or (
        has_word(normalized, "agenda") and any(has_word(normalized, v) for v in _CALENDAR_ACTION_WORDS)
    )

    if is_ms_ctx and is_mail:
        return send_outlook_mail(raw, workspace)
    if is_ms_ctx and is_calendar:
        return list_outlook_calendar()

    if has_word(normalized, "onedrive"):
        return upload_onedrive_csv(workspace)
    if has_word(normalized, "sharepoint"):
        return upload_sharepoint_csv(workspace)

    if is_calendar:
        return list_google_calendar_events()

    if has_word(normalized, "drive") and any(has_word(normalized, x) for x in ("google", "upload", "salvar", "nuvem")):
        return upload_google_drive_csv(workspace)

    if is_mail:
        return send_gmail_summary(raw, workspace)

    return None
