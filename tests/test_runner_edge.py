"""Tests for runner edge cases: sheet switching, hydration, read-only path, intent classification, ReAct loop."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
from src.agent.runner import (
    _detect_sheet_name,
    _extract_loose_actions,
    _handle_sheet_query,
    _is_read_only_intent,
    _is_workbook_broad_query,
    _list_sheet_names,
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


class TestListSheetNamesCOMFallback:
    def test_com_path_no_excel(self, tmp_path):
        xlsx = tmp_path / "com_sheets.xlsx"
        pd.DataFrame({"A": [1]}).to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(
            path=str(xlsx), workbook_name="com_sheets.xlsx", sheet_name="Sheet",
            columns=["A"], row_count=1, indexed_rows=1,
            excel_live=True, excel_book_name="com_sheets.xlsx", error=None,
        )
        with patch("src.agent.runner._cached_sheet_names", return_value=[]):
            result = _list_sheet_names(ws)
            assert result == []

    def test_cached_names_returned_first(self, tmp_path):
        xlsx = tmp_path / "cached.xlsx"
        pd.DataFrame({"A": [1]}).to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(
            path=str(xlsx), workbook_name="cached.xlsx", sheet_name="Sheet",
            columns=["A"], row_count=1, indexed_rows=1,
            excel_live=True, excel_book_name="cached.xlsx", error=None,
        )
        with patch("src.agent.runner._cached_sheet_names", return_value=["Alpha", "Beta"]):
            result = _list_sheet_names(ws)
            assert result == ["Alpha", "Beta"]


class TestReActNoActionsReceived:
    def test_empty_actions_list_retries(self, tmp_path):
        xlsx = tmp_path / "react.xlsx"
        pd.DataFrame({"A": [1, 2]}).to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(
            path=str(xlsx), workbook_name="react.xlsx", sheet_name="Sheet",
            columns=["A"], row_count=2, indexed_rows=2,
            df=pd.DataFrame({"A": [1, 2]}),
            excel_live=False, excel_book_name=None, error=None,
        )
        call_count = 0

        def mock_generate(prompt, system=None, max_tokens=2048):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return '[ACTIONS]\n{"actions": []}\n[/ACTIONS]'
            return "Nenhuma ação válida foi gerada. Tente reformular."

        client = MagicMock()
        client.is_available.return_value = True
        client.generate = mock_generate
        messages = []
        run_agent("ordena por A", ws, client=client, on_message=lambda t: messages.append(t))
        assert call_count == 2
        assert len(messages) > 0

    def test_llm_returns_no_tool_block(self, tmp_path):
        xlsx = tmp_path / "notool.xlsx"
        pd.DataFrame({"A": [1, 2]}).to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(
            path=str(xlsx), workbook_name="notool.xlsx", sheet_name="Sheet",
            columns=["A"], row_count=2, indexed_rows=2,
            df=pd.DataFrame({"A": [1, 2]}),
            excel_live=False, excel_book_name=None, error=None,
        )
        client = MagicMock()
        client.is_available.return_value = True
        client.generate.return_value = "Os dados parecem organizados."
        messages = []
        result = run_agent("ordena por A", ws, client=client, on_message=lambda t: messages.append(t))
        assert "organizados" in result or any("organizados" in m for m in messages)


class TestReActMaxStepsExceeded:
    def test_max_steps_reached(self, tmp_path):
        xlsx = tmp_path / "maxsteps.xlsx"
        pd.DataFrame({"A": [1, 2]}).to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(
            path=str(xlsx), workbook_name="maxsteps.xlsx", sheet_name="Sheet",
            columns=["A"], row_count=2, indexed_rows=2,
            df=pd.DataFrame({"A": [1, 2]}),
            excel_live=False, excel_book_name=None, error=None,
        )
        call_count = 0

        def mock_generate(prompt, system=None, max_tokens=2048):
            nonlocal call_count
            call_count += 1
            return '[ACTIONS]\n{"actions": [{"action": "sort", "by": "NONEXISTENT"}]}\n[/ACTIONS]'

        client = MagicMock()
        client.is_available.return_value = True
        client.generate = mock_generate
        messages = []
        run_agent("ordena por A", ws, client=client, on_message=lambda t: messages.append(t), max_steps=3)
        assert call_count == 3


class TestReActOptimizeDeprecated:
    def test_optimize_block_returns_error(self, tmp_path):
        xlsx = tmp_path / "opt_dep.xlsx"
        pd.DataFrame({"A": [1, 2]}).to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(
            path=str(xlsx), workbook_name="opt_dep.xlsx", sheet_name="Sheet",
            columns=["A"], row_count=2, indexed_rows=2,
            df=pd.DataFrame({"A": [1, 2]}),
            excel_live=False, excel_book_name=None, error=None,
        )
        client = MagicMock()
        client.is_available.return_value = True
        client.generate.return_value = "[OPTIMIZE]\ndf = df.sort_values('A')\n[/OPTIMIZE]"
        messages = []
        result = run_agent("ordena por A", ws, client=client, on_message=lambda t: messages.append(t))
        assert "E0" in result or any("E0" in m for m in messages) or any("segurança" in m.lower() for m in messages)


class TestReActConfirmCancel:
    def test_user_cancels_confirmation(self, tmp_path):
        xlsx = tmp_path / "confirm.xlsx"
        pd.DataFrame({"A": [1, 2]}).to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(
            path=str(xlsx), workbook_name="confirm.xlsx", sheet_name="Sheet",
            columns=["A"], row_count=2, indexed_rows=2,
            df=pd.DataFrame({"A": [1, 2]}),
            excel_live=False, excel_book_name=None, error=None,
        )
        client = MagicMock()
        client.is_available.return_value = True
        client.generate.return_value = '[ACTIONS]\n{"actions": [{"action": "sort", "by": "A"}]}\n[/ACTIONS]'
        messages = []
        result = run_agent(
            "ordena por A", ws, client=client,
            on_message=lambda t: messages.append(t),
            on_confirm_change=lambda preview: False,
        )
        assert any("cancelada" in m.lower() for m in messages) or "cancelada" in result.lower()


class TestWorkbookBroadQueryIntegration:
    def test_broad_query_prepends_overview(self, tmp_path):
        xlsx = tmp_path / "broad_int.xlsx"
        with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
            pd.DataFrame({"X": [1, 2]}).to_excel(writer, sheet_name="A1", index=False)
            pd.DataFrame({"Y": [3, 4]}).to_excel(writer, sheet_name="A2", index=False)
        ws = Workspace(
            path=str(xlsx), workbook_name="broad_int.xlsx", sheet_name="A1",
            columns=["X"], row_count=2, indexed_rows=2,
            df=pd.DataFrame({"X": [1, 2]}),
            excel_live=False, excel_book_name=None, error=None,
        )
        captured_prompts = []

        def mock_generate(prompt, system=None, max_tokens=2048):
            captured_prompts.append(prompt)
            return "Este arquivo tem 2 abas."

        client = MagicMock()
        client.is_available.return_value = True
        client.generate = mock_generate
        messages = []
        run_agent("descreva a planilha", ws, client=client, on_message=lambda t: messages.append(t))
        assert len(captured_prompts) == 1
        assert "A1" in captured_prompts[0]
        assert "A2" in captured_prompts[0]

    def test_non_broad_query_no_overview(self, tmp_path):
        xlsx = tmp_path / "not_broad_int.xlsx"
        pd.DataFrame({"A": [1, 2]}).to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(
            path=str(xlsx), workbook_name="not_broad_int.xlsx", sheet_name="Sheet",
            columns=["A"], row_count=2, indexed_rows=2,
            df=pd.DataFrame({"A": [1, 2]}),
            excel_live=False, excel_book_name=None, error=None,
        )
        captured_prompts = []

        def mock_generate(prompt, system=None, max_tokens=2048):
            captured_prompts.append(prompt)
            return "A media e 1.5"

        client = MagicMock()
        client.is_available.return_value = True
        client.generate = mock_generate
        messages = []
        run_agent("qual a media de A?", ws, client=client, on_message=lambda t: messages.append(t))
        assert len(captured_prompts) == 1
        assert "Aba" not in captured_prompts[0].split("Pergunta")[0] or "overview" not in captured_prompts[0].lower()


class TestListSheetNamesNoPath:
    def test_no_path_returns_empty(self):
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0)
        assert _list_sheet_names(ws) == []


class TestRequestMoreRows:
    def test_request_more_rows_reprompts(self, tmp_path):
        import json
        xlsx = tmp_path / "more_rows.xlsx"
        pd.DataFrame({"A": range(100)}).to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(
            path=str(xlsx), workbook_name="more_rows.xlsx", sheet_name="Sheet",
            columns=["A"], row_count=100, indexed_rows=50, truncated=True,
            df=pd.DataFrame({"A": range(50)}),
            excel_live=False, excel_book_name=None, error=None,
        )
        actions = [{"action": "request_more_rows"}]
        call_count = 0

        def mock_generate(prompt, system=None, max_tokens=2048):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return f"[ACTIONS]\n{json.dumps({'actions': actions})}\n[/ACTIONS]"
            return "Dados carregados com sucesso."

        client = MagicMock()
        client.is_available.return_value = True
        client.generate = mock_generate
        msgs = []
        result = run_agent("altera para carregar mais linhas", ws, client=client, on_message=lambda t: msgs.append(t), max_steps=3)
        assert call_count == 2
        assert "sucesso" in result.lower() or "dados" in result.lower()


class TestAdjustHeader:
    def test_adjust_header_reprompts(self, tmp_path):
        import json
        xlsx = tmp_path / "header.xlsx"
        df = pd.DataFrame({"0": ["Nome", "Alice", "Bob"], "1": ["Idade", 25, 30]})
        df.to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(
            path=str(xlsx), workbook_name="header.xlsx", sheet_name="Sheet",
            columns=["0", "1"], row_count=3, indexed_rows=3, df=df,
            excel_live=False, excel_book_name=None, error=None,
        )
        actions = [{"action": "adjust_header"}]
        call_count = 0

        def mock_generate(prompt, system=None, max_tokens=2048):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return f"[ACTIONS]\n{json.dumps({'actions': actions})}\n[/ACTIONS]"
            return "Cabeçalho ajustado."

        client = MagicMock()
        client.is_available.return_value = True
        client.generate = mock_generate
        msgs = []
        run_agent("altera o cabeçalho", ws, client=client, on_message=lambda t: msgs.append(t), max_steps=3)
        assert call_count == 2


class TestReadOnlyNoLLM:
    def test_read_only_no_llm_returns_local_answer(self, tmp_path):
        xlsx = tmp_path / "nollm.xlsx"
        pd.DataFrame({"A": [1, 2], "B": [3, 4]}).to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(
            path=str(xlsx), workbook_name="nollm.xlsx", sheet_name="Sheet",
            columns=["A", "B"], row_count=2, indexed_rows=2,
            df=pd.DataFrame({"A": [1, 2], "B": [3, 4]}),
            excel_live=False, excel_book_name=None, error=None,
        )
        client = MagicMock()
        client.is_available.return_value = False
        messages = []
        result = run_agent("qual a media de A?", ws, client=client, on_message=lambda t: messages.append(t))
        assert "LLM indispon" in result or "indispon" in result
        assert len(messages) > 0

    def test_read_only_with_llm_works(self, tmp_path):
        xlsx = tmp_path / "withllm.xlsx"
        pd.DataFrame({"A": [1, 2], "B": [3, 4]}).to_excel(xlsx, index=False, engine="openpyxl")
        ws = Workspace(
            path=str(xlsx), workbook_name="withllm.xlsx", sheet_name="Sheet",
            columns=["A", "B"], row_count=2, indexed_rows=2,
            df=pd.DataFrame({"A": [1, 2], "B": [3, 4]}),
            excel_live=False, excel_book_name=None, error=None,
        )
        client = MagicMock()
        client.is_available.return_value = True
        client.generate.return_value = "A media de A e 1.5"
        messages = []
        run_agent("qual a media de A?", ws, client=client, on_message=lambda t: messages.append(t))
        assert len(messages) > 0


class TestRunnerParameterNames:
    def test_run_agent_accepts_query_not_text(self, tmp_path):
        import inspect
        sig = inspect.signature(run_agent)
        assert "query" in sig.parameters
        assert "text" not in sig.parameters
