# -*- coding: utf-8 -*-
"""Smoke test: empty actions validation + sheet context switching."""
import sys, pathlib, tempfile, shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import openpyxl
from src.indexing.excel_reader import Workspace
from src.agent.runner import _handle_sheet_query, _switch_workspace_to_sheet

# --- 1. Empty actions validation (tested indirectly through runner) ---
import json
from src.agent.runner import _extract_actions, _extract_loose_actions

text_empty = '[ACTIONS]{"actions": []}[/ACTIONS]'
payload = _extract_actions(text_empty)
assert payload is not None
raw = json.loads(payload)
acts = raw.get("actions", [])
assert acts == [], "Expected empty list"
print("OK: empty actions detected correctly")

# --- 2. Sheet switch test ---
tmp = pathlib.Path(tempfile.mkdtemp()) / "switch_test.xlsx"
wb = openpyxl.Workbook()
wb.active.title = "Vendas"
wb.active.append(["Produto", "Valor"])
wb.active.append(["A", 100])
wb.create_sheet("Estoque")
wb["Estoque"].append(["Item", "Qtd"])
wb["Estoque"].append(["B", 50])
wb.save(str(tmp))
wb.close()

# Create workspace pointing to "Vendas"
ws = Workspace(
    path=str(tmp),
    workbook_name=tmp.name,
    sheet_name="Vendas",
    columns=["Produto", "Valor"],
    row_count=1,
    indexed_rows=1,
)

# Ask about "aba Estoque" => should switch context
result = _switch_workspace_to_sheet("o que tem na aba Estoque?", ws)
assert result.sheet_name == "Estoque", f"Expected Estoque, got {result.sheet_name}"
print("OK: workspace switched to Estoque")

# Ask without sheet reference => should stay on same
result2 = _switch_workspace_to_sheet("mostre os dados", ws)
assert result2 is ws, "Should return same workspace"
print("OK: no switch when no sheet reference")

# --- 3. _handle_sheet_query with "quantas" ---
reply = _handle_sheet_query("quantas abas tem?", ws)
assert reply is not None and "2" in reply, f"Expected 2 sheets answer: {reply}"
print("OK: quantas abas query works")

shutil.rmtree(tmp.parent, ignore_errors=True)
print("SMOKE_SWITCH_VALIDATE_OK")
