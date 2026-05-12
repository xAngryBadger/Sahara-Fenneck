"""
Backend: SharePoint (Microsoft Graph — upload CSV).
"""
from __future__ import annotations

import os
import urllib.parse
from datetime import datetime

from ...indexing import Workspace
from ._utils import SHAREPOINT_DRIVE_ENV, SHAREPOINT_SITE_ENV, http_json, microsoft_token, safe_sheet_name


def upload_sharepoint_csv(workspace: Workspace) -> str:
    token, err = microsoft_token()
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
    filename = f"{safe_sheet_name(workspace.workbook_name)}-{safe_sheet_name(workspace.sheet_name)}-{ts}.csv"
    encoded_name = urllib.parse.quote(f"SaharaFennec/{filename}")
    if drive_id:
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root:/{encoded_name}:/content"
    else:
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:/{encoded_name}:/content"
    status, data, details = http_json(
        "PUT",
        url,
        {"Authorization": f"Bearer {token}", "Content-Type": "text/csv", "Accept": "application/json"},
        csv_data,
    )
    if not (200 <= status < 300):
        return f"Falha ao enviar arquivo ao SharePoint (status={status}). {details[:300]}"
    link = (data.get("webUrl") or "") if isinstance(data, dict) else ""
    return f"Arquivo enviado ao SharePoint com sucesso.\nLink: {link}" if link else "Arquivo enviado ao SharePoint."
