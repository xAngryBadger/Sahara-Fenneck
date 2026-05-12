"""Integration tests for the agent loop (run_agent) with mocked LLM."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from src.agent.runner import _extract_actions, _extract_loose_actions, _extract_optimize, run_agent
from src.indexing.excel_reader import Workspace


def _make_workspace(df, path="/tmp/test_agent.xlsx"):
    return Workspace(
        path=path,
        workbook_name="test.xlsx",
        sheet_name="Sheet1",
        columns=list(df.columns),
        row_count=len(df),
        indexed_rows=len(df),
        truncated=False,
        df=df,
        excel_live=False,
    )


@pytest.fixture
def ws(sample_df):
    return _make_workspace(sample_df)


@pytest.fixture
def mock_ollama():
    client = MagicMock()
    client.is_available.return_value = True
    client.model = "test"
    client.base_url = "http://localhost:11434"
    return client


class TestExtractActions:
    def test_tagged_actions(self):
        text = 'some text [ACTIONS]\n[{"action":"sort","by":"A"}]\n[/ACTIONS]'
        assert _extract_actions(text) is not None

    def test_no_actions_tag(self):
        text = "just a regular response"
        assert _extract_actions(text) is None


class TestExtractLooseActions:
    def test_json_array_in_text(self):
        text = 'Here are the actions:\n[{"action":"sort","by":"A"}]'
        result = _extract_loose_actions(text)
        assert result is not None

    def test_no_json(self):
        text = "No JSON here"
        assert _extract_loose_actions(text) is None


class TestExtractOptimize:
    def test_tagged(self):
        text = "some [OPTIMIZE]\ndf = df.sort_values('A')\n[/OPTIMIZE]"
        assert _extract_optimize(text) is not None

    def test_no_tag(self):
        assert _extract_optimize("no optimize here") is None


class TestRunAgentOptimizeBlocked:
    def test_optimize_returns_deprecation(self, ws, mock_ollama, tmp_path):
        mock_ollama.generate.return_value = (
            "Vou otimizar:\n[OPTIMIZE]\ndf = df.sort_values('A')\n[/OPTIMIZE]"
        )
        ws.path = str(tmp_path / "test.xlsx")
        sample_df = ws.df
        sample_df.to_excel(ws.path, index=False, engine="openpyxl")
        messages = []
        result = run_agent(
            "ordena por A",
            ws,
            client=mock_ollama,
            on_message=lambda m: messages.append(m),
            on_confirm_change=lambda preview: True,
        )
        assert "removida" in result.lower() or "segurança" in result.lower()


class TestRunAgentActionsApplied:
    def test_sort_via_actions(self, ws, mock_ollama, tmp_path):
        actions = [{"action": "sort", "by": "Idade"}]
        mock_ollama.generate.return_value = (
            f"Vou ordenar por Idade.\n[ACTIONS]\n{json.dumps(actions)}\n[/ACTIONS]"
        )
        ws.path = str(tmp_path / "test.xlsx")
        ws.df.to_excel(ws.path, index=False, engine="openpyxl")
        run_agent(
            "ordena por idade",
            ws,
            client=mock_ollama,
            on_confirm_change=lambda preview: True,
        )
        assert ws.df is not None
        assert list(ws.df["Idade"]) == [22, 25, 28, 30, 35]


class TestRunAgentActionsRejected:
    def test_user_rejects_change(self, ws, mock_ollama, tmp_path):
        actions = [{"action": "sort", "by": "Idade"}]
        mock_ollama.generate.return_value = (
            f"[ACTIONS]\n{json.dumps(actions)}\n[/ACTIONS]"
        )
        ws.path = str(tmp_path / "test.xlsx")
        ws.df.to_excel(ws.path, index=False, engine="openpyxl")
        result = run_agent(
            "ordena",
            ws,
            client=mock_ollama,
            on_confirm_change=lambda preview: False,
        )
        assert "cancelada" in result.lower()


class TestRunAgentNoTool:
    def test_plain_answer(self, ws, mock_ollama, tmp_path):
        mock_ollama.generate.return_value = (
            "A planilha tem 5 linhas e 4 colunas."
        )
        ws.path = str(tmp_path / "test.xlsx")
        ws.df.to_excel(ws.path, index=False, engine="openpyxl")
        messages = []
        result = run_agent(
            "quantas linhas?",
            ws,
            client=mock_ollama,
            on_message=lambda m: messages.append(m),
        )
        assert "5" in result or "colunas" in result


class TestRunAgentActionsFailRetries:
    def test_invalid_action_retries(self, ws, mock_ollama, tmp_path):
        bad_actions = [{"action": "sort", "by": "NONEXISTENT"}]
        good_actions = [{"action": "sort", "by": "Idade"}]
        mock_ollama.generate.side_effect = [
            f"[ACTIONS]\n{json.dumps(bad_actions)}\n[/ACTIONS]",
            f"Agora sim:\n[ACTIONS]\n{json.dumps(good_actions)}\n[/ACTIONS]",
        ]
        ws.path = str(tmp_path / "test.xlsx")
        ws.df.to_excel(ws.path, index=False, engine="openpyxl")
        run_agent(
            "ordena",
            ws,
            client=mock_ollama,
            on_confirm_change=lambda preview: True,
            max_steps=3,
        )
        assert ws.df is not None


class TestRunAgentOllamaUnavailable:
    def test_returns_error_message(self, ws, tmp_path):
        mock_client = MagicMock()
        mock_client.is_available.return_value = False
        ws.path = str(tmp_path / "test.xlsx")
        ws.df.to_excel(ws.path, index=False, engine="openpyxl")
        result = run_agent("ordena por A", ws, client=mock_client)
        assert "ollama" in result.lower() or "não" in result.lower()


class TestRunAgentWorkspaceError:
    def test_error_workspace_returns_message(self, tmp_path):
        ws = Workspace(
            path="",
            workbook_name="",
            sheet_name="",
            columns=[],
            row_count=0,
            indexed_rows=0,
            error="Arquivo não encontrado.",
        )
        result = run_agent("algo", ws, client=MagicMock())
        assert "não encontrado" in result.lower() or "Nenhuma" in result
