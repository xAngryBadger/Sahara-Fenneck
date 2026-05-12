"""
Backend: Gmail (OAuth Google API ou fallback SMTP).
"""
from __future__ import annotations

import base64
import json
import logging
import os
import smtplib
from email.message import EmailMessage

from ...indexing import Workspace, get_workspace_summary
from ._utils import GMAIL_PASS_ENV, GMAIL_TO_ENV, GMAIL_USER_ENV, extract_emails, google_token, http_json

log = logging.getLogger(__name__)


def send_gmail_summary(query: str, workspace: Workspace) -> str:
    recipients = extract_emails(query)
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

    token, err = google_token()
    if token:
        msg = EmailMessage()
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg.set_content(body)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii").rstrip("=")
        status, _, details = http_json(
            "POST",
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json.dumps({"raw": raw}).encode("utf-8"),
        )
        if 200 <= status < 300:
            return f"E-mail enviado via Gmail API para: {', '.join(recipients)}."

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
        log.warning("Falha ao enviar e-mail via SMTP Gmail: %s", e)
        return f"Falha ao enviar Gmail: {e!s}"
