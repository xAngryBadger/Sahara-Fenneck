"""Tests for runner edge cases: sheet switching, hydration, read-only path, intent classification."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.agent.runner import (
    _detect_sheet_name,
    _extract_loose_actions,
    _handle_sheet_query,
    _is_read_only_intent,
    _is_workbook_broad_query,
    _strip_tool_payload_from_response,
    run_agent,
)
from src.indexing.excel_reader import Workspace


class TestIntentClassification:
    def test_read_only_questions(self):
        queries = [
            "qual a media salarial?",
            "quantos registros tem?",
            "mostre o resumo",
            "o que eh X?",
            "liste as abas",
        ]
        for q in queries:
            assert _is_read_only_intent(q), f"Should be read-only: {q}"

    def test_modification_intents(self):
        queries = [
            "ordena por salario",
            "filtra os vendedores",
            "remove a coluna X",
            "renomeie a aba",
            "apague as linhas vazias",
        ]
        for q in queries:
            assert not _is_read_only_intent(q), f"Should be modification: {q}"


class TestExtractLooseActions:
    def test_json_in_code_fence(self):
        text = 'Aqui estao as acoes:\n```json\n{"actions": [{"action": "sort", "by": ["Nome"]}]}\n```'
        result = _extract_loose_actions(text)
        assert result is not None

    def test_raw_json_dict(self):
        text = '{"actions": [{"action": "fillna", "column": "X", "value": 0}]}'
        result = _extract_loose_actions(text)
        assert result is not None

    def test_no_json(self):
        result = _extract_loose_actions("Apenas texto sem JSON")
        assert result is None

    def test_empty_text(self):
        assert _extract_loose_actions("") is None


class TestStripToolPayload:
    def test_tagged_payload_removed(self):
        response = "Vou ordenar os dados.\n[ACTIONS]\n{\"actions\": []}\n[/ACTIONS]\nResultado aplicado."
        result = _strip_tool_payload_from_response(response, "{\"actions\": []}", "ACTIONS")
        assert "[ACTIONS]" not in result
        assert "Vou ordenar" in result

    def test_no_tag(self):
        response = "Texto simples sem tags"
        result = _strip_tool_payload_from_response(response, "", "ACTIONS")
        assert result == "Texto simples sem tags"


class TestDetectSheetName:
    def test_detects_aba_pattern(self):
        ws = Workspace(path="/tmp/test.xlsx", workbook_name="test.xlsx", sheet_name="Plan1", columns=[], row_count=0, indexed_rows=0)
        with patch("src.agent.runner._cached_sheet_names", return_value=["Vendas", "RH"]):
            result = _detect_sheet_name("mostre a aba Vendas", ws)
            assert result == "Vendas"

    def test_no_sheet_reference(self):
        ws = Workspace(path="", workbook_name="", sheet_name="Plan1", columns=[], row_count=0, indexed_rows=0)
        result = _detect_sheet_name("qual a media?", ws)
        assert result is None


class TestHandleSheetQuery:
    def test_not_a_sheet_query(self):
        ws = Workspace(path="", workbook_name="", sheet_name="Plan1", columns=[], row_count=0, indexed_rows=0)
        result = _handle_sheet_query("qual a media salarial?", ws)
        assert result is None

    def test_list_sheets(self):
        ws = Workspace(path="/tmp/test.xlsx", workbook_name="test.xlsx", sheet_name="A", columns=[], row_count=0, indexed_rows=0)
        with patch("src.agent.runner._list_sheet_names", return_value=["A", "B", "C"]):
            result = _handle_sheet_query("quais as abas?", ws)
            assert result is not None
            assert "3" in result

    def test_sheet_exists(self):
        ws = Workspace(path="/tmp/test.xlsx", workbook_name="test.xlsx", sheet_name="A", columns=[], row_count=0, indexed_rows=0)
        with patch("src.agent.runner._list_sheet_names", return_value=["Vendas", "RH"]):
            with patch("src.agent.runner._detect_sheet_name", return_value="Vendas"):
                result = _handle_sheet_query("existe a aba Vendas?", ws)
                assert result is not None
                assert "Sim" in result


class TestRunAgentReadOnly:
    def test_read_only_returns_answer(self, tmp_path):
        import pandas as pd
        xlsx = tmp_path / "ro.xlsx"
        pd.DataFrame({"A": [1, 2], "B": [3, 4]}).to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(
            path=str(xlsx), workbook_name="ro.xlsx", sheet_name="Sheet",
            columns=["A", "B"], row_count=2, indexed_rows=2,
            df=pd.DataFrame({"A": [1, 2], "B": [3, 4]}),
            excel_live=False, excel_book_name=None, error=None,
        )
        client = MagicMock()
        client.is_available.return_value = True
        client.generate.return_value = "A media da coluna A e 1.5"

        messages = []
        result = run_agent("qual a media de A?", ws, client=client, on_message=lambda t: messages.append(t))
        assert "1.5" in result or len(messages) > 0

    def test_workspace_error_returns_early(self):
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0, error="Planilha com erro")
        client = MagicMock()
        messages = []
        result = run_agent("ordena por A", ws, client=client, on_message=lambda t: messages.append(t))
        assert any("erro" in m.lower() or "E0" in m for m in messages) or "E0" in result


class TestIsWorkbookBroadQuery:
    def test_broad_keywords(self, tmp_path):
        import pandas as pd
        xlsx = tmp_path / "bq.xlsx"
        pd.DataFrame({"A": [1]}).to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(path=str(xlsx), workbook_name="bq.xlsx", sheet_name="Sheet1", columns=["A"], row_count=1, indexed_rows=1)
        assert _is_workbook_broad_query("descreva a planilha", ws) is True
        assert _is_workbook_broad_query("visão geral do arquivo", ws) is True
        assert _is_workbook_broad_query("o que tem nesse workbook?", ws) is True

    def test_specific_sheet_not_broad(self, tmp_path):
        import pandas as pd
        xlsx = tmp_path / "bq.xlsx"
        pd.DataFrame({"A": [1]}).to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(path=str(xlsx), workbook_name="bq.xlsx", sheet_name="Sheet1", columns=["A"], row_count=1, indexed_rows=1)
        with patch("src.agent.runner._detect_sheet_name", return_value="Vendas"):
            assert _is_workbook_broad_query("descreva a aba Vendas", ws) is False

    def test_no_path_not_broad(self):
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0)
        assert _is_workbook_broad_query("visão geral", ws) is False

    def test_specific_query_not_broad(self, tmp_path):
        import pandas as pd
        xlsx = tmp_path / "bq.xlsx"
        pd.DataFrame({"A": [1]}).to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(path=str(xlsx), workbook_name="bq.xlsx", sheet_name="Sheet1", columns=["A"], row_count=1, indexed_rows=1)
        assert _is_workbook_broad_query("qual a media de A?", ws) is False
