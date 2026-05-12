"""
Backend: Microsoft Teams (Incoming Webhook).
"""
from __future__ import annotations

import json
import os

from ...indexing import Workspace, get_workspace_summary
from ._utils import TEAMS_WEBHOOK_ENV, http_json


def send_teams_summary(workspace: Workspace) -> str:
    webhook = (os.environ.get(TEAMS_WEBHOOK_ENV) or "").strip()
    if not webhook:
        return f"Teams nao configurado. Defina {TEAMS_WEBHOOK_ENV}."

    text = (
        "Sahara Fennec - resumo de planilha\n\n"
        f"Arquivo: {workspace.workbook_name}\n"
        f"Aba: {workspace.sheet_name}\n\n"
        f"{get_workspace_summary(workspace)[:3500]}"
    )
    status, _, err = http_json(
        "POST",
        webhook,
        {"Content-Type": "application/json"},
        json.dumps({"text": text}).encode("utf-8"),
    )
    if 200 <= status < 300:
        return "Resumo enviado para o Microsoft Teams com sucesso."
    return f"Falha ao enviar para Teams (status={status}). {err[:300]}"
