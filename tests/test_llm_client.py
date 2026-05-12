"""Tests for LLMClient protocol, create_client factory, and backend switching."""
from __future__ import annotations

from unittest.mock import patch

from src.agent.llm_client import LLMClient, create_client
from src.agent.ollama_client import OllamaClient


class TestLLMClientProtocol:
    def test_ollama_satisfies_protocol(self):
        client = OllamaClient(model="qwen2.5:7b")
        assert isinstance(client, LLMClient)

    def test_protocol_requires_methods(self):
        class Incomplete:
            def is_available(self) -> bool:
                return True

        assert not isinstance(Incomplete(), LLMClient)


class TestCreateClient:
    @patch("src.agent.ollama_client.OllamaClient")
    def test_ollama_backend(self, MockOllama):
        settings = {"llm_backend": "ollama", "model": "qwen2.5:7b"}
        create_client(settings)
        MockOllama.assert_called_once_with(model="qwen2.5:7b")

    @patch("src.agent.nim_client.NimClient")
    @patch("src.integrations.token_store.get_nim_api_key", return_value="nvapi-test-key")
    def test_nim_backend_with_stored_key(self, mock_get_key, MockNim):
        settings = {
            "llm_backend": "nim",
            "nim_base_url": "https://integrate.api.nvidia.com/v1",
            "nim_model": "meta/llama-3.1-70b-instruct",
        }
        create_client(settings)
        MockNim.assert_called_once_with(
            api_key="nvapi-test-key",
            model="meta/llama-3.1-70b-instruct",
            base_url="https://integrate.api.nvidia.com/v1",
        )

    @patch("src.agent.nim_client.NimClient")
    @patch("src.integrations.token_store.get_nim_api_key", return_value="")
    @patch.dict("os.environ", {"NVIDIA_API_KEY": "env-key"})
    def test_nim_backend_with_env_key(self, mock_get_key, MockNim):
        settings = {"llm_backend": "nim"}
        create_client(settings)
        MockNim.assert_called_once_with(
            api_key="env-key",
            model="meta/llama-3.1-70b-instruct",
            base_url="https://integrate.api.nvidia.com/v1",
        )

    @patch("src.agent.ollama_client.OllamaClient")
    def test_default_backend_is_ollama(self, MockOllama):
        settings = {}
        create_client(settings)
        MockOllama.assert_called_once_with(model="qwen2.5:7b")

    @patch("src.agent.ollama_client.OllamaClient")
    def test_case_insensitive_backend(self, MockOllama):
        settings = {"llm_backend": "OLLAMA", "model": "phi3:mini"}
        create_client(settings)
        MockOllama.assert_called_once_with(model="phi3:mini")
