"""
Backend: Google Calendar.
"""
from __future__ import annotations

import urllib.parse
from datetime import UTC, datetime

from ._utils import google_token, http_json


def list_google_calendar_events() -> str:
    token, err = google_token()
    if not token:
        return f"Google Agenda nao disponivel. {err}"

    params = urllib.parse.urlencode(
        {
            "maxResults": 10,
            "singleEvents": "true",
            "orderBy": "startTime",
            "timeMin": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
    )
    status, data, details = http_json(
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
