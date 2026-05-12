"""Tests for runner utility functions: _extract_actions, _extract_optimize, _summarize_actions, _switch_workspace_to_sheet."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
from src.agent.runner import (
    _extract_actions,
    _extract_optimize,
    _strip_tool_payload_from_response,
    _summarize_actions,
    _switch_workspace_to_sheet,
)
from src.indexing.excel_reader import Workspace


class TestExtractActions:
    def test_tagged_actions(self):
        text = '[ACTIONS]\n{"actions": [{"action": "sort", "by": "A"}]}\n[/ACTIONS]'
        result = _extract_actions(text)
        assert result is not None
        assert "sort" in result

    def test_no_actions_tag(self):
        assert _extract_actions("plain text") is None

    def test_empty_tag(self):
        result = _extract_actions("[ACTIONS]\n\n[/ACTIONS]")
        assert result is not None


class TestExtractOptimize:
    def test_tagged_optimize(self):
        text = "[OPTIMIZE]\ndf = df.sort_values('A')\n[/OPTIMIZE]"
        result = _extract_optimize(text)
        assert result is not None
        assert "sort_values" in result

    def test_no_optimize_tag(self):
        assert _extract_optimize("plain text") is None


class TestSummarizeActions:
    def test_valid_actions(self):
        payload = '{"actions": [{"action": "sort", "by": "Nome"}, {"action": "fillna", "column": "Idade", "value": 0}]}'
        ws = Workspace(path="/tmp/test.xlsx", workbook_name="test.xlsx", sheet_name="Sheet1", columns=[], row_count=0, indexed_rows=0)
        result = _summarize_actions(payload, ws)
        assert "Ordenar" in result
        assert "Preencher" in result
        assert "test.xlsx" in result

    def test_invalid_json(self):
        ws = Workspace(path="/tmp/test.xlsx", workbook_name="test.xlsx", sheet_name="Sheet1", columns=[], row_count=0, indexed_rows=0)
        result = _summarize_actions("bad json{{{", ws)
        assert "previa" in result.lower() or "ACTIONS" in result

    def test_non_dict_action(self):
        payload = '{"actions": [42, "bad"]}'
        ws = Workspace(path="/tmp/test.xlsx", workbook_name="test.xlsx", sheet_name="Sheet1", columns=[], row_count=0, indexed_rows=0)
        result = _summarize_actions(payload, ws)
        assert "Acao invalida" in result or "acao" in result.lower()

    def test_unknown_action_kind_label(self):
        payload = '{"actions": [{"action": "teleport", "target": "mars"}]}'
        ws = Workspace(path="/tmp/test.xlsx", workbook_name="test.xlsx", sheet_name="Sheet1", columns=[], row_count=0, indexed_rows=0)
        result = _summarize_actions(payload, ws)
        assert "teleport" in result

    def test_workbook_actions_in_labels(self):
        payload = '{"actions": [{"action": "duplicate_sheet", "name": "Copy"}, {"action": "create_sheet", "name": "New"}, {"action": "delete_sheet", "name": "Old"}, {"action": "rename_sheet", "from": "A", "to": "B"}]}'
        ws = Workspace(path="/tmp/test.xlsx", workbook_name="test.xlsx", sheet_name="Sheet1", columns=[], row_count=0, indexed_rows=0)
        result = _summarize_actions(payload, ws)
        assert "Duplicar" in result
        assert "Criar" in result
        assert "Excluir" in result
        assert "Renomear" in result


class TestSwitchWorkspaceToSheet:
    def test_switch_to_different_sheet(self, tmp_path):
        xlsx = tmp_path / "multi.xlsx"
        with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
            pd.DataFrame({"A": [1]}).to_excel(writer, sheet_name="Plan1", index=False)
            pd.DataFrame({"B": [2]}).to_excel(writer, sheet_name="Plan2", index=False)
        ws = Workspace(
            path=str(xlsx), workbook_name="multi.xlsx", sheet_name="Plan1",
            columns=["A"], row_count=1, indexed_rows=1, truncated=False,
            df=pd.DataFrame({"A": [1]}), excel_live=False, excel_book_name=None, error=None,
        )
        with patch("src.agent.runner._detect_sheet_name", return_value="Plan2"):
            result = _switch_workspace_to_sheet("mostre a aba Plan2", ws)
            assert result.sheet_name == "Plan2"

    def test_same_sheet_no_switch(self, tmp_path):
        xlsx = tmp_path / "single.xlsx"
        pd.DataFrame({"A": [1]}).to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(
            path=str(xlsx), workbook_name="single.xlsx", sheet_name="Sheet1",
            columns=["A"], row_count=1, indexed_rows=1, truncated=False,
            df=pd.DataFrame({"A": [1]}), excel_live=False, excel_book_name=None, error=None,
        )
        with patch("src.agent.runner._detect_sheet_name", return_value="Sheet1"):
            result = _switch_workspace_to_sheet("ordena Sheet1", ws)
            assert result is ws

    def test_no_sheet_detected(self, tmp_path):
        xlsx = tmp_path / "nosheet.xlsx"
        pd.DataFrame({"A": [1]}).to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(
            path=str(xlsx), workbook_name="nosheet.xlsx", sheet_name="Sheet1",
            columns=["A"], row_count=1, indexed_rows=1, truncated=False,
            df=pd.DataFrame({"A": [1]}), excel_live=False, excel_book_name=None, error=None,
        )
        with patch("src.agent.runner._detect_sheet_name", return_value=None):
            result = _switch_workspace_to_sheet("qual a media?", ws)
            assert result is ws

    def test_no_path_no_switch(self):
        ws = Workspace(path="", workbook_name="", sheet_name="A", columns=[], row_count=0, indexed_rows=0)
        result = _switch_workspace_to_sheet("mostre aba B", ws)
        assert result is ws

    def test_switch_to_nonexistent_sheet(self, tmp_path):
        xlsx = tmp_path / "basic.xlsx"
        pd.DataFrame({"A": [1]}).to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(
            path=str(xlsx), workbook_name="basic.xlsx", sheet_name="Sheet1",
            columns=["A"], row_count=1, indexed_rows=1, truncated=False,
            df=pd.DataFrame({"A": [1]}), excel_live=False, excel_book_name=None, error=None,
        )
        with patch("src.agent.runner._detect_sheet_name", return_value="GhostSheet"):
            with patch("src.agent.runner.index_from_path", side_effect=Exception("no such sheet")):
                result = _switch_workspace_to_sheet("mostre aba GhostSheet", ws)
                assert result is ws


class TestStripToolPayloadVariants:
    def test_raw_json_stripped(self):
        response = 'Aqui estão as ações: {"actions": [{"action": "sort", "by": "A"}]}'
        payload = '{"actions": [{"action": "sort", "by": "A"}]}'
        result = _strip_tool_payload_from_response(response, payload, "ACTIONS")
        assert "actions" not in result or "Aqui" in result

    def test_code_fence_stripped(self):
        response = 'Ações:\n```json\n{"actions": []}\n```\nFeito.'
        payload = '{"actions": []}'
        result = _strip_tool_payload_from_response(response, payload, "ACTIONS")
        assert "```" not in result

    def test_empty_payload(self):
        response = "Texto qualquer"
        result = _strip_tool_payload_from_response(response, "", "ACTIONS")
        assert result == "Texto qualquer"

    def test_tagged_with_trailing_closing(self):
        response = "Vou ordenar.\n[ACTIONS]\n{\"actions\": []}\n[/ACTIONS]\n Algum texto.\n[/OPTIMIZE]"
        payload = '{"actions": []}'
        result = _strip_tool_payload_from_response(response, payload, "ACTIONS")
        assert "[ACTIONS]" not in result
