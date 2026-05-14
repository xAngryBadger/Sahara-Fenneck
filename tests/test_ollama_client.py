"""Tests for OllamaClient and module-level helpers (all mocked — no real Ollama)."""
from __future__ import annotations

import json
import subprocess
import threading
from unittest.mock import MagicMock, patch

import pytest
from src.agent.ollama_client import (
    OLLAMA_BASE,
    OllamaClient,
    _check_ollama,
    _cleanup_ollama,
    _find_ollama_exe,
    _list_local_models,
    _pull_model_if_missing,
    _resolve_model,
    _start_ollama_if_possible,
)


def _mock_response(status: int = 200, body: bytes = b"{}"):
    r = MagicMock()
    r.status = status
    r.read.return_value = body
    r.__enter__ = lambda s: s
    r.__exit__ = MagicMock(return_value=False)
    return r


class TestCheckOllama:
    @patch("src.agent.ollama_client.urllib.request.urlopen")
    def test_returns_true_when_200(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(200)
        assert _check_ollama() is True

    @patch("src.agent.ollama_client.urllib.request.urlopen")
    def test_returns_false_when_non_200(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(503)
        assert _check_ollama() is False

    @patch("src.agent.ollama_client.urllib.request.urlopen", side_effect=Exception("connect fail"))
    def test_returns_false_on_exception(self, mock_urlopen):
        assert _check_ollama() is False

    @patch("src.agent.ollama_client.urllib.request.urlopen", side_effect=TimeoutError("timed out"))
    def test_returns_false_on_timeout(self, mock_urlopen):
        assert _check_ollama() is False


class TestFindOllamaExe:
    @patch("src.agent.ollama_client.shutil.which", return_value="/usr/bin/ollama")
    def test_found_via_which(self, mock_which):
        assert _find_ollama_exe() == "/usr/bin/ollama"

    @patch("src.agent.ollama_client.shutil.which", return_value=None)
    @patch("src.agent.ollama_client.os.path.exists", return_value=True)
    @patch.dict("src.agent.ollama_client.os.environ", {"LOCALAPPDATA": "/local", "ProgramFiles": ""})
    def test_found_via_localappdata(self, mock_exists, mock_which):
        result = _find_ollama_exe()
        assert result is not None
        assert "ollama.exe" in result

    @patch("src.agent.ollama_client.shutil.which", return_value=None)
    @patch("src.agent.ollama_client.os.path.exists", side_effect=[False, True])
    @patch.dict("src.agent.ollama_client.os.environ", {"LOCALAPPDATA": "", "ProgramFiles": "/pf"})
    def test_found_via_programfiles(self, mock_exists, mock_which):
        result = _find_ollama_exe()
        assert result is not None
        assert "ollama.exe" in result

    @patch("src.agent.ollama_client.shutil.which", return_value=None)
    @patch("src.agent.ollama_client.os.path.exists", return_value=False)
    @patch.dict("src.agent.ollama_client.os.environ", {"LOCALAPPDATA": "", "ProgramFiles": ""})
    def test_returns_none_when_not_found(self, mock_exists, mock_which):
        assert _find_ollama_exe() is None

    @patch("src.agent.ollama_client.shutil.which", return_value=None)
    @patch("src.agent.ollama_client.os.path.exists", return_value=False)
    @patch.dict("src.agent.ollama_client.os.environ", {}, clear=True)
    def test_returns_none_when_env_missing(self, mock_exists, mock_which):
        assert _find_ollama_exe() is None


class TestStartOllamaIfPossible:
    @patch("src.agent.ollama_client._check_ollama", return_value=True)
    def test_returns_true_if_already_running(self, mock_check):
        assert _start_ollama_if_possible() is True
        mock_check.assert_called_once()

    @patch("src.agent.ollama_client._check_ollama", return_value=False)
    @patch("src.agent.ollama_client._find_ollama_exe", return_value=None)
    def test_returns_false_if_no_exe(self, mock_find, mock_check):
        assert _start_ollama_if_possible() is False

    @patch("src.agent.ollama_client._check_ollama", side_effect=[False, True])
    @patch("src.agent.ollama_client._find_ollama_exe", return_value="/usr/bin/ollama")
    @patch("src.agent.ollama_client.subprocess.Popen")
    @patch("src.agent.ollama_client.time")
    def test_starts_and_becomes_available(self, mock_time, mock_popen, mock_find, mock_check):
        import src.agent.ollama_client as mod

        old_proc = mod._ollama_process
        try:
            mod._ollama_process = None
            mock_time.time.side_effect = [0, 1]
            mock_time.sleep = MagicMock()
            fake_proc = MagicMock()
            mock_popen.return_value = fake_proc

            assert _start_ollama_if_possible(timeout_sec=5) is True
            mock_popen.assert_called_once_with(
                ["/usr/bin/ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            assert mod._ollama_process is fake_proc
        finally:
            mod._ollama_process = old_proc

    @patch("src.agent.ollama_client._check_ollama", return_value=False)
    @patch("src.agent.ollama_client._find_ollama_exe", return_value="/usr/bin/ollama")
    @patch("src.agent.ollama_client.subprocess.Popen", side_effect=OSError("boom"))
    def test_returns_false_on_popen_failure(self, mock_popen, mock_find, mock_check):
        assert _start_ollama_if_possible() is False

    @patch("src.agent.ollama_client._check_ollama", side_effect=[False, False, False])
    @patch("src.agent.ollama_client._find_ollama_exe", return_value="/usr/bin/ollama")
    @patch("src.agent.ollama_client.subprocess.Popen")
    @patch("src.agent.ollama_client.time")
    def test_times_out(self, mock_time, mock_popen, mock_find, mock_check):
        import src.agent.ollama_client as mod

        old_proc = mod._ollama_process
        try:
            mod._ollama_process = None
            mock_time.time.side_effect = [0, 1, 2, 25]
            mock_time.sleep = MagicMock()
            mock_popen.return_value = MagicMock()

            assert _start_ollama_if_possible(timeout_sec=20) is False
            assert mock_check.call_count >= 3
        finally:
            mod._ollama_process = old_proc


class TestListLocalModels:
    @patch("src.agent.ollama_client.urllib.request.urlopen")
    def test_returns_model_names(self, mock_urlopen):
        body = json.dumps({"models": [{"name": "qwen2.5:7b"}, {"name": "llama3:8b"}]}).encode()
        mock_urlopen.return_value = _mock_response(200, body)
        assert _list_local_models() == ["qwen2.5:7b", "llama3:8b"]

    @patch("src.agent.ollama_client.urllib.request.urlopen")
    def test_returns_empty_list_on_empty_models(self, mock_urlopen):
        body = json.dumps({"models": []}).encode()
        mock_urlopen.return_value = _mock_response(200, body)
        assert _list_local_models() == []

    @patch("src.agent.ollama_client.urllib.request.urlopen")
    def test_returns_empty_on_missing_key(self, mock_urlopen):
        body = json.dumps({}).encode()
        mock_urlopen.return_value = _mock_response(200, body)
        assert _list_local_models() == []

    @patch("src.agent.ollama_client.urllib.request.urlopen", side_effect=Exception("fail"))
    def test_returns_empty_on_exception(self, mock_urlopen):
        assert _list_local_models() == []


class TestResolveModel:
    @patch("src.agent.ollama_client._list_local_models", return_value=["qwen2.5:7b", "llama3:8b"])
    def test_returns_requested_if_installed(self, mock_list):
        assert _resolve_model("qwen2.5:7b") == "qwen2.5:7b"

    @patch("src.agent.ollama_client._list_local_models", return_value=["qwen2.5:3b", "llama3:8b"])
    def test_falls_back_to_prefix_match(self, mock_list):
        assert _resolve_model("qwen2.5:7b") == "qwen2.5:3b"

    @patch("src.agent.ollama_client._list_local_models", return_value=["llama3:8b", "gemma:2b"])
    def test_falls_back_to_first_available(self, mock_list):
        assert _resolve_model("qwen2.5:7b") == "llama3:8b"

    @patch("src.agent.ollama_client._list_local_models", return_value=[])
    def test_returns_requested_if_no_models(self, mock_list):
        assert _resolve_model("qwen2.5:7b") == "qwen2.5:7b"

    @patch("src.agent.ollama_client._list_local_models", return_value=["qwen2.5-coder:7b"])
    def test_prefix_match_uses_base_name(self, mock_list):
        assert _resolve_model("qwen2.5-coder") == "qwen2.5-coder:7b"


class TestPullModelIfMissing:
    @patch("src.agent.ollama_client._find_ollama_exe", return_value=None)
    def test_returns_false_if_no_exe(self, mock_find):
        assert _pull_model_if_missing("qwen2.5:7b") is False

    @patch("src.agent.ollama_client._find_ollama_exe", return_value="/usr/bin/ollama")
    @patch("src.agent.ollama_client.subprocess.run")
    def test_returns_true_if_model_already_in_ls(self, mock_run, mock_find):
        ls_result = MagicMock()
        ls_result.returncode = 0
        ls_result.stdout = "qwen2.5:7b    4.7 GB    2024-01-01"
        mock_run.return_value = ls_result
        assert _pull_model_if_missing("qwen2.5:7b") is True
        mock_run.assert_called_once()

    @patch("src.agent.ollama_client._find_ollama_exe", return_value="/usr/bin/ollama")
    @patch("src.agent.ollama_client.subprocess.run")
    def test_pulls_model_when_missing(self, mock_run, mock_find):
        ls_result = MagicMock()
        ls_result.returncode = 0
        ls_result.stdout = "other-model    4 GB    2024-01-01"
        pull_result = MagicMock()
        pull_result.returncode = 0
        mock_run.side_effect = [ls_result, pull_result]
        assert _pull_model_if_missing("qwen2.5:7b") is True
        assert mock_run.call_count == 2

    @patch("src.agent.ollama_client._find_ollama_exe", return_value="/usr/bin/ollama")
    @patch("src.agent.ollama_client.subprocess.run")
    def test_returns_false_on_pull_failure(self, mock_run, mock_find):
        ls_result = MagicMock()
        ls_result.returncode = 0
        ls_result.stdout = ""
        pull_result = MagicMock()
        pull_result.returncode = 1
        mock_run.side_effect = [ls_result, pull_result]
        assert _pull_model_if_missing("qwen2.5:7b") is False

    @patch("src.agent.ollama_client._find_ollama_exe", return_value="/usr/bin/ollama")
    @patch("src.agent.ollama_client.subprocess.run", side_effect=Exception("subprocess error"))
    def test_returns_false_on_exception(self, mock_run, mock_find):
        assert _pull_model_if_missing("qwen2.5:7b") is False

    @patch("src.agent.ollama_client._find_ollama_exe", return_value="/usr/bin/ollama")
    @patch("src.agent.ollama_client.subprocess.run")
    def test_returns_false_if_ls_nonzero_and_pull_fails(self, mock_run, mock_find):
        ls_result = MagicMock()
        ls_result.returncode = 1
        ls_result.stdout = ""
        pull_result = MagicMock()
        pull_result.returncode = 1
        mock_run.side_effect = [ls_result, pull_result]
        assert _pull_model_if_missing("qwen2.5:7b") is False


class TestOllamaClientInit:
    @patch("src.agent.ollama_client._resolve_model", return_value="qwen2.5:7b")
    def test_default_model_resolved(self, mock_resolve):
        c = OllamaClient()
        assert c.model == "qwen2.5:7b"
        mock_resolve.assert_called_once_with("qwen2.5:7b")

    @patch("src.agent.ollama_client._resolve_model", return_value="llama3:8b")
    def test_custom_model_resolved(self, mock_resolve):
        c = OllamaClient(model="llama3:8b")
        assert c.model == "llama3:8b"
        mock_resolve.assert_called_once_with("llama3:8b")

    @patch("src.agent.ollama_client._resolve_model", return_value="qwen2.5:7b")
    def test_default_base_url(self, mock_resolve):
        c = OllamaClient()
        assert c.base_url == OLLAMA_BASE

    @patch("src.agent.ollama_client._resolve_model", return_value="qwen2.5:7b")
    def test_custom_base_url_trailing_slash_stripped(self, mock_resolve):
        c = OllamaClient(base_url="http://host:11434/")
        assert c.base_url == "http://host:11434"

    @patch("src.agent.ollama_client._resolve_model", return_value="qwen2.5:7b")
    def test_custom_base_url_no_trailing_slash(self, mock_resolve):
        c = OllamaClient(base_url="http://host:11434")
        assert c.base_url == "http://host:11434"


class TestOllamaClientIsAvailable:
    @patch("src.agent.ollama_client._check_ollama", return_value=True)
    def test_available_when_ollama_running(self, mock_check):
        c = OllamaClient.__new__(OllamaClient)
        c.model = "test"
        c.base_url = OLLAMA_BASE
        assert c.is_available() is True

    @patch("src.agent.ollama_client._check_ollama", return_value=False)
    @patch("src.agent.ollama_client._start_ollama_if_possible", return_value=True)
    def test_starts_ollama_when_not_running(self, mock_start, mock_check):
        c = OllamaClient.__new__(OllamaClient)
        c.model = "test"
        c.base_url = OLLAMA_BASE
        assert c.is_available() is True

    @patch("src.agent.ollama_client._check_ollama", return_value=False)
    @patch("src.agent.ollama_client._start_ollama_if_possible", return_value=False)
    def test_unavailable_when_cannot_start(self, mock_start, mock_check):
        c = OllamaClient.__new__(OllamaClient)
        c.model = "test"
        c.base_url = OLLAMA_BASE
        assert c.is_available() is False


class TestOllamaClientGenerate:
    @patch("src.agent.ollama_client.urllib.request.urlopen")
    def test_successful_generation(self, mock_urlopen):
        body = json.dumps({"response": "Olá mundo"}).encode()
        mock_urlopen.return_value = _mock_response(200, body)
        c = OllamaClient.__new__(OllamaClient)
        c.model = "test-model"
        c.base_url = OLLAMA_BASE
        result = c.generate("Qual a média?")
        assert result == "Olá mundo"

    @patch("src.agent.ollama_client.urllib.request.urlopen")
    def test_successful_generation_with_system(self, mock_urlopen):
        body = json.dumps({"response": "resposta"}).encode()
        mock_urlopen.return_value = _mock_response(200, body)
        c = OllamaClient.__new__(OllamaClient)
        c.model = "test-model"
        c.base_url = OLLAMA_BASE
        result = c.generate("Pergunta", system="Você é o Fennec.")
        assert result == "resposta"

    @patch("src.agent.ollama_client.urllib.request.urlopen", side_effect=Exception("conn refused"))
    def test_raises_runtime_error_on_failure(self, mock_urlopen):
        c = OllamaClient.__new__(OllamaClient)
        c.model = "test-model"
        c.base_url = OLLAMA_BASE
        with pytest.raises(RuntimeError, match=r"\[E018\]"):
            c.generate("test")

    @patch("src.agent.ollama_client._pull_model_if_missing", return_value=True)
    @patch("src.agent.ollama_client.urllib.request.urlopen")
    def test_auto_pull_on_not_found_error(self, mock_urlopen, mock_pull):
        not_found_body = json.dumps({"error": "model test-model not found"}).encode()
        success_body = json.dumps({"response": "pulled answer"}).encode()
        r1 = _mock_response(200, not_found_body)
        r2 = _mock_response(200, success_body)
        mock_urlopen.side_effect = [r1, r2]
        c = OllamaClient.__new__(OllamaClient)
        c.model = "test-model"
        c.base_url = OLLAMA_BASE
        result = c.generate("test")
        assert result == "pulled answer"
        mock_pull.assert_called_once_with("test-model")

    @patch("src.agent.ollama_client._pull_model_if_missing", return_value=False)
    @patch("src.agent.ollama_client.urllib.request.urlopen")
    def test_no_retry_if_pull_fails(self, mock_urlopen, mock_pull):
        not_found_body = json.dumps({"error": "model test-model not found", "response": ""}).encode()
        mock_urlopen.return_value = _mock_response(200, not_found_body)
        c = OllamaClient.__new__(OllamaClient)
        c.model = "test-model"
        c.base_url = OLLAMA_BASE
        result = c.generate("test")
        assert result == ""

    @patch("src.agent.ollama_client.urllib.request.urlopen")
    def test_non_not_found_error_returns_empty_response(self, mock_urlopen):
        err_body = json.dumps({"error": "OOM killed", "response": ""}).encode()
        mock_urlopen.return_value = _mock_response(200, err_body)
        c = OllamaClient.__new__(OllamaClient)
        c.model = "test-model"
        c.base_url = OLLAMA_BASE
        result = c.generate("test")
        assert result == ""

    @patch("src.agent.ollama_client._pull_model_if_missing", return_value=True)
    @patch("src.agent.ollama_client.urllib.request.urlopen")
    def test_non_not_found_error_does_not_trigger_pull(self, mock_urlopen, mock_pull):
        err_body = json.dumps({"error": "OOM killed", "response": ""}).encode()
        mock_urlopen.return_value = _mock_response(200, err_body)
        c = OllamaClient.__new__(OllamaClient)
        c.model = "test-model"
        c.base_url = OLLAMA_BASE
        c.generate("test")
        mock_pull.assert_not_called()

    @patch("src.agent.ollama_client.urllib.request.urlopen")
    def test_whitespace_trimmed(self, mock_urlopen):
        body = json.dumps({"response": "  resposta  \n  "}).encode()
        mock_urlopen.return_value = _mock_response(200, body)
        c = OllamaClient.__new__(OllamaClient)
        c.model = "test-model"
        c.base_url = OLLAMA_BASE
        assert c.generate("test") == "resposta"

    @patch("src.agent.ollama_client.urllib.request.urlopen")
    def test_empty_response_returns_empty_string(self, mock_urlopen):
        body = json.dumps({"response": ""}).encode()
        mock_urlopen.return_value = _mock_response(200, body)
        c = OllamaClient.__new__(OllamaClient)
        c.model = "test-model"
        c.base_url = OLLAMA_BASE
        assert c.generate("test") == ""

    @patch("src.agent.ollama_client.urllib.request.urlopen")
    def test_missing_response_key_returns_empty(self, mock_urlopen):
        body = json.dumps({}).encode()
        mock_urlopen.return_value = _mock_response(200, body)
        c = OllamaClient.__new__(OllamaClient)
        c.model = "test-model"
        c.base_url = OLLAMA_BASE
        assert c.generate("test") == ""

    @patch("src.agent.ollama_client.urllib.request.urlopen")
    def test_custom_max_tokens_in_payload(self, mock_urlopen):
        body = json.dumps({"response": "ok"}).encode()
        mock_urlopen.return_value = _mock_response(200, body)
        c = OllamaClient.__new__(OllamaClient)
        c.model = "test-model"
        c.base_url = OLLAMA_BASE
        c.generate("test", max_tokens=512)
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        payload = json.loads(req.data.decode())
        assert payload["options"]["num_predict"] == 512

    @patch("src.agent.ollama_client.urllib.request.urlopen")
    def test_system_omitted_when_none(self, mock_urlopen):
        body = json.dumps({"response": "ok"}).encode()
        mock_urlopen.return_value = _mock_response(200, body)
        c = OllamaClient.__new__(OllamaClient)
        c.model = "test-model"
        c.base_url = OLLAMA_BASE
        c.generate("test", system=None)
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        payload = json.loads(req.data.decode())
        assert "system" not in payload

    @patch("src.agent.ollama_client.urllib.request.urlopen")
    def test_default_max_tokens(self, mock_urlopen):
        body = json.dumps({"response": "ok"}).encode()
        mock_urlopen.return_value = _mock_response(200, body)
        c = OllamaClient.__new__(OllamaClient)
        c.model = "test-model"
        c.base_url = OLLAMA_BASE
        c.generate("test")
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        payload = json.loads(req.data.decode())
        assert payload["options"]["num_predict"] == 2048


class TestCleanupOllama:
    def test_cleanup_terminates_process(self):
        import src.agent.ollama_client as mod

        old_proc = mod._ollama_process
        fake_proc = MagicMock()
        try:
            mod._ollama_process = fake_proc
            _cleanup_ollama()
            fake_proc.terminate.assert_called_once()
            fake_proc.wait.assert_called_once_with(timeout=5)
            assert mod._ollama_process is None
        finally:
            mod._ollama_process = old_proc

    def test_cleanup_noop_when_none(self):
        import src.agent.ollama_client as mod

        old_proc = mod._ollama_process
        try:
            mod._ollama_process = None
            _cleanup_ollama()
            assert mod._ollama_process is None
        finally:
            mod._ollama_process = old_proc

    def test_cleanup_survives_terminate_exception(self):
        import src.agent.ollama_client as mod

        old_proc = mod._ollama_process
        fake_proc = MagicMock()
        fake_proc.terminate.side_effect = OSError("already dead")
        try:
            mod._ollama_process = fake_proc
            _cleanup_ollama()
            assert mod._ollama_process is None
        finally:
            mod._ollama_process = old_proc

    def test_cleanup_survives_wait_timeout(self):
        import src.agent.ollama_client as mod

        old_proc = mod._ollama_process
        fake_proc = MagicMock()
        fake_proc.wait.side_effect = subprocess.TimeoutExpired("ollama", 5)
        try:
            mod._ollama_process = fake_proc
            _cleanup_ollama()
            assert mod._ollama_process is None
        finally:
            mod._ollama_process = old_proc


class TestCleanupOllamaThreadSafety:
    def test_cleanup_acquires_lock(self):
        import src.agent.ollama_client as mod

        old_proc = mod._ollama_process
        fake_proc = MagicMock()
        try:
            mod._ollama_process = fake_proc
            with patch.object(mod, "_ollama_lock", wraps=mod._ollama_lock):
                _cleanup_ollama()
        finally:
            mod._ollama_process = old_proc

    def test_cleanup_blocks_concurrent_access(self):
        import src.agent.ollama_client as mod

        old_proc = mod._ollama_process
        fake_proc = MagicMock()
        acquired = threading.Event()
        blocked = threading.Event()

        def slow_wait(timeout=None):
            acquired.set()
            blocked.wait(timeout=2)
            return 0

        fake_proc.wait = slow_wait
        try:
            mod._ollama_process = fake_proc
            t = threading.Thread(target=_cleanup_ollama)
            t.start()
            acquired.wait(timeout=2)
            assert mod._ollama_lock.locked()
            blocked.set()
            t.join(timeout=5)
            assert mod._ollama_process is None
        finally:
            mod._ollama_process = old_proc
