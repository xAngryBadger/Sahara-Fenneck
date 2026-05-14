"""Tests for NimClient (NVIDIA NIM backend)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from src.agent.nim_client import NimClient


@pytest.fixture
def nim():
    return NimClient(api_key="nvapi-test-key", model="meta/llama-3.1-70b-instruct")


class TestNimClientInit:
    def test_default_values(self):
        c = NimClient()
        assert c.api_key == ""
        assert c.model == "meta/llama-3.1-70b-instruct"
        assert c.base_url == "https://integrate.api.nvidia.com/v1"

    def test_custom_values(self):
        c = NimClient(api_key="k", model="m", base_url="https://custom/v1")
        assert c.api_key == "k"
        assert c.model == "m"
        assert c.base_url == "https://custom/v1"

    def test_trailing_slash_stripped(self):
        c = NimClient(base_url="https://host/v1/")
        assert c.base_url == "https://host/v1"


class TestNimClientAvailability:
    def test_unavailable_without_key(self):
        c = NimClient(api_key="")
        assert c.is_available() is False

    @patch("src.agent.nim_client.NimClient._get_client")
    def test_available_with_key_and_ping(self, mock_get):
        fake_client = MagicMock()
        mock_get.return_value = fake_client
        c = NimClient(api_key="nvapi-key")
        assert c.is_available() is True
        mock_get.assert_called()

    @patch("src.agent.nim_client.NimClient._get_client")
    def test_unavailable_on_init_error(self, mock_get):
        mock_get.side_effect = Exception("connection error")
        c = NimClient(api_key="nvapi-key")
        assert c.is_available() is False


class TestNimClientGenerate:
    @patch("src.agent.nim_client.NimClient._get_client")
    def test_successful_generation(self, mock_get):
        fake_response = MagicMock()
        fake_response.choices = [MagicMock()]
        fake_response.choices[0].message.content = "Resposta do modelo"
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = fake_response
        mock_get.return_value = fake_client

        c = NimClient(api_key="nvapi-key")
        result = c.generate("Qual a média?", system="Você é o Fennec.")
        assert result == "Resposta do modelo"
        fake_client.chat.completions.create.assert_called_once()
        call_kwargs = fake_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "meta/llama-3.1-70b-instruct"
        assert call_kwargs.kwargs["messages"][0]["role"] == "system"
        assert call_kwargs.kwargs["messages"][1]["role"] == "user"

    @patch("src.agent.nim_client.NimClient._get_client")
    def test_generation_without_system(self, mock_get):
        fake_response = MagicMock()
        fake_response.choices = [MagicMock()]
        fake_response.choices[0].message.content = "Resposta"
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = fake_response
        mock_get.return_value = fake_client

        c = NimClient(api_key="nvapi-key")
        c.generate("Pergunta")
        messages = fake_client.chat.completions.create.call_args.kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    def test_generation_without_api_key(self):
        c = NimClient(api_key="")
        result = c.generate("test")
        assert "[E023]" in result

    @patch("src.agent.nim_client.NimClient._get_client")
    def test_auth_error(self, mock_get):
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = Exception("401 Unauthorized - invalid api_key")
        mock_get.return_value = fake_client

        c = NimClient(api_key="bad-key")
        result = c.generate("test")
        assert "[E023]" in result

    @patch("src.agent.nim_client.NimClient._get_client")
    def test_generic_request_error(self, mock_get):
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = Exception("503 Service Unavailable")
        mock_get.return_value = fake_client

        c = NimClient(api_key="nvapi-key")
        result = c.generate("test")
        assert "[E024]" in result

    def test_missing_openai_package(self):
        c = NimClient(api_key="nvapi-key")
        with patch.dict("sys.modules", {"openai": None}):
            result = c.generate("test")
            assert "[E022]" in result or "openai" in result.lower()

    @patch("src.agent.nim_client.NimClient._get_client")
    def test_empty_response_content(self, mock_get):
        fake_response = MagicMock()
        fake_response.choices = [MagicMock()]
        fake_response.choices[0].message.content = None
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = fake_response
        mock_get.return_value = fake_client

        c = NimClient(api_key="nvapi-key")
        result = c.generate("test")
        assert result == ""

    @patch("src.agent.nim_client.NimClient._get_client")
    def test_whitespace_trimmed(self, mock_get):
        fake_response = MagicMock()
        fake_response.choices = [MagicMock()]
        fake_response.choices[0].message.content = "  resposta  \n  "
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = fake_response
        mock_get.return_value = fake_client

        c = NimClient(api_key="nvapi-key")
        result = c.generate("test")
        assert result == "resposta"

    @patch("src.agent.nim_client.NimClient._get_client")
    def test_max_tokens_forwarded(self, mock_get):
        fake_response = MagicMock()
        fake_response.choices = [MagicMock()]
        fake_response.choices[0].message.content = "ok"
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = fake_response
        mock_get.return_value = fake_client

        c = NimClient(api_key="nvapi-key")
        c.generate("test", max_tokens=512)
        call_kwargs = fake_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 512
