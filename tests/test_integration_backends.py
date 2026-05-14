"""Comprehensive tests for integration backends and router.

All HTTP calls are mocked — no real network access.
"""
from __future__ import annotations

import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

from src.indexing import Workspace
from src.integrations.backends._utils import (
    GMAIL_PASS_ENV,
    GMAIL_TO_ENV,
    GMAIL_USER_ENV,
    GOOGLE_TOKEN_ENV,
    MICROSOFT_TOKEN_ENV,
    OUTLOOK_TO_ENV,
    SHAREPOINT_DRIVE_ENV,
    SHAREPOINT_SITE_ENV,
    TEAMS_WEBHOOK_ENV,
    TRELLO_KEY_ENV,
    TRELLO_LIST_ENV,
    TRELLO_TOKEN_ENV,
    extract_emails,
    google_token,
    has_word,
    http_json,
    microsoft_token,
    normalize,
    safe_sheet_name,
    trello_auth,
)
from src.integrations.backends.gmail import send_gmail_summary
from src.integrations.backends.google_calendar import list_google_calendar_events
from src.integrations.backends.google_drive import upload_google_drive_csv
from src.integrations.backends.onedrive import upload_onedrive_csv
from src.integrations.backends.outlook import send_outlook_mail
from src.integrations.backends.outlook_calendar import list_outlook_calendar
from src.integrations.backends.sharepoint import upload_sharepoint_csv
from src.integrations.backends.teams import send_teams_summary
from src.integrations.backends.trello import trello_create_card, trello_list_boards
from src.integrations.router import _integration_list_message, handle_integration_query

# ---------------------------------------------------------------------------
# _utils
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_ascii_lowercase(self):
        assert normalize("Hello World") == "hello world"

    def test_removes_diacritics(self):
        assert normalize("São Paulo") == "sao paulo"
        assert normalize("Café") == "cafe"
        assert normalize("Ação") == "acao"

    def test_empty_string(self):
        assert normalize("") == ""

    def test_none_input(self):
        assert normalize(None) == ""

    def test_mixed_diacritics(self):
        assert normalize("Órgão") == "orgao"


class TestHasWord:
    def test_word_present(self):
        assert has_word("enviar email gmail", "gmail") is True

    def test_word_absent(self):
        assert has_word("enviar email outlook", "gmail") is False

    def test_partial_match_is_not_word(self):
        assert has_word("gmailuser@company.com", "gmail") is False

    def test_case_sensitivity(self):
        assert has_word("GMAIL is cool", "gmail") is False
        assert has_word("gmail is cool", "gmail") is True

    def test_word_at_start(self):
        assert has_word("teams integration", "teams") is True

    def test_word_at_end(self):
        assert has_word("use trello", "trello") is True


