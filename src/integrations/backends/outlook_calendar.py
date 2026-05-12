"""
Backend: Outlook Calendar (Microsoft Graph).
"""
from __future__ import annotations

import urllib.parse
from datetime import UTC, datetime, timedelta

from ._utils import http_json, microsoft_token


def list_outlook_calendar() -> str:
    token, err = microsoft_token()
    if not token:
        return f"Outlook/Graph nao disponivel. {err}"
    start = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    end = (datetime.now(UTC) + timedelta(days=7)).isoformat().replace("+00:00", "Z")
    params = urllib.parse.urlencode({"startDateTime": start, "endDateTime": end, "$top": 10, "$orderby": "start/dateTime"})
    status, data, details = http_json(
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
