"""
Backend: OneDrive (Microsoft Graph — upload CSV).
"""
from __future__ import annotations

import urllib.parse
from datetime import datetime

from ...indexing import Workspace
from ._utils import http_json, microsoft_token, safe_sheet_name


def upload_onedrive_csv(workspace: Workspace) -> str:
    token, err = microsoft_token()
    if not token:
        return f"OneDrive nao disponivel. {err}"
    if workspace.df is None:
        return "Nao ha DataFrame carregado para enviar ao OneDrive."

    csv_data = workspace.df.to_csv(index=False).encode("utf-8")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{safe_sheet_name(workspace.workbook_name)}-{safe_sheet_name(workspace.sheet_name)}-{ts}.csv"
    encoded_name = urllib.parse.quote(f"SaharaFennec/{filename}")
    url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{encoded_name}:/content"
    status, data, details = http_json(
        "PUT",
        url,
        {"Authorization": f"Bearer {token}", "Content-Type": "text/csv", "Accept": "application/json"},
        csv_data,
    )
    if not (200 <= status < 300):
        return f"Falha ao enviar arquivo ao OneDrive (status={status}). {details[:300]}"
    link = (data.get("webUrl") or "") if isinstance(data, dict) else ""
    return f"Arquivo enviado ao OneDrive com sucesso.\nLink: {link}" if link else "Arquivo enviado ao OneDrive."
