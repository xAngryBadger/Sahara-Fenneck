"""
Backend: Outlook Mail (Microsoft Graph).
"""
from __future__ import annotations

import json
import os

from ...indexing import Workspace, get_workspace_summary
from ._utils import OUTLOOK_TO_ENV, extract_emails, http_json, microsoft_token


def send_outlook_mail(query: str, workspace: Workspace) -> str:
    token, err = microsoft_token()
    if not token:
        return f"Outlook/Graph nao disponivel. {err}"
    recipients = extract_emails(query)
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
    status, _, details = http_json(
        "POST",
        "https://graph.microsoft.com/v1.0/me/sendMail",
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json.dumps(payload).encode("utf-8"),
    )
    if 200 <= status < 300:
        return f"E-mail enviado via Outlook para: {', '.join(recipients)}."
    return f"Falha ao enviar Outlook e-mail (status={status}). {details[:300]}"
