"""Tests for integration router: dispatch routes and keyword matching."""
from __future__ import annotations

from unittest.mock import patch

from src.indexing.excel_reader import Workspace
from src.integrations.backends._utils import has_word, normalize
from src.integrations.router import handle_integration_query


class TestHasWord:
    def test_exact_match(self):
        assert has_word("enviar email", "email")

    def test_no_match(self):
        assert not has_word("enviar mensagem", "email")

    def test_partial_word_no_match(self):
        assert not has_word("emailing", "email")

    def test_accented_normalized(self):
        result = normalize("calendário")
        assert "calendario" in result


class TestNormalize:
    def test_strips_accents(self):
        assert "calendario" in normalize("calendário")

    def test_lowercases(self):
        assert "teams" in normalize("Teams")

    def test_preserves_spaces(self):
        assert " " in normalize("enviar email")


class TestRouterDispatch:
    @patch("src.integrations.router.send_teams_summary")
    def test_teams_keyword(self, mock_teams):
        mock_teams.return_value = "Teams OK"
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0)
        result = handle_integration_query("enviar resumo pelo teams", ws)
        assert result == "Teams OK"
        mock_teams.assert_called_once()

    @patch("src.integrations.router.trello_list_boards")
    def test_trello_keyword(self, mock_trello):
        mock_trello.return_value = "Trello boards"
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0)
        result = handle_integration_query("listar trello", ws)
        assert result == "Trello boards"

    @patch("src.integrations.router.trello_create_card")
    def test_trello_create_card(self, mock_create):
        mock_create.return_value = "Card created"
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0)
        result = handle_integration_query("criar card no trello", ws)
        assert result == "Card created"

    @patch("src.integrations.router.send_gmail_summary")
    def test_gmail_keyword(self, mock_gmail):
        mock_gmail.return_value = "Gmail sent"
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0)
        result = handle_integration_query("enviar email com resumo", ws)
        assert result == "Gmail sent"

    @patch("src.integrations.router.upload_onedrive_csv")
    def test_onedrive_keyword(self, mock_od):
        mock_od.return_value = "Uploaded to OneDrive"
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0)
        result = handle_integration_query("salvar no onedrive", ws)
        assert result == "Uploaded to OneDrive"

    @patch("src.integrations.router.upload_sharepoint_csv")
    def test_sharepoint_keyword(self, mock_sp):
        mock_sp.return_value = "Uploaded to SharePoint"
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0)
        result = handle_integration_query("upload para sharepoint", ws)
        assert result == "Uploaded to SharePoint"

    @patch("src.integrations.router.list_google_calendar_events")
    def test_calendar_keyword(self, mock_cal):
        mock_cal.return_value = "Calendar events"
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0)
        result = handle_integration_query("meus eventos do calendario", ws)
        assert result == "Calendar events"

    @patch("src.integrations.router.upload_google_drive_csv")
    def test_google_drive_keyword(self, mock_drive):
        mock_drive.return_value = "Uploaded to Drive"
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0)
        result = handle_integration_query("salvar no google drive", ws)
        assert result == "Uploaded to Drive"

    @patch("src.integrations.router.send_outlook_mail")
    def test_outlook_mail_keyword(self, mock_outlook):
        mock_outlook.return_value = "Outlook sent"
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0)
        result = handle_integration_query("enviar email pelo outlook", ws)
        assert result == "Outlook sent"

    @patch("src.integrations.router.list_outlook_calendar")
    def test_outlook_calendar_keyword(self, mock_cal):
        mock_cal.return_value = "Outlook calendar"
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0)
        result = handle_integration_query("eventos do calendario microsoft", ws)
        assert result == "Outlook calendar"

    def test_integration_list_message(self):
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0)
        result = handle_integration_query("quais integracoes disponiveis", ws)
        assert result is not None
        assert "Gmail" in result

    def test_no_match_returns_none(self):
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0)
        result = handle_integration_query("qual a media salarial", ws)
        assert result is None
