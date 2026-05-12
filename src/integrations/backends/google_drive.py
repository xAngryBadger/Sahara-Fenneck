"""
Backend: Google Drive (upload CSV).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from ...indexing import Workspace
from ._utils import google_token, http_json, safe_sheet_name

log = logging.getLogger(__name__)


def upload_google_drive_csv(workspace: Workspace) -> str:
    token, err = google_token()
    if not token:
        return f"Google Drive nao disponivel. {err}"
    if workspace.df is None:
        return "Nao ha DataFrame carregado para enviar ao Google Drive."

    try:
        csv_content = workspace.df.to_csv(index=False)
    except Exception as e:
        log.warning("Falha ao gerar CSV para Google Drive: %s", e)
        return f"Falha ao gerar CSV: {e!s}"

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{safe_sheet_name(workspace.workbook_name)}-{safe_sheet_name(workspace.sheet_name)}-{ts}.csv"
    metadata = {"name": filename, "mimeType": "text/csv"}
    boundary = "FENNECBOUNDARY123456789"
    payload = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\nContent-Type: text/csv; charset=UTF-8\r\n\r\n{csv_content}\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    status, data, details = http_json(
        "POST",
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,webViewLink",
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
            "Accept": "application/json",
        },
        payload,
    )
    if not (200 <= status < 300):
        return f"Falha ao enviar para Google Drive (status={status}). {details[:300]}"
    name = data.get("name", filename)
    link = data.get("webViewLink", "")
    return f"Arquivo enviado ao Google Drive: {name}\nLink: {link}" if link else f"Arquivo enviado: {name}"