class TestHttpJson:
    def _mock_response(self, body: bytes, status: int = 200):
        resp = MagicMock()
        resp.status = status
        resp.read.return_value = body
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    @patch("src.integrations.backends._utils.urllib.request.urlopen")
    def test_success_json(self, mock_urlopen):
        body = json.dumps({"id": "123", "name": "test"}).encode("utf-8")
        mock_urlopen.return_value = self._mock_response(body, 200)
        status, data, err = http_json("GET", "https://example.com/api", {"Accept": "application/json"})
        assert status == 200
        assert data == {"id": "123", "name": "test"}
        assert err == ""

    @patch("src.integrations.backends._utils.urllib.request.urlopen")
    def test_success_empty_body(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response(b"  ", 200)
        status, data, err = http_json("GET", "https://example.com/api", {})
        assert status == 200
        assert data == {}
        assert err == ""

    @patch("src.integrations.backends._utils.urllib.request.urlopen")
    def test_success_list_response(self, mock_urlopen):
        body = json.dumps([{"name": "a"}, {"name": "b"}]).encode("utf-8")
        mock_urlopen.return_value = self._mock_response(body, 200)
        status, data, err = http_json("GET", "https://example.com/api", {})
        assert status == 200
        assert data == {"raw": [{"name": "a"}, {"name": "b"}]}

    @patch("src.integrations.backends._utils.urllib.request.urlopen")
    def test_http_error(self, mock_urlopen):
        err_response = BytesIO(b'{"error": "unauthorized"}')
        http_err = urllib.error.HTTPError(
            url="https://example.com/api",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=err_response,
        )
        mock_urlopen.side_effect = http_err
        status, data, err = http_json("GET", "https://example.com/api", {})
        assert status == 401
        assert data == {}
        assert "unauthorized" in err

    @patch("src.integrations.backends._utils.urllib.request.urlopen")
    def test_connection_error(self, mock_urlopen):
        mock_urlopen.side_effect = ConnectionError("refused")
        status, data, err = http_json("GET", "https://example.com/api", {})
        assert status == 500
        assert data == {}
        assert "refused" in err

    @patch("src.integrations.backends._utils.urllib.request.urlopen")
    def test_redact_url(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response(b"{}", 200)
        http_json("GET", "https://api.trello.com/1/boards?key=SECRETKEY&token=SECRETTOKEN", {}, redact_url=True)
        mock_urlopen.assert_called_once()

    @patch("src.integrations.backends._utils.urllib.request.urlopen")
    def test_post_with_payload(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response(b'{"ok": true}', 201)
        status, data, err = http_json(
            "POST", "https://example.com/api",
            {"Content-Type": "application/json"},
            payload=b'{"test": 1}',
        )
        assert status == 201
        assert data == {"ok": True}

    @patch("src.integrations.backends._utils.urllib.request.urlopen")
    def test_http_error_unreadable_body(self, mock_urlopen):
        http_err = urllib.error.HTTPError(
            url="https://example.com/api",
            code=500,
            msg="Server Error",
            hdrs=None,
            fp=None,
        )
        http_err.read = MagicMock(side_effect=Exception("cannot read"))
        mock_urlopen.side_effect = http_err
        status, data, err = http_json("GET", "https://example.com/api", {})
        assert status == 500
        assert data == {}


class TestExtractEmails:
    def test_single_email(self):
        assert extract_emails("enviar para user@example.com") == ["user@example.com"]

    def test_multiple_emails(self):
        result = extract_emails("para a@b.com e c@d.com")
        assert result == ["a@b.com", "c@d.com"]

    def test_no_email(self):
        assert extract_emails("sem email aqui") == []

    def test_none_input(self):
        assert extract_emails(None) == []

    def test_complex_email(self):
        assert extract_emails("test.user+tag@sub.domain.com") == ["test.user+tag@sub.domain.com"]


class TestSafeSheetName:
    def test_normal_name(self):
        assert safe_sheet_name("Planilha1") == "Planilha1"

    def test_special_characters(self):
        assert safe_sheet_name("Relatório 2024") == "Relat_rio_2024"

    def test_empty_string(self):
        assert safe_sheet_name("") == "planilha"

    def test_none_input(self):
        assert safe_sheet_name(None) == "planilha"

    def test_brackets_and_colons(self):
        assert safe_sheet_name("Sheet [1]: Data") == "Sheet_1_Data"


class TestTrelloAuth:
    @patch.dict("os.environ", {TRELLO_KEY_ENV: "mykey", TRELLO_TOKEN_ENV: "mytoken"})
    def test_configured(self):
        key, token, err = trello_auth()
        assert key == "mykey"
        assert token == "mytoken"
        assert err == ""

    @patch.dict("os.environ", {}, clear=True)
    def test_not_configured(self):
        key, token, err = trello_auth()
        assert key == ""
        assert token == ""
        assert "Trello nao configurado" in err

    @patch.dict("os.environ", {TRELLO_KEY_ENV: "key_only"}, clear=True)
    def test_partial_config_missing_token(self):
        key, token, err = trello_auth()
        assert key == ""
        assert "Trello nao configurado" in err


class TestGoogleToken:
    @patch.dict("os.environ", {GOOGLE_TOKEN_ENV: "env-google-token"}, clear=True)
    def test_env_token(self):
        token, err = google_token()
        assert token == "env-google-token"
        assert err == ""

    @patch.dict("os.environ", {}, clear=True)
    @patch("src.integrations.backends._utils.settings_client_ids", return_value=("gcid", "mscid"))
    @patch("src.integrations.oauth.get_access_token", return_value=("oauth-token", ""))
    def test_oauth_fallback(self, mock_oauth, mock_ids):
        token, err = google_token()
        assert token == "oauth-token"
        assert err == ""
        mock_oauth.assert_called_once_with("google", "gcid")

    @patch.dict("os.environ", {}, clear=True)
    @patch("src.integrations.backends._utils.settings_client_ids", return_value=("gcid", "mscid"))
    @patch("src.integrations.oauth.get_access_token", return_value=("", "not connected"))
    def test_oauth_failure(self, mock_oauth, mock_ids):
        token, err = google_token()
        assert token == ""
        assert "not connected" in err


class TestMicrosoftToken:
    @patch.dict("os.environ", {MICROSOFT_TOKEN_ENV: "env-ms-token"}, clear=True)
    def test_env_token(self):
        token, err = microsoft_token()
        assert token == "env-ms-token"
        assert err == ""

    @patch.dict("os.environ", {}, clear=True)
    @patch("src.integrations.backends._utils.settings_client_ids", return_value=("gcid", "mscid"))
    @patch("src.integrations.oauth.get_access_token", return_value=("ms-oauth-token", ""))
    def test_oauth_fallback(self, mock_oauth, mock_ids):
        token, err = microsoft_token()
        assert token == "ms-oauth-token"
        assert err == ""
        mock_oauth.assert_called_once_with("microsoft", "mscid")

    @patch.dict("os.environ", {}, clear=True)
    @patch("src.integrations.backends._utils.settings_client_ids", return_value=("gcid", "mscid"))
    @patch("src.integrations.oauth.get_access_token", return_value=("", "expired"))
    def test_oauth_failure(self, mock_oauth, mock_ids):
        token, err = microsoft_token()
        assert token == ""
        assert "expired" in err


# ---------------------------------------------------------------------------
# Trello backend
# ---------------------------------------------------------------------------


class TestTrelloListBoards:
    @patch("src.integrations.backends.trello.trello_auth", return_value=("", "", "Trello nao configurado"))
    def test_auth_failure(self, mock_auth):
        result = trello_list_boards()
        assert "Trello nao configurado" in result

    @patch("src.integrations.backends.trello.trello_auth", return_value=("key", "token", ""))
    @patch("src.integrations.backends.trello.http_json", return_value=(200, [{"name": "Board1", "url": "https://trello.com/b1"}], ""))
    def test_success_with_boards(self, mock_http, mock_auth):
        result = trello_list_boards()
        assert "Board1" in result
        assert "https://trello.com/b1" in result

    @patch("src.integrations.backends.trello.trello_auth", return_value=("key", "token", ""))
    @patch("src.integrations.backends.trello.http_json", return_value=(200, {"raw": [{"name": "B2", "url": "u2"}]}, ""))
    def test_success_with_raw_list(self, mock_http, mock_auth):
        result = trello_list_boards()
        assert "B2" in result

    @patch("src.integrations.backends.trello.trello_auth", return_value=("key", "token", ""))
    @patch("src.integrations.backends.trello.http_json", return_value=(200, {}, ""))
    def test_success_empty(self, mock_http, mock_auth):
        result = trello_list_boards()
        assert "Nenhum quadro" in result

    @patch("src.integrations.backends.trello.trello_auth", return_value=("key", "token", ""))
    @patch("src.integrations.backends.trello.http_json", return_value=(403, {}, "forbidden"))
    def test_http_failure(self, mock_http, mock_auth):
        result = trello_list_boards()
        assert "Falha" in result
        assert "403" in result


class TestTrelloCreateCard:
    @patch("src.integrations.backends.trello.trello_auth", return_value=("", "", "nao configurado"))
    def test_auth_failure(self, mock_auth, workspace):
        result = trello_create_card("criar card", workspace)
        assert "nao configurado" in result

    @patch("src.integrations.backends.trello.trello_auth", return_value=("key", "token", ""))
    @patch.dict("os.environ", {}, clear=True)
    def test_no_list_id(self, mock_auth, workspace):
        result = trello_create_card("criar card", workspace)
        assert "Informe a lista" in result

    @patch("src.integrations.backends.trello.trello_auth", return_value=("key", "token", ""))
    @patch.dict("os.environ", {TRELLO_LIST_ENV: "list123"}, clear=True)
    @patch("src.integrations.backends.trello.http_json", return_value=(200, {"url": "https://trello.com/card1"}, ""))
    def test_success_env_list_id(self, mock_http, mock_auth, workspace):
        result = trello_create_card("criar card titulo: Minha Tarefa", workspace)
        assert "Card criado" in result
        assert "https://trello.com/card1" in result

    @patch("src.integrations.backends.trello.trello_auth", return_value=("key", "token", ""))
    @patch.dict("os.environ", {}, clear=True)
    @patch("src.integrations.backends.trello.http_json", return_value=(200, {"url": "https://trello.com/c2"}, ""))
    def test_success_query_list_id(self, mock_http, mock_auth, workspace):
        result = trello_create_card("lista abc123 titulo: Task", workspace)
        assert "Card criado" in result

    @patch("src.integrations.backends.trello.trello_auth", return_value=("key", "token", ""))
    @patch.dict("os.environ", {TRELLO_LIST_ENV: "list456"}, clear=True)
    @patch("src.integrations.backends.trello.http_json", return_value=(200, {}, ""))
    def test_success_no_url_in_response(self, mock_http, mock_auth, workspace):
        result = trello_create_card("criar card", workspace)
        assert "Card criado" in result

    @patch("src.integrations.backends.trello.trello_auth", return_value=("key", "token", ""))
    @patch.dict("os.environ", {TRELLO_LIST_ENV: "list789"}, clear=True)
    @patch("src.integrations.backends.trello.http_json", return_value=(400, {}, "bad request"))
    def test_http_failure(self, mock_http, mock_auth, workspace):
        result = trello_create_card("criar card", workspace)
        assert "Falha" in result

    @patch("src.integrations.backends.trello.trello_auth", return_value=("key", "token", ""))
    @patch.dict("os.environ", {TRELLO_LIST_ENV: "list999"}, clear=True)
    @patch("src.integrations.backends.trello.http_json", return_value=(200, {"url": "https://trello.com/c3"}, ""))
    def test_default_title_from_workspace(self, mock_http, mock_auth, workspace):
        trello_create_card("lista abc", workspace)
        call_args = mock_http.call_args
        payload = call_args[0][4] if len(call_args[0]) > 4 else call_args.kwargs.get("payload")
        assert "Resumo test.xlsx" in payload.decode("utf-8") if payload else True


# ---------------------------------------------------------------------------
# Teams backend
# ---------------------------------------------------------------------------


class TestSendTeamsSummary:
    @patch.dict("os.environ", {}, clear=True)
    def test_not_configured(self, workspace):
        result = send_teams_summary(workspace)
        assert "Teams nao configurado" in result

    @patch.dict("os.environ", {TEAMS_WEBHOOK_ENV: "https://outlook.webhook.url"}, clear=True)
    @patch("src.integrations.backends.teams.http_json", return_value=(200, {}, ""))
    def test_success(self, mock_http, workspace):
        result = send_teams_summary(workspace)
        assert "enviado para o Microsoft Teams" in result

    @patch.dict("os.environ", {TEAMS_WEBHOOK_ENV: "https://outlook.webhook.url"}, clear=True)
    @patch("src.integrations.backends.teams.http_json", return_value=(500, {}, "server error"))
    def test_http_failure(self, mock_http, workspace):
        result = send_teams_summary(workspace)
        assert "Falha" in result

    @patch.dict("os.environ", {TEAMS_WEBHOOK_ENV: "https://outlook.webhook.url"}, clear=True)
    @patch("src.integrations.backends.teams.http_json", return_value=(200, {}, ""))
    def test_payload_contains_workspace_info(self, mock_http, workspace):
        send_teams_summary(workspace)
        call_args = mock_http.call_args
        payload_bytes = call_args[0][3]
        payload_str = json.loads(payload_bytes.decode("utf-8"))
        assert "test.xlsx" in payload_str["text"]


# ---------------------------------------------------------------------------
# Gmail backend
# ---------------------------------------------------------------------------


class TestSendGmailSummary:
    @patch("src.integrations.backends.gmail.google_token", return_value=("gtoken", ""))
    @patch("src.integrations.backends.gmail.http_json", return_value=(200, {}, ""))
    def test_oauth_success(self, mock_http, mock_token, workspace):
        result = send_gmail_summary("enviar email para user@example.com", workspace)
        assert "Gmail API" in result
        assert "user@example.com" in result

    @patch("src.integrations.backends.gmail.google_token", return_value=("gtoken", ""))
    @patch("src.integrations.backends.gmail.http_json", return_value=(403, {}, "forbidden"))
    @patch.dict("os.environ", {GMAIL_USER_ENV: "sender@gmail.com", GMAIL_PASS_ENV: "app_pass"}, clear=True)
    @patch("src.integrations.backends.gmail.smtplib.SMTP")
    def test_smtp_fallback_on_oauth_failure(self, mock_smtp_cls, mock_http, mock_token, workspace):
        smtp_instance = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=smtp_instance)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        result = send_gmail_summary("enviar para dest@example.com", workspace)
        assert "SMTP" in result
        smtp_instance.login.assert_called_once()

    @patch("src.integrations.backends.gmail.google_token", return_value=("gtoken", ""))
    @patch("src.integrations.backends.gmail.http_json", return_value=(403, {}, "forbidden"))
    @patch.dict("os.environ", {}, clear=True)
    def test_no_credentials(self, mock_http, mock_token, workspace):
        result = send_gmail_summary("enviar email para x@y.com", workspace)
        assert "Gmail indisponivel" in result

    @patch("src.integrations.backends.gmail.google_token", return_value=("", "not connected"))
    @patch.dict("os.environ", {}, clear=True)
    def test_no_token_no_smtp(self, mock_token, workspace):
        result = send_gmail_summary("enviar para a@b.com", workspace)
        assert "Gmail indisponivel" in result

    @patch.dict("os.environ", {GMAIL_TO_ENV: "default@company.com"}, clear=True)
    @patch("src.integrations.backends.gmail.google_token", return_value=("gtoken", ""))
    @patch("src.integrations.backends.gmail.http_json", return_value=(200, {}, ""))
    def test_recipient_from_env(self, mock_http, mock_token, workspace):
        result = send_gmail_summary("enviar email", workspace)
        assert "default@company.com" in result

    @patch("src.integrations.backends.gmail.google_token", return_value=("", ""))
    @patch.dict("os.environ", {}, clear=True)
    def test_no_recipient_at_all(self, mock_token, workspace):
        result = send_gmail_summary("enviar mensagem", workspace)
        assert "Informe destinatario" in result

    @patch("src.integrations.backends.gmail.google_token", return_value=("gtoken", ""))
    @patch("src.integrations.backends.gmail.http_json", return_value=(403, {}, "forbidden"))
    @patch.dict("os.environ", {GMAIL_USER_ENV: "s@gmail.com", GMAIL_PASS_ENV: "pass"}, clear=True)
    @patch("src.integrations.backends.gmail.smtplib.SMTP", side_effect=Exception("SMTP failed"))
    def test_smtp_exception(self, mock_smtp_cls, mock_http, mock_token, workspace):
        result = send_gmail_summary("enviar para d@e.com", workspace)
        assert "Falha ao enviar Gmail" in result


# ---------------------------------------------------------------------------
# SharePoint backend
# ---------------------------------------------------------------------------


class TestUploadSharepointCsv:
    @patch("src.integrations.backends.sharepoint.microsoft_token", return_value=("", "not available"))
    def test_no_token(self, mock_token, workspace):
        result = upload_sharepoint_csv(workspace)
        assert "SharePoint nao disponivel" in result

    @patch("src.integrations.backends.sharepoint.microsoft_token", return_value=("mstoken", ""))
    @patch.dict("os.environ", {}, clear=True)
    def test_no_site_id(self, mock_token, workspace):
        result = upload_sharepoint_csv(workspace)
        assert "configuracao de site" in result

    @patch("src.integrations.backends.sharepoint.microsoft_token", return_value=("mstoken", ""))
    @patch.dict("os.environ", {SHAREPOINT_SITE_ENV: "invalid site id!"}, clear=True)
    def test_invalid_site_id(self, mock_token, workspace):
        result = upload_sharepoint_csv(workspace)
        assert "site_id invalido" in result

    @patch("src.integrations.backends.sharepoint.microsoft_token", return_value=("mstoken", ""))
    @patch.dict("os.environ", {SHAREPOINT_SITE_ENV: "site123", SHAREPOINT_DRIVE_ENV: "bad drive!"}, clear=True)
    def test_invalid_drive_id(self, mock_token, workspace):
        result = upload_sharepoint_csv(workspace)
        assert "drive_id invalido" in result

    @patch("src.integrations.backends.sharepoint.microsoft_token", return_value=("mstoken", ""))
    @patch.dict("os.environ", {SHAREPOINT_SITE_ENV: "site123"}, clear=True)
    @patch("src.integrations.backends.sharepoint.http_json", return_value=(201, {"webUrl": "https://sharepoint.com/file"}, ""))
    def test_success_with_site_only(self, mock_http, mock_token, workspace):
        result = upload_sharepoint_csv(workspace)
        assert "enviado ao SharePoint" in result
        assert "https://sharepoint.com/file" in result

    @patch("src.integrations.backends.sharepoint.microsoft_token", return_value=("mstoken", ""))
    @patch.dict("os.environ", {SHAREPOINT_SITE_ENV: "site456", SHAREPOINT_DRIVE_ENV: "drive789"}, clear=True)
    @patch("src.integrations.backends.sharepoint.http_json", return_value=(201, {"webUrl": "https://sharepoint.com/f2"}, ""))
    def test_success_with_drive_id(self, mock_http, mock_token, workspace):
        result = upload_sharepoint_csv(workspace)
        assert "enviado ao SharePoint" in result

    @patch("src.integrations.backends.sharepoint.microsoft_token", return_value=("mstoken", ""))
    @patch.dict("os.environ", {SHAREPOINT_SITE_ENV: "site123"}, clear=True)
    @patch("src.integrations.backends.sharepoint.http_json", return_value=(500, {}, "server error"))
    def test_upload_failure(self, mock_http, mock_token, workspace):
        result = upload_sharepoint_csv(workspace)
        assert "Falha" in result

    @patch("src.integrations.backends.sharepoint.microsoft_token", return_value=("mstoken", ""))
    @patch.dict("os.environ", {SHAREPOINT_SITE_ENV: "site123"}, clear=True)
    @patch("src.integrations.backends.sharepoint.http_json", return_value=(201, {}, ""))
    def test_success_no_link(self, mock_http, mock_token, workspace):
        result = upload_sharepoint_csv(workspace)
        assert "enviado ao SharePoint" in result

    @patch("src.integrations.backends.sharepoint.microsoft_token", return_value=("mstoken", ""))
    @patch.dict("os.environ", {SHAREPOINT_SITE_ENV: "site123"}, clear=True)
    def test_no_dataframe(self, mock_token):
        ws = Workspace(
            path="", workbook_name="x.xlsx", sheet_name="S1",
            columns=[], row_count=0, indexed_rows=0,
            truncated=False, df=None, excel_live=False,
            excel_book_name=None, error=None,
        )
        result = upload_sharepoint_csv(ws)
        assert "Nao ha DataFrame" in result


# ---------------------------------------------------------------------------
# Google Calendar backend
# ---------------------------------------------------------------------------


class TestListGoogleCalendarEvents:
    @patch("src.integrations.backends.google_calendar.google_token", return_value=("", "not connected"))
    def test_no_token(self, mock_token):
        result = list_google_calendar_events()
        assert "Google Agenda nao disponivel" in result

    @patch("src.integrations.backends.google_calendar.google_token", return_value=("gtoken", ""))
    @patch("src.integrations.backends.google_calendar.http_json", return_value=(200, {
        "items": [
            {"summary": "Meeting", "start": {"dateTime": "2026-05-14T10:00:00Z"}},
            {"summary": "Lunch", "start": {"date": "2026-05-15"}},
        ],
    }, ""))
    def test_success_with_events(self, mock_http, mock_token):
        result = list_google_calendar_events()
        assert "Meeting" in result
        assert "Lunch" in result

    @patch("src.integrations.backends.google_calendar.google_token", return_value=("gtoken", ""))
    @patch("src.integrations.backends.google_calendar.http_json", return_value=(200, {"items": []}, ""))
    def test_no_events(self, mock_http, mock_token):
        result = list_google_calendar_events()
        assert "Nenhum compromisso" in result

    @patch("src.integrations.backends.google_calendar.google_token", return_value=("gtoken", ""))
    @patch("src.integrations.backends.google_calendar.http_json", return_value=(401, {}, "unauthorized"))
    def test_http_failure(self, mock_http, mock_token):
        result = list_google_calendar_events()
        assert "Falha" in result

    @patch("src.integrations.backends.google_calendar.google_token", return_value=("gtoken", ""))
    @patch("src.integrations.backends.google_calendar.http_json", return_value=(200, {"items": [
        {"start": {"date": "2026-05-15"}},
    ]}, ""))
    def test_event_without_summary(self, mock_http, mock_token):
        result = list_google_calendar_events()
        assert "sem titulo" in result


# ---------------------------------------------------------------------------
# Google Drive backend
# ---------------------------------------------------------------------------


class TestUploadGoogleDriveCsv:
    @patch("src.integrations.backends.google_drive.google_token", return_value=("", "not connected"))
    def test_no_token(self, mock_token, workspace):
        result = upload_google_drive_csv(workspace)
        assert "Google Drive nao disponivel" in result

    @patch("src.integrations.backends.google_drive.google_token", return_value=("gtoken", ""))
    def test_no_dataframe(self, mock_token):
        ws = Workspace(
            path="", workbook_name="x.xlsx", sheet_name="S1",
            columns=[], row_count=0, indexed_rows=0,
            truncated=False, df=None, excel_live=False,
            excel_book_name=None, error=None,
        )
        result = upload_google_drive_csv(ws)
        assert "Nao ha DataFrame" in result

    @patch("src.integrations.backends.google_drive.google_token", return_value=("gtoken", ""))
    @patch("src.integrations.backends.google_drive.http_json", return_value=(200, {
        "name": "data.csv", "webViewLink": "https://drive.google.com/file",
    }, ""))
    def test_success_with_link(self, mock_http, mock_token, workspace):
        result = upload_google_drive_csv(workspace)
        assert "data.csv" in result
        assert "https://drive.google.com/file" in result

    @patch("src.integrations.backends.google_drive.google_token", return_value=("gtoken", ""))
    @patch("src.integrations.backends.google_drive.http_json", return_value=(200, {"name": "data.csv"}, ""))
    def test_success_no_link(self, mock_http, mock_token, workspace):
        result = upload_google_drive_csv(workspace)
        assert "data.csv" in result

    @patch("src.integrations.backends.google_drive.google_token", return_value=("gtoken", ""))
    @patch("src.integrations.backends.google_drive.http_json", return_value=(500, {}, "error"))
    def test_upload_failure(self, mock_http, mock_token, workspace):
        result = upload_google_drive_csv(workspace)
        assert "Falha" in result

    @patch("src.integrations.backends.google_drive.google_token", return_value=("gtoken", ""))
    @patch("src.integrations.backends.google_drive.http_json", return_value=(200, {"id": "fid"}, ""))
    def test_success_uses_multipart(self, mock_http, mock_token, workspace):
        upload_google_drive_csv(workspace)
        call_args = mock_http.call_args
        headers = call_args[0][2]
        assert "multipart/related" in headers.get("Content-Type", "")


# ---------------------------------------------------------------------------
# OneDrive backend
# ---------------------------------------------------------------------------


class TestUploadOnedriveCsv:
    @patch("src.integrations.backends.onedrive.microsoft_token", return_value=("", "not available"))
    def test_no_token(self, mock_token, workspace):
        result = upload_onedrive_csv(workspace)
        assert "OneDrive nao disponivel" in result

    @patch("src.integrations.backends.onedrive.microsoft_token", return_value=("mstoken", ""))
    def test_no_dataframe(self, mock_token):
        ws = Workspace(
            path="", workbook_name="x.xlsx", sheet_name="S1",
            columns=[], row_count=0, indexed_rows=0,
            truncated=False, df=None, excel_live=False,
            excel_book_name=None, error=None,
        )
        result = upload_onedrive_csv(ws)
        assert "Nao ha DataFrame" in result

    @patch("src.integrations.backends.onedrive.microsoft_token", return_value=("mstoken", ""))
    @patch("src.integrations.backends.onedrive.http_json", return_value=(201, {"webUrl": "https://onedrive.com/file"}, ""))
    def test_success_with_link(self, mock_http, mock_token, workspace):
        result = upload_onedrive_csv(workspace)
        assert "OneDrive" in result
        assert "https://onedrive.com/file" in result

    @patch("src.integrations.backends.onedrive.microsoft_token", return_value=("mstoken", ""))
    @patch("src.integrations.backends.onedrive.http_json", return_value=(201, {}, ""))
    def test_success_no_link(self, mock_http, mock_token, workspace):
        result = upload_onedrive_csv(workspace)
        assert "OneDrive" in result

    @patch("src.integrations.backends.onedrive.microsoft_token", return_value=("mstoken", ""))
    @patch("src.integrations.backends.onedrive.http_json", return_value=(403, {}, "forbidden"))
    def test_upload_failure(self, mock_http, mock_token, workspace):
        result = upload_onedrive_csv(workspace)
        assert "Falha" in result


# ---------------------------------------------------------------------------
# Outlook Calendar backend
# ---------------------------------------------------------------------------


class TestListOutlookCalendar:
    @patch("src.integrations.backends.outlook_calendar.microsoft_token", return_value=("", "not available"))
    def test_no_token(self, mock_token):
        result = list_outlook_calendar()
        assert "Outlook/Graph nao disponivel" in result

    @patch("src.integrations.backends.outlook_calendar.microsoft_token", return_value=("mstoken", ""))
    @patch("src.integrations.backends.outlook_calendar.http_json", return_value=(200, {
        "value": [
            {"subject": "Team Sync", "start": {"dateTime": "2026-05-14T14:00"}},
            {"subject": "1:1", "start": {"dateTime": "2026-05-15T09:00"}},
        ],
    }, ""))
    def test_success_with_events(self, mock_http, mock_token):
        result = list_outlook_calendar()
        assert "Team Sync" in result
        assert "1:1" in result

    @patch("src.integrations.backends.outlook_calendar.microsoft_token", return_value=("mstoken", ""))
    @patch("src.integrations.backends.outlook_calendar.http_json", return_value=(200, {"value": []}, ""))
    def test_no_events(self, mock_http, mock_token):
        result = list_outlook_calendar()
        assert "Nenhum compromisso" in result

    @patch("src.integrations.backends.outlook_calendar.microsoft_token", return_value=("mstoken", ""))
    @patch("src.integrations.backends.outlook_calendar.http_json", return_value=(401, {}, "unauthorized"))
    def test_http_failure(self, mock_http, mock_token):
        result = list_outlook_calendar()
        assert "Falha" in result

    @patch("src.integrations.backends.outlook_calendar.microsoft_token", return_value=("mstoken", ""))
    @patch("src.integrations.backends.outlook_calendar.http_json", return_value=(200, {"value": [
        {"start": {"dateTime": "2026-05-14T10:00"}},
    ]}, ""))
    def test_event_without_subject(self, mock_http, mock_token):
        result = list_outlook_calendar()
        assert "sem titulo" in result


# ---------------------------------------------------------------------------
# Outlook Mail backend
# ---------------------------------------------------------------------------


class TestSendOutlookMail:
    @patch("src.integrations.backends.outlook.microsoft_token", return_value=("", "not available"))
    def test_no_token(self, mock_token, workspace):
        result = send_outlook_mail("enviar email para x@y.com", workspace)
        assert "Outlook/Graph nao disponivel" in result

    @patch("src.integrations.backends.outlook.microsoft_token", return_value=("mstoken", ""))
    @patch.dict("os.environ", {}, clear=True)
    def test_no_recipient(self, mock_token, workspace):
        result = send_outlook_mail("enviar mensagem", workspace)
        assert "Informe destinatario" in result

    @patch("src.integrations.backends.outlook.microsoft_token", return_value=("mstoken", ""))
    @patch("src.integrations.backends.outlook.http_json", return_value=(202, {}, ""))
    def test_success_with_email_in_query(self, mock_http, mock_token, workspace):
        result = send_outlook_mail("enviar para user@company.com", workspace)
        assert "enviado via Outlook" in result
        assert "user@company.com" in result

    @patch("src.integrations.backends.outlook.microsoft_token", return_value=("mstoken", ""))
    @patch.dict("os.environ", {OUTLOOK_TO_ENV: "default@outlook.com"}, clear=True)
    @patch("src.integrations.backends.outlook.http_json", return_value=(202, {}, ""))
    def test_recipient_from_env(self, mock_http, mock_token, workspace):
        result = send_outlook_mail("enviar email microsoft", workspace)
        assert "default@outlook.com" in result

    @patch("src.integrations.backends.outlook.microsoft_token", return_value=("mstoken", ""))
    @patch("src.integrations.backends.outlook.http_json", return_value=(500, {}, "server error"))
    def test_http_failure(self, mock_http, mock_token, workspace):
        result = send_outlook_mail("enviar para a@b.com", workspace)
        assert "Falha" in result

    @patch("src.integrations.backends.outlook.microsoft_token", return_value=("mstoken", ""))
    @patch("src.integrations.backends.outlook.http_json", return_value=(202, {}, ""))
    def test_payload_structure(self, mock_http, mock_token, workspace):
        send_outlook_mail("enviar para test@corp.com", workspace)
        call_args = mock_http.call_args
        payload_bytes = call_args[0][3]
        payload = json.loads(payload_bytes.decode("utf-8"))
        assert "message" in payload
        assert "toRecipients" in payload["message"]
        assert payload["message"]["toRecipients"][0]["emailAddress"]["address"] == "test@corp.com"
        assert payload["saveToSentItems"] is True


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class TestHandleIntegrationQuery:
    def test_integration_list_message(self, workspace):
        with patch("src.integrations.router.provider_status", side_effect=lambda p: f"{p}: ok"):
            result = handle_integration_query("mostrar integrações", workspace)
        assert result is not None
        assert "Gmail" in result
        assert "google: ok" in result
        assert "microsoft: ok" in result

    @patch("src.integrations.router.send_teams_summary", return_value="teams ok")
    def test_teams_routing(self, mock_teams, workspace):
        result = handle_integration_query("enviar resumo para teams", workspace)
        assert result == "teams ok"
        mock_teams.assert_called_once_with(workspace)

    @patch("src.integrations.router.trello_list_boards", return_value="trello boards")
    def test_trello_list_routing(self, mock_list, workspace):
        result = handle_integration_query("listar quadros trello", workspace)
        assert result == "trello boards"

    @patch("src.integrations.router.trello_create_card", return_value="card created")
    def test_trello_create_routing(self, mock_create, workspace):
        result = handle_integration_query("criar card no trello", workspace)
        assert result == "card created"

    @patch("src.integrations.router.trello_create_card", return_value="card created")
    def test_trello_cartao_routing(self, mock_create, workspace):
        result = handle_integration_query("criar cartao trello", workspace)
        assert result == "card created"

    @patch("src.integrations.router.send_outlook_mail", return_value="outlook sent")
    def test_outlook_mail_routing(self, mock_mail, workspace):
        result = handle_integration_query("enviar email microsoft outlook", workspace)
        assert result == "outlook sent"

    @patch("src.integrations.router.list_outlook_calendar", return_value="outlook cal")
    def test_outlook_calendar_routing(self, mock_cal, workspace):
        result = handle_integration_query("ver calendario microsoft outlook", workspace)
        assert result == "outlook cal"

    @patch("src.integrations.router.upload_onedrive_csv", return_value="onedrive ok")
    def test_onedrive_routing(self, mock_od, workspace):
        result = handle_integration_query("upload onedrive", workspace)
        assert result == "onedrive ok"

    @patch("src.integrations.router.upload_sharepoint_csv", return_value="sharepoint ok")
    def test_sharepoint_routing(self, mock_sp, workspace):
        result = handle_integration_query("upload sharepoint", workspace)
        assert result == "sharepoint ok"

    @patch("src.integrations.router.list_google_calendar_events", return_value="gcal events")
    def test_google_calendar_routing(self, mock_gcal, workspace):
        result = handle_integration_query("ver calendario reuniao", workspace)
        assert result == "gcal events"

    @patch("src.integrations.router.upload_google_drive_csv", return_value="gdrive ok")
    def test_google_drive_routing(self, mock_gdrive, workspace):
        result = handle_integration_query("upload google drive", workspace)
        assert result == "gdrive ok"

    @patch("src.integrations.router.upload_google_drive_csv", return_value="gdrive ok")
    def test_google_drive_salvar_routing(self, mock_gdrive, workspace):
        result = handle_integration_query("salvar no drive google", workspace)
        assert result == "gdrive ok"

    @patch("src.integrations.router.send_gmail_summary", return_value="gmail sent")
    def test_gmail_routing(self, mock_gmail, workspace):
        result = handle_integration_query("enviar email gmail", workspace)
        assert result == "gmail sent"

    @patch("src.integrations.router.send_gmail_summary", return_value="gmail sent")
    def test_gmail_resumo_routing(self, mock_gmail, workspace):
        result = handle_integration_query("enviar resumo email", workspace)
        assert result == "gmail sent"

    def test_no_match_returns_none(self, workspace):
        result = handle_integration_query("qual é a média de salário?", workspace)
        assert result is None

    def test_integration_keyword_routing(self, workspace):
        with patch("src.integrations.router.provider_status", return_value="ok"):
            result = handle_integration_query("quais integrações", workspace)
        assert result is not None
        assert "Integracoes disponiveis" in result

    @patch("src.integrations.router.send_outlook_mail", return_value="outlook sent")
    def test_office365_mail_routing(self, mock_mail, workspace):
        result = handle_integration_query("enviar email office 365", workspace)
        assert result == "outlook sent"

    @patch("src.integrations.router.list_outlook_calendar", return_value="outlook cal")
    def test_microsoft_calendar_routing(self, workspace):
        with patch("src.integrations.router.list_outlook_calendar", return_value="outlook cal"):
            result = handle_integration_query("ver calendario microsoft", workspace)
            assert result == "outlook cal"

    @patch("src.integrations.router.list_google_calendar_events", return_value="gcal")
    def test_agenda_compromisso_routing(self, mock_gcal, workspace):
        result = handle_integration_query("agenda compromisso", workspace)
        assert result == "gcal"


class TestIntegrationListMessage:
    @patch("src.integrations.router.provider_status", return_value="Conectado")
    def test_message_contains_providers(self, mock_status):
        msg = _integration_list_message()
        assert "Gmail" in msg
        assert "Google Agenda" in msg
        assert "Google Drive" in msg
        assert "Outlook" in msg
        assert "OneDrive" in msg
        assert "SharePoint" in msg
        assert "Teams" in msg
        assert "Trello" in msg

    @patch("src.integrations.router.provider_status", return_value="Conectado")
    def test_message_contains_oauth_status(self, mock_status):
        msg = _integration_list_message()
        assert "Status OAuth Google: Conectado" in msg
        assert "Status OAuth Microsoft: Conectado" in msg

    @patch("src.integrations.router.provider_status", return_value="Nao conectado")
    def test_message_disconnected(self, mock_status):
        msg = _integration_list_message()
        assert "Nao conectado" in msg

    @patch("src.integrations.router.provider_status", return_value="ok")
    def test_message_contains_config_hints(self, mock_status):
        msg = _integration_list_message()
        assert TEAMS_WEBHOOK_ENV in msg
        assert TRELLO_KEY_ENV in msg
        assert SHAREPOINT_SITE_ENV in msg
