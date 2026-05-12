"""
Backend: Trello (API key + token).
"""
from __future__ import annotations

import os
import re
import urllib.parse

from ...indexing import Workspace, get_workspace_summary
from ._utils import TRELLO_LIST_ENV, http_json, trello_auth


def trello_list_boards() -> str:
    key, token, err = trello_auth()
    if err:
        return err
    url = f"https://api.trello.com/1/members/me/boards?fields=name,url&key={urllib.parse.quote(key)}&token={urllib.parse.quote(token)}"
    status, data, details = http_json("GET", url, {"Accept": "application/json"})
    if not (200 <= status < 300):
        return f"Falha ao listar quadros Trello (status={status}). {details[:300]}"
    if not isinstance(data, list):
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


def trello_create_card(query: str, workspace: Workspace) -> str:
    key, token, err = trello_auth()
    if err:
        return err
    list_id = (os.environ.get(TRELLO_LIST_ENV) or "").strip()
    m = re.search(r"lista[:\s]+([A-Za-z0-9]+)", query or "", re.IGNORECASE)
    if m:
        list_id = m.group(1)
    if not list_id:
        return "Informe a lista Trello (FENNEC_TRELLO_LIST_ID) ou use 'lista <id>' no comando."

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
    status, data, details = http_json(
        "POST",
        "https://api.trello.com/1/cards",
        {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        urllib.parse.urlencode(params).encode("utf-8"),
    )
    if not (200 <= status < 300):
        return f"Falha ao criar card no Trello (status={status}). {details[:300]}"
    card_url = data.get("url", "")
    return f"Card criado no Trello com sucesso.\nLink: {card_url}" if card_url else "Card criado no Trello."
