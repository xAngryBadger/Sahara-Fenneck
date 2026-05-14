"""Unit tests for oauth — PKCE, HTTP form post, browser open, callback server,
connect/refresh/get_access/disconnect/status — all mocked, no real network."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import threading
import time
import urllib.parse
from http.server import HTTPServer
from io import BytesIO
from unittest.mock import MagicMock, patch

from src.integrations.oauth import (
    _http_form_post,
    _new_pkce,
    _open_auth_url,
    _refresh_provider_token,
    _start_callback_server,
    connect_provider,
    disconnect_provider,
    get_access_token,
    provider_status,
)


# ---------------------------------------------------------------------------
# _new_pkce
# ---------------------------------------------------------------------------
class TestNewPkce:
    def test_returns_two_strings(self):
        verifier, challenge = _new_pkce()
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)
        assert len(verifier) > 0
        assert len(challenge) > 0

    def test_base64url_safe_chars(self):
        verifier, challenge = _new_pkce()
        allowed = re.compile(r'^[A-Za-z0-9_-]+$')
        assert allowed.match(verifier), f"verifier has invalid chars: {verifier!r}"
        assert allowed.match(challenge), f"challenge has invalid chars: {challenge!r}"

    def test_no_padding(self):
        verifier, challenge = _new_pkce()
        assert "=" not in verifier
        assert "=" not in challenge

    def test_challenge_is_sha256_of_verifier(self):
        verifier, challenge = _new_pkce()
        expected_digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected_challenge = base64.urlsafe_b64encode(expected_digest).decode("ascii").rstrip("=")
        assert challenge == expected_challenge

    def test_unique_per_call(self):
        v1, _ = _new_pkce()
        v2, _ = _new_pkce()
        assert v1 != v2

    def test_verifier_length(self):
        verifier, _ = _new_pkce()
        raw = base64.urlsafe_b64decode(verifier + "==")
        assert len(raw) == 48


# ---------------------------------------------------------------------------
# _http_form_post
# ---------------------------------------------------------------------------
class TestHttpFormPost:
    @patch("src.integrations.oauth.urllib.request.urlopen")
    def test_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"access_token": "abc", "expires_in": 3600}).encode()
        mock_urlopen.return_value = mock_resp

        status, data, err = _http_form_post("https://example.com/token", {"grant_type": "code"})
        assert status == 200
        assert data["access_token"] == "abc"
        assert err == ""

    @patch("src.integrations.oauth.urllib.request.urlopen")
    def test_empty_body(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 200
        mock_resp.read.return_value = b""
        mock_urlopen.return_value = mock_resp

        status, data, err = _http_form_post("https://example.com/token", {})
        assert status == 200
        assert data == {}
        assert err == ""

    @patch("src.integrations.oauth.urllib.request.urlopen")
    def test_non_dict_json_body(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 200
        mock_resp.read.return_value = b'"just a string"'
        mock_urlopen.return_value = mock_resp

        status, data, err = _http_form_post("https://example.com/token", {})
        assert status == 200
        assert "raw" in data
        assert data["raw"] == "just a string"

    @patch("src.integrations.oauth.urllib.request.urlopen")
    def test_http_error_with_body(self, mock_urlopen):
        error = urllib.error.HTTPError(
            "https://example.com/token", 400, "Bad Request", {}, BytesIO(b'{"error":"invalid_grant"}')
        )
        mock_urlopen.side_effect = error

        status, data, err = _http_form_post("https://example.com/token", {"code": "bad"})
        assert status == 400
        assert data == {}
        assert "invalid_grant" in err

    @patch("src.integrations.oauth.urllib.request.urlopen")
    def test_http_error_without_read(self, mock_urlopen):
        error = Exception("connection reset")
        mock_urlopen.side_effect = error

        status, data, err = _http_form_post("https://example.com/token", {})
        assert status == 500
        assert data == {}
        assert "connection reset" in err

    @patch("src.integrations.oauth.urllib.request.urlopen")
    def test_posts_encoded_form_data(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 200
        mock_resp.read.return_value = b"{}"
        mock_urlopen.return_value = mock_resp

        _http_form_post("https://example.com/token", {"key": "val", "foo": "bar"})
        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Content-type") == "application/x-www-form-urlencoded"
        sent = req.data.decode("utf-8")
        assert "key=val" in sent
        assert "foo=bar" in sent

    @patch("src.integrations.oauth.urllib.request.urlopen")
    def test_error_code_attribute(self, mock_urlopen):
        class FakeErr(Exception):
            code = 403

            def read(self):
                return b"forbidden"

        mock_urlopen.side_effect = FakeErr()

        status, data, err = _http_form_post("https://example.com/token", {})
        assert status == 403
        assert err == "forbidden"


# ---------------------------------------------------------------------------
# _open_auth_url
# ---------------------------------------------------------------------------
class TestOpenAuthUrl:
    @patch("src.integrations.oauth.webbrowser.open", return_value=True)
    def test_webbrowser_success(self, mock_wb):
        ok, err = _open_auth_url("https://example.com/auth")
        assert ok is True
        assert err == ""
        mock_wb.assert_called_once_with("https://example.com/auth", new=2, autoraise=True)

    @patch("src.integrations.oauth.webbrowser.open", side_effect=Exception("no browser"))
    @patch("src.integrations.oauth.shutil.which", return_value=None)
    @patch("src.integrations.oauth.subprocess.Popen", side_effect=Exception("no powershell"))
    def test_all_fail(self, mock_popen, mock_which, mock_wb, monkeypatch):
        monkeypatch.setattr("src.integrations.oauth.os.name", "posix")
        ok, err = _open_auth_url("https://example.com/auth")
        assert ok is False
        assert err != ""

    @patch("src.integrations.oauth.webbrowser.open", side_effect=Exception("wb fail"))
    def test_windows_startfile_fallback(self, mock_wb, monkeypatch):
        monkeypatch.setattr("src.integrations.oauth.os.name", "nt")
        mock_startfile = MagicMock(return_value=None)
        monkeypatch.setattr("src.integrations.oauth.os.startfile", mock_startfile, raising=False)
        ok, err = _open_auth_url("https://example.com/auth")
        assert ok is True
        mock_startfile.assert_called_once_with("https://example.com/auth")

    @patch("src.integrations.oauth.webbrowser.open", side_effect=Exception("wb fail"))
    def test_windows_powershell_fallback(self, mock_wb, monkeypatch):
        monkeypatch.setattr("src.integrations.oauth.os.name", "nt")
        monkeypatch.setattr("src.integrations.oauth.os.startfile", MagicMock(side_effect=Exception("no startfile")), raising=False)
        with patch("src.integrations.oauth.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            ok, err = _open_auth_url("https://example.com/auth")
            assert ok is True
            mock_popen.assert_called_once()

    @patch("src.integrations.oauth.webbrowser.open", side_effect=Exception("wb fail"))
    def test_linux_xdg_open_fallback(self, mock_wb, monkeypatch):
        monkeypatch.setattr("src.integrations.oauth.os.name", "posix")
        with patch("src.integrations.oauth.subprocess.Popen", side_effect=[Exception("ps fail"), MagicMock()]), \
             patch("src.integrations.oauth.shutil.which", return_value="/usr/bin/xdg-open"):
            ok, err = _open_auth_url("https://example.com/auth")
            assert ok is True

    @patch("src.integrations.oauth.webbrowser.open", side_effect=Exception("wb fail"))
    def test_linux_xdg_open_success(self, mock_wb, monkeypatch):
        monkeypatch.setattr("src.integrations.oauth.os.name", "posix")
        with patch("src.integrations.oauth.subprocess.Popen", side_effect=[Exception("ps fail"), MagicMock()]), \
             patch("src.integrations.oauth.shutil.which", return_value="/usr/bin/xdg-open"):
            ok, err = _open_auth_url("https://example.com/auth")
            assert ok is True

    @patch("src.integrations.oauth.webbrowser.open", side_effect=Exception("wb fail"))
    def test_linux_no_opener_found(self, mock_wb, monkeypatch):
        monkeypatch.setattr("src.integrations.oauth.os.name", "posix")
        with patch("src.integrations.oauth.subprocess.Popen", side_effect=Exception("fail")), \
             patch("src.integrations.oauth.shutil.which", return_value=None):
            ok, err = _open_auth_url("https://example.com/auth")
            assert ok is False


# ---------------------------------------------------------------------------
# _start_callback_server
# ---------------------------------------------------------------------------
class TestStartCallbackServer:
    def test_server_starts_and_returns_port(self):
        server, thread, result, port = _start_callback_server("teststate123")
        assert isinstance(server, HTTPServer)
        assert thread.daemon is True
        assert port > 0
        result.event.set()
        server.server_close()

    def test_result_initial_state(self):
        _server, _thread, result, _port = _start_callback_server("mystate")
        assert result.code == ""
        assert result.state == ""
        assert result.error == ""
        assert isinstance(result.event, threading.Event)
        result.event.set()
        _server.server_close()

    def test_callback_with_valid_code(self):
        server, thread, result, port = _start_callback_server("validstate")
        import urllib.request as _ureq

        url = f"http://127.0.0.1:{port}/callback?state=validstate&code=authcode123"
        try:
            resp = _ureq.urlopen(url, timeout=5)
            body = resp.read().decode("utf-8", errors="replace")
            assert resp.status == 200
            assert "sucesso" in body.lower() or "concluida" in body.lower()
        finally:
            result.event.wait(timeout=3)
            server.server_close()

        assert result.code == "authcode123"
        assert result.state == "validstate"
        assert result.error == ""

    def test_callback_with_state_mismatch(self):
        server, thread, result, port = _start_callback_server("expected_state")
        import urllib.request as _ureq

        url = f"http://127.0.0.1:{port}/callback?state=wrong_state&code=somecode"
        try:
            resp = _ureq.urlopen(url, timeout=5)
            assert resp.status == 400
        except Exception:
            pass
        finally:
            result.event.wait(timeout=3)
            server.server_close()

        assert result.error == "state mismatch"

    def test_callback_with_error_param(self):
        server, thread, result, port = _start_callback_server("mystate")
        import urllib.request as _ureq

        url = f"http://127.0.0.1:{port}/callback?state=mystate&error=access_denied"
        try:
            resp = _ureq.urlopen(url, timeout=5)
            assert resp.status == 400
        except Exception:
            pass
        finally:
            result.event.wait(timeout=3)
            server.server_close()

        assert result.error == "access_denied"


# ---------------------------------------------------------------------------
# connect_provider
# ---------------------------------------------------------------------------
class TestConnectProvider:
    @patch("src.integrations.oauth.set_provider_token")
    @patch("src.integrations.oauth._http_form_post")
    @patch("src.integrations.oauth._open_auth_url", return_value=(True, ""))
    @patch("src.integrations.oauth._start_callback_server")
    @patch("src.integrations.oauth._new_pkce", return_value=("verifier", "challenge"))
    @patch("src.integrations.oauth.secrets.token_urlsafe", return_value="fakestate")
    def test_success_google(self, mock_state, mock_pkce, mock_server, mock_open, mock_post, mock_set):
        result = MagicMock()
        result.code = "authcode"
        result.state = "fakestate"
        result.error = ""
        result.event = MagicMock()
        result.event.wait.return_value = True
        result.event.is_set.return_value = True
        mock_server.return_value = (MagicMock(), MagicMock(), result, 54321)

        mock_post.return_value = (200, {
            "access_token": "goog_access",
            "refresh_token": "goog_refresh",
            "expires_in": 3600,
        }, "")

        out = connect_provider("google", "my-client-id")
        assert "sucesso" in out.lower() or "concluida" in out.lower()
        mock_set.assert_called_once()
        token_arg = mock_set.call_args[0]
        assert token_arg[0] == "google"
        assert token_arg[1]["access_token"] == "goog_access"
        assert token_arg[1]["refresh_token"] == "goog_refresh"

    @patch("src.integrations.oauth.set_provider_token")
    @patch("src.integrations.oauth._http_form_post")
    @patch("src.integrations.oauth._open_auth_url", return_value=(True, ""))
    @patch("src.integrations.oauth._start_callback_server")
    @patch("src.integrations.oauth._new_pkce", return_value=("v", "c"))
    @patch("src.integrations.oauth.secrets.token_urlsafe", return_value="st")
    def test_success_microsoft(self, mock_state, mock_pkce, mock_server, mock_open, mock_post, mock_set):
        result = MagicMock()
        result.code = "mscode"
        result.state = "st"
        result.error = ""
        result.event = MagicMock()
        result.event.wait.return_value = True
        result.event.is_set.return_value = True
        mock_server.return_value = (MagicMock(), MagicMock(), result, 9999)

        mock_post.return_value = (200, {
            "access_token": "ms_access",
            "refresh_token": "ms_refresh",
            "expires_in": 3600,
        }, "")

        out = connect_provider("microsoft", "ms-client-id")
        assert "sucesso" in out.lower() or "concluida" in out.lower()
        mock_set.assert_called_once()
        payload = mock_post.call_args[0][1]
        assert "scope" in payload

    def test_invalid_provider(self):
        out = connect_provider("dropbox", "some-id")
        assert "invalido" in out.lower() or "invalid" in out.lower()

    @patch("src.integrations.oauth.get_default_client_id", return_value="")
    def test_no_client_id(self, mock_defaults):
        out = connect_provider("google", "")
        assert "client id" in out.lower() or "Client ID" in out

    @patch("src.integrations.oauth._start_callback_server")
    @patch("src.integrations.oauth._new_pkce", return_value=("v", "c"))
    @patch("src.integrations.oauth.secrets.token_urlsafe", return_value="st")
    @patch("src.integrations.oauth._open_auth_url", return_value=(False, "no browser"))
    def test_auth_url_open_failure(self, mock_open, mock_state, mock_pkce, mock_server):
        mock_result = MagicMock()
        mock_result.error = ""
        mock_result.event = MagicMock()
        mock_server.return_value = (MagicMock(), MagicMock(), mock_result, 1234)

        out = connect_provider("google", "my-client-id")
        assert "falha" in out.lower() or "manualmente" in out.lower()
        mock_result.event.set.assert_called()

    @patch("src.integrations.oauth._start_callback_server")
    @patch("src.integrations.oauth._new_pkce", return_value=("v", "c"))
    @patch("src.integrations.oauth.secrets.token_urlsafe", return_value="st")
    @patch("src.integrations.oauth._open_auth_url", return_value=(True, ""))
    def test_timeout(self, mock_open, mock_state, mock_pkce, mock_server):
        result = MagicMock()
        result.code = ""
        result.state = ""
        result.error = ""
        result.event = MagicMock()
        result.event.wait.return_value = False
        result.event.is_set.return_value = False
        mock_server.return_value = (MagicMock(), MagicMock(), result, 1234)

        out = connect_provider("google", "my-client-id")
        assert "timeout" in out.lower() or "falha" in out.lower()

    @patch("src.integrations.oauth._http_form_post")
    @patch("src.integrations.oauth._open_auth_url", return_value=(True, ""))
    @patch("src.integrations.oauth._start_callback_server")
    @patch("src.integrations.oauth._new_pkce", return_value=("v", "c"))
    @patch("src.integrations.oauth.secrets.token_urlsafe", return_value="st")
    def test_token_exchange_failure(self, mock_state, mock_pkce, mock_server, mock_open, mock_post):
        result = MagicMock()
        result.code = "somecode"
        result.state = "st"
        result.error = ""
        result.event = MagicMock()
        result.event.wait.return_value = True
        result.event.is_set.return_value = True
        mock_server.return_value = (MagicMock(), MagicMock(), result, 1234)

        mock_post.return_value = (400, {}, "invalid_grant")

        out = connect_provider("google", "my-client-id")
        assert "falha" in out.lower() or "400" in out

    @patch("src.integrations.oauth._http_form_post")
    @patch("src.integrations.oauth._open_auth_url", return_value=(True, ""))
    @patch("src.integrations.oauth._start_callback_server")
    @patch("src.integrations.oauth._new_pkce", return_value=("v", "c"))
    @patch("src.integrations.oauth.secrets.token_urlsafe", return_value="st")
    def test_no_access_token_in_response(self, mock_state, mock_pkce, mock_server, mock_open, mock_post):
        result = MagicMock()
        result.code = "somecode"
        result.state = "st"
        result.error = ""
        result.event = MagicMock()
        result.event.wait.return_value = True
        result.event.is_set.return_value = True
        mock_server.return_value = (MagicMock(), MagicMock(), result, 1234)

        mock_post.return_value = (200, {"refresh_token": "rf", "expires_in": 3600}, "")

        out = connect_provider("google", "my-client-id")
        assert "access_token" in out.lower() or "nao retornou" in out.lower()

    @patch("src.integrations.oauth._start_callback_server")
    @patch("src.integrations.oauth._new_pkce", return_value=("v", "c"))
    @patch("src.integrations.oauth.secrets.token_urlsafe", return_value="st")
    @patch("src.integrations.oauth._open_auth_url", return_value=(True, ""))
    def test_callback_error(self, mock_open, mock_state, mock_pkce, mock_server):
        result = MagicMock()
        result.code = ""
        result.state = ""
        result.error = "access_denied"
        result.event = MagicMock()
        result.event.wait.return_value = True
        result.event.is_set.return_value = True
        mock_server.return_value = (MagicMock(), MagicMock(), result, 1234)

        out = connect_provider("google", "my-client-id")
        assert "falha" in out.lower() or "access_denied" in out

    @patch("src.integrations.oauth.set_provider_token")
    @patch("src.integrations.oauth._http_form_post")
    @patch("src.integrations.oauth._open_auth_url", return_value=(True, ""))
    @patch("src.integrations.oauth._start_callback_server")
    @patch("src.integrations.oauth._new_pkce", return_value=("v", "c"))
    @patch("src.integrations.oauth.secrets.token_urlsafe", return_value="st")
    def test_provider_stripped_and_lowered(self, mock_state, mock_pkce, mock_server, mock_open, mock_post, mock_set):
        result = MagicMock()
        result.code = "code1"
        result.state = "st"
        result.error = ""
        result.event = MagicMock()
        result.event.wait.return_value = True
        result.event.is_set.return_value = True
        mock_server.return_value = (MagicMock(), MagicMock(), result, 1234)

        mock_post.return_value = (200, {"access_token": "a", "refresh_token": "r", "expires_in": 3600}, "")

        out = connect_provider("  GOOGLE  ", "cid")
        assert "sucesso" in out.lower() or "concluida" in out.lower()
        assert mock_set.call_args[0][0] == "google"


# ---------------------------------------------------------------------------
# _refresh_provider_token
# ---------------------------------------------------------------------------
class TestRefreshProviderToken:
    @patch("src.integrations.oauth.set_provider_token")
    @patch("src.integrations.oauth._http_form_post")
    def test_successful_refresh(self, mock_post, mock_set):
        mock_post.return_value = (200, {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_in": 3600,
        }, "")

        token_data = {"refresh_token": "old_refresh", "access_token": "old_access"}
        ok, err = _refresh_provider_token("google", token_data, "my-client-id")
        assert ok is True
        assert err == ""
        mock_set.assert_called_once()
        assert token_data["access_token"] == "new_access"

    @patch("src.integrations.oauth.set_provider_token")
    @patch("src.integrations.oauth._http_form_post")
    def test_refresh_keeps_old_refresh_if_none_returned(self, mock_post, mock_set):
        mock_post.return_value = (200, {
            "access_token": "new_access",
            "expires_in": 3600,
        }, "")

        token_data = {"refresh_token": "old_refresh", "access_token": "old"}
        ok, err = _refresh_provider_token("google", token_data, "cid")
        assert ok is True
        assert token_data["refresh_token"] == "old_refresh"

    def test_invalid_provider(self):
        ok, err = _refresh_provider_token("slack", {}, "cid")
        assert ok is False
        assert "invalido" in err.lower() or "invalid" in err.lower()

    def test_missing_refresh_token(self):
        ok, err = _refresh_provider_token("google", {}, "cid")
        assert ok is False
        assert "refresh" in err.lower()

    @patch("src.integrations.oauth._http_form_post")
    def test_http_failure(self, mock_post):
        mock_post.return_value = (401, {}, "unauthorized")
        ok, err = _refresh_provider_token("google", {"refresh_token": "rt"}, "cid")
        assert ok is False
        assert "401" in err or "unauthorized" in err.lower()

    @patch("src.integrations.oauth._http_form_post")
    def test_refresh_no_access_token_in_response(self, mock_post):
        mock_post.return_value = (200, {"expires_in": 3600}, "")
        ok, err = _refresh_provider_token("google", {"refresh_token": "rt"}, "cid")
        assert ok is False
        assert "access token" in err.lower()

    @patch("src.integrations.oauth.set_provider_token")
    @patch("src.integrations.oauth._http_form_post")
    def test_microsoft_includes_scope(self, mock_post, mock_set):
        mock_post.return_value = (200, {
            "access_token": "ms_new",
            "refresh_token": "ms_ref",
            "expires_in": 3600,
        }, "")

        _refresh_provider_token("microsoft", {"refresh_token": "rt"}, "cid")
        payload = mock_post.call_args[0][1]
        assert "scope" in payload


# ---------------------------------------------------------------------------
# get_access_token
# ---------------------------------------------------------------------------
class TestGetAccessToken:
    @patch("src.integrations.oauth.get_provider_token")
    def test_valid_cached_token(self, mock_get):
        mock_get.return_value = {
            "access_token": "cached_tok",
            "expires_at": int(time.time()) + 3600,
            "client_id": "cid",
        }

        token, err = get_access_token("google", "cid")
        assert token == "cached_tok"
        assert err == ""

    @patch("src.integrations.oauth.get_provider_token")
    def test_no_token_data(self, mock_get):
        mock_get.return_value = None
        token, err = get_access_token("google", "cid")
        assert token == ""
        assert "nao conectado" in err.lower() or "conecte" in err.lower()

    @patch("src.integrations.oauth.get_provider_token")
    def test_client_id_mismatch(self, mock_get):
        mock_get.return_value = {
            "access_token": "tok",
            "expires_at": int(time.time()) + 3600,
            "client_id": "old-client-id",
        }
        token, err = get_access_token("google", "new-client-id")
        assert token == ""
        assert "client id" in err.lower() or "mudou" in err.lower()

    @patch("src.integrations.oauth._refresh_provider_token")
    @patch("src.integrations.oauth.get_provider_token")
    def test_expired_token_refresh_success(self, mock_get, mock_refresh):
        expired_time = int(time.time()) - 100
        mock_get.side_effect = [
            {
                "access_token": "old_tok",
                "expires_at": expired_time,
                "client_id": "cid",
                "refresh_token": "rt",
            },
            {
                "access_token": "refreshed_tok",
                "expires_at": int(time.time()) + 3600,
            },
        ]
        mock_refresh.return_value = (True, "")

        token, err = get_access_token("google", "cid")
        assert token == "refreshed_tok"
        assert err == ""

    @patch("src.integrations.oauth._refresh_provider_token")
    @patch("src.integrations.oauth.get_provider_token")
    def test_expired_token_refresh_failure(self, mock_get, mock_refresh):
        mock_get.return_value = {
            "access_token": "old_tok",
            "expires_at": int(time.time()) - 100,
            "client_id": "cid",
            "refresh_token": "rt",
        }
        mock_refresh.return_value = (False, "refresh failed")

        token, err = get_access_token("google", "cid")
        assert token == ""
        assert "refresh failed" in err.lower() or "falha" in err.lower()

    @patch("src.integrations.oauth.get_provider_token")
    def test_empty_client_id_skips_mismatch_check(self, mock_get):
        mock_get.return_value = {
            "access_token": "tok",
            "expires_at": int(time.time()) + 3600,
            "client_id": "stored-cid",
        }
        token, err = get_access_token("google", "")
        assert token == "tok"
        assert err == ""

    @patch("src.integrations.oauth.get_provider_token")
    def test_provider_name_normalized(self, mock_get):
        mock_get.return_value = None
        token, err = get_access_token("  GOOGLE  ", "cid")
        mock_get.assert_called_with("google")


# ---------------------------------------------------------------------------
# disconnect_provider
# ---------------------------------------------------------------------------
class TestDisconnectProvider:
    @patch("src.integrations.oauth.clear_provider_token")
    def test_disconnect(self, mock_clear):
        out = disconnect_provider("google")
        mock_clear.assert_called_once_with("google")
        assert "removida" in out.lower()

    @patch("src.integrations.oauth.clear_provider_token")
    def test_strips_and_lowers(self, mock_clear):
        disconnect_provider("  MICROSOFT  ")
        mock_clear.assert_called_once_with("microsoft")


# ---------------------------------------------------------------------------
# provider_status
# ---------------------------------------------------------------------------
class TestProviderStatus:
    @patch("src.integrations.oauth.get_provider_token")
    def test_not_connected(self, mock_get):
        mock_get.return_value = None
        status = provider_status("google")
        assert "nao conectado" in status.lower() or "not connected" in status.lower()

    @patch("src.integrations.oauth.get_provider_token")
    def test_expired_token(self, mock_get):
        mock_get.return_value = {
            "expires_at": int(time.time()) - 100,
        }
        status = provider_status("google")
        assert "expirado" in status.lower()

    @patch("src.integrations.oauth.get_provider_token")
    def test_valid_token(self, mock_get):
        mock_get.return_value = {
            "expires_at": int(time.time()) + 600,
        }
        status = provider_status("google")
        assert "conectado" in status.lower()
        assert "min" in status.lower()

    @patch("src.integrations.oauth.get_provider_token")
    def test_provider_name_normalized(self, mock_get):
        mock_get.return_value = None
        provider_status("  GOOGLE  ")
        mock_get.assert_called_once_with("google")

    @patch("src.integrations.oauth.get_provider_token")
    def test_zero_expires_at(self, mock_get):
        mock_get.return_value = {
            "expires_at": 0,
        }
        status = provider_status("google")
        assert "expirado" in status.lower()
